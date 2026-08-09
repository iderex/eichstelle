"""The command the mutation workflow runs, run as a process.

The unit tests reach the score reader through its functions. What a workflow
step runs is a command, and a command has an exit code and a stream each message
goes to. Neither is exercised by calling a function, and the exit code is the
whole mechanism here: it is what turns a broken mutation run into a red job and
a low score into a quiet one.

The deliberately broken tool is the case worth running as a process. A mutation
run that fell over writes no stats document, and this is what the workflow does
about that.
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

SCRIPT = Path(__file__).resolve().parents[2] / "tools" / "mutation_score.py"


def stats_file(directory: Path, **counts: int) -> Path:
    """Write a stats document of the shape the mutation tool exports."""
    document: dict[str, Any] = {
        "killed": 0,
        "survived": 0,
        "total": 0,
        "no_tests": 0,
        "skipped": 0,
        "suspicious": 0,
        "timeout": 0,
        "segfault": 0,
        "check_was_interrupted_by_user": False,
    }
    document.update(counts)
    path = directory / "mutmut-cicd-stats.json"
    path.write_text(json.dumps(document, indent=4), encoding="utf-8")
    return path


def run(*arguments: str) -> subprocess.CompletedProcess[str]:
    """Run the script with the interpreter running this suite."""
    return subprocess.run(  # noqa: S603
        [sys.executable, str(SCRIPT), *arguments],
        capture_output=True,
        text=True,
        check=False,
    )


def test_a_score_is_printed_and_the_command_exits_zero(tmp_path: Path) -> None:
    """A run with a number in it reports it on stdout and succeeds."""
    finished = run(str(stats_file(tmp_path, killed=3, survived=1, total=4)))

    assert finished.returncode == 0, finished.stderr
    assert "mutation score: 75.00%" in finished.stdout
    assert finished.stderr == ""


def test_a_score_of_zero_still_exits_zero(tmp_path: Path) -> None:
    """The lowest possible number is a finding and not a failing command."""
    finished = run(str(stats_file(tmp_path, killed=0, survived=9, total=9)))

    assert finished.returncode == 0, finished.stderr
    assert "mutation score: 0.00%" in finished.stdout


def test_a_run_that_produced_nothing_exits_two_and_says_so(tmp_path: Path) -> None:
    """The broken-tool case: no stats document, a red job, a reason on stderr."""
    finished = run(str(tmp_path / "mutants" / "mutmut-cicd-stats.json"))

    assert finished.returncode == 2
    assert finished.stdout == ""
    assert "no mutation score" in finished.stderr
    assert "did not produce a score" in finished.stderr


def test_a_truncated_stats_document_exits_two(tmp_path: Path) -> None:
    """A run killed part way through leaves half a file, which is not a score."""
    path = tmp_path / "mutmut-cicd-stats.json"
    path.write_text('{\n    "killed": 12,\n    "surv', encoding="utf-8")

    finished = run(str(path))

    assert finished.returncode == 2
    assert "is not JSON" in finished.stderr
