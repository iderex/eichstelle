"""Reading a declaration, and deciding a pair against it.

Nothing here invokes anything except `query`, which runs one capabilities job
through the runner. The deciding is a pure function of a fixture and a
declaration, so the rule that decides whether a pair is meaningful can be read,
tested and argued with on its own.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final

from eichstelle.runner import Invocation, RunnerConfiguration, invoke

# The protocol this speaks, echoed into every job. One place rather than a
# literal at each call site.
PROTOCOL_VERSION: Final = 1

# Why a pair was not invoked. Each is a statement about coverage rather than
# about correctness, and a report has to be able to tell them apart: an adapter
# that never claimed the metric and one that claimed the metric but not the
# edition are different findings about the same implementation.
METRIC_NOT_DECLARED: Final = "metric_not_declared"
EDITION_NOT_DECLARED: Final = "edition_not_declared"
SAMPLE_RATE_NOT_ACCEPTED: Final = "sample_rate_not_accepted"
FIELD_CONDITION_NOT_DECLARED: Final = "field_condition_not_declared"
CALIBRATION_CONVENTION_NOT_DECLARED: Final = "calibration_convention_not_declared"

# The two fixture parameters that are matched against the declaration. Anything
# else in `metric_parameters` is the metric's business and is passed through, so
# a metric adding a parameter does not silently start making pairs unsupported.
FIELD_CONDITION: Final = "field_condition"
CALIBRATION_CONVENTION: Final = "calibration_convention"


class DeclarationFailure(Exception):
    """The adapter could not be asked what it does, so it cannot be used.

    Raised once per adapter and never once per fixture. An adapter that fails
    its capability query produces one line in the record saying so, because two
    hundred identical failures say the same thing two hundred times and bury
    every other finding in the run.
    """

    def __init__(self, adapter: str, reason: str, detail: str = "") -> None:
        self.adapter = adapter
        self.reason = reason
        self.detail = detail
        message = f"{adapter}: {reason}"
        super().__init__(f"{message}. {detail}" if detail else message)


@dataclass(frozen=True)
class MetricClaim:
    """What an adapter claims about one metric."""

    metric: str
    editions: tuple[int, ...]
    field_conditions: tuple[str, ...] = ()
    calibration_conventions: tuple[str, ...] = ()


@dataclass(frozen=True)
class Declaration:
    """Everything an adapter said it can do, plus what it loaded to do it."""

    adapter: str
    upstream_version: str
    sample_rates: tuple[int, ...]
    metrics: Mapping[str, MetricClaim]

    @property
    def version_is_known(self) -> bool:
        """Whether the adapter could name the version it loaded.

        The empty string is the declared unknown. It is carried as an unknown
        into the record rather than filled in with a guess, because a version
        nobody can identify is not reproducible and the reader should see that
        rather than a plausible number.
        """
        return self.upstream_version != ""


@dataclass(frozen=True)
class Pair:
    """One fixture against one adapter, as much of it as the decision needs."""

    fixture_id: str
    metric: str
    edition: int
    sample_rate: int
    metric_parameters: Mapping[str, Any]


@dataclass(frozen=True)
class Decision:
    """Whether a pair is worth invoking, and why not when it is not.

    `declared` is the field the record depends on. An entry that was attempted
    was attempted because the adapter claimed it, so an error on it is an error
    on a declared capability. An entry that was not attempted carries `reason`,
    and the two are never collapsed.
    """

    pair: Pair
    declared: bool
    reason: str = ""
    detail: str = ""


def capability_job(timeout_seconds: str) -> dict[str, object]:
    """The job document that asks an adapter what it does.

    It carries no fixture and no signal, because it is about no stimulus. The
    runner owns `result_path` and `working_directory` and refuses a job that
    already carries either, so this builds the rest and nothing more.
    """
    return {
        "protocol_version": PROTOCOL_VERSION,
        "kind": "capabilities",
        "timeout_seconds": timeout_seconds,
    }


def _claims_from(entries: Sequence[Any], adapter: str) -> dict[str, MetricClaim]:
    """Turn the declared list into claims, refusing a metric declared twice."""
    claims: dict[str, MetricClaim] = {}
    for entry in entries:
        metric = entry["metric"]
        if metric in claims:
            raise DeclarationFailure(
                adapter,
                "the declaration names one metric twice",
                f"{metric!r} appears more than once, and the two entries could "
                f"say different things about the same metric",
            )
        claims[metric] = MetricClaim(
            metric=metric,
            editions=tuple(entry["editions"]),
            field_conditions=tuple(entry.get("field_conditions", ())),
            calibration_conventions=tuple(entry.get("calibration_conventions", ())),
        )
    return claims


def declaration_from(invocation: Invocation, adapter: str) -> Declaration:
    """Read a declaration out of what the adapter answered a capabilities job with.

    Separate from `query` so that the reading can be tested without a process,
    and so a caller holding an invocation from somewhere else gets the same
    refusals.
    """
    if invocation.outcome != "measured":
        raise DeclarationFailure(
            adapter,
            "the capability query did not produce an answer",
            f"the invocation ended as {invocation.outcome!r}"
            + (f", cause {invocation.cause!r}" if invocation.cause else "")
            + (f": {invocation.detail}" if invocation.detail else ""),
        )

    document = invocation.declaration
    if document is None:
        raise DeclarationFailure(
            adapter,
            "the answer to the capability query declared nothing",
            "the result validated as a measurement rather than as a declaration, "
            "so this adapter has said nothing about what it can do",
        )

    return Declaration(
        adapter=adapter,
        upstream_version=document["upstream_version"],
        sample_rates=tuple(document["sample_rates"]),
        metrics=_claims_from(document["capabilities"], adapter),
    )


def query(
    *,
    adapter: Sequence[str],
    configuration: RunnerConfiguration,
    name: str | None = None,
) -> Declaration:
    """Ask one adapter what it can do, once, before any fixture is run.

    Raises `DeclarationFailure` for every way this can go wrong, including the
    ways the runner reports rather than raises. The caller records one finding
    against the adapter and moves on to the next one; nothing about this failure
    is attributable to any fixture, so nothing is recorded against one.
    """
    label = name if name is not None else " ".join(adapter)
    invocation = invoke(
        adapter=adapter,
        job=capability_job(str(configuration.timeout_seconds)),
        configuration=configuration,
    )
    return declaration_from(invocation, label)


def decide(pair: Pair, declaration: Declaration) -> Decision:
    """Whether this pair is meaningful, decided before anything is invoked.

    The order of the checks is the order a reader wants the reason in. A metric
    that is not claimed at all is a more useful thing to be told than an edition
    mismatch inside a metric that is not claimed either.
    """
    claim = declaration.metrics.get(pair.metric)
    if claim is None:
        declared = ", ".join(sorted(declaration.metrics)) or "nothing"
        return Decision(
            pair=pair,
            declared=False,
            reason=METRIC_NOT_DECLARED,
            detail=(
                f"{declaration.adapter} does not claim {pair.metric!r}; it claims "
                f"{declared}"
            ),
        )

    if pair.edition not in claim.editions:
        editions = ", ".join(str(year) for year in claim.editions)
        return Decision(
            pair=pair,
            declared=False,
            reason=EDITION_NOT_DECLARED,
            detail=(
                f"{declaration.adapter} claims {pair.metric!r} under {editions} "
                f"and this fixture is under {pair.edition}"
            ),
        )

    if pair.sample_rate not in declaration.sample_rates:
        rates = ", ".join(str(rate) for rate in declaration.sample_rates)
        return Decision(
            pair=pair,
            declared=False,
            reason=SAMPLE_RATE_NOT_ACCEPTED,
            detail=(
                f"{declaration.adapter} accepts {rates} Hz and this fixture is at "
                f"{pair.sample_rate} Hz"
            ),
        )

    for parameter, declared_values, reason in (
        (FIELD_CONDITION, claim.field_conditions, FIELD_CONDITION_NOT_DECLARED),
        (
            CALIBRATION_CONVENTION,
            claim.calibration_conventions,
            CALIBRATION_CONVENTION_NOT_DECLARED,
        ),
    ):
        asked = pair.metric_parameters.get(parameter)
        if asked is None:
            continue
        if asked not in declared_values:
            claimed = ", ".join(declared_values) or "none"
            return Decision(
                pair=pair,
                declared=False,
                reason=reason,
                detail=(
                    f"{declaration.adapter} claims {claimed} for {parameter} on "
                    f"{pair.metric!r} and this fixture asks for {asked!r}"
                ),
            )

    return Decision(pair=pair, declared=True)


def plan(pairs: Sequence[Pair], declaration: Declaration) -> list[Decision]:
    """Decide every pair, in the order given, so a run is reproducible."""
    return [decide(pair, declaration) for pair in pairs]


# What a record entry says when the adapter had claimed the pair. Each of these
# is a stronger finding than the same shape from an undeclared pair, and the
# suffix is what carries that into a record a later reader aggregates.
DECLINED_DESPITE_DECLARING: Final = "declined_a_declared_capability"
FAILED_ON_DECLARED_CAPABILITY: Final = "failed_on_a_declared_capability"
TIMED_OUT_ON_DECLARED_CAPABILITY: Final = "timed_out_on_a_declared_capability"


def verdict_for(decision: Decision, invocation: Invocation | None) -> tuple[str, str]:
    """The verdict and the reason a record entry carries for this pair.

    This is where the distinction the declaration exists for reaches the record.
    An `unsupported` entry from a pair that was never invoked carries the reason
    it was not, and an entry from a pair the adapter DID claim carries a reason
    saying so. Both can be `unsupported` in the verdict column, and a report that
    could not tell them apart would put an implementation that honestly declined
    beside one that claimed a metric and then declined it anyway.

    `invocation` is None for a pair that was not invoked. A declared pair with no
    invocation is `not_run` rather than anything else: the run did not reach it,
    and saying otherwise would report coverage the run does not have.

    A `measured` outcome returns no verdict here. What a produced value is worth
    is the comparator's decision and this module does not have the fixture's
    tolerance, so it says so by refusing rather than by guessing.
    """
    if not decision.declared:
        return "unsupported", decision.reason
    if invocation is None:
        return "not_run", "the run did not reach this pair"
    if invocation.outcome == "unsupported":
        return "unsupported", DECLINED_DESPITE_DECLARING
    if invocation.outcome == "errored":
        cause = invocation.cause or "unknown"
        return "errored", f"{cause}: {FAILED_ON_DECLARED_CAPABILITY}"
    if invocation.outcome == "timed_out":
        return "timed_out", TIMED_OUT_ON_DECLARED_CAPABILITY
    raise ValueError(
        f"a {invocation.outcome!r} invocation produced a value, and what that "
        f"value is worth is the comparator's decision rather than this one"
    )
