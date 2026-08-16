# 0011. Personal data stays on the host

## Decision

Audio an operator points this suite at stays on the operator's machine: the
harness makes no outbound network connection, it writes nothing outside the
directories the operator named, and the only way any result leaves the host is an
act the operator performs on purpose, per run, having seen exactly what would be
sent.

## Context

This is not a courtesy and it is not a privacy statement written to have one. The
material this suite processes is sound recordings, and a sound recording can be
personal data in the ordinary legal sense.

The cases are not exotic. A field recording made to characterise a product
carries whatever voices were in the room while it was made. A recording of a
machine in a workplace carries the people working near it, and in some
jurisdictions the recording of a workplace is a matter for the works council
before it is a matter for anybody else. A vehicle cabin recording carries its
occupants. A recording made in a hospital corridor carries patients. Where a
recording relates to an identifiable person, data protection law applies to it,
and the operator is the one answerable for that, not this project.

Nothing here is legal advice and this record does not attempt any. The point is
narrower and it is entirely within this project's control: the operator has an
obligation, and the only useful thing this suite can do about it is to make
certain it never becomes part of the problem. A tool that quietly uploaded a
sample for diagnostics would turn one organisation's controlled processing into a
transfer nobody assessed.

So the rules below are architectural and not aspirational. A promise that
depends on an operator configuring something correctly is a promise the operator
has to audit, and auditing this suite's network behaviour is not their job.

### The harness makes no outbound connection

Not for telemetry. Not for update checks. Not for crash reporting. Not for
fetching fixtures, which is why record 0005 has stimuli generated from recipes
and never downloaded. Not for resolving a standard reference, which is why
record 0005 has an operator's licensed reference read from a local directory
and never looked up.

Installing dependencies is a separate act, performed by the operator's own
package manager, before the suite runs and outside it. That act reaches the
network, obviously, and it is the operator's package manager doing the thing it
exists to do under the operator's own policy. The rule is about the suite, and
the suite does not install anything.

