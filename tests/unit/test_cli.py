"""The console entry point, exercised in process.

This is the test the issue asks for when it asks for one that exercises real
project code rather than asserting a constant. It imports the function the
packaging metadata names, runs it, and compares what it printed against the
version the installed distribution reports. Break `main` and this goes red.
"""

from importlib.metadata import version

import pytest

from eichstelle import __version__
from eichstelle.cli import main


def test_main_prints_the_version_and_returns_zero(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The entry point prints exactly the version and reports success."""
    exit_code = main()
    printed = capsys.readouterr()

    assert exit_code == 0
    assert printed.out == f"{__version__}\n"
    assert printed.err == ""


def test_the_package_version_comes_from_the_installed_distribution() -> None:
    """`__version__` is read from the install rather than written in the source.

    The docstring in `eichstelle/__init__.py` claims this, and the claim is what
    keeps a version from being wrong in two places at once. A literal reinstated
    in the source would pass an equality test against itself, so the comparison
    here is against the metadata the packaging tool wrote.
    """
    assert __version__ == version("eichstelle")
