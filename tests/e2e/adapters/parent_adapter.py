"""An adapter that starts a long-lived child and then hangs.

This is the MATLAB case in miniature. A real adapter for a licensed toolbox
launches a second runtime, and terminating the adapter alone leaves that runtime
holding the machine for the rest of the run, which turns the next fixture's
timing into somebody's conformance finding.

The child writes its process identifier to a file the test names, so the test
can ask the operating system afterwards whether it is still there rather than
inferring it from timing.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

PID_FILE_VARIABLE = "EICHSTELLE_CHILD_PID_FILE"

# Long enough that nothing here ends on its own inside any test's patience, so a
# process that is still running afterwards was not reached rather than not yet
# finished.
CHILD_SECONDS = 600
PARENT_SECONDS = 600


def main(argv: list[str]) -> int:
    """Start a child that sleeps, record it, and then sleep past the limit."""
    json.loads(Path(argv[1]).read_text(encoding="utf-8"))

    child = subprocess.Popen(  # noqa: S603 - this interpreter, sleeping
        [sys.executable, "-c", f"import time; time.sleep({CHILD_SECONDS})"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        shell=False,
    )

    pid_file = os.environ.get(PID_FILE_VARIABLE)
    if pid_file:
        Path(pid_file).write_text(str(child.pid), encoding="utf-8")

    time.sleep(PARENT_SECONDS)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
