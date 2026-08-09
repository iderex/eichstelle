"""An adapter that answers with whatever value it is told to answer with.

`tools/fake_adapter.py` answers one constant, which is what a test about the
contract needs. A test about the spread between implementations needs several
adapters answering several different values, and a fake that could only answer
one would make every differential run agree with itself.

It lives beside the tests that need it rather than in the shared fake, because
the shared fake is the worked example an adapter author reads and an adapter
whose answer comes from the environment is not an example of anything.

The value is read from the environment rather than taken as a flag, so the
invocation shape stays the one the contract states: one argument, the path to
the job document, and nothing else.

    EICHSTELLE_VALUED_ADAPTER_VALUE     the decimal string to answer with
    EICHSTELLE_VALUED_ADAPTER_UNIT      the unit to answer in, default sone
    EICHSTELLE_VALUED_ADAPTER_VERSION   the upstream version to declare

Nothing here computes anything. The point of it is that the number a run
compares came from outside this harness, across a process boundary, in the same
shape a real implementation's would.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

VALUE_VARIABLE = "EICHSTELLE_VALUED_ADAPTER_VALUE"
UNIT_VARIABLE = "EICHSTELLE_VALUED_ADAPTER_UNIT"
VERSION_VARIABLE = "EICHSTELLE_VALUED_ADAPTER_VERSION"

DEFAULT_UNIT = "sone"
DEFAULT_VERSION = "0.0.1"


def declaration() -> dict[str, Any]:
    """What this adapter claims, which is loudness under one edition."""
    return {
        "protocol_version": 1,
        "status": "ok",
        "diagnostic": "",
        "upstream_version": os.environ.get(VERSION_VARIABLE, DEFAULT_VERSION),
        "sample_rates": [48000],
        "capabilities": [
            {
                "metric": "loudness",
                "editions": [2017],
                "field_conditions": ["free"],
                "calibration_conventions": ["full_scale_sine"],
            }
        ],
    }


def measurement(job: dict[str, Any]) -> dict[str, Any]:
    """The answer, which is the environment's number and never a computation."""
    return {
        "protocol_version": 1,
        "fixture_id": job.get("fixture_id", ""),
        "status": "ok",
        "values": [os.environ[VALUE_VARIABLE]],
        "unit": os.environ.get(UNIT_VARIABLE, DEFAULT_UNIT),
        "edition": job.get("edition", 2017),
        "diagnostic": "",
    }


def main(argv: list[str]) -> int:
    """Read the job, write the result the contract asks for, exit zero."""
    job: dict[str, Any] = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    answer = declaration() if job.get("kind") == "capabilities" else measurement(job)
    Path(job["result_path"]).write_text(json.dumps(answer, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
