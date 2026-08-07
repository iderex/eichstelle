# 0008. Fixtures pin a standard edition and are not edited in place

## Decision

Every fixture names the edition of the standard it encodes, every result record
carries that edition, and a fixture is never edited to follow a revision.

## Context

This looks like bookkeeping and it is the difference between a comparable result
and a meaningless one.

The standards in scope move. ECMA-418-2 has had several editions in a short span,
and the three implementations do not all target the same one: published material
on one of them names the 2025 edition of that standard, while another describes
itself against ECMA-418 with no year at all. ISO 532-1:2017 is under revision.
DIN 45692 dates from 2009 and depends on a loudness standard that has itself
changed since.

Two implementations computing the same named metric to two different editions are
not in disagreement. They are answering different questions. A suite that cannot
tell those apart will publish a false finding within its first month, and a false
finding is worse than no suite, because it costs the goodwill of the projects
this one depends on.

### The fields that pin an edition

A fixture carries `standard`, the designation of the document; `part`, where the
document has parts; `edition`, the year of the edition the expected value comes
from; and `reference`, the clause, table or figure inside that edition the value
was taken from. Record 0004 lists these among the fields a fixture must carry;
this record says what they mean.

A result record carries the same four, copied from the fixture rather than
restated by whoever wrote the result. Copied, because a restated value is a value
that can drift, and the whole purpose of the fields is to make two results
comparable years apart.

An adapter declares which editions it claims, through the capability mechanism in
record 0006. Where an adapter's declared edition does not match a fixture's, the
verdict is `unsupported`. It is never a disagreement, and the report must not
render it as one. An implementation that never claimed the 2025 edition is not
wrong about the 2025 edition.

### The no-edit rule

When a standard is revised, the existing fixtures are not updated in place. A new
fixture set is added for the new edition, with new identifiers, and the old set
stays where it is.

Editing in place destroys the ability to reproduce a result that was published
against the old edition, and that reproducibility is the whole basis on which
anyone would cite this suite. It also silently rewrites history for every
operator who pulls: their next run compares against different numbers than their
last one did, with nothing in the output saying so.

### The correction exception

The narrow exception is a fixture that was simply wrong. A transcription error in
an expected value, a mistake in a signal recipe, a tolerance entered against the
wrong unit. Those are corrected in place, because leaving a known-wrong fixture
in the set to preserve a principle serves nobody.

A correction increments the fixture's `revision`, which is an integer starting at
1, and appends an entry to the fixture's `corrections` list. The identity in `id`
does not change; a correction is the same fixture stating a different number, not
a different fixture.

A correction entry states four things: what the value was, what it now is, how
the error was found, and the date. All four, because a correction with no account
of how it was found is indistinguishable from a correction made to get a run
green, and this project cannot afford that ambiguity in the one file class its
credibility rests on.

A result record names the `id` and the `revision` it ran against. Without the
revision, two results against the same identifier are not comparable and nothing
in either of them says so.

### An obsolete edition

An edition eventually stops being the question anyone is asking. A fixture set
for such an edition is marked with `lifecycle` set to `obsolete`, carrying the
date it was marked and a sentence saying why, and it stops being part of the
default run. It is included by an explicit flag for anyone reproducing an older
result.

It is not deleted. A deleted fixture makes every result that cited it
unverifiable, and the disk cost of keeping a JSON file is not a reason worth
weighing against that.

## Alternatives

A single fixture per metric, updated to the current edition as standards move.
Rejected because it makes every published result unreproducible the moment a
standard is revised, and because it silently changes what an operator's run means
between two pulls.

Recording the edition only in the result record, not in the fixture. Rejected
because the fixture is where the expected value lives, and a value whose source
edition is stated somewhere else is a value that will eventually be paired with
the wrong edition.

Treating an edition mismatch as a disagreement and letting the reader work it
out. Rejected because the reader is often a maintainer of the implementation
being reported on, and handing them a false finding to sort out is exactly the
way this project loses the access it needs.

Deleting obsolete fixtures to keep the set small. Rejected because the set only
growing is a cost this project can pay and unverifiable published results is not.

## Consequences

The fixture set only grows. It never shrinks and it never shifts under a reader.
That is a maintenance cost in review time and in run time, and it is the cost
this decision chooses.

A fixture identifier scheme has to carry the edition, or the set becomes
unreadable once two editions of one standard are present. What that scheme is
belongs to the fixture issues in milestone 3; this record only requires that two
editions of one metric never collide.

The report has to distinguish three outcomes rather than two: agreement,
disagreement, and not applicable because the editions differ. A report that
renders the third as either of the first two is a defect, and it is the specific
defect this record exists to prevent.

## Status

Accepted, 2026-08-07.
