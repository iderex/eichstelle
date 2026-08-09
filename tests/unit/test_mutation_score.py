"""The mutation score reader, and every shape of broken run it refuses.

The asymmetry issue #48 asks for is the whole subject of this file. A score of
zero passes, because a low number is a finding rather than a failure. A run that
produced no number at all fails, because that is the tool having stopped, and a
stopped tool leaves the previous score standing and the schedule green.

So most of what is below drives the second half. Each test breaks the stats
document in one way somebody will actually break it - the run never wrote it,
it wrote something that is not JSON, it wrote an object missing a count, it
wrote a count that is not a number, it wrote all zeroes - and asserts exit 2 and
a message that says which.
"""

from __future__ import annotations

import importlib.util
import json
from decimal import Decimal
from pathlib import Path
from types import ModuleType

import pytest


def _load() -> ModuleType:
    """Import tools/mutation_score.py, which is not part of the package.

    It lives under tools/ because it is a repository script rather than
    something an operator installs, so it is not importable by name and is
    loaded from its path here. The same arrangement as the tracked-audio
    script's own suite would use.
    """
    path = Path(__file__).resolve().parents[2] / "tools" / "mutation_score.py"
    specification = importlib.util.spec_from_file_location("mutation_score", path)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


mutation_score = _load()


def write(path: Path, document: object) -> Path:
    """Write a stats document and return its path."""
    stats = path / "mutmut-cicd-stats.json"
    stats.write_text(json.dumps(document), encoding="utf-8")
    return stats


def full(**overrides: int) -> dict[str, int]:
    """A stats document with every count a run produces, before overriding."""
    document = {
        "killed": 0,
        "survived": 0,
        "total": 0,
        "no_tests": 0,
        "skipped": 0,
        "suspicious": 0,
        "timeout": 0,
        "segfault": 0,
    }
    document.update(overrides)
    return document


class TestTheScore:
    """What the number is, over documents that do carry one."""

    def test_every_mutant_killed_is_a_hundred_per_cent(self) -> None:
        assert mutation_score.score_of(
            {"killed": 7, "survived": 0, "no_tests": 0}
        ) == Decimal("100.00")

    def test_nothing_killed_is_zero_and_is_not_an_error(self, tmp_path: Path) -> None:
        # The asymmetry, at its sharpest. Zero per cent is a finding about the
        # suite and this script reports it and exits clean.
        stats = write(tmp_path, full(killed=0, survived=11, total=11))
        assert mutation_score.main([str(stats)]) == 0

    def test_an_uncovered_mutant_counts_against_the_score(self) -> None:
        # 1 killed, 1 uncovered. If `no_tests` were dropped from the
        # denominator this would read 100%, and the score would rise as
        # coverage fell.
        assert mutation_score.score_of(
            {"killed": 1, "survived": 0, "no_tests": 1}
        ) == Decimal("50.00")

    def test_the_four_unscored_outcomes_move_nothing(self) -> None:
        counts = {"killed": 1, "survived": 1, "no_tests": 0}
        with_noise = dict(counts, timeout=9, suspicious=9, skipped=9, segfault=9)
        assert mutation_score.score_of(with_noise) == mutation_score.score_of(counts)

    def test_the_score_is_a_decimal_rather_than_a_float(self) -> None:
        # 1/3 is the case that shows it: a float would print a tail nobody
        # asked for, and this number goes into a document as text.
        assert mutation_score.score_of(
            {"killed": 1, "survived": 2, "no_tests": 0}
        ) == Decimal("33.33")


