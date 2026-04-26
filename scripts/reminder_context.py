"""Read reminder outbox context for follow-up actions."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

try:
    from . import outbox, util
except ImportError:  # Allows running as: python3 scripts/reminder_context.py ...
    import outbox  # type: ignore
    import util  # type: ignore


REMINDER_STATUSES = {"sent_via_hermes_cron", "sent_dry_run", "pending"}
REMINDER_TYPE = "calendar_reminder"


def _message(record: dict[str, Any]) -> dict[str, Any]:
    message = record.get("message")
    if isinstance(message, dict):
        return message
    return {}


def _metadata(record: dict[str, Any]) -> dict[str, Any]:
    metadata = _message(record).get("metadata")
    if isinstance(metadata, dict):
        return metadata
    return {}


def _is_calendar_reminder(record: dict[str, Any]) -> bool:
    if record.get("status") not in REMINDER_STATUSES:
        return False
    return _metadata(record).get("type") == REMINDER_TYPE


def _sort_key(record: dict[str, Any]) -> str:
    result = record.get("result")
    if isinstance(result, dict) and result.get("processed_at"):
        return str(result.get("processed_at"))
    return str(record.get("created_at", ""))


def get_recent_sent_reminders(limit: int = 5) -> list[dict[str, Any]]:
    """Return recent calendar reminder records from the local outbox."""
    records = [record for record in outbox.load_outbox_records() if _is_calendar_reminder(record)]
    records.sort(key=_sort_key, reverse=True)
    return records[: max(limit, 0)]


def get_latest_sent_reminder() -> dict[str, Any] | None:
    """Return the latest calendar reminder record, or None."""
    records = get_recent_sent_reminders(limit=1)
    if not records:
        return None
    return records[0]


def find_reminder_by_record_id(record_id: str) -> dict[str, Any] | None:
    """Find one calendar reminder record by outbox id."""
    for record in outbox.load_outbox_records():
        if record.get("id") == record_id and _is_calendar_reminder(record):
            return record
    return None


def extract_calendar_event_identity(reminder_record: dict[str, Any]) -> dict[str, Any]:
    """Extract the Calendar event identity from a reminder outbox record."""
    metadata = _metadata(reminder_record)
    return {
        "record_id": reminder_record.get("id", ""),
        "calendar": metadata.get("calendar", ""),
        "title": metadata.get("title", ""),
        "start": metadata.get("start", ""),
        "end": metadata.get("end", ""),
        "location": metadata.get("location", ""),
        "fingerprint": metadata.get("fingerprint", ""),
        "offset_minutes": metadata.get("offset_minutes"),
    }


def _public_record(record: dict[str, Any]) -> dict[str, Any]:
    message = _message(record)
    return {
        "id": record.get("id", ""),
        "created_at": record.get("created_at", ""),
        "status": record.get("status", ""),
        "message": message.get("message", ""),
        "event": extract_calendar_event_identity(record),
    }


def main(argv: list[str] | None = None) -> int:
    args = list(argv or [])
    command = args[0] if args else "latest"
    if command == "latest":
        record = get_latest_sent_reminder()
        result = util.json_ok({"record": _public_record(record) if record else None})
    elif command == "recent":
        limit = int(args[1]) if len(args) > 1 else 5
        result = util.json_ok({"records": [_public_record(record) for record in get_recent_sent_reminders(limit)]})
    else:
        result = util.json_error(f"Unknown command: {command}")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
