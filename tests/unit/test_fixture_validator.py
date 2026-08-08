"""What the validator refuses, one refusal at a time.

Every case here is a one-change neighbour of the same valid fixture: exactly one
field is removed or altered, and nothing else. That is what makes each test say
something about the field under test. A defective fixture built from scratch
would be refused for reasons nobody chose, and would go on passing after the
rule it was written for had been deleted.

The fixture below is a fixture vocabulary and not this repository's fixture set.
A test that reads the real fixtures reports the state of the tree on the day it
ran; this one reports the state of the validator.
"""

from typing import Any

import pytest

from eichstelle.fixtures import Problem, known_schema_versions, validate_documents

PATH = "fixtures/example.json"


def valid_fixture() -> dict[str, Any]:
    """A fixture that meets every rule, and the base of every neighbour below."""
    return {
        "id": "example-tone-at-forty-decibels",
        "revision": 1,
        "schema_version": 1,
        "title": "a 1 kHz sinusoid at 40 dB SPL",
        "signal": {
            "kind": "sinusoid",
            "sample_rate": 48000,
            "channels": 1,
            "duration_seconds": "2.0",
            "parameters": {
                "frequency_hz": "1000.0",
                "level_db_spl": "40.0",
                "calibration_reference_db_spl": "94.0",
                "fade": {"shape": "raised_cosine", "duration_seconds": "0.05"},
            },
        },
        "metric": "loudness",
        "metric_parameters": {"field_condition": "free"},
        "expected": "1.0",
        "unit": "sone",
        "tolerance": "0.05",
        "tolerance_kind": "absolute",
        "standard": {
            "designation": "ISO 532",
            "part": "1",
            "edition_year": 2017,
            "clause": "4.1",
        },
        "provenance": "generated-by-definition",
    }


def problems_for(document: dict[str, Any]) -> list[Problem]:
    """Validate one document on its own."""
    return validate_documents({PATH: document})


def without(*keys: str) -> dict[str, Any]:
    """The valid fixture with one top-level field removed."""
    document = valid_fixture()
    for key in keys:
        del document[key]
    return document


def test_a_valid_fixture_passes() -> None:
    """The validator is shown not to refuse everything.

    Without this the whole file could pass with a validator that refuses its
    input unconditionally, which is the cheapest way to make a set of refusal
    tests green.
    """
    assert problems_for(valid_fixture()) == []


# Each entry is a name, a change, and the location the refusal must be reported
# at. The location is asserted rather than only the count, because a refusal
# landing somewhere else is a rule firing for the wrong reason.
REFUSALS = [
    ("no tolerance", lambda d: d.pop("tolerance"), "$"),
    ("no provenance", lambda d: d.pop("provenance"), "$"),
    ("no unit on the expected value", lambda d: d.pop("unit"), "$"),
    ("no tolerance kind", lambda d: d.pop("tolerance_kind"), "$"),
    (
        "no standard edition",
        lambda d: d["standard"].pop("edition_year"),
        "$.standard",
    ),
    (
        "a parameter the generator does not accept",
        lambda d: d["signal"]["parameters"].update({"freq_hz": "1000.0"}),
        "$.signal.parameters",
    ),
    (
        "a signal kind no generator produces",
        lambda d: d["signal"].update({"kind": "square_wave"}),
        "$.signal.kind",
    ),
    ("a tolerance of zero", lambda d: d.update({"tolerance": "0.0"}), "$.tolerance"),
    (
        "a negative tolerance",
        lambda d: d.update({"tolerance": "-0.05"}),
        "$.tolerance",
    ),
    (
        "an expected value written as a JSON number",
        lambda d: d.update({"expected": 1.0}),
        "$.expected",
    ),
    (
        "a hyphenated field name inside the metric parameters",
        lambda d: d.update({"metric_parameters": {"field-condition": "free"}}),
        "$.metric_parameters",
    ),
]


@pytest.mark.parametrize(
    ("change", "where"),
    [(change, where) for _, change, where in REFUSALS],
    ids=[name for name, _, _ in REFUSALS],
)
def test_the_validator_refuses(change: Any, where: str) -> None:
    """One change to a valid fixture produces one refusal, in the right place."""
    document = valid_fixture()
    change(document)

    problems = problems_for(document)

    assert len(problems) == 1, problems
    assert problems[0].where == where
    assert problems[0].path == PATH


def test_a_colliding_identifier_is_refused() -> None:
    """Two fixtures under one identifier are refused, naming both files.

    No schema sees more than one document at a time, so this is the one refusal
    that cannot live in the schema. An identifier is what a published result
    names, and two fixtures carrying one make that citation ambiguous.
    """
    first = valid_fixture()
    second = valid_fixture()
    second["title"] = "the same identifier on a different fixture"

    problems = validate_documents({"fixtures/a.json": first, "fixtures/b.json": second})

    assert len(problems) == 1, problems
    assert problems[0].where == "$.id"
    assert "fixtures/b.json" in problems[0].detail


def test_two_fixtures_with_different_identifiers_do_not_collide() -> None:
    """The collision check is shown not to fire on a set that is fine."""
    first = valid_fixture()
    second = valid_fixture()
    second["id"] = "example-tone-at-sixty-decibels"

    assert validate_documents({"a.json": first, "b.json": second}) == []


def test_every_problem_is_reported_in_one_pass() -> None:
    """A fixture missing three fields yields three refusals, not the first one.

    A contributor writing their first fixture gets one list rather than five
    iterations, and a validator that stops at the first error is what turns that
    into five.
    """
    document = without("tolerance", "provenance", "unit")

    problems = problems_for(document)

    assert len(problems) == 3, problems
    reported = " ".join(problem.detail for problem in problems)
    assert "tolerance" in reported
    assert "provenance" in reported
    assert "unit" in reported


def test_an_unknown_schema_version_is_refused_rather_than_downgraded() -> None:
    """A fixture is never validated against the newest schema to hand.

    The fixture here is otherwise valid against version 1, so a validator that
    fell back would report it clean. Refusing it is what keeps an operator
    reproducing an old result from being judged by rules written afterwards.
    """
    document = valid_fixture()
    document["schema_version"] = max(known_schema_versions()) + 1

    problems = problems_for(document)

    assert len(problems) == 1, problems
    assert problems[0].where == "$.schema_version"


@pytest.mark.parametrize("declared", [True, "1", 1.0, None])
def test_a_schema_version_that_is_not_an_integer_is_refused(declared: Any) -> None:
    """`true` is the case worth naming: bool is a subclass of int in Python.

    So `schema_version: true` does select schema version 1, and what refuses it
    is the schema's `const: 1`, which `true` does not satisfy because the types
    differ. The other three never select a schema at all. Both routes report at
    the same location, which is why this test asserts the location and not the
    wording.
    """
    document = valid_fixture()
    document["schema_version"] = declared

    problems = problems_for(document)

    assert problems[0].where == "$.schema_version"


def test_a_document_that_is_not_an_object_is_refused() -> None:
    """A JSON array or string is not a fixture, and says so once."""
    problems = validate_documents({PATH: ["not", "a", "fixture"]})

    assert len(problems) == 1, problems
    assert problems[0].where == "$.schema_version"


def test_the_known_versions_come_from_the_packaged_files() -> None:
    """The version list is derived rather than written down in the code.

    A list in the source drifts against the directory that decides it, and the
    drift shows up as a fixture refused for declaring a version that is sitting
    right there.
    """
    versions = known_schema_versions()

    assert set(versions) == {1}
    assert '"$schema"' in versions[1]
