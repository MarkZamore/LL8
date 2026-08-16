#!/usr/bin/env python3
"""One-command updater: rebuild the LL8 checkout from the newest upstream release.

Pulls the requested TNP Limitless 8 release (CurseForge project 1027782) into a
work directory, stages a complete verified pack tree (manifest downloads plus
override files plus reuse sources for author-blocked jars), then rewrites the
managed roots of this checkout to match, applies the local overlay
(tools/overlay.json), regenerates portable-pack.json, gates on the dependency
scanner and finally commits/pushes in push-sized slices.

Pipeline (one function per stage, in run order):
  resolve_release -> fetch_client -> index_files -> index_reuse -> stage
  -> scan_versions/diff_mods -> [--dry-run stops here] -> sync_managed_roots
  -> apply_overlay -> write_portable_pack -> run_scan -> world_impact
  -> write_update_log + state -> git_publish [-> --wait-release verify]

Exit codes:
  0  updated, or already up to date
  2  author-blocked files need manual download (checkout left untouched)
  3  overlay / portable-pack failure
  4  scan gate failed, or --strict-world found world items of removed mods
  5  git preconditions / push failure

Stdlib only (Python 3.12). The CurseForge API key comes from --api-key, the
CURSEFORGE_API_KEY environment variable, or ~/.curseforge/api-key.txt; it is
never printed.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import fnmatch
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_DIR.parent
sys.path.insert(0, str(TOOLS_DIR))
import scan_mods  # noqa: E402  (repo-local import, needs sys.path above)

API = "https://api.curseforge.com"
PROJECT_LL8 = 1027782
GITHUB_REPO = "MarkZamore/LL8"
STATE_FILE = TOOLS_DIR / "ll8-state.json"
OVERLAY_FILE = TOOLS_DIR / "overlay.json"
UPDATE_LOG = REPO_ROOT / "UPDATE-LOG.md"

CHUNK = 1 << 20
BATCH = 50
DOWNLOAD_WORKERS = 6
USER_AGENT = "LL8-update/1.0"

# CurseForge project classId -> directory the file loads from at runtime.
# Resource/shader packs load from the instance roots; datapacks load via paxi.
CLASS_ROUTES = {6: "mods", 12: "resourcepacks", 6552: "shaderpacks",
                6945: "config/paxi/datapacks"}
# Reuse sources are probed at these subpaths, mirroring CLASS_ROUTES, so a
# plain pack checkout (this repo, or the old Infinity one) works as --reuse.
REUSE_SUBPATHS = ("mods", "resourcepacks", "shaderpacks", "config/paxi/datapacks")

# Directory trees this tool owns end-to-end: rebuilt from the staged release
# on every update. Everything else in the checkout (tools/, README, workflows,
# the client jar) is never touched by the sync.
MANAGED_ROOTS = ("mods", "config", "kubejs", "defaultconfigs",
                 "configureddefaults", "resourcepacks", "shaderpacks",
                 "scripts", "data")
# Override trees copied verbatim from the client zip (subset of MANAGED_ROOTS;
# overrides/mods is special-cased because its jars merge with manifest mods).
OVERRIDE_TREES = ("config", "kubejs", "defaultconfigs", "configureddefaults",
                  "resourcepacks", "shaderpacks", "scripts", "data")

EXIT_MANUAL = 2
EXIT_OVERLAY = 3
EXIT_SCAN = 4
EXIT_GIT = 5


def fail(code: int, message: str) -> "NoReturn":  # noqa: F821
    print(f"error: {message}", file=sys.stderr)
    sys.exit(code)


# ---------------------------------------------------------------- hashing / http

_sha1_memo: dict[Path, str] = {}


def sha1_of(path: Path) -> str:
    cached = _sha1_memo.get(path)
    if cached is not None:
        return cached
    digest = hashlib.sha1()
    with open(path, "rb") as handle:
        while chunk := handle.read(CHUNK):
            digest.update(chunk)
    value = digest.hexdigest()
    _sha1_memo[path] = value
    return value


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while chunk := handle.read(CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def request_json(url: str, api_key: str, payload: dict | None = None) -> dict:
    body = None if payload is None else json.dumps(payload).encode()
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, data=body, headers={
                "x-api-key": api_key,
                "Accept": "application/json",
                "User-Agent": USER_AGENT,
                **({"Content-Type": "application/json"} if body else {}),
            })
            with urllib.request.urlopen(req, timeout=60) as response:
                return json.load(response)
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt == 3:
                raise
            wait = 5 * (attempt + 1)
            print(f"  retry in {wait}s: {url} ({exc})")
            time.sleep(wait)
    raise AssertionError("unreachable")


def download_file(url: str, destination: Path, label: str,
                  expected_sha1: str | None) -> str | None:
    """Download with .part staging, sha1 verification and retries.

    Returns None on success or an error string (the caller aggregates them so
    one flaky CDN file does not abort an 800-jar batch mid-flight).
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = destination.with_suffix(destination.suffix + ".part")
    last_error = "unknown"
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=120) as response, \
                    open(temp, "wb") as out:
                shutil.copyfileobj(response, out, CHUNK)
            if expected_sha1:
                digest = hashlib.sha1()
                with open(temp, "rb") as handle:
                    while chunk := handle.read(CHUNK):
                        digest.update(chunk)
                actual = digest.hexdigest()
                if actual != expected_sha1:
                    last_error = f"sha1 {actual} != {expected_sha1}"
                    temp.unlink(missing_ok=True)
                    time.sleep(5 * (attempt + 1))
                    continue
            temp.replace(destination)
            _sha1_memo.pop(destination, None)
            return None
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = str(exc)
            time.sleep(10 * (attempt + 1))
    temp.unlink(missing_ok=True)
    return f"{label}: {last_error}"


def extract_zip(archive: Path, destination: Path) -> None:
    if destination.exists():
        return
    print(f"extracting {archive.name} ...")
    staging = destination.with_name(destination.name + ".extracting")
    if staging.exists():
        shutil.rmtree(staging)
    with zipfile.ZipFile(archive) as bundle:
        bundle.extractall(staging)
    staging.replace(destination)


def default_api_key() -> str:
    value = os.environ.get("CURSEFORGE_API_KEY", "").strip()
    if value:
        return value
    stored = Path.home() / ".curseforge" / "api-key.txt"
    return stored.read_text(encoding="utf-8").strip() if stored.exists() else ""


def load_state() -> dict | None:
    if not STATE_FILE.is_file():
        return None
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


# ---------------------------------------------------------------- resolve / fetch

