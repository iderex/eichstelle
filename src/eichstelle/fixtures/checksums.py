"""The signal checksums, and the mismatch that stops a run.

Decision record 0005 says reference signals are generated and never shipped, so
a fixture carries a description and the samples are made at run time. That
arrangement has one hazard and it is the reason this module exists: the bytes a
description renders to depend on the code that renders them, and nothing in the
fixture records which bytes anybody saw. A numeric library moves a filter
coefficient in its last bits, every band-limited noise fixture shifts slightly,
and every implementation appears to develop a small disagreement at once. The
investigation then starts by suspecting the implementations, which is the wrong
end.

So the hash of each fixture's rendered signal is committed, and the harness
regenerates and compares before any adapter is invoked. A mismatch stops the run
rather than warning, because a run that proceeded on a different stimulus
produces numbers that look like results and are not.

## What is hashed, and what is deliberately not

The samples and the format parameters that decide how those samples are read:
the sample rate, the channel count, the frame count and the sample encoding. No
container byte enters the hash at all. WAVE has no timestamp field, but writers
add `LIST` and `INFO` chunks carrying authoring metadata, and a hash over a
container is a hash that moves when the writer changes its mind about chunk
layout.

The consequence is worth stating in the same breath, because it bounds what a
green verification means. The manifest proves nothing about a file on disk. It
proves that regenerating the description yields the same samples, which is
exactly what the failure above needs: a coefficient that moved changes samples,
not chunk layout.

## The direction the comparison runs

The manifest is the authority and the regenerated signal is the candidate. A
mismatch names the fixture and shows both hashes. The manifest is never quietly
rewritten by a verification; moving it is a separate command whose diff somebody
reads.

## The edge, stated rather than discovered

The comparison is exact to the last bit of the encoding, which is what makes a
coefficient change visible at all. That sensitivity has no floor: the generators
call `math.sin`, `math.log` and `math.tan`, which CPython delegates to the
platform's own maths library, and two libraries may round the last bit of a
transcendental differently. A sample landing within one of those bits of a
quantisation step would then encode differently on the two platforms, and the
mismatch would be reported in the same words as a real one.

Whether that happens between the platforms this project supports is NOT MEASURED
here. It would be measured by regenerating on each and comparing, which is one
command per platform:

    python -m eichstelle.fixtures --write-checksums fixtures/

Nothing in this module hides the case: a mismatch prints both hashes and the
fixture, which is what somebody comparing two platforms needs.
"""

from __future__ import annotations

import hashlib
import json
import re
import struct
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from eichstelle.signals.generator import (
    AMPLITUDE_MODULATED,
    FREQUENCY_MODULATED,
    SINUSOID,
    DescriptionError,
    encode_pcm,
    parse_modulated,
    parse_sinusoid,
    render,
    render_modulated,
)
from eichstelle.signals.noise import (
    BAND_LIMITED_NOISE,
    NOISE,
    parse_noise,
    render_noise,
)

# Where the manifest lives, relative to the fixture root it describes. Beside
# the fixtures rather than inside a source directory, because it is reviewed
# with them. The suffix is not `.json`: the fixture command walks a directory
# for `*.json` and the gate counts the same pattern, so a manifest under that
# name would be handed to the validator as a fixture and refused.
MANIFEST_NAME: Final = "checksums.txt"

# The first line of the manifest. It names a format rather than a version of
# this package, so a manifest written today is readable by a reader that knows
# only what the line says.
MANIFEST_MARKER: Final = "eichstelle-signal-checksums-1"

# The hash. Named in the manifest beside every entry rather than assumed, so
# that a second algorithm is a new prefix and not a silent reinterpretation of
# sixty-four hexadecimal characters.
ALGORITHM: Final = "sha256"

# The header that goes into the hash ahead of the samples. It carries the
# format parameters, so two descriptions that render identical samples at
# different sample rates do not collide.
DIGEST_MARKER: Final = "eichstelle-signal-1"

