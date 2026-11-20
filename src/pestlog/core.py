"""Pest control visit log: validate, append, summarize, find overdue follow-ups."""

from __future__ import annotations

import csv
import os
from collections import Counter
from dataclasses import dataclass
from datetime import date

FIELDS = ["date", "area", "pest", "severity", "action", "technician", "follow_up_date"]
SEVERITIES = ["none", "low", "medium", "high"]


class LogError(ValueError):
    """Raised for an invalid visit entry."""


@dataclass(frozen=True)
class Visit:
    date: date
    area: str
    pest: str
    severity: str
    action: str
    technician: str
    follow_up: date | None


def parse_date(text: str, label: str) -> date:
    try:
        return date.fromisoformat(text.strip())
    except ValueError as exc:
        raise LogError(f"{label} '{text}' is not a date in YYYY-MM-DD form") from exc


def make_visit(row: dict) -> Visit:
    """Build a Visit from a row dict, raising LogError for any problem."""
    for key in ("date", "area", "pest", "severity", "action", "technician"):
        if not (row.get(key) or "").strip():
            raise LogError(f"'{key}' is required")
    severity = row["severity"].strip().lower()
    if severity not in SEVERITIES:
        raise LogError(f"severity '{severity}' is not one of {SEVERITIES}")
    visit_date = parse_date(row["date"], "date")
    follow_text = (row.get("follow_up_date") or "").strip()
    follow = parse_date(follow_text, "follow_up_date") if follow_text else None
    if follow and follow < visit_date:
        raise LogError("follow_up_date is before the visit date")
    if severity in ("medium", "high") and not follow:
        raise LogError(f"a {severity} finding needs a follow_up_date")
    return Visit(visit_date, row["area"].strip(), row["pest"].strip().lower(), severity,
                 row["action"].strip(), row["technician"].strip(), follow)


def load_log(path: str) -> tuple[list[Visit], list[str]]:
    """Return (visits, problems). Problems are strings like 'line 4: ...'."""
    visits, problems = [], []
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        missing = [f for f in FIELDS if f not in (reader.fieldnames or [])]
        if missing:
            return [], [f"missing column(s): {', '.join(missing)}"]
        for i, row in enumerate(reader, start=2):
            try:
                visits.append(make_visit(row))
            except LogError as exc:
                problems.append(f"line {i}: {exc}")
    return visits, problems


def append_visit(path: str, row: dict) -> Visit:
    """Validate then append one visit, creating the file with a header if needed."""
    visit = make_visit(row)
    new = not os.path.exists(path) or os.path.getsize(path) == 0
    with open(path, "a", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        if new:
            writer.writerow(FIELDS)
        writer.writerow([row.get(f, "").strip() if row.get(f) else "" for f in FIELDS])
    return visit


def summarize(visits: list[Visit]) -> list[tuple[str, int, str, str]]:
    """One row per area: (area, visit count, worst severity seen, latest severity)."""
    rows = []
    for area in sorted({v.area for v in visits}):
        mine = sorted((v for v in visits if v.area == area), key=lambda v: v.date)
        worst = max(mine, key=lambda v: SEVERITIES.index(v.severity)).severity
        rows.append((area, len(mine), worst, mine[-1].severity))
    return rows


def pest_counts(visits: list[Visit]) -> Counter:
    return Counter(v.pest for v in visits if v.severity != "none")


def open_followups(visits: list[Visit], today: date) -> list[tuple[Visit, int]]:
    """Follow-ups not yet closed by a later visit to the same area and pest.

    Returns (visit, days_overdue) sorted most overdue first; negative days
    means the follow-up is still in the future.
    """
    result = []
    for v in visits:
        if not v.follow_up:
            continue
        closed = any(o.area == v.area and o.pest == v.pest and o.date > v.date for o in visits)
        if not closed:
            result.append((v, (today - v.follow_up).days))
    result.sort(key=lambda item: -item[1])
    return result