def file_sha1_from_api(info: dict) -> str | None:
    for entry in info.get("hashes", []):
        if entry.get("algo") == 1:  # 1 = sha1, 2 = md5
            return (entry.get("value") or "").lower() or None
    return None


def version_from_display(info: dict) -> str:
    match = re.search(r"\d+(?:\.\d+)+", info.get("displayName", ""))
    return match.group() if match else str(info["id"])


def resolve_release(args, api_key: str) -> tuple[dict, str]:
    """Pick the client release file to install and its human version string."""
    if args.file_id:
        info = request_json(f"{API}/v1/mods/{PROJECT_LL8}/files/{args.file_id}",
                            api_key)["data"]
        if info.get("isServerPack"):
            fail(1, f"file {args.file_id} is a server pack, not a client file")
        return info, version_from_display(info)

    allowed_types = {1, 2} if args.allow_beta else {1}
    chosen: dict | None = None
    index = 0
    while True:
        page = request_json(
            f"{API}/v1/mods/{PROJECT_LL8}/files?pageSize=50&index={index}", api_key)
        data = page.get("data", [])
        for info in data:
            if info.get("isServerPack") or info.get("releaseType") not in allowed_types:
                continue
            if args.version and version_from_display(info) != args.version:
                continue
            if chosen is None or info["id"] > chosen["id"]:
                chosen = info
        index += len(data)
        total = page.get("pagination", {}).get("totalCount", index)
        # Newest files come first: for "latest" the first page that yields any
        # candidate already contains the maximal id; a pinned --version may sit
        # deeper in history and needs more pages.
        if chosen is not None and not args.version:
            break
        if not data or index >= total:
            break
    if chosen is None:
        wanted = args.version or "latest release"
        fail(1, f"no matching client release found for {wanted}")
    return chosen, version_from_display(chosen)


