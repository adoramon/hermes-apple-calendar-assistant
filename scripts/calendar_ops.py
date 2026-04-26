"""Minimal Calendar.app operations via osascript.

This module intentionally keeps confirmation logic out of the Calendar layer.
Callers must confirm destructive actions before calling ``delete_event``.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date, datetime, time, timedelta
from typing import Any

try:
    from . import assistant_persona
except ImportError:  # Allows running as: python3 scripts/calendar_ops.py ...
    import assistant_persona  # type: ignore


MONTH_NAMES = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)

DEFAULT_EVENT_LOOKBACK_DAYS = 30
DEFAULT_EVENT_LOOKAHEAD_DAYS = 30
OSASCRIPT_TIMEOUT_SECONDS = 30


def _result(ok: bool, data: Any = None, error: str | None = None) -> dict[str, Any]:
    return {"ok": ok, "data": data, "error": error}


def _escape_applescript_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _normalize_calendar_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"", "missing value", "null", "none"}:
        return ""
    return text


def _parse_datetime(value: datetime | date | str | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            return value.astimezone().replace(tzinfo=None)
        return value
    if isinstance(value, date):
        return datetime.combine(value, time.min)
    if isinstance(value, str):
        normalized = value.strip()
        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError as exc:
            raise ValueError(f"Expected ISO datetime/date, got: {value!r}") from exc
        if parsed.tzinfo is not None:
            return parsed.astimezone().replace(tzinfo=None)
        return parsed
    raise TypeError(f"Unsupported datetime value: {type(value).__name__}")


def _apple_date_assignment(var_name: str, value: datetime) -> str:
    month_name = MONTH_NAMES[value.month - 1]
    seconds_since_midnight = value.hour * 3600 + value.minute * 60 + value.second
    return "\n".join(
        [
            f"set {var_name} to current date",
            f"set year of {var_name} to {value.year}",
            f"set month of {var_name} to {month_name}",
            f"set day of {var_name} to {value.day}",
            f"set time of {var_name} to {seconds_since_midnight}",
        ]
    )


def _run_osascript(script: str) -> tuple[bool, str, str | None]:
    try:
        completed = subprocess.run(
            ["osascript", "-e", script],
            check=False,
            capture_output=True,
            text=True,
            timeout=OSASCRIPT_TIMEOUT_SECONDS,
        )
    except FileNotFoundError:
        return False, "", "osascript not found. This script must run on macOS."
    except subprocess.TimeoutExpired:
        return False, "", "osascript timed out."
    except Exception as exc:  # Defensive boundary for CLI/Hermes callers.
        return False, "", f"osascript failed: {exc}"

    # Preserve tabs and spaces because Calendar rows use tab-delimited fields;
    # empty trailing fields (for example no location/notes) are meaningful.
    stdout = completed.stdout.rstrip("\r\n")
    stderr = completed.stderr.strip()
    if completed.returncode != 0:
        return False, stdout, stderr or f"osascript exited with {completed.returncode}"
    return True, stdout, None


def list_calendars() -> dict[str, Any]:
    """Return Calendar.app calendar names."""
    script = """
tell application "Calendar"
    set output to ""
    repeat with cal in calendars
        set output to output & (name of cal as text) & linefeed
    end repeat
    return output
end tell
""".strip()
    ok, stdout, error = _run_osascript(script)
    if not ok:
        return _result(False, error=error)
    calendars = [line for line in stdout.splitlines() if line.strip()]
    return _result(True, data={"calendars": calendars})


def list_events(
    calendar_name: str,
    start_date: datetime | date | str | None = None,
    end_date: datetime | date | str | None = None,
) -> dict[str, Any]:
    """Return events for a calendar, optionally bounded by start/end dates."""
    try:
        start = _parse_datetime(start_date)
        end = _parse_datetime(end_date)
    except (TypeError, ValueError) as exc:
        return _result(False, error=str(exc))

    # Calendar.app can be very slow when AppleScript asks for every event in a
    # busy calendar, so never default to a full-history scan.
    if start is None and end is None:
        now = datetime.now()
        start = now - timedelta(days=DEFAULT_EVENT_LOOKBACK_DAYS)
        end = now + timedelta(days=DEFAULT_EVENT_LOOKAHEAD_DAYS)
    elif start is None:
        start = end - timedelta(days=DEFAULT_EVENT_LOOKBACK_DAYS)
    elif end is None:
        end = start + timedelta(days=DEFAULT_EVENT_LOOKAHEAD_DAYS)
    if end <= start:
        return _result(False, error="end_date must be after start_date.")

    calendar_name_escaped = _escape_applescript_text(calendar_name)
    prelude: list[str] = []
    prelude.append(_apple_date_assignment("windowStart", start))
    prelude.append(_apple_date_assignment("windowEnd", end))
    # Include any event that overlaps the requested window. Calendar.app's
    # AppleScript dictionary requires "its" for date properties in whose filters.
    event_query = (
        "every event of targetCalendar whose its end date is greater than windowStart "
        "and its start date is less than windowEnd"
    )
    script = f"""
