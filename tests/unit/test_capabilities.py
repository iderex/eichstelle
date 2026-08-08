"""The rule that decides whether a fixture and an adapter are worth pairing.

The failure this is against is a report that prints an implementation which
never claimed a metric in the same column as one that claimed it and got it
wrong. That is a false accusation, and no amount of careful wording downstream
repairs it, because the number is already in the table.

So the decision happens before anything is invoked, it is a pure function of a
fixture and a declaration, and every way of not being covered carries its own
reason rather than one shared `unsupported`. An adapter that does not claim the
metric and one that claims the metric but not the edition are different findings
about the same implementation.
"""

from typing import Any

import pytest

from eichstelle.capabilities import (
    CALIBRATION_CONVENTION_NOT_DECLARED,
    DECLINED_DESPITE_DECLARING,
    EDITION_NOT_DECLARED,
    FIELD_CONDITION_NOT_DECLARED,
    METRIC_NOT_DECLARED,
    SAMPLE_RATE_NOT_ACCEPTED,
    Declaration,
    DeclarationFailure,
    MetricClaim,
    Pair,
    decide,
    declaration_from,
    plan,
    verdict_for,
)
from eichstelle.runner import Invocation


def declaration(**over: Any) -> Declaration:
    """A declaration claiming two metrics, and the base of every case below."""
    fields: dict[str, Any] = {
        "adapter": "fake",
        "upstream_version": "1.2.3",
        "sample_rates": (44100, 48000),
        "metrics": {
            "loudness": MetricClaim(
                metric="loudness",
                editions=(2017,),
                field_conditions=("free",),
                calibration_conventions=("full_scale_sine",),
            ),
            "sharpness": MetricClaim(metric="sharpness", editions=(2009, 2017)),
        },
    }
    fields.update(over)
    return Declaration(**fields)


def pair(**over: Any) -> Pair:
    """A fixture the declaration above covers, and the base of every neighbour."""
    fields: dict[str, Any] = {
        "fixture_id": "example",
        "metric": "loudness",
        "edition": 2017,
        "sample_rate": 48000,
        "metric_parameters": {"field_condition": "free"},
    }
    fields.update(over)
    return Pair(**fields)


def test_a_covered_pair_is_declared() -> None:
    """The case every refusal below is a one-change neighbour of.

    Without it the whole file could pass under a rule that declares nothing
    supported, which is the cheapest way to make a set of unsupported tests
    green and would stop the suite ever running.
    """
    decision = decide(pair(), declaration())
    assert decision.declared is True
    assert decision.reason == ""


def test_an_undeclared_metric_is_not_invoked() -> None:
    """An implementation that never claimed roughness is not wrong about it."""
    decision = decide(pair(metric="roughness", metric_parameters={}), declaration())
    assert decision.declared is False
    assert decision.reason == METRIC_NOT_DECLARED
    assert "roughness" in decision.detail
    assert "loudness, sharpness" in decision.detail


def test_an_edition_the_adapter_does_not_claim_is_not_invoked() -> None:
    """A disagreement across editions is about editions, not implementations."""
    decision = decide(pair(edition=2020), declaration())
    assert decision.declared is False
    assert decision.reason == EDITION_NOT_DECLARED
    assert "2017" in decision.detail
    assert "2020" in decision.detail


def test_a_sample_rate_the_adapter_does_not_accept_is_not_invoked() -> None:
    """Enumerated rather than ranged, so this is decidable at all."""
    decision = decide(pair(sample_rate=96000), declaration())
    assert decision.declared is False
    assert decision.reason == SAMPLE_RATE_NOT_ACCEPTED
    assert "96000" in decision.detail


def test_a_field_condition_the_adapter_does_not_claim_is_not_invoked() -> None:
    """Free and diffuse field give different answers for the same signal.

    An adapter that claims loudness and says nothing about which field it
    answers in would produce a value the report cannot attribute, so a fixture
    asking for a condition it did not claim is declined rather than attempted.
    """
    decision = decide(
        pair(metric_parameters={"field_condition": "diffuse"}), declaration()
    )
    assert decision.declared is False
    assert decision.reason == FIELD_CONDITION_NOT_DECLARED
    assert "diffuse" in decision.detail


def test_a_metric_claiming_no_field_condition_declines_a_fixture_asking_for_one() -> (
    None
):
    """Absent is a claim of none rather than a claim of all.

    The other reading is the dangerous one: an adapter that said nothing would
    be handed every field condition and would answer in whichever it defaults
    to, silently.
    """
    decision = decide(
        pair(metric="sharpness", metric_parameters={"field_condition": "free"}),
        declaration(),
    )
    assert decision.declared is False
    assert decision.reason == FIELD_CONDITION_NOT_DECLARED
    assert "none" in decision.detail