def fetch_client(client_info: dict, version: str, work: Path) -> tuple[dict, Path, str]:
    """Download + extract the client zip; return (manifest, extractedRoot, loaderId)."""
    zip_path = work / "sources" / f"ll8-client-{version}.zip"
    expected = file_sha1_from_api(client_info)
    if zip_path.is_file() and expected and sha1_of(zip_path) != expected:
        print(f"cached {zip_path.name} has a stale sha1; re-downloading")
        zip_path.unlink()
        _sha1_memo.pop(zip_path, None)
    if not zip_path.is_file():
        print(f"downloading {zip_path.name} ...")
        error = download_file(client_info["downloadUrl"], zip_path,
                              zip_path.name, expected)
        if error:
            fail(1, f"client zip download failed: {error}")
    client_root = work / f"client-{version}"
    extract_zip(zip_path, client_root)

    manifest_path = client_root / "manifest.json"
    if not manifest_path.is_file():
        fail(1, f"client zip has no manifest.json: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    game = manifest.get("minecraft", {})
    if game.get("version") != "1.21.1":
        fail(1, f"manifest is for Minecraft {game.get('version')!r}, expected "
                "1.21.1 - a game version bump needs a human decision first")
    loaders = game.get("modLoaders", [])
    primary = next((entry for entry in loaders if entry.get("primary")),
                   loaders[0] if loaders else None)
    if primary is None or not primary.get("id"):
        fail(1, "manifest has no mod loader entry")
    print(f"manifest: minecraft {game.get('version')} loader {primary['id']} "
          f"files {len(manifest.get('files', []))}")
    return manifest, client_root, primary["id"]


# ---------------------------------------------------------------- index_files

@dataclass
class Entry:
    file_id: int
    project_id: int
    file_name: str
    route: str
    sha1: str | None
    download_url: str | None
    slug: str
    website: str
    status: str = ""


def index_files(manifest: dict, api_key: str, cache_dir: Path,
                refresh: bool) -> list[Entry]:
    cache_dir.mkdir(parents=True, exist_ok=True)

    def cached_json(name: str, producer) -> dict:
        path = cache_dir / name
        if path.is_file() and not refresh:
            return json.loads(path.read_text(encoding="utf-8"))
        data = producer()
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return data

    raw_entries = manifest.get("files", [])
    file_ids = sorted({entry["fileID"] for entry in raw_entries})
    file_index: dict[int, dict] = {}
    for start in range(0, len(file_ids), BATCH):
        chunk = file_ids[start:start + BATCH]
        blob = cached_json(f"files-{start:04}.json", lambda chunk=chunk: request_json(
            f"{API}/v1/mods/files", api_key, {"fileIds": chunk}))
        for info in blob.get("data", []):
            file_index[info["id"]] = info
    project_ids = sorted({entry["projectID"] for entry in raw_entries})
    project_index: dict[int, dict] = {}
    for start in range(0, len(project_ids), BATCH):
        chunk = project_ids[start:start + BATCH]
        blob = cached_json(f"mods-{start:04}.json", lambda chunk=chunk: request_json(
            f"{API}/v1/mods", api_key, {"modIds": chunk}))
        for info in blob.get("data", []):
            project_index[info["id"]] = info

    entries: list[Entry] = []
    unknown_class: list[str] = []
    no_data: list[str] = []
    for raw in raw_entries:
        info = file_index.get(raw["fileID"])
        project = project_index.get(raw["projectID"], {})
        slug = project.get("slug", str(raw["projectID"]))
        if info is None:
            no_data.append(f"{slug} file {raw['fileID']}")
            continue
        class_id = project.get("classId")
        route = CLASS_ROUTES.get(class_id)
        if route is None:
            unknown_class.append(f"{slug} / {info['fileName']} (classId={class_id})")
            continue
        links = project.get("links") or {}
        entries.append(Entry(
            file_id=info["id"],
            project_id=raw["projectID"],
            file_name=info["fileName"],
            route=route,
            sha1=file_sha1_from_api(info),
            download_url=info.get("downloadUrl") or None,
            slug=slug,
            website=links.get("websiteUrl")
                    or f"https://www.curseforge.com/projects/{raw['projectID']}",
        ))
    if no_data:
        fail(1, "API returned no metadata for: " + ", ".join(no_data))
    if unknown_class:
        fail(1, "unknown classId (add a route to CLASS_ROUTES): "
                + ", ".join(unknown_class))
    seen: dict[str, str] = {}
    duplicates: list[str] = []
    for entry in entries:
        prior = seen.get(entry.file_name)
        if prior is not None:
            duplicates.append(f"{entry.file_name} ({prior} and {entry.slug})")
        seen[entry.file_name] = entry.slug
    if duplicates:
        fail(1, "duplicate fileName in manifest: " + ", ".join(duplicates))
    return entries


# ---------------------------------------------------------------- index_reuse

class ReuseIndex:
    """Filename -> candidate paths, sha1-verified lazily on first use.

    Sources, in priority order: this checkout's own routed dirs (indexed BEFORE
    the sync wipes them), every --reuse dir at the same subpaths, the manual
    drop folder, and the permanent content-addressed blocked-file cache.
    """

    def __init__(self, reuse_dirs: list[Path], work: Path) -> None:
        self.candidates: dict[str, list[Path]] = {}
        roots: list[Path] = []
        for base in [REPO_ROOT, *reuse_dirs]:
            roots.extend(base / sub for sub in REUSE_SUBPATHS)
        roots.append(work / "manual")
        cache_root = work / "cache"
        if cache_root.is_dir():
            roots.extend(sorted(child for child in cache_root.iterdir()
                                if child.is_dir()))
        for root in roots:
            if not root.is_dir():
                continue
            for item in sorted(root.iterdir()):
                if item.is_file():
                    self.candidates.setdefault(item.name, []).append(item)

    def resolve(self, file_name: str, expected_sha1: str | None) -> Path | None:
        for candidate in self.candidates.get(file_name, []):
            if expected_sha1:
                actual = sha1_of(candidate)
                if actual != expected_sha1:
                    print(f"  note: {candidate} sha1 mismatch "
                          f"({actual} != {expected_sha1}); skipped")
                    continue
            return candidate
        return None


# ---------------------------------------------------------------- stage

def cache_blocked_copy(work: Path, entry: Entry, source: Path) -> None:
    """Keep a permanent verified copy of an author-blocked file.

    Reuse sources (the old Infinity checkout in particular) will eventually be
    deleted; the content-addressed cache is what keeps future re-installs of
    the same blocked file fully automatic.
    """
    if not entry.sha1:
        return
    target = work / "cache" / entry.sha1 / entry.file_name
    if not target.is_file():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def stage(entries: list[Entry], version: str, work: Path, client_root: Path,
          reuse: ReuseIndex) -> tuple[Path, list[str], list[Entry]]:
    """Build <work>/staged-<version>: the complete new pack tree.

    Returns (stagedDir, overrideJarNames, missingEntries). The checkout is not
    touched here; on missing blocked files the caller exits 2 with reports.
    """
    staged = work / f"staged-{version}"
    overrides = client_root / "overrides"

    for tree in OVERRIDE_TREES:
        destination = staged / tree
        if destination.exists():
            shutil.rmtree(destination)
        source = overrides / tree
        if source.is_dir():
            shutil.copytree(source, destination)
    handled = set(OVERRIDE_TREES) | {"mods", "local"}
    if overrides.is_dir():
        for child in sorted(overrides.iterdir()):
            if child.is_dir() and child.name not in handled \
                    and any(p.is_file() for p in child.rglob("*")):
                print(f"note: unhandled override tree ignored: overrides/{child.name}")

    # overrides/mods jars are NOT in the CurseForge manifest (cc-tweaked lives
    # here); a jar present in both places is taken from the manifest because
    # the API copy carries a verifiable sha1.
    staged_mods = staged / "mods"
    staged_mods.mkdir(parents=True, exist_ok=True)
    manifest_names = {entry.file_name for entry in entries}
    override_jars: list[str] = []
    overrides_mods = overrides / "mods"
    if overrides_mods.is_dir():
        for item in sorted(overrides_mods.iterdir()):
            if not item.is_file():
                continue
            if item.suffix.lower() != ".jar":
                print(f"note: non-jar file in overrides/mods ignored: {item.name}")
                continue
            if item.name in manifest_names:
                print(f"note: overrides/mods/{item.name} also in manifest; "
                      "manifest wins")
                continue
            target = staged_mods / item.name
            if not target.is_file() or sha1_of(target) != sha1_of(item):
                shutil.copy2(item, target)
                _sha1_memo.pop(target, None)
            override_jars.append(item.name)

    missing: list[Entry] = []
    to_download: list[Entry] = []
    for entry in entries:
        target = staged / entry.route / entry.file_name
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_file() and entry.sha1 and sha1_of(target) == entry.sha1:
            entry.status = "STAGED"  # kept from a previous run of this version
            if not entry.download_url:
                cache_blocked_copy(work, entry, target)
            continue
        found = reuse.resolve(entry.file_name, entry.sha1)
        if found is not None:
            shutil.copy2(found, target)
            _sha1_memo.pop(target, None)
            entry.status = "REUSE"
            if not entry.download_url:
                cache_blocked_copy(work, entry, found)
            continue
        if entry.download_url:
            to_download.append(entry)
        else:
            entry.status = "MANUAL_PENDING"
            missing.append(entry)

    if to_download:
        print(f"downloading {len(to_download)} files ({DOWNLOAD_WORKERS} workers) ...")
        progress_lock = threading.Lock()
        done = [0]

        def fetch_one(entry: Entry) -> str | None:
            target = staged / entry.route / entry.file_name
            error = download_file(entry.download_url, target,
                                  entry.file_name, entry.sha1)
            if error is None:
                entry.status = "DOWNLOADED"
                with progress_lock:
                    done[0] += 1
                    if done[0] % 50 == 0:
                        print(f"  {done[0]}/{len(to_download)}")
            return error

        with concurrent.futures.ThreadPoolExecutor(
                max_workers=DOWNLOAD_WORKERS) as pool:
            errors = [e for e in pool.map(fetch_one, to_download) if e]
        if errors:
            fail(1, "downloads failed:\n  " + "\n  ".join(errors))

    # Prune staged/mods leftovers from older attempts so the sync mirror never
    # picks up a jar that is no longer part of the release.
    expected_mods = ({e.file_name for e in entries if e.route == "mods"}
                     | set(override_jars))
    for item in sorted(staged_mods.iterdir()):
        if item.is_file() and item.name not in expected_mods:
            print(f"  pruning stale staged jar: {item.name}")
            item.unlink()

    write_reports(entries, override_jars, missing, version, work)
    return staged, override_jars, missing


def write_reports(entries: list[Entry], override_jars: list[str],
                  missing: list[Entry], version: str, work: Path) -> None:
    reports = work / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    for entry in entries:
        counts[entry.status] = counts.get(entry.status, 0) + 1
    coverage = reports / f"{version}-coverage.md"
    with open(coverage, "w", encoding="utf-8") as report:
        report.write(f"# LL8 {version} coverage\n\n")
        report.write(f"manifest entries: {len(entries)}, staged: "
                     f"{len(entries) - len(missing)}, manual pending: "
                     f"{len(missing)}, override jars: {len(override_jars)}\n\n")
        for status, count in sorted(counts.items(), key=lambda kv: -kv[1]):
            report.write(f"- {status}: {count}\n")
        report.write("\n| slug | file | route | status |\n|---|---|---|---|\n")
        for entry in sorted(entries, key=lambda e: (e.status, e.slug)):
            report.write(f"| {entry.slug} | {entry.file_name} | {entry.route} "
                         f"| {entry.status} |\n")
    manual = reports / f"{version}-manual-downloads.md"
    with open(manual, "w", encoding="utf-8") as report:
        report.write("# Files requiring manual download "
                     "(allowModDistribution=false)\n\n")
        report.write(f"Place the files into {work / 'manual'} and rerun "
                     "tools/update_ll8.py.\n\n")
        for entry in sorted(missing, key=lambda e: e.file_name.lower()):
            report.write(f"- `{entry.file_name}`\n  sha1 `{entry.sha1 or '?'}`\n"
                         f"  {entry.website}\n")
    print(f"coverage report: {coverage}")


# ---------------------------------------------------------------- diff

def overlay_pinned_mod_names() -> set[str]:
    """Basenames of overlay-pinned mods/ files, excluded from release diffs.

    The overlay re-adds them after every sync, so counting them as
    added/removed release churn would be noise (and a false world-impact hit).
    """
    try:
        overlay = json.loads(OVERLAY_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    names: set[str] = set()
    for spec in overlay.get("files", []):
        target = str(spec.get("target", ""))
        if target.startswith("mods/"):
            names.add(target.rsplit("/", 1)[-1])
    return names


def scan_versions(mods_dir: Path, cache: dict,
                  skip_names: set[str]) -> dict[str, tuple[str, str]]:
    """modId -> (version, jarName) for top-level providers of every jar."""
    result: dict[str, tuple[str, str]] = {}
    if not mods_dir.is_dir():
        return result
    for jar in sorted(mods_dir.glob("*.jar")):
        if jar.name in skip_names:
            continue
        stat = jar.stat()
        key = f"{jar.name}|{stat.st_size}|{stat.st_mtime_ns}"
        providers = cache.get(key)
        if providers is None:
            scanned = scan_mods.scan_jar(jar)
            providers = [[p.mod_id, p.version]
                         for p in scanned.providers if not p.nested_path]
            cache[key] = providers
        for mod_id, mod_version in providers:
            result[mod_id] = (mod_version, jar.name)
    return result


@dataclass
class Diff:
    added: dict[str, tuple[str, str]]
    removed: dict[str, tuple[str, str]]
    updated: dict[str, tuple[str, str, str]]  # modId -> (oldVer, newVer, newJar)
    packs: dict[str, tuple[list[str], list[str]]]  # route -> (added, removed)
    initial: bool


def diff_mods(old: dict[str, tuple[str, str]], new: dict[str, tuple[str, str]],
              staged: Path) -> Diff:
    added = {m: new[m] for m in new.keys() - old.keys()}
    removed = {m: old[m] for m in old.keys() - new.keys()}
    updated = {m: (old[m][0], new[m][0], new[m][1])
               for m in new.keys() & old.keys() if old[m][0] != new[m][0]}
    packs: dict[str, tuple[list[str], list[str]]] = {}
    for route in ("resourcepacks", "shaderpacks", "config/paxi/datapacks"):
        old_dir = REPO_ROOT / route
        new_dir = staged / route
        old_names = ({p.name for p in old_dir.glob("*") if p.is_file()}
                     if old_dir.is_dir() else set())
        new_names = ({p.name for p in new_dir.glob("*") if p.is_file()}
                     if new_dir.is_dir() else set())
        packs[route] = (sorted(new_names - old_names), sorted(old_names - new_names))
    return Diff(added=added, removed=removed, updated=updated, packs=packs,
                initial=not old)


def print_diff(diff: Diff) -> None:
    if diff.initial:
        print(f"diff: initial import ({len(diff.added)} modIds; no previous mods/)")
    else:
        print(f"diff: +{len(diff.added)} / -{len(diff.removed)} / "
              f"~{len(diff.updated)} modIds")
        for mod_id, (mod_version, jar) in sorted(diff.added.items()):
            print(f"  + {mod_id} {mod_version} ({jar})")
        for mod_id, (mod_version, jar) in sorted(diff.removed.items()):
            print(f"  - {mod_id} {mod_version} ({jar})")
        for mod_id, (old_v, new_v, jar) in sorted(diff.updated.items()):
            print(f"  ~ {mod_id} {old_v} -> {new_v} ({jar})")
    for route, (added, removed) in diff.packs.items():
        if added or removed:
            print(f"  {route}: +{len(added)} {added} / -{len(removed)} {removed}")


# ---------------------------------------------------------------- sync

def sync_managed_roots(staged: Path) -> dict[str, int]:
    stats = {"copied": 0, "deleted": 0, "kept": 0}
    for root in MANAGED_ROOTS:
        src_root = staged / root
        dst_root = REPO_ROOT / root
        if not src_root.is_dir():
            if dst_root.is_dir():
                shutil.rmtree(dst_root)
                print(f"sync: removed root {root}/ (absent from the release)")
            continue
        src_files = {p.relative_to(src_root).as_posix(): p
                     for p in src_root.rglob("*") if p.is_file()}
        if dst_root.is_dir():
            for item in list(dst_root.rglob("*")):
                if item.is_file():
                    rel = item.relative_to(dst_root).as_posix()
                    if rel not in src_files:
                        item.unlink()
                        stats["deleted"] += 1
            # Drop directories emptied by the deletions, deepest first.
            for folder in sorted((d for d in dst_root.rglob("*") if d.is_dir()),
                                 key=lambda d: -len(d.parts)):
                try:
                    folder.rmdir()
                except OSError:
                    pass
        for rel, src in sorted(src_files.items()):
            dst = dst_root / rel
            if dst.is_file() and dst.stat().st_size == src.stat().st_size \
                    and sha256_of(dst) == sha256_of(src):
                stats["kept"] += 1
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            stats["copied"] += 1
    print(f"sync: copied {stats['copied']}, deleted {stats['deleted']}, "
          f"kept {stats['kept']}")
    return stats


# ---------------------------------------------------------------- overlay

def apply_toml_edit(edit: dict) -> str:
    """Line-level `key = value` rewrite scoped to one [table] ('' = preamble).

    Everything except the value on the one matched line is preserved
    byte-for-byte: LL8 owns these files and the next update must diff clean.
    """
    path = REPO_ROOT / edit["file"]
    if not path.is_file():
        fail(EXIT_OVERLAY, f"overlay tomlEdit target missing: {edit['file']} "
                           "- update tools/overlay.json")
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    table = ""
    pattern = re.compile(
        r"^(\s*" + re.escape(edit["key"]) + r"\s*=\s*)(.*?)(\s*(?:#.*)?)$")
    header = re.compile(r"^\s*\[([^\]]*)\]")
    for i, line in enumerate(lines):
        bare = line.rstrip("\r\n")
        ending = line[len(bare):]
        head = header.match(bare)
        if head:
            table = head.group(1).strip()
            continue
        if table != edit["table"]:
            continue
        match = pattern.match(bare)
        if match is None:
            continue
        new_value = str(edit["value"])
        if match.group(2) == new_value:
            return f"{edit['file']}: {edit['key']} already {new_value}"
        lines[i] = match.group(1) + new_value + match.group(3) + ending
        with open(path, "w", encoding="utf-8", newline="") as handle:
            handle.write("".join(lines))
        return (f"{edit['file']}: {edit['key']} {match.group(2)} "
                f"-> {new_value}")
    fail(EXIT_OVERLAY,
         f"overlay tomlEdit key `{edit['key']}` not found in {edit['file']} "
         f"(table {edit['table']!r}) - LL8 changed the config format; "
         "update tools/overlay.json")


def apply_overlay() -> list[str]:
    try:
        overlay = json.loads(OVERLAY_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        fail(EXIT_OVERLAY, f"cannot read tools/overlay.json: {exc}")
    summary: list[str] = []
    for spec in overlay.get("files", []):
        source = REPO_ROOT / spec["source"]
        target = REPO_ROOT / spec["target"]
        if not source.is_file():
            fail(EXIT_OVERLAY, f"overlay source missing: {spec['source']}")
        actual = sha256_of(source)
        if actual != spec["sha256"]:
            fail(EXIT_OVERLAY, f"overlay source sha256 mismatch for "
                               f"{spec['source']}: {actual}")
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.is_file() or sha256_of(target) != spec["sha256"]:
            shutil.copy2(source, target)
        globs = [g.lower() for g in spec.get("forbidGlobs", [])]
        for candidate in sorted(target.parent.iterdir()):
            if candidate.name == target.name or not candidate.is_file():
                continue
            if any(fnmatch.fnmatchcase(candidate.name.lower(), g) for g in globs):
                fail(EXIT_OVERLAY,
                     f"overlay conflict: {candidate.name} matches a forbidden "
                     f"glob of {spec['target']} ({spec.get('reason', 'pinned')}); "
                     "resolve manually and update tools/overlay.json")
        summary.append(f"pinned {spec['target']}")
    for spec in overlay.get("remove", []):
        # LL8 ships a few things this pack has no use for. They are deleted
        # after staging rather than skipped during it, so a rename upstream
        # shows up as "matched nothing" instead of silently coming back.
        matched = sorted(REPO_ROOT.glob(spec["path"]))
        for path in matched:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
        summary.append(
            f"removed {spec['path']} ({len(matched)} path(s))"
            if matched else f"removed nothing for {spec['path']} - upstream may have renamed it")
    for edit in overlay.get("tomlEdits", []):
        summary.append(apply_toml_edit(edit))
    for line in summary:
        print(f"overlay: {line}")
    return summary


# ---------------------------------------------------------------- portable-pack

def write_portable_pack(loader_id: str, minecraft_version: str) -> dict:
    # "neoforge-21.1.244" -> type neoforge, version 21.1.244
    loader_type, _, loader_version = loader_id.partition("-")
    if not loader_type or not loader_version:
        fail(EXIT_OVERLAY, f"cannot parse mod loader id {loader_id!r}")
    client_jar = f"minecraft-{minecraft_version}-client.jar"
    if not (REPO_ROOT / client_jar).is_file():
        fail(EXIT_OVERLAY, f"client jar missing from the checkout: {client_jar}")
    data = {
        "schemaVersion": 1,
        "minecraftVersion": minecraft_version,
        "loader": {"type": loader_type, "version": loader_version},
        "clientJar": client_jar,
    }
    with open(REPO_ROOT / "portable-pack.json", "w", encoding="utf-8",
              newline="\n") as handle:
        json.dump(data, handle, indent=2)
        handle.write("\n")
    print(f"portable-pack.json: {loader_type} {loader_version}")
    return data


# ---------------------------------------------------------------- scan gate

def run_scan() -> None:
    result = subprocess.run(
        [sys.executable, str(TOOLS_DIR / "scan_mods.py"), "--mods", "mods",
         "--fail-on-issues", "--lenient-ranges"],
        cwd=REPO_ROOT)
    if result.returncode != 0:
        print("\nThe checkout is left modified so the failure can be inspected.",
              file=sys.stderr)
        print("Revert with: git -C {0} checkout -- . && git -C {0} clean -fd {1}"
              .format(REPO_ROOT, " ".join(MANAGED_ROOTS)), file=sys.stderr)
        fail(EXIT_SCAN, "scan gate failed (see errors above)")


# ---------------------------------------------------------------- world impact

def world_impact(world: Path, removed_mod_ids: set[str]) -> tuple[list[str], bool]:
    """WARN lines for world item stacks whose namespace is a removed mod."""
    try:
        from nbtlite import read_nbt, iter_item_stacks, iter_ae2_keys
    except ImportError:
        print("world impact skipped: nbtlite not available")
        return ["world check skipped: nbtlite not available"], False
    if not removed_mod_ids:
        print("world impact: no removed mods, nothing to check")
        return ["world check: no removed mods"], False

    counts: dict[tuple[str, str], int] = {}

    def norm(stack) -> tuple[str, int]:
        if isinstance(stack, (tuple, list)) and len(stack) >= 2:
            try:
                return str(stack[0]), int(stack[1])
            except (TypeError, ValueError):
                return str(stack[0]), 1
        if isinstance(stack, dict):
            ident = stack.get("id") or stack.get("item") or ""
            raw_count = stack.get("count", stack.get("Count", 1))
            try:
                return str(ident), int(raw_count)
            except (TypeError, ValueError):
                return str(ident), 1
        return str(stack), 1

    def tally(label: str, stacks) -> None:
        for stack in stacks:
            item_id, count = norm(stack)
            if ":" not in item_id:
                continue
            namespace = item_id.split(":", 1)[0]
            if namespace in removed_mod_ids:
                counts[(namespace, label)] = counts.get((namespace, label), 0) + count

    def try_source(path: Path, label: str, extract) -> None:
        if not path.is_file():
            return
        try:
            root = read_nbt(path)
            tally(label, extract(root))
        except Exception as exc:  # noqa: BLE001 - one broken file must not kill the update
            print(f"world impact: failed to read {path.name}: {exc}")

    def level_player_stacks(root):
        node = root
        try:
            for key in ("Data", "Player"):
                node = node[key]
        except (KeyError, TypeError, IndexError):
            node = root  # level.dat holds no other stacks; scanning all is safe
        return iter_item_stacks(node)

    try_source(world / "level.dat", "level.dat:Data.Player", level_player_stacks)
    playerdata = world / "playerdata"
    if playerdata.is_dir():
        for dat in sorted(playerdata.glob("*.dat")):
            try_source(dat, f"playerdata/{dat.name}", iter_item_stacks)
    try_source(world / "data" / "disk_manager.dat", "AE2 disk_manager",
               iter_ae2_keys)
    for name in ("sophisticatedbackpacks.dat", "IFBackpack.dat",
                 "mekanism_InventoryFrequencyHandler.dat"):
        try_source(world / "data" / name, f"data/{name}", iter_item_stacks)

    lines: list[str] = []
    by_namespace: dict[str, int] = {}
    for (namespace, label), count in sorted(counts.items()):
        lines.append(f"WARN world: {namespace} - {count} items in {label}")
        by_namespace[namespace] = by_namespace.get(namespace, 0) + count
    for line in lines:
        print(line)
    if not lines:
        print("world impact: OK, no items of removed mods found")
        return ["world check: OK (no items of removed mods)"], False
    summary = ", ".join(f"{ns}: {n}" for ns, n in sorted(by_namespace.items()))
    return ([f"world check: WARN removed-mod items present - {summary}"] + lines,
            True)


# ---------------------------------------------------------------- log / state

def compose_log_entry(version: str, client_info: dict, manifest_sha: str,
                      diff: Diff, entries: list[Entry],
                      overlay_summary: list[str], world_lines: list[str],
                      history_note: str) -> str:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    mods_total = len(list((REPO_ROOT / "mods").glob("*.jar")))
    route_counts = {route: sum(1 for e in entries if e.route == route)
                    for route in ("mods", "resourcepacks", "shaderpacks",
                                  "config/paxi/datapacks")}
    lines = [f"## {version} — {today} (CurseForge file {client_info['id']}, "
             f"manifest sha256 {manifest_sha})", ""]
    lines.append(f"- mods: {mods_total} total (+{len(diff.added)} / "
                 f"−{len(diff.removed)} / ~{len(diff.updated)})")
    lines.append(f"- resourcepacks: {route_counts['resourcepacks']}, "
                 f"shaderpacks: {route_counts['shaderpacks']}, "
                 f"paxi datapacks: {route_counts['config/paxi/datapacks']}")
    if diff.initial:
        lines.append(f"- initial import: {len(diff.added)} modIds, no previous "
                     "mods/ to diff against")
    else:
        for mod_id, (mod_version, jar) in sorted(diff.added.items()):
            lines.append(f"- added: {jar} ({mod_id} {mod_version})")
        for mod_id, (mod_version, jar) in sorted(diff.removed.items()):
            lines.append(f"- removed: {jar} ({mod_id} {mod_version})")
        for mod_id, (old_v, new_v, jar) in sorted(diff.updated.items()):
            lines.append(f"- updated: {jar} ({mod_id} {old_v} → {new_v})")
        for route, (added, removed) in diff.packs.items():
            for name in added:
                lines.append(f"- added: {route}/{name}")
            for name in removed:
                lines.append(f"- removed: {route}/{name}")
    lines.append("- overlay: " + ("; ".join(overlay_summary) or "none"))
    lines.extend(f"- {line}" for line in world_lines)
    lines.append(f"- {history_note}")
    lines.append("")
    return "\n".join(lines)


def prepend_update_log(entry_text: str) -> None:
    header = "# LL8 update log\n\n"
    existing = ""
    if UPDATE_LOG.is_file():
        existing = UPDATE_LOG.read_text(encoding="utf-8")
        if existing.startswith(header):
            existing = existing[len(header):]
    with open(UPDATE_LOG, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(header + entry_text + "\n" + existing)


def append_squash_note(note: str) -> None:
    """Attach a squash note to the newest UPDATE-LOG entry (created just now)."""
    if not UPDATE_LOG.is_file():
        return
    text = UPDATE_LOG.read_text(encoding="utf-8")
    marker = "\n\n## "
    position = text.find(marker, text.find("## "))
    insertion = f"- {note}\n"
    if position == -1:
        text = text.rstrip("\n") + "\n" + insertion
    else:
        text = text[:position + 1] + insertion + text[position + 1:]
    with open(UPDATE_LOG, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def write_state(version: str, client_info: dict, manifest_sha: str,
                entries: list[Entry]) -> None:
    state = {
        "schemaVersion": 1,
        "version": version,
        "clientFileId": client_info["id"],
        "serverFileId": client_info.get("serverPackFileId"),
        "updatedAtUtc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "manifestSha256": manifest_sha,
        "blockedFiles": sorted(e.file_name for e in entries if not e.download_url),
        "counts": {
            "mods": sum(1 for e in entries if e.route == "mods"),
            "resourcepacks": sum(1 for e in entries if e.route == "resourcepacks"),
            "shaderpacks": sum(1 for e in entries if e.route == "shaderpacks"),
            "datapacks": sum(1 for e in entries
                             if e.route == "config/paxi/datapacks"),
        },
    }
    with open(STATE_FILE, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(state, handle, indent=2)
        handle.write("\n")


# ---------------------------------------------------------------- git

def run_git(*git_args: str, check: bool = True) -> str:
    result = subprocess.run(["git", "-C", str(REPO_ROOT), *git_args],
                            capture_output=True, text=True)
    if check and result.returncode != 0:
        fail(EXIT_GIT, f"git {' '.join(git_args)} failed:\n{result.stderr.strip()}")
    return result.stdout


def git_ok(*git_args: str) -> bool:
    return subprocess.run(["git", "-C", str(REPO_ROOT), *git_args],
                          capture_output=True).returncode == 0


def changed_paths() -> list[str]:
    # -uall lists untracked files individually; rename detection is disabled so
    # every record is a single NUL-terminated "XY path" (simpler slicing).
    out = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "-c", "status.renames=false", "status",
         "--porcelain=v1", "-z", "-uall"],
        capture_output=True, text=True, encoding="utf-8")
    if out.returncode != 0:
        fail(EXIT_GIT, f"git status failed:\n{out.stderr.strip()}")
    paths = []
    for record in out.stdout.split("\0"):
        if len(record) > 3:
            paths.append(record[3:])
    # Pack content hidden from git by the pack's OWN nested .gitignore files
    # (LL8 ships config/almostunified/.gitignore which ignores its own
    # debug.json) must still be committed, or CI clones would publish an
    # incomplete release. commit_slices force-adds, so listing them suffices.
    roots = [root for root in MANAGED_ROOTS if (REPO_ROOT / root).is_dir()]
    if roots:
        ignored = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "ls-files", "--others", "--ignored",
             "--exclude-standard", "-z", "--", *roots],
            capture_output=True, text=True, encoding="utf-8")
        if ignored.returncode == 0:
            for record in ignored.stdout.split("\0"):
                if record:
                    paths.append(record)
    return paths


def repo_git_size_bytes() -> int:
    out = run_git("count-objects", "-v")
    kib = 0
    for line in out.splitlines():
        key, _, value = line.partition(":")
        if key.strip() in ("size", "size-pack"):
            kib += int(value.strip())
    return kib * 1024


def slice_paths(paths: list[str], limit_bytes: int) -> list[list[str]]:
    slices: list[list[str]] = []
    current: list[str] = []
    current_size = 0
    for path in sorted(paths):
        full = REPO_ROOT / path
        size = full.stat().st_size if full.is_file() else 0  # deletions cost 0
        if current and current_size + size > limit_bytes:
            slices.append(current)
            current, current_size = [], 0
        current.append(path)
        current_size += size
    if current:
        slices.append(current)
    return slices


def commit_slices(paths: list[str], message_base: str,
                  limit_bytes: int) -> list[str]:
    """Commit the given paths in <= limit_bytes slices; returns commit shas."""
    slices = slice_paths(paths, limit_bytes)
    total = len(slices)
    shas: list[str] = []
    for i, chunk in enumerate(slices, 1):
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="",
                                         suffix=".pathspec",
                                         delete=False) as spec:
            # :(literal) so bracketed filenames ("Foo [1.2].zip") are not
            # treated as glob character classes by the pathspec engine.
            spec.write("\0".join(":(literal)" + p for p in chunk))
            spec_path = spec.name
        try:
            # -f: some shipped paths are ignored by the pack's own nested
            # .gitignore files (see changed_paths) yet must be committed.
            run_git("add", "-A", "-f", "--pathspec-from-file", spec_path,
                    "--pathspec-file-nul")
        finally:
            os.unlink(spec_path)
        if git_ok("diff", "--cached", "--quiet"):
            continue  # nothing actually staged in this slice
        message = message_base if total == 1 else f"{message_base} ({i}/{total})"
        run_git("commit", "-m", message)
        sha = run_git("rev-parse", "HEAD").strip()
        shas.append(sha)
        print(f"committed {message} ({sha[:12]})")
    return shas


def unpushed_commits(has_remote_main: bool) -> list[str]:
    span = "origin/main..HEAD" if has_remote_main else "HEAD"
    out = run_git("log", "--reverse", "--format=%H", span)
    return [line for line in out.split() if line]


def push_main(commits: list[str], force: bool = False) -> None:
    force_args = ["--force"] if force else []
    if len(commits) <= 1:
        run_git("push", *force_args, "origin", "main")
    else:
        # Every push transfers at most one slice of objects; GitHub caps a
        # single push at ~2 GiB, so main is only pushed once its objects are
        # already on the remote via the throwaway _upload ref.
        for sha in commits:
            run_git("push", "--force", "origin", f"{sha}:refs/heads/_upload")
        run_git("push", *force_args, "origin", "main")
        run_git("push", "origin", ":refs/heads/_upload")
    print(f"pushed {len(commits)} commit(s) to origin/main")


def orphan_squash(version: str, limit_bytes: int) -> list[str]:
    """Rewrite history to a fresh root; returns the new slice commit shas."""
    append_squash_note(
        f"git history squashed to a fresh root on "
        f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')} "
        "(history size exceeded --history-limit-gib)")
    run_git("checkout", "--orphan", "_fresh")
    run_git("rm", "-r", "--cached", ".")
    shas = commit_slices(changed_paths(), f"LL8 {version}", limit_bytes)
    run_git("branch", "-M", "main")
    return shas


def git_publish(version: str, args, allow_squash: bool) -> None:
    branch = run_git("symbolic-ref", "--short", "HEAD").strip()
    if branch != "main":
        fail(EXIT_GIT, f"checkout is on branch {branch!r}, expected main")
    had_head = git_ok("rev-parse", "--verify", "HEAD")
    remotes = run_git("remote").split()
    has_remote = "origin" in remotes
    has_remote_main = False
    if has_remote:
        run_git("fetch", "origin")
        has_remote_main = git_ok("rev-parse", "--verify", "origin/main")
        if had_head and has_remote_main:
            behind = int(run_git("rev-list", "--count", "HEAD..origin/main").strip())
            if behind:
                fail(EXIT_GIT, f"checkout is {behind} commit(s) behind "
                               "origin/main; pull/rebase first")

    limit_bytes = int(args.push_slice_gib * (1 << 30))
    size_before = repo_git_size_bytes()
    pending = changed_paths()
    if pending:
        commit_slices(pending, f"LL8 {version}", limit_bytes)
    else:
        print("git: no pending changes to commit")
    size_after = repo_git_size_bytes()
    print(f"git history size: {size_before / (1 << 30):.2f} GiB -> "
          f"{size_after / (1 << 30):.2f} GiB "
          f"(limit {args.history_limit_gib} GiB)")

    squashed = False
    limit = args.history_limit_gib * (1 << 30)
    if allow_squash and size_after > limit and not args.no_squash:
        if not had_head:
            # A fresh import has no replaced blobs to shed: an orphan squash
            # would rewrite the same objects and reclaim nothing.
            print("history over the limit but this is the initial import; "
                  "skipping squash")
        else:
            print("history exceeds the limit; squashing to a fresh root ...")
            orphan_squash(version, limit_bytes)
            squashed = True

    if not args.push:
        print("push disabled (--no-push)")
        return
    if not has_remote:
        print("no remote: skipping push")
        return
    commits = unpushed_commits(has_remote_main and not squashed)
    if not commits:
        print("git: nothing to push")
        return
    push_main(commits, force=squashed)
    if squashed:
        run_git("reflog", "expire", "--expire=now", "--all")
        run_git("gc", "--prune=now")
        print(f"post-squash history size: "
              f"{repo_git_size_bytes() / (1 << 30):.2f} GiB")


def wait_release() -> None:
    head = run_git("rev-parse", "HEAD").strip()
    result = subprocess.run(
        [sys.executable, str(TOOLS_DIR / "verify_release.py"),
         "--repo", GITHUB_REPO, "--tag", "pack-latest",
         "--expect-revision", head, "--timeout-min", "40"])
    if result.returncode != 0:
        sys.exit(result.returncode)


# ---------------------------------------------------------------- entry points

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Update the LL8 pack checkout from the newest upstream "
                    "release.")
    selector = parser.add_mutually_exclusive_group()
    selector.add_argument("--version", help="install this exact LL8 version "
                                            "(default: latest release)")
    selector.add_argument("--file-id", type=int,
                          help="install this exact CurseForge file id")
    parser.add_argument("--allow-beta", action="store_true",
                        help="also consider beta releases")
    parser.add_argument("--work", type=Path,
                        default=Path(r"C:\Users\Oskar\Documents\LL8-work"))
    parser.add_argument("--reuse", type=Path, action="append", default=[],
                        help="extra pack checkout(s) to source jars from "
                             "(mods/, resourcepacks/, shaderpacks/, "
                             "config/paxi/datapacks/)")
    parser.add_argument("--dry-run", action="store_true",
                        help="stage + diff only; never touch the checkout")
    parser.add_argument("--commit", action=argparse.BooleanOptionalAction,
                        default=True, help="commit the update (default on)")
    parser.add_argument("--push", action=argparse.BooleanOptionalAction,
                        default=True, help="push to origin (default on)")
    parser.add_argument("--force", action="store_true",
                        help="proceed even if ll8-state.json says up to date")
    parser.add_argument("--publish-only", action="store_true",
                        help="skip resolve/download/stage/sync; commit pending "
                             "changes and push per the slicing rules")
    parser.add_argument("--world", type=Path,
                        help="world directory to check for items of removed mods")
    parser.add_argument("--strict-world", action="store_true",
                        help="exit 4 when the world holds items of removed mods")
    parser.add_argument("--history-limit-gib", type=float, default=3.0)
    parser.add_argument("--no-squash", action="store_true")
    parser.add_argument("--push-slice-gib", type=float, default=1.2)
    parser.add_argument("--wait-release", action="store_true",
                        help="wait for CI to republish pack-latest, then verify")
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--refresh-api", action="store_true",
                        help="ignore cached API responses")
    parser.add_argument("--allow-dirty", action="store_true",
                        help="run the update even if the checkout has "
                             "uncommitted changes")
    return parser


