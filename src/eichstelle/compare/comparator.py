"""Turning a produced value and an expected value into a verdict.

Every claim this project makes passes through here, which is why the module is
written to refuse rather than to cope. A comparator that is wrong in the
permissive direction produces a suite that finds nothing and reports that
everything is fine, and that failure looks exactly like success from outside.

Two verdicts are produced here, ``agrees`` and ``disagrees``. Decision record
0007 names six, and the other four are the harness's observations about an
invocation rather than statements about a number: an adapter that declined, one
that fell over, one that ran past its limit, and a pair that was never
attempted. None of those reaches a comparison, so none of them is spelled here.

Arithmetic is ``decimal.Decimal`` throughout, because a fixture writes every
physical quantity as a decimal string and decision record 0004 gives the reason:
a band of ``0.1`` parsed as an IEEE 754 double is ``0.1000000000000000055...``,
which is a footnote in most projects and decides a boundary case in this one.
The boundary tests in this module's suite are exact for that reason, and would
be approximate under binary floating point.

There is no default tolerance anywhere below. Decision record 0007 argues at
length why a default is the mechanism by which a conformance suite converts
disagreement into agreement, and the practical form of that argument is that
every function here that needs a band takes one and none of them invents one.

What is deliberately not here:

- A time series reduced to one number. Record 0007 says what a fixture may
  declare (a percentile with its interpolation convention, a maximum, a mean, or
  the series point by point with a permitted fraction of exceedances) and
  schema version 1 carries no field to declare any of it. Reducing a series by a
  rule the fixture did not ask for is the shape of guess this module exists
  against, so a series arrives here already reduced or not at all.
- Unit conversion. A produced value in a unit the fixture did not ask for is
  refused, never converted. Deciding that two unit spellings mean the same
  quantity is a judgement, and a comparator making it silently would attribute a
  disagreement to an implementation that had answered correctly in a unit
  nobody agreed on.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, DecimalException
from typing import Final

# The two verdicts a comparison can reach. Record 0007's other four are reached
# without a comparison, so they are not this module's to produce.
AGREES: Final = "agrees"
DISAGREES: Final = "disagrees"

# What the fixture schema's `tolerance_kind` may say, plus the combined form.
#
# `percent` is in schema version 1 and is not in record 0007's prose, which
# names absolute, relative and combined. `combined` is in the record and is not
# in the schema, and the record says so itself: carrying it is a new schema
# version and a migration, argued on the fixture schema issue. So the two lists
# differ in both directions today, and this module implements the union rather
# than either one: refusing `percent` would refuse a fixture the published
# schema admits, and omitting `combined` would leave the record's own worked
# example unimplemented.
ABSOLUTE: Final = "absolute"
RELATIVE: Final = "relative"
PERCENT: Final = "percent"
COMBINED: Final = "combined"

TOLERANCE_KINDS: Final = frozenset({ABSOLUTE, RELATIVE, PERCENT, COMBINED})

# The kinds whose band is a fraction of the expected value, and which therefore
# have nothing to scale when that value is zero.
_SCALED_KINDS: Final = frozenset({RELATIVE, PERCENT})

# Exact, rather than a division by 100. Decimal division is correct to the
# context's precision and this multiplication is correct without qualification,
# which matters because the result is compared against a boundary.
_PER_CENT: Final = Decimal("0.01")

# Units naming a magnitude, where a negative value is not a small answer but a
# broken one. The four are the anchor units of decision record 0007's vocabulary
# and issue #26's anchor fixtures: loudness, sharpness, roughness and
# fluctuation strength.
#
# It is a list of what is known rather than a rule about units in general. A
# unit not named here is not checked for sign, and that is stated rather than
# left for a reader to discover: adding a metric whose unit belongs here and
# forgetting this line leaves the check silent, which is the way a guard of this
# shape stops working.
NON_NEGATIVE_UNITS: Final = frozenset({"sone", "acum", "asper", "vacil"})


class ComparisonError(Exception):
    """The comparison did not happen, so there is no verdict.

    Every refusal in this module raises this and nothing else. That is what
    makes the claim "none of these cases can produce an agrees verdict"
    structural rather than a promise: the only path to a `Comparison` runs
    through the end of `compare`, and every case named in issue #39 leaves
    before it.

    The caller maps this onto record 0007's `errored`, with the message kept, so
    that a reader of a record can tell which of the causes it was.
    """


@dataclass(frozen=True)
class Tolerance:
    """The band a comparison is made against, and what the band is measured in.

    Constructed through the four class methods rather than directly, so that a
    combined tolerance cannot be built without its floor and an absolute one
    cannot be built with a floor that would be ignored.
    """

    kind: str
    value: Decimal
    floor: Decimal | None = None
    below_floor: Decimal | None = None

    @classmethod
    def absolute(cls, value: object) -> Tolerance:
        """A band in the metric's own unit."""
        return cls(kind=ABSOLUTE, value=_positive(value, "tolerance"))

    @classmethod
    def relative(cls, value: object) -> Tolerance:
        """A band as a fraction of the expected value: 0.05 is five per cent."""
        return cls(kind=RELATIVE, value=_positive(value, "tolerance"))

    @classmethod
    def percent(cls, value: object) -> Tolerance:
        """A band as a percentage of the expected value: 5 is five per cent."""
        return cls(kind=PERCENT, value=_positive(value, "tolerance"))

    @classmethod
    def combined(
        cls, *, fraction: object, floor: object, absolute: object
    ) -> Tolerance:
        """A fraction above a floor and a fixed band below it.

        Record 0007 gives the case that forces this: a five per cent band on
        0.02 sone is one thousandth of a sone, which no implementation meets and
        none needs to, because nobody claims three significant figures down
        there. Above the floor the fraction means something and is used.

        The floor is a value of the measured quantity, in the fixture's unit,
        and it is compared against the magnitude of the expected value.
        """
        return cls(
            kind=COMBINED,
            value=_positive(fraction, "tolerance"),
            floor=_positive(floor, "tolerance floor"),
            below_floor=_positive(absolute, "tolerance below the floor"),
        )


