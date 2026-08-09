"""A differential run driven by adapters that are real processes.

The unit suite for `eichstelle.compare.differential` proves the arithmetic and
the absences. This proves the thing the arithmetic is about: several
implementations, each a separate process answering across the contract's
boundary, and a spread computed from what came back rather than from what a test
constructed.

Three arrangements, which are the three issue #40 asks for. Adapters that agree,
adapters that disagree slightly, and adapters that disagree grossly. The numbers
they answer with are the only difference between the three, and every other part
of the run is identical, so what the assertions are about is the spread and not
the plumbing.

The declaration is queried through the same route a real run uses, so the
version each value is attributed to is the version the adapter reported having
loaded rather than one this test supplied.
"""

from __future__ import annotations

import os
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from eichstelle.capabilities import query
from eichstelle.compare import (
    AGREEMENT,
    DISAGREEMENT,
    FEWER_THAN_TWO_USABLE,
    NO_OUTCOME,
    Observation,
    differential,
    observations_from_entries,
)
from eichstelle.record import Writer, read
from eichstelle.runner import RunnerConfiguration, invoke, python_adapter

ADAPTER = Path(__file__).parent / "adapters" / "valued_adapter.py"

VALUE_VARIABLE = "EICHSTELLE_VALUED_ADAPTER_VALUE"
VERSION_VARIABLE = "EICHSTELLE_VALUED_ADAPTER_VERSION"

# One tenth of a sone around the loudness anchor. Absolute rather than relative
# so the band in this test is the number written here and not an arithmetic
# result a reader has to reproduce.
FIXTURE: dict[str, Any] = {
    "id": "loudness-anchor-1khz-40db",
    "unit": "sone",
    "expected": "1.0",
    "tolerance": "0.1",
    "tolerance_kind": "absolute",
}


def measurement_job(signal: Path) -> dict[str, object]:
    """A complete measurement job. The runner fills in the rest."""
    return {
        "kind": "measure",
        "fixture_id": FIXTURE["id"],
        "fixture_revision": 1,
        "signal_path": str(signal),
        "sample_rate": 48000,
        "channels": 1,
        "metric": "loudness",
        "metric_parameters": {"field_condition": "free"},
        "standard": "ISO 532",
        "part": "1",
        "edition": 2017,
    }


def observe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    named: dict[str, str],
) -> list[Observation]:
    """Run one adapter process per entry and collect what each answered.

    `named` maps an adapter name to the decimal string it should answer with.
    Each run is a separate process invoked through the runner, and the version
    is read from that adapter's own declaration rather than assumed.
    """
    signal = tmp_path / "stimulus.wav"
    signal.write_bytes(b"RIFF")
    configuration = RunnerConfiguration(
        workspace=tmp_path / "workspace", timeout_seconds=Decimal("30")
    )
    adapter = python_adapter(ADAPTER)

    observations = []
    for name, value in named.items():
        monkeypatch.setenv(VALUE_VARIABLE, value)
        monkeypatch.setenv(VERSION_VARIABLE, f"{name}-1.0")
        declaration = query(adapter=adapter, configuration=configuration, name=name)
        invocation = invoke(
            adapter=adapter, job=measurement_job(signal), configuration=configuration
        )
        assert invocation.outcome == "measured", invocation.detail
        observations.append(
            Observation(
                adapter=name,
                upstream_version=declaration.upstream_version,
                values=invocation.values,
                unit=invocation.unit,
            )
        )
    return observations


