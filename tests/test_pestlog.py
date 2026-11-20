from datetime import date

import pytest

from pestlog.cli import main
from pestlog.core import LogError, append_visit, load_log, make_visit, open_followups, pest_counts, summarize


def row(**kw):
    base = dict(date="2026-11-01", area="Kitchen", pest="Ant", severity="low", action="spray",
                technician="T", follow_up_date="")
    base.update(kw)
    return base


def test_make_visit_normalizes_case():
    v = make_visit(row(pest="ANT", severity="LOW"))
    assert v.pest == "ant" and v.severity == "low"


def test_bad_severity():
    with pytest.raises(LogError, match="severity"):
        make_visit(row(severity="severe"))


def test_bad_date():
    with pytest.raises(LogError, match="YYYY-MM-DD"):
        make_visit(row(date="11/01/2026"))


def test_missing_required():
    with pytest.raises(LogError, match="'area' is required"):
        make_visit(row(area=" "))


def test_medium_needs_follow_up():
    with pytest.raises(LogError, match="needs a follow_up_date"):
        make_visit(row(severity="medium"))


def test_follow_up_before_visit():
    with pytest.raises(LogError, match="before the visit"):
        make_visit(row(severity="medium", follow_up_date="2026-10-01"))


def test_load_example_is_clean():
    visits, problems = load_log("examples/pest_log.csv")
    assert len(visits) == 7 and problems == []


def test_load_error_example_reports_lines():
    visits, problems = load_log("examples/pest_log_errors.csv")
    assert [p.split(":")[0] for p in problems] == ["line 2", "line 3", "line 4", "line 5"]
    assert visits == []


def test_summarize_worst_and_latest():
    visits, _ = load_log("examples/pest_log.csv")
    kitchen = [r for r in summarize(visits) if r[0] == "Kitchen"][0]
    assert kitchen == ("Kitchen", 3, "medium", "none")


def test_pest_counts_skip_none():
    visits, _ = load_log("examples/pest_log.csv")
    assert pest_counts(visits)["cockroach"] == 2


def test_followup_closed_by_later_visit():
    visits, _ = load_log("examples/pest_log.csv")
    pending = open_followups(visits, date(2026, 11, 20))
    areas = {(v.area, v.pest) for v, _ in pending}
    assert ("Kitchen", "cockroach") not in areas and ("Storage room", "ant") in areas


def test_followup_days_overdue_sorted():
    visits, _ = load_log("examples/pest_log.csv")
    days = [d for _, d in open_followups(visits, date(2026, 11, 20))]
    assert days == [22, 8]


def test_append_creates_file_with_header(tmp_path):
    path = tmp_path / "log.csv"
    append_visit(str(path), row())
    lines = path.read_text().splitlines()
    assert lines[0].startswith("date,area") and len(lines) == 2


def test_append_rejects_bad_row_without_writing(tmp_path):
    path = tmp_path / "log.csv"
    with pytest.raises(LogError):
        append_visit(str(path), row(severity="bad"))
    assert not path.exists()


def test_cli_exit_codes(capsys, tmp_path):
    assert main(["validate", "examples/pest_log.csv"]) == 0
    assert main(["validate", "examples/pest_log_errors.csv"]) == 1
    assert main(["followups", "examples/pest_log.csv", "--today", "2026-11-20"]) == 1
    assert main(["followups", "examples/pest_log.csv", "--today", "2026-10-01"]) == 0
    assert main(["report", "nope.csv"]) == 2


def test_cli_add_then_report(capsys, tmp_path):
    log = str(tmp_path / "l.csv")
    code = main(["add", "--log", log, "--date", "2026-11-02", "--area", "Lobby", "--pest", "ant",
                 "--severity", "low", "--action", "spray", "--technician", "T"])
    assert code == 0
    main(["report", log])
    assert "Lobby" in capsys.readouterr().out
