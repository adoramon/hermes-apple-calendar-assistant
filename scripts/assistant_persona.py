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


def _schedule_error_note(errors: list[dict[str, Any]] | None) -> list[str]:
    if not errors:
        return []
    calendars = [clean_text(item.get("calendar")) for item in errors if clean_text(item.get("calendar"))]
    if not calendars:
        return ["有部分日历暂时没读成功，我没有把它们算进来。"]
    return [f"有部分日历暂时没读成功：{'、'.join(calendars)}。"]


def _schedule_item_line(event: dict[str, Any]) -> str:
    start = parse_datetime(event.get("start"))
    time_text = f"{start:%H:%M}" if start else format_day_time(event.get("start"))
    title = clean_text(event.get("title")) or "未命名日程"
    location = clean_text(event.get("location"))
    if location:
        return f"{time_text}  {title}（{location}）"
    return f"{time_text}  {title}"


def _trip_short_line(trip: dict[str, Any]) -> str:
    start = _format_trip_date(trip.get("start_date"))
    end = _format_trip_date(trip.get("end_date"))
    destination = clean_text(trip.get("destination_city")) or "出行"
    title = clean_text(trip.get("title")) or f"{destination}行程"
    status = clean_text(trip.get("planning_status"))
    suffix = f"｜{status}" if status else ""
    return f"{start} - {end}  {title}{suffix}"


def format_today_schedule(
    events: list[dict[str, Any]],
    trips: list[dict[str, Any]] | None = None,
    errors: list[dict[str, Any]] | None = None,
) -> str:
    """Format today's schedule query."""
    trips = trips or []
    lines = ["高先生，今天我帮您看了一下安排 🌤️", ""]
    if events:
        lines.extend(_schedule_item_line(event) for event in events)
    else:
        lines.append("今天暂时没有查到明确日程。")
    if trips:
        lines.extend(["", "另外，今天相关出行："])
        lines.extend(f"- {_trip_short_line(trip)}" for trip in trips)
    else:
        lines.extend(["", "另外，今天没有新的出差安排。"])
    lines.extend(_schedule_error_note(errors))
    return "\n".join(lines)


def format_tomorrow_schedule(
    events: list[dict[str, Any]],
    trips: list[dict[str, Any]] | None = None,
    errors: list[dict[str, Any]] | None = None,
) -> str:
    """Format tomorrow's schedule query."""
    trips = trips or []
    lines = ["高先生，明天我帮您看了一下安排 🌤️", ""]
    if events:
        lines.extend(_schedule_item_line(event) for event in events)
    else:
        lines.append("明天暂时没有查到明确日程。")
    if trips:
        lines.extend(["", "明天相关出行："])
        lines.extend(f"- {_trip_short_line(trip)}" for trip in trips)
    else:
        lines.extend(["", "另外，明天没有新的出差安排。"])
    if events:
        lines.extend(["", "我建议您按第一场安排倒推出门时间，会更从容。"])
    lines.extend(_schedule_error_note(errors))
    return "\n".join(lines)


def _trip_summary_lines(trip: dict[str, Any]) -> list[str]:
    lines = [_trip_short_line(trip)]
    linked = trip.get("linked_flights") if isinstance(trip.get("linked_flights"), dict) else {}
    outbound = linked.get("outbound")
    return_flight = linked.get("return")
    if isinstance(outbound, dict):
        lines.append(f"  去程航班已关联飞行计划：{clean_text(outbound.get('flight_no'))}")
    for order in trip.get("orders", []):
        if not isinstance(order, dict) or order.get("confirmation_status") == "date_conflict":
            continue
        fields = order.get("fields") if isinstance(order.get("fields"), dict) else {}
        if order.get("order_type") == "hotel":
            lines.append(f"  入住：{clean_text(fields.get('hotel_name')) or '酒店'}")
        if order.get("order_type") == "train":
            lines.append(f"  高铁：{clean_text(fields.get('train_no'))} {clean_text(fields.get('departure_station'))} → {clean_text(fields.get('arrival_station'))}")
    for event in trip.get("events", []):
        if not isinstance(event, dict):
            continue
        if clean_text(event.get("event_type")) == "meeting_placeholder":
            location = clean_text(event.get("location")) or "待补地点"
            lines.append(f"  客户拜访：{location}")
    if isinstance(return_flight, dict):
        lines.append(f"  返程航班已关联飞行计划：{clean_text(return_flight.get('flight_no'))}")
    missing = format_trip_missing_items(trip)
    if missing != "暂无明显待确认事项。":
        lines.append("  待确认：" + "；".join(line.lstrip("- ") for line in missing.splitlines()))
    return lines


