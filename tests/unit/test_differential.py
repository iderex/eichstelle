"""The differential mode, and the things it must never do.

Half of these tests are about a number and half are about an absence. The
absences are the ones worth reading first: no code path here elects a value, and
a fixture that produced fewer than two usable answers is never reported as
agreement. Both are properties of the module rather than of any one call, so
they are asserted as properties.
"""

from __future__ import annotations

import ast
from dataclasses import fields
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from eichstelle.compare import (
    AGREEMENT,
    DISAGREEMENT,
    FEWER_THAN_TWO_USABLE,
    NO_DECLARED_BAND,
    NO_OUTCOME,
    NOT_A_NUMBER,
    NOTHING_PRODUCED,
    SERIES_NOT_REDUCED,
    UNIT_NOT_THE_FIXTURES,
    Differential,
    DifferentialError,
    Observation,
    differential,
    observations_from_entries,
)

MODULE = Path(__file__).resolve().parents[2] / "src" / "eichstelle" / "compare"


def fixture(**overrides: Any) -> dict[str, Any]:
    """A fixture with an absolute band of one tenth of a sone."""
    document: dict[str, Any] = {
        "id": "loudness-anchor-1khz-40db",
        "unit": "sone",
        "expected": "1.0",
        "tolerance": "0.1",
        "tolerance_kind": "absolute",
    }
    document.update(overrides)
    return document


def answered(adapter: str, value: str, *, unit: str = "sone") -> Observation:
    """One adapter's single-valued answer."""
    return Observation(
        adapter=adapter, upstream_version="1.2.3", values=(value,), unit=unit
    )


def test_three_adapters_that_agree_are_reported_as_agreement() -> None:
    """A spread inside the fixture's band is a result worth recording as one."""
    result = differential(
        fixture(),
        [answered("a", "1.00"), answered("b", "1.02"), answered("c", "1.05")],
    )
    assert result.outcome == AGREEMENT
    assert result.low == Decimal("1.00")
    assert result.high == Decimal("1.05")
    assert result.spread == Decimal("0.05")
    assert result.band == Decimal("0.1")
    assert result.exceeds_tolerance is False


def test_a_slight_disagreement_is_reported_with_its_spread() -> None:
    """Just outside the band is a disagreement, and the number says by how much."""
    result = differential(fixture(), [answered("a", "1.00"), answered("b", "1.11")])
    assert result.outcome == DISAGREEMENT
    assert result.spread == Decimal("0.11")
    assert result.exceeds_tolerance is True


def test_a_gross_disagreement_is_the_same_shape_and_a_larger_number() -> None:
    """Nothing about a large disagreement is a different kind of result."""
    result = differential(
        fixture(),
        [answered("a", "1.00"), answered("b", "1.02"), answered("c", "42.0")],
    )
    assert result.outcome == DISAGREEMENT
    assert result.spread == Decimal("41.0")
    assert result.relative_spread == Decimal("41.0") / Decimal("1.00")


def test_a_spread_exactly_the_width_of_the_band_agrees() -> None:
    """The boundary is inclusive, as it is in the comparator.

    A fixture's tolerance is a number the fixture chose, and excluding its own
    endpoint would make the declared number mean slightly less than it says.
    """
    result = differential(fixture(), [answered("a", "1.00"), answered("b", "1.10")])
    assert result.spread == result.band
    assert result.outcome == AGREEMENT


def test_the_relative_spread_is_measured_against_the_smallest_value() -> None:
    """The denominator is the smallest value and nothing derived from the set."""
    result = differential(fixture(), [answered("a", "2.0"), answered("b", "2.5")])
    assert result.relative_spread == Decimal("0.5") / Decimal("2.0")


def test_there_is_no_relative_spread_where_the_smallest_value_is_not_positive() -> None:
    """A ratio against zero is absent rather than filled in.

    Zero would read as no disagreement and an infinity would read as a total
    one, and neither is what a spread against a zero baseline means.
    """
    result = differential(
        fixture(expected="0.0", tolerance="0.5"),
        [answered("a", "0.0"), answered("b", "0.4")],
    )
    assert result.spread == Decimal("0.4")
    assert result.relative_spread is None


