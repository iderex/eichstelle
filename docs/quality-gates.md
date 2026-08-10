# The quality gates and the commands that run them

Three tools, three commands. A pull request runs them, in the `verify`
workflow that issue #17 added:

    $ grep -rl 'ruff\|mypy' .github/workflows/
    .github/workflows/verify.yml

It runs exactly the commands below, so a green run locally and a green check on
a pull request mean the same thing. If the two ever diverge the workflow is
wrong rather than this list. `docs/ci-checks.md` names the checks it produces
and says what a failure of each one means.

Install the development tools first. They are declared in the `dev` dependency
group in `pyproject.toml` and are not part of what an operator installs.

    uv sync --locked

Locked mode, so the versions are the ones in `uv.lock` and not whatever resolves
today. `python -m pip install -e . --group dev` also works and resolves freshly,
which means two contributors can get two different ruff releases from the same
commit and see two different results from the same command. `CONTRIBUTING.md`
says which is which.

## The linter

    ruff check

Refusing mode. Any match fails, and there is no advisory setting. The rule
selection is written out in `[tool.ruff.lint]` in `pyproject.toml` with a
comment on each entry naming the defect class it catches, rather than inherited
from whatever ruff's default is in the release a contributor happens to have.

Locally, `ruff check --fix` writes the fixes the tool can make on its own,
including the import order.

## The formatter

    ruff format --check

The same tool with the same configuration as the linter, running in check mode.
Locally, `ruff format` writes instead of reporting. Nothing in the formatter
configuration departs from ruff's defaults, so there is no house style for a
contributor to learn or to argue with.

## The type checker

    mypy

Strict mode, reading `[tool.mypy]` in `pyproject.toml`. The `files` entry there
is the whole of what the bare command covers, so the command cannot drift away
from the scope it is supposed to have. That scope is the package and the tests:

    $ grep -n '^files' pyproject.toml
    181:files = ["src", "tests"]

    $ git ls-files tests | wc -l
    4

The tests were outside it until issue #14 created a directory for mypy to read.
mypy refuses a path that does not exist and refuses a directory holding no
Python file, so naming `tests` on an empty tree made the documented command exit
2. That is what #14 owed this issue and it is paid, so the command now covers
the half of the tree where the assertions live and a type error in a test is
reported.

Strict from the first commit, because strictness is affordable on an empty tree
and unaffordable on a full one. An import with no type information is an error
rather than silence, which is what forces an untyped dependency to arrive as a
declared per-module relaxation naming the library and the reason, instead of
quietly turning everything it touches into `Any`.

There are no per-module relaxations today. When one is needed it goes in
`pyproject.toml` as its own `[[tool.mypy.overrides]]` block with a comment
naming the untyped dependency that forces it.

## What these do not cover

None of the three runs the test suite. That is a fourth command:

    python -m pytest

It reads `[tool.pytest.ini_options]` in `pyproject.toml`, which names `tests` as
the only path it collects from, promotes warnings to errors, and refuses an
unregistered marker and an unknown key in its own configuration. `CONTRIBUTING.md`
says how the fast and the slow halves are selected. Like the three above, a
pull request runs it, once per supported interpreter version and with no
outbound network. `docs/ci-checks.md` names those checks.

What it does not catch is a test that simply contains no assertion. pytest has
no mechanism for that. The configuration promotes pytest's return-not-None
warning to an error, which catches a test that computes a value and returns it
instead of asserting on it, and that is the nearest thing available rather than
the thing itself.

None of the three refuses a tracked audio file. That is a fifth command:

    python tools/refuse_tracked_audio.py

It reads the tracked tree, refuses a path by extension and independently by
leading bytes, and exits 2 rather than 0 on anything that stops it completing.
Issue #6 is the decision it enforces and issue #19 is where it was built and
where it became a check name. Like the three above, a pull request runs it:

    $ grep -n refuse_tracked_audio .github/workflows/verify.yml
    373:        run: .venv/bin/python tools/refuse_tracked_audio.py

The check is called `no-tracked-audio`. What it does not cover is written in the
script's own docstring and repeated in `docs/ci-checks.md`: the signature table
is a floor, and somebody who stores samples as text defeats both halves of it.

None of the three refuses a line that breaks one of this project's own
invariants. That is a sixth command:

    python tools/invariants.py

Exit 0 is no match, exit 1 is at least one refusal, and exit 2 is a run that did
not complete, which includes a rule file that will not parse and a rule that
leaves out a field it has to declare. Issue #49 is where the set was argued and
the check is called `invariants`.

