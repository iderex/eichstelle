"""Asking a real process what it can do, and deciding fixtures against it.

The unit suite checks the decision rule against a declaration built in memory.
This drives the whole thing through the fake adapter as a process: the job goes
out, the declaration comes back, and the fixtures are decided against what the
adapter actually said rather than against what a test assembled.

The four cases the issue that built this asks for are all here, and each one is
driven through the fake rather than described. A declared-but-broken capability,
an undeclared metric, an edition mismatch and a sample-rate mismatch.
"""

from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from eichstelle.capabilities import (
    EDITION_NOT_DECLARED,
    METRIC_NOT_DECLARED,
    SAMPLE_RATE_NOT_ACCEPTED,
    DeclarationFailure,
    Pair,
    capability_job,
    decide,
    plan,
    query,
)
from eichstelle.runner import RunnerConfiguration, invoke, python_adapter

ADAPTER_PATH = Path(__file__).parent.parent.parent / "tools" / "fake_adapter.py"
BEHAVIOUR_VARIABLE = "EICHSTELLE_FAKE_ADAPTER_BEHAVIOUR"


@pytest.fixture
def configuration(tmp_path: Path) -> RunnerConfiguration:
    """A runner pointed at a workspace inside the test's own directory."""
    return RunnerConfiguration(
        workspace=tmp_path / "workspace", timeout_seconds=Decimal("30")
    )


