"""The coverage bar on the verdict surface.

Issue #47 argues the shape and `docs/quality-parity.md` is where it is matched
against the target board. The short version: a bar over the whole tree is
satisfied by covering the easy parts, and a bar over nothing is a report. So the
bar sits on the code that can produce a wrong verdict without anyone noticing,
and the rest of the tree is measured and printed without being enforced.

The surface and the deliberate exclusions are both named below, each with the
reason it is where it is. A module that is on neither list stops this gate,
because a module nobody placed is a module whose coverage nobody decided to care
about, and the drift that produces is silent.

Counting is per executable line across the whole surface, never an average of
per-module percentages. Those two numbers differ, and they differ in the
direction that matters: one large uncovered module hides behind several small
covered ones under an average and does not hide here. The suite in
`tests/unit/test_coverage_gate.py` carries a fixture where the average passes
and the line count fails, so the difference is proven rather than asserted.

It fails closed. A report that is absent, a report that cannot be parsed, and a
surface that matched no executable line at all are all errors rather than
passes. The last of those is the one worth stating twice: a rename that empties
the surface leaves a gate that measures nothing and reports green, and a gate
that has stopped working without saying so is worse than no gate.

Exit codes:

    0   the surface is covered at or above the threshold
    1   the surface is covered below the threshold
    2   the measurement could not be read, so the result is unknown

Produce the report and run it:

    python -m coverage run --source=src/eichstelle -m pytest
    python -m coverage json -o coverage.json
    python tools/coverage_gate.py coverage.json
"""

from __future__ import annotations

import json
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any, Final

# Where the report is looked for when no path is given, relative to wherever the
# script was invoked. `coverage json` writes here by default.
DEFAULT_REPORT: Final = "coverage.json"

# The threshold, as a percentage of executable lines across the whole surface.
#
# It is not a round number chosen in advance, because a round number chosen in
# advance is either unreachable and gets lowered or trivial and gets ignored. It
# comes from the first honest measurement of this surface, which was 96.80 per
# cent, and the pull request that landed this gate carries that measurement and
# the command that produced it.
#
# The gap between the measurement and the number below is 0.3 of a percentage
# point and it is a margin rather than slack. The measurement was taken on one
# platform, and two tests in this suite behave differently on another: one is
# skipped where the signal sequence it needs does not exist, and one fails
# there for a reason that predates this gate. Neither reaches the surface, so
# the expected difference is small, and 0.3 is what covers a small difference
# without covering a real regression.
THRESHOLD: Final = Decimal("96.5")

# The verdict surface. Modules are named one by one rather than by a glob, so
# that a module which moves or is renamed drops out of this list and is refused
# by the placement check below instead of quietly leaving the surface.
#
# The list is issue #47's, in this tree's paths, plus `compare/differential.py`,
# which did not exist when that issue was written and belongs to the same
# family: it evaluates a fixture's band against a spread of observations, which
# is a tolerance evaluation under another name. `[tool.mutmut] only_mutate` in
# pyproject.toml already names the whole of `compare/`, so the two questions
# asked about this surface - was the line run, and would anything have noticed
# if it were wrong - are asked about the same code.
SURFACE: Final[tuple[tuple[str, str], ...]] = (
    (
        "src/eichstelle/capabilities/declaration.py",
        "the capability matching that decides unsupported, and the mapping from "
        "an adapter's outcome to a verdict",
    ),
    (
        "src/eichstelle/compare/comparator.py",
        "the comparator and its tolerance evaluation",
    ),
    (
        "src/eichstelle/compare/differential.py",
        "the spread between implementations and the band it is tested against",
    ),
    (
        "src/eichstelle/fixtures/checksums.py",
        "the signal checksums, which decide whether a run proceeds at all. A "
        "verification that passes when it should not is silent, and what comes "
        "out of the run it let through is a false finding about somebody's "
        "implementation, which is the harm this surface is drawn around",
    ),
    (
        "src/eichstelle/record/record.py",
        "the record writer, which is this project's primary output",
    ),
    (
        "src/eichstelle/report/render.py",
        "the report renderer, which is what a person reads",
    ),
)

