# 0004. What a fixture is, and in what format

## Decision

A fixture is a single JSON file, validated against a versioned JSON Schema, that
binds a regenerable signal, a metric, an expected value, a tolerance and a
standard edition into one thing that can be cited by path.

## Context

A fixture binds five things together: a signal, described completely enough to be
regenerated; the metric to compute from it; the value expected; the tolerance
within which a result counts as agreeing; and the standard, part and edition the
expectation comes from. Anything naming fewer than five of those is not a
fixture, it is a note.

Fixtures are read by more than this harness. An implementation maintainer will
want to run their own code against the fixture set without installing this
project, and the implementations in scope live in Python and MATLAB with more
languages likely later. JSON parses in the standard library of every one of them,
MATLAB included, with no dependency and no ambiguity about types.

A schema and not a convention, because a fixture with a missing tolerance
field is the exact shape of mistake that produces a green run proving nothing,
and a schema refuses it before any code reads it.

One fixture per file and not a large catalogue file, because fixtures are
added by different people over time and a single catalogue is a permanent merge
conflict. It also makes a fixture citable by path, which is what a published
result needs in order to name what it was produced against.

### The fields a fixture carries

Every fixture carries all of these. The schema requires each one, and a fixture
missing any of them is refused rather than defaulted.

`id` is a stable identifier that never changes once the fixture has landed. It is
what a result record names and what a published finding cites.

`revision` is an integer starting at 1. It moves only when a fixture is corrected
under the narrow exception in record 0008, and a result record names the revision
it ran against.

`schema_version` is the integer schema version this fixture targets. See below.

`title` is a short human-readable line saying what the fixture is for. It is
written for someone reading a failure, not for a catalogue.

`signal` is an object describing the stimulus completely enough to regenerate it
byte for byte: its kind, its parameters, its duration, its sample rate and its
channel count. Its exact shape per signal kind belongs to the signal issues in
milestone 3 and not to this record.

`metric` names the quantity to compute, and `metric_parameters` carries the
arguments that quantity takes, which differ between metrics and between editions.

`expected` is the value the fixture asserts, and `unit` names what it is in.

`tolerance` states the band inside which a computed result counts as agreeing,
and `tolerance_kind` says whether that band is absolute, relative, or a
percentage of the expected value. A bare number with no kind is the mistake this
field pair exists to make impossible.

`standard` pins the expectation to a document: its designation, its part, its
edition year and the clause or table the value comes from. Record 0008 owns what
those fields mean and what happens when the document is revised.

`provenance` says where the expected value came from, and is one of the four
values below.

### Provenance, and how a failure under each should be read

`generated-by-definition`. The expected value follows from the definition of the
signal and the metric, with no document and no measurement behind it. One sone is
the loudness of the reference tone because that is what a sone is. A failure here
is unambiguous: the implementation is wrong, or this project's signal generation
is, and nothing else is in play.

`standard-clause`. The expected value is transcribed from a named clause or table
of a named edition of a standard the maintainer holds a copy of. A failure means
the implementation disagrees with a normative target, which is the strongest
result this suite can produce. The value is transcribed; the source document is
never redistributed and never enters this tree.

`published-paper`. The expected value comes from a paper, named in the fixture. A
failure means a disagreement with published literature, which is weaker than a
normative target because the paper may itself be describing one implementation.

`implementation-consensus`. The expected value is what several independent
implementations agree on, with no document behind it. A failure means the
implementation under test is an outlier among its peers, and nothing more. It is
explicitly not a claim that the outlier is wrong, and a reader must not treat it
as one.

Provenance is not decoration. Someone reading a failure needs to know whether
they are disagreeing with a normative table or with a consensus, and the two call
for different responses.

### Numbers

Every field carrying a physical quantity is written as a decimal string and not
than a JSON number. That covers `expected`, `tolerance`, and every physical
parameter inside `signal` and `metric_parameters`: a frequency in hertz, a level
in decibels, a duration in seconds, a modulation depth, a modulation rate.

JSON numbers are IEEE 754 doubles in every parser this project will meet. A
tolerance written as `0.1` becomes `0.10000000000000000555` on the way through,
which is a footnote in most projects and a problem in one whose entire output is
a comparison against a tolerance. A decimal string survives every parser
unchanged and is converted deliberately, once, by whoever consumes it.

Counts stay JSON numbers, because they are exact integers and nothing is lost:
`sample_rate` in hertz, `channels`, `revision` and `schema_version`.

### Field names

Field names are lowercase with underscores. No hyphens, and none starts with a
digit. This is not a style preference: MATLAB's `jsondecode` maps object keys onto
struct field names and rewrites any key that is not a valid MATLAB identifier, so
a hyphenated key silently arrives under a different name in one of the three
consumers this format exists for. That is a claim about MATLAB's documented
behaviour and not something this project has measured.

### Schema versioning

Each fixture declares `schema_version` as an integer. The validator selects the
schema by that field and refuses a fixture whose declared version it does not
know, rather than falling back to the newest schema it happens to have.

The version increases when a change would make a currently valid fixture invalid,
or when a new required field is added. Adding an optional field does not increase
it. A schema version, once published, is never edited, for the same reason a
fixture is not: an operator reproducing an old result needs the rules that
applied when it was produced.

## Alternatives

TOML. Reads better than JSON and would be pleasant to write by hand. Rejected
because it has no MATLAB story, and one of the three implementations in scope is
a MATLAB toolbox whose maintainers are exactly the audience this format exists
for.

YAML. Rejected because it has several implementations and they disagree about
what its type system means. Values that a reader would call obviously numeric or
obviously boolean are parsed differently by different libraries, which is not a
property to want in a file whose whole content is numeric tolerances.

A single catalogue file, in any format. Rejected because it is a permanent merge
conflict once fixtures are added by more than one person, and because it removes
the ability to cite one fixture by path.

A binary or columnar format such as HDF5 or Parquet. Rejected because a fixture
whose change cannot be read in a pull request diff cannot be reviewed, and a
corrected expected value that nobody can see arriving is the failure mode this
project can least afford.

Fixtures as Python source, as literals or as a module. Rejected because it closes
the fixture set to every consumer that is not this harness, which defeats the
reason the fixture set exists at all.

## Consequences

Every consumer converts the decimal strings itself before comparing anything.
MATLAB receives them as character arrays and converts with `str2double`; Python
converts with `decimal.Decimal` or `float`, and which of the two is used in the
comparator is the comparator issue's decision and not this one's.

JSON Schema's numeric keywords do not apply to strings, so a bound on a frequency
or a level is expressed as a regular expression on its text rather than as
`minimum` and `maximum`. That is a genuinely weaker constraint and it is the
price of the representation. The validator therefore checks the shape of those
fields and not their range, and any range checking is code the fixture issues own.

The fixture set is directly usable by an implementation maintainer with no
install of this project, which is the point. It also means a fixture's on-disk
shape is a public interface, so a change to it is a schema version and a
migration rather than a commit.

## Status

Accepted, 2026-08-07.

Superseded by 0012, 2026-08-10, on the provenance list only: `standard-clause`
is no longer one of the values, because a value transcribed from a purchased
document cannot be redistributed with the fixture set that carries it, and the
normative comparison moves to the licensed reference in issue #31. Every other
section of this record is in force.
