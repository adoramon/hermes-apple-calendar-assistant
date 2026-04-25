"""Typed accessors for project settings."""

from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    from . import util
except ImportError:  # Allows importing as: python3 scripts/settings.py
    import util  # type: ignore


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SETTINGS_PATH = PROJECT_ROOT / "config" / "settings.json"

DEFAULT_READ_CALENDARS = ("商务计划", "家庭计划", "个人计划", "夫妻计划", "飞行计划")
DEFAULT_WRITE_CALENDARS = ("商务计划", "家庭计划", "个人计划", "夫妻计划")
DEFAULT_FLIGHT_CALENDAR = "飞行计划"
DEFAULT_TIMEZONE = "Asia/Shanghai"
DEFAULT_EVENT_DURATION_MINUTES = 60
DEFAULT_CONFLICT_CHECK_WINDOW_DAYS = 30
DEFAULT_REMINDER_SCAN_MINUTES = 180
DEFAULT_REMINDER_OFFSETS_MINUTES = (15, 60)
DEFAULT_OUTBOX_SETTINGS = {
    "send_mode": "dry_run",
    "send_modes_supported": ["dry_run"],
    "real_send_enabled": False,
    "sender": "channel_sender",
    "allowed_channels": ["hermes"],
    "default_channel": "hermes",
    "default_recipient": "default",
    "max_messages_per_run": 10,
    "hermes_channel": {
        "enabled": False,
        "transport": "local_cli",
        "notes": "reserved for future real Hermes dispatch",
    },
}
DEFAULT_REAL_SEND_GATE = {
    "enabled": False,
    "require_manual_config_change": True,
    "require_confirm_phrase": "ENABLE_REAL_SEND",
    "allowed_channels": [],
    "audit_required": True,
}


def load_settings() -> dict[str, Any]:
    """Load settings from config/settings.json with an empty-dict fallback."""
    raw = util.load_json(SETTINGS_PATH, {})
    if not isinstance(raw, dict):
        return {}
    return raw


def _string_list(value: Any, default: tuple[str, ...]) -> list[str]:
    """Normalize a settings value into a non-empty string list."""
    if not isinstance(value, list):
        return list(default)
    items = [item for item in value if isinstance(item, str) and item]
    return items or list(default)


def get_read_calendars() -> list[str]:
    """Return calendars that may be read by the assistant."""
    settings = load_settings()
    return _string_list(settings.get("read_calendars"), DEFAULT_READ_CALENDARS)


def get_write_calendars() -> list[str]:
    """Return calendars that may be written through normal CRUD."""
    settings = load_settings()
    return _string_list(settings.get("write_calendars"), DEFAULT_WRITE_CALENDARS)


def get_flight_calendar() -> str:
    """Return the configured flight calendar name."""
    settings = load_settings()
    value = settings.get("flight_calendar")
    if isinstance(value, str) and value:
        return value
    return DEFAULT_FLIGHT_CALENDAR


def get_timezone() -> str:
    """Return the configured IANA timezone name."""
    settings = load_settings()
    value = settings.get("timezone")
    if isinstance(value, str) and value:
        return value
    return DEFAULT_TIMEZONE


def get_default_event_duration_minutes() -> int:
    """Return the default duration for parsed event drafts."""
    settings = load_settings()
    value = settings.get("default_event_duration_minutes")
    if isinstance(value, int) and value > 0:
        return value
    return DEFAULT_EVENT_DURATION_MINUTES


def get_conflict_check_window_days() -> int:
    """Return the default lookahead window for conflict checks."""
    settings = load_settings()
    value = settings.get("conflict_check_window_days")
    if isinstance(value, int) and value > 0:
        return value
    return DEFAULT_CONFLICT_CHECK_WINDOW_DAYS


def get_reminder_scan_minutes() -> int:
    """Return how far ahead reminder scanning should inspect events."""
    current_settings = load_settings()
    value = current_settings.get("reminder_scan_minutes")
    if isinstance(value, int) and value > 0:
        return value
    return DEFAULT_REMINDER_SCAN_MINUTES


def get_reminder_default_offsets_minutes() -> list[int]:
    """Return reminder offsets, in minutes before event start."""
    current_settings = load_settings()
    value = current_settings.get("reminder_default_offsets_minutes")
    if not isinstance(value, list):
        return list(DEFAULT_REMINDER_OFFSETS_MINUTES)
    offsets = sorted({item for item in value if isinstance(item, int) and item > 0})
    return offsets or list(DEFAULT_REMINDER_OFFSETS_MINUTES)


