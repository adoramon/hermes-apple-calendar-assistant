"""Safe natural-language delete flow for Calendar events."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Any

try:
    from . import assistant_persona, calendar_ops, settings, util
except ImportError:  # Allows running as: python3 scripts/delete_event_flow.py ...
    import assistant_persona  # type: ignore
    import calendar_ops  # type: ignore
    import settings  # type: ignore
    import util  # type: ignore


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PENDING_CONFIRMATIONS_PATH = PROJECT_ROOT / "data" / "pending_confirmations.json"
ACTION_NAME = "delete_event"
DELETE_WORDS = ("删除", "取消", "删掉", "移除", "撤销", "不要")
TITLE_STOP_WORDS = (
    "计划",
    "安排",
    "日程",
    "事件",
    "行程",
    "今天",
    "明天",
    "后天",
    "上午",
    "下午",
    "晚上",
    "中午",
    "早上",
    "这个",
    "那个",
    "一下",
    "帮我",
)


def _result(ok: bool, data: Any = None, error: str | None = None) -> dict[str, Any]:
    return {"ok": ok, "data": data, "error": error}


def _read_pending_store() -> dict[str, Any]:
    raw = util.load_json(PENDING_CONFIRMATIONS_PATH, {"sessions": {}})
    if not isinstance(raw, dict):
        return {"sessions": {}}
    if not isinstance(raw.get("sessions"), dict):
        raw["sessions"] = {}
    return raw


def _write_pending_store(store: dict[str, Any]) -> None:
    util.save_json_atomic(PENDING_CONFIRMATIONS_PATH, store)


def _date_window(text: str) -> tuple[datetime, datetime, list[str]]:
    today = datetime.now().date()
    assumptions: list[str] = []
    if "后天" in text:
        target = today + timedelta(days=2)
        return datetime.combine(target, time.min), datetime.combine(target + timedelta(days=1), time.min), assumptions
    if "明天" in text:
        target = today + timedelta(days=1)
        return datetime.combine(target, time.min), datetime.combine(target + timedelta(days=1), time.min), assumptions
    if "今天" in text or "今日" in text:
        return datetime.combine(today, time.min), datetime.combine(today + timedelta(days=1), time.min), assumptions
    assumptions.append("未指定日期，默认查找今天起未来 30 天内可写日历中的匹配日程。")
    return datetime.combine(today, time.min), datetime.combine(today + timedelta(days=30), time.min), assumptions


def _normalize_title(value: Any) -> str:
    text = str(value or "")
    for word in DELETE_WORDS + TITLE_STOP_WORDS:
        text = text.replace(word, " ")
    text = re.sub(r"[，,。.!！?？\s]+", "", text)
    return text


def _extract_target_title(text: str) -> str:
    return _normalize_title(text)


def _candidate_score(target: str, event: dict[str, Any]) -> int:
    title = _normalize_title(event.get("title"))
    if not target or not title:
        return 0
    if title == target:
        return 100
    if target in title:
        return 85
    if title in target:
        return 80
    common = sum(1 for char in set(target) if char in title)
    return common * 10 if common >= 2 else 0


def _find_candidates(text: str) -> dict[str, Any]:
    start, end, assumptions = _date_window(text)
    target = _extract_target_title(text)
    if not target:
        return _result(False, data={"missing_fields": ["title"]}, error="delete_target_title_missing")

    candidates: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for calendar in settings.get_write_calendars():
        events_result = calendar_ops.list_events(calendar, start_date=start, end_date=end)
        if not events_result.get("ok"):
            errors.append({"calendar": calendar, "error": events_result.get("error")})
            continue
        for event in events_result.get("data", {}).get("events", []):
            if not isinstance(event, dict):
                continue
            score = _candidate_score(target, event)
            if score <= 0:
                continue
            candidates.append(
                {
                    "calendar": calendar,
                    "title": event.get("title", ""),
                    "start": event.get("start", ""),
                    "end": event.get("end", ""),
                    "location": event.get("location", ""),
                    "notes": event.get("notes", ""),
                    "match_score": score,
                }
            )
    candidates.sort(key=lambda item: (-int(item.get("match_score", 0)), str(item.get("start", ""))))
    return _result(
        True,
        data={
            "target_title": target,
            "start": start.isoformat(timespec="seconds"),
            "end": end.isoformat(timespec="seconds"),
            "assumptions": assumptions,
            "candidates": candidates,
            "errors": errors,
        },
    )


def _summary(candidate: dict[str, Any], assumptions: list[str]) -> str:
    lines = ["我先找到这条日程，删除前请您再确认一次：", ""]
    lines.append(f"📌 {candidate.get('title', '')}")
    lines.append(f"🕐 {assistant_persona.format_time_range(candidate.get('start'), candidate.get('end'))}")
    lines.append(f"📅 日历：{candidate.get('calendar', '')}")
    location = str(candidate.get("location") or "").strip()
    if location:
        lines.append(f"📍 {location}")
    if assumptions:
        lines.extend(["", "当前默认："])
        for item in assumptions:
            lines.append(f"- {item}")
    lines.extend(["", "回复“确认删除”后我再从 Apple Calendar 删除。"])
    return "\n".join(lines)


def _session_key(text: str, candidate: dict[str, Any]) -> str:
    raw = "|".join(
        [
            ACTION_NAME,
            text,
            str(candidate.get("calendar", "")),
            str(candidate.get("title", "")),
            str(candidate.get("start", "")),
            str(candidate.get("end", "")),
            util.now_local_iso(),
        ]
    )
    return f"delete_event_{hashlib.sha1(raw.encode('utf-8')).hexdigest()[:12]}"


def draft_delete(text: str) -> dict[str, Any]:
    found = _find_candidates(text)
    if not found.get("ok"):
        return found
    data = found.get("data", {})
    candidates = [item for item in data.get("candidates", []) if isinstance(item, dict)]
    if not candidates:
        return _result(False, data=data, error="delete_event_not_found")
    best_score = int(candidates[0].get("match_score", 0))
    best = [item for item in candidates if int(item.get("match_score", 0)) == best_score]
    if len(best) != 1:
        return _result(False, data=data, error="delete_event_ambiguous")

    candidate = best[0]
    session_key = _session_key(text, candidate)
    summary = _summary(candidate, list(data.get("assumptions") or []))
    pending = {
        "session_key": session_key,
        "action": ACTION_NAME,
        "status": "pending",
        "created_at": util.now_local_iso(),
        "source_text": text,
        "target_event": candidate,
        "candidates": candidates[:5],
        "needs_confirmation": True,
        "summary": summary,
        "display_message": summary,
    }
    store = _read_pending_store()
    store.setdefault("sessions", {})[session_key] = pending
    _write_pending_store(store)
    return _result(
        True,
        data={
            "session_key": session_key,
            "target_event": candidate,
            "candidates": candidates[:5],
            "needs_confirmation": True,
            "display_message": summary,
        },
    )


def confirm_delete(session_key: str) -> dict[str, Any]:
    store = _read_pending_store()
    pending = store.get("sessions", {}).get(session_key)
    if not isinstance(pending, dict):
        return _result(False, error=f"No pending delete action found for session: {session_key}")
    if pending.get("status") != "pending":
        return _result(False, error=f"Delete action is not pending for session: {session_key}")
    if pending.get("action") != ACTION_NAME:
        return _result(False, error=f"Unsupported pending action: {pending.get('action')}")
    event = pending.get("target_event")
    if not isinstance(event, dict):
        return _result(False, error="pending delete action is malformed")

    delete_result = calendar_ops.delete_event_exact_identity(
        str(event.get("calendar", "")),
        str(event.get("title", "")),
        str(event.get("start", "")),
        str(event.get("end", "")),
    )
    if not delete_result.get("ok"):
        return delete_result

    pending["status"] = "confirmed"
    pending["confirmed_at"] = util.now_local_iso()
    pending["result"] = delete_result.get("data")
    store["sessions"][session_key] = pending
    _write_pending_store(store)
    return _result(
        True,
        data={
            "session_key": session_key,
            "target_event": event,
            "result": delete_result.get("data"),
            "display_message": delete_result.get("data", {}).get("display_message"),
        },
    )


def show_pending(session_key: str) -> dict[str, Any]:
    pending = _read_pending_store().get("sessions", {}).get(session_key)
    if not isinstance(pending, dict):
        return _result(False, error=f"No pending delete action found for session: {session_key}")
    return _result(True, data=pending)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Draft and confirm safe Calendar event deletion.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    draft = subparsers.add_parser("draft")
    draft.add_argument("--text", required=True)
    confirm = subparsers.add_parser("confirm")
    confirm.add_argument("--session-key", required=True)
    show = subparsers.add_parser("show-pending")
    show.add_argument("--session-key", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "draft":
        result = draft_delete(args.text)
    elif args.command == "confirm":
        result = confirm_delete(args.session_key)
    elif args.command == "show-pending":
        result = show_pending(args.session_key)
    else:
        raise AssertionError(args.command)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
