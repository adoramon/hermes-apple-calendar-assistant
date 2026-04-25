"""Hermes-facing local CLI for safe outbox inspection and dry-run marking."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

try:
    from . import outbox, util
except ImportError:  # Allows running as: python3 scripts/hermes_outbox_cli.py ...
    import outbox  # type: ignore
    import util  # type: ignore


DRY_RUN_STATUS = "sent_dry_run"


def _json_error(message: str) -> dict[str, Any]:
    """Return the Hermes CLI error envelope with data=null."""
    return {"ok": False, "data": None, "error": message}


def _message(record: dict[str, Any]) -> dict[str, Any]:
    """Return the nested outbound message as a dict."""
    message = record.get("message")
    if isinstance(message, dict):
        return message
    return {}


def _public_record(record: dict[str, Any]) -> dict[str, Any]:
    """Build the Hermes-safe representation of one outbox record."""
    message = _message(record)
    return {
        "id": record.get("id", ""),
        "created_at": record.get("created_at", ""),
        "status": record.get("status", ""),
        "channel": message.get("channel", ""),
        "recipient": message.get("recipient", ""),
        "message": message.get("message", ""),
        "metadata": message.get("metadata", {}),
    }


def _find_record(record_id: str) -> dict[str, Any] | None:
    """Find one outbox record by id."""
    for record in outbox.load_outbox_records():
        if record.get("id") == record_id:
            return record
    return None


def pending(limit: int = 10) -> dict[str, Any]:
    """Return pending outbox messages for Hermes to display."""
    records = [_public_record(record) for record in outbox.get_pending_outbox(limit)]
    return util.json_ok({"records": records})


def status(record_id: str) -> dict[str, Any]:
    """Return the current status for one outbox record."""
    record = _find_record(record_id)
    if record is None:
        return _json_error("outbox_record_not_found")
    return util.json_ok(_public_record(record))


def mark_dry_run_sent(record_id: str) -> dict[str, Any]:
    """Mark one pending outbox record as sent_dry_run without sending it."""
    record = _find_record(record_id)
    if record is None:
        return _json_error("outbox_record_not_found")
    if record.get("status") != "pending":
        return _json_error("only_pending_records_can_be_marked_sent_dry_run")

    result = outbox.update_outbox_status(
        record_id,
        DRY_RUN_STATUS,
        result={
            "mode": "dry_run",
            "processed_at": util.now_local_iso(),
            "source": "hermes_outbox_cli",
        },
    )
    if not result["ok"]:
        return _json_error(str(result["error"]))
    updated = result.get("record")
    if not isinstance(updated, dict):
        return _json_error("outbox_record_update_failed")
    return util.json_ok(_public_record(updated))


def _build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(description="Hermes-safe local outbox CLI.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    pending_parser = subparsers.add_parser("pending", help="List pending outbox messages.")
    pending_parser.add_argument("--limit", type=int, default=10)

    mark_parser = subparsers.add_parser("mark-dry-run-sent", help="Mark one pending message as sent_dry_run.")
    mark_parser.add_argument("--id", required=True)

    status_parser = subparsers.add_parser("status", help="Show one outbox record status.")
    status_parser.add_argument("--id", required=True)

    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the command-line interface."""
    args = _build_parser().parse_args(argv)
    if args.command == "pending":
        result = pending(args.limit)
    elif args.command == "mark-dry-run-sent":
        result = mark_dry_run_sent(args.id)
    elif args.command == "status":
        result = status(args.id)
    else:
        raise AssertionError(args.command)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
