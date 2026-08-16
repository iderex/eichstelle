# Writing an adapter

An adapter connects one implementation of a psychoacoustic standard to this
suite. It is an executable. The harness writes a JSON job to a file, runs your
executable with the path to that file as its one argument, and reads a JSON
result from the path the job named.

That is the whole interface. Nothing is imported, no library is loaded into the
harness, and your implementation's language and runtime are your business. This
document is written so you can satisfy the contract without reading any of this
project's source. If you have to read the source to answer a question, the
question belongs in an issue here, because the answer is missing from this file.

This is protocol version 1.

## The invocation

    <your adapter> <path to the job document>

One argument. Your process starts with its working directory set to the
directory the job names in `working_directory`. Nothing is written to your
standard input, and nothing you write to standard output or standard error is
read as a result; use them for logs.

`tools/fake_adapter.py` in this repository is a complete adapter that computes
nothing, and it is worth reading beside this document.

## The job document

An object. Every field is required for the kind of job it belongs to; nothing is
optional and nothing has a default you are expected to know.

| field | type | meaning |
| --- | --- | --- |
| `protocol_version` | integer | Always `1` today. If it is a number you do not implement, refuse rather than guess. |
| `kind` | string | `measure` or `capabilities`. |
| `result_path` | string | Where you write your result. |
| `working_directory` | string | A directory the harness made for this invocation and will delete afterwards. Your process starts in it. |
| `timeout_seconds` | decimal string | The limit the harness will terminate you at. |

A `measure` job also carries:

| field | type | meaning |
| --- | --- | --- |
| `fixture_id` | string | Echo it in your result. |
| `fixture_revision` | integer | Which revision of that fixture this is. |
| `signal_path` | string | An absolute path to the stimulus, a WAVE file. Read-only, outside your working directory, and the same file every adapter in this run is given. |
| `sample_rate` | integer | Hertz. Describes the file at `signal_path`. |
| `channels` | integer | Channel count of that file. |
| `metric` | string | What to compute. Lowercase with underscores. |
| `metric_parameters` | object | The arguments that metric takes. Its keys are lowercase with underscores; what they mean is the metric's business. |
| `standard` | string | The document designation, for example `ISO 532`. |
| `part` | string | The part, as text, because parts are not always numbers. |
| `edition` | integer | The edition year the answer is expected to be against. |

A `capabilities` job carries none of the fixture or signal fields. It is not
about a stimulus.

The schema is `src/eichstelle/schema/adapter-job-1.schema.json` and it is the
authority for the shape. Validate against it while you are developing; it will
tell you what a hand-built job is missing faster than this table will.

## Why the numbers are strings

`timeout_seconds` is a string, and so is every value you return. JSON numbers
are IEEE 754 doubles in every parser this contract has to cross, and this suite's
entire output is a comparison against a tolerance. A decimal string survives
every parser unchanged and is converted deliberately, once, by whoever consumes
it. Counts stay numbers, because they are exact integers and nothing is lost.

## The result document

Write it to `result_path`. An object.

| field | type | meaning |
| --- | --- | --- |
| `protocol_version` | integer | Echo `1`. |
| `status` | string | `ok`, `unsupported` or `error`. |
| `diagnostic` | string | Free text for a human reading a failure. Required, may be empty. Nothing branches on it. |
| `fixture_id` | string | Echo the job's, so a result written to the wrong path is caught and never misattributed. Required when `status` is `ok`. |
| `values` | array of decimal strings | Your answer. Required and non-empty when `status` is `ok`, and empty when it is not. |
| `unit` | string | What the values are in. Required when `status` is `ok`. |
| `edition` | integer | The edition you actually answered against. Required when `status` is `ok`. |
| `capabilities` | array | Only on the answer to a `capabilities` job. See below. |

`values` is a list and not a single number because a time-varying metric answers
with a series. Answer with a one-element list for a scalar metric. A contract
that starts scalar acquires a second shape later, and this one does not.

`edition` is not decoration and it is not the job's field echoed back. Say which
edition you actually computed. An implementation answering a 2017 request with a
2025 model is a real and defensible thing to do, and a report that shows the
disagreement without showing that is a false finding about somebody's software.

The schema is `src/eichstelle/schema/adapter-result-1.schema.json`.

### The three statuses you may write

`ok` means you computed the metric and `values` is the answer.

`unsupported` means you do not claim this metric, or you do not claim this
edition of it, and you are declining, not failing.

`error` means you tried and could not, and `diagnostic` says why.

You may not write anything else. Four further outcomes exist and the harness
records them itself, because in each case there is no statement of yours worth
trusting: `timeout` when you ran past your limit, `crashed` when you exited
non-zero without leaving a well-formed result, `no_result` when you exited
cleanly and wrote nothing, and `malformed_result` when what you wrote does not
validate.

