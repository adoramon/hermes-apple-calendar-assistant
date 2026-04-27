"""Generate pre-trip briefing messages into the Hermes outbox."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Any

try:
    from . import assistant_persona, outbox, util
except ImportError:  # Allows running as: python3 scripts/trip_briefing_worker.py ...
    import assistant_persona  # type: ignore
    import outbox  # type: ignore
    import util  # type: ignore


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TRIP_DRAFTS_PATH = PROJECT_ROOT / "data" / "trip_drafts.json"
TRIP_BRIEFING_SEEN_PATH = PROJECT_ROOT / "data" / "trip_briefing_seen.json"
DEFAULT_CHANNEL = "hermes"
DEFAULT_RECIPIENT = "default"
BRIEFING_TYPES = {"pre_trip_24h", "pre_trip_48h", "travel_day_morning"}


def _result(ok: bool, data: Any = None, error: str | None = None) -> dict[str, Any]:
    return {"ok": ok, "data": data, "error": error}


def _read_trips() -> dict[str, Any]:
    raw = util.load_json(TRIP_DRAFTS_PATH, {"trips": {}})
    if not isinstance(raw, dict):
        return {"trips": {}}
    if not isinstance(raw.get("trips"), dict):
        raw["trips"] = {}
    return raw


def _read_seen() -> dict[str, Any]:
    raw = util.load_json(TRIP_BRIEFING_SEEN_PATH, {"items": {}})
    if not isinstance(raw, dict):
        return {"items": {}}
    if not isinstance(raw.get("items"), dict):
        raw["items"] = {}
    return raw


def _write_seen(store: dict[str, Any]) -> None:
    util.save_json_atomic(TRIP_BRIEFING_SEEN_PATH, store)


def _trip_start(trip: dict[str, Any]) -> datetime | None:
    event_starts = []
    for event in trip.get("events", []):
        if not isinstance(event, dict):
            continue
        start = assistant_persona.parse_datetime(event.get("start"))
        if start:
            event_starts.append(start)
    if event_starts:
        return min(event_starts)
    return assistant_persona.parse_datetime(trip.get("start_date"))


def _briefing_type_for(start: datetime, now: datetime) -> str | None:
    if start < now:
        return None
    hours_until = (start - now).total_seconds() / 3600
    if start.date() == now.date() and now.time() <= time(12, 0):
        return "travel_day_morning"
    if hours_until <= 24:
        return "pre_trip_24h"
    if hours_until <= 48:
        return "pre_trip_48h"
    return None


def _eligible_trips(hours: int, now: datetime) -> list[tuple[dict[str, Any], str, datetime]]:
    if hours <= 0:
        return []
    horizon = now + timedelta(hours=hours)
    trips = []
    for trip in _read_trips().get("trips", {}).values():
        if not isinstance(trip, dict):
            continue
        if trip.get("status") not in {"draft", "confirmed"}:
            continue
        if not trip.get("planning_status"):
            continue
        start = _trip_start(trip)
        if not start or start < now or start > horizon:
            continue
        briefing_type = _briefing_type_for(start, now)
        if briefing_type:
            trips.append((trip, briefing_type, start))
    trips.sort(key=lambda item: item[2])
    return trips


def _outbox_message(trip: dict[str, Any], briefing_type: str) -> dict[str, Any]:
    trip_id = str(trip.get("trip_id") or "")
    return {
        "channel": DEFAULT_CHANNEL,
        "recipient": DEFAULT_RECIPIENT,
        "message": assistant_persona.format_trip_briefing(trip, briefing_type),
        "metadata": {
            "type": "trip_briefing",
            "trip_id": trip_id,
            "briefing_type": briefing_type,
            "fingerprint": f"{trip_id}|{briefing_type}",
        },
    }


def scan(hours: int = 48) -> dict[str, Any]:
    if hours <= 0:
        return _result(False, error="hours must be greater than 0")
    now = datetime.now()
    seen = _read_seen()
    seen_items = seen.setdefault("items", {})
    written = []
    skipped = []
    for trip, briefing_type, start in _eligible_trips(hours, now):
        trip_id = str(trip.get("trip_id") or "")
        key = f"{trip_id}|{briefing_type}"
        if key in seen_items:
            skipped.append({"trip_id": trip_id, "briefing_type": briefing_type, "reason": "already_seen"})
            continue
        message = _outbox_message(trip, briefing_type)
        append_result = outbox.append_outbox_message(message)
        if append_result.get("written"):
            outbox_id = append_result.get("id", "")
            seen_items[key] = {"sent_at": util.now_local_iso(), "outbox_id": outbox_id}
            written.append(
                {
                    "trip_id": trip_id,
                    "briefing_type": briefing_type,
                    "outbox_id": outbox_id,
                    "start": start.isoformat(timespec="seconds"),
                }
            )
        else:
            skipped.append(
                {
                    "trip_id": trip_id,
                    "briefing_type": briefing_type,
                    "reason": append_result.get("reason", "not_written"),
                    "outbox_id": append_result.get("id", ""),
                }
            )
    _write_seen(seen)
    return _result(
        True,
        data={
            "hours": hours,
            "written_count": len(written),
            "skipped_count": len(skipped),
            "written": written,
            "skipped": skipped,
        },
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate Trip briefing messages into the Hermes outbox.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    scan_parser = subparsers.add_parser("scan")
    scan_parser.add_argument("--hours", type=int, default=48)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "scan":
        result = scan(hours=args.hours)
    else:
        raise AssertionError(args.command)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
