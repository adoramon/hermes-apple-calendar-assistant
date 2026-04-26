"""Trip draft, calendar selection, and confirmed Calendar write flow."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

try:
    from . import assistant_persona, calendar_ops, trip_aggregator, util
except ImportError:  # Allows running as: python3 scripts/trip_flow.py ...
    import assistant_persona  # type: ignore
    import calendar_ops  # type: ignore
    import trip_aggregator  # type: ignore
    import util  # type: ignore


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TRIP_DRAFTS_PATH = PROJECT_ROOT / "data" / "trip_drafts.json"
TRIP_SEEN_PATH = PROJECT_ROOT / "data" / "trip_seen.json"
ALLOWED_TRIP_CALENDARS = {"商务计划", "个人计划", "夫妻计划"}


def _result(ok: bool, data: Any = None, error: str | None = None) -> dict[str, Any]:
    return {"ok": ok, "data": data, "error": error}


def _read_trips() -> dict[str, Any]:
    raw = util.load_json(TRIP_DRAFTS_PATH, {"trips": {}})
    if not isinstance(raw, dict):
        return {"trips": {}}
    if not isinstance(raw.get("trips"), dict):
        raw["trips"] = {}
    return raw


def _write_trips(store: dict[str, Any]) -> None:
    util.save_json_atomic(TRIP_DRAFTS_PATH, store)


def _read_seen() -> dict[str, Any]:
    raw = util.load_json(TRIP_SEEN_PATH, {"events": {}})
    if not isinstance(raw, dict):
        return {"events": {}}
    if not isinstance(raw.get("events"), dict):
        raw["events"] = {}
    return raw


def _write_seen(store: dict[str, Any]) -> None:
    util.save_json_atomic(TRIP_SEEN_PATH, store)


def _load_trip(trip_id: str) -> dict[str, Any] | None:
    return _read_trips().get("trips", {}).get(trip_id)


def _combine(date_text: str | None, time_text: str | None) -> str:
    if not date_text or not time_text:
        return ""
    return f"{date_text}T{time_text}:00"


def _note_lines(items: list[tuple[str, Any]]) -> str:
    return "\n".join(f"{label}：{value}" for label, value in items if value)


def _flight_event(order: dict[str, Any], calendar: str | None) -> dict[str, Any]:
    fields = order.get("fields", {})
    dep = "".join([str(fields.get("departure_airport") or ""), str(fields.get("departure_terminal") or "")])
    arr = "".join([str(fields.get("arrival_airport") or ""), str(fields.get("arrival_terminal") or "")])
    title = f"航班｜{fields.get('flight_no')} {fields.get('departure_city')}→{fields.get('arrival_city')}"
    return {
        "event_type": "flight",
        "title": title,
        "calendar": calendar,
        "start": fields.get("departure_datetime", ""),
        "end": fields.get("arrival_datetime", ""),
        "location": dep,
        "notes": _note_lines(
            [
                ("航班号", fields.get("flight_no")),
                ("航空公司", fields.get("airline")),
                ("出发机场", dep),
                ("到达机场", arr),
                ("乘机人", fields.get("passenger_name")),
                ("订单号", fields.get("confirmation_number")),
                ("平台来源", order.get("source_platform")),
            ]
        ),
        "confirmation_number": fields.get("confirmation_number", ""),
    }


def _train_event(order: dict[str, Any], calendar: str | None) -> dict[str, Any]:
    fields = order.get("fields", {})
    title = f"高铁｜{fields.get('train_no')} {fields.get('departure_station')}→{fields.get('arrival_station')}"
    return {
        "event_type": "train",
        "title": title,
        "calendar": calendar,
        "start": fields.get("departure_datetime", ""),
        "end": fields.get("arrival_datetime", ""),
        "location": fields.get("departure_station", ""),
        "notes": _note_lines(
            [
                ("车次", fields.get("train_no")),
                ("出发站", fields.get("departure_station")),
                ("到达站", fields.get("arrival_station")),
                ("座位", fields.get("seat")),
                ("乘车人", fields.get("passenger_name")),
                ("订单号", fields.get("confirmation_number")),
                ("平台来源", order.get("source_platform")),
            ]
        ),
        "confirmation_number": fields.get("confirmation_number", ""),
    }


def _hotel_event(order: dict[str, Any], calendar: str | None) -> dict[str, Any]:
    fields = order.get("fields", {})
    start = _combine(fields.get("checkin_date"), fields.get("checkin_time"))
    end = _combine(fields.get("checkout_date"), fields.get("checkout_time") or "12:00")
    return {
        "event_type": "hotel",
        "title": f"入住｜{fields.get('hotel_name')}",
        "calendar": calendar,
        "start": start,
        "end": end,
        "location": fields.get("address", ""),
        "notes": _note_lines(
            [
                ("酒店名称", fields.get("hotel_name")),
                ("地址", fields.get("address")),
                ("入住", f"{fields.get('checkin_date')} {fields.get('checkin_time')}".strip()),
                ("离店", f"{fields.get('checkout_date')} {fields.get('checkout_time') or '12:00'}".strip()),
                ("房型", fields.get("room_type")),
                ("订单号", fields.get("confirmation_number")),
                ("电话", fields.get("phone")),
                ("平台来源", order.get("source_platform")),
            ]
        ),
        "confirmation_number": fields.get("confirmation_number", ""),
    }


def build_events(trip: dict[str, Any]) -> list[dict[str, Any]]:
    calendar = trip.get("calendar")
    events: list[dict[str, Any]] = []
    builders = {"flight": _flight_event, "train": _train_event, "hotel": _hotel_event}
    for order in trip.get("orders", []):
        if not isinstance(order, dict):
            continue
        builder = builders.get(str(order.get("order_type")))
        if builder:
            event = builder(order, calendar)
            if event.get("title") and event.get("start") and event.get("end"):
                events.append(event)
    events.sort(key=lambda item: str(item.get("start", "")))
    return events


def _fingerprint(event: dict[str, Any]) -> str:
    raw = "|".join(
        [
            str(event.get("event_type", "")),
            str(event.get("title", "")),
            str(event.get("start", "")),
            str(event.get("end", "")),
            str(event.get("confirmation_number", "")),
        ]
    )
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def draft_trip(trip_id: str) -> dict[str, Any]:
    trip = _load_trip(trip_id)
    if not trip:
        return _result(False, error=f"Trip not found: {trip_id}")
    events = build_events(trip)
    missing = []
    if not trip.get("calendar"):
        missing.append("calendar")
    if not events:
        missing.append("events")
    data = {
        "trip_id": trip_id,
        "trip": trip,
        "calendar": trip.get("calendar"),
        "events": events,
        "needs_confirmation": True,
        "missing_fields": missing,
        "display_message": assistant_persona.format_trip_draft({**trip, "events": events, "missing_fields": missing}),
    }
    return _result(True, data=data)


def set_calendar(trip_id: str, calendar: str) -> dict[str, Any]:
    if calendar not in ALLOWED_TRIP_CALENDARS:
        return _result(False, error="calendar must be one of: 商务计划, 个人计划, 夫妻计划")
    store = _read_trips()
    trip = store.get("trips", {}).get(trip_id)
    if not trip:
        return _result(False, error=f"Trip not found: {trip_id}")
    if trip.get("status") != "draft":
        return _result(False, error=f"Trip is not draft: {trip_id}")
    trip["calendar"] = calendar
    trip["needs_calendar_choice"] = False
    trip["missing_fields"] = []
    trip["updated_at"] = util.now_local_iso()
    _write_trips(store)
    return draft_trip(trip_id)


def confirm_trip(trip_id: str) -> dict[str, Any]:
    store = _read_trips()
    trip = store.get("trips", {}).get(trip_id)
    if not trip:
        return _result(False, error=f"Trip not found: {trip_id}")
    if trip.get("status") != "draft":
        return _result(False, error=f"Trip is not draft: {trip_id}")
    if trip.get("calendar") not in ALLOWED_TRIP_CALENDARS:
        return _result(False, data={"missing_fields": ["calendar"]}, error="trip_missing_calendar")
    events = build_events(trip)
    if not events:
        return _result(False, data={"missing_fields": ["events"]}, error="trip_has_no_events")

    seen = _read_seen()
    seen_events = seen.setdefault("events", {})
    results: list[dict[str, Any]] = []
    for event in events:
        fingerprint = _fingerprint(event)
        if fingerprint in seen_events:
            results.append({"event": event, "status": "skipped_duplicate", "fingerprint": fingerprint})
            continue
        create_result = calendar_ops.create_event(
            str(trip["calendar"]),
            str(event["title"]),
            str(event["start"]),
            str(event["end"]),
            location=str(event.get("location", "")),
            notes=str(event.get("notes", "")),
        )
        if not create_result.get("ok"):
            results.append({"event": event, "status": "failed", "error": create_result.get("error"), "fingerprint": fingerprint})
            continue
        seen_events[fingerprint] = {
            "trip_id": trip_id,
            "title": event.get("title"),
            "start": event.get("start"),
            "end": event.get("end"),
            "created_at": util.now_local_iso(),
            "calendar_result": create_result.get("data"),
        }
        results.append({"event": event, "status": "created", "fingerprint": fingerprint, "calendar_result": create_result.get("data")})
    _write_seen(seen)
    trip["status"] = "confirmed"
    trip["confirmed_at"] = util.now_local_iso()
    trip["results"] = results
    store["trips"][trip_id] = trip
    _write_trips(store)
    return _result(
        True,
        data={
            "trip_id": trip_id,
            "trip": trip,
            "results": results,
            "display_message": assistant_persona.format_trip_confirmed(trip, results),
        },
    )


def cancel_trip(trip_id: str) -> dict[str, Any]:
    return trip_aggregator.cancel_trip(trip_id)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Draft and confirm aggregated trip Calendar events.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    draft = subparsers.add_parser("draft")
    draft.add_argument("--trip-id", required=True)
    set_cal = subparsers.add_parser("set-calendar")
    set_cal.add_argument("--trip-id", required=True)
    set_cal.add_argument("--calendar", required=True)
    confirm = subparsers.add_parser("confirm")
    confirm.add_argument("--trip-id", required=True)
    cancel = subparsers.add_parser("cancel")
    cancel.add_argument("--trip-id", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "draft":
        result = draft_trip(args.trip_id)
    elif args.command == "set-calendar":
        result = set_calendar(args.trip_id, args.calendar)
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
