# 0007. The verdict vocabulary and the tolerance model

## Decision

A run produces exactly one of six verdicts for each fixture and adapter pair, and
those verdicts are never collapsed into one another; the number a comparison is
made against is declared by the fixture itself, because this project has no
default tolerance and the schema refuses a fixture that omits one.

## Context

Two rules, in one record because each is useless without the other. A verdict
vocabulary with no stated tolerance is a set of words attached to nothing, and a
tolerance model with no vocabulary has nowhere to put its answer.

### There is no default tolerance

Every fixture declares its own, and the fixture schema requires the field. A
fixture arriving without one is refused before any code reads it, which is the
behaviour record 0004 chose a schema for.

A global default is the mechanism by which a conformance suite silently converts
disagreement into agreement. Somebody picks a number that works for loudness,
because loudness is the first metric anyone implements. Three years later a
roughness fixture inherits it, and roughness is a metric where published work
describes the standard's instructions as open to interpretation, so the inherited
band is wide enough to admit every reading at once. Every fixture passes. Nothing
in the output says why.

The standards state their own tolerances, and they differ by metric, by level
range and by signal type. A tolerance that is not attached to the fixture it
applies to is a guess wearing a number, and it is a guess a reader has no way to
audit because it is not written next to the thing it governs.

### What a tolerance says

A tolerance declares its kind as well as its size, and the pair is what the
comparison uses.

`absolute` is a band in the metric's own unit. A result agrees when it lies
within that many sone, acum, asper or vacil of the expected value.

`relative` is a band expressed as a fraction of the expected value, so the band
widens with the quantity being measured. Loudness across a level sweep is the
ordinary case: the same fractional agreement means the same thing at 0.5 sone and
at 50 sone, and the same absolute band does not.

`combined` is a relative bound above a stated floor and an absolute bound below
it, and it exists because the first two do not cover the bottom of a scale.
Loudness near the bottom in sone is the case that forces it. A five per cent
relative bound on 0.02 sone is a band of one thousandth of a sone, which is a
bound no implementation can meet and none needs to meet, because at that level
nobody is claiming three significant figures. A `combined` tolerance says: use
the fraction where the quantity is large enough for a fraction to mean something,
and use a fixed band below that. It carries three numbers and not one, and
the floor is stated in the fixture like everything else.

A tolerance is never zero and never negative. Zero is a claim of bit-exact
agreement between two independent floating-point implementations, which is not a
claim anybody means to make, and negative is a typing mistake. Both are refused
rather than interpreted.

### A time series is compared against a stated target

A metric that answers with a value against time is not compared point against
point unless the fixture asks for that. What is compared is declared by the
fixture, because what should be compared is part of what the standard asks for
and it varies between metrics and between editions.

The forms a fixture may declare are a percentile of the series, its maximum, its
mean, or the series itself point by point with a per-point tolerance and a stated
fraction of points permitted to exceed it. Anything else is a fixture asking for
something the comparator does not do, and it is refused and never approximated.

A percentile is not one operation. Several interpolation conventions exist and
two implementations using different ones will differ for a reason that has
nothing to do with loudness, so the convention is part of the declaration and not
a property of whichever library the comparator happens to use. Issue #28 is where
the first fixture family of this kind lands and where the convention is settled
in writing.

### The six verdicts

Exactly one per fixture and adapter pair, and they are not collapsible.

`agrees`. The result was produced and lies within the fixture's tolerance.

`disagrees`. The result was produced and lies outside the fixture's tolerance.
This is the finding the project exists to produce, and it is deliberately not
called a failure, because the fixture may be the thing that is wrong.

`unsupported`. The adapter declared that it does not implement this metric, or
does not implement it at this standard edition, and declined. It is not a
criticism of anything and it is not evidence about the implementation's quality.

`errored`. The adapter was invoked and did not produce a usable result. The
adapter's own `error` status, a non-zero exit, an empty result file and a result
that fails its own schema all land here, and the record carries which of them it
was.

