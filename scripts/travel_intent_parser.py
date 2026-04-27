"""Rule-based natural language parser for travel intent planning."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

try:
    from . import util
except ImportError:  # Allows running as: python3 scripts/travel_intent_parser.py ...
    import util  # type: ignore


DEFAULT_ORIGIN_CITY = "北京"
WEEKDAY_MAP = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6}
NUMBER_MAP = {
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}
CITY_HINTS = (
    "北京",
    "上海",
    "广州",
    "深圳",
    "杭州",
    "南京",
    "苏州",
    "成都",
    "重庆",
    "西安",
    "长沙",
    "武汉",
    "青岛",
    "厦门",
    "三亚",
    "东京",
    "大阪",
    "香港",
    "澳门",
    "首尔",
    "新加坡",
)
BUSINESS_HINTS = ("见客户", "拜访客户", "开会", "出差", "商务", "客户")
COUPLE_HINTS = ("和太太", "和老婆", "夫妻", "两个人", "一起去", "一起玩", "蜜月")
PERSONAL_HINTS = ("个人", "自己", "独自", "一个人")
LEISURE_HINTS = ("旅行", "旅游", "玩", "度假")
PURPOSE_PATTERNS = (
    re.compile(r"(见客户)"),
    re.compile(r"(拜访客户)"),
    re.compile(r"(开会)"),
    re.compile(r"(出差)"),
    re.compile(r"(旅行)"),
    re.compile(r"(旅游)"),
    re.compile(r"(度假)"),
    re.compile(r"(玩)"),
)


@dataclass
class DateResolution:
    start_date: str | None = None
    assumption: str | None = None


def _clean(text: Any) -> str:
    return " ".join(str(text or "").split())


def _number_from_text(text: str) -> int | None:
    normalized = text.strip()
    if not normalized:
        return None
    if normalized.isdigit():
        return int(normalized)
    if normalized == "十":
        return 10
    if len(normalized) == 2 and normalized.startswith("十") and normalized[1] in NUMBER_MAP:
        return 10 + NUMBER_MAP[normalized[1]]
    if len(normalized) == 2 and normalized.endswith("十") and normalized[0] in NUMBER_MAP:
        return NUMBER_MAP[normalized[0]] * 10
    if len(normalized) == 2 and normalized[0] in NUMBER_MAP and normalized[1] in NUMBER_MAP:
        return NUMBER_MAP[normalized[0]] + NUMBER_MAP[normalized[1]]
    return NUMBER_MAP.get(normalized)


def _next_weekday(base: date, weekday: int) -> date:
    delta = (weekday - base.weekday()) % 7
    return base + timedelta(days=delta)


def _extract_city(text: str) -> str:
    for pattern in (
        re.compile(r"(?:去|到|赴|飞往|飞去|前往)([\u4e00-\u9fa5]{2,8})"),
        re.compile(r"([\u4e00-\u9fa5]{2,8})(?:出差|旅行|旅游|玩|度假|拜访客户|见客户|开会)"),
    ):
        match = pattern.search(text)
        if not match:
            continue
        candidate = match.group(1)
        candidate = re.sub(r"^(下周[一二三四五六日天]|本周[一二三四五六日天]|周[一二三四五六日天]|明天|后天|下月|本周|下周)", "", candidate)
        candidate = re.split(r"(见客户|拜访客户|开会|出差|旅行|旅游|玩|度假|住一晚|当天回|当日回|两天|三天|四天|五天)", candidate)[0]
        candidate = candidate.strip("，。,、 ")
        if candidate and candidate not in {"客户", "太太", "老婆", "自己", "独自"}:
            return candidate
    for city in CITY_HINTS:
        if city in text:
            return city
    return ""


def _extract_origin(text: str) -> tuple[str, list[str]]:
    assumptions: list[str] = []
    for pattern in (
        re.compile(r"从([\u4e00-\u9fa5]{2,8})出发"),
        re.compile(r"([\u4e00-\u9fa5]{2,8})飞[\u4e00-\u9fa5]{2,8}"),
    ):
        match = pattern.search(text)
        if match:
            return match.group(1), assumptions
    assumptions.append("未提供出发城市，默认按北京规划。")
    return DEFAULT_ORIGIN_CITY, assumptions


def _resolve_date(text: str, today: date | None = None) -> DateResolution:
    today = today or date.today()

    match = re.search(r"下周([一二三四五六日天])", text)
    if match:
        next_monday = today - timedelta(days=today.weekday()) + timedelta(days=7)
        resolved = next_monday + timedelta(days=WEEKDAY_MAP[match.group(1)])
        return DateResolution(start_date=resolved.isoformat())

    match = re.search(r"本周([一二三四五六日天])", text)
    if match:
        current_monday = today - timedelta(days=today.weekday())
        resolved = current_monday + timedelta(days=WEEKDAY_MAP[match.group(1)])
        return DateResolution(start_date=resolved.isoformat())

    match = re.search(r"周([一二三四五六日天])", text)
    if match:
        resolved = _next_weekday(today, WEEKDAY_MAP[match.group(1)])
        return DateResolution(start_date=resolved.isoformat())

    if "明天" in text:
        return DateResolution(start_date=(today + timedelta(days=1)).isoformat())
    if "后天" in text:
        return DateResolution(start_date=(today + timedelta(days=2)).isoformat())
    if "下周" in text:
        next_monday = today - timedelta(days=today.weekday()) + timedelta(days=7)
        return DateResolution(
            start_date=next_monday.isoformat(),
            assumption="只提到“下周”，默认从下周一开始规划。",
        )
    if "本周" in text:
        current_monday = today - timedelta(days=today.weekday())
        return DateResolution(
            start_date=current_monday.isoformat(),
            assumption="只提到“本周”，默认从本周一开始规划。",
        )
    if "下月" in text:
        year = today.year + (1 if today.month == 12 else 0)
        month = 1 if today.month == 12 else today.month + 1
        resolved = date(year, month, 1)
        return DateResolution(
            start_date=resolved.isoformat(),
            assumption="只提到“下月”，默认从下月1日开始规划。",
        )
    return DateResolution()


def _extract_duration(text: str) -> tuple[int | None, bool, bool]:
    same_day_return = any(word in text for word in ("当天回", "当日回", "当天往返", "当天来回"))
    if same_day_return:
        return 1, True, False

    stay_one_night = "住一晚" in text
    if stay_one_night:
        return 2, False, True

    match = re.search(r"([一二两三四五六七八九十\d]+)天", text)
    if match:
        number = _number_from_text(match.group(1))
        if number:
            return number, False, number > 1
    return None, False, False


def _detect_intent(text: str) -> tuple[str, str, list[str]]:
    companions: list[str] = []
    if any(hint in text for hint in COUPLE_HINTS):
        if "太太" in text:
            companions.append("太太")
        elif "老婆" in text:
            companions.append("老婆")
        elif "两个人" in text or "夫妻" in text:
            companions.append("同伴")
        purpose = "旅行" if any(hint in text for hint in LEISURE_HINTS) else "出行"
        return "couple_trip", purpose, companions
    if any(hint in text for hint in BUSINESS_HINTS):
        for pattern in PURPOSE_PATTERNS:
            match = pattern.search(text)
            if match and match.group(1) in BUSINESS_HINTS:
                return "business_trip", match.group(1), companions
        return "business_trip", "出差", companions
    if any(hint in text for hint in PERSONAL_HINTS):
        companions.append("自己")
        purpose = "旅行" if any(hint in text for hint in LEISURE_HINTS) else "出行"
        return "personal_trip", purpose, companions
    if any(hint in text for hint in LEISURE_HINTS):
        for pattern in PURPOSE_PATTERNS:
            match = pattern.search(text)
            if match and match.group(1) in LEISURE_HINTS:
                return "personal_trip", match.group(1), companions
        return "personal_trip", "旅行", companions
    return "unknown", "", companions


def _suggested_calendar(intent_type: str) -> str | None:
    if intent_type == "business_trip":
        return "商务计划"
    if intent_type == "couple_trip":
        return "夫妻计划"
    if intent_type == "personal_trip":
        return "个人计划"
    return None


def parse_intent(text: str) -> dict[str, Any]:
    normalized = _clean(text)
    intent_type, purpose, companions = _detect_intent(normalized)
    destination_city = _extract_city(normalized)
    origin_city, assumptions = _extract_origin(normalized)
    date_resolution = _resolve_date(normalized)
    if date_resolution.assumption:
        assumptions.append(date_resolution.assumption)
    duration_days, same_day_return, hotel_hint = _extract_duration(normalized)

    start_date = date_resolution.start_date
    end_date: str | None = None
    if start_date and duration_days:
        base = datetime.fromisoformat(start_date).date()
        end_date = (base + timedelta(days=duration_days - 1)).isoformat()
    elif start_date and same_day_return:
        end_date = start_date

    if duration_days is None and same_day_return:
        duration_days = 1
    needs_hotel = bool(hotel_hint or (duration_days and duration_days > 1 and not same_day_return))
    missing_fields: list[str] = []
    if not destination_city:
        missing_fields.append("destination_city")
    if not start_date:
        missing_fields.append("start_date")
    if duration_days is None and not same_day_return:
        missing_fields.append("duration_days")

    confidence = 0.15
    confidence += 0.3 if intent_type != "unknown" else 0.0
    confidence += 0.2 if destination_city else 0.0
    confidence += 0.15 if start_date else 0.0
    confidence += 0.1 if duration_days or same_day_return else 0.0
    confidence += 0.05 if purpose else 0.0
    confidence += 0.05 if companions else 0.0

    data = {
        "intent_type": intent_type,
        "destination_city": destination_city or None,
        "origin_city": origin_city,
        "start_date": start_date,
        "end_date": end_date,
        "duration_days": duration_days,
        "purpose": purpose or None,
        "companions": companions,
        "same_day_return": same_day_return,
        "needs_hotel": needs_hotel,
        "suggested_calendar": _suggested_calendar(intent_type),
        "missing_fields": missing_fields,
        "confidence": round(min(confidence, 0.95), 2),
        "needs_confirmation": True,
        "assumptions": assumptions,
    }
    return util.result(True, data=data, error=None)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Parse natural-language travel intent.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    parse = subparsers.add_parser("parse")
    parse.add_argument("text")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "parse":
        result = parse_intent(args.text)
    else:
        raise AssertionError(args.command)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
