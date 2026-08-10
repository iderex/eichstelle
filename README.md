# eichstelle

Psychoacoustic metrics now have three independent implementations of the same standards, MOSQITO and SQAT and PsyTools, and nobody checks whether they agree. That is worse than it sounds because the standards cannot be read without buying them, so each implementer validates against their own understanding. That this goes wrong is shown by a BELLHOP fork which found that some discontinuities in the physics of the most-used propagation code in the discipline were purely artificial. What is missing is the reference signals and target values from the standards as machine-readable fixtures plus a CI harness any implementation can be run against; the EAA benchmark on Zenodo is a start and does not cover signal processing at all.

Planning happens on the issue tracker first. Every decision that shapes
the architecture is written down there with its reasons before the code
that depends on it exists.

Audio you run through this suite stays on your machine. Nothing leaves it unless
you publish it deliberately, and [docs/privacy.md](docs/privacy.md) is where
that is written out for somebody who has to answer for it, including which parts
of it a test checks and which parts are a rule people follow.

The standards this suite tests against are sold by their publishers and no part
of one is distributed here. [docs/legal.md](docs/legal.md) says what is and is
not in this repository, where every expected value came from, and how an
operator who owns a standard runs its own material without it ever reaching this
tree. It also says the thing a legal reader needs first, which is that this
repository declares no license and is therefore all rights reserved.

## What this project does not claim

This project certifies nothing. A green result says that an implementation
agreed with a set of fixtures, within the tolerances those fixtures declare, on
one machine on one day, and no clause of any standard makes that a conformance
certificate. What you get instead is a result record naming the fixtures, their
revisions, the standard editions and the adapters it ran against, so the run can
be repeated and cited by somebody who was not there.

Most of the fixture set is differential only. For those fixtures the suite
reports whether the implementations agree with each other and cannot say which
of them is right, so it reports the spread and elects no winner. Where an
expected value does come from a normative table the fixture says so in its
provenance field, which is how a reader tells the two situations apart without
guessing.

It implements no metric, so it adjudicates nothing. There is no house answer
here to compare anyone against: every number in a report comes from an
implementation under test, reached across a process boundary, and the harness
never touches it on the way through.

Agreement between two implementations is weaker evidence than it looks where
those implementations share a lineage. This project says what it knows about
where each one came from, so that agreement is not read as independent
confirmation when it is not.

Coverage is partial and always will be. The fixture set covers what somebody has
written a fixture for, so a run says what it did not cover, because a result
silent about its gaps gets read as having none.

A disagreement is a finding and not a verdict about anyone's software. It may be
the fixture, the calibration convention, the standard edition, the platform or
the implementation, and nothing here can tell which without a person looking.
What the suite offers is the disagreement, stated precisely enough to be
investigated.

The reasoning behind each of these is in
[docs/decisions](docs/decisions), and
[docs/versioning.md](docs/versioning.md) says what a version number here does
and does not promise.

See [NOTICE.md](NOTICE.md) for the intended-use notice.
