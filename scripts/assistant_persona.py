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


def _format_trip_date(value: Any) -> str:
    parsed = parse_datetime(value)
    if parsed is None:
        text = clean_text(value)
        try:
            parsed = datetime.fromisoformat(text + "T00:00:00")
        except ValueError:
            return text
    return f"{parsed.month}月{parsed.day}日"


def _trip_event_icon(event: dict[str, Any]) -> str:
    event_type = clean_text(event.get("event_type"))
    if event_type == "flight":
        return "✈️"
    if event_type == "train":
        return "🚄"
    if event_type == "hotel":
        return "🏨"
    if event_type == "outbound_placeholder":
        return "✈️"
    if event_type == "hotel_placeholder":
        return "🏨"
    if event_type == "meeting_placeholder":
        return "🤝"
    if event_type == "leisure_placeholder":
        return "🧳"
    if event_type == "return_placeholder":
        return "🚄"
    return "📌"


def _format_trip_event_line(event: dict[str, Any]) -> list[str]:
    icon = _trip_event_icon(event)
    title = clean_text(event.get("title"))
    lines = [f"{icon} {format_time_range(event.get('start'), event.get('end'))}"]
    if title:
        lines.append(f"   {title}")
    location = clean_text(event.get("location"))
    if location:
        lines.append(f"   📍 {location}")
    return lines


def format_trip_draft(trip: dict[str, Any]) -> str:
    """Format an aggregated business travel draft."""
    events = [event for event in trip.get("events", []) if isinstance(event, dict)]
    destination = clean_text(trip.get("destination_city")) or "这次"
    start = _format_trip_date(trip.get("start_date"))
    end = _format_trip_date(trip.get("end_date"))
    lines = [
        "高先生，我把这几条订单整理成一次完整出行了 ✈️🏨",
        "",
        f"📍 目的地：{destination}",
        f"📅 时间：{start} - {end}",
        "",
        "行程如下：",
        "",
    ]
    if events:
        for index, event in enumerate(events, start=1):
            event_lines = _format_trip_event_line(event)
            lines.append(f"{index}. {event_lines[0]}")
            lines.extend(event_lines[1:])
            if index != len(events):
                lines.append("")
    else:
        lines.append("我还没整理出可写入的行程事件，需要再看一下订单文字。")

    missing = set(trip.get("missing_fields") or [])
    if "calendar" in missing or not trip.get("calendar"):
        suggested = clean_text(trip.get("suggested_calendar"))
        lines.extend(
            [
                "",
                "请您确认写入哪个日历：",
                "- 商务计划",
                "- 个人计划",
                "- 夫妻计划",
            ]
        )
        if suggested:
            lines.extend(["", f"我这边建议先放到「{suggested}」，但最终听您的。"])
        lines.extend(["", "确认后，我一次性帮您写入 Apple Calendar。"])
    else:
        lines.extend(["", f"📅 日历：{clean_text(trip.get('calendar'))}", "您确认后，我一次性帮您写入 Apple Calendar。"])
    return "\n".join(lines)


def format_trip_confirmed(trip: dict[str, Any], results: list[dict[str, Any]]) -> str:
    """Format confirmed trip write results."""
    created = [item for item in results if item.get("status") == "created"]
    skipped = [item for item in results if item.get("status") == "skipped_duplicate"]
    failed = [item for item in results if item.get("status") == "failed"]
    lines = ["高先生，这次出行我已经替您整理进 Apple Calendar 了 ✨", ""]
    if created:
        lines.append(f"已新增 {len(created)} 条日程。")
    if skipped:
        lines.append(f"有 {len(skipped)} 条之前已经写过，我就没重复创建。")
    if failed:
        lines.append(f"有 {len(failed)} 条没写成功，我先帮您标出来。")
    calendar = clean_text(trip.get("calendar"))
    if calendar:
        lines.append(f"📅 日历：{calendar}")
    lines.extend(["", "我会帮您把交通和酒店时间一起盯住。"])
    return "\n".join(lines)


def format_trip_missing_fields(trip: dict[str, Any]) -> str:
    """Format missing field prompt for trip drafts."""
    missing = set(trip.get("missing_fields") or [])
    if "calendar" in missing or not trip.get("calendar"):
        return "\n".join(
            [
                "高先生，这次出行草稿我已经整理好啦。",
                "",
                "写入前您选一下日历：商务计划、个人计划，还是夫妻计划？",
            ]
        )
    return "高先生，这次出行草稿还差一点信息，我再帮您补齐。"


def format_trip_duplicate_warning(trip: dict[str, Any]) -> str:
    """Format duplicate warning for trip writes."""
    return "\n".join(
        [
            "高先生，这次出行里有日程之前已经写过了。",
            "",
            "我不会重复创建，也不会覆盖旧日程，稳一点更好。✨",
        ]
    )


