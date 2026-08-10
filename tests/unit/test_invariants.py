"""Every invariant rule, shown refusing the mistake it names.

Issue #49 says a rule that has never been shown to fire is a rule nobody knows
the behaviour of. So each rule in `tools/invariants.toml` arrives here with two
lines: the one-line mistake it exists to catch, which it must refuse, and the
corrected form of the same line, which it must let through. The pair is what
makes the rule reviewable, because a pattern that refuses everything and a
pattern that refuses nothing both look like a passing check from outside.

The other half of this file is the loader. A rule with no `mistake` field, a
pattern that will not compile, two rules under one id and an exemption naming no
reason are each refused rather than run, and that matters more than it looks: a
lint rule whose message says nothing is met by somebody who then works out what
to delete to make it stop.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest


def _load() -> ModuleType:
    """Import tools/invariants.py, which is not part of the package.

    It is registered in `sys.modules` before it is executed, unlike the two
    other repository scripts loaded this way. A frozen dataclass resolves its
    own module out of that table while the class body is being processed, so
    loading this file without the registration fails on the decorator rather
    than on anything the test is about.
    """
    path = Path(__file__).resolve().parents[2] / "tools" / "invariants.py"
    specification = importlib.util.spec_from_file_location("invariants", path)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


invariants = _load()

RULE_FILE = Path(__file__).resolve().parents[2] / "tools" / "invariants.toml"


def rules() -> dict[str, Any]:
    """The rule set as this tree carries it, by id."""
    loaded = invariants.rules_from(RULE_FILE.read_text(encoding="utf-8"))
    return {rule.id: rule for rule in loaded}


# One row per rule: where such a line would live, the mistake, and the same
# line written correctly. The corrected form is not a comment or a deletion; it
# is what the author meant to write, so that a rule refusing both would be
# caught here rather than in somebody's pull request.
CASES: list[tuple[str, str, str, str]] = [
    (
        "no-transcribed-expected-value",
        "fixtures/loudness-one-sone.json",
        '  "provenance": "standard-clause",',
        '  "provenance": "generated-by-definition",',
    ),
    (
        "no-fallback-from-a-licensed-reference",
        "src/eichstelle/reference/resolve.py",
        "    samples = licensed_reference(fixture) or render(signal)",
        "    samples = licensed_reference(fixture)",
    ),
    (
        "no-arithmetic-in-an-adapter",
        "adapters/mosqito/adapter.py",
        '    value = answer["loudness"] * 0.5',
        '    value = answer["loudness"]',
    ),
    (
        "no-default-tolerance-in-the-comparator",
        "src/eichstelle/compare/comparator.py",
        '    band = fixture.get("tolerance", "0.1")',
        '    band = fixture["tolerance"]',
    ),
    (
        "no-socket-device-or-display-in-the-suite",
        "tests/e2e/test_upstream.py",
        "import socket",
        "import socketserver",
    ),
    (
        "no-implementation-under-test-in-the-core-dependencies",
        "pyproject.toml",
        '  "mosqito>=1.2",',
        '  "jsonschema>=4.18",',
    ),
]


@pytest.mark.parametrize(("identifier", "path", "mistake", "corrected"), CASES)
def test_each_rule_refuses_the_mistake_it_names(
    identifier: str, path: str, mistake: str, corrected: str
) -> None:
    """The rule fires on the mistake and does not fire on the correction."""
    rule = rules()[identifier]
    assert rule.selects(path), f"{identifier} does not read {path}"
    refusals = invariants.matches(rule, path, mistake)
    assert len(refusals) == 1
    assert refusals[0].startswith(f"{path}:1:")
    assert invariants.matches(rule, path, corrected) == []


def test_every_case_above_covers_a_rule_in_the_tree() -> None:
    """The table above and the rule file name the same set.

    Without this, a rule added to the file with no row here is a rule nothing
    has ever seen fire, which is the state this whole file exists against.
    """
    assert {identifier for identifier, _, _, _ in CASES} == set(rules())


def test_every_rule_declares_what_a_reader_needs() -> None:
    """Each rule names its decision, its mistake, its bound and its origin."""
    for rule in rules().values():
        for field in ("decision", "mistake", "bound", "prompted_by"):
            assert getattr(rule, field).strip(), f"{rule.id} has an empty {field}"


def test_a_rule_missing_a_field_is_refused_rather_than_run() -> None:
    """A rule with no mistake text would produce a refusal nobody can act on."""
    text = """
[[rule]]
id = "half-declared"
decision = "somewhere"
bound = "narrow"
prompted_by = "nothing"
paths = ["src/"]
patterns = ["never"]
"""
    with pytest.raises(invariants.ScanError, match="missing mistake"):
        invariants.rules_from(text)


def test_a_pattern_that_will_not_compile_stops_the_run() -> None:
    """A broken pattern fails closed rather than matching nothing quietly."""
    text = """
[[rule]]
id = "broken"
decision = "d"
mistake = "m"
bound = "b"
prompted_by = "p"
paths = ["src/"]
patterns = ["(unclosed"]
"""
    with pytest.raises(invariants.ScanError, match="will not compile"):
        invariants.rules_from(text)


def test_two_rules_under_one_id_are_refused() -> None:
    """An id is what a refusal is reported under, so it has to be unique."""
    entry = """
[[rule]]
id = "twice"
decision = "d"
mistake = "m"
bound = "b"
prompted_by = "p"
paths = ["src/"]
patterns = ["x"]
"""
    with pytest.raises(invariants.ScanError, match="twice"):
        invariants.rules_from(entry + entry)


def test_an_empty_rule_set_is_refused() -> None:
    """A file with no rule in it would report green having asserted nothing."""
    with pytest.raises(invariants.ScanError, match="declares no rule"):
        invariants.rules_from("")


def test_an_exemption_with_no_reason_is_refused() -> None:
    """An exception nobody had to justify is what the reason field prevents."""
    text = """
[[rule]]
id = "exempting"
decision = "d"
mistake = "m"
bound = "b"
prompted_by = "p"
paths = ["tests/"]
patterns = ["x"]

[[rule.allow]]
path = "tests/unit/test_x.py"
"""
    with pytest.raises(invariants.ScanError, match="declares no reason"):
        invariants.rules_from(text)


def test_an_exemption_covers_the_path_it_names_and_no_other() -> None:
    """The allow list is per path, so a neighbour is still refused."""
    rule = rules()["no-socket-device-or-display-in-the-suite"]
    exempt = next(iter(rule.allow))
    assert invariants.matches(rule, exempt, "import socket") == []
    assert (
        len(invariants.matches(rule, "tests/e2e/test_other.py", "import socket")) == 1
    )


def test_a_directory_entry_covers_what_is_under_it_and_a_suffix_narrows_it() -> None:
    """Path selection, which decides what a rule never even reads."""
    rule = rules()["no-default-tolerance-in-the-comparator"]
    assert rule.selects("src/eichstelle/compare/comparator.py")
    assert not rule.selects("src/eichstelle/compare/notes.md")
    assert not rule.selects("src/eichstelle/record/record.py")

    exact = rules()["no-implementation-under-test-in-the-core-dependencies"]
    assert exact.selects("pyproject.toml")
    assert not exact.selects("tools/pyproject.toml")


def test_the_rule_file_in_this_tree_is_the_one_the_tests_read() -> None:
    """The rules proven above are the rules the check will run.

    The tests load the file from its path rather than from the index, and the
    check reads the index. The two agree in a clean checkout and this says so
    out loud, because a suite proving a rule set nobody ships is worth nothing.
    """
    assert RULE_FILE.is_file()
    assert len(rules()) == len(CASES)