on cleanField(rawValue)
    set cleanedText to ""
    try
        set cleanedText to rawValue as text
    end try
    if cleanedText is "missing value" then
        set cleanedText to ""
    end if
    set AppleScript's text item delimiters to {{tab, linefeed, return}}
    set cleanedParts to text items of cleanedText
    set AppleScript's text item delimiters to " "
    set cleanedText to cleanedParts as text
    set AppleScript's text item delimiters to ""
    return cleanedText
end cleanField

{chr(10).join(prelude)}
tell application "Calendar"
    set targetCalendar to calendar "{calendar_name_escaped}"
    set matchingEvents to ({event_query})
    set output to ""
    repeat with ev in matchingEvents
        set f1 to my cleanField(summary of ev)
        set f2 to my cleanField(start date of ev)
        set f3 to my cleanField(end date of ev)
        set f4 to ""
        set f5 to ""
        try
            set f4 to my cleanField(location of ev)
        end try
        try
            set f5 to my cleanField(description of ev)
        end try
        set output to output & f1 & tab & f2 & tab & f3 & tab & f4 & tab & f5 & linefeed
    end repeat
    return output
end tell
""".strip()

    ok, stdout, error = _run_osascript(script)
    if not ok:
        return _result(False, error=error)

    events = []
    for line in stdout.splitlines():
        fields = line.split("\t")
        if len(fields) < 5:
            continue
        title, starts_at, ends_at, location, notes = fields[:5]
        events.append(
            {
                "title": title,
                "start": starts_at,
                "end": ends_at,
                "location": _normalize_calendar_text(location),
                "notes": _normalize_calendar_text(notes),
            }
        )
    return _result(True, data={"events": events})


def create_event(
    calendar_name: str,
    title: str,
    start_dt: datetime | date | str,
    end_dt: datetime | date | str,
    location: str = "",
    notes: str = "",
) -> dict[str, Any]:
    """Create a Calendar.app event."""
    try:
        start = _parse_datetime(start_dt)
        end = _parse_datetime(end_dt)
    except (TypeError, ValueError) as exc:
        return _result(False, error=str(exc))
    if start is None or end is None:
        return _result(False, error="start_dt and end_dt are required.")
    if end <= start:
        return _result(False, error="end_dt must be after start_dt.")

    calendar_name_escaped = _escape_applescript_text(calendar_name)
    title_escaped = _escape_applescript_text(title)
    location_escaped = _escape_applescript_text(location)
    notes_escaped = _escape_applescript_text(notes)

    script = f"""
{_apple_date_assignment("eventStartValue", start)}
{_apple_date_assignment("eventEndValue", end)}
tell application "Calendar"
    set targetCalendar to calendar "{calendar_name_escaped}"
    set newEvent to make new event at end of events of targetCalendar with properties {{summary:"{title_escaped}", start date:eventStartValue, end date:eventEndValue, location:"{location_escaped}", description:"{notes_escaped}"}}
    return uid of newEvent
