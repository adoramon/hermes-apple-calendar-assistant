"""Automatically enhance future flight events by writing departure location."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

try:
    from . import calendar_ops, flight_enhancer, flight_parser, util
except ImportError:  # Allows running as: python3 scripts/flight_auto_enhancer.py run
    import calendar_ops  # type: ignore
    import flight_enhancer  # type: ignore
    import flight_parser  # type: ignore
    import util  # type: ignore


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FLIGHT_SEEN_PATH = PROJECT_ROOT / "data" / "flight_seen.json"
ALLOWED_FLIGHT_CALENDAR = "飞行计划"
DEFAULT_SCAN_DAYS = 30
SOURCE_NAME = "flight_auto_enhancer"


def _result(ok: bool, data: Any = None, error: str | None = None) -> dict[str, Any]:
    return util.result(ok, data=data, error=error)


def _read_seen_store() -> dict[str, Any]:
    raw = util.load_json_file(FLIGHT_SEEN_PATH, {})
    if not isinstance(raw, dict):
        return {"events": {}}
    events = raw.get("events", raw)
    if not isinstance(events, dict):
        events = {}
    normalized_events = {}
    for key, record in events.items():
        if not isinstance(record, dict):
            continue
        fingerprint = record.get("fingerprint")
        status = record.get("status")
        if isinstance(fingerprint, str) and fingerprint and isinstance(status, str):
            normalized_events[fingerprint] = record
        elif _looks_like_legacy_seen_key(key, record):
            continue
    return {"events": normalized_events}


def _write_seen_store(store: dict[str, Any]) -> None:
    util.write_json_file(FLIGHT_SEEN_PATH, store)


def _load_runtime_config() -> dict[str, Any]:
    settings = util.load_settings()
    flight_calendar = settings.get("flight_calendar") or ALLOWED_FLIGHT_CALENDAR
    scan_days = settings.get("flight_scan_days", DEFAULT_SCAN_DAYS)
    if not isinstance(scan_days, int) or scan_days <= 0:
        scan_days = DEFAULT_SCAN_DAYS
    return {
        "flight_calendar": flight_calendar,
        "flight_scan_days": scan_days,
    }


def build_event_fingerprint(calendar_name: str, event: dict[str, Any]) -> str:
    raw = "|".join(
        [
            calendar_name,
            str(event.get("title", "")),
            str(event.get("start", "")),
            str(event.get("end", "")),
        ]
    )
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def _looks_like_legacy_seen_key(key: str, record: dict[str, Any]) -> bool:
    return "|" in key and set(record.keys()) == {"seen_at"}


def _normalize_location(value: Any) -> str:
    return util.normalize_calendar_text(value)


def _is_terminal_seen_record(record: Any) -> bool:
    if not isinstance(record, dict):
        return False
    status = record.get("status")
    if status in {"enhanced", "skipped_no_parse"}:
        return True
    if status == "skipped_has_location":
        return bool(_normalize_location(record.get("location_written")))
    return False


def _build_seen_record(
    fingerprint: str,
    calendar_name: str,
    event: dict[str, Any],
    status: str,
    location_written: str = "",
    error: str | None = None,
) -> dict[str, Any]:
    record = {
        "fingerprint": fingerprint,
        "calendar": calendar_name,
        "title": event.get("title", ""),
        "start": event.get("start", ""),
        "end": event.get("end", ""),
        "location_written": location_written,
        "status": status,
        "processed_at": util.now_iso(),
        "source": SOURCE_NAME,
    }
    if error:
        record["error"] = error
    return record


def _enhance_one_event(calendar_name: str, event: dict[str, Any]) -> dict[str, Any]:
    fingerprint = build_event_fingerprint(calendar_name, event)
    current_location = _normalize_location(event.get("location"))
    if current_location:
        return _result(
            True,
            data=_build_seen_record(
                fingerprint,
                calendar_name,
                event,
                status="skipped_has_location",
                location_written=current_location,
            ),
        )

    parse_result = flight_parser.parse_flight_event(event)
    if not parse_result["ok"]:
        return _result(
            True,
            data=_build_seen_record(
                fingerprint,
                calendar_name,
                event,
                status="skipped_no_parse",
                error=parse_result["error"],
            ),
        )

    enhancement_result = flight_enhancer.build_enhancement(event, parse_result["data"])
    if not enhancement_result["ok"]:
        return _result(
            True,
            data=_build_seen_record(
                fingerprint,
                calendar_name,
                event,
                status="skipped_no_parse",
                error=enhancement_result["error"],
            ),
        )

    location = enhancement_result["data"]["suggestion"]["location"]
    update_result = calendar_ops.update_event_location_exact(
        calendar_name,
        str(event.get("title", "")),
        str(event.get("start", "")),
        str(event.get("end", "")),
        location,
    )
    if not update_result["ok"]:
        return _result(
            True,
            data=_build_seen_record(
                fingerprint,
                calendar_name,
                event,
                status="failed",
                location_written=location,
                error=update_result["error"],
            ),
        )

    record = _build_seen_record(
        fingerprint,
        calendar_name,
        event,
        status="enhanced",
        location_written=location,
    )
    record["calendar_result"] = update_result["data"]
    return _result(True, data=record)


def run_auto_enhancer() -> dict[str, Any]:
    config = _load_runtime_config()
    flight_calendar = config["flight_calendar"]
    scan_days = config["flight_scan_days"]
    if flight_calendar != ALLOWED_FLIGHT_CALENDAR:
        return _result(False, error=f"Only {ALLOWED_FLIGHT_CALENDAR} calendar is allowed for automatic enhancement.")

    now = datetime.now()
    start = now.isoformat(timespec="seconds")
    end = (now + timedelta(days=scan_days)).isoformat(timespec="seconds")
    events_result = calendar_ops.list_events(flight_calendar, start_date=start, end_date=end)
    if not events_result["ok"]:
        return events_result

    store = _read_seen_store()
    seen = store.setdefault("events", {})
    processed = []
    skipped = []
    for event in events_result["data"]["events"]:
        fingerprint = build_event_fingerprint(flight_calendar, event)
        existing = seen.get(fingerprint)
        if _is_terminal_seen_record(existing):
            skipped.append(
                {
                    "fingerprint": fingerprint,
                    "title": event.get("title", ""),
                    "start": event.get("start", ""),
                    "end": event.get("end", ""),
                    "reason": f"already_{existing.get('status')}",
                }
            )
            continue

        result = _enhance_one_event(flight_calendar, event)
        record = result["data"]
        seen[fingerprint] = record
        processed.append(record)

    _write_seen_store(store)
    return _result(
        True,
        data={
            "calendar": flight_calendar,
            "scan_days": scan_days,
            "start": start,
            "end": end,
            "processed": processed,
            "skipped": skipped,
        },
    )


def clean_bad_location_skips() -> dict[str, Any]:
    store = _read_seen_store()
    seen = store.setdefault("events", {})
    removed = []
    for fingerprint, record in list(seen.items()):
        if not isinstance(record, dict):
            continue
        if record.get("status") != "skipped_has_location":
            continue
        if _normalize_location(record.get("location_written")):
            continue
        removed.append(
            {
                "fingerprint": fingerprint,
                "title": record.get("title", ""),
                "start": record.get("start", ""),
                "end": record.get("end", ""),
                "location_written": record.get("location_written", ""),
            }
        )
        del seen[fingerprint]
    _write_seen_store(store)
    return _result(True, data={"removed": removed, "removed_count": len(removed)})


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Automatically enhance future flight events.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("run", help="Scan future flights and write departure locations.")
    subparsers.add_parser(
        "clean-bad-location-skips",
        help="Remove skipped_has_location seen records whose location is actually empty.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "run":
        result = run_auto_enhancer()
    elif args.command == "clean-bad-location-skips":
        result = clean_bad_location_skips()
    else:
        raise AssertionError(args.command)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
