"""The installed console script, run as a process.

`pyproject.toml` declares one entry point and says it exists so that the
packaging is proven by something that runs rather than by something that
imports. An import test cannot tell a working entry point from a missing one,
because the import path is the source tree either way.

So this runs the executable the install wrote, and it fails rather than skips
when that executable is not there. Not finding it is exactly the packaging
defect this test exists for, and a skip would report that defect as an absence
of information.

The end-to-end directory starts here with one member. Milestone 4 fills it with
runs through the fake adapter, and the split it needs is already in place.
"""

import os
import subprocess
import sysconfig
from pathlib import Path

from eichstelle import __version__


def console_script() -> Path:
    """The path the install wrote for the `eichstelle` entry point."""
    scripts = Path(sysconfig.get_path("scripts"))
    name = "eichstelle.exe" if os.name == "nt" else "eichstelle"
    return scripts / name


def test_the_console_script_prints_the_version_and_exits_zero() -> None:
    """The installed command runs, prints the version and reports success."""
    executable = console_script()
    assert executable.exists(), (
        f"no console script at {executable}. The suite runs against an install: "
        "python -m pip install -e . --group dev"
    )

    result = subprocess.run(  # noqa: S603
        [str(executable)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == __version__
    assert result.stderr == ""