@dataclass(frozen=True)
class Comparison:
    """One produced value judged against one expected value.

    `band` is the half-width actually applied, in the fixture's unit, after the
    tolerance kind has been resolved against the expected value. It is recorded
    rather than recomputed by a reader, because for a combined tolerance it also
    says which side of the floor the comparison fell on.

    `deviation` is signed, `produced - expected`, so a reader can tell an
    implementation that reads high from one that reads low without going back to
    the record's raw values.

    `margin` is `band - abs(deviation)`: positive means inside the band by that
    much, zero means exactly on the boundary, negative means outside by that
    much. It is in the fixture's unit like the band, and it is recorded for
    every comparison including the ones that disagree, because how far outside a
    value fell is the difference between an implementation that is marginally
    wrong and one that is wrong by a factor.
    """

    verdict: str
    expected: Decimal
    produced: Decimal
    unit: str
    tolerance: Tolerance
    band: Decimal
    deviation: Decimal
    margin: Decimal


def _decimal(value: object, where: str) -> Decimal:
    """Read a decimal, refusing everything that is not exactly one.

    `bool` is refused before `int` because it is a subclass of it in Python, and
    `True` would otherwise arrive as the number 1 with no complaint at all.

    `float` is refused rather than converted. It is not an unusable type; it is
    the type that carries the imprecision decision record 0004 chose decimal
    strings to avoid, and accepting it here would make the boundary cases in
    this module's suite depend on which side of a double a value landed on. The
    message says what to send instead, because a contributor meeting this
    refusal is holding a number and needs the shape rather than the argument.
    """
    if isinstance(value, bool):
        raise ComparisonError(f"{where} is a boolean rather than a number: {value!r}")
    if isinstance(value, float):
        raise ComparisonError(
            f"{where} arrived as a binary floating-point number ({value!r}); send it "
            f"as a decimal string so that the value is the one that was written"
        )
    if isinstance(value, Decimal):
        parsed = value
    elif isinstance(value, (int, str)):
        try:
            parsed = Decimal(value)
        except (DecimalException, ValueError) as exc:
            raise ComparisonError(f"{where} is not a number: {value!r}") from exc
    else:
        raise ComparisonError(f"{where} is not a number: {value!r}")

    # `Decimal` parses "NaN", "Infinity" and "-Infinity" without complaint, and
    # arithmetic on them produces answers that compare as though they meant
    # something. An infinite deviation against any finite band disagrees, which
    # looks like a finding and is not one, and a NaN compares false against
    # every bound, which under a different arrangement of the same code would
    # read as agreement. Both are refused here, at the one place values enter.
    if not parsed.is_finite():
        raise ComparisonError(f"{where} is not a finite number: {value!r}")
    return parsed


