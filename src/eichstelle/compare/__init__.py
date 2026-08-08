"""The comparison, and the verdicts it reaches.

This is the smallest package in the tree and the one most worth being paranoid
about. Every finding this project ever publishes is a verdict that came from
here, and a comparator that is wrong in the permissive direction produces a
suite that reports agreement it never established.

``comparator`` holds the whole of it. What each refusal exists for is written
next to the refusal rather than here, because the reason a case is refused is
the thing a reader needs while looking at the case.
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

__all__ = [
    "ABSOLUTE",
    "AGREES",
    "COMBINED",
    "DISAGREES",
    "NON_NEGATIVE_UNITS",
    "PERCENT",
    "RELATIVE",
    "TOLERANCE_KINDS",
    "Comparison",
    "ComparisonError",
    "Tolerance",
    "band_for",
    "compare",
    "compare_against_fixture",
    "tolerance_from_fixture",
]
