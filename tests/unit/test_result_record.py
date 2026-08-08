"""What the record writer puts on disk, and what the reader gets back.

The three properties worth more than the rest, in the order issue #41 puts them:
a round trip changes nothing, an interrupted run leaves a file that is readable
and says it was interrupted, and no filesystem path belonging to an operator
reaches the record unless the operator turned paths on.

The last of those is the one with a person behind it. Decision record 0011 says
the record is the file most likely to be attached to an issue, so the default is
tested from both sides: the path is absent when nobody asked, and it is present
when somebody did, because a switch that does nothing is worse than no switch.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from eichstelle.record import (
    ENTRY_FIELDS,
    FORMAT_VERSION,
    GENERATED,
    Counts,
    RecordError,
    Writer,
    now,
    read,
    read_lines,
    this_machine,
)

ADAPTERS = [{"identifier": "fake", "upstream_version": "0.0.0"}]


def writer(path: Path, **changes: Any) -> Writer:
    """A writer with everything a header needs, ready to be entered."""
    settings: dict[str, Any] = {
        "path": path,
        "fixture_set_version": "0.1.0",
        "fixture_set_checksum": "sha256:0000",
        "harness_version": "0.0.0",
        "adapters": ADAPTERS,
        "possible": 2,
    }
    settings.update(changes)
    return Writer(**settings)


def an_entry(**changes: Any) -> dict[str, Any]:
    """One agreeing entry, with every field an entry always carries."""
    entry: dict[str, Any] = {
        "fixture_id": "loudness-anchor",
        "fixture_revision": 1,
        "standard": "ISO 532",
        "part": "1",
        "edition": 2017,
        "adapter": "fake",
        "adapter_upstream_version": "0.0.0",
        "verdict": "agrees",
        "reason": "",
        "diagnostic": "",
        "produced": ["1.02"],
        "produced_unit": "sone",
        "expected": "1.0",
        "expected_unit": "sone",
        "tolerance": "0.05",
        "tolerance_kind": "absolute",
        "margin": "0.03",
        "duration_seconds": "0.42",
        "source": GENERATED,
    }
    entry.update(changes)
    return entry


# ---------------------------------------------------------------------------
# The round trip
# ---------------------------------------------------------------------------


def test_a_round_trip_preserves_every_field(tmp_path: Path) -> None:
    """What went in comes out, field for field, on the header and the entries.

    Asserted over the whole mapping rather than over a handful of keys. A test
    naming five fields keeps passing when the sixth stops being written, which
    is the way a format quietly loses a column.
    """
    path = tmp_path / "run.ndjson"
    first = an_entry()
    second = an_entry(
        fixture_id="loudness-level-sweep", verdict="disagrees", margin="-2.5"
    )
    with writer(path) as handle:
        handle.entry(first, produced=True)
        handle.entry(second, produced=True)

    back = read(path)
    assert back.finished is True
    assert len(back.entries) == 2
    for written, got in ((first, back.entries[0]), (second, back.entries[1])):
        for name, value in written.items():
            assert got[name] == value, name
    assert back.header["harness_version"] == "0.0.0"
    assert back.header["fixture_set_checksum"] == "sha256:0000"
    assert back.header["adapters"] == ADAPTERS
    assert back.header["format_version"] == FORMAT_VERSION
    assert back.counts == Counts(possible=2, attempted=2, produced=2)


def test_every_entry_carries_every_field_even_when_it_is_empty(tmp_path: Path) -> None:
    """A field that disappears when empty is one a reader stops looking for.

    The entry written here states only what a not-run pair has to say and omits
    every field a comparison would have filled in. All of them come back, empty,
    because the writer fills them rather than leaving a reader to tell an absent
    margin from one that was not computed.
    """
    path = tmp_path / "run.ndjson"
    with writer(path, possible=1) as handle:
        handle.entry(
            {
                "fixture_id": "loudness-anchor",
                "fixture_revision": 1,
                "standard": "ISO 532",
                "part": "1",
                "adapter": "fake",
                "verdict": "not_run",
                "reason": "the operator asked for a subset",
                "duration_seconds": "0.0",
                "source": GENERATED,
            },
            attempted=False,
        )
    entry = read(path).entries[0]
    for name in ENTRY_FIELDS:
        assert name in entry, name
    assert entry["margin"] is None
    assert entry["expected"] is None
    assert entry["edition"] is None
    assert entry["produced"] == []
    assert entry["diagnostic"] == ""


def test_the_header_is_the_first_line_and_the_summary_the_last(tmp_path: Path) -> None:
    """The shape a reader dispatches on, checked as bytes rather than as objects."""
    path = tmp_path / "run.ndjson"
    with writer(path) as handle:
        handle.entry(an_entry(), produced=True)
    lines = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert [line["kind"] for line in lines] == ["header", "entry", "summary"]
    assert lines[0]["run_finished"] is False
    assert lines[-1]["run_finished"] is True


# ---------------------------------------------------------------------------
# The interrupted run
# ---------------------------------------------------------------------------


def test_an_interrupted_run_leaves_a_valid_file_that_says_so(tmp_path: Path) -> None:
    """The run died after two entries and the two entries are still there.

    A run against several implementations over a large fixture set takes real
    time, and a run interrupted after three hours has to leave usable results
    rather than nothing. What it must not leave is something that reads as a
    finished run.
    """
    path = tmp_path / "run.ndjson"
    with pytest.raises(KeyboardInterrupt), writer(path) as handle:
        handle.entry(an_entry(), produced=True)
        handle.entry(an_entry(fixture_id="second"), produced=True)
        raise KeyboardInterrupt

    back = read(path)
    assert back.finished is False
    assert back.summary is None
    assert back.header["run_finished"] is False
    assert len(back.entries) == 2
    assert back.counts == Counts(possible=2, attempted=2, produced=2, derived=True)


def test_the_counts_of_an_interrupted_run_say_they_were_derived(tmp_path: Path) -> None:
    """A derived count presented as a stated one lets a partial run pass for whole."""
    path = tmp_path / "run.ndjson"
    with pytest.raises(RuntimeError), writer(path, possible=100) as handle:
        handle.entry(an_entry(), produced=True)
        raise RuntimeError("the adapter took the machine down with it")
    back = read(path)
    assert back.counts.derived is True
    assert back.counts.possible == 100
    assert back.counts.attempted == 1


def test_a_record_cut_off_mid_line_keeps_everything_before_it(tmp_path: Path) -> None:
    """A process killed mid-write leaves a partial last line and whole earlier ones."""
    path = tmp_path / "run.ndjson"
    with writer(path) as handle:
        handle.entry(an_entry(), produced=True)
        handle.entry(an_entry(fixture_id="second"), produced=True)

    whole = path.read_text(encoding="utf-8")
    cut = (
        whole[: whole.rindex("\n", 0, whole.rindex("\n")) + 1]
        + '{"kind": "entry", "fix'
    )
    path.write_text(cut, encoding="utf-8")

    back = read(path)
    assert len(back.entries) == 2
    assert back.finished is False


def test_every_line_is_on_disk_before_the_next_one_is_written(tmp_path: Path) -> None:
    """Incremental in fact, not in intention: the file grows as entries arrive."""
    path = tmp_path / "run.ndjson"
    with writer(path, possible=3) as handle:
        after_header = len(path.read_text(encoding="utf-8").splitlines())
        handle.entry(an_entry(), produced=True)
        after_one = len(path.read_text(encoding="utf-8").splitlines())
        handle.entry(an_entry(fixture_id="second"), produced=True)
        after_two = len(path.read_text(encoding="utf-8").splitlines())
    assert (after_header, after_one, after_two) == (1, 2, 3)


# ---------------------------------------------------------------------------
# An operator's own material
# ---------------------------------------------------------------------------


def test_no_operator_path_reaches_the_record_by_default(tmp_path: Path) -> None:
    """The path is passed in and is not written, which is the default working."""
    path = tmp_path / "run.ndjson"
    operator_file = "/home/somebody/recordings/ward-3/2026-08-08 interview.wav"
    with writer(path, possible=1) as handle:
        handle.entry(
            an_entry(source="operator-recording-7"),
            produced=True,
            source_path=operator_file,
        )

    text = path.read_text(encoding="utf-8")
    assert operator_file not in text
    assert "recordings" not in text
    assert "source_path" not in text
    back = read(path)
    assert back.entries[0]["source"] == "operator-recording-7"
    assert back.header["operator_paths_included"] is False


def test_an_operator_who_asks_for_paths_gets_them(tmp_path: Path) -> None:
    """A switch that does nothing is worse than no switch.

    Somebody debugging their own run on their own machine needs the path, which
    is why record 0011 makes this a mode rather than a prohibition. The header
    says which mode the record was written in, so a reader never has to read an
    absence as a promise.
    """
    path = tmp_path / "run.ndjson"
    where = "/home/somebody/recordings/one.wav"
    with writer(path, possible=1, operator_paths_included=True) as handle:
        handle.entry(
            an_entry(source="operator-recording-7"), produced=True, source_path=where
        )

    back = read(path)
    assert back.header["operator_paths_included"] is True
    assert back.entries[0]["source_path"] == where


def test_an_entry_with_no_source_is_refused(tmp_path: Path) -> None:
    """A source of nothing is how a path gets written back in as a stand-in."""
    path = tmp_path / "run.ndjson"
    with pytest.raises(RecordError, match="states no source"), writer(path) as handle:
        handle.entry(an_entry(source=None))


# ---------------------------------------------------------------------------
# Compatibility, in both directions
# ---------------------------------------------------------------------------


def test_a_reader_ignores_fields_it_does_not_know(tmp_path: Path) -> None:
    """A newer harness's record stays readable by this reader.

    Refusing an unknown field is not the cautious choice it looks like: the
    record it refuses is one produced by a newer harness against the same
    fixtures, which is the record most worth reading.
    """
    path = tmp_path / "run.ndjson"
    with writer(path, possible=1) as handle:
        handle.entry(
            an_entry(confidence_interval="0.01", experimental_flag=True), produced=True
        )

    back = read(path)
    assert back.entries[0]["confidence_interval"] == "0.01"
    assert back.entries[0]["fixture_id"] == "loudness-anchor"
    assert back.counts.produced == 1


def test_a_line_shape_this_reader_does_not_know_is_skipped() -> None:
    """The same rule one level up, for a line kind rather than a field."""
    lines = [
        json.dumps(
            {
                "kind": "header",
                "format_version": 1,
                "started_at": now(),
                "harness_version": "0.0.0",
                "fixture_set_version": "0.1.0",
                "fixture_set_checksum": "sha256:0000",
                **this_machine(),
                "adapters": ADAPTERS,
                "possible": 1,
                "run_finished": False,
                "operator_paths_included": False,
            }
        )
        + "\n",
        json.dumps({"kind": "annotation", "text": "written by a later harness"}) + "\n",
        json.dumps({"kind": "entry", **an_entry()}) + "\n",
    ]
    back = read_lines(lines)
    assert len(back.entries) == 1
    assert back.finished is False


# ---------------------------------------------------------------------------
# The refusals
# ---------------------------------------------------------------------------


def test_a_record_with_no_header_is_refused(tmp_path: Path) -> None:
    """A file of entries is not a record, because nothing says what it ran on."""
    path = tmp_path / "run.ndjson"
    path.write_text(
        json.dumps({"kind": "entry", **an_entry()}) + "\n", encoding="utf-8"
    )
    with pytest.raises(RecordError, match="before any header"):
        read(path)


def test_an_empty_file_is_not_a_record(tmp_path: Path) -> None:
    """Nothing at all is not an interrupted run, it is not a record."""
    path = tmp_path / "run.ndjson"
    path.write_text("", encoding="utf-8")
    with pytest.raises(RecordError, match="no header"):
        read(path)


def test_an_entry_that_does_not_satisfy_the_schema_is_refused(tmp_path: Path) -> None:
    """The writer validates each line before it is on disk, not afterwards.

    A record is a public interface from its first release, and a line that was
    written and then found to be wrong is a line somebody already has.
    """
    path = tmp_path / "run.ndjson"
    with pytest.raises(RecordError, match="record schema"), writer(path) as handle:
        handle.entry(an_entry(verdict="passed"))


def test_a_second_header_is_refused(tmp_path: Path) -> None:
    """Two runs concatenated into one file are not one run."""
    path = tmp_path / "run.ndjson"
    with writer(path, possible=1) as handle:
        handle.entry(an_entry(), produced=True)
    doubled = path.read_text(encoding="utf-8")
    path.write_text(doubled + doubled, encoding="utf-8")
    with pytest.raises(RecordError, match="second header"):
        read(path)


def test_an_entry_after_the_summary_is_refused(tmp_path: Path) -> None:
    """The summary says the run finished, so nothing may follow it."""
    path = tmp_path / "run.ndjson"
    with writer(path, possible=1) as handle:
        handle.entry(an_entry(), produced=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps({"kind": "entry", **an_entry()}) + "\n")
    with pytest.raises(RecordError, match="after the summary"):
        read(path)


def test_a_line_that_is_not_json_is_refused(tmp_path: Path) -> None:
    """A record whose middle is corrupt is not read as though it were not."""
    path = tmp_path / "run.ndjson"
    with writer(path, possible=1) as handle:
        handle.entry(an_entry(), produced=True)
    text = path.read_text(encoding="utf-8").splitlines(keepends=True)
    text.insert(1, "{ not json\n")
    path.write_text("".join(text), encoding="utf-8")
    with pytest.raises(RecordError, match="not JSON"):
        read(path)


# ---------------------------------------------------------------------------
# The timestamp and the machine
# ---------------------------------------------------------------------------


def test_the_timestamp_is_one_format_at_one_offset(tmp_path: Path) -> None:
    """Two records from two machines are comparable without a time zone table."""
    path = tmp_path / "run.ndjson"
    with writer(path, possible=1) as handle:
        handle.entry(an_entry(), produced=True)
    back = read(path)
    for stamp in (back.header["started_at"], (back.summary or {})["finished_at"]):
        assert stamp.endswith("Z")
        assert len(stamp) == len("2026-08-08T19:21:49.123456Z")


def test_the_header_says_what_it_ran_on(tmp_path: Path) -> None:
    """The first question about a reported disagreement is where it reproduces."""
    path = tmp_path / "run.ndjson"
    with writer(path, possible=1) as handle:
        handle.entry(an_entry(), produced=True)
    header = read(path).header
    for name in (
        "platform",
        "operating_system",
        "operating_system_version",
        "architecture",
        "interpreter_version",
    ):
        assert header[name] == this_machine()[name]


def test_nothing_is_written_where_the_caller_did_not_ask(tmp_path: Path) -> None:
    """The record goes where it was told and the directory below it is made."""
    path = tmp_path / "somewhere" / "deeper" / "run.ndjson"
    with writer(path, possible=1) as handle:
        handle.entry(an_entry(), produced=True)
    assert path.exists()
    assert sorted(entry.name for entry in (tmp_path / "somewhere").rglob("*")) == [
        "deeper",
        "run.ndjson",
    ]