# One manifest entry: an identifier, a revision and a prefixed hash.
ENTRY: Final = re.compile(
    r"^(?P<id>[a-z0-9]+(?:-[a-z0-9]+)*)"
    r"\s+(?P<revision>[1-9][0-9]*)"
    r"\s+(?P<algorithm>[a-z0-9]+):(?P<digest>[0-9a-f]+)$"
)


class ChecksumError(Exception):
    """The verification did not complete, so its result is unknown."""


@dataclass(frozen=True, order=True)
class Entry:
    """One line of the manifest."""

    fixture_id: str
    revision: int
    digest: str

    def line(self) -> str:
        """Render as the manifest writes it."""
        return f"{self.fixture_id} {self.revision} {ALGORITHM}:{self.digest}"


@dataclass(frozen=True, order=True)
class Mismatch:
    """One reason a fixture and the manifest do not agree."""

    fixture_id: str
    revision: int
    detail: str

    def __str__(self) -> str:
        """Render as one line, naming the fixture a reader has to open."""
        return f"{self.fixture_id} revision {self.revision}: {self.detail}"


def encoding_name(bit_depth: int | None) -> str:
    """What the samples are written as, for the hashed header.

    A description with no `bit_depth` renders floating point in the range minus
    one to plus one, which the hash takes as IEEE 754 doubles. A description
    with one renders integers at that depth. Both names are in the header so
    that the same samples at two encodings are two different hashes, which is
    the honest answer: they are two different stimuli in front of an adapter.
    """
    if bit_depth is None:
        return "float64le"
    return f"pcm_s{bit_depth}le"


def _encoded(samples: list[float], bit_depth: int | None) -> bytes:
    """The samples as the bytes the hash covers."""
    if bit_depth is None:
        return struct.pack(f"<{len(samples)}d", *samples)
    return encode_pcm(samples, bit_depth)


def _rendered(
    description: Mapping[str, object],
) -> tuple[list[float], int, int, int | None]:
    """Render a `signal` object and report its format parameters with it.

    The dispatch is on `kind` and it refuses an unknown one rather than falling
    through to a generator that happens to be to hand. A kind the schema admits
    and this function does not know is a generator that was added without its
    entry here, and the fixture it belongs to would otherwise be hashed by
    whichever branch ran last.
    """
    kind = description.get("kind")
    if kind == SINUSOID:
        sinusoid = parse_sinusoid(description)
        return (
            render(sinusoid),
            sinusoid.sample_rate,
            sinusoid.channels,
            sinusoid.bit_depth,
        )
    if kind in (AMPLITUDE_MODULATED, FREQUENCY_MODULATED):
        modulated = parse_modulated(description)
        return (
            render_modulated(modulated),
            modulated.sample_rate,
            modulated.channels,
            modulated.bit_depth,
        )
    if kind in (NOISE, BAND_LIMITED_NOISE):
        noise = parse_noise(description)
        return (
            render_noise(noise),
            noise.sample_rate,
            noise.channels,
            noise.bit_depth,
        )
    raise DescriptionError(
        f"signal: kind {kind!r} is not one this checksum knows how to render. "
        "A kind arrives with its generator and with its entry here, so that a "
        "fixture is never hashed by whichever branch happened to run"
    )


def digest(description: Mapping[str, object]) -> str:
    """The hash of the samples a `signal` object renders to.

    `DescriptionError` comes out of here where the description cannot be
    rendered. That is a statement about the fixture rather than about the run,
    so callers report it beside a refusal and not as a run that failed.
    """
    samples, sample_rate, channels, bit_depth = _rendered(description)
    encoding = encoding_name(bit_depth)
    frames = len(samples) // channels if channels else 0
    header = (
        f"{DIGEST_MARKER}\n"
        f"sample_rate={sample_rate}\n"
        f"channels={channels}\n"
        f"frames={frames}\n"
        f"encoding={encoding}\n"
    ).encode("ascii")
    running = hashlib.sha256()
    running.update(header)
    running.update(_encoded(samples, bit_depth))
    return running.hexdigest()


