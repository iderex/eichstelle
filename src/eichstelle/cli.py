"""The console entry point.

Today it prints the version and exits zero, and that is the whole of it. The
command an operator actually types is issue #43, and the comparison behind it is
milestone 5. What this exists for now is to make the packaging provable by
running the installed artefact rather than by importing the working tree.
"""

import sys

from . import __version__


def main() -> int:
    """Print the version and return the process exit code."""
    print(__version__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
