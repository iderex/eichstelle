"""Refuse a tracked line that breaks one of this project's invariants.

Issue #49 asks for this project's own invariants as lint rules that refuse. The
rules are in `tools/invariants.toml`, one entry per invariant, each naming the
decision it comes from and the mistake it catches. This file is only the engine:
it loads that set, refuses a rule that is not fully declared, and matches what
is left against the tracked tree.

It judges the index rather than the working tree, so it reports what is being
pushed rather than what somebody happens to have lying around. The rule file,
the allow list entries inside it and the file contents all come from the index,
which means a rule cannot be weakened by an untracked copy.

It fails closed. A rule file that will not parse, a rule missing a field, a
pattern that will not compile and an allow list entry naming a path nobody
tracks are each a non-zero exit and never a clean result, because a linter that
could not run and said nothing is how a guard of this shape turns into
decoration.

Exit codes:

    0   every selected path was examined and no rule matched
    1   at least one line was refused
    2   the run did not complete, so its result is unknown

What it is not. These are token-level pattern matches over source text, which
anybody who wants to write the same shape a different way can walk through. Each
rule states its own edge in its `bound` field and the run prints those edges, so
that a green result is read as the floor it is. `docs/quality-gates.md` says how
a rule is added and `docs/ci-checks.md` says what a failure means.

Run it from anywhere inside a checkout:

    python tools/invariants.py
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from typing import Any

# The rule file, as a path relative to the top of the checkout. Read from the
# index like everything else.
RULES = "tools/invariants.toml"

# What a rule has to declare. The first three are what a reader meets in a red
# check; `bound` is what stops the rule reading as airtight; `prompted_by` is
# the place to record which defect asked for it. A rule missing any of them is
# refused rather than run, because the message a match produces is the whole
# value of the match.
REQUIRED = ("id", "decision", "mistake", "bound", "prompted_by", "paths", "patterns")

# How much of a matching line is quoted back. A refusal names the file and the
# line number, so the quote is an aid to recognition rather than the evidence,
# and an unbounded one turns a minified file into a wall.
QUOTE = 160


class ScanError(Exception):
    """The run did not complete. Raising this is how the check fails closed."""


@dataclass(frozen=True)
class Rule:
    """One invariant: what it refuses, where it looks, and what it cannot see."""

    id: str
    decision: str
    mistake: str
    bound: str
    prompted_by: str
    paths: tuple[str, ...]
    suffixes: tuple[str, ...]
    patterns: tuple[re.Pattern[str], ...]
    allow: dict[str, str]

    def selects(self, path: str) -> bool:
        """Whether this rule reads the given tracked path."""
        under = any(
            path == entry or (entry.endswith("/") and path.startswith(entry))
            for entry in self.paths
        )
        if not under:
            return False
        return not self.suffixes or path.endswith(self.suffixes)


def git_path() -> str:
    """Return the path to git, or raise if there is none to run."""
    found = shutil.which("git")
    if found is None:
        raise ScanError("git is not on PATH, so the tracked tree cannot be read")
    return found


def run_git(git: str, args: list[str], cwd: str | None = None) -> bytes:
    """Run git and return its standard output, raising on any failure."""
    try:
        # S603: the executable is resolved by shutil.which rather than by the
        # shell searching a partial name, no shell is involved, and every
        # argument below is a literal from this file or a tracked path.
        completed = subprocess.run(  # noqa: S603
            [git, *args],
            capture_output=True,
            check=False,
            cwd=cwd,
        )
    except OSError as exc:
        raise ScanError(f"git {' '.join(args)} could not be started: {exc}") from exc
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", "replace").strip()
        raise ScanError(f"git {' '.join(args)} exited {completed.returncode}: {detail}")
    return completed.stdout


def repository_root(git: str) -> str:
    """Return the top of the checkout this script was invoked inside."""
    return run_git(git, ["rev-parse", "--show-toplevel"]).decode("utf-8").strip()


def tracked_paths(git: str, root: str) -> list[str]:
    """Return every tracked path, as git records it."""
    out = run_git(git, ["ls-files", "-z"], cwd=root)
    return [
        chunk.decode("utf-8", "surrogateescape") for chunk in out.split(b"\0") if chunk
    ]


def read_blob(git: str, root: str, path: str) -> str:
    """Return one tracked file's contents from the index, decoded as UTF-8."""
    raw = run_git(git, ["cat-file", "blob", f":{path}"], cwd=root)
    try:
        return raw.decode("utf-8", "strict")
    except UnicodeDecodeError as exc:
        raise ScanError(
            f"{path} is not UTF-8, so it cannot be read as text: {exc}"
        ) from exc


def _text(entry: dict[str, Any], field: str, where: str) -> str:
    """Return a required string field, refusing an empty or absent one."""
    value = entry.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ScanError(f"{where} declares no {field}, so it may not run")
    return value


def _strings(entry: dict[str, Any], field: str, where: str) -> tuple[str, ...]:
    """Return a required list-of-strings field, refusing anything else."""
    value = entry.get(field, [])
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ScanError(
            f"{where} declares {field} as something other than a list of text"
        )
    return tuple(value)