def get_outbox_settings() -> dict[str, Any]:
    """Return normalized outbox settings for dry-run message consumption."""
    current_settings = load_settings()
    raw = current_settings.get("outbox")
    if not isinstance(raw, dict):
        raw = {}
    return {
        "send_mode": raw.get("send_mode")
        if isinstance(raw.get("send_mode"), str) and raw.get("send_mode")
        else DEFAULT_OUTBOX_SETTINGS["send_mode"],
        "send_modes_supported": _string_list(
            raw.get("send_modes_supported"), tuple(DEFAULT_OUTBOX_SETTINGS["send_modes_supported"])
        ),
        "real_send_enabled": raw.get("real_send_enabled")
        if isinstance(raw.get("real_send_enabled"), bool)
        else DEFAULT_OUTBOX_SETTINGS["real_send_enabled"],
        "sender": raw.get("sender")
        if isinstance(raw.get("sender"), str) and raw.get("sender")
        else DEFAULT_OUTBOX_SETTINGS["sender"],
        "allowed_channels": _string_list(raw.get("allowed_channels"), tuple(DEFAULT_OUTBOX_SETTINGS["allowed_channels"])),
        "default_channel": raw.get("default_channel")
        if isinstance(raw.get("default_channel"), str) and raw.get("default_channel")
        else DEFAULT_OUTBOX_SETTINGS["default_channel"],
        "default_recipient": raw.get("default_recipient")
        if isinstance(raw.get("default_recipient"), str) and raw.get("default_recipient")
        else DEFAULT_OUTBOX_SETTINGS["default_recipient"],
        "max_messages_per_run": raw.get("max_messages_per_run")
        if isinstance(raw.get("max_messages_per_run"), int) and raw.get("max_messages_per_run") > 0
        else DEFAULT_OUTBOX_SETTINGS["max_messages_per_run"],
        "hermes_channel": raw.get("hermes_channel")
        if isinstance(raw.get("hermes_channel"), dict)
        else dict(DEFAULT_OUTBOX_SETTINGS["hermes_channel"]),
    }


def get_outbox_send_mode() -> str:
    """Return the configured outbox send mode."""
    return str(get_outbox_settings()["send_mode"])


def get_outbox_real_send_enabled() -> bool:
    """Return whether real outbox sending is enabled."""
    return bool(get_outbox_settings()["real_send_enabled"])


def get_outbox_send_modes_supported() -> list[str]:
    """Return outbox send modes supported by this installation."""
    return list(get_outbox_settings()["send_modes_supported"])


def get_outbox_sender() -> str:
    """Return the configured outbox sender abstraction name."""
    return str(get_outbox_settings()["sender"])


def get_outbox_allowed_channels() -> list[str]:
    """Return outbound channels allowed for outbox consumption."""
    return list(get_outbox_settings()["allowed_channels"])


def get_outbox_default_channel() -> str:
    """Return the default outbound channel for future sender integrations."""
    return str(get_outbox_settings()["default_channel"])


def get_outbox_default_recipient() -> str:
    """Return the default outbound recipient for future sender integrations."""
    return str(get_outbox_settings()["default_recipient"])


def get_outbox_max_messages_per_run() -> int:
    """Return the maximum outbox messages a consumer may process per run."""
    return int(get_outbox_settings()["max_messages_per_run"])


def get_hermes_channel_settings() -> dict[str, Any]:
    """Return reserved Hermes channel settings for future real dispatch."""
    value = get_outbox_settings()["hermes_channel"]
    if isinstance(value, dict):
        return dict(value)
    return dict(DEFAULT_OUTBOX_SETTINGS["hermes_channel"])


def get_real_send_gate() -> dict[str, Any]:
    """Return normalized real-send gate settings."""
    current_settings = load_settings()
    raw = current_settings.get("real_send_gate")
    if not isinstance(raw, dict):
        raw = {}
    return {
        "enabled": raw.get("enabled")
        if isinstance(raw.get("enabled"), bool)
        else DEFAULT_REAL_SEND_GATE["enabled"],
        "require_manual_config_change": raw.get("require_manual_config_change")
        if isinstance(raw.get("require_manual_config_change"), bool)
        else DEFAULT_REAL_SEND_GATE["require_manual_config_change"],
        "require_confirm_phrase": raw.get("require_confirm_phrase")
        if isinstance(raw.get("require_confirm_phrase"), str) and raw.get("require_confirm_phrase")
        else DEFAULT_REAL_SEND_GATE["require_confirm_phrase"],
        "allowed_channels": _string_list(
            raw.get("allowed_channels"), tuple(DEFAULT_REAL_SEND_GATE["allowed_channels"])
        ),
        "audit_required": raw.get("audit_required")
        if isinstance(raw.get("audit_required"), bool)
        else DEFAULT_REAL_SEND_GATE["audit_required"],
    }


def is_real_send_gate_enabled() -> bool:
    """Return whether the final real-send gate is enabled."""
    return bool(get_real_send_gate()["enabled"])


def get_real_send_confirm_phrase() -> str:
    """Return the required phrase for real-send attempts."""
    return str(get_real_send_gate()["require_confirm_phrase"])


def get_real_send_allowed_channels() -> list[str]:
    """Return channels allowed by the final real-send gate."""
    return list(get_real_send_gate()["allowed_channels"])