def entry_for(document: Mapping[str, object]) -> Entry:
    """The manifest entry a fixture document asks for.

    It reads the three fields it needs and nothing else. The validator is what
    refuses a malformed fixture, and a second opinion here would drift from it.
    """
    fixture_id = document.get("id")
    revision = document.get("revision")
    signal = document.get("signal")
    if not isinstance(fixture_id, str) or not fixture_id:
        raise DescriptionError("no id, so there is nothing to record a hash under")
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
        raise DescriptionError(f"{fixture_id}: revision is {revision!r}")
    if not isinstance(signal, Mapping):
        raise DescriptionError(f"{fixture_id}: no signal object")
    return Entry(fixture_id=fixture_id, revision=revision, digest=digest(signal))


def read_documents(paths: Iterable[Path]) -> dict[str, object]:
    """Read the fixture files, raising rather than skipping one that will not."""
    documents: dict[str, object] = {}
    for path in sorted(paths):
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ChecksumError(f"{path} could not be read: {exc}") from exc
        try:
            documents[str(path)] = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ChecksumError(f"{path} is not JSON: {exc}") from exc
    return documents


def entries_for(documents: Mapping[str, object]) -> list[Entry]:
    """The manifest the given fixtures ask for, sorted and deduplicated.

    A fixture whose signal cannot be rendered raises. Producing a manifest with
    that fixture missing would write a file which then verifies clean, which is
    the shape of quiet failure this whole module is against.
    """
    entries: list[Entry] = []
    for path, document in sorted(documents.items()):
        if not isinstance(document, Mapping):
            raise ChecksumError(f"{path} is not a JSON object")
        try:
            entries.append(entry_for(document))
        except DescriptionError as exc:
            raise ChecksumError(f"{path}: {exc}") from exc
    return sorted(set(entries))


def render_manifest(entries: Sequence[Entry]) -> str:
    """The manifest as it is written to disk.

    One line per fixture so that a regeneration produces a diff naming exactly
    which signals moved, which is the whole reason this is a single tracked file
    rather than a field inside each fixture.
    """
    lines = [
        f"# {MANIFEST_MARKER}",
        "#",
        "# One line per fixture: identifier, revision, and the hash of the samples",
        "# its signal description renders to. The hash covers the samples and the",
        "# format parameters that decide how they are read, and no container byte.",
        "# docs/fixtures.md states exactly what it covers and what it excludes.",
        "#",
        "# This file is the authority and a regenerated signal is the candidate. It",
        "# is moved by one command, and a change to it is explained in the body of",
        "# the pull request that carries it: why the signals moved, and what was",
        "# checked to establish that the new bytes are the right ones.",
        "#",
        "#     python -m eichstelle.fixtures --write-checksums fixtures/",
        "",
    ]
    lines.extend(entry.line() for entry in entries)
    return "\n".join(lines) + "\n"


def parse_manifest(text: str) -> list[Entry]:
    """Read a manifest, refusing anything it cannot account for.

    A line it does not recognise stops it. A manifest is the authority a run is
    held against, so a line skipped as unreadable is a fixture silently
    unchecked, which is worse than no manifest at all.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != f"# {MANIFEST_MARKER}":
        raise ChecksumError(
            f"the manifest does not begin with '# {MANIFEST_MARKER}', so what "
            "format it is in is unknown"
        )
    entries: list[Entry] = []
    seen: dict[tuple[str, int], str] = {}
    for number, line in enumerate(lines[1:], start=2):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = ENTRY.match(stripped)
        if match is None:
            raise ChecksumError(
                f"line {number} of the manifest is not an entry: {stripped!r}"
            )
        if match.group("algorithm") != ALGORITHM:
            raise ChecksumError(
                f"line {number} names hash {match.group('algorithm')!r} and this "
                f"reader knows {ALGORITHM!r}"
            )
        key = (match.group("id"), int(match.group("revision")))
        if key in seen:
            raise ChecksumError(
                f"line {number} repeats {key[0]} revision {key[1]}, which already "
                "has an entry, so which of the two a run is held against is "
                "undecided"
            )
        seen[key] = match.group("digest")
        entries.append(
            Entry(
                fixture_id=key[0],
                revision=key[1],
                digest=match.group("digest"),
            )
        )
    return sorted(entries)


def read_manifest(path: Path) -> list[Entry]:
    """Read the manifest at `path`, failing closed on anything it cannot read."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ChecksumError(
            f"there is no manifest at {path}. Nothing records what these signals "
            "are supposed to be, so nothing can be verified"
        ) from exc
    except OSError as exc:
        raise ChecksumError(f"{path} could not be read: {exc}") from exc
    return parse_manifest(text)


