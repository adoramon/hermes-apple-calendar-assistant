"""Create and apply pending location enhancements for flight events."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from . import calendar_ops
except ImportError:  # Allows running as: python3 scripts/flight_enhancer.py ...
    import calendar_ops  # type: ignore


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FLIGHT_PENDING_PATH = PROJECT_ROOT / "data" / "flight_pending.json"
FLIGHT_CALENDAR = "飞行计划"


def _result(ok: bool, data: Any = None, error: str | None = None) -> dict[str, Any]:
    return {"ok": ok, "data": data, "error": error}


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _read_store() -> dict[str, Any]:
    if not FLIGHT_PENDING_PATH.exists():
        return {"tasks": {}}
    try:
        raw = json.loads(FLIGHT_PENDING_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"tasks": {}}
    if not isinstance(raw, dict):
        return {"tasks": {}}
    if "tasks" not in raw or not isinstance(raw["tasks"], dict):
        return {"tasks": raw}
    return raw


def _write_store(store: dict[str, Any]) -> None:
    FLIGHT_PENDING_PATH.parent.mkdir(parents=True, exist_ok=True)
    FLIGHT_PENDING_PATH.write_text(
        json.dumps(store, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _event_key(event: dict[str, Any]) -> str:
    raw = f"{event.get('title', '')}|{event.get('start', '')}|{event.get('end', '')}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _build_location(parsed: dict[str, Any]) -> str | None:
    departure = parsed.get("departure_airport_raw")
    terminal = parsed.get("departure_terminal")
    if not departure:
        return None
    return f"{departure}{terminal or ''}"


def build_enhancement(event: dict[str, Any], parsed: dict[str, Any]) -> dict[str, Any]:
    """Build a location-only enhancement without writing to Calendar.app."""
    location = _build_location(parsed)
    if not location:
        return _result(False, error="Missing departure airport; cannot build flight location.")
    return _result(True, data={"suggestion": {"location": location}})


def save_pending_enhancement(event: dict[str, Any], parsed: dict[str, Any]) -> dict[str, Any]:
    """Save a pending flight location enhancement task."""
    enhancement_result = build_enhancement(event, parsed)
    if not enhancement_result["ok"]:
        return enhancement_result

    task_id = _event_key(event)
    task = {
        "id": task_id,
        "action": "set_flight_location",
        "status": "pending",
        "created_at": _now_iso(),
        "calendar": FLIGHT_CALENDAR,
        "event": event,
        "parsed": parsed,
        "suggestion": enhancement_result["data"]["suggestion"],
    }
    store = _read_store()
    existing = store.setdefault("tasks", {}).get(task_id)
    if existing and existing.get("status") == "confirmed":
        return _result(True, data={"task_id": task_id, "pending": existing, "skipped": "already_confirmed"})
    store["tasks"][task_id] = task
    _write_store(store)
    return _result(True, data={"task_id": task_id, "pending": task})


def list_pending_enhancements() -> dict[str, Any]:
    store = _read_store()
    tasks = [task for task in store.get("tasks", {}).values() if task.get("status") == "pending"]
    return _result(True, data={"tasks": tasks})


def cancel_pending_enhancement(task_id: str) -> dict[str, Any]:
    store = _read_store()
    task = store.get("tasks", {}).get(task_id)
    if not task:
        return _result(False, error=f"No pending flight enhancement found: {task_id}")
    if task.get("status") != "pending":
        return _result(False, error=f"Flight enhancement is not pending: {task_id}")
    task["status"] = "cancelled"
    task["cancelled_at"] = _now_iso()
    store["tasks"][task_id] = task
    _write_store(store)
    return _result(True, data={"task_id": task_id, "status": "cancelled"})


def confirm_pending_enhancement(task_id: str) -> dict[str, Any]:
    """Confirm and write the suggested location to the original flight event."""
    store = _read_store()
    task = store.get("tasks", {}).get(task_id)
    if not task:
        return _result(False, error=f"No pending flight enhancement found: {task_id}")
    if task.get("status") != "pending":
        return _result(False, error=f"Flight enhancement is not pending: {task_id}")

    event = task["event"]
    location = task["suggestion"]["location"]
    update_result = calendar_ops.update_event(
        FLIGHT_CALENDAR,
        event["title"],
        location=location,
    )
    if not update_result["ok"]:
        return update_result

    task["status"] = "confirmed"
    task["confirmed_at"] = _now_iso()
    task["result"] = update_result["data"]
    store["tasks"][task_id] = task
    _write_store(store)
    return _result(True, data={"task_id": task_id, "calendar_result": update_result["data"]})


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage pending flight location enhancements.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list-pending", help="List pending enhancement tasks.")
    confirm = subparsers.add_parser("confirm", help="Confirm and apply an enhancement task.")
    confirm.add_argument("task_id")
    cancel = subparsers.add_parser("cancel", help="Cancel an enhancement task.")
    cancel.add_argument("task_id")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "list-pending":
        result = list_pending_enhancements()
    elif args.command == "confirm":
        result = confirm_pending_enhancement(args.task_id)
    elif args.command == "cancel":
        result = cancel_pending_enhancement(args.task_id)
    else:
        raise AssertionError(args.command)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