def test_three_processes_that_agree_produce_an_agreement_with_its_spread(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Inside the fixture's band, and recorded as a result rather than as silence."""
    result = differential(
        FIXTURE,
        observe(tmp_path, monkeypatch, {"a": "1.00", "b": "1.02", "c": "1.05"}),
    )
    assert result.outcome == AGREEMENT
    assert result.spread == Decimal("0.05")
    assert result.band == Decimal("0.1")
    assert [entry.observation.upstream_version for entry in result.usable] == [
        "a-1.0",
        "b-1.0",
        "c-1.0",
    ]


def test_three_processes_that_disagree_slightly_produce_a_disagreement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Just outside the band, which is the finding this project exists for."""
    result = differential(
        FIXTURE,
        observe(tmp_path, monkeypatch, {"a": "1.00", "b": "1.05", "c": "1.12"}),
    )
    assert result.outcome == DISAGREEMENT
    assert result.spread == Decimal("0.12")
    assert result.exceeds_tolerance is True


def test_three_processes_that_disagree_grossly_report_the_same_shape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A large disagreement is a larger number and not a different kind of result."""
    result = differential(
        FIXTURE,
        observe(tmp_path, monkeypatch, {"a": "1.00", "b": "1.02", "c": "37.5"}),
    )
    assert result.outcome == DISAGREEMENT
    assert result.spread == Decimal("36.5")
    assert result.relative_spread == Decimal("36.5") / Decimal("1.00")
    assert result.high == Decimal("37.5")


def test_one_process_answering_alone_produces_no_differential_outcome(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One implementation agreeing with itself is not a measurement."""
    result = differential(FIXTURE, observe(tmp_path, monkeypatch, {"a": "1.00"}))
    assert result.outcome == NO_OUTCOME
    assert result.reason == FEWER_THAN_TWO_USABLE
    assert result.outcome != AGREEMENT


def test_the_value_compared_came_out_of_the_adapter_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nothing in this test supplied the number the spread was taken over.

    Asserted because it is the property the whole boundary exists for: a value
    this harness computed would make every differential run a comparison of this
    project against itself.
    """
    monkeypatch.delenv(VALUE_VARIABLE, raising=False)
    observations = observe(tmp_path, monkeypatch, {"a": "2.5", "b": "2.5"})
    assert os.environ.get(VALUE_VARIABLE) == "2.5"
    assert [entry.values for entry in observations] == [("2.5",), ("2.5",)]


def test_a_record_written_by_a_run_is_what_a_later_reader_aggregates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The differential survives a round trip through the record on disk.

    Issue #40 asks that a differential outcome reach the record in a form a
    later reader can aggregate, and the record format already carries the whole
    of it: every entry names its fixture, its adapter, the version that adapter
    loaded, and what it produced. So nothing new is written into a record, and
    what is asserted here is that grouping a record's entries by fixture and
    running the same function over them gives the same answer the live run gave.

    That is the stronger claim of the two. A field written alongside the entries
    could disagree with them; a value derived from them cannot.
    """
    observations = observe(
        tmp_path, monkeypatch, {"a": "1.00", "b": "1.02", "c": "37.5"}
    )
    live = differential(FIXTURE, observations)

    path = tmp_path / "record.jsonl"
    with Writer(
        path=path,
        fixture_set_version="0",
        fixture_set_checksum="not-verified",
        harness_version="0.0.0",
        adapters=[
            {"identifier": entry.adapter, "upstream_version": entry.upstream_version}
            for entry in observations
        ],
        possible=len(observations),
    ) as writer:
        for observation in observations:
            writer.entry(
                {
                    "fixture_id": FIXTURE["id"],
                    "fixture_revision": 1,
                    "standard": "ISO 532",
                    "part": "1",
                    "edition": 2017,
                    "adapter": observation.adapter,
                    "adapter_upstream_version": observation.upstream_version,
                    "verdict": "agrees",
                    "reason": "",
                    "produced": list(observation.values),
                    "produced_unit": observation.unit,
                    "expected": FIXTURE["expected"],
                    "expected_unit": FIXTURE["unit"],
                    "tolerance": FIXTURE["tolerance"],
                    "tolerance_kind": FIXTURE["tolerance_kind"],
                    "margin": None,
                    "duration_seconds": "0.1",
                    "source": "generated",
                },
                produced=True,
            )

    record = read(path)
    for_this_fixture = [
        entry for entry in record.entries if entry["fixture_id"] == FIXTURE["id"]
    ]
    from_disk = differential(FIXTURE, observations_from_entries(for_this_fixture))

    assert from_disk.outcome == live.outcome
    assert from_disk.spread == live.spread
    assert [entry.observation.adapter for entry in from_disk.usable] == [
        entry.observation.adapter for entry in live.usable
    ]
    assert [entry.observation.upstream_version for entry in from_disk.usable] == [
        "a-1.0",
        "b-1.0",
        "c-1.0",
    ]