def cmd_publish_only(args) -> None:
    state = load_state()
    version = state.get("version", "unknown") if state else "unknown"
    if not args.commit:
        print("--publish-only with --no-commit: nothing to do")
        return
    git_publish(version, args, allow_squash=False)
    if args.wait_release and args.push:
        wait_release()


def cmd_update(args) -> None:
    api_key = args.api_key or default_api_key()
    if not api_key:
        fail(1, "CURSEFORGE_API_KEY is not set (pass --api-key, export it, or "
                "put it in ~/.curseforge/api-key.txt)")

    work = args.work
    for sub in ("api-cache", "sources", "manual", "cache", "reports"):
        (work / sub).mkdir(parents=True, exist_ok=True)

    client_info, version = resolve_release(args, api_key)
    print(f"LL8 client file: {client_info['displayName']} (id {client_info['id']})")
    state = load_state()
    if state and state.get("clientFileId") == client_info["id"] and not args.force:
        print(f"up to date: {state.get('version')} "
              f"(file {state.get('clientFileId')}); use --force to reinstall")
        return

    # A dirty tree would blend unrelated edits into the update commit; catch it
    # before anything is modified. The initial import (no HEAD yet) is exempt.
    if args.commit and not args.dry_run and not args.allow_dirty \
            and git_ok("rev-parse", "--verify", "HEAD") and changed_paths():
        fail(EXIT_GIT, "checkout has uncommitted changes; commit/stash them or "
                       "pass --allow-dirty")

    manifest, client_root, loader_id = fetch_client(client_info, version, work)
    manifest_sha = sha256_of(client_root / "manifest.json")
    entries = index_files(manifest, api_key, work / "api-cache" / version,
                          args.refresh_api)
    reuse = ReuseIndex(list(args.reuse), work)
    staged, override_jars, missing = stage(entries, version, work, client_root,
                                           reuse)
    if missing:
        print(f"\n{len(missing)} author-blocked file(s) have no verified local "
              "copy. The checkout was not modified.")
        print(f"Download them into {work / 'manual'} as listed in "
              f"{work / 'reports' / (version + '-manual-downloads.md')} and rerun.")
        sys.exit(EXIT_MANUAL)

    scan_cache_path = work / "scan-cache.json"
    try:
        scan_cache = json.loads(scan_cache_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        scan_cache = {}
    pinned_names = overlay_pinned_mod_names()
    old_map = scan_versions(REPO_ROOT / "mods", scan_cache, pinned_names)
    new_map = scan_versions(staged / "mods", scan_cache, pinned_names)
    scan_cache_path.write_text(json.dumps(scan_cache), encoding="utf-8")
    diff = diff_mods(old_map, new_map, staged)
    print_diff(diff)
    removed_ids = set(diff.removed)

    if args.dry_run:
        if args.world:
            world_impact(args.world, removed_ids)
        print(f"\ndry run: staged tree left at {staged}; checkout untouched")
        return

    sync_managed_roots(staged)
    overlay_summary = apply_overlay()
    write_portable_pack(loader_id, manifest["minecraft"]["version"])
    run_scan()

    world_lines = ["world check: skipped (--world not given)"]
    world_hit = False
    if args.world:
        world_lines, world_hit = world_impact(args.world, removed_ids)
        if world_hit and args.strict_world:
            print("\n--strict-world: aborting before commit; the checkout is "
                  "left modified for inspection.", file=sys.stderr)
            fail(EXIT_SCAN, "world still holds items of removed mods")

    history_note = (f"git history before commit: "
                    f"{repo_git_size_bytes() / (1 << 30):.2f} GiB "
                    f"(squash threshold {args.history_limit_gib} GiB)")
    log_entry = compose_log_entry(version, client_info, manifest_sha, diff,
                                  entries, overlay_summary, world_lines,
                                  history_note)
    prepend_update_log(log_entry)
    write_state(version, client_info, manifest_sha, entries)
    print(f"updated UPDATE-LOG.md and tools/ll8-state.json for {version}")

    if not args.commit:
        print("--no-commit: leaving the changes uncommitted")
        return
    git_publish(version, args, allow_squash=True)
    if args.wait_release and args.push:
        wait_release()


def main() -> None:
    args = build_parser().parse_args()
    if args.publish_only:
        cmd_publish_only(args)
    else:
        cmd_update(args)


if __name__ == "__main__":
    main()
