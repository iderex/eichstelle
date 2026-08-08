"""The result record: the primary output of a run.

Decision record 0009 makes this file the thing a run produces and everything a
person reads a rendering of it. The writer and the reader live together, because
a format whose compatibility promises are only ever exercised by the code that
wrote it has no compatibility promises.
"""

from eichstelle.record.record import (
    ENTRY,
    ENTRY_FIELDS,
    FORMAT_VERSION,
    GENERATED,
    HEADER,
    RECORD_SCHEMA_FILE,
    SUMMARY,
    TIMESTAMP_FORMAT,
    Counts,
    Record,
    RecordError,
    Writer,
    now,
    read,
    read_lines,
    this_machine,
)

__all__ = [
    "ENTRY",
    "ENTRY_FIELDS",
    "FORMAT_VERSION",
    "GENERATED",
    "HEADER",
    "RECORD_SCHEMA_FILE",
    "SUMMARY",
    "TIMESTAMP_FORMAT",
    "Counts",
    "Record",
    "RecordError",
    "Writer",
    "now",
    "read",
    "read_lines",
    "this_machine",
]
