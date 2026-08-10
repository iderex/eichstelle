# 0012. Provenance, without transcription

## Decision

An expected value in this tree declares one of three provenances,
`generated-by-definition`, `published-paper` or `implementation-consensus`, and
no expected value is transcribed here from a document this project does not
hold.

## Context

Record 0004 defines the fixture format and lists four provenances. One of them
licenses exactly what every other statement of this rule forbids:

    $ git grep -n 'transcribed' origin/main -- docs/decisions/0004-fixture-format.md
    origin/main:docs/decisions/0004-fixture-format.md:79:`standard-clause`. The expected value is transcribed from a named clause or table
    origin/main:docs/decisions/0004-fixture-format.md:82:result this suite can produce. The value is transcribed; the source document is

Three other places in this repository say the opposite, and they agree with each
other. `CONTRIBUTING.md` lists it among the four things this project will not
accept:

    $ git grep -n 'No expected value is copied' origin/main -- CONTRIBUTING.md
    origin/main:CONTRIBUTING.md:32:No expected value is copied out of a purchased standard. The standards are sold,

`docs/adding-a-fixture.md` carries a section headed "The value you may not write
down" and sends the number to an operator's own machine instead. Issue #55 asks
for the copyright document and states the rule stricter than the law requires,
issue #49 calls it the invariant that must never be violated once, and issue #31
is the mechanism that serves the normative case without the value ever entering
this tree.

So the landed record is the odd one out, and it is the one a contributor reaches
first. A rule that lives only in an issue is not a rule; a record is what
somebody has in front of them while they are writing the fixture.

The disagreement is not about caution. A single number is a fact and facts carry
no copyright, but the tables in these standards are compilations, they are what
the publisher sells, and a fixture set carrying values lifted from one is a
fixture set nobody may copy. That is the whole reason the set exists. Deciding
per value where the line between a fact and a compilation runs is an argument
this project would be having at the margin, for a number it does not need,
against a publisher with more time than it has.

Two narrower readings were available and neither survives. Restricting
`standard-clause` to the maintainer does not help: who typed the value changes
nothing about what the repository then distributes. Reading it as covering only
the maintainer's private tree does not help either, because a provenance value is
a field in a tracked file and there is no private tree.

Nothing is lost that the design does not already replace. What
`standard-clause` promised was a comparison against a normative target, which
record 0004 calls the strongest result the suite can produce. Issue #31 keeps
that comparison and moves the value to the operator who bought the standard: the
harness reads it from a directory they control, checks it against a hash, and
reports which fixtures ran that way. The result is the same result. It is
available to the operator who holds the document and to nobody else, which is
the situation the licensing already creates and not one this record adds.

## Alternatives

Edit record 0004 in place, so that the directory reads as the current state.
Rejected by record 0001, which forbids it for the reason that editing a landed
record destroys the evidence that the project once thought otherwise. That
evidence is the useful half here: somebody will propose transcription again, and
the argument against it is worth more with 0004 still readable beside it.

Leave 0004 alone and let the lint rule from #49 refuse the shape. Rejected
because it puts a contributor between two authorities that disagree, with a red
check on one side and a landed decision on the other, and the check is the one
that looks wrong in that pairing. The rule is right and the record is what has
to change first.

Withdraw 0004 entirely and write the fixture format again. Rejected because one
section of it is wrong and the rest is in force. A rewrite would restate a format
that has a schema behind it, and the restatement would drift against the schema
the first time either moved.

Keep a fourth provenance for standards that publish a preview or a freely
readable clause. Rejected because it makes the rule a judgement about each
document's terms, made by whoever is adding a fixture, at the moment they most
want the number.

## Consequences

Record 0004 gains a supersession line on its status and nothing else. It is
superseded on its provenance list only, and the sentence there says so, because
everything else in it is the format this repository runs on.

Schema version 1 still admits `standard-clause`. A published schema version is
never edited where the edit would refuse a fixture that is valid under it today,
which is 0004's own rule and the schema's own description, so removing the value
is a version 2 and a migration rather than a line in this record. Nothing in the
validator therefore refuses the value at this commit, and nothing else does
either: issue #49 is where a rule refuses it in a tracked fixture, and until that
lands this record is prose and should be read as prose.

A contributor who holds a standard and wants its number has one route and it is
not this repository. Their fixture declares a different provenance, or it waits
for the licensed-reference slot in #31, or it does not get written. That is a
real cost and it falls on the people best placed to produce good fixtures.

The suite's public claim gets narrower and more honest in the same move. Most of
the fixture set is differential, `README.md` already says so, and this record is
what makes that sentence true of the maintainer's own fixtures as well as of
everyone else's.

## Status

Accepted, 2026-08-10.
