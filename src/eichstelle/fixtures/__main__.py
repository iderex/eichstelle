"""The command that refuses a malformed fixture.

    python -m eichstelle.fixtures fixtures/

Exit codes follow the same convention as the other check in this tree, because
a reader should not have to learn a second one:

    0   every path given was read and every fixture in it is valid
    1   at least one fixture was refused
    2   the validation did not complete, so its result is unknown

It fails closed. A path that cannot be read is exit 2 and never a clean result.
A file that reads and is not JSON is exit 1: it was seen, and what it says is
that it is not a fixture.

Directories are walked for `*.json`, so the command takes the fixture root
rather than a list somebody maintains by hand. A list is a thing a new fixture
gets left out of.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path

from eichstelle.fixtures.validator import ValidatorError, validate_paths


def collect(arguments: Sequence[str]) -> list[Path]:
    """Expand the arguments into the fixture files to read."""
    found: list[Path] = []
    for argument in arguments:
        path = Path(argument)
        if path.is_dir():
            found.extend(sorted(path.rglob("*.json")))
        else:
            found.append(path)
    return found


def main(argv: Sequence[str] | None = None) -> int:
    """Validate the paths given and return the process exit code."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments:
        print(
            "usage: python -m eichstelle.fixtures PATH [PATH ...]",
            file=sys.stderr,
        )
        return 2

    paths = collect(arguments)
    if not paths:
        print(
            f"no .json file was found under {', '.join(arguments)}. Refusing to "
            "report a clean run over nothing",
            file=sys.stderr,
        )
        return 2

    try:
        problems = validate_paths(paths)
    except ValidatorError as exc:
        print(f"fixture validation did not complete: {exc}", file=sys.stderr)
        print("failing closed: the result of this run is unknown", file=sys.stderr)
        return 2

    if problems:
        for problem in problems:
            print(f"refused: {problem}", file=sys.stderr)
        print(
            f"{len(problems)} problem(s) in {len(paths)} file(s). "
            "docs/fixtures.md says what a fixture carries and why",
            file=sys.stderr,
        )
        return 1

    print(f"{len(paths)} fixture(s) valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
