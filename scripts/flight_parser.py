"""Parse flight details from Apple Calendar flight event titles."""

from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Any


FLIGHT_NO_RE = re.compile(r"(?<![A-Z0-9])([A-Z]{2}|[A-Z][0-9]|[0-9][A-Z])\s?(\d{3,4})(?![A-Z0-9])", re.I)
ROUTE_DASH_RE = re.compile(r"([\u4e00-\u9fa5A-Za-z0-9]+?)(?:-|－|—|–|->|→)([\u4e00-\u9fa5A-Za-z0-9]+)")
ROUTE_TO_RE = re.compile(r"([\u4e00-\u9fa5A-Za-z]{2,20})到([\u4e00-\u9fa5A-Za-z]{2,20}?)(?:的)?航班")
TERMINAL_SUFFIX_RE = re.compile(r"^(.*?)(T[1-4])$", re.I)
TERMINAL_WORD_RE = re.compile(r"^(.*?)([1-4])号?航站楼$", re.I)


def _result(ok: bool, data: Any = None, error: str | None = None) -> dict[str, Any]:
    return {"ok": ok, "data": data, "error": error}


def _clean_text(value: str | None) -> str:
    return re.sub(r"\s+", "", value or "")


def extract_flight_no(title: str) -> str | None:
    """Extract a flight number such as CA1210 or MU5579."""
    match = FLIGHT_NO_RE.search(title)
    if not match:
        return None
    return f"{match.group(1).upper()}{match.group(2)}"


def _split_terminal(segment: str) -> tuple[str | None, str | None]:
    cleaned = _clean_text(segment).strip("-－—–>→")
    match = TERMINAL_SUFFIX_RE.match(cleaned)
    if match:
        airport = match.group(1) or None
        terminal = match.group(2).upper()
        return airport, terminal
    match = TERMINAL_WORD_RE.match(cleaned)
    if match:
        airport = match.group(1) or None
        terminal = f"T{match.group(2)}"
        return airport, terminal
    return cleaned or None, None


def extract_route_and_terminals(title: str) -> dict[str, Any]:
    """Extract route and terminal hints without standardizing airport names.

    The first version prioritizes titles like "乘坐CA1210 西安咸阳T2-北京首都T3".
    More complex airport expressions can be added later without changing callers.
    """
    compact_title = _clean_text(title)
    compact_title = re.sub(r"^乘坐", "", compact_title)
    compact_title = FLIGHT_NO_RE.sub("", compact_title, count=1)
    compact_title = re.sub(r"(当地时间|北京时间|起飞|到达|【).*$", "", compact_title)
    route_match = ROUTE_DASH_RE.search(compact_title)
    if not route_match:
        route_match = ROUTE_TO_RE.search(compact_title)

    if not route_match:
        return {
            "departure_airport_raw": None,
            "arrival_airport_raw": None,
            "departure_terminal": None,
            "arrival_terminal": None,
        }

    departure_raw, departure_terminal = _split_terminal(route_match.group(1))
    arrival_raw, arrival_terminal = _split_terminal(route_match.group(2))
    return {
        "departure_airport_raw": departure_raw,
        "arrival_airport_raw": arrival_raw,
        "departure_terminal": departure_terminal,
        "arrival_terminal": arrival_terminal,
    }


def _calculate_confidence(flight_no: str | None, route: dict[str, Any], title: str) -> float:
    score = 0.0
    if flight_no:
        score += 0.45
    if route.get("departure_airport_raw") and route.get("arrival_airport_raw"):
        score += 0.4
        if "航班" in title and not flight_no:
            score += 0.2
    if route.get("departure_terminal"):
        score += 0.075
    if route.get("arrival_terminal"):
        score += 0.075
    if "航班" in title and score == 0.0:
        score += 0.2
    return min(score, 1.0)


def parse_flight_title(title: str) -> dict[str, Any]:
    """Parse a flight title into a stable first-version structure."""
    if not isinstance(title, str) or not title.strip():
        return _result(False, error="title must be a non-empty string.")

    flight_no = extract_flight_no(title)
    route = extract_route_and_terminals(title)
    confidence = _calculate_confidence(flight_no, route, title)
    is_flight_event = bool(flight_no) or (
        "航班" in title and bool(route.get("departure_airport_raw")) and bool(route.get("arrival_airport_raw"))
    )

    data = {
        "is_flight_event": is_flight_event,
        "title": title,
        "flight_no": flight_no,
        "departure_airport_raw": route["departure_airport_raw"],
        "arrival_airport_raw": route["arrival_airport_raw"],
        "departure_terminal": route["departure_terminal"],
        "arrival_terminal": route["arrival_terminal"],
        "confidence": round(confidence if is_flight_event else 0.0, 3),
    }
    return _result(True, data=data)


def parse_flight_event(event: dict[str, Any]) -> dict[str, Any]:
    """Compatibility wrapper for callers that pass Calendar.app event dicts."""
    return parse_flight_title(str(event.get("title", "")))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Parse a flight event title.")
    parser.add_argument("title", help="Flight event title to parse.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    result = parse_flight_title(args.title)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