def test_one_usable_result_produces_no_outcome_and_is_not_agreement() -> None:
    """One implementation agreeing with itself is not a measurement."""
    result = differential(fixture(), [answered("a", "1.0")])
    assert result.outcome == NO_OUTCOME
    assert result.reason == FEWER_THAN_TWO_USABLE
    assert result.outcome != AGREEMENT
    assert result.spread is None


def test_no_results_at_all_produce_no_outcome() -> None:
    """A fixture nothing answered is a coverage statement, not agreement."""
    result = differential(fixture(), [])
    assert result.outcome == NO_OUTCOME
    assert result.reason == FEWER_THAN_TWO_USABLE


def test_two_answers_one_of_which_is_unusable_produce_no_outcome() -> None:
    """Usable is counted after the unusable ones have been taken out."""
    result = differential(
        fixture(),
        [answered("a", "1.0"), Observation("b", "9", (), "sone")],
    )
    assert result.outcome == NO_OUTCOME
    assert result.reason == FEWER_THAN_TWO_USABLE
    assert [entry.reason for entry in result.unusable] == [NOTHING_PRODUCED]


def test_a_series_is_not_reduced_and_says_so() -> None:
    """Which statistic of a series is compared is the fixture's to declare."""
    result = differential(
        fixture(),
        [answered("a", "1.0"), Observation("b", "9", ("1.0", "1.1"), "sone")],
    )
    assert [entry.reason for entry in result.unusable] == [SERIES_NOT_REDUCED]


def test_an_answer_in_another_unit_is_not_converted() -> None:
    """Deciding two unit spellings mean one quantity is a judgement, not a step."""
    result = differential(
        fixture(),
        [answered("a", "1.0"), answered("b", "1.0", unit="phon")],
    )
    assert [entry.reason for entry in result.unusable] == [UNIT_NOT_THE_FIXTURES]


def test_an_answer_that_is_not_a_number_does_not_remove_the_others() -> None:
    """One adapter's malformed answer is a statement about that adapter."""
    result = differential(
        fixture(),
        [answered("a", "1.0"), answered("b", "1.02"), answered("c", "not-a-number")],
    )
    assert result.outcome == AGREEMENT
    assert [entry.reason for entry in result.unusable] == [NOT_A_NUMBER]
    assert [entry.observation.adapter for entry in result.usable] == ["a", "b"]


def test_an_infinity_is_not_a_number_here_either() -> None:
    """`Decimal` parses Infinity, and arithmetic on it reads as a finding."""
    result = differential(fixture(), [answered("a", "1.0"), answered("b", "Infinity")])
    assert [entry.reason for entry in result.unusable] == [NOT_A_NUMBER]
    assert result.outcome == NO_OUTCOME


def test_a_relative_band_is_resolved_against_the_fixture_never_the_answers() -> None:
    """The band comes from the expected value the fixture declared."""
    result = differential(
        fixture(expected="10.0", tolerance="0.05", tolerance_kind="relative"),
        [answered("a", "1.0"), answered("b", "1.4")],
    )
    # Five per cent of the fixture's ten, not five per cent of anything answered.
    assert result.band == Decimal("0.500")
    assert result.outcome == AGREEMENT


def test_a_fixture_with_no_expected_value_reports_the_spread_and_no_verdict() -> None:
    """A spread still exists; whether it is too large is a question with no answer.

    Schema version 1 requires an expected value on every fixture, so this is the
    forward case rather than one a validated fixture reaches today. Issue #30 is
    where a fixture with no available target value is argued.
    """
    document = fixture()
    del document["expected"]
    result = differential(document, [answered("a", "1.0"), answered("b", "9.0")])
    assert result.spread == Decimal("8.0")
    assert result.band is None
    assert result.exceeds_tolerance is None
    assert result.outcome == NO_OUTCOME
    assert result.reason == NO_DECLARED_BAND


def test_a_fixture_with_no_identifier_is_refused() -> None:
    """A spread nobody can name is not a result anybody can cite."""
    document = fixture()
    del document["id"]
    with pytest.raises(DifferentialError, match="no identifier"):
        differential(document, [answered("a", "1.0"), answered("b", "1.0")])


