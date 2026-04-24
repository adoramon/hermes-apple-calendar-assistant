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
