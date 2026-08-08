"""What the two adapter schemas refuse.

The end-to-end tests run the fake adapter and validate what it writes, which
shows the schemas accepting a good document. That is half a check. A schema that
accepts everything also accepts every good document, and the runner in #33 is
going to lean on these refusals to tell an implementation that declined from one
that fell over.

So each case here is a one-change neighbour of the same valid document: exactly
one field removed or altered, nothing else. A defective document built from
scratch would be refused for reasons nobody chose.
"""

import json
from pathlib import Path
from typing import Any

import jsonschema
import pytest

SCHEMA_DIRECTORY = Path(__file__).parent.parent.parent / "src" / "eichstelle" / "schema"


def validator(name: str) -> jsonschema.Draft202012Validator:
    """A validator for one packaged schema, checked against its own dialect."""
    schema = json.loads((SCHEMA_DIRECTORY / name).read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    return jsonschema.Draft202012Validator(schema)


def measurement_job() -> dict[str, Any]:
    """A valid `measure` job."""
    return {
        "protocol_version": 1,
        "kind": "measure",
        "fixture_id": "example-tone-at-forty-decibels",
        "fixture_revision": 1,
        "signal_path": "/signals/example.wav",
        "sample_rate": 48000,
        "channels": 1,
        "metric": "loudness",
        "metric_parameters": {"field_condition": "free"},
        "standard": "ISO 532",
        "part": "1",
        "edition": 2017,
        "result_path": "/invocations/0001/result.json",
        "working_directory": "/invocations/0001",
        "timeout_seconds": "120.0",
    }


def capability_job() -> dict[str, Any]:
    """A valid `capabilities` job, which is about no fixture."""
    return {
        "protocol_version": 1,
        "kind": "capabilities",
        "result_path": "/invocations/0001/result.json",
        "working_directory": "/invocations/0001",
        "timeout_seconds": "120.0",
    }


def ok_result() -> dict[str, Any]:
    """A valid `ok` measurement result."""
    return {
        "protocol_version": 1,
        "fixture_id": "example-tone-at-forty-decibels",
        "status": "ok",
        "values": ["1.02"],
        "unit": "sone",
        "edition": 2017,
        "diagnostic": "",
    }


def declined_result() -> dict[str, Any]:
    """A valid `unsupported` result, which carries no values."""
    return {
        "protocol_version": 1,
        "fixture_id": "example-tone-at-forty-decibels",
        "status": "unsupported",
        "values": [],
        "diagnostic": "this implementation follows the 2005 edition only",
    }


def capability_result() -> dict[str, Any]:
    """A valid capability declaration."""
    return {
        "protocol_version": 1,
        "status": "ok",
        "capabilities": [{"metric": "loudness", "editions": [2017]}],
        "diagnostic": "",
    }


VALID_JOBS = [("measure", measurement_job), ("capabilities", capability_job)]
VALID_RESULTS = [
    ("ok", ok_result),
    ("unsupported", declined_result),
    ("capabilities", capability_result),
]


@pytest.mark.parametrize(
    "build", [build for _, build in VALID_JOBS], ids=[name for name, _ in VALID_JOBS]
)
def test_a_valid_job_passes(build: Any) -> None:
    """Both job kinds are accepted, so the refusals below mean something."""
    assert list(validator("adapter-job-1.schema.json").iter_errors(build())) == []


@pytest.mark.parametrize(
    "build",
    [build for _, build in VALID_RESULTS],
    ids=[name for name, _ in VALID_RESULTS],
)
def test_a_valid_result_passes(build: Any) -> None:
    """All three result shapes are accepted."""
    assert list(validator("adapter-result-1.schema.json").iter_errors(build())) == []


JOB_REFUSALS = [
    ("a measure job with no signal", measurement_job, lambda d: d.pop("signal_path")),
    ("a measure job with no metric", measurement_job, lambda d: d.pop("metric")),
    ("a measure job with no edition", measurement_job, lambda d: d.pop("edition")),
    ("a job with no result path", measurement_job, lambda d: d.pop("result_path")),
    (
        "a job with no working directory",
        measurement_job,
        lambda d: d.pop("working_directory"),
    ),
    ("a job with no timeout", measurement_job, lambda d: d.pop("timeout_seconds")),
    (
        "a timeout written as a JSON number",
        measurement_job,
        lambda d: d.update({"timeout_seconds": 120.0}),
    ),
    (
        "a job from another protocol version",
        measurement_job,
        lambda d: d.update({"protocol_version": 2}),
    ),
    (
        "a job of no known kind",
        measurement_job,
        lambda d: d.update({"kind": "benchmark"}),
    ),
    (
        "a field the contract does not carry",
        measurement_job,
        lambda d: d.update({"expected": "1.0"}),
    ),
    (
        "a capabilities job naming a fixture",
        capability_job,
        lambda d: d.update({"fixture_id": "example-tone-at-forty-decibels"}),
    ),
    (
        "a capabilities job naming a signal",
        capability_job,
        lambda d: d.update({"signal_path": "/signals/example.wav"}),
    ),
]


@pytest.mark.parametrize(
    ("build", "change"),
    [(build, change) for _, build, change in JOB_REFUSALS],
    ids=[name for name, _, _ in JOB_REFUSALS],
)
def test_the_job_schema_refuses(build: Any, change: Any) -> None:
    """One change to a valid job is refused.

    The last two are the pair worth naming. A capabilities job is about no
    fixture, so one carrying a fixture or a signal invites an adapter to answer
    about a stimulus that was never generated.
    """
    document = build()
    change(document)

    errors = list(validator("adapter-job-1.schema.json").iter_errors(document))

    assert errors != [], document


RESULT_REFUSALS = [
    ("an ok result with no values", ok_result, lambda d: d.update({"values": []})),
    ("an ok result with no unit", ok_result, lambda d: d.pop("unit")),
    ("an ok result with no edition", ok_result, lambda d: d.pop("edition")),
    ("an ok result with no fixture id", ok_result, lambda d: d.pop("fixture_id")),
    ("a result with no status", ok_result, lambda d: d.pop("status")),
    ("a result with no diagnostic", ok_result, lambda d: d.pop("diagnostic")),
    (
        "a status the adapter may not write",
        ok_result,
        lambda d: d.update({"status": "timeout"}),
    ),
    (
        "a value written as a JSON number",
        ok_result,
        lambda d: d.update({"values": [1.02]}),
    ),
    (
        "a value that is not a scalar in a list",
        ok_result,
        lambda d: d.update({"values": "1.02"}),
    ),
    (
        "an unsupported result carrying a value",
        declined_result,
        lambda d: d.update({"values": ["1.02"]}),
    ),
    (
        "a capability declaration about a fixture",
        capability_result,
        lambda d: d.update({"fixture_id": "example-tone-at-forty-decibels"}),
    ),
    (
        "a capability entry claiming no edition",
        capability_result,
        lambda d: d.update({"capabilities": [{"metric": "loudness", "editions": []}]}),
    ),
    (
        "a field the contract does not carry",
        ok_result,
        lambda d: d.update({"confidence": "high"}),
    ),
]


@pytest.mark.parametrize(
    ("build", "change"),
    [(build, change) for _, build, change in RESULT_REFUSALS],
    ids=[name for name, _, _ in RESULT_REFUSALS],
)
def test_the_result_schema_refuses(build: Any, change: Any) -> None:
    """One change to a valid result is refused.

    Two of these are the ones the runner leans on. An `ok` with an empty
    `values` would have a run record agreement it never computed, and an
    `unsupported` carrying a number is a contradiction whose reader takes the
    number.
    """
    document = build()
    change(document)

    errors = list(validator("adapter-result-1.schema.json").iter_errors(document))

    assert errors != [], document
