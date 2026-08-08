"""Comparing two runs, which is how this suite becomes useful over time.

One run says what the state is. Two runs compared say what changed, and for
nearly everyone who will use this the second statement is the more valuable one.
An implementation maintainer wants to know whether their last change moved a
verdict. This project wants to know whether an upstream version bump moved six
of them, which is the observation the pinning issue exists to preserve. An
operator wants to know whether last month's result still holds.

Three things make this a comparison rather than a diff.

It refuses loudly. Two records made against different fixture sets are not
comparable, and producing a difference between them would be comparing different
stimuli while looking like a result. The refusal names which fixtures differ
rather than saying the checksums do not match, because the first is a finding and
the second is a shrug.

It reports what stayed inside its band as well as what crossed it. A result
drifting from comfortably inside tolerance to barely inside it has not changed
verdict and is the earliest warning available that it is about to.

It reports what is no longer there. A fixture that stopped running is exactly the
kind of thing that goes unnoticed for a year, so it is added or removed and never
quietly absent.
"""

from eichstelle.runs.compare import (
    CHANGED,
    INCOMPARABLE,
    NO_CHANGE,
    Change,
    Comparison,
    Incomparable,
    compare_records,
    render,
)

__all__ = [
    "CHANGED",
    "INCOMPARABLE",
    "NO_CHANGE",
    "Change",
    "Comparison",
    "Incomparable",
    "compare_records",
    "render",
]
