"""Reading fixtures, and refusing the ones that are not fixtures.

Decision record 0004 says a fixture binds five things into one file: a signal
described completely enough to regenerate, the metric to compute from it, the
value expected, the tolerance within which a result counts as agreeing, and the
standard edition the expectation comes from. Anything naming fewer than five of
those is a note, and the point of validating is that a note must not be able to
sit in the fixture set looking like a fixture.

What a green run over a fixture set with a missing tolerance proves is nothing,
and it prints the same characters as a run that proved something. That is the
failure this module exists against, and it is why every refusal below has a
named way of going quietly wrong rather than being a tidiness rule.

The other half of the same promise is the signal checksums. A fixture describes
its stimulus rather than shipping it, so what an adapter is actually handed
depends on the code that rendered it, and nothing in the fixture records which
bytes anybody saw. `checksums` is where that is held still.
"""

from eichstelle.fixtures.checksums import (
    MANIFEST_NAME,
    ChecksumError,
    Entry,
    Mismatch,
    compare,
    digest,
    read_manifest,
    verify,
    write,
)
from eichstelle.fixtures.validator import (
    Problem,
    known_schema_versions,
    validate_documents,
    validate_paths,
)

__all__ = [
    "MANIFEST_NAME",
    "ChecksumError",
    "Entry",
    "Mismatch",
    "Problem",
    "compare",
    "digest",
    "known_schema_versions",
    "read_manifest",
    "validate_documents",
    "validate_paths",
    "verify",
    "write",
]
