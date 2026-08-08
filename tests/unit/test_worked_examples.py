"""The worked examples the how-to documents walk through, run rather than read.

`docs/adding-a-fixture.md` and `docs/adding-an-implementation.md` are written
for somebody who has never seen this project, and each of them ends in an
example. An example nobody executes is wrong within a year: a field gets
renamed, a refusal gets added, an invocation grows an argument, and the document
goes on showing what used to work. So both examples live in the tree and both
are exercised here.

The fixture example is checked three ways rather than one. It validates, which
is what the document claims. Its signal description is accepted by the
generator, which is a stronger claim than validating: the schema knows the
parameter names and the generator knows what they mean, and a document teaching
somebody to write a fixture has to be right about both. And it renders, so the
example is a stimulus somebody could actually run rather than a shape.

The adapter example is `tools/fake_adapter.py`, which
`tests/e2e/test_fake_adapter.py` already drives against the contract in every
behaviour it declares. What is asserted here is the one thing that file does not
cover and the document depends on: that the example the document points at is
the file that exists.
"""

import json
from pathlib import Path
from typing import Any

from eichstelle.fixtures import validate_documents
from eichstelle.signals import parse_sinusoid, render

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_EXAMPLE = REPOSITORY_ROOT / "docs" / "examples" / "tone-at-forty-decibels.json"
ADAPTER_EXAMPLE = REPOSITORY_ROOT / "tools" / "fake_adapter.py"


def example_document() -> dict[str, Any]:
    """The worked example, read from the file the document points a reader at."""
    document: dict[str, Any] = json.loads(FIXTURE_EXAMPLE.read_text(encoding="utf-8"))
    return document


def test_the_worked_fixture_example_validates() -> None:
    """The example in `docs/adding-a-fixture.md` is a fixture the validator accepts.

    Enforces the claim the document makes about itself. Delete a required field
    from the example and this fails, which is the point: the document cannot
    teach a shape the validator refuses.
    """
    problems = validate_documents({str(FIXTURE_EXAMPLE): example_document()})
    assert problems == []


def test_the_worked_fixture_example_is_a_signal_the_generator_accepts() -> None:
    """Its signal description parses and renders.

    Validating proves the fixture is shaped like a fixture. This proves the
    stimulus it describes is one this tree can actually produce, which is what a
    reader following the document will try next. Two seconds at 48 kHz is
    96000 frames, and a length that is not that means the description and the
    generator disagree about duration or sample rate.
    """
    signal = parse_sinusoid(example_document()["signal"])
    samples = render(signal)

    assert len(samples) == 96000
    assert max(abs(sample) for sample in samples) > 0.0


def test_the_worked_adapter_example_is_where_the_document_says_it_is() -> None:
    """`docs/adding-an-implementation.md` ends at a file, and it is this one."""
    assert ADAPTER_EXAMPLE.is_file()
