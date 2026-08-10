"""The signal checksums, and the mismatch that stops a run.

A fixture describes its stimulus rather than shipping it, so the bytes an
adapter is handed depend on the code that rendered them. The manifest is what
holds that still, and these are the assertions that make it a fact rather than a
hope.

What is asserted here, and why each one is a way the manifest goes quietly
wrong:

- the hash covers exactly what the documentation says it covers, recomputed here
  from the parts rather than compared against a constant somebody pasted
- a description that moved is caught, which is the whole purpose
- a fixture with no entry, and an entry with no fixture, are each reported and
  are not the same report as a hash that moved
- a manifest this reader cannot account for stops it, because a line skipped as
  unreadable is a fixture silently unchecked
- the committed tree verifies, so the tracked manifest is not a file that has
  drifted from the fixtures beside it
"""

import hashlib
import json
import struct
from pathlib import Path
from typing import Any

import pytest

from eichstelle.fixtures import checksums
from eichstelle.signals.generator import (
    DescriptionError,
    encode_pcm,
    parse_sinusoid,
    render,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
TRACKED_FIXTURE_ROOT = REPOSITORY_ROOT / "fixtures"

TONE: dict[str, Any] = {
    "kind": "sinusoid",
    "sample_rate": 8000,
    "channels": 1,
    "duration_seconds": "0.05",
    "parameters": {
        "frequency_hz": "1000.0",
        "level_db_spl": "40.0",
        "calibration_reference_db_spl": "94.0",
        "fade": {"shape": "raised_cosine", "duration_seconds": "0.005"},
    },
}

NOISE: dict[str, Any] = {
    "kind": "noise",
    "sample_rate": 8000,
    "channels": 1,
    "duration_seconds": "0.05",
    "parameters": {
        "random_algorithm": "xoshiro256plusplus",
        "random_seed": 7,
        "spectral_shape": "white",
        "level_db_spl": "40.0",
        "calibration_reference_db_spl": "94.0",
        "fade": {"shape": "linear", "duration_seconds": "0.005"},
    },
}


def fixture_document(fixture_id: str, signal: dict[str, Any]) -> dict[str, Any]:
    """A fixture document carrying the three fields the manifest reads."""
    return {"id": fixture_id, "revision": 1, "signal": signal}


def write_fixture(directory: Path, name: str, document: object) -> Path:
    """Write one fixture file and return its path."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(json.dumps(document, indent=2), encoding="utf-8")
    return path


def test_the_hash_covers_the_samples_and_the_format_parameters() -> None:
    """Recomputed from the parts, so the documentation is checkable rather than trusted.

    This is the assertion that makes `docs/fixtures.md` a description of what
    happens. Everything the hash is claimed to cover is put in by hand here, and
    a change to the header or to the encoding that is not also a change to that
    document fails.
    """
    samples = render(parse_sinusoid(TONE))
    expected = hashlib.sha256()
    expected.update(
        (
            "eichstelle-signal-1\n"
            "sample_rate=8000\n"
            "channels=1\n"
            f"frames={len(samples)}\n"
            "encoding=float64le\n"
        ).encode("ascii")
    )
    expected.update(struct.pack(f"<{len(samples)}d", *samples))

    assert checksums.digest(TONE) == expected.hexdigest()


def test_an_integer_depth_hashes_the_encoded_samples() -> None:
    """A stated bit depth is a different stimulus, and hashes as one.

    The same tone at sixteen bits and as floating point are two different sets
    of bytes in front of an adapter, so they are two different hashes. Reading
    them as one would let a fixture change what it hands over without moving its
    entry.
    """
    at_depth = dict(TONE, bit_depth=16)
    samples = render(parse_sinusoid(at_depth))
    expected = hashlib.sha256()
    expected.update(
        (
            "eichstelle-signal-1\n"
            "sample_rate=8000\n"
            "channels=1\n"
            f"frames={len(samples)}\n"
            "encoding=pcm_s16le\n"
        ).encode("ascii")
    )
    expected.update(encode_pcm(samples, 16))

    assert checksums.digest(at_depth) == expected.hexdigest()
    assert checksums.digest(at_depth) != checksums.digest(TONE)


def test_the_hash_is_the_same_on_two_calls() -> None:
    """A hash that moved between two calls of one process would refuse everything."""
    assert checksums.digest(NOISE) == checksums.digest(NOISE)


def test_a_kind_with_no_entry_in_the_dispatch_is_refused() -> None:
    """A generator added without its line here would otherwise hash by fallthrough."""
    with pytest.raises(DescriptionError, match="not one this checksum knows"):
        checksums.digest(dict(TONE, kind="square_wave"))


def test_an_altered_signal_description_is_caught(tmp_path: Path) -> None:
    """The assertion the whole manifest exists for.

    A frequency moved in its seventh decimal place is a stimulus nobody would
    see by reading the fixture, and it is what a regenerated signal is held
    against. The mismatch names the fixture and shows both hashes, so an
    investigation starts at the stimulus rather than at the implementations.
    """
    root = tmp_path / "fixtures"
    path = write_fixture(root, "tone.json", fixture_document("tone", TONE))
    checksums.write(manifest=root / checksums.MANIFEST_NAME, paths=[path])

    moved = json.loads(json.dumps(TONE))
    moved["parameters"]["frequency_hz"] = "1000.0000001"
    write_fixture(root, "tone.json", fixture_document("tone", moved))

    mismatches = checksums.verify(manifest=root / checksums.MANIFEST_NAME, paths=[path])

    assert len(mismatches) == 1
    assert mismatches[0].fixture_id == "tone"
    assert "the stimulus moved" in mismatches[0].detail
    assert checksums.digest(TONE) in mismatches[0].detail
    assert checksums.digest(moved) in mismatches[0].detail


def test_a_signal_that_did_not_move_verifies(tmp_path: Path) -> None:
    """The other half of the same claim: an unchanged description is not reported."""
    root = tmp_path / "fixtures"
    tone = write_fixture(root, "tone.json", fixture_document("tone", TONE))
    noise = write_fixture(root, "noise.json", fixture_document("noise", NOISE))
    checksums.write(manifest=root / checksums.MANIFEST_NAME, paths=[tone, noise])

    assert (
        checksums.verify(manifest=root / checksums.MANIFEST_NAME, paths=[tone, noise])
        == []
    )


def test_a_fixture_with_no_entry_is_reported_as_unheld(tmp_path: Path) -> None:
    """Nothing holds a stimulus nobody recorded, and that is not a hash that moved."""
    root = tmp_path / "fixtures"
    tone = write_fixture(root, "tone.json", fixture_document("tone", TONE))
    checksums.write(manifest=root / checksums.MANIFEST_NAME, paths=[tone])
    noise = write_fixture(root, "noise.json", fixture_document("noise", NOISE))

    mismatches = checksums.verify(
        manifest=root / checksums.MANIFEST_NAME, paths=[tone, noise]
    )

    assert [mismatch.fixture_id for mismatch in mismatches] == ["noise"]
    assert "no entry in the manifest" in mismatches[0].detail


def test_an_entry_with_no_fixture_is_reported(tmp_path: Path) -> None:
    """A line left behind by a deletion.

    Left in place it would hold a later fixture reusing that identifier against
    a stranger's bytes, which is a refusal nobody could explain.
    """
    root = tmp_path / "fixtures"
    tone = write_fixture(root, "tone.json", fixture_document("tone", TONE))
    noise = write_fixture(root, "noise.json", fixture_document("noise", NOISE))
    checksums.write(manifest=root / checksums.MANIFEST_NAME, paths=[tone, noise])
    noise.unlink()

    mismatches = checksums.verify(manifest=root / checksums.MANIFEST_NAME, paths=[tone])

    assert [mismatch.fixture_id for mismatch in mismatches] == ["noise"]
    assert "no fixture under this root claims it" in mismatches[0].detail


def test_the_manifest_round_trips() -> None:
    """What is written is what is read, so the file is not a one-way format."""
    entries = [
        checksums.Entry(fixture_id="b-tone", revision=2, digest="ab" * 32),
        checksums.Entry(fixture_id="a-tone", revision=1, digest="cd" * 32),
    ]

    read_back = checksums.parse_manifest(checksums.render_manifest(sorted(entries)))

    assert read_back == sorted(entries)


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("a-tone 1 sha256:" + "ab" * 32 + "\n", "does not begin with"),
        ("# eichstelle-signal-checksums-1\nnonsense\n", "is not an entry"),
        (
            "# eichstelle-signal-checksums-1\na-tone 1 md5:" + "ab" * 16 + "\n",
            "this reader knows",
        ),
        (
            "# eichstelle-signal-checksums-1\n"
            "a-tone 1 sha256:" + "ab" * 32 + "\n"
            "a-tone 1 sha256:" + "cd" * 32 + "\n",
            "repeats",
        ),
    ],
)
def test_a_manifest_this_reader_cannot_account_for_stops_it(
    text: str, reason: str
) -> None:
    """Fails closed rather than skipping the line it did not understand."""
    with pytest.raises(checksums.ChecksumError, match=reason):
        checksums.parse_manifest(text)


def test_an_absent_manifest_is_a_run_that_did_not_complete(tmp_path: Path) -> None:
    """Not a clean result. Nothing records what the signals are supposed to be."""
    with pytest.raises(checksums.ChecksumError, match="there is no manifest"):
        checksums.read_manifest(tmp_path / checksums.MANIFEST_NAME)


def test_a_fixture_whose_signal_will_not_render_stops_the_write(tmp_path: Path) -> None:
    """Writing a manifest with that fixture missing produces a file that verifies clean."""
    root = tmp_path / "fixtures"
    broken = json.loads(json.dumps(TONE))
    del broken["parameters"]["calibration_reference_db_spl"]
    path = write_fixture(root, "broken.json", fixture_document("broken", broken))

    with pytest.raises(checksums.ChecksumError, match=r"broken.json"):
        checksums.write(manifest=root / checksums.MANIFEST_NAME, paths=[path])


def test_writing_reports_what_moved(tmp_path: Path) -> None:
    """The command prints a summary rather than leaving the diff as the only account."""
    root = tmp_path / "fixtures"
    path = write_fixture(root, "tone.json", fixture_document("tone", TONE))
    checksums.write(manifest=root / checksums.MANIFEST_NAME, paths=[path])

    moved_signal = json.loads(json.dumps(TONE))
    moved_signal["parameters"]["level_db_spl"] = "60.0"
    write_fixture(root, "tone.json", fixture_document("tone", moved_signal))
    entries, moved = checksums.write(
        manifest=root / checksums.MANIFEST_NAME, paths=[path]
    )

    assert [entry.fixture_id for entry in entries] == ["tone"]
    assert [mismatch.fixture_id for mismatch in moved] == ["tone"]
    assert "the stimulus moved" in moved[0].detail
    assert checksums.verify(manifest=root / checksums.MANIFEST_NAME, paths=[path]) == []


def test_a_mismatch_reads_as_one_line_naming_the_fixture() -> None:
    """What a reader sees first is the identifier and the revision."""
    mismatch = checksums.Mismatch(
        fixture_id="tone", revision=3, detail="the stimulus moved"
    )

    assert str(mismatch) == "tone revision 3: the stimulus moved"


@pytest.mark.parametrize(
    "signal",
    [
        {
            "kind": "amplitude_modulated_sinusoid",
            "sample_rate": 8000,
            "channels": 1,
            "duration_seconds": "0.05",
            "parameters": {
                "carrier_frequency_hz": "1000.0",
                "modulation_frequency_hz": "4.0",
                "modulation_depth": "1.0",
                "level_db_spl": "60.0",
                "level_convention": "carrier",
                "calibration_reference_db_spl": "94.0",
                "fade": {"shape": "linear", "duration_seconds": "0.005"},
            },
        },
        {
            "kind": "band_limited_noise",
            "sample_rate": 8000,
            "channels": 1,
            "duration_seconds": "0.05",
            "parameters": {
                "random_algorithm": "xoshiro256plusplus",
                "random_seed": 3,
                "low_edge_hz": "800.0",
                "high_edge_hz": "1200.0",
                "filter_type": "butterworth",
                "filter_order": 4,
                "level_db_spl": "40.0",
                "calibration_reference_db_spl": "94.0",
                "fade": {"shape": "linear", "duration_seconds": "0.005"},
            },
        },
    ],
    ids=["amplitude_modulated_sinusoid", "band_limited_noise"],
)
def test_every_generator_this_tree_carries_has_a_hash(signal: dict[str, Any]) -> None:
    """A kind with a generator and no line in the dispatch would refuse instead.

    The sinusoid and the broadband noise are exercised above. These are the two
    remaining branches, so every kind the schema admits is reached by something
    here rather than by whichever fixture happens to arrive first.
    """
    assert len(checksums.digest(signal)) == 64


@pytest.mark.parametrize(
    ("document", "reason"),
    [
        ({"revision": 1, "signal": TONE}, "nothing to record a hash under"),
        ({"id": "tone", "revision": 0, "signal": TONE}, "revision is 0"),
        ({"id": "tone", "revision": True, "signal": TONE}, "revision is True"),
        ({"id": "tone", "revision": 1}, "no signal object"),
    ],
    ids=["no id", "revision below one", "a boolean revision", "no signal"],
)
def test_a_document_with_nothing_to_hash_is_refused(
    document: dict[str, Any], reason: str
) -> None:
    """Three fields are read and each absence is named rather than defaulted."""
    with pytest.raises(DescriptionError, match=reason):
        checksums.entry_for(document)


def test_a_path_that_cannot_be_read_stops_the_run(tmp_path: Path) -> None:
    """Not a fixture that is skipped: a verification that did not happen."""
    with pytest.raises(checksums.ChecksumError, match="could not be read"):
        checksums.read_documents([tmp_path / "absent.json"])


def test_a_file_that_is_not_json_stops_the_run(tmp_path: Path) -> None:
    """The validator is where that becomes a refusal; here it is unknown."""
    path = tmp_path / "notes.json"
    path.write_text("this is not JSON", encoding="utf-8")

    with pytest.raises(checksums.ChecksumError, match="is not JSON"):
        checksums.read_documents([path])


def test_a_json_file_that_is_not_an_object_stops_the_run(tmp_path: Path) -> None:
    """A list of fixtures is not a fixture, and hashing it would hash nothing."""
    path = tmp_path / "list.json"
    path.write_text("[]", encoding="utf-8")

    with pytest.raises(checksums.ChecksumError, match="is not a JSON object"):
        checksums.entries_for(checksums.read_documents([path]))


def test_a_manifest_that_cannot_be_read_stops_the_run(tmp_path: Path) -> None:
    """A directory where the manifest should be is not an absent manifest."""
    (tmp_path / checksums.MANIFEST_NAME).mkdir()

    with pytest.raises(checksums.ChecksumError, match="could not be read"):
        checksums.read_manifest(tmp_path / checksums.MANIFEST_NAME)


def test_the_manifest_is_written_with_one_line_ending(tmp_path: Path) -> None:
    """No carriage return, on any platform.

    `.gitattributes` stores this file with line feeds. Python's default
    translation writes carriage returns on one of the platforms this project
    declares support for, and the command would then rewrite every line of the
    manifest there and none of them elsewhere. A diff meant to name which
    signals moved would name all of them.
    """
    root = tmp_path / "fixtures"
    path = write_fixture(root, "tone.json", fixture_document("tone", TONE))
    checksums.write(manifest=root / checksums.MANIFEST_NAME, paths=[path])

    assert b"\r" not in (root / checksums.MANIFEST_NAME).read_bytes()


def test_a_manifest_that_cannot_be_written_stops_the_run(tmp_path: Path) -> None:
    """Reported rather than swallowed, so nothing believes a write happened."""
    root = tmp_path / "fixtures"
    path = write_fixture(root, "tone.json", fixture_document("tone", TONE))
    (root / checksums.MANIFEST_NAME).mkdir()

    with pytest.raises(checksums.ChecksumError, match="could not be written"):
        checksums.write(manifest=root / checksums.MANIFEST_NAME, paths=[path])


def test_the_committed_tree_verifies() -> None:
    """The tracked manifest agrees with the tracked fixtures.

    It passes over an empty set today, and that is a statement about the tree
    rather than about this test: no fixture is tracked under `fixtures/` at this
    commit, which is issue #26. The assertion is here now so that the first
    fixture to land is covered by having been added.
    """
    tracked = sorted(TRACKED_FIXTURE_ROOT.rglob("*.json"))
    manifest = TRACKED_FIXTURE_ROOT / checksums.MANIFEST_NAME

    assert manifest.is_file(), f"{manifest} is not tracked"
    assert checksums.verify(manifest=manifest, paths=tracked) == []
