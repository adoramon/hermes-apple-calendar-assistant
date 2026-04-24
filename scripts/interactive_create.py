"""Platform-neutral state manager for conversational event creation."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from . import calendar_ops, conflict_checker
except ImportError:  # Allows running as: python3 scripts/interactive_create.py demo
    import calendar_ops  # type: ignore
    import conflict_checker  # type: ignore


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PENDING_CONFIRMATIONS_PATH = PROJECT_ROOT / "data" / "pending_confirmations.json"

ALLOWED_CALENDARS = ("商务计划", "家庭计划", "个人计划", "夫妻计划")
REQUIRED_FIELDS = ("calendar", "title", "start", "end")
DRAFT_FIELDS = ("calendar", "title", "start", "end", "location", "notes")


def _result(ok: bool, data: Any = None, error: str | None = None) -> dict[str, Any]:
    return {"ok": ok, "data": data, "error": error}


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _format_datetime_for_summary(value: Any) -> str:
    if not isinstance(value, str):
        return str(value)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return value
    return parsed.strftime("%Y-%m-%d %H:%M")


def _format_time_range_for_summary(start: Any, end: Any) -> str:
    start_text = _format_datetime_for_summary(start)
    end_text = _format_datetime_for_summary(end)
    if isinstance(start_text, str) and isinstance(end_text, str):
        start_day = start_text[:10]
        if start_day and end_text.startswith(start_day):
            return f"{start_text} - {end_text[11:]}"
    return f"{start_text} - {end_text}"


def _read_pending_store() -> dict[str, Any]:
    if not PENDING_CONFIRMATIONS_PATH.exists():
        return {"sessions": {}}
    try:
        raw = json.loads(PENDING_CONFIRMATIONS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"sessions": {}}
    if not isinstance(raw, dict):
        return {"sessions": {}}
    if "sessions" in raw and isinstance(raw["sessions"], dict):
        return raw
    if "confirmations" in raw and isinstance(raw["confirmations"], dict):
        return {"sessions": raw["confirmations"]}
    return {"sessions": raw}


def _write_pending_store(store: dict[str, Any]) -> None:
    PENDING_CONFIRMATIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    PENDING_CONFIRMATIONS_PATH.write_text(
        json.dumps(store, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def build_draft_from_slots(payload: dict[str, Any]) -> dict[str, Any]:
    """Build a normalized draft from structured slot data."""
    slots = payload.get("slots", payload)
    if not isinstance(slots, dict):
        return _result(False, error="payload must be a dict or contain a dict 'slots' field.")

    draft = {
        "calendar": slots.get("calendar") or slots.get("calendar_name"),
        "title": slots.get("title"),
        "start": slots.get("start") or slots.get("start_dt"),
        "end": slots.get("end") or slots.get("end_dt"),
        "location": slots.get("location", ""),
        "notes": slots.get("notes", ""),
    }
    validation = get_missing_fields(draft)
    return _result(True, data={"draft": draft, **validation["data"]})


def get_missing_fields(draft: dict[str, Any]) -> dict[str, Any]:
    """Return absent required fields and invalid draft values."""
    missing = [field for field in REQUIRED_FIELDS if not draft.get(field)]
    invalid = []
    calendar = draft.get("calendar")
    if calendar and calendar not in ALLOWED_CALENDARS:
        invalid.append(
            {
                "field": "calendar",
                "message": f"calendar must be one of: {', '.join(ALLOWED_CALENDARS)}",
            }
        )
    return _result(True, data={"missing_fields": missing, "invalid_fields": invalid})


def build_confirmation_summary(draft: dict[str, Any]) -> dict[str, Any]:
    """Build a concise confirmation message for a pending create action."""
    validation = get_missing_fields(draft)
    missing = validation["data"]["missing_fields"]
    invalid = validation["data"]["invalid_fields"]
    if missing:
        return _result(False, error=f"Missing required fields: {', '.join(missing)}")
    if invalid:
        return _result(False, error=invalid[0]["message"])

    lines = [
        "请确认是否创建日程：",
        f"日历：{draft['calendar']}",
        f"标题：{draft['title']}",
        f"时间：{_format_time_range_for_summary(draft['start'], draft['end'])}",
    ]
    if draft.get("location"):
        lines.append(f"地点：{draft['location']}")
    if draft.get("notes"):
        lines.append(f"说明：{draft['notes']}")
    return _result(True, data={"summary": "\n".join(lines)})


def save_pending_confirmation(
    session_key: str,
    draft: dict[str, Any],
    conflict_check: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Save a draft by session key; Calendar.app is not written until confirm."""
    summary_result = build_confirmation_summary(draft)
    if not summary_result["ok"]:
        return summary_result

    normalized_draft = {field: draft.get(field, "") for field in DRAFT_FIELDS}
    pending = {
        "session_key": session_key,
        "action": "create_event",
        "status": "pending",
        "created_at": _now_iso(),
        "draft": normalized_draft,
        "summary": summary_result["data"]["summary"],
    }
    if conflict_check is not None:
        pending["conflict_check"] = conflict_check
    try:
        store = _read_pending_store()
        store.setdefault("sessions", {})[session_key] = pending
        _write_pending_store(store)
    except OSError as exc:
        return _result(False, error=f"Failed to save pending confirmation: {exc}")

    return _result(True, data={"session_key": session_key, "pending": pending})


