#!/usr/bin/env python3
"""Dependency validator for the LL8 mods/ tree.

Stdlib only. Per jar: parse META-INF/neoforge.mods.toml (fallback mods.toml),
resolve ${file.jarVersion} from MANIFEST.MF, walk META-INF/jarjar/metadata.json
recursively (shaded/nested jars satisfy dependencies). Then check:
  (a) duplicate modIds provided by different top-level jars (crash at launch)
  (b) unsatisfied mandatory dependencies (side annotated)
  (c) present deps whose version violates the declared range, and present
      type="incompatible" targets
  (d) jars whose declared `neoforge` range excludes the pack loader version
  (e) informational: modIds nothing depends on (orphan candidates)

--fail-on-issues exits 1 if any of (a)-(d) fired. With --lenient-ranges the
range-shaped findings (c)+(d) degrade to warnings: LL8 upstream ships the pack
exactly as scanned here, so range mismatches are the modpack author's problem,
while duplicate modIds (a) and missing mandatory deps (b) would break OUR
tree and stay fatal.
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import tomllib
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

MODS_DEFAULT = Path(__file__).resolve().parents[1] / "mods"
# Fallback only: the real loader version comes from <repo>/portable-pack.json
# (loader.version) so the scan always matches what the pack actually ships.
LOADER_VERSION = "21.1.244"
MINECRAFT_VERSION = "1.21.1"

# Provided by the runtime, not by any jar in mods/.
ENVIRONMENT_MODS = {
    "minecraft": MINECRAFT_VERSION,
    "neoforge": LOADER_VERSION,
}


def _loader_version_from_pack() -> str:
    """loader.version from the repo's portable-pack.json, or the constant."""
    pack_json = Path(__file__).resolve().parents[1] / "portable-pack.json"
    try:
        data = json.loads(pack_json.read_text(encoding="utf-8-sig"))
        version = data.get("loader", {}).get("version")
        if isinstance(version, str) and version:
            return version
    except (OSError, ValueError):
        pass
    return LOADER_VERSION


# ---------------------------------------------------------------- versions
#
# Maven ComparableVersion-style ordering, which is what FML actually uses.
# '.' separates items on the same level; '-' (and any other non-alphanumeric,
# and digit<->letter transitions) starts a nested qualifier list. Numbers beat
# qualifier lists at the same position ("1.21.1-93" > "1.21-87"), known
# qualifiers sort below release ("21-beta" < "21"), trailing zeros are trimmed
# ("1.21.0" == "1.21"). The naive flat split mandated first produced false
# positives on exactly those hyphenated cases, so it was upgraded.

_QUALIFIERS = {"alpha": "0", "beta": "1", "milestone": "2", "rc": "3", "cr": "3",
               "snapshot": "4", "": "5", "final": "5", "ga": "5", "release": "5",
               "sp": "6"}


def _qualifier_key(token: str) -> str:
    return _QUALIFIERS.get(token, "7-" + token)


def _tokenize(version: str) -> list:
    root: list = []
    current = root
    token = ""
    prev_digit: bool | None = None

    def flush() -> None:
        nonlocal token
        if token:
            current.append(int(token) if token.isdigit() else token)
            token = ""

    for ch in version.strip().lower():
        if ch == ".":
            if not token:
                current.append(0)
            flush()
            prev_digit = None
        elif not ch.isalnum():
            flush()
            sub: list = []
            current.append(sub)
            current = sub
            prev_digit = None
        else:
            if token and prev_digit is not None and ch.isdigit() != prev_digit:
                flush()
                sub = []
                current.append(sub)
                current = sub
            token += ch
            prev_digit = ch.isdigit()
    flush()
    return root


def _trim(items: list) -> list:
    out: list = []
    for item in items:
        out.append(_trim(item) if isinstance(item, list) else item)
    while out and _null_item(out[-1]):
        out.pop()
    return out


def _null_item(item: object) -> bool:
    if isinstance(item, int):
        return item == 0
    if isinstance(item, list):
        return not item
    return item == ""


