"""Parse simple natural-language event requests into create-event drafts."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, time, timedelta
from typing import Any

try:
    from . import interactive_create, util
except ImportError:  # Allows running as: python3 scripts/nl_draft_parser.py ...
    import interactive_create  # type: ignore
    import util  # type: ignore


DEFAULT_DURATION_MINUTES = 60
TIME_RANGE_RE = re.compile(
    r"(?P<start_hour>\d{1,2})(?:[:：点](?P<start_minute>\d{1,2})?)?\s*"
    r"(?:-|－|—|–|到|至)\s*"
    r"(?P<end_hour>\d{1,2})(?:[:：点](?P<end_minute>\d{1,2})?)?"
)
SINGLE_TIME_RE = re.compile(r"(?<!\d)(?P<hour>\d{1,2})(?:[:：点](?P<minute>\d{1,2})?)")
ISO_DATE_RE = re.compile(r"(?P<year>\d{4})[-/.年](?P<month>\d{1,2})[-/.月](?P<day>\d{1,2})日?")
MD_DATE_RE = re.compile(r"(?P<month>\d{1,2})月(?P<day>\d{1,2})日?")
LOCATION_RE = re.compile(
    r"(?:在|地点[:：])(?P<location>[\u4e00-\u9fa5A-Za-z0-9_\-·\.]+?)"
    r"(?=和|跟|与|开会|会议|见面|吃饭|$)"
)
CALENDAR_HINTS = {
    "商务计划": ("商务", "客户", "会议", "开会", "工作", "项目", "面试"),
    "家庭计划": ("家庭", "家里", "父母", "孩子", "亲子"),
    "个人计划": ("个人", "自己", "健身", "体检", "理发", "学习"),
    "夫妻计划": ("夫妻", "老婆", "老公", "约会", "纪念日"),
}


def _result(ok: bool, data: Any = None, error: str | None = None) -> dict[str, Any]:
    return util.result(ok, data=data, error=error)


def _parse_date(text: str, today: date) -> tuple[date | None, list[str]]:
    consumed = []
    if "大后天" in text:
        consumed.append("大后天")
        return today + timedelta(days=3), consumed
    if "后天" in text:
        consumed.append("后天")
        return today + timedelta(days=2), consumed
    if "明天" in text:
        consumed.append("明天")
        return today + timedelta(days=1), consumed
    if "今天" in text:
        consumed.append("今天")
        return today, consumed

    iso_match = ISO_DATE_RE.search(text)
    if iso_match:
        consumed.append(iso_match.group(0))
        return (
            date(
                int(iso_match.group("year")),
                int(iso_match.group("month")),
                int(iso_match.group("day")),
            ),
            consumed,
        )

    md_match = MD_DATE_RE.search(text)
    if md_match:
        consumed.append(md_match.group(0))
        month = int(md_match.group("month"))
        day = int(md_match.group("day"))
        candidate = date(today.year, month, day)
        if candidate < today:
            candidate = date(today.year + 1, month, day)
        return candidate, consumed

    return None, consumed


def _apply_daypart(text: str, hour: int) -> int:
    if any(word in text for word in ("下午", "晚上", "今晚")) and 1 <= hour <= 11:
        return hour + 12
    if "中午" in text and 1 <= hour <= 10:
        return hour + 12
    return hour


def _parse_time_range(text: str, event_date: date) -> tuple[datetime | None, datetime | None, list[str]]:
    range_match = TIME_RANGE_RE.search(text)
    if range_match:
        start_hour = _apply_daypart(text, int(range_match.group("start_hour")))
        start_minute = int(range_match.group("start_minute") or 0)
        end_hour = _apply_daypart(text, int(range_match.group("end_hour")))
        end_minute = int(range_match.group("end_minute") or 0)
        start = datetime.combine(event_date, time(start_hour, start_minute))
        end = datetime.combine(event_date, time(end_hour, end_minute))
        if end <= start:
            end += timedelta(days=1)
        return start, end, [range_match.group(0)]

    single_match = SINGLE_TIME_RE.search(text)
    if single_match:
        hour = _apply_daypart(text, int(single_match.group("hour")))
        minute = int(single_match.group("minute") or 0)
        start = datetime.combine(event_date, time(hour, minute))
        end = start + timedelta(minutes=DEFAULT_DURATION_MINUTES)
        return start, end, [single_match.group(0)]

    return None, None, []


def _infer_calendar(text: str) -> str:
    for calendar, hints in CALENDAR_HINTS.items():
        if any(hint in text for hint in hints):
            return calendar
    return "个人计划"


def _extract_location(text: str) -> tuple[str, list[str]]:
    match = LOCATION_RE.search(text)
    if not match:
        return "", []
    return match.group("location"), [match.group(0)]


def _extract_title(text: str, consumed: list[str], location: str) -> str:
    title = text
    for fragment in consumed:
        title = title.replace(fragment, " ")
    for token in ("帮我", "安排", "添加", "新建", "创建", "日程", "提醒我", "提醒"):
        title = title.replace(token, " ")
    if location:
        title = title.replace(f"在{location}", " ")
        title = title.replace(f"地点：{location}", " ")
        title = title.replace(f"地点:{location}", " ")
    title = re.sub(r"\s+", " ", title).strip(" ，,。")
    title = title.lstrip("和跟与")
    return title


def parse_natural_language(text: str, today: date | None = None) -> dict[str, Any]:
    if not isinstance(text, str) or not text.strip():
        return _result(False, error="text must be a non-empty string.")

    base_date = today or datetime.now().date()
    event_date, consumed = _parse_date(text, base_date)
    if event_date is None:
        draft = {
            "calendar": _infer_calendar(text),
            "title": _extract_title(text, consumed, ""),
            "start": None,
            "end": None,
            "location": "",
            "notes": "",
        }
        validation = interactive_create.get_missing_fields(draft)
        return _result(True, data={"draft": draft, **validation["data"], "confidence": 0.3})

    start, end, time_consumed = _parse_time_range(text, event_date)
    location, location_consumed = _extract_location(text)
    all_consumed = consumed + time_consumed + location_consumed
    title = _extract_title(text, all_consumed, location)
    draft = {
        "calendar": _infer_calendar(text),
        "title": title,
        "start": start.isoformat(timespec="minutes") if start else None,
        "end": end.isoformat(timespec="minutes") if end else None,
        "location": location,
        "notes": "",
    }
    validation = interactive_create.get_missing_fields(draft)
    confidence = 0.85 if not validation["data"]["missing_fields"] else 0.55
    return _result(True, data={"draft": draft, **validation["data"], "confidence": confidence})


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Parse natural-language event text into a draft.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    parse = subparsers.add_parser("parse", help="Parse text into a create-event draft.")
    parse.add_argument("text")
    parse.add_argument("--today", help="Test-only base date, e.g. 2026-04-24.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "parse":
        today = date.fromisoformat(args.today) if args.today else None
        result = parse_natural_language(args.text, today=today)
    else:
        raise AssertionError(args.command)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
