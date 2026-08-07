"""eichstelle, a conformance test suite for acoustics standards.

This package computes no acoustic quantity. Decision record 0004 in
``docs/decisions`` says what a fixture is, record 0006 says how an
implementation is connected, and every number this suite reports comes from an
implementation under test rather than from here.

The version is read from the installed distribution metadata rather than written
here as a literal, so there is one place a version can be wrong instead of two.
That also means importing this package outside an install fails loudly, which is
the src layout doing what it exists to do.
"""

from importlib.metadata import version

__all__ = ["__version__"]

__version__ = version("eichstelle")
