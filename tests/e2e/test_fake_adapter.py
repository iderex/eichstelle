"""The fake adapter, run as a process, once per behaviour it claims.

The fake exists to let everything above the adapter boundary be exercised
without installing any implementation. That is only true if the fake really can
produce each behaviour a real adapter can, so each one is produced here and
looked at, rather than being listed in a document and believed.

The well-behaved answers are validated against the result schema this change
also adds. A fake whose normal output does not satisfy the contract would give
the runner in #33 a false green from its first day.
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import jsonschema
import pytest

ADAPTER = Path(__file__).parent.parent.parent / "tools" / "fake_adapter.py"
SCHEMA_DIRECTORY = Path(__file__).parent.parent.parent / "src" / "eichstelle" / "schema"

BEHAVIOUR_VARIABLE = "EICHSTELLE_FAKE_ADAPTER_BEHAVIOUR"

# The constants the fake documents. Written out here rather than imported from
# it, so that a change to either side is a disagreement between two files a
# reader can see and not a change that quietly moves both at once.
OK_VALUE = "1.0"
OUTSIDE_TOLERANCE_VALUE = "1000.0"


def schema(name: str) -> dict[str, Any]:
    """Read one of the packaged schemas.

    Nothing in the package reads the adapter schemas yet. They are read here
    directly, which is what a consumer outside this project would also do, and
    the runner in #33 is where the harness starts reading them.
    """
    document = json.loads((SCHEMA_DIRECTORY / name).read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    return document


def measurement_job(tmp_path: Path, **overrides: Any) -> dict[str, Any]:
    """A complete measurement job, in a working directory under tmp_path."""
    working = tmp_path / "invocation"
    working.mkdir(exist_ok=True)
    signal = tmp_path / "stimulus.wav"
    signal.write_bytes(b"RIFF")
    job: dict[str, Any] = {
        "protocol_version": 1,
        "kind": "measure",
        "fixture_id": "example-tone-at-forty-decibels",
        "fixture_revision": 1,
        "signal_path": str(signal),
        "sample_rate": 48000,
        "channels": 1,
        "metric": "loudness",
        "metric_parameters": {"field_condition": "free"},
        "standard": "ISO 532",
        "part": "1",
        "edition": 2017,
        "result_path": str(working / "result.json"),
        "working_directory": str(working),
        "timeout_seconds": "5.0",
    }
    job.update(overrides)
    return job


def invoke(
    tmp_path: Path,
    job: dict[str, Any],
    behaviour: str | None = None,
    timeout: float = 30.0,
) -> subprocess.CompletedProcess[str]:
    """Write the job and run the adapter exactly as the contract says."""
    job_path = tmp_path / "job.json"
    job_path.write_text(json.dumps(job, indent=2), encoding="utf-8")
    environment = dict(os.environ)
    if behaviour is None:
        environment.pop(BEHAVIOUR_VARIABLE, None)
    else:
        environment[BEHAVIOUR_VARIABLE] = behaviour
    return subprocess.run(  # noqa: S603
        [sys.executable, str(ADAPTER), str(job_path)],
        capture_output=True,
        text=True,
        check=False,
        cwd=job["working_directory"],
        env=environment,
        timeout=timeout,
    )


def result_of(job: dict[str, Any]) -> Any:
    """Whatever the adapter left at the path the job named."""
    return json.loads(Path(job["result_path"]).read_text(encoding="utf-8"))


def test_the_job_the_tests_build_satisfies_the_job_schema(tmp_path: Path) -> None:
    """Otherwise every test below would be exercising the fake with a bad job."""
    jsonschema.Draft202012Validator(schema("adapter-job-1.schema.json")).validate(
        measurement_job(tmp_path)
    )


def test_the_normal_output_validates_against_the_result_schema(
    tmp_path: Path,
) -> None:
    """The condition the issue names, and the one the runner will rely on."""
    job = measurement_job(tmp_path)

    completed = invoke(tmp_path, job)

    assert completed.returncode == 0, completed.stderr
    result = result_of(job)
    jsonschema.Draft202012Validator(schema("adapter-result-1.schema.json")).validate(
        result
    )
    assert result["status"] == "ok"
    assert result["values"] == [OK_VALUE]
    assert result["unit"] == "sone"
    assert result["fixture_id"] == job["fixture_id"]


def test_a_value_outside_tolerance_is_still_a_valid_result(tmp_path: Path) -> None:
    """A disagreement is a well-formed answer, not a malformed one.

    If the fake could only produce a wrong number by producing a wrong document,
    every disagreement test downstream would be testing the parser instead of
    the comparator.
    """
    job = measurement_job(tmp_path)

    completed = invoke(tmp_path, job, "outside_tolerance")

    assert completed.returncode == 0, completed.stderr
    result = result_of(job)
    jsonschema.Draft202012Validator(schema("adapter-result-1.schema.json")).validate(
        result
    )
    assert result["values"] == [OUTSIDE_TOLERANCE_VALUE]


@pytest.mark.parametrize("status", ["unsupported", "error"])
def test_declining_and_failing_are_different_documents(
    tmp_path: Path, status: str
) -> None:
    """An implementation that declined and one that fell over are not the same.

    A report merging them cannot tell a reader which response either calls for,
    which is why the contract keeps them apart and why neither carries a value.
    """
    job = measurement_job(tmp_path)

    completed = invoke(tmp_path, job, status)

    assert completed.returncode == 0, completed.stderr
    result = result_of(job)
    jsonschema.Draft202012Validator(schema("adapter-result-1.schema.json")).validate(
        result
    )
    assert result["status"] == status
    assert result["values"] == []
    assert result["diagnostic"] != ""


def test_it_can_exit_non_zero_without_writing_a_result(tmp_path: Path) -> None:
    """The `crashed` case: a non-zero exit and nothing to attribute to it."""
    job = measurement_job(tmp_path)

    completed = invoke(tmp_path, job, "exit_non_zero")

    assert completed.returncode != 0
    assert not Path(job["result_path"]).exists()


def test_it_can_write_something_that_is_not_a_result(tmp_path: Path) -> None:
    """The `malformed_result` case: exit zero and a file that does not parse."""
    job = measurement_job(tmp_path)

    completed = invoke(tmp_path, job, "malformed_result")

    assert completed.returncode == 0
    written = Path(job["result_path"]).read_text(encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        json.loads(written)


def test_it_can_exit_cleanly_and_write_nothing(tmp_path: Path) -> None:
    """The `no_result` case, and the one a runner is most likely to read as success.

    Exit zero with no file is indistinguishable from success to anything that
    checks only the exit code, which is why the fake has to be able to produce
    it before the runner is written.
    """
    job = measurement_job(tmp_path)

    completed = invoke(tmp_path, job, "no_result")

    assert completed.returncode == 0
    assert not Path(job["result_path"]).exists()


def test_it_can_run_past_its_own_stated_limit(tmp_path: Path) -> None:
    """The `timeout` case. Nothing in the adapter decides it; the harness does.

    The wait here is deliberately shorter than the limit stated in the job, so
    the test proves the process is still running when it should be and does not
    sit through the fake's whole sleep.
    """
    job = measurement_job(tmp_path, timeout_seconds="5.0")

    with pytest.raises(subprocess.TimeoutExpired):
        invoke(tmp_path, job, "hang", timeout=2.0)

    assert not Path(job["result_path"]).exists()


def test_it_can_write_outside_the_working_directory(tmp_path: Path) -> None:
    """The prohibition, broken on purpose, so whoever enforces it has a case.

    An adapter that writes outside the directory it was given can alter the
    stimulus another adapter will be handed, which turns a disagreement between
    implementations into a disagreement about bytes.
    """
    job = measurement_job(tmp_path)
    escaped = Path(job["working_directory"]).parent / "escaped.txt"
    assert not escaped.exists()

    completed = invoke(tmp_path, job, "write_outside_working_directory")

    assert completed.returncode == 0, completed.stderr
    assert escaped.exists()


def test_a_capabilities_job_gets_a_capability_declaration(tmp_path: Path) -> None:
    """The same job and result files, not a second command-line protocol."""
    working = tmp_path / "invocation"
    working.mkdir(exist_ok=True)
    job = {
        "protocol_version": 1,
        "kind": "capabilities",
        "result_path": str(working / "result.json"),
        "working_directory": str(working),
        "timeout_seconds": "5.0",
    }
    jsonschema.Draft202012Validator(schema("adapter-job-1.schema.json")).validate(job)

    completed = invoke(tmp_path, job)

    assert completed.returncode == 0, completed.stderr
    result = result_of(job)
    jsonschema.Draft202012Validator(schema("adapter-result-1.schema.json")).validate(
        result
    )
    claimed = {entry["metric"] for entry in result["capabilities"]}
    assert claimed == {"loudness", "sharpness"}


def test_a_job_from_another_protocol_version_is_refused(tmp_path: Path) -> None:
    """The reason the field exists: an older contract refuses rather than guesses."""
    job = measurement_job(tmp_path, protocol_version=2)

    completed = invoke(tmp_path, job)

    assert completed.returncode == 2
    assert "protocol version 1" in completed.stderr
    assert not Path(job["result_path"]).exists()


def test_an_unknown_behaviour_is_refused_rather_than_treated_as_normal(
    tmp_path: Path,
) -> None:
    """A typo in the variable must not silently give a well-behaved adapter.

    Falling back to `ok` would turn a misspelt behaviour in a downstream test
    into a test that passes while exercising nothing it named.
    """
    job = measurement_job(tmp_path)

    completed = invoke(tmp_path, job, "okay")

    assert completed.returncode == 2
    assert "unknown behaviour" in completed.stderr
    assert not Path(job["result_path"]).exists()
