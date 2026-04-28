"""Route natural-language schedule queries to Calendar and Trip readers."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any

try:
    from . import assistant_persona, calendar_ops, settings, util
except ImportError:  # Allows running as: python3 scripts/schedule_query_router.py ...
    import assistant_persona  # type: ignore
    import calendar_ops  # type: ignore
    import settings  # type: ignore
    import util  # type: ignore


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TRIP_DRAFTS_PATH = PROJECT_ROOT / "data" / "trip_drafts.json"
CITY_HINTS = ("北京", "上海", "广州", "深圳", "杭州", "南京", "长沙", "成都", "重庆", "西安", "厦门", "香港", "东京")


def _result(ok: bool, data: Any = None, error: str | None = None) -> dict[str, Any]:
    return {"ok": ok, "data": data, "error": error}


def _read_trips() -> dict[str, Any]:
    raw = util.load_json(TRIP_DRAFTS_PATH, {"trips": {}})
    if not isinstance(raw, dict):
        return {"trips": {}}
    if not isinstance(raw.get("trips"), dict):
        raw["trips"] = {}
    return raw


def _day_window(day: date) -> tuple[datetime, datetime]:
    return datetime.combine(day, time.min), datetime.combine(day + timedelta(days=1), time.min)


def _week_window(today: date, next_week: bool = False) -> tuple[datetime, datetime]:
    monday = today - timedelta(days=today.weekday())
    if next_week:
        monday += timedelta(days=7)
    return datetime.combine(monday, time.min), datetime.combine(monday + timedelta(days=7), time.min)


def _month_window(today: date) -> tuple[datetime, datetime]:
    start = today.replace(day=1)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return datetime.combine(start, time.min), datetime.combine(end, time.min)


def _extract_city(text: str) -> str:
    for city in CITY_HINTS:
        if city in text:
            return city
    return ""


def _today_remaining_window(now: datetime) -> tuple[datetime, datetime]:
    return now.replace(microsecond=0), datetime.combine(now.date() + timedelta(days=1), time.min)


def _parse_window(text: str, now: datetime) -> tuple[str, datetime, datetime]:
    today = now.date()
    if "明天" in text:
        start, end = _day_window(today + timedelta(days=1))
        return "tomorrow_schedule", start, end
    if "今天" in text or "今日" in text:
        start, end = _today_remaining_window(now)
        return "today_schedule", start, end
    if "下周" in text:
        start, end = _week_window(today, next_week=True)
        return "next_week_schedule", start, end
    if "本周" in text or "这周" in text:
        start, end = _week_window(today, next_week=False)
        return "week_schedule", start, end
    if "这个月" in text or "本月" in text:
        start, end = _month_window(today)
        return "month_schedule", start, end
    start, end = _today_remaining_window(now)
    return "today_schedule", start, end


def _is_trip_query(text: str) -> bool:
    return any(word in text for word in ("出差", "旅行", "行程", "什么时候去")) or bool(_extract_city(text))


def _is_meeting_query(text: str) -> bool:
    return any(word in text for word in ("会", "会议", "拜访", "见客户"))


def _event_matches_query(event: dict[str, Any], text: str) -> bool:
    if not _is_meeting_query(text):
        return True
    title = str(event.get("title") or "")
    notes = str(event.get("notes") or "")
    return any(word in title or word in notes for word in ("会", "会议", "拜访", "客户", "见"))


def _calendar_events(start: datetime, end: datetime, text: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    events: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for calendar in settings.get_read_calendars():
        result = calendar_ops.list_events(calendar, start_date=start, end_date=end)
        if not result.get("ok"):
            errors.append({"calendar": calendar, "error": result.get("error")})
            continue
        for event in result.get("data", {}).get("events", []):
            if not isinstance(event, dict) or not _event_matches_query(event, text):
                continue
            item = dict(event)
            item["calendar"] = calendar
            item["item_type"] = "calendar_event"
            events.append(item)
    events.sort(key=lambda item: str(item.get("start", "")))
    return events, errors


def _date_from_trip_value(value: Any) -> date | None:
    parsed = assistant_persona.parse_datetime(value)
    if parsed:
        return parsed.date()
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value + "T00:00:00").date()
        except ValueError:
            return None
    return None


def _trip_overlaps(trip: dict[str, Any], start: datetime, end: datetime) -> bool:
    trip_start = _date_from_trip_value(trip.get("start_date"))
    trip_end = _date_from_trip_value(trip.get("end_date")) or trip_start
    if not trip_start or not trip_end:
        return False
    left = datetime.combine(trip_start, time.min)
    right = datetime.combine(trip_end + timedelta(days=1), time.min)
    return right > start and left < end


def _trip_matches_text(trip: dict[str, Any], text: str, city: str) -> bool:
    if city and city != str(trip.get("destination_city") or ""):
        return False
    if "出差" in text and str(trip.get("intent_type") or "") not in {"", "business_trip", "unknown"}:
        return False
    return True


def _trip_items(start: datetime, end: datetime, text: str) -> list[dict[str, Any]]:
    city = _extract_city(text)
    trips = []
    for trip in _read_trips().get("trips", {}).values():
        if not isinstance(trip, dict):
            continue
        if trip.get("status") not in {"draft", "confirmed"}:
            continue
        if not _trip_overlaps(trip, start, end):
            continue
        if not _trip_matches_text(trip, text, city):
            continue
        item = dict(trip)
        item["item_type"] = "trip"
        trips.append(item)
    trips.sort(key=lambda item: str(item.get("start_date", "")))
    return trips


def _summary(query_type: str, text: str, events: list[dict[str, Any]], trips: list[dict[str, Any]], errors: list[dict[str, Any]]) -> str:
    if query_type in {"city_trip_query", "trip_query"}:
        return assistant_persona.format_trip_summary(trips, query_text=text, errors=errors)
    if query_type == "today_schedule":
        return assistant_persona.format_today_schedule(events, trips, errors=errors)
    if query_type == "tomorrow_schedule":
        return assistant_persona.format_tomorrow_schedule(events, trips, errors=errors)
    if query_type in {"week_schedule", "next_week_schedule", "month_schedule"}:
        if _is_trip_query(text) and trips:
            return assistant_persona.format_trip_summary(trips, query_text=text, errors=errors)
        return assistant_persona.format_week_schedule(events, trips, query_text=text, errors=errors)
    if trips:
        return assistant_persona.format_trip_summary(trips, query_text=text, errors=errors)
    return assistant_persona.format_week_schedule(events, trips, query_text=text, errors=errors)


def query(text: str) -> dict[str, Any]:
    if not isinstance(text, str) or not text.strip():
        return _result(False, error="text must be a non-empty string")
    now = datetime.now()
    query_type, start, end = _parse_window(text, now)
    events, errors = _calendar_events(start, end, text)
    trips = _trip_items(start, end, text) if _is_trip_query(text) else []
    if _is_trip_query(text) and _extract_city(text):
        query_type = "city_trip_query"
    elif _is_trip_query(text) and query_type not in {"today_schedule", "tomorrow_schedule"}:
        query_type = "trip_query"
    summary = _summary(query_type, text, events, trips, errors)
    return _result(
        True,
        data={
            "query_type": query_type,
            "range": {"start": start.isoformat(timespec="seconds"), "end": end.isoformat(timespec="seconds")},
            "summary": summary,
            "items": [*events, *trips],
            "errors": errors,
        },
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Route WeChat natural-language schedule queries.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    query_parser = subparsers.add_parser("query")
    query_parser.add_argument("--text", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "query":
        result = query(args.text)
    else:
        raise AssertionError(args.command)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
