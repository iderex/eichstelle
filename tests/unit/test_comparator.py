"""What the comparator decides, and everything it refuses to decide.

Issue #39 asks for a table of cases with the expected verdict and margin stated,
including the boundary exactly at the tolerance, one unit inside it and one unit
outside it. That table is `AGREEMENT_CASES` below and it is where the arithmetic
is checked.

"One unit" here means one unit of the last decimal place written, and every
number in the table is exact under `decimal.Decimal`. Under binary floating
point these assertions would be approximate, which would make the boundary cases
prove nothing: a band whose endpoint cannot be represented cannot be landed on.

The second half of the file is the refusals, and the reason there are so many is
that the permissive direction is the expensive one. A comparator that quietly
answers `agrees` for a value it did not understand produces a suite that reports
agreement it never established, and nothing downstream can tell that from the
real thing. So every case issue #39 names is driven through the public entry
point and asserted to leave through `ComparisonError`, and one test walks the
whole list at once to assert that none of them returns a verdict at all.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import pytest

from eichstelle.compare import (
    AGREES,
    COMBINED,
    DISAGREES,
    NON_NEGATIVE_UNITS,
    Comparison,
    ComparisonError,
    Tolerance,
    band_for,
    compare,
    compare_against_fixture,
    tolerance_from_fixture,
)


@dataclass(frozen=True)
class Case:
    """One row of the agreement table."""

    name: str
    tolerance: Tolerance
    expected: str
    produced: str
    verdict: str
    band: str
    margin: str
    # Sone unless the row is about something sone cannot be. A negative value
    # in sone is refused before any band is computed, so the row showing a
    # relative band taking a magnitude has to be in a unit that admits one.
    unit: str = "sone"


# An absolute tolerance of 0.5 sone on 10 sone: the band runs from 9.5 to 10.5
# and both endpoints are in it.
ABSOLUTE_TOLERANCE = Tolerance.absolute("0.5")

# Five per cent of 20 sone is 1 sone, written once as a fraction and once as a
# percentage so that the two spellings are shown to reach the same band rather
# than assumed to.
RELATIVE_TOLERANCE = Tolerance.relative("0.05")
PERCENT_TOLERANCE = Tolerance.percent("5")

# The case record 0007 uses to argue for the combined form: five per cent where
# the quantity is large enough for a fraction to mean something, and a fixed
# 0.01 sone below a floor of 1 sone, because five per cent of 0.02 sone is a
# band no implementation meets and none needs to.
COMBINED_TOLERANCE = Tolerance.combined(fraction="0.05", floor="1", absolute="0.01")

AGREEMENT_CASES = [
    # Absolute, both endpoints and one unit of the last place either side.
    Case(
        "absolute high boundary", ABSOLUTE_TOLERANCE, "10.0", "10.5", AGREES, "0.5", "0"
    ),
    Case(
        "absolute low boundary", ABSOLUTE_TOLERANCE, "10.0", "9.5", AGREES, "0.5", "0"
    ),
    Case(
        "absolute one unit inside the high boundary",
        ABSOLUTE_TOLERANCE,
        "10.0",
        "10.4999999999",
        AGREES,
        "0.5",
        "0.0000000001",
    ),
    Case(
        "absolute one unit outside the high boundary",
        ABSOLUTE_TOLERANCE,
        "10.0",
        "10.5000000001",
        DISAGREES,
        "0.5",
        "-0.0000000001",
    ),
    Case(
        "absolute one unit outside the low boundary",
        ABSOLUTE_TOLERANCE,
        "10.0",
        "9.4999999999",
        DISAGREES,
        "0.5",
        "-0.0000000001",
    ),
    Case("absolute exact", ABSOLUTE_TOLERANCE, "10.0", "10.0", AGREES, "0.5", "0.5"),
    # Relative: the band widens with the quantity, which is the property that
    # makes it the right kind for a level sweep.
    Case(
        "relative high boundary", RELATIVE_TOLERANCE, "20.0", "21.0", AGREES, "1", "0"
    ),
    Case("relative low boundary", RELATIVE_TOLERANCE, "20.0", "19.0", AGREES, "1", "0"),
    Case(
        "relative one unit inside the high boundary",
        RELATIVE_TOLERANCE,
        "20.0",
        "20.9999999999",
        AGREES,
        "1",
        "0.0000000001",
    ),
    Case(
        "relative one unit outside the high boundary",
        RELATIVE_TOLERANCE,
        "20.0",
        "21.0000000001",
        DISAGREES,
        "1",
        "-0.0000000001",
    ),
    Case(
        "relative band widens with the expected value",
        RELATIVE_TOLERANCE,
        "40.0",
        "42.0",
        AGREES,
        "2",
        "0",
    ),
    Case(
        "relative against a negative expected value uses its magnitude",
        RELATIVE_TOLERANCE,
        "-20.0",
        "-21.0",
        AGREES,
        "1",
        "0",
        unit="db",
    ),
    # Percent: the same band as the relative case above, reached by the other
    # spelling the published schema admits.
    Case("percent high boundary", PERCENT_TOLERANCE, "20.0", "21.0", AGREES, "1", "0"),
    Case(
        "percent one unit outside the high boundary",
        PERCENT_TOLERANCE,
        "20.0",
        "21.0000000001",
        DISAGREES,
        "1",
        "-0.0000000001",
    ),
    # Combined, above the floor: the fraction applies and the absolute half is
    # not consulted.
    Case(
        "combined above the floor takes the fraction",
        COMBINED_TOLERANCE,
        "20.0",
        "21.0",
        AGREES,
        "1",
        "0",
    ),
    Case(
        "combined above the floor, one unit outside",
        COMBINED_TOLERANCE,
        "20.0",
        "21.0000000001",
        DISAGREES,
        "1",
        "-0.0000000001",
    ),
    # Combined, at the floor exactly. The fraction applies at the floor itself,
    # so the two halves meet at one stated point rather than leaving a value the
    # tolerance does not describe.
    Case(
        "combined at the floor takes the fraction",
        COMBINED_TOLERANCE,
        "1",
        "1.05",
        AGREES,
        "0.05",
        "0",
    ),
    # Combined, below the floor: the fixed band applies, and it is far wider
    # than the fraction would have been. This is the whole reason the kind
    # exists, and the numbers say so: five per cent of 0.02 is 0.001.
    Case(
        "combined below the floor takes the absolute band",
        COMBINED_TOLERANCE,
        "0.02",
        "0.03",
        AGREES,
        "0.01",
        "0",
    ),
    Case(
        "combined below the floor, one unit outside",
        COMBINED_TOLERANCE,
        "0.02",
        "0.0300000001",
        DISAGREES,
        "0.01",
        "-0.0000000001",
    ),
    Case(
        "combined below the floor, a value the fraction would have refused",
        COMBINED_TOLERANCE,
        "0.02",
        "0.025",
        AGREES,
        "0.01",
        "0.005",
    ),
    # Combined against an expected value of zero. It is answerable because zero
    # is below any floor and the band below the floor is stated rather than
    # scaled, which is exactly the case a bare relative tolerance is refused for.
    Case(
        "combined against zero uses the absolute band",
        COMBINED_TOLERANCE,
        "0",
        "0.01",
        AGREES,
        "0.01",
        "0",
    ),
    Case(
        "combined against zero, one unit outside",
        COMBINED_TOLERANCE,
        "0",
        "0.0100000001",
        DISAGREES,
        "0.01",
        "-0.0000000001",
    ),
]


@pytest.mark.parametrize("case", AGREEMENT_CASES, ids=lambda case: case.name)
def test_the_table_of_cases(case: Case) -> None:
    """Each row reaches its stated verdict, band and margin."""
    result = compare(
        expected=case.expected,
        unit=case.unit,
        tolerance=case.tolerance,
        produced=case.produced,
        produced_unit=case.unit,
    )
    assert result.verdict == case.verdict
    assert result.band == Decimal(case.band)
    assert result.margin == Decimal(case.margin)


def test_the_table_covers_both_verdicts_at_a_boundary() -> None:
    """The table would still pass if it only ever agreed, so check its shape.

    A table of cases is only worth what its rows cover, and a table that drifted
    into agreeing everywhere would keep passing while proving nothing about the
    direction that matters. Both verdicts have to be present and every tolerance
    kind has to appear, including the one no fixture can declare yet.
    """
    verdicts = {case.verdict for case in AGREEMENT_CASES}
    assert verdicts == {AGREES, DISAGREES}

    kinds = {case.tolerance.kind for case in AGREEMENT_CASES}
    assert kinds == {"absolute", "relative", "percent", "combined"}

    # At least one row sits exactly on a boundary, which is the row that would
    # move if the comparison ever stopped being inclusive.
    assert any(case.margin == "0" for case in AGREEMENT_CASES)


def test_the_margin_is_recorded_for_a_disagreement() -> None:
    """A disagreement carries how far outside it fell, not only that it did.

    A suite that records pass and fail throws away most of what it measured, and
    the difference between an implementation that is marginally wrong and one
    that is wrong by a factor is in this number.
    """
    result = compare(
        expected="10.0",
        unit="sone",
        tolerance=ABSOLUTE_TOLERANCE,
        produced="30.0",
        produced_unit="sone",
    )
    assert result.verdict == DISAGREES
    assert result.deviation == Decimal("20.0")
    assert result.band == Decimal("0.5")
    assert result.margin == Decimal("-19.5")


def test_the_deviation_keeps_its_sign() -> None:
    """Reading high and reading low are different findings and stay different."""
    high = compare(
        expected="10.0",
        unit="sone",
        tolerance=ABSOLUTE_TOLERANCE,
        produced="12.0",
        produced_unit="sone",
    )
    low = compare(
        expected="10.0",
        unit="sone",
        tolerance=ABSOLUTE_TOLERANCE,
        produced="8.0",
        produced_unit="sone",
    )
    assert high.deviation == Decimal("2.0")
    assert low.deviation == Decimal("-2.0")
    assert high.margin == low.margin


# ---------------------------------------------------------------------------
# The refusals
#
# Each entry is a keyword set for `compare` that must not reach a verdict, with
# the reason it must not. They are driven individually below, so that a failure
# names the case, and then all at once, so that the claim "none of these can
# produce an agrees verdict" is checked over the whole list rather than one row
# at a time.
# ---------------------------------------------------------------------------

SOUND: dict[str, Any] = {
    "expected": "10.0",
    "unit": "sone",
    "tolerance": ABSOLUTE_TOLERANCE,
    "produced": "10.0",
    "produced_unit": "sone",
}


def but(**changes: Any) -> dict[str, Any]:
    """The sound call with some arguments replaced."""
    return {**SOUND, **changes}


REFUSALS = [
    ("produced text that is not a number", but(produced="not a number")),
    ("produced an empty string", but(produced="")),
    ("produced nothing at all", but(produced=None)),
    ("produced a list", but(produced=["10.0"])),
    ("produced a mapping", but(produced={"value": "10.0"})),
    ("produced a boolean", but(produced=True)),
    ("produced a binary float", but(produced=10.0)),
    ("produced not a number, spelled", but(produced="NaN")),
    ("produced positive infinity", but(produced="Infinity")),
    ("produced negative infinity", but(produced="-Infinity")),
    ("expected not a number, spelled", but(expected="NaN")),
    ("expected positive infinity", but(expected="Infinity")),
    ("produced a negative magnitude", but(produced="-1.0")),
    ("expected a negative magnitude", but(expected="-10.0", produced="-10.0")),
    ("answered in another unit", but(produced_unit="acum")),
    ("answered in no unit", but(produced_unit="")),
    ("the fixture states no unit", but(unit="")),
    (
        "a relative band against zero",
        but(expected="0", produced="0", tolerance=RELATIVE_TOLERANCE),
    ),
    (
        "a percent band against zero",
        but(expected="0", produced="0", tolerance=PERCENT_TOLERANCE),
    ),
    (
        "a relative band against a zero written with a scale",
        but(expected="0.000", produced="0", tolerance=RELATIVE_TOLERANCE),
    ),
]


@pytest.mark.parametrize(("name", "call"), REFUSALS, ids=[name for name, _ in REFUSALS])
def test_each_refusal(name: str, call: dict[str, Any]) -> None:
    """Every case issue #39 names leaves through ComparisonError."""
    assert name  # the identifier is the point of the row
    with pytest.raises(ComparisonError):
        compare(**call)


