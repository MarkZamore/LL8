"""Drop Lootr chest records that no longer describe anything.

Lootr keeps one small file per loot chest it has ever seen, under
data/lootr/<hex>/<hex>/<uuid>.dat, and each file names the chest's dimension
and position. Once chunks are trimmed and dimensions reset, most of those
files describe chests that no longer exist - and forty thousand tiny files
are what makes copying a world take minutes when it holds three hundred
megabytes. Records whose chunk still exists are kept, opened or not.

    python tools/prune_lootr.py --world <world> --keep keep.json          # preview
    python tools/prune_lootr.py --world <world> --keep keep.json --apply
"""
import argparse
import collections
import json
import os
import pathlib
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nbtlite as N  # noqa: E402

OVERWORLD = "minecraft:overworld"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--world", type=pathlib.Path, required=True)
    parser.add_argument("--keep", type=pathlib.Path, required=True,
                        help="JSON array of kept [chunk x, chunk z] pairs")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    keep = {tuple(pair) for pair in json.loads(args.keep.read_text(encoding="utf-8"))}
    root = args.world / "data" / "lootr"
    if not root.is_dir():
        print("no data/lootr in this world")
        return 0

    verdicts = collections.Counter()
    doomed = []
    for path in root.rglob("*.dat"):
        if path.name.startswith("Lootr-"):
            continue  # the mod's own bookkeeping, not a chest
        try:
            _, node, _ = N.read_nbt(path)
            data = N.nbt_to_py(node).get("data", {})
        except Exception:
            verdicts["unreadable, kept"] += 1
            continue
        position = data.get("position") or [0, 0, 0]
        dimension = str(data.get("dimension", ""))
        chunk = (int(position[0]) >> 4, int(position[2]) >> 4)
        if dimension != OVERWORLD:
            verdicts["dimension reset"] += 1
            doomed.append(path)
        elif chunk not in keep:
            verdicts["chunk trimmed"] += 1
            doomed.append(path)
        else:
            verdicts["kept"] += 1

    for reason, count in verdicts.most_common():
        print(f"  {reason}: {count}")
    freed = sum(p.stat().st_size for p in doomed)
    print(f"{'removing' if args.apply else 'would remove'} {len(doomed)} record(s), "
          f"{freed / 1024:.0f} KiB on disk")

    if not args.apply:
        print("nothing was modified - add --apply to prune")
        return 0

    for path in doomed:
        path.unlink()
    # Directories left with nothing in them would still be walked and copied.
    removed_dirs = 0
    for directory in sorted((d for d in root.rglob("*") if d.is_dir()), key=lambda d: -len(d.parts)):
        try:
            directory.rmdir()
            removed_dirs += 1
        except OSError:
            pass
    print(f"removed {len(doomed)} file(s) and {removed_dirs} empty director(ies)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