@pytest.fixture
def behaviour(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Set the fake's behaviour for one test, and leave the environment alone."""

    def set_to(value: str | None) -> None:
        if value is None:
            monkeypatch.delenv(BEHAVIOUR_VARIABLE, raising=False)
        else:
            monkeypatch.setenv(BEHAVIOUR_VARIABLE, value)

    set_to(None)
    return set_to


def pair(**over: Any) -> Pair:
    """A fixture the fake's declaration covers, and the base of the neighbours."""
    fields: dict[str, Any] = {
        "fixture_id": "example-tone-at-forty-decibels",
        "metric": "loudness",
        "edition": 2017,
        "sample_rate": 48000,
        "metric_parameters": {"field_condition": "free"},
    }
    fields.update(over)
    return Pair(**fields)


def test_the_declaration_comes_back_from_the_process(
    configuration: RunnerConfiguration,
) -> None:
    """What the fake claims, read off a real invocation.

    The version is the one it says it loaded. It is not a real library version
    because there is no library behind the fake, and the fake says exactly that
    rather than inventing a number.
    """
    declaration = query(
        adapter=python_adapter(ADAPTER_PATH), configuration=configuration, name="fake"
    )

    assert sorted(declaration.metrics) == ["loudness", "sharpness"]
    assert declaration.metrics["loudness"].editions == (2017,)
    assert declaration.metrics["sharpness"].editions == (2009, 2017)
    assert declaration.sample_rates == (44100, 48000)
    assert declaration.upstream_version == "fake-adapter-no-upstream"
    assert declaration.version_is_known is True


def test_the_query_costs_one_invocation_however_many_fixtures_follow(
    configuration: RunnerConfiguration,
) -> None:
    """The declaration is read once and decides every pair without a process.

    This is the second thing the declaration is for. Two hundred fixtures an
    adapter cannot compute would otherwise be two hundred invocations producing
    two hundred error verdicts, which is slow and unreadable in equal measure.
    """
    declaration = query(
        adapter=python_adapter(ADAPTER_PATH), configuration=configuration, name="fake"
    )
    pairs = [
        pair(fixture_id=f"fixture-{index}", metric="roughness") for index in range(200)
    ]

    decisions = plan(pairs, declaration)

    assert len(decisions) == 200
    assert all(decision.declared is False for decision in decisions)
    assert {decision.reason for decision in decisions} == {METRIC_NOT_DECLARED}


def test_an_undeclared_metric_is_decided_without_invoking_anything(
    configuration: RunnerConfiguration,
) -> None:
    """The fake claims loudness and sharpness, and nothing else."""
    declaration = query(
        adapter=python_adapter(ADAPTER_PATH), configuration=configuration, name="fake"
    )
    decision = decide(pair(metric="roughness", metric_parameters={}), declaration)

    assert decision.declared is False
    assert decision.reason == METRIC_NOT_DECLARED


def test_an_edition_mismatch_is_decided_without_invoking_anything(
    configuration: RunnerConfiguration,
) -> None:
    """It claims loudness under 2017 only, so a 2020 fixture is not its problem."""
    declaration = query(
        adapter=python_adapter(ADAPTER_PATH), configuration=configuration, name="fake"
    )
    decision = decide(pair(edition=2020), declaration)

    assert decision.declared is False
    assert decision.reason == EDITION_NOT_DECLARED


def test_a_sample_rate_mismatch_is_decided_without_invoking_anything(
    configuration: RunnerConfiguration,
) -> None:
    """It accepts 44100 and 48000, and a 96 kHz fixture is neither."""
    declaration = query(
        adapter=python_adapter(ADAPTER_PATH), configuration=configuration, name="fake"
    )
    decision = decide(pair(sample_rate=96000), declaration)

    assert decision.declared is False
    assert decision.reason == SAMPLE_RATE_NOT_ACCEPTED


def test_a_declared_capability_that_breaks_is_an_error_on_a_declared_capability(
    configuration: RunnerConfiguration, behaviour: Any
) -> None:
    """The instinct the contract warns against, and what the record has to show.

    The fake is told to claim everything. Every pair is then declared, so every
    pair is invoked, and what comes back is an error. That error is attributable
    to a capability the adapter claimed, which is a stronger finding than a
    decline from something it never claimed, and the two must not arrive in the
    record looking the same.
    """
    behaviour("declares_everything")
    declaration = query(
        adapter=python_adapter(ADAPTER_PATH), configuration=configuration, name="fake"
    )

    decision = decide(pair(metric="roughness", edition=2025), declaration)
    assert decision.declared is True

    invocation = invoke(
        adapter=python_adapter(ADAPTER_PATH),
        job={
            "protocol_version": 1,
            "kind": "measure",
            "fixture_id": decision.pair.fixture_id,
            "fixture_revision": 1,
            "signal_path": str(ADAPTER_PATH),
            "sample_rate": decision.pair.sample_rate,
            "channels": 1,
            "metric": decision.pair.metric,
            "metric_parameters": {},
            "standard": "ECMA-418",
            "part": "2",
            "edition": decision.pair.edition,
            "timeout_seconds": "30",
        },
        configuration=configuration,
    )

    assert invocation.outcome == "errored"
    assert invocation.cause == "adapter_error"


def test_a_declaration_the_schema_refuses_is_one_failure_for_the_adapter(
    configuration: RunnerConfiguration, behaviour: Any
) -> None:
    """An adapter that cannot say what it does is unusable, and says so once.

    The fake writes a declaration with no `upstream_version`, which the result
    schema refuses, so the runner records it as a malformed result. What matters
    here is the shape of what reaches the caller: one exception naming the
    adapter, not a verdict per fixture.
    """
    behaviour("declaration_missing_version")

    with pytest.raises(DeclarationFailure) as raised:
        query(
            adapter=python_adapter(ADAPTER_PATH),
            configuration=configuration,
            name="fake",
        )

    assert raised.value.adapter == "fake"
    assert "did not produce an answer" in raised.value.reason
    assert "malformed_result" in raised.value.detail


def test_an_adapter_that_cannot_be_run_at_all_is_one_failure(
    configuration: RunnerConfiguration,
) -> None:
    """The same shape for the coarsest failure there is."""
    missing = ADAPTER_PATH.parent / "there_is_no_adapter_here.py"

    with pytest.raises(DeclarationFailure) as raised:
        query(
            adapter=python_adapter(missing), configuration=configuration, name="absent"
        )

    assert raised.value.adapter == "absent"


def test_the_capability_job_carries_no_fixture() -> None:
    """It is about no stimulus, and the runner owns the two fields it omits."""
    job = capability_job("30")

    assert job["kind"] == "capabilities"
    assert "fixture_id" not in job
    assert "signal_path" not in job
    assert "result_path" not in job
    assert "working_directory" not in job
