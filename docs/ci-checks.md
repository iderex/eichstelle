# The checks that run on a pull request

This is the one place that names them. `CONTRIBUTING.md` and
`docs/quality-parity.md` both point here instead of carrying a second copy,
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
`[tool.mypy]` and not an argument in the workflow, so this check cannot
cover less than the bare `mypy` command covers on a contributor's machine.

**`tests (3.11)`**, **`tests (3.12)`**, **`tests (3.13)`**, **`tests (3.14)`**
each run `python -m pytest` once, on the interpreter named in the check. A
failure is a failing test, a collection error, or a warning, since
`filterwarnings = ["error"]` in `pyproject.toml` makes every warning a failure.
A failure on one leg and not the others is the thing four legs exist to find:
`pyproject.toml` declares support for four interpreters, and support nothing
runs on is a claim and not a fact.

The suite runs with no outbound network. The step opens an empty network
namespace, brings loopback up inside it and runs the suite there, so a test that
reaches for the internet fails, and does not pass on a runner that happens to
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

**`coverage`** measures the suite once, on the declared interpreter floor, and
judges the verdict surface against the threshold in `tools/coverage_gate.py`. A
failure is either the surface covered below that threshold, or a measurement the
gate could not read.

The second kind is worth telling apart from the first, and the gate's exit code
does: exit 1 is coverage below the bar, exit 2 is a report that is absent, a
report that cannot be parsed, a surface module the report does not mention, a
surface holding no executable line, or a module in the package that is on
neither the surface nor the exclusion list. All of those are a gate that has
stopped measuring what it claims to measure, and a gate in that state reporting
green is worse than no gate at all.

Which modules are on the surface, which are outside it and the reason for each
are in `tools/coverage_gate.py`, next to the code that reads them, and not
here. Counting is per executable line across the whole surface, so one large
uncovered module cannot hide behind several small covered ones.

What it does not cover: the whole-repository number, which the gate prints and
never enforces; the modules named as exclusions, for the reasons written beside
them; and the parts of a run that happen in a subprocess, which coverage does
not follow into and which therefore make the number an understatement and never
an overstatement. This job also runs the suite with ordinary network
access, so the offline promise is the `tests` legs' and not this one's.

**`fixtures`** validates every tracked fixture under `fixtures/` against the
schema and holds every fixture's regenerated signal against the committed
checksums in `fixtures/checksums.txt`, using `python -m eichstelle.fixtures`. A
failure is a fixture the validator refuses, which `docs/fixtures.md` lists by
kind, or a stimulus whose hash does not match the manifest, or a run that could
not complete and whose result is therefore unknown. A stimulus that moved names
the fixture and shows both hashes, so an investigation starts at the signal
and not at the implementations.

Today it validates nothing and verifies nothing, because no fixture is tracked
yet, and it says both in its own output instead of reporting green in silence.
The manifest is tracked and empty, which is the same statement from the other
side: it holds every fixture there is. Read this check green today as "there was
nothing to refuse", not as "the fixture set is sound".

What the checksum half does not cover is worth knowing before it is trusted. It
compares regenerated samples against a recorded hash, so it says nothing about
any file on disk, and it is exact to the last bit of the encoding, which means a
platform whose maths library rounds a transcendental differently can report a
mismatch that is not a change to this repository. Whether that happens between
the platforms this project supports is not measured; `docs/fixtures.md` says how
it would be.

**`invariants`** runs `tools/invariants.py`, which matches this project's own
invariants against the tracked tree. A failure is a line breaking one of them,
or a run that did not complete: a rule file that will not parse, a rule that
leaves out one of the fields it has to declare, a pattern that will not compile,
or an exemption naming a path nobody tracks. Exit 1 is the first kind and exit 2
is the second, and both fail the job.

The rules are data in `tools/invariants.toml` and not code, one entry per
invariant, each naming the decision it enforces, the mistake it catches, its own
edge and what prompted it. They are not listed here, because the file is the
authority and a second copy would drift against it. A refusal quotes the rule's
decision and its mistake, so a red check says what it is about without anybody
opening that file.

What it does not cover is a floor rather than a guarantee, and the run prints
each rule's own edge on every pass, and not only in a document. These are
token-level pattern matches over source text: a shape written a different way
walks through, several of the rules read one directory and say so, and one of
them reads a set of exemptions whose reasons are printed beside the count.
Read this check green as "no line matched", never as "the invariant holds".

**`no-tracked-audio`** runs `tools/refuse_tracked_audio.py`. A failure is a
tracked file whose extension names an audio container, or a tracked file whose
leading bytes match an audio container signature whatever it is called, or a
scan that could not complete. Issue #6 is the decision it enforces: no audio is
committed here, because the reference signals belong to the purchased standards
and committing one would be redistribution.

It judges the index and not the working tree, so it reports what is being
pushed. `tools/tracked-audio-allowlist.txt` is the only way past it, it is empty
and expected to stay empty, and every entry has to carry a reason beside the
path. A path with no reason stops the scan and grants nothing.

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
arrives in the code scanning view and not as a red check;
`docs/quality-parity.md` holds the rule for what happens to a finding there.

The supply-chain self-audit in `scorecard.yml` is deliberately absent from this
list. It has no `pull_request` trigger, because that path cannot publish its
results, so it is not a check anybody sees on a pull request.

The mutation run in `mutation.yml` is absent for the same shape of reason and a
different one underneath it. It has no `pull_request` trigger either, because
issue #48 decides that a mutation score never blocks a change: the number moves
with refactoring and not with test quality, and a run slow enough to make
every pull request wait for it would be switched off within a month. It is
scheduled, its score goes into its own job summary and into
`docs/measurements/mutation-score.md`, and the one thing it does fail on is
producing no score at all, which is the tool having stopped rather than a low
number.

## What none of them do

None of them is a mutation score or a fuzzing run. `docs/quality-parity.md` is
the map of what is still owed and which issue owes it. The mutation score exists
as of #48 and is not on this list because nothing it does reaches a pull
request.

The coverage bar was on this paragraph until #47 landed and is now a check of
its own above. It bars one surface and reports the rest, so a green `coverage`
says the verdict surface is covered to the threshold and says nothing at all
about the modules named as exclusions.

None of them measures anything about acoustics. `README.md` says what a green
result from this suite does and does not mean, and none of the checks above is
that result.