def _cmp_items(a: object, b: object) -> int:
    if a is None and b is None:
        return 0
    if a is None:
        return -_cmp_items(b, None)
    if isinstance(a, int):
        if b is None:
            return 0 if a == 0 else 1
        if isinstance(b, int):
            return (a > b) - (a < b)
        return 1  # number beats qualifier string and qualifier list
    if isinstance(a, str):
        if b is None:
            ka, kb = _qualifier_key(a), _QUALIFIERS[""]
            return (ka > kb) - (ka < kb)
        if isinstance(b, int):
            return -1
        if isinstance(b, str):
            ka, kb = _qualifier_key(a), _qualifier_key(b)
            return (ka > kb) - (ka < kb)
        return -1  # string < list
    # a is a list
    if b is None:
        return _cmp_items(a[0], None) if a else 0
    if isinstance(b, int):
        return -1
    if isinstance(b, str):
        return 1
    for i in range(max(len(a), len(b))):
        xa = a[i] if i < len(a) else None
        xb = b[i] if i < len(b) else None
        result = _cmp_items(xa, xb)
        if result:
            return result
    return 0


def compare_versions(a: str, b: str) -> int:
    return _cmp_items(_trim(_tokenize(a)), _trim(_tokenize(b)))


@dataclass
class Bound:
    version: str
    inclusive: bool


@dataclass
class Interval:
    lower: Bound | None  # None = unbounded
    upper: Bound | None

    def contains(self, version: str) -> bool:
        if self.lower is not None:
            c = compare_versions(version, self.lower.version)
            if c < 0 or (c == 0 and not self.lower.inclusive):
                return False
        if self.upper is not None:
            c = compare_versions(version, self.upper.version)
            if c > 0 or (c == 0 and not self.upper.inclusive):
                return False
        return True


class VersionRange:
    """Maven range spec: '*', '', bare version (soft: matches anything),
    '[a]', '[a,b)', '(a,b]', '[a,)', '(,b]', unions '[a,b),[c,)'."""

    def __init__(self, spec: str):
        self.spec = (spec or "").strip()
        self.match_all = self.spec in ("", "*")
        self.intervals: list[Interval] = []
        self.malformed = False
        if not self.match_all:
            try:
                self._parse(self.spec)
            except ValueError:
                self.malformed = True
                self.match_all = True  # do not spam false positives

    def _parse(self, spec: str) -> None:
        i, n = 0, len(spec)
        while i < n:
            ch = spec[i]
            if ch in ",\u0020\t":
                i += 1
                continue
            if ch in "[(":
                close = min((x for x in (spec.find("]", i), spec.find(")", i)) if x != -1), default=-1)
                if close == -1:
                    raise ValueError(spec)
                body = spec[i + 1:close]
                lower_inc, upper_inc = ch == "[", spec[close] == "]"
                if "," in body:
                    lo, hi = (part.strip() for part in body.split(",", 1))
                    self.intervals.append(Interval(
                        Bound(lo, lower_inc) if lo else None,
                        Bound(hi, upper_inc) if hi else None,
                    ))
                else:  # [a] exact
                    exact = body.strip()
                    self.intervals.append(Interval(Bound(exact, True), Bound(exact, True)))
                i = close + 1
            else:  # bare version = maven soft requirement, matches anything
                next_bracket = min((x for x in (spec.find("[", i), spec.find("(", i)) if x != -1), default=n)
                i = next_bracket
                self.match_all = True

    def contains(self, version: str) -> bool:
        if self.match_all:
            return True
        return any(interval.contains(version) for interval in self.intervals)


# ---------------------------------------------------------------- jar parsing

@dataclass
class Provider:
    mod_id: str
    version: str
    jar: str            # top-level jar file name
    nested_path: str = ""  # '' for top-level mods


@dataclass
class DepEdge:
    consumer_jar: str
    consumer_mod: str
    dep_id: str
    mandatory: bool
    version_range: str
    side: str
    dep_type: str


@dataclass
class JarScan:
    providers: list[Provider] = field(default_factory=list)
    edges: list[DepEdge] = field(default_factory=list)
    nested: list[tuple[str, str, str]] = field(default_factory=list)  # (identity, version, path)
    warnings: list[str] = field(default_factory=list)


