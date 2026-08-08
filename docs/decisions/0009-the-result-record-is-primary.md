# 0009. The machine-readable result record is the primary output

## Decision

The output of a run is a machine-readable record, written as newline-delimited
JSON with a run header on its first line and one entry per fixture and adapter
pair after it, and everything a person reads is rendered from that file rather
than written by hand.

## Context

The reason is what the project is for. A conformance result that cannot be
diffed against last week's, filtered by metric, aggregated across
implementations or cited in a paper is a screenshot. Every use this project is
built for is a use by a program: comparing two runs, watching a scheduled run for
a moved verdict, collecting results from several operators, or reproducing
somebody's published finding.

The moment a summary is hand-written it starts drifting from the numbers it
describes, and the drift is invisible because the summary is the only thing
anybody reads. That failure does not require carelessness. It requires only that
the numbers change after the sentence was written, which they do.

### The format

Newline-delimited JSON. One JSON object per line, the first line the run header
and every line after it one entry.

JSON because record 0004 already chose it for fixtures and for the same reason:
it parses in the standard library of every language this project's readers use,
MATLAB included, with no dependency and no ambiguity about types. A project with
two serialisation formats has two parsers to test and two sets of edge cases, and
there is nothing here the second one would buy.

Newline-delimited rather than one enclosing array because the file is written as
the run proceeds. A run that is interrupted, killed or crashes leaves a file
whose every complete line is readable, which is exactly the run whose partial
results are most worth having. A single enclosing array is unreadable until its
closing bracket arrives, so an interrupted run leaves nothing. It also means a
long run never has to be held in memory, by the writer or by a reader.

The record is append-safe in that sense and in one more: appending an entry never
requires rewriting a byte that is already on disk, so nothing can be corrupted by
a second writer arriving late.

Physical quantities are decimal strings, for the reason record 0004 gives. A
record whose entire content is a comparison against a tolerance may not have its
numbers rounded on the way through a parser. Counts, years and sample rates stay
JSON numbers because they are exact integers.

### What an entry carries

One entry per fixture and adapter pair, and every one of these fields is present
on every entry.

The fixture identity and its revision, so a finding names something citable and
so a fixture corrected later cannot be confused with the fixture as it was.

The standard designation, the part and the edition the fixture applies under.

The adapter identity, and the upstream version the adapter actually loaded rather
than the version it declared. Issue #38 is where the difference between those two
becomes a stopped run; the record carries the loaded one because that is the one
the result is attributable to.

The verdict, one of the six in record 0007.

The value produced and the value expected, each with its unit, and the tolerance
that was applied with its kind. A reader recomputing the comparison from the
record must not need the fixture file to do it.

The margin, meaning how far inside or outside the tolerance the result landed. A
result that agrees by a hair and one that agrees comfortably are different
observations, and issue #44 exists to watch the first turn into the second.

The wall-clock duration of the invocation.

Where the verdict is `not_run`, `unsupported`, `errored` or `timed_out`, the
reason, in a field that is always present and says which of the causes it was.
Record 0007 folds four distinct adapter outcomes into `errored`, and this is
where they are told apart again.

### What the header carries

One object, the first line of the file.

The record format version, an integer. When it started, as a timestamp with an
offset. The harness version. The fixture set version and the checksum of the
fixture set. The platform, the operating system and its version, the processor
architecture, and the interpreter version.

The platform fields are not padding. This project's central claim is that a
disagreement is attributable, and the first question anybody will ask about a
reported disagreement is whether it reproduces elsewhere. A record that does not
say what it ran on cannot answer that, and a reader who has to ask the author is
reading a screenshot again.

The header also carries the counts the report is not allowed to collapse: how
many fixture and adapter pairs were possible, how many were attempted, and how
many produced a verdict.

### Compatibility

The header carries a format version, and readers ignore fields they do not know.

Those two sentences are one rule and it runs in both directions. Adding a field
does not move the version, because a reader written against the older format
ignores it and continues to be correct about everything else. Removing a field,
renaming one, or changing what a value means does move the version, because a
reader that does not notice would be silently wrong rather than silently
incomplete.

Within one major version of the harness the format does not change in a way that
breaks a reader written against an earlier release in that line. Across a major
version it may, and the version field is how a reader finds out rather than
discovering it by misreading a number.

A reader that refuses an unknown field is refusing a record produced by a newer
harness against the same fixtures, which is precisely the record that is most
worth reading, so refusing is not the cautious choice it looks like.

### The human report is rendered

The report a person reads is generated from the record by code, and no part of it
is written by hand at run time. It states the counts by verdict, including the
categories with a count of zero. It lists every disagreement individually with
enough to reproduce it. It states what was not run and why.

The not-run section is present even when it is empty, and it says so in words. A
section that disappears when empty teaches a reader to stop looking for it, and
then its return goes unnoticed. A reader who has learned to check it should never
have to wonder whether it was omitted or was genuinely empty.

## Alternatives

A human-readable report as the primary output, with a machine-readable export
alongside. Rejected because the export is then the thing that lags. Whichever
artefact the code writes first is the one that is correct, and the other one is a
best effort, so the choice is which of the two readers is served properly.

CSV. Rejected because an entry is not flat. Tolerances have kinds, values may be
a series, and reasons are structured, so a CSV either loses that or encodes it
inside cells, which is JSON with a worse parser.

A single enclosing JSON array, or one JSON object for the whole run. Rejected
because an interrupted run leaves nothing readable, and because a long run has to
be held in memory to be written.

SQLite. Genuinely attractive: it is queryable, it is a single file, and it is
readable everywhere. Rejected because a result that cannot be read in a pull
request diff, attached to an issue, or opened in a text editor on a machine
somebody is debugging on loses more than the query language gains. Loading these
records into a database is a few lines for whoever wants one, and the reverse is
not.

Parquet or another columnar format. Rejected for the same reason, more strongly,
and because it adds a dependency to anybody who wants to read a result.

Writing no record at all for a pair that was not run. Rejected in record 0007 and
again here: absence is not a statement, and the whole point of the not-run
category is that it is one.

## Consequences

The report generator becomes a piece of code with a correctness problem of its
own, and the specific failure it must not have is dropping a category. A
renderer that omits an empty verdict class, or a not-run section, or the
distinction between attempted and possible, defeats this decision while appearing
to implement it. Issue #42 owes the test that constructs a record with one entry
of every verdict kind and asserts each one appears in the output, and that test
is the reason the issue exists rather than a detail of it.

Nothing described here is built. There is no record writer, no reader and no
renderer today, and this record is a specification for issues #41 and #42 rather
than a description of the tree. Read it as prose until those land.

The record can contain fragments of what it processed, including file paths.
Record 0011 governs that, and its identifier-instead-of-path default applies to
this file before it applies to anything rendered from it.

The format is a public interface from its first release. An operator's stored
records and a published finding both cite it, so changing it costs a version
number and a migration, and the append-only shape means an old record is never
rewritten into the new format in place.

## Status

Accepted, 2026-08-08.
