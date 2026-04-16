"""Scan upcoming flight calendar events and propose enhancements."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

try:
    from . import calendar_ops, flight_enhancer, flight_parser
except ImportError:  # Allows running as: python3 scripts/flight_watcher.py ...
    import calendar_ops  # type: ignore
    import flight_enhancer  # type: ignore
    import flight_parser  # type: ignore


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FLIGHT_SEEN_PATH = PROJECT_ROOT / "data" / "flight_seen.json"
FLIGHT_CALENDAR = "飞行计划"
DEFAULT_SCAN_DAYS = 30


def _result(ok: bool, data: Any = None, error: str | None = None) -> dict[str, Any]:
    return {"ok": ok, "data": data, "error": error}


def _read_seen_store() -> dict[str, Any]:
    if not FLIGHT_SEEN_PATH.exists():
        return {"events": {}}
    try:
        raw = json.loads(FLIGHT_SEEN_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"events": {}}
    if not isinstance(raw, dict):
        return {"events": {}}
    if "events" not in raw or not isinstance(raw["events"], dict):
        return {"events": raw}
    return raw


def _write_seen_store(store: dict[str, Any]) -> None:
    FLIGHT_SEEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    FLIGHT_SEEN_PATH.write_text(
        json.dumps(store, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _event_seen_key(event: dict[str, Any]) -> str:
    return f"{event.get('title', '')}|{event.get('start', '')}|{event.get('end', '')}"


def scan_upcoming_flights(days: int = DEFAULT_SCAN_DAYS, include_seen: bool = False) -> dict[str, Any]:
    """Scan 飞行计划 for upcoming flight events and save location suggestions."""
    now = datetime.now()
    start = now.isoformat(timespec="seconds")
    end = (now + timedelta(days=days)).isoformat(timespec="seconds")
    events_result = calendar_ops.list_events(FLIGHT_CALENDAR, start_date=start, end_date=end)
    if not events_result["ok"]:
        return events_result

    seen_store = _read_seen_store()
    seen = seen_store.setdefault("events", {})
    proposals = []
    skipped = []
    for event in events_result["data"]["events"]:
        seen_key = _event_seen_key(event)
        if not include_seen and seen_key in seen:
            skipped.append({"event": event, "reason": "already_seen"})
            continue

        parse_result = flight_parser.parse_flight_event(event)
        if not parse_result["ok"]:
            skipped.append({"event": event, "reason": parse_result["error"]})
            continue
        parsed = parse_result["data"]
        if not parsed["is_flight_event"]:
            skipped.append({"event": event, "reason": "not_flight"})
            continue

        save_result = flight_enhancer.save_pending_enhancement(
            event,
            parsed,
        )
        if not save_result["ok"]:
            skipped.append({"event": event, "reason": save_result["error"]})
            continue
        proposals.append(save_result["data"])
        seen[seen_key] = {"seen_at": datetime.now().astimezone().isoformat(timespec="seconds")}

    _write_seen_store(seen_store)
    return _result(
        True,
        data={
            "calendar": FLIGHT_CALENDAR,
            "start": start,
            "end": end,
            "proposals": proposals,
            "skipped": skipped,
        },
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scan upcoming flight events.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    scan = subparsers.add_parser("scan", help="Scan future flight events and create pending tasks.")
    scan.add_argument("--days", type=int, default=DEFAULT_SCAN_DAYS)
    scan.add_argument("--include-seen", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "scan":
        result = scan_upcoming_flights(days=args.days, include_seen=args.include_seen)
    else:
        raise AssertionError(args.command)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
