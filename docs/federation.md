# Federation, and why it is off

Federation means publishing the results of a run so they can be compared with
results other operators produced. This document is the design for it. No part of
it is implemented, and the last section says why that is deliberate and not
late.

## What it is for

A conformance result from one machine is a data point. The same fixture run by
forty operators on forty platforms is evidence about where an implementation is
sensitive to its environment, and nobody has that today. An implementation
maintainer learns that their library answers differently on one architecture. An
operator learns whether the disagreement they are looking at is theirs alone. The
project learns which fixtures discriminate and which ones every implementation
passes, which is the difference between a fixture set that measures something and
one that is long.

That value is real and it is the only reason to accept the risk below.

## The risk this design is built around

This suite processes audio. Decision record 0011 works through why a sound
recording is often personal data in the ordinary legal sense, and why the
operator, and not this project, is answerable for it. A publishing feature that
is easy to turn on and hard to inspect is the mechanism by which such material
leaves a machine without anybody deciding that it should.

So the design goal is not that publishing is safe. It is that publishing by
accident is not reachable. Every rule below exists to remove one route to an
accidental transfer, and each names the route.

## Off by default, and per run

Publication happens only when the operator asks for it on the command line of
that run. There is no configuration file key, no environment variable and no
stored profile that turns it on for later runs.

The route this removes is the stored setting. A preference set once, for one run,
on a machine that later processes different material, is a decision taken by
somebody who is no longer in the room. A per-run request cannot be in that state,
because it does not persist to be in a state at all.

This also means there is no route by which a shared checkout, a copied home
directory or a container image carries publication with it. Somebody who clones a
colleague's setup inherits no consent.

A consequence worth stating, so nobody discovers it instead: a scheduled or scripted run
that wants to publish has to pass the flag every time, which makes the intent
visible in the script and never hidden in a file beside it.

## The operator sees the payload, not a summary of it

Before anything is sent, the full payload is written out for the operator to
read. Not a description of it, not a field count, not a redacted view. The bytes
that would leave the machine are the bytes shown.

The route this removes is the summary that is accurate about what it mentions and
silent about what it does not. A preview that says "12 results, no paths" is a
claim the operator has to trust; a preview that is the payload is a claim they
can check.

This has a design consequence. The payload has to stay small enough that reading
it is realistic, which is the second reason for the minimisation below.

## Nothing derived from operator audio, unless asked for separately

The default payload carries only results computed from generated fixture signals.
Those contain no personal data by construction: there was never a recording,
there was a description in a fixture file in this repository, and the samples
were produced from it on the operator's own machine.

Results computed from operator-supplied material are excluded from the default
payload. Including them is a separate request, made explicitly, in addition to
the request to publish at all, and refusing it still allows the generated-signal
results to go.

The route this removes is the mixed payload. A single switch covering both kinds
means an operator who wants to contribute the safe half has to send the unsafe
half too, and the predictable outcome is that they send it.

Two further points about the operator-derived half, for whoever implements this.
A metric value computed from a recording is derived from personal data, and
derivation is not anonymisation, so the separate consent is about the numbers and
not only about the paths. And the entry that carries such a result identifies its
input by the identifier the operator assigned and never by a filesystem path,
which record 0011 already makes the default for the record itself.

## The payload, field by field

Every field is listed with the reason it is there. A field with no reason is not
added, and that rule is the whole of the minimisation policy. There is no
allowance for a field that is merely useful, or that a later feature might want.

The payload is drawn from the result record described by
`src/eichstelle/schema/result-record-1.schema.json`. It is a subset of it and not
than a new document, so a reader who knows the record knows this too.

### From the run's header

`format_version`. Which record format the payload speaks, so a receiver written
against an older one can tell what it is holding and does not have to guess.

`started_at`. When the run happened, in UTC. Without it a result cannot be placed
against an upstream release, which is most of what a reader wants to know.

`harness_version`. Which version of this suite produced the result. A verdict is
partly a statement about the comparator that made it.

`fixture_set_version` and `fixture_set_checksum`. Which fixtures ran, and the
checksum that pins them to exact bytes. Two results from two operators are
comparable only if these agree, so a receiver that cannot check this cannot
aggregate honestly.

`platform`, `operating_system`, `operating_system_version`, `architecture`,
`interpreter_version`. Environment sensitivity is the thing federation exists to
measure. A result whose environment is unknown contributes nothing to the
question being asked.