Keeping `unsupported` and `error` apart is the point of having both. An
implementation that never claimed to compute roughness is not failing to compute
roughness, and a report that says otherwise manufactures a disagreement out of
nothing.

## Exit codes

Exit `0` when you wrote a result, whatever its status. A declined measurement is
a successful invocation: you did what you were asked and the answer is that you
do not claim it.

Exit non-zero when you could not get far enough to write anything, including
when the job names a protocol version you do not implement. The harness records
`crashed` and reports the code.

The harness reads the result file, not the exit code, for anything about the
measurement. An exit code alone tells it nothing it can attribute to a fixture.

## The timeout

The harness terminates you and your children at `timeout_seconds` and records
`timeout` for that fixture. The run continues. Nothing about the rest of it is
lost, and it is never an exception that ends the run.

The number is in the job so you can give up early and write an `error` result
with a useful diagnostic, which is more informative than being killed. You are
not obliged to.

## The working directory and what you may not do

The harness makes a fresh directory for each invocation, names it in the job,
starts you in it, and deletes it afterwards. Inside it you may do as you like.

Three prohibitions, and they are short because they are absolute.

You do not write outside your working directory, except to `result_path`. The
stimulus at `signal_path` is outside it and is read-only, and it is the same file
handed to every adapter in the run, so writing to it would turn a disagreement
between implementations into a disagreement about bytes.

You do not open a network connection. Decision record 0010 is where that comes
from, and the intent is that this suite runs where there is no outbound network
at all, so an adapter needing one would not work there.

You do not require a display. The same reason: nothing is guaranteed to have one.

One of these is refused against an adapter, in one place, and the other two are
not refused anywhere.

The `verify` workflow runs this project's own suite inside an empty network
namespace, and says so out loud.

    git grep -n 'unshare --net' -- .github/workflows/verify.yml
    .github/workflows/verify.yml:150:        # The sandbox is an empty network namespace: `unshare --net` gives the
    .github/workflows/verify.yml:171:          sudo unshare --net -- bash -c '

So the suite runs where there is no egress, which is the environment an adapter
has to work in. Beside that, the offline guard reaches a process the run started
and not only the process that loaded it, which is asserted rather than hoped
for:

    git grep -n 'def test_the_denial_reaches_a_process_the_suite_starts' -- tests
    tests/e2e/test_architecture_conformance.py:269:def test_the_denial_reaches_a_process_the_suite_starts() -> None:

An adapter started inside that run is such a process, so a Python adapter
reaching outbound gets an exception at the call and never a connection. Read
the bound with it. The guard is on `PYTHONPATH` for a checked run and for nothing
else, so an ordinary `python -m pytest` and an operator's own run install it
nowhere; it replaces functions in Python's socket module, so an adapter that is
not a Python program is outside it entirely; and the namespace is the workflow's
Linux runner. Nothing anywhere inspects an adapter's source for any of the three.

The other two prohibitions have nothing behind them at all. No route reads where
an adapter wrote, and no route asks whether it wanted a display. These are the
contract, and breaking them is a defect in that adapter and not something
this project detects for you.

## Capabilities

A job with `kind` set to `capabilities` carries no fixture and no signal. It
asks one question: what do you do?

```json
{
  "protocol_version": 1,
  "status": "ok",
  "capabilities": [
    {
      "metric": "loudness",
      "editions": [2017],
      "field_conditions": ["free", "diffuse"],
      "calibration_conventions": ["full_scale_sine"]
    },
    { "metric": "sharpness", "editions": [2009, 2017] }
  ],
  "sample_rates": [44100, 48000],
  "upstream_version": "1.4.2",
  "diagnostic": ""
}
```

Three fields, and every one of them is required on a declaration.

| field | type | meaning |
| --- | --- | --- |
| `capabilities` | array | One entry per metric you claim. |
| `sample_rates` | array of integers | The rates in hertz you accept, enumerated. |
| `upstream_version` | string | The version of the implementation you wrapped, as loaded. |

Each entry in `capabilities`:

| field | type | meaning |
| --- | --- | --- |
| `metric` | string | The quantity, lowercase with underscores. |
| `editions` | array of integers | The standard editions you claim for it. Required, and at least one. |
| `field_conditions` | array of strings | Optional. The field conditions you claim for this metric. |
| `calibration_conventions` | array of strings | Optional. The conventions you can be told for this metric. |

The declaration travels through the same job and result files as a measurement,
so you implement one contract and not two, and it is validated the same way your
answers are.

### What the harness does with it

It asks once per run, before any fixture is invoked, and it decides every pair
of fixture and adapter against the answer. A pair you did not claim is recorded
as unsupported with the reason, and you are never invoked for it.

