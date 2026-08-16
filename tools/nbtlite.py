#!/usr/bin/env python3
"""Exact, dependency-free NBT codec shared by the LL8 tools.

Why this exists: the world migration rewrites live save files, so a reader that
"mostly" works is not good enough - every byte we do not understand must survive
a read -> write round trip untouched.  The reader/writer started as the one
inside Infinity's ``tools/migrate_relics_playerdata.py`` and was hardened here:

* **MUTF-8** (Java modified UTF-8) instead of ``utf-8``/``replace``: NUL is
  stored as ``C0 80`` and astral characters as CESU-8 surrogate pairs.  The old
  decoder replaced both with U+FFFD, which silently corrupted such strings on
  write.  Strings whose bytes do not re-encode identically keep their original
  bytes (see :class:`NbtString`).
* **Floats keep their exact bits**: a NaN payload (or any value CPython would
  re-normalise) is stored together with its raw bytes.
* **Empty TAG_List element types are preserved** verbatim - vanilla writes
  ``TAG_End`` for empty lists but some mods write the real element type, and
  flipping that byte is a needless diff.
* Compound key order is preserved (``dict`` insertion order).

Value representation (small tuples, no classes, so a whole save is cheap):

    ("b", int) ("s", int) ("i", int) ("l", int)
    ("f", float[, raw4]) ("d", float[, raw8])
    ("ba", bytes) ("str", str)
    ("list", element_tag, [payload, ...])
    ("comp", {name: payload, ...})
    ("ia", [int, ...]) ("la", [int, ...])

Containers (``dict`` / ``list``) are mutable in place, which is exactly what the
migration needs.
"""

from __future__ import annotations

import gzip
import struct
import zlib
from pathlib import Path
from typing import Any, Iterator, NamedTuple

__all__ = [
    "TAG_OF", "NbtError", "NbtString",
    "read_nbt", "write_nbt", "decode", "encode", "roundtrip_ok",
    "walk", "nbt_to_py", "namespace", "safe_text",
    "iter_item_stacks", "iter_ae2_keys", "Stack", "AE2Key", "stack_fields",
    "as_node", "get_path", "is_compound", "is_list",
]

TAG_END, TAG_BYTE, TAG_SHORT, TAG_INT, TAG_LONG, TAG_FLOAT, TAG_DOUBLE = range(7)
TAG_BYTE_ARRAY, TAG_STRING, TAG_LIST, TAG_COMPOUND, TAG_INT_ARRAY, TAG_LONG_ARRAY = range(7, 13)

TAG_OF = {"b": TAG_BYTE, "s": TAG_SHORT, "i": TAG_INT, "l": TAG_LONG,
          "f": TAG_FLOAT, "d": TAG_DOUBLE, "ba": TAG_BYTE_ARRAY, "str": TAG_STRING,
          "list": TAG_LIST, "comp": TAG_COMPOUND, "ia": TAG_INT_ARRAY, "la": TAG_LONG_ARRAY}
NUMERIC_KINDS = frozenset({"b", "s", "i", "l", "f", "d"})


class NbtError(ValueError):
    """Malformed NBT (truncated stream, unknown tag id, oversized string)."""


class NbtString(str):
    """A string whose original bytes are kept because they do not re-encode.

    Behaves like ``str`` everywhere (dict keys, comparisons, formatting); the
    writer just prefers ``.raw`` when present so odd encodings survive.
    """

    __slots__ = ("raw",)

    def __new__(cls, value: str, raw: bytes) -> "NbtString":
        obj = super().__new__(cls, value)
        obj.raw = raw
        return obj


# ------------------------------------------------------------------ MUTF-8

def _decode_mutf8(raw: bytes) -> str:
    """Java modified UTF-8 -> ``str`` (may contain lone surrogates)."""
    # C0 80 is an overlong NUL; C0 never appears in well-formed UTF-8, so a
    # blind replace cannot damage a neighbouring sequence.
    if b"\xc0\x80" in raw:
        raw = raw.replace(b"\xc0\x80", b"\x00")
    # 'surrogatepass' keeps CESU-8 halves as lone surrogates instead of U+FFFD.
    return raw.decode("utf-8", "surrogatepass")


def _encode_mutf8(text: str) -> bytes:
    raw = text.encode("utf-8", "surrogatepass")
    if b"\x00" in raw:
        raw = raw.replace(b"\x00", b"\xc0\x80")
    return raw


def safe_text(value: Any) -> str:
    """Printable form of an NBT string (lone surrogates -> U+FFFD)."""
    text = str(value)
    return text.encode("utf-8", "replace").decode("utf-8", "replace")


# ------------------------------------------------------------------ reader

