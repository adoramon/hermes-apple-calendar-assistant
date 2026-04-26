"""Check single-calendar event conflicts and suggest same-day free slots."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, time, timedelta
from typing import Any

try:
    from . import assistant_persona, calendar_ops, settings, util
except ImportError:  # Allows running as: python3 scripts/conflict_checker.py ...
    import assistant_persona  # type: ignore
    import calendar_ops  # type: ignore
    import settings  # type: ignore
    import util  # type: ignore


APPLE_DATETIME_RE = re.compile(
    r"(?P<year>\d{4})年(?P<month>\d{1,2})月(?P<day>\d{1,2})日.*?"
    r"(?P<hour>\d{1,2}):(?P<minute>\d{2}):(?P<second>\d{2})"
)
MAX_SUGGESTED_SLOTS = 3
WORKDAY_START = time(9, 0, 0)
WORKDAY_END = time(21, 0, 0)


def _parse_iso_datetime(value: str, field_name: str) -> datetime:
    """Parse a required ISO datetime CLI argument."""
    if not value:
        raise ValueError(f"{field_name} is required.")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO datetime.") from exc
    if parsed.tzinfo is not None:
        return parsed.astimezone().replace(tzinfo=None)
    return parsed


def _parse_event_datetime(value: Any) -> datetime | None:
    """Parse Calendar.app event datetime text when possible."""
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        parsed = None
    if parsed is not None:
        if parsed.tzinfo is not None:
            return parsed.astimezone().replace(tzinfo=None)
        return parsed

    match = APPLE_DATETIME_RE.search(text)
    if not match:
        return None
    return datetime(
        int(match.group("year")),
        int(match.group("month")),
        int(match.group("day")),
        int(match.group("hour")),
        int(match.group("minute")),
        int(match.group("second")),
    )


def _overlaps(start_a: datetime, end_a: datetime, start_b: datetime, end_b: datetime) -> bool:
    """Return whether two half-open datetime ranges overlap."""
    return start_a < end_b and start_b < end_a


def _event_overlaps(event: dict[str, Any], start: datetime, end: datetime) -> bool:
    """Return whether an event overlaps the requested range."""
    event_start = _parse_event_datetime(event.get("start"))
    event_end = _parse_event_datetime(event.get("end"))
    if event_start is None or event_end is None:
        return True
    return _overlaps(start, end, event_start, event_end)


def _compact_event(event: dict[str, Any]) -> dict[str, Any]:
    """Return the public conflict fields for one Calendar.app event."""
    return {
        "title": event.get("title", ""),
        "start": event.get("start", ""),
        "end": event.get("end", ""),
        "location": event.get("location", ""),
    }


def _busy_ranges(events: list[dict[str, Any]]) -> list[tuple[datetime, datetime]]:
    """Parse and sort busy ranges from Calendar.app events."""
    ranges = []
    for event in events:
        event_start = _parse_event_datetime(event.get("start"))
        event_end = _parse_event_datetime(event.get("end"))
        if event_start is None or event_end is None or event_end <= event_start:
            continue
        ranges.append((event_start, event_end))
    ranges.sort(key=lambda item: item[0])
    return ranges


def _suggest_slots(
    requested_start: datetime,
    requested_end: datetime,
    day_events: list[dict[str, Any]],
) -> list[dict[str, str]]:
    """Suggest up to three same-day free slots inside 09:00-21:00."""
    duration = requested_end - requested_start
    window_start = datetime.combine(requested_start.date(), WORKDAY_START)
    window_end = datetime.combine(requested_start.date(), WORKDAY_END)
    cursor = max(requested_start, window_start)
    suggestions = []

    for busy_start, busy_end in _busy_ranges(day_events):
        if busy_start >= window_end:
            break
        if busy_end <= cursor:
            continue
        busy_start = max(busy_start, window_start)
        busy_end = min(busy_end, window_end)
        if busy_start > cursor:
            while cursor + duration <= busy_start and len(suggestions) < MAX_SUGGESTED_SLOTS:
                slot_end = cursor + duration
                suggestions.append(
                    {
                        "start": cursor.isoformat(timespec="seconds"),
                        "end": slot_end.isoformat(timespec="seconds"),
                    }
                )
                cursor = slot_end
            if len(suggestions) >= MAX_SUGGESTED_SLOTS:
                return suggestions
        if busy_end > cursor:
            cursor = busy_end

    while cursor + duration <= window_end and len(suggestions) < MAX_SUGGESTED_SLOTS:
        slot_end = cursor + duration
        suggestions.append(
            {
                "start": cursor.isoformat(timespec="seconds"),
                "end": slot_end.isoformat(timespec="seconds"),
            }
        )
        cursor = slot_end
    return suggestions


def check_conflicts(calendar_name: str, start_text: str, end_text: str) -> dict[str, Any]:
    """Check one readable calendar for conflicts in a proposed time range."""
    if calendar_name not in settings.get_read_calendars():
        return util.json_error(f"calendar must be readable: {calendar_name}")

    try:
        start = _parse_iso_datetime(start_text, "start")
        end = _parse_iso_datetime(end_text, "end")
    except ValueError as exc:
        return util.json_error(str(exc))
    if end <= start:
        return util.json_error("end must be after start.")

    conflict_result = calendar_ops.list_events(calendar_name, start_date=start, end_date=end)
    if not conflict_result["ok"]:
        return conflict_result

    conflicts = [
        _compact_event(event)
        for event in conflict_result["data"]["events"]
        if _event_overlaps(event, start, end)
    ]
    suggested_slots: list[dict[str, str]] = []
    if conflicts:
        day_start = datetime.combine(start.date(), WORKDAY_START)
        day_end = datetime.combine(start.date(), WORKDAY_END)
        day_result = calendar_ops.list_events(calendar_name, start_date=day_start, end_date=day_end)
        if not day_result["ok"]:
            return day_result
        suggested_slots = _suggest_slots(start, end, day_result["data"]["events"])

    return util.json_ok(
        {
            "calendar": calendar_name,
            "start": start_text,
            "end": end_text,
            "has_conflict": bool(conflicts),
            "conflicts": conflicts,
            "suggested_slots": suggested_slots,
            "display_message": assistant_persona.format_calendar_conflict(conflicts, suggested_slots)
            if conflicts
            else "",
        }
    )


def _build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(description="Check one calendar for event conflicts.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    check = subparsers.add_parser("check", help="Check Calendar.app for conflicts.")
    check.add_argument("--calendar", required=True)
    check.add_argument("--start", required=True, help="ISO datetime, e.g. 2026-04-27T15:00:00.")
    check.add_argument("--end", required=True, help="ISO datetime, e.g. 2026-04-27T16:00:00.")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the command-line interface."""
    args = _build_parser().parse_args(argv)
    if args.command == "check":
        result = check_conflicts(args.calendar, args.start, args.end)
    else:
        raise AssertionError(args.command)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
