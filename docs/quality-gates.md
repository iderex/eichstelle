# The quality gates and the commands that run them

Three tools, three commands. These are the commands the workflow runs, so a
green run locally and a green check on a pull request mean the same thing. If
they ever diverge, the workflow is wrong, not the list below.

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

Strict mode over the package and the tests, reading `[tool.mypy]` in
`pyproject.toml`. The `files` entry there is what makes the bare command cover
both directories, so the command cannot drift away from the scope it is supposed
to have.

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

None of the three is a security review, and the bandit rules in the linter's
selection are pattern matches over source text rather than an analysis. A rule
set of this shape is a floor and can be evaded by anyone who wants to.

A tool version is bounded from below in `pyproject.toml` and not pinned. Two
contributors on two different ruff releases can therefore see two different
results from the same command. Issue #16 is where that is closed.
