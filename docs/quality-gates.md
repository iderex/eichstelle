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

    python -m pip install -e . --group dev

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
from the scope it is supposed to have. That scope is the package and nothing
else:

    $ grep -n '^files' pyproject.toml
    175:files = ["src"]

    $ git ls-files tests | wc -l
    0

The tests are outside it because there are none yet. mypy refuses a path that
does not exist and refuses a directory holding no Python file, so naming
`tests` today would make the documented command exit 2 on a clean tree. Adding
it is what issue #14 owes issue #15, and until that is done this command says
nothing at all about the half of the tree where the assertions will live. A
type error in a test would not be reported by it.

Strict from the first commit, because strictness is affordable on an empty tree
and unaffordable on a full one. An import with no type information is an error
rather than silence, which is what forces an untyped dependency to arrive as a
declared per-module relaxation naming the library and the reason, instead of
quietly turning everything it touches into `Any`.

There are no per-module relaxations today. When one is needed it goes in
`pyproject.toml` as its own `[[tool.mypy.overrides]]` block with a comment
naming the untyped dependency that forces it.

## What these do not cover

None of the three runs the test suite. That is a separate command and a separate
check.

None of the three refuses a tracked audio file. That is a fourth command:

    python tools/refuse_tracked_audio.py

It reads the tracked tree, refuses a path by extension and independently by
leading bytes, and exits 2 rather than 0 on anything that stops it completing.
Issue #6 is the decision it enforces and issue #19 is where it was built. Like
the three above, nothing runs it on a pull request yet; #17 is where it becomes
a check name.

None of the three is a security review, and the bandit rules in the linter's
selection are pattern matches over source text rather than an analysis. A rule
set of this shape is a floor and can be evaded by anyone who wants to.

A tool version is bounded from below in `pyproject.toml` and not pinned. Two
contributors on two different ruff releases can therefore see two different
results from the same command. Issue #16 is where that is closed.
