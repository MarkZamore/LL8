#!/usr/bin/env python3
"""Verify that the published rolling release matches its own pack-manifest.

Polls the release's pack-manifest.json until it is present (and, with
--expect-revision, until it was built from that commit), then cross-checks the
release's real asset list against the manifest: every manifest asset must
exist with the exact size, and nothing else may be attached (only
pack-manifest.json itself is expected on top). Finally a random sample of
assets is downloaded and sha256-compared, proving the CDN serves the bytes
the manifest promises.

Needs the `gh` CLI (authenticated) for the asset listing. Stdlib otherwise.

Usage:
  python tools/verify_release.py --repo MarkZamore/LL8 --tag pack-latest \
      [--expect-revision SHA] [--sample 5] [--timeout-min 40]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import subprocess
import sys
import time
import urllib.error
import urllib.request

CHUNK = 1 << 20
POLL_SECONDS = 20
USER_AGENT = "LL8-verify/1.0"


def fetch_bytes(url: str, timeout: int = 120) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read()


def fetch_sha256_and_size(url: str) -> tuple[str, int]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    digest = hashlib.sha256()
    size = 0
    with urllib.request.urlopen(req, timeout=300) as response:
        while chunk := response.read(CHUNK):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def gh_json(path: str):
    result = subprocess.run(["gh", "api", path], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"error: gh api {path} failed:\n{result.stderr.strip()}",
              file=sys.stderr)
        sys.exit(1)
    return json.loads(result.stdout)


def wait_for_manifest(repo: str, tag: str, expect_revision: str | None,
                      timeout_min: float) -> dict:
    deadline = time.monotonic() + timeout_min * 60
    attempt = 0
    while True:
        attempt += 1
        # The cache-buster defeats the CDN so a freshly replaced release is
        # seen as soon as GitHub serves it.
        url = (f"https://github.com/{repo}/releases/download/{tag}/"
               f"pack-manifest.json?cache={int(time.time() * 1000)}")
        try:
            manifest = json.loads(fetch_bytes(url, timeout=60))
            revision = manifest.get("revision")
            if not expect_revision or revision == expect_revision:
                print(f"manifest present (revision {revision})")
                return manifest
            print(f"  attempt {attempt}: manifest revision {revision}, "
                  f"waiting for {expect_revision}")
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            print(f"  attempt {attempt}: manifest not ready ({exc})")
        if time.monotonic() > deadline:
            print("error: timed out waiting for pack-manifest.json",
                  file=sys.stderr)
            sys.exit(1)
        time.sleep(POLL_SECONDS)


def list_release_assets(repo: str, tag: str) -> dict[str, int]:
    release = gh_json(f"repos/{repo}/releases/tags/{tag}")
    release_id = release["id"]
    assets: dict[str, int] = {}
    page = 1
    while True:
        chunk = gh_json(f"repos/{repo}/releases/{release_id}/assets"
                        f"?per_page=100&page={page}")
        for asset in chunk:
            assets[asset["name"]] = asset["size"]
        if len(chunk) < 100:
            return assets
        page += 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify the rolling pack release against its manifest.")
    parser.add_argument("--repo", default="MarkZamore/LL8")
    parser.add_argument("--tag", default="pack-latest")
    parser.add_argument("--expect-revision", default=None)
    parser.add_argument("--sample", type=int, default=5,
                        help="random assets to download and sha256-check")
    parser.add_argument("--timeout-min", type=float, default=40)
    args = parser.parse_args()

    manifest = wait_for_manifest(args.repo, args.tag, args.expect_revision,
                                 args.timeout_min)
    expected = {asset["name"]: asset for asset in manifest.get("assets", [])}
    if not expected:
        print("error: manifest lists no assets", file=sys.stderr)
        return 1
    actual = list_release_assets(args.repo, args.tag)

    problems: list[str] = []
    for name, asset in sorted(expected.items()):
        size = actual.get(name)
        if size is None:
            problems.append(f"missing asset: {name}")
        elif size != asset["sizeBytes"]:
            problems.append(f"size mismatch: {name} expected "
                            f"{asset['sizeBytes']}, release has {size}")
    for name in sorted(actual):
        if name not in expected and name != "pack-manifest.json":
            problems.append(f"unexpected asset: {name}")
    if "pack-manifest.json" not in actual:
        problems.append("pack-manifest.json is not attached to the release")

    sample = random.sample(sorted(expected), min(args.sample, len(expected)))
    for name in sample:
        url = (f"https://github.com/{args.repo}/releases/download/"
               f"{args.tag}/{name}")
        try:
            sha256, size = fetch_sha256_and_size(url)
        except (urllib.error.URLError, TimeoutError) as exc:
            problems.append(f"sample download failed: {name} ({exc})")
            continue
        asset = expected[name]
        if sha256 != asset["sha256"] or size != asset["sizeBytes"]:
            problems.append(f"sample content mismatch: {name} "
                            f"sha256 {sha256} size {size}, expected "
                            f"{asset['sha256']} / {asset['sizeBytes']}")
        else:
            print(f"sample ok: {name}")

    print(f"manifest assets: {len(expected)}, release assets: {len(actual)}, "
          f"sampled: {len(sample)}")
    if problems:
        for problem in problems:
            print(f"PROBLEM: {problem}", file=sys.stderr)
        return 1
    print("release verified: assets complete, sizes match, sample hashes ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
