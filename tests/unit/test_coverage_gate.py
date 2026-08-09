"""The coverage bar, and every shape of unreadable measurement it refuses.

Issue #47 asks for a gate that fails closed on a missing report, an unparsable
report and a surface that matched zero lines, with a test for each. Those three
are the subject of most of this file, because they are the cases where a gate
stops working and reports green, which is the failure a coverage bar is
uniquely good at hiding.

The other half is the counting rule. Per executable line across the whole
surface is not the same number as the average of per-module percentages, and
`test_counting_is_per_line_and_not_an_average_of_modules` builds the fixture
where the two disagree: several small modules fully covered and one large one
barely covered. The average passes the threshold and the line count does not,
so the rule is proven rather than restated.
"""

from __future__ import annotations

import importlib.util
import json
from decimal import Decimal
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest


def _load() -> ModuleType:
    """Import tools/coverage_gate.py, which is not part of the package.

    It lives under tools/ because it is a repository script rather than
    something an operator installs, so it is not importable by name and is
    loaded from its path here, the same way the mutation score reader's suite
    loads its own subject.
    """
    path = Path(__file__).resolve().parents[2] / "tools" / "coverage_gate.py"
    specification = importlib.util.spec_from_file_location("coverage_gate", path)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


coverage_gate = _load()


def write(directory: Path, document: object) -> Path:
    """Write a coverage report and return its path."""
    report = directory / "coverage.json"
    report.write_text(json.dumps(document), encoding="utf-8")
    return report


def summary(covered: int, statements: int) -> dict[str, Any]:
    """One file's summary section, in the shape `coverage json` writes it."""
    return {"summary": {"covered_lines": covered, "num_statements": statements}}


def report(
    surface: dict[str, tuple[int, int]] | None = None,
    separator: str = "/",
    extra: dict[str, tuple[int, int]] | None = None,
) -> dict[str, Any]:
    """A whole report, covering every surface module unless told otherwise.

    `separator` exists because `coverage json` writes the path separator of the
    platform it ran on, and this gate has to read both.
    """
    counts = dict(surface or {})
    files: dict[str, Any] = {}
    for path, _ in coverage_gate.SURFACE:
        covered, statements = counts.get(path, (100, 100))
        files[path.replace("/", separator)] = summary(covered, statements)
    for path, (covered, statements) in (extra or {}).items():
        files[path.replace("/", separator)] = summary(covered, statements)
    covered_total = sum(entry["summary"]["covered_lines"] for entry in files.values())
    statement_total = sum(
        entry["summary"]["num_statements"] for entry in files.values()
    )
    return {
        "files": files,
        "totals": {
            "covered_lines": covered_total,
            "num_statements": statement_total,
        },
    }


def test_a_fully_covered_surface_passes(tmp_path: Path) -> None:
    """The green case, so that every red case below is red for its own reason."""
    path = write(tmp_path, report())
    assert coverage_gate.main(["coverage_gate", str(path)]) == 0


def test_a_missing_report_is_an_error_and_not_a_pass(tmp_path: Path) -> None:
    """Nothing was measured, so nothing can be judged."""
    absent = tmp_path / "coverage.json"
    assert coverage_gate.main(["coverage_gate", str(absent)]) == 2


def test_an_unparsable_report_is_an_error_and_not_a_pass(tmp_path: Path) -> None:
    """A truncated or half-written report is a run that did not finish."""
    path = tmp_path / "coverage.json"
    path.write_text('{"files": {"src/eichstelle/record/rec', encoding="utf-8")
    assert coverage_gate.main(["coverage_gate", str(path)]) == 2


def test_a_report_that_is_not_an_object_is_an_error(tmp_path: Path) -> None:
    """Valid JSON is not the same thing as a coverage report."""
    path = write(tmp_path, [1, 2, 3])
    assert coverage_gate.main(["coverage_gate", str(path)]) == 2


def test_a_report_with_no_per_file_section_is_an_error(tmp_path: Path) -> None:
    """A report shaped like something else entirely."""
    path = write(tmp_path, {"totals": {"covered_lines": 1, "num_statements": 1}})
    assert coverage_gate.main(["coverage_gate", str(path)]) == 2


def test_a_surface_that_matched_zero_lines_is_an_error(tmp_path: Path) -> None:
    """The case this gate exists to survive.

    A rename empties the surface. Nothing is measured, the average of nothing is
    not a failure, and a gate that treats that as satisfied has stopped working
    without telling anyone.
    """
    document = report()
    document["files"] = {
        path.replace("src/eichstelle/", "src/eichstelle/renamed/"): entry
        for path, entry in document["files"].items()
    }
    path = write(tmp_path, document)
    assert coverage_gate.main(["coverage_gate", str(path)]) == 2


def test_a_surface_present_but_holding_no_statement_is_an_error(
    tmp_path: Path,
) -> None:
    """Every surface module in the report, and not an executable line between them.

    This is the same failure as the rename above arriving by a different route,
    and the two take different branches, so both are here.
    """
    empty = {path: (0, 0) for path, _ in coverage_gate.SURFACE}
    path = write(tmp_path, report(surface=empty))
    assert coverage_gate.main(["coverage_gate", str(path)]) == 2