def format_trip_summary(
    trips: list[dict[str, Any]],
    query_text: str = "",
    errors: list[dict[str, Any]] | None = None,
) -> str:
    """Format Trip-oriented schedule query."""
    city = ""
    for candidate in ("北京", "上海", "广州", "深圳", "杭州", "南京", "长沙", "成都", "重庆", "西安", "厦门", "香港", "东京"):
        if candidate in query_text:
            city = candidate
            break
    title = f"高先生，{city}这趟出差目前是这样 ✈️" if city else "高先生，我帮您把出行安排过了一遍 ✈️"
    lines = [title, ""]
    if trips:
        for index, trip in enumerate(trips, start=1):
            trip_lines = _trip_summary_lines(trip)
            lines.append(f"{index}. {trip_lines[0]}")
            lines.extend(trip_lines[1:])
            if index != len(trips):
                lines.append("")
        lines.extend(["", "整体我会继续帮您盯着订单和时间。"])
    else:
        lines.append("暂时没有查到匹配的出差 Trip。")
    lines.extend(_schedule_error_note(errors))
    return "\n".join(lines)


def format_week_schedule(
    events: list[dict[str, Any]],
    trips: list[dict[str, Any]] | None = None,
    query_text: str = "",
    errors: list[dict[str, Any]] | None = None,
) -> str:
    """Format week/range schedule query."""
    trips = trips or []
    heading = "高先生，这段时间的行程我帮您汇总了一下 📅"
    if "本周" in query_text or "这周" in query_text:
        heading = "高先生，本周行程我帮您汇总了一下 📅"
    elif "下周" in query_text:
        heading = "高先生，下周行程我帮您汇总了一下 📅"
    elif "这个月" in query_text or "本月" in query_text:
        heading = "高先生，这个月的出差和日程我帮您看了一下 📅"
    lines = [heading, ""]
    if events:
        lines.append("日程：")
        lines.extend(f"- {_schedule_item_line(event)}" for event in events)
    else:
        lines.append("暂时没有查到明确日程。")
    if trips:
        lines.extend(["", "出行："])
        lines.extend(f"- {_trip_short_line(trip)}" for trip in trips)
    lines.extend(_schedule_error_note(errors))
    return "\n".join(lines)


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
    status = clean_text(event.get("confirmation_status"))
    prefix = ""
    if status == "confirmed":
        prefix = "✅ "
    elif status == "linked_readonly":
        prefix = "🔗 "
    elif status == "date_conflict":
        prefix = "⚠️ "
    elif status == "planned" or str(event.get("event_type") or "").endswith("_placeholder"):
        prefix = "⏳ "
    lines = [f"{prefix}{icon} {format_time_range(event.get('start'), event.get('end'))}"]
    if title:
        lines.append(f"   {title}")
    location = clean_text(event.get("location"))
    if location:
        lines.append(f"   📍 {location}")
    return lines


def _trip_conflict_lines(trip: dict[str, Any]) -> list[str]:
    conflicts = [
        order
        for order in trip.get("orders", [])
        if isinstance(order, dict) and order.get("confirmation_status") == "date_conflict"
    ]
    if not conflicts:
        return []
    lines = ["⚠️ 日期冲突待确认："]
    for order in conflicts:
        fields = order.get("fields") if isinstance(order.get("fields"), dict) else {}
        if order.get("order_type") == "hotel":
            name = clean_text(fields.get("hotel_name")) or "酒店订单"
            checkin = clean_text(fields.get("checkin_date"))
            checkout = clean_text(fields.get("checkout_date"))
            lines.append(f"- 酒店：{name}，入住 {checkin}，离店 {checkout}")
        elif order.get("order_type") == "train":
            train_no = clean_text(fields.get("train_no")) or "高铁订单"
            route = f"{clean_text(fields.get('departure_station'))} → {clean_text(fields.get('arrival_station'))}"
            lines.append(f"- 高铁：{train_no} {route}")
        else:
            lines.append(f"- {clean_text(order.get('order_type')) or '订单'}")
    lines.append("这些真实订单暂未替换计划占位，等您确认后再合并，避免误覆盖。")
    return lines