def test_a_calibration_convention_the_adapter_does_not_claim_is_not_invoked() -> None:
    """A convention assumed rather than accepted moves every value produced."""
    decision = decide(
        pair(
            metric_parameters={
                "field_condition": "free",
                "calibration_convention": "full_scale_root_mean_square",
            }
        ),
        declaration(),
    )
    assert decision.declared is False
    assert decision.reason == CALIBRATION_CONVENTION_NOT_DECLARED


def test_a_metric_parameter_nobody_matches_on_does_not_make_a_pair_unsupported() -> (
    None
):
    """Only the two parameters the declaration speaks about are matched.

    A metric adding a parameter of its own must not silently make every pair
    unsupported, which is what matching on everything in `metric_parameters`
    would do.
    """
    decision = decide(
        pair(metric_parameters={"field_condition": "free", "time_constant_ms": "125"}),
        declaration(),
    )
    assert decision.declared is True


def test_the_plan_keeps_the_order_it_was_given() -> None:
    """A run is reproducible in its record even where it is not in its timing."""
    pairs = [
        pair(fixture_id="one"),
        pair(fixture_id="two", metric="roughness", metric_parameters={}),
        pair(fixture_id="three", metric="sharpness", metric_parameters={}),
    ]
    decisions = plan(pairs, declaration())
    assert [decision.pair.fixture_id for decision in decisions] == [
        "one",
        "two",
        "three",
    ]
    assert [decision.declared for decision in decisions] == [True, False, True]


def test_an_unknown_version_is_carried_as_unknown() -> None:
    """The empty string is the declared unknown and stays one.

    Filling it in with a guess would attribute a result to a version nobody can
    identify while looking as if somebody had.
    """
    assert declaration().version_is_known is True
    assert declaration(upstream_version="").version_is_known is False


def test_a_query_that_did_not_produce_an_answer_is_one_failure() -> None:
    """An adapter that cannot say what it does is unusable, once."""
    with pytest.raises(DeclarationFailure) as raised:
        declaration_from(
            Invocation(outcome="timed_out", detail="ran past its limit"), "fake"
        )
    assert raised.value.adapter == "fake"
    assert "did not produce an answer" in raised.value.reason
    assert "timed_out" in raised.value.detail


def test_an_answer_that_declares_nothing_is_a_failure() -> None:
    """A measurement in place of a declaration is not a declaration of nothing."""
    with pytest.raises(DeclarationFailure) as raised:
        declaration_from(
            Invocation(outcome="measured", values=("1.0",), unit="sone"), "fake"
        )
    assert "declared nothing" in raised.value.reason


def test_a_metric_declared_twice_is_a_failure() -> None:
    """Two entries for one metric could say different things about it."""
    document = {
        "capabilities": [
            {"metric": "loudness", "editions": [2017]},
            {"metric": "loudness", "editions": [2020]},
        ],
        "sample_rates": [48000],
        "upstream_version": "1.2.3",
    }
    with pytest.raises(DeclarationFailure) as raised:
        declaration_from(Invocation(outcome="measured", declaration=document), "fake")
    assert "twice" in raised.value.reason


def test_an_unsupported_pair_carries_the_reason_it_was_not_invoked() -> None:
    """The record has to say which kind of coverage gap this was."""
    decision = decide(pair(metric="roughness", metric_parameters={}), declaration())
    verdict, reason = verdict_for(decision, None)

    assert verdict == "unsupported"
    assert reason == METRIC_NOT_DECLARED


def test_an_error_on_a_declared_capability_is_marked_as_one() -> None:
    """The distinction the declaration exists to make, in the record's own words.

    Both of these land under `errored` in the verdict column. Without the reason
    a reader cannot tell an implementation that claimed a metric and fell over
    from one that was never asked, which is the difference between a finding and
    a coverage note.
    """
    verdict, reason = verdict_for(
        decide(pair(), declaration()),
        Invocation(outcome="errored", cause="adapter_error"),
    )

    assert verdict == "errored"
    assert reason == "adapter_error: failed_on_a_declared_capability"


def test_declining_a_capability_the_adapter_declared_is_not_the_same_as_not_claiming_it() -> (
    None
):
    """Two `unsupported` entries, and the reasons keep them apart."""
    honest = verdict_for(
        decide(pair(metric="roughness", metric_parameters={}), declaration()), None
    )
    contradictory = verdict_for(
        decide(pair(), declaration()), Invocation(outcome="unsupported")
    )

    assert honest[0] == contradictory[0] == "unsupported"
    assert honest[1] != contradictory[1]
    assert contradictory[1] == DECLINED_DESPITE_DECLARING


def test_a_declared_pair_the_run_never_reached_is_not_run() -> None:
    """Coverage the run does not have is never reported as coverage it has."""
    verdict, _ = verdict_for(decide(pair(), declaration()), None)
    assert verdict == "not_run"


def test_a_produced_value_is_not_this_module_s_to_judge() -> None:
    """It does not hold the tolerance, so it refuses rather than guesses."""
    with pytest.raises(ValueError, match="comparator"):
        verdict_for(
            decide(pair(), declaration()),
            Invocation(outcome="measured", values=("1.0",), unit="sone"),
        )