def test_no_refusal_can_reach_a_verdict() -> None:
    """None of the refused cases returns anything, let alone an agreement.

    The per-case test above would still pass if one row started returning a
    `Comparison` for a different reason than the one it names. This one asserts
    the property the issue actually states, over the whole list at once: not one
    of these inputs produces a verdict.
    """
    reached: list[tuple[str, Comparison]] = []
    for name, call in REFUSALS:
        try:
            reached.append((name, compare(**call)))
        except ComparisonError:
            continue
    assert reached == []


def test_a_binary_float_is_refused_by_name_and_not_as_a_stray_type() -> None:
    """The float branch is a message rather than a refusal, and is tested as one.

    Removing the branch leaves a float refused anyway, by the fallback that
    catches everything which is not a decimal, an integer or text. What is lost
    is the sentence, and the sentence is the whole of what the branch is for: a
    contributor holding 10.0 and told "is not a number: 10.0" has been given a
    reason that is not true. So the assertion is on the message, and the branch
    is red when it goes.
    """
    with pytest.raises(ComparisonError, match="decimal string"):
        compare(**but(produced=10.0))


def test_a_tolerance_is_never_zero() -> None:
    """Zero is a claim of bit-exact agreement, which nobody means to make."""
    with pytest.raises(ComparisonError, match="never zero"):
        Tolerance.absolute("0")