def compare(committed: Sequence[Entry], regenerated: Sequence[Entry]) -> list[Mismatch]:
    """What the manifest and the regenerated signals disagree about.

    Three kinds, and they are three rather than one because they call for
    different responses. A hash that moved is a stimulus that changed. A fixture
    with no entry is one nothing is holding still. An entry with no fixture is a
    line left behind by a deletion, and leaving it would let a later fixture
    reusing that identifier be checked against a stranger's bytes.
    """
    held = {(entry.fixture_id, entry.revision): entry.digest for entry in committed}
    made = {(entry.fixture_id, entry.revision): entry.digest for entry in regenerated}
    mismatches: list[Mismatch] = []
    for key in sorted(set(held) | set(made)):
        fixture_id, revision = key
        if key not in made:
            mismatches.append(
                Mismatch(
                    fixture_id=fixture_id,
                    revision=revision,
                    detail=(
                        "the manifest carries an entry and no fixture under this "
                        f"root claims it. Committed {ALGORITHM}:{held[key]}"
                    ),
                )
            )
            continue
        if key not in held:
            mismatches.append(
                Mismatch(
                    fixture_id=fixture_id,
                    revision=revision,
                    detail=(
                        "no entry in the manifest, so nothing holds this stimulus "
                        f"still. Regenerated {ALGORITHM}:{made[key]}"
                    ),
                )
            )
            continue
        if held[key] != made[key]:
            mismatches.append(
                Mismatch(
                    fixture_id=fixture_id,
                    revision=revision,
                    detail=(
                        "the stimulus moved. "
                        f"Committed {ALGORITHM}:{held[key]}, "
                        f"regenerated {ALGORITHM}:{made[key]}"
                    ),
                )
            )
    return mismatches


def verify(*, manifest: Path, paths: Iterable[Path]) -> list[Mismatch]:
    """Regenerate every fixture's signal and hold it against the manifest.

    This is what runs before any adapter is invoked. It raises `ChecksumError`
    where it could not complete, and returns the disagreements otherwise, so a
    caller can tell a stimulus that moved from a verification that never
    happened.
    """
    committed = read_manifest(manifest)
    regenerated = entries_for(read_documents(paths))
    return compare(committed, regenerated)


def write(
    *, manifest: Path, paths: Iterable[Path]
) -> tuple[list[Entry], list[Mismatch]]:
    """Regenerate the manifest, and report what moved on the way.

    The movement is computed against whatever was committed before the write,
    and against nothing where there was no manifest, so the command can print a
    summary rather than leaving the diff as the only account.
    """
    regenerated = entries_for(read_documents(paths))
    try:
        committed = read_manifest(manifest)
    except ChecksumError:
        committed = []
    moved = compare(committed, regenerated)
    try:
        manifest.parent.mkdir(parents=True, exist_ok=True)
        # The line ending is stated rather than left to the platform. Python's
        # default translation writes CRLF on Windows, `.gitattributes` stores
        # this file with LF, and the difference is not cosmetic here: the
        # command would rewrite every line of the manifest on one platform and
        # none of them on the other, so a diff meant to name which signals moved
        # would name all of them.
        manifest.write_text(
            render_manifest(regenerated), encoding="utf-8", newline="\n"
        )
    except OSError as exc:
        raise ChecksumError(f"{manifest} could not be written: {exc}") from exc
    return regenerated, moved
