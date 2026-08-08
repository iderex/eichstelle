# Security policy

## What is supported

Nothing is released yet. There is no tag, no published artefact and no version
number that promises anything; the value in `pyproject.toml` is a placeholder
and `docs/versioning.md` says what a version here will and will not mean once
one exists.

So the supported version is the tip of the default branch, and that is the whole
list. When the first release is cut this section says which releases receive
fixes and for how long, and not before.

## Reporting a vulnerability

Use the private reporting channel on this repository, under Security, then
Report a vulnerability. It is enabled:

    $ gh api repos/iderex/eichstelle/private-vulnerability-reporting
    {"enabled":true}

Do not open a public issue for something you believe is exploitable. There is no
email address here on purpose, because an address outgrows the person behind it
and the channel above does not.

What to expect. An acknowledgement within seven days that a human has read the
report, and an assessment within thirty days saying whether it is accepted, what
the fix is, or why it is out of scope. This project has one maintainer and no
paid support, so those are the honest numbers rather than a service level
anybody is holding to. If seven days pass in silence, say so on the same report.

A fix lands as a public change with the issue and the reasoning visible, the
same as every other change here. Credit is given where the reporter wants it.

## What this project is exposed to

The harness runs third-party numeric code on an operator's machine and reads
files the operator supplies. That is the shape of it, and these are the places
where the shape has consequences.

An adapter is arbitrary code, by design. Connecting an implementation means
running it, and running it means whatever that implementation does. The harness
launches it across a process boundary and reads what comes back; it does not
sandbox it, does not restrict what it may open or send, and does not claim to.
Nothing here turns an untrusted implementation into a safe one, and an operator
who runs an adapter has decided to run that code. What is owed instead is
isolation of the harness from the adapter's failures and honest reporting of
what actually ran, including what each adapter loaded.

A fixture file is parsed input. Fixtures are meant to be exchanged, which means
a fixture can arrive from somewhere the operator did not write. Parsing one must
stay parsing: a malformed or hostile fixture may be refused, and it may not
become code execution, a file write outside the working directory, or a network
call. The same holds for a result record read back in and for whatever an
adapter prints on its way out.

An audio file supplied by an operator is untrusted input to a parser. It has the
same standing as a fixture and the same rule applies to it.

A result record may carry fragments of an operator's data. File names, paths,
parameters and, depending on what was measured, characteristics of the audio
itself. Issue #12 is the decision that treats a record as sensitive for that
reason, and a report about a record leaking more than it should is in scope
here.

## What is out of scope

A vulnerability in an implementation under test is that project's, not this
one's. MOSQITO, SQAT, PsyTools and anything else reached through an adapter are
separate projects with their own maintainers and their own reporting routes, and
a finding about their code belongs with them. Send it there. If you cannot find
the route, open a report here anyway and it will be routed rather than dropped;
routing it is help this project is glad to give, and fixing it is not something
this project can do.

That an adapter can run arbitrary code is not a vulnerability. It is the
described behaviour, stated above and stated again wherever an operator
configures one. A report that the harness "executes untrusted code" without
naming a way to reach that execution other than an operator deliberately
configuring an adapter will be closed as out of scope.

Denial of service against a local test harness by feeding it a file that makes
it slow is out of scope. A crash that turns into code execution is not.

Findings against the repository's own workflows, actions and supply chain are in
scope and are wanted.

## Intended use

[NOTICE.md](NOTICE.md) states what this software is developed for and where the
responsibility for a lawful deployment sits. It is not restated here.