def test_a_fixture_whose_band_cannot_be_resolved_is_refused() -> None:
    """A relative band against an expected value of zero is a band of zero."""
    with pytest.raises(DifferentialError, match="tolerance cannot be resolved"):
        differential(
            fixture(expected="0", tolerance_kind="relative", tolerance="0.05"),
            [answered("a", "1.0"), answered("b", "1.0")],
        )


def test_the_observations_come_back_in_the_order_they_were_given() -> None:
    """No sort, because a sorted list reads as a ranking."""
    result = differential(
        fixture(),
        [answered("c", "1.05"), answered("a", "1.00"), answered("b", "1.02")],
    )
    assert [entry.observation.adapter for entry in result.usable] == ["c", "a", "b"]


def test_every_value_is_carried_with_its_adapter_and_its_version() -> None:
    """Attribution is the point of the mode, so nothing is reported anonymously."""
    result = differential(
        fixture(),
        [
            Observation("mosqito", "1.2.1", ("1.00",), "sone"),
            Observation("psytools", "", ("1.02",), "sone"),
        ],
    )
    carried = {
        entry.observation.adapter: (entry.observation.upstream_version, entry.value)
        for entry in result.usable
    }
    assert carried == {
        "mosqito": ("1.2.1", Decimal("1.00")),
        "psytools": ("", Decimal("1.02")),
    }


def test_an_unknown_upstream_version_stays_unknown() -> None:
    """The empty string is the declared unknown and is never filled in."""
    result = differential(
        fixture(),
        [Observation("a", "", ("1.0",), "sone"), answered("b", "1.02")],
    )
    assert result.usable[0].observation.upstream_version == ""


def test_the_result_carries_no_field_that_names_a_correct_value() -> None:
    """The absence is asserted rather than assumed.

    A field called `consensus`, `reference`, `winner`, `best` or `truth` is the
    shape this mode is against, and the day somebody adds one this test is where
    the argument happens.
    """
    forbidden = {"consensus", "reference", "winner", "best", "truth", "correct", "rank"}
    named = {field.name for field in fields(Differential)}
    assert not named & forbidden, named & forbidden


def test_no_code_path_in_the_module_computes_a_central_value() -> None:
    """No mean, no median, no mode, no sort, anywhere in the module.

    Read from the source rather than promised in a docstring, because the
    promise is what a reader of this module has to be able to check. `min` and
    `max` are permitted and are the ends of the range; a `sorted` or a
    `statistics` call would be a step towards a value treated as truth.
    """
    source = (MODULE / "differential.py").read_text(encoding="utf-8")
    called = {
        node.func.id
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert not called & {"sorted", "mean", "median", "mode", "fmean"}, called
    assert "statistics" not in imported


def test_a_record_entry_becomes_the_observation_it_was_written_from() -> None:
    """The record is what a later reader aggregates, so it has to round trip."""
    entries: list[dict[str, Any]] = [
        {
            "fixture_id": "loudness-anchor-1khz-40db",
            "adapter": "mosqito",
            "adapter_upstream_version": "1.2.1",
            "produced": ["1.00"],
            "produced_unit": "sone",
        },
        {
            "fixture_id": "loudness-anchor-1khz-40db",
            "adapter": "psytools",
            "adapter_upstream_version": None,
            "produced": [],
            "produced_unit": None,
        },
    ]
    read = observations_from_entries(entries)
    assert read[0] == Observation("mosqito", "1.2.1", ("1.00",), "sone")
    assert read[1] == Observation("psytools", "", (), None)


def test_an_adapter_that_answered_nothing_stays_in_the_spread_as_unusable() -> None:
    """A dropped entry is an adapter that disappears from the report."""
    entries: list[dict[str, Any]] = [
        {
            "adapter": "a",
            "adapter_upstream_version": "1",
            "produced": ["1.0"],
            "produced_unit": "sone",
        },
        {
            "adapter": "b",
            "adapter_upstream_version": "2",
            "produced": ["1.02"],
            "produced_unit": "sone",
        },
        {
            "adapter": "c",
            "adapter_upstream_version": None,
            "produced": [],
            "produced_unit": None,
        },
    ]
    result = differential(fixture(), observations_from_entries(entries))
    assert result.outcome == AGREEMENT
    assert [entry.observation.adapter for entry in result.unusable] == ["c"]
