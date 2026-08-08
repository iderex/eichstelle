# The quality gates and the commands that run them

Three tools, three commands. Nothing runs them on a pull request. Five
workflows exist here and none of them mentions either tool:

    $ git ls-files .github/workflows
    .github/workflows/dco.yml
    .github/workflows/dependency-review.yml
    .github/workflows/scorecard.yml
    .github/workflows/unicode-guard.yml
    .github/workflows/zizmor.yml

    $ grep -rl 'ruff\|mypy' .github/workflows/ ; echo "exit=$?"
    exit=1

So a contributor who does not run the three commands below is refused by
nothing, and a pull request that fails all three can still be green. Issue #17
adds the workflow that runs them. When it lands it runs exactly these commands,
so that a green run locally and a green check on a pull request mean the same
thing, and if the two ever diverge the workflow is wrong rather than the list
below. Until then the sentence above is the whole of what a reader may assume.

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
says how the fast and the slow halves are selected. Like the three above,
nothing runs it on a pull request yet; #17 is where it becomes a check name.

What it does not catch is a test that simply contains no assertion. pytest has
no mechanism for that. The configuration promotes pytest's return-not-None
warning to an error, which catches a test that computes a value and returns it
instead of asserting on it, and that is the nearest thing available rather than
the thing itself.

None of the three refuses a tracked audio file. That is a fifth command:

    python tools/refuse_tracked_audio.py

It reads the tracked tree, refuses a path by extension and independently by
leading bytes, and exits 2 rather than 0 on anything that stops it completing.
Issue #6 is the decision it enforces and issue #19 is where it was built. Like
the three above, nothing runs it on a pull request yet; #17 is where it becomes
a check name.

None of the three is a security review, and the bandit rules in the linter's
selection are pattern matches over source text rather than an analysis. A rule
set of this shape is a floor and can be evaded by anyone who wants to.

A tool version is bounded from below in `pyproject.toml` and pinned exactly, with
a hash, in `uv.lock`. Which of the two a contributor gets depends on which
install command they ran, and only `uv sync --locked` refuses to move. Nothing
here obliges anybody to run that one, and no workflow runs either, so a
contributor on a freshly resolved ruff still sees a different result from the
same command. Issue #16 stays open on that and on the rest of what it asks for.
