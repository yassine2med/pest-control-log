"""Command line entry for the pest control log."""

from __future__ import annotations

import argparse
import sys
from datetime import date

from .core import LogError, append_visit, load_log, open_followups, parse_date, pest_counts, summarize


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pestlog", description="Pest control visit log")
    sub = parser.add_subparsers(dest="command", required=True)
    add = sub.add_parser("add", help="append one visit to a log")
    add.add_argument("--log", required=True, help="log CSV (created if missing)")
    for name in ("date", "area", "pest", "severity", "action", "technician"):
        add.add_argument(f"--{name}", required=True)
    add.add_argument("--follow-up", default="", help="follow-up date, YYYY-MM-DD")
    sub.add_parser("validate", help="check every row of a log").add_argument("log")
    sub.add_parser("report", help="summary by area and pest").add_argument("log")
    due = sub.add_parser("followups", help="open follow-ups, most overdue first")
    due.add_argument("log")
    due.add_argument("--today", help="date to compare against (default: today)")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Return 0 when fine, 1 when problems or overdue follow-ups exist, 2 for bad input."""
    args = build_parser().parse_args(argv)
    if args.command == "add":
        row = {k: getattr(args, k) for k in ("date", "area", "pest", "severity", "action", "technician")}
        row["follow_up_date"] = args.follow_up
        try:
            visit = append_visit(args.log, row)
        except LogError as exc:
            print(f"Rejected: {exc}", file=sys.stderr)
            return 2
        print(f"Added {visit.date} {visit.area}: {visit.pest} ({visit.severity})")
        return 0
    try:
        visits, problems = load_log(args.log)
    except FileNotFoundError:
        print(f"File not found: {args.log}", file=sys.stderr)
        return 2
    if args.command == "validate":
        for p in problems:
            print(p)
        print(f"{len(visits)} valid visit(s), {len(problems)} problem(s)")
        return 1 if problems else 0
    if problems:
        print(f"Log has {len(problems)} problem(s); run validate first", file=sys.stderr)
        return 2
    if args.command == "report":
        print(f"{'area':<14}{'visits':>7}  {'worst':<8}latest")
        for area, count, worst, latest in summarize(visits):
            print(f"{area:<14}{count:>7}  {worst:<8}{latest}")
        print("findings by pest: " + ", ".join(f"{p} {n}" for p, n in sorted(pest_counts(visits).items())))
        return 0
    try:
        today = parse_date(args.today, "--today") if args.today else date.today()
    except LogError as exc:
        print(f"Bad input: {exc}", file=sys.stderr)
        return 2
    pending = open_followups(visits, today)
    overdue = 0
    for visit, days in pending:
        state = f"OVERDUE {days}d" if days > 0 else ("due today" if days == 0 else f"in {-days}d")
        overdue += days > 0
        print(f"{visit.follow_up}  {visit.area:<13}{visit.pest:<10}{visit.severity:<7}{state}")
    print(f"{len(pending)} open follow-up(s), {overdue} overdue")
    return 1 if overdue else 0


if __name__ == "__main__":
    sys.exit(main())
