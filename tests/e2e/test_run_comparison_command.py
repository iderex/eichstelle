"""The command an operator runs to see what moved, and what its exit code says.

Three exit codes rather than two, and the third is the one that matters. A
caller scripting this has to tell a run where nothing moved from a run where
something did, and both of those from a refusal to compare at all. Folding the
refusal into either of the other two turns a comparison that never happened into
a comparison that found nothing.

The records here are written by the writer this project ships rather than
assembled as text, so what the command reads is what a run produces.
"""

from pathlib import Path
from typing import Any

import pytest

from eichstelle.record import Writer
from eichstelle.runs.__main__ import main

ADAPTERS = [{"identifier": "fake", "upstream_version": "1.2.3"}]


def write_record(
    path: Path, entries: list[dict[str, Any]], *, checksum: str = "sha256:same"
) -> Path:
    """A finished record at `path`, carrying those entries."""
    with Writer(
        path=path,
        fixture_set_version="2026.08",
        fixture_set_checksum=checksum,
        harness_version="0.1.0",
        adapters=ADAPTERS,
        possible=len(entries),
    ) as writer:
        for fields in entries:
            writer.entry({"source": "generated", **fields}, produced=True)
    return path


def entry(**over: Any) -> dict[str, Any]:
    """One entry of a record, and the base of the neighbours below."""
    fields: dict[str, Any] = {
        "fixture_id": "anchor-loudness",
        "fixture_revision": 1,
        "standard": "ISO 532",
        "part": "1",
        "edition": 2017,
        "adapter": "fake",
        "adapter_upstream_version": "1.2.3",
        "verdict": "agrees",
        "produced": ["1.02"],
        "produced_unit": "sone",
        "expected": "1.00",
        "expected_unit": "sone",
        "tolerance": "0.05",
        "tolerance_kind": "absolute",
        "margin": "0.40",
        "duration_seconds": "0.5",
    }
    fields.update(over)
    return fields


def test_nothing_moved_is_exit_zero(tmp_path: Path, capsys: Any) -> None:
    """The state a scheduled comparison is expected to be in most of the time."""
    before = write_record(tmp_path / "before.jsonl", [entry()])
    after = write_record(tmp_path / "after.jsonl", [entry()])

    assert main([str(before), str(after)]) == 0
    assert "Nothing moved." in capsys.readouterr().out


def test_something_moved_is_exit_one(tmp_path: Path, capsys: Any) -> None:
    """A verdict that moved is the product, and the exit code says there is one."""
    before = write_record(tmp_path / "before.jsonl", [entry()])
    after = write_record(
        tmp_path / "after.jsonl", [entry(verdict="disagrees", margin="-0.10")]
    )

    assert main([str(before), str(after)]) == 1
    assert "agrees then disagrees" in capsys.readouterr().out


def test_an_incomparable_pair_is_exit_two(tmp_path: Path, capsys: Any) -> None:
    """Distinct from both, because nothing was compared.

    Exit 1 here would put a refusal in the same column as a finding, and exit 0
    would put it in the same column as a clean run, which is worse.
    """
    before = write_record(tmp_path / "before.jsonl", [entry()])
    after = write_record(
        tmp_path / "after.jsonl",
        [entry(fixture_id="anchor-sharpness")],
        checksum="sha256:different",
    )

    assert main([str(before), str(after)]) == 2
    captured = capsys.readouterr()
    assert "refusing to compare" in captured.err
    assert "anchor-loudness" in captured.err
    assert "anchor-sharpness" in captured.err


def test_a_record_that_cannot_be_read_is_exit_two(tmp_path: Path, capsys: Any) -> None:
    """Failing closed. A comparison that did not happen never reports zero."""
    before = write_record(tmp_path / "before.jsonl", [entry()])

    assert main([str(before), str(tmp_path / "there-is-no-record-here.jsonl")]) == 2
    assert "nothing was compared" in capsys.readouterr().err


@pytest.mark.parametrize(
    "arguments",
    [[], ["only-one"], ["--margin"], ["--margin", "nonsense", "a", "b"]],
    ids=["no arguments", "one path", "a threshold with no value", "a bad threshold"],
)
def test_a_call_that_cannot_be_understood_is_exit_two(
    arguments: list[str], capsys: Any
) -> None:
    """The same code as a refusal, because nothing was compared in either case."""
    assert main(arguments) == 2
    assert capsys.readouterr().err != ""


def test_the_threshold_reaches_the_comparison(tmp_path: Path, capsys: Any) -> None:
    """A drift under the default and over a smaller one, on the same two records."""
    before = write_record(tmp_path / "before.jsonl", [entry(margin="0.4000")])
    after = write_record(tmp_path / "after.jsonl", [entry(margin="0.3999")])

    assert main([str(before), str(after)]) == 0
    assert main(["--margin", "0.00001", str(before), str(after)]) == 1
    assert "margin moved" in capsys.readouterr().out
