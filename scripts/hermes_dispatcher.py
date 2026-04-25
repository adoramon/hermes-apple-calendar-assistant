"""Local Hermes dispatch placeholder.

This module only supports dry-run dispatch. It never sends network requests and
does not call WeChat, Telegram, or any external messaging API.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

try:
    from . import outbox, util
except ImportError:  # Allows running as: python3 scripts/hermes_dispatcher.py ...
    import outbox  # type: ignore
    import util  # type: ignore


DRY_RUN_MODE = "dry_run"
DRY_RUN_STATUS = "sent_dry_run"


def _json_error(message: str) -> dict[str, Any]:
    """Return a standard error envelope with explicit data=null."""
    return {"ok": False, "data": None, "error": message}


def _find_record(record_id: str) -> dict[str, Any] | None:
    """Find one outbox record by id."""
    for record in outbox.load_outbox_records():
        if record.get("id") == record_id:
            return record
    return None


def dry_run_dispatch_message(message: dict[str, Any]) -> dict[str, Any]:
    """Build the local Hermes dry-run dispatch result for one message."""
    if message.get("channel") != "hermes":
        return _json_error("unsupported channel")
    recipient = message.get("recipient")
    if not isinstance(recipient, str) or not recipient.strip():
        return _json_error("invalid recipient")
    return util.json_ok(
        {
            "mode": DRY_RUN_MODE,
            "message": dict(message),
            "status": DRY_RUN_STATUS,
            "processed_at": util.now_local_iso(),
        }
    )


def dry_run_dispatch(record_id: str, update_status: bool = True) -> dict[str, Any]:
    """Dry-run dispatch one pending outbox record by id."""
    record = _find_record(record_id)
    if record is None:
        return _json_error("outbox_record_not_found")
    if record.get("status") != "pending":
        return _json_error("only_pending_records_can_be_dispatched")

    message = record.get("message")
    if not isinstance(message, dict):
        return _json_error("invalid message")

    dispatch_result = dry_run_dispatch_message(message)
    if not dispatch_result["ok"]:
        return dispatch_result

    status = "pending"
    if update_status:
        update_result = outbox.update_outbox_status(
            record_id,
            DRY_RUN_STATUS,
            result={
                "mode": DRY_RUN_MODE,
                "processed_at": dispatch_result["data"]["processed_at"],
                "sender": "hermes_dispatcher",
            },
        )
        if not update_result["ok"]:
            return _json_error(str(update_result["error"]))
        status = DRY_RUN_STATUS

    return util.json_ok(
        {
            "id": record_id,
            "mode": DRY_RUN_MODE,
            "message": dispatch_result["data"]["message"],
            "status": status,
        }
    )


def _build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(description="Local Hermes dispatch placeholder.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    dry_run_parser = subparsers.add_parser("dry-run", help="Dry-run dispatch a pending outbox record.")
    dry_run_parser.add_argument("--id", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the command-line interface."""
    args = _build_parser().parse_args(argv)
    if args.command == "dry-run":
        result = dry_run_dispatch(args.id, update_status=True)
    else:
        raise AssertionError(args.command)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
