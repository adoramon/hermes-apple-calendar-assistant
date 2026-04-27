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
    from . import flight_plan_reader, travel_order_parser, trip_flight_matcher, util
except ImportError:  # Allows running as: python3 scripts/trip_aggregator.py ...
    import flight_plan_reader  # type: ignore
    import travel_order_parser  # type: ignore
    import trip_flight_matcher  # type: ignore
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


def _trip_warning(trip: dict[str, Any], order: dict[str, Any], destination: str, dates: list[date]) -> str | None:
    trip_city = str(trip.get("destination_city") or "")
    if trip_city and destination and trip_city != destination:
        return f"订单目的地「{destination}」与 Trip 目的地「{trip_city}」不一致。"
    trip_start = _parse_dt(trip.get("start_date"))
    trip_end = _parse_dt(trip.get("end_date"))
    if trip_start and trip_end and dates:
        if not any(_date_close(item, trip_start.date()) or _date_close(item, trip_end.date()) for item in dates):
            order_days = "、".join(item.isoformat() for item in sorted(set(dates)))
            return f"订单日期（{order_days}）与 Trip 日期（{trip_start.date()} 至 {trip_end.date()}）相差较大。"
    return None


def _matching_trips(trips: dict[str, Any], order: dict[str, Any], destination: str, dates: list[date]) -> list[dict[str, Any]]:
    matches = [
        trip
        for trip in trips.values()
        if isinstance(trip, dict) and trip.get("status") == "draft" and _matches_trip(trip, order, destination, dates)
    ]
    matches.sort(key=lambda item: (0 if item.get("source") == "travel_intent" else 1, str(item.get("updated_at", ""))))
    return matches


def _update_trip_bounds(trip: dict[str, Any]) -> None:
    dates: list[date] = []
    for event in trip.get("events", []) if isinstance(trip.get("events"), list) else []:
        if not isinstance(event, dict):
            continue
        for value in (event.get("start"), event.get("end")):
            parsed = _parse_dt(value)
            if parsed:
                dates.append(parsed.date())
    for order in trip.get("orders", []):
        if isinstance(order, dict):
            if order.get("confirmation_status") == "date_conflict":
                continue
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


def _ensure_trip_defaults(trip: dict[str, Any]) -> None:
    trip.setdefault("origin_city", "北京")
    trip.setdefault("linked_flights", {})
    trip.setdefault("needs_flight", True)
    trip.setdefault("orders", [])
    trip.setdefault("merge_history", [])
    for index, event in enumerate(trip.get("events", []) if isinstance(trip.get("events"), list) else []):
        if not isinstance(event, dict):
            continue
        event.setdefault("placeholder_id", f"{event.get('event_type') or 'event'}_{index + 1}")
        if str(event.get("event_type") or "").endswith("_placeholder"):
            event.setdefault("source_type", "travel_intent")
            event.setdefault("confirmation_status", "planned")
        else:
            event.setdefault("source_type", "manual")
            event.setdefault("confirmation_status", "confirmed")
        event.setdefault("replaced_placeholder_id", None)


def _place_matches(place: Any, city: Any) -> bool:
    place_text = str(place or "")
    city_text = str(city or "")
    if not place_text or not city_text:
        return False
    return city_text in place_text or place_text in city_text


def _route_placeholder_type(trip: dict[str, Any], order: dict[str, Any]) -> str | None:
    fields = order.get("fields") if isinstance(order.get("fields"), dict) else {}
    origin = str(trip.get("origin_city") or "北京")
    destination = str(trip.get("destination_city") or "")
    dep = str(fields.get("departure_city") or fields.get("departure_station") or "")
    arr = str(fields.get("arrival_city") or fields.get("arrival_station") or "")
    dep_station = str(fields.get("departure_station") or "")
    arr_station = str(fields.get("arrival_station") or "")
    if (_place_matches(dep, origin) or _place_matches(dep_station, origin)) and (
        _place_matches(arr, destination) or _place_matches(arr_station, destination)
    ):
        return "outbound_placeholder"
    if (_place_matches(dep, destination) or _place_matches(dep_station, destination)) and (
        _place_matches(arr, origin) or _place_matches(arr_station, origin)
    ):
        return "return_placeholder"
    return None


def _find_placeholder(trip: dict[str, Any], event_type: str) -> dict[str, Any] | None:
    for event in trip.get("events", []) if isinstance(trip.get("events"), list) else []:
        if not isinstance(event, dict):
            continue
        if event.get("event_type") != event_type:
            continue
        if event.get("confirmation_status") == "confirmed":
            continue
        return event
    return None


def _append_merge_history(trip: dict[str, Any], placeholder_type: str, new_source_type: str, summary: str) -> None:
    trip.setdefault("merge_history", []).append(
        {
            "at": util.now_local_iso(),
            "action": "replace_placeholder",
            "placeholder_type": placeholder_type,
            "new_source_type": new_source_type,
            "summary": summary,
        }
    )


