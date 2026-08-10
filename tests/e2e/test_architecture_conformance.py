"""The project's own architecture, asserted by the suite rather than by a reader.

A structural rule that only a person checks is a rule that holds until the day
somebody is in a hurry. Each test here fails like any other test, and each one
names in a comment the decision record it enforces, so a red result points at
the reasoning rather than at this file.

Three of them are about decision record 0010, which makes headless, offline and
unprivileged birth requirements of the default suite rather than later
hardening. The record itself says a sentence in a decision record is not a
rule; these are the run-time half of what makes it one, and the lint rule that
refuses the shape of a violation in the source is the other half and is issue
#49.

## The offline check, and what it is worth

The suite is run again, as a child process, with the outbound socket calls
replaced by ones that refuse. `offline/offline_guard.py` says exactly what is
denied and what is not; the short version is that it is a floor rather than a
sandbox, because a program that reaches the network without going through
Python's socket module is outside what it can see.

The denial reaches subprocesses, which is the part that matters here: the
end-to-end tests spend their time in adapters running as separate processes,
and an adapter is exactly the kind of program that phones home. It reaches them
through `PYTHONPATH` and a `sitecustomize` module, so a Python process anywhere
in the run's process tree loads the guard before it runs anything.

The child run does not include this test, because a suite that ran itself would
not stop. That is one skipped test inside the inner run and it is visible in the
inner run's own output.

## What the two fixture-set checks are worth today

Both of them read the set this repository actually carries, which is the claim
the validator's own suite cannot make: that suite proves the rules bite on the
inputs it is handed, and these say the tracked tree is one of them.

The set is empty at this commit, so both skip rather than pass, because a green
tick over no files cannot be told from a green tick over a set that was
checked. The correspondence check skips only while the fixture set and the
manifest are BOTH empty, and that is the part worth reading twice: the failure
it exists for is a fixture deleted with its manifest entry left behind, and an
entry left behind is a manifest that is not empty, so that case asserts rather
than skips even with no fixture in the tree.

It compares identifiers and revisions and never hashes anything. Whether a
signal still renders to the bytes the manifest recorded is the `fixtures` check
in `docs/ci-checks.md`, which regenerates every stimulus; a second opinion here
would be the slower half of that check run again under another name.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import os
import subprocess
import sys
import tomllib
from collections.abc import Iterator, Mapping
from importlib.resources import files
from pathlib import Path
from typing import Final

import pytest

from eichstelle.fixtures.checksums import (
    MANIFEST_NAME,
    Entry,
    read_manifest,
    render_manifest,
)

# The repository, from this file's own location. Asserted rather than assumed,
# so a moved test file fails here instead of quietly checking a smaller tree.
REPOSITORY: Final = Path(__file__).resolve().parents[2]

# Where the guard and the module that loads it into a fresh interpreter live.
OFFLINE_DIRECTORY: Final = Path(__file__).resolve().parent / "offline"

# Set in the child run so the whole-suite test below skips itself there. Without
# it the child starts a grandchild, and so on.
CHILD_MARKER: Final = "EICHSTELLE_ARCHITECTURE_CHILD"

# The environment variables that hand a process a display. Removed from the
# child run, so a test that needs one fails there rather than passing on a
# developer machine and failing on a runner.
DISPLAY_VARIABLES: Final = ("DISPLAY", "WAYLAND_DISPLAY")

# Long enough for the whole suite on a slow runner, and short enough that a
# hang is a failure rather than a job that is killed with no output.
CHILD_TIMEOUT_SECONDS: Final = 1500

# What `offline/sitecustomize.py` exits with when the guard did not load.
GUARD_DID_NOT_LOAD: Final = 78


def _checked_environment(*, extra_path: Path | None = None) -> dict[str, str]:
    """The environment a checked process runs in: guarded, and with no display.

    Built from this process's environment rather than from nothing, because a
    run needs its interpreter, its temporary directory and its locale, and a
    hand-built environment is a second thing to keep in step with the platform.
    """
    directory = str(extra_path if extra_path is not None else OFFLINE_DIRECTORY)
    environment = dict(os.environ)
    existing = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = (
        f"{directory}{os.pathsep}{existing}" if existing else directory
    )
    environment[CHILD_MARKER] = "1"
    # Options the outer run was given must not silently become options of the
    # inner one; the inner run is the default suite and nothing else.
    for name in ("PYTEST_ADDOPTS", *DISPLAY_VARIABLES):
        environment.pop(name, None)
    return environment


@pytest.fixture(scope="module")
def checked_suite_run() -> subprocess.CompletedProcess[str]:
    """Run the whole default suite once, offline and with no display.

    One run rather than one per property. The two tests below assert different
    things about the same run, and running the suite twice to ask two questions
    of it would double the cost of the gate for nothing.

    Inside the checked run itself this skips, and the skip is the reason the
    inner run terminates: a suite that ran itself would not.
    """
    if os.environ.get(CHILD_MARKER) == "1":
        pytest.skip(
            "this IS the checked run, and a suite that runs itself does not stop. "
            "What was asserted about this run is asserted by the run that started it"
        )
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"],
        cwd=str(REPOSITORY),
        env=_checked_environment(),
        capture_output=True,
        text=True,
        timeout=CHILD_TIMEOUT_SECONDS,
        check=False,
    )


def _tail(completed: subprocess.CompletedProcess[str]) -> str:
    """The last of a child run's output, for a failure message worth reading."""
    combined = f"{completed.stdout}\n{completed.stderr}".strip().splitlines()
    return "\n".join(combined[-40:])