class Reader:
    """Big-endian NBT payload reader over a ``bytes`` buffer."""

    def __init__(self, data: bytes) -> None:
        self.d = data
        self.p = 0

    def u8(self) -> int:
        try:
            value = self.d[self.p]
        except IndexError as error:
            raise NbtError("truncated NBT stream") from error
        self.p += 1
        return value

    def read(self, fmt: str):
        try:
            value = struct.unpack_from(fmt, self.d, self.p)[0]
        except struct.error as error:
            raise NbtError(f"truncated NBT stream at {self.p}") from error
        self.p += struct.calcsize(fmt)
        return value

    def raw(self, count: int) -> bytes:
        if count < 0 or self.p + count > len(self.d):
            raise NbtError(f"bad NBT length {count} at {self.p}")
        chunk = self.d[self.p:self.p + count]
        self.p += count
        return bytes(chunk)

    def string(self) -> str:
        raw = self.raw(self.read(">H"))
        try:
            text = _decode_mutf8(raw)
        except UnicodeDecodeError:
            # Not even MUTF-8: keep the bytes so the file still round-trips.
            return NbtString(raw.decode("latin-1"), raw)
        return text if _encode_mutf8(text) == raw else NbtString(text, raw)

    def payload(self, tag: int):
        if tag == TAG_BYTE:
            return ("b", self.read(">b"))
        if tag == TAG_SHORT:
            return ("s", self.read(">h"))
        if tag == TAG_INT:
            return ("i", self.read(">i"))
        if tag == TAG_LONG:
            return ("l", self.read(">q"))
        if tag == TAG_FLOAT:
            raw = self.raw(4)
            value = struct.unpack(">f", raw)[0]
            # NaN payloads (and only those, in practice) survive only as bytes.
            return ("f", value) if struct.pack(">f", value) == raw else ("f", value, raw)
        if tag == TAG_DOUBLE:
            raw = self.raw(8)
            value = struct.unpack(">d", raw)[0]
            return ("d", value) if struct.pack(">d", value) == raw else ("d", value, raw)
        if tag == TAG_BYTE_ARRAY:
            return ("ba", self.raw(self.read(">i")))
        if tag == TAG_STRING:
            return ("str", self.string())
        if tag == TAG_LIST:
            element = self.u8()
            count = self.read(">i")
            if count < 0:
                count = 0  # vanilla treats a negative length as empty
            if element == TAG_END and count:
                raise NbtError("TAG_List of TAG_End with elements")
            return ("list", element, [self.payload(element) for _ in range(count)])
        if tag == TAG_COMPOUND:
            out: dict[str, Any] = {}
            while True:
                child = self.u8()
                if child == TAG_END:
                    return ("comp", out)
                name = self.string()
                out[name] = self.payload(child)
        if tag == TAG_INT_ARRAY:
            count = self.read(">i")
            return ("ia", list(struct.unpack(">%di" % count, self.raw(4 * count))))
        if tag == TAG_LONG_ARRAY:
            count = self.read(">i")
            return ("la", list(struct.unpack(">%dq" % count, self.raw(8 * count))))
        raise NbtError(f"unknown NBT tag {tag} at {self.p}")


# ------------------------------------------------------------------ writer

class Writer:
    """Serialiser mirroring :class:`Reader` byte for byte."""

    def __init__(self) -> None:
        self.parts: list[bytes] = []

    def value(self) -> bytes:
        return b"".join(self.parts)

    def w(self, fmt: str, *values) -> None:
        self.parts.append(struct.pack(fmt, *values))

    def string(self, text: str) -> None:
        raw = getattr(text, "raw", None)
        if raw is None:
            raw = _encode_mutf8(text)
        if len(raw) > 0xFFFF:
            raise NbtError(f"NBT string too long ({len(raw)} bytes)")
        self.w(">H", len(raw))
        self.parts.append(raw)

    def payload(self, node) -> None:
        kind = node[0]
        if kind == "b":
            self.w(">b", node[1])
        elif kind == "s":
            self.w(">h", node[1])
        elif kind == "i":
            self.w(">i", node[1])
        elif kind == "l":
            self.w(">q", node[1])
        elif kind == "f":
            self.parts.append(node[2] if len(node) > 2 else struct.pack(">f", node[1]))
        elif kind == "d":
            self.parts.append(node[2] if len(node) > 2 else struct.pack(">d", node[1]))
        elif kind == "ba":
            self.w(">i", len(node[1]))
            self.parts.append(bytes(node[1]))
        elif kind == "str":
            self.string(node[1])
        elif kind == "list":
            element, items = node[1], node[2]
            if items and element == TAG_END:
                raise NbtError("TAG_List of TAG_End with elements")
            self.parts.append(bytes([element]))
            self.w(">i", len(items))
            for item in items:
                self.payload(item)
        elif kind == "comp":
            for name, child in node[1].items():
                self.parts.append(bytes([TAG_OF[child[0]]]))
                self.string(name)
                self.payload(child)
            self.parts.append(b"\x00")
        elif kind == "ia":
            self.w(">i", len(node[1]))
            self.w(">%di" % len(node[1]), *node[1])
        elif kind == "la":
            self.w(">i", len(node[1]))
            self.w(">%dq" % len(node[1]), *node[1])
        else:
            raise NbtError(f"unknown NBT kind {kind!r}")


