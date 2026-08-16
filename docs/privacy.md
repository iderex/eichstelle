# Data protection: where an operator's audio goes

Nothing an operator runs through this suite leaves their machine unless they
publish it deliberately. The harness opens no outbound connection of its own, it
writes only where it was told to write, and there is no telemetry, no update
check and no crash reporting to switch off, because none of it was built. Audio
an operator points the suite at is read on that machine and stays there.

That is the whole answer, and the rest of this document is about how much of it
is checked and how much of it is a rule people follow. The difference matters
here more than usual: somebody reading this page is often being asked to sign
off on running the tool inside an organisation, and a promise with nothing
behind it is worth less than a promise with a test behind it. Both kinds appear
below and each one says which it is.

This is not legal advice, and nothing in it tells an operator what their own
obligations are.

## Why audio is treated as if it were personal data

A sound recording can be personal data in the ordinary sense: it can relate to
an identifiable person, and then the law that governs personal data governs it.

The cases are not exotic ones. A recording made to characterise a product
carries whoever was audible in the room while it was made. A machine recorded in
a workplace carries the people working near it, and in some jurisdictions
recording a workplace is a matter for the works council before it is a matter
for anybody else. A vehicle cabin carries its occupants. A hospital corridor
carries patients.

This project does not decide whether a given recording is personal data, and it
does not need to, because its behaviour is the same either way. Deciding is the
operator's, and it depends on facts about the recording that no tool can see.
What this project can do, and the only useful thing it can do, is make certain
it never becomes part of the problem. Decision record
[0011](decisions/0011-personal-data-stays-on-the-host.md) is where that argument
was made and is the record this document reports on.

A metric computed from a recording is derived from it, and derivation is not
anonymisation. That is why the caution below extends to the result record and
not only to the audio.

## The suite makes no outbound connection

Not for telemetry, not for update checks, not for error reporting, not for
fetching fixtures and not for resolving a standard reference. Reference signals
are generated from their parameters and never downloaded, and an operator's
licensed reference material is read from a directory they control and not
looked up.

This claim carries a check. The default suite is run again as a child process
with every outbound socket call replaced by one that refuses, and the test
asserting it passes that way is
`test_the_default_suite_passes_with_outbound_network_denied` in
`tests/e2e/test_architecture_conformance.py`. Two more tests in the same file
carry the parts that make the first one worth anything:
`test_the_denial_reaches_a_process_the_suite_starts`, because the end to end
runs spend their time in adapters running as separate processes and an adapter
is exactly the kind of program that phones home, and
`test_the_guard_reddens_a_test_that_opens_a_connection`, which is the guard
biting a deliberate violation, so a green result is not a guard that has quietly
stopped denying anything.

What the check does not cover is written where the guard is, in
`tests/e2e/offline/offline_guard.py`, and is repeated here because a reader of
this page should not have to open a test file to find the limits. The guard
replaces the socket calls a Python program reaches the network through. A raw
socket, a connection made through `ctypes` against the platform's own sockets
library, and a subprocess that is not a Python interpreter are all outside what
it can see. So it is a floor on what the suite is permitted to reach and not
a sandbox. The `tests` legs on a pull request make the stronger statement, by
running the suite inside an empty network namespace with nothing in it but
loopback, and by proving there was egress to remove before removing it.

Installing dependencies reaches the network, obviously. That is the operator's
own package manager doing what it exists to do, before the suite runs and
outside it, under whatever policy the operator already applies to it. The claim
above is about the suite.

## Operator audio, and what the suite does with it

Operator audio is read and is not copied anywhere the operator did not name.
Nothing is written into the installed package or into this repository. A suite
that wrote results or caches beside its own source is a suite whose outputs get
committed by accident, and the accident would be a recording in a public
repository.

Two things about this are worth being exact about, and being reassuring about
them would be worth less.

The suite cannot read an operator's audio file at all today. There is no audio
reader in the tree: what exists writes generated stimuli, and reading a file an
operator supplies is not yet built. So the paragraph above describes the rule
the reader will be built to, and today it describes a route nothing takes.

Temporary directories are the harness's to create and remove, and each adapter
invocation is given a fresh one. An adapter is told in
[adapter-contract.md](adapter-contract.md) not to write outside the directory it
was given, and the harness does not enforce that. An adapter is third-party code
running as a separate process on the operator's machine with the operator's own
permissions, and this project cannot make it behave. What it can do is not hand
it anything it was not asked to run against.

## The record names your material by an identifier, not by a path

The result record contains no audio. It can still carry fragments of what was
processed, because a file path carries a site name, a project code name, a
person's name or a patient identifier often enough that treating paths as
harmless is wrong.

So the record identifies operator-supplied inputs by an identifier the operator
assigns, and the filesystem path is left out. This is the default and it is off
in the sense that matters: the field is absent unless somebody asked for it.

How it is turned on, in the tree as it stands, is a single argument to the
record writer, `operator_paths_included` in `src/eichstelle/record/record.py`,
which defaults to false. With it false a source path handed to the writer is
dropped and not refused, so a caller that passes one produces a record
without it and never an error. With it true the path is written into the
record. There is no command-line switch for it yet, because the command an
operator types is still being built, and this document will be wrong about that
sentence and not about the default when it lands.

An operator debugging their own run on their own machine is the reason the
setting exists at all. An operator who intends to send a record to somebody else
has one thing to check and not a file to audit.

## Publishing is something you do, per run, having seen it

Publishing a result so that it can be compared with other operators' results is
worth having and it is the feature most likely to leak something. The design
answer is that publishing by accident is not reachable: it is requested on the
command line of the run that publishes, there is no configuration key,
environment variable or stored profile that turns it on for later runs, and the
operator sees the payload itself rather than a summary of it before anything is
sent. Anything derived from operator-supplied audio is outside the default
payload and needs its own separate confirmation.

None of that is implemented. [federation.md](federation.md) is the design and
says so in its own first paragraph, and the decision record says the
implementation is deliberately not in the first release. Read this section as
what the feature will be required to do, not as a description of something an
operator can use or has to defend against. The thing an operator can rely on
today is simpler and stronger: there is no code here that sends anything
anywhere.

Results computed from the generated fixture signals contain no personal data by
construction. There was never a recording, only a recipe, and every input is in
this repository already. That is the case the publishing design is built around.

## What this project does not do

It does not encrypt an operator's files, and it does not manage keys.

It does not manage retention, delete anything on a schedule, or know how long an
operator is allowed to keep what they have.

It does not classify a recording. It cannot tell an operator whether a given
file is personal data, whether they have a lawful basis for processing it, or
whether their works council has been asked.

It does not audit an adapter. An adapter is somebody else's code and it runs as
a separate process with the operator's own permissions, so what it does with
what it is given is between the operator and whoever wrote it.

It does not certify anything about an implementation, which is a different
subject and is in the README.

Claiming any of these would be worse than saying nothing, because each one is a
thing somebody might otherwise stop doing for themselves.
