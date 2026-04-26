"""Hermes cron bridge that renders pending outbox messages as plain text."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from typing import Any

try:
    from . import assistant_persona, outbox, util
except ImportError:  # Allows running as: python3 scripts/hermes_cron_outbox_bridge.py ...
    import assistant_persona  # type: ignore
    import outbox  # type: ignore
    import util  # type: ignore


EMPTY_MODE_SILENT = "silent"
EMPTY_MODE_MESSAGE = "message"
EMPTY_MESSAGE = assistant_persona.format_no_pending_reminders()
BRIDGE_STATUS = "sent_via_hermes_cron"


def _parse_created_at(value: Any) -> tuple[int, str]:
    """Return a sortable key for created_at, keeping invalid values last."""
    if not isinstance(value, str) or not value.strip():
        return (1, "")
    text = value.strip()
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return (1, text)
    return (0, parsed.isoformat())


def _message(record: dict[str, Any]) -> dict[str, Any]:
    """Return the nested outbound message as a dict."""
    message = record.get("message")
    if isinstance(message, dict):
        return message
    return {}


def _record_message_text(record: dict[str, Any]) -> str:
    """Return one pending outbox record as a display line."""
    message = _message(record)
    text = message.get("message", "")
    if isinstance(text, str):
        return text.strip()
    return str(text or "").strip()


def _metadata(record: dict[str, Any]) -> dict[str, Any]:
    """Return outbound metadata as a dict."""
    metadata = _message(record).get("metadata")
    if isinstance(metadata, dict):
        return metadata
    return {}


def _clean_text(value: Any) -> str:
    """Normalize metadata text for WeChat-friendly display."""
    return assistant_persona.clean_text(value)


def _record_event(record: dict[str, Any]) -> dict[str, Any]:
    """Build a reminder event for assistant_persona."""
    metadata = _metadata(record)
    title = _clean_text(metadata.get("title")) or _record_message_text(record)
    return {
        "title": title,
        "start": metadata.get("start", ""),
        "end": metadata.get("end", ""),
        "location": metadata.get("location", ""),
        "offset_minutes": metadata.get("offset_minutes"),
    }


def _select_pending_records(limit: int) -> list[dict[str, Any]]:
    """Return oldest pending outbox records, limited by count."""
    records = [record for record in outbox.load_outbox_records() if record.get("status") == "pending"]
    records.sort(key=lambda record: _parse_created_at(record.get("created_at")))
    return records[: max(limit, 0)]


def _render_records(records: list[dict[str, Any]], empty_mode: str) -> str:
    """Render selected records as Hermes-friendly plain text."""
    selected = records

    events = [_record_event(record) for record in selected]
    output = assistant_persona.format_multi_reminder_message(events)
    if not output:
        if empty_mode == EMPTY_MODE_MESSAGE:
            return EMPTY_MESSAGE
        return ""
    return output


def _mark_records_sent(records: list[dict[str, Any]]) -> None:
    """Mark selected pending records as sent_via_hermes_cron."""
    result = outbox.update_outbox_statuses(
        [str(record.get("id", "")) for record in records],
        BRIDGE_STATUS,
        result={
            "mode": "hermes_cron",
            "processed_at": util.now_local_iso(),
            "note": "Message handed to Hermes Cron stdout for delivery",
        },
        only_if_status="pending",
    )
    if not result.get("ok"):
        raise RuntimeError(str(result.get("error") or "outbox_update_failed"))


def read_pending(limit: int = 5, empty_mode: str = EMPTY_MODE_SILENT, mark_sent: bool = False) -> str:
    """Render oldest pending outbox messages and optionally mark them as sent."""
    records = _select_pending_records(limit)
    output = _render_records(records, empty_mode)
    if mark_sent and records and output:
        _mark_records_sent(records)
    return output


def _build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(
        description="Render pending outbox records as plain text for Hermes cron --script delivery."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    read_parser = subparsers.add_parser("read-pending", help="Read pending outbox records as plain text.")
    read_parser.add_argument("--limit", type=int, default=5)
    read_parser.add_argument(
        "--empty-mode",
        choices=(EMPTY_MODE_SILENT, EMPTY_MODE_MESSAGE),
        default=EMPTY_MODE_SILENT,
    )
    read_parser.add_argument("--mark-sent", action="store_true")

    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the command-line interface."""
    args = _build_parser().parse_args(argv)
    if args.command == "read-pending":
        output = read_pending(args.limit, args.empty_mode, args.mark_sent)
    else:
        raise AssertionError(args.command)
    print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
