"""The report, and the one failure it must not have.

The renderer's correctness problem is dropping a category. A summary that omits
a verdict kind when its count is zero teaches a reader to stop looking for it,
and the day it stops being zero nobody notices. So the test that matters here
builds a record carrying one entry of every verdict kind, asserts each of them
appears, and then builds a record carrying none of them and asserts every
category still appears at zero.

The list of categories is not written in this file either. It comes from the
schema, so a category added to the record format is a category this suite starts
requiring of the report without anybody remembering to add it here.
"""

from typing import Any

import pytest

from eichstelle.record import Counts, Record
from eichstelle.report import (
    every_count,
    render,
    render_document,
    render_text,
    summarise,
    verdicts,
)


def header(**over: Any) -> dict[str, Any]:
    """A header with every field the report reads."""
    document: dict[str, Any] = {
        "kind": "header",
        "format_version": 1,
        "started_at": "2026-08-09T01:02:03.000004Z",
        "harness_version": "0.1.0",
        "fixture_set_version": "2026.08",
        "fixture_set_checksum": "sha256:abc",
        "platform": "Linux-6.8",
        "operating_system": "Linux",
        "operating_system_version": "6.8",
        "architecture": "x86_64",
        "interpreter_version": "3.13.1",
        "adapters": [
            {"identifier": "fake", "upstream_version": "1.2.3"},
            {"identifier": "nameless", "upstream_version": ""},
        ],
        "possible": 12,
        "run_finished": False,
        "operator_paths_included": False,
    }
    document.update(over)
    return document


def entry(verdict: str, **over: Any) -> dict[str, Any]:
    """One entry of the given verdict, with everything a disagreement needs."""
    document: dict[str, Any] = {
        "kind": "entry",
        "fixture_id": f"fixture-{verdict}",
        "fixture_revision": 1,
        "standard": "ISO 532",
        "part": "1",
        "edition": 2017,
        "adapter": "fake",
        "adapter_upstream_version": "1.2.3",
        "verdict": verdict,
        "reason": f"reason-for-{verdict}",
        "produced": ["1.20"],
        "produced_unit": "sone",
        "expected": "1.00",
        "expected_unit": "sone",
        "tolerance": "0.05",
        "tolerance_kind": "absolute",
        "margin": "-0.15",
        "duration_seconds": "0.5",
        "source": "generated",
    }
    document.update(over)
    return document


def record_of(entries: list[dict[str, Any]], **over: Any) -> Record:
    """A record holding those entries, finished unless said otherwise."""
    fields: dict[str, Any] = {
        "header": header(),
        "entries": tuple(entries),
        "summary": {"kind": "summary", "run_finished": True},
        "counts": Counts(possible=12, attempted=len(entries), produced=len(entries)),
    }
    fields.update(over)
    return Record(**fields)


def one_of_every_verdict() -> Record:
    """A record carrying exactly one entry of every verdict the format admits."""
    return record_of([entry(verdict) for verdict in verdicts()])


def test_every_verdict_kind_appears_in_both_renderings() -> None:
    """The test the whole issue is about.

    One entry of every verdict kind, and every one of them named in the output.
    Deleting a category from the summary loop fails this for that category.
    """
    report = summarise(one_of_every_verdict())
    text = render_text(report)
    document = render_document(report)

    for verdict in verdicts():
        assert verdict in text, f"{verdict} is missing from the terminal form"
        assert verdict in document, f"{verdict} is missing from the document form"


def test_a_category_with_no_entries_still_appears_at_zero() -> None:
    """A category that vanishes when empty is one a reader stops looking for."""
    report = summarise(record_of([]))
    text = render_text(report)

    assert report.verdict_counts == dict.fromkeys(verdicts(), 0)
    for verdict in verdicts():
        assert f"{verdict:<12} 0" in text


