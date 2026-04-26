"""Rule-based parser for reminder follow-up replies."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, time, timedelta
from typing import Any

try:
    from . import util
except ImportError:  # Allows running as: python3 scripts/reminder_action_parser.py ...
    import util  # type: ignore


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


def _chinese_number_to_int(value: str) -> int | None:
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


def _parse_minutes(text: str, default: int | None = None) -> int | None:
    hour_match = re.search(r"(?P<num>\d+|[一二两三四五六七八九十]+)\s*个?\s*小时", text)
    if hour_match:
        value = _chinese_number_to_int(hour_match.group("num"))
        return value * 60 if value is not None else default
    minute_match = re.search(r"(?P<num>\d+|[一二两三四五六七八九十]+)\s*分钟", text)
    if minute_match:
        return _chinese_number_to_int(minute_match.group("num"))
    return default


def _apply_daypart(daypart: str | None, hour: int) -> int:
    if daypart in {"下午", "晚上", "今晚"} and 1 <= hour <= 11:
        return hour + 12
    if daypart == "中午" and 1 <= hour <= 10:
        return hour + 12
    return hour


def _parse_target_time(text: str, now: datetime | None = None) -> str | None:
    base = now or datetime.now()
    target_date = base.date()
    if "明天" in text:
        target_date = target_date + timedelta(days=1)
    elif "后天" in text:
        target_date = target_date + timedelta(days=2)

    match = re.search(
        r"(?P<daypart>上午|下午|晚上|今晚|中午|早上)?\s*"
        r"(?P<hour>\d{1,2}|[一二两三四五六七八九十]{1,3})"
        r"(?:(?:点(?P<minute_word>\d{1,2}|[一二两三四五六七八九十]{1,3}|半)?)|(?:[:：](?P<minute_colon>\d{1,2})))",
        text,
    )
    if not match:
        return None
    hour_value = _chinese_number_to_int(match.group("hour"))
    if hour_value is None:
        return None
    minute_text = match.group("minute_word") or match.group("minute_colon")
    if minute_text == "半":
        minute = 30
    elif minute_text:
        minute_value = _chinese_number_to_int(minute_text)
        if minute_value is None:
            return None
        minute = minute_value
    else:
        minute = 0
    hour = _apply_daypart(match.group("daypart"), hour_value)
    return datetime.combine(target_date, time(hour, minute)).isoformat(timespec="minutes")


def parse_action_text(text: str) -> dict[str, Any]:
    """Parse a reminder follow-up reply into an action intent."""
    if not isinstance(text, str) or not text.strip():
        return util.json_error("text must be a non-empty string.")
    normalized = text.strip()
    data: dict[str, Any] = {
        "intent": "unknown",
        "minutes": None,
        "target_time": None,
        "needs_confirmation": True,
    }

    if any(token in normalized for token in ("已到达", "到了", "我到了")):
        data["intent"] = "arrived"
        return util.json_ok(data)
    if "不再提醒" in normalized or "别再提醒" in normalized:
        data["intent"] = "disable_reminder"
        return util.json_ok(data)
    if "提前" in normalized and "提醒" in normalized:
        data["intent"] = "change_offset"
        data["minutes"] = _parse_minutes(normalized)
        return util.json_ok(data)
    if any(token in normalized for token in ("取消这个日程", "取消日程")) or normalized == "取消":
        data["intent"] = "cancel"
        return util.json_ok(data)
    if any(token in normalized for token in ("延后", "推迟", "稍后提醒")):
        data["intent"] = "snooze"
        data["minutes"] = _parse_minutes(normalized, default=10)
        return util.json_ok(data)
    if any(token in normalized for token in ("改到", "改成", "改为", "调整到")):
        data["intent"] = "reschedule"
        data["target_time"] = _parse_target_time(normalized)
        return util.json_ok(data)

    data["needs_confirmation"] = False
    return util.json_ok(data)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Parse reminder follow-up action text.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    parse = subparsers.add_parser("parse")
    parse.add_argument("text")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "parse":
        result = parse_action_text(args.text)
    else:
        raise AssertionError(args.command)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
