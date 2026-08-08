# The checks that run on a pull request

This is the one place that names them. `CONTRIBUTING.md` and
`docs/quality-parity.md` both point here rather than carrying a second copy,
because two lists of check names drift and the one in the wrong place is the one
a reader trusts.

A check name matters more than it looks. A required status check is matched by
the literal name of the check run, and a check run takes its name from the
`name` field of the job that produced it, falling back to the job id when the
field is absent. So renaming a job detaches it from whatever required it, and
the detachment is silent: the requirement goes on naming a check that no longer
appears, and a pull request merges having satisfied it by never running it.
Every name below is fixed deliberately. Changing one is a change to this file in
the same commit.

The names, and what a failure of each one means.

## From `.github/workflows/verify.yml`

**`lint`** runs `ruff check` and then `ruff format --check`. A failure is a
defect the linter's rule selection names, or a file the formatter would rewrite.
Both are reproduced locally by the same two commands, and `ruff check --fix` and
`ruff format` write most of what either one refuses.

**`types`** runs `mypy` in strict mode over the package and the tests. A failure
is a type error, an unannotated function, or an import with no type information
arriving where the configuration refuses one. The scope is the `files` entry in
`[tool.mypy]` rather than an argument in the workflow, so this check cannot
cover less than the bare `mypy` command covers on a contributor's machine.

**`tests (3.11)`**, **`tests (3.12)`**, **`tests (3.13)`**, **`tests (3.14)`**
each run `python -m pytest` once, on the interpreter named in the check. A
failure is a failing test, a collection error, or a warning, since
`filterwarnings = ["error"]` in `pyproject.toml` makes every warning a failure.
A failure on one leg and not the others is the thing four legs exist to find:
`pyproject.toml` declares support for four interpreters, and support nothing
runs on is a claim rather than a fact.

The suite runs with no outbound network. The step opens an empty network
namespace, brings loopback up inside it and runs the suite there, so a test that
reaches for the internet fails rather than passing on a runner that happens to
have a route. The step makes the same outbound request twice, once outside the
namespace and once inside it, and requires the first to succeed and the second
to be refused. The first half is not ceremony: without it a refused connection
inside proves only that something was unreachable, which is also what a broken
runner network looks like. If the inner request ever succeeds the job fails and
says so.

What that does not cover: the install step before it runs with ordinary network
access, because it has to fetch the locked set. Everything after it is sealed.
Nothing checks whether the suite would have needed the network, only that it did
not get it.

**`fixtures`** validates every tracked fixture under `fixtures/` against the
schema, using `python -m eichstelle.fixtures`. A failure is a fixture the
validator refuses, which `docs/fixtures.md` lists by kind, or a run that could
not complete and whose result is therefore unknown.

Today it validates nothing, because no fixture is tracked yet, and it says so in
its own output rather than reporting green in silence. It also prints that it
verified no signal checksums, which is the other half of what its name promises
and which issue #25 owes. Read this check green today as "there was nothing to
refuse", not as "the fixture set is sound".

**`no-tracked-audio`** runs `tools/refuse_tracked_audio.py`. A failure is a
tracked file whose extension names an audio container, or a tracked file whose
leading bytes match an audio container signature whatever it is called, or a
scan that could not complete. Issue #6 is the decision it enforces: no audio is
committed here, because the reference signals belong to the purchased standards
and committing one would be redistribution.

It judges the index rather than the working tree, so it reports what is being
pushed. `tools/tracked-audio-allowlist.txt` is the only way past it, it is empty
and expected to stay empty, and every entry has to carry a reason beside the
path. A path with no reason stops the scan rather than granting anything.

What it does not cover is a floor rather than a guarantee. The signature table
holds twenty-one containers and thirty-one extensions, so a container nobody
listed walks through the second test, and samples stored as text defeat both.
The check is aimed at the honest mistake and at a large binary arriving under an
innocent name.

## From the other workflows

These five ran here before the gate above existed. Each is described where it
lives; what follows is only the name and the failure.

**`DCO sign-off`**, from `dco.yml`. A commit in the pull request carries no
`Signed-off-by` trailer, or carries one that does not match its author exactly.
`CONTRIBUTING.md` says how to add it, and `git rebase --signoff origin/main`
adds it to work already committed.

**`dependency-review`**, from `dependency-review.yml`. A dependency introduced
or upgraded by the pull request carries a known vulnerability. The bar is
`fail-on-severity: low`, so any advisory at all blocks it. That job carries no
`name` field on purpose, so its check name is its job id; the comment in the
file says why, and it is the reason this whole document exists.

**`Reject Trojan Source Unicode`**, from `unicode-guard.yml`. A tracked text
file contains a bidirectional override, isolate or mark, or a zero-width
character. These make source render differently from how it executes, which is
CVE-2021-42574. Ordinary non-ASCII is not in the set.

**`Audit workflows (zizmor)`**, from `zizmor.yml`. A workflow file carries a
security defect at low severity or worse: an unpinned action, a template
injection, an excessive permission, a dangerous trigger. Every workflow here is
subject to it, including `verify.yml`.

**`Analyze (python)`** and **`Analyze (actions)`**, from `codeql.yml`. The
static analysis found something it treats as an error. Most of what it finds
arrives in the code scanning view rather than as a red check;
`docs/quality-parity.md` holds the rule for what happens to a finding there.

The supply-chain self-audit in `scorecard.yml` is deliberately absent from this
list. It has no `pull_request` trigger, because that path cannot publish its
results, so it is not a check anybody sees on a pull request.

## What none of them do

None of them is a coverage bar, a mutation score or a fuzzing run.
`docs/quality-parity.md` is the map of what is still owed and which issue owes
it.

None of them measures anything about acoustics. `README.md` says what a green
result from this suite does and does not mean, and none of the checks above is
that result.
