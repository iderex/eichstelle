# Writing a fixture

A fixture is one JSON file. It binds five things into one thing that can be
cited by path: a signal described completely enough to regenerate, the metric to
compute from it, the value expected, the tolerance inside which a result counts
as agreeing, and the standard edition the expectation comes from. Anything
naming fewer than five of those is a note.

The schema is the authority for the shape:

    src/eichstelle/schema/fixture-1.schema.json

It is a file rather than a description of a file, so an implementation maintainer
who wants to run their own code against this fixture set can read it without
installing anything and without reading any Python. Decision record 0004 in
`docs/decisions` is where the format is argued and `docs/calibration.md` is what
the levels in a signal description mean.

There are no fixtures in this tree yet. The first four are issue #26.

## A complete example

```json
{
  "id": "example-tone-at-forty-decibels",
  "revision": 1,
  "schema_version": 1,
  "title": "a 1 kHz sinusoid at 40 dB SPL",
  "signal": {
    "kind": "sinusoid",
    "sample_rate": 48000,
    "channels": 1,
    "duration_seconds": "2.0",
    "parameters": {
      "frequency_hz": "1000.0",
      "level_db_spl": "40.0",
      "calibration_reference_db_spl": "94.0",
      "fade": { "shape": "raised_cosine", "duration_seconds": "0.05" }
    }
  },
  "metric": "loudness",
  "metric_parameters": { "field_condition": "free" },
  "expected": "1.0",
  "unit": "sone",
  "tolerance": "0.05",
  "tolerance_kind": "absolute",
  "standard": {
    "designation": "ISO 532",
    "part": "1",
    "edition_year": 2017,
    "clause": "4.1"
  },
  "provenance": "generated-by-definition"
}
```

That document is the one the tests are built from, and it is an illustration
rather than a fixture: nothing has been run against it and the expected value in
it has not been checked by anything.

## Two things that surprise people

Every physical quantity is a string. A frequency, a level, a duration, a
tolerance, an expected value. JSON numbers are IEEE 754 doubles in every parser
this project will meet, so a tolerance written as `0.1` arrives as
`0.10000000000000000555`, which is a footnote in most projects and a problem in
one whose entire output is a comparison against a tolerance. Counts stay
numbers: `sample_rate`, `channels`, `revision`, `schema_version` and
`edition_year` are exact integers and nothing is lost.

Field names are lowercase with underscores, never hyphens. MATLAB's `jsondecode`
maps object keys onto struct field names and rewrites any key that is not a
valid MATLAB identifier, so a hyphenated key arrives under a different name in
one of the three consumers this format exists for.

## Running the check

    python -m eichstelle.fixtures fixtures/

It takes a directory and walks it for `*.json`, so a new fixture is covered by
having been added rather than by being remembered. Exit 0 is every file read and
valid, exit 1 is at least one refusal, exit 2 is a run that did not complete and
whose result is therefore unknown.

It reports everything it finds in one pass. Somebody writing their first fixture
gets one list rather than five iterations.

Nothing runs it on a pull request. Issue #17 is where it becomes a check name,
and until then a malformed fixture is caught by whoever runs the command.

## What it refuses, and why each one

Each of these is a way a fixture set goes quietly wrong, and none is a tidiness
rule.

A fixture with no `tolerance` cannot be compared against at all, so a run over it
either stops or invents a band nobody chose.

A `tolerance` of zero or less is either a slip or a claim of bit-exact
agreement, which no floating-point implementation of a psychoacoustic model can
meet. This one is not in the schema: JSON Schema's numeric keywords do not apply
to strings, and the quantities here are strings on purpose.

A fixture with no `tolerance_kind` leaves a bare number whose meaning depends on
whether the reader takes it as absolute, relative or a percentage.

A fixture with no `provenance` leaves a reader unable to tell a disagreement
with a normative table from a disagreement with a consensus among
implementations. Record 0004 says how a failure under each of the four values
should be read, and they call for different responses.

A fixture with no `edition_year` under `standard` pins its expectation to
nothing. The edition is exactly what moves under a value.

An `expected` value with no `unit` is a number a reader supplies a unit for by
guessing.

Two fixtures carrying one `id` make a published result ambiguous about what it
was produced against. This is the one refusal that cannot be in the schema,
because no schema sees more than one document at a time.

A `signal.parameters` object naming a parameter no generator accepts is a
fixture written against a feature that was renamed. Without the refusal the
signal is generated with the parameter silently dropped, and the fixture that
results is a different stimulus wearing the same name. The parameter set is
closed per signal kind, which is what makes this refusable at all.

A `signal.kind` no generator produces is refused for the same reason.

## Signal kinds

The schema carries a closed parameter set per kind. Two kinds are defined,
`sinusoid` and `amplitude_modulated_sinusoid`, and both are held to what
`docs/calibration.md` fixes: the calibration reference is a required field with
no default, and a modulated description states which level reading it means,
because at full depth the two differ by 1.76 dB in the same direction on exactly
the fixtures the roughness and fluctuation strength anchors rest on.

Neither generator exists yet. Issue #21 builds the sinusoid, #23 the modulated
one and #22 the noise kinds, and each of those adds its kind to the enum and its
closed parameter set beside it. Adding a kind makes no fixture that is valid
today invalid, so it does not raise the schema version.

`fade` is required on both kinds and carries a shape and a duration. Which
shapes a generator accepts is the generator's to decide, so the schema checks
that the field is there and says nothing about which shapes are legal.

## Versioning

`schema_version` is an integer and the validator selects a schema by it. A
version it does not know is refused rather than downgraded to the newest schema
to hand, because the rules that applied when a result was produced are what
reproduces it.

A published schema version is never edited. The version rises when a change
would make a currently valid fixture invalid, or when a new required field is
added; adding an optional field or a new signal kind does not raise it.

The versions a build carries are read from the packaged schema directory rather
than listed in the code, so publishing version 2 is adding a file.