# Decision record 0010: no test in the default gate makes an outbound
# connection, and the gate runs the same on a machine with no route as on one
# with. Issue #52 asks for this in the form of a run rather than a promise.
def test_the_default_suite_passes_with_outbound_network_denied(
    checked_suite_run: subprocess.CompletedProcess[str],
) -> None:
    """The suite passes when every outbound socket call refuses."""
    assert checked_suite_run.returncode == 0, (
        "the default suite does not pass with outbound network denied, so the "
        "offline claim in decision record 0010 is not true of this tree:\n"
        f"{_tail(checked_suite_run)}"
    )


# Decision record 0010: no test creates a window, opens a graphics context, or
# requires a session that provides one.
def test_no_default_suite_test_requires_a_display(
    checked_suite_run: subprocess.CompletedProcess[str],
) -> None:
    """The same run had no display handed to it and still passed.

    On Windows there is no display variable to remove, so this leg asserts
    nothing there beyond what the test above already asserts. That is a real
    gap in where this is checked rather than in what it checks, and the
    workflow runs the suite on Linux.
    """
    environment = _checked_environment()
    for name in DISPLAY_VARIABLES:
        assert name not in environment
    assert checked_suite_run.returncode == 0, _tail(checked_suite_run)


# Decision record 0010: no test attempts a privileged operation, and the
# constraint is asserted by the gate running unprivileged.
def test_the_suite_is_running_unprivileged() -> None:
    """This run is not a privileged one.

    A suite that needs elevation to pass is a suite nobody can run in the
    ordinary way, and a run that HAS elevation cannot notice that it needed it.
    So the assertion is about the run rather than about any one test, which is
    the form decision record 0010 gives it.
    """
    if sys.platform == "win32":
        import ctypes

        elevated = bool(ctypes.windll.shell32.IsUserAnAdmin())
        assert not elevated, (
            "this run is elevated, so it cannot tell a test that needs "
            "elevation from one that does not"
        )
        return
    assert os.geteuid() != 0, (
        "this run is root, so it cannot tell a test that needs elevation from "
        "one that does not"
    )


