"""Reading two records and saying what moved between them."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Final

from eichstelle.record import Record

# The three things this can conclude, as process exit codes. A caller scripting
# this needs to tell "nothing moved" from "something moved" without reading the
# text, and both of those from "I could not compare these at all". Collapsing
# the last into either of the first two is how a refusal becomes a silent pass.
NO_CHANGE: Final = 0
CHANGED: Final = 1
INCOMPARABLE: Final = 2

# How far a margin may move without being reported, when a caller names no
# threshold. Zero would report every last-place difference in a decimal string
# and bury the drifts worth seeing.
DEFAULT_MARGIN_THRESHOLD: Final = Decimal("0.01")

# The three shapes of change, kept apart because they call for different
# responses. A verdict that moved is a result. A margin that moved without the
# verdict is a warning. A pair that appeared or vanished is a question about the
# fixture set rather than about any implementation.
VERDICT_CHANGE: Final = "verdict"
MARGIN_DRIFT: Final = "margin"
ADDED: Final = "added"
REMOVED: Final = "removed"

# The header fields that describe where a run happened. A difference in any of
# them does not stop a comparison, and is stated in the output, because it is
# one of the explanations a reader has to consider for anything that moved.
ENVIRONMENT_FIELDS: Final = (
    "platform",
    "operating_system",
    "operating_system_version",
    "architecture",
    "interpreter_version",
)


class Incomparable(Exception):
    """The two records are not about the same thing, so nothing is compared.

    Raised rather than returned. A caller that has to remember to check a flag
    is a caller that will one day print a difference between two fixture sets as
    if it were a difference between two runs.
    """


@dataclass(frozen=True)
class Change:
    """One thing that moved, and enough to say what it was."""

    kind: str
    fixture_id: str
    adapter: str
    before: str
    after: str
    detail: str = ""


@dataclass(frozen=True)
class Comparison:
    """What moved between two runs, and what a reader has to know to read it."""

    changes: tuple[Change, ...]
    environment_differences: tuple[str, ...]
    threshold: Decimal

    @property
    def status(self) -> int:
        """The exit code this comparison implies."""
        return CHANGED if self.changes else NO_CHANGE


def _key(entry: Mapping[str, Any]) -> tuple[str, str]:
    """What identifies a pair across two runs.

    The fixture and the adapter, and not the revision. A fixture whose revision
    moved is the same pair measured against a corrected stimulus, and that is
    exactly the case somebody comparing two runs wants to see rather than have
    reported as one pair removed and another added.
    """
    return str(entry.get("fixture_id", "")), str(entry.get("adapter", ""))


def _label(key: tuple[str, str]) -> str:
    """A pair, for a message."""
    return f"{key[0]} against {key[1]}"


def _margin(entry: Mapping[str, Any]) -> Decimal | None:
    """The margin as a number, or None where the entry carries none.

    A margin that is present and unreadable is treated as absent rather than
    guessed at. The record's schema admits only decimal strings there, so this
    is the case where somebody hand-edited a record.
    """
    value = entry.get("margin")
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def _fixtures_in(record: Record) -> set[str]:
    """Every fixture identifier the record's entries name."""
    return {str(entry.get("fixture_id", "")) for entry in record.entries}


def _refuse_on_fixture_set(before: Record, after: Record) -> None:
    """Refuse two records made against different fixture sets, and say which.

    Naming the fixtures rather than the checksums is the whole point. A reader
    told that two checksums differ knows only that something did; a reader told
    which fixtures are on one side and not the other can see immediately whether
    the set grew, shrank, or was replaced.
    """
    earlier = str(before.header.get("fixture_set_checksum", ""))
    later = str(after.header.get("fixture_set_checksum", ""))
    if earlier == later:
        return

    only_before = sorted(_fixtures_in(before) - _fixtures_in(after))
    only_after = sorted(_fixtures_in(after) - _fixtures_in(before))
    parts = [
        "these two records were made against different fixture sets, so a "
        "difference between them would be a difference between stimuli",
        f"  before: {earlier or 'no checksum'}",
        f"  after:  {later or 'no checksum'}",
    ]
    if only_before:
        parts.append(f"  only in the earlier run: {', '.join(only_before)}")
    if only_after:
        parts.append(f"  only in the later run:  {', '.join(only_after)}")
    if not only_before and not only_after:
        parts.append(
            "  the same fixture identifiers are in both, so what moved is "
            "inside a fixture rather than the list of them"
        )
    raise Incomparable("\n".join(parts))


