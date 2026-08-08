"""The command a gate would run, run as a process.

The unit tests reach the validator through its Python API. What a check runs is
a command, and a command has an exit code, a stream each message goes to, and a
behaviour when it is pointed at nothing. None of those is exercised by calling a
function, and each of them is a way a check passes while proving nothing.
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

VALID: dict[str, Any] = {
    "id": "example-tone-at-forty-decibels",
    "revision": 1,
    "schema_version": 1,
    "title": "a 1 kHz sinusoid at 40 dB SPL",
    "signal": {
        "kind": "sinusoid",
        "sample_rate": 48000,
        "channels": 1,
        "duration_seconds": "2.0",
        "parameters": {
            "frequency_hz": "1000.0",
            "level_db_spl": "40.0",
            "calibration_reference_db_spl": "94.0",
            "fade": {"shape": "raised_cosine", "duration_seconds": "0.05"},
        },
    },
    "metric": "loudness",
    "metric_parameters": {"field_condition": "free"},
    "expected": "1.0",
    "unit": "sone",
    "tolerance": "0.05",
    "tolerance_kind": "absolute",
    "standard": {
        "designation": "ISO 532",
        "part": "1",
        "edition_year": 2017,
        "clause": "4.1",
    },
    "provenance": "generated-by-definition",
}


def run_check(*arguments: str) -> subprocess.CompletedProcess[str]:
    """Run the fixture check the way a gate would."""
    return subprocess.run(  # noqa: S603
        [sys.executable, "-m", "eichstelle.fixtures", *arguments],
        capture_output=True,
        text=True,
        check=False,
    )


def write(directory: Path, name: str, document: object) -> None:
    """Write one fixture file."""
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text(json.dumps(document, indent=2), encoding="utf-8")


def test_a_directory_of_valid_fixtures_passes(tmp_path: Path) -> None:
    """Exit zero, and the count on stdout so a log says what was examined."""
    write(tmp_path / "fixtures", "tone.json", VALID)

    result = run_check(str(tmp_path / "fixtures"))

    assert result.returncode == 0, result.stderr
    assert "1 fixture(s) valid" in result.stdout


def test_a_malformed_fixture_reddens_the_check(tmp_path: Path) -> None:
    """Exit one, with the reason on stderr and the file named."""
    broken = json.loads(json.dumps(VALID))
    del broken["tolerance"]
    write(tmp_path / "fixtures", "broken.json", broken)

    result = run_check(str(tmp_path / "fixtures"))

    assert result.returncode == 1
    assert "broken.json" in result.stderr
    assert "tolerance" in result.stderr


def test_a_file_that_is_not_json_is_refused_rather_than_skipped(tmp_path: Path) -> None:
    """A file that reads and is not JSON was seen, and it is not a fixture."""
    (tmp_path / "fixtures").mkdir()
    (tmp_path / "fixtures" / "notes.json").write_text("this is not JSON", "utf-8")

    result = run_check(str(tmp_path / "fixtures"))

    assert result.returncode == 1
    assert "not valid JSON" in result.stderr


def test_a_directory_holding_no_fixture_does_not_report_a_clean_run(
    tmp_path: Path,
) -> None:
    """Exit two rather than zero.

    Zero over an empty directory is the failure this whole check exists against
    in miniature: a path typo, a moved fixture root, and a green check that
    examined nothing prints the same success a real run does.
    """
    (tmp_path / "fixtures").mkdir()

    result = run_check(str(tmp_path / "fixtures"))

    assert result.returncode == 2
    assert "Refusing to report a clean run over nothing" in result.stderr


def test_a_path_that_cannot_be_read_fails_closed(tmp_path: Path) -> None:
    """A named file that is not there is exit two, never a clean result."""
    result = run_check(str(tmp_path / "missing.json"))

    assert result.returncode == 2
    assert "did not complete" in result.stderr
    assert "failing closed" in result.stderr


def test_no_argument_is_refused() -> None:
    """Called with nothing, it says how to call it and exits two."""
    result = run_check()

    assert result.returncode == 2
    assert "usage:" in result.stderr
