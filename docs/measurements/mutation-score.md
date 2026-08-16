# The mutation score

Measurements, oldest first. Nothing is edited once it is here; a new run is a
new entry underneath. Each entry carries the date, the commit, the versions and
the command, because a score with none of those is a number nobody can reproduce
and nobody can argue with.

There is no target and there is not going to be one written here. Issue #48
decides that the score gates nothing, and a target chosen before the first
measurement is a guess dressed as a standard. What the number is for is the
direction it moves and the list of survivors underneath it.

## What is being measured

Mutation testing changes the code a little, one change at a time, and asks
whether a test fails. A mutant that dies is a line something would have noticed
being wrong. A mutant that lives is a line nothing would have noticed.

The surface is the verdict surface, which `docs/quality-parity.md` names as the
place where a silent wrong answer does the harm here: the comparator, the record
writer and the report renderer. `[tool.mutmut]` in `pyproject.toml` is where that
selection is written and where the reason for each exclusion is.

The score is `killed / (killed + survived + no_tests)`, and
`tools/mutation_score.py` is where that definition lives along with the argument
for putting uncovered mutants in the denominator and not beside it.

## What a low score does and does not mean

It does not mean the code is wrong. It means the suite would not have noticed a
particular small change, which is a different statement and a weaker one.

Two things inflate the survivor count on this surface in particular, and they are
worth knowing before anybody reads a number here as an indictment.

The tool mutates string literals, so every message this project writes into a
report or an error is a mutant, and a test that asserts a verdict and not a
sentence lets it live. Some of those are worth killing and some are a test
asserting on prose that will change next month.

And the report renderer is mostly text layout. A mutant that moves a column
width survives every test that reads the numbers out of the report, which is
what the report's own suite is for. That is why the renderer's score is the
lowest of the three below and why it is not the most alarming of them.

The comparator is the one where a survivor is expensive. A mutant that lives
inside the tolerance evaluation is a verdict that can come out wrong with
nothing to catch it, and this project's entire output is verdicts.

## 2026-08-09

    $ uv sync --locked --group mutation
    $ mutmut run
    $ mutmut export-cicd-stats
    $ python tools/mutation_score.py mutants/mutmut-cicd-stats.json
    mutation score: 57.00%
    killed 472 of 828 scored mutant(s)
        killed: 472
        survived: 356
        no tests: 0
        timeout: 0
        suspicious: 0
        skipped: 0
        segfault: 0
    0 mutant(s) are outside the denominator: a timeout, an unclassifiable result, a skip and a segfault are statements about the run rather than about the suite.
    This score gates nothing. Issue #48 decides that, and the reason is that the number moves with refactoring rather than with test quality.

Commit `9d0727a`, mutmut 3.7.0, CPython 3.12.3 on Linux. The whole surface was
scored: no mutant timed out, none was skipped and none was left uncovered.

Per file, from the run's own metadata:

    src/eichstelle/compare/comparator.py    killed 114  survived  51  of 165    69.09%
    src/eichstelle/record/record.py         killed 120  survived  25  of 145    82.76%
    src/eichstelle/report/render.py         killed 238  survived 280  of 518    45.95%

The renderer holds four fifths of the survivors and is the file the paragraph
about text layout above is about. The comparator's fifty-one are the ones worth
reading one at a time.

This run was taken on Linux, not on the machine the rest of the gate was
run on. mutmut refuses to start on Windows and says so, pointing at its own open
issue for native support, so a contributor on Windows runs this measurement
inside a Linux environment or not at all. The scheduled workflow runs it on
Linux, which is where the number that lands here in future comes from.

## How the next entry gets here

The scheduled run in `.github/workflows/mutation.yml` prints the score into its
own job summary and keeps the run's metadata as an artefact. It does not write
to this file, and that is deliberate: a workflow that pushes a number into the
tree on a schedule produces a document nobody has read, and the point of this
file is that somebody read the number and the list of survivors under it.

So an entry is added by hand, by whoever looked. What the schedule guarantees is
that the measurement keeps being taken and that a run which stops producing a
score is loud rather than quiet.
