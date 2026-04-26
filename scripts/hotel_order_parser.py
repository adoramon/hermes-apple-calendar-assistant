"""Rule-based hotel order parser for Calendar draft creation."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from typing import Any


HOTEL_HINTS = ("酒店", "入住", "离店", "退房", "房型", "订单号", "确认号", "预订", "民宿")
PLATFORMS = ("携程", "美团", "飞猪", "Booking", "Agoda", "Airbnb", "Expedia", "Trip.com")
DATE_RE = re.compile(r"(20\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})日?")
DATE_NO_YEAR_RE = re.compile(r"(?<!\d)(\d{1,2})月(\d{1,2})日")
TIME_RE = re.compile(r"(?<!\d)([01]?\d|2[0-3]):([0-5]\d)(?!\d)")


def _result(ok: bool, data: Any = None, error: str | None = None) -> dict[str, Any]:
    return {"ok": ok, "data": data, "error": error}


def _clean(value: Any) -> str:
    if not isinstance(value, str):
        return str(value or "").strip()
    return " ".join(value.split()).strip(" ：:，,;；")


def _date_iso(match: re.Match[str]) -> str:
    return f"{int(match.group(1)):04d}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"


def _date_iso_no_year(match: re.Match[str]) -> str:
    return f"{datetime.now().year:04d}-{int(match.group(1)):02d}-{int(match.group(2)):02d}"


def _find_after_label(text: str, labels: tuple[str, ...], stop_words: tuple[str, ...], max_len: int = 60) -> str:
    label_pattern = "|".join(re.escape(label) for label in labels)
    stop_pattern = "|".join(re.escape(word) for word in stop_words)
    match = re.search(rf"(?:{label_pattern})\s*[:：]?\s*(.+?)(?=\s*(?:{stop_pattern})\s*[:：]?|$)", text, re.I)
    if not match:
        return ""
    return _clean(match.group(1))[:max_len].strip()


def _find_dates(text: str) -> tuple[str | None, str | None]:
    checkin = None
    checkout = None
    checkin_match = re.search(r"(?:入住|到店|入住日期)\s*[:：]?\s*" + DATE_RE.pattern, text)
    if checkin_match:
        checkin = f"{int(checkin_match.group(1)):04d}-{int(checkin_match.group(2)):02d}-{int(checkin_match.group(3)):02d}"
    checkout_match = re.search(r"(?:离店|退房|离店日期|退房日期)\s*[:：]?\s*" + DATE_RE.pattern, text)
    if checkout_match:
        checkout = f"{int(checkout_match.group(1)):04d}-{int(checkout_match.group(2)):02d}-{int(checkout_match.group(3)):02d}"
    if checkin and checkout:
        return checkin, checkout
    dates = [_date_iso(match) for match in DATE_RE.finditer(text)]
    if not dates:
        dates = [_date_iso_no_year(match) for match in DATE_NO_YEAR_RE.finditer(text)]
    if not checkin and dates:
        checkin = dates[0]
    if not checkout and len(dates) > 1:
        checkout = dates[1]
    return checkin, checkout


def _find_time_near(text: str, labels: tuple[str, ...]) -> str | None:
    label_pattern = "|".join(re.escape(label) for label in labels)
    match = re.search(rf"(?:{label_pattern})\s*(?:时间)?\s*[:：]?\s*{TIME_RE.pattern}", text)
    if match:
        return f"{int(match.group(1)):02d}:{int(match.group(2)):02d}"
    label_match = re.search(rf"(?:{label_pattern})\s*(?:时间)?\s*[:：]?", text)
    if not label_match:
        return None
    # Hotel screenshots often say "入住 2026-04-27 23:30" or "预计到店 23:00".
    nearby = text[label_match.end() : label_match.end() + 48]
    time_match = TIME_RE.search(nearby)
    if not time_match:
        return None
    return f"{int(time_match.group(1)):02d}:{int(time_match.group(2)):02d}"


def _find_platform(text: str) -> str:
    lowered = text.lower()
    for platform in PLATFORMS:
        if platform.lower() in lowered:
            return platform
    return ""


def _find_hotel_name(text: str) -> str:
    explicit = _find_after_label(
        text,
        ("酒店名称", "酒店", "民宿", "住宿"),
        ("地址", "入住", "离店", "退房", "入住人", "房型", "订单号", "确认号"),
    )
    if explicit:
        explicit = re.sub(r"^(订单|预订|确认单|预订单)\s*", "", explicit).strip()
        if explicit.startswith(("入住", "离店", "退房", "预计到店")):
            explicit = ""
        if explicit and explicit not in {"订单", "预订"}:
            return explicit
    match = re.search(r"(?:订单|预订)\s+([^\s，,。；;]{2,40}(?:酒店|宾馆|民宿|度假村|公寓|客栈|Banyan Tree|Hotel))", text, re.I)
    if match:
        return _clean(match.group(1))
    match = re.search(r"([^\s，,。；;]{2,60}(?:酒店|宾馆|民宿|度假村|公寓|客栈|Banyan Tree|Hotel))\s+(?:入住|离店|退房|地址)", text, re.I)
    return _clean(match.group(1)) if match else ""


def parse_order_text(text: str) -> dict[str, Any]:
    """Parse text into a hotel-order data object."""
    normalized = _clean(text)
    hint_count = sum(1 for hint in HOTEL_HINTS if hint.lower() in normalized.lower())
    source = _find_platform(normalized)
    checkin_date, checkout_date = _find_dates(normalized)
    hotel_name = _find_hotel_name(normalized)
    is_hotel_order = bool(hotel_name and (checkin_date or checkout_date) and hint_count >= 1)

    address = _find_after_label(
        normalized,
        ("酒店地址", "地址"),
        ("入住", "离店", "退房", "入住人", "客人", "房型", "订单号", "确认号", "平台"),
        max_len=120,
    )
    guest_name = _find_after_label(
        normalized,
        ("入住人", "客人", "住客", "姓名"),
        ("房型", "订单号", "确认号", "平台", "地址", "入住", "离店"),
        max_len=30,
    )
    room_type = _find_after_label(
        normalized,
        ("房型", "房间类型"),
        ("订单号", "确认号", "平台", "入住人", "地址", "入住", "离店"),
        max_len=60,
    )
    confirmation_number = _find_after_label(
        normalized,
        ("订单号", "确认号", "预订号", "订单编号"),
        ("平台", "房型", "入住人", "地址", "入住", "离店"),
        max_len=40,
    )
    checkin_time = _find_time_near(normalized, ("入住时间", "到店时间", "预计到店", "到店", "入住"))
    checkout_time = _find_time_near(normalized, ("离店时间", "退房时间", "退房", "离店"))

    missing_fields = ["calendar"]
    if not checkin_time:
        missing_fields.append("checkin_time")
    if is_hotel_order:
        for field_name, value in (
            ("hotel_name", hotel_name),
            ("checkin_date", checkin_date),
            ("checkout_date", checkout_date),
        ):
            if not value:
                missing_fields.append(field_name)
    confidence = 0.0
    if is_hotel_order:
        score = 0.45 + min(hint_count, 4) * 0.08
        score += 0.12 if source else 0
        score += 0.12 if address else 0
        score += 0.08 if confirmation_number else 0
        confidence = min(score, 0.95)

    return {
        "is_hotel_order": is_hotel_order,
        "hotel_name": hotel_name,
        "address": address,
        "checkin_date": checkin_date,
        "checkout_date": checkout_date,
        "checkin_time": checkin_time,
        "checkout_time": checkout_time,
        "guest_name": guest_name,
        "room_type": room_type,
        "confirmation_number": confirmation_number,
        "source": source,
        "confidence": round(confidence, 2),
        "missing_fields": missing_fields if is_hotel_order else [],
        "needs_confirmation": bool(is_hotel_order),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Parse hotel order text.")
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
