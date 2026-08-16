# 0005. Reference signals are generated, never shipped

## Decision

No audio file is committed to this repository. A fixture describes its stimulus
as a recipe, the harness generates the samples when a run needs them, and a
committed checksum proves the samples that were generated are the samples the
fixture meant.

## Context

This is the decision the whole project's legal position rests on, so it is
recorded before any audio file exists anywhere near the tree.

The forcing constraint comes from outside the project. The reference signals an
implementation is supposed to be validated against are part of the standards
themselves. ISO 532-1:2017 carries a normative annex whose test signals and
result tables are supplied electronically with the purchased standard, as audio
and spreadsheet files licensed to the purchaser. Committing them here would be
redistribution, and no amount of good intent about open science changes what that
is. A project whose entire purpose is to be a trustworthy common reference cannot
begin by infringing, and the first serious user of it will be an organisation
whose legal department reads the repository before its engineers do.

Generation is not merely the legally safe option. It is the better engineering,
and it would be the choice here even if every signal were free to redistribute.

A committed audio file is opaque to review. A reviewer sees a binary blob arrive
or change and can do nothing except take the author's word for what is inside it.
A generated signal is reviewed as a recipe, and the recipe is a dozen lines of
arithmetic that a person can check against the clause it claims to implement.
Errors in stimulus generation are a known way for a conformance suite to be
quietly wrong about everything at once, because every fixture built on the bad
generator agrees with every other, and a recipe is the only form in which that
error is findable before it has done its damage.

### The checksum, and what happens when it does not match

The recipe alone is not enough. The same recipe evaluated by a different version
of a numeric library, on a different platform, can produce different bytes, and a
difference of that kind is invisible in the fixture and visible in the result.

Each fixture therefore carries a checksum of the samples its recipe produces,
committed alongside it. Before a stimulus is handed to any adapter, the harness
generates it, hashes it and compares. On a mismatch the run stops for that
fixture and says what it expected, what it got, and that the two differ. It does
not warn and continue, and it does not use the samples it generated.

Continuing would destroy the measurement, not degrade it. A disagreement
between two implementations and a disagreement between two machines look
identical in the output, and the second one masquerading as the first is a
finding published against somebody's software for a reason that has nothing to do
with their software. Stopping is loud, and it should be: a moved checksum means
either that the generator changed, which is a thing to review, or that the
environment changed, which is a thing to record.

Issue #25 is where the checksums and the manifest are built, and the two-way
correspondence between fixtures and manifest entries is asserted by the
conformance tests in issue #52, so neither can drift from the other unnoticed.

### The licensed-reference slot

An operator who owns the standards should be able to run this suite against the
real material, and the design has to allow that without the material ever
touching this tree.

A fixture may declare a slot for a licensed reference: a file name, a checksum,
and a note naming the standard, edition and clause the file comes from. None of
those three is the file. The operator places the file in a directory they
configure, outside the repository, and the harness looks for it there by name,
verifies it against the declared checksum, and uses it as the stimulus if it
matches.

If the file is absent, the fixture reports itself as not run, with the reason
that a licensed reference was not available, and the run says so in its summary.
If the file is present and its checksum does not match, that is a refusal and not
than a not-run, because a file under the expected name with unexpected contents
is a stronger statement than an absent one.

What never happens is a silent fall back to a generated approximation. A run that
quietly substituted a different stimulus would be worse than one that skipped:
the skip is visible in the report and produces no number, while the substitution
produces a number that looks like every other number and answers a different
question.

### No audio file is tracked here

Plainly, and without qualification: this repository tracks no audio file, and it
never will while this record stands. Not a fixture signal, not an example, not a
short clip in a test, and not one in documentation.

`tools/refuse_tracked_audio.py` is the check. It reads the tracked tree, refuses
a path by extension and independently by leading bytes so that a renamed file is
caught as well as a named one, and exits non-zero on anything that stops it
completing, and never reports a clean tree it did not manage to read. Issue
#19 is where it was built and issue #17 is where it becomes a check that runs on
a pull request. Until #17 lands, nothing runs it automatically, and
`docs/quality-gates.md` is the authority for that.

## Alternatives

Commit the standards' own signal files. Rejected because it is redistribution of
licensed material. This is not a risk to be weighed against convenience; it is
the thing that would end the project.

Commit generated signal files, produced once and checked in as bytes, so that
every run uses identical samples with no generator involved. Rejected because it
gives up the reviewability that is half the reason for this decision, and because
it makes the fixture set large and its history larger. It also moves the
reproducibility problem instead of solving it: the bytes are reproducible and
the recipe that produced them is not recorded in a form anyone can check.

Distribute generated signals as a release artefact, downloaded on first run.
Rejected because it requires an outbound network connection, which record 0011
forbids for the harness, and because it makes a run depend on a server being up
in three years' time.

Skip the checksums and trust the generator. Rejected because the whole claim of
this project is that a disagreement is attributable, and without a checksum a
disagreement cannot be attributed to the implementations rather than to the
stimulus. The cost of the checksum is one hash per fixture per run.

Fall back to a generated approximation when a licensed reference is absent, and
mark the result as approximate. Rejected because the marking is not what a reader
sees when they read the number, and because the fixture's expected value came
from the licensed material in the first place, so the comparison it would be
making is not the one anybody asked for.

## Consequences

Every stimulus is only as reproducible as the library that generates it, so the
numeric behaviour of that library becomes part of the reference. The checksums
make a change in it visible as a stopped run and not as a shifted result,
which is the trade this record accepts: the suite will sometimes refuse to run on
a machine where it previously ran, and that refusal is the mechanism working.

Noise is the hard case and it gets its own attention in issue #22. A pseudorandom
sequence depends on an algorithm, a seed and a library version, none of which is
visible in the output, so the seed and the generator algorithm are explicit
fields of the signal description and never defaults.

The fixture set cannot carry a real-world recording, because a recording cannot
be generated from a recipe. That is a real limit on what this suite can test.
Anything of that kind is operator material, supplied on the operator's machine
under record 0011, and it is not part of the fixture set.

An operator with no licensed reference gets a smaller run than one who has it,
and the difference is visible in the report rather than hidden in it. Record 0009
requires the not-run section to be present always, with a reason per entry, so a
run missing half its fixtures cannot read as a clean sheet.

## Status

Accepted, 2026-08-08.