def load_pending_confirmation(session_key: str) -> dict[str, Any]:
    """Load a pending confirmation without modifying Calendar.app."""
    pending = _read_pending_store().get("sessions", {}).get(session_key)
    if not pending:
        return _result(False, error=f"No pending confirmation found for session: {session_key}")
    return _result(True, data={"session_key": session_key, "pending": pending})


def confirm_pending_action(session_key: str) -> dict[str, Any]:
    """Confirm a pending create action and write it to Calendar.app."""
    load_result = load_pending_confirmation(session_key)
    if not load_result["ok"]:
        return load_result

    pending = load_result["data"]["pending"]
    if pending.get("status") != "pending":
        return _result(False, error=f"Confirmation is not pending for session: {session_key}")
    if pending.get("action") != "create_event":
        return _result(False, error=f"Unsupported pending action: {pending.get('action')}")

    draft = pending.get("draft", {})
    summary_result = build_confirmation_summary(draft)
    if not summary_result["ok"]:
        return summary_result

    create_result = calendar_ops.create_event(
        draft["calendar"],
        draft["title"],
        draft["start"],
        draft["end"],
        location=draft.get("location", ""),
        notes=draft.get("notes", ""),
    )
    if not create_result["ok"]:
        return create_result

    try:
        store = _read_pending_store()
        pending["status"] = "confirmed"
        pending["confirmed_at"] = _now_iso()
        pending["result"] = create_result["data"]
        store.setdefault("sessions", {})[session_key] = pending
        _write_pending_store(store)
    except OSError as exc:
        return _result(False, error=f"Calendar event created, but state update failed: {exc}")

    return _result(True, data={"session_key": session_key, "calendar_result": create_result["data"]})


def cancel_pending_action(session_key: str) -> dict[str, Any]:
    """Cancel a pending action without touching Calendar.app."""
    load_result = load_pending_confirmation(session_key)
    if not load_result["ok"]:
        return load_result

    pending = load_result["data"]["pending"]
    if pending.get("status") != "pending":
        return _result(False, error=f"Confirmation is not pending for session: {session_key}")

    try:
        store = _read_pending_store()
        pending["status"] = "cancelled"
        pending["cancelled_at"] = _now_iso()
        store.setdefault("sessions", {})[session_key] = pending
        _write_pending_store(store)
    except OSError as exc:
        return _result(False, error=f"Failed to cancel pending confirmation: {exc}")

    return _result(True, data={"session_key": session_key, "status": "cancelled"})


def _run_demo() -> dict[str, Any]:
    """Run a local demo without creating a Calendar.app event."""
    session_key = "demo_session"
    invalid_session_key = "demo_invalid_calendar"
    payload = {
        "calendar": "个人计划",
        "title": "[测试] Interactive Create Demo",
        "start": "2026-04-16T11:00:00",
        "end": "2026-04-16T12:00:00",
        "location": "测试地点",
        "notes": "CLI demo only; confirm_pending_action() would create the event.",
    }
    draft_result = build_draft_from_slots(payload)
    if not draft_result["ok"]:
        return draft_result
    save_result = save_pending_confirmation(session_key, draft_result["data"]["draft"])
    if not save_result["ok"]:
        return save_result
    load_result = load_pending_confirmation(session_key)
    if not load_result["ok"]:
        return load_result
    cancel_result = cancel_pending_action(session_key)
    if not cancel_result["ok"]:
        return cancel_result

    invalid_payload = {
        "calendar": "飞行计划",
        "title": "[测试] Invalid Calendar Demo",
        "start": "2026-04-16T13:00:00",
        "end": "2026-04-16T14:00:00",
        "location": "测试地点",
        "notes": "This should not be saved as a confirmable pending action.",
    }
    invalid_draft_result = build_draft_from_slots(invalid_payload)
    if not invalid_draft_result["ok"]:
        return invalid_draft_result
    invalid_save_result = save_pending_confirmation(
        invalid_session_key,
        invalid_draft_result["data"]["draft"],
    )
    invalid_load_result = load_pending_confirmation(invalid_session_key)

    return _result(
        True,
        data={
            "valid_calendar_flow": {
                "draft": draft_result["data"],
                "saved": save_result["data"],
                "loaded": load_result["data"],
                "cancelled": cancel_result["data"],
            },
            "invalid_calendar_flow": {
                "draft": invalid_draft_result["data"],
                "save_attempt": invalid_save_result,
                "load_attempt": invalid_load_result,
                "expected": "invalid_fields contains calendar, save_attempt.ok is false, and load_attempt.ok is false.",
            },
            "note": "Demo does not call confirm_pending_action(), so it does not write to Calendar.app.",
        },
    )