def _readonly_flight_line(flight: dict[str, Any], label: str) -> list[str]:
    flight_no = clean_text(flight.get("flight_no"))
    dep = clean_text(flight.get("departure_airport"))
    dep_terminal = clean_text(flight.get("departure_terminal"))
    arr = clean_text(flight.get("arrival_airport"))
    arr_terminal = clean_text(flight.get("arrival_terminal"))
    route = f"{dep}{dep_terminal} → {arr}{arr_terminal}".strip(" →")
    heading = f"✈️ {label}：{flight_no} {route}".strip()
    lines = [heading]
    time_text = format_time_range(flight.get("start"), flight.get("end"))
    if time_text:
        lines.append(f"   🕐 {time_text}")
    location = clean_text(flight.get("location"))
    if location:
        lines.append(f"   📍 {location}")
    lines.append("   来源：飞行计划，只读，不重复写入")
    return lines


def _linked_flight_sections(trip: dict[str, Any]) -> list[str]:
    linked = trip.get("linked_flights") if isinstance(trip.get("linked_flights"), dict) else {}
    lines: list[str] = []
    outbound = linked.get("outbound")
    return_flight = linked.get("return")
    if isinstance(outbound, dict) or isinstance(return_flight, dict):
        lines.append("已关联到「飞行计划」：")
        if isinstance(outbound, dict):
            lines.extend(_readonly_flight_line(outbound, "去程"))
        if isinstance(return_flight, dict):
            if isinstance(outbound, dict):
                lines.append("")
            lines.extend(_readonly_flight_line(return_flight, "返程"))
    return lines


def format_trip_with_readonly_flights(trip: dict[str, Any]) -> str:
    """Format a Trip draft with linked read-only flight calendar events."""
    events = [event for event in trip.get("events", []) if isinstance(event, dict)]
    destination = clean_text(trip.get("destination_city")) or "这次"
    start = _format_trip_date(trip.get("start_date"))
    end = _format_trip_date(trip.get("end_date"))
    lines = [
        f"高先生，我把这次{destination}出行整理好了 ✈️🏨",
        "",
        f"📍 目的地：{destination}",
        f"📅 时间：{start} - {end}",
        "",
    ]
    flight_lines = _linked_flight_sections(trip)
    if flight_lines:
        lines.extend(flight_lines)
        lines.append("")

    lines.append("待写入 Apple Calendar：")
    if events:
        for index, event in enumerate(events, start=1):
            event_lines = _format_trip_event_line(event)
            lines.append(f"{index}. {event_lines[0]}")
            lines.extend(event_lines[1:])
            if index != len(events):
                lines.append("")
    else:
        lines.append("暂无需要写入商务/个人/夫妻日历的非航班日程。")

    missing = set(trip.get("missing_fields") or [])
    if "calendar" in missing or not trip.get("calendar"):
        suggested = clean_text(trip.get("suggested_calendar"))
        lines.extend(["", "请您确认写入哪个日历：", "- 商务计划", "- 个人计划", "- 夫妻计划"])
        if suggested:
            lines.extend(["", f"我这边建议先放到「{suggested}」，但最终听您的。"])
    else:
        lines.extend(["", f"请确认是否写入「{clean_text(trip.get('calendar'))}」。"])
    return "\n".join(lines)


def format_trip_flight_linked(trip: dict[str, Any]) -> str:
    """Format a successful read-only flight link message."""
    destination = clean_text(trip.get("destination_city")) or "这次出行"
    lines = [
        "高先生，我看这趟航班已经在「飞行计划」里了，我就不重复写入啦 ✈️",
        "",
        f"我已经把它关联到这次{destination}出行：",
        "",
    ]
    sections = _linked_flight_sections(trip)
    if sections:
        lines.extend(sections[1:] if sections[0].startswith("已关联") else sections)
    lines.extend(["", "接下来我只会把酒店、客户拜访和高铁安排写入您选择的日历。"])
    return "\n".join(lines)


def format_trip_flight_pending_sync(trip: dict[str, Any]) -> str:
    """Format no matching 飞行计划 flight yet."""
    destination = clean_text(trip.get("destination_city")) or "这次出行"
    return "\n".join(
        [
            f"高先生，我还没有在「飞行计划」里找到这次{destination}出行对应的航班。",
            "",
            "机票仍由航旅纵横统一同步到「飞行计划」，我不会重复创建航班日程。",
            "等航旅纵横同步后，我再帮您把航班关联进 Trip。",
        ]
    )


def _travel_label_date(value: Any) -> str:
    parsed = parse_datetime(value)
    if parsed is None and isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value + "T00:00:00")
        except ValueError:
            parsed = None
    if parsed is None:
        return clean_text(value)
    today = datetime.now().date()
    current_monday = today - timedelta(days=today.weekday())
    next_monday = current_monday + timedelta(days=7)
    if parsed.month != today.month or parsed.year != today.year:
        return f"{parsed.month}月{parsed.day}日"
    if parsed.date() == today:
        return "今天"
    if parsed.date() == today + timedelta(days=1):
        return "明天"
    if current_monday <= parsed.date() <= current_monday + timedelta(days=6):
        return f"本周{['一', '二', '三', '四', '五', '六', '日'][parsed.weekday()]}"
    if next_monday <= parsed.date() <= next_monday + timedelta(days=6):
        return f"下周{['一', '二', '三', '四', '五', '六', '日'][parsed.weekday()]}"
    return f"{parsed.month}月{parsed.day}日"