`adapters`, each with its identifier and the upstream version actually loaded.
The result is attributable to the implementation version that ran, not to the one
that was requested, and record 0009 is where that distinction is argued.

`possible`. How many fixture and adapter pairs the run could have produced a
verdict for. Without it an aggregate cannot tell a small run from a large run
that mostly failed.

### From each entry

`fixture_id` and `fixture_revision`. What was run. A revision, not an
identifier alone, because a fixture that moved is a different stimulus.

`standard`, `part`, `edition`. What the expectation was taken under. Two
implementations disagreeing across editions is a finding about editions, and a
payload that dropped this would present it as a finding about implementations.

`adapter` and `adapter_upstream_version`. Which implementation answered, echoed
onto the entry so a single line is attributable without holding the header.

`verdict` and `reason`. The outcome and its cause. Both, because the categories
that carry causes are exactly the ones an aggregate would otherwise flatten.

`produced` and `produced_unit`. What the implementation answered. This is the
measurement, and without it the payload reports somebody's conclusion instead of
their data.

`expected`, `expected_unit`, `tolerance`, `tolerance_kind`, `margin`. What the
comparison was made against and how far the result landed inside or outside it.
A receiver recomputing the comparison from the payload needs all five, and one
that cannot recompute it is trusting the sender's arithmetic.

`duration_seconds`. Wall clock for the invocation. It is the field most likely to
be argued about, and it stays because a run that took ten times as long on one
platform is the first sign of a difference nobody has named yet.

`source`. Whether the entry came from a generated stimulus or from operator
material. It is in the payload precisely so that a receiver can refuse anything
that is not generated, rather than relying on the sender having filtered
correctly.

### From the summary

`finished_at`, `possible`, `attempted`, `produced`. The three counts stay
separate, for the reason the record keeps them separate: a run that covered part
of the set must never read as a run that covered it.

### What is not in it, and why

The machine's name, its network name, its domain, and any account or user name.
None of them is needed to answer the question federation asks, and each of them
identifies a person or an organisation.

`source_path`. The filesystem path of operator material. It is off by default
even in the local record, and a path carries a person's name, a site, a project
code or a patient identifier often enough that it is the single field most likely
to turn a result into a disclosure.

`diagnostic`. What an adapter printed. It is arbitrary text from a foreign
program that may quote a filename, a path or a fragment of input, and there is no
reading of it that makes it safe to forward. An aggregate that wants error text
is a later argument that has to be made on its own.

Any absolute path, working directory or temporary directory, for the same reason
as `source_path`.

Anything identifying the operator, unless they later ask to be identified. That
is a feature nobody has asked for and it is not designed here.

## What is a maintainer decision and not an engineering one

Two questions in this are not settled by the design and are not the design's to
settle. Where published results are held, and under what terms a published result
may be reused, cited, redistributed or withdrawn. Both are commitments to other
people, and both are hard to loosen once made.

They are entry 6 on issue #1, which is where decisions of that kind are kept.
Nothing here presumes an answer, and the field list above is deliberately
independent of it: the payload is the same whether it goes to a repository, to a
research archive, or to a file the operator hands somebody.

## Not in the first release

Federation is not implemented for the first release, and the reason is that a
publishing feature built to meet a release date is the one that ships with the
route it did not think of. Every rule above removes a specific route to an
accidental transfer, and each of them costs implementation work that is easy to
trim when a date is close. Trimming any of them produces something that publishes
correctly in the demonstration and wrongly in the case that matters.

The value of federation also depends on there being a fixture set worth
aggregating and more than one implementation running against it. Publishing
before that exists produces a shared collection of nothing much, and it commits
the project to a destination and to terms of reuse before there is any evidence
about what operators would actually want to send.

So this document is the deliverable and the code is not. Somebody implementing it
later has the design and the reasons, and a reason is what stops a rule being
traded away by somebody who does not know what it was for.

## What enforces any of this

Nothing does. There is no publishing code in this tree, so there is nothing to
refuse a violation of these rules, and this document is a design rule rather than
a mechanism. The first thing the implementation owes is a test per rule above,
and the rule that most needs one is the preview: an assertion that the bytes
shown to the operator and the bytes sent are the same bytes, failing when they
are made to differ.

Decision record 0011 is where the position these rules follow from is argued, and
it says the same thing about itself.