def test_a_tolerance_is_never_negative() -> None:
    """Negative is a typing mistake and is refused rather than taken as a width."""
    with pytest.raises(ComparisonError, match="never negative"):
        Tolerance.relative("-0.05")


def test_a_combined_tolerance_refuses_a_zero_floor() -> None:
    """A floor of zero makes the absolute half unreachable and says nothing."""
    with pytest.raises(ComparisonError, match="never zero"):
        Tolerance.combined(fraction="0.05", floor="0", absolute="0.01")


def test_a_combined_tolerance_without_its_floor_is_refused() -> None:
    """The dataclass can be built by hand, and a half-built one is not used.

    The class methods cannot produce this, so the check exists for the caller
    who constructs the dataclass directly. Falling back to the fraction here
    would put a band into a comparison that no fixture stated.
    """
    half_built = Tolerance(kind=COMBINED, value=Decimal("0.05"))
    with pytest.raises(ComparisonError, match="needs a floor"):
        band_for(half_built, Decimal("20"))


def test_a_unit_outside_the_known_magnitudes_is_not_checked_for_sign() -> None:
    """The sign check is a list of what is known, and this is what that costs.

    Stated as a test rather than left in a comment, because the cost of the
    check being a list is that a metric whose unit belongs on it and was not
    added is silently unchecked. A test that reads as a wrong answer is the
    thing that gets noticed when that unit arrives.
    """
    assert "db" not in NON_NEGATIVE_UNITS
    result = compare(
        expected="-10.0",
        unit="db",
        tolerance=ABSOLUTE_TOLERANCE,
        produced="-10.0",
        produced_unit="db",
    )
    assert result.verdict == AGREES