# Named, and deliberately outside the bar. An exclusion with no reason beside it
# is an exclusion nobody has to defend, so every entry here carries one.
EXCLUDED: Final[tuple[tuple[str, str], ...]] = (
    (
        "src/eichstelle/cli.py",
        "the command-line surface, covered by its own tests and where a mistake "
        "is visible to whoever typed the command",
    ),
    (
        "src/eichstelle/fixtures/__main__.py",
        "the fixture validator's command-line surface, same reason as cli.py",
    ),
    (
        "src/eichstelle/fixtures/validator.py",
        "a refusal that is wrong is loud: a fixture is either accepted or named "
        "in the output, so a defect here does not pass silently the way a wrong "
        "verdict does",
    ),
    (
        "src/eichstelle/runner/runner.py",
        "process handling rather than judgement, and its branches differ by "
        "operating system, so a line bar over it would measure the platform the "
        "gate happens to run on",
    ),
    (
        "src/eichstelle/runs/__main__.py",
        "the run-comparison command-line surface, same reason as cli.py",
    ),
    (
        "src/eichstelle/runs/compare.py",
        "it reads two finished records and reports what moved between them, so a "
        "defect misstates a difference between two of this project's own runs "
        "rather than producing a verdict about somebody's implementation. "
        "Widening the surface to include it is a decision to argue on an issue",
    ),
    (
        "src/eichstelle/signals/generator.py",
        "covered by property tests asserting measured properties of its output "
        "against docs/calibration.md, where a line count is a poor proxy for "
        "correctness",
    ),
    (
        "src/eichstelle/signals/noise.py",
        "the same, for the noise generators",
    ),
)

# Package `__init__.py` files are outside the bar without being listed one by
# one. They carry re-exports, and what they re-export is judged above or below
# on its own.
#
# The bound is worth stating rather than discovering: this rule is by file name,
# so logic moved into an `__init__.py` leaves the surface without appearing in
# any diff to this file. Nothing here refuses that, and a reviewer is what
# stands between it and the tree.
PACKAGE_INIT: Final = "__init__.py"

# What the placement check reads. Anything in the report under this prefix is
# required to be on one of the two lists above or to be a package `__init__.py`.
PACKAGE_PREFIX: Final = "src/eichstelle/"


class GateError(Exception):
    """The measurement could not be read. Raising this is how the gate fails closed."""


def normalise(path: str) -> str:
    """Return a report path with forward slashes.

    `coverage json` writes the separator of the platform it ran on, so the same
    tree produces `src\\eichstelle\\record\\record.py` on one runner and
    `src/eichstelle/record/record.py` on another. Comparing the raw strings
    would make the surface empty on exactly one of them, which the surface
    check would then report as a rename.
    """
    return path.replace("\\", "/")


def load(report_path: Path) -> dict[str, Any]:
    """Read the coverage report, raising rather than defaulting on anything wrong."""
    try:
        raw = report_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise GateError(
            f"there is no coverage report at {report_path}. "
            "Nothing was measured, so nothing can be judged"
        ) from exc
    except OSError as exc:
        raise GateError(f"{report_path} could not be read: {exc}") from exc
    try:
        document = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise GateError(f"{report_path} is not JSON: {exc}") from exc
    if not isinstance(document, dict):
        raise GateError(f"{report_path} is not a JSON object")
    return document


def files_of(document: dict[str, Any], report_path: Path) -> dict[str, Any]:
    """Return the per-file section of the report, keyed by a normalised path."""
    files = document.get("files")
    if not isinstance(files, dict):
        raise GateError(f"{report_path} carries no per-file section to read")
    return {normalise(str(path)): entry for path, entry in files.items()}


def counts_of(path: str, entry: Any) -> tuple[int, int]:
    """Return the covered and executable line counts for one reported file."""
    if not isinstance(entry, dict):
        raise GateError(f"the entry for {path} is not an object")
    summary = entry.get("summary")
    if not isinstance(summary, dict):
        raise GateError(f"the entry for {path} carries no summary")
    covered = summary.get("covered_lines")
    statements = summary.get("num_statements")
    if not isinstance(covered, int) or not isinstance(statements, int):
        raise GateError(
            f"the summary for {path} does not carry integer line counts, "
            f"so its coverage is unknown"
        )
    return covered, statements


