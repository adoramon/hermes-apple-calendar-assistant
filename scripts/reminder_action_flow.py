"""Confirmation flow for reminder follow-up actions."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

try:
    from . import calendar_ops, reminder_action_parser, reminder_context, util
except ImportError:  # Allows running as: python3 scripts/reminder_action_flow.py ...
    import calendar_ops  # type: ignore
    import reminder_action_parser  # type: ignore
    import reminder_context  # type: ignore
    import util  # type: ignore


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PENDING_CONFIRMATIONS_PATH = PROJECT_ROOT / "data" / "pending_confirmations.json"
REMINDER_ACTION_STATE_PATH = PROJECT_ROOT / "data" / "reminder_action_state.json"
ACTION_PREFIX = "reminder_action"


def _result(ok: bool, data: Any = None, error: str | None = None) -> dict[str, Any]:
    return {"ok": ok, "data": data, "error": error}


def _read_pending_store() -> dict[str, Any]:
    raw = util.load_json(PENDING_CONFIRMATIONS_PATH, {"sessions": {}})
    if not isinstance(raw, dict):
        return {"sessions": {}}
    sessions = raw.get("sessions")
    if not isinstance(sessions, dict):
        sessions = {}
    raw["sessions"] = sessions
    return raw


def _write_pending_store(store: dict[str, Any]) -> None:
    util.save_json_atomic(PENDING_CONFIRMATIONS_PATH, store)


def _parse_dt(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _event_identity_from_latest() -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    record = reminder_context.get_latest_sent_reminder()
    if record is None:
        return None, None
    return record, reminder_context.extract_calendar_event_identity(record)


def _build_session_key(text: str, record_id: str, intent: str) -> str:
    raw = "|".join([ACTION_PREFIX, record_id, intent, text, util.now_local_iso()])
    return f"{ACTION_PREFIX}_{hashlib.sha1(raw.encode('utf-8')).hexdigest()[:12]}"


def _build_proposed_change(intent: str, action: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    start = _parse_dt(event.get("start"))
    end = _parse_dt(event.get("end"))
    if intent == "snooze":
        return {"snooze_minutes": action.get("minutes")}
    if intent == "reschedule" and action.get("target_time") and start and end:
        new_start = _parse_dt(action["target_time"])
        if new_start is None:
            return {"target_time": action.get("target_time")}
        new_end = new_start + (end - start)
        return {"new_start": new_start.isoformat(timespec="minutes"), "new_end": new_end.isoformat(timespec="minutes")}
    if intent == "cancel":
        return {"delete_event": True}
    if intent == "change_offset":
        return {"offset_minutes": action.get("minutes")}
    if intent in {"arrived", "disable_reminder"}:
        return {"status": intent}
    return {}


def _summary(intent: str, event: dict[str, Any], proposed_change: dict[str, Any]) -> str:
    lines = [
        "请确认提醒后续操作：",
        f"操作：{intent}",
        f"日历：{event.get('calendar', '')}",
        f"标题：{event.get('title', '')}",
        f"原时间：{event.get('start', '')} - {event.get('end', '')}",
    ]
    if proposed_change.get("new_start"):
        lines.append(f"新时间：{proposed_change['new_start']} - {proposed_change.get('new_end', '')}")
    if proposed_change.get("snooze_minutes"):
        lines.append(f"延后提醒：{proposed_change['snooze_minutes']} 分钟")
    if proposed_change.get("offset_minutes"):
        lines.append(f"提醒提前量：{proposed_change['offset_minutes']} 分钟")
    return "\n".join(lines)


def draft_action(text: str) -> dict[str, Any]:
    action_result = reminder_action_parser.parse_action_text(text)
    if not action_result["ok"]:
        return action_result
    action = action_result["data"]
    intent = action.get("intent")
    if intent == "unknown":
        return _result(False, data=action, error="unknown_reminder_action")

    record, event = _event_identity_from_latest()
    if record is None or event is None:
        candidates = [
            reminder_context.extract_calendar_event_identity(item)
            for item in reminder_context.get_recent_sent_reminders(limit=5)
        ]
        return _result(False, data={"candidates": candidates}, error="no_recent_reminder_context")
    if not event.get("calendar") or not event.get("title"):
        candidates = [
            reminder_context.extract_calendar_event_identity(item)
            for item in reminder_context.get_recent_sent_reminders(limit=5)
        ]
        return _result(False, data={"candidates": candidates}, error="reminder_context_incomplete")

    proposed_change = _build_proposed_change(intent, action, event)
    if intent == "reschedule" and not proposed_change.get("new_start"):
        return _result(False, data={"action": action, "target_event": event}, error="reschedule_target_time_unresolved")
    if intent == "change_offset" and not proposed_change.get("offset_minutes"):
        return _result(False, data={"action": action, "target_event": event}, error="change_offset_minutes_unresolved")

    session_key = _build_session_key(text, str(event.get("record_id", "")), str(intent))
    pending = {
        "session_key": session_key,
        "action": "reminder_action",
        "status": "pending",
        "created_at": util.now_local_iso(),
        "intent": intent,
        "source_text": text,
        "record_id": event.get("record_id", ""),
        "target_event": event,
        "proposed_change": proposed_change,
        "needs_confirmation": True,
        "summary": _summary(str(intent), event, proposed_change),
    }
    store = _read_pending_store()
    store.setdefault("sessions", {})[session_key] = pending
    _write_pending_store(store)
    return _result(
        True,
        data={
            "session_key": session_key,
            "intent": intent,
            "target_event": {
                "calendar": event.get("calendar", ""),
                "title": event.get("title", ""),
                "start": event.get("start", ""),
                "end": event.get("end", ""),
            },
            "proposed_change": proposed_change,
            "needs_confirmation": True,
            "summary": pending["summary"],
        },
    )


def _load_pending(session_key: str) -> dict[str, Any] | None:
    return _read_pending_store().get("sessions", {}).get(session_key)


def _record_state(pending: dict[str, Any], result: dict[str, Any]) -> None:
    raw = util.load_json(REMINDER_ACTION_STATE_PATH, {"actions": []})
    if not isinstance(raw, dict):
        raw = {"actions": []}
    actions = raw.get("actions")
    if not isinstance(actions, list):
        actions = []
    actions.append(
        {
            "session_key": pending.get("session_key", ""),
            "record_id": pending.get("record_id", ""),
            "intent": pending.get("intent", ""),
            "processed_at": util.now_local_iso(),
            "result": result,
        }
    )
    raw["actions"] = actions[-200:]
    util.save_json_atomic(REMINDER_ACTION_STATE_PATH, raw)


def confirm_action(session_key: str) -> dict[str, Any]:
    pending = _load_pending(session_key)
    if not pending:
        return _result(False, error=f"No pending reminder action found for session: {session_key}")
    if pending.get("status") != "pending":
        return _result(False, error=f"Reminder action is not pending for session: {session_key}")
    if pending.get("action") != "reminder_action":
        return _result(False, error=f"Unsupported pending action: {pending.get('action')}")

    intent = pending.get("intent")
    event = pending.get("target_event", {})
    proposed = pending.get("proposed_change", {})
    if not isinstance(event, dict) or not isinstance(proposed, dict):
        return _result(False, error="pending reminder action is malformed")

    if intent == "cancel":
        action_result = calendar_ops.delete_event(str(event.get("calendar", "")), str(event.get("title", "")))
    elif intent == "reschedule":
        action_result = calendar_ops.update_event(
            str(event.get("calendar", "")),
            str(event.get("title", "")),
            start_dt=proposed.get("new_start"),
            end_dt=proposed.get("new_end"),
        )
    elif intent in {"snooze", "arrived", "disable_reminder", "change_offset"}:
        action_result = _result(True, data={"recorded": True, "intent": intent, "proposed_change": proposed})
    else:
        return _result(False, error=f"Unsupported reminder action intent: {intent}")

    if not action_result["ok"]:
        return action_result

    store = _read_pending_store()
    saved = store.setdefault("sessions", {}).get(session_key, pending)
    saved["status"] = "confirmed"
    saved["confirmed_at"] = util.now_local_iso()
    saved["result"] = action_result["data"]
    store["sessions"][session_key] = saved
    _write_pending_store(store)
    _record_state(saved, action_result["data"])
    return _result(True, data={"session_key": session_key, "intent": intent, "result": action_result["data"]})


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Draft and confirm reminder follow-up actions.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    draft = subparsers.add_parser("draft")
    draft.add_argument("--text", required=True)
    confirm = subparsers.add_parser("confirm")
    confirm.add_argument("--session-key", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "draft":
        result = draft_action(args.text)
    elif args.command == "confirm":
        result = confirm_action(args.session_key)
    else:
        raise AssertionError(args.command)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
