"""Link read-only 飞行计划 flights to existing Trip drafts."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

try:
    from . import assistant_persona, flight_plan_reader, util
except ImportError:  # Allows running as: python3 scripts/trip_flight_matcher.py ...
    import assistant_persona  # type: ignore
    import flight_plan_reader  # type: ignore
    import util  # type: ignore


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TRIP_DRAFTS_PATH = PROJECT_ROOT / "data" / "trip_drafts.json"


def _result(ok: bool, data: Any = None, error: str | None = None) -> dict[str, Any]:
    return {"ok": ok, "data": data, "error": error}


def _read_store() -> dict[str, Any]:
    raw = util.load_json(TRIP_DRAFTS_PATH, {"trips": {}})
    if not isinstance(raw, dict):
        return {"trips": {}}
    if not isinstance(raw.get("trips"), dict):
        raw["trips"] = {}
    return raw


def _write_store(store: dict[str, Any]) -> None:
    util.save_json_atomic(TRIP_DRAFTS_PATH, store)


def _parse_date(value: Any) -> date | None:
    parsed = assistant_persona.parse_datetime(value)
    if parsed:
        return parsed.date()
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value).date()
        except ValueError:
            try:
                return datetime.fromisoformat(value + "T00:00:00").date()
            except ValueError:
                return None
    return None


def _close_to(value: Any, target: Any, days: int = 1) -> bool:
    left = _parse_date(value)
    right = _parse_date(target)
    if not left or not right:
        return False
    return abs((left - right).days) <= days


def _readonly_link(flight: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_calendar": flight_plan_reader.FLIGHT_CALENDAR,
        "title": flight.get("title", ""),
        "start": flight.get("start", ""),
        "end": flight.get("end", ""),
        "location": flight.get("location", ""),
        "flight_no": flight.get("flight_no", ""),
        "departure_city": flight.get("departure_city", ""),
        "arrival_city": flight.get("arrival_city", ""),
        "departure_airport": flight.get("departure_airport", ""),
        "arrival_airport": flight.get("arrival_airport", ""),
        "departure_terminal": flight.get("departure_terminal", ""),
        "arrival_terminal": flight.get("arrival_terminal", ""),
        "readonly": True,
    }


def _matches_outbound(trip: dict[str, Any], flight: dict[str, Any]) -> bool:
    return (
        str(flight.get("arrival_city") or "") == str(trip.get("destination_city") or "")
        and str(flight.get("departure_city") or "") == str(trip.get("origin_city") or "北京")
        and _close_to(flight.get("start"), trip.get("start_date"), days=1)
    )


def _matches_return(trip: dict[str, Any], flight: dict[str, Any]) -> bool:
    return (
        str(flight.get("departure_city") or "") == str(trip.get("destination_city") or "")
        and str(flight.get("arrival_city") or "") == str(trip.get("origin_city") or "北京")
        and _close_to(flight.get("start"), trip.get("end_date"), days=1)
    )


def _choose_unique(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    return candidates[0] if len(candidates) == 1 else None


def update_planning_status(trip: dict[str, Any]) -> None:
    linked = trip.get("linked_flights") if isinstance(trip.get("linked_flights"), dict) else {}
    has_outbound = isinstance(linked.get("outbound"), dict)
    has_return = isinstance(linked.get("return"), dict)
    if not trip.get("needs_flight", True):
        trip["flight_link_status"] = "no_flight_needed"
    elif has_outbound and has_return:
        trip["flight_link_status"] = "fully_linked"
    elif has_outbound:
        trip["flight_link_status"] = "outbound_linked"
    elif has_return:
        trip["flight_link_status"] = "return_linked"
    else:
        trip["flight_link_status"] = "flight_pending_sync"

    has_orders = bool(trip.get("orders"))
    if trip["flight_link_status"] in {"fully_linked", "no_flight_needed"} and has_orders:
        trip["planning_status"] = "fully_confirmed"
    elif has_orders or has_outbound or has_return:
        trip["planning_status"] = "partially_confirmed"
    else:
        trip["planning_status"] = "planned_only"


def link_matching_flights(trip: dict[str, Any], flights: list[dict[str, Any]]) -> dict[str, Any]:
    outbound_candidates = [flight for flight in flights if _matches_outbound(trip, flight)]
    return_candidates = [flight for flight in flights if _matches_return(trip, flight)]
    linked = trip.setdefault("linked_flights", {})
    linked_now: dict[str, Any] = {}
    ambiguous: dict[str, Any] = {}

    outbound = _choose_unique(outbound_candidates)
    if outbound:
        linked["outbound"] = _readonly_link(outbound)
        linked_now["outbound"] = linked["outbound"]
    elif outbound_candidates:
        ambiguous["outbound"] = outbound_candidates

    return_flight = _choose_unique(return_candidates)
    if return_flight:
        linked["return"] = _readonly_link(return_flight)
        linked_now["return"] = linked["return"]
    elif return_candidates:
        ambiguous["return"] = return_candidates

    update_planning_status(trip)
    trip["updated_at"] = util.now_local_iso()
    return {"linked": linked_now, "ambiguous_candidates": ambiguous}


def match_trip(trip_id: str, days: int = 30) -> dict[str, Any]:
    store = _read_store()
    trip = store.get("trips", {}).get(trip_id)
    if not isinstance(trip, dict):
        return _result(False, error=f"Trip not found: {trip_id}")

    flights_result = flight_plan_reader.list_flights(days=days)
    if not flights_result.get("ok"):
        return flights_result
    flights = flights_result.get("data", {}).get("flights", [])
    match_result = link_matching_flights(trip, [item for item in flights if isinstance(item, dict)])
    store["trips"][trip_id] = trip
    _write_store(store)
    formatter = assistant_persona.format_trip_flight_linked if match_result.get("linked") else assistant_persona.format_trip_flight_pending_sync
    return _result(
        True,
        data={
            "trip_id": trip_id,
            "trip": trip,
            "linked": match_result["linked"],
            "ambiguous_candidates": match_result["ambiguous_candidates"],
            "display_message": formatter(trip),
        },
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Match 飞行计划 flights into Trip drafts.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    match = subparsers.add_parser("match")
    match.add_argument("--trip-id", required=True)
    match.add_argument("--days", type=int, default=30)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "match":
        result = match_trip(args.trip_id, days=args.days)
    else:
        raise AssertionError(args.command)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