end tell
""".strip()

    ok, stdout, error = _run_osascript(script)
    if not ok:
        return _result(False, error=error)
    event = {
        "calendar": calendar_name,
        "title": title,
        "start": start_dt,
        "end": end_dt,
        "location": location,
    }
    return _result(
        True,
        data={
            "uid": stdout,
            "title": title,
            "display_message": assistant_persona.format_calendar_created(event),
        },
    )


def update_event(
    calendar_name: str,
    old_title: str,
    new_title: str | None = None,
    start_dt: datetime | date | str | None = None,
    end_dt: datetime | date | str | None = None,
    location: str | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    """Update the first exact-title match in the target calendar.

    This is the first update version: it only handles the first event found by
    exact calendar name + exact event title. No fuzzy matching or candidate
    selection is attempted here.
    """
    if all(value is None for value in (new_title, start_dt, end_dt, location, notes)):
        return _result(False, error="At least one field must be provided to update.")

    try:
        start = _parse_datetime(start_dt)
        end = _parse_datetime(end_dt)
    except (TypeError, ValueError) as exc:
        return _result(False, error=str(exc))
    if start is not None and end is not None and end <= start:
        return _result(False, error="end_dt must be after start_dt.")

    calendar_name_escaped = _escape_applescript_text(calendar_name)
    old_title_escaped = _escape_applescript_text(old_title)

    prelude: list[str] = []
    update_lines: list[str] = []
    updated_fields: list[str] = []
    if new_title is not None:
        new_title_escaped = _escape_applescript_text(new_title)
        update_lines.append(f'set summary of targetEvent to "{new_title_escaped}"')
        updated_fields.append("title")
    if start is not None:
        prelude.append(_apple_date_assignment("updatedStartValue", start))
        update_lines.append("set start date of targetEvent to updatedStartValue")
        updated_fields.append("start")
    if end is not None:
        prelude.append(_apple_date_assignment("updatedEndValue", end))
        update_lines.append("set end date of targetEvent to updatedEndValue")
        updated_fields.append("end")
    if location is not None:
        location_escaped = _escape_applescript_text(location)
        update_lines.append(f'set location of targetEvent to "{location_escaped}"')
        updated_fields.append("location")
    if notes is not None:
        notes_escaped = _escape_applescript_text(notes)
        update_lines.append(f'set description of targetEvent to "{notes_escaped}"')
        updated_fields.append("notes")

    script = f"""
{chr(10).join(prelude)}
tell application "Calendar"
    set targetCalendar to calendar "{calendar_name_escaped}"
    set matches to events of targetCalendar whose summary is "{old_title_escaped}"
    if (count of matches) is 0 then
        return "NOT_FOUND"
    end if
    set targetEvent to item 1 of matches
    set originalTitle to summary of targetEvent as text
    {chr(10).join(update_lines)}
    return (uid of targetEvent as text) & tab & originalTitle & tab & (summary of targetEvent as text)
end tell
""".strip()

    ok, stdout, error = _run_osascript(script)
    if not ok:
        return _result(False, error=error)
    if stdout == "NOT_FOUND":
        return _result(False, error=f"No event found with title: {old_title}")

    fields = stdout.split("\t", maxsplit=2)
    uid = fields[0] if len(fields) > 0 else ""
    original_title = fields[1] if len(fields) > 1 else old_title
    updated_title = fields[2] if len(fields) > 2 else new_title or old_title
    event = {
        "calendar": calendar_name,
        "title": updated_title,
        "start": start_dt,
        "end": end_dt,
    }
    return _result(
        True,
        data={
            "uid": uid,
            "original_title": original_title,
            "title": updated_title,
            "updated_fields": updated_fields,
            "display_message": assistant_persona.format_calendar_updated(event),
        },
    )


def update_event_location_exact(
    calendar_name: str,
    title: str,
    start_text: str,
    end_text: str,
    location: str,
) -> dict[str, Any]:
    """Update only the location field for one exact title+start+end match."""
    if not title:
        return _result(False, error="title is required.")
    if not start_text or not end_text:
        return _result(False, error="start_text and end_text are required.")

    calendar_name_escaped = _escape_applescript_text(calendar_name)
    title_escaped = _escape_applescript_text(title)
    start_text_escaped = _escape_applescript_text(start_text)
    end_text_escaped = _escape_applescript_text(end_text)
    location_escaped = _escape_applescript_text(location)

    script = f"""
tell application "Calendar"
    set targetCalendar to calendar "{calendar_name_escaped}"
    set matches to events of targetCalendar whose summary is "{title_escaped}"
    set matchedCount to 0
    set targetEvent to missing value
    repeat with ev in matches
        set f2 to (start date of ev) as text
        set f3 to (end date of ev) as text
        if f2 is "{start_text_escaped}" and f3 is "{end_text_escaped}" then
            set matchedCount to matchedCount + 1
            set targetEvent to ev
        end if
    end repeat
    if matchedCount is 0 then
        return "NOT_FOUND"
    end if
    if matchedCount is greater than 1 then
        return "AMBIGUOUS"
    end if
    set originalLocation to ""
    try
        set originalLocation to location of targetEvent as text
    end try
    set location of targetEvent to "{location_escaped}"
    return (uid of targetEvent as text) & tab & (summary of targetEvent as text) & tab & originalLocation & tab & (location of targetEvent as text)
