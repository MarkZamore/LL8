#!/usr/bin/env python3
"""One-off migration of an Infinity world to a clean TNP Limitless 8 (LL8) pack.

The world (Chebupeli) keeps its overworld, its players and their progress; every
other dimension is dropped, and everything that belonged to a mod LL8 does not
ship is either remapped (AllTheOres -> the LL8 equivalent, found through the
``c:`` item tags) or deleted with a full report.

Default mode is a **dry run**: it computes and prints exactly what ``--apply``
would do and writes only the report.  Nothing in the world is touched.

    python tools/migrate_world_ll8.py --world <world> --pack <LL8 checkout>
    python tools/migrate_world_ll8.py --world <world> --pack <LL8> --apply
        --fresh-level <fresh LL8 world>/level.dat
    python tools/migrate_world_ll8.py --world <world> --pack <LL8> --verify

Exit codes: 0 done, 2 blocked before touching anything (world open, unreadable
NBT, no space), 3 --verify found a mismatch.

Design notes (the "why"):

* The set of surviving namespaces is **data driven** - the modIds of every jar
  in ``<pack>/mods`` (top level and nested), plus the ids KubeJS creates at
  startup, plus the loader/vanilla namespaces.  Hard-coding a mod list would go
  stale on the first LL8 update.
* Unknown *component* types make the whole ItemStack unparseable in 1.21.1, so
  foreign components are stripped from **live** stacks too, not only from the
  ones being deleted (``gravestonecurioscompat:*`` sits on ~30 perfectly good
  items, including items inside the ME cell).
* ``level.dat:Data.Player`` and ``playerdata/<uuid>.dat`` are two copies of the
  same inventory - the launcher re-exports one into the other on every launch,
  so both get the identical treatment.
* Every stage is idempotent and compares the re-encoded NBT against what is
  already on disk, so a second run reports "nothing to do".
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import struct
import sys
import tempfile
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import nbtlite as N  # noqa: E402  (path juggling has to happen first)

try:
    from scan_mods import scan_jar
except ImportError:  # pragma: no cover - scan_mods travels with this file
    scan_jar = None

try:
    import msvcrt
except ImportError:  # pragma: no cover - the launcher only runs on Windows
    msvcrt = None
    import fcntl

EXIT_OK, EXIT_BLOCKED, EXIT_VERIFY = 0, 2, 3

OVERWORLD = "minecraft:overworld"
NETHER = "minecraft:the_nether"
THE_END = "minecraft:the_end"
KEPT_DIMENSIONS = (OVERWORLD, NETHER, THE_END)

# Namespaces that exist without any jar in mods/.
ENVIRONMENT_NAMESPACES = frozenset({"minecraft", "neoforge", "forge", "c", "fabric", "kubejs"})

DEFAULT_OLD_PACK = Path(r"C:\Users\Oskar\Documents\Infinity")
DEFAULT_BACKUP_ROOT = Path(r"C:\Users\Oskar\Documents\LANMinecraft\Minecraft\Personal\Backups\Worlds")

DIMENSION_DIRECTORIES = ("DIM-1", "DIM1", "dimensions")
FTB_DELETE = ("ftbquests", "serverconfig")
FTB_KEEP = ("ftbteams", "ftbchunks", "ftbessentials")

# World paths that belong to one mod: deleted only when that mod is gone.
# ``None`` means "delete unconditionally" (stale cache of a mod that is present).
WORLD_FILE_OWNERS: dict[str, str | None] = {
    "chunkloaders": "chunkloaders",
    "data/chunkloaders_loaded_chunks.dat": "chunkloaders",
    "dimpockets": "dimensionalpocketsii",
    "minformax_indices": "minformax",
    "deaths": "gravestone",
    "alternate-current.conf": "alternate_current",
    "data/dankstorage": "dankstorage",
    "data/avaritia_accelerated_blocks.dat": "avaritia",
    "data/crafttweaker_saved_data.dat": "crafttweaker",
    "data/minecolonies_colony_manager.dat": "minecolonies",
    "data/citadel_world_data.dat": "citadel",
    "data/InControlData.dat": "incontrol",
    "data/biolith_overworld_state.dat": "biolith",
    "mfix_stronghold_cache_v2.nbt": None,
}

# Files handled by their own stage; the generic data/*.dat pass skips them.
SPECIAL_DATA_FILES = ("disk_manager.dat", "sophisticatedbackpacks.dat", "IFBackpack.dat",
                      "mekanism_InventoryFrequencyHandler.dat", "waystones.dat")

# Compounds under these keys carry a bare namespaced id (no count) and are
# blanked when their mod is gone - Mekanism frequencies store fluids this way.
FLUID_KEYS = frozenset({"fluid", "chemical", "Fluid", "FluidName", "gas"})
SLOT_KEYS = frozenset({"slot", "Slot", "index", "Index"})
STACK_VALUE_KEYS = frozenset({"item", "Item", "stack", "Stack"})
AMOUNT_SIBLINGS = ("Amount", "amount", "count", "Count")

# Which mod should provide the replacement when several tag members survive.
REMAP_PREFERENCE = ("mekanism", "modern_industrialization", "create",
                    "immersiveengineering", "enderio", "oritech")

# `c:` tags with a single path segment (c:ingots, c:gems, ...) group everything
# of a kind, so a "provider" from them would be an arbitrary item.  Only tags
# that name the material (c:ingots/tin) may drive a remap - and only within a
# *material* family: functional tags such as c:tools/ranged_weapon or
# c:foods/berry group items that merely behave alike, and swapping a trident for
# a random bow because both are "ranged weapons" is worse than deleting it.
REMAP_TAG_FAMILIES = frozenset({
    "ingots", "nuggets", "dusts", "small_dusts", "tiny_dusts", "dirty_dusts",
    "plates", "double_plates", "dense_plates", "curved_plates", "sheets",
    "rods", "gears", "wires", "gems", "clumps", "crystals", "shards",
    "raw_materials", "ores", "storage_blocks", "raw_blocks", "blocks",
})
TAG_ENTRY = re.compile(r"^data/(?P<ns>[^/]+)/tags/items?/(?P<path>.+)\.json$")

# id shape -> c: tag, used when the old pack ships no tag for the item.
SHAPE_TAGS: tuple[tuple[re.Pattern, str], ...] = (
    (re.compile(r"^raw_(.+)$"), "c:raw_materials/{0}"),
    (re.compile(r"^(.+)_ingot$"), "c:ingots/{0}"),
    (re.compile(r"^(.+)_dust$"), "c:dusts/{0}"),
    (re.compile(r"^(.+)_plate$"), "c:plates/{0}"),
    (re.compile(r"^(.+)_rod$"), "c:rods/{0}"),
    (re.compile(r"^(.+)_gear$"), "c:gears/{0}"),
    (re.compile(r"^(.+)_nugget$"), "c:nuggets/{0}"),
    (re.compile(r"^(.+)_gem$"), "c:gems/{0}"),
    (re.compile(r"^(.+)_ore$"), "c:ores/{0}"),
    (re.compile(r"^deepslate_(.+)_ore$"), "c:ores/{0}"),
    (re.compile(r"^(.+)_block$"), "c:storage_blocks/{0}"),
    (re.compile(r"^raw_(.+)_block$"), "c:storage_blocks/raw_{0}"),
    (re.compile(r"^(.+)$"), "c:gems/{0}"),  # bare gem names: ruby, peridot, ...
)

DELETE = object()  # sentinel returned by the scrubber: "drop me from my parent"


# ------------------------------------------------------------------ helpers

def abort(message: str):
    """Refuse to continue; exit code 2 means "blocked, world untouched"."""
    print("ERROR " + message, file=sys.stderr)
    raise SystemExit(EXIT_BLOCKED)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def stamp() -> str:
    return utc_now().astimezone().strftime("%Y%m%d-%H%M%S")


def human(size: float) -> str:
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if abs(size) < 1024 or unit == "TiB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TiB"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tree_size(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += (Path(root) / name).stat().st_size
            except OSError:
                pass
    return total


def free_space(path: Path) -> int:
    """Free bytes on the volume of `path`, walking up to an existing parent."""
    probe = path
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    return shutil.disk_usage(probe).free


def component_namespace(key: str) -> str:
    """Namespace of a component key, ignoring the 1.21 ``!`` removal marker."""
    return N.namespace(str(key).lstrip("!"))


def world_is_open(world: Path) -> bool:
    """Byte-range probe on ``session.lock`` - the same test as WorldAccessGuard."""
    lock = world / "session.lock"
    if not lock.is_file():
        return False
    try:
        with lock.open("r+b") as handle:
            length = max(1, os.fstat(handle.fileno()).st_size)
            if msvcrt is not None:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, length)
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, length)
            else:  # pragma: no cover
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        return False
    except OSError:
        return True


# ------------------------------------------------------------------ the pack

def kubejs_namespaces(pack: Path) -> set[str]:
    """Namespaces of ids created by ``kubejs/startup_scripts`` (``tnp:`` & co)."""
    found: set[str] = set()
    root = pack / "kubejs" / "startup_scripts"
    if not root.is_dir():
        return found
    pattern = re.compile(r"""\.create\w*\(\s*['"]([a-z0-9_.\-]+):""")
    for script in root.rglob("*.js"):
        try:
            text = script.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        found.update(pattern.findall(text))
    return found


def present_namespaces(pack: Path, extra: list[str]) -> tuple[set[str], dict]:
    """modIds of every jar in ``<pack>/mods`` + environment + KubeJS + extras."""
    mods = pack / "mods"
    if not mods.is_dir():
        abort(f"pack has no mods directory: {mods}")
    if scan_jar is None:
        abort("scan_mods.py is required next to this script")
    ids: set[str] = set()
    jars = sorted(mods.glob("*.jar"))
    for jar in jars:
        for provider in scan_jar(jar).providers:
            ids.add(provider.mod_id)
    scripted = kubejs_namespaces(pack)
    info = {"jars": len(jars), "modIds": len(ids), "kubejs": sorted(scripted),
            "extra": sorted(extra)}
    return ids | ENVIRONMENT_NAMESPACES | scripted | set(extra), info


class TagIndex:
    """``c:`` item tags of one pack, merged across every jar and datapack."""

    def __init__(self, tags: dict[str, list[str]] | None = None) -> None:
        self.tags: dict[str, list[str]] = tags or {}

    @classmethod
    def build(cls, mods: Path, datapack_roots=()) -> "TagIndex":
        index = cls()
        for jar in sorted(mods.glob("*.jar")) if mods.is_dir() else []:
            index._absorb_zip(jar)
        for root in datapack_roots:
            if not root.exists():
                continue
            for entry in sorted(root.iterdir()) if root.is_dir() else []:
                if entry.is_dir():
                    index._absorb_directory(entry)
                elif entry.suffix.lower() == ".zip":
                    index._absorb_zip(entry)
        return index

    def _absorb_zip(self, archive_path: Path) -> None:
        try:
            with zipfile.ZipFile(archive_path) as archive:
                for name in archive.namelist():
                    match = TAG_ENTRY.match(name)
                    if not match or match.group("ns") != "c":
                        continue
                    self._absorb_json("c:" + match.group("path"), archive.read(name))
        except (OSError, zipfile.BadZipFile, KeyError):
            pass

    def _absorb_directory(self, root: Path) -> None:
        for path in root.rglob("*.json"):
            relative = path.relative_to(root).as_posix()
            match = TAG_ENTRY.match(relative)
            if not match or match.group("ns") != "c":
                continue
            try:
                self._absorb_json("c:" + match.group("path"), path.read_bytes())
            except OSError:
                pass

    def _absorb_json(self, tag: str, raw: bytes) -> None:
        try:
            document = json.loads(raw.decode("utf-8-sig"))
        except (UnicodeDecodeError, ValueError):
            return
        values = self.tags.setdefault(tag, [])
        for value in document.get("values", []) if isinstance(document, dict) else []:
            if isinstance(value, dict):
                value = value.get("id")
            if isinstance(value, str) and value not in values:
                values.append(value)

    def tags_of(self, item_id: str) -> list[str]:
        """Material tags holding the item (``c:ingots/tin``), most specific first."""
        hits = [tag for tag, values in self.tags.items()
                if item_id in values and is_material_tag(tag)]
        return sorted(set(hits), key=lambda tag: (-tag.count("/"), tag))

    def members(self, tag: str, present: set[str], seen: set[str] | None = None) -> list[str]:
        """Tag members whose mod is installed, ``#c:`` references expanded."""
        seen = seen or set()
        if tag in seen:
            return []
        seen.add(tag)
        out: list[str] = []
        for value in self.tags.get(tag, []):
            if value.startswith("#"):
                out.extend(self.members(value[1:], present, seen))
            elif N.namespace(value) in present and value not in out:
                out.append(value)
        return out


class Remapper:
    """Absent item id -> the LL8 item that plays the same role (or ``None``)."""

    def __init__(self, mode: str, old_tags: TagIndex, new_tags: TagIndex,
                 present: set[str], overrides: dict[str, str | None]) -> None:
        self.mode = mode
        self.old_tags = old_tags
        self.new_tags = new_tags
        self.present = present
        self.overrides = overrides
        self.cache: dict[str, tuple[str | None, str]] = {}

    def _pick(self, candidates: list[str]) -> str | None:
        if not candidates:
            return None
        def rank(item_id: str) -> tuple[int, str]:
            namespace = N.namespace(item_id)
            order = REMAP_PREFERENCE.index(namespace) if namespace in REMAP_PREFERENCE else len(REMAP_PREFERENCE)
            return order, item_id
        return sorted(candidates, key=rank)[0]

    def target(self, item_id: str) -> tuple[str | None, str]:
        """-> (new id or None, human readable reason)."""
        if item_id in self.cache:
            return self.cache[item_id]
        result: tuple[str | None, str] = (None, "no match")
        if item_id in self.overrides:
            result = (self.overrides[item_id], "override")
        elif self.mode == "off":
            result = (None, "remap off")
        else:
            for tag in self.old_tags.tags_of(item_id):
                pick = self._pick(self.new_tags.members(tag, self.present))
                if pick:
                    result = (pick, f"tag {tag}")
                    break
            else:
                # No usable tag in the old pack (or none of its members survive):
                # guess the tag from the id shape and try again.
                for pattern, template in SHAPE_TAGS:
                    match = pattern.match(item_id.split(":", 1)[1])
                    if not match:
                        continue
                    tag = template.format(*match.groups())
                    if not is_material_tag(tag):
                        continue
                    pick = self._pick(self.new_tags.members(tag, self.present))
                    if pick:
                        result = (pick, f"shape {tag}")
                        break
        if result[0] is not None and N.namespace(result[0]) not in self.present:
            result = (None, "candidate mod absent")
        self.cache[item_id] = result
        return result


# ------------------------------------------------------------------ NBT file

class NbtFile:
    """A save file held in memory; written back only when its NBT changed."""

    def __init__(self, path: Path, relative: str) -> None:
        self.path = path
        self.relative = relative
        self.name, self.root, self.packed = N.read_nbt(path)
        self.baseline = N.encode(self.name, self.root)

    def current(self) -> bytes:
        return N.encode(self.name, self.root)

    def changed(self) -> bool:
        return self.current() != self.baseline


# ------------------------------------------------------------------ migration

def long_path(path: pathlib.Path) -> str:
    r"""Windows still stops at 260 characters unless a path says otherwise.

    The waypoint store nests a player UUID under a twenty-digit revision
    directory, and copying that into a timestamped backup folder is exactly the
    case that overflows. The \\?\ prefix lifts the limit; it demands an
    absolute path with no relative parts, which abspath already guarantees.
    """
    text = os.path.abspath(path)
    if os.name != "nt" or text.startswith("\\\\?\\"):
        return text
    if text.startswith("\\\\"):
        return "\\\\?\\UNC\\" + text[2:]
    return "\\\\?\\" + text


def copy_tree_long(source: pathlib.Path, destination: pathlib.Path) -> None:
    """copytree that survives deep paths on Windows."""
    root_source = long_path(source)
    root_destination = long_path(destination)
    for current, _, files in os.walk(root_source):
        relative = os.path.relpath(current, root_source)
        target = root_destination if relative == "." else os.path.join(root_destination, relative)
        os.makedirs(target, exist_ok=True)
        for name in files:
            shutil.copy2(os.path.join(current, name), os.path.join(target, name))


class Migration:
    """Holds the plan; every stage records what it did (or would do)."""

    def __init__(self, arguments: argparse.Namespace) -> None:
        self.args = arguments
        # abspath, not resolve(): resolve() expands substituted drives and
        # symlinks, which would turn a short path back into a >260 char one.
        self.world = Path(os.path.abspath(arguments.world))
        self.pack = Path(os.path.abspath(arguments.pack))
        self.old_pack = Path(os.path.abspath(arguments.old_pack))
        self.apply = bool(arguments.apply)
        self.backup_dir: Path | None = None
        self.planned_backup: Path | None = None
        self.player_sources: list[str] = []
        self.report_dir: Path = Path()
        self.warnings: list[str] = []
        self.notes: list[str] = []
        self.actions: list[str] = []
        self.deleted: list[dict] = []
        self.left_in_place: list[dict] = []
        self.written: list[str] = []
        self.per_source: dict[str, Counter] = {}
        self.remapped: dict[str, Counter] = {}
        self.remap_reason: dict[str, str] = {}
        self.collateral: Counter = Counter()
        self.components_stripped: list[dict] = []
        self.attachments_pruned: list[dict] = []
        self.recipes_pruned: list[dict] = []
        self.blanked: list[dict] = []
        self.level_before: dict = {}
        self.level_after: dict = {}
        self.waypoints: list[dict] = []
        self.expectations: dict = {}
        self.player_names: dict[str, str] = {}
        self.spawn = (0.5, 64.0, 0.5)
        self.present: set[str] = set()
        self.remapper: Remapper | None = None

    # -------------------------------------------------------------- plumbing

    def log(self, line: str) -> None:
        print(line)

    def warn(self, line: str) -> None:
        self.warnings.append(line)
        print("WARN " + line)

    def act(self, line: str) -> None:
        self.actions.append(line)
        print(("apply  " if self.apply else "would  ") + line)

    def dead(self, item_id: str) -> bool:
        return N.namespace(item_id) not in self.present

    def record(self, source: str, item_id: str, count: int, new_id: str | None) -> None:
        if new_id:
            self.remapped.setdefault(source, Counter())[f"{item_id}>{new_id}"] += count
        else:
            self.per_source.setdefault(source, Counter())[item_id] += count

    def backup_file(self, path: Path) -> None:
        """Pre-edit copy under ``<backup>/pre-ll8-files/<relative>``.

        Never a sibling of the original: the launcher tracks and transfers every
        GUID-named file in playerdata/, stats/ and advancements/, so a stray
        ``*.bak`` there would travel to the other player.
        """
        if not self.apply or self.backup_dir is None:
            return
        try:
            relative = path.relative_to(self.world)
        except ValueError:
            return
        target = self.backup_dir / "pre-ll8-files" / relative
        if target.exists():
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)

    def save(self, handle: NbtFile) -> bool:
        """Write the file back when its NBT differs from what is on disk."""
        if not handle.changed():
            return False
        self.act(f"rewrite {handle.relative}")
        self.written.append(handle.relative)
        if self.apply:
            self.backup_file(handle.path)
            N.write_nbt(handle.path, handle.name, handle.root, handle.packed)
        return True

    def remove_path(self, path: Path, reason: str) -> None:
        if not path.exists():
            return
        size = tree_size(path)
        relative = path.relative_to(self.world).as_posix()
        self.deleted.append({"path": relative, "kind": "dir" if path.is_dir() else "file",
                             "bytes": size, "reason": reason})
        self.act(f"delete {relative} ({human(size)}) - {reason}")
        if self.apply:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()

    # -------------------------------------------------------------- stage 0

    def nbt_targets(self) -> list[Path]:
        """Every NBT file this run may rewrite."""
        targets = [self.world / "level.dat", self.world / "level.dat_old"]
        playerdata = self.world / "playerdata"
        if playerdata.is_dir():
            targets += [p for p in sorted(playerdata.iterdir())
                        if p.suffix in (".dat", ".dat_old") or p.name.endswith(".dat_old")]
        data = self.world / "data"
        if data.is_dir():
            targets += sorted(data.glob("*.dat"))
        return [p for p in targets if p.is_file()]

    def preflight(self) -> None:
        if not (self.world / "level.dat").is_file():
            abort(f"not a world directory: {self.world}")
        if world_is_open(self.world):
            abort(f"world {self.world.name} is open in Minecraft - close it first")
        self.log(f"preflight: world closed ({self.world})")

        broken = [p for p in self.nbt_targets() if not N.roundtrip_ok(p)]
        if broken:
            for path in broken:
                print(f"  cannot round-trip: {path}", file=sys.stderr)
            abort("some NBT files do not survive a read/write round trip")
        self.log(f"preflight: {len(self.nbt_targets())} NBT files round-trip byte-identically")

        if self.apply and not self.args.no_backup:
            size = tree_size(self.world)
            free = free_space(self.args.backup_root)
            need = int(size * 1.2)
            self.log(f"preflight: world {human(size)}, free {human(free)} (need {human(need)})")
            if free < need:
                abort("not enough free space for the backup")

    # -------------------------------------------------------------- stage 1

    def make_backup(self) -> None:
        if not self.apply or self.args.no_backup or self.planned_backup is None:
            if self.args.no_backup and self.apply:
                self.warn("--no-backup: the world is edited in place, nothing is copied")
            self.backup_dir = None
            return
        self.backup_dir = self.planned_backup
        copy = self.backup_dir / self.world.name
        if copy.exists():
            abort(f"backup target already exists: {copy}")
        self.act(f"backup {self.world} -> {self.backup_dir}")
        # The directory may already hold this run's report/cache files.
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        copy_tree_long(self.world, copy)
        self.log(f"backup complete: {self.backup_dir}")

    # -------------------------------------------------------------- scrubbing

    def strip_components(self, node: tuple, path: str, source: str) -> None:
        """Drop component entries of absent mods from one stack/AE2 key.

        1.21.1 refuses to parse an ItemStack carrying an unknown component type,
        which would throw away a perfectly good item - so this runs on live
        stacks as well.
        """
        components = node[1].get("components")
        if not N.is_compound(components):
            return
        for key in list(components[1]):
            if component_namespace(key) in self.present:
                continue
            del components[1][key]
            ident = node[1].get("id")
            self.components_stripped.append({
                "source": source, "path": path, "component": N.safe_text(key),
                "stack": N.safe_text(ident[1]) if ident else "?",
            })

    def scrub(self, node, path: str, source: str, in_list: bool = False):
        """Recursive removal/remap pass; returns DELETE to be dropped by the parent."""
        if N.is_compound(node):
            fields = node[1]
            stack = N.stack_fields(node)
            if stack is not None:
                item_id, count, _count_key = stack
                if self.dead(item_id):
                    new_id, reason = self.remapper.target(item_id)
                    if new_id:
                        fields["id"] = ("str", new_id)
                        self.record(source, item_id, count, new_id)
                        self.remap_reason[item_id] = reason
                    else:
                        self.record(source, item_id, count, None)
                        for nested in N.iter_item_stacks(node):
                            if nested.node is not node:
                                self.collateral[nested.id] += nested.count
                        return DELETE
            self.strip_components(node, path, source)
            for key in list(fields):
                child = fields.get(key)
                if child is None:
                    continue
                if key in FLUID_KEYS and N.is_compound(child):
                    ident = child[1].get("id")
                    if ident is not None and ident[0] == "str" and self.dead(str(ident[1])):
                        self.record(source, str(ident[1]), 1, None)
                        self.blank(fields, key, path, source)
                        continue
                if not (N.is_compound(child) or N.is_list(child)):
                    continue
                verdict = self.scrub(child, f"{path}.{N.safe_text(key)}" if path else N.safe_text(key),
                                     source, in_list=False)
                if verdict is DELETE:
                    # {slot, item} wrapper inside a list -> drop the whole entry.
                    if in_list and key in STACK_VALUE_KEYS and len(fields) <= 4 \
                            and any(slot in fields for slot in SLOT_KEYS):
                        return DELETE
                    self.blank(fields, key, path, source)
            return None
        if N.is_list(node):
            kept = []
            for index, child in enumerate(node[2]):
                verdict = self.scrub(child, f"{path}[{index}]", source, in_list=True)
                if verdict is not DELETE:
                    kept.append(child)
            node[2][:] = kept
            return None
        return None

    def blank(self, fields: dict, key: str, path: str, source: str) -> None:
        """Replace a named compound value with an empty compound (and warn)."""
        fields[key] = ("comp", {})
        for sibling in AMOUNT_SIBLINGS:
            value = fields.get(sibling)
            if value is not None and value[0] in N.NUMERIC_KINDS:
                fields[sibling] = (value[0], 0)
        where = f"{path}.{N.safe_text(key)}" if path else N.safe_text(key)
        self.blanked.append({"source": source, "path": where})
        self.warn(f"{source}: {where} replaced with an empty compound")

    # -------------------------------------------------------------- stage 2

    def stage_dimensions(self, level: NbtFile) -> None:
        for name in DIMENSION_DIRECTORIES:
            self.remove_path(self.world / name, "non-overworld dimension data")

        data = N.get_path(level.root, "Data")
        if data is None:
            abort("level.dat has no Data compound")
        spawn = [N.get_path(data, key) for key in ("SpawnX", "SpawnY", "SpawnZ")]
        if all(node is not None for node in spawn):
            self.spawn = (float(spawn[0][1]) + 0.5, float(spawn[1][1]), float(spawn[2][1]) + 0.5)

        stems = N.get_path(data, "WorldGenSettings", "dimensions")
        self.level_before = {
            "dimensions": sorted(N.safe_text(k) for k in stems[1]) if stems else [],
            "dataPacks": N.nbt_to_py(N.get_path(data, "DataPacks")) if N.get_path(data, "DataPacks") else {},
            "dragonFight": "DragonFight" in data[1],
            "extraDragonFight": "bei_ExtraDragonFight" in data[1],
        }

        fresh_stems, fresh_packs = self.read_fresh_level()
        if stems is not None:
            for key in list(stems[1]):
                if str(key) not in KEPT_DIMENSIONS:
                    del stems[1][key]
            # The world's nether stem is NOT vanilla (explicit incendium biome
            # list), so it must be replaced rather than kept.
            stems[1][NETHER] = fresh_stems.get(NETHER, vanilla_nether_stem())
            stems[1][THE_END] = fresh_stems.get(THE_END, vanilla_end_stem())
            if OVERWORLD not in stems[1]:
                self.warn("level.dat has no minecraft:overworld stem")

        for key in ("DragonFight", "bei_ExtraDragonFight"):
            if data[1].pop(key, None) is not None:
                self.act(f"level.dat: drop Data.{key} (the regenerated End gets a fresh fight)")

        packs = N.get_path(data, "DataPacks")
        if fresh_packs is not None:
            if packs is None or N.encode("", packs) != N.encode("", fresh_packs):
                self.act("level.dat: DataPacks taken from --fresh-level")
            data[1]["DataPacks"] = fresh_packs
        elif packs is not None:
            self.prune_datapacks(packs)
            self.warn("no --fresh-level: DataPacks were only pruned. Create a world in LL8 "
                      "and re-run with --fresh-level <ll8 world>/level.dat before --apply.")

        self.level_after = {
            "dimensions": sorted(N.safe_text(k) for k in stems[1]) if stems else [],
            "dataPacks": N.nbt_to_py(N.get_path(data, "DataPacks")) if N.get_path(data, "DataPacks") else {},
            "dragonFight": "DragonFight" in data[1],
            "extraDragonFight": "bei_ExtraDragonFight" in data[1],
        }

    def read_fresh_level(self) -> tuple[dict, tuple | None]:
        if not self.args.fresh_level:
            return {}, None
        path: Path = self.args.fresh_level
        if not path.is_file():
            abort(f"--fresh-level not found: {path}")
        _name, root, _packed = N.read_nbt(path)
        stems = N.get_path(root, "Data", "WorldGenSettings", "dimensions")
        packs = N.get_path(root, "Data", "DataPacks")
        picked = {}
        if stems is not None:
            for key in (NETHER, THE_END):
                if key in stems[1]:
                    picked[key] = stems[1][key]
        self.notes.append(f"fresh level.dat: {path}")
        return picked, packs

    def prune_datapacks(self, packs: tuple) -> None:
        """Drop pack ids whose mod is gone; unknown shapes are kept untouched."""
        for list_name in ("Enabled", "Disabled"):
            entries = packs[1].get(list_name)
            if not N.is_list(entries):
                continue
            kept = []
            for entry in entries[2]:
                text = str(entry[1])
                namespace = datapack_namespace(text)
                if namespace and namespace not in self.present:
                    self.act(f"level.dat: DataPacks.{list_name} drop {text}")
                    continue
                kept.append(entry)
            entries[2][:] = kept

    # -------------------------------------------------------------- stage 3

    def stage_players(self, level: NbtFile) -> None:
        player = N.get_path(level.root, "Data", "Player")
        if player is not None:
            self.scrub_player(player, "level.dat:Data.Player")
        playerdata = self.world / "playerdata"
        if not playerdata.is_dir():
            return
        for path in sorted(playerdata.iterdir()):
            if not (path.name.endswith(".dat") or path.name.endswith(".dat_old")):
                continue  # .pre-relics012 and .cosarmor are left alone on purpose
            handle = NbtFile(path, f"playerdata/{path.name}")
            label = self.player_label(path)
            if path.name.endswith(".dat"):
                self.player_sources.append(label)
            self.scrub_player(handle.root, label)
            self.save(handle)

    def player_label(self, path: Path) -> str:
        uuid = path.name.split(".")[0]
        name = self.player_names.get(uuid)
        suffix = "_old" if path.name.endswith("_old") else ""
        return f"{name or uuid}{suffix} (playerdata/{path.name})"

    def scrub_player(self, player: tuple, source: str) -> None:
        self.scrub(player, "", source)
        if not self.args.keep_attachments:
            attachments = player[1].get("neoforge:attachments")
            if N.is_compound(attachments):
                for key in list(attachments[1]):
                    if N.namespace(key) not in self.present:
                        del attachments[1][key]
                        self.attachments_pruned.append({"source": source, "key": N.safe_text(key)})
                if not attachments[1]:
                    del player[1]["neoforge:attachments"]
        book = player[1].get("recipeBook")
        if N.is_compound(book):
            for key, value in list(book[1].items()):
                if not N.is_list(value) or value[1] != N.TAG_OF["str"]:
                    continue
                kept = []
                for entry in value[2]:
                    if N.namespace(str(entry[1])) in self.present:
                        kept.append(entry)
                    else:
                        self.recipes_pruned.append({"source": source, "key": N.safe_text(key),
                                                    "id": N.safe_text(entry[1])})
                value[2][:] = kept
        self.reset_dimension(player, source)

    def reset_dimension(self, player: tuple, source: str) -> None:
        """A player standing in a deleted dimension is moved to the world spawn."""
        fields = player[1]
        dimension = fields.get("Dimension")
        if dimension is not None and dimension[0] == "str" and str(dimension[1]) != OVERWORLD:
            self.act(f"{source}: Dimension {N.safe_text(dimension[1])} -> {OVERWORLD} at spawn")
            fields["Dimension"] = ("str", OVERWORLD)
            fields["Pos"] = ("list", N.TAG_OF["d"], [("d", value) for value in self.spawn])
            fields["Motion"] = ("list", N.TAG_OF["d"], [("d", 0.0)] * 3)
            fields["FallDistance"] = ("f", 0.0)
            if fields.pop("RootVehicle", None) is not None:
                self.act(f"{source}: dropped RootVehicle (its vehicle is gone)")
        spawn_dimension = fields.get("SpawnDimension")
        if spawn_dimension is not None and spawn_dimension[0] == "str" \
                and str(spawn_dimension[1]) != OVERWORLD:
            self.act(f"{source}: SpawnDimension {N.safe_text(spawn_dimension[1])} -> world spawn")
            for key in ("SpawnDimension", "SpawnX", "SpawnY", "SpawnZ", "SpawnAngle", "SpawnForced"):
                fields.pop(key, None)

    # -------------------------------------------------------------- stage 4

    def stage_storage(self) -> None:
        data = self.world / "data"
        if not data.is_dir():
            return
        disk = data / "disk_manager.dat"
        if disk.is_file():
            handle = NbtFile(disk, "data/disk_manager.dat")
            self.migrate_ae2(handle)
            self.save(handle)
        for name in ("sophisticatedbackpacks.dat", "IFBackpack.dat",
                     "mekanism_InventoryFrequencyHandler.dat"):
            path = data / name
            if not path.is_file():
                continue
            handle = NbtFile(path, f"data/{name}")
            self.scrub(handle.root, "", f"data/{name}")
            self.save(handle)
        for path in sorted(data.glob("*.dat")):
            if path.name in SPECIAL_DATA_FILES or re.match(r"^map_\d+\.dat$", path.name):
                continue
            handle = NbtFile(path, f"data/{path.name}")
            self.scrub(handle.root, "", f"data/{path.name}")
            self.save(handle)

    def migrate_ae2(self, handle: NbtFile) -> None:
        """AE2 Things cells: parallel ``keys[]``/``amts[]``, merged on collision."""
        source = "AE2 disk_manager"
        for _path, node in N.walk(handle.root):
            if not N.is_compound(node):
                continue
            keys, amts = node[1].get("keys"), node[1].get("amts")
            if not N.is_list(keys) or amts is None or amts[0] != "la":
                continue
            new_keys: list = []
            new_amounts: list[int] = []
            index: dict[bytes, int] = {}
            for position, key in enumerate(keys[2]):
                amount = amts[1][position] if position < len(amts[1]) else 0
                ident = key[1].get("id") if N.is_compound(key) else None
                item_id = str(ident[1]) if ident is not None and ident[0] == "str" else ""
                if item_id and self.dead(item_id):
                    new_id, reason = self.remapper.target(item_id)
                    if not new_id:
                        self.record(source, item_id, amount, None)
                        continue
                    key[1]["id"] = ("str", new_id)
                    self.record(source, item_id, amount, new_id)
                    self.remap_reason[item_id] = reason
                if N.is_compound(key):
                    self.strip_components(key, f"keys[{position}]", source)
                signature = N.encode("", key)
                if signature in index:
                    new_amounts[index[signature]] += amount
                    continue
                index[signature] = len(new_keys)
                new_keys.append(key)
                new_amounts.append(amount)
            keys[2][:] = new_keys
            amts[1][:] = new_amounts
            total = node[1].get("item_count")
            if total is not None:
                before = int(total[1])
                node[1]["item_count"] = (total[0], sum(new_amounts))
                if before != sum(new_amounts):
                    self.act(f"{source}: item_count {before} -> {sum(new_amounts)}")
                self.expectations.setdefault("diskItemCount", []).append(sum(new_amounts))

    # -------------------------------------------------------------- stage 5/6

    def stage_waystones(self) -> None:
        path = self.world / "data" / "waystones.dat"
        if not path.is_file():
            return
        handle = NbtFile(path, "data/waystones.dat")
        self.scrub(handle.root, "", "data/waystones.dat")
        for _path, node in N.walk(handle.root):
            if not N.is_compound(node):
                continue
            stones = node[1].get("Waystones")
            if not N.is_list(stones):
                continue
            kept, dropped = [], 0
            for entry in stones[2]:
                world = N.get_path(entry, "World")
                if world is not None and world[0] == "str" and str(world[1]) != OVERWORLD:
                    dropped += 1
                    continue
                kept.append(entry)
            if dropped:
                self.act(f"data/waystones.dat: drop {dropped} non-overworld waystone(s), "
                         f"{len(kept)} kept")
            stones[2][:] = kept
        self.save(handle)

    def stage_maps(self) -> None:
        data = self.world / "data"
        if not data.is_dir():
            return
        for path in sorted(data.glob("map_*.dat")):
            try:
                _name, root, _packed = N.read_nbt(path)
            except (N.NbtError, OSError, struct.error):
                continue
            dimension = N.get_path(root, "data", "dimension")
            if dimension is not None and dimension[0] == "str" and str(dimension[1]) != OVERWORLD:
                self.remove_path(path, f"map of {N.safe_text(dimension[1])}")

    # -------------------------------------------------------------- stage 7/8

    def stage_ftb(self) -> None:
        for name in FTB_DELETE:
            self.remove_path(self.world / name, "LL8 ships its own quests/server config")
        for name in FTB_KEEP:
            if (self.world / name).exists():
                self.left_in_place.append({"path": name, "reason": "teams/claims/homes are kept"})

    def stage_orphans(self) -> None:
        for relative, owner in WORLD_FILE_OWNERS.items():
            path = self.world / relative
            if not path.exists():
                continue
            if owner is None:
                self.remove_path(path, "stale cache, regenerated on demand")
            elif owner not in self.present:
                self.remove_path(path, f"owner mod '{owner}' is not in the pack")
            else:
                self.left_in_place.append({"path": relative, "reason": f"'{owner}' is installed"})

    def stage_left_in_place(self) -> None:
        """Everything that survives, so the report accounts for the whole world."""
        deleted = {entry["path"] for entry in self.deleted}
        listed = {entry["path"] for entry in self.left_in_place}
        touched = {path.split("/", 1)[0] for path in self.written} | \
                  {path.split("/", 1)[0] for path in deleted if "/" in path}
        for entry in sorted(self.world.iterdir()):
            relative = entry.name
            if relative in deleted or relative in listed:
                continue
            reason = "правится этим скриптом" if relative in touched else \
                "не принадлежит удалённому моду"
            self.left_in_place.append({"path": relative, "reason": reason,
                                       "bytes": tree_size(entry)})

    # -------------------------------------------------------------- stage 9

    def stage_waypoints(self) -> None:
        store = self.world / ".minecraft-portable-waypoints"
        manifest_path = store / "manifest.json"
        if not manifest_path.is_file():
            return
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        touched = False
        for uuid, player in (manifest.get("players") or {}).items():
            for provider_id, provider in (player.get("providers") or {}).items():
                files = provider.get("files") or []
                kept = [f for f in files if keeps_waypoint_file(provider_id, f["relativePath"])]
                dropped = [f for f in files if f not in kept]
                if not dropped:
                    continue
                touched = True
                revision = int(provider["revision"]) + 1
                digest = snapshot_hash(provider, kept, store, provider["revisionDirectory"])
                directory = (f"players/{uuid.lower()}/{provider_id.lower()}"
                             f"/revisions/{revision:020d}-{digest[:12]}")
                self.act(f"waypoints {self.player_names.get(uuid, uuid)}/{provider_id}: drop "
                         + ", ".join(f["relativePath"] for f in dropped)
                         + f" -> revision {revision}")
                self.waypoints.append({
                    "player": uuid, "provider": provider_id,
                    "dropped": [f["relativePath"] for f in dropped],
                    "kept": [f["relativePath"] for f in kept],
                    "revision": revision, "sha256": digest, "directory": directory,
                })
                if self.apply:
                    old_root = store / provider["revisionDirectory"]
                    new_root = store / directory
                    new_root.mkdir(parents=True, exist_ok=True)
                    for entry in kept:
                        destination = new_root / entry["relativePath"]
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(old_root / entry["relativePath"], destination)
                    if old_root.exists() and old_root.resolve() != new_root.resolve():
                        shutil.rmtree(old_root)
                provider["files"] = kept
                provider["revision"] = revision
                provider["sha256"] = digest
                provider["sizeBytes"] = sum(int(f["sizeBytes"]) for f in kept)
                provider["savedAtUtc"] = utc_now().isoformat()
                provider["revisionDirectory"] = directory
        if touched:
            manifest["updatedAtUtc"] = utc_now().isoformat()
            if self.apply:
                self.backup_file(manifest_path)
                manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False),
                                         encoding="utf-8")
            self.written.append(".minecraft-portable-waypoints/manifest.json")

    # -------------------------------------------------------------- driver

    def load_player_names(self) -> None:
        """uuid -> nickname, for readable report columns (both files are read only).

        The player manifest can carry an empty ``lastKnownName`` (a player who
        never finished a transfer), so the waypoint manifest fills the gaps.
        """
        def remember(uuid: str, name) -> None:
            name = str(name or "").strip()
            if uuid and name and not self.player_names.get(uuid):
                self.player_names[uuid] = name

        players = self.world / ".minecraft-portable-players.json"
        if players.is_file():
            try:
                document = json.loads(players.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                document = {}
            for player in document.get("players") or []:
                remember(str(player.get("portableUuid") or player.get("minecraftUuid") or ""),
                         player.get("lastKnownName"))
        waypoints = self.world / ".minecraft-portable-waypoints" / "manifest.json"
        if waypoints.is_file():
            try:
                document = json.loads(waypoints.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                document = {}
            for uuid, player in (document.get("players") or {}).items():
                remember(str(uuid), (player or {}).get("lastKnownName"))

    def prepare(self) -> None:
        cache_dir = self.report_dir
        cache_dir.mkdir(parents=True, exist_ok=True)
        self.present, info = present_namespaces(self.pack, self.args.extra_present)
        self.present |= set(self.args.keep_namespace)
        self.log(f"pack: {info['jars']} jars, {info['modIds']} modIds, "
                 f"kubejs adds {info['kubejs']}, present namespaces {len(self.present)}")
        (cache_dir / "ll8-present-namespaces.json").write_text(
            json.dumps({"pack": str(self.pack), "computedAtUtc": utc_now().isoformat(),
                        "info": info, "namespaces": sorted(self.present)}, indent=1),
            encoding="utf-8")

        overrides: dict[str, str | None] = {}
        mode = self.args.remap
        if mode not in ("auto", "off"):
            overrides = json.loads(Path(mode).read_text(encoding="utf-8"))
            mode = "auto"
        old_tags = TagIndex.build(self.old_pack / "mods") if mode == "auto" else TagIndex()
        new_tags = TagIndex.build(self.pack / "mods",
                                  [self.pack / "config" / "paxi" / "datapacks"]) if mode == "auto" else TagIndex()
        if mode == "auto":
            self.log(f"tags: {len(old_tags.tags)} c: tags in the old pack, "
                     f"{len(new_tags.tags)} in LL8")
        self.remapper = Remapper(mode, old_tags, new_tags, self.present, overrides)
        self.load_player_names()

    def reset(self) -> None:
        """Clear the accumulators so the same object can analyse more than once."""
        self.actions, self.deleted, self.left_in_place, self.written = [], [], [], []
        self.per_source, self.remapped, self.collateral = {}, {}, Counter()
        self.components_stripped, self.attachments_pruned = [], []
        self.recipes_pruned, self.blanked, self.waypoints = [], [], []
        self.player_sources, self.expectations, self.warnings = [], {}, []
        self.notes = [note for note in self.notes if note.startswith("fresh level.dat")]

    def run(self) -> None:
        self.reset()
        self.preflight()
        self.make_backup()
        level = NbtFile(self.world / "level.dat", "level.dat")
        self.stage_dimensions(level)
        self.stage_players(level)
        self.save(level)
        self.sync_level_dat_old(level)
        self.stage_storage()
        self.stage_waystones()
        self.stage_maps()
        self.stage_ftb()
        self.stage_orphans()
        self.stage_waypoints()
        self.stage_left_in_place()
        self.add_notes()
        self.build_expectations()

    def add_notes(self) -> None:
        """Things the tool deliberately does not touch, for the report."""
        lootr = self.world / "data" / "lootr"
        if lootr.is_dir():
            self.notes.append(
                f"`data/lootr/**` ({sum(1 for _ in lootr.rglob('*.dat'))} файлов) не правится: "
                "мод есть в LL8, а неизвестные предметы внутри сундуков Minecraft отбросит сам "
                "при первом открытии.")
        self.notes.append(
            "`region/`, `entities/`, `poi/` не трогаются: блоки и мобы удалённых модов исчезнут "
            "при загрузке чанков (с предупреждениями в логе) — это ожидаемо.")
        self.notes.append(
            "`.minecraft-portable-players.json` и `.minecraft-portable-world.json` не трогаются: "
            "лаунчер владеет ими и перезаписывает при запуске.")

    def sync_level_dat_old(self, level: NbtFile) -> None:
        """``level.dat_old`` := the migrated ``level.dat``.

        Minecraft falls back to level.dat_old when level.dat cannot be read; a
        stale copy would silently restore the 39 dead dimension stems.
        """
        target = self.world / "level.dat_old"
        body = level.current()
        if target.is_file():
            try:
                name, root, _packed = N.read_nbt(target)
                if N.encode(name, root) == body:
                    return
            except (N.NbtError, OSError, struct.error):
                pass
        self.act("level.dat_old := copy of the migrated level.dat")
        self.written.append("level.dat_old")
        if self.apply:
            if target.is_file():
                self.backup_file(target)
            N.write_nbt(target, level.name, level.root, level.packed)

    def build_expectations(self) -> None:
        self.expectations["dimensionStems"] = self.level_after.get("dimensions", [])
        self.expectations["deletedPaths"] = [entry["path"] for entry in self.deleted]
        # DIM-1/DIM1/dimensions/ftbquests come back on the next launch, orphans
        # of absent mods must not - that is what --verify can actually assert.
        self.expectations["orphansGone"] = [
            entry["path"] for entry in self.deleted
            if "owner mod" in entry["reason"] or "stale cache" in entry["reason"]]
        quests = self.world / "ftbquests"
        self.expectations["ftbQuestFiles"] = sorted(
            p.name for p in quests.iterdir()) if quests.is_dir() else []
        teams = self.world / "ftbteams"
        self.expectations["ftbTeams"] = {
            p.relative_to(teams).as_posix(): sha256_file(p)
            for p in sorted(teams.rglob("*")) if p.is_file()} if teams.is_dir() else {}
        self.expectations["deadStacks"] = sum(sum(c.values()) for c in self.per_source.values())
        self.expectations["remappedStacks"] = sum(sum(c.values()) for c in self.remapped.values())
        self.expectations["foreignComponents"] = len(self.components_stripped)


def is_material_tag(tag: str) -> bool:
    """``c:ingots/tin`` yes, ``c:ingots`` and ``c:tools/shears`` no."""
    path = tag.split(":", 1)[1] if ":" in tag else tag
    return "/" in path and path.split("/", 1)[0] in REMAP_TAG_FAMILIES


def datapack_namespace(entry: str) -> str | None:
    """Mod namespace behind a DataPacks entry, or ``None`` when unknown."""
    text = entry.strip()
    if text.startswith("mod/"):
        text = text[4:]
        return text.split(":", 1)[0].split("/", 1)[0] or None
    if text.startswith(("file/", "builtin/")) or "/" in text:
        return None  # user packs and vanilla builtins: never guess
    if ":" in text:
        return text.split(":", 1)[0]
    return None


def vanilla_nether_stem() -> tuple:
    return ("comp", {
        "type": ("str", NETHER),
        "generator": ("comp", {
            "type": ("str", "minecraft:noise"),
            "biome_source": ("comp", {
                "type": ("str", "minecraft:multi_noise"),
                "preset": ("str", "minecraft:nether"),
            }),
            "settings": ("str", "minecraft:nether"),
        }),
    })


def vanilla_end_stem() -> tuple:
    return ("comp", {
        "type": ("str", THE_END),
        "generator": ("comp", {
            "type": ("str", "minecraft:noise"),
            "biome_source": ("comp", {"type": ("str", "minecraft:the_end")}),
            "settings": ("str", "minecraft:end"),
        }),
    })


def keeps_waypoint_file(provider_id: str, relative: str) -> bool:
    """Overworld-only filter matching each provider's native layout."""
    parts = relative.split("/")
    if provider_id == "ftb-chunks":
        # <dimension folder>/waypoints.json, one folder per dimension.
        return len(parts) < 2 or parts[0] == "minecraft_overworld"
    if provider_id == "xaero-minimap":
        # dim%<id>/waypoints*.txt; provider root files carry no dimension.
        return len(parts) < 2 or not parts[0].startswith("dim%") or parts[0] == "dim%0"
    return True


def snapshot_hash(provider: dict, files: list[dict], store: Path, revision_directory: str) -> str:
    """WaypointStoreService.ComputeSnapshotHash re-implemented byte for byte."""
    digest = hashlib.sha256()

    def append_string(value: str) -> None:
        raw = (value or "").encode("utf-8")
        digest.update(len(raw).to_bytes(8, "big"))
        digest.update(raw)

    append_string(provider.get("providerId", ""))
    append_string(provider.get("formatVersion", ""))
    append_string(provider.get("worldContextId", ""))
    for entry in sorted(files, key=lambda item: item["relativePath"]):
        content = (store / revision_directory / entry["relativePath"]).read_bytes()
        append_string(entry["relativePath"])
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


# ------------------------------------------------------------------ report

def render_report(migration: Migration) -> tuple[str, dict]:
    """Russian markdown report + the machine readable twin."""
    names = migration.player_names
    ae2 = migration.per_source.get("AE2 disk_manager", Counter())
    backpacks = migration.per_source.get("data/sophisticatedbackpacks.dat", Counter())
    ifpack = migration.per_source.get("data/IFBackpack.dat", Counter())
    players = {source: migration.per_source.get(source, Counter())
               for source in migration.player_sources}

    def merged(counters) -> Counter:
        total = Counter()
        for counter in counters:
            total.update(counter)
        return total

    summary_sources = [ae2, backpacks, ifpack] + list(players.values())
    grand = merged(summary_sources)
    namespaces = sorted({N.namespace(item) for item in grand},
                        key=lambda ns: -sum(v for k, v in grand.items() if N.namespace(k) == ns))

    lines: list[str] = []
    add = lines.append
    add(f"# Миграция мира {migration.world.name}: Infinity → LL8")
    add("")
    add(f"* режим: **{'ПРИМЕНЕНИЕ (--apply)' if migration.apply else 'предпросмотр (dry-run)'}**")
    add(f"* дата: {utc_now().astimezone().strftime('%Y-%m-%d %H:%M:%S %z')}")
    add(f"* мир: `{migration.world}`")
    add(f"* пак LL8: `{migration.pack}`  •  старый пак (теги): `{migration.old_pack}`")
    add(f"* бэкап: `{migration.backup_dir}`" if migration.backup_dir else "* бэкап: не создавался")
    add(f"* присутствующих неймспейсов: {len(migration.present)}")
    add("")

    add("## Сводка по модам (что исчезает из мира)")
    add("")
    header = ["мод (namespace)", "id", "всего", "МЭ-диск", "рюкзаки", "IF"]
    header += [names.get(source.split(" ")[0], source.split(" ")[0]) for source in players]
    add("| " + " | ".join(header) + " |")
    add("|" + "|".join(["---"] * len(header)) + "|")
    for namespace in namespaces:
        def part(counter: Counter) -> int:
            return sum(value for key, value in counter.items() if N.namespace(key) == namespace)
        row = [namespace,
               str(sum(1 for key in grand if N.namespace(key) == namespace)),
               str(part(grand)), str(part(ae2)), str(part(backpacks)), str(part(ifpack))]
        row += [str(part(counter)) for counter in players.values()]
        add("| " + " | ".join(row) + " |")
    add("| **итого** | " + str(len(grand)) + " | " + str(sum(grand.values())) + " | "
        + str(sum(ae2.values())) + " | " + str(sum(backpacks.values())) + " | "
        + str(sum(ifpack.values())) + " | "
        + " | ".join(str(sum(counter.values())) for counter in players.values()) + " |")
    add("")
    add("> Колонки игроков — их `playerdata/<uuid>.dat`. Копия инвентаря хозяина в "
        "`level.dat:Data.Player` и файлы `.dat_old` правятся так же, но в сводке не "
        "учитываются, чтобы не считать одно и то же дважды.")
    add("")

    add("## Удаляемые предметы по источникам")
    add("")
    for source in sorted(migration.per_source):
        counter = migration.per_source[source]
        if not counter:
            continue
        add(f"### {source} — {len(counter)} id / {sum(counter.values())} шт.")
        add("")
        by_namespace: dict[str, list[tuple[str, int]]] = {}
        for item_id, count in counter.most_common():
            by_namespace.setdefault(N.namespace(item_id), []).append((item_id, count))
        for namespace in sorted(by_namespace, key=lambda ns: -sum(c for _, c in by_namespace[ns])):
            entries = by_namespace[namespace]
            add(f"* **{namespace}** ({sum(count for _, count in entries)} шт.): "
                + ", ".join(f"`{item}` ×{count}" for item, count in entries))
        add("")
    if migration.collateral:
        add("### Содержимое удаляемых контейнеров (исчезнет вместе с ними)")
        add("")
        add(", ".join(f"`{item}` ×{count}" for item, count in migration.collateral.most_common()))
        add("")

    add("## Таблица переноса (remap)")
    add("")
    remap_rows = merged(migration.remapped.values())
    if remap_rows:
        add("| было | стало | шт. | источник соответствия |")
        add("|---|---|---|---|")
        for key, count in remap_rows.most_common():
            old, new = key.split(">", 1)
            add(f"| `{old}` | `{new}` | {count} | {migration.remap_reason.get(old, '')} |")
        add(f"| **итого** | | {sum(remap_rows.values())} | |")
    else:
        add("нет переносов (`--remap off` или ни одного совпадения)")
    add("")

    add("## Компоненты и аттачменты")
    add("")
    stripped = Counter((entry["component"], entry["source"]) for entry in migration.components_stripped)
    if stripped:
        add(f"Срезано компонентов отсутствующих модов: **{len(migration.components_stripped)}** "
            "(без этого 1.21.1 не может разобрать весь предмет целиком).")
        add("")
        for (component, source), count in stripped.most_common():
            add(f"* `{component}` — {source} ×{count}")
    else:
        add("Чужих компонентов не найдено.")
    add("")
    pruned = Counter((entry["key"], entry["source"]) for entry in migration.attachments_pruned)
    if pruned:
        add(f"Удалено `neoforge:attachments`: **{len(migration.attachments_pruned)}**")
        add("")
        for (key, source), count in pruned.most_common(200):
            add(f"* `{key}` — {source} ×{count}")
    else:
        add("Аттачменты не трогались.")
    add("")
    if migration.recipes_pruned:
        add(f"Из `recipeBook` удалено {len(migration.recipes_pruned)} рецептов отсутствующих модов.")
        add("")

    add("## level.dat")
    add("")
    before, after = migration.level_before, migration.level_after
    add(f"* измерения: было **{len(before.get('dimensions', []))}**, стало "
        f"**{len(after.get('dimensions', []))}** — {', '.join(after.get('dimensions', []))}")
    add(f"* `Data.DragonFight`: {before.get('dragonFight')} → {after.get('dragonFight')}; "
        f"`bei_ExtraDragonFight`: {before.get('extraDragonFight')} → {after.get('extraDragonFight')}")
    packs_before = before.get("dataPacks", {}) or {}
    packs_after = after.get("dataPacks", {}) or {}
    add(f"* `Data.DataPacks`: Enabled {len(packs_before.get('Enabled', []))} → "
        f"{len(packs_after.get('Enabled', []))}, Disabled {len(packs_before.get('Disabled', []))} → "
        f"{len(packs_after.get('Disabled', []))}")
    add("* `level.dat_old` перезаписан копией нового `level.dat`")
    add("")

    add("## Удалённые файлы и каталоги")
    add("")
    if migration.deleted:
        add("| путь | тип | размер | причина |")
        add("|---|---|---|---|")
        for entry in sorted(migration.deleted, key=lambda item: -item["bytes"]):
            add(f"| `{entry['path']}` | {entry['kind']} | {human(entry['bytes'])} | {entry['reason']} |")
        add(f"| **итого** | | {human(sum(entry['bytes'] for entry in migration.deleted))} | |")
    else:
        add("нечего удалять")
    add("")

    add("## Точки телепорта (.minecraft-portable-waypoints)")
    add("")
    if migration.waypoints:
        for entry in migration.waypoints:
            add(f"* {names.get(entry['player'], entry['player'])} / {entry['provider']}: "
                f"убрано {', '.join(entry['dropped'])}; осталось "
                f"{', '.join(entry['kept']) or '—'}; ревизия {entry['revision']}, "
                f"sha256 `{entry['sha256'][:16]}…`")
    else:
        add("изменений нет")
    add("")

    add("## Оставлено как есть")
    add("")
    for entry in sorted(migration.left_in_place, key=lambda item: item["path"]):
        size = f" ({human(entry['bytes'])})" if "bytes" in entry else ""
        add(f"* `{entry['path']}`{size} — {entry['reason']}")
    add("")

    add("## Примечания")
    add("")
    for note in migration.notes:
        add(f"* {note}")
    add("")

    add("## Предупреждения")
    add("")
    if migration.warnings:
        for warning in migration.warnings:
            add(f"* {warning}")
    else:
        add("нет")
    add("")

    add("## Ожидания для `--verify`")
    add("")
    expectations = migration.expectations
    add(f"* стемов измерений: {len(expectations.get('dimensionStems', []))} "
        f"({', '.join(expectations.get('dimensionStems', []))})")
    add(f"* `item_count` МЭ-дисков: {expectations.get('diskItemCount')}")
    add(f"* мёртвых стаков после миграции: 0 (сейчас {expectations.get('deadStacks')})")
    add(f"* чужих компонентов после миграции: 0 (сейчас {expectations.get('foreignComponents')})")
    add(f"* `ftbteams/`: {len(expectations.get('ftbTeams', {}))} файл(ов) без изменений")
    add("")

    document = {
        "generatedAtUtc": utc_now().isoformat(),
        "mode": "apply" if migration.apply else "dry-run",
        "world": str(migration.world),
        "pack": str(migration.pack),
        "oldPack": str(migration.old_pack),
        "backup": str(migration.backup_dir) if migration.backup_dir else None,
        "presentNamespaces": len(migration.present),
        "removedBySource": {source: dict(counter.most_common())
                            for source, counter in migration.per_source.items()},
        "remappedBySource": {source: dict(counter.most_common())
                             for source, counter in migration.remapped.items()},
        "remapReasons": migration.remap_reason,
        "collateral": dict(migration.collateral.most_common()),
        "componentsStripped": migration.components_stripped,
        "attachmentsPruned": migration.attachments_pruned,
        "recipesPruned": migration.recipes_pruned,
        "blankedCompounds": migration.blanked,
        "levelBefore": migration.level_before,
        "levelAfter": migration.level_after,
        "deleted": migration.deleted,
        "leftInPlace": migration.left_in_place,
        "written": migration.written,
        "waypoints": migration.waypoints,
        "warnings": migration.warnings,
        "notes": migration.notes,
        "actions": migration.actions,
        "expectations": migration.expectations,
    }
    return "\n".join(lines), document


# ------------------------------------------------------------------ verify

def verify(migration: Migration) -> int:
    """Re-read the world after the first LL8 session and check the report."""
    report_path = migration.report_dir / "migration-report.json"
    if not report_path.is_file():
        abort(f"no report to verify against: {report_path}")
    expected = json.loads(report_path.read_text(encoding="utf-8")).get("expectations", {})
    world = migration.world
    checks: list[tuple[bool, str]] = []

    _name, root, _packed = N.read_nbt(world / "level.dat")
    stems = N.get_path(root, "Data", "WorldGenSettings", "dimensions")
    have = sorted(N.safe_text(key) for key in stems[1]) if stems else []
    checks.append((set(have) >= set(KEPT_DIMENSIONS) and len(have) >= 3,
                   f"level.dat: {len(have)} стемов измерений ({', '.join(have[:6])}…)"))

    old_dimension_dirs = [entry for entry in (world / "dimensions").iterdir()
                          if entry.is_dir()] if (world / "dimensions").is_dir() else []
    stale = [entry.name for entry in old_dimension_dirs if entry.name not in migration.present]
    checks.append((not stale, f"dimensions/: нет каталогов удалённых модов ({stale or 'ok'})"))

    quests = world / "ftbquests"
    current = sorted(p.name for p in quests.iterdir()) if quests.is_dir() else []
    checks.append((not set(current) & set(expected.get("ftbQuestFiles", [])),
                   f"ftbquests/: старые файлы прогресса отсутствуют ({len(current)} новых)"))

    teams = world / "ftbteams"
    same = all(teams.joinpath(rel).is_file() and sha256_file(teams / rel) == digest
               for rel, digest in (expected.get("ftbTeams") or {}).items())
    checks.append((same, "ftbteams/: файлы команд не изменились"))

    resurrected = [path for path in expected.get("orphansGone", [])
                   if (world / path).exists()]
    checks.append((not resurrected,
                   f"осиротевшие файлы удалённых модов не вернулись ({resurrected or 'ok'})"))

    disk = world / "data" / "disk_manager.dat"
    counts: list[int] = []
    if disk.is_file():
        _n, disk_root, _p = N.read_nbt(disk)
        for _path, node in N.walk(disk_root):
            if N.is_compound(node) and "item_count" in node[1] and "keys" in node[1]:
                counts.append(int(node[1]["item_count"][1]))
    checks.append((counts == (expected.get("diskItemCount") or []),
                   f"МЭ-диск item_count {counts} == ожидание {expected.get('diskItemCount')}"))

    fresh = Migration(migration.args)
    fresh.apply = False  # verify never writes, even when --apply is also given
    fresh.report_dir = migration.report_dir
    fresh.present = migration.present
    fresh.remapper = migration.remapper
    fresh.player_names = migration.player_names
    fresh.run()
    dead = sum(sum(counter.values()) for counter in fresh.per_source.values())
    checks.append((dead == 0, f"повторный dry-run: мёртвых предметов {dead}"))
    checks.append((not fresh.components_stripped,
                   f"повторный dry-run: чужих компонентов {len(fresh.components_stripped)}"))

    print()
    for ok, text in checks:
        print(("PASS " if ok else "FAIL ") + text)
    return EXIT_OK if all(ok for ok, _ in checks) else EXIT_VERIFY


# ------------------------------------------------------------------ CLI

def parse_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--world", required=True, type=Path)
    parser.add_argument("--pack", required=True, type=Path,
                        help="LL8 checkout or instance directory (needs mods/)")
    parser.add_argument("--old-pack", type=Path, default=DEFAULT_OLD_PACK,
                        help="pack the world was played on; source of the item tags")
    parser.add_argument("--fresh-level", type=Path,
                        help="level.dat of a freshly created LL8 world (dimension stems + DataPacks)")
    parser.add_argument("--apply", action="store_true", help="actually modify the world")
    parser.add_argument("--report-dir", type=Path)
    parser.add_argument("--backup-root", type=Path, default=DEFAULT_BACKUP_ROOT)
    parser.add_argument("--no-backup", action="store_true")
    parser.add_argument("--remap", default="auto", help="auto | off | <path to a json map>")
    parser.add_argument("--keep-namespace", action="append", default=[],
                        help="treat this namespace as present (repeatable)")
    parser.add_argument("--extra-present", action="append", default=[],
                        help="extra namespace for the present set (repeatable)")
    parser.add_argument("--keep-attachments", action="store_true",
                        help="do not prune neoforge:attachments of absent mods")
    parser.add_argument("--verify", action="store_true",
                        help="check the world against migration-report.json")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    arguments = parse_arguments(argv)
    migration = Migration(arguments)

    if arguments.apply and not arguments.no_backup:
        migration.planned_backup = (arguments.backup_root
                                    / f"{migration.world.name}-pre-ll8-{stamp()}")
    if arguments.report_dir:
        migration.report_dir = Path(os.path.abspath(arguments.report_dir))
    elif migration.planned_backup is not None:
        migration.report_dir = migration.planned_backup
    else:
        migration.report_dir = Path(tempfile.gettempdir()) / "ll8-migrate"

    migration.prepare()
    if arguments.verify:
        return verify(migration)

    migration.run()
    migration.report_dir.mkdir(parents=True, exist_ok=True)
    text, document = render_report(migration)
    (migration.report_dir / "migration-report.md").write_text(text, encoding="utf-8")
    (migration.report_dir / "migration-report.json").write_text(
        json.dumps(document, indent=1, ensure_ascii=False), encoding="utf-8")

    dead = sum(sum(counter.values()) for counter in migration.per_source.values())
    moved = sum(sum(counter.values()) for counter in migration.remapped.values())
    print()
    print(f"{'applied' if migration.apply else 'dry run'}: {dead} item(s) removed, "
          f"{moved} remapped, {len(migration.components_stripped)} component(s) stripped, "
          f"{len(migration.deleted)} path(s) deleted, {len(migration.written)} file(s) rewritten")
    print(f"report: {migration.report_dir / 'migration-report.md'}")
    if not migration.apply:
        print("nothing was modified (dry run) - add --apply to perform the migration")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
