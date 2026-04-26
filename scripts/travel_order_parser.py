"""Rule-based travel order parser for trip aggregation."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timedelta
from typing import Any

try:
    from . import hotel_order_parser
except ImportError:  # Allows running as: python3 scripts/travel_order_parser.py ...
    import hotel_order_parser  # type: ignore


PLATFORMS = (
    "携程",
    "飞猪",
    "航旅纵横",
    "12306",
    "美团",
    "Booking",
    "Agoda",
    "Airbnb",
    "Trip.com",
)
DATE_RE = re.compile(r"(20\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})日?")
TIME_RE = re.compile(r"(?<!\d)([01]?\d|2[0-3]):([0-5]\d)(?!\d)")
FLIGHT_NO_RE = re.compile(r"\b([A-Z]{2}\d{2,4})\b", re.I)
TRAIN_NO_RE = re.compile(r"\b([GDCZTK]\d{1,5})\b", re.I)
ORDER_NO_RE = re.compile(r"(?:订单号|确认号|预订号|订单编号)\s*[:：]?\s*([A-Za-z0-9_-]{3,40})")
PERSON_RE = re.compile(r"(?:乘机人|乘车人|入住人|旅客|客人|姓名)\s*[:：]?\s*([\u4e00-\u9fa5A-Za-z·]{2,30})")
SEAT_RE = re.compile(r"(?:座位|座席|席位)\s*[:：]?\s*([^\s，,。；;]{2,20})")
AIRPORT_STATION_RE = re.compile(
    r"([\u4e00-\u9fa5]{2,12}(?:首都|大兴|虹桥|浦东|白云|宝安|双流|天府|萧山|禄口|高崎|江北|新郑|咸阳|黄花|机场|东站|西站|南站|北站|站|东|西|南|北)(?:T\d)?)"
)


def _result(ok: bool, data: Any = None, error: str | None = None) -> dict[str, Any]:
    return {"ok": ok, "data": data, "error": error}


def _clean(value: Any) -> str:
    if not isinstance(value, str):
        return str(value or "").strip()
    return " ".join(value.split()).strip(" ：:，,;；")


def _source_platform(text: str) -> str:
    lowered = text.lower()
    for platform in PLATFORMS:
        if platform.lower() in lowered:
            return platform
    return "unknown"


def _raw_hash(text: str) -> str:
    return hashlib.sha1(_clean(text).encode("utf-8")).hexdigest()[:16]


def _all_dates(text: str) -> list[str]:
    return [f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}" for m in DATE_RE.finditer(text)]


def _all_times(text: str) -> list[str]:
    return [f"{int(m.group(1)):02d}:{int(m.group(2)):02d}" for m in TIME_RE.finditer(text)]


def _combine(date_text: str | None, time_text: str | None) -> str | None:
    if not date_text or not time_text:
        return None
    return f"{date_text}T{time_text}:00"


def _same_or_next_day(start_iso: str | None, end_iso: str | None) -> str | None:
    if not start_iso or not end_iso:
        return end_iso
    start = datetime.fromisoformat(start_iso)
    end = datetime.fromisoformat(end_iso)
    if end < start:
        end += timedelta(days=1)
    return end.isoformat(timespec="seconds")


def _city_from_place(place: str) -> str:
    for city in ("北京", "上海", "广州", "深圳", "杭州", "南京", "长沙", "成都", "重庆", "西安", "厦门", "香港"):
        if place.startswith(city):
            return city
    cleaned = place
    changed = True
    while changed:
        changed = False
        new_value = re.sub(r"(T\d|首都|大兴|虹桥|浦东|白云|宝安|双流|天府|萧山|禄口|高崎|江北|新郑|咸阳|黄花|机场|火车站|东站|西站|南站|北站|站|东|西|南|北)$", "", cleaned)
        if new_value != cleaned:
            cleaned = new_value
            changed = True
    return cleaned[:4].strip()


def _terminal_from_place(place: str) -> str:
    match = re.search(r"(T\d)", place, re.I)
    return match.group(1).upper() if match else ""


def _confirmation_number(text: str) -> str:
    match = ORDER_NO_RE.search(text)
    return _clean(match.group(1)) if match else ""


def _person_name(text: str) -> str:
    match = PERSON_RE.search(text)
    return _clean(match.group(1)) if match else ""


def _parse_flight(text: str) -> dict[str, Any]:
    normalized = _clean(text)
    flight_match = FLIGHT_NO_RE.search(normalized)
    places = AIRPORT_STATION_RE.findall(normalized)
    airport_places = [place for place in places if "站" not in place]
    dates = _all_dates(normalized)
    times = _all_times(normalized)
    dep_place = airport_places[0] if airport_places else ""
    arr_place = airport_places[1] if len(airport_places) > 1 else ""
    dep_date = dates[0] if dates else None
    arr_date = dates[1] if len(dates) > 1 else dep_date
    departure_datetime = _combine(dep_date, times[0] if times else None)
    arrival_datetime = _combine(arr_date, times[1] if len(times) > 1 else None)
    arrival_datetime = _same_or_next_day(departure_datetime, arrival_datetime)
    fields = {
        "flight_no": flight_match.group(1).upper() if flight_match else "",
        "airline": "",
        "departure_city": _city_from_place(dep_place) if dep_place else "",
        "arrival_city": _city_from_place(arr_place) if arr_place else "",
        "departure_airport": re.sub(r"T\d$", "", dep_place),
        "arrival_airport": re.sub(r"T\d$", "", arr_place),
        "departure_terminal": _terminal_from_place(dep_place),
        "arrival_terminal": _terminal_from_place(arr_place),
        "departure_datetime": departure_datetime,
        "arrival_datetime": arrival_datetime,
        "passenger_name": _person_name(normalized),
        "confirmation_number": _confirmation_number(normalized),
    }
    missing = [name for name in ("flight_no", "departure_datetime", "arrival_datetime") if not fields.get(name)]
    if not fields.get("departure_airport"):
        missing.append("departure_airport")
    if not fields.get("arrival_airport"):
        missing.append("arrival_airport")
    confidence = 0.35
    confidence += 0.25 if fields["flight_no"] else 0
    confidence += 0.15 if fields["departure_datetime"] and fields["arrival_datetime"] else 0
    confidence += 0.15 if fields["departure_airport"] and fields["arrival_airport"] else 0
    confidence += 0.05 if _source_platform(normalized) != "unknown" else 0
    return {"fields": fields, "missing_fields": missing, "confidence": min(confidence, 0.95)}


def _parse_train(text: str) -> dict[str, Any]:
    normalized = _clean(text)
    train_match = TRAIN_NO_RE.search(normalized)
    places = AIRPORT_STATION_RE.findall(normalized)
    station_places = [place for place in places if "站" in place]
    if len(station_places) < 2:
        station_places = places
    dates = _all_dates(normalized)
    times = _all_times(normalized)
    dep_place = station_places[0] if station_places else ""
    arr_place = station_places[1] if len(station_places) > 1 else ""
    dep_date = dates[0] if dates else None
    arr_date = dates[1] if len(dates) > 1 else dep_date
    departure_datetime = _combine(dep_date, times[0] if times else None)
    arrival_datetime = _combine(arr_date, times[1] if len(times) > 1 else None)
    arrival_datetime = _same_or_next_day(departure_datetime, arrival_datetime)
    seat_match = SEAT_RE.search(normalized)
    fields = {
        "train_no": train_match.group(1).upper() if train_match else "",
        "departure_city": _city_from_place(dep_place) if dep_place else "",
        "arrival_city": _city_from_place(arr_place) if arr_place else "",
        "departure_station": dep_place,
        "arrival_station": arr_place,
        "departure_datetime": departure_datetime,
        "arrival_datetime": arrival_datetime,
        "passenger_name": _person_name(normalized),
        "seat": _clean(seat_match.group(1)) if seat_match else "",
        "confirmation_number": _confirmation_number(normalized),
    }
    missing = [name for name in ("train_no", "departure_datetime", "arrival_datetime") if not fields.get(name)]
    if not fields.get("departure_station"):
        missing.append("departure_station")
    if not fields.get("arrival_station"):
        missing.append("arrival_station")
    confidence = 0.35
    confidence += 0.25 if fields["train_no"] else 0
    confidence += 0.15 if fields["departure_datetime"] and fields["arrival_datetime"] else 0
    confidence += 0.15 if fields["departure_station"] and fields["arrival_station"] else 0
    confidence += 0.05 if _source_platform(normalized) != "unknown" else 0
    return {"fields": fields, "missing_fields": missing, "confidence": min(confidence, 0.95)}


def _parse_hotel(text: str) -> dict[str, Any]:
    parsed = hotel_order_parser.parse_order_text(text)
    fields = {
        "hotel_name": parsed.get("hotel_name", ""),
        "address": parsed.get("address", ""),
        "checkin_date": parsed.get("checkin_date"),
        "checkout_date": parsed.get("checkout_date"),
        "checkin_time": parsed.get("checkin_time"),
        "checkout_time": parsed.get("checkout_time") or "12:00",
        "nights": None,
        "guest_name": parsed.get("guest_name", ""),
        "room_type": parsed.get("room_type", ""),
        "rooms": "",
        "confirmation_number": parsed.get("confirmation_number", ""),
        "phone": "",
    }
    if fields["checkin_date"] and fields["checkout_date"]:
        start = datetime.fromisoformat(str(fields["checkin_date"]))
        end = datetime.fromisoformat(str(fields["checkout_date"]))
        fields["nights"] = max((end.date() - start.date()).days, 0)
    missing = [field for field in ("hotel_name", "checkin_date", "checkout_date", "checkin_time") if not fields.get(field)]
    return {"fields": fields, "missing_fields": missing, "confidence": parsed.get("confidence", 0.0)}


def parse_order_text(text: str) -> dict[str, Any]:
    normalized = _clean(text)
    source = _source_platform(normalized)
    flight_score = 0
    train_score = 0
    hotel_score = 0
    if FLIGHT_NO_RE.search(normalized) or "航班" in normalized or "乘机人" in normalized or source == "航旅纵横":
        flight_score += 2
    if TRAIN_NO_RE.search(normalized) or "高铁" in normalized or "火车" in normalized or "乘车人" in normalized or source == "12306":
        train_score += 2
    if any(hint in normalized for hint in ("酒店", "入住", "离店", "退房", "房型", "民宿", "宾馆")):
        hotel_score += 2

    order_type = "unknown"
    parsed = {"fields": {}, "missing_fields": [], "confidence": 0.0}
    if hotel_score >= flight_score and hotel_score >= train_score and hotel_score > 0:
        parsed = _parse_hotel(normalized)
        order_type = "hotel" if parsed["confidence"] >= 0.35 else "unknown"
    elif flight_score >= train_score and flight_score > 0:
        parsed = _parse_flight(normalized)
        order_type = "flight" if parsed["confidence"] >= 0.45 else "unknown"
    elif train_score > 0:
        parsed = _parse_train(normalized)
        order_type = "train" if parsed["confidence"] >= 0.45 else "unknown"

    return {
        "order_type": order_type,
        "confidence": round(float(parsed.get("confidence", 0.0)), 2),
        "source_platform": source,
        "raw_text_hash": _raw_hash(normalized),
        "fields": parsed.get("fields", {}) if order_type != "unknown" else {},
        "missing_fields": parsed.get("missing_fields", []) if order_type != "unknown" else [],
        "needs_confirmation": order_type != "unknown",
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Parse travel order text.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    parse = subparsers.add_parser("parse")
    parse.add_argument("--text", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "parse":
        result = _result(True, data=parse_order_text(args.text))
    else:
        raise AssertionError(args.command)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