The reasons are kept separate, and are not one shared decline, because they are
different statements about your implementation: `metric_not_declared`,
`edition_not_declared`, `sample_rate_not_accepted`,
`field_condition_not_declared` and `calibration_convention_not_declared`.

### Declare narrowly, and why

The instinct is to claim everything and let the results speak. The outcome is a
wall of errors that reads, to anybody looking at the report, like your library is
broken. It was asked questions it never claimed to answer, and each one became a
red line with your name on it.

Declaring narrowly costs nothing. A metric you do not claim is reported as
coverage and never as correctness. Adding a claim later is one line.

There is a difference the report depends on: an error from a capability you
DECLARED is a stronger finding than a decline from one you did not, and the
record keeps the two apart. Declaring honestly is what keeps that distinction
worth anything.

### Absent means none, not all

An optional field left out is a claim of NONE and never a claim of all. A
fixture asking for a free field against a metric whose entry names no
`field_conditions` is unsupported and is not invoked.

The other reading is the dangerous one. Free field and diffuse field give
different answers for the same signal, and an implementation handed a fixture it
never said it could place would answer in whichever it defaults to. That value
would arrive in the report looking like a disagreement about loudness.

Same for the calibration convention. A convention you assume instead of accept
moves every value you produce, in one direction, invisibly.

`sample_rates` is enumerated and not a range, because a range has to be
interpreted, and an adapter that quietly resamples to suit itself is what the
no-corrections rule forbids.

### The version, and the honest unknown

`upstream_version` is what you LOADED, not what you pinned. Those two can differ,
and when they do a result attributed to the pin is wrong in a way nothing else
would catch.

Where the library exposes no version at all, write the empty string. That is the
declared unknown and it reaches the report as an unknown, because a result
attributed to a version nobody can identify is not reproducible and the reader is
entitled to see which of the two they are holding. Do not fill it in with a
plausible number.

### If you cannot answer

An adapter that fails the capability query is unusable, and the run says so
ONCE, against the adapter, and does not fail every fixture separately. A
declaration the schema refuses is the same case: nothing partial is taken from
it.

### One note on the version of this contract

The three declaration fields were specified here by issue #34, and two of them,
`sample_rates` and `upstream_version`, became required after protocol version 1
was published. The rule below says adding a required field raises the version.
It was not raised, and the reason is written down and not left out: until
this change nothing in this project ever asked an adapter for its capabilities,
so no adapter could have been written against the declaration in a way that ran.
The versioning rule protects an adapter author who has something working, and on
this document shape there was nobody in that position. From here it applies
normally.

## A complete worked example

The job the harness writes:

```json
{
  "protocol_version": 1,
  "kind": "measure",
  "fixture_id": "example-tone-at-forty-decibels",
  "fixture_revision": 1,
  "signal_path": "/run/eichstelle/signals/example-tone-at-forty-decibels.wav",
  "sample_rate": 48000,
  "channels": 1,
  "metric": "loudness",
  "metric_parameters": { "field_condition": "free" },
  "standard": "ISO 532",
  "part": "1",
  "edition": 2017,
  "result_path": "/run/eichstelle/invocations/0001/result.json",
  "working_directory": "/run/eichstelle/invocations/0001",
  "timeout_seconds": "120.0"
}
```

The result you write to `/run/eichstelle/invocations/0001/result.json`:

```json
{
  "protocol_version": 1,
  "fixture_id": "example-tone-at-forty-decibels",
  "status": "ok",
  "values": ["1.02"],
  "unit": "sone",
  "edition": 2017,
  "diagnostic": ""
}
```

Declining the same job, because you do not claim that edition:

```json
{
  "protocol_version": 1,
  "fixture_id": "example-tone-at-forty-decibels",
  "status": "unsupported",
  "values": [],
  "diagnostic": "this implementation follows the 2005 edition of ISO 532-1 only"
}
```

## Versions, and what happens when this changes

`protocol_version` is an integer and it is `1`. Refuse a job carrying a version
you do not implement, and exit non-zero. Do not answer it on the assumption that
the fields you know are still there and still mean the same thing, because that
assumption is exactly what the field exists to make unnecessary.

A change that would break an adapter written against version 1 raises the
version. That includes adding a required field, removing one, narrowing what a
field may contain, and changing what a value means. Adding an optional field
does not, and neither does adding a new value to a set an adapter is expected to
handle by ignoring what it does not recognise.

When the version rises, the schema for the old version stays in the tree
unedited, exactly as it was published, and the harness keeps writing version 1
jobs to adapters that declare only version 1 for at least one release after the
new one appears. An adapter author gets a release to move, and finds out by
reading a changelog and not by a run failing.

None of that is built. There is one version, there is no negotiation and no
adapter has ever been run by this project. What is written here is the rule that
applies when the second version exists, recorded now because deciding it after
the fact is how a protocol acquires two incompatible dialects.
