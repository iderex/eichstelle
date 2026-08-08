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

A pull request runs it too, as the `fixtures` check in
`.github/workflows/verify.yml`, over the tracked files rather than over the
working tree. The command there is the one above, character for character, so a
green run here is what a green check there means.

What that check asserts today is nothing, and it prints so rather than reporting
green in silence. No fixture is tracked yet, so the job takes its empty branch,
says it validated none, and warns that it made no assertion about correctness.
The moment one fixture is tracked the validator runs and its exit code is the
job's. `docs/ci-checks.md` is where the check is described alongside the others.

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

The schema carries a closed parameter set per kind. Five kinds are defined:
`sinusoid`, `amplitude_modulated_sinusoid`, `frequency_modulated_sinusoid`,
`noise` and `band_limited_noise`. All of them are held to what
`docs/calibration.md` fixes: the calibration reference is a required field with
no default, and a modulated description states which level reading it means,
because at full depth the two differ by 1.76 dB in the same direction on exactly
the fixtures the roughness and fluctuation strength anchors rest on.

A kind arrives with the generator that produces it and its closed parameter set
beside it. Adding a kind makes no fixture that is valid today invalid, so it does
not raise the schema version.

`fade` is required on every kind and carries a shape and a duration. Which
shapes a generator accepts is the generator's to decide, so the schema checks
that the field is there and says nothing about which shapes are legal.

### The noise kinds, and the stream they are reproducible through

A tone is reproducible because its description determines it. A noise is not.
The samples come from a pseudo-random sequence that depends on an algorithm, a
seed and the version of whatever produced it, and none of the three is visible
in the output. Two runs of one fixture on two machines can produce two different
noises, both looking exactly like noise, and the metric difference that follows
cannot be told from an implementation disagreeing.

So `random_algorithm` and `random_seed` are both required, and a description
missing either is refused rather than defaulted.

The generator this repository implements is `xoshiro256plusplus`, written out in
`src/eichstelle/signals/noise.py` rather than taken from a library. That is the
whole point of naming an algorithm in a fixture: the name has to identify a
sequence somebody can still produce in ten years.

A library default is not acceptable here, and the reason is specific rather than
cautious. The standard library's `random` and a numeric library's default
generator both produce a stream their maintainers may change between releases,
deliberately and legitimately, and a change would move every noise fixture in the
set at once while nothing in any fixture recorded that it had happened. A fixture
would still validate, still name its seed, and produce a different stimulus. The
seed alone does not identify a sequence; a named algorithm this repository
implements does.

The suite pins the first words of the stream for a known seed, so a change to the
generator is a failing test rather than a quiet change to every noise fixture.

### The spectral shape, and the filter

`noise` carries a `spectral_shape`. Two are produced, `white` and `pink`. Pink
is realised as a ladder of first-order sections, and it is an approximation: over
a band from 20 Hz to a fifth of the sample rate it stays within 0.6 dB of an
exact minus three decibels per octave, which the suite measures rather than
claims.

`band_limited_noise` carries `low_edge_hz`, `high_edge_hz`, `filter_type` and
`filter_order`, and all four are required. The filter is part of the stimulus.
A band one critical band wide made with a brick wall and one made with a
realisable filter of stated order are different signals with different metric
values, so a description naming only the edges has not said what it means.

The edges are the half-power points, meaning where the response is 3 dB down,
and the design pre-warps them so they land there rather than near there.

`filter_order` is the order of the family's PROTOTYPE. The low-pass to band-pass
transformation maps each prototype pole to two, so a `filter_order` of 4 is
realised as a band-pass with eight poles whose skirts fall at 24 dB per octave.
A fixture author writing 4 and expecting a fourth-order response would be
describing a different stimulus from the one produced, which is why the factor is
stated here rather than left in the code.

One family is built, `butterworth`, chosen because it is maximally flat in the
pass band, which is what a fixture wants when the band edges are the statement
being made. A brick wall would be a second value rather than a synonym.

### The level of a noise

Stated the same way as for a tone, as a sound pressure level against the same
calibration reference. The generator scales to hit it MEASURED from the samples
it produced rather than computed from theory: a filter has pass band ripple and a
shaping ladder has its own, so the two differ, and the fixture's number has to be
the one a meter would read.

The root mean square over the sustain is the requested level, which is the same
convention the tone generator carries and is why the fade is excluded from the
measurement.

A noise peaks well above its root mean square, so a level a tone carries
comfortably can put a noise outside the range a sample holds. That is refused
rather than clipped, because clipping is broadband energy every metric under test
would see.

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
