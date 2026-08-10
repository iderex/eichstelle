"""The runner, driven through real processes doing real things to it.

Every case here starts an actual adapter. That is deliberate and it is what
makes the file slow: the outcomes this module is responsible for are things an
operating system does, and a mocked subprocess would assert that the runner
handles the cases the mock was written to produce.

`tools/fake_adapter.py` supplies the behaviours the adapter contract names. Two
behaviours the contract does not name are supplied by scripts in
`tests/e2e/adapters/`, because they are about this runner rather than about the
contract: an adapter that writes far more than anyone wants, and one whose
diagnostic is written to be dangerous. A third starts a child and hangs, which
is the case that decides whether a stop reaches processes the adapter began.

Nothing here needs a display, elevation, a network or an acoustics library. The
adapters are this interpreter running a short script from this repository.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from eichstelle.runner import (
    ADAPTER_ERROR,
    CRASHED,
    DEFAULT_CONCURRENCY,
    ERRORED,
    KILLED,
    MALFORMED_RESULT,
    MEASURED,
    NO_RESULT,
    TERMINATED,
    TERMINATION_REACHES_CHILDREN,
    TIMED_OUT,
    UNSUPPORTED,
    Invocation,
    RunnerConfiguration,
    RunnerError,
    invoke,
    invoke_all,
    python_adapter,
)

REPOSITORY = Path(__file__).parent.parent.parent
FAKE = REPOSITORY / "tools" / "fake_adapter.py"
ADAPTERS = Path(__file__).parent / "adapters"

BEHAVIOUR_VARIABLE = "EICHSTELLE_FAKE_ADAPTER_BEHAVIOUR"


def job(**changes: Any) -> dict[str, Any]:
    """A `measure` job without the two fields the runner fills in itself."""
    document: dict[str, Any] = {
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
    }
    document.update(changes)
    return document


@pytest.fixture
def configuration(tmp_path: Path) -> RunnerConfiguration:
    """A configuration whose workspace is a directory this test owns."""
    return RunnerConfiguration(
        workspace=tmp_path / "workspace",
        timeout_seconds=Decimal("30"),
    )


@pytest.fixture
def behaving(monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    """Select a behaviour on the shared fake adapter for one test."""

    def select(behaviour: str) -> tuple[str, ...]:
        monkeypatch.setenv(BEHAVIOUR_VARIABLE, behaviour)
        return python_adapter(FAKE)

    yield select


# ---------------------------------------------------------------------------
# Every failure mode named in issue #33, mapped onto record 0007's vocabulary
# ---------------------------------------------------------------------------


def test_a_good_answer_is_measured_and_not_a_verdict(
    behaving: Any, configuration: RunnerConfiguration
) -> None:
    """An adapter that answered has not yet agreed with anything.

    `measured` rather than `agrees` is the whole of what record 0007 means when
    it says the verdicts are the harness's and not the adapter's. Nothing in the
    runner can reach `agrees`, because reaching it needs a fixture's tolerance
    and a comparison.
    """
    result = invoke(adapter=behaving("ok"), job=job(), configuration=configuration)
    assert result.outcome == MEASURED
    assert result.values == ("1.0",)
    assert result.unit == "sone"
    assert result.edition == 2017
    assert result.exit_code == 0
    assert result.cause is None


def test_a_declined_metric_is_unsupported(
    behaving: Any, configuration: RunnerConfiguration
) -> None:
    """Declining is not failing, and the two do not share an outcome."""
    result = invoke(
        adapter=behaving("unsupported"), job=job(), configuration=configuration
    )
    assert result.outcome == UNSUPPORTED
    assert result.cause is None
    assert "does not claim" in result.diagnostic


def test_an_adapters_own_error_is_errored_with_its_reason(
    behaving: Any, configuration: RunnerConfiguration
) -> None:
    """The adapter said it could not, and the record keeps what it said."""
    result = invoke(adapter=behaving("error"), job=job(), configuration=configuration)
    assert result.outcome == ERRORED
    assert result.cause == ADAPTER_ERROR
    assert result.diagnostic == "the model did not converge"


def test_a_non_zero_exit_with_no_result_is_crashed(
    behaving: Any, configuration: RunnerConfiguration
) -> None:
    """The exit code is kept, because it is the only thing the adapter said."""
    result = invoke(
        adapter=behaving("exit_non_zero"), job=job(), configuration=configuration
    )
    assert result.outcome == ERRORED
    assert result.cause == CRASHED
    assert result.exit_code == 3
    assert "falling over on purpose" in result.stderr.text


def test_a_clean_exit_with_nothing_written_is_no_result(
    behaving: Any, configuration: RunnerConfiguration
) -> None:
    """The one a runner is most likely to read as success, and does not."""
    result = invoke(
        adapter=behaving("no_result"), job=job(), configuration=configuration
    )
    assert result.outcome == ERRORED
    assert result.cause == NO_RESULT
    assert result.exit_code == 0


def test_a_result_that_does_not_validate_is_malformed(
    behaving: Any, configuration: RunnerConfiguration
) -> None:
    """A file that is not a result document is not read as one."""
    result = invoke(
        adapter=behaving("malformed_result"), job=job(), configuration=configuration
    )
    assert result.outcome == ERRORED
    assert result.cause == MALFORMED_RESULT
    assert result.detail


def test_a_result_that_parses_and_fails_the_schema_is_malformed(
    configuration: RunnerConfiguration, tmp_path: Path
) -> None:
    """The harder half of the same case: valid JSON that is not a valid result.

    The shared fake writes bytes that are not JSON at all, which the reader
    refuses before the schema is consulted. This one writes a well-formed
    document claiming `ok` with no values, which only the schema refuses, so the
    validation step is shown to be doing work rather than being reached.
    """
    script = tmp_path / "ok_with_nothing_in_it.py"
    script.write_text(
        "import json, sys\n"
        "from pathlib import Path\n"
        "job = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))\n"
        "Path(job['result_path']).write_text(json.dumps("
        "{'protocol_version': 1, 'status': 'ok', 'diagnostic': ''}"
        "), encoding='utf-8')\n",
        encoding="utf-8",
    )
    result = invoke(
        adapter=python_adapter(script), job=job(), configuration=configuration
    )
    assert result.outcome == ERRORED
    assert result.cause == MALFORMED_RESULT
    assert "does not validate" in result.detail


def test_a_valid_result_followed_by_a_non_zero_exit_is_not_taken(
    configuration: RunnerConfiguration, tmp_path: Path
) -> None:
    """A process that fell over has not made a statement worth trusting.

    This is the ordering nobody writes a test for and everybody assumes: the
    result was there and it validated, and the adapter then exited three. Taking
    the value would record a measurement from a run that failed.
    """
    script = tmp_path / "answer_then_fall_over.py"
    script.write_text(
        "import json, sys\n"
        "from pathlib import Path\n"
        "job = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))\n"
        "Path(job['result_path']).write_text(json.dumps({"
        "'protocol_version': 1, 'fixture_id': job['fixture_id'], 'status': 'ok',"
        "'values': ['1.0'], 'unit': 'sone', 'edition': 2017, 'diagnostic': ''}"
        "), encoding='utf-8')\n"
        "sys.exit(3)\n",
        encoding="utf-8",
    )
    result = invoke(
        adapter=python_adapter(script), job=job(), configuration=configuration
    )
    assert result.outcome == ERRORED
    assert result.cause == CRASHED
    assert result.exit_code == 3
    assert result.values == ()


def test_an_adapter_that_cannot_be_started_is_crashed(
    configuration: RunnerConfiguration, tmp_path: Path
) -> None:
    """A missing executable is an outcome, not an exception out of the run."""
    result = invoke(
        adapter=(str(tmp_path / "no-such-adapter"),),
        job=job(),
        configuration=configuration,
    )
    assert result.outcome == ERRORED
    assert result.cause == CRASHED
    assert "could not be started" in result.detail


def test_every_named_failure_mode_reaches_a_verdict(
    monkeypatch: pytest.MonkeyPatch, configuration: RunnerConfiguration
) -> None:
    """None of the contract's behaviours raises, and each lands somewhere.

    The per-case tests above would still pass if a new behaviour arrived and
    escaped as an exception. This one walks the whole set the fake claims and
    asserts the property the issue states: everything comes out as a recorded
    outcome.
    """
    behaviours = [
        "ok",
        "outside_tolerance",
        "unsupported",
        "error",
        "exit_non_zero",
        "malformed_result",
        "no_result",
        "write_outside_working_directory",
    ]
    outcomes = {}
    for behaviour in behaviours:
        monkeypatch.setenv(BEHAVIOUR_VARIABLE, behaviour)
        result = invoke(
            adapter=python_adapter(FAKE), job=job(), configuration=configuration
        )
        outcomes[behaviour] = result.outcome

    assert set(outcomes) == set(behaviours)
    assert set(outcomes.values()) <= {MEASURED, UNSUPPORTED, ERRORED, TIMED_OUT}


# ---------------------------------------------------------------------------
# The limit, and the two steps of stopping
# ---------------------------------------------------------------------------


def test_a_hanging_adapter_is_stopped_and_the_record_says_how(
    behaving: Any, tmp_path: Path
) -> None:
    """The run completes, and which of terminate and kill was reached is kept."""
    configuration = RunnerConfiguration(
        workspace=tmp_path / "workspace",
        timeout_seconds=Decimal("1"),
        grace_seconds=3.0,
    )
    result = invoke(adapter=behaving("hang"), job=job(), configuration=configuration)
    assert result.outcome == TIMED_OUT
    assert result.termination in {TERMINATED, KILLED}
    assert result.duration_seconds >= 1.0
    assert "1 second limit" in result.detail


def test_an_adapter_that_ignores_being_asked_to_stop_is_killed(tmp_path: Path) -> None:
    """The second step, shown rather than assumed.

    An adapter that catches the signal and keeps running is the case the kill
    exists for, and a runner that only ever terminated would pass every test
    above. On Windows there is no signal to catch and no second step to reach,
    so the case is skipped there and the skip says why rather than the file
    quietly containing one fewer test on that platform.
    """
    if os.name == "nt":
        pytest.skip(
            "the two-step stop is a POSIX signal sequence; on Windows an adapter "
            "cannot decline to be terminated, so there is no second step to show"
        )

    script = tmp_path / "deaf_adapter.py"
    script.write_text(
        "import signal, sys, time\n"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        "sys.stderr.write('ignoring\\n')\n"
        "sys.stderr.flush()\n"
        "time.sleep(600)\n",
        encoding="utf-8",
    )
    configuration = RunnerConfiguration(
        workspace=tmp_path / "workspace",
        timeout_seconds=Decimal("1"),
        grace_seconds=2.0,
    )
    result = invoke(
        adapter=python_adapter(script), job=job(), configuration=configuration
    )
    assert result.outcome == TIMED_OUT
    assert result.termination == KILLED


# How many times the measurement below is multiplied to get the limit. The
# measurement and the run it has to cover are the same work on the same machine
# minutes apart, and the same work timed ten times on the machine that produced
# issue #111 varied by a factor of 3.3 between its fastest and slowest sample.
# Four is that factor with room above it, and what makes it defensible is that
# it multiplies a measurement rather than standing on its own.
PROCESS_START_MARGIN = 4

# The limit never goes below this, whatever the measurement says. A machine that
# starts a process in forty milliseconds would otherwise get a limit of under a
# fifth of a second, which is a shorter fuse than the one that has been working,
# and the test's own duration is the limit, so the floor is also what keeps it
# cheap where nothing is wrong.
PROCESS_START_FLOOR = Decimal("1")


def _two_process_starts() -> float:
    """What this machine charges for the process creations a limit must cover.

    The runner starts its clock before the adapter's interpreter does, so a
    limit has to cover starting the adapter, the adapter starting its child, and
    the small write between them. Two of those three are the operating system's
    work and this suite has no say in what they cost. An interpreter that starts
    an interpreter is the same shape, so it is what gets timed.

    It over-estimates on purpose. The inner interpreter here runs to completion
    while the adapter's child only has to be launched, and over-estimating a
    quantity a margin is applied to is the safe direction.

    The maximum of two samples rather than one. The spread between samples is
    the thing that made issue #111 depend on what had run before it, so a single
    sample can land at the bottom of it and produce a limit the next run does
    not fit inside.
    """
    samples = []
    for _ in range(2):
        started = time.perf_counter()
        subprocess.run(
            [
                sys.executable,
                "-c",
                "import subprocess, sys;"
                " subprocess.run([sys.executable, '-c', 'pass'], check=True)",
            ],
            capture_output=True,
            check=True,
        )
        samples.append(time.perf_counter() - started)
    return max(samples)


def test_stopping_an_adapter_reaches_a_process_it_started(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The MATLAB case: a runtime the adapter launched must not outlive it.

    `TERMINATION_REACHES_CHILDREN` is what this asserts against, in both
    directions, so the test says what the platform actually does rather than
    passing everywhere by asking for less. On Windows the constant is False and
    the assertion is that the child survives, which is the documented
    limitation rather than a hidden one.

    The limit is measured rather than written down, for the reason in issue
    #111: the constant here was one second, and one second is less than this
    platform charges for two process creations, so the adapter was killed before
    it had recorded the child and the assertion could not be made at all. The
    limit is also this test's duration, because the adapter is written to sleep
    past any limit, so a number large enough for the slowest machine would be
    paid by every run on the fastest one. Measuring is what avoids choosing
    between those two.
    """
    measured = _two_process_starts()
    limit = max(
        PROCESS_START_FLOOR,
        Decimal(str(round(measured * PROCESS_START_MARGIN, 3))),
    )
    pid_file = tmp_path / "child.pid"
    configuration = RunnerConfiguration(
        workspace=tmp_path / "workspace",
        timeout_seconds=limit,
        grace_seconds=3.0,
    )
    monkeypatch.setenv("EICHSTELLE_CHILD_PID_FILE", str(pid_file))
    result = invoke(
        adapter=python_adapter(ADAPTERS / "parent_adapter.py"),
        job=job(),
        configuration=configuration,
    )

    assert result.outcome == TIMED_OUT
    # Said rather than left as a bare FileNotFoundError from the read below,
    # which is how issue #111 presented and which named neither the limit nor
    # the reason the file was absent.
    assert pid_file.exists(), (
        "the adapter was stopped before it recorded the child it started, so "
        "nothing here says whether the stop reached that child. The limit was "
        f"{limit} seconds, from {measured:.3f} seconds measured for two process "
        f"starts on this machine times a margin of {PROCESS_START_MARGIN}, and "
        "the adapter needed longer than that to start one"
    )
    child = int(pid_file.read_text(encoding="utf-8"))
    try:
        assert _is_running(child) is not TERMINATION_REACHES_CHILDREN
    finally:
        _make_sure_it_is_gone(child)


