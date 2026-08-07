# 0010. Headless, unprivileged, offline and unlicensed by birth

## Decision

Every test in the default gate runs without a display, without elevated
privileges, without a network and without a licensed runtime. Anything that
cannot is not in the gate, and it is named so that nobody mistakes it for
something that is.

## Context

This is a birth requirement rather than a later hardening step, because
retrofitting it is not possible. A suite whose tests quietly assume a soundcard,
a graphics context, an installed MATLAB or an internet connection has those
assumptions distributed through hundreds of files by the time anyone notices, and
the noticing usually happens as an unexplained failure on somebody else's
machine.

### The four constraints

No display. No test creates a window, opens a graphics context, or requires a
session that provides one.

No elevation. No test attempts a privileged operation, installs anything system
wide, registers a service or a scheduled task, or trusts a certificate. A test
that needs elevation is not run and its absence is disclosed.

No network. No test binds a port, listens, or makes an outbound connection. The
gate runs the same on a machine with no route to the internet as on one with.

No licensed runtime. No test invokes software that requires a license key to
start.

### What the default gate is permitted to touch

A temporary directory it created. The repository tree, read only. Its own
subprocesses. Nothing else.

No audio device is opened, no window is created, no port is bound, no outbound
connection is made, no privileged operation is attempted, and no software
requiring a license key is invoked.

### The architectural consequences

These run all the way back into the design, which is why this is a decision and
not a policy note.

It is the reason the adapter boundary is a process and a pair of files rather
than an import, in record 0006. A process boundary is what lets the whole harness
be exercised end to end by a fake adapter that is a short script with no
dependencies, on a runner with no scientific stack and no license behind it. An
in-process interface would have made the harness untestable without the very
things it exists to be independent of.

It is the reason reference signals are generated rather than fetched. A run with
no network cannot download a stimulus, so the stimulus has to follow from a
recipe the tree carries.

It is the reason the fixture set carries checksums. A run with no network cannot
go and look up what it should have got, so the expected bytes travel with the
fixture and a stimulus that moved stops the run.

### The paths that genuinely need more

There are genuinely hardware-bound and license-bound paths, and pretending
otherwise would be the dishonesty this decision is against.

Running the MATLAB toolbox needs MATLAB, or needs an Octave compatibility route
which is itself a claim requiring its own evidence. Verifying that a generated
WAVE file plays back at the level it claims needs a calibrated output chain and a
room. Neither can be faked and neither should be dropped.

Those live in a separate harness, invoked deliberately, never a required check,
and recording its results in the same format as the default gate so that the two
are comparable.

The naming rule matters as much as the separation. A job called "integration"
tells a reader nothing, and a reader who cannot tell what a job needs will
eventually assume it needs nothing. A job called "needs a MATLAB license" cannot
be misread. The harness name states its requirement in plain words, and that is a
rule about the name rather than a suggestion about it.

### The run says what it did not cover

A run of the default gate states in its output which harnesses were not part of
it, and what running them would require. A run that covered less than everything
must not be readable as one that covered everything and found nothing.

This is the half that is easiest to skip and the half that makes the rest
honest. A green gate that says nothing about what it skipped is a green gate
somebody will cite as evidence the licensed paths pass.

### What refuses a violation

A sentence in a decision record is not a rule. The rule is in milestone 6.

Issue #49 carries the lint rule that refuses a test in the default suite which
opens a socket, opens a device, or requires a display, and the rule lands with
the deliberate violation it was shown to refuse. That is the check that makes
this record enforceable rather than advisory.

Issue #52 carries the conformance test that runs the whole default suite with
outbound network access denied and asserts it passes, and the test that asserts
no default-suite test requires a display or elevation. That is the other half:
the lint refuses the shape of a violation in the source, and the conformance test
refuses the behaviour at run time. Neither alone is enough, because the lint is a
pattern match that can be evaded and the conformance test only sees what actually
ran.

Until both land, this record is prose, and it should be read as prose.

## Alternatives

Allow network access in the gate and rely on discipline. Rejected because a test
that reaches the network passes on the author's machine and fails on somebody
else's, and because the failure surfaces months later as flakiness rather than as
a refusal.

Allow the licensed and hardware-bound paths into the default gate and skip them
when their requirement is absent. Rejected because a skipped test that reports as
part of a passing run is the mechanism by which a suite stops meaning anything. A
green run containing silently skipped legs is worse than a red one.

Make it a policy note in the contributing guide rather than a decision with
checks behind it. Rejected because the four constraints have architectural
consequences that other decisions already depend on, and a note is not something
another record can rest on.

## Consequences

Whole classes of test are unavailable in the gate, and the answers they would
have given are not available either. This suite cannot assert, in its default
run, that a generated WAVE file plays back at the level it claims. That is a real
gap and it is named here rather than left for a reader to discover.

The separate harness has to be run by someone, deliberately, or its results are
stale. Nothing in the default gate will remind anyone, which is the cost of it
never being a required check. The scheduled run in milestone 6 is where that is
answered.

Every future test carries this constraint whether or not its author knows about
it, which is why the mechanism is a refusing check rather than a review habit.

## Status

Accepted, 2026-08-07.
