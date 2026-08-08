"""An adapter whose diagnostic is written to be dangerous rather than helpful.

Adapter text is arbitrary bytes from a foreign program. The runner stores it as
data, and the property worth testing is that what comes back out is what went
in, unchanged and unexecuted, so that a later stage cannot be handed something
that was already half-interpreted.

Every hostile character is written here as an escape rather than as itself. The
tracked bytes of this file stay plain ASCII, which keeps it out of the way of
the guard against bidirectional and invisible Unicode and out of the way of the
line-ending normalisation that would otherwise delete the carriage return this
file exists to send. The string that reaches the runner is assembled at run time
and is not what a reader of this file sees, which is the point.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

# One string carrying, in order: a shell substitution, a shell backtick, a
# format specifier for two different formatting mechanisms, a template
# placeholder, an ANSI escape that would recolour a terminal and move its
# cursor, a carriage return that would overwrite a line, a null byte, a
# terminator for a JSON string, one for an HTML attribute, and a script tag.
HOSTILE = (
    "$(rm -rf /) "
    "`id` "
    "%s %(name)s {0} {name} ${placeholder} "
    "\x1b[31m\x1b[2K\x1b[1A "
    "line one\rline two "
    "\x00 "
    '" }] '
    "'><script>alert(1)</script> "
    "\\n not a newline"
)


def main(argv: list[str]) -> int:
    """Answer the job properly, with the diagnostic carrying all of the above."""
    job: dict[str, Any] = json.loads(Path(argv[1]).read_text(encoding="utf-8"))

    sys.stderr.write(HOSTILE)
    sys.stderr.flush()

    Path(job["result_path"]).write_text(
        json.dumps(
            {
                "protocol_version": 1,
                "fixture_id": job.get("fixture_id", ""),
                "status": "ok",
                "values": ["1.0"],
                "unit": "sone",
                "edition": job.get("edition", 2017),
                "diagnostic": HOSTILE,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