def _hotel_dates_match_trip(trip: dict[str, Any], order: dict[str, Any]) -> bool:
    fields = order.get("fields") if isinstance(order.get("fields"), dict) else {}
    checkin = _parse_dt(fields.get("checkin_date"))
    checkout = _parse_dt(fields.get("checkout_date"))
    trip_start = _parse_dt(trip.get("start_date"))
    trip_end = _parse_dt(trip.get("end_date"))
    if not checkin or not checkout or not trip_start or not trip_end:
        return True
    return checkin.date() == trip_start.date() and checkout.date() == trip_end.date()


def _mark_placeholder_replaced(trip: dict[str, Any], placeholder_type: str, order: dict[str, Any]) -> dict[str, Any] | None:
    placeholder = _find_placeholder(trip, placeholder_type)
    if not placeholder:
        return None
    placeholder["confirmation_status"] = "confirmed"
    placeholder["source_type"] = order.get("source_type")
    placeholder["replaced_by_order_hash"] = order.get("raw_text_hash")
    placeholder["replaced_at"] = util.now_local_iso()
    order["replaced_placeholder_id"] = placeholder.get("placeholder_id")
    return placeholder


def _add_order_once(trip: dict[str, Any], order: dict[str, Any]) -> bool:
    if any(existing.get("raw_text_hash") == order["raw_text_hash"] for existing in trip.get("orders", []) if isinstance(existing, dict)):
        return False
    trip.setdefault("orders", []).append(order)
    return True


def _merge_real_order_into_trip(trip: dict[str, Any], order: dict[str, Any], explicit_trip: bool) -> dict[str, Any]:
    order_type = str(order.get("order_type") or "")
    order.setdefault("replaced_placeholder_id", None)
    warning = None
    needs_confirmation = False
    replaced_placeholder = None

    if order_type == "hotel":
        order["source_type"] = "hotel_order"
        if not _hotel_dates_match_trip(trip, order):
            order["confirmation_status"] = "date_conflict"
            warning = "酒店订单日期与当前 Trip 日期不一致，已标记为日期冲突，暂不替换住宿占位。"
            needs_confirmation = True
        else:
            order["confirmation_status"] = "confirmed"
            replaced_placeholder = _mark_placeholder_replaced(trip, "hotel_placeholder", order)
            if replaced_placeholder:
                fields = order.get("fields", {})
                _append_merge_history(
                    trip,
                    "hotel_placeholder",
                    "hotel_order",
                    f"酒店订单替换住宿占位：{fields.get('hotel_name') or '酒店'}",
                )
    elif order_type == "train":
        order["source_type"] = "train_order"
        placeholder_type = _route_placeholder_type(trip, order)
        if not placeholder_type:
            order["confirmation_status"] = "date_conflict" if explicit_trip else "confirmed"
            warning = "高铁订单路线与当前 Trip 的去程/返程方向不完全匹配，需要用户确认。"
            needs_confirmation = True
        else:
            order["confirmation_status"] = "confirmed"
            replaced_placeholder = _mark_placeholder_replaced(trip, placeholder_type, order)
            if replaced_placeholder:
                fields = order.get("fields", {})
                _append_merge_history(
                    trip,
                    placeholder_type,
                    "train_order",
                    f"高铁订单替换{placeholder_type}：{fields.get('train_no') or '高铁'}",
                )
    else:
        order.setdefault("source_type", "manual")
        order.setdefault("confirmation_status", "confirmed")

    _add_order_once(trip, order)
    return {
        "warning": warning,
        "needs_confirmation": needs_confirmation,
        "replaced_placeholder": replaced_placeholder,
    }


