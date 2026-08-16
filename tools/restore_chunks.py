"""Put chunks back from a backup, renaming block ids on the way.

A mod that builds a block per wood type loses those blocks when the wood's
mod leaves the pack: the variant is never registered, so the game drops it
and the build is gone. The same mod usually has the same block for a wood
this pack does have. Restoring the chunk from before the load and renaming
the id inside it gives the build back, in a form the pack can keep.

    python tools/restore_chunks.py --world <world> --from <backup world>
        --chunks -125,-7 -124,-7 --rename old:id=new:id [--apply]
"""
import argparse
import json
import os
import pathlib
import re
import struct
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nbtlite as N  # noqa: E402
import trim_chunks as T  # noqa: E402


# nbtlite tags its nodes with short text codes, not the on-disk numbers.
STRING = "str"


def rename_strings(root, renames, counter):
    """Rewrites every string equal to a key of ``renames``, in place.

    Block ids live in two places in a chunk: the palette entry that names the
    block and the block entity that carries its contents. Both are plain
    strings, so renaming every matching string covers them together.
    """
    for _, node in N.walk(root):
        if N.is_compound(node):
            for key, child in list(node[1].items()):
                child = N.as_node(child)
                if isinstance(child, tuple) and child and child[0] == STRING:
                    text = N.safe_text(child[1])
                    if text in renames:
                        node[1][key] = (STRING, renames[text])
                        counter[renames[text]] = counter.get(renames[text], 0) + 1
        elif N.is_list(node) and len(node) > 2 and node[1] == STRING:
            for index, child in enumerate(node[2]):
                text = N.safe_text(N.as_node(child)[1])
                if text in renames:
                    node[2][index] = (STRING, renames[text])
                    counter[renames[text]] = counter.get(renames[text], 0) + 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--world", type=pathlib.Path, required=True)
    parser.add_argument("--from", dest="source", type=pathlib.Path, required=True)
    parser.add_argument("--chunks", nargs="+", default=[], help="x,z pairs")
    parser.add_argument("--chunks-file", type=pathlib.Path,
                        help="JSON array of [x, z] pairs; argparse cannot take "
                             "negative coordinates as bare arguments")
    parser.add_argument("--rename", action="append", default=[], help="old:id=new:id")
    parser.add_argument("--directories", nargs="+", default=["region", "entities", "poi"])
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    wanted = {tuple(int(part) for part in text.split(",")) for text in args.chunks}
    if args.chunks_file:
        wanted |= {tuple(pair) for pair in json.loads(args.chunks_file.read_text(encoding="utf-8"))}
    if not wanted:
        parser.error("give --chunks or --chunks-file")
    renames = dict(entry.split("=", 1) for entry in args.rename)
    print(f"chunks: {sorted(wanted)}")
    for old, new in renames.items():
        print(f"rename: {old} -> {new}")

    counter = {}
    for directory in args.directories:
        source_root = args.source / directory
        target_root = args.world / directory
        if not source_root.is_dir() or not target_root.is_dir():
            continue
        by_region = {}
        for chunk in wanted:
            by_region.setdefault((chunk[0] >> 5, chunk[1] >> 5), []).append(chunk)
        for (region_x, region_z), chunks in sorted(by_region.items()):
            name = f"r.{region_x}.{region_z}.mca"
            source = source_root / name
            target = target_root / name
            if not source.is_file() or not target.is_file():
                continue
            backup_chunks, _ = T.region_chunks(source)
            live_chunks, _ = T.region_chunks(target)
            restored = 0
            for chunk in chunks:
                if chunk not in backup_chunks:
                    continue
                payload, timestamp, index = backup_chunks[chunk]
                length, scheme = struct.unpack(">IB", payload[:5])
                if scheme != 2:
                    print(f"  {chunk}: unexpected compression {scheme}, skipped")
                    continue
                body = zlib.decompress(payload[5:4 + length])
                if renames:
                    root_name, root = N.decode(body)
                    rename_strings(root, renames, counter)
                    body = N.encode(root_name, root)
                packed = zlib.compress(body, 6)
                framed = struct.pack(">IB", len(packed) + 1, 2) + packed
                live_chunks[chunk] = (framed, timestamp, index)
                restored += 1
            if restored and args.apply:
                T.rewrite(target, live_chunks)
            print(f"  {directory}/{name}: {restored} chunk(s) "
                  f"{'restored' if args.apply else 'would be restored'}")

    if counter:
        print("\nrenamed ids:")
        for name, count in sorted(counter.items(), key=lambda item: -item[1]):
            print(f"  {name}: {count}")
    if not args.apply:
        print("\nnothing was modified - add --apply to restore")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
