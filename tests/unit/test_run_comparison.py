"""What moved between two runs, and what it refuses to compare at all.

Six cases the issue names, each built as a one-change neighbour of the same pair
of records: a verdict improving, a verdict regressing, a margin drifting without
the verdict moving, a pair added, a pair removed, and two records that are not
about the same fixture set.

The refusal is the one worth reading twice. Two records made against different
fixture sets can be diffed, and the diff looks exactly like a result, and it is a
comparison of different stimuli. So it is refused rather than reported, and the
refusal names the fixtures rather than the checksums.
"""

from decimal import Decimal
from typing import Any

import pytest

from eichstelle.record import Counts, Record
from eichstelle.runs import (
    CHANGED,
    NO_CHANGE,
    Incomparable,
    compare_records,
    render,
)
from eichstelle.runs.compare import ADDED, MARGIN_DRIFT, REMOVED, VERDICT_CHANGE


def header(**over: Any) -> dict[str, Any]:
    """A header for a run, with the fields a comparison reads."""
    document: dict[str, Any] = {
        "kind": "header",
        "fixture_set_version": "2026.08",
        "fixture_set_checksum": "sha256:same",
        "platform": "Linux-6.8",
        "operating_system": "Linux",
        "operating_system_version": "6.8",
        "architecture": "x86_64",
        "interpreter_version": "3.13.1",
        "possible": 2,
    }
    document.update(over)
    return document


def entry(**over: Any) -> dict[str, Any]:
    """One entry, and the base of every neighbour below."""
    document: dict[str, Any] = {
        "kind": "entry",
        "fixture_id": "anchor-loudness",
        "fixture_revision": 1,
        "adapter": "fake",
        "verdict": "agrees",
        "reason": "",
        "margin": "0.40",
    }
    document.update(over)
    return document


def record(entries: list[dict[str, Any]], **over: Any) -> Record:
    """A finished record holding those entries."""
    fields: dict[str, Any] = {
        "header": header(),
        "entries": tuple(entries),
        "summary": {"kind": "summary", "run_finished": True},
        "counts": Counts(possible=2, attempted=len(entries), produced=len(entries)),
    }
    fields.update(over)
    return Record(**fields)


def kinds(comparison: Any) -> list[str]:
    """The kinds of change, in the order they were reported."""
    return [change.kind for change in comparison.changes]


def test_two_identical_runs_report_nothing() -> None:
    """The case every neighbour below is one change away from."""
    comparison = compare_records(record([entry()]), record([entry()]))

    assert comparison.changes == ()
    assert comparison.status == NO_CHANGE
    assert "Nothing moved." in render(comparison)


def test_a_verdict_improving_is_reported_with_its_direction() -> None:
    """Which way it went, because a report that only says "changed" is a puzzle."""
    comparison = compare_records(
        record([entry(verdict="disagrees", margin="-0.20")]),
        record([entry(verdict="agrees", margin="0.40")]),
    )

    assert kinds(comparison) == [VERDICT_CHANGE]
    assert comparison.changes[0].before == "disagrees"
    assert comparison.changes[0].after == "agrees"
    assert comparison.status == CHANGED


def test_a_verdict_regressing_is_reported_with_its_direction() -> None:
    """The same in the other direction, which is the one somebody is watching for."""
    comparison = compare_records(
        record([entry(verdict="agrees", margin="0.40")]),
        record([entry(verdict="disagrees", margin="-0.20")]),
    )

    assert kinds(comparison) == [VERDICT_CHANGE]
    assert comparison.changes[0].before == "agrees"
    assert comparison.changes[0].after == "disagrees"


def test_a_verdict_change_is_not_also_reported_as_a_margin_drift() -> None:
    """One movement is one change, whatever the margin did alongside it."""
    comparison = compare_records(
        record([entry(verdict="agrees", margin="0.40")]),
        record([entry(verdict="disagrees", margin="-0.20")]),
    )

    assert MARGIN_DRIFT not in kinds(comparison)


def test_a_margin_drifting_without_a_verdict_change_is_the_early_warning() -> None:
    """Comfortably inside to barely inside, which is worth seeing before it crosses."""
    comparison = compare_records(
        record([entry(margin="0.40")]),
        record([entry(margin="0.02")]),
    )

    assert kinds(comparison) == [MARGIN_DRIFT]
    assert comparison.changes[0].before == "0.40"
    assert comparison.changes[0].after == "0.02"
    assert "closer to the edge" in comparison.changes[0].detail


