"""Outbound message payload adapters for local assistant outputs."""

from __future__ import annotations

from typing import Any

try:
    from . import assistant_persona, util
except ImportError:  # Allows importing as: python3 scripts/message_adapter.py
    import assistant_persona  # type: ignore
    import util  # type: ignore

json_ok = util.json_ok
json_error = util.json_error


def build_calendar_reminder_message(reminder: dict[str, Any]) -> str:
    """Build a human-readable calendar reminder message."""
    return assistant_persona.format_reminder_message(reminder)


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
        "metadata": dict(metadata or {}),
    }
