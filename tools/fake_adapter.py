"""An adapter that computes nothing and can misbehave on demand.

Decision record 0006 says the adapter boundary is a process and a pair of JSON
documents, and it says the reason that carries the decision is this file: if the
boundary is a process and two documents, then a fake adapter is a short script
with no dependencies, and everything above the boundary can be exercised on a
bare runner with no MATLAB license, no scientific stack, no display and no
network.

It is written before the runner on purpose. A contract that has only ever been
satisfied by an adapter written by the same person who wrote the runner is a
contract that has never been tested as a contract, and the questions an outside
author would ask are the ones that go unasked.

It depends on nothing outside the standard library, and that is a property of
this file rather than a preference: it stands in for implementations this
project has never seen, on machines where none of them is installed.

## Invoking it

    python tools/fake_adapter.py <path to the job document>

One argument, exactly as the contract says, and no flags. A flag here would be a
second invocation shape that no real adapter has, and a test double whose
interface differs from the contract is a test double that proves the wrong
thing. What it does instead is read one environment variable:

    EICHSTELLE_FAKE_ADAPTER_BEHAVIOUR

Unset means `ok`. The rest are listed in BEHAVIOURS below, one per way a real
adapter can behave, including the ways the harness has to survive rather than
trust.

## What it answers with

Nothing here computes anything. The value for `ok` is a constant, and the value
for `outside_tolerance` is a different constant far enough away that no sane
tolerance admits it. The job carries no expected value, by design, so a fake
cannot be built that answers correctly in a way that depends on knowing one.
A test that wants agreement writes a fixture expecting OK_VALUE.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Final

# The environment variable that selects a behaviour, and what each one is for.
BEHAVIOUR_VARIABLE: Final = "EICHSTELLE_FAKE_ADAPTER_BEHAVIOUR"

# The answer for `ok`, as a decimal string, and the answer for the run that has
# to come out as a disagreement. Constants rather than anything derived, so a
# test reading this file knows what to expect without running it.
OK_VALUE: Final = "1.0"
OUTSIDE_TOLERANCE_VALUE: Final = "1000.0"

# A unit per metric, so a result looks like a result. Any metric not named here
# answers in the fallback, which is honest: this adapter does not know what it
# would be computing.
UNITS: Final = {
    "loudness": "sone",
    "sharpness": "acum",
    "roughness": "asper",
    "fluctuation_strength": "vacil",
    "tonality": "tu",
}
FALLBACK_UNIT: Final = "1"

# What this adapter claims when asked. Two metrics and two editions, which is
# enough for a caller to see a claimed metric, an unclaimed metric, a claimed
# edition and an unclaimed one without a second fake. Loudness carries a field
# condition and sharpness carries none, so both sides of that rule are reachable
# too.
CAPABILITIES: Final = [
    {
        "metric": "loudness",
        "editions": [2017],
        "field_conditions": ["free"],
        "calibration_conventions": ["full_scale_sine"],
    },
    {"metric": "sharpness", "editions": [2009, 2017]},
]

# The rates this adapter accepts, enumerated rather than described. A real
# adapter lists what its library takes; this one lists two so that a fixture at
# a third rate is a case a test can reach.
SAMPLE_RATES: Final = [44100, 48000]

# The version of the implementation this adapter wrapped, as loaded. There is no
# implementation here, so the string says that rather than inventing a number.
UPSTREAM_VERSION: Final = "fake-adapter-no-upstream"

BEHAVIOURS: Final = (
    "ok",
    "outside_tolerance",
    "unsupported",
    "error",
    "exit_non_zero",
    "malformed_result",
    "no_result",
    "hang",
    "write_outside_working_directory",
    "declaration_missing_version",
    "declares_everything",
)


def read_job(path: Path) -> dict[str, Any]:
    """Read the job document, or say why it could not be read and stop."""
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise TypeError(f"the job at {path} is not a JSON object")
    return document


def measurement(job: dict[str, Any], *, value: str) -> dict[str, Any]:
    """A well-formed `ok` result for the metric the job named."""
    metric = job.get("metric", "")
    return {
        "protocol_version": 1,
        "fixture_id": job.get("fixture_id", ""),
        "status": "ok",
        "values": [value],
        "unit": UNITS.get(metric, FALLBACK_UNIT),
        "edition": job.get("edition", 0),
        "diagnostic": "",
    }


def declined(job: dict[str, Any], *, status: str, reason: str) -> dict[str, Any]:
    """A result that declines or fails, carrying no values.

    A number alongside `unsupported` or `error` is a contradiction, and the
    schema refuses one, so the fake must not be able to produce it by accident
    while pretending to be a well-behaved adapter.
    """
    return {
        "protocol_version": 1,
        "fixture_id": job.get("fixture_id", ""),
        "status": status,
        "values": [],
        "diagnostic": reason,
    }


def capability_declaration(**over: Any) -> dict[str, Any]:
    """The answer to a capabilities job."""
    document: dict[str, Any] = {
        "protocol_version": 1,
        "status": "ok",
        "capabilities": [dict(entry) for entry in CAPABILITIES],
        "sample_rates": list(SAMPLE_RATES),
        "upstream_version": UPSTREAM_VERSION,
        "diagnostic": "",
    }
    document.update(over)
    return document


def write(job: dict[str, Any], document: object) -> None:
    """Write a result to the path the job named."""
    Path(job["result_path"]).write_text(
        json.dumps(document, indent=2), encoding="utf-8"
    )


def run(job: dict[str, Any], behaviour: str) -> int:
    """Behave as asked and return the process exit code."""
    if job.get("kind") == "capabilities":
        if behaviour == "declaration_missing_version":
            # A declaration with no version, which the schema refuses. The
            # harness has to record one failure for this adapter rather than a
            # failure for every fixture it would have been asked about.
            document = capability_declaration()
            del document["upstream_version"]
            write(job, document)
            return 0

        if behaviour == "declares_everything":
            # The instinct the contract warns against: claim it all and let the
            # results speak. Every pair then reaches this adapter, and what
            # comes back under `error` is a finding against a DECLARED
            # capability, which is the stronger one.
            write(
                job,
                capability_declaration(
                    capabilities=[
                        {
                            "metric": metric,
                            "editions": [2005, 2009, 2017, 2020, 2025],
                            "field_conditions": ["free", "diffuse"],
                            "calibration_conventions": ["full_scale_sine"],
                        }
                        for metric in UNITS
                    ],
                    sample_rates=[8000, 16000, 22050, 44100, 48000, 96000],
                ),
            )
            return 0

        if behaviour in ("ok", "outside_tolerance", "unsupported"):
            write(job, capability_declaration())
            return 0

    if behaviour in ("declaration_missing_version", "declares_everything"):
        # Outside a capabilities job these two behave like `error`, so a run
        # that reaches a measurement with one of them set gets a finding rather
        # than a silent success.
        write(
            job,
            declined(
                job,
                status="error",
                reason="this behaviour is about the capability declaration",
            ),
        )
        return 0

    if behaviour == "ok":
        write(job, measurement(job, value=OK_VALUE))
        return 0

    if behaviour == "outside_tolerance":
        write(job, measurement(job, value=OUTSIDE_TOLERANCE_VALUE))
        return 0

    if behaviour == "unsupported":
        write(
            job,
            declined(
                job,
                status="unsupported",
                reason="this adapter does not claim that metric at that edition",
            ),
        )
        return 0

    if behaviour == "error":
        write(
            job,
            declined(job, status="error", reason="the model did not converge"),
        )
        return 0

    if behaviour == "exit_non_zero":
        # Exits without writing anything, which is what the harness records as
        # `crashed` rather than as a statement by the adapter.
        print("fake adapter: falling over on purpose", file=sys.stderr)
        return 3

    if behaviour == "malformed_result":
        # Writes something that is not a result, which the harness records as
        # `malformed_result`. Not valid JSON at all, because a file that parses
        # and then fails the schema is the easier half of that case.
        Path(job["result_path"]).write_text("{not json at all", encoding="utf-8")
        return 0

    if behaviour == "no_result":
        # Exits cleanly and writes nothing, which is `no_result`. This is the
        # one a runner is most likely to read as success.
        return 0

    if behaviour == "hang":
        # Sleeps past its own stated limit. The harness terminates it and
        # records `timeout`; nothing here decides that.
        limit = float(job.get("timeout_seconds", "5"))
        time.sleep(limit * 4 + 60)
        return 0

    if behaviour == "write_outside_working_directory":
        # The prohibition the contract states, broken deliberately, so that
        # whoever enforces it has something that actually breaks it. It writes
        # beside the working directory rather than anywhere absolute, so a test
        # can keep the whole thing inside a temporary tree.
        outside = Path(job["working_directory"]).parent / "escaped.txt"
        outside.write_text("an adapter wrote here\n", encoding="utf-8")
        write(job, measurement(job, value=OK_VALUE))
        return 0

    print(
        f"fake adapter: unknown behaviour {behaviour!r}. "
        f"Known: {', '.join(BEHAVIOURS)}",
        file=sys.stderr,
    )
    return 2


def main(argv: list[str] | None = None) -> int:
    """Read the job named on the command line and behave as told."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    if len(arguments) != 1:
        print("usage: python tools/fake_adapter.py JOB_PATH", file=sys.stderr)
        return 2

    behaviour = os.environ.get(BEHAVIOUR_VARIABLE, "ok")
    try:
        job = read_job(Path(arguments[0]))
    except (OSError, TypeError, json.JSONDecodeError) as exc:
        print(f"fake adapter: could not read the job: {exc}", file=sys.stderr)
        return 2

    if job.get("protocol_version") != 1:
        # The reason the field exists. An adapter written against an older
        # contract refuses rather than guessing, and refusing is a non-zero exit
        # because it has no result path it can trust either.
        print(
            f"fake adapter: this adapter speaks protocol version 1, the job says "
            f"{job.get('protocol_version')!r}",
            file=sys.stderr,
        )
        return 2

    return run(job, behaviour)


if __name__ == "__main__":
    sys.exit(main())