def _is_running(pid: int) -> bool:
    """Whether a process is still there, asked of the operating system."""
    if os.name == "nt":  # pragma: no cover - exercised on Windows only
        listing = subprocess.run(  # noqa: S603
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"],  # noqa: S607
            capture_output=True,
            text=True,
            check=False,
        )
        return str(pid) in listing.stdout
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:  # pragma: no cover - not this test's own child
        return True
    return True


def _make_sure_it_is_gone(pid: int) -> None:
    """Leave no process behind, whichever way the assertion went."""
    try:
        os.kill(pid, getattr(__import__("signal"), "SIGKILL", 9))
    except (ProcessLookupError, PermissionError, OSError):  # pragma: no cover
        pass


# ---------------------------------------------------------------------------
# The bound on captured output
# ---------------------------------------------------------------------------


def test_the_output_cap_holds_against_a_noisy_adapter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A runaway adapter fills neither memory nor a disk, and says it was cut.

    The adapter writes a megabyte to each stream against a cap of four kilobytes
    and then answers correctly, so the capture being bounded and the measurement
    surviving are shown in the same run. A prefix presented as the whole would
    pass the size assertion, which is why `truncated` is asserted too and the
    real byte count is kept.
    """
    cap = 4096
    noise = 1024 * 1024
    configuration = RunnerConfiguration(
        workspace=tmp_path / "workspace",
        timeout_seconds=Decimal("60"),
        output_cap_bytes=cap,
    )
    monkeypatch.setenv("EICHSTELLE_NOISY_BYTES", str(noise))
    result = invoke(
        adapter=python_adapter(ADAPTERS / "noisy_adapter.py"),
        job=job(),
        configuration=configuration,
    )

    assert result.outcome == MEASURED
    for capture in (result.stdout, result.stderr):
        assert len(capture.text.encode("utf-8")) <= cap
        assert capture.truncated is True
        assert capture.byte_count >= noise


def test_output_under_the_cap_is_kept_whole(
    behaving: Any, configuration: RunnerConfiguration
) -> None:
    """The cap does not truncate an adapter that stayed inside it."""
    result = invoke(
        adapter=behaving("exit_non_zero"), job=job(), configuration=configuration
    )
    assert result.stderr.truncated is False
    assert result.stderr.text.strip() == "fake adapter: falling over on purpose"


# ---------------------------------------------------------------------------
# Adapter text is data
# ---------------------------------------------------------------------------


def test_hostile_adapter_text_arrives_unchanged_and_uninterpreted(
    tmp_path: Path,
) -> None:
    """What the adapter wrote is what the record holds, byte for byte.

    The diagnostic carries a shell substitution, backticks, format specifiers
    for two formatting mechanisms, a template placeholder, ANSI escapes, a
    carriage return, a null byte, a JSON string terminator, an HTML attribute
    terminator and a script tag. The assertion is equality with what the adapter
    intended, which fails if anything on the way formatted, escaped, stripped or
    expanded it.

    What this does not prove is that no path exists which would interpret it.
    That is a structural property of the code rather than of one input, and
    issues #49 and #52 are where a rule refusing the shape lands. This test
    shows the runner storing the text as data on the one input that would
    otherwise show it doing something else.
    """
    sys.path.insert(0, str(ADAPTERS))
    try:
        from hostile_adapter import HOSTILE
    finally:
        sys.path.remove(str(ADAPTERS))

    configuration = RunnerConfiguration(
        workspace=tmp_path / "workspace",
        timeout_seconds=Decimal("30"),
    )
    result = invoke(
        adapter=python_adapter(ADAPTERS / "hostile_adapter.py"),
        job=job(),
        configuration=configuration,
    )
    assert result.outcome == MEASURED
    assert result.diagnostic == HOSTILE
    assert result.stderr.text == HOSTILE


# ---------------------------------------------------------------------------
# The working directory
# ---------------------------------------------------------------------------


def test_the_working_directory_is_made_and_removed(
    behaving: Any, tmp_path: Path
) -> None:
    """A fresh directory per invocation, and nothing left behind afterwards."""
    workspace = tmp_path / "workspace"
    configuration = RunnerConfiguration(
        workspace=workspace, timeout_seconds=Decimal("30")
    )
    for _ in range(3):
        assert (
            invoke(
                adapter=behaving("ok"), job=job(), configuration=configuration
            ).outcome
            == MEASURED
        )
    assert list(workspace.iterdir()) == []


def test_the_directory_is_removed_even_when_the_adapter_left_files(
    behaving: Any, tmp_path: Path
) -> None:
    """An adapter may do as it likes inside its directory, and it still goes."""
    workspace = tmp_path / "workspace"
    configuration = RunnerConfiguration(
        workspace=workspace, timeout_seconds=Decimal("30")
    )
    result = invoke(
        adapter=behaving("write_outside_working_directory"),
        job=job(),
        configuration=configuration,
    )
    assert result.outcome == MEASURED
    # The fake writes beside its working directory, which the runner does not
    # prevent and does not clean up. The directory itself is gone; what the
    # adapter put in the workspace is the workspace owner's, and refusing an
    # adapter that writes there is not this issue.
    assert not any(entry.is_dir() for entry in workspace.iterdir())


def test_nothing_is_written_into_the_repository(
    behaving: Any, configuration: RunnerConfiguration
) -> None:
    """The tree is the same afterwards, asked of git rather than of the runner."""
    before = subprocess.run(
        ["git", "status", "--porcelain"],  # noqa: S607
        cwd=str(REPOSITORY),
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert (
        invoke(adapter=behaving("ok"), job=job(), configuration=configuration).outcome
        == MEASURED
    )
    after = subprocess.run(
        ["git", "status", "--porcelain"],  # noqa: S607
        cwd=str(REPOSITORY),
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert before == after


def test_a_workspace_inside_the_installed_package_is_refused() -> None:
    """The one place a workspace may never be, refused where it is configured.

    The runner deletes the directories it makes, so a workspace pointed at the
    installed tree is a configuration that deletes parts of the installation.
    """
    package = Path(str(__import__("eichstelle").__file__)).parent
    with pytest.raises(RunnerError, match="inside the installed package"):
        RunnerConfiguration(
            workspace=package / "workspace", timeout_seconds=Decimal("30")
        )


# ---------------------------------------------------------------------------
# The job document, and the settings
# ---------------------------------------------------------------------------


def test_the_runner_fills_in_the_fields_it_owns(
    configuration: RunnerConfiguration, tmp_path: Path
) -> None:
    """The adapter is handed a directory that exists and a path to write to."""
    script = tmp_path / "echo_the_job.py"
    script.write_text(
        "import json, os, sys\n"
        "from pathlib import Path\n"
        "job = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))\n"
        "Path(job['result_path']).write_text(json.dumps({"
        "'protocol_version': 1, 'fixture_id': job['fixture_id'], 'status': 'ok',"
        "'values': ['1.0'], 'unit': 'sone', 'edition': 2017,"
        "'diagnostic': json.dumps({"
        "'cwd': os.getcwd(), 'working_directory': job['working_directory'],"
        "'timeout_seconds': job['timeout_seconds']})}"
        "), encoding='utf-8')\n",
        encoding="utf-8",
    )
    result = invoke(
        adapter=python_adapter(script), job=job(), configuration=configuration
    )
    assert result.outcome == MEASURED
    reported = __import__("json").loads(result.diagnostic)
    assert (
        Path(reported["cwd"]).resolve() == Path(reported["working_directory"]).resolve()
    )
    assert reported["timeout_seconds"] == "30"


def test_a_job_carrying_a_field_the_runner_owns_is_refused(
    behaving: Any, configuration: RunnerConfiguration
) -> None:
    """A caller cannot name a directory this invocation has not made yet."""
    with pytest.raises(RunnerError, match="already carries"):
        invoke(
            adapter=behaving("ok"),
            job=job(working_directory="/somewhere"),
            configuration=configuration,
        )


def test_the_job_beats_the_configuration_on_the_limit(
    behaving: Any, tmp_path: Path
) -> None:
    """One precedence, stated once: what the job says wins over the default."""
    configuration = RunnerConfiguration(
        workspace=tmp_path / "workspace",
        timeout_seconds=Decimal("600"),
        grace_seconds=3.0,
    )
    result = invoke(
        adapter=behaving("hang"),
        job=job(timeout_seconds="1"),
        configuration=configuration,
    )
    assert result.outcome == TIMED_OUT
    assert result.duration_seconds < 60


def test_a_job_stating_a_limit_that_is_not_one_is_refused(
    behaving: Any, configuration: RunnerConfiguration
) -> None:
    """Nothing here invents a limit for a job that stated a broken one."""
    for stated in ("nonsense", "0", "-5", "Infinity"):
        with pytest.raises(RunnerError):
            invoke(
                adapter=behaving("ok"),
                job=job(timeout_seconds=stated),
                configuration=configuration,
            )


@pytest.mark.parametrize(
    "settings",
    [
        {"timeout_seconds": Decimal("0")},
        {"timeout_seconds": Decimal("-1")},
        {"output_cap_bytes": 0},
        {"concurrency": 0},
    ],
)
def test_a_configuration_that_cannot_mean_what_it_says_is_refused(
    tmp_path: Path, settings: dict[str, Any]
) -> None:
    """Each setting is refused where it is set rather than where it is used."""
    base: dict[str, Any] = {
        "workspace": tmp_path / "workspace",
        "timeout_seconds": Decimal("30"),
    }
    with pytest.raises(RunnerError):
        RunnerConfiguration(**{**base, **settings})


def test_the_default_concurrency_is_one() -> None:
    """Conservative, and written down where a reader will see it move."""
    assert DEFAULT_CONCURRENCY == 1


def test_several_jobs_come_back_in_the_order_they_were_given(
    behaving: Any, tmp_path: Path
) -> None:
    """Concurrency changes the timing of a run and never its record."""
    adapter = behaving("ok")
    jobs = [job(fixture_id=f"fixture-{index}") for index in range(6)]
    configuration = RunnerConfiguration(
        workspace=tmp_path / "workspace",
        timeout_seconds=Decimal("60"),
        concurrency=3,
    )
    results: list[Invocation] = invoke_all(
        adapter=adapter, jobs=jobs, configuration=configuration
    )
    assert len(results) == len(jobs)
    assert all(result.outcome == MEASURED for result in results)
    assert list((configuration.workspace).iterdir()) == []


def test_no_jobs_is_no_invocations(
    behaving: Any, configuration: RunnerConfiguration
) -> None:
    """An empty selection runs nothing rather than running everything."""
    assert (
        invoke_all(adapter=behaving("ok"), jobs=[], configuration=configuration) == []
    )


def test_no_adapter_is_refused(configuration: RunnerConfiguration) -> None:
    """An empty command is a caller defect and not an adapter that crashed."""
    with pytest.raises(RunnerError, match="no adapter"):
        invoke(adapter=(), job=job(), configuration=configuration)