# ------------------------------------------------------------------ files

def decode(data: bytes) -> tuple[str, tuple]:
    """Uncompressed NBT bytes -> ``(root_name, root_compound)``."""
    reader = Reader(data)
    tag = reader.u8()
    if tag != TAG_COMPOUND:
        raise NbtError(f"root tag is {tag}, not TAG_Compound")
    name = reader.string()
    root = reader.payload(TAG_COMPOUND)
    if reader.p != len(data):
        raise NbtError(f"{len(data) - reader.p} trailing byte(s) after the root tag")
    return name, root


def encode(root_name: str, root: tuple) -> bytes:
    """``(root_name, root_compound)`` -> uncompressed NBT bytes."""
    writer = Writer()
    writer.parts.append(bytes([TAG_COMPOUND]))
    writer.string(root_name)
    writer.payload(root)
    return writer.value()


def _decompress(raw: bytes):
    """-> (plain bytes, compression flag) where the flag feeds write_nbt."""
    if raw[:2] == b"\x1f\x8b":
        return gzip.decompress(raw), True
    if raw[:1] == b"\x78":  # zlib (NbtIo "compressed" variant used by a few mods)
        return zlib.decompress(raw), "zlib"
    return raw, False


def read_nbt(path) -> tuple[str, tuple, Any]:
    """Read a (possibly gzipped) NBT file -> ``(root_name, root, gzipped)``.

    ``gzipped`` is ``True``/``False``/``"zlib"``; pass it straight back to
    :func:`write_nbt` to keep the container format.
    """
    plain, packed = _decompress(Path(path).read_bytes())
    name, root = decode(plain)
    return name, root, packed


def write_nbt(path, root_name: str, root: tuple, gzipped: Any = True) -> None:
    """Write an NBT file, verifying it decodes back to the same bytes."""
    body = encode(root_name, root)
    # A save file we cannot re-read is worse than no edit at all, so prove the
    # payload before it reaches the disk.
    if encode(*decode(body)) != body:
        raise NbtError("re-encoded NBT does not match; refusing to write")
    if gzipped == "zlib":
        blob = zlib.compress(body, 6)
    elif gzipped:
        # mtime=0 keeps repeated runs byte-stable (gzip stores the clock).
        blob = gzip.compress(body, 6, mtime=0)
    else:
        blob = body
    target = Path(path)
    temporary = target.with_name(target.name + ".ll8tmp")
    temporary.write_bytes(blob)
    temporary.replace(target)


def roundtrip_ok(path) -> bool:
    """True when the file decodes and re-encodes to identical NBT bytes.

    Only the *decompressed* payload is compared: gzip framing depends on the
    deflate implementation, and Minecraft rewrites the container anyway.
    """
    try:
        plain, _ = _decompress(Path(path).read_bytes())
        name, root = decode(plain)
        return encode(name, root) == plain
    except (OSError, NbtError, zlib.error, EOFError, struct.error):
        return False


# ------------------------------------------------------------------ walking

def as_node(value):
    """Accept either a payload node or a :func:`read_nbt` triple."""
    if (isinstance(value, tuple) and len(value) == 3 and isinstance(value[2], bool)
            and isinstance(value[1], tuple) and value[1] and value[1][0] == "comp"):
        return value[1]  # (root_name, root, gzipped)
    return value


def is_compound(node) -> bool:
    return isinstance(node, tuple) and bool(node) and node[0] == "comp"


def is_list(node) -> bool:
    return isinstance(node, tuple) and bool(node) and node[0] == "list"


def _join(path: str, key: str) -> str:
    return key if not path else f"{path}.{key}"


def walk(node, path: str = "") -> Iterator[tuple[str, tuple]]:
    """Yield ``(path, node)`` for the node and every descendant, depth first."""
    node = as_node(node)
    yield path, node
    if is_compound(node):
        for name, child in list(node[1].items()):
            yield from walk(child, _join(path, safe_text(name)))
    elif is_list(node):
        for index, child in enumerate(node[2]):
            yield from walk(child, f"{path}[{index}]")


def get_path(node, *keys):
    """``get_path(root, "Data", "Player")`` -> node or ``None``."""
    node = as_node(node)
    for key in keys:
        if isinstance(key, int):
            if not is_list(node) or key >= len(node[2]):
                return None
            node = node[2][key]
        else:
            if not is_compound(node):
                return None
            node = node[1].get(key)
            if node is None:
                return None
    return node


