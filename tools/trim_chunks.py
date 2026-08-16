"""Keep a chosen set of chunks and let the game generate the rest again.

A region file holds up to 1024 chunks behind an 8 KiB header of offsets. Take
a chunk's entry out of that header and the chunk is simply not there any more:
the next time a player walks in, the game generates it from the world seed with
whatever mods are installed now. That is the point - terrain made by mods this
pack no longer has is replaced by terrain this pack does make.

The keep list is a JSON array of [chunk x, chunk z]. Everything outside it goes,
in region/, entities/ and poi/ alike: leaving an entity or a village record
behind for a chunk that no longer exists would resurrect half of it.

    python tools/trim_chunks.py --world <world> --keep keep.json          # preview
    python tools/trim_chunks.py --world <world> --keep keep.json --apply
"""
import argparse
import json
import os
import pathlib
import re
import shutil
import struct
import sys
import time

REGION_NAME = re.compile(r"r\.(-?\d+)\.(-?\d+)\.mca")
CHUNK_DIRECTORIES = ("region", "entities", "poi")
SECTOR = 4096


def region_chunks(path):
    """-> {(chunk x, chunk z): (payload bytes, timestamp)} for one region file."""
    raw = path.read_bytes()
    if len(raw) < 2 * SECTOR:
        return {}, raw
    match = REGION_NAME.fullmatch(path.name)
    if not match:
        return {}, raw
    region_x, region_z = int(match.group(1)), int(match.group(2))
    found = {}
    for index in range(1024):
        head = raw[index * 4:index * 4 + 4]
        offset = int.from_bytes(head[:3], "big")
        sectors = head[3]
        if not offset or not sectors:
            continue
        start = offset * SECTOR
        end = min(start + sectors * SECTOR, len(raw))
        if start >= len(raw):
            continue
        timestamp = raw[SECTOR + index * 4:SECTOR + index * 4 + 4]
        chunk = (region_x * 32 + index % 32, region_z * 32 + index // 32)
        found[chunk] = (raw[start:end], timestamp, index)
    return found, raw


def rewrite(path, kept):
    """Writes a region file containing only the kept chunks, compacted."""
    locations = bytearray(SECTOR)
    timestamps = bytearray(SECTOR)
    body = bytearray()
    next_sector = 2
    for chunk, (payload, timestamp, index) in sorted(kept.items(), key=lambda item: item[1][2]):
        sectors = (len(payload) + SECTOR - 1) // SECTOR
        if sectors > 255:
            # An oversized chunk lives in a companion .mcc file; the payload
            # here is just a stub, so this cannot normally happen.
            raise ValueError(f"chunk {chunk} needs {sectors} sectors")
        locations[index * 4:index * 4 + 3] = next_sector.to_bytes(3, "big")
        locations[index * 4 + 3] = sectors
        timestamps[index * 4:index * 4 + 4] = timestamp
        body += payload + bytes(sectors * SECTOR - len(payload))
        next_sector += sectors
    temporary = path.with_suffix(path.suffix + ".trim")
    temporary.write_bytes(bytes(locations) + bytes(timestamps) + bytes(body))
    temporary.replace(path)


def human(size):
    for unit in ("B", "KiB", "MiB", "GiB"):
        if size < 1024 or unit == "GiB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--world", type=pathlib.Path, required=True)
    parser.add_argument("--keep", type=pathlib.Path, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup-root", type=pathlib.Path)
    args = parser.parse_args()

    world = pathlib.Path(os.path.abspath(args.world))
    keep = {tuple(entry) for entry in json.loads(args.keep.read_text(encoding="utf-8"))}
    print(f"world: {world}")
    print(f"keep list: {len(keep)} chunk(s)")

    lock = world / "session.lock"
    if lock.is_file() and args.apply:
        try:
            handle = os.open(lock, os.O_RDWR)
            try:
                if sys.platform == "win32":
                    import msvcrt
                    msvcrt.locking(handle, msvcrt.LK_NBLCK, 1)
                    msvcrt.locking(handle, msvcrt.LK_UNLCK, 1)
            finally:
                os.close(handle)
        except OSError:
            print("the world is open in Minecraft; close it first")
            return 2

    if args.apply and args.backup_root:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        destination = pathlib.Path(args.backup_root) / f"{world.name}-pre-trim-{stamp}"
        print(f"backup: {destination}")
        shutil.copytree(world, destination)

    total_kept = total_dropped = 0
    freed = 0
    for directory in CHUNK_DIRECTORIES:
        root = world / directory
        if not root.is_dir():
            continue
        files = sorted(root.glob("r.*.mca"))
        kept_here = dropped_here = 0
        removed_files = 0
        for path in files:
            chunks, raw = region_chunks(path)
            if not chunks:
                continue
            survivors = {chunk: value for chunk, value in chunks.items() if chunk in keep}
            kept_here += len(survivors)
            dropped_here += len(chunks) - len(survivors)
            if len(survivors) == len(chunks):
                continue
            before = path.stat().st_size
            if args.apply:
                if survivors:
                    rewrite(path, survivors)
                else:
                    path.unlink()
                    removed_files += 1
                freed += before - (path.stat().st_size if path.exists() else 0)
            else:
                # Without --apply nothing is written; the saving is what the
                # kept sectors would take instead of the whole file.
                freed += before - sum(len(v[0]) for v in survivors.values())
                if not survivors:
                    removed_files += 1
        print(f"  {directory}: keep {kept_here}, drop {dropped_here}, "
              f"{removed_files} file(s) empty" + ("" if args.apply else " (preview)"))
        total_kept += kept_here
        total_dropped += dropped_here

    print(f"\n{'trimmed' if args.apply else 'would trim'}: "
          f"{total_dropped} chunk record(s) dropped, {total_kept} kept, about {human(freed)} freed")
    if not args.apply:
        print("nothing was modified - add --apply to perform the trim")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