def format_trip_placeholder_replaced(trip: dict[str, Any], order: dict[str, Any]) -> str:
    """Format a successful real-order replacement notice."""
    fields = order.get("fields") if isinstance(order.get("fields"), dict) else {}
    if order.get("order_type") == "hotel":
        return "\n".join(
            [
                "高先生，我已经把酒店订单替换进这次出行了 🏨",
                "",
                f"✅ 酒店：{clean_text(fields.get('hotel_name'))}",
                f"🛏️ 入住：{clean_text(fields.get('checkin_date'))} {clean_text(fields.get('checkin_time'))}".strip(),
                f"🚪 离店：{clean_text(fields.get('checkout_date'))} {clean_text(fields.get('checkout_time'))}".strip(),
                "",
                "原来的“住宿计划”已被替换，不会重复写入。",
            ]
        )
    if order.get("order_type") == "train":
        return "\n".join(
            [
                "高先生，我已经把高铁订单替换进这次出行了 🚄",
                "",
                f"✅ 车次：{clean_text(fields.get('train_no'))}",
                f"📍 {clean_text(fields.get('departure_station'))} → {clean_text(fields.get('arrival_station'))}",
                f"🕐 {format_time_range(fields.get('departure_datetime'), fields.get('arrival_datetime'))}",
                "",
                "对应的去程/返程计划占位已被替换，不会重复写入。",
            ]
        )
    return "高先生，我已经把真实订单合并进这次出行草稿了。"


def format_trip_date_conflict(trip: dict[str, Any]) -> str:
    """Format date conflict notice for real-order merge."""
    lines = ["高先生，这张真实订单和当前 Trip 日期不太一致，我先不直接覆盖。", ""]
    lines.extend(_trip_conflict_lines(trip))
    lines.extend(["", "您确认这是同一次出行后，我再帮您合并。"])
    return "\n".join(lines)


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
    conflict_lines = _trip_conflict_lines(trip)
    if conflict_lines:
        lines.extend(conflict_lines)
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


def _briefing_date(value: Any) -> str:
    parsed = parse_datetime(value)
    if parsed is None and isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value + "T00:00:00")
        except ValueError:
            parsed = None
    if parsed is None:
        return clean_text(value)
    return f"{parsed.month}月{parsed.day}日"


def _briefing_flight_lines(flight: dict[str, Any], label: str) -> list[str]:
    flight_no = clean_text(flight.get("flight_no"))
    dep = clean_text(flight.get("departure_airport")) or clean_text(flight.get("departure_city"))
    dep_terminal = clean_text(flight.get("departure_terminal"))
    arr = clean_text(flight.get("arrival_airport")) or clean_text(flight.get("arrival_city"))
    arr_terminal = clean_text(flight.get("arrival_terminal"))
    route = f"{dep}{dep_terminal} → {arr}{arr_terminal}".strip(" →")
    detail = f"{flight_no} {route}".strip()
    lines = [f"✈️ {label}", f"   {detail}" if detail else "   航班待确认"]
    time_text = format_time_range(flight.get("start"), flight.get("end"))
    if time_text:
        lines.append(f"   {time_text}")
    lines.append("   来源：飞行计划")
    return lines


def _briefing_train_lines(order: dict[str, Any], label: str) -> list[str]:
    fields = order.get("fields") if isinstance(order.get("fields"), dict) else {}
    train_no = clean_text(fields.get("train_no"))
    dep = clean_text(fields.get("departure_station"))
    arr = clean_text(fields.get("arrival_station"))
    detail = f"{train_no} {dep} → {arr}".strip()
    lines = [f"🚄 {label}", f"   {detail}" if detail else "   高铁待确认"]
    time_text = format_time_range(fields.get("departure_datetime"), fields.get("arrival_datetime"))
    if time_text:
        lines.append(f"   {time_text}")
    return lines


