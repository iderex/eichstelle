"""The command that refuses a malformed fixture and a stimulus that moved.

    python -m eichstelle.fixtures fixtures/
    python -m eichstelle.fixtures --write-checksums fixtures/

The first form is the check. It validates every fixture under the paths given
against the schema, then regenerates every signal and holds it against the
committed manifest. Both halves run, and the second is the reason a run that
proceeded on a different stimulus cannot look like a result.

The second form is the one deliberate way to move the manifest. It regenerates,
prints what moved, and writes. It is a separate word rather than a flag on the
check, and it prints rather than staying quiet, because a manifest that can be
refreshed reflexively is a manifest nobody reads the diff of. A pull request
carrying a change to that file says in its body why the signals moved and what
was checked to establish that the new bytes are the right ones.

Exit codes follow the same convention as the other check in this tree, because
a reader should not have to learn a second one:

    0   every path given was read, every fixture in it is valid, and every
        signal hashes to what the manifest says
    1   at least one fixture was refused, or at least one stimulus moved
    2   the run did not complete, so its result is unknown

It fails closed. A path that cannot be read is exit 2 and never a clean result.
A file that reads and is not JSON is exit 1 for the validator: it was seen, and
what it says is that it is not a fixture. An absent or unreadable manifest is
exit 2, because nothing then records what the signals are supposed to be.

Directories are walked for `*.json`, so the command takes the fixture root
rather than a list somebody maintains by hand. A list is a thing a new fixture
gets left out of. The manifest is not walked into: it carries no `.json` suffix
for exactly that reason.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path

from eichstelle.fixtures.checksums import (
    MANIFEST_NAME,
    ChecksumError,
    verify,
    write,
)
from eichstelle.fixtures.validator import ValidatorError, validate_paths

USAGE: str = "usage: python -m eichstelle.fixtures [--write-checksums] PATH [PATH ...]"

# The flag that moves the manifest. Spelled out rather than abbreviated: it is
# typed rarely, by somebody who has decided to do it, and a single letter beside
# the check's own arguments is a keystroke away from the check.
WRITE_FLAG: str = "--write-checksums"


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


def manifest_for(arguments: Sequence[str]) -> Path:
    """Where the manifest sits for the roots given.

    Beside the first directory named, which is the fixture root. A command given
    single files rather than a root gets the manifest beside the first of them,
    which is where a fixture root would have been.
    """
    for argument in arguments:
        path = Path(argument)
        if path.is_dir():
            return path / MANIFEST_NAME
    return Path(arguments[0]).parent / MANIFEST_NAME


def _write(arguments: Sequence[str], paths: Sequence[Path]) -> int:
    """Regenerate the manifest and say what moved."""
    manifest = manifest_for(arguments)
    try:
        entries, moved = write(manifest=manifest, paths=paths)
    except ChecksumError as exc:
        print(f"the manifest was not written: {exc}", file=sys.stderr)
        return 2

    for mismatch in moved:
        print(f"moved: {mismatch}")
    if not moved:
        print("nothing moved: every entry is the hash that was already committed")
    print(f"{len(entries)} entr(ies) written to {manifest}")
    print(
        "Read the diff. The body of the pull request carrying it says why the "
        "signals moved and what was checked to establish that the new bytes are "
        "the right ones"
    )
    return 0


def _check(arguments: Sequence[str], paths: Sequence[Path]) -> int:
    """Validate every fixture, then hold every signal against the manifest."""
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

    manifest = manifest_for(arguments)
    try:
        mismatches = verify(manifest=manifest, paths=paths)
    except ChecksumError as exc:
        print(f"checksum verification did not complete: {exc}", file=sys.stderr)
        print("failing closed: the result of this run is unknown", file=sys.stderr)
        return 2

    if mismatches:
        for mismatch in mismatches:
            print(f"stimulus: {mismatch}", file=sys.stderr)
        print(
            f"{len(mismatches)} signal(s) do not match {manifest}. Nothing is "
            "run against a stimulus nobody recorded: a number produced from one "
            "looks like a result and is not",
            file=sys.stderr,
        )
        return 1

    print(f"{len(paths)} fixture(s) valid")
    print(f"{len(paths)} signal checksum(s) verified against {manifest}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run the check, or move the manifest, and return the process exit code."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    writing = WRITE_FLAG in arguments
    arguments = [argument for argument in arguments if argument != WRITE_FLAG]
    if not arguments:
        print(USAGE, file=sys.stderr)
        return 2

    paths = collect(arguments)
    if not paths:
        print(
            f"no .json file was found under {', '.join(arguments)}. Refusing to "
            "report a clean run over nothing",
            file=sys.stderr,
        )
        return 2

    if writing:
        return _write(arguments, paths)
    return _check(arguments, paths)


if __name__ == "__main__":
    sys.exit(main())
