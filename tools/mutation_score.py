"""Read the mutation score out of a mutation run, and be loud when there is none.

Issue #48 decides the posture and it is deliberately lopsided. A low score does
not fail anything, because the number moves for reasons that have nothing to do
with test quality - a refactor changes how many mutable points exist, and a
threshold over that produces red runs that teach everybody to ignore the check.
What does have to fail is the tool not producing a score at all. A mutation run
that quietly stopped running leaves a green schedule and a number from months
ago, and the number looks exactly as trustworthy as it did the day it was true.

So this script is the verdict of the mutation workflow and the mutation tool is
not. The workflow runs the tool without letting its exit code decide anything,
and then runs this, which fails when and only when there is no score to read.

What it reads is `mutmut export-cicd-stats` output, which is a small JSON
document of counts. Reading counts rather than parsing a terminal report means
the check does not break the day the report's layout changes, and it means this
script has no opinion about which mutation tool produced them beyond the names
of the keys.

## The score, and what is in its denominator

    score = killed / (killed + survived + no_tests)

Three outcomes are in the denominator because all three answer the question the
measurement exists to ask, which is whether anything would have noticed:

    killed      a test failed, so something noticed
    survived    every test still passed, so nothing noticed
    no_tests    no test covers the mutated code at all, so nothing could notice

`no_tests` is in there rather than set aside. A mutant nothing runs is the
strongest form of "nothing would notice", and a score that quietly dropped those
would rise as coverage fell, which is the wrong direction for a number about
test quality.

Four outcomes are outside the denominator, and they are printed rather than
hidden, because each is a statement about the run rather than about the suite:
a mutant whose tests ran past the time limit, one whose result the tool could
not classify, one it was told to skip, and one that took the interpreter down.
The counts are printed on every run and the total outside the denominator is
printed as its own line, so a score computed over a third of the mutants cannot
be read as one computed over all of them.

## Exit codes

    0   a score was produced, whatever it is
    2   no score could be produced, so the state of the measurement is unknown

There is no exit 1. A low score is not a failure here and giving it a code of
its own would invite somebody to start failing on it.

Run it against the stats a run left behind:

    python tools/mutation_score.py mutants/mutmut-cicd-stats.json
"""

from __future__ import annotations

import argparse
import json
import sys
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path

# Where `mutmut export-cicd-stats` writes, relative to the directory the run
# happened in. Named here so the workflow and this script cannot drift apart on
# it, and overridable on the command line so a test can point at its own file.
DEFAULT_STATS = "mutants/mutmut-cicd-stats.json"

# The three counts the score is computed from. Every one of them has to be
# present: a document missing one is a document this script cannot compute the
# advertised number from, and computing a different number under the same name
# is the failure mode this whole file exists against.
SCORED = ("killed", "survived", "no_tests")

# The counts that are reported and are not in the denominator. Absent is treated
# as zero for these, because an older or a different producer may not emit all
# of them, and refusing on that would fail a run that has a perfectly good score
# in it.
UNSCORED = ("timeout", "suspicious", "skipped", "segfault")


class NoScore(Exception):
    """Raised when the stats cannot yield a score, whatever the reason."""


def read_stats(path: Path) -> dict[str, int]:
    """Return the counts in the stats document, or raise NoScore."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise NoScore(f"{path} could not be read: {exc}") from exc
    try:
        document = json.loads(text)
    except json.JSONDecodeError as exc:
        raise NoScore(f"{path} is not JSON: {exc}") from exc
    if not isinstance(document, dict):
        raise NoScore(f"{path} holds {type(document).__name__} rather than an object")

    counts: dict[str, int] = {}
    for key in SCORED:
        if key not in document:
            raise NoScore(f"{path} carries no {key!r} count")
        counts[key] = _count(document[key], key, path)
    for key in UNSCORED:
        if key in document:
            counts[key] = _count(document[key], key, path)
        else:
            counts[key] = 0
    return counts


def _count(value: object, key: str, path: Path) -> int:
    """Return value as a count, or raise NoScore saying why it is not one."""
    # bool is a subclass of int and True would silently count as one mutant.
    if isinstance(value, bool) or not isinstance(value, int):
        raise NoScore(f"{path} has {key!r} as {value!r}, which is not a count")
    if value < 0:
        raise NoScore(f"{path} has {key!r} as {value}, which is not a count")
    return value


def score_of(counts: dict[str, int]) -> Decimal:
    """Return the mutation score as a percentage, or raise NoScore."""
    denominator = sum(counts[key] for key in SCORED)
    if denominator == 0:
        raise NoScore(
            "no mutant reached a killed, survived or uncovered outcome, "
            "so there is nothing to compute a score over"
        )
    fraction = Decimal(counts["killed"]) / Decimal(denominator) * Decimal(100)
    return fraction.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)


def lines(counts: dict[str, int], score: Decimal) -> list[str]:
    """Return what a reader is told about the run, one line at a time."""
    denominator = sum(counts[key] for key in SCORED)
    outside = sum(counts[key] for key in UNSCORED)
    reported = [
        f"mutation score: {score}%",
        f"killed {counts['killed']} of {denominator} scored mutant(s)",
    ]
    reported += [f"    {key.replace('_', ' ')}: {counts[key]}" for key in SCORED]
    reported += [f"    {key}: {counts[key]}" for key in UNSCORED]
    reported.append(
        f"{outside} mutant(s) are outside the denominator: a timeout, an "
        f"unclassifiable result, a skip and a segfault are statements about the "
        f"run rather than about the suite."
    )
    reported.append(
        "This score gates nothing. Issue #48 decides that, and the reason is "
        "that the number moves with refactoring rather than with test quality."
    )
    return reported


def main(argv: list[str] | None = None) -> int:
    """Read the stats and return the process exit code."""
    parser = argparse.ArgumentParser(
        description="Read the mutation score, and fail when there is none.",
    )
    parser.add_argument(
        "stats",
        nargs="?",
        default=DEFAULT_STATS,
        help=f"the stats document a mutation run left behind (default {DEFAULT_STATS})",
    )
    parser.add_argument(
        "--summary",
        default=None,
        help="a file the reported lines are appended to as well as printed",
    )
    arguments = parser.parse_args(argv)

    try:
        counts = read_stats(Path(arguments.stats))
        score = score_of(counts)
    except NoScore as exc:
        print(f"no mutation score: {exc}", file=sys.stderr)
        print(
            "The mutation run did not produce a score. That is a broken tool "
            "rather than a low number, and it is loud on purpose: a run that "
            "stops running leaves the last score standing and looks green.",
            file=sys.stderr,
        )
        return 2

    reported = lines(counts, score)
    for line in reported:
        print(line)
    if arguments.summary is not None:
        with Path(arguments.summary).open("a", encoding="utf-8") as handle:
            handle.write("\n".join(reported) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