def _create_draft_from_args(args: argparse.Namespace) -> dict[str, Any]:
    payload = {
        "calendar": args.calendar,
        "title": args.title,
        "start": args.start,
        "end": args.end,
        "location": args.location,
        "notes": args.notes,
    }
    draft_result = build_draft_from_slots(payload)
    if not draft_result["ok"]:
        return draft_result

    draft_data = draft_result["data"]
    if draft_data["missing_fields"] or draft_data["invalid_fields"]:
        return _result(False, data=draft_data, error="Draft is incomplete or invalid.")

    conflict_check = None
    if args.check_conflict:
        conflict_result = conflict_checker.check_conflicts(
            draft_data["draft"]["calendar"],
            draft_data["draft"]["start"],
            draft_data["draft"]["end"],
        )
        if not conflict_result["ok"]:
            return conflict_result
        conflict_check = conflict_result["data"]

    save_result = save_pending_confirmation(
        args.session_key,
        draft_data["draft"],
        conflict_check=conflict_check,
    )
    if not save_result["ok"]:
        return save_result

    data = {
        "draft": draft_data["draft"],
        "missing_fields": draft_data["missing_fields"],
        "invalid_fields": draft_data["invalid_fields"],
        "pending": save_result["data"]["pending"],
        "summary": save_result["data"]["pending"]["summary"],
    }
    if conflict_check is not None:
        data["conflict_check"] = conflict_check
        data["has_conflict"] = conflict_check["has_conflict"]
        data["conflicts"] = conflict_check["conflicts"]
        data["suggested_slots"] = conflict_check["suggested_slots"]
    return _result(True, data=data)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create-event confirmation workflow demo.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_draft = subparsers.add_parser(
        "create-draft",
        help="Build, validate, and save a pending create-event draft.",
    )
    create_draft.add_argument("--session-key", required=True, help="Stable caller/session id.")
    create_draft.add_argument("--calendar", required=True, help="Target calendar name.")
    create_draft.add_argument("--title", required=True, help="Event title.")
    create_draft.add_argument("--start", required=True, help="ISO datetime, e.g. 2026-04-18T15:00:00.")
    create_draft.add_argument("--end", required=True, help="ISO datetime, e.g. 2026-04-18T16:00:00.")
    create_draft.add_argument("--location", default="", help="Optional event location.")
    create_draft.add_argument("--notes", default="", help="Optional event notes.")
    create_draft.add_argument("--check-conflict", action="store_true", help="Attach a read-only conflict check.")

    show_pending = subparsers.add_parser("show-pending", help="Show pending confirmation for a session.")
    show_pending.add_argument("--session-key", required=True, help="Stable caller/session id.")

    confirm = subparsers.add_parser("confirm", help="Confirm a pending create-event action.")
    confirm.add_argument("--session-key", required=True, help="Stable caller/session id.")

    cancel = subparsers.add_parser("cancel", help="Cancel a pending create-event action.")
    cancel.add_argument("--session-key", required=True, help="Stable caller/session id.")

    subparsers.add_parser("demo", help="Run a local draft/save/load/cancel demo.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "create-draft":
        result = _create_draft_from_args(args)
    elif args.command == "show-pending":
        result = load_pending_confirmation(args.session_key)
    elif args.command == "confirm":
        result = confirm_pending_action(args.session_key)
    elif args.command == "cancel":
        result = cancel_pending_action(args.session_key)
    elif args.command == "demo":
        result = _run_demo()
    else:
        parser.error(f"Unknown command: {args.command}")

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
