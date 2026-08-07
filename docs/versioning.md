# Versioning, and what a version number promises

Two things here are versioned, and conflating them would be a mistake that
lasts. The harness has a version. The fixture set has a version. A result record
names both, because a result produced by a new harness against an old fixture
set is a different thing from the reverse, and a reader has to be able to tell
which they are holding.

## The harness version

The harness version follows ordinary compatibility rules: a major change may
break something a user depends on, a minor change adds without breaking, and a
patch change fixes without adding.

What "something a user depends on" means is not left to taste. Four surfaces are
covered by the promise, and they are covered because each has a user outside
this project who cannot be told to adjust:

The command line. The verbs, their options, their exit statuses and what they
write.

The adapter contract. The job document, the result document, the capability
declaration and the invocation shape, as decision record 0006 sets them out.

The record format. The fields of a result record and what each one means.

The fixture schema. The fields a fixture carries and how a fixture declares
which schema version it targets, as decision record 0004 sets them out.

A change that breaks an existing adapter is a major change regardless of its
size. A one-character rename of a field in the job document is a major change.
This is not proportionality, it is who pays: the people affected write code this
project does not control and did not ask for, and a small change that silently
stops their adapter working costs them more than it saved here.

## The fixture set version

The fixture set version is not a compatibility statement. It is an identity.

Fixtures are added, and they are corrected under the narrow rules in decision
record 0008, but they are not silently changed. So what the fixture set version
communicates is which fixtures existed and at what revision, not whether
anything will still work.

The checksum manifest in a result record's header is what actually pins the
fixture set. The version is what a person quotes in a sentence. If the two ever
disagree, the manifest is right.

## Before the first release

The numbering says clearly that nothing is stable yet, and the harness carries a
`0.` major version until the condition below is met. The placeholder currently
in the project metadata promises nothing at all and should not be read as a
position on any of this.

The condition for declaring the contract stable is deliberately not a date and
not a feature list. It is that the adapter contract has survived being
implemented by somebody outside this project without needing a change.

That is the honest condition because until it has happened the contract is a
guess. Every field in it was chosen by the same people who wrote the harness
that consumes it, and a contract only ever tested by its author is a contract
whose assumptions have never been contradicted. An outside implementation is the
first thing that can contradict them.

## What a version number does not promise

It does not promise that a fixture's expected value will never be corrected. A
fixture found to be wrong is corrected, under the rules in decision record 0008,
because leaving a known-wrong expected value in place to protect a version
number serves nobody.

What it promises instead is that the correction is visible. A correction
increments the fixture's revision and records what the value was, what it now
is, how the error was found and when. A result record names the revision it ran
against, so two results against the same fixture identifier can always be told
apart.

It does not promise that a report from one harness version can be compared with
a report from another without reading both headers. The headers exist for
exactly that reason.

It does not promise anything about the implementations under test. Their
versions are theirs, and an adapter reports the version it actually loaded
rather than the version it was pinned to.
