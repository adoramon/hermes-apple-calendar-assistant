"""Local dry-run outbox queue for outbound messages."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

try:
    from . import util
except ImportError:  # Allows running as: python3 scripts/outbox.py ...
    import util  # type: ignore


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTBOX_PATH = PROJECT_ROOT / "data" / "outbox_messages.jsonl"


def _message_identity(message: dict[str, Any]) -> str:
    """Build the stable idempotency identity for one outbound message."""
    metadata = message.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    identity = {
        "channel": message.get("channel", ""),
        "recipient": message.get("recipient", ""),
        "fingerprint": metadata.get("fingerprint", ""),
        "offset_minutes": metadata.get("offset_minutes", ""),
    }
    if not identity["fingerprint"]:
        identity["message"] = message.get("message", "")
        identity["metadata"] = metadata
    return json.dumps(identity, ensure_ascii=False, sort_keys=True)


def _record_id(message: dict[str, Any]) -> str:
    """Return a stable SHA1 id for one outbound message."""
    return hashlib.sha1(_message_identity(message).encode("utf-8")).hexdigest()


def _read_outbox_records() -> list[dict[str, Any]]:
    """Read all valid outbox records from the JSONL queue."""
    if not OUTBOX_PATH.exists():
        return []
    records = []
    for line in OUTBOX_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict):
            records.append(record)
    return records


def _existing_ids() -> set[str]:
    """Return all ids already present in the outbox."""
    ids = set()
    for record in _read_outbox_records():
        record_id = record.get("id")
        if isinstance(record_id, str) and record_id:
            ids.add(record_id)
    return ids


def build_outbox_record(message: dict[str, Any]) -> dict[str, Any]:
    """Build a pending dry-run outbox record for one outbound message."""
    return {
        "id": _record_id(message),
        "created_at": util.now_local_iso(),
        "status": "pending",
        "message": message,
    }


def append_outbox_message(message: dict[str, Any]) -> dict[str, Any]:
    """Append one outbound message to the outbox unless it already exists."""
    record = build_outbox_record(message)
    if record["id"] in _existing_ids():
        return {
            "written": False,
            "id": record["id"],
            "reason": "already_in_outbox",
        }

    util.ensure_dir(OUTBOX_PATH.parent)
    with OUTBOX_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
        fh.write("\n")
    return {
        "written": True,
        "id": record["id"],
        "record": record,
    }


def append_outbox_messages(messages: list[dict[str, Any]]) -> dict[str, Any]:
    """Append outbound messages and return written records plus skipped items."""
    written = []
    skipped = []
    seen_ids = _existing_ids()
    util.ensure_dir(OUTBOX_PATH.parent)
    with OUTBOX_PATH.open("a", encoding="utf-8") as fh:
        for message in messages:
            record = build_outbox_record(message)
            if record["id"] in seen_ids:
                skipped.append(
                    {
                        "id": record["id"],
                        "reason": "already_in_outbox",
                        "message": message,
                    }
                )
                continue
            fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
            fh.write("\n")
            seen_ids.add(record["id"])
            written.append(record)
    return {"written": written, "skipped": skipped}


def load_recent_outbox(limit: int = 20) -> list[dict[str, Any]]:
    """Load recent outbox records, newest first."""
    records = _read_outbox_records()
    return list(reversed(records[-max(limit, 0) :]))


def _build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(description="Inspect the local dry-run outbound message queue.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    list_parser = subparsers.add_parser("list", help="List recent outbox messages.")
    list_parser.add_argument("--limit", type=int, default=20)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the command-line interface."""
    args = _build_parser().parse_args(argv)
    if args.command == "list":
        result = util.json_ok({"records": load_recent_outbox(args.limit)})
    else:
        raise AssertionError(args.command)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
