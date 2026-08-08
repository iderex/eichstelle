"""What an adapter claims, and what the harness does with the claim.

An implementation that does not claim to compute roughness under a given edition
is not wrong about roughness. A suite that prints it in the same column as an
implementation that claimed it and got it wrong is publishing a false
accusation, and this project's credibility rests on not doing that. So the
declaration is a mechanism rather than documentation: it is read once, before
any fixture is run, and a pair it does not cover is never invoked.

The second effect is smaller and immediate. Invoking an implementation on two
hundred fixtures it cannot compute, to collect two hundred error verdicts, is
slow and produces a report nobody can read.

Two failure modes are handled here rather than left to be discovered.

An adapter that cannot answer the query at all is unusable, and that is ONE
finding about the adapter rather than one per fixture. `DeclarationFailure`
carries it, and the caller records it once.

An adapter that declares a capability it does not have will produce errors, and
those errors are a stronger finding than a decline from something undeclared.
`Decision.declared` is what keeps the two apart in the record: an entry that was
attempted was attempted because the adapter said it could, and an entry that was
not carries the reason it was not.
"""

from eichstelle.capabilities.declaration import (
    CALIBRATION_CONVENTION_NOT_DECLARED,
    DECLINED_DESPITE_DECLARING,
    EDITION_NOT_DECLARED,
    FAILED_ON_DECLARED_CAPABILITY,
    FIELD_CONDITION_NOT_DECLARED,
    METRIC_NOT_DECLARED,
    SAMPLE_RATE_NOT_ACCEPTED,
    TIMED_OUT_ON_DECLARED_CAPABILITY,
    Decision,
    Declaration,
    DeclarationFailure,
    MetricClaim,
    Pair,
    capability_job,
    decide,
    declaration_from,
    plan,
    query,
    verdict_for,
)

__all__ = [
    "CALIBRATION_CONVENTION_NOT_DECLARED",
    "DECLINED_DESPITE_DECLARING",
    "EDITION_NOT_DECLARED",
    "FAILED_ON_DECLARED_CAPABILITY",
    "FIELD_CONDITION_NOT_DECLARED",
    "METRIC_NOT_DECLARED",
    "SAMPLE_RATE_NOT_ACCEPTED",
    "TIMED_OUT_ON_DECLARED_CAPABILITY",
    "Decision",
    "Declaration",
    "DeclarationFailure",
    "MetricClaim",
    "Pair",
    "capability_job",
    "decide",
    "declaration_from",
    "plan",
    "query",
    "verdict_for",
]