def test_the_known_magnitudes_are_the_four_anchor_units() -> None:
    """The four units of record 0007's vocabulary, and no others by accident."""
    assert NON_NEGATIVE_UNITS == frozenset({"sone", "acum", "asper", "vacil"})


# ---------------------------------------------------------------------------
# Reading a tolerance out of a fixture
# ---------------------------------------------------------------------------

FIXTURE: dict[str, Any] = {
    "id": "loudness-anchor",
    "expected": "1.0",
    "unit": "sone",
    "tolerance": "0.05",
    "tolerance_kind": "absolute",
}


def test_a_fixture_supplies_its_own_band() -> None:
    """The ordinary path: the fixture says what it wants and gets it."""
    result = compare_against_fixture(FIXTURE, produced="1.04", produced_unit="sone")
    assert result.verdict == AGREES
    assert result.band == Decimal("0.05")


@pytest.mark.parametrize("missing", ["tolerance", "tolerance_kind", "expected", "unit"])
def test_a_fixture_missing_a_field_is_refused(missing: str) -> None:
    """No default anywhere, so a fixture that skipped the validator is refused.

    The schema requires all four, which means a fixture arriving here without
    one has not been validated. That is precisely the fixture a default
    tolerance would be applied to, and it would pass.
    """
    fixture = {key: value for key, value in FIXTURE.items() if key != missing}
    with pytest.raises(ComparisonError):
        compare_against_fixture(fixture, produced="1.0", produced_unit="sone")


def test_an_unknown_tolerance_kind_is_refused() -> None:
    """A kind nobody implemented is not quietly treated as the nearest one."""
    fixture = {**FIXTURE, "tolerance_kind": "roughly"}
    with pytest.raises(ComparisonError, match="not one of"):
        tolerance_from_fixture(fixture)


def test_a_combined_tolerance_cannot_be_read_from_a_version_1_fixture() -> None:
    """Three numbers do not fit in one field, and none of them is guessed.

    Record 0007 says carrying the combined form is a new fixture schema version
    and a migration rather than a reading of the published one. Until that
    lands, this is the honest answer: the comparator implements the kind and no
    fixture can declare it.
    """
    fixture = {**FIXTURE, "tolerance_kind": "combined"}
    with pytest.raises(ComparisonError, match="one tolerance field"):
        tolerance_from_fixture(fixture)


def test_the_published_schema_cannot_express_the_combined_kind_either() -> None:
    """The refusal above agrees with the schema rather than merely asserting it.

    Read from the packaged schema rather than restated here, so that the day the
    migration lands this test fails and the refusal above is revisited instead
    of quietly refusing something the schema now admits.
    """
    import json
    from importlib.resources import files

    schema = json.loads(
        files("eichstelle")
        .joinpath("schema/fixture-1.schema.json")
        .read_text(encoding="utf-8")
    )
    assert schema["properties"]["tolerance_kind"]["enum"] == [
        "absolute",
        "relative",
        "percent",
    ]
