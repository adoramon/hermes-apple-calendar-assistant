"""Platform-neutral draft and confirmation flow for creating calendar events."""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from . import calendar_ops
except ImportError:  # Allows running as: python3 scripts/interactive_create.py ...
    import calendar_ops  # type: ignore


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PENDING_CONFIRMATIONS_PATH = PROJECT_ROOT / "data" / "pending_confirmations.json"
REQUIRED_FIELDS = ("calendar_name", "title", "start_dt", "end_dt")
OPTIONAL_FIELDS = ("location", "notes")


def _result(ok: bool, data: Any = None, error: str | None = None) -> dict[str, Any]:
    return {"ok": ok, "data": data, "error": error}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_pending_store() -> dict[str, Any]:
    if not PENDING_CONFIRMATIONS_PATH.exists():
        return {"confirmations": {}}
    try:
        raw = json.loads(PENDING_CONFIRMATIONS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"confirmations": {}}
    if "confirmations" not in raw or not isinstance(raw["confirmations"], dict):
        return {"confirmations": raw if isinstance(raw, dict) else {}}
    return raw


def _write_pending_store(store: dict[str, Any]) -> None:
    PENDING_CONFIRMATIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    PENDING_CONFIRMATIONS_PATH.write_text(
        json.dumps(store, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def build_draft_from_slots(payload: dict[str, Any]) -> dict[str, Any]:
    """Build a normalized create-event draft from structured slot data."""
    slots = payload.get("slots", payload)
    if not isinstance(slots, dict):
        return _result(False, error="payload must be a dict or contain a dict 'slots' field.")

    draft = {
        "action": "create_event",
        "calendar_name": slots.get("calendar_name") or slots.get("calendar"),
        "title": slots.get("title"),
        "start_dt": slots.get("start_dt") or slots.get("start"),
        "end_dt": slots.get("end_dt") or slots.get("end"),
        "location": slots.get("location", ""),
        "notes": slots.get("notes", ""),
    }
    missing_fields = get_missing_fields(draft)["data"]["missing_fields"]
    return _result(True, data={"draft": draft, "missing_fields": missing_fields})


def get_missing_fields(draft: dict[str, Any]) -> dict[str, Any]:
    """Return required fields that are absent or empty in the draft."""
    missing = [field for field in REQUIRED_FIELDS if not draft.get(field)]
    return _result(True, data={"missing_fields": missing})


def build_confirmation_summary(draft: dict[str, Any]) -> dict[str, Any]:
    """Build a human-readable summary for the pending create action."""
    missing = get_missing_fields(draft)["data"]["missing_fields"]
    if missing:
        return _result(False, error=f"Missing required fields: {', '.join(missing)}")

    lines = [
        "请确认是否创建以下日历事件：",
        f"- 日历：{draft['calendar_name']}",
        f"- 标题：{draft['title']}",
        f"- 开始：{draft['start_dt']}",
        f"- 结束：{draft['end_dt']}",
    ]
    if draft.get("location"):
        lines.append(f"- 地点：{draft['location']}")
    if draft.get("notes"):
        lines.append(f"- 备注：{draft['notes']}")
    return _result(True, data={"summary": "\n".join(lines)})


def save_pending_confirmation(draft: dict[str, Any]) -> dict[str, Any]:
    """Persist a create-event draft until the caller confirms or cancels it."""
    summary_result = build_confirmation_summary(draft)
    if not summary_result["ok"]:
        return summary_result

    confirmation_id = uuid.uuid4().hex
    pending_task = {
        "id": confirmation_id,
        "action": "create_event",
        "status": "pending",
        "created_at": _now_iso(),
        "draft": draft,
        "summary": summary_result["data"]["summary"],
    }

    store = _read_pending_store()
    store.setdefault("confirmations", {})[confirmation_id] = pending_task
    _write_pending_store(store)

    return _result(
        True,
        data={
            "confirmation_id": confirmation_id,
            "summary": pending_task["summary"],
            "pending": pending_task,
        },
    )


def confirm_pending_action(confirmation_id: str) -> dict[str, Any]:
    """Confirm a pending create action and write it to Calendar.app."""
    store = _read_pending_store()
    pending = store.get("confirmations", {}).get(confirmation_id)
    if not pending:
        return _result(False, error=f"No pending confirmation found: {confirmation_id}")
    if pending.get("status") != "pending":
        return _result(False, error=f"Confirmation is not pending: {confirmation_id}")
    if pending.get("action") != "create_event":
        return _result(False, error=f"Unsupported pending action: {pending.get('action')}")

    draft = pending.get("draft", {})
    missing = get_missing_fields(draft)["data"]["missing_fields"]
    if missing:
        return _result(False, error=f"Pending draft is missing fields: {', '.join(missing)}")

    create_result = calendar_ops.create_event(
        draft["calendar_name"],
        draft["title"],
        draft["start_dt"],
        draft["end_dt"],
        location=draft.get("location", ""),
        notes=draft.get("notes", ""),
    )
    if not create_result["ok"]:
        return create_result

    pending["status"] = "confirmed"
    pending["confirmed_at"] = _now_iso()
    pending["result"] = create_result["data"]
    store["confirmations"][confirmation_id] = pending
    _write_pending_store(store)

    return _result(
        True,
        data={"confirmation_id": confirmation_id, "calendar_result": create_result["data"]},
    )


def cancel_pending_action(confirmation_id: str) -> dict[str, Any]:
    """Cancel a pending action without touching Calendar.app."""
    store = _read_pending_store()
    pending = store.get("confirmations", {}).get(confirmation_id)
    if not pending:
        return _result(False, error=f"No pending confirmation found: {confirmation_id}")
    if pending.get("status") != "pending":
        return _result(False, error=f"Confirmation is not pending: {confirmation_id}")

    pending["status"] = "cancelled"
    pending["cancelled_at"] = _now_iso()
    store["confirmations"][confirmation_id] = pending
    _write_pending_store(store)
    return _result(True, data={"confirmation_id": confirmation_id, "status": "cancelled"})


def _load_payload(value: str) -> dict[str, Any]:
    path = Path(value)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return json.loads(value)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create-event confirmation workflow demo.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    draft = subparsers.add_parser("draft", help="Create and save a pending draft.")
    draft.add_argument("payload", help="JSON payload string or path to a JSON file.")

    confirm = subparsers.add_parser("confirm", help="Confirm a pending draft.")
    confirm.add_argument("confirmation_id")

    cancel = subparsers.add_parser("cancel", help="Cancel a pending draft.")
    cancel.add_argument("confirmation_id")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "draft":
        try:
            payload = _load_payload(args.payload)
        except (OSError, json.JSONDecodeError) as exc:
            result = _result(False, error=f"Invalid payload: {exc}")
        else:
            draft_result = build_draft_from_slots(payload)
            if not draft_result["ok"]:
                result = draft_result
            elif draft_result["data"]["missing_fields"]:
                result = draft_result
            else:
                result = save_pending_confirmation(draft_result["data"]["draft"])
    elif args.command == "confirm":
        result = confirm_pending_action(args.confirmation_id)
    elif args.command == "cancel":
        result = cancel_pending_action(args.confirmation_id)
    else:
        parser.error(f"Unknown command: {args.command}")

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
