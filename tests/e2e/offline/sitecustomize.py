"""Load the outbound-network guard into every Python process of a checked run.

CPython imports `sitecustomize` at interpreter start if it can find one on the
import path, and a child process inherits `PYTHONPATH` from its parent. So
putting this directory on `PYTHONPATH` makes the guard beside it reach the
whole process tree of a run, including the adapters the end-to-end tests start
as subprocesses. That is the half a patch applied inside the test session
cannot do, and adapters are exactly the programs a network denial is about.

This file is not imported by the suite in the ordinary way and it is not
imported by anything at all unless a caller put this directory on the path
deliberately.

Nothing here is silent. CPython prints a traceback from a failing
`sitecustomize` and carries on starting the interpreter, which would leave a
run reporting green under a guard that never loaded. So a failure ends the
process instead, with a status nothing else in this tree uses, and the run that
was going to be checked does not happen rather than appearing to have been.
"""

from __future__ import annotations

import os
import sys

# Distinct from anything pytest, the harness or an adapter exits with, so a
# reader who sees it can only be looking at this.
GUARD_DID_NOT_LOAD: int = 78


def _load() -> None:
    """Install the guard, or end this interpreter saying it could not."""
    try:
        import offline_guard

        offline_guard.install()
    # A bare catch, because the alternative is an interpreter that starts
    # anyway and a run that reports green under a guard that never loaded.
    except BaseException as exc:
        sys.stderr.write(
            f"the offline guard could not be installed, so this process is not "
            f"the checked one it was started as: {exc!r}\n"
        )
        sys.stderr.flush()
        os._exit(GUARD_DID_NOT_LOAD)


_load()
