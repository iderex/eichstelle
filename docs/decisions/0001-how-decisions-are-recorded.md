# 0001. How decisions are recorded

## Decision

A decision that shapes this project is written as a numbered file in
`docs/decisions`, in five sections in a fixed order, and once it has landed it is
never rewritten: a decision that turns out to be wrong is superseded by a later
record that names it, and the old record stays where it is.

## Context

Every other record in this directory has a format to follow, and this is where
that format is written down, so that the records are checkable against something
rather than against taste.

A decision that lives only in someone's head is a habit. The failure that
prevents is the one where a choice gets made implicitly by the first commit that
depends on it, and a year later nobody can say whether the alternative was
considered or simply never occurred to anyone. The opposite failure matters just
as much: a decision whose reasons were never written down gets reopened every
time somebody new arrives, because there is nothing to argue with except the
person who made it.

The format is deliberately small. A long template does not get filled in, and a
template that does not get filled in produces records that are worse than no
record, because they look like reasoning and are not.

### The file name

    docs/decisions/NNNN-kebab-slug.md

`NNNN` is a zero-padded four-digit sequence number. The slug is lowercase words
separated by hyphens, and it says what the decision is about rather than what
kind of thing it is.

A number is never reused, including by a record that is withdrawn, superseded or
abandoned before it lands. A number is an address: a commit message, an issue, a
pull request or another record may cite `0004` for as long as this repository
exists, and a reused number silently redirects every one of those citations to a
different decision.

The number comes from the issue that produced the decision, which is where the
reasoning was argued before the file existed. Two records being written at the
same time therefore do not collide over a number, because their issues do not
collide. Nothing checks this, and the paragraph below on what is not enforced
says so again.

### The sections, in this order

**The decision.** One sentence, in the present tense, saying what is now true. If
it takes a paragraph, the record is carrying two decisions and should be two
records.

**Context.** What forced a choice. What the constraints were, which of them come
from outside this project, and what would have gone wrong if the question had
been left open. A reader who disagrees with the decision is nearly always
disagreeing with something in this section, and this is where they should be able
to find it.

**Alternatives.** What else was considered, each with the reason it was rejected.
An empty alternatives section is a claim that no other option existed, which is
almost never true, and a reader has no way to tell it apart from an author who
did not look.

**Consequences.** What the project now has to live with, including the parts that
are inconvenient. A consequences section listing only benefits is an
advertisement. The costs are the half a later reader needs, because they are what
a superseding decision will be arguing about.

**Status.** One of the values below, with a date.

### The status values

`Accepted`, with the date it was accepted. The decision is in force.

`Superseded by NNNN`, with the date of the supersession and a sentence saying
what changed. The record stays exactly as it was, and this line is the only thing
added to it. A reader arriving at an old record is told, in the record itself,
where the current answer is.

`Withdrawn`, with the date and the reason. The decision was in force and is no
longer, and nothing replaced it. This is different from being superseded and the
difference matters: superseded means the question has a new answer, withdrawn
means the question is open again.

There is no `Proposed`. A record is written when the decision has been made, and
the argument that produced it happens on the issue, in public, where anyone can
join it. A directory of proposals is a second place for the argument to live and
the two drift.

### Records are appended, never rewritten

A landed record is not edited. The one exception is adding the supersession
pointer or the withdrawal line to its status section, and that is an addition
rather than a rewrite.

This is not tidiness. Editing a landed record destroys the only evidence that the
project once thought otherwise, and that evidence is exactly what a later reader
needs. Somebody who finds a decision surprising is served by seeing what was
believed before, what changed, and when. Somebody who finds a rewritten record is
served by nothing at all, because the record now agrees with the present in a way
that proves nothing about the reasoning.

A typographical fix is not worth an exception, and a record with a typographical
error in it has never harmed anyone.

## Alternatives

No records, with the reasoning left in commit messages, issues and pull request
descriptions. Rejected because all three are organised by when something
happened, and a decision is looked up by what it is about. It also loses the
distinction between what was decided and what was merely discussed, which is the
distinction the directory exists to hold.

A longer template, of the kind that carries headings for drivers, decision
outcome, confirmation, pros and cons per option, and links. Rejected because
sections that are filled in out of obligation read as reasoning and are not, and
because the cost of writing a record should be low enough that the record gets
written. Five sections is already at the edge of what a small decision justifies.

Editing a record in place when it turns out to be wrong, so that the directory
always reads as the current state. Rejected for the reason above: it is the
directory that would then be the only record, and it would carry no history at
all. The current state is what the code and the schemas already are.

Numbering by date, for example `2026-08-07-fixture-format.md`. Rejected because
the date answers a question nobody asks and makes citation long. The date is in
the status line, where it belongs, and the sequence number is short enough to say
out loud.

One `decisions.md` file with a section per decision. Rejected because it is a
permanent merge conflict once more than one person writes a record, and because
a decision cannot then be cited by path.

Keeping decisions in the issue tracker alone, with a label. Rejected because the
tracker is not in the tree. A clone of this repository has to carry the reasoning
that produced it, and a reader offline, or reading a tag from three years ago,
gets the code without the argument otherwise.

## Consequences

The directory grows and never shrinks, and some of what it holds is out of date
by design. A reader who opens one record without following its status line can
come away with a superseded answer. The supersession pointer is the whole defence
against that, so a supersession that lands without it is a defect worth treating
as one.

Nothing here is enforced. No check refuses a record with a missing section, a
status that is not one of the three values, a reused number, or an edit to a
record that has already landed. `docs/quality-gates.md` is the authority for what
does run, and none of it reads this directory. Issue #49 is where this project's
invariants become lint rules that refuse, and the shape of a record is a
reasonable candidate for one; until something lands there, this record is prose
and should be read as prose.

The five records already in the tree were written before this one and follow this
format, which is where the format came from. They are not edited by this record,
including the ones whose sections could be described more precisely, because that
is exactly the edit this record forbids.

Writing a record is a cost paid on every decision that shapes the project, and
some of those decisions are small. The line is whether a later reader would be
surprised, and that judgement is a person's. No rule here draws it, and a
directory of thirty records where three would do is its own failure.

## Status

Accepted, 2026-08-08.