def _travel_event_summary(event: dict[str, Any]) -> tuple[str, str]:
    event_type = clean_text(event.get("event_type"))
    start = parse_datetime(event.get("start"))
    end = parse_datetime(event.get("end"))
    start_text = _travel_label_date(event.get("start"))
    if start and end and start.date() == end.date():
        when = f"{start_text}{'上午' if start.hour < 12 else '下午'}"
    else:
        when = start_text
    if event_type == "outbound_placeholder":
        return "🚄/✈️ 去程计划", f"{when}：{clean_text(event.get('title')).replace('去程｜', '')}"
    if event_type == "meeting_placeholder":
        return "🤝 客户拜访", f"{when}：{clean_text(event.get('location'))}客户拜访"
    if event_type == "hotel_placeholder":
        return "🏨 住宿计划", f"{start_text}晚：{clean_text(event.get('location'))}住宿"
    if event_type == "return_placeholder":
        return "🚄/✈️ 返程计划", f"{when}：{clean_text(event.get('title')).replace('返程｜', '')}"
    if event_type == "leisure_placeholder":
        return "🧳 出行安排", f"{when}：{clean_text(event.get('location'))}自由安排"
    return clean_text(event.get("title")), when


def format_travel_intent_draft(plan: dict[str, Any]) -> str:
    """Format a one-sentence travel intent planning draft."""
    destination = clean_text(plan.get("destination_city")) or "这次出行"
    purpose = clean_text(plan.get("purpose")) or "出行安排"
    calendar = clean_text(plan.get("calendar") or plan.get("suggested_calendar"))
    assumptions = [clean_text(item) for item in plan.get("assumptions", []) if clean_text(item)]
    start = _travel_label_date(plan.get("start_date"))
    end = _travel_label_date(plan.get("end_date"))
    title = "高先生，我先按您的意思整理了一个出行草稿 ✈️"
    if destination and destination != "这次出行":
        title = f"高先生，我先按您的意思整理了一个{destination}出行草稿 ✈️"
    lines = [
        title,
        "",
        f"📍 目的地：{destination}",
        f"📅 时间：{start} - {end}" if end else f"📅 时间：{start}",
        f"🎯 目的：{purpose}",
    ]
    if calendar:
        lines.append(f"📅 建议写入：{calendar}")
    lines.extend(["", "我先这样规划：", ""])
    events = [event for event in plan.get("events", []) if isinstance(event, dict)]
    for index, event in enumerate(events, start=1):
        heading, detail = _travel_event_summary(event)
        lines.append(f"{index}. {heading}")
        lines.append(f"   {detail}")
        if index != len(events):
            lines.append("")
    if assumptions:
        lines.extend(["", "当前默认："])
        for item in assumptions:
            lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "这些是计划草稿，还不是实际订单。",
            "您确认后，我先写入 Apple Calendar，后面等您发机票/酒店订单截图，我再帮您替换成准确行程。",
        ]
    )
    return "\n".join(lines)


def format_travel_intent_missing_fields(plan: dict[str, Any]) -> str:
    """Format missing field prompts for one-sentence travel planning."""
    missing = set(plan.get("missing_fields") or [])
    lines = ["高先生，这次出行我先帮您整理成计划草稿了。", "", "写入前我还需要您补几项信息："]
    if "destination_city" in missing:
        lines.append("- 目的地是哪里？")
    if "start_date" in missing:
        lines.append("- 您打算哪天出发？")
    if "duration_days" in missing:
        lines.append("- 这次大概几天？如果当天回也可以直接告诉我。")
    lines.extend(
        [
            "",
            "这是计划草稿，不代表真实订票或订房。",
            "等信息补齐后，我再帮您整理成可确认写入的 Apple Calendar 草稿。",
        ]
    )
    return "\n".join(lines)


def format_travel_plan_confirmed(plan: dict[str, Any], results: list[dict[str, Any]]) -> str:
    """Format confirmed one-sentence travel planning results."""
    created = [item for item in results if item.get("status") == "created"]
    failed = [item for item in results if item.get("status") == "failed"]
    destination = clean_text(plan.get("destination_city")) or "这次出行"
    calendar = clean_text(plan.get("calendar"))
    lines = [f"高先生，{destination}这次计划草稿我已经先写进 Apple Calendar 了 ✨", ""]
    if created:
        lines.append(f"已新增 {len(created)} 条计划草稿日程。")
    if failed:
        lines.append(f"有 {len(failed)} 条没写成功，我稍后可以继续帮您检查。")
    if calendar:
        lines.append(f"📅 日历：{calendar}")
    lines.extend(
        [
            "",
            "这些还是计划草稿，不代表实际机票或酒店订单。",
            "后面您把订单截图发我，我再帮您替换成准确行程，不会去写飞行计划，也不会写 Apple Reminders。",
        ]
    )
    return "\n".join(lines)
