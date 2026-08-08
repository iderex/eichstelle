"""The command that says what moved between two runs.

    python -m eichstelle.runs EARLIER LATER

Exit codes, and the reason there are three rather than two:

    0   nothing moved
    1   something moved, and it is listed
    2   the two records could not be compared, so nothing was compared

A caller scripting this has to tell "nothing moved" from "something moved"
without reading the text, and both of those from a refusal. Folding a refusal
into either of the first two is how a run that compared nothing comes out looking
like a run that found nothing.

The threshold below which a margin movement is not reported is `--margin`. It
exists because zero would report every last-place difference in a decimal string
and bury the drifts worth seeing.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from decimal import Decimal, InvalidOperation
from pathlib import Path

from eichstelle.record import RecordError, read
from eichstelle.runs.compare import (
    DEFAULT_MARGIN_THRESHOLD,
    INCOMPARABLE,
    Incomparable,
    compare_records,
    render,
)

USAGE: str = "usage: python -m eichstelle.runs [--margin THRESHOLD] EARLIER LATER"


def main(argv: Sequence[str] | None = None) -> int:
    """Compare the two records named and return the process exit code."""
    arguments = list(sys.argv[1:] if argv is None else argv)

    threshold = DEFAULT_MARGIN_THRESHOLD
    if arguments and arguments[0] == "--margin":
        if len(arguments) < 2:
            print(USAGE, file=sys.stderr)
            return INCOMPARABLE
        try:
            threshold = Decimal(arguments[1])
        except InvalidOperation:
            print(f"--margin {arguments[1]!r} is not a number", file=sys.stderr)
            return INCOMPARABLE
        arguments = arguments[2:]

    if len(arguments) != 2:
        print(USAGE, file=sys.stderr)
        return INCOMPARABLE

    try:
        before = read(Path(arguments[0]))
        after = read(Path(arguments[1]))
    except (RecordError, OSError) as exc:
        print(f"a record could not be read: {exc}", file=sys.stderr)
        print("failing closed: nothing was compared", file=sys.stderr)
        return INCOMPARABLE

    try:
        comparison = compare_records(before, after, margin_threshold=threshold)
    except (Incomparable, ValueError) as exc:
        print(f"refusing to compare: {exc}", file=sys.stderr)
        return INCOMPARABLE

    print(render(comparison))
    return comparison.status


if __name__ == "__main__":
    sys.exit(main())
