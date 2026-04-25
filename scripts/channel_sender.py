"""Channel sender abstraction for future outbound delivery.

Current implementation is intentionally dry-run only. It does not perform any
network requests and does not integrate with Telegram, WeChat, or Hermes push.
"""

from __future__ import annotations

from typing import Any

try:
    from . import settings, util
except ImportError:  # Allows importing as: python3 scripts/channel_sender.py
    import settings  # type: ignore
    import util  # type: ignore


DRY_RUN_MODE = "dry_run"
REAL_MODE = "real"
SUPPORTED_CHANNELS = {"hermes"}


def _json_error(message: str) -> dict[str, Any]:
    """Return a standard error envelope with explicit data=null."""
    return {"ok": False, "data": None, "error": message}


def validate_channel(message: dict[str, Any]) -> dict[str, Any]:
    """Validate that an outbound message uses a supported channel."""
    channel = message.get("channel")
    if channel not in SUPPORTED_CHANNELS:
        return _json_error("unsupported channel")
    return util.json_ok({"channel": channel})


def validate_recipient(message: dict[str, Any]) -> dict[str, Any]:
    """Validate that an outbound message has a non-empty recipient."""
    recipient = message.get("recipient")
    if not isinstance(recipient, str) or not recipient.strip():
        return _json_error("invalid recipient")
    return util.json_ok({"recipient": recipient})


def dry_run_send(message: dict[str, Any]) -> dict[str, Any]:
    """Simulate sending a message without calling any external service."""
    channel_result = validate_channel(message)
    if not channel_result["ok"]:
        return channel_result
    recipient_result = validate_recipient(message)
    if not recipient_result["ok"]:
        return recipient_result
    return util.json_ok(
        {
            "mode": DRY_RUN_MODE,
            "status": "sent_dry_run",
            "channel": message.get("channel", ""),
            "recipient": message.get("recipient", ""),
            "processed_at": util.now_local_iso(),
        }
    )


def send_message(message: dict[str, Any], mode: str) -> dict[str, Any]:
    """Send one outbound message using the configured mode.

    Only dry_run is implemented. The real branch is reserved and always rejected
    in this phase, even when the safety placeholder is enabled.
    """
    if mode == DRY_RUN_MODE:
        return dry_run_send(message)
    if mode == REAL_MODE:
        if not settings.get_outbox_real_send_enabled():
            return _json_error("real send is not implemented")
        return _json_error("real send is not implemented")
    return _json_error("unsupported send mode")
