"""Suite-wide collection rules.

The suite is split into fast in-process tests and slower end-to-end runs, and
the split has to be usable two ways: by path, which is what a contributor types,
and by marker, which is what a selection expression and a workflow matrix want.

Keeping those two in step by hand is the thing that quietly stops being true. So
the marker is not written on each test at all. It is derived here from the
directory the test was collected from, which means a file that moves takes its
marker with it and a file that is never marked cannot exist.

A test outside both directories is refused rather than left unmarked, because an
unmarked test is one that no selection ever runs and no run ever reports as
missing.
"""

from pathlib import Path

import pytest

TESTS_ROOT = Path(__file__).parent

# The directory name and the marker it implies. Adding a third kind of test
# means adding an entry here and a marker in pyproject.toml, and forgetting
# either one is refused by the collection hook below or by --strict-markers.
DIRECTORY_MARKERS = {
    "unit": "unit",
    "e2e": "e2e",
}


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Mark every collected test from the directory it was collected from."""
    unplaced = []
    for item in items:
        relative = Path(str(item.path)).relative_to(TESTS_ROOT)
        marker = DIRECTORY_MARKERS.get(relative.parts[0]) if relative.parts else None
        if marker is None:
            unplaced.append(str(relative))
            continue
        item.add_marker(getattr(pytest.mark, marker))

    if unplaced:
        known = ", ".join(sorted(DIRECTORY_MARKERS))
        raise pytest.UsageError(
            "these tests sit outside the suite's directories and would carry no "
            f"marker, so no selection would run them: {', '.join(unplaced)}. "
            f"Move each one under tests/<{known}>."
        )
