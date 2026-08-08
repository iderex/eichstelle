# Adding an implementation

This is for somebody who knows their own psychoacoustics library and nothing
about this project. By the end of it you have an adapter: a small program that
lets this suite run your implementation against a set of fixtures and report what
it answered.

You are not asked to change your library, to import anything from here, or to
learn this project's internals. `docs/adapter-contract.md` is the interface and
it is written to be satisfiable without reading any source in this repository.
This document is the walkthrough over it, plus the two things newcomers get
wrong.

## What an adapter is

An executable. The suite writes a JSON job to a file, runs your executable with
the path to that file as its one argument, and reads a JSON result from the path
the job named.

That is the whole boundary. It is a process and two documents, so your language
and your runtime are your business, and nothing of yours is loaded into this
suite or the other way round. Decision record 0006 is where that shape is argued.

The consequence worth knowing before you start: your adapter can be written in
whatever the implementation is written in, and a bare machine with none of the
three toolboxes installed can still exercise everything above the boundary.

## Read this file first

    tools/fake_adapter.py

It is a complete adapter that computes nothing, it depends on nothing outside
the Python standard library, and it is the worked example this document ends at.
`tests/e2e/test_fake_adapter.py` drives it through every behaviour it declares,
so it is kept working by the suite rather than by anybody remembering.

Read it beside `docs/adapter-contract.md`. Between them they answer most of what
follows.

## The five steps

**Answer the capabilities job.** The suite asks once per run what you claim,
before any fixture is invoked. You answer with a list of metrics and, per metric,
the editions you claim. The next section is entirely about getting this right.

**Read the measure job.** It names a fixture, a WAVE file to read, its sample
rate and channel count, the metric, the metric parameters, and the standard,
part and edition the answer is expected against. Every field is required and none
has a default you are expected to know.

**Compute.** Read the stimulus, call your library, take the number out.

**Write the result.** A JSON document at the path the job named, with one of
three statuses. `ok` and the value. `unsupported` if you do not claim this metric
or this edition. `error` if you tried and could not, with a diagnostic saying
why.

**Exit 0 if you wrote a result, whatever its status.** A declined measurement is
a successful invocation. Exit non-zero only when you could not get far enough to
write anything.

The numbers you write are decimal strings rather than JSON numbers, for the
reason the contract gives: a value that is going to be compared against a
tolerance must not be rounded on the way through somebody's parser.

## Declaring what you can do, honestly

This is the part newcomers get wrong, and it is worth a section because the
instinct that produces the mistake is a good one.

The instinct is to declare everything and let the results speak. The outcome is a
wall of errors that reads, to anybody looking at the report, like your library is
broken. It is not broken. It was asked two hundred questions it never claimed to
answer, and every one of those became a red line with your name on it.

Declaring narrowly costs you nothing. A metric you do not claim is reported as
unsupported, which is a statement about coverage rather than about correctness,
and nobody reads it as a defect. Adding a claim later is one line in your
declaration.

Three specific things to be honest about.

The edition. If your library implements the 2017 edition of a standard, claim
2017 and not the edition somebody asked you about last week. Two implementations
computing what they both call roughness under different editions will disagree,
and that disagreement is about editions rather than about either library. A
declaration that names the wrong edition turns a correct answer into a finding
against you.

The metric you nearly implement. A metric your library computes in a variant, or
only for stationary signals, or only in free field, is a metric to claim
carefully rather than broadly. Where the contract has no field fine enough to say
what you mean, say it in an issue here rather than claiming the whole thing; the
missing field is a defect in the contract.

The version. Report the version of the upstream implementation your adapter
actually loaded rather than the one it was pinned to. Those two can differ, and a
result attributed to a version that was not running is not reproducible.

There is a difference the report depends on: an error from a capability you
declared is a stronger finding than one from a capability you did not. Declaring
honestly is what keeps that distinction meaningful.

## The rule that is not negotiable

An adapter contains no correction and no workaround.

Not a scale factor to line your answer up with somebody else's. Not a resampling
step because your library prefers a different rate. Not a level offset because
the calibration convention here is not the one you use internally. Not a special
case for one fixture that fails. Not a retry that returns the second answer.

The reason is the whole point of the project. This suite exists to report where
implementations of the same standard disagree. A correction inside an adapter
removes exactly the disagreement somebody is trying to see, and it removes it
silently: the report shows agreement, the reader concludes the implementations
agree, and the difference is still there in the library. That is worse than no
suite, because it produces confident wrong information instead of none.

The second reason is that a correction is a claim about which side is right. This
project has no house implementation and computes no metric of its own precisely
so that it is not party to any disagreement it reports. An adapter that adjusts a
number has made this project a participant, using code nobody reviewed as an
implementation.

What to do instead, in each of the cases the temptation actually arises.

Your library wants a different sample rate. Say so in your capability
declaration. A pair the suite cannot form is reported as unsupported and costs
nobody anything.

Your calibration convention differs from the fixture's. `docs/calibration.md`
fixes what a level here means. If your library needs to be told a convention,
that is an argument in the metric parameters, and if there is no field for it,
that is an issue here. Adjusting the samples or the answer is not the route.

You believe the fixture is wrong. Quite possibly it is. Say so on the issue that
added the fixture, with your reasoning. A disagreement traced to a fixture is a
result this project wants, and it is one of the listed explanations for a
disagreement in the first place.

Your library errors on one stimulus. Let it error. An `error` status with a
useful diagnostic is a finding. A hidden retry is not.

## Three more prohibitions, and why they are short

You do not write outside the working directory the job gives you, except to the
result path. The stimulus is read-only and is the same file handed to every
adapter in the run, so writing to it turns a disagreement between implementations
into a disagreement about bytes.

You do not open a network connection. This suite is meant to run where there is
no outbound network at all.

You do not require a display.

None of these is enforced by the harness today, and the contract says so in its
own words. They are the contract, and breaking one is a defect in that adapter
rather than something this project catches for you.

## What your pull request carries

The adapter, its own dependency declaration, and an exact pin of the upstream
version it wraps.

What is known about the implementation's lineage: whether it was developed
independently or validated against another implementation, with the source for
whatever you state. Agreement between two implementations that share an ancestor
is not the same measurement as agreement between two that do not, and the suite's
differential mode is only as honest as what it knows about this.

An end-to-end run against the current fixture set, with any disagreements listed
individually rather than counted.

The license of the implementation you wrapped, if it has terms an operator would
need to know about before running it.

## Where to ask

If you had to read this project's source to answer a question about the
interface, the answer is missing from `docs/adapter-contract.md` and that is a
defect worth an issue. The contract is meant to stand on its own.
