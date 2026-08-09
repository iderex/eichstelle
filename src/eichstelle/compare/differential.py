"""The spread between implementations, with no winner elected.

This is the mode most of the fixture set will run in, because most expected
values sit behind a paywall this project will not cross, and it is where the
project's headline claim lives. Several implementations answer the same
fixture, and what comes out is a description of how far apart they are.

## What is deliberately absent, and where the temptation was closest

There is no majority, no median, no mean, no reference implementation and no
ranking. Two implementations that agree may share a lineage, a misreading of the
same sentence of a standard, or an author, so agreement between them is not
evidence about the standard and this module never treats it as any. Nothing here
returns "the correct value", and nothing here orders the observations by how far
each one sits from anything.

Three places came close enough to be worth naming, because a reader checking
that claim should be able to check it at the places where it was hard rather
than only where it was easy.

The relative spread needs a denominator, and every choice of one is a choice of
a reference. The smallest value is used, which is what issue #40 asks for, and
it is a scale rather than a truth: it says how large the disagreement is
compared to the smallest thing anybody measured, and it would say the same
number if every implementation were wrong together. Where the smallest value is
not positive there is no scale to express, and the field is absent rather than
filled in.

The band is read from the fixture, never from the values. It would have been
easy to scale a relative tolerance against the observations themselves, since
the fixture's expected value is exactly what a differential-only fixture is
short of. That would make the implementations decide the band they are then
judged against, which is a consensus treated as truth wearing a different hat.
Where the fixture states no expectation to scale against, `exceeds_tolerance` is
absent and says so.

Ordering. `low` and `high` are the ends of the range and are named as ends
rather than as the best and worst answer. The observations come back in the
order they were given, so a report can cluster them without this module having
decided what a cluster is; issue #42 holds the presentation, and a sort here
would have made the first entry read as a winner.

## What a spread is measured against

A fixture's tolerance is the half-width of the band the fixture is willing to
call the same answer. The spread is the full width of what the implementations
actually did. They are compared directly: a spread wider than the band means the
implementations do not agree to the precision the fixture asks for.

That is the tighter of the two readings available, and it is chosen on purpose.
The looser one, twice the band, is the width two values could span while both
still sitting inside one band around some common value, and it would report
agreement for a pair whose disagreement is as large as the whole tolerance. This
project's output is findings, and the reading that produces fewer of them is the
one that has to earn its place.

## Fewer than two

One implementation agreeing with itself is not a measurement. A fixture with
fewer than two usable results produces no differential outcome and says which
of the results were not usable and why, rather than reporting agreement over a
set nobody could have disagreed in.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Final

from eichstelle.compare.comparator import (
    ComparisonError,
    Tolerance,
    band_for,
    tolerance_from_fixture,
)

# The three outcomes of a differential comparison. The first two are findings
# about the implementations; the third is a statement about coverage and is
# never collapsed into agreement.
AGREEMENT: Final = "agreement"
DISAGREEMENT: Final = "disagreement"
NO_OUTCOME: Final = "no_differential_outcome"

# Why an observation could not take part. Each is a different thing to tell a
# reader, and a report that merged them would put an adapter that declined
# beside one whose answer this harness cannot yet reduce.
NOTHING_PRODUCED: Final = "nothing_produced"
SERIES_NOT_REDUCED: Final = "series_not_reduced"
UNIT_NOT_THE_FIXTURES: Final = "unit_not_the_fixtures"
NOT_A_NUMBER: Final = "not_a_number"

# Why a differential comparison reached no outcome. The two are different
# states and a report that merged them would say a run covered less than it did:
# the first is a fixture nobody could disagree on, the second is a spread that
# exists and has nothing declared to judge it against.
FEWER_THAN_TWO_USABLE: Final = "fewer_than_two_usable_results"
NO_DECLARED_BAND: Final = "no_declared_band"


class DifferentialError(Exception):
    """The comparison could not be set up, so there is no outcome at all.

    Distinct from an observation that could not take part, which is a value this
    module returns. This is raised when the fixture itself cannot be read, which
    is a defect in the fixture rather than a finding about anybody's software.
    """


@dataclass(frozen=True)
class Observation:
    """What one adapter answered one fixture with.

    `values` and `unit` arrive exactly as the adapter wrote them and as a record
    entry carries them, so a differential can be computed from a run in flight
    or from a record read back months later without either path converting
    anything on the way.

    `upstream_version` is what the adapter loaded. The empty string is the
    declared unknown, carried rather than filled in, because a value attributed
    to a version nobody can identify is not reproducible and a reader of the
    spread is entitled to see which of the two they are holding.
    """

    adapter: str
    upstream_version: str
    values: tuple[str, ...]
    unit: str | None


@dataclass(frozen=True)
class Usable:
    """An observation this comparison could use, and the number it contributed."""

    observation: Observation
    value: Decimal


@dataclass(frozen=True)
class Unusable:
    """An observation this comparison could not use, and which of the reasons."""

    observation: Observation
    reason: str
    detail: str


@dataclass(frozen=True)
class Differential:
    """What several implementations did with one fixture.

    `outcome` is `agreement`, `disagreement` or `no_differential_outcome`. The
    third is not a weaker form of the first, and `reason` says which of its two
    cases it is: fewer than two usable answers, so no spread exists at all, or a
    spread that exists with nothing declared to judge it against.

    `low` and `high` are the ends of the range and `spread` is `high - low`, all
    in the fixture's unit. `relative_spread` is `spread / low` and is None where
    the smallest value is not positive, because there is then no scale to
    express it against and a zero or a negative ratio would be read as one.

    `band` is the half-width the fixture declared, resolved against its expected
    value, and `exceeds_tolerance` is whether the spread is wider than it. Both
    are None where the fixture states no expectation to resolve the band
    against; a spread is still reported there, and whether it is too large is
    then a question this suite has no fixture-declared answer to.
    """

    fixture_id: str
    outcome: str
    reason: str
    unit: str | None
    usable: tuple[Usable, ...]
    unusable: tuple[Unusable, ...]
    low: Decimal | None = None
    high: Decimal | None = None
    spread: Decimal | None = None
    relative_spread: Decimal | None = None
    band: Decimal | None = None
    exceeds_tolerance: bool | None = None


def _number(text: str) -> Decimal | None:
    """Read a decimal string, or None where it is not one.

    None rather than a raised error, because a value that is not a number is a
    statement about one adapter and the other adapters' answers are still worth
    reporting. The comparator refuses in the same situation, and correctly: it
    is judging one answer and has nothing else to report.
    """
    try:
        parsed = Decimal(text)
    except ArithmeticError:
        return None
    except (TypeError, ValueError):
        return None
    return parsed if parsed.is_finite() else None


def _partition(
    observations: Sequence[Observation], unit: str | None
) -> tuple[list[Usable], list[Unusable]]:
    """Split the observations into the ones a spread can be taken over and the rest."""
    usable: list[Usable] = []
    unusable: list[Unusable] = []
    for observation in observations:
        if not observation.values:
            unusable.append(
                Unusable(
                    observation=observation,
                    reason=NOTHING_PRODUCED,
                    detail="the adapter produced no value for this fixture",
                )
            )
            continue
        if len(observation.values) > 1:
            unusable.append(
                Unusable(
                    observation=observation,
                    reason=SERIES_NOT_REDUCED,
                    detail=(
                        f"the adapter produced {len(observation.values)} values, and "
                        f"which statistic of a series is compared is the fixture's to "
                        f"declare; schema version 1 carries no field for it, so "
                        f"reducing it here would be a rule nobody asked for"
                    ),
                )
            )
            continue
        if unit is not None and observation.unit != unit:
            unusable.append(
                Unusable(
                    observation=observation,
                    reason=UNIT_NOT_THE_FIXTURES,
                    detail=(
                        f"the adapter answered in {observation.unit!r} and the fixture "
                        f"asked for {unit!r}; nothing here converts between units"
                    ),
                )
            )
            continue
        value = _number(observation.values[0])
        if value is None:
            unusable.append(
                Unusable(
                    observation=observation,
                    reason=NOT_A_NUMBER,
                    detail=(
                        f"the adapter produced {observation.values[0]!r}, which is not "
                        f"a finite number"
                    ),
                )
            )
            continue
        usable.append(Usable(observation=observation, value=value))
    return usable, unusable


def _band_from(fixture: Mapping[str, Any]) -> Decimal | None:
    """The half-width this fixture declares, or None where it declares none.

    Read from the fixture and never from the observations. A relative band
    scaled against the values under comparison would let the implementations
    decide the band they are then judged against.
    """
    expected = fixture.get("expected")
    if expected is None:
        return None
    try:
        tolerance: Tolerance = tolerance_from_fixture(fixture)
        return band_for(tolerance, Decimal(str(expected)))
    except (ArithmeticError, ComparisonError, ValueError) as exc:
        raise DifferentialError(
            f"the fixture's tolerance cannot be resolved against its expected "
            f"value: {exc}"
        ) from exc


def differential(
    fixture: Mapping[str, Any], observations: Sequence[Observation]
) -> Differential:
    """What several implementations did with one fixture, and how far apart.

    The fixture supplies the identifier, the unit and the band, and nothing
    else: no expected value reaches a verdict here, because in this mode there
    may not be one worth trusting and the point is what the implementations did
    relative to each other.
    """
    identifier = fixture.get("id")
    if not isinstance(identifier, str) or not identifier:
        raise DifferentialError("the fixture carries no identifier")
    unit = fixture.get("unit")
    if unit is not None and not isinstance(unit, str):
        raise DifferentialError(f"the fixture's unit is not text: {unit!r}")

    usable, unusable = _partition(observations, unit)

    if len(usable) < 2:
        return Differential(
            fixture_id=identifier,
            outcome=NO_OUTCOME,
            reason=FEWER_THAN_TWO_USABLE,
            unit=unit,
            usable=tuple(usable),
            unusable=tuple(unusable),
        )

    values = [entry.value for entry in usable]
    low = min(values)
    high = max(values)
    spread = high - low
    relative = spread / low if low > 0 else None

    band = _band_from(fixture)
    exceeds = None if band is None else spread > band
    if exceeds is None:
        outcome, reason = NO_OUTCOME, NO_DECLARED_BAND
    else:
        outcome, reason = (DISAGREEMENT if exceeds else AGREEMENT), ""

    return Differential(
        fixture_id=identifier,
        outcome=outcome,
        reason=reason,
        unit=unit,
        usable=tuple(usable),
        unusable=tuple(unusable),
        low=low,
        high=high,
        spread=spread,
        relative_spread=relative,
        band=band,
        exceeds_tolerance=exceeds,
    )


def observations_from_entries(
    entries: Sequence[Mapping[str, Any]],
) -> list[Observation]:
    """Read observations out of the entries of a result record.

    This is what makes the record aggregable rather than a second copy of the
    same data in a shape only a live run can produce. A record entry already
    carries the adapter, the version it loaded, the values and their unit, so a
    reader six months later groups the entries of a record by `fixture_id` and
    gets exactly what a differential was computed from at the time.

    Entries whose values are absent arrive as observations that produced
    nothing, rather than being dropped. A dropped entry is an adapter that
    disappears from the spread, and an adapter that answered nothing is a
    different statement from an adapter that was not in the run.
    """
    read: list[Observation] = []
    for entry in entries:
        values = entry.get("produced") or ()
        read.append(
            Observation(
                adapter=str(entry.get("adapter", "")),
                upstream_version=str(entry.get("adapter_upstream_version") or ""),
                values=tuple(str(value) for value in values),
                unit=entry.get("produced_unit"),
            )
        )
    return read
