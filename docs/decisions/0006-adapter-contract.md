# 0006. An implementation is connected as a subprocess adapter

## Decision

An adapter is an executable. The harness writes a JSON job to a file and invokes
the adapter with the path to it; the adapter writes a JSON result to the file
whose path the job names. Nothing belonging to an implementation under test is
ever imported into the harness process.

## Context

Three reasons, and the third is the one that decides it.

It is language-agnostic in the only way that matters. The implementations in
scope are Python and MATLAB today, and this field's older and more consequential
codebases are Fortran and C++. A contract expressed as files and a process
invocation is satisfiable by all of them without the harness knowing anything
about their runtime.

It is fault-isolating. An implementation under test is, from this project's point
of view, arbitrary third-party numeric code that may segfault, hang, exhaust
memory, or exit with a stack trace on a signal it does not like. In-process, that
takes the harness down and the run reports nothing at all, including about the
fixtures that had already passed. Out of process it is a non-zero exit code, a
timeout or a malformed result, all of which are outcomes the suite records and
reports.

It makes the harness testable without installing any implementation, and this is
the reason that carries the decision. If the adapter boundary is a process and a
pair of JSON documents, then a fake adapter that reads a job and writes a
plausible result is a short script with no dependencies. Everything above that
boundary, which is nearly all of the harness, can then be exercised end to end on
a bare runner with no MATLAB license, no scientific stack, no display and no
network. That is the headless promise in record 0010, and an in-process plugin
interface would have made it impossible to keep.

### The job document

`protocol_version`, an integer, so an adapter written against an older contract
refuses rather than guesses.

`kind`, either `measure` or `capabilities`. See below.

`fixture_id` and `fixture_revision`, copied from the fixture, so the result can
be attributed without the adapter being trusted to echo them correctly.

`signal_path`, an absolute path to the generated stimulus, and `sample_rate` and
`channels` describing it. The file is read-only and lives outside the working
directory, and the same file is handed to every adapter in a run, so that a
disagreement is about the implementations and never about the bytes they were
given.

`metric` and `metric_parameters`, naming what to compute and with what arguments.

`standard`, `part` and `edition`, naming which edition the answer is expected to
be against.

`result_path`, the path the adapter must write its result to.

`working_directory`, the path the harness created for this invocation.

`timeout_seconds`, so an adapter that wants to give up early can, and so the
number is not a secret the harness keeps to itself.

### The result document

`protocol_version`, echoed.

`fixture_id`, echoed, so a result written to the wrong path is detected and not
than misattributed.

`status`, one of `ok`, `unsupported` or `error`.

`values`, a list of decimal strings, and `unit` naming what they are in. A list
rather than a scalar because a time-varying metric answers with a series, and a
contract that starts scalar acquires a second shape later.

`edition`, naming the edition the adapter actually answered against, which is not
always the one requested and is the thing a false finding turns on.

`diagnostic`, free text, for a human reading a failure. It carries no meaning to
the harness and nothing branches on it.

### Statuses the adapter writes, and outcomes the harness derives

The adapter may write exactly three statuses. `ok` means it computed the metric
and `values` is the answer. `unsupported` means it does not claim this metric, or
this edition, and is declining, not failing. `error` means it tried and
could not, and `diagnostic` says why.

Four further outcomes are recorded by the harness, and an adapter cannot write
them, because in each case there is no adapter statement worth trusting.
`timeout` when the invocation ran past its limit. `crashed` when the process
exited non-zero without leaving a well-formed result. `no_result` when the
process exited cleanly and wrote nothing at `result_path`. `malformed_result`
when what it wrote does not validate.

Keeping the two sets apart matters because a report that merges them cannot
distinguish an implementation that honestly declined from one that fell over, and
those call for opposite responses from whoever reads the report.

### Capability declaration

A job with `kind` set to `capabilities` carries no fixture and no signal. The
adapter writes a result listing the metrics it claims and, per metric, the
standard editions it claims. The harness reads that once per run and reports a
metric the adapter does not claim as `unsupported` without ever invoking it for
that fixture.

Capabilities travel through the same job and result files as a measurement, and
not
than through a second command-line protocol, so an adapter author implements one
contract and not two, and so the declaration is subject to the same validation.

`unsupported` and `error` are different words for different states. An
implementation that never claimed to compute roughness is not failing to compute
roughness, and a report that says otherwise manufactures a disagreement out of
nothing. This distinction is the reason capabilities exist as a mechanism and not
than as documentation.

### Timeouts

The harness imposes a timeout on every invocation and states it in the job. On
expiry the harness terminates the process and its children and records `timeout`
for that fixture. A timeout is a result: the run continues, the report says the
adapter did not answer within its limit, and nothing about the rest of the run is
lost. It is never an exception that ends the run.

### The working directory

The harness creates a fresh directory per invocation, names it in the job, and
runs the adapter with it as the process working directory. The harness makes no
promise about what an adapter does inside it, beyond deleting it afterwards. An
adapter may not write outside it, and the signal file it is given is outside it
and read-only, so an adapter cannot alter the stimulus another adapter will be
handed.

## Alternatives

An in-process plugin interface, with each implementation imported and called
directly. Rejected on all three counts. It is limited to implementations written
in the harness's own language, so the MATLAB toolbox and every Fortran and C++
codebase in the field are out by construction. It gives the harness no way to
survive a segfault or a hang in code it does not control. And it would make the
harness untestable without installing the very things it exists to be independent
of, which is the reason it is rejected and not merely disliked.

A long-lived server process per implementation, spoken to over a socket.
Rejected because it opens a port, which record 0010 forbids in the default gate,
and because it trades the fault isolation this decision is for against a startup
cost the next section says is affordable.

## Consequences

Process startup dominates the runtime for cheap metrics, particularly where the
adapter has to boot a large interpreter or a MATLAB session for each invocation.
For a fixture set of any size against an implementation of that shape, the run
time is mostly startup and not computation. That cost is named here and accepted
now.

A batching extension to the contract, where one invocation carries several jobs,
is a later decision. It is deferred rather than ruled out, and it is deferred
because batching before the contract has been exercised would fix the wrong shape
in place. Nothing in this record forbids it, and the `kind` field is where it
would arrive.

The harness cannot see inside an implementation. Everything it reports is derived
from a file the implementation wrote and an exit code, which is exactly the
limitation this project wants, because it is also the limit of what an outside
observer can honestly claim.

## Status

Accepted, 2026-08-07.
