"""Hermes cron bridge that renders pending outbox messages as plain text."""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timedelta
from typing import Any

try:
    from . import outbox, util
except ImportError:  # Allows running as: python3 scripts/hermes_cron_outbox_bridge.py ...
    import outbox  # type: ignore
    import util  # type: ignore


EMPTY_MODE_SILENT = "silent"
EMPTY_MODE_MESSAGE = "message"
EMPTY_MESSAGE = "当前没有待发送日历提醒。"
BRIDGE_STATUS = "sent_via_hermes_cron"
APPLE_DATETIME_RE = re.compile(
    r"(?P<year>\d{4})年(?P<month>\d{1,2})月(?P<day>\d{1,2})日.*?"
    r"(?P<hour>\d{1,2}):(?P<minute>\d{2}):(?P<second>\d{2})"
)


def _parse_created_at(value: Any) -> tuple[int, str]:
    """Return a sortable key for created_at, keeping invalid values last."""
    if not isinstance(value, str) or not value.strip():
        return (1, "")
    text = value.strip()
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return (1, text)
    return (0, parsed.isoformat())


def _message(record: dict[str, Any]) -> dict[str, Any]:
    """Return the nested outbound message as a dict."""
    message = record.get("message")
    if isinstance(message, dict):
        return message
    return {}


def _record_message_text(record: dict[str, Any]) -> str:
    """Return one pending outbox record as a display line."""
    message = _message(record)
    text = message.get("message", "")
    if isinstance(text, str):
        return text.strip()
    return str(text or "").strip()


def _metadata(record: dict[str, Any]) -> dict[str, Any]:
    """Return outbound metadata as a dict."""
    metadata = _message(record).get("metadata")
    if isinstance(metadata, dict):
        return metadata
    return {}


def _parse_event_datetime(value: Any) -> datetime | None:
    """Parse an outbox reminder event datetime into a local naive datetime."""
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


def _format_event_time(value: Any) -> str:
    """Format reminder time as 今天/明天 HH:MM when possible."""
    parsed = _parse_event_datetime(value)
    if parsed is None:
        return str(value or "").strip()
    today = datetime.now().date()
    if parsed.date() == today:
        prefix = "今天"
    elif parsed.date() == today + timedelta(days=1):
        prefix = "明天"
    else:
        prefix = parsed.strftime("%m月%d日")
    return f"{prefix} {parsed:%H:%M}"


def _format_offset(value: Any) -> str:
    """Return a human-readable reminder offset."""
    if isinstance(value, int) and value > 0:
        return f"{value} 分钟后"
    return "稍后"


def _clean_text(value: Any) -> str:
    """Normalize metadata text for WeChat-friendly display."""
    if not isinstance(value, str):
        return str(value or "").strip()
    return " ".join(value.split())


def _record_view(record: dict[str, Any]) -> dict[str, str]:
    """Build a safe display view for one outbox record."""
    metadata = _metadata(record)
    title = _clean_text(metadata.get("title"))
    start = _format_event_time(metadata.get("start"))
    location = _clean_text(metadata.get("location"))
    offset = _format_offset(metadata.get("offset_minutes"))

    if not title:
        title = _record_message_text(record)
    return {
        "title": title,
        "start": start,
        "location": location,
        "offset": offset,
    }


def _select_pending_records(limit: int) -> list[dict[str, Any]]:
    """Return oldest pending outbox records, limited by count."""
    records = [record for record in outbox.load_outbox_records() if record.get("status") == "pending"]
    records.sort(key=lambda record: _parse_created_at(record.get("created_at")))
    return records[: max(limit, 0)]


def _render_records(records: list[dict[str, Any]], empty_mode: str) -> str:
    """Render selected records as Hermes-friendly plain text."""
    selected = records

    views = [_record_view(record) for record in selected]
    views = [view for view in views if view["title"] or view["start"]]

    if not views:
        if empty_mode == EMPTY_MODE_MESSAGE:
            return EMPTY_MESSAGE
        return ""

    if len(views) == 1:
        view = views[0]
        lines = [
            "📅 日程提醒",
            "",
            f"高先生，您 {view['offset']}有一个日程：",
            "",
        ]
        if view["start"]:
            lines.append(f"🕐 时间：{view['start']}")
        lines.append(f"📌 事项：{view['title']}")
        if view["location"]:
            lines.append(f"📍 地点：{view['location']}")
        lines.extend(
            [
                "",
                "您可以直接回复：",
                "- 推迟30分钟",
                "- 取消这个日程",
                "- 改到明天上午10点",
                "- 已到达",
            ]
        )
        return "\n".join(lines)

    lines = [
        "📅 日程提醒",
        "",
        f"高先生，您有 {len(views)} 个即将开始的日程：",
        "",
    ]
    for index, view in enumerate(views, start=1):
        lines.append(f"{index}. 🕐 {view['start'] or view['offset']}")
        lines.append(f"   📌 {view['title']}")
        if view["location"]:
            lines.append(f"   📍 {view['location']}")
        if index != len(views):
            lines.append("")

    lines.extend(
        [
            "",
            "您可以直接回复：推迟30分钟、取消这个日程、改到明天上午10点、已到达",
        ]
    )
    return "\n".join(lines)


def _mark_records_sent(records: list[dict[str, Any]]) -> None:
    """Mark selected pending records as sent_via_hermes_cron."""
    result = outbox.update_outbox_statuses(
        [str(record.get("id", "")) for record in records],
        BRIDGE_STATUS,
        result={
            "mode": "hermes_cron",
            "processed_at": util.now_local_iso(),
            "note": "Message handed to Hermes Cron stdout for delivery",
        },
        only_if_status="pending",
    )
    if not result.get("ok"):
        raise RuntimeError(str(result.get("error") or "outbox_update_failed"))


def read_pending(limit: int = 5, empty_mode: str = EMPTY_MODE_SILENT, mark_sent: bool = False) -> str:
    """Render oldest pending outbox messages and optionally mark them as sent."""
    records = _select_pending_records(limit)
    output = _render_records(records, empty_mode)
    if mark_sent and records and output:
        _mark_records_sent(records)
    return output


def _build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(
        description="Render pending outbox records as plain text for Hermes cron --script delivery."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    read_parser = subparsers.add_parser("read-pending", help="Read pending outbox records as plain text.")
    read_parser.add_argument("--limit", type=int, default=5)
    read_parser.add_argument(
        "--empty-mode",
        choices=(EMPTY_MODE_SILENT, EMPTY_MODE_MESSAGE),
        default=EMPTY_MODE_SILENT,
    )
    read_parser.add_argument("--mark-sent", action="store_true")

    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the command-line interface."""
    args = _build_parser().parse_args(argv)
    if args.command == "read-pending":
        output = read_pending(args.limit, args.empty_mode, args.mark_sent)
    else:
        raise AssertionError(args.command)
    print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