def test_the_categories_come_from_the_schema() -> None:
    """Not from a list in the renderer, and not from a list in this file.

    Asserting the six by name here would put the drift this is against into the
    test instead of the code. What is asserted is that the set is non-empty, that
    it carries the two the report has sections for, and that it is what the
    packaged schema says.
    """
    import json
    from importlib.resources import files

    from eichstelle.record import RECORD_SCHEMA_FILE

    schema = json.loads(
        files("eichstelle").joinpath(RECORD_SCHEMA_FILE).read_text(encoding="utf-8")
    )
    declared = schema["$defs"]["entry"]["properties"]["verdict"]["enum"]

    assert list(verdicts()) == declared
    assert "disagrees" in declared
    assert "not_run" in declared


def test_the_three_counts_are_stated_separately() -> None:
    """A run that covered part of the set never reads as one that covered it."""
    report = summarise(record_of([entry("agrees")]))
    text = render_text(report)

    assert "possible  12" in text
    assert "attempted 1" in text
    assert "produced  1" in text
    assert "11 of 12 possible pairs produced no verdict" in text


def test_an_interrupted_record_says_the_counts_were_derived() -> None:
    """The marker that keeps a partial run from reading as a finished one."""
    report = summarise(
        record_of(
            [entry("agrees")],
            summary=None,
            counts=Counts(possible=12, attempted=1, produced=1, derived=True),
        )
    )
    text = render_text(report)

    assert "run finished   no" in text
    assert "did not finish" in text


def test_a_disagreement_is_listed_with_everything_needed_to_reproduce_it() -> None:
    """A summary saying "twelve disagreements" has failed at its one job."""
    report = summarise(record_of([entry("disagrees")]))
    text = render_text(report)

    for fragment in (
        "fixture-disagrees",
        "revision 1",
        "ISO 532",
        "part 1",
        "edition 2017",
        "fake",
        "1.2.3",
        "produced ['1.20'] sone",
        "expected 1.00 sone",
        "tolerance 0.05 absolute",
        "margin -0.15",
    ):
        assert fragment in text, f"{fragment!r} is missing from the disagreement"


def test_the_not_run_section_is_present_even_when_empty() -> None:
    """Always there, so its absence never has to be noticed."""
    text = render_text(summarise(record_of([entry("agrees")])))

    assert "Not run (0)" in text
    assert "none" in text


def test_a_not_run_entry_carries_its_reason() -> None:
    """Why a pair did not run is the thing a reader came for."""
    text = render_text(summarise(record_of([entry("not_run", reason="no signal")])))

    assert "fixture-not_run against fake: no signal" in text


def test_both_forms_carry_the_same_numbers() -> None:
    """One code path, so they cannot disagree about a count.

    Every number the summary is supposed to carry is checked in both, rather
    than a couple of them, because a comparison over a subset stops meaning
    anything the moment the subset is the part that happens to match.
    """
    report = summarise(one_of_every_verdict())
    text = render_text(report)
    document = render_document(report)

    for number in every_count(report):
        assert str(number) in text
        assert str(number) in document


def test_an_unknown_upstream_version_reads_as_unknown() -> None:
    """The declared unknown stays a statement rather than becoming a blank."""
    text = render_text(summarise(record_of([entry("agrees")])))

    assert "nameless at unknown" in text


def test_the_document_form_escapes_what_an_adapter_wrote() -> None:
    """Every string in a record can be arbitrary bytes from a foreign program.

    A fixture identifier is the one nobody thinks about, so it is the one used
    here. The document is a file somebody is sent and opens.
    """
    hostile = entry("disagrees", fixture_id="<script>alert(1)</script>")
    document = render_document(summarise(record_of([hostile])))

    assert "<script>alert(1)</script>" not in document
    assert "&lt;script&gt;" in document


def test_the_document_form_reaches_for_nothing_outside_itself() -> None:
    """A report that fetches something is a report that leaks when it is opened."""
    document = render_document(summarise(one_of_every_verdict()))

    for fragment in ("http://", "https://", "<script", "<img", "<link", "@import"):
        assert fragment not in document


@pytest.mark.parametrize("document", [False, True])
def test_render_takes_a_record_and_picks_a_form(document: bool) -> None:
    """The one entry point a caller uses, so neither form is reachable alone."""
    output = render(one_of_every_verdict(), document=document)

    assert output.startswith("<!DOCTYPE html>" if document else "eichstelle result")