`timed_out`. The adapter ran past the limit it was given and was terminated. It
is recorded separately from `errored` because a timeout is a statement about the
environment as much as about the code, and a machine under load produces them
where an idle one does not.

`not_run`. The pair was never attempted, and the record says why: a licensed
reference was absent, the adapter was not installed, the adapter did not claim
the metric before any fixture ran, or the operator asked for a subset.

### How this meets the adapter contract

An adapter writes one of three statuses, `ok`, `unsupported` and `error`, and
`docs/adapter-contract.md` is where that is specified. The verdicts are the
harness's, not the adapter's, and the mapping is deliberate.

`ok` becomes `agrees` or `disagrees` depending on the comparison, which is a
decision the adapter has no part in and no way to influence. `unsupported`
becomes `unsupported`. `error` becomes `errored`, and so do the three outcomes
the adapter cannot report because in each of them there is no statement of the
adapter's worth trusting: exiting non-zero without a result, exiting cleanly
having written nothing, and writing something that does not validate. A timeout
is the harness's own observation and no adapter can claim it.

That is the reason the two vocabularies are not the same words. An adapter
reporting its own verdict would be reporting on its own conformance.

## Alternatives

A default tolerance with per-fixture overrides. Rejected for the reason the
context gives: the default is what gets used, the override is what gets
forgotten, and a fixture that silently inherited a band from somewhere else
cannot be reviewed by reading it.

Tolerances derived from the standard's stated values by the harness and not
written in the fixture. Rejected because it would put a reading of the standard
into this repository, which record 0003 forbids, and because the standards state
tolerances in prose that does not reduce to a table.

A single verdict pair, pass and fail. Rejected because it is the collapse this
whole record exists to prevent. An implementation that declined a metric, one
that crashed, and one that answered wrongly would then be reported identically,
and the first of those is not a finding about the implementation at all.

Folding `timed_out` into `errored`. Rejected because a timeout is the one outcome
that is routinely the fault of the machine and not the software, and a reader
looking at a scheduled run needs to tell a slow runner from a broken adapter
without opening the log.

Folding `not_run` into a simple absence, with the pair left out of the record
entirely. Rejected because absence is unreadable. A pair missing from the record
and a pair that was never possible look the same, and a fixture that quietly
stopped running is exactly the kind of thing that goes unnoticed for a year.

A numeric score per fixture instead of a verdict. Rejected because it invites
aggregation into a single figure of merit per implementation, and a league table
is the thing this project must not produce. The margin is recorded, in record
0009, as a number beside the verdict and never instead of it.

## Consequences

A partial run is reported as partial. Record 0009 requires the not-run section to
be present in every report, empty or not, with a reason per entry, and requires
the possible, attempted and produced counts to be stated separately rather than
collapsed into one. Issue #42 is where that becomes a test: a record containing
one entry of every verdict kind, rendered, with an assertion that each one
appears. Until that test exists this paragraph is prose, and the renderer it
describes is not written.

The tolerance vocabulary in this record is wider than the fixture schema
currently accepts. The published schema takes `absolute`, `relative` and
`percent`, and record 0004's summary of the fields names those three. `combined`
is not among them, and neither record 0004 nor the published schema version is
edited to add it: a landed record is not rewritten, and record 0004 states that a
published schema version is never edited either. Carrying `combined` is therefore
a new fixture schema version and a migration, argued on the fixture schema issue
and not here. Until that lands, a fixture needing the combined form cannot be
written, and the anchor fixtures in issue #26 do not need it.

Six verdicts is more than a reader wants and fewer than the outcomes that exist.
The record from issue #41 carries the detail underneath each one, so that
`errored` can be told apart into its four causes by someone who needs to, without
putting four columns in front of someone who does not.

Every report and every summary in this project has to carry all six categories
including the ones with a count of zero. A category that disappears when empty
teaches a reader to stop looking for it, and its reappearance then goes
unnoticed.

## Status

Accepted, 2026-08-08.