def _environment_differences(before: Record, after: Record) -> tuple[str, ...]:
    """Where the two runs happened, wherever that is not the same place.

    Stated rather than refused. A platform difference is a legitimate thing to
    compare across, and it is also one of the first explanations for anything
    that moved, so a report that dropped it would be hiding the answer.
    """
    lines = []
    for field in ENVIRONMENT_FIELDS:
        earlier = str(before.header.get(field, ""))
        later = str(after.header.get(field, ""))
        if earlier != later:
            lines.append(f"{field.replace('_', ' ')}: {earlier} then {later}")
    return tuple(lines)


def compare_records(
    before: Record,
    after: Record,
    *,
    margin_threshold: Decimal = DEFAULT_MARGIN_THRESHOLD,
) -> Comparison:
    """What moved between two runs.

    Raises `Incomparable` where the two are not about the same fixture set.
    """
    if margin_threshold < 0:
        raise ValueError(
            f"the margin threshold is {margin_threshold}, and a negative "
            f"threshold reports every pair as having drifted"
        )
    _refuse_on_fixture_set(before, after)

    earlier = {_key(entry): entry for entry in before.entries}
    later = {_key(entry): entry for entry in after.entries}

    changes: list[Change] = []
    for key in sorted(earlier.keys() - later.keys()):
        entry = earlier[key]
        changes.append(
            Change(
                kind=REMOVED,
                fixture_id=key[0],
                adapter=key[1],
                before=str(entry.get("verdict", "")),
                after="",
                detail=f"{_label(key)} ran in the earlier record and not in the later",
            )
        )
    for key in sorted(later.keys() - earlier.keys()):
        entry = later[key]
        changes.append(
            Change(
                kind=ADDED,
                fixture_id=key[0],
                adapter=key[1],
                before="",
                after=str(entry.get("verdict", "")),
                detail=f"{_label(key)} ran in the later record and not in the earlier",
            )
        )

    for key in sorted(earlier.keys() & later.keys()):
        was = earlier[key]
        now = later[key]
        before_verdict = str(was.get("verdict", ""))
        after_verdict = str(now.get("verdict", ""))
        if before_verdict != after_verdict:
            changes.append(
                Change(
                    kind=VERDICT_CHANGE,
                    fixture_id=key[0],
                    adapter=key[1],
                    before=before_verdict,
                    after=after_verdict,
                    detail=f"{_label(key)}: {before_verdict} then {after_verdict}",
                )
            )
            continue

        was_margin = _margin(was)
        now_margin = _margin(now)
        if was_margin is None or now_margin is None:
            continue
        movement = now_margin - was_margin
        if abs(movement) > margin_threshold:
            direction = "further inside" if movement > 0 else "closer to the edge"
            changes.append(
                Change(
                    kind=MARGIN_DRIFT,
                    fixture_id=key[0],
                    adapter=key[1],
                    before=str(was_margin),
                    after=str(now_margin),
                    detail=(
                        f"{_label(key)}: still {after_verdict}, margin moved "
                        f"{movement:+} and is {direction}"
                    ),
                )
            )

    return Comparison(
        changes=tuple(changes),
        environment_differences=_environment_differences(before, after),
        threshold=margin_threshold,
    )


def _section(title: str, lines: Sequence[str]) -> list[str]:
    """One section, present whether or not it has anything in it."""
    out = [f"{title} ({len(lines)})", "-" * len(title)]
    out.extend(lines or ["none"])
    out.append("")
    return out


def render(comparison: Comparison) -> str:
    """What moved, as text.

    Every section is present at zero for the same reason the report's categories
    are: a section that disappears when empty is one a reader stops looking for.
    """
    out: list[str] = ["what moved between these two runs", "=" * 33, ""]

    if comparison.environment_differences:
        out.append("These runs did not happen in the same place.")
        out.extend(f"  {line}" for line in comparison.environment_differences)
        out.append("A difference here is one of the explanations for anything below.")
    else:
        out.append("Both runs report the same platform and interpreter.")
    out.append("")

    for title, kind in (
        ("Verdicts that moved", VERDICT_CHANGE),
        (f"Margins that drifted by more than {comparison.threshold}", MARGIN_DRIFT),
        ("Pairs added", ADDED),
        ("Pairs no longer run", REMOVED),
    ):
        out.extend(
            _section(
                title,
                [change.detail for change in comparison.changes if change.kind == kind],
            )
        )

    out.append(
        f"{len(comparison.changes)} change(s)."
        if comparison.changes
        else "Nothing moved."
    )
    return "\n".join(out)