def totals_of(document: dict[str, Any], report_path: Path) -> tuple[int, int]:
    """Return the whole-repository line counts the report carries."""
    totals = document.get("totals")
    if not isinstance(totals, dict):
        raise GateError(f"{report_path} carries no totals section to read")
    covered = totals.get("covered_lines")
    statements = totals.get("num_statements")
    if not isinstance(covered, int) or not isinstance(statements, int):
        raise GateError(f"the totals in {report_path} do not carry integer line counts")
    return covered, statements


def check_placement(files: dict[str, Any]) -> None:
    """Refuse a reported module that is on neither list.

    A module nobody placed is a module whose coverage nobody decided about, and
    the way that arrives is somebody adding a file rather than somebody removing
    a line. It stops the gate rather than being counted either way, because both
    defaults are a judgement this script has no business making.
    """
    placed = {path for path, _ in SURFACE} | {path for path, _ in EXCLUDED}
    unplaced = sorted(
        path
        for path in files
        if path.startswith(PACKAGE_PREFIX)
        and not path.endswith(PACKAGE_INIT)
        and path not in placed
    )
    if unplaced:
        raise GateError(
            "these modules are on neither the surface nor the exclusion list in "
            f"{Path(__file__).name}: {', '.join(unplaced)}. Add each one to "
            "whichever list it belongs on, with the reason"
        )


def check_surface_present(files: dict[str, Any]) -> None:
    """Refuse a surface that is not in the report at all."""
    missing = sorted(path for path, _ in SURFACE if path not in files)
    if missing:
        raise GateError(
            "these surface modules are not in the coverage report: "
            f"{', '.join(missing)}. Either the run did not reach them or they "
            "have moved, and a bar over a surface that is not there measures "
            "nothing"
        )


def percentage(covered: int, statements: int) -> Decimal:
    """Return covered lines as a percentage of executable lines."""
    return (Decimal(covered) * 100 / Decimal(statements)).quantize(Decimal("0.01"))


def main(argv: list[str]) -> int:
    """Read the report, judge the surface and return the process exit code."""
    report_path = Path(argv[1] if len(argv) > 1 else DEFAULT_REPORT)
    try:
        document = load(report_path)
        files = files_of(document, report_path)
        check_placement(files)
        check_surface_present(files)

        covered = 0
        statements = 0
        lines: list[str] = []
        for path, reason in SURFACE:
            file_covered, file_statements = counts_of(path, files[path])
            covered += file_covered
            statements += file_statements
            lines.append(f"  {path}  {file_covered}/{file_statements}  {reason}")

        if statements == 0:
            raise GateError(
                "the surface matched zero executable lines. Every module on it "
                "is in the report and none of them has a statement in it, which "
                "is a gate that has stopped working rather than a surface that "
                "is fully covered"
            )
        # The whole-repository number is reported and never enforced, and it is
        # still read strictly: printing a figure out of a section nobody checked
        # is how a number with no basis ends up quoted back.
        whole_covered, whole_statements = totals_of(document, report_path)
    except GateError as exc:
        print(f"the coverage gate did not complete: {exc}", file=sys.stderr)
        print("failing closed: this surface's coverage is unknown", file=sys.stderr)
        return 2

    print("The verdict surface, counted per executable line across the whole")
    print("surface rather than as an average of per-module percentages:")
    print()
    for line in lines:
        print(line)
    print()
    measured = percentage(covered, statements)
    print(f"  surface total  {covered}/{statements}  {measured}%")
    print(f"  threshold      {THRESHOLD}%")
    print()
    print("Deliberately outside the bar:")
    for path, reason in EXCLUDED:
        print(f"  {path}  {reason}")
    print()
    if whole_statements > 0:
        whole = percentage(whole_covered, whole_statements)
        print(
            f"Whole repository: {whole_covered}/{whole_statements}  {whole}%. "
            "Reported, not enforced."
        )
    else:
        print("Whole repository: no executable line reported. Reported, not enforced.")
    print()
    print("The checksum verification issue #47 also names is on the surface as of")
    print("#25. What it holds still is empty: no fixture is tracked, so the module")
    print("is covered by its own suite and by nothing the fixture set contributes.")

    if measured < THRESHOLD:
        print(
            f"the verdict surface is covered at {measured}%, below the "
            f"{THRESHOLD}% this gate holds",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