def test_a_margin_movement_under_the_threshold_is_not_reported() -> None:
    """A threshold of zero would bury every drift worth seeing in last places."""
    comparison = compare_records(
        record([entry(margin="0.400")]),
        record([entry(margin="0.399")]),
    )

    assert comparison.changes == ()


def test_the_threshold_is_configurable() -> None:
    """The same pair of records, and a caller who wants to see smaller movements."""
    before = record([entry(margin="0.400")])
    after = record([entry(margin="0.399")])

    assert compare_records(before, after).changes == ()
    assert kinds(
        compare_records(before, after, margin_threshold=Decimal("0.0001"))
    ) == [MARGIN_DRIFT]


def test_a_negative_threshold_is_refused() -> None:
    """It would report every pair as having drifted, which is not a comparison."""
    with pytest.raises(ValueError, match="negative threshold"):
        compare_records(
            record([entry()]), record([entry()]), margin_threshold=Decimal("-1")
        )


def test_a_pair_that_appeared_is_reported_as_added() -> None:
    """Never silently present, because the set growing is worth knowing."""
    comparison = compare_records(
        record([entry()]),
        record([entry(), entry(fixture_id="anchor-sharpness")]),
    )

    assert kinds(comparison) == [ADDED]
    assert comparison.changes[0].fixture_id == "anchor-sharpness"


def test_a_pair_that_stopped_running_is_reported_as_removed() -> None:
    """The one that goes unnoticed for a year if nothing says it."""
    comparison = compare_records(
        record([entry(), entry(fixture_id="anchor-sharpness")]),
        record([entry()]),
    )

    assert kinds(comparison) == [REMOVED]
    assert comparison.changes[0].fixture_id == "anchor-sharpness"
    assert "not in the later" in comparison.changes[0].detail


def test_a_fixture_whose_revision_moved_is_one_pair_and_not_two() -> None:
    """A corrected stimulus is the case somebody comparing two runs came for.

    Keying on the revision as well would report it as one pair removed and
    another added, which hides the verdict movement that is the whole point.
    """
    comparison = compare_records(
        record([entry(fixture_revision=1, verdict="disagrees")]),
        record([entry(fixture_revision=2, verdict="agrees")]),
    )

    assert kinds(comparison) == [VERDICT_CHANGE]


def test_two_different_fixture_sets_are_refused_and_the_fixtures_are_named() -> None:
    """A diff between two fixture sets looks exactly like a result."""
    with pytest.raises(Incomparable) as raised:
        compare_records(
            record([entry(fixture_id="anchor-loudness")]),
            record(
                [entry(fixture_id="anchor-sharpness")],
                header=header(fixture_set_checksum="sha256:different"),
            ),
        )

    message = str(raised.value)
    assert "different fixture sets" in message
    assert "anchor-loudness" in message
    assert "anchor-sharpness" in message


def test_a_changed_checksum_over_the_same_identifiers_says_so() -> None:
    """The case where a fixture was edited rather than added or removed."""
    with pytest.raises(Incomparable) as raised:
        compare_records(
            record([entry()]),
            record([entry()], header=header(fixture_set_checksum="sha256:other")),
        )

    assert "inside a fixture rather than the list of them" in str(raised.value)


def test_a_platform_difference_is_stated_and_does_not_refuse() -> None:
    """Comparable, and one of the explanations a reader has to consider."""
    comparison = compare_records(
        record([entry()]),
        record([entry()], header=header(platform="Windows-11", architecture="arm64")),
    )

    assert comparison.status == NO_CHANGE
    assert any("platform" in line for line in comparison.environment_differences)
    assert any("architecture" in line for line in comparison.environment_differences)
    assert "did not happen in the same place" in render(comparison)


def test_every_section_is_present_even_when_empty() -> None:
    """A section that vanishes when empty is one a reader stops looking for."""
    text = render(compare_records(record([entry()]), record([entry()])))

    for title in (
        "Verdicts that moved (0)",
        "Pairs added (0)",
        "Pairs no longer run (0)",
    ):
        assert title in text
    assert "Margins that drifted by more than 0.01 (0)" in text


def test_an_unreadable_margin_is_treated_as_absent_rather_than_guessed() -> None:
    """A hand-edited record does not become a drift report."""
    comparison = compare_records(
        record([entry(margin="not a number")]),
        record([entry(margin="0.40")]),
    )

    assert comparison.changes == ()