def _positive(value: object, where: str) -> Decimal:
    """Read a decimal that has to be greater than zero.

    Record 0007: a tolerance is never zero and never negative. Zero is a claim
    of bit-exact agreement between two independent floating-point
    implementations, which nobody means to make, and negative is a typing
    mistake. Both are refused rather than interpreted.
    """
    parsed = _decimal(value, where)
    if parsed <= 0:
        raise ComparisonError(
            f"{where} is {parsed}, and a tolerance is never zero and never negative"
        )
    return parsed


def tolerance_from_fixture(fixture: Mapping[str, object]) -> Tolerance:
    """Read the tolerance a fixture declares, refusing a fixture that has none.

    The schema requires both fields, so a fixture reaching here without one has
    not been validated. That is the case worth refusing loudly rather than
    assuming away: a fixture that skipped the validator is exactly the one a
    default tolerance would be applied to.

    `combined` is refused with its own message. Schema version 1 carries one
    tolerance field, a combined tolerance needs three numbers, and record 0007
    says carrying it is a new schema version rather than a reading of the
    existing one. Guessing a floor here would put a band into a comparison that
    no fixture stated, which is the whole thing this module is against.
    """
    if "tolerance_kind" not in fixture:
        raise ComparisonError(
            "the fixture declares no tolerance_kind, and there is no default"
        )
    if "tolerance" not in fixture:
        raise ComparisonError(
            "the fixture declares no tolerance, and there is no default"
        )

    kind = fixture["tolerance_kind"]
    if not isinstance(kind, str) or kind not in TOLERANCE_KINDS:
        raise ComparisonError(
            f"tolerance_kind is {kind!r}, which is not one of "
            f"{', '.join(sorted(TOLERANCE_KINDS))}"
        )
    if kind == COMBINED:
        raise ComparisonError(
            "a combined tolerance carries a fraction, a floor and an absolute band, "
            "and a schema version 1 fixture has one tolerance field to write them in"
        )

    value = fixture["tolerance"]
    if kind == ABSOLUTE:
        return Tolerance.absolute(value)
    if kind == RELATIVE:
        return Tolerance.relative(value)
    return Tolerance.percent(value)


def band_for(tolerance: Tolerance, expected: Decimal) -> Decimal:
    """The half-width this tolerance means against this expected value.

    The refusal here is the one issue #39 singles out. A relative band against
    an expected value of zero is a band of zero, which is the bit-exact claim
    record 0007 refuses, and it arrives by arithmetic rather than by anybody
    writing it down. It is refused rather than evaluated, and the message names
    the expected value so that the fixture is the thing the reader opens.
    """
    magnitude = abs(expected)

    if tolerance.kind == ABSOLUTE:
        return tolerance.value

    if tolerance.kind in _SCALED_KINDS:
        if magnitude == 0:
            raise ComparisonError(
                f"a {tolerance.kind} tolerance against an expected value of "
                f"{expected} is a band of zero, which is a claim of bit-exact "
                f"agreement; state an absolute tolerance instead"
            )
        if tolerance.kind == RELATIVE:
            return magnitude * tolerance.value
        return magnitude * tolerance.value * _PER_CENT

    # Combined. Both halves are stated by the fixture, so neither is derived
    # from the other, and below the floor the expected value is not scaled at
    # all, which is why an expected value of zero is answerable here and is not
    # under a bare relative tolerance.
    if tolerance.floor is None or tolerance.below_floor is None:
        raise ComparisonError(
            "a combined tolerance needs a floor and an absolute band below it"
        )
    if magnitude >= tolerance.floor:
        return magnitude * tolerance.value
    return tolerance.below_floor