def _script(body: str, environment: dict[str, str]) -> subprocess.CompletedProcess[str]:
    """Run a short program in a fresh interpreter under the given environment."""
    return subprocess.run(  # noqa: S603 - the interpreter running this test
        [sys.executable, "-c", body],
        cwd=str(REPOSITORY),
        env=environment,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


# Decision record 0010, and the near-miss the guard exists for: a test that
# opens a connection has to redden the run rather than be reported as offline.
def test_the_guard_refuses_every_route_it_replaces() -> None:
    """Each outbound route raises, and loopback still works.

    Four routes rather than one, because a guard that covers `connect` and not
    `getaddrinfo` denies an address and admits a name, which is the spelling
    almost every library actually uses.
    """
    completed = _script(
        "\n".join(
            (
                "import socket",
                "import offline_guard",
                "assert offline_guard.is_installed()",
                "refused = []",
                "for label, call in (",
                "    ('connect', lambda: socket.socket().connect(('93.184.216.34', 80))),",
                "    ('connect_ex', lambda: socket.socket().connect_ex(('93.184.216.34', 80))),",
                "    ('getaddrinfo', lambda: socket.getaddrinfo('example.com', 80)),",
                "    ('sendto', lambda: socket.socket(",
                "        socket.AF_INET, socket.SOCK_DGRAM",
                "    ).sendto(b'x', ('93.184.216.34', 53))),",
                "):",
                "    try:",
                "        call()",
                "    except OSError as exc:",
                "        if offline_guard.MARKER in str(exc):",
                "            refused.append(label)",
                "print(','.join(refused))",
                "print(bool(socket.getaddrinfo('127.0.0.1', 8080)))",
            )
        ),
        _checked_environment(),
    )
    assert completed.returncode == 0, completed.stderr
    lines = completed.stdout.splitlines()
    assert lines[0].split(",") == ["connect", "connect_ex", "getaddrinfo", "sendto"], (
        f"not every outbound route was refused: {completed.stdout!r}"
    )
    assert lines[1] == "True", "loopback was denied, which is not what this denies"


# Decision record 0010: the constraint reaches the adapters, which are
# subprocesses under record 0006 rather than imports.
def test_the_denial_reaches_a_process_the_suite_starts() -> None:
    """A grandchild interpreter is guarded too, without being told to be."""
    completed = _script(
        "\n".join(
            (
                "import subprocess, sys",
                "inner = subprocess.run(",
                "    [sys.executable, '-c',",
                "     'import socket; socket.getaddrinfo(\"example.com\", 80)'],",
                "    capture_output=True, text=True, check=False)",
                "print(inner.returncode)",
                "print('MARKER' if 'eichstelle offline guard' in inner.stderr else 'no')",
            )
        ),
        _checked_environment(),
    )
    assert completed.returncode == 0, completed.stderr
    returncode, marker = completed.stdout.splitlines()[:2]
    assert returncode != "0", "the grandchild resolved a remote name"
    assert marker == "MARKER", (
        "the grandchild failed for some reason other than this guard, so "
        f"nothing here shows the denial reached it: {completed.stdout!r}"
    )


# Decision record 0010: a run that covered less than it claims must not be
# readable as one that covered everything.
def test_the_loader_ends_the_process_when_the_guard_cannot_load(
    tmp_path: Path,
) -> None:
    """A `sitecustomize` that cannot find the guard stops the interpreter.

    CPython prints a traceback from a failing `sitecustomize` and carries on,
    which would leave a run reporting green under a guard that never loaded.
    This is the near-miss: the loader is present and the guard beside it is not.
    """
    (tmp_path / "sitecustomize.py").write_text(
        (OFFLINE_DIRECTORY / "sitecustomize.py").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(tmp_path)
    completed = _script("print('this should not be reached')", environment)
    assert completed.returncode == GUARD_DID_NOT_LOAD, (
        "a missing guard did not stop the interpreter, so a run under it would "
        f"look exactly like a checked one: {completed.returncode}"
    )
    assert "this should not be reached" not in completed.stdout


def _deliberate_violation(directory: Path) -> Path:
    """A one-file suite whose only test opens a connection."""
    path = directory / "test_deliberate_violation.py"
    path.write_text(
        "import socket\n"
        "\n"
        "\n"
        "def test_reaches_the_network() -> None:\n"
        "    socket.create_connection(('example.com', 80), timeout=5)\n",
        encoding="utf-8",
    )
    return path


# Decision record 0010, again as the near-miss: this is the deliberate
# violation the check above was shown to refuse, kept in the suite rather than
# pasted into a pull request body once and then never run again.
def test_the_guard_reddens_a_test_that_opens_a_connection(tmp_path: Path) -> None:
    """A test that reaches the network fails under the same environment.

    Run against a one-file tree rather than against this repository, so the
    violation is a real pytest run and no file in this tree has to be broken to
    produce it.
    """
    violation = _deliberate_violation(tmp_path)
    environment = _checked_environment()
    completed = subprocess.run(  # noqa: S603 - the interpreter running this test
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            str(violation),
        ],
        cwd=str(tmp_path),
        env=environment,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    assert completed.returncode != 0, (
        "a test that opened a connection passed under the offline environment, "
        f"so the check above proves nothing:\n{_tail(completed)}"
    )
    assert "eichstelle offline guard" in completed.stdout, (
        "the violating test failed for some reason other than this guard:\n"
        f"{_tail(completed)}"
    )


def imported_module_roots(source: str) -> set[str]:
    """The top-level module names a Python source file imports.

    A relative import cannot leave the package it is in, so it is not read
    here. Only the absolute ones can cross the boundary this is about.
    """
    roots: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def _declared_dependencies() -> set[str]:
    """The runtime dependencies `pyproject.toml` declares, by distribution name.

    Read rather than listed, so adding a dependency is one edit. The name a
    distribution is installed under and the name it is imported under are not
    the same thing in general; they are for the one dependency this project
    has, and a future one where they differ makes this test fail rather than
    pass quietly, which is the right way round.
    """
    text = (REPOSITORY / "pyproject.toml").read_text(encoding="utf-8")
    declared = tomllib.loads(text)["project"]["dependencies"]
    names = set()
    for entry in declared:
        name = entry
        for separator in ("[", "<", ">", "=", "!", "~", ";", " "):
            name = name.split(separator)[0]
        names.add(name.strip().replace("-", "_"))
    return names


def _package_sources() -> Iterator[Path]:
    """Every Python file of the harness core, from the tree rather than the wheel."""
    return (REPOSITORY / "src" / "eichstelle").rglob("*.py")


# Decision record 0006: the adapter boundary is a process and a pair of files
# rather than an import, and record 0010 depends on that being true.
def test_the_harness_core_imports_nothing_outside_its_own_declared_set() -> None:
    """The package imports the standard library, its dependencies, and itself.

    Stated this way round rather than as a list of forbidden names, because the
    thing that must not happen is an import of an adapter, of the test tree, or
    of a third-party library nobody declared, and one rule refuses all three.
    """
    permitted = sys.stdlib_module_names | _declared_dependencies() | {"eichstelle"}
    offenders: dict[str, set[str]] = {}
    for path in _package_sources():
        roots = imported_module_roots(path.read_text(encoding="utf-8"))
        outside = roots - permitted
        if outside:
            offenders[path.relative_to(REPOSITORY).as_posix()] = outside
    assert not offenders, (
        "the harness core imports something that is neither the standard "
        "library, a declared dependency, nor itself. An adapter reached by "
        f"import is not an adapter under decision record 0006: {offenders}"
    )


# Decision record 0006, the same boundary read from the other side.
def test_the_import_boundary_rule_catches_an_import_of_an_adapter() -> None:
    """The near-miss: the rule above, applied to a module that breaks it.

    Without this the rule passes over a tree that happens to contain no such
    import, and nothing shows it would have noticed one.
    """
    roots = imported_module_roots(
        "from tools.fake_adapter import main\nimport tests.e2e.adapters\n"
    )
    permitted = sys.stdlib_module_names | _declared_dependencies() | {"eichstelle"}
    assert roots - permitted == {"tools", "tests"}


# Decision record 0006: nothing of an adapter is loaded into this suite, so no
# adapter can travel inside the distribution an operator installs.
def test_no_adapter_lives_inside_the_installed_distribution() -> None:
    """No adapter is reachable from the package an operator installs.

    The adapters this tree carries are the fake one under `tools/` and the ones
    the end-to-end runs drive. None of them is under `src/`, which is the whole
    of what the wheel is built from, and this says so as an assertion rather
    than as a fact about the current layout.
    """
    installed = Path(str(files("eichstelle"))).resolve()
    for path in _package_sources():
        assert "adapter" not in path.name, (
            f"{path.relative_to(REPOSITORY).as_posix()} sits inside the harness "
            "core and names itself an adapter"
        )
        assert "adapters" not in path.parts
    assert importlib.util.find_spec("eichstelle.adapters") is None
    for adapter in (
        REPOSITORY / "tools" / "fake_adapter.py",
        *(REPOSITORY / "tests" / "e2e" / "adapters").glob("*.py"),
    ):
        assert installed not in adapter.resolve().parents, (
            f"{adapter} resolves inside the installed distribution at {installed}"
        )


# Decision record 0004: an identifier is what a published result names, and two
# fixtures under one name make that citation ambiguous.
def test_every_tracked_fixture_carries_a_distinct_identifier() -> None:
    """No two fixtures in this tree share an identifier.

    The validator refuses a collision inside the set it is handed, and its own
    suite proves that. This is the different claim: that the set this
    repository actually carries has none. It skips rather than passes while
    that set is empty, because a green tick over no files is indistinguishable
    from a green tick over a set that was checked.
    """
    paths = sorted((REPOSITORY / "fixtures").glob("*.json"))
    if not paths:
        pytest.skip(
            "no fixture is tracked under fixtures/ at this commit, so there is "
            "nothing here to be distinct; milestone 3 is where a set arrives"
        )
    seen: dict[str, str] = {}
    for path in paths:
        document = json.loads(path.read_text(encoding="utf-8"))
        identifier = document["id"]
        assert identifier not in seen, (
            f"{path.name} and {seen[identifier]} both carry the identifier "
            f"{identifier!r}"
        )
        seen[identifier] = path.name


def _claimed_and_committed(
    root: Path,
) -> tuple[dict[tuple[str, int], str], set[tuple[str, int]]]:
    """What the fixtures under `root` claim, and what the manifest beside them holds.

    A fixture is keyed on its identifier and its revision together, which is the
    key the manifest itself is written under, so a fixture revised without its
    entry being regenerated is a pair the manifest has no line for rather than a
    pair that silently matches an older line.

    The walk is recursive, because `python -m eichstelle.fixtures` walks the
    fixture root with `rglob` and writes an entry for everything it finds. A
    check reading one directory level would report a fixture in a subdirectory
    as an entry nothing claims, which is a failure about this file rather than
    about the tree.

    Only `id` and `revision` are read. What else a fixture has to carry is the
    schema's to refuse, and a second opinion here would drift from the
    validator.
    """
    claimed: dict[tuple[str, int], str] = {}
    for path in sorted(root.rglob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        claimed[(document["id"], document["revision"])] = path.name
    entries = read_manifest(root / MANIFEST_NAME)
    committed = {(entry.fixture_id, entry.revision) for entry in entries}
    return claimed, committed


def _correspondence_failures(
    claimed: Mapping[tuple[str, int], str], committed: set[tuple[str, int]]
) -> list[str]:
    """Every fixture with no entry, and every entry no fixture claims.

    Both directions in one list, each naming the file or the line a reader has
    to open, because the two are repaired differently: a fixture with no entry
    is a manifest that was not regenerated, and an entry with no fixture is a
    line a deletion left behind.
    """
    failures = [
        f"{identifier} revision {revision} has a manifest entry and no fixture "
        "under the fixture root claims it, so a later fixture reusing that "
        "identifier would be held against a stranger's bytes"
        for identifier, revision in sorted(committed - set(claimed))
    ]
    failures.extend(
        f"{claimed[key]} claims {key[0]} revision {key[1]} and the manifest "
        "holds no entry for it, so nothing holds that stimulus still"
        for key in sorted(set(claimed) - committed)
    )
    return failures


# Decision record 0005: a generated stimulus is proved to be the one the fixture
# meant by a committed checksum, and the record names issue #52 as where the
# two-way correspondence between fixtures and manifest entries is asserted, so
# neither can drift from the other unnoticed.
def test_every_fixture_has_a_manifest_entry_and_every_entry_a_fixture() -> None:
    """The tracked fixture set and the tracked manifest name the same signals.

    This is the failure the pair exists for: a fixture is deleted, its entry
    stays, and six months later somebody spends a day working out why a checksum
    has no signal. The reverse costs less to find and is worse to have, because
    a fixture nothing records is a stimulus nothing holds still.
    """
    root = REPOSITORY / "fixtures"
    claimed, committed = _claimed_and_committed(root)
    if not claimed and not committed:
        pytest.skip(
            "no fixture is tracked under fixtures/ at this commit and the "
            "manifest beside them is empty, so the two agree about nothing; "
            "milestone 3 is where a set arrives. An entry left behind by a "
            "deleted fixture does not reach this skip"
        )
    failures = _correspondence_failures(claimed, committed)
    assert not failures, (
        f"the fixture set and {root / MANIFEST_NAME} have drifted apart. "
        "`python -m eichstelle.fixtures --write-checksums fixtures/` "
        "regenerates the manifest, and its diff is what the pull request "
        "body explains:\n" + "\n".join(failures)
    )


# Decision record 0005, as the near-miss: the check above passes over a tree
# where the two happen to agree, and nothing in that shows it would notice a
# tree where they do not.
def test_the_correspondence_catches_a_stale_entry_and_an_unrecorded_fixture(
    tmp_path: Path,
) -> None:
    """One drift in each direction, read off a real root rather than asserted.

    The manifest is written by the same renderer the command writes with, so
    this cannot pass against a format the tree no longer uses. The digests in it
    are not real hashes and nothing here reads them: this is the correspondence
    between identifiers, and whether a signal still renders to its recorded
    bytes is the `fixtures` check.
    """
    root = tmp_path / "fixtures"
    root.mkdir()
    for identifier in ("kept", "orphan"):
        (root / f"{identifier}.json").write_text(
            json.dumps({"id": identifier, "revision": 1}), encoding="utf-8"
        )
    (root / MANIFEST_NAME).write_text(
        render_manifest(
            [
                Entry(fixture_id="kept", revision=1, digest="0" * 64),
                Entry(fixture_id="stale", revision=2, digest="1" * 64),
            ]
        ),
        encoding="utf-8",
        newline="\n",
    )

    claimed, committed = _claimed_and_committed(root)
    failures = _correspondence_failures(claimed, committed)

    assert len(failures) == 2, f"expected one drift in each direction: {failures}"
    left_behind, unrecorded = failures
    assert left_behind.startswith("stale revision 2 has a manifest entry"), left_behind
    assert unrecorded.startswith("orphan.json claims orphan revision 1"), unrecorded
    assert not [failure for failure in failures if "kept" in failure], (
        f"the fixture whose entry is present was reported as a drift: {failures}"
    )


# The license of this repository is a maintainer decision and is issue #1.
@pytest.mark.skip(
    reason=(
        "the license header conformance test cannot be written until issue #1 "
        "answers what the license is; this skip is here so the absence appears "
        "in every run's output as owed rather than being invisible"
    )
)
def test_every_source_file_carries_the_license_header() -> None:  # pragma: no cover
    """Owed, and blocked on issue #1.

    There is no license in this tree, so there is no header for a test to
    require. `CONTRIBUTING.md` says the same thing about the sign-off
    certificate, and until #1 is answered this repository is all rights
    reserved.
    """
    raise AssertionError("unreachable while issue #1 is open")
