"""Aggregate travel orders into trip drafts."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

try:
    from . import travel_order_parser, util
except ImportError:  # Allows running as: python3 scripts/trip_aggregator.py ...
    import travel_order_parser  # type: ignore
    import util  # type: ignore


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TRIP_DRAFTS_PATH = PROJECT_ROOT / "data" / "trip_drafts.json"
HOME_CITIES = ("北京", "北京市")


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


def _parse_dt(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        try:
            return datetime.fromisoformat(value + "T00:00:00")
        except ValueError:
            return None


def _order_dates(order: dict[str, Any]) -> list[date]:
    fields = order.get("fields") if isinstance(order.get("fields"), dict) else {}
    values: list[Any] = []
    if order.get("order_type") in {"flight", "train"}:
        values.extend([fields.get("departure_datetime"), fields.get("arrival_datetime")])
    elif order.get("order_type") == "hotel":
        values.extend([fields.get("checkin_date"), fields.get("checkout_date")])
    dates = []
    for value in values:
        parsed = _parse_dt(value)
        if parsed:
            dates.append(parsed.date())
    return dates


def _order_destination(order: dict[str, Any]) -> str:
    fields = order.get("fields") if isinstance(order.get("fields"), dict) else {}
    order_type = order.get("order_type")
    if order_type == "hotel":
        name = str(fields.get("hotel_name") or fields.get("address") or "")
        for city in ("北京", "上海", "广州", "深圳", "杭州", "南京", "长沙", "成都", "重庆", "西安", "厦门", "香港"):
            if city in name:
                return city
        return ""
    dep = str(fields.get("departure_city") or "")
    arr = str(fields.get("arrival_city") or "")
    if arr and arr not in HOME_CITIES:
        return arr
    if dep and dep not in HOME_CITIES:
        return dep
    return arr or dep


def _trip_id(start_date: str, city: str, raw_hash: str) -> str:
    clean_city = city or "unknown"
    short = hashlib.sha1(f"{start_date}|{clean_city}|{raw_hash}".encode("utf-8")).hexdigest()[:8]
    return f"trip_{start_date.replace('-', '')}_{clean_city}_{short}"


def _date_close(a: date, b: date, days: int = 3) -> bool:
    return abs((a - b).days) <= days


def _matches_trip(trip: dict[str, Any], order: dict[str, Any], destination: str, dates: list[date]) -> bool:
    if not dates:
        return False
    trip_city = str(trip.get("destination_city") or "")
    if trip_city and destination and trip_city != destination:
        return False
    trip_start = _parse_dt(trip.get("start_date"))
    trip_end = _parse_dt(trip.get("end_date"))
    if not trip_start or not trip_end:
        return False
    return any(_date_close(item, trip_start.date()) or _date_close(item, trip_end.date()) for item in dates)


def _update_trip_bounds(trip: dict[str, Any]) -> None:
    dates: list[date] = []
    for order in trip.get("orders", []):
        if isinstance(order, dict):
            dates.extend(_order_dates(order))
    if dates:
        trip["start_date"] = min(dates).isoformat()
        trip["end_date"] = max(dates).isoformat()
    trip["updated_at"] = util.now_local_iso()


def _build_title(city: str, orders: list[dict[str, Any]]) -> str:
    text = json.dumps(orders, ensure_ascii=False)
    if any(word in text for word in ("客户", "会议", "商务", "出差")):
        return f"{city}商务出行" if city else "商务出行"
    return f"{city}出行" if city else "出行计划"


def _suggest_calendar(orders: list[dict[str, Any]]) -> str:
    text = json.dumps(orders, ensure_ascii=False)
    if any(word in text for word in ("客户", "会议", "商务", "出差")):
        return "商务计划"
    if any(word in text for word in ("双人", "夫妻", "太太", "家人")):
        return "夫妻计划"
    return "个人计划"


def add_order(text: str) -> dict[str, Any]:
    parsed = travel_order_parser.parse_order_text(text)
    if parsed.get("order_type") == "unknown":
        return _result(False, data={"parsed": parsed}, error="unknown_travel_order")

    order = {
        "order_type": parsed["order_type"],
        "source_platform": parsed.get("source_platform", "unknown"),
        "raw_text_hash": parsed.get("raw_text_hash"),
        "fields": parsed.get("fields", {}),
        "missing_fields": parsed.get("missing_fields", []),
        "confidence": parsed.get("confidence", 0.0),
        "added_at": util.now_local_iso(),
    }
    destination = _order_destination(order)
    dates = _order_dates(order)
    if not dates:
        return _result(False, data={"parsed": parsed}, error="travel_order_missing_dates")

    store = _read_store()
    trips = store.setdefault("trips", {})
    target: dict[str, Any] | None = None
    for trip in trips.values():
        if isinstance(trip, dict) and trip.get("status") == "draft" and _matches_trip(trip, order, destination, dates):
            target = trip
            break

    created_new = False
    if target is None:
        start_date = min(dates).isoformat()
        trip_id = _trip_id(start_date, destination, str(parsed.get("raw_text_hash", "")))
        target = {
            "trip_id": trip_id,
            "status": "draft",
            "title": _build_title(destination, [order]),
            "destination_city": destination,
            "start_date": start_date,
            "end_date": max(dates).isoformat(),
            "orders": [],
            "calendar": None,
            "suggested_calendar": _suggest_calendar([order]),
            "needs_calendar_choice": True,
            "missing_fields": ["calendar"],
            "created_at": util.now_local_iso(),
            "updated_at": util.now_local_iso(),
        }
        trips[trip_id] = target
        created_new = True

    if not any(existing.get("raw_text_hash") == order["raw_text_hash"] for existing in target.get("orders", []) if isinstance(existing, dict)):
        target.setdefault("orders", []).append(order)
    if destination and not target.get("destination_city"):
        target["destination_city"] = destination
    target["title"] = _build_title(str(target.get("destination_city") or destination), list(target.get("orders") or []))
    target["suggested_calendar"] = _suggest_calendar(list(target.get("orders") or []))
    target["missing_fields"] = ["calendar"] if not target.get("calendar") else []
    target["needs_calendar_choice"] = not bool(target.get("calendar"))
    _update_trip_bounds(target)
    _write_store(store)
    return _result(True, data={"trip": target, "added_order": order, "created_new_trip": created_new})


def list_trips() -> dict[str, Any]:
    trips = list(_read_store().get("trips", {}).values())
    trips.sort(key=lambda item: str(item.get("updated_at", "")), reverse=True)
    return _result(True, data={"trips": trips})


def show_trip(trip_id: str) -> dict[str, Any]:
    trip = _read_store().get("trips", {}).get(trip_id)
    if not trip:
        return _result(False, error=f"Trip not found: {trip_id}")
    return _result(True, data={"trip": trip})


def cancel_trip(trip_id: str) -> dict[str, Any]:
    store = _read_store()
    trip = store.get("trips", {}).get(trip_id)
    if not trip:
        return _result(False, error=f"Trip not found: {trip_id}")
    trip["status"] = "cancelled"
    trip["cancelled_at"] = util.now_local_iso()
    trip["updated_at"] = util.now_local_iso()
    _write_store(store)
    return _result(True, data={"trip_id": trip_id, "status": "cancelled"})


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Aggregate travel orders into trip drafts.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    add = subparsers.add_parser("add")
    add.add_argument("--text", required=True)
    show = subparsers.add_parser("show")
    show.add_argument("--trip-id", required=True)
    cancel = subparsers.add_parser("cancel")
    cancel.add_argument("--trip-id", required=True)
    subparsers.add_parser("list")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "add":
        result = add_order(args.text)
    elif args.command == "list":
        result = list_trips()
    elif args.command == "show":
        result = show_trip(args.trip_id)
    elif args.command == "cancel":
        result = cancel_trip(args.trip_id)
    else:
        raise AssertionError(args.command)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