def _briefing_hotel_lines(order: dict[str, Any]) -> list[str]:
    fields = order.get("fields") if isinstance(order.get("fields"), dict) else {}
    lines = ["🏨 酒店", f"   {clean_text(fields.get('hotel_name')) or '酒店待确认'}"]
    checkin = f"{_briefing_date(fields.get('checkin_date'))} {clean_text(fields.get('checkin_time'))}".strip()
    checkout = f"{_briefing_date(fields.get('checkout_date'))} {clean_text(fields.get('checkout_time') or '12:00')}".strip()
    if checkin:
        lines.append(f"   入住：{checkin}")
    if checkout:
        lines.append(f"   离店：{checkout}")
    address = clean_text(fields.get("address"))
    if address:
        lines.append(f"   地址：{address}")
    return lines


def _briefing_event_lines(event: dict[str, Any]) -> list[str]:
    event_type = clean_text(event.get("event_type"))
    if event_type == "meeting_placeholder":
        label = "🤝 客户拜访"
    elif event_type == "hotel_placeholder":
        label = "🏨 住宿计划"
    elif event_type == "outbound_placeholder":
        label = "🚄/✈️ 去程计划"
    elif event_type == "return_placeholder":
        label = "🚄/✈️ 返程计划"
    else:
        label = f"{_trip_event_icon(event)} {clean_text(event.get('title')) or '行程'}"
    lines = [label]
    time_text = format_time_range(event.get("start"), event.get("end"))
    if time_text:
        lines.append(f"   {time_text}")
    location = clean_text(event.get("location"))
    lines.append(f"   {location or '地点待确认'}")
    return lines


def _trip_briefing_sections(trip: dict[str, Any]) -> list[list[str]]:
    sections: list[list[str]] = []
    linked = trip.get("linked_flights") if isinstance(trip.get("linked_flights"), dict) else {}
    outbound_flight = linked.get("outbound")
    return_flight = linked.get("return")
    if isinstance(outbound_flight, dict):
        sections.append(_briefing_flight_lines(outbound_flight, "去程"))

    train_orders = [
        order
        for order in trip.get("orders", [])
        if isinstance(order, dict)
        and order.get("order_type") == "train"
        and order.get("confirmation_status") != "date_conflict"
    ]
    hotel_orders = [
        order
        for order in trip.get("orders", [])
        if isinstance(order, dict)
        and order.get("order_type") == "hotel"
        and order.get("confirmation_status") != "date_conflict"
    ]
    for order in train_orders:
        replaced = clean_text(order.get("replaced_placeholder_id"))
        if "outbound" in replaced:
            sections.append(_briefing_train_lines(order, "去程"))
    if hotel_orders:
        sections.append(_briefing_hotel_lines(hotel_orders[0]))

    for event in trip.get("events", []):
        if not isinstance(event, dict):
            continue
        event_type = clean_text(event.get("event_type"))
        if event.get("confirmation_status") == "confirmed" and event.get("replaced_by_order_hash"):
            continue
        if event_type in {"meeting_placeholder", "leisure_placeholder"}:
            sections.append(_briefing_event_lines(event))

    if isinstance(return_flight, dict):
        sections.append(_briefing_flight_lines(return_flight, "返程"))
    for order in train_orders:
        replaced = clean_text(order.get("replaced_placeholder_id"))
        if "return" in replaced:
            sections.append(_briefing_train_lines(order, "返程"))

    for event in trip.get("events", []):
        if not isinstance(event, dict):
            continue
        event_type = clean_text(event.get("event_type"))
        if event.get("confirmation_status") == "confirmed" and event.get("replaced_by_order_hash"):
            continue
        if event_type in {"outbound_placeholder", "return_placeholder", "hotel_placeholder"}:
            has_hotel = event_type == "hotel_placeholder" and bool(hotel_orders)
            has_outbound = event_type == "outbound_placeholder" and (
                isinstance(outbound_flight, dict)
                or any("outbound" in clean_text(order.get("replaced_placeholder_id")) for order in train_orders)
            )
            has_return = event_type == "return_placeholder" and (
                isinstance(return_flight, dict)
                or any("return" in clean_text(order.get("replaced_placeholder_id")) for order in train_orders)
            )
            if not (has_hotel or has_outbound or has_return):
                sections.append(_briefing_event_lines(event))
    return sections


