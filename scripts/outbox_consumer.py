"""Dry-run consumer for the local outbound message queue."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

try:
    from . import outbox, settings, util
except ImportError:  # Allows running as: python3 scripts/outbox_consumer.py ...
    import outbox  # type: ignore
    import settings  # type: ignore
    import util  # type: ignore


DRY_RUN_STATUS = "sent_dry_run"


def _message_field(record: dict[str, Any], field: str) -> Any:
    """Read one field from a record's nested outbound message."""
    message = record.get("message")
    if not isinstance(message, dict):
        return ""
    return message.get(field, "")


def dry_run(limit: int = 10) -> dict[str, Any]:
    """Simulate consuming pending outbox records without sending messages."""
    send_mode = settings.get_outbox_send_mode()
    if send_mode != "dry_run":
        return util.json_error(f"real sending is not implemented for outbox send_mode={send_mode}")

    allowed_channels = set(settings.get_outbox_allowed_channels())
    max_messages = settings.get_outbox_max_messages_per_run()
    effective_limit = min(max(limit, 0), max_messages)
    processed = []
    skipped = []
    for record in outbox.get_pending_outbox(effective_limit):
        record_id = record.get("id", "")
        channel = _message_field(record, "channel")
        recipient = _message_field(record, "recipient")
        if channel not in allowed_channels:
            skipped.append(
                {
                    "id": record_id,
                    "channel": channel,
                    "recipient": recipient,
                    "reason": "channel_not_allowed",
                }
            )
            continue
        update_result = outbox.update_outbox_status(
            record_id,
            DRY_RUN_STATUS,
            result={
                "mode": "dry_run",
                "processed_at": util.now_local_iso(),
            },
        )
        if not update_result["ok"]:
            skipped.append({"id": record_id, "reason": update_result["error"]})
            continue
        processed.append(
            {
                "id": record_id,
                "channel": channel,
                "recipient": recipient,
                "message": _message_field(record, "message"),
                "status": DRY_RUN_STATUS,
            }
        )
    return util.json_ok(
        {
            "send_mode": send_mode,
            "limit": effective_limit,
            "max_messages_per_run": max_messages,
            "processed": processed,
            "skipped": skipped,
        }
    )


def _build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(description="Dry-run consume local outbox messages.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    dry_run_parser = subparsers.add_parser("dry-run", help="Mark pending outbox messages as sent_dry_run.")
    dry_run_parser.add_argument("--limit", type=int, default=10)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the command-line interface."""
    args = _build_parser().parse_args(argv)
    if args.command == "dry-run":
        result = dry_run(args.limit)
    else:
        raise AssertionError(args.command)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
