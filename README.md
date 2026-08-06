# eichstelle

Psychoacoustic metrics now have three independent implementations of the same standards, MOSQITO and SQAT and PsyTools, and nobody checks whether they agree. That is worse than it sounds because the standards cannot be read without buying them, so each implementer validates against their own understanding. That this goes wrong is shown by a BELLHOP fork which found that some discontinuities in the physics of the most-used propagation code in the discipline were purely artificial. What is missing is the reference signals and target values from the standards as machine-readable fixtures plus a CI harness any implementation can be run against; the EAA benchmark on Zenodo is a start and does not cover signal processing at all.

Planning happens on the issue tracker first. Every decision that shapes
the architecture is written down there with its reasons before the code
that depends on it exists.

See [NOTICE.md](NOTICE.md) for the intended-use notice.
