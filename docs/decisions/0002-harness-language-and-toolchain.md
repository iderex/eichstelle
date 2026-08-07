# 0002. The harness language and toolchain

## Decision

The harness is written in Python, with an interpreter floor of 3.11, dependencies
resolved and locked by uv into `uv.lock`, and installed in locked mode wherever a
gate runs.

## Context

A conformance suite has authority only if the people whose implementations it
tests will run it. Two of the three implementations in scope are Python libraries
and the third is MATLAB. A harness those maintainers can install with one command
and read without learning a new language is a harness they will run. A harness in
a language none of them uses is a harness they will read about and ignore, and an
ignored conformance suite proves nothing.

The second reason is the work the harness actually does, which is signal
generation and numeric comparison. Generating a calibrated tone, a band-limited
noise and an amplitude-modulated carrier, and writing them as WAVE, is a short
piece of work against NumPy and SciPy and a research project in most
alternatives. The reference implementations of every DSP primitive this project
needs already live in that ecosystem. Reimplementing them elsewhere would put
this project's own numerics in doubt at exactly the moment it is asking others to
trust its numbers.

The interpreter floor is 3.11 rather than an older version for two reasons, both
stated here as claims about upstream rather than as measurements this project
made. The CPython release schedule puts 3.10 at the end of its security support
in October 2026, which is inside this project's first release horizon, and a
suite whose whole value is reproducibility should not ask an operator to run an
interpreter that no longer receives security fixes. Separately, 3.11 is the first
version carrying `tomllib` in the standard library, so the harness reads its own
configuration without a dependency, and the current NumPy line has already moved
its own floor to 3.11.

A ceiling exists as well as a floor, because the scientific wheels this project
depends on lag a new CPython release by months and an unbounded upper bound turns
that lag into a broken install for whoever upgrades first. The ceiling and the
comment giving its reason are set in the project metadata, which is the
scaffolding issue's work rather than this record's.

uv is the dependency manager because the repository already installs it: the
workflow-security audit job uses `astral-sh/setup-uv`, so choosing uv adds no new
tool to the tree. It produces a single `uv.lock` covering every platform the
project supports, and `uv sync --locked` fails when the lock file does not match
the declared dependencies instead of quietly resolving something newer, which is
the behaviour a gate needs. The package itself stays a plain PEP 621 project, so
`python -m pip install -e .` continues to work for anyone who does not want uv.

## Alternatives

Go. The maintainer knows it well and it would give a single static binary an
operator can run with nothing installed. Rejected because every DSP primitive the
project needs would have to be written from scratch, which puts this project's
own numerics in doubt, and because it puts the harness in a language none of the
three target projects reads.

Rust. Rejected for the same two reasons as Go, plus a steeper contribution
barrier for the research audience this suite depends on.

C++. Rejected because the build burden falls on every contributor, and because
the toolchain difference between three platforms becomes the project's problem
before any acoustics does.

MATLAB. Rejected because a suite that requires a paid license to run cannot be
the neutral ground three projects meet on. It would also make the harness
untestable on a bare runner, which the headless decision forbids.

Poetry, PDM and pip-tools as the dependency manager. All three can produce a lock
file and a locked install. Rejected because the repository already carries uv and
none of them removes a tool the tree would otherwise not have.

## Consequences

Python is dynamically typed, so a class of mistake another language refuses at
compile time has to be refused by a type checker configured strictly and run as a
gate. Issue #15 is where that cost is paid, and a type checker in advisory mode
does not pay it.

Python's dependency resolution is not reproducible by default, so the lock file
and the locked-mode install are not optional. A gate that resolves dependencies
freshly is a gate whose green result is about a set of versions nobody recorded.

NumPy's own numeric behaviour becomes part of the reference. A generated signal
is only reproducible to the extent that the library producing it is, so the
signal checksums in milestone 3 exist to make a change in that behaviour visible
as a stopped run rather than as a shifted result.

The single static binary is lost, and it is a real loss rather than a detail. An
operator with no Python installed cannot run this suite today. Milestone 8 has to
answer how that operator gets a working suite, and the answer is not "install
Python first" unless that is written down as the answer.

Python is slow. This costs nothing here, because a run's time is dominated by the
implementations under test rather than by the harness, and because every
implementation is reached across a process boundary that costs more than the
harness does.

The harness core is permitted to depend on NumPy, on SciPy, and on a JSON Schema
validator, and on nothing else. NumPy and SciPy carry the signal generation and
the numeric comparison; the validator refuses a malformed fixture before any code
reads it, which the fixture format decision requires and the standard library
cannot do. Adding a fourth is a new decision record, not a commit. Development
tools, the test runner, the linter, the formatter and the type checker are not
harness-core dependencies and are declared separately, so an operator installing
the suite does not install them.

No implementation under test may ever be a dependency of the harness core. Not
MOSQITO, not SQAT, not PsyTools, and not whatever is added later. Every one of
them is reached across the adapter process boundary and lives in its own
environment. A harness that imports the thing it is testing cannot be installed
without it, cannot be tested without it, and cannot report an honest result about
it.

## Status

Accepted, 2026-08-07.
