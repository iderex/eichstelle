# 0003. This repository implements no acoustics metric

## Decision

No implementation of a psychoacoustic metric exists in this repository, in any
form and for any purpose, and the line that separates what is permitted from what
is not is whether the code has to make a judgement about a standard's meaning.

## Context

The temptation is real and it arrives early. The first time two implementations
disagree, the fastest way to find out which one is wrong is to write a third and
see which side it lands on. That third implementation is where this project ends.

Two reasons, and the second is the harder one.

The first is standing. This suite's authority to say that two projects disagree
comes entirely from having no stake in which of them is right. The moment a
metric lives in this tree, the suite is a fourth implementation that also happens
to own the scoreboard, and every finding it publishes is a finding by an
interested party. No amount of care in how the comparison is written repairs
that, because the objection is not about the care.

The second is subtler and it survives even perfect good faith. A conformance
suite that carries its own implementation will, over time, encode that
implementation's interpretation of the standard into the expected values, because
that interpretation is the one the author has in front of them while writing
them. The disagreements this suite exists to find are precisely disagreements
about interpretation. A suite with a house interpretation cannot see them: the
fixtures agree with the house, the implementations that share the reading pass,
and the ones that read the clause differently are reported as wrong. The result
looks like a working conformance suite and is a machine for confirming one
reading of an ambiguous document.

### Where the line is

The test is whether the code has to make a judgement about what the standard
means. If it does, it does not belong here.

Signal generation is on the permitted side. Producing a one kilohertz sinusoid at
a stated sound pressure level, a band of noise with stated edges and a stated
filter, or a carrier amplitude-modulated at a stated rate and depth involves no
psychoacoustic model and no reading of a clause. It is arithmetic against a
description that the fixture already contains. The generator is stimulus, and
stimulus is not measurement.

Arithmetic on results after the fact is on the permitted side. Extracting a
percentile from a time series, converting between units where the conversion is
defined outside the metric, computing the spread across several implementations'
answers, or aggregating over a set of runs are all operations on numbers other
people produced. None of them needs to know what loudness is.

Computing a loudness is on the forbidden side, and so is everything shaped like
it: a critical-band filterbank, a specific-loudness pattern, a temporal
integration stage, a tonality weighting, a roughness model. Each of those
requires a decision about how a clause is meant, which is the judgement this
record is about.

The awkward cases are the ones worth naming rather than the clear ones. An
A-weighting filter is defined by a table and a formula in a standard about sound
level meters and involves no psychoacoustic model, so it is permitted, and a
fixture that needs one says so. A loudness-to-phon conversion is defined by the
loudness standard itself in terms of the model, so it is not permitted here even
though it looks like unit conversion, and an implementation that reports phon is
the thing that produces it. Where a case is genuinely unclear, the answer is an
issue and not a commit, because the whole value of the rule is that it is not
decided case by case by whoever is in a hurry.

## Alternatives

Write a reference implementation and mark it as non-authoritative. Rejected
because the marking has no force. Once a number exists in this tree, it is the
number a reader compares against, whatever the documentation calls it, and the
expected values will drift towards agreeing with it because that is the path of
least resistance for whoever is writing the next fixture.

Write a metric implementation for test purposes only, kept out of the shipped
package. Rejected for the same reason and one more: a metric used to test the
harness has to be correct, so it acquires its own conformance problem, and the
project now maintains the thing it exists to test. The fake adapter in record
0006 covers what testing actually needs, which is an adapter that behaves in
every way a real one can, and it computes nothing at all.

Vendor an existing open implementation as a fallback for when no adapter is
installed. Rejected because a fallback is the most dangerous form of this
mistake. A run that quietly answered from a vendored copy would report agreement
between the suite and itself, and the report would not distinguish that from a
measurement.

Compute a consensus value from the installed implementations and treat it as the
expected value where no other source exists. Rejected because it is a house
interpretation assembled by vote. Record 0004 already carries
`implementation-consensus` as a provenance kind, which is the honest version of
this: the fixture says that is where its number came from, and a reader knows to
discount it accordingly.

## Consequences

This project can never answer "which one is correct" by itself, and that
limitation has to be stated wherever a result is presented rather than left for a
reader to infer. Where two implementations disagree and no normative target is
available, the finding is a disagreement and nothing more. It is not evidence
about which of them is wrong, and a report that let it read as such would be
making a claim this project has no standing to make.

Where the answer does matter, it comes from a normative reference the operator
holds. Record 0005 describes the slot a fixture declares for a licensed reference
that lives outside this tree, and issue #31 is where that slot is built. An
operator who owns the standard gets an adjudication against the standard's own
material, on their own machine, and this repository never sees the file. Everyone
else gets a disagreement, reported as one.

Milestone 5's differential mode exists because of this record. It is the mode in
which most of the fixture set will run, and record 0007's verdict vocabulary is
built so that a disagreement is never collapsed into a failure by anybody's
implementation.

The suite is weaker than a suite with a reference implementation would appear to
be, and the appearance is the thing being given up. A suite that reported which
implementation was right would be more useful if it were correct, and there is no
way for a reader to tell whether it was.

### The one exception route

If a metric implementation ever becomes necessary, it does not arrive here. It
lives in a separate repository, under its own name, developed as an
implementation rather than as part of a test suite, and it is then a candidate
for an adapter like any other implementation, competing on the same terms and
reported in the same columns.

Taking that route requires a decision record in this repository that supersedes
this one and says what changed, because the route is not a loophole in this
decision. It is the abandonment of it, and it should read that way to whoever
finds it later.

## Status

Accepted, 2026-08-08.
