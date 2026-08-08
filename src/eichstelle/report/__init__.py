"""The report a person reads, rendered from the record and never written by hand.

Decision record 0009 makes the record the primary output and everything a person
reads a rendering of it. This is that rendering, and its correctness problem is
specific enough to test.

The failure it must not have is dropping a category. A summary that omits a
verdict kind when its count is zero teaches a reader to stop looking for it, and
then the day it stops being zero nobody notices. So every category the record
format admits appears in the summary, at zero as readily as at forty, and the
list of categories is read out of the schema rather than written here, because a
list written here would drift against the schema that decides it.

The second failure is a partial run reading as a whole one. The three counts stay
separate: how many pairs were possible, how many were attempted, and how many
produced a verdict. A run that covered a third of the set and a run that covered
all of it look different in this output, and no arithmetic collapses them.

The third is a summary that makes a reader open a file. A disagreement is the
product of this suite, so each one is listed with enough to reproduce it rather
than counted.

Two forms come out, one for a terminal and one to send somebody, and they are
rendered from the same summary by the same code path so they cannot disagree
about a number.
"""

from eichstelle.report.render import (
    Report,
    every_count,
    render,
    render_document,
    render_text,
    summarise,
    verdicts,
)

__all__ = [
    "Report",
    "every_count",
    "render",
    "render_document",
    "render_text",
    "summarise",
    "verdicts",
]
