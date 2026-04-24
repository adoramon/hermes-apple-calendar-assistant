"""Detect calendar conflicts for proposed event drafts."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from typing import Any

try:
    from . import calendar_ops, util
except ImportError:  # Allows running as: python3 scripts/conflict_detector.py ...
    import calendar_ops  # type: ignore
    import util  # type: ignore


def _result(ok: bool, data: Any = None, error: str | None = None) -> dict[str, Any]:
    return util.result(ok, data=data, error=error)


def _parse_datetime(value: Any, field_name: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} is required.")
    try:
        parsed = datetime.fromisoformat(value.strip())
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO datetime.") from exc
    if parsed.tzinfo is not None:
        return parsed.astimezone().replace(tzinfo=None)
    return parsed


def _load_settings() -> dict[str, Any]:
    settings = util.load_settings()
    read_calendars = settings.get("read_calendars")
    write_calendars = settings.get("write_calendars")
    if not isinstance(read_calendars, list):
        read_calendars = []
    if not isinstance(write_calendars, list):
        write_calendars = []
    return {"read_calendars": read_calendars, "write_calendars": write_calendars}


def validate_draft_window(draft: dict[str, Any]) -> dict[str, Any]:
    try:
        start = _parse_datetime(draft.get("start"), "start")
        end = _parse_datetime(draft.get("end"), "end")
    except ValueError as exc:
        return _result(False, error=str(exc))
    if end <= start:
        return _result(False, error="end must be after start.")
    return _result(True, data={"start": start, "end": end})


def detect_conflicts_from_events(draft: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any]:
    validation = validate_draft_window(draft)
    if not validation["ok"]:
        return validation
    conflicts = []
    draft_title = draft.get("title", "")
    for event in events:
        if draft_title and event.get("title") == draft_title and event.get("start") == draft.get("start"):
            continue
        conflicts.append(event)
    return _result(True, data={"has_conflict": bool(conflicts), "conflicts": conflicts})


def detect_conflicts(calendar_name: str, start: str, end: str) -> dict[str, Any]:
    settings = _load_settings()
    if calendar_name not in settings["read_calendars"]:
        return _result(False, error=f"calendar must be readable: {calendar_name}")
    if calendar_name not in settings["write_calendars"]:
        return _result(False, error=f"calendar is not writable for normal CRUD: {calendar_name}")

    draft = {"calendar": calendar_name, "start": start, "end": end}
    validation = validate_draft_window(draft)
    if not validation["ok"]:
        return validation

    events_result = calendar_ops.list_events(calendar_name, start_date=start, end_date=end)
    if not events_result["ok"]:
        return events_result
    events = events_result["data"]["events"]
    return _result(
        True,
        data={
            "calendar": calendar_name,
            "start": start,
            "end": end,
            "has_conflict": bool(events),
            "conflicts": events,
        },
    )


def _check_json(args: argparse.Namespace) -> dict[str, Any]:
    try:
        draft = json.loads(args.draft_json)
        events = json.loads(args.events_json)
    except json.JSONDecodeError as exc:
        return _result(False, error=f"invalid JSON: {exc}")
    if not isinstance(draft, dict):
        return _result(False, error="draft-json must be a JSON object.")
    if not isinstance(events, list):
        return _result(False, error="events-json must be a JSON array.")
    return detect_conflicts_from_events(draft, events)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Detect event conflicts.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    check = subparsers.add_parser("check", help="Check Calendar.app for conflicts.")
    check.add_argument("--calendar", required=True)
    check.add_argument("--start", required=True, help="ISO datetime.")
    check.add_argument("--end", required=True, help="ISO datetime.")

    check_json = subparsers.add_parser("check-json", help="Check conflicts from supplied JSON events.")
    check_json.add_argument("--draft-json", required=True)
    check_json.add_argument("--events-json", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "check":
        result = detect_conflicts(args.calendar, args.start, args.end)
    elif args.command == "check-json":
        result = _check_json(args)
    else:
        raise AssertionError(args.command)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
