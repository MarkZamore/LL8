#!/usr/bin/env python3
"""Fetches the files that are too large to live in git, straight into the pack.

GitHub refuses a file over 100 MB, and Cobblemon is 123 MB; a 65 MB resource
pack would be committed twice over, once in the tree and once as an overlay
source. Such a file is not committed at all: tools/remote-files.json says where
it lives and what its SHA-256 must be, this fetches it before anything reads
those folders, and a file whose hash does not match is deleted rather than
used. So the pack still ships one exact copy to every player - the guarantee
just comes from the hash instead of from git holding the bytes.

Stdlib only, no arguments needed:

    python tools/fetch_remote_files.py [--check]

--check verifies what is already on disk and downloads nothing; it exits 1 if
anything is missing, which is how a local checkout learns it needs a fetch.

Exit codes: 0 everything present and correct, 1 a file is missing or wrong,
2 the list itself is unreadable.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parent
LIST = TOOLS / "remote-files.json"
ATTEMPTS = 3
CHUNK = 1 << 20


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


def download(url: str, destination: Path) -> None:
    """Downloads beside the target and moves it into place once it is whole."""
    partial = destination.with_suffix(destination.suffix + ".part")
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "LL8-pack/1.0 (+github.com/MarkZamore/LL8)"})
    with urllib.request.urlopen(request, timeout=120) as response, partial.open("wb") as handle:
        while True:
            block = response.read(CHUNK)
            if not block:
                break
            handle.write(block)
    partial.replace(destination)


def fetch(entry: dict, check_only: bool) -> tuple[bool, str]:
    """(ok, what happened) for one entry."""
    target = REPO / entry["target"]
    expected = entry["sha256"]

    if target.is_file():
        actual = sha256_of(target)
        if actual == expected:
            return True, f"{entry['target']} already here"
        # A wrong file is worse than none: it would be published as if it were
        # the real thing, so it goes before anything else looks at the pack.
        target.unlink()
        if check_only:
            return False, f"{entry['target']} had the wrong hash ({actual}) and was removed"

    if check_only:
        return False, f"{entry['target']} is missing"

    last = ""
    for attempt in range(1, ATTEMPTS + 1):
        try:
            download(entry["url"], target)
        except (urllib.error.URLError, TimeoutError, OSError) as failure:
            last = f"{type(failure).__name__}: {failure}"
            continue
        actual = sha256_of(target)
        if actual == expected:
            size = target.stat().st_size
            return True, f"{entry['target']} fetched, {size / 1048576:.1f} MiB, hash matches"
        target.unlink()
        last = f"hash mismatch: expected {expected}, got {actual}"
        if attempt == ATTEMPTS:
            break
    return False, f"{entry['target']} could not be fetched ({last})"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="verify only, download nothing")
    args = parser.parse_args()

    try:
        listed = json.loads(LIST.read_text(encoding="utf-8"))["files"]
    except (OSError, ValueError, KeyError) as failure:
        print(f"cannot read {LIST.relative_to(REPO)}: {failure}", file=sys.stderr)
        return 2

    problems = 0
    for entry in listed:
        ok, message = fetch(entry, args.check)
        print(("  " if ok else "  !! ") + message)
        problems += 0 if ok else 1

    print(f"{len(listed)} remote file(s), {problems} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