def nbt_to_py(node):
    """Plain Python mirror of a node (for JSON reports and debugging)."""
    node = as_node(node)
    kind = node[0]
    if kind == "comp":
        return {safe_text(name): nbt_to_py(child) for name, child in node[1].items()}
    if kind == "list":
        return [nbt_to_py(child) for child in node[2]]
    if kind == "str":
        return safe_text(node[1])
    if kind in ("ba", "ia", "la"):
        return list(node[1])
    return node[1]


def namespace(item_id: str) -> str:
    """``"alltheores:tin_ingot"`` -> ``"alltheores"``; bare ids are vanilla."""
    text = str(item_id)
    return text.split(":", 1)[0] if ":" in text else "minecraft"


# ------------------------------------------------------------------ stacks

class Stack(NamedTuple):
    """One item stack found in a save file.

    The first two fields are ``id`` and ``count`` so callers can treat the tuple
    as a simple pair; the rest is the context needed to delete or rewrite it.
    """

    id: str
    count: int
    path: str          # e.g. Data.Player.Inventory[3].components."minecraft:bundle_contents"[0]
    node: tuple        # the ("comp", {...}) node of the stack itself
    parent: Any        # container holding it: dict payload, list payload, or None for the root
    key: Any           # dict key or list index inside `parent`
    count_key: str     # "count" (1.21) or "Count" (legacy)


class AE2Key(NamedTuple):
    """One AE2 storage key with its parallel amount."""

    id: str
    amount: int
    path: str
    node: tuple        # the key compound
    parent: list       # the payload list of "keys"
    key: int           # index into `parent` and into `amts`
    amts: list         # the payload list of "amts"


def stack_fields(node):
    """-> (id, count, count_key) when the compound looks like an ItemStack."""
    if not is_compound(node):
        return None
    fields = node[1]
    ident = fields.get("id")
    if ident is None or ident[0] != "str" or ":" not in str(ident[1]):
        return None
    for count_key in ("count", "Count"):
        count = fields.get(count_key)
        if count is not None and count[0] in NUMERIC_KINDS:
            try:
                return str(ident[1]), int(count[1]), count_key
            except (TypeError, ValueError):
                return str(ident[1]), 1, count_key
    return None


def iter_item_stacks(root) -> Iterator[Stack]:
    """Yield every item stack in the tree, including nested ones.

    Nested stacks (bundle contents, charged projectiles, ``minecraft:container``
    slots, backpack inventories) fall out for free because the whole tree is
    walked - ``components`` is not special-cased.
    """
    def visit(node, path: str, parent, key) -> Iterator[Stack]:
        node = as_node(node)
        if is_compound(node):
            found = stack_fields(node)
            if found is not None:
                yield Stack(found[0], found[1], path, node, parent, key, found[2])
            for name, child in list(node[1].items()):
                yield from visit(child, _join(path, safe_text(name)), node[1], name)
        elif is_list(node):
            for index, child in enumerate(list(node[2])):
                yield from visit(child, f"{path}[{index}]", node[2], index)

    yield from visit(root, "", None, None)


def iter_ae2_keys(root) -> Iterator[AE2Key]:
    """Yield AE2 storage-cell keys (``...diskdata.keys[]`` + ``amts[]``).

    AE2 Things' ``disk_manager.dat`` stores cell contents as two parallel
    arrays; any compound carrying both is treated as such a pair, so the layout
    around it (``data.disklist[].diskdata``) may change without breaking this.
    """
    for path, node in walk(root):
        if not is_compound(node):
            continue
        keys, amts = node[1].get("keys"), node[1].get("amts")
        if not is_list(keys) or amts is None or amts[0] != "la":
            continue
        for index, key in enumerate(keys[2]):
            if not is_compound(key):
                continue
            ident = key[1].get("id")
            if ident is None or ident[0] != "str":
                continue
            amount = amts[1][index] if index < len(amts[1]) else 0
            yield AE2Key(str(ident[1]), int(amount), f"{path}.keys[{index}]",
                         key, keys[2], index, amts[1])


def main() -> int:
    """``python nbtlite.py <file>...`` - round-trip check / dump helper."""
    import argparse
    import json

    parser = argparse.ArgumentParser(description="NBT round-trip check / dump")
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--dump", action="store_true", help="print the tree as JSON")
    arguments = parser.parse_args()
    failures = 0
    for path in arguments.files:
        ok = roundtrip_ok(path)
        failures += 0 if ok else 1
        print(f"{'ok  ' if ok else 'FAIL'} {path}")
        if arguments.dump:
            name, root, packed = read_nbt(path)
            print(json.dumps({"rootName": safe_text(name), "gzipped": packed,
                              "root": nbt_to_py(root)}, indent=2, ensure_ascii=False)[:20000])
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
