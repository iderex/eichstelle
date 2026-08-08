"""Running an adapter, and recording what it did rather than reacting to it.

The adapter boundary is a process and two JSON documents, which decision record
0006 chose so that this project never loads a third party's numeric code into
its own interpreter. What that buys is containment, and this package is where
the containment is actually implemented: a fresh directory per invocation, a
bound on captured output, a limit with a two-step stop behind it, and a mapping
from every way an invocation can end onto record 0007's vocabulary.

Nothing an adapter does raises out of `invoke`. That is the property the rest of
the harness is built on, and it is why a run over a hundred fixtures against a
library that falls over on one of them still produces ninety-nine results.
"""

from eichstelle.runner.runner import (
    ADAPTER_ERROR,
    CRASHED,
    DEFAULT_CONCURRENCY,
    DEFAULT_GRACE_SECONDS,
    DEFAULT_OUTPUT_CAP_BYTES,
    ERRORED,
    KILLED,
    MALFORMED_RESULT,
    MEASURED,
    NO_RESULT,
    PROTOCOL_VERSION,
    TERMINATED,
    TERMINATION_REACHES_CHILDREN,
    TIMED_OUT,
    UNSUPPORTED,
    Capture,
    Invocation,
    RunnerConfiguration,
    RunnerError,
    invoke,
    invoke_all,
    python_adapter,
)

__all__ = [
    "ADAPTER_ERROR",
    "CRASHED",
    "DEFAULT_CONCURRENCY",
    "DEFAULT_GRACE_SECONDS",
    "DEFAULT_OUTPUT_CAP_BYTES",
    "ERRORED",
    "KILLED",
    "MALFORMED_RESULT",
    "MEASURED",
    "NO_RESULT",
    "PROTOCOL_VERSION",
    "TERMINATED",
    "TERMINATION_REACHES_CHILDREN",
    "TIMED_OUT",
    "UNSUPPORTED",
    "Capture",
    "Invocation",
    "RunnerConfiguration",
    "RunnerError",
    "invoke",
    "invoke_all",
    "python_adapter",
]
