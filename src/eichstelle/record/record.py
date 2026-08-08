"""Writing the result record, and reading one back.

Decision record 0009 makes this file the primary output of a run and everything
a person reads a rendering of it. Newline-delimited JSON: a header on the first
line, one entry per fixture and adapter pair after it, and a summary at the end
of a run that finished.

The writer and the reader are in one module because a format whose compatibility
promises are only ever exercised by the thing that wrote it has no compatibility
promises. The round trip is asserted in the suite, and a reader that ignores
fields it does not know is asserted there too, in both directions: a newer record
stays readable by an older reader, which is the record most worth reading.

## Why the counts are not all in the header

Record 0009 says the header carries how many pairs were possible, how many were
attempted and how many produced a verdict. Two of those three are not knowable
when the header is written, and the same record requires the header to be written
first so that an interrupted run leaves usable results. The two requirements
cannot both be met by one line, and rewriting the header afterwards is refused by
the third: appending never rewrites a byte already on disk.

So `possible` is in the header, where it is known, and `attempted` and `produced`
are in a summary line the writer appends when the run finishes. The header's
`run_finished` is always false, because it is written before the run and can
honestly say nothing else, and that is the marker issue #41 asks for: a record
whose last line is not a summary was interrupted, and its header never claimed
otherwise. A reader of an interrupted record still gets both counts, derived from
the entries it can see, and says so.

## What is deliberately not decided here

Nothing here decides a verdict, computes a margin, or reads a fixture. The
comparator produces the first two and the caller supplies them. This module's
whole job is that what was decided elsewhere survives being written down and read
back.
"""

from __future__ import annotations

import json
import platform
import sys
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from importlib.resources import files
from pathlib import Path
from types import TracebackType
from typing import Any, Final, TextIO

import jsonschema

FORMAT_VERSION: Final = 1
RECORD_SCHEMA_FILE: Final = "schema/result-record-1.schema.json"

HEADER: Final = "header"
ENTRY: Final = "entry"
SUMMARY: Final = "summary"

# The timestamp format, written once and used by everything that writes one.
# UTC with microseconds and a trailing Z: one format at one offset, so two
# records from two machines are comparable without anybody working out a local
# time zone, which is the failure the fixed offset is against rather than a
# preference about how a date looks.
TIMESTAMP_FORMAT: Final = "%Y-%m-%dT%H:%M:%S.%fZ"

# What `source` says when the stimulus came from a fixture description rather
# than from something an operator handed the suite. Record 0011 singles this
# case out: a result computed from a generated signal carries no personal data
# by construction, and it is the case publishing is built around.
GENERATED: Final = "generated"

# The fields an entry always carries, whatever its verdict. A field that
# disappears when it is empty is a field a reader learns to stop looking for,
# which is record 0009's argument about the not-run section applied one level
# down.
ENTRY_FIELDS: Final = (
    "fixture_id",
    "fixture_revision",
    "standard",
    "part",
    "edition",
    "adapter",
    "adapter_upstream_version",
    "verdict",
    "reason",
    "diagnostic",
    "produced",
    "produced_unit",
    "expected",
    "expected_unit",
    "tolerance",
    "tolerance_kind",
    "margin",
    "duration_seconds",
    "source",
)


class RecordError(Exception):
    """The record could not be written or could not be read as one."""


def now() -> str:
    """The current moment, in the one format this project writes."""
    return datetime.now(timezone.utc).strftime(TIMESTAMP_FORMAT)


def this_machine() -> dict[str, str]:
    """What a reader needs to ask whether a finding reproduces elsewhere.

    Record 0009 calls these fields the answer to the first question anybody asks
    about a reported disagreement. They are read from the running interpreter
    rather than passed in, because a caller supplying them is a caller who can
    get them wrong and a record that is wrong about what it ran on is worse than
    one that does not say.
    """
    return {
        "platform": platform.platform(),
        "operating_system": platform.system(),
        "operating_system_version": platform.release(),
        "architecture": platform.machine(),
        "interpreter_version": sys.version.split()[0],
    }


