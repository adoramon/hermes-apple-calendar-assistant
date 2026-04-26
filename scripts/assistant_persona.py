"""Persona wording system for Mr. Gao's Apple Calendar assistant."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any


APPLE_DATETIME_RE = re.compile(
    r"(?P<year>\d{4})年(?P<month>\d{1,2})月(?P<day>\d{1,2})日.*?"
    r"(?P<hour>\d{1,2}):(?P<minute>\d{2}):(?P<second>\d{2})"
)


def clean_text(value: Any) -> str:
    """Normalize user-facing text without changing business data."""
    if not isinstance(value, str):
        return str(value or "").strip()
    text = " ".join(value.split())
    return "" if text.lower() in {"missing value", "none", "null"} else text


def parse_datetime(value: Any) -> datetime | None:
    """Parse ISO or Calendar.app datetime text."""
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        parsed = None
    if parsed is not None:
        if parsed.tzinfo is not None:
            return parsed.astimezone().replace(tzinfo=None)
        return parsed

    match = APPLE_DATETIME_RE.search(text)
    if not match:
        return None
    return datetime(
        int(match.group("year")),
        int(match.group("month")),
        int(match.group("day")),
        int(match.group("hour")),
        int(match.group("minute")),
        int(match.group("second")),
    )


def format_day_time(value: Any) -> str:
    """Format a datetime as 今天/明天 HH:MM when possible."""
    parsed = parse_datetime(value)
    if parsed is None:
        return clean_text(value)
    today = datetime.now().date()
    if parsed.date() == today:
        prefix = "今天"
    elif parsed.date() == today + timedelta(days=1):
        prefix = "明天"
    else:
        prefix = parsed.strftime("%m月%d日")
    return f"{prefix} {parsed:%H:%M}"


def format_time_range(start: Any, end: Any) -> str:
    """Format a compact event time range."""
    start_dt = parse_datetime(start)
    end_dt = parse_datetime(end)
    if start_dt and end_dt:
        start_text = format_day_time(start)
        if start_dt.date() == end_dt.date():
            return f"{start_text} - {end_dt:%H:%M}"
        return f"{start_text} - {format_day_time(end)}"
    start_text = clean_text(start)
    end_text = clean_text(end)
    if start_text and end_text:
        return f"{start_text} - {end_text}"
    return start_text or end_text


def _event_lines(event: dict[str, Any], include_calendar: bool = False) -> list[str]:
    lines = [f"📌 {clean_text(event.get('title'))}"]
    time_text = format_time_range(event.get("start"), event.get("end"))
    if time_text:
        lines.append(f"🕐 {time_text}")
    location = clean_text(event.get("location"))
    if location:
        lines.append(f"📍 {location}")
    calendar = clean_text(event.get("calendar"))
    if include_calendar and calendar:
        lines.append(f"📅 日历：{calendar}")
    return lines


def format_calendar_created(event: dict[str, Any]) -> str:
    """Format a successful Calendar create response."""
    lines = ["高先生，已经帮您安排好了 📅", ""]
    lines.extend(_event_lines(event))
    lines.extend(["", "我会替您盯着时间。"])
    return "\n".join(lines)


def format_calendar_updated(event: dict[str, Any], changes: dict[str, Any] | None = None) -> str:
    """Format a successful Calendar update response."""
    changes = changes or {}
    start = changes.get("new_start", event.get("start"))
    end = changes.get("new_end", event.get("end"))
    lines = ["已经帮您调整好了 ✨", "", f"📌 {clean_text(event.get('title'))}"]
    time_text = format_time_range(start, end)
    if time_text:
        lines.append(f"🕐 改为 {time_text}")
    lines.extend(["", "新的时间我已经写入 Apple Calendar。"])
    return "\n".join(lines)


def format_calendar_deleted(event: dict[str, Any]) -> str:
    """Format a successful Calendar delete response."""
    return "\n".join(
        [
            "好的，这个安排我已经替您取消了。",
            "",
            f"📌 {clean_text(event.get('title'))}",
            "🗑️ 已从 Apple Calendar 移除",
        ]
    )


def format_calendar_draft(event: dict[str, Any], conflict_check: dict[str, Any] | None = None) -> str:
    """Format a pending Calendar create/update draft."""
    if conflict_check and conflict_check.get("has_conflict"):
        return format_calendar_conflict(
            list(conflict_check.get("conflicts") or []),
            suggested_slots=list(conflict_check.get("suggested_slots") or []),
        )
    lines = ["我先帮您整理成这样，您确认后我再写入日历：", ""]
    lines.extend(_event_lines(event))
    lines.extend(["", "回复“确认”即可。"])
    return "\n".join(lines)


def format_calendar_conflict(
    conflicts: list[dict[str, Any]],
    suggested_slots: list[dict[str, Any]] | None = None,
) -> str:
    """Format a conflict notice."""
    lines = ["我帮您看了一下，这个时间段已经有安排了：", ""]
    for index, event in enumerate(conflicts, start=1):
        lines.append(f"{index}. 🕐 {format_time_range(event.get('start'), event.get('end'))}")
        lines.append(f"   📌 {clean_text(event.get('title'))}")
        if index != len(conflicts):
            lines.append("")
    suggestions = suggested_slots or []
    if suggestions:
        lines.extend(["", "可以考虑这些时间："])
        for slot in suggestions:
            lines.append(f"- {format_time_range(slot.get('start'), slot.get('end'))}")
        lines.extend(["", "您选一个，我再帮您安排。"])
    else:
        lines.extend(["", "要不要我帮您顺延一下其中一个？"])
    return "\n".join(lines)


def format_reminder_message(reminder: dict[str, Any]) -> str:
    """Format a single reminder push message."""
    offset = reminder.get("offset_minutes")
    offset_text = f"{offset} 分钟" if isinstance(offset, int) and offset > 0 else "一会儿"
    lines = [
        "高先生，提醒您一下 ⏰",
        "",
        f"您还有 {offset_text}有个安排：",
        "",
        f"📌 {clean_text(reminder.get('title'))}",
    ]
    time_text = format_day_time(reminder.get("start"))
    if time_text:
        lines.append(f"🕐 {time_text}")
    location = clean_text(reminder.get("location"))
    if location:
        lines.append(f"📍 {location}")
    lines.extend(
        [
            "",
            "您可以直接回复：",
            "- 推迟30分钟",
            "- 改到明天上午10点",
            "- 取消这个日程",
        ]
    )
    return "\n".join(lines)


def format_multi_reminder_message(reminders: list[dict[str, Any]]) -> str:
    """Format multiple reminder push messages."""
    valid = [item for item in reminders if clean_text(item.get("title"))]
    if not valid:
        return format_no_pending_reminders()
    if len(valid) == 1:
        return format_reminder_message(valid[0])

    lines = [f"高总，接下来有 {len(valid)} 个安排，我帮您盯着时间 📅", ""]
    for index, reminder in enumerate(valid, start=1):
        lines.append(f"{index}. 🕐 {format_day_time(reminder.get('start'))}")
        lines.append(f"   📌 {clean_text(reminder.get('title'))}")
        location = clean_text(reminder.get("location"))
        if location:
            lines.append(f"   📍 {location}")
        if index != len(valid):
            lines.append("")
    return "\n".join(lines)


def format_reminder_action_draft(action: dict[str, Any]) -> str:
    """Format a reminder follow-up draft."""
    event = action.get("target_event") if isinstance(action.get("target_event"), dict) else action
    proposed = action.get("proposed_change") if isinstance(action.get("proposed_change"), dict) else {}
    lines = ["我先帮您整理成这样，您确认后我再处理：", ""]
    lines.append(f"📌 {clean_text(event.get('title'))}")
    original_time = format_time_range(event.get("start"), event.get("end"))
    if original_time:
        lines.append(f"🕐 原时间：{original_time}")
    if proposed.get("new_start"):
        lines.append(f"🕐 改为：{format_time_range(proposed.get('new_start'), proposed.get('new_end'))}")
    if proposed.get("snooze_minutes"):
        lines.append(f"⏰ 延后提醒：{proposed['snooze_minutes']} 分钟")
    if proposed.get("delete_event"):
        lines.append("🗑️ 准备取消这个日程")
    lines.extend(["", "回复“确认”即可。", "已生成操作草稿，尚未修改日程。"])
    return "\n".join(lines)


def format_reminder_action_confirmed(action: dict[str, Any]) -> str:
    """Format a confirmed reminder follow-up action."""
    event = action.get("target_event") if isinstance(action.get("target_event"), dict) else action
    proposed = action.get("proposed_change") if isinstance(action.get("proposed_change"), dict) else {}
    intent = action.get("intent")
    if intent == "cancel":
        return format_calendar_deleted(event)
    if intent == "reschedule":
        return format_calendar_updated(event, {"new_start": proposed.get("new_start"), "new_end": proposed.get("new_end")})
    if intent == "snooze":
        minutes = proposed.get("snooze_minutes", 30)
        return f"高总，已经帮您记下了，{minutes} 分钟后我再提醒您。"
    if intent == "arrived":
        return "好的，我记下您已到达。"
    if intent == "disable_reminder":
        return "好的，这个安排后续我先不再提醒您。"
    return "这边已帮您处理好。"


def format_no_pending_reminders() -> str:
    """Format no pending reminder text."""
    return "高总，当前没有待发送的日程提醒。"


def format_error_friendly(error: Any, context: str | None = None) -> str:
    """Format a concise friendly error without hiding the boundary."""
    prefix = "这边刚才没处理成功"
    if context:
        prefix += f"（{context}）"
    text = clean_text(error) or "原因暂时不明确"
    return f"{prefix}，我先帮您记一下：{text}"


def format_hotel_order_draft(order: dict[str, Any], missing_fields: list[str] | None = None) -> str:
    """Format a hotel order draft without claiming Calendar writes."""
    missing = set(missing_fields or [])
    lines = ["高先生，我看这是一条酒店订单，我先帮您整理好了 📅", ""]
    hotel_name = clean_text(order.get("hotel_name"))
    if hotel_name:
        lines.append(f"🏨 酒店：{hotel_name}")
    address = clean_text(order.get("address"))
    if address:
        lines.append(f"📍 地址：{address}")
    checkin = clean_text(order.get("checkin_date"))
    if order.get("checkin_time"):
        checkin = f"{checkin} {clean_text(order.get('checkin_time'))}".strip()
    if checkin:
        lines.append(f"🛏️ 入住：{checkin}")
    checkout = clean_text(order.get("checkout_date"))
    if order.get("checkout_time"):
        checkout = f"{checkout} {clean_text(order.get('checkout_time'))}".strip()
    if checkout:
        lines.append(f"🚪 离店：{checkout}")
    guest = clean_text(order.get("guest_name"))
    if guest:
        lines.append(f"👤 入住人：{guest}")
    room_type = clean_text(order.get("room_type"))
    if room_type:
        lines.append(f"🛏️ 房型：{room_type}")

    questions = []
    if "calendar" in missing:
        questions.append("写入「个人计划」还是「夫妻计划」？")
    if "checkin_time" in missing:
        questions.append("入住当天几点记录比较合适？例如 15:00。")
    if questions:
        lines.extend(["", "写入前我还需要您确认："])
        for index, question in enumerate(questions, start=1):
            lines.append(f"{index}. {question}")
    else:
        lines.extend(["", "您确认后我再写入 Apple Calendar。"])
    return "\n".join(lines)