def format_trip_missing_items(trip: dict[str, Any]) -> str:
    """Format pending items for a Trip briefing."""
    items: list[str] = []
    linked = trip.get("linked_flights") if isinstance(trip.get("linked_flights"), dict) else {}
    orders = [order for order in trip.get("orders", []) if isinstance(order, dict)]
    events = [event for event in trip.get("events", []) if isinstance(event, dict)]
    if trip.get("needs_flight", True) and not isinstance(linked.get("outbound"), dict):
        has_outbound_train = any("outbound" in clean_text(order.get("replaced_placeholder_id")) for order in orders)
        if not has_outbound_train:
            items.append("去程交通还没确认到真实订单或飞行计划。")
    if trip.get("needs_flight", True) and not isinstance(linked.get("return"), dict):
        has_return_train = any("return" in clean_text(order.get("replaced_placeholder_id")) for order in orders)
        if not has_return_train:
            items.append("返程交通还没确认到真实订单或飞行计划。")
    has_hotel = any(order.get("order_type") == "hotel" and order.get("confirmation_status") != "date_conflict" for order in orders)
    if trip.get("needs_hotel", False) and not has_hotel:
        items.append("酒店订单还没确认。")
    for event in events:
        if clean_text(event.get("event_type")) == "meeting_placeholder" and not clean_text(event.get("location")):
            items.append("客户拜访地点还没补充。")
    for order in orders:
        if order.get("order_type") == "hotel":
            fields = order.get("fields") if isinstance(order.get("fields"), dict) else {}
            if not clean_text(fields.get("phone")):
                items.append("酒店电话未记录。")
        if order.get("confirmation_status") == "date_conflict":
            items.append("有订单日期冲突待确认。")
    if not items:
        return "暂无明显待确认事项。"
    return "\n".join(f"- {item}" for item in dict.fromkeys(items))


def format_trip_departure_suggestion(trip: dict[str, Any]) -> str:
    """Format practical pre-departure suggestions."""
    suggestions = ["提前检查身份证件和充电器。"]
    if trip.get("flight_link_status") in {"outbound_linked", "fully_linked"}:
        suggestions.append("出发前看一眼航旅纵横，确认登机口和航班状态。")
    else:
        suggestions.append("出发前确认交通订单和出发站/机场。")
    if trip.get("needs_hotel", False):
        suggestions.append("酒店入住信息可以提前截屏备用。")
    return "\n".join(f"- {item}" for item in suggestions)


def format_trip_briefing(trip: dict[str, Any], briefing_type: str) -> str:
    """Format a pre-trip briefing message."""
    destination = clean_text(trip.get("destination_city")) or "这次"
    purpose = clean_text(trip.get("purpose")) or "出行安排"
    start = _briefing_date(trip.get("start_date"))
    end = _briefing_date(trip.get("end_date"))
    heading = {
        "pre_trip_48h": f"高先生，接下来这趟{destination}出行我先帮您过一遍 ✈️",
        "pre_trip_24h": f"高先生，明天这趟{destination}出差我帮您整理好了 ✈️",
        "travel_day_morning": f"高先生，今天这趟{destination}出行我帮您再确认一下 ✈️",
    }.get(briefing_type, f"高先生，这趟{destination}出行我帮您整理好了 ✈️")
    lines = [
        heading,
        "",
        f"📍 目的地：{destination}",
        f"📅 时间：{start} - {end}" if end else f"📅 时间：{start}",
        f"🎯 目的：{purpose}",
        "",
        "行程安排：",
    ]
    sections = _trip_briefing_sections(trip)
    if sections:
        for index, section in enumerate(sections, start=1):
            lines.append(f"{index}. {section[0]}")
            lines.extend(section[1:])
            if index != len(sections):
                lines.append("")
    else:
        lines.append("暂无可整理的确认行程，我会继续留意订单和计划草稿。")
    lines.extend(["", "我这边还看到这些待确认事项：", format_trip_missing_items(trip)])
    lines.extend(["", "出发前建议：", format_trip_departure_suggestion(trip)])
    lines.extend(["", "我会继续替您盯着时间 ⏰"])
    return "\n".join(lines)


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
