# Adding a fixture

A fixture is one JSON file. It says what signal to produce, what quantity to
compute from it, what answer is expected, how far a result may be from that
answer and still count as agreeing, and where the expectation came from.

This walks through writing one. `docs/fixtures.md` is the reference for the
format and the schema at `src/eichstelle/schema/fixture-1.schema.json` is the
authority; this document is about the judgement calls the schema cannot make for
you, and there are three of them. The tolerance. The provenance. And whether the
number you are about to write is yours to write down at all.

## The worked example

    docs/examples/tone-at-forty-decibels.json

That file is in this tree and the test suite runs against it, so it cannot drift
from what actually works. `tests/unit/test_worked_examples.py` validates it,
parses its signal description with the generator and renders it to samples.
Delete a field from it and two of those three tests fail.

Read it beside this document. Everything below refers to it.

## The fields, and what a reader does with each

`id` is what a published result names. It never changes once the fixture has
landed, because a citation that resolves to a different stimulus a year later is
worse than no citation. Choose something a person can read: the example is
`example-tone-at-forty-decibels`, not a hash.

`revision` starts at 1 and moves only when the fixture is corrected. A result
record carries the revision it ran against, so two results are comparable only if
both the identifier and the revision match. Record 0008 owns when a correction is
allowed at all.

`schema_version` is which version of the fixture format the file speaks. It is an
integer and the validator picks a schema by it. Write 1.

`title` is one line, written for somebody reading a failure rather than for
somebody browsing the set. "a 1 kHz sinusoid at 40 dB SPL" tells a reader looking
at a red line what was in front of the implementation.

`signal` describes the stimulus completely enough to regenerate it. No audio is
committed here, so the description is the stimulus: whatever it does not say is
not reproducible. The parameter set is closed per kind, so a name the generator
does not accept is refused rather than silently ignored. `docs/calibration.md` is
what the levels in it mean.

`metric` and `metric_parameters` are the quantity and the arguments it takes.
The parameter names are lowercase with underscores. What belongs in there differs
per metric and per edition, and the example carries `field_condition` because
free field and diffuse field give different answers and implementations differ in
which they assume.

`expected` and `unit`. The value asserted, as a decimal string, and what it is
in. A string rather than a JSON number because a JSON number is an IEEE 754
double in every parser this format will meet, and this project's whole output is
a comparison against a tolerance. A number with no unit is a number the reader
supplies a unit for by guessing, so both are required.

`tolerance` and `tolerance_kind`. The half-width of the band, and whether it is
absolute, relative or a percentage. The next section is entirely about choosing
it.

`standard` pins the expectation to a document: designation, part, edition year
and clause. The edition is exactly the thing that moves under a value, which is
why it is required and why a fixture without it is refused.

`provenance` says where the expected value came from. Four values, and they are
not interchangeable. The section after next is about which one you may write.

## Choosing a tolerance, and justifying it

This is where a well-meaning contributor does the most damage, and the damage is
invisible. A tolerance chosen so that the fixture passes is a fixture that
measures nothing, and it passes forever, including when the implementation breaks.

The rule is that the tolerance follows from the physics, the format or the
arithmetic, and never from a result you have in front of you. Concretely: you
must be able to write the justification without naming any number any
implementation produced.

Justifications that hold, and each says what the band is made of.

The definition is exact and the only spread is numerical. An anchor value like
one sone at the reference tone is exact by definition, so the band covers
floating-point accumulation and resampling, and it is tight. A per-cent band on
an anchor is a strong statement, and it should be: an implementation that misses
its own scale's anchor by more than a few per cent is telling you something.

The quantity is defined only to a stated precision. Where the source states a
value to three significant figures, the band cannot be tighter than the last
digit, and the justification says so and quotes the precision.

The stimulus itself has a spread. A band-limited noise made with a realisable
filter has passband ripple, and the level it actually achieves varies with the
filter. Where the fixture's own signal has a spread, the tolerance carries it,
and the justification states the mechanism rather than the size.

The comparison is between implementations rather than against a target. The band
is what counts as agreement for this metric at this level, argued from the
metric, and the justification says what a spread that size would mean.

Justifications that do not hold, and a reviewer refusing a fixture can point at
this paragraph.

"This is what the implementations produce." That is the fixture being fitted to
the result. If the implementations agree, that agreement is the finding, and it
belongs in the pull request body as evidence rather than in the tolerance as a
band.

