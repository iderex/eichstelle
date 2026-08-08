"""Summarising a record, and rendering the summary two ways.

`summarise` is the whole of the reading. Both renderers take its output and
neither reads a record, so a number that appears in one appears in the other or
in neither.
"""

from __future__ import annotations

import html
import json
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files
from typing import Any, Final

from eichstelle.record import RECORD_SCHEMA_FILE, Counts, Record

# The verdict this suite exists to surface. Named because the disagreement
# section is about it and nothing else.
DISAGREES: Final = "disagrees"

# The verdict for a pair the run never reached. Its section is always present,
# with a reason per entry, for the same reason every category is always present.
NOT_RUN: Final = "not_run"

# The fields a disagreement is listed with. Enough to reproduce one without
# opening the record, which is the one job this report has.
DISAGREEMENT_FIELDS: Final = (
    "fixture_id",
    "fixture_revision",
    "standard",
    "part",
    "edition",
    "adapter",
    "adapter_upstream_version",
    "produced",
    "produced_unit",
    "expected",
    "expected_unit",
    "tolerance",
    "tolerance_kind",
    "margin",
)


@lru_cache(maxsize=1)
def verdicts() -> tuple[str, ...]:
    """Every verdict category the record format admits, in the schema's order.

    Read from the packaged schema rather than listed here. A list in this file
    would drift against the schema that decides what a record may carry, and the
    direction it would drift in is the dangerous one: a category added to the
    format and forgotten here would be a category this report silently drops,
    which is the exact failure the report is written against.
    """
    text = files("eichstelle").joinpath(RECORD_SCHEMA_FILE).read_text(encoding="utf-8")
    schema = json.loads(text)
    entry = schema["$defs"]["entry"]["properties"]["verdict"]
    return tuple(entry["enum"])


@dataclass(frozen=True)
class Report:
    """What a record says, arranged for reading and for nothing else.

    Every field here comes from the record. Nothing is inferred, and the two
    renderers may state nothing that is not in one of these fields.
    """

    started_at: str
    finished: bool
    harness_version: str
    fixture_set_version: str
    fixture_set_checksum: str
    machine: Mapping[str, str]
    adapters: tuple[Mapping[str, str], ...]
    operator_paths_included: bool
    counts: Counts
    verdict_counts: Mapping[str, int]
    disagreements: tuple[Mapping[str, Any], ...]
    not_run: tuple[Mapping[str, Any], ...]


def summarise(record: Record) -> Report:
    """Count a record and pull out the two sections that are listed in full."""
    counted = dict.fromkeys(verdicts(), 0)
    for entry in record.entries:
        verdict = str(entry.get("verdict", ""))
        if verdict in counted:
            counted[verdict] += 1

    header = record.header
    machine = {
        key: str(header.get(key, ""))
        for key in (
            "platform",
            "operating_system",
            "operating_system_version",
            "architecture",
            "interpreter_version",
        )
    }
    adapters = tuple(
        {
            "identifier": str(adapter.get("identifier", "")),
            "upstream_version": str(adapter.get("upstream_version", "")),
        }
        for adapter in header.get("adapters", ())
    )

    return Report(
        started_at=str(header.get("started_at", "")),
        finished=record.finished,
        harness_version=str(header.get("harness_version", "")),
        fixture_set_version=str(header.get("fixture_set_version", "")),
        fixture_set_checksum=str(header.get("fixture_set_checksum", "")),
        machine=machine,
        adapters=adapters,
        operator_paths_included=bool(header.get("operator_paths_included", False)),
        counts=record.counts,
        verdict_counts=counted,
        disagreements=tuple(
            entry for entry in record.entries if entry.get("verdict") == DISAGREES
        ),
        not_run=tuple(
            entry for entry in record.entries if entry.get("verdict") == NOT_RUN
        ),
    )


def _version_of(adapter: Mapping[str, str]) -> str:
    """How an adapter's version reads, including when there is not one.

    The empty string is the declared unknown, and it stays an unknown here. A
    report that printed nothing at all would look like a field somebody forgot
    rather than a version nobody can identify.
    """
    return adapter["upstream_version"] or "unknown"


