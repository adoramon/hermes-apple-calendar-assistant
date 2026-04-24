"""Rule-based natural-language event draft parser for v2.0-alpha."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, time, timedelta
from typing import Any

try:
    from . import settings, util
except ImportError:  # Allows running as: python3 scripts/nlp_event_parser.py ...
    import settings  # type: ignore
    import util  # type: ignore


WEEKDAY_MAP = {
    "一": 0,
    "二": 1,
    "三": 2,
    "四": 3,
    "五": 4,
    "六": 5,
    "日": 6,
    "天": 6,
}
CHINESE_DIGITS = {
    "零": 0,
    "〇": 0,
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
}
TIME_RE = re.compile(
    r"(?P<daypart>上午|下午|晚上|今晚|中午|早上)?\s*"
    r"(?P<hour>\d{1,2}|[零〇一二两三四五六七八九十]{1,3})"
    r"(?:(?:点(?P<minute_word>\d{1,2}|[零〇一二两三四五六七八九十]{1,3}|半)?)|(?:[:：](?P<minute_colon>\d{1,2})))"
)
LOCATION_PATTERNS = (
    re.compile(r"去(?P<location>[\u4e00-\u9fa5A-Za-z0-9_\-·\.]+?)(?=见|拜访|开会|吃饭|合作|$)"),
    re.compile(r"在(?P<location>[\u4e00-\u9fa5A-Za-z0-9_\-·\.]+?)(?=和|跟|与|见|拜访|开会|会议|吃饭|合作|$)"),
)
BUSINESS_KEYWORDS = ("客户", "会议", "商务", "开会", "拜访", "合作")
PERSONAL_KEYWORDS = ("个人", "健身", "体检", "看病", "开药", "理发")
COUPLE_KEYWORDS = ("家人", "入住酒店", "孩子", "吃饭", "家庭", "旅游", "夫妻", "太太", "老婆", "两个人")


def _chinese_number_to_int(value: str) -> int | None:
    """Convert a small Chinese number to an integer."""
    if value.isdigit():
        return int(value)
    if value in CHINESE_DIGITS:
        return CHINESE_DIGITS[value]
    if value == "十":
        return 10
    if "十" in value:
        left, _, right = value.partition("十")
        tens = CHINESE_DIGITS.get(left, 1) if left else 1
        ones = CHINESE_DIGITS.get(right, 0) if right else 0
        return tens * 10 + ones
    return None


def _parse_date(text: str, today: date) -> tuple[date | None, list[str], list[str]]:
    """Parse supported date expressions from text."""
    assumptions: list[str] = []
    consumed: list[str] = []
    if "后天" in text:
        return today + timedelta(days=2), ["后天"], assumptions
    if "明天" in text:
        return today + timedelta(days=1), ["明天"], assumptions
    if "今天" in text:
        return today, ["今天"], assumptions

    next_week = re.search(r"下周([一二三四五六日天])", text)
    if next_week:
        weekday = WEEKDAY_MAP[next_week.group(1)]
        monday = today - timedelta(days=today.weekday())
        return monday + timedelta(days=7 + weekday), [next_week.group(0)], assumptions

    this_week = re.search(r"(?:周|星期)([一二三四五六日天])", text)
    if this_week:
        weekday = WEEKDAY_MAP[this_week.group(1)]
        monday = today - timedelta(days=today.weekday())
        candidate = monday + timedelta(days=weekday)
        if candidate < today:
            candidate += timedelta(days=7)
            assumptions.append("weekday_without_next_uses_upcoming_week")
        return candidate, [this_week.group(0)], assumptions

    return None, consumed, assumptions


def _apply_daypart(daypart: str | None, hour: int) -> int:
    """Apply Chinese daypart hints to a parsed hour."""
    if daypart in {"下午", "晚上", "今晚"} and 1 <= hour <= 11:
        return hour + 12
    if daypart == "中午" and 1 <= hour <= 10:
        return hour + 12
    return hour


def _default_hour_for_daypart(text: str) -> int | None:
    """Return a conservative default hour for daypart-only expressions."""
    if "上午" in text or "早上" in text:
        return 9
    if "下午" in text:
        return 15
    if "晚上" in text or "今晚" in text:
        return 19
    if "中午" in text:
        return 12
    return None


def _parse_time(text: str, event_date: date) -> tuple[datetime | None, list[str], list[str]]:
    """Parse supported time expressions from text."""
    match = TIME_RE.search(text)
    assumptions: list[str] = []
    if match:
        hour_value = _chinese_number_to_int(match.group("hour"))
        if hour_value is None or not 0 <= hour_value <= 23:
            return None, [], ["time_parse_failed"]
        minute_text = match.group("minute_word") or match.group("minute_colon")
        if minute_text == "半":
            minute = 30
        elif minute_text:
            minute_value = _chinese_number_to_int(minute_text)
            if minute_value is None or not 0 <= minute_value <= 59:
                return None, [], ["time_parse_failed"]
            minute = minute_value
        else:
            minute = 0
        hour = _apply_daypart(match.group("daypart"), hour_value)
        return datetime.combine(event_date, time(hour, minute)), [match.group(0)], assumptions

    default_hour = _default_hour_for_daypart(text)
    if default_hour is not None:
        assumptions.append("time_defaulted_from_daypart")
        return datetime.combine(event_date, time(default_hour, 0)), [], assumptions
    return None, [], assumptions


def _infer_calendar(text: str) -> tuple[str, list[str]]:
    """Infer the target normal-write calendar from keywords."""
    if any(keyword in text for keyword in BUSINESS_KEYWORDS) or re.search(r"[\u4e00-\u9fa5A-Za-z]+总", text):
        return "商务计划", ["calendar_inferred_from_business_keywords"]
    if any(keyword in text for keyword in COUPLE_KEYWORDS):
        return "夫妻计划", ["calendar_inferred_from_family_keywords"]
    if any(keyword in text for keyword in PERSONAL_KEYWORDS):
        return "个人计划", ["calendar_inferred_from_personal_keywords"]
    return "个人计划", ["calendar_defaulted_to_personal"]


def _extract_location(text: str) -> tuple[str, list[str], list[str]]:
    """Extract a simple location phrase from text."""
    for pattern in LOCATION_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group("location"), [match.group(0)], []
    return "", [], []


def _extract_title(text: str, consumed: list[str], location: str) -> str:
    """Remove date/time/location scaffolding to produce a draft title."""
    title = text
    for fragment in consumed:
        if fragment:
            title = title.replace(fragment, " ")
    if location:
        title = title.replace(location, " ")
    for token in ("帮我", "安排", "添加", "新建", "创建", "日程", "提醒我", "提醒", "上午", "下午", "晚上", "今晚", "中午", "早上", "去", "在"):
        title = title.replace(token, " ")
    title = re.sub(r"\s+", " ", title).strip(" ，,。")
    return title.lstrip("和跟与")


def parse_event_text(text: str, today: date | None = None) -> dict[str, Any]:
    """Parse natural-language text into a confirmation-required event draft."""
    if not isinstance(text, str) or not text.strip():
        return util.json_error("text must be a non-empty string.")

    base_date = today or datetime.now().date()
    assumptions: list[str] = []
    event_date, date_consumed, date_assumptions = _parse_date(text, base_date)
    assumptions.extend(date_assumptions)
    if event_date is None:
        event_date = base_date
        assumptions.append("date_defaulted_to_today")

    start, time_consumed, time_assumptions = _parse_time(text, event_date)
    assumptions.extend(time_assumptions)
    location, location_consumed, location_assumptions = _extract_location(text)
    assumptions.extend(location_assumptions)
    calendar, calendar_assumptions = _infer_calendar(text)
    assumptions.extend(calendar_assumptions)

    if start is None:
        start = datetime.combine(event_date, time(9, 0))
        assumptions.append("time_defaulted_to_09:00")

    duration_minutes = settings.get_default_event_duration_minutes()
    end = start + timedelta(minutes=duration_minutes)
    assumptions.append(f"default_duration_minutes={duration_minutes}")

    title = _extract_title(text, date_consumed + time_consumed + location_consumed, location)
    if not title:
        title = text.strip()
        assumptions.append("title_defaulted_to_original_text")

    confidence = 0.55
    if date_consumed:
        confidence += 0.15
    if time_consumed:
        confidence += 0.15
    if not any(item.startswith("calendar_defaulted") for item in assumptions):
        confidence += 0.1
    if location:
        confidence += 0.05

    data = {
        "title": title,
        "calendar": calendar,
        "start": start.isoformat(timespec="seconds"),
        "end": end.isoformat(timespec="seconds"),
        "location": location,
        "notes": "",
        "confidence": min(round(confidence, 3), 1.0),
        "needs_confirmation": True,
        "assumptions": assumptions,
    }
    return util.json_ok(data)


def _build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(description="Parse natural-language event text into a draft.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    parse = subparsers.add_parser("parse", help="Parse natural-language event text.")
    parse.add_argument("text")
    parse.add_argument("--today", help="Test-only base date, e.g. 2026-04-24.")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the command-line interface."""
    args = _build_parser().parse_args(argv)
    if args.command == "parse":
        today = date.fromisoformat(args.today) if args.today else None
        result = parse_event_text(args.text, today=today)
    else:
        raise AssertionError(args.command)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