def _validator() -> jsonschema.Draft202012Validator:
    """A validator for one line of a record."""
    text = files("eichstelle").joinpath(RECORD_SCHEMA_FILE).read_text(encoding="utf-8")
    schema = json.loads(text)
    jsonschema.Draft202012Validator.check_schema(schema)
    return jsonschema.Draft202012Validator(schema)


@dataclass(frozen=True)
class Counts:
    """The three counts, never collapsed into one another.

    `derived` says the last two were counted from the entries rather than read
    from a summary, which is the case for an interrupted record. A reader that
    presented a derived count as a stated one would let a partial run look like
    a finished one, which is the whole thing the summary line exists to prevent.
    """

    possible: int
    attempted: int
    produced: int
    derived: bool = False


@dataclass(frozen=True)
class Record:
    """A record read back: its header, its entries, and whether it finished."""

    header: Mapping[str, Any]
    entries: tuple[Mapping[str, Any], ...]
    summary: Mapping[str, Any] | None
    counts: Counts

    @property
    def finished(self) -> bool:
        """Whether the run that wrote this got to the end of itself."""
        return self.summary is not None


@dataclass
class Writer:
    """Writes a record as the run proceeds, one line at a time.

    Used as a context manager. Leaving the block normally appends the summary;
    leaving it because something was raised does not, so a run that died leaves
    a record that says it died rather than one that looks finished.

    Every line is flushed as it is written. A record whose last complete line is
    on disk is the point of the format, and an interrupted run holding its last
    ten entries in a buffer would have thrown that away.
    """

    path: Path
    fixture_set_version: str
    fixture_set_checksum: str
    harness_version: str
    adapters: Sequence[Mapping[str, str]]
    possible: int
    selection: Mapping[str, Any] | None = None
    operator_paths_included: bool = False
    _handle: TextIO | None = field(default=None, init=False, repr=False)
    _attempted: int = field(default=0, init=False, repr=False)
    _produced: int = field(default=0, init=False, repr=False)
    _validate: jsonschema.Draft202012Validator | None = field(
        default=None, init=False, repr=False
    )

    def __enter__(self) -> Writer:
        """Open the file and write the header."""
        if self.possible < 0:
            raise RecordError(f"a run cannot have {self.possible} possible pairs")
        self._validate = _validator()
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._handle = self.path.open("w", encoding="utf-8", newline="\n")
        except OSError as exc:
            raise RecordError(
                f"the record at {self.path} could not be opened: {exc}"
            ) from exc

        header: dict[str, Any] = {
            "kind": HEADER,
            "format_version": FORMAT_VERSION,
            "started_at": now(),
            "harness_version": self.harness_version,
            "fixture_set_version": self.fixture_set_version,
            "fixture_set_checksum": self.fixture_set_checksum,
            **this_machine(),
            "adapters": [dict(adapter) for adapter in self.adapters],
            "possible": self.possible,
            "run_finished": False,
            "operator_paths_included": self.operator_paths_included,
        }
        if self.selection is not None:
            header["selection"] = dict(self.selection)
        self._write(header)
        return self

    def __exit__(
        self,
        kind: type[BaseException] | None,
        value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Append the summary, unless the run is leaving because it failed."""
        try:
            if kind is None:
                self._write(
                    {
                        "kind": SUMMARY,
                        "finished_at": now(),
                        "run_finished": True,
                        "possible": self.possible,
                        "attempted": self._attempted,
                        "produced": self._produced,
                    }
                )
        finally:
            if self._handle is not None:
                self._handle.close()
                self._handle = None

    def entry(
        self,
        fields: Mapping[str, Any],
        *,
        attempted: bool = True,
        produced: bool = False,
        source_path: str | None = None,
    ) -> None:
        """Append one entry.

        `source_path` is the one field that can carry an operator's own
        filesystem layout, and it is dropped unless the operator turned paths
        on. Dropping rather than refusing is deliberate: a caller passing a path
        into a record configured without them has not made an error, it has
        supplied something the operator asked not to be written, and refusing
        the run over it would push a caller towards not passing it at all, which
        removes the option the operator can turn on.
        """
        line: dict[str, Any] = {"kind": ENTRY}
        for name in ENTRY_FIELDS:
            line[name] = fields.get(name)
        for name, value in fields.items():
            if name not in line:
                line[name] = value
        if line.get("source") is None:
            raise RecordError(
                "an entry states no source; use the identifier the operator "
                f"assigned, or {GENERATED!r} for a stimulus this suite produced"
            )
        line["reason"] = line.get("reason") or ""
        line["diagnostic"] = line.get("diagnostic") or ""
        line["produced"] = list(line.get("produced") or [])

        if source_path is not None and self.operator_paths_included:
            line["source_path"] = source_path

        self._write(line)
        if attempted:
            self._attempted += 1
        if produced:
            self._produced += 1

    def _write(self, line: Mapping[str, Any]) -> None:
        """Validate one line and put it on disk before returning."""
        if self._handle is None or self._validate is None:
            raise RecordError("the record is not open")
        errors = sorted(self._validate.iter_errors(dict(line)), key=str)
        if errors:
            where = (
                "/".join(str(part) for part in errors[0].absolute_path) or "the line"
            )
            raise RecordError(
                f"this line does not satisfy the record schema: {where}: "
                f"{errors[0].message}"
            )
        self._handle.write(json.dumps(line, sort_keys=False) + "\n")
        self._handle.flush()


def read(path: Path) -> Record:
    """Read a record back, including one that stops in the middle of a line.

    A run that was killed mid-write leaves a final partial line, and that line
    is dropped with everything before it kept. Refusing the whole file over its
    last few bytes would throw away the results the format exists to preserve.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RecordError(f"the record at {path} could not be read: {exc}") from exc
    return read_lines(text.splitlines(keepends=True))


def read_lines(lines: Sequence[str] | Iterator[str]) -> Record:
    """Read a record from its lines, which is what `read` does with a file."""
    header: Mapping[str, Any] | None = None
    entries: list[Mapping[str, Any]] = []
    summary: Mapping[str, Any] | None = None

    for number, raw in enumerate(lines, start=1):
        if not raw.endswith("\n"):
            # The last line of a killed run. Anything before it is complete and
            # is kept; this is what newline-delimited JSON is chosen for.
            break
        stripped = raw.strip()
        if not stripped:
            continue
        try:
            line = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise RecordError(f"line {number} is not JSON: {exc}") from exc
        if not isinstance(line, dict):
            raise RecordError(f"line {number} is not a JSON object")

        kind = line.get("kind")
        if kind == HEADER:
            if header is not None:
                raise RecordError(f"line {number} is a second header")
            if number != 1:
                raise RecordError(f"the header is on line {number} rather than first")
            header = line
        elif kind == ENTRY:
            if header is None:
                raise RecordError(f"line {number} is an entry before any header")
            if summary is not None:
                raise RecordError(f"line {number} is an entry after the summary")
            entries.append(line)
        elif kind == SUMMARY:
            if header is None:
                raise RecordError(f"line {number} is a summary before any header")
            if summary is not None:
                raise RecordError(f"line {number} is a second summary")
            summary = line
        else:
            # A line shape a newer harness writes and this reader does not know.
            # Skipped rather than refused, for the reason record 0009 gives
            # about unknown fields: refusing makes the record produced by a
            # newer harness against the same fixtures the one that cannot be
            # read.
            continue

    if header is None:
        raise RecordError("the record carries no header")

    if summary is not None:
        counts = Counts(
            possible=int(summary.get("possible", 0)),
            attempted=int(summary.get("attempted", 0)),
            produced=int(summary.get("produced", 0)),
        )
    else:
        counts = Counts(
            possible=int(header.get("possible", 0)),
            attempted=len(entries),
            produced=sum(1 for entry in entries if entry.get("produced")),
            derived=True,
        )

    return Record(header=header, entries=tuple(entries), summary=summary, counts=counts)
