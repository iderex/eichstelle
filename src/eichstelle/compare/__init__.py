"""The comparison, and the verdicts it reaches.

This is the smallest package in the tree and the one most worth being paranoid
about. Every finding this project ever publishes is a verdict that came from
here, and a comparator that is wrong in the permissive direction produces a
suite that reports agreement it never established.

``comparator`` judges one produced value against one expected value, which is
the mode a fixture with a normative target runs in. ``differential`` takes
several implementations against one fixture and reports how far apart they are,
which is the mode most of the fixture set will run in and the one that elects no
winner. What each refusal exists for is written next to the refusal rather than
here, because the reason a case is refused is the thing a reader needs while
looking at the case.
"""

from eichstelle.compare.comparator import (
    ABSOLUTE,
    AGREES,
    COMBINED,
    DISAGREES,
    NON_NEGATIVE_UNITS,
    PERCENT,
    RELATIVE,
    TOLERANCE_KINDS,
    Comparison,
    ComparisonError,
    Tolerance,
    band_for,
    compare,
    compare_against_fixture,
    tolerance_from_fixture,
)
from eichstelle.compare.differential import (
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
    Unusable,
    Usable,
    differential,
    observations_from_entries,
)

__all__ = [
    "ABSOLUTE",
    "AGREEMENT",
    "AGREES",
    "COMBINED",
    "DISAGREEMENT",
    "DISAGREES",
    "FEWER_THAN_TWO_USABLE",
    "NON_NEGATIVE_UNITS",
    "NOTHING_PRODUCED",
    "NOT_A_NUMBER",
    "NO_DECLARED_BAND",
    "NO_OUTCOME",
    "PERCENT",
    "RELATIVE",
    "SERIES_NOT_REDUCED",
    "TOLERANCE_KINDS",
    "UNIT_NOT_THE_FIXTURES",
    "Comparison",
    "ComparisonError",
    "Differential",
    "DifferentialError",
    "Observation",
    "Tolerance",
    "Unusable",
    "Usable",
    "band_for",
    "compare",
    "compare_against_fixture",
    "differential",
    "observations_from_entries",
    "tolerance_from_fixture",
]