def manifest_value(raw: bytes, key: str) -> str | None:
    """Parse a MANIFEST.MF attribute, honouring continuation lines."""
    lines = raw.decode("utf-8", "replace").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    unfolded: list[str] = []
    for line in lines:
        if line.startswith(" ") and unfolded:
            unfolded[-1] += line[1:]
        else:
            unfolded.append(line)
    prefix = key + ":"
    for line in unfolded:
        if line.lower().startswith(prefix.lower()):
            return line[len(prefix):].strip()
    return None


def _parse_mods_toml(archive: zipfile.ZipFile, jar_label: str, nested_path: str, scan: JarScan) -> None:
    raw = None
    for name in ("META-INF/neoforge.mods.toml", "META-INF/mods.toml"):
        try:
            raw = archive.read(name)
            break
        except KeyError:
            continue
    if raw is None:
        return
    try:
        data = tomllib.loads(raw.decode("utf-8", "replace"))
    except tomllib.TOMLDecodeError as error:
        scan.warnings.append(f"{jar_label}:{nested_path or '.'}: bad mods.toml: {error}")
        return

    jar_version: str | None = None

    def resolve_version(value: str) -> str:
        nonlocal jar_version
        if "${file.jarVersion}" in value:
            if jar_version is None:
                try:
                    jar_version = manifest_value(archive.read("META-INF/MANIFEST.MF"),
                                                "Implementation-Version") or "0.0NONE"
                except KeyError:
                    jar_version = "0.0NONE"
            return value.replace("${file.jarVersion}", jar_version)
        return value

    local_ids: list[str] = []
    for mod in data.get("mods", []):
        mod_id = mod.get("modId", "")
        if not mod_id:
            continue
        version = resolve_version(str(mod.get("version", "0.0NONE")))
        scan.providers.append(Provider(mod_id, version, jar_label, nested_path))
        local_ids.append(mod_id)

    dependencies = data.get("dependencies", {})
    if isinstance(dependencies, dict):
        for owner, deps in dependencies.items():
            if not isinstance(deps, list):
                continue
            consumer = owner if owner in local_ids or not local_ids else local_ids[0]
            for dep in deps:
                if not isinstance(dep, dict):
                    continue
                dep_id = dep.get("modId", "")
                if not dep_id:
                    continue
                dep_type = str(dep.get("type", "")).lower()
                if not dep_type:
                    dep_type = "required" if dep.get("mandatory", False) else "optional"
                scan.edges.append(DepEdge(
                    consumer_jar=jar_label,
                    consumer_mod=consumer,
                    dep_id=dep_id,
                    mandatory=dep_type == "required",
                    version_range=str(dep.get("versionRange", "")),
                    side=str(dep.get("side", "BOTH")).upper(),
                    dep_type=dep_type,
                ))


def _walk_archive(archive: zipfile.ZipFile, jar_label: str, nested_path: str, scan: JarScan) -> None:
    _parse_mods_toml(archive, jar_label, nested_path, scan)
    try:
        metadata = json.loads(archive.read("META-INF/jarjar/metadata.json"))
    except KeyError:
        return
    except json.JSONDecodeError as error:
        scan.warnings.append(f"{jar_label}:{nested_path or '.'}: bad jarjar metadata: {error}")
        return
    for entry in metadata.get("jars", []):
        path = entry.get("path", "")
        identifier = entry.get("identifier", {})
        identity = f"{identifier.get('group', '?')}:{identifier.get('artifact', '?')}"
        version = str(entry.get("version", {}).get("artifactVersion", "0"))
        child_path = f"{nested_path}!{path}" if nested_path else path
        scan.nested.append((identity, version, f"{jar_label}:{child_path}"))
        try:
            payload = archive.read(path)
        except KeyError:
            scan.warnings.append(f"{jar_label}: jarjar entry missing in archive: {path}")
            continue
        try:
            with zipfile.ZipFile(io.BytesIO(payload)) as nested:
                _walk_archive(nested, jar_label, child_path, scan)
        except zipfile.BadZipFile:
            scan.warnings.append(f"{jar_label}: nested jar unreadable: {child_path}")


def scan_jar(jar: Path) -> JarScan:
    scan = JarScan()
    try:
        with zipfile.ZipFile(jar) as archive:
            _walk_archive(archive, jar.name, "", scan)
    except (OSError, zipfile.BadZipFile) as error:
        scan.warnings.append(f"{jar.name}: unreadable jar: {error}")
    return scan


