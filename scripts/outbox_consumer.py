"""Dry-run consumer for the local outbound message queue."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

try:
    from . import channel_sender, outbox, settings, util
except ImportError:  # Allows running as: python3 scripts/outbox_consumer.py ...
    import channel_sender  # type: ignore
    import outbox  # type: ignore
    import settings  # type: ignore
    import util  # type: ignore


DRY_RUN_STATUS = "sent_dry_run"
REAL_BLOCKED_STATUS = "failed_real_send_blocked"


def _message_field(record: dict[str, Any], field: str) -> Any:
    """Read one field from a record's nested outbound message."""
    message = record.get("message")
    if not isinstance(message, dict):
        return ""
    return message.get(field, "")


def _record_message(record: dict[str, Any]) -> dict[str, Any]:
    """Return a record's nested outbound message."""
    message = record.get("message")
    if isinstance(message, dict):
        return message
    return {}


def consume_outbox(mode: str = "dry_run", limit: int = 10, confirm_phrase: str | None = None) -> dict[str, Any]:
    """Consume pending outbox records with dry-run or blocked real mode."""
    send_mode = mode
    sender = settings.get_outbox_sender()
    if sender != "channel_sender":
        return {"ok": False, "data": None, "error": "unsupported sender"}

    allowed_channels = set(settings.get_outbox_allowed_channels())
    max_messages = settings.get_outbox_max_messages_per_run()
    effective_limit = min(max(limit, 0), max_messages)
    processed = []
    skipped = []
    pending_records = outbox.get_pending_outbox(effective_limit)
    if send_mode == "real" and not pending_records:
        return {
            "ok": False,
            "data": {
                "send_mode": send_mode,
                "sender": sender,
                "limit": effective_limit,
                "max_messages_per_run": max_messages,
                "processed": [],
                "skipped": [],
            },
            "error": "real send is not implemented",
        }
    for record in pending_records:
        record_id = record.get("id", "")
        message = _record_message(record)
        channel = message.get("channel", "")
        recipient = message.get("recipient", "")
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
        send_result = channel_sender.send_message(message, send_mode, confirm_phrase=confirm_phrase)
        if not send_result["ok"]:
            if send_mode == "real":
                outbox.update_outbox_status(
                    record_id,
                    REAL_BLOCKED_STATUS,
                    result={
                        "mode": send_mode,
                        "reason": send_result["error"],
                        "processed_at": util.now_local_iso(),
                        "sender": "channel_sender",
                    },
                )
            skipped.append(
                {
                    "id": record_id,
                    "channel": channel,
                    "recipient": recipient,
                    "reason": send_result["error"],
                }
            )
            continue
        if send_mode == "real":
            skipped.append(
                {
                    "id": record_id,
                    "channel": channel,
                    "recipient": recipient,
                    "reason": "real_send_unexpected_success_blocked",
                }
            )
            continue
        update_result = outbox.update_outbox_status(
            record_id,
            DRY_RUN_STATUS,
            result={
                "mode": send_result["data"]["mode"],
                "processed_at": send_result["data"]["processed_at"],
                "sender": "channel_sender",
                "dispatcher": send_result["data"].get("dispatcher", ""),
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
    data = {
        "send_mode": send_mode,
        "sender": sender,
        "limit": effective_limit,
        "max_messages_per_run": max_messages,
        "processed": processed,
        "skipped": skipped,
    }
    if send_mode == "real":
        return {"ok": False, "data": data, "error": "real send is not implemented"}
    return util.json_ok(data)


def dry_run(limit: int = 10) -> dict[str, Any]:
    """Simulate consuming pending outbox records without sending messages."""
    return consume_outbox(mode="dry_run", limit=limit)


def _build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(description="Consume local outbox messages without real sending.")
    parser.add_argument("command", nargs="?", choices=("dry-run",), help="Compatibility command for dry-run mode.")
    parser.add_argument("--mode", choices=("dry_run", "real"), default="dry_run")
    parser.add_argument("--confirm-phrase", default=None)
    parser.add_argument("--limit", type=int, default=10)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the command-line interface."""
    args = _build_parser().parse_args(argv)
    mode = "dry_run" if args.command == "dry-run" else args.mode
    result = consume_outbox(mode=mode, limit=args.limit, confirm_phrase=args.confirm_phrase)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