def _margin_reading(entry: Mapping[str, Any]) -> str:
    """What the margin means, in the words the record's own schema uses."""
    margin = entry.get("margin")
    if margin is None:
        return "no margin"
    return f"margin {margin} (positive is inside the band)"


def _coverage_lines(report: Report) -> list[str]:
    """The three counts, and what it means that they differ.

    Never collapsed, and never presented as one number. The sentence about a
    partial run is derived from the counts rather than written for a particular
    run, so it cannot claim anything the record does not carry.
    """
    counts = report.counts
    lines = [
        f"possible  {counts.possible}",
        f"attempted {counts.attempted}",
        f"produced  {counts.produced}",
    ]
    if counts.derived:
        lines.append(
            "The attempted and produced counts were derived from the entries "
            "because this record has no summary line, which means the run that "
            "wrote it did not finish."
        )
    if counts.produced < counts.possible:
        lines.append(
            f"{counts.possible - counts.produced} of {counts.possible} possible "
            f"pairs produced no verdict. This run did not cover the set."
        )
    return lines


def render_text(report: Report) -> str:
    """The terminal form."""
    out: list[str] = []
    out.append("eichstelle result")
    out.append("=" * 17)
    out.append("")
    out.append(f"started        {report.started_at}")
    out.append(f"run finished   {'yes' if report.finished else 'no'}")
    out.append(f"harness        {report.harness_version}")
    out.append(f"fixture set    {report.fixture_set_version}")
    out.append(f"set checksum   {report.fixture_set_checksum}")
    for key, value in report.machine.items():
        out.append(f"{key.replace('_', ' '):<14} {value}")
    out.append(
        "operator paths "
        + (
            "included in this record"
            if report.operator_paths_included
            else "not included"
        )
    )
    out.append("")

    out.append("Adapters")
    out.append("-" * 8)
    if not report.adapters:
        out.append("none")
    for adapter in report.adapters:
        out.append(f"{adapter['identifier']} at {_version_of(adapter)}")
    out.append("")

    out.append("Coverage")
    out.append("-" * 8)
    out.extend(_coverage_lines(report))
    out.append("")

    out.append("Verdicts")
    out.append("-" * 8)
    for verdict, count in report.verdict_counts.items():
        out.append(f"{verdict:<12} {count}")
    out.append("")

    out.append(f"Disagreements ({len(report.disagreements)})")
    out.append("-" * 20)
    if not report.disagreements:
        out.append("none")
    for entry in report.disagreements:
        out.append(
            f"{entry.get('fixture_id')} revision {entry.get('fixture_revision')}"
        )
        out.append(
            f"    {entry.get('standard')} part {entry.get('part')}, "
            f"edition {entry.get('edition')}"
        )
        out.append(
            f"    {entry.get('adapter')} at "
            f"{entry.get('adapter_upstream_version') or 'unknown'}"
        )
        out.append(
            f"    produced {entry.get('produced')} "
            f"{entry.get('produced_unit') or ''}".rstrip()
        )
        out.append(
            f"    expected {entry.get('expected')} "
            f"{entry.get('expected_unit') or ''}".rstrip()
        )
        out.append(
            f"    tolerance {entry.get('tolerance')} "
            f"{entry.get('tolerance_kind') or ''}".rstrip()
        )
        out.append(f"    {_margin_reading(entry)}")
    out.append("")

    out.append(f"Not run ({len(report.not_run)})")
    out.append("-" * 20)
    if not report.not_run:
        out.append("none")
    for entry in report.not_run:
        out.append(
            f"{entry.get('fixture_id')} against {entry.get('adapter')}: "
            f"{entry.get('reason') or 'no reason recorded'}"
        )
    out.append("")
    return "\n".join(out)


def _cell(value: Any) -> str:
    """One value, escaped.

    Every string in a record can carry arbitrary bytes from a foreign program.
    A diagnostic is the obvious one and a fixture identifier is the one nobody
    thinks about. Both go through here, so the document form cannot be made to
    carry markup by an adapter.
    """
    return html.escape("" if value is None else str(value))


