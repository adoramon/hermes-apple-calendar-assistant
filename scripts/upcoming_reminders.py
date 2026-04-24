"""Scan upcoming calendar events and emit reminder candidates as JSON."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from typing import Any

try:
    from . import calendar_ops, util
except ImportError:  # Allows running as: python3 scripts/upcoming_reminders.py ...
    import calendar_ops  # type: ignore
    import util  # type: ignore


DEFAULT_LOOKAHEAD_MINUTES = 60


def _result(ok: bool, data: Any = None, error: str | None = None) -> dict[str, Any]:
    return util.result(ok, data=data, error=error)


def _read_calendars() -> list[str]:
    settings = util.load_settings()
    calendars = settings.get("read_calendars")
    if not isinstance(calendars, list):
        return []
    return [calendar for calendar in calendars if isinstance(calendar, str) and calendar]


def build_reminder_candidates(
    calendar_events: dict[str, list[dict[str, Any]]],
    start: str,
    end: str,
) -> dict[str, Any]:
    reminders = []
    for calendar_name, events in calendar_events.items():
        for event in events:
            reminders.append(
                {
                    "calendar": calendar_name,
                    "title": event.get("title", ""),
                    "start": event.get("start", ""),
                    "end": event.get("end", ""),
                    "location": event.get("location", ""),
                    "notes": event.get("notes", ""),
                    "status": "candidate",
                    "delivery": "none",
                }
            )
    reminders.sort(key=lambda item: (str(item.get("start", "")), str(item.get("calendar", ""))))
    return _result(
        True,
        data={
            "start": start,
            "end": end,
            "delivery": "none",
            "reminders": reminders,
        },
    )


def scan_upcoming(minutes: int = DEFAULT_LOOKAHEAD_MINUTES) -> dict[str, Any]:
    if minutes <= 0:
        return _result(False, error="minutes must be greater than 0.")

    calendars = _read_calendars()
    if not calendars:
        return _result(False, error="No readable calendars configured.")

    now = datetime.now()
    start = now.isoformat(timespec="seconds")
    end = (now + timedelta(minutes=minutes)).isoformat(timespec="seconds")
    calendar_events: dict[str, list[dict[str, Any]]] = {}
    errors = []
    for calendar_name in calendars:
        events_result = calendar_ops.list_events(calendar_name, start_date=start, end_date=end)
        if not events_result["ok"]:
            errors.append({"calendar": calendar_name, "error": events_result["error"]})
            continue
        calendar_events[calendar_name] = events_result["data"]["events"]

    result = build_reminder_candidates(calendar_events, start, end)
    result["data"]["errors"] = errors
    return result


def _scan_json(args: argparse.Namespace) -> dict[str, Any]:
    try:
        calendar_events = json.loads(args.calendar_events_json)
    except json.JSONDecodeError as exc:
        return _result(False, error=f"invalid JSON: {exc}")
    if not isinstance(calendar_events, dict):
        return _result(False, error="calendar-events-json must be a JSON object.")
    normalized: dict[str, list[dict[str, Any]]] = {}
    for calendar_name, events in calendar_events.items():
        if not isinstance(calendar_name, str) or not isinstance(events, list):
            return _result(False, error="calendar-events-json must map calendar names to event arrays.")
        normalized[calendar_name] = [event for event in events if isinstance(event, dict)]
    return build_reminder_candidates(normalized, args.start, args.end)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scan upcoming reminder candidates.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan = subparsers.add_parser("scan", help="Scan Calendar.app for upcoming events.")
    scan.add_argument("--minutes", type=int, default=DEFAULT_LOOKAHEAD_MINUTES)

    scan_json = subparsers.add_parser("scan-json", help="Build reminder candidates from supplied JSON.")
    scan_json.add_argument("--calendar-events-json", required=True)
    scan_json.add_argument("--start", default="2026-04-24T12:00:00")
    scan_json.add_argument("--end", default="2026-04-24T13:00:00")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "scan":
        result = scan_upcoming(minutes=args.minutes)
    elif args.command == "scan-json":
        result = _scan_json(args)
    else:
        raise AssertionError(args.command)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
