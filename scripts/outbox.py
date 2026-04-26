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


def load_outbox_records() -> list[dict[str, Any]]:
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


def save_outbox_records_atomic(records: list[dict[str, Any]]) -> None:
    """Persist outbox records atomically as JSONL."""
    util.ensure_dir(OUTBOX_PATH.parent)
    tmp_path = OUTBOX_PATH.with_suffix(".jsonl.tmp")
    with tmp_path.open("w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
            fh.write("\n")
    tmp_path.replace(OUTBOX_PATH)


def update_outbox_status(record_id: str, status: str, result: dict[str, Any] | None = None) -> dict[str, Any]:
    """Update one outbox record status and optional result by id."""
    records = load_outbox_records()
    updated_record = None
    for record in records:
        if record.get("id") != record_id:
            continue
        record["status"] = status
        if result is not None:
            record["result"] = result
        updated_record = record
        break
    if updated_record is None:
        return {"ok": False, "error": "outbox_record_not_found", "record": None}
    save_outbox_records_atomic(records)
    return {"ok": True, "error": None, "record": updated_record}


def update_outbox_statuses(
    record_ids: list[str],
    status: str,
    result: dict[str, Any] | None = None,
    only_if_status: str | None = None,
) -> dict[str, Any]:
    """Update multiple outbox records by id, optionally filtering by current status."""
    target_ids = {record_id for record_id in record_ids if isinstance(record_id, str) and record_id}
    if not target_ids:
        return {"ok": True, "error": None, "updated_records": []}

    records = load_outbox_records()
    updated_records = []
    for record in records:
        record_id = record.get("id")
        if record_id not in target_ids:
            continue
        if only_if_status is not None and record.get("status") != only_if_status:
            continue
        record["status"] = status
        if result is not None:
            record["result"] = dict(result)
        updated_records.append(record)
    save_outbox_records_atomic(records)
    return {"ok": True, "error": None, "updated_records": updated_records}


def get_pending_outbox(limit: int = 20) -> list[dict[str, Any]]:
    """Return pending outbox records, oldest first."""
    pending = [record for record in load_outbox_records() if record.get("status") == "pending"]
    return pending[: max(limit, 0)]


def _existing_ids() -> set[str]:
    """Return all ids already present in the outbox."""
    ids = set()
    for record in load_outbox_records():
        record_id = record.get("id")
        if isinstance(record_id, str) and record_id:
            ids.add(record_id)
    return ids


def build_outbox_record(message: dict[str, Any]) -> dict[str, Any]:
    """Build a pending dry-run outbox record for one outbound message."""
    created_at = util.now_local_iso()
    return {
        "id": _record_id(message),
        "created_at": created_at,
        "status": "pending",
        "message": message,
        "result": None,
        "audit": {
            "created_at": created_at,
            "source": "outbox",
        },
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
    records = load_outbox_records()
    return list(reversed(records[-max(limit, 0) :]))


def _summarize_record(record: dict[str, Any]) -> dict[str, Any]:
    """Return a compact record shape for list output."""
    message = record.get("message")
    if not isinstance(message, dict):
        message = {}
    result = record.get("result")
    if not isinstance(result, dict):
        result = {}
    return {
        "id": record.get("id", ""),
        "created_at": record.get("created_at", ""),
        "status": record.get("status", ""),
        "channel": message.get("channel", ""),
        "recipient": message.get("recipient", ""),
        "message": message.get("message", ""),
        "result": {
            "mode": result.get("mode", ""),
            "note": result.get("note", ""),
            "reason": result.get("reason", ""),
            "processed_at": result.get("processed_at", ""),
            "sender": result.get("sender", ""),
            "dispatcher": result.get("dispatcher", ""),
        },
    }


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
        records = [_summarize_record(record) for record in load_recent_outbox(args.limit)]
        result = util.json_ok({"records": records})
    else:
        raise AssertionError(args.command)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