def rule_from(entry: dict[str, Any], where: str) -> Rule:
    """Build one rule, refusing anything it has not fully declared."""
    missing = [field for field in REQUIRED if field not in entry]
    if missing:
        raise ScanError(f"{where} is missing {', '.join(sorted(missing))}")
    identifier = _text(entry, "id", where)
    where = f"{RULES} rule {identifier}"
    paths = _strings(entry, "paths", where)
    if not paths:
        raise ScanError(f"{where} selects no path, so it can refuse nothing")
    expressions = _strings(entry, "patterns", where)
    if not expressions:
        raise ScanError(f"{where} carries no pattern, so it can refuse nothing")
    compiled = []
    for expression in expressions:
        try:
            compiled.append(re.compile(expression))
        except re.error as exc:
            raise ScanError(
                f"{where} carries a pattern that will not compile: {exc}"
            ) from exc
    allow: dict[str, str] = {}
    for exemption in entry.get("allow", []):
        if not isinstance(exemption, dict):
            raise ScanError(f"{where} carries an exemption that is not a table")
        path = _text(exemption, "path", f"{where} exemption")
        reason = _text(exemption, "reason", f"{where} exemption for {path}")
        if path in allow:
            raise ScanError(f"{where} exempts {path} twice")
        allow[path] = reason
    return Rule(
        id=identifier,
        decision=_text(entry, "decision", where),
        mistake=_text(entry, "mistake", where),
        bound=_text(entry, "bound", where),
        prompted_by=_text(entry, "prompted_by", where),
        paths=paths,
        suffixes=_strings(entry, "suffixes", where),
        patterns=tuple(compiled),
        allow=allow,
    )


def rules_from(text: str) -> list[Rule]:
    """Parse the rule file, refusing a set that is empty or repeats an id."""
    try:
        document = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise ScanError(f"{RULES} will not parse: {exc}") from exc
    entries = document.get("rule", [])
    if not isinstance(entries, list) or not entries:
        raise ScanError(f"{RULES} declares no rule, so this check would assert nothing")
    rules: list[Rule] = []
    seen: set[str] = set()
    for number, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            raise ScanError(f"{RULES} rule {number} is not a table")
        rule = rule_from(entry, f"{RULES} rule {number}")
        if rule.id in seen:
            raise ScanError(f"{RULES} declares the id {rule.id} twice")
        seen.add(rule.id)
        rules.append(rule)
    return rules


def load(git: str, root: str, tracked: list[str]) -> list[Rule]:
    """Read the rule file from the index and check every exemption resolves."""
    if RULES not in tracked:
        raise ScanError(f"{RULES} is not tracked, so no rule can be read")
    rules = rules_from(read_blob(git, root, RULES))
    for rule in rules:
        for path in rule.allow:
            if path not in tracked:
                raise ScanError(
                    f"{RULES} rule {rule.id} exempts {path}, which is not tracked, "
                    "so the list no longer says what it appears to say"
                )
    return rules


def matches(rule: Rule, path: str, text: str) -> list[str]:
    """Return one line per match of this rule in this file's text."""
    if path in rule.allow:
        return []
    found: list[str] = []
    for number, line in enumerate(text.splitlines(), start=1):
        for pattern in rule.patterns:
            if pattern.search(line):
                found.append(f"{path}:{number}: {line.strip()[:QUOTE]}")
                break
    return found


def scan(
    git: str, root: str
) -> tuple[list[Rule], dict[str, int], list[tuple[Rule, str]]]:
    """Return the rules, how many paths each read, and every refusal."""
    tracked = tracked_paths(git, root)
    rules = load(git, root, tracked)
    read: dict[str, int] = {rule.id: 0 for rule in rules}
    refusals: list[tuple[Rule, str]] = []
    for path in tracked:
        selecting = [rule for rule in rules if rule.selects(path)]
        if not selecting:
            continue
        text = read_blob(git, root, path)
        for rule in selecting:
            read[rule.id] += 1
            refusals.extend((rule, line) for line in matches(rule, path, text))
    return rules, read, refusals


def report(rules: list[Rule], read: dict[str, int]) -> None:
    """Say what was examined, so a green result cannot be read as more."""
    for rule in rules:
        print(f"{rule.id}: {read[rule.id]} tracked path(s) read")
        for path, reason in sorted(rule.allow.items()):
            print(f"  allowed: {path}: {reason}")
        if read[rule.id] == 0:
            print(
                f"  nothing selected this rule at this commit: {', '.join(rule.paths)}"
            )
        print(f"  bound: {rule.bound}")


def main() -> int:
    """Scan the tracked tree against the rule file and return the exit code."""
    try:
        git = git_path()
        root = repository_root(git)
        rules, read, refusals = scan(git, root)
    except ScanError as exc:
        print(f"invariant check did not complete: {exc}", file=sys.stderr)
        print("failing closed: the result of this check is unknown", file=sys.stderr)
        return 2
    report(rules, read)
    if refusals:
        for rule, line in refusals:
            print(f"refused [{rule.id}] {line}", file=sys.stderr)
        for rule in sorted(
            {rule.id: rule for rule, _ in refusals}.values(), key=lambda r: r.id
        ):
            print(
                f"\n[{rule.id}]\n  {rule.decision}\n  The mistake: {rule.mistake}",
                file=sys.stderr,
            )
        print(
            f"\n{len(refusals)} line(s) refused. Issue #49 is where these rules come from "
            f"and {RULES} is where each one is written.",
            file=sys.stderr,
        )
        return 1
    print(f"no tracked line matched any of the {len(rules)} rule(s)")
    print("these are pattern matches over source text, so read this as a floor")
    return 0


if __name__ == "__main__":
    sys.exit(main())