"A tighter value failed." That is the same thing, arrived at by iteration. A
tolerance widened until a run went green records the run and not the metric.

"It seemed reasonable." Not a justification, and it cannot be reviewed. If the
band is a judgement, the judgement has a reason and the reason is what goes in
the body.

No number at all. A pull request adding a fixture and saying nothing about its
tolerance has left out the part that a reviewer has to check.

Two smaller rules. A tolerance of zero or less is refused by the validator, as
either a slip or a claim of bit-exact agreement that no floating-point
implementation of a psychoacoustic model can meet. And the kind matters as much
as the number: `0.05` absolute on a value of one sone is five per cent, and the
same `0.05` as `relative` is five per cent of whatever the value happens to be,
which are different assertions on a sweep.

## Provenance, and the evidence each kind needs

`generated-by-definition`. The value follows from the definition of the signal
and the metric, with no document and no measurement behind it. One sone is the
loudness of the reference tone because that is what a sone is. The evidence is
the definition itself, stated in the pull request body. A failure here is
unambiguous, which is what makes these the most valuable fixtures in the set.

`published-paper`. The value comes from a paper. The evidence is the citation, in
the fixture and in the body, precise enough to find the number: author, title,
year, and where in it. A failure means a disagreement with published literature,
which is weaker than a normative target because the paper may itself describe one
implementation.

`implementation-consensus`. The value is what several independent implementations
agree on. The evidence is the run that established it, with the implementations
and their versions named, in the body. Read a failure under this as saying the
implementation under test is an outlier among its peers and nothing more. It is
not a claim that the outlier is wrong, and a report must not present it as one.
Independence matters here: two implementations sharing a lineage agreeing is
weaker evidence than the same agreement between two that do not.

`standard-clause`. Not a provenance any fixture here declares. Record 0004
listed it as a value transcribed from a document the maintainer holds a copy of,
and record 0012 supersedes that list for the reason the next section gives. The
value is still in the schema, because a published schema version is not edited,
and it is the one value the validator will accept and a reviewer will not.

## The value you may not write down

Do not transcribe an expected value out of a standard you bought. Not into a
fixture, not into a test, not into a comment, and not into a pull request body.

The reason is not caution. The standards are sold, their tables are the seller's,
and a fixture carrying a number lifted from one cannot be redistributed, which
means the fixture set stops being something anybody may copy. `CONTRIBUTING.md`
states this as one of four things this project will not accept.

This is not a gap in the design. Issue #31 is the slot that exists for exactly
this case: an operator who owns a standard supplies its values locally, against a
checksum, and nothing of the kind is tracked here. If the number you want is in a
document you paid for, that is where it goes, and the fixture you contribute here
carries a different provenance or waits.

The same applies to the reference audio supplied with a standard. No audio file
is committed to this tree at all, `tools/refuse_tracked_audio.py` refuses one,
and the signals are generated from their descriptions for this reason among
others.

## Writing it, and checking it

Copy the worked example, change what differs, and record what its signal renders
to:

    python -m eichstelle.fixtures --write-checksums fixtures/
    python -m eichstelle.fixtures fixtures/

The first command adds your fixture's line to `fixtures/checksums.txt` and
prints what moved. The second is the check: it validates against the schema and
then regenerates every signal and holds it against those recorded hashes. Exit 0
is every file read, every fixture valid and every stimulus where it was; exit 1
is at least one refusal or at least one stimulus that moved; exit 2 is a run
that did not complete. It reports everything it finds in one pass rather than
stopping at the first problem, so a first fixture gets one list rather than five
iterations.

A fixture with no line in the manifest does not pass the check. That is the
point of the file rather than an inconvenience: what an adapter is handed is the
bytes some code produced from your description, and until a hash of them is
committed nothing holds them still.

The second command runs as the `fixtures` check on a pull request, over the
tracked files. `docs/fixtures.md` lists every refusal, says exactly what the
hash covers and what it excludes, and describes the way a fixture set goes
quietly wrong without either half.

## What the pull request body has to carry

The tolerance and its justification, in the form the section above asks for.

The provenance evidence for the kind you declared.

The validator's output on the fixture you are adding.

If your fixture is one of a family, say what the family is for and what the next
members would be, because a sweep with one member in it is hard to review on its
own.
