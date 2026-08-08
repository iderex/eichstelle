"""Refuse a tracked audio file.

Issue #6 decides that no audio file is committed to this repository, for a
copyright reason that tolerates no exception: the reference signals an
implementation is supposed to be validated against are part of the purchased
standards, and committing one here would be redistribution. A decision with no
mechanism behind it is an explanation of a rule rather than a rule. This is the
mechanism.

It judges the tracked tree rather than the working tree, so it reports what is
being pushed rather than what somebody happens to have lying around. Both the
path list and the bytes come from the index, never from the filesystem.

Two independent tests run over every tracked path. The first is the extension.
The second is the leading bytes, whatever the file is called, and it exists
because the first is defeated by renaming and because the interesting failure
is a large binary arriving under an innocent name.

It fails closed. Anything that stops the scan completing is a non-zero exit and
never a clean result, because a scanner that cannot run and says nothing is how
a guard of this shape turns into decoration.

Exit codes:

    0   every tracked path was examined and none of them is audio
    1   at least one tracked path was refused
    2   the scan did not complete, so its result is unknown

The escape hatch is the allow list named below. It is tracked and it is empty,
so carrying a file would be a diff a reviewer sees rather than an edit to this
script, and every entry has to state a reason next to the path.

Run it from anywhere inside a checkout:

    python tools/refuse_tracked_audio.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import PurePosixPath

# The allow list, as a path relative to the top of the checkout. It is read
# from the index like everything else, so an untracked copy lying in the
# working tree grants nothing.
ALLOWLIST = "tools/tracked-audio-allowlist.txt"

# How many leading bytes are read per file. Every signature below fits inside
# this window, and reading a fixed prefix is what keeps a large file from being
# pulled into memory to be rejected.
HEAD_BYTES = 16

# Extensions that name an audio container. Lowercased, with the leading dot.
# This half of the check is the cheap one and it is trivially defeated by a
# rename, which is what the signature half is for.
AUDIO_EXTENSIONS = frozenset(
    {
        ".aac",
        ".aif",
        ".aifc",
        ".aiff",
        ".amr",
        ".ape",
        ".au",
        ".bwf",
        ".caf",
        ".dff",
        ".dsf",
        ".flac",
        ".m4a",
        ".m4b",
        ".mka",
        ".mp3",
        ".mp4",
        ".mpc",
        ".oga",
        ".ogg",
        ".opus",
        ".rf64",
        ".snd",
        ".spx",
        ".tta",
        ".w64",
        ".wav",
        ".wave",
        ".webm",
        ".wma",
        ".wv",
    }
)

# Leading-byte signatures. Every pair in a signature must match for it to fire,
# so the container tests that share a chunk header stay distinguishable.
Signature = tuple[str, tuple[tuple[int, bytes], ...]]

SIGNATURES: tuple[Signature, ...] = (
    ("WAVE in a RIFF container", ((0, b"RIFF"), (8, b"WAVE"))),
    ("WAVE in an RF64 container", ((0, b"RF64"), (8, b"WAVE"))),
    ("Wave64", ((0, b"riff\x2e\x91\xcf\x11"),)),
    ("AIFF", ((0, b"FORM"), (8, b"AIFF"))),
    ("AIFF-C", ((0, b"FORM"), (8, b"AIFC"))),
    ("FLAC", ((0, b"fLaC"),)),
    ("Ogg", ((0, b"OggS"),)),
    ("an ID3 tag, which is worn by MP3", ((0, b"ID3"),)),
    ("an ISO base media container, which is worn by MP4 and M4A", ((4, b"ftyp"),)),
    ("Core Audio Format", ((0, b"caff"),)),
    ("Sun or NeXT au", ((0, b".snd"),)),
    ("ASF, which is worn by WMA", ((0, b"\x30\x26\xb2\x75\x8e\x66\xcf\x11"),)),
    ("WavPack", ((0, b"wvpk"),)),
    ("Monkey's Audio", ((0, b"MAC "),)),
    ("Matroska or WebM", ((0, b"\x1a\x45\xdf\xa3"),)),
    ("AMR", ((0, b"#!AMR"),)),
    ("DSDIFF", ((0, b"FRM8"),)),
    ("DSF", ((0, b"DSD "),)),
    ("Musepack", ((0, b"MPCK"),)),
    ("TrueAudio", ((0, b"TTA1"),)),
    ("Shorten", ((0, b"ajkg"),)),
)


class ScanError(Exception):
    """The scan did not complete. Raising this is how the check fails closed."""


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
        # argument below is a literal from this file.
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
    out = run_git(git, ["rev-parse", "--show-toplevel"])
    return out.decode("utf-8", "strict").strip()


def tracked_paths(git: str, root: str) -> list[str]:
    """Return every tracked path, as git records it."""
    out = run_git(git, ["ls-files", "-z"], cwd=root)
    paths = [chunk.decode("utf-8", "surrogateescape") for chunk in out.split(b"\0")]
    return [path for path in paths if path]


def read_heads(git: str, root: str, paths: list[str]) -> dict[str, bytes]:
    """Return the leading bytes of every path, read from the index.

    One `git cat-file --batch` handles the whole list, and the request side of
    that protocol is newline delimited. A path containing a newline cannot be
    asked for through it, so such a path stops the scan instead of being
    skipped quietly.
    """
    for path in paths:
        if "\n" in path:
            raise ScanError(
                f"tracked path contains a newline and cannot be read: {path!r}"
            )
    if not paths:
        return {}
    request = "".join(f":{path}\n" for path in paths).encode("utf-8", "surrogateescape")
    try:
        # S603: as above. The executable is resolved, no shell is involved, and
        # the arguments are literals; only stdin carries repository data.
        completed = subprocess.run(  # noqa: S603
            [git, "cat-file", "--batch"],
            input=request,
            capture_output=True,
            check=False,
            cwd=root,
        )
    except OSError as exc:
        raise ScanError(f"git cat-file could not be started: {exc}") from exc
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", "replace").strip()
        raise ScanError(f"git cat-file exited {completed.returncode}: {detail}")
    return parse_batch(completed.stdout, paths)


def parse_batch(stream: bytes, paths: list[str]) -> dict[str, bytes]:
    """Split one `git cat-file --batch` response into leading bytes per path."""
    heads: dict[str, bytes] = {}
    offset = 0
    for path in paths:
        end = stream.find(b"\n", offset)
        if end < 0:
            raise ScanError(f"git cat-file returned no header for {path}")
        header = stream[offset:end].decode("utf-8", "replace")
        offset = end + 1
        fields = header.rsplit(" ", 2)
        if len(fields) != 3 or not fields[2].isdigit():
            raise ScanError(f"git cat-file could not read {path}: {header}")
        size = int(fields[2])
        if offset + size + 1 > len(stream):
            raise ScanError(f"git cat-file returned a short body for {path}")
        heads[path] = stream[offset : offset + min(size, HEAD_BYTES)]
        offset += size + 1
    if offset != len(stream):
        raise ScanError("git cat-file returned more bodies than were asked for")
    return heads


def parse_allowlist(text: str) -> dict[str, str]:
    """Return the allowed paths and the reason given for each.

    A line naming a path with no reason beside it is an error rather than an
    entry, because an exception nobody had to justify is the shape this list
    exists to prevent.
    """
    allowed: dict[str, str] = {}
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split(None, 1)
        if len(fields) != 2 or not fields[1].strip():
            raise ScanError(
                f"{ALLOWLIST} line {number} names a path with no reason beside it: {line}"
            )
        path, reason = fields[0], fields[1].strip()
        if path in allowed:
            raise ScanError(f"{ALLOWLIST} line {number} repeats the path {path}")
        allowed[path] = reason
    return allowed


def read_allowlist(git: str, root: str, tracked: list[str]) -> dict[str, str]:
    """Read the allow list from the index and check every entry resolves."""
    if ALLOWLIST not in tracked:
        raise ScanError(f"{ALLOWLIST} is not tracked, so no exception can be read")
    raw = run_git(git, ["cat-file", "blob", f":{ALLOWLIST}"], cwd=root)
    try:
        text = raw.decode("utf-8", "strict")
    except UnicodeDecodeError as exc:
        raise ScanError(f"{ALLOWLIST} is not UTF-8: {exc}") from exc
    allowed = parse_allowlist(text)
    for path in allowed:
        if path not in tracked:
            raise ScanError(
                f"{ALLOWLIST} names {path}, which is not tracked, "
                "so the list no longer says what it appears to say"
            )
    return allowed


def looks_like_mpeg_frame(head: bytes) -> bool:
    """Report whether the leading bytes are a valid MPEG audio frame header.

    Eleven set bits are a weak signal on their own, so the reserved encodings
    of the fields that follow them are checked as well. Without that a run of
    high bytes in any binary reads as an MP3.
    """
    if len(head) < 4 or head[0] != 0xFF or head[1] & 0xE0 != 0xE0:
        return False
    version = (head[1] >> 3) & 0x03
    layer = (head[1] >> 1) & 0x03
    bitrate = (head[2] >> 4) & 0x0F
    sampling = (head[2] >> 2) & 0x03
    return (
        version != 0x01
        and layer != 0x00
        and bitrate not in (0x00, 0x0F)
        and sampling != 0x03
    )


def signature_of(head: bytes) -> str | None:
    """Return the name of the container the leading bytes belong to, if any."""
    for name, tests in SIGNATURES:
        if all(head[at : at + len(want)] == want for at, want in tests):
            return name
    if looks_like_mpeg_frame(head):
        return "an MPEG audio frame header, which is worn by MP3"
    return None


def extension_of(path: str) -> str:
    """Return the lowercased extension of a path, with its leading dot."""
    return PurePosixPath(path).suffix.lower()


def scan(git: str, root: str) -> tuple[dict[str, str], list[str]]:
    """Return the allowed paths with their reasons, and one line per refusal."""
    tracked = tracked_paths(git, root)
    allowed = read_allowlist(git, root, tracked)
    heads = read_heads(git, root, tracked)
    refusals: list[str] = []
    for path in tracked:
        if path in allowed:
            continue
        reasons: list[str] = []
        extension = extension_of(path)
        if extension in AUDIO_EXTENSIONS:
            reasons.append(f"the extension {extension} names an audio container")
        signature = signature_of(heads.get(path, b""))
        if signature is not None:
            reasons.append(f"the leading bytes are {signature}")
        if reasons:
            refusals.append(f"{path}: {' and '.join(reasons)}")
    return allowed, refusals


def main() -> int:
    """Scan the tracked tree and return the process exit code."""
    try:
        git = git_path()
        root = repository_root(git)
        allowed, refusals = scan(git, root)
    except ScanError as exc:
        print(f"tracked audio scan did not complete: {exc}", file=sys.stderr)
        print("failing closed: the result of this scan is unknown", file=sys.stderr)
        return 2
    for path, reason in sorted(allowed.items()):
        print(f"allowed: {path}: {reason}")
    if refusals:
        for line in sorted(refusals):
            print(f"refused: {line}", file=sys.stderr)
        print(
            f"{len(refusals)} tracked path(s) refused. Issue #6 decides that no audio "
            f"file is committed here. To carry one, add it to {ALLOWLIST} with a reason.",
            file=sys.stderr,
        )
        return 1
    print("no tracked path is audio")
    return 0


if __name__ == "__main__":
    sys.exit(main())
