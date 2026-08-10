# Copyright: what is distributed here and what is not

This repository distributes a test harness, a set of fixtures that describe
signals by their parameters, and the documents around them. It distributes no
part of any standard: not the text, not the tables, not the tolerances, and not
the validation signals published with them. It contains no audio file of any
kind. Every reference signal is generated from its description when a run
happens, on the machine the run happens on.

The rest of this document says why, what an operator who owns a standard can do
instead, and what the reciprocal obligations are when this suite is run against
somebody else's implementation. It is written for two readers who want different
things: a researcher asking whether the fixtures can be used in a paper, and a
legal department asking whether running this suite creates an exposure. Both
answers are meant to be in front of them rather than at the end.

This document is not legal advice.

## This repository has no license, and that is the first thing to know

There is no license file here:

    $ git ls-files | grep -ci "^LICEN[CS]E"
    0

    $ gh api repos/iderex/eichstelle --jq .license
    null

In copyright terms that means all rights reserved. Nobody may copy, modify or
redistribute this work, and a contributor who opens a pull request has no terms
to contribute under. That is not an oversight. Which license this repository
carries is a maintainer decision and it is open as issue #1, with the options
and their costs written out there.

Until it is answered, everything below describes what this project does with
other people's material. It does not tell you what you may do with this
project's own, and reading anything here as a grant would be reading it wrong.

## The standards are sold, and their contents stay with their publishers

The standards this suite tests against are copyrighted works published and sold
by standards bodies. Where a standard distributes normative validation
material, and at least one of the ones this project cares about does, that
material is part of what the purchaser bought and is not redistributable. This
project will never ship it.

The consequence for the fixture set is direct and it is stricter than the law
requires. No expected value is written into this repository out of a document
this project does not hold. Not into a fixture, not into a test, not into a
comment.

A single number is a fact, and facts carry no copyright. A table of numbers is a
compilation, it is what the publisher sells, and a fixture set carrying values
out of one is a fixture set nobody may copy. Where the line between those two
runs in a particular case is an argument this project would be having at the
margin, for a number it does not need, against a publisher with more time than
it has. So the rule is drawn well short of the line rather than on it.

Decision record 0012 in `docs/decisions` is where that was decided and what it
supersedes. `CONTRIBUTING.md` lists it among the things this project will not
accept.

### The rule has a check behind it

`tools/invariants.toml` carries a rule with the id `no-transcribed-expected-value`,
and `tools/invariants.py` runs it as the `invariants` check on every pull
request. It refuses a fixture declaring the `standard-clause` provenance and a
small set of phrases that describe writing a value down out of a document.

Read that as a floor rather than a guarantee, which is what the rule says about
itself in the file. It is a pattern match over source text. It cannot tell a
citation from a transcription in prose, because an honest fixture names a
standard designation in exactly the same words, and no token separates the two.
The half it catches is the half a schema value makes checkable, and review is
what stands behind the rest.

`docs/ci-checks.md` says what a failure of that check means.

## Where an expected value in this repository came from

Every fixture declares its provenance in a field, and there are three kinds.
Decision record 0012 fixed the list and `docs/adding-a-fixture.md` says what
evidence each one needs.

`generated-by-definition`. The value follows from the definition of the signal
and the metric. One sone is the loudness of the reference tone because that is
what a sone is. A definition is a fact rather than an expression, so nothing
here restricts reuse.

`published-paper`. The value comes from the open literature, cited precisely
enough to find. What is distributed here is a number and a citation, not the
paper. Anybody reusing the fixture should follow the citation for the source's
own terms, which are the publisher's and not this project's.

`implementation-consensus`. The value is what several independent
implementations agreed on when this project ran them. That is a measurement this
project made, and it is distributable on whatever terms this repository ends up
carrying.

There is a fourth value, `standard-clause`, still present in schema version 1:

    $ git grep -c standard-clause -- src/eichstelle/schema/fixture-1.schema.json
    src/eichstelle/schema/fixture-1.schema.json:1

No fixture here declares it and none may. A published schema version is not
edited where the edit would refuse a fixture that is valid under it today, so
removing the value is a version 2 and a migration rather than a deletion.
Decision record 0012 says this and `docs/adding-a-fixture.md` tells a
contributor plainly that it is the one value the validator will accept and a
reviewer will not.

## The operator who owns a standard is not asked to break their license

An operator who bought a standard is entitled to use its validation material.
They cannot share it, and this project does not ask them to. What they need is a
suite that will read their own files from a place they control.

The design for that is the licensed-reference slot, decided in decision record
0005 and built by issue #31. How it works:

- A fixture may carry a reference slot naming a file, a checksum of that file,
  and the standard, edition and clause it belongs to. None of those three is the
  file, and none of them is a value out of the document.
- The operator puts their file in a directory they configure, outside this
  repository, and points the harness at it.
- The harness looks for the file there by name and verifies it against the
  declared checksum. On a match it uses it as the stimulus. The same slot carries
  normative expected values on the same terms: supplied locally, never tracked
  here.
- An absent directory or an absent file is a not-run verdict naming the reason.
  A checksum that does not match is a refusal that stops the run, because a file
  under the expected name with unexpected contents is a stronger statement than
  an absent one.
- There is no fall back to a generated approximation. A run that quietly
  substituted a different stimulus would produce a number that looks like every
  other number and answers a different question.
- A run says which fixtures used a licensed reference and which did not, so two
  reports can be compared without anyone having to ask.

That slot is designed and is not built. Issue #31 is where it arrives, and until
it does there is nothing in this tree for an operator to configure. The design is
described here rather than left until then because it is the answer to the
question this section's heading asks, and a legal reader deciding whether to
depend on this project needs the answer before the code exists.

The checksum in such a slot fingerprints a file this project does not have and
cannot produce. It would be contributed by an operator who holds the standard,
and it says that two operators are running the same bytes and nothing more.
Nothing in the reporting should let it read as validation of the file's
contents.

## No audio is committed here

Plainly, and without qualification. Not a fixture signal, not an example, not a
short clip in a test, and not one in a document. Decision record 0005 is where
that was decided, and `tools/refuse_tracked_audio.py` is the check that refuses
one, running as `no-tracked-audio` on every pull request.

That check reads the index rather than the working tree, so what it judges is
what is being pushed. Its own bound is worth knowing: it matches a table of
container extensions and leading-byte signatures, so a container nobody listed
walks through it, and samples stored as text defeat both. It is aimed at the
honest mistake and at a large binary arriving under an innocent name.

## The implementations this suite runs against carry their own licenses

Running an implementation from an adapter does not relicense this repository,
and nothing of an implementation's code or its bundled sound files is copied
into this tree. What an operator runs on their own machine is between them and
that implementation's license.

One of the three implementations this project targets is published under a
Creative Commons license carrying a non-commercial term. A commercial operator
running the suite against it is bound by that term, and this project's position
on what its documentation should say about that is a maintainer decision, open
as issue #1.

This document names no implementation's license, and that is an absence rather
than an omission. No adapter is in this tree:

    $ git ls-files adapters | wc -l
    0

An adapter pins the exact upstream version it wraps, and the license of what is
wrapped belongs beside that pin, where it can be read against the version it
applies to. Issues #35, #36 and #37 are where the three adapters arrive.
Writing a license name here before then would be a claim about somebody else's
project made from memory, and a license that moved between versions would leave
this document confidently wrong.

## Where the rest of it is

`NOTICE.md` carries the intended-use notice. `README.md` says what a green
result from this suite does and does not mean. `docs/privacy.md` covers the
separate question of where an operator's own audio goes, which is data
protection rather than copyright and is answered in its own document.
