"""Outbound message payload adapters for local assistant outputs."""

from __future__ import annotations

import re
from typing import Any

try:
    from . import util
except ImportError:  # Allows importing as: python3 scripts/message_adapter.py
    import util  # type: ignore


APPLE_DATETIME_RE = re.compile(
    r"(?P<year>\d{4})年(?P<month>\d{1,2})月(?P<day>\d{1,2})日.*?"
    r"(?P<hour>\d{1,2}):(?P<minute>\d{2}):(?P<second>\d{2})"
)

json_ok = util.json_ok
json_error = util.json_error


def _format_start(value: Any) -> str:
    """Format a reminder start value for concise outbound text."""
    if not isinstance(value, str):
        return str(value or "")
    match = APPLE_DATETIME_RE.search(value)
    if match:
        return (
            f"{int(match.group('year')):04d}-{int(match.group('month')):02d}-"
            f"{int(match.group('day')):02d} {int(match.group('hour')):02d}:"
            f"{int(match.group('minute')):02d}"
        )
    text = value.strip()
    if "T" in text:
        return text[:16].replace("T", " ")
    return text


def build_calendar_reminder_message(reminder: dict[str, Any]) -> str:
    """Build a human-readable calendar reminder message."""
    offset = reminder.get("offset_minutes", "")
    calendar = reminder.get("calendar", "")
    title = reminder.get("title", "")
    start = _format_start(reminder.get("start", ""))
    location = reminder.get("location", "")
    location_text = f"｜地点：{location}" if location else ""
    return f"{offset}分钟后：{calendar}｜{title}｜{start}{location_text}"


def build_outbound_payload(
    channel: str,
    recipient: str,
    message: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a standard outbound message payload without sending it."""
    return {
        "channel": channel,
        "recipient": recipient,
        "message": message,
        "metadata": metadata or {},
    }
