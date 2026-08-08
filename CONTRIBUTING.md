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

## Running the gate locally

The tools, the commands and what each one does and does not cover are in
[docs/quality-gates.md](docs/quality-gates.md). That file is the authority; a
second copy of the list here would drift against it, and the one in the wrong
place would be this one.

There is no single command that runs all of them yet, and nothing runs any of
them on a pull request. `docs/quality-gates.md` says so in its own words and
shows the command behind the claim. Issue #15 and issue #17 are where that
changes.

## Running the tests

    python -m pytest

That is the whole suite, and it is one invocation with no path or flag, so that
the workflow issue #17 adds can run the same characters and a green run here
means what a green check there means. No workflow runs it today. It needs the
project installed, because the package reads its own version from the installed
distribution: `python -m pip install -e . --group dev`.

The suite is split into fast in-process tests under `tests/unit` and slower
end-to-end runs under `tests/e2e`, selected either by that path or by the marker
of the same name with `-m unit` or `-m e2e`, and the marker is derived from the
directory in `tests/conftest.py` so the two cannot drift apart.

## The checks that run on a pull request

Not listed here. `docs/ci-checks.md` is the one place that names them, so that
a check can be added or renamed in one file rather than two.

That file is not written yet. Issue #17 owes it, along with the workflow it
describes, and until both land the honest answer to "what runs on my pull
request" is the set of workflows in `.github/workflows`, read directly.

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

## Where the decisions live

[docs/decisions](docs/decisions) holds the decisions that shape the
architecture, each with the reasoning that produced it. They are written before
the code that depends on them, and a pull request that contradicts one is an
argument with the record rather than with a reviewer. If you think a record is
wrong, say so on the issue it came from.

Planning happens on the issue tracker first, and a change starts as an issue
that says what is wrong, what the evidence is, and what done means. Where the
evidence is a number, it carries the command that produced it.