# ---------------------------------------------------------------- analysis

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mods", type=Path, default=MODS_DEFAULT)
    parser.add_argument("--fail-on-issues", action="store_true")
    parser.add_argument("--lenient-ranges", action="store_true",
                        help="version-range violations, present incompatibles and "
                             "neoforge-range exclusions become warnings; duplicate "
                             "modIds and missing mandatory deps stay errors")
    parser.add_argument("--loader-version", default=None,
                        help="override the loader version (default: "
                             "portable-pack.json loader.version)")
    arguments = parser.parse_args()

    loader_version = arguments.loader_version or _loader_version_from_pack()
    environment_mods = {"minecraft": MINECRAFT_VERSION, "neoforge": loader_version}

    jars = sorted(arguments.mods.glob("*.jar"))
    if not jars:
        print(f"no jars found under {arguments.mods}")
        return 1

    providers: dict[str, list[Provider]] = {}
    edges: list[DepEdge] = []
    warnings: list[str] = []
    for jar in jars:
        scan = scan_jar(jar)
        warnings.extend(scan.warnings)
        edges.extend(scan.edges)
        for provider in scan.providers:
            providers.setdefault(provider.mod_id, []).append(provider)

    for mod_id, version in environment_mods.items():
        providers.setdefault(mod_id, []).append(Provider(mod_id, version, "<environment>"))

    issues_a: list[str] = []  # duplicate modIds
    issues_b: list[str] = []  # unsatisfied mandatory deps
    issues_c: list[str] = []  # range violations / present incompatibles
    issues_d: list[str] = []  # neoforge range excludes loader
    info_e: list[str] = []    # orphans

    # (a) duplicates. Only two TOP-LEVEL jars claiming the same modId is a
    # guaranteed launch failure. Nested copies (nested-vs-nested and even
    # nested-vs-top-level) are deduped by JarJar selection: both source packs
    # boot with e.g. gag(nested Placebo)+standalone Placebo, uranus(nested
    # architectury)+standalone architectury, bumblezone(nested athena/
    # resourcefullib)+standalones — so those degrade to warnings.
    for mod_id, plist in sorted(providers.items()):
        jars_for_id = sorted({p.jar for p in plist if p.jar != "<environment>"})
        if len(jars_for_id) <= 1:
            continue
        top_level_jars = sorted({p.jar for p in plist if not p.nested_path})
        detail = ", ".join(
            f"{p.jar}{' (nested ' + p.nested_path + ')' if p.nested_path else ''} v{p.version}"
            for p in plist)
        if len(top_level_jars) > 1:
            issues_a.append(f"modId `{mod_id}` provided by {len(top_level_jars)} top-level jars: {detail}")
        elif len(top_level_jars) == 1:
            warnings.append(f"modId `{mod_id}` both standalone and nested "
                            f"(JarJar dedupes; pairing boots in a source pack): {detail}")
        else:
            warnings.append(f"nested-only modId `{mod_id}` shipped by multiple jars "
                            f"(JarJar will pick highest): {detail}")

    # (b)+(c) dependency satisfaction
    for edge in edges:
        if edge.dep_type in ("optional", "discouraged", "suggested"):
            candidates = providers.get(edge.dep_id, [])
            if candidates and edge.version_range:
                rng = VersionRange(edge.version_range)
                if not any(rng.contains(p.version) for p in candidates):
                    versions = ", ".join(sorted({p.version for p in candidates}))
                    issues_c.append(
                        f"{edge.consumer_jar} ({edge.consumer_mod}) optionally wants "
                        f"`{edge.dep_id}` {edge.version_range}, present: {versions} [side={edge.side}, optional]")
            continue
        if edge.dep_type == "incompatible":
            candidates = providers.get(edge.dep_id, [])
            rng = VersionRange(edge.version_range)
            hits = [p for p in candidates if rng.contains(p.version)]
            if hits:
                versions = ", ".join(sorted({p.version for p in hits}))
                issues_c.append(
                    f"{edge.consumer_jar} ({edge.consumer_mod}) declares `{edge.dep_id}` "
                    f"{edge.version_range or '*'} INCOMPATIBLE, but it is present: {versions} [side={edge.side}]")
            continue
        if not edge.mandatory:
            continue
        candidates = providers.get(edge.dep_id, [])
        if not candidates:
            issues_b.append(
                f"{edge.consumer_jar} ({edge.consumer_mod}) requires `{edge.dep_id}` "
                f"{edge.version_range or '*'} — MISSING [side={edge.side}]")
            continue
        rng = VersionRange(edge.version_range)
        if not any(rng.contains(p.version) for p in candidates):
            versions = ", ".join(sorted({f"{p.version} ({p.jar})" for p in candidates}))
            # Loader-tolerated pattern: 1.21-family jars declaring [1.21,1.21.1)
            # or [1.21] demonstrably load on 1.21.1 (jei/cucumber/waystones etc.
            # ship in both booting source packs), so this degrades to a warning.
            if edge.dep_id == "minecraft" and rng.contains("1.21"):
                warnings.append(
                    f"{edge.consumer_jar} ({edge.consumer_mod}) declares 1.21-only "
                    f"minecraft range {edge.version_range}; loads on 1.21.1 in practice")
                continue
            issues_c.append(
                f"{edge.consumer_jar} ({edge.consumer_mod}) requires `{edge.dep_id}` "
                f"{edge.version_range}, present: {versions} [side={edge.side}]")

    # (d) neoforge range excludes the pack loader version
    for edge in edges:
        if edge.dep_id != "neoforge" or not edge.mandatory or not edge.version_range:
            continue
        if not VersionRange(edge.version_range).contains(loader_version):
            issues_d.append(
                f"{edge.consumer_jar} ({edge.consumer_mod}) neoforge range "
                f"{edge.version_range} excludes loader {loader_version}")

    # (e) orphans: top-level modIds with no incoming dependency edge at all
    referenced = {edge.dep_id for edge in edges}
    for mod_id, plist in sorted(providers.items()):
        if mod_id in environment_mods or mod_id in referenced:
            continue
        if any(not p.nested_path for p in plist):
            info_e.append(f"`{mod_id}` ({', '.join(sorted({p.jar for p in plist}))})")

    # Empirically-tolerated declarations (tools/scan_exceptions.json): each rule
    # names a jar prefix plus an issue substring and the evidence why the
    # violation is survivable in practice; matches degrade to warnings.
    exceptions_file = Path(__file__).resolve().parent / "scan_exceptions.json"
    if exceptions_file.is_file():
        rules = json.loads(exceptions_file.read_text(encoding="utf-8"))

        def excused(item: str) -> bool:
            for rule in rules:
                if item.startswith(rule["jar"]) and rule.get("contains", "") in item:
                    warnings.append(f"{item} [excused: {rule['reason']}]")
                    return True
            return False

        issues_b = [i for i in issues_b if not excused(i)]
        issues_c = [i for i in issues_c if not excused(i)]
        issues_d = [i for i in issues_d if not excused(i)]

    # Under --lenient-ranges the range-shaped findings are printed as warnings
    # and stop gating --fail-on-issues (see module docstring for the rationale).
    if arguments.lenient_ranges:
        warnings.extend(issues_c)
        warnings.extend(issues_d)
        issues_c = []
        issues_d = []

    print(f"jars scanned: {len(jars)}")
    print(f"modIds provided (incl. nested): {len(providers) - len(environment_mods)}")
    print(f"dependency edges: {len(edges)}")
    print()

    def emit(title: str, items: list[str], severity: str) -> None:
        print(f"== {title}: {len(items)}")
        for item in items:
            print(f"  [{severity}] {item}")
        print()

    emit("(a) duplicate modIds", issues_a, "ERROR")
    emit("(b) unsatisfied mandatory deps", issues_b, "ERROR")
    emit("(c) version-range violations", issues_c, "ERROR")
    emit(f"(d) neoforge range excludes {loader_version}", issues_d, "ERROR")
    if warnings:
        emit("warnings", warnings, "WARN")
    print(f"== (e) informational: modIds with no consumers: {len(info_e)}")
    for item in info_e:
        print(f"  [INFO] {item}")

    blocking = len(issues_a) + len(issues_b) + len(issues_c) + len(issues_d)
    print(f"\nblocking issues: {blocking}")
    if arguments.fail_on_issues and blocking:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