def _handle_flight_order(order: dict[str, Any], destination: str, dates: list[date], trip_id: str | None = None) -> dict[str, Any]:
    store = _read_store()
    trips = store.setdefault("trips", {})
    matches = []
    if trip_id:
        target = trips.get(trip_id)
        if not isinstance(target, dict):
            return _result(False, data={"trip_id": trip_id}, error=f"Trip not found: {trip_id}")
        matches = [target]
    else:
        matches = _matching_trips(trips, order, destination, dates)
    if not matches:
        return _result(
            True,
            data={
                "added_order": order,
                "trip": None,
                "created_new_trip": False,
                "flight_link_status": "flight_pending_sync",
                "message": "我没有找到可合并的出行草稿，也不会创建航班日程。等航旅纵横同步后，我再帮您合并。",
            },
        )

    target = matches[0]
    _ensure_trip_defaults(target)
    warning = _trip_warning(target, order, destination, dates) if trip_id else None
    flights_result = flight_plan_reader.list_flights(days=30)
    if not flights_result.get("ok"):
        return flights_result
    flights = [item for item in flights_result.get("data", {}).get("flights", []) if isinstance(item, dict)]
    match_result = trip_flight_matcher.link_matching_flights(target, flights)
    target.setdefault("flight_order_hints", [])
    if not any(existing.get("raw_text_hash") == order["raw_text_hash"] for existing in target["flight_order_hints"] if isinstance(existing, dict)):
        target["flight_order_hints"].append(order)
    trip_flight_matcher.update_planning_status(target)
    target["updated_at"] = util.now_local_iso()
    _write_store(store)
    if match_result.get("linked"):
        message = "我已经从「飞行计划」找到对应航班并关联到这次 Trip，不会重复写入航班日程。"
    else:
        message = "我没有在飞行计划中找到这趟航班。等航旅纵横同步后，我再帮您合并。"
    return _result(
        True,
        data={
            "trip": target,
            "added_order": order,
            "created_new_trip": False,
            "linked": match_result.get("linked", {}),
            "ambiguous_candidates": match_result.get("ambiguous_candidates", {}),
            "flight_link_status": target.get("flight_link_status"),
            "warning": warning,
            "needs_confirmation": bool(warning),
            "message": message,
        },
    )


def add_order(text: str, trip_id: str | None = None) -> dict[str, Any]:
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
        "source_type": f"{parsed['order_type']}_order" if parsed["order_type"] in {"hotel", "train", "flight"} else "manual",
        "confirmation_status": "confirmed",
        "replaced_placeholder_id": None,
    }
    destination = _order_destination(order)
    dates = _order_dates(order)
    if not dates:
        return _result(False, data={"parsed": parsed}, error="travel_order_missing_dates")
    if order["order_type"] == "flight":
        return _handle_flight_order(order, destination, dates, trip_id=trip_id)

    store = _read_store()
    trips = store.setdefault("trips", {})
    warning = None
    explicit_trip = bool(trip_id)
    if trip_id:
        target = trips.get(trip_id)
        if not isinstance(target, dict):
            return _result(False, data={"trip_id": trip_id}, error=f"Trip not found: {trip_id}")
        warning = _trip_warning(target, order, destination, dates)
    else:
        matches = _matching_trips(trips, order, destination, dates)
        target = matches[0] if matches else None

    created_new = False
    if target is None:
        start_date = min(dates).isoformat()
        trip_id = _trip_id(start_date, destination, str(parsed.get("raw_text_hash", "")))
        target = {
            "trip_id": trip_id,
            "status": "draft",
            "title": _build_title(destination, [order]),
            "origin_city": "北京",
            "destination_city": destination,
            "start_date": start_date,
            "end_date": max(dates).isoformat(),
            "orders": [],
            "merge_history": [],
            "linked_flights": {},
            "needs_flight": True,
            "flight_link_status": "flight_pending_sync",
            "planning_status": "planned_only",
            "calendar": None,
            "suggested_calendar": _suggest_calendar([order]),
            "needs_calendar_choice": True,
            "missing_fields": ["calendar"],
            "created_at": util.now_local_iso(),
            "updated_at": util.now_local_iso(),
        }
        trips[trip_id] = target
        created_new = True

    _ensure_trip_defaults(target)
    merge_result = _merge_real_order_into_trip(target, order, explicit_trip=explicit_trip)
    warning = warning or merge_result.get("warning")
    if destination and not target.get("destination_city"):
        target["destination_city"] = destination
    if target.get("source") != "travel_intent":
        target["title"] = _build_title(str(target.get("destination_city") or destination), list(target.get("orders") or []))
        target["suggested_calendar"] = _suggest_calendar(list(target.get("orders") or []))
    else:
        target.setdefault("suggested_calendar", target.get("calendar") or _suggest_calendar(list(target.get("orders") or [])))
    target["missing_fields"] = ["calendar"] if not target.get("calendar") else []
    target["needs_calendar_choice"] = not bool(target.get("calendar"))
    _update_trip_bounds(target)
    trip_flight_matcher.update_planning_status(target)
    _write_store(store)
    return _result(
        True,
        data={
            "trip": target,
            "added_order": order,
            "created_new_trip": created_new,
            "warning": warning,
            "needs_confirmation": bool(warning) or bool(merge_result.get("needs_confirmation")),
            "replaced_placeholder": merge_result.get("replaced_placeholder"),
        },
    )


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
    add.add_argument("--trip-id")
    show = subparsers.add_parser("show")
    show.add_argument("--trip-id", required=True)
    cancel = subparsers.add_parser("cancel")
    cancel.add_argument("--trip-id", required=True)
    subparsers.add_parser("list")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "add":
        result = add_order(args.text, trip_id=args.trip_id)
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
