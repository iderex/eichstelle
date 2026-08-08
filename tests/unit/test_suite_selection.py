"""The split between fast and slow tests, checked rather than assumed.

`tests/conftest.py` derives a marker from the directory a test was collected
from. If that hook stops running, every selection built on `-m unit` or `-m e2e`
starts matching nothing, and a run that selects nothing exits reporting no
failures. That is the shape of a suite that cannot fail, so the mechanism gets
its own test.

Both tests here run pytest as a subprocess against a tree they build in
`tmp_path`. A fixture vocabulary rather than this repository's own suite: a test
that inspects the real tests directory reports the state of the tree on the day
it ran, not the state of the hook.
"""

import subprocess
import sys
from pathlib import Path

import pytest

CONFTEST = Path(__file__).parent.parent / "conftest.py"

MARKER_REPORT = """
def test_reports_its_own_markers(request):
    names = sorted(m.name for m in request.node.iter_markers())
    print("MARKERS=" + ",".join(names))
    assert names
"""

UNPLACED = """
def test_sits_in_no_directory():
    assert True
"""


def run_pytest(tree: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    """Run pytest against a fixture tree, isolated from this repository's config."""
    return subprocess.run(  # noqa: S603
        [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "no:cacheprovider",
            "-s",
            str(tree),
            *arguments,
        ],
        capture_output=True,
        text=True,
        cwd=tree,
        check=False,
    )


def build_tree(root: Path, *, directory: str) -> Path:
    """Write a minimal suite carrying the hook and one test in `directory`."""
    tests = root / "tests"
    (tests / directory).mkdir(parents=True)
    (tests / "conftest.py").write_text(CONFTEST.read_text(encoding="utf-8"), "utf-8")
    (tests / directory / "test_marked.py").write_text(MARKER_REPORT, "utf-8")
    (root / "pytest.ini").write_text(
        "[pytest]\nmarkers =\n    unit: fast\n    e2e: slow\naddopts = --strict-markers\n",
        "utf-8",
    )
    return tests


@pytest.mark.parametrize("directory", ["unit", "e2e"])
def test_a_test_is_marked_from_the_directory_it_lives_in(
    tmp_path: Path, directory: str
) -> None:
    """A test under tests/<name> carries the marker <name> without being written."""
    tests = build_tree(tmp_path, directory=directory)

    result = run_pytest(tests)

    assert f"MARKERS={directory}" in result.stdout, result.stdout
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("directory", ["unit", "e2e"])
def test_the_marker_selects(tmp_path: Path, directory: str) -> None:
    """Selecting by marker runs the matching test and skips the other kind."""
    tests = build_tree(tmp_path, directory=directory)
    other = "e2e" if directory == "unit" else "unit"

    selected = run_pytest(tests, "-m", directory)
    rejected = run_pytest(tests, "-m", other)

    assert "1 passed" in selected.stdout, selected.stdout
    assert "1 deselected" in rejected.stdout, rejected.stdout


def test_a_test_outside_both_directories_is_refused(tmp_path: Path) -> None:
    """An unplaced test stops the run instead of being collected unmarked.

    Without this the hook would fall back to leaving the test alone, and a file
    dropped straight into tests/ would run under no marker: invisible to every
    selection and reported as missing by nothing.
    """
    tests = build_tree(tmp_path, directory="unit")
    (tests / "test_unplaced.py").write_text(UNPLACED, "utf-8")

    result = run_pytest(tests)

    assert result.returncode != 0
    assert "test_unplaced.py" in result.stdout + result.stderr
    assert "sit outside the suite's directories" in result.stdout + result.stderr
