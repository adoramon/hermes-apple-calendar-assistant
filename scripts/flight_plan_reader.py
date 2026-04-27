"""Read future flights from the protected Apple Calendar flight calendar."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

try:
    from . import calendar_ops, flight_parser, util
except ImportError:  # Allows running as: python3 scripts/flight_plan_reader.py ...
    import calendar_ops  # type: ignore
    import flight_parser  # type: ignore
    import util  # type: ignore


FLIGHT_CALENDAR = "飞行计划"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
FLIGHT_SEEN_PATH = PROJECT_ROOT / "data" / "flight_seen.json"
CITY_HINTS = ("北京", "上海", "广州", "深圳", "杭州", "南京", "长沙", "成都", "重庆", "西安", "厦门", "香港")


def _result(ok: bool, data: Any = None, error: str | None = None) -> dict[str, Any]:
    return {"ok": ok, "data": data, "error": error}


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _city_from_airport(value: Any) -> str:
    text = _clean(value)
    for city in CITY_HINTS:
        if text.startswith(city):
            return city
    return re.sub(
        r"(T\d|首都|大兴|虹桥|浦东|白云|宝安|双流|天府|萧山|禄口|高崎|江北|新郑|咸阳|黄花|机场)$",
        "",
        text,
    )[:4]


def _flight_from_event(event: dict[str, Any]) -> dict[str, Any] | None:
    parsed = flight_parser.parse_flight_event(event)
    if not parsed.get("ok"):
        return None
    data = parsed.get("data") or {}
    if not data.get("is_flight_event"):
        return None
    departure_airport = _clean(data.get("departure_airport_raw"))
    arrival_airport = _clean(data.get("arrival_airport_raw"))
    return {
        "title": event.get("title", ""),
        "start": event.get("start", ""),
        "end": event.get("end", ""),
        "location": event.get("location", ""),
        "flight_no": data.get("flight_no") or "",
        "departure_city": _city_from_airport(departure_airport),
        "arrival_city": _city_from_airport(arrival_airport),
        "departure_airport": departure_airport,
        "arrival_airport": arrival_airport,
        "departure_terminal": data.get("departure_terminal") or "",
        "arrival_terminal": data.get("arrival_terminal") or "",
        "source": FLIGHT_CALENDAR,
    }


def _events_from_seen_store() -> list[dict[str, Any]]:
    raw = util.load_json(FLIGHT_SEEN_PATH, {"events": {}})
    events = raw.get("events", {}) if isinstance(raw, dict) else {}
    output = []
    if not isinstance(events, dict):
        return output
    for record in events.values():
        if not isinstance(record, dict) or record.get("calendar") != FLIGHT_CALENDAR:
            continue
        output.append(
            {
                "title": record.get("title", ""),
                "start": record.get("start", ""),
                "end": record.get("end", ""),
                "location": record.get("location_written", ""),
            }
        )
    return output


def list_flights(days: int = 30) -> dict[str, Any]:
    if days <= 0:
        return _result(False, error="days must be greater than 0")
    now = datetime.now()
    start = now.isoformat(timespec="seconds")
    end = (now + timedelta(days=days)).isoformat(timespec="seconds")
    events_result = calendar_ops.list_events(FLIGHT_CALENDAR, start_date=start, end_date=end)
    events_source = "Apple Calendar"
    if not events_result.get("ok"):
        events_result = _result(True, data={"events": _events_from_seen_store()})
        events_source = "flight_seen.json"

    flights = []
    for event in events_result.get("data", {}).get("events", []):
        if not isinstance(event, dict):
            continue
        flight = _flight_from_event(event)
        if flight:
            flight["reader_source"] = events_source
            flights.append(flight)
    return _result(True, data={"calendar": FLIGHT_CALENDAR, "reader_source": events_source, "flights": flights})


def diagnose(days: int = 30) -> dict[str, Any]:
    if days <= 0:
        return _result(False, error="days must be greater than 0")
    now = datetime.now()
    start = now.isoformat(timespec="seconds")
    end = (now + timedelta(days=days)).isoformat(timespec="seconds")
    errors: list[str] = []
    events_result = calendar_ops.list_events(FLIGHT_CALENDAR, start_date=start, end_date=end)
    apple_script_ok = bool(events_result.get("ok"))
    events: list[dict[str, Any]] = []
    if apple_script_ok:
        raw_events = events_result.get("data", {}).get("events", [])
        events = [item for item in raw_events if isinstance(item, dict)]
    else:
        errors.append(str(events_result.get("error") or "AppleScript 查询飞行计划失败"))

    parse_success_count = 0
    parse_failed_count = 0
    for event in events:
        if _flight_from_event(event):
            parse_success_count += 1
        else:
            parse_failed_count += 1

    data = {
        "calendar": FLIGHT_CALENDAR,
        "calendar_found": apple_script_ok,
        "permission_ok": apple_script_ok,
        "apple_script_ok": apple_script_ok,
        "event_count": len(events),
        "parse_success_count": parse_success_count,
        "parse_failed_count": parse_failed_count,
        "errors": errors,
    }
    return _result(True, data=data, error=None if apple_script_ok else errors[0])


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read future flights from 飞行计划.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    list_parser = subparsers.add_parser("list")
    list_parser.add_argument("--days", type=int, default=30)
    diagnose_parser = subparsers.add_parser("diagnose")
    diagnose_parser.add_argument("--days", type=int, default=30)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "list":
        result = list_flights(days=args.days)
    elif args.command == "diagnose":
        result = diagnose(days=args.days)
    else:
        raise AssertionError(args.command)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
