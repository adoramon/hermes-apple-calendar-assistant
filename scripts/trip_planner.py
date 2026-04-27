"""Plan draft trips from one-sentence travel intent and confirm them into Calendar."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

try:
    from . import assistant_persona, calendar_ops, travel_intent_parser, util
except ImportError:  # Allows running as: python3 scripts/trip_planner.py ...
    import assistant_persona  # type: ignore
    import calendar_ops  # type: ignore
    import travel_intent_parser  # type: ignore
    import util  # type: ignore


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TRIP_DRAFTS_PATH = PROJECT_ROOT / "data" / "trip_drafts.json"
ALLOWED_CALENDARS = {"商务计划", "个人计划", "夫妻计划"}
PLANNER_NOTE = "由一句话出差模式生成，交通/酒店信息待订单确认。"


def _result(ok: bool, data: Any = None, error: str | None = None) -> dict[str, Any]:
    return {"ok": ok, "data": data, "error": error}


def _read_store() -> dict[str, Any]:
    raw = util.load_json(TRIP_DRAFTS_PATH, {"trips": {}})
    if not isinstance(raw, dict):
        return {"trips": {}}
    if not isinstance(raw.get("trips"), dict):
        raw["trips"] = {}
    return raw


def _write_store(store: dict[str, Any]) -> None:
    util.save_json_atomic(TRIP_DRAFTS_PATH, store)


def _combine(date_text: str | None, time_text: str) -> str:
    if not date_text:
        return ""
    return f"{date_text}T{time_text}:00"


def _trip_id(payload: dict[str, Any], text: str) -> str:
    seed = "|".join(
        [
            str(payload.get("destination_city") or "unknown"),
            str(payload.get("start_date") or "undated"),
            str(payload.get("intent_type") or "unknown"),
            text,
        ]
    )
    short = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:8]
    date_part = str(payload.get("start_date") or datetime.now().date().isoformat()).replace("-", "")
    city_part = str(payload.get("destination_city") or "unknown")
    return f"plan_{date_part}_{city_part}_{short}"


def _trip_title(plan: dict[str, Any]) -> str:
    destination = str(plan.get("destination_city") or "出行")
    intent_type = str(plan.get("intent_type") or "")
    if intent_type == "business_trip":
        return f"{destination}商务出行"
    if intent_type == "couple_trip":
        return f"{destination}夫妻出行"
    if intent_type == "personal_trip":
        return f"{destination}个人出行"
    return f"{destination}出行计划"


def _parse_date(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value + "T00:00:00")
    except ValueError:
        return None


def _recompute_dates(plan: dict[str, Any]) -> None:
    start_text = plan.get("start_date")
    start_dt = _parse_date(start_text)
    duration = plan.get("duration_days")
    same_day_return = bool(plan.get("same_day_return"))
    if start_dt and isinstance(duration, int) and duration > 0:
        plan["end_date"] = (start_dt + timedelta(days=duration - 1)).date().isoformat()
    elif start_dt and same_day_return:
        plan["end_date"] = start_dt.date().isoformat()


def _placeholder_event(event_type: str, title: str, start: str, end: str, location: str, notes: str) -> dict[str, Any]:
    return {
        "event_type": event_type,
        "title": title,
        "start": start,
        "end": end,
        "location": location,
        "notes": notes,
    }


def _build_events(plan: dict[str, Any]) -> list[dict[str, Any]]:
    start_date = plan.get("start_date")
    end_date = plan.get("end_date")
    destination = str(plan.get("destination_city") or "")
    origin = str(plan.get("origin_city") or "")
    purpose = str(plan.get("purpose") or "")
    intent_type = str(plan.get("intent_type") or "")
    duration = plan.get("duration_days")
    if not start_date or not destination or ("duration_days" in set(plan.get("missing_fields") or []) and not plan.get("same_day_return")):
        return []

    events: list[dict[str, Any]] = []
    if plan.get("same_day_return"):
        events.append(
            _placeholder_event(
                "outbound_placeholder",
                f"去程｜{origin} → {destination}",
                _combine(start_date, "09:00"),
                _combine(start_date, "11:30"),
                origin,
                "待确认具体航班/高铁",
            )
        )
        meeting_title = "客户拜访｜" + destination if intent_type == "business_trip" else "行程安排｜" + destination
        meeting_note = "根据用户意图生成，待确认具体客户与地点" if intent_type == "business_trip" else "根据用户意图生成，待确认具体安排"
        events.append(
            _placeholder_event(
                "meeting_placeholder",
                meeting_title,
                _combine(start_date, "14:00"),
                _combine(start_date, "16:00"),
                destination,
                meeting_note,
            )
        )
        events.append(
            _placeholder_event(
                "return_placeholder",
                f"返程｜{destination} → {origin}",
                _combine(start_date, "17:00"),
                _combine(start_date, "19:30"),
                destination,
                "待确认具体航班/高铁",
            )
        )
        return events

    if not isinstance(duration, int) or duration <= 0 or not end_date:
        return []

    events.append(
        _placeholder_event(
            "outbound_placeholder",
            f"去程｜{origin} → {destination}",
            _combine(start_date, "09:00"),
            _combine(start_date, "11:30"),
            origin,
            "待确认具体航班/高铁",
        )
    )

    if intent_type == "business_trip":
        events.append(
            _placeholder_event(
                "meeting_placeholder",
                f"客户拜访｜{destination}",
                _combine(start_date, "14:00"),
                _combine(start_date, "16:00"),
                destination,
                "根据用户意图生成，待确认具体客户与地点" if not purpose else f"根据用户意图生成：{purpose}，待确认具体客户与地点",
            )
        )
    else:
        events.append(
            _placeholder_event(
                "leisure_placeholder",
                f"出行安排｜{destination}",
                _combine(start_date, "14:00"),
                _combine(start_date, "17:00"),
                destination,
                "根据用户意图生成，待确认具体安排",
            )
        )

    if plan.get("needs_hotel"):
        events.append(
            _placeholder_event(
                "hotel_placeholder",
                f"住宿｜{destination}",
                _combine(start_date, "15:00"),
                _combine(end_date, "12:00"),
                destination,
                "待确认酒店订单",
            )
        )

    events.append(
        _placeholder_event(
            "return_placeholder",
            f"返程｜{destination} → {origin}",
            _combine(end_date, "17:00"),
            _combine(end_date, "19:30"),
            destination,
            "待确认具体航班/高铁",
        )
    )
    return events


def _refresh_plan(plan: dict[str, Any]) -> dict[str, Any]:
    missing = list(plan.get("parser_missing_fields") or plan.get("missing_fields") or [])
    plan["missing_fields"] = missing
    plan["needs_calendar_choice"] = False
    plan["events"] = _build_events(plan) if not missing else []
    if not plan["events"] and "events" not in plan["missing_fields"] and not missing:
        plan["missing_fields"] = list(plan["missing_fields"]) + ["events"]
    return plan


def _store_plan(plan: dict[str, Any]) -> dict[str, Any]:
    store = _read_store()
    store.setdefault("trips", {})[plan["trip_id"]] = plan
    _write_store(store)
    return store


def draft_trip(text: str) -> dict[str, Any]:
    parsed = travel_intent_parser.parse_intent(text)
    if not parsed.get("ok"):
        return parsed
    payload = dict(parsed.get("data") or {})
    trip_id = _trip_id(payload, text)
    plan = {
        "trip_id": trip_id,
        "source": "travel_intent",
        "status": "draft",
        "title": _trip_title(payload),
        "origin_city": payload.get("origin_city"),
        "destination_city": payload.get("destination_city"),
        "start_date": payload.get("start_date"),
        "end_date": payload.get("end_date"),
        "duration_days": payload.get("duration_days"),
        "purpose": payload.get("purpose"),
        "calendar": payload.get("suggested_calendar"),
        "suggested_calendar": payload.get("suggested_calendar"),
        "needs_calendar_choice": False,
        "intent_type": payload.get("intent_type"),
        "companions": payload.get("companions", []),
        "same_day_return": payload.get("same_day_return", False),
        "needs_hotel": payload.get("needs_hotel", False),
        "events": [],
        "linked_flights": {},
        "needs_flight": True,
        "flight_link_status": "flight_pending_sync",
        "planning_status": "planned_only",
        "missing_fields": list(payload.get("missing_fields") or []),
        "parser_missing_fields": list(payload.get("missing_fields") or []),
        "assumptions": list(payload.get("assumptions") or []),
        "confidence": payload.get("confidence"),
        "needs_confirmation": True,
        "source_text": text,
        "created_at": util.now_local_iso(),
        "updated_at": util.now_local_iso(),
    }
    _recompute_dates(plan)
    _refresh_plan(plan)
    _store_plan(plan)
    formatter = assistant_persona.format_travel_intent_missing_fields if plan["missing_fields"] else assistant_persona.format_travel_intent_draft
    return _result(
        True,
        data={
            "trip_id": trip_id,
            "trip": plan,
            "display_message": formatter(plan),
        },
    )


def show_trip(trip_id: str) -> dict[str, Any]:
    trip = _read_store().get("trips", {}).get(trip_id)
    if not trip:
        return _result(False, error=f"Trip not found: {trip_id}")
    formatter = assistant_persona.format_travel_intent_missing_fields if trip.get("missing_fields") else assistant_persona.format_travel_intent_draft
    return _result(True, data={"trip_id": trip_id, "trip": trip, "display_message": formatter(trip)})


def set_field(trip_id: str, field: str, value: str) -> dict[str, Any]:
    store = _read_store()
    trip = store.get("trips", {}).get(trip_id)
    if not trip:
        return _result(False, error=f"Trip not found: {trip_id}")
    if trip.get("status") != "draft":
        return _result(False, error=f"Trip is not draft: {trip_id}")

    if field == "calendar":
        if value not in ALLOWED_CALENDARS:
            return _result(False, error="calendar must be one of: 商务计划, 个人计划, 夫妻计划")
        trip["calendar"] = value
        trip["suggested_calendar"] = value
    elif field == "destination_city":
        trip["destination_city"] = value
        trip["title"] = _trip_title(trip)
    elif field == "origin_city":
        trip["origin_city"] = value
    elif field == "start_date":
        trip["start_date"] = value
    elif field == "end_date":
        trip["end_date"] = value
    elif field == "duration_days":
        try:
            trip["duration_days"] = int(value)
        except ValueError:
            return _result(False, error="duration_days must be an integer")
    elif field == "purpose":
        trip["purpose"] = value
    elif field == "same_day_return":
        trip["same_day_return"] = value.lower() in {"1", "true", "yes", "y", "是"}
    else:
        return _result(False, error=f"unsupported field: {field}")

    parser_missing = set(trip.get("parser_missing_fields") or [])
    if field in parser_missing:
        parser_missing.discard(field)
    if field == "same_day_return" and trip.get("same_day_return"):
        parser_missing.discard("duration_days")
        trip["duration_days"] = 1
    trip["parser_missing_fields"] = sorted(parser_missing)
    _recompute_dates(trip)
    _refresh_plan(trip)
    trip["updated_at"] = util.now_local_iso()
    store["trips"][trip_id] = trip
    _write_store(store)
    formatter = assistant_persona.format_travel_intent_missing_fields if trip.get("missing_fields") else assistant_persona.format_travel_intent_draft
    return _result(True, data={"trip_id": trip_id, "trip": trip, "display_message": formatter(trip)})


def _confirmed_title(event: dict[str, Any]) -> str:
    title = str(event.get("title") or "")
    mapping = {
        "outbound_placeholder": "去程计划",
        "hotel_placeholder": "住宿计划",
        "meeting_placeholder": "客户拜访计划",
        "leisure_placeholder": "出行安排计划",
        "return_placeholder": "返程计划",
    }
    prefix = mapping.get(str(event.get("event_type") or ""), "计划草稿")
    suffix = title.split("｜", 1)[1] if "｜" in title else title
    suffix = suffix.strip()
    return f"{prefix}｜{suffix}" if suffix else prefix


def _confirmed_notes(event: dict[str, Any]) -> str:
    original = str(event.get("notes") or "").strip()
    if original:
        return f"{PLANNER_NOTE}\n{original}"
    return PLANNER_NOTE


def confirm_trip(trip_id: str) -> dict[str, Any]:
    store = _read_store()
    trip = store.get("trips", {}).get(trip_id)
    if not trip:
        return _result(False, error=f"Trip not found: {trip_id}")
    if trip.get("status") != "draft":
        return _result(False, error=f"Trip is not draft: {trip_id}")
    if trip.get("calendar") not in ALLOWED_CALENDARS:
        return _result(False, data={"missing_fields": ["calendar"]}, error="trip_missing_calendar")
    if trip.get("missing_fields"):
        return _result(False, data={"missing_fields": trip.get("missing_fields")}, error="trip_missing_required_fields")

    skipped_types = {"outbound_placeholder", "return_placeholder"}
    events = [
        event
        for event in trip.get("events", [])
        if isinstance(event, dict) and event.get("event_type") not in skipped_types
    ]
    if not events:
        return _result(False, data={"missing_fields": ["events"]}, error="trip_has_no_events")

    results: list[dict[str, Any]] = []
    for event in events:
        create_result = calendar_ops.create_event(
            str(trip["calendar"]),
            _confirmed_title(event),
            str(event.get("start") or ""),
            str(event.get("end") or ""),
            location=str(event.get("location") or ""),
            notes=_confirmed_notes(event),
        )
        if create_result.get("ok"):
            results.append({"event": event, "status": "created", "calendar_result": create_result.get("data")})
        else:
            results.append({"event": event, "status": "failed", "error": create_result.get("error")})

    trip["status"] = "confirmed"
    trip["confirmed_at"] = util.now_local_iso()
    trip["results"] = results
    trip["updated_at"] = util.now_local_iso()
    store["trips"][trip_id] = trip
    _write_store(store)
    return _result(
        True,
        data={
            "trip_id": trip_id,
            "trip": trip,
            "results": results,
            "display_message": assistant_persona.format_travel_plan_confirmed(trip, results),
        },
    )


def cancel_trip(trip_id: str) -> dict[str, Any]:
    store = _read_store()
    trip = store.get("trips", {}).get(trip_id)
    if not trip:
        return _result(False, error=f"Trip not found: {trip_id}")
    trip["status"] = "cancelled"
    trip["cancelled_at"] = util.now_local_iso()
    trip["updated_at"] = util.now_local_iso()
    store["trips"][trip_id] = trip
    _write_store(store)
    return _result(True, data={"trip_id": trip_id, "status": "cancelled"})


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Draft and confirm one-sentence travel plans.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    draft = subparsers.add_parser("draft")
    draft.add_argument("--text", required=True)

    show = subparsers.add_parser("show")
    show.add_argument("--trip-id", required=True)

    set_parser = subparsers.add_parser("set-field")
    set_parser.add_argument("--trip-id", required=True)
    set_parser.add_argument("--field", required=True)
    set_parser.add_argument("--value", required=True)

    confirm = subparsers.add_parser("confirm")
    confirm.add_argument("--trip-id", required=True)

    cancel = subparsers.add_parser("cancel")
    cancel.add_argument("--trip-id", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "draft":
        result = draft_trip(args.text)
    elif args.command == "show":
        result = show_trip(args.trip_id)
    elif args.command == "set-field":
        result = set_field(args.trip_id, args.field, args.value)
    elif args.command == "confirm":
        result = confirm_trip(args.trip_id)
    elif args.command == "cancel":
        result = cancel_trip(args.trip_id)
    else:
        raise AssertionError(args.command)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