class TestWhatIsReported:
    """What a reader is told, which has to include what the score left out."""

    def test_every_count_is_printed(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        stats = write(
            tmp_path,
            full(killed=3, survived=1, no_tests=2, timeout=4, segfault=5, total=15),
        )
        assert mutation_score.main([str(stats)]) == 0
        printed = capsys.readouterr().out
        assert "mutation score: 50.00%" in printed
        assert "killed 3 of 6 scored mutant(s)" in printed
        for count in ("killed: 3", "survived: 1", "no tests: 2"):
            assert count in printed
        for count in ("timeout: 4", "segfault: 5", "suspicious: 0", "skipped: 0"):
            assert count in printed

    def test_the_mutants_outside_the_denominator_are_counted_out_loud(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # A score over six mutants when twenty were generated is not a score
        # over twenty, and the line that says so is what stops it being read
        # as one.
        stats = write(
            tmp_path,
            full(killed=3, survived=3, timeout=10, skipped=4, total=20),
        )
        assert mutation_score.main([str(stats)]) == 0
        assert "14 mutant(s) are outside the denominator" in capsys.readouterr().out

    def test_the_summary_file_gets_the_same_lines(self, tmp_path: Path) -> None:
        stats = write(tmp_path, full(killed=1, survived=1, total=2))
        summary = tmp_path / "summary.md"
        assert mutation_score.main([str(stats), "--summary", str(summary)]) == 0
        written = summary.read_text(encoding="utf-8")
        assert "mutation score: 50.00%" in written
        assert "This score gates nothing" in written

    def test_the_summary_file_is_appended_to_rather_than_replaced(
        self, tmp_path: Path
    ) -> None:
        # It is the step summary of a workflow job, which other steps write to.
        stats = write(tmp_path, full(killed=1, survived=0, total=1))
        summary = tmp_path / "summary.md"
        summary.write_text("something an earlier step wrote\n", encoding="utf-8")
        assert mutation_score.main([str(stats), "--summary", str(summary)]) == 0
        assert summary.read_text(encoding="utf-8").startswith(
            "something an earlier step wrote\n"
        )


class TestABrokenRunIsLoud:
    """Exit 2, once per way the tool can stop producing a number."""

    def test_no_stats_file_at_all(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # The plainest form of the tool having broken: the run fell over before
        # it wrote anything.
        missing = tmp_path / "mutants" / "mutmut-cicd-stats.json"
        assert mutation_score.main([str(missing)]) == 2
        assert "could not be read" in capsys.readouterr().err

    def test_the_stats_file_is_not_json(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        stats = tmp_path / "mutmut-cicd-stats.json"
        stats.write_text("Traceback (most recent call last):\n", encoding="utf-8")
        assert mutation_score.main([str(stats)]) == 2
        assert "is not JSON" in capsys.readouterr().err

    def test_the_stats_file_is_json_but_not_an_object(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        stats = write(tmp_path, [1, 2, 3])
        assert mutation_score.main([str(stats)]) == 2
        assert "holds list rather than an object" in capsys.readouterr().err

    @pytest.mark.parametrize("missing", ["killed", "survived", "no_tests"])
    def test_a_count_the_score_needs_is_absent(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str], missing: str
    ) -> None:
        # A producer that renamed a key is the same failure as one that
        # crashed, and it is the more dangerous of the two because the file
        # exists and looks like a result.
        document = full(killed=1, survived=1, total=2)
        del document[missing]
        assert mutation_score.main([str(write(tmp_path, document))]) == 2
        assert f"carries no {missing!r} count" in capsys.readouterr().err

    @pytest.mark.parametrize("value", [None, "3", 3.5, [3], True])
    def test_a_count_that_is_not_a_count(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str], value: object
    ) -> None:
        # `True` is in that list on purpose. bool is a subclass of int, so a
        # producer writing a flag where a count belongs would otherwise be
        # counted as one mutant and pass.
        document: dict[str, object] = dict(full(killed=1, survived=1, total=2))
        document["killed"] = value
        assert mutation_score.main([str(write(tmp_path, document))]) == 2
        assert "which is not a count" in capsys.readouterr().err

    def test_a_negative_count(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert mutation_score.main([str(write(tmp_path, full(killed=-1)))]) == 2
        assert "which is not a count" in capsys.readouterr().err

    def test_a_run_that_scored_no_mutant_at_all(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # Every count zero. This is what a tool that started, found nothing to
        # mutate and exited zero leaves behind, and it is the shape most likely
        # to be read as a clean run.
        assert mutation_score.main([str(write(tmp_path, full()))]) == 2
        assert "nothing to compute a score over" in capsys.readouterr().err

    def test_a_run_whose_mutants_all_timed_out(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # Every mutant outside the denominator, which is what a runner
        # misconfigured to a one-second limit produces. There is no score in
        # that and this says so rather than reporting a division it cannot do.
        stats = write(tmp_path, full(timeout=40, total=40))
        assert mutation_score.main([str(stats)]) == 2
        assert "nothing to compute a score over" in capsys.readouterr().err

    def test_there_is_no_exit_one(self, tmp_path: Path) -> None:
        # Exit 1 is what a caller would reach for to mean "the score is too
        # low", and issue #48 decides there is no such outcome. Nothing here
        # produces it, over a healthy run and over a broken one.
        healthy = write(tmp_path, full(killed=1, survived=1, total=2))
        broken = tmp_path / "absent.json"
        outcomes = {
            mutation_score.main([str(healthy)]),
            mutation_score.main([str(broken)]),
        }
        assert outcomes == {0, 2}


class TestTheDefaultPath:
    """Where it looks when nobody says."""

    def test_the_default_is_where_the_tool_writes(self) -> None:
        # The workflow does not pass the path, so a change to either side of
        # this has to be a change to both.
        assert mutation_score.DEFAULT_STATS == "mutants/mutmut-cicd-stats.json"

    def test_the_default_is_used_when_no_path_is_given(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "mutants").mkdir()
        write(tmp_path / "mutants", full(killed=2, survived=0, total=2))
        assert mutation_score.main([]) == 0
