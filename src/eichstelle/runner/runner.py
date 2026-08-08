"""Invoking an adapter and surviving whatever it does.

An implementation under test is third-party numeric code running in a process
this project does not control. It will segfault, hang, exhaust memory, exit zero
having written nothing, and emit an unbounded quantity of warnings on standard
error. None of that is a defect in this repository, and all of it has to come
out as a recorded outcome rather than as an exception that ends the run.

So there is one entry, `invoke`, and it raises nothing an adapter can cause. The
only exception it lets out is `RunnerError`, which says the harness could not set
up an invocation at all, and every way an adapter can misbehave is a value it
returns instead.

## The outcome vocabulary

Decision record 0007 names six verdicts and three of them are reachable here:
`unsupported`, `errored` and `timed_out`. The fourth state this module produces
is `measured`, which is not a verdict and is deliberately not spelled as one. An
adapter that produced a value has not yet agreed or disagreed with anything; the
comparison decides that, and record 0007 is explicit that the adapter has no
part in it. `not_run` belongs to whatever decided not to attempt the pair, which
happens before this module is called.

Under `errored` the record keeps which of four things happened, in the words
`docs/adapter-contract.md` uses with adapter authors: `adapter_error` when the
adapter said so itself, `crashed` when it exited non-zero without leaving a
well-formed result, `no_result` when it exited cleanly and wrote nothing, and
`malformed_result` when what it wrote does not validate. Record 0007 asks for
exactly that: one verdict in front of a reader who wants one, four causes
underneath for a reader who needs them.

## Three things worth knowing before reading the code

The output cap is enforced while reading rather than after. A cap applied to a
completed capture has already let the runaway adapter fill memory, which is the
failure the cap exists to prevent. Each stream is drained by its own thread that
stops accumulating at the bound and keeps reading afterwards, because a pipe
nobody drains blocks the adapter instead of the adapter blocking on nothing.

Termination is two steps and the record says which one was reached. An adapter
is asked to stop, given a grace period, and killed if it did not take it.

The adapter is started in its own process group where the platform has one, and
the group is signalled rather than the process. A MATLAB or Octave process
launched by an adapter survives a terminated adapter otherwise and keeps the
machine busy for the rest of the run. `TERMINATION_REACHES_CHILDREN` says
whether that holds on the platform this is running on, and it is False on
Windows: a new process group there is not a kill boundary without a job object,
which this module does not build. That is stated rather than left to be
discovered, because a timeout is a verdict in this system and a leaked process
turns the next fixture's timing into somebody's conformance finding.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from decimal import Decimal, DecimalException
from importlib.resources import files
from pathlib import Path
from tempfile import mkdtemp
from typing import IO, Any, Final

import jsonschema

# The states an invocation can end in. Three are record 0007's verdicts and one
# is not a verdict at all, which is the distinction the name is carrying.
MEASURED: Final = "measured"
UNSUPPORTED: Final = "unsupported"
ERRORED: Final = "errored"
TIMED_OUT: Final = "timed_out"

# What `errored` was, in the contract's words rather than in new ones.
ADAPTER_ERROR: Final = "adapter_error"
CRASHED: Final = "crashed"
NO_RESULT: Final = "no_result"
MALFORMED_RESULT: Final = "malformed_result"

# How an adapter that ran past its limit was stopped.
TERMINATED: Final = "terminated"
KILLED: Final = "killed"

# Whether stopping an adapter reaches processes it started.
#
# On POSIX the adapter is started in a new session, which makes it a process
# group leader, and the signal goes to the group. On Windows a new process group
# stops console signals from leaking between processes and is not a kill
# boundary: reaching a grandchild there needs a job object, and this module does
# not build one. False is the honest value and the tests assert against it
# rather than around it.
TERMINATION_REACHES_CHILDREN: Final = sys.platform != "win32"

# The default bound on each captured stream, per invocation. 64 KiB is far more
# than a diagnostic needs and far less than a runaway adapter produces. It is a
# default rather than a rule: the configuration carries it and an operator
# chasing a specific adapter's log can raise it.
DEFAULT_OUTPUT_CAP_BYTES: Final = 64 * 1024

# How long an adapter is given between being asked to stop and being killed.
DEFAULT_GRACE_SECONDS: Final = 5.0

# How many adapters run at once by default.
#
# One. Every other setting in this file is a bound on damage and this one is a
# bound on a false finding: a timeout is a verdict in this system, and a host
# running several multithreaded numeric libraries at once produces timeouts that
# are statements about the machine and get read as statements about somebody's
# software. The argument for the default is in this change's pull request body
# rather than restated here.
DEFAULT_CONCURRENCY: Final = 1

# The protocol this runner speaks, and the result schema for it.
PROTOCOL_VERSION: Final = 1
RESULT_SCHEMA_FILE: Final = "schema/adapter-result-1.schema.json"

# The fields the runner fills in itself. A caller supplying one has built a job
# against a directory this invocation has not made yet.
RUNNER_OWNED_FIELDS: Final = ("result_path", "working_directory")


class RunnerError(Exception):
    """The invocation could not be set up, so nothing was attempted.

    Distinct from everything an adapter can do, all of which is returned rather
    than raised. This is the harness failing, and it is the one thing a caller
    has to handle as an exception.
    """


@dataclass(frozen=True)
class RunnerConfiguration:
    """What the operator decided, and nothing this module decided for them.

    `workspace` is where per-invocation directories are made. It is required and
    has no default, because every default anyone would pick is either the
    repository, which decision record 0010 keeps clean, or a home directory,
    which issue #43 says nothing writes into without being asked.
    """

    workspace: Path
    timeout_seconds: Decimal
    output_cap_bytes: int = DEFAULT_OUTPUT_CAP_BYTES
    grace_seconds: float = DEFAULT_GRACE_SECONDS
    concurrency: int = DEFAULT_CONCURRENCY

    def __post_init__(self) -> None:
        """Refuse a configuration that cannot mean what it says."""
        if self.timeout_seconds <= 0:
            raise RunnerError(
                f"the timeout is {self.timeout_seconds} seconds, and an adapter "
                f"given no time at all is a timeout rather than a measurement"
            )
        if self.output_cap_bytes <= 0:
            raise RunnerError(
                f"the output cap is {self.output_cap_bytes} bytes, which captures "
                f"nothing; a cap that captures nothing is not a cap"
            )
        if self.concurrency < 1:
            raise RunnerError(
                f"the concurrency is {self.concurrency}, and a run with no adapter "
                f"running is not a run"
            )
        # The package's own directory, resolved through any link. An operator
        # who points the workspace at the installed tree gets adapter working
        # directories inside it, and this module deletes those directories.
        package = Path(str(files("eichstelle"))).resolve()
        workspace = self.workspace.resolve()
        if workspace == package or package in workspace.parents:
            raise RunnerError(
                f"the workspace {self.workspace} resolves inside the installed "
                f"package at {package}; nothing this runner creates is written "
                f"into the tree it runs from"
            )


@dataclass(frozen=True)
class Capture:
    """One captured stream, and whether it is all of it."""

    text: str
    truncated: bool
    byte_count: int


@dataclass(frozen=True)
class Invocation:
    """What happened when one adapter was asked one thing.

    `outcome` is `measured`, `unsupported`, `errored` or `timed_out`. `cause` is
    set only under `errored` and says which of the four it was.

    `values`, `unit` and `edition` are the adapter's answer, present only under
    `measured`. They are strings and an integer exactly as they arrived; nothing
    here converts a decimal string to a number, because the comparison is the
    place that decides how a value is read.

    `diagnostic`, `stdout` and `stderr` are arbitrary bytes from a foreign
    program. They are data. Nothing in this module formats them into anything
    that is then interpreted, and nothing downstream may either.
    """

    outcome: str
    cause: str | None = None
    detail: str = ""
    values: tuple[str, ...] = ()
    unit: str | None = None
    edition: int | None = None
    diagnostic: str = ""
    exit_code: int | None = None
    termination: str | None = None
    duration_seconds: float = 0.0
    stdout: Capture = field(default_factory=lambda: Capture("", False, 0))
    stderr: Capture = field(default_factory=lambda: Capture("", False, 0))


def _result_validator() -> jsonschema.Draft202012Validator:
    """A validator for the packaged adapter result schema."""
    text = files("eichstelle").joinpath(RESULT_SCHEMA_FILE).read_text(encoding="utf-8")
    schema = json.loads(text)
    jsonschema.Draft202012Validator.check_schema(schema)
    return jsonschema.Draft202012Validator(schema)


def _drain(
    stream: IO[bytes] | None, cap: int, into: list[bytes], state: list[int]
) -> None:
    """Read a stream to its end, keeping at most `cap` bytes of it.

    The reading does not stop at the cap and the keeping does. A reader that
    stopped would leave the pipe full, and a full pipe blocks the adapter on a
    write instead of letting it run to its own end or to its timeout, which
    turns a noisy adapter into a hang and reports the wrong outcome about it.

    `state[0]` accumulates the total byte count and `state[1]` is 1 once
    something was dropped, so the caller can say the capture is partial rather
    than presenting a prefix as the whole.
    """
    if stream is None:
        return
    kept = 0
    while True:
        chunk = stream.read(8192)
        if not chunk:
            break
        state[0] += len(chunk)
        room = cap - kept
        if room <= 0:
            state[1] = 1
            continue
        if len(chunk) > room:
            into.append(chunk[:room])
            kept = cap
            state[1] = 1
            continue
        into.append(chunk)
        kept += len(chunk)


def _capture(parts: list[bytes], state: list[int]) -> Capture:
    """Turn a drained stream into text that cannot fail to decode.

    Replacement rather than strict decoding: an adapter's log is bytes from a
    foreign program and may not be UTF-8 at all, and refusing to record a
    diagnostic because of its encoding loses the one thing that would explain
    the failure it belongs to.
    """
    return Capture(
        text=b"".join(parts).decode("utf-8", errors="replace"),
        truncated=state[1] == 1,
        byte_count=state[0],
    )


def _stop(process: subprocess.Popen[bytes], grace: float) -> str:
    """Ask the adapter to stop, and kill it if it does not take the offer.

    The signal goes to the group where the platform has one, so that a process
    the adapter started is reached too. Where it does not,
    `TERMINATION_REACHES_CHILDREN` is False and this stops the adapter alone.
    """
    _signal_group(process, signal.SIGTERM)
    try:
        process.wait(timeout=grace)
    except subprocess.TimeoutExpired:
        _signal_group(
            process, signal.SIGKILL if hasattr(signal, "SIGKILL") else signal.SIGTERM
        )
        try:
            process.wait(timeout=grace)
        except subprocess.TimeoutExpired:  # pragma: no cover - the kernel refused
            pass
        return KILLED
    return TERMINATED


def _signal_group(process: subprocess.Popen[bytes], sig: int) -> None:
    """Signal the adapter's process group, or the adapter where there is none.

    The branch is on `sys.platform` rather than on `os.name`, because the type
    checker reads the first one and knows that `os.killpg` does not exist on
    Windows. `TERMINATION_REACHES_CHILDREN` is the same fact stated for a reader
    and for the tests, and the two are derived from the same value below.
    """
    if sys.platform != "win32":
        try:
            os.killpg(os.getpgid(process.pid), sig)
        except (ProcessLookupError, PermissionError):
            pass
        return
    try:  # pragma: no cover - exercised on Windows only
        if sig == signal.SIGTERM:
            process.terminate()
        else:
            process.kill()
    except (ProcessLookupError, PermissionError):  # pragma: no cover - a race
        pass


def _start(
    adapter: Sequence[str], job_path: Path, directory: Path
) -> subprocess.Popen[bytes]:
    """Start the adapter in its own process group, in its own directory."""
    keywords: dict[str, Any] = {}
    if sys.platform == "win32":  # pragma: no cover - exercised on Windows only
        keywords["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        keywords["start_new_session"] = True
    return subprocess.Popen(  # noqa: S603 - the adapter is the thing being run
        [*adapter, str(job_path)],
        cwd=str(directory),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
        **keywords,
    )


def _timeout_for(
    job: Mapping[str, object], configuration: RunnerConfiguration
) -> Decimal:
    """The limit for this invocation: the job's if it states one, else the configuration's.

    Stated once here so that the precedence is in one place. Issue #43 fixes the
    same order for everything else an operator can set.
    """
    stated = job.get("timeout_seconds")
    if stated is None:
        return configuration.timeout_seconds
    try:
        limit = Decimal(str(stated))
    except (DecimalException, ValueError) as exc:
        raise RunnerError(
            f"the job states a timeout of {stated!r}, which is not a number"
        ) from exc
    if not limit.is_finite() or limit <= 0:
        raise RunnerError(f"the job states a timeout of {limit}, which is not a limit")
    return limit


def _read_result(
    path: Path, validator: jsonschema.Draft202012Validator
) -> tuple[dict[str, Any] | None, str]:
    """Read and validate the result document, or say why it is not one."""
    if not path.exists():
        return None, "the adapter wrote no result at the path its job named"
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, f"the result is not readable JSON: {exc}"
    if not isinstance(document, dict):
        return None, "the result is not a JSON object"
    errors = sorted(validator.iter_errors(document), key=str)
    if errors:
        where = (
            "/".join(str(part) for part in errors[0].absolute_path) or "the document"
        )
        return None, f"the result does not validate: {where}: {errors[0].message}"
    return document, ""


def _from_result(document: Mapping[str, Any]) -> Invocation:
    """Map a validated result onto an outcome, per decision record 0007."""
    status = document.get("status")
    diagnostic = str(document.get("diagnostic", ""))

    if status == "unsupported":
        return Invocation(outcome=UNSUPPORTED, diagnostic=diagnostic, exit_code=0)
    if status == "error":
        return Invocation(
            outcome=ERRORED,
            cause=ADAPTER_ERROR,
            detail="the adapter reported that it could not compute the metric",
            diagnostic=diagnostic,
            exit_code=0,
        )

    values = document.get("values", [])
    unit = document.get("unit")
    edition = document.get("edition")
    return Invocation(
        outcome=MEASURED,
        values=tuple(str(value) for value in values),
        unit=str(unit) if unit is not None else None,
        edition=int(edition) if isinstance(edition, int) else None,
        diagnostic=diagnostic,
        exit_code=0,
    )


def invoke(
    *,
    adapter: Sequence[str],
    job: Mapping[str, object],
    configuration: RunnerConfiguration,
) -> Invocation:
    """Run one adapter against one job and return what happened.

    Nothing an adapter does raises out of here. A `RunnerError` means the
    harness could not set the invocation up: a job that already carries the
    fields this runner owns, a timeout that is not a limit, or a workspace that
    cannot be made.

    The working directory is made fresh for this invocation and removed
    afterwards, including when the adapter left files in it, and including when
    the adapter had to be killed.
    """
    if not adapter:
        raise RunnerError("no adapter was named")
    for owned in RUNNER_OWNED_FIELDS:
        if owned in job:
            raise RunnerError(
                f"the job already carries {owned!r}, which this invocation "
                f"decides; the directory it would name does not exist yet"
            )

    limit = _timeout_for(job, configuration)
    validator = _result_validator()

    try:
        configuration.workspace.mkdir(parents=True, exist_ok=True)
        directory = Path(
            mkdtemp(prefix="invocation-", dir=str(configuration.workspace))
        )
    except OSError as exc:
        raise RunnerError(
            f"the working directory could not be made under "
            f"{configuration.workspace}: {exc}"
        ) from exc

    try:
        return _invoke_in(
            adapter=adapter,
            job=job,
            directory=directory,
            limit=limit,
            configuration=configuration,
            validator=validator,
        )
    finally:
        _remove(directory)


def _invoke_in(
    *,
    adapter: Sequence[str],
    job: Mapping[str, object],
    directory: Path,
    limit: Decimal,
    configuration: RunnerConfiguration,
    validator: jsonschema.Draft202012Validator,
) -> Invocation:
    """The body of one invocation, with the working directory already made."""
    result_path = directory / "result.json"
    job_path = directory / "job.json"
    written = {
        **job,
        "protocol_version": job.get("protocol_version", PROTOCOL_VERSION),
        "timeout_seconds": str(limit),
        "result_path": str(result_path),
        "working_directory": str(directory),
    }
    try:
        job_path.write_text(json.dumps(written, indent=2), encoding="utf-8")
    except (OSError, TypeError, ValueError) as exc:
        raise RunnerError(f"the job document could not be written: {exc}") from exc

    started = time.monotonic()
    try:
        process = _start(adapter, job_path, directory)
    except OSError as exc:
        return Invocation(
            outcome=ERRORED,
            cause=CRASHED,
            detail=f"the adapter could not be started: {exc}",
            duration_seconds=time.monotonic() - started,
        )

    out_parts: list[bytes] = []
    err_parts: list[bytes] = []
    out_state = [0, 0]
    err_state = [0, 0]
    readers = [
        threading.Thread(
            target=_drain,
            args=(process.stdout, configuration.output_cap_bytes, out_parts, out_state),
            daemon=True,
        ),
        threading.Thread(
            target=_drain,
            args=(process.stderr, configuration.output_cap_bytes, err_parts, err_state),
            daemon=True,
        ),
    ]
    for reader in readers:
        reader.start()

    termination: str | None = None
    try:
        exit_code: int | None = process.wait(timeout=float(limit))
    except subprocess.TimeoutExpired:
        termination = _stop(process, configuration.grace_seconds)
        exit_code = process.poll()

    for reader in readers:
        reader.join(timeout=configuration.grace_seconds)
    for stream in (process.stdout, process.stderr):
        if stream is not None:
            stream.close()

    duration = time.monotonic() - started
    captured_out = _capture(out_parts, out_state)
    captured_err = _capture(err_parts, err_state)

    if termination is not None:
        return Invocation(
            outcome=TIMED_OUT,
            detail=(
                f"the adapter ran past the {limit} second limit it was given and was "
                f"{termination}"
            ),
            exit_code=exit_code,
            termination=termination,
            duration_seconds=duration,
            stdout=captured_out,
            stderr=captured_err,
        )

    document, why = _read_result(result_path, validator)
    if document is None:
        if exit_code != 0:
            cause, detail = (
                CRASHED,
                (f"the adapter exited {exit_code} and left no usable result: {why}"),
            )
        elif not result_path.exists():
            cause, detail = NO_RESULT, why
        else:
            cause, detail = MALFORMED_RESULT, why
        return Invocation(
            outcome=ERRORED,
            cause=cause,
            detail=detail,
            exit_code=exit_code,
            duration_seconds=duration,
            stdout=captured_out,
            stderr=captured_err,
        )

    if exit_code != 0:
        # A well-formed result and a non-zero exit is a contradiction, and the
        # contract says the exit code alone tells the harness nothing it can
        # attribute to a fixture. The result is not taken: an adapter that fell
        # over after writing has not made a statement worth trusting.
        return Invocation(
            outcome=ERRORED,
            cause=CRASHED,
            detail=(
                f"the adapter wrote a valid result and then exited {exit_code}; a "
                f"result from a process that fell over is not taken"
            ),
            diagnostic=str(document.get("diagnostic", "")),
            exit_code=exit_code,
            duration_seconds=duration,
            stdout=captured_out,
            stderr=captured_err,
        )

    mapped = _from_result(document)
    return Invocation(
        outcome=mapped.outcome,
        cause=mapped.cause,
        detail=mapped.detail,
        values=mapped.values,
        unit=mapped.unit,
        edition=mapped.edition,
        diagnostic=mapped.diagnostic,
        exit_code=exit_code,
        duration_seconds=duration,
        stdout=captured_out,
        stderr=captured_err,
    )


def _remove(directory: Path) -> None:
    """Remove a working directory and everything an adapter left in it.

    Written out rather than `shutil.rmtree`, because a read-only file an adapter
    left behind stops that call on some platforms, and a working directory that
    survives its invocation accumulates until a run fills a disk. A path that
    still cannot be removed is left rather than raised over: the invocation's
    outcome is the thing the caller asked for and a stale directory does not
    change it.
    """
    for path in sorted(
        directory.rglob("*"), key=lambda entry: len(entry.parts), reverse=True
    ):
        try:
            if path.is_dir() and not path.is_symlink():
                path.rmdir()
            else:
                path.chmod(0o600)
                path.unlink()
        except OSError:  # pragma: no cover - platform dependent
            pass
    try:
        directory.rmdir()
    except OSError:  # pragma: no cover - platform dependent
        pass


def invoke_all(
    *,
    adapter: Sequence[str],
    jobs: Sequence[Mapping[str, object]],
    configuration: RunnerConfiguration,
) -> list[Invocation]:
    """Run several jobs, at most `configuration.concurrency` of them at once.

    The results come back in the order the jobs were given, whatever order they
    finished in, so that a run is reproducible in its record even when it is not
    reproducible in its timing.

    Threads rather than processes: every worker here spends its life waiting on
    a subprocess, which is the case a thread is for, and a process pool would
    add a second layer of the same thing this module already manages.
    """
    if not jobs:
        return []
    if configuration.concurrency == 1:
        return [
            invoke(adapter=adapter, job=job, configuration=configuration)
            for job in jobs
        ]
    with ThreadPoolExecutor(max_workers=configuration.concurrency) as pool:
        return list(
            pool.map(
                lambda job: invoke(
                    adapter=adapter, job=job, configuration=configuration
                ),
                jobs,
            )
        )


def python_adapter(script: Path) -> tuple[str, ...]:
    """The command that runs a Python adapter with the interpreter running this.

    Here rather than in a test, because a caller pointing at a `.py` file wants
    the interpreter the harness is installed into and not whatever `python`
    happens to mean on the path.
    """
    return (sys.executable, str(script))
