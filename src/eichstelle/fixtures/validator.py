"""The validator, and the refusals it makes.

Every refusal here exists because of one way a fixture set goes quietly wrong,
and none of them is a tidiness rule.

A fixture with no tolerance cannot be compared against, so a run over it either
crashes or invents a band. A fixture with no provenance leaves a reader unable
to tell a disagreement with a normative table from a disagreement with a
consensus, which decision record 0004 says are opposite findings. A fixture with
no standard edition pins its expectation to nothing, and the edition is exactly
what moves under a value. Two fixtures with one identifier make a published
result ambiguous about what it was produced against. An expected value with no
unit is a bare number a reader supplies a unit for by guessing. A signal
description naming a parameter the generator does not accept is a fixture
written against a feature that was renamed, and the cost of not refusing it is a
signal generated with the parameter silently dropped. A tolerance of zero or
less is either a slip or a claim of bit-exact agreement no floating-point
implementation can meet.

Most of those are refused by the schema's shape. Two are not, for reasons worth
knowing before looking for them in the wrong file:

- the missing field cases, the unit, and the closed per-kind parameter set are
  the schema, in ``schema/fixture-1.schema.json``
- the sign of the tolerance is here, because JSON Schema's numeric keywords do
  not apply to strings and decision record 0004 writes every physical quantity
  as a decimal string on purpose
- the colliding identifier is here, because no schema sees more than one
  document at a time

Everything is reported in one pass. A contributor writing their first fixture
gets one list rather than five iterations, which is worth the small cost of
continuing after a failure that would let an early return look reasonable.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from importlib.resources import files
from pathlib import Path
from typing import Final

import jsonschema

# The schema directory, and the shape of a schema file name in it. The set of
# known versions is derived from what is on disk rather than written out here,
# so publishing version 2 is adding a file and not also remembering to edit a
# list that would otherwise disagree with it.
SCHEMA_DIRECTORY: Final = "schema"
SCHEMA_FILE_PATTERN: Final = re.compile(r"^fixture-(\d+)\.schema\.json$")


class ValidatorError(Exception):
    """The validation did not complete, so its result is unknown."""


@dataclass(frozen=True, order=True)
class Problem:
    """One reason one fixture is refused."""

    path: str
    where: str
    detail: str

    def __str__(self) -> str:
        """Render as one line, with the location the reader has to open."""
        return f"{self.path}: {self.where}: {self.detail}"


def known_schema_versions() -> dict[int, str]:
    """The schema versions this build carries, read from the packaged files."""
    directory = files("eichstelle").joinpath(SCHEMA_DIRECTORY)
    versions: dict[int, str] = {}
    for entry in directory.iterdir():
        match = SCHEMA_FILE_PATTERN.match(entry.name)
        if match is not None:
            versions[int(match.group(1))] = entry.read_text(encoding="utf-8")
    if not versions:
        raise ValidatorError(
            f"no schema file matching {SCHEMA_FILE_PATTERN.pattern} was found in "
            f"the packaged {SCHEMA_DIRECTORY} directory"
        )
    return versions


def _validators() -> dict[int, jsonschema.Draft202012Validator]:
    """One validator per known schema version, each checked against its dialect."""
    built: dict[int, jsonschema.Draft202012Validator] = {}
    for version, text in known_schema_versions().items():
        try:
            schema = json.loads(text)
        except json.JSONDecodeError as exc:  # pragma: no cover - a broken build
            raise ValidatorError(
                f"schema version {version} is not JSON: {exc}"
            ) from exc
        # A schema this project ships that is not a legal schema would otherwise
        # refuse every fixture for a reason that is not the fixture's.
        jsonschema.Draft202012Validator.check_schema(schema)
        built[version] = jsonschema.Draft202012Validator(schema)
    return built


def _selected_version(document: object) -> int | None:
    """The declared schema version, or None when there is nothing usable to read.

    `bool` is excluded on purpose: it is a subclass of `int` in Python, so
    `schema_version: true` would otherwise select schema version 1.
    """
    if not isinstance(document, Mapping):
        return None
    declared = document.get("schema_version")
    if isinstance(declared, bool) or not isinstance(declared, int):
        return None
    return declared


def _tolerance_problems(path: str, document: object) -> list[Problem]:
    """Refuse a tolerance of zero or less, which the schema cannot express."""
    if not isinstance(document, Mapping):
        return []
    tolerance = document.get("tolerance")
    if not isinstance(tolerance, str):
        # Absent or the wrong type. The schema already refuses that, and saying
        # it twice would make one mistake look like two.
        return []
    try:
        value = Decimal(tolerance)
    except InvalidOperation:
        return []
    if value > 0:
        return []
    return [
        Problem(
            path=path,
            where="$.tolerance",
            detail=(
                f"a tolerance of {tolerance} admits nothing. Zero or less is either a "
                "slip or a claim of bit-exact agreement, which no floating-point "
                "implementation of a psychoacoustic model can meet"
            ),
        )
    ]


def _collision_problems(documents: Mapping[str, object]) -> list[Problem]:
    """Refuse an identifier carried by more than one of the documents given."""
    seen: dict[str, list[str]] = {}
    for path in sorted(documents):
        document = documents[path]
        if not isinstance(document, Mapping):
            continue
        identifier = document.get("id")
        if isinstance(identifier, str):
            seen.setdefault(identifier, []).append(path)
    problems = []
    for identifier, paths in sorted(seen.items()):
        if len(paths) > 1:
            problems.append(
                Problem(
                    path=paths[0],
                    where="$.id",
                    detail=(
                        f"the identifier {identifier!r} is also carried by "
                        f"{', '.join(paths[1:])}. An identifier is what a published "
                        "result names, and two fixtures under one name make that "
                        "citation ambiguous"
                    ),
                )
            )
    return problems


def validate_documents(documents: Mapping[str, object]) -> list[Problem]:
    """Return every problem in the given documents, keyed by where each came from.

    The documents are already-parsed JSON. Taking them this way rather than
    taking paths is what lets a test build a one-change neighbour of a valid
    fixture in memory, and it keeps the collision check honest: it sees exactly
    the set it was asked about and never a directory it went looking in.
    """
    validators = _validators()
    problems: list[Problem] = []

    for path in sorted(documents):
        document = documents[path]
        version = _selected_version(document)
        if version is None or version not in validators:
            known = ", ".join(str(v) for v in sorted(validators))
            problems.append(
                Problem(
                    path=path,
                    where="$.schema_version",
                    detail=(
                        f"declares schema version {version!r}, which this build does "
                        f"not know. Known: {known}. A fixture is not validated against "
                        "the newest schema to hand, because the rules that applied when "
                        "a result was produced are what reproduces it"
                    ),
                )
            )
            # No schema was selected, so nothing below could be judged against
            # one. The tolerance check does not need a schema and still runs.
            problems.extend(_tolerance_problems(path, document))
            continue

        for error in validators[version].iter_errors(document):
            problems.append(
                Problem(path=path, where=error.json_path, detail=error.message)
            )
        problems.extend(_tolerance_problems(path, document))

    problems.extend(_collision_problems(documents))
    return sorted(problems)


def validate_paths(paths: Iterable[Path]) -> list[Problem]:
    """Read each path as JSON and validate the set as a whole.

    A path that cannot be read stops the run with `ValidatorError`, because a
    validator that cannot see a file and reports nothing is how a check of this
    shape turns into decoration. A file that reads but is not JSON is a refusal:
    the file was seen, and what it says is that it is not a fixture.
    """
    documents: dict[str, object] = {}
    problems: list[Problem] = []
    for path in paths:
        name = path.as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ValidatorError(f"could not read {name}: {exc}") from exc
        try:
            documents[name] = json.loads(text)
        except json.JSONDecodeError as exc:
            problems.append(
                Problem(path=name, where="$", detail=f"is not valid JSON: {exc}")
            )
    return sorted(problems + validate_documents(documents))
