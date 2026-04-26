"""Draft/confirm flow for hotel orders into Apple Calendar."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from . import assistant_persona, calendar_ops, hotel_order_parser, util
except ImportError:  # Allows running as: python3 scripts/hotel_order_flow.py ...
    import assistant_persona  # type: ignore
    import calendar_ops  # type: ignore
    import hotel_order_parser  # type: ignore
    import util  # type: ignore


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PENDING_CONFIRMATIONS_PATH = PROJECT_ROOT / "data" / "pending_confirmations.json"
ALLOWED_HOTEL_CALENDARS = {"个人计划", "夫妻计划"}
TIME_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")


def _result(ok: bool, data: Any = None, error: str | None = None) -> dict[str, Any]:
    return {"ok": ok, "data": data, "error": error}


def _read_store() -> dict[str, Any]:
    raw = util.load_json(PENDING_CONFIRMATIONS_PATH, {"sessions": {}})
    if not isinstance(raw, dict):
        return {"sessions": {}}
    sessions = raw.get("sessions")
    if not isinstance(sessions, dict):
        sessions = {}
    raw["sessions"] = sessions
    return raw


def _write_store(store: dict[str, Any]) -> None:
    util.save_json_atomic(PENDING_CONFIRMATIONS_PATH, store)


def _session_key(text: str) -> str:
    raw = "|".join(["hotel_order", text, util.now_local_iso()])
    return f"hotel_order_{hashlib.sha1(raw.encode('utf-8')).hexdigest()[:12]}"


def _normalize_time(value: str | None) -> str | None:
    if not value:
        return None
    match = TIME_RE.match(value.strip())
    if not match:
        return None
    return f"{int(match.group(1)):02d}:{int(match.group(2)):02d}"


def _build_notes(order: dict[str, Any], assumptions: list[str]) -> str:
    fields = [
        ("酒店名称", order.get("hotel_name")),
        ("入住日期", order.get("checkin_date")),
        ("离店日期", order.get("checkout_date")),
        ("入住人", order.get("guest_name")),
        ("房型", order.get("room_type")),
        ("订单号", order.get("confirmation_number")),
        ("平台来源", order.get("source")),
    ]
    lines = [f"{name}：{value}" for name, value in fields if value]
    if assumptions:
        lines.append("假设：" + "；".join(assumptions))
    return "\n".join(lines)


def _missing_fields(order: dict[str, Any], calendar: str | None = None, checkin_time: str | None = None) -> list[str]:
    missing = []
    if not calendar:
        missing.append("calendar")
    if not checkin_time:
        missing.append("checkin_time")
    for field in ("hotel_name", "checkin_date", "checkout_date"):
        if not order.get(field):
            missing.append(field)
    return missing


def _build_event(order: dict[str, Any], calendar: str | None, checkin_time: str | None) -> dict[str, Any] | None:
    if not calendar or not checkin_time or not order.get("checkin_date") or not order.get("checkout_date"):
        return None
    checkout_time = _normalize_time(order.get("checkout_time")) or "12:00"
    assumptions = []
    if not order.get("checkout_time"):
        assumptions.append("离店时间缺失，暂按 12:00 记录")
    return {
        "calendar": calendar,
        "title": f"入住｜{order.get('hotel_name')}",
        "start": f"{order['checkin_date']}T{checkin_time}:00",
        "end": f"{order['checkout_date']}T{checkout_time}:00",
        "location": order.get("address", ""),
        "notes": _build_notes(order, assumptions),
        "assumptions": assumptions,
    }


def _pending_display(order: dict[str, Any], missing: list[str]) -> str:
    return assistant_persona.format_hotel_order_draft(order, missing)


def draft_order(text: str) -> dict[str, Any]:
    parsed = hotel_order_parser.parse_order_text(text)
    if not parsed.get("is_hotel_order"):
        return _result(False, data=parsed, error="not_hotel_order")
    session_key = _session_key(text)
    missing = _missing_fields(parsed, parsed.get("calendar"), parsed.get("checkin_time"))
    pending = {
        "session_key": session_key,
        "action": "hotel_order_create_event",
        "status": "pending",
        "created_at": util.now_local_iso(),
        "source_text": text,
        "order": parsed,
        "draft": None,
        "missing_fields": missing,
        "needs_confirmation": True,
        "summary": _pending_display(parsed, missing),
        "display_message": _pending_display(parsed, missing),
    }
    store = _read_store()
    store.setdefault("sessions", {})[session_key] = pending
    _write_store(store)
    return _result(
        True,
        data={
            "session_key": session_key,
            "order": parsed,
            "draft": None,
            "missing_fields": missing,
            "needs_confirmation": True,
            "display_message": pending["display_message"],
        },
    )


def update_draft(session_key: str, calendar: str | None = None, checkin_time: str | None = None) -> dict[str, Any]:
    store = _read_store()
    pending = store.setdefault("sessions", {}).get(session_key)
    if not pending or pending.get("action") != "hotel_order_create_event":
        return _result(False, error=f"No pending hotel order draft found for session: {session_key}")
    if pending.get("status") != "pending":
        return _result(False, error=f"Hotel order draft is not pending: {session_key}")
    if calendar is not None and calendar not in ALLOWED_HOTEL_CALENDARS:
        return _result(False, error="calendar must be one of: 个人计划, 夫妻计划")
    normalized_time = _normalize_time(checkin_time) if checkin_time else None
    if checkin_time is not None and normalized_time is None:
        return _result(False, error="checkin-time must be HH:MM, for example 15:00")

    order = pending.get("order") if isinstance(pending.get("order"), dict) else {}
    if calendar is not None:
        order["calendar"] = calendar
    if normalized_time is not None:
        order["checkin_time"] = normalized_time
    missing = _missing_fields(order, order.get("calendar"), order.get("checkin_time"))
    draft = _build_event(order, order.get("calendar"), order.get("checkin_time"))
    display_message = (
        assistant_persona.format_calendar_draft(draft)
        if draft and not missing
        else _pending_display(order, missing)
    )
    pending["order"] = order
    pending["draft"] = draft
    pending["missing_fields"] = missing
    pending["summary"] = display_message
    pending["display_message"] = display_message
    store["sessions"][session_key] = pending
    _write_store(store)
    return _result(
        True,
        data={
            "session_key": session_key,
            "order": order,
            "draft": draft,
            "missing_fields": missing,
            "needs_confirmation": True,
            "display_message": display_message,
        },
    )


def confirm_order(session_key: str) -> dict[str, Any]:
    store = _read_store()
    pending = store.setdefault("sessions", {}).get(session_key)
    if not pending or pending.get("action") != "hotel_order_create_event":
        return _result(False, error=f"No pending hotel order draft found for session: {session_key}")
    if pending.get("status") != "pending":
        return _result(False, error=f"Hotel order draft is not pending: {session_key}")
    order = pending.get("order") if isinstance(pending.get("order"), dict) else {}
    missing = _missing_fields(order, order.get("calendar"), order.get("checkin_time"))
    if missing:
        return _result(False, data={"missing_fields": missing}, error="hotel_order_draft_incomplete")
    draft = pending.get("draft") if isinstance(pending.get("draft"), dict) else None
    if draft is None:
        draft = _build_event(order, order.get("calendar"), order.get("checkin_time"))
    if not draft:
        return _result(False, data={"missing_fields": missing}, error="hotel_order_draft_incomplete")
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
    pending["status"] = "confirmed"
    pending["confirmed_at"] = util.now_local_iso()
    pending["draft"] = draft
    pending["result"] = create_result["data"]
    store["sessions"][session_key] = pending
    _write_store(store)
    return _result(
        True,
        data={
            "session_key": session_key,
            "draft": draft,
            "calendar_result": create_result["data"],
            "display_message": assistant_persona.format_calendar_created(draft),
        },
    )


def cancel_order(session_key: str) -> dict[str, Any]:
    store = _read_store()
    pending = store.setdefault("sessions", {}).get(session_key)
    if not pending or pending.get("action") != "hotel_order_create_event":
        return _result(False, error=f"No pending hotel order draft found for session: {session_key}")
    if pending.get("status") != "pending":
        return _result(False, error=f"Hotel order draft is not pending: {session_key}")
    pending["status"] = "cancelled"
    pending["cancelled_at"] = util.now_local_iso()
    store["sessions"][session_key] = pending
    _write_store(store)
    return _result(True, data={"session_key": session_key, "status": "cancelled"})


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Draft and confirm hotel order Calendar events.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    draft = subparsers.add_parser("draft")
    draft.add_argument("--text", required=True)
    update = subparsers.add_parser("update-draft")
    update.add_argument("--session-key", required=True)
    update.add_argument("--calendar")
    update.add_argument("--checkin-time")
    confirm = subparsers.add_parser("confirm")
    confirm.add_argument("--session-key", required=True)
    cancel = subparsers.add_parser("cancel")
    cancel.add_argument("--session-key", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "draft":
        result = draft_order(args.text)
    elif args.command == "update-draft":
        result = update_draft(args.session_key, calendar=args.calendar, checkin_time=args.checkin_time)
    elif args.command == "confirm":
        result = confirm_order(args.session_key)
    elif args.command == "cancel":
        result = cancel_order(args.session_key)
    else:
        raise AssertionError(args.command)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
