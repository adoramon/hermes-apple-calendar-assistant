"""Shared utility helpers."""

from __future__ import annotations

import json
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "config" / "settings.json"


def result(ok: bool, data: Any = None, error: str | None = None) -> dict[str, Any]:
    return {"ok": ok, "data": data, "error": error}


def json_ok(data: Any) -> dict[str, Any]:
    """Return the standard successful CLI JSON envelope."""
    return {"ok": True, "data": data, "error": None}


def json_error(message: str) -> dict[str, Any]:
    """Return the standard failed CLI JSON envelope."""
    return {"ok": False, "error": message}


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def now_local_iso() -> str:
    """Return the current local time as an ISO-8601 string."""
    return now_iso()


def normalize_calendar_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"", "missing value", "null", "none"}:
        return ""
    return text


def ensure_dir(path: str | Path) -> Path:
    """Create a directory if needed and return it as a Path."""
    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def load_json(path: str | Path, default: Any) -> Any:
    """Load JSON from path, returning default when the file is absent or invalid."""
    json_path = Path(path)
    if not json_path.exists():
        return default
    try:
        raw = json.loads(json_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default
    return raw


def save_json_atomic(path: str | Path, data: Any) -> None:
    """Write JSON atomically by replacing the target with a completed temp file."""
    json_path = Path(path)
    ensure_dir(json_path.parent)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=str(json_path.parent),
        delete=False,
    ) as tmp:
        tmp_path = Path(tmp.name)
        json.dump(data, tmp, ensure_ascii=False, indent=2)
        tmp.write("\n")
    tmp_path.replace(json_path)


def load_json_file(path: Path, default: Any) -> Any:
    """Compatibility wrapper for load_json()."""
    return load_json(path, default)


def write_json_file(path: Path, payload: Any) -> None:
    """Compatibility wrapper for save_json_atomic()."""
    save_json_atomic(path, payload)


def load_settings() -> dict[str, Any]:
    """Load raw project settings from config/settings.json."""
    raw = load_json(CONFIG_PATH, {})
    if not isinstance(raw, dict):
        return {}
    return raw