end tell
""".strip()

    ok, stdout, error = _run_osascript(script)
    if not ok:
        return _result(False, error=error)
    if stdout == "NOT_FOUND":
        return _result(False, error="No event found with the exact title/start/end identity.")
    if stdout == "AMBIGUOUS":
        return _result(False, error="Multiple events matched the same title/start/end identity.")

    fields = stdout.split("\t", maxsplit=3)
    uid = fields[0] if len(fields) > 0 else ""
    updated_title = fields[1] if len(fields) > 1 else title
    original_location = _normalize_calendar_text(fields[2] if len(fields) > 2 else "")
    updated_location = _normalize_calendar_text(fields[3] if len(fields) > 3 else location)
    return _result(
        True,
        data={
            "uid": uid,
            "title": updated_title,
            "original_location": original_location,
            "location": updated_location,
            "updated_fields": ["location"],
            "display_message": assistant_persona.format_calendar_updated(
                {"calendar": calendar_name, "title": updated_title, "location": updated_location}
            ),
        },
    )


def delete_event(calendar_name: str, title: str) -> dict[str, Any]:
    """Delete the first event with an exact title match in the target calendar."""
    calendar_name_escaped = _escape_applescript_text(calendar_name)
    title_escaped = _escape_applescript_text(title)
    script = f"""
tell application "Calendar"
    set targetCalendar to calendar "{calendar_name_escaped}"
    set matches to events of targetCalendar whose summary is "{title_escaped}"
    if (count of matches) is 0 then
        return "NOT_FOUND"
    end if
    set targetEvent to item 1 of matches
    set deletedTitle to summary of targetEvent as text
    delete targetEvent
    return deletedTitle
end tell
""".strip()

    ok, stdout, error = _run_osascript(script)
    if not ok:
        return _result(False, error=error)
    if stdout == "NOT_FOUND":
        return _result(False, error=f"No event found with title: {title}")
    return _result(
        True,
        data={
            "deleted_title": stdout,
            "display_message": assistant_persona.format_calendar_deleted({"title": stdout, "calendar": calendar_name}),
        },
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Debug Apple Calendar operations.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("calendars", help="List Calendar.app calendars.")

    events = subparsers.add_parser("events", help="List events in a calendar.")
    events.add_argument("calendar_name")
    events.add_argument("--start", help="ISO datetime, e.g. 2026-04-16T00:00:00")
    events.add_argument("--end", help="ISO datetime, e.g. 2026-04-17T00:00:00")

    create = subparsers.add_parser("create", help="Create an event.")
    create.add_argument("calendar_name")
    create.add_argument("title")
    create.add_argument("start_dt", help="ISO datetime, for example 2026-04-14T09:00:00")
    create.add_argument("end_dt", help="ISO datetime, for example 2026-04-14T10:00:00")
    create.add_argument("--location", default="")
    create.add_argument("--notes", default="")

    update = subparsers.add_parser("update", help="Update the first exact-title match.")
    update.add_argument("calendar_name")
    update.add_argument("old_title")
    update.add_argument("--new-title", dest="new_title")
    update.add_argument("--start", dest="start_dt")
    update.add_argument("--end", dest="end_dt")
    update.add_argument("--location")
    update.add_argument("--notes")

    delete = subparsers.add_parser("delete", help="Delete the first exact-title match.")
    delete.add_argument("calendar_name")
    delete.add_argument("title")
    delete.add_argument("--yes", action="store_true", help="Required to confirm deletion.")

    update_location = subparsers.add_parser(
        "update-location-exact",
        help="Update location for one exact title+start+end match.",
    )
    update_location.add_argument("calendar_name")
    update_location.add_argument("title")
    update_location.add_argument("start_text")
    update_location.add_argument("end_text")
    update_location.add_argument("location")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "calendars":
        result = list_calendars()
    elif args.command == "events":
        result = list_events(args.calendar_name, start_date=args.start, end_date=args.end)
    elif args.command == "create":
        result = create_event(
            args.calendar_name,
            args.title,
            args.start_dt,
            args.end_dt,
            location=args.location,
            notes=args.notes,
        )
    elif args.command == "update":
        result = update_event(
            args.calendar_name,
            args.old_title,
            new_title=args.new_title,
            start_dt=args.start_dt,
            end_dt=args.end_dt,
            location=args.location,
            notes=args.notes,
        )
    elif args.command == "delete":
        if not args.yes:
            result = _result(False, error="Refusing to delete without --yes.")
        else:
            result = delete_event(args.calendar_name, args.title)
    elif args.command == "update-location-exact":
        result = update_event_location_exact(
            args.calendar_name,
            args.title,
            args.start_text,
            args.end_text,
            args.location,
        )
    else:
        parser.error(f"Unknown command: {args.command}")

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
