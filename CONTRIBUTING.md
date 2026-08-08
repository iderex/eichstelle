# Contributing

## What this project is

eichstelle is a conformance test suite. It runs somebody else's implementation
of a psychoacoustic standard against a set of fixtures, across a process
boundary, and reports what the implementation returned and how that compares to
what the fixture declares. It computes no acoustic quantity of its own, so it
has no house answer to measure anyone against.

That shape decides most of what is welcome here. A fixture, an adapter, a
comparison, a report, a test, a document: yes. A metric: no. `README.md` says
what a green result does and does not mean, and it is worth reading before
opening a pull request that assumes otherwise.

## What this project will not accept

Four rules. Each of them has a reason that is written down somewhere else, and
each of them is easier to read here than to discover in a rejected pull
request.

No audio file is committed. Reference signals are generated from their
parameters at run time and never shipped as bytes in this tree. Issue #6 is the
decision and `tools/refuse_tracked_audio.py` is the check that refuses one.

No implementation of a metric is accepted. Not as a reference, not as a
fallback, not "just for a test". The moment this repository can compute a
loudness it becomes a fourth implementation with an opinion, and it can no
longer report a disagreement without being party to it. Issue #4 is the
decision.

No expected value is copied out of a purchased standard. The standards are sold,
their tables are the seller's, and a fixture carrying a number lifted from one
cannot be redistributed. Where an operator owns a standard they may supply such
values locally; issue #31 is the slot that exists for exactly that, and nothing
of the kind is tracked here.

Every fixture carries its provenance. A fixture says where its expected value
came from, whether that is a normative table, a published paper, or the
agreement of the implementations themselves. A fixture that does not say cannot
be told apart from one that made its number up, and a reader has no way back to
the source.

## Installing, and the lock file

    uv sync --locked

That is the install. Locked mode means uv refuses when `uv.lock` does not match
what `pyproject.toml` declares, instead of quietly resolving something newer, so
a green run is a green run of a set of versions somebody recorded. It covers the
development tools as well as the runtime dependencies, because a linter that
changes its rules between two runs of the same commit is the same problem in a
smaller costume.

    uv lock

That is the single command that regenerates the lock. It is run deliberately and
its diff is read, and there is no scheduled refresh that moves those versions
without anybody looking at them. Decision record 0002 is where uv was chosen and
why.

`python -m pip install -e . --group dev` still works for anyone who does not
want uv, and it resolves freshly every time. Use it if you like, and know that
what it gives you is not the recorded set.

## Running the gate locally

The tools, the commands and what each one does and does not cover are in
[docs/quality-gates.md](docs/quality-gates.md). That file is the authority; a
second copy of the list here would drift against it, and the one in the wrong
place would be this one.

There is still no single command that runs all of them locally. On a pull
request they are run for you, each as its own check, by the `verify` workflow.
`docs/quality-gates.md` says which commands those checks run and what each one
does not cover.

## Running the tests

    python -m pytest

That is the whole suite, and it is one invocation with no path or flag, so that
the `verify` workflow runs the same characters and a green run here means what a
green check there means. It needs the project installed, because the package
reads its own version from the installed distribution, which is what
`uv sync --locked` above does.

On a pull request the suite runs once per supported interpreter version, and it
runs with no outbound network. A test that reaches the internet passes here and
fails there.

The suite is split into fast in-process tests under `tests/unit` and slower
end-to-end runs under `tests/e2e`, selected either by that path or by the marker
of the same name with `-m unit` or `-m e2e`, and the marker is derived from the
directory in `tests/conftest.py` so the two cannot drift apart.

## The checks that run on a pull request

Not listed here. `docs/ci-checks.md` is the one place that names them, so that
a check can be added or renamed in one file rather than two.

It carries every check name a pull request produces and what a failure of each
one means, including the ones that do not come from the gate above. Read it
before asking why a check is red.

## Signing your work

Every commit carries a `Signed-off-by` trailer matching its author. Git writes
it for you:

    git commit -s

Adding it to work already committed is a rebase over the base of your branch:

    git rebase --signoff origin/main

The trailer is an assertion, not a formality. What you are asserting is the text
in [DCO](DCO), which is the Developer Certificate of Origin 1.1, unmodified.
Read it once. The sign-off gate refuses a commit whose trailer does not match
its author exactly, so a mismatch between the name in your git config and the
name in the trailer fails the check rather than passing it quietly.

One thing the certificate assumes is not true here yet. Its clauses speak of
"the open source license indicated in the file", and this repository declares no
license, which makes it all rights reserved. That is not an oversight: the
license is a maintainer decision and is open as issue #1. Until it is answered,
signing off certifies that you have the right to submit your contribution and
that you accept the permanent public record of it, and the license it will
eventually be distributed under is not yet a thing anyone can name. If that
matters to you, wait for #1.

## Adding a fixture, or an implementation

Two walkthroughs, each written for somebody who has not seen this project
before.

[docs/adding-a-fixture.md](docs/adding-a-fixture.md) is how to write a fixture:
what the fields mean, how to choose a tolerance and how to justify it, what
evidence each provenance kind needs, and what the rule above about purchased
standards means when you are holding a number and deciding where it goes.

[docs/adding-an-implementation.md](docs/adding-an-implementation.md) is how to
connect your own library: the five steps of the adapter contract, how to declare
your capabilities without producing a wall of errors that reads as your library
being broken, and why an adapter may contain no correction.

Both end at a worked example that lives in this tree and is run by the suite, so
neither can drift from what works. Neither is restated here; if this file and one
of them ever disagree, they are the ones that are right about their own subject.

## Where the decisions live

[docs/decisions](docs/decisions) holds the decisions that shape the
architecture, each with the reasoning that produced it. They are written before
the code that depends on them, and a pull request that contradicts one is an
argument with the record rather than with a reviewer. If you think a record is
wrong, say so on the issue it came from.

Planning happens on the issue tracker first, and a change starts as an issue
that says what is wrong, what the evidence is, and what done means. Where the
evidence is a number, it carries the command that produced it.