Like the audio guard above, a pull request runs it:

    $ grep -n invariants.py .github/workflows/verify.yml
    334:        run: .venv/bin/python tools/invariants.py

The rules are data in `tools/invariants.toml`, one entry per invariant, and this
document does not list them: the file is the authority and a second copy here
would drift against it. What each entry has to declare is the part worth stating
outside the file, because it is what makes a red check answerable. A rule names
the decision it comes from, the mistake it exists to catch, its own edge, and
what prompted it. The loader refuses a rule that leaves out any of those rather
than running it, so a pattern with no explanation beside it cannot ship.

Adding a rule is what happens after a defect got through, and `prompted_by` is
where that defect is named. The steps are an entry in the rule file and a row in
`tests/unit/test_invariants.py`, which carries per rule the one-line mistake it
must refuse and the corrected form of the same line it must let through. A rule
with no row there is refused by the suite, because a rule that has never been
seen to fire is one whose behaviour nobody knows. Every rule in the file today
was placed ahead of the defect rather than after it, and each one says so in its
own `prompted_by` field rather than leaving a reader to assume otherwise.

What it does not cover: everything a token-level pattern match misses. Each rule
states its own edge in the file and the run prints those edges on every pass, so
a green result is read as a floor. Several rules read one directory, one of them
reads a directory that does not exist in this tree yet, and one carries
exemptions whose reasons are printed with the count. None of them reads what a
value is, only how a line is written.

None of the three is a security review, and the bandit rules in the linter's
selection are pattern matches over source text rather than an analysis. A rule
set of this shape is a floor and can be evaded by anyone who wants to.

None of them is a mutation run, and that one now exists without being a gate. It
is a seventh command and it refuses nothing:

    uv sync --locked --group mutation
    mutmut run
    mutmut export-cicd-stats
    python tools/mutation_score.py

The tool sits in its own dependency group, so `uv sync --locked` on its own does
not install it and neither the gate above nor a contributor pays for a slow tool
they are not running. The last command is the only one whose exit code means
anything: zero whatever the score is, and 2 when the run produced no score,
because a mutation run that stopped running leaves the last number standing and
looks exactly as green as one that succeeded. Issue #48 is where that asymmetry
is argued, `.github/workflows/mutation.yml` runs it on a schedule rather than on
a pull request, and `docs/measurements/mutation-score.md` holds the numbers and
what a low one does and does not mean.

Two things it does not do. It does not run on Windows: mutmut refuses to start
there and says so, so this measurement is taken inside a Linux environment or
left to the schedule. And it covers the verdict surface rather than the package;
`[tool.mutmut]` in `pyproject.toml` names what is mutated and why the generators
are outside it.

None of them is a coverage bar, and that one is a gate. It is an eighth command,
in three parts because the measurement and the judgement are separate things:

    python -m coverage run --source=src/eichstelle -m pytest
    python -m coverage json -o coverage.json
    python tools/coverage_gate.py coverage.json

`coverage` is in the `dev` group, so `uv sync --locked` installs it and a
contributor sees the same number the check does. The last command is the one
whose exit code is the gate: 0 at or above the threshold, 1 below it, and 2 when
the measurement could not be read at all. Issue #47 is where the shape is argued
and `docs/quality-parity.md` is where it is matched against the target board.

What it bars is the verdict surface rather than the tree, and the surface, the
exclusions and the reason for each are in `tools/coverage_gate.py` where the
code that reads them is. The whole-repository number is printed and never
enforced, because a bar over everything is satisfied by covering the easy parts.

Three things it does not do. It does not follow a subprocess, so the end-to-end
runs that invoke an adapter through a process boundary contribute nothing to the
number, which makes the measurement an understatement rather than an
overstatement. It does not assert the offline promise: this measurement runs
with ordinary network access and the `tests` legs are where that claim is
checked. And a line that ran is not a line anything would have noticed being
wrong, which is the second question and is the mutation run's above.

A tool version is bounded from below in `pyproject.toml` and pinned exactly, with
a hash, in `uv.lock`. Which of the two a contributor gets depends on which
install command they ran, and only `uv sync --locked` refuses to move. The
`verify` workflow runs that one, so the checks on a pull request see the
recorded set. Nothing obliges a contributor to run it locally, so somebody on a
freshly resolved ruff can still see a different result from the same command
than the check does.