def test_a_module_on_neither_list_stops_the_gate(tmp_path: Path) -> None:
    """A module nobody placed is a module whose coverage nobody decided about."""
    path = write(tmp_path, report(extra={"src/eichstelle/verdicts/new.py": (0, 40)}))
    assert coverage_gate.main(["coverage_gate", str(path)]) == 2


def test_a_package_init_needs_no_placement(tmp_path: Path) -> None:
    """Re-export shims are outside the bar by name, and do not stop the gate."""
    path = write(
        tmp_path, report(extra={"src/eichstelle/verdicts/__init__.py": (2, 2)})
    )
    assert coverage_gate.main(["coverage_gate", str(path)]) == 0


def test_paths_written_with_the_other_platforms_separator_still_match(
    tmp_path: Path,
) -> None:
    """The same tree measured on Windows and on Linux is the same surface.

    Without this the surface is empty on exactly one of the two platforms, which
    the check above would then report as a rename, so the gate would fail for a
    reason that has nothing to do with coverage.
    """
    path = write(tmp_path, report(separator="\\"))
    assert coverage_gate.main(["coverage_gate", str(path)]) == 0


def test_a_surface_below_the_threshold_is_refused(tmp_path: Path) -> None:
    """The gate's own subject: a real measurement that is not good enough."""
    thin = {path: (50, 100) for path, _ in coverage_gate.SURFACE}
    path = write(tmp_path, report(surface=thin))
    assert coverage_gate.main(["coverage_gate", str(path)]) == 1


def test_the_threshold_is_a_floor_and_not_a_ceiling(tmp_path: Path) -> None:
    """Coverage exactly at the threshold passes.

    The near-miss is the comparison operator. A gate written with `>` instead of
    `>=` refuses the tree that is precisely as good as the number it holds,
    which is the tree the threshold was measured from.
    """
    statements = 10000
    covered = int(coverage_gate.THRESHOLD * statements / 100)
    at_the_line = {path: (0, 0) for path, _ in coverage_gate.SURFACE}
    first = coverage_gate.SURFACE[0][0]
    at_the_line[first] = (covered, statements)
    path = write(tmp_path, report(surface=at_the_line))
    assert coverage_gate.main(["coverage_gate", str(path)]) == 0


def test_counting_is_per_line_and_not_an_average_of_modules(tmp_path: Path) -> None:
    """The fixture where the two counting rules disagree.

    Four small modules fully covered and one large module barely covered. The
    average of the five percentages clears the threshold; the line count over
    the whole surface does not. A gate averaging per-module percentages passes
    this report, and this project's largest uncovered module would be hiding
    behind four small ones.
    """
    surface = {path: (5, 5) for path, _ in coverage_gate.SURFACE}
    largest = coverage_gate.SURFACE[-1][0]
    surface[largest] = (850, 1000)

    percentages = [
        Decimal(covered) * 100 / Decimal(statements)
        for covered, statements in surface.values()
    ]
    average = sum(percentages) / len(percentages)
    assert average > coverage_gate.THRESHOLD, (
        "the average has to pass, or this proves nothing"
    )

    path = write(tmp_path, report(surface=surface))
    assert coverage_gate.main(["coverage_gate", str(path)]) == 1


def test_the_whole_repository_number_is_reported_and_not_enforced(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A tree whose surface is covered and whose whole is not still passes."""
    document = report()
    document["totals"] = {"covered_lines": 1, "num_statements": 1000}
    path = write(tmp_path, document)
    assert coverage_gate.main(["coverage_gate", str(path)]) == 0
    printed = capsys.readouterr().out
    assert "Reported, not enforced." in printed
    assert "1/1000" in printed


def test_unreadable_totals_stop_the_gate(tmp_path: Path) -> None:
    """The unenforced number is still read strictly.

    Printing a figure out of a section nobody checked is how a number with no
    basis ends up quoted back at this project.
    """
    document = report()
    document["totals"] = {"covered_lines": "many", "num_statements": 1000}
    path = write(tmp_path, document)
    assert coverage_gate.main(["coverage_gate", str(path)]) == 2


def test_every_surface_and_exclusion_entry_names_a_tracked_module() -> None:
    """Both lists are checked against the tree, in both directions.

    A list naming a module that no longer exists reads as a decision somebody
    took about code that is not there, and the surface half of that is what
    empties the bar. This is the assertion that catches it in the suite rather
    than in a red gate on somebody else's pull request.
    """
    root = Path(__file__).resolve().parents[2]
    for path, reason in (*coverage_gate.SURFACE, *coverage_gate.EXCLUDED):
        assert (root / path).is_file(), f"{path} is on a list and not in the tree"
        assert reason.strip(), f"{path} is listed with no reason beside it"


def test_every_module_in_the_package_is_on_one_of_the_two_lists() -> None:
    """The placement check above, run against this tree rather than a fixture.

    The gate refuses an unplaced module when it reads a report. This asserts the
    tree has none right now, so a module added without a placement is a red
    suite on the pull request that adds it rather than a red gate later.
    """
    root = Path(__file__).resolve().parents[2]
    placed = {path for path, _ in coverage_gate.SURFACE}
    placed |= {path for path, _ in coverage_gate.EXCLUDED}
    present = {
        module.relative_to(root).as_posix()
        for module in (root / "src" / "eichstelle").rglob("*.py")
        if module.name != coverage_gate.PACKAGE_INIT
    }
    assert present - placed == set()