The rule gets its teeth from the test suite running with outbound network access
denied, because a rule of this kind that is merely stated is a rule that decays
the first time somebody adds a convenient lookup. Record 0010 is where the
headless shape of this project is argued, and the two mechanisms it names as owed
are in the tree, as is a workflow that runs the suite:

    $ git grep -n 'id = "no-socket-device-or-display-in-the-suite"' -- tools/invariants.toml
    tools/invariants.toml:85:id = "no-socket-device-or-display-in-the-suite"

    $ git grep -n 'def test_the_default_suite_passes_with_outbound_network_denied' -- tests
    tests/e2e/test_architecture_conformance.py:157:def test_the_default_suite_passes_with_outbound_network_denied(

    $ grep -c 'python -m pytest' .github/workflows/verify.yml
    1

Four things hold this section up, and each of them is a floor rather than a
proof. Reading any one of them as the whole rule is how a reader ends up
believing more than has been established.

The invariant rule, run as the `invariants` check, matches patterns against
tracked test sources. Its own entry in `tools/invariants.toml` states its edge: a
connection made through a library that wraps the socket module, or through
`ctypes` against the platform's sockets library, passes it.

The offline guard in `tests/e2e/offline/` replaces four functions in Python's
socket module, so what it can see is what a Python process does. Its own
docstring calls itself a floor and not a sandbox, and names what is outside it:
a raw socket, a connection made through `ctypes`, and any subprocess that is not
a Python interpreter.

The conformance test asserts that the whole default suite passes with that guard
loaded into every process of the run. That is a statement about what ran. A route
no test takes is a route it says nothing about.

The fourth is the strongest and it is not in this tree's own code. The `tests`
checks run the suite inside an empty network namespace, so there is no route for
anything in that process tree to take, whatever language it is written in and
whichever of the three above it would have slipped past. What it does not cover:
it runs on the workflow's Linux runner, so a run on another platform is outside
it, and the install step ahead of it has ordinary network access because it has
to fetch the locked set.

So this section is enforced, and what is enforced is narrower than the sentence
it opens with. What is refused is a socket the suite opens through Python, and a
whole run given no route at all on one platform. Nothing measures whether the
harness would reach the network if something gave it the chance.

### Operator audio and the working directories

Operator audio is read and never copied anywhere the operator did not name.

Nothing is written into the repository tree. A suite that writes results, caches
or temporary files next to its own source is a suite whose outputs get committed
by accident, and the accident is a recording in a public repository.

Temporary files go in a directory the operator can name, and the run removes what
it created when it ends. Each adapter invocation gets a fresh directory,
`docs/adapter-contract.md` says so, and an adapter is told not to write outside
it. That prohibition is stated to adapter authors and is not enforced by the
harness today, which the contract says in its own words.

### The record is treated as sensitive by default

The result record can contain fragments of what it processed even though it
contains no audio. A file path can carry a person's name, a site name, a project
code name or a patient identifier. A diagnostic message quoting a filename
carries the same. A metric value computed from a recording is derived from
personal data, and derivation is not anonymisation.

So the record is treated as potentially sensitive by default and is not treated
as a set of numbers. The default report identifies operator-supplied inputs by a
stable identifier the operator assigns, not by path. The full path is available
in a mode the operator turns on, because somebody debugging their own run on
their own machine needs it, and it is off unless they ask.

Results computed purely from the generated fixture signals contain no personal
data by construction. There was never a recording, there was a recipe, and every
input is in this repository already. That distinction is what makes the next
section possible.

### Federation is a deliberate act

Federation means publishing your results so they can be compared with other
operators' results. It is worth having and it is the feature most likely to leak
something, so it is built with the leak in mind from the beginning.

It is off by default. It is per run and not a stored setting, so no
configuration file can be in a state where publishing happens without somebody
deciding it that day. The operator sees exactly what would be sent, in full,
before anything is sent, and the preview is the payload itself, never a summary of
it. Anything derived from operator-supplied audio is excluded from the default
payload and requires a separate, explicit confirmation of its own.

The case federation is designed around is the safe one: results computed from
generated fixture signals, which is also the case that produces the comparison
anybody wants. Where results go and under what terms they are then available is a
maintainer question and not an engineering one.

Issue #60 carries the design and issue #57 carries the text that tells a reader
about all of this in the place they will look first. Nothing of it is
implemented, and issue #60 says the implementation is deliberately not in the
first release.

## Alternatives

Opt-out telemetry, with an easy switch. Rejected because a default that sends
anything makes the operator's compliance position depend on their having read the
documentation, and because the first version of any telemetry payload is the one
that turns out to include a file path.

Anonymising paths by hashing them instead of replacing them with an
operator-assigned identifier. Rejected because a hash of a short, guessable
string is not anonymous, and because the operator needs to be able to map the
identifier back to their own material, which a hash they cannot invert does not
give them.

Uploading results automatically and asking forgiveness through a documented
delete route. Rejected because a transfer that has happened cannot be undone by a
deletion, and because the operator, not this project, is the one who has to
answer for it.

Refusing operator-supplied audio entirely, so that the suite runs only on
generated fixtures. Rejected because running an implementation against your own
material is a real use, and one an implementation maintainer will want. The risk
is handled by keeping it on the host and not by forbidding it.

Storing the operator's mapping from identifier to path in the record, so that a
report can show both. Rejected for the obvious reason: it puts the path in the
record, which is the file most likely to be attached to an issue.

## Consequences

The suite cannot report a crash to anybody automatically. A bug report is
something the operator writes and sends, having read it, and this project gets
fewer and later reports than a project with crash reporting does. That cost is
accepted deliberately.

There is no built-in way to fetch a fixture set update, so an operator moves to a
new fixture set by updating the installed package or the checkout. Record 0005's
checksums are what tell them the set they are running is the set they think it
is.

Every feature added later has to be checked against this record before it is
built, and some obvious conveniences are not available: a documentation link
resolver, a version notifier, a shared cache of expected values, a hosted report
viewer that uploads a record to render it. None of those is refused by a machine
today.

The identifier-instead-of-path default costs the operator a step. They assign
identifiers to their own material, and a run over a directory of files nobody has
named is more awkward than one that just prints paths. That awkwardness is the
mechanism, and softening it would remove the thing it does.

Part of this record is refused by a machine and part of it is not, and collapsing
the two is how a reader ends up trusting the half that is prose. The
outbound-connection rule is held by the four things that section names, each with
its bound written beside it there.

The rest of the record has one check between it, and that check is narrower than
the section it belongs to:

    $ git grep -n 'def test_no_operator_path_reaches_the_record_by_default' -- tests
    tests/unit/test_result_record.py:233:def test_no_operator_path_reaches_the_record_by_default(tmp_path: Path) -> None:

It writes a record with the default settings and asserts that no source path
reached it and that the header says so. It does not reach a diagnostic message
that quotes a filename, where a temporary file was written, or any of the
federation rules, which have no implementation for a check to read.

Those are a design rule the code has to be built to satisfy, and the list of
conveniences above is what that reading has to hold out against. A feature that
uploaded a record would be caught by a person reading this record before it was
built, or not at all.

## Status

Accepted, 2026-08-08.