def compare(
    *,
    expected: object,
    unit: str,
    tolerance: Tolerance,
    produced: object,
    produced_unit: str,
) -> Comparison:
    """Judge one produced value against one expected value.

    Every refusal happens before any arithmetic that could reach a verdict, so
    there is one exit that returns a `Comparison` and every case issue #39 names
    leaves through `ComparisonError` instead.

    The boundary is inclusive: a value exactly one band away from the expected
    value agrees. A tolerance is a half-width the fixture chose, and excluding
    its own endpoint would make the declared number mean slightly less than it
    says. `margin` is zero there, so a reader can see it was exact.
    """
    if not isinstance(unit, str) or not unit:
        raise ComparisonError("the fixture states no unit for its expected value")
    if not isinstance(produced_unit, str) or not produced_unit:
        raise ComparisonError("the adapter stated no unit for the value it produced")
    if produced_unit != unit:
        raise ComparisonError(
            f"the adapter answered in {produced_unit!r} and the fixture asked for "
            f"{unit!r}; nothing here converts between units"
        )

    expected_value = _decimal(expected, "the expected value")
    produced_value = _decimal(produced, "the produced value")

    # A magnitude cannot be negative, and an implementation that returns one has
    # not produced a small answer, it has produced a broken one. Comparing it
    # against a band would report a disagreement, which reads as a finding about
    # the metric when what happened is that the adapter or the library returned
    # something that is not a measurement at all.
    if unit in NON_NEGATIVE_UNITS:
        if expected_value < 0:
            raise ComparisonError(
                f"the fixture expects {expected_value} {unit}, and {unit} is a "
                f"magnitude that cannot be negative"
            )
        if produced_value < 0:
            raise ComparisonError(
                f"the adapter produced {produced_value} {unit}, and {unit} is a "
                f"magnitude that cannot be negative"
            )

    band = band_for(tolerance, expected_value)
    deviation = produced_value - expected_value
    margin = band - abs(deviation)

    return Comparison(
        verdict=AGREES if margin >= 0 else DISAGREES,
        expected=expected_value,
        produced=produced_value,
        unit=unit,
        tolerance=tolerance,
        band=band,
        deviation=deviation,
        margin=margin,
    )


def compare_against_fixture(
    fixture: Mapping[str, object],
    *,
    produced: object,
    produced_unit: str,
) -> Comparison:
    """Judge a produced value against what a fixture declares.

    The fixture is read for its expected value, its unit and its tolerance, and
    a fixture missing any of the three is refused. This is the entry the runner
    uses, and it is the reason `compare` above takes a `Tolerance` rather than a
    fixture: the two failure modes, a fixture that does not say what it wants
    and an answer that does not meet it, are different findings and are reported
    with different messages.
    """
    if "expected" not in fixture:
        raise ComparisonError("the fixture declares no expected value")
    if "unit" not in fixture:
        raise ComparisonError("the fixture declares no unit")

    unit = fixture["unit"]
    if not isinstance(unit, str):
        raise ComparisonError(f"the fixture's unit is not text: {unit!r}")

    return compare(
        expected=fixture["expected"],
        unit=unit,
        tolerance=tolerance_from_fixture(fixture),
        produced=produced,
        produced_unit=produced_unit,
    )
