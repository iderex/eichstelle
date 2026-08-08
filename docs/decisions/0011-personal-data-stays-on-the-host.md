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
and the operator is the one answerable for that rather than this project.

Nothing here is legal advice and this record does not attempt any. The point is
narrower and it is entirely within this project's control: the operator has an
obligation, and the only useful thing this suite can do about it is to make
certain it never becomes part of the problem. A tool that quietly uploaded a
sample for diagnostics would turn one organisation's controlled processing into a
transfer nobody assessed.

So the rules below are architectural rather than aspirational. A promise that
depends on an operator configuring something correctly is a promise the operator
has to audit, and auditing this suite's network behaviour is not their job.

### The harness makes no outbound connection

Not for telemetry. Not for update checks. Not for crash reporting. Not for
fetching fixtures, which is why record 0005 has stimuli generated from recipes
rather than downloaded. Not for resolving a standard reference, which is why
record 0005 has an operator's licensed reference read from a local directory
rather than looked up.

Installing dependencies is a separate act, performed by the operator's own
package manager, before the suite runs and outside it. That act reaches the
network, obviously, and it is the operator's package manager doing the thing it
exists to do under the operator's own policy. The rule is about the suite, and
the suite does not install anything.

The rule gets its teeth from the test suite running with outbound network access
denied, because a rule of this kind that is merely stated is a rule that decays
the first time somebody adds a convenient lookup. Record 0010 is where the
headless shape of this project is argued and it says of itself that the mechanism
is owed: issue #49 carries the lint rule that refuses a test which opens a
socket, and issue #52 carries the conformance test that runs the whole default
suite with the network denied and asserts it passes. Neither has landed. No
workflow in this repository runs the suite at all today, with or without a
network, and until #49 and #52 are in the tree this section is a design rule that
nothing enforces.

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

So the record is treated as potentially sensitive by default rather than treated
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

It is off by default. It is per run rather than a stored setting, so no
configuration file can be in a state where publishing happens without somebody
deciding it that day. The operator sees exactly what would be sent, in full,
before anything is sent, and the preview is the payload rather than a summary of
it. Anything derived from operator-supplied audio is excluded from the default
payload and requires a separate, explicit confirmation of its own.

The case federation is designed around is the safe one: results computed from
generated fixture signals, which is also the case that produces the comparison
anybody wants. Where results go and under what terms they are then available is a
maintainer question rather than an engineering one.

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
is handled by keeping it on the host rather than by forbidding it.

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

This record is not enforced by anything at present. The harness does not exist
yet, so nothing has been written that could violate it, and the checks that would
refuse a violation are owed by issues #49 and #52. Read it as a design rule that
the code has to be built to satisfy, and as prose until those two land.

## Status

Accepted, 2026-08-08.
