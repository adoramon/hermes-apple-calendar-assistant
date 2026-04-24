"""Read-only reminder scan worker with local idempotency."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

try:
    from . import calendar_ops, message_adapter, settings, util
except ImportError:  # Allows running as: python3 scripts/reminder_worker.py ...
    import calendar_ops  # type: ignore
    import message_adapter  # type: ignore
    import settings  # type: ignore
    import util  # type: ignore


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REMINDER_SEEN_PATH = PROJECT_ROOT / "data" / "reminder_seen.json"
APPLE_DATETIME_RE = re.compile(
    r"(?P<year>\d{4})年(?P<month>\d{1,2})月(?P<day>\d{1,2})日.*?"
    r"(?P<hour>\d{1,2}):(?P<minute>\d{2}):(?P<second>\d{2})"
)
SOURCE_NAME = "reminder_worker"


def _parse_event_datetime(value: Any) -> datetime | None:
    """Parse Calendar.app datetime text into a naive local datetime."""
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


def _read_seen_store() -> dict[str, Any]:
    """Read reminder seen state from disk."""
    raw = util.load_json(REMINDER_SEEN_PATH, {})
    if not isinstance(raw, dict):
        return {"reminders": {}}
    reminders = raw.get("reminders")
    if not isinstance(reminders, dict):
        reminders = {}
    return {"reminders": reminders}


def _write_seen_store(store: dict[str, Any]) -> None:
    """Persist reminder seen state atomically."""
    util.save_json_atomic(REMINDER_SEEN_PATH, store)


def _event_fingerprint(calendar_name: str, event: dict[str, Any]) -> str:
    """Build a stable event fingerprint from calendar, title, start, and end."""
    raw = "|".join(
        [
            calendar_name,
            str(event.get("title", "")),
            str(event.get("start", "")),
            str(event.get("end", "")),
        ]
    )
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def _seen_key(fingerprint: str, offset_minutes: int) -> str:
    """Build an idempotency key for one event and one reminder offset."""
    return f"{fingerprint}:{offset_minutes}"


def _build_message(event: dict[str, Any], offset_minutes: int) -> str:
    """Build a human-readable reminder message."""
    title = event.get("title", "")
    location = event.get("location", "")
    suffix = f" @ {location}" if location else ""
    return f"{offset_minutes}分钟后：{title}{suffix}"


def _is_due(now: datetime, event_start: datetime, offset_minutes: int) -> bool:
    """Return whether a reminder offset is due during this scan."""
    due_at = event_start - timedelta(minutes=offset_minutes)
    return due_at <= now < event_start


def scan_reminders() -> dict[str, Any]:
    """Scan readable calendars and emit idempotent reminder candidates."""
    read_calendars = settings.get_read_calendars()
    scan_minutes = settings.get_reminder_scan_minutes()
    offsets = settings.get_reminder_default_offsets_minutes()
    now = datetime.now()
    scan_start = now.isoformat(timespec="seconds")
    scan_end = (now + timedelta(minutes=scan_minutes)).isoformat(timespec="seconds")
    seen_store = _read_seen_store()
    seen = seen_store.setdefault("reminders", {})
    reminders = []
    skipped = []

    for calendar_name in read_calendars:
        events_result = calendar_ops.list_events(calendar_name, start_date=scan_start, end_date=scan_end)
        if not events_result["ok"]:
            skipped.append({"calendar": calendar_name, "reason": events_result["error"]})
            continue

        for event in events_result["data"]["events"]:
            event_start = _parse_event_datetime(event.get("start"))
            if event_start is None:
                skipped.append(
                    {
                        "calendar": calendar_name,
                        "title": event.get("title", ""),
                        "reason": "unparseable_start",
                    }
                )
                continue
            fingerprint = _event_fingerprint(calendar_name, event)
            for offset in offsets:
                key = _seen_key(fingerprint, offset)
                if key in seen:
                    skipped.append(
                        {
                            "calendar": calendar_name,
                            "title": event.get("title", ""),
                            "offset_minutes": offset,
                            "reason": "already_seen",
                        }
                    )
                    continue
                if not _is_due(now, event_start, offset):
                    skipped.append(
                        {
                            "calendar": calendar_name,
                            "title": event.get("title", ""),
                            "offset_minutes": offset,
                            "reason": "not_due",
                        }
                    )
                    continue

                reminder = {
                    "fingerprint": key,
                    "calendar": calendar_name,
                    "title": event.get("title", ""),
                    "start": event.get("start", ""),
                    "end": event.get("end", ""),
                    "location": event.get("location", ""),
                    "offset_minutes": offset,
                    "message": _build_message(event, offset),
                }
                reminders.append(reminder)
                seen[key] = {
                    "key": key,
                    "fingerprint": fingerprint,
                    "calendar": calendar_name,
                    "title": event.get("title", ""),
                    "start": event.get("start", ""),
                    "end": event.get("end", ""),
                    "offset_minutes": offset,
                    "seen_at": util.now_local_iso(),
                    "source": SOURCE_NAME,
                }

    _write_seen_store(seen_store)
    return util.json_ok(
        {
            "scan_minutes": scan_minutes,
            "offsets": offsets,
            "reminders": reminders,
            "skipped": skipped,
        }
    )


def _format_outbound_result(raw_result: dict[str, Any], channel: str, recipient: str) -> dict[str, Any]:
    """Convert raw reminder candidates into outbound message payloads."""
    if not raw_result["ok"]:
        return raw_result
    messages = []
    for reminder in raw_result["data"]["reminders"]:
        metadata = {
            "type": "calendar_reminder",
            "calendar": reminder.get("calendar", ""),
            "title": reminder.get("title", ""),
            "start": reminder.get("start", ""),
            "end": reminder.get("end", ""),
            "location": reminder.get("location", ""),
            "offset_minutes": reminder.get("offset_minutes"),
            "fingerprint": reminder.get("fingerprint", ""),
        }
        messages.append(
            message_adapter.build_outbound_payload(
                channel,
                recipient,
                message_adapter.build_calendar_reminder_message(reminder),
                metadata=metadata,
            )
        )
    return util.json_ok({"messages": messages, "skipped": raw_result["data"]["skipped"]})


def _build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(description="Scan reminder candidates without sending notifications.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    scan = subparsers.add_parser("scan", help="Scan readable calendars for due reminder candidates.")
    scan.add_argument("--format", choices=("raw", "outbound"), default="raw")
    scan.add_argument("--channel", default="hermes")
    scan.add_argument("--recipient", default="default")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the command-line interface."""
    args = _build_parser().parse_args(argv)
    if args.command == "scan":
        result = scan_reminders()
        if args.format == "outbound":
            result = _format_outbound_result(result, args.channel, args.recipient)
    else:
        raise AssertionError(args.command)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
