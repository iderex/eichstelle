"""An adapter that answers correctly after writing far more than anyone wants.

`tools/fake_adapter.py` covers every behaviour the contract names. This one
covers a behaviour the contract does not name and the runner still has to
survive: an implementation that writes an unbounded quantity of warnings before
it gets to an answer. It lives beside the test that needs it rather than in the
shared fake, because it is about the runner's capture rather than about the
adapter contract, and the shared fake is what an adapter author reads.

How much it writes is read from the environment so that a test can ask for
several times whatever cap it configured, rather than this file and that test
each carrying a number that has to agree.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

BYTES_VARIABLE = "EICHSTELLE_NOISY_BYTES"
DEFAULT_BYTES = 1024 * 1024

# One line, repeated. Its length is a round number so a test can reason about
# the total without counting characters.
LINE = "warning: this adapter is about to say this again" + " " * 16 + "\n"


def shout(stream: Any, total: int) -> None:
    """Write at least `total` bytes to a stream, in whole lines."""
    written = 0
    while written < total:
        stream.write(LINE)
        written += len(LINE)
    stream.flush()


def main(argv: list[str]) -> int:
    """Make a great deal of noise, then answer the job properly."""
    job: dict[str, Any] = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    total = int(os.environ.get(BYTES_VARIABLE, str(DEFAULT_BYTES)))

    shout(sys.stdout, total)
    shout(sys.stderr, total)

    Path(job["result_path"]).write_text(
        json.dumps(
            {
                "protocol_version": 1,
                "fixture_id": job.get("fixture_id", ""),
                "status": "ok",
                "values": ["1.0"],
                "unit": "sone",
                "edition": job.get("edition", 2017),
                "diagnostic": "",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