def render_document(report: Report) -> str:
    """The self-contained form, for sending somebody.

    One file with no external reference of any kind: no stylesheet, no script,
    no image, no font. A report that fetches something is a report that leaks
    when it is opened, and record 0011 keeps this suite's output on the host it
    was produced on unless somebody decides otherwise.
    """
    out: list[str] = []
    out.append("<!DOCTYPE html>")
    out.append('<html lang="en"><head><meta charset="utf-8">')
    out.append("<title>eichstelle result</title>")
    out.append(
        "<style>body{font-family:sans-serif;max-width:60em;margin:2em auto;"
        "padding:0 1em}table{border-collapse:collapse}"
        "td,th{border:1px solid #999;padding:0.2em 0.6em;text-align:left}"
        "</style></head><body>"
    )
    out.append("<h1>eichstelle result</h1>")

    out.append("<h2>This run</h2><table>")
    for label, value in (
        ("started", report.started_at),
        ("run finished", "yes" if report.finished else "no"),
        ("harness", report.harness_version),
        ("fixture set", report.fixture_set_version),
        ("set checksum", report.fixture_set_checksum),
        *((key.replace("_", " "), value) for key, value in report.machine.items()),
        (
            "operator paths",
            "included in this record"
            if report.operator_paths_included
            else "not included",
        ),
    ):
        out.append(f"<tr><th>{_cell(label)}</th><td>{_cell(value)}</td></tr>")
    out.append("</table>")

    out.append("<h2>Adapters</h2>")
    if not report.adapters:
        out.append("<p>none</p>")
    else:
        out.append("<table><tr><th>adapter</th><th>upstream version</th></tr>")
        for adapter in report.adapters:
            out.append(
                f"<tr><td>{_cell(adapter['identifier'])}</td>"
                f"<td>{_cell(_version_of(adapter))}</td></tr>"
            )
        out.append("</table>")

    out.append("<h2>Coverage</h2><table>")
    for count_name, count in (
        ("possible", report.counts.possible),
        ("attempted", report.counts.attempted),
        ("produced", report.counts.produced),
    ):
        out.append(f"<tr><th>{_cell(count_name)}</th><td>{_cell(count)}</td></tr>")
    out.append("</table>")
    for line in _coverage_lines(report)[3:]:
        out.append(f"<p>{_cell(line)}</p>")

    out.append("<h2>Verdicts</h2><table>")
    for verdict, count in report.verdict_counts.items():
        out.append(f"<tr><th>{_cell(verdict)}</th><td>{_cell(count)}</td></tr>")
    out.append("</table>")

    out.append(f"<h2>Disagreements ({len(report.disagreements)})</h2>")
    if not report.disagreements:
        out.append("<p>none</p>")
    else:
        out.append("<table><tr>")
        for name in DISAGREEMENT_FIELDS:
            out.append(f"<th>{_cell(name.replace('_', ' '))}</th>")
        out.append("<th>reading</th></tr>")
        for entry in report.disagreements:
            out.append("<tr>")
            for name in DISAGREEMENT_FIELDS:
                out.append(f"<td>{_cell(entry.get(name))}</td>")
            out.append(f"<td>{_cell(_margin_reading(entry))}</td></tr>")
        out.append("</table>")

    out.append(f"<h2>Not run ({len(report.not_run)})</h2>")
    if not report.not_run:
        out.append("<p>none</p>")
    else:
        out.append("<table><tr><th>fixture</th><th>adapter</th><th>reason</th></tr>")
        for entry in report.not_run:
            out.append(
                f"<tr><td>{_cell(entry.get('fixture_id'))}</td>"
                f"<td>{_cell(entry.get('adapter'))}</td>"
                f"<td>{_cell(entry.get('reason') or 'no reason recorded')}</td></tr>"
            )
        out.append("</table>")

    out.append("</body></html>")
    return "\n".join(out)


def render(record: Record, *, document: bool = False) -> str:
    """Summarise once and render whichever form was asked for."""
    report = summarise(record)
    return render_document(report) if document else render_text(report)


def every_count(report: Report) -> tuple[int, ...]:
    """Every number both forms are supposed to carry.

    Here rather than in a test, so a caller comparing the two renderings cannot
    compare a different set of numbers in each of them, which is the way that
    comparison quietly stops meaning anything.
    """
    return (
        report.counts.possible,
        report.counts.attempted,
        report.counts.produced,
        *report.verdict_counts.values(),
    )
