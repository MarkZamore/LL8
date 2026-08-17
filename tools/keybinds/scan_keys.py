#!/usr/bin/env python3
"""Takes stock of every keybinding the pack registers, and how each one conflicts.

Reads a live instance's options.txt for the list of key mappings (every mod's
mappings are written there, bound or not), the pack's configureddefaults for
upstream defaults, and every jar in mods/ for three things the options file
cannot say:

  * the English name of each mapping (assets/<mod>/lang/en_us.json),
  * its NeoForge conflict context, read from the bytecode: the class that
    registers "key.foo" also references KeyConflictContext.GUI or .IN_GAME
    near it, or it does not - in which case the mapping is UNIVERSAL, which is
    what NeoForge assumes for a mapping built with the vanilla constructor, and
  * the mappings of mods installed after that options.txt was written: they are
    missing from it entirely, yet in game they arrive on their own default key,
    on top of whatever the layout put there. Every KeyMapping the bytecode
    builds under a literal name is read out here, with its default key when that
    is literal too.

This last pass is a net, not a proof. A mod that glues its names together at
runtime ("key.mekanism." + mode) or registers through a shared library hands
the bytecode no name to read, and stays invisible until an instance has run
with it and written its options.txt. So a fresh snapshot is still the ground
truth; the jars only make sure a mod added since cannot land on the layout
unannounced.

The context decides which mappings may share a physical key, so the layout in
../../launcher/controls-preset.txt is designed and checked against this stock.

Writes registered-keys.tsv and contexts.json beside this script.

    python tools/keybinds/scan_keys.py --options <path to options.txt>
"""
from __future__ import annotations

import argparse
import json
import re
import struct
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
MODS = REPO / "mods"
DEFAULTS = REPO / "configureddefaults" / "options.txt"

CONTEXT_CLASS = "net/neoforged/neoforge/client/settings/KeyConflictContext"
KEYMAPPING_CLASS = "net/minecraft/client/KeyMapping"
INPUT_TYPE_CLASS = "com/mojang/blaze3d/platform/InputConstants$Type"
# A mod may not call the vanilla constructor at all: Cobblemon builds its keys
# through CobblemonKeyBinding, which passes the name up to KeyMapping itself.
# A class whose name ends this way is a key binding whoever wrote it.
KEYBIND_CLASSES = ("KeyMapping", "KeyBinding", "Keybinding", "KeyBind")
KEY_LINE = re.compile(r"^key_(?P<name>[^:]+):(?P<value>.+)$")

UNBOUND_KEY = "key.keyboard.unknown"

# The default key a mod passes to KeyMapping is a GLFW code; options.txt writes
# a name. Letters, digits, function and keypad keys follow a formula; the rest
# are listed. -1 (GLFW_KEY_UNKNOWN) means the mod ships the mapping unbound.
GLFW_NAMES = {
    32: "space", 39: "apostrophe", 44: "comma", 45: "minus", 46: "period", 47: "slash",
    59: "semicolon", 61: "equal", 91: "left.bracket", 92: "backslash", 93: "right.bracket",
    96: "grave.accent", 161: "world.1", 162: "world.2", 257: "enter", 258: "tab",
    259: "backspace", 260: "insert", 261: "delete", 262: "right", 263: "left", 264: "down",
    265: "up", 266: "page.up", 267: "page.down", 268: "home", 269: "end", 280: "caps.lock",
    281: "scroll.lock", 282: "num.lock", 283: "print.screen", 284: "pause",
    330: "keypad.decimal", 331: "keypad.divide", 332: "keypad.multiply", 333: "keypad.subtract",
    334: "keypad.add", 335: "keypad.enter", 336: "keypad.equal",
    340: "left.shift", 341: "left.control", 342: "left.alt", 343: "left.win",
    344: "right.shift", 345: "right.control", 346: "right.alt", 347: "right.win", 348: "menu",
}
GLFW_NAMES.update({code: chr(code) for code in range(48, 58)})            # 0-9
GLFW_NAMES.update({code: chr(code + 32) for code in range(65, 91)})       # A-Z
GLFW_NAMES.update({290 + n: f"f{n + 1}" for n in range(25)})              # F1-F25
GLFW_NAMES.update({320 + n: f"keypad.{n}" for n in range(10)})            # keypad 0-9


def key_name(code: int) -> str:
    """The options.txt name of a GLFW key code, or unbound if it is not one."""
    name = GLFW_NAMES.get(code)
    return f"key.keyboard.{name}" if name else UNBOUND_KEY


# Lang entries worth keeping while the list of mappings is still growing.
LANG_CANDIDATE = re.compile(r"^key[._]|^keybind|\.keybinding\.")

# A mapping name is dotted, lower case at the start of every part, made of word
# characters: key.walkers, equipmentcompare.key.showTooltips. That shape alone
# throws out the neighbours a constructor call drags in - class names
# (xaero.common.IXaeroMinimap), texture paths, and bare halves of a name the mod
# glues together at runtime (open_backpack; those mods are in the options
# snapshot anyway) - and NOT_A_NAME throws out the categories and translation
# keys that pass it.
# Calls that mean the string beside them is half of a name, not a name.
NAME_BUILDERS = {
    ("net/minecraft/Util", "makeDescriptionId"), ("java/lang/String", "format"),
    ("java/lang/String", "concat"), ("java/lang/StringBuilder", "append"),
    ("java/lang/StringBuilder", "toString"),
}
MAPPING_NAME = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][A-Za-z0-9_]*)+$")
# ... and a config file name can look just like a mapping name (lightoverlay.properties).
NOT_A_NAME = re.compile(r"category|categories|itemGroup|^mod\.|%|^key\.keyboard\.|^key\.mouse\.|\.(properties|json|toml|cfg|txt|png|ogg|xml|ya?ml)$")

# One entry per JVM opcode: how many operand bytes follow it. Variable-length
# opcodes (tableswitch, lookupswitch, wide) are handled in the scanner.
OPERANDS = [0] * 256
for op in (0x10, 0x12, 0x15, 0x16, 0x17, 0x18, 0x19, 0x36, 0x37, 0x38, 0x39, 0x3a, 0xa9, 0xbc):
    OPERANDS[op] = 1
for op in (0x11, 0x13, 0x14, 0x84, 0xb2, 0xb3, 0xb4, 0xb5, 0xb6, 0xb7, 0xb8, 0xbb, 0xbd, 0xc0, 0xc1,
           *range(0x99, 0xa9), 0xc6, 0xc7):
    OPERANDS[op] = 2
for op in (0xc5,):
    OPERANDS[op] = 3
for op in (0xb9, 0xba, 0xc8, 0xc9):
    OPERANDS[op] = 4
TABLESWITCH, LOOKUPSWITCH, WIDE = 0xaa, 0xab, 0xc4
LDC, LDC_W, GETSTATIC, INVOKESPECIAL, INVOKEVIRTUAL, INVOKESTATIC, INVOKEINTERFACE = (
    0x12, 0x13, 0xb2, 0xb7, 0xb6, 0xb8, 0xb9)
BIPUSH, SIPUSH, ICONST_M1, ICONST_0, ICONST_5 = 0x10, 0x11, 0x02, 0x03, 0x08


def read_options(path: Path) -> dict[str, str]:
    keys: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = KEY_LINE.match(raw.strip())
        if match:
            keys[match.group("name")] = match.group("value")
    return keys


class ClassFile:
    """Just enough of the class file format: the constant pool and method code."""

    def __init__(self, data: bytes):
        self.data = data
        self.pool: list = [None]
        offset = 8
        count = struct.unpack_from(">H", data, offset)[0]
        offset += 2
        index = 1
        while index < count:
            tag = data[offset]
            offset += 1
            if tag == 1:
                length = struct.unpack_from(">H", data, offset)[0]
                offset += 2
                self.pool.append(("utf8", data[offset:offset + length].decode("utf-8", "replace")))
                offset += length
            elif tag in (3, 4):
                self.pool.append(("num",))
                offset += 4
            elif tag in (5, 6):
                self.pool.append(("wide",))
                self.pool.append(None)
                offset += 8
                index += 1
            elif tag in (7, 8, 16, 19, 20):
                self.pool.append((tag, struct.unpack_from(">H", data, offset)[0]))
                offset += 2
            elif tag in (9, 10, 11, 12, 17, 18):
                self.pool.append((tag, *struct.unpack_from(">HH", data, offset)))
                offset += 4
            elif tag == 15:
                self.pool.append(("handle",))
                offset += 3
            else:
                raise ValueError(f"unknown constant tag {tag}")
            index += 1
        self.after_pool = offset

    def utf8(self, index: int) -> str | None:
        entry = self.pool[index] if 0 < index < len(self.pool) else None
        return entry[1] if entry and entry[0] == "utf8" else None

    def class_name(self, index: int) -> str | None:
        entry = self.pool[index] if 0 < index < len(self.pool) else None
        return self.utf8(entry[1]) if entry and entry[0] == 7 else None

    def string_at(self, index: int) -> str | None:
        entry = self.pool[index] if 0 < index < len(self.pool) else None
        return self.utf8(entry[1]) if entry and entry[0] == 8 else None

    def member(self, index: int) -> tuple[str, str] | None:
        """(owner class, member name) of a Fieldref/Methodref/InterfaceMethodref."""
        entry = self.pool[index] if 0 < index < len(self.pool) else None
        if not entry or entry[0] not in (9, 10, 11):
            return None
        owner = self.class_name(entry[1])
        name_and_type = self.pool[entry[2]]
        if not owner or not name_and_type or name_and_type[0] != 12:
            return None
        return owner, self.utf8(name_and_type[1]) or ""

    def strings(self) -> set[str]:
        return {entry[1] for entry in self.pool if entry and entry[0] == "utf8"}

    def methods_code(self):
        """Yields the bytecode of every method that has a Code attribute."""
        data = self.data
        offset = self.after_pool + 6  # access, this, super
        interfaces = struct.unpack_from(">H", data, offset)[0]
        offset += 2 + 2 * interfaces
        for _ in range(2):  # fields, then methods
            count = struct.unpack_from(">H", data, offset)[0]
            offset += 2
            is_methods = _ == 1
            for _member in range(count):
                offset += 6
                attributes = struct.unpack_from(">H", data, offset)[0]
                offset += 2
                for _attribute in range(attributes):
                    name_index, length = struct.unpack_from(">HI", data, offset)
                    body = offset + 6
                    if is_methods and self.utf8(name_index) == "Code":
                        code_length = struct.unpack_from(">I", data, body + 4)[0]
                        yield data[body + 8:body + 8 + code_length]
                    offset = body + length


def scan_code(code: bytes, cls: ClassFile, known: set[str]) -> list[tuple[str, str]]:
    """Pairs (key name, context) found in one method's bytecode.

    The context that follows a key string closest is the one that mapping was
    built with. A setKeyConflictContext call is attributed the same way.
    """
    pairs: list[tuple[str, str]] = []
    pc = 0
    last_key: str | None = None
    while pc < len(code):
        op = code[pc]
        if op in (LDC, LDC_W):
            index = code[pc + 1] if op == LDC else struct.unpack_from(">H", code, pc + 1)[0]
            text = cls.string_at(index)
            if text is not None:
                # options.txt writes the mapping's name; mods register with the
                # same string, so a match here is the registration.
                if text in known:
                    last_key = text
        elif op == GETSTATIC:
            member = cls.member(struct.unpack_from(">H", code, pc + 1)[0])
            if member and member[0] == CONTEXT_CLASS and member[1] in ("GUI", "IN_GAME", "UNIVERSAL"):
                if last_key is not None:
                    pairs.append((last_key, member[1]))
        elif op in (INVOKESPECIAL, INVOKEVIRTUAL, INVOKESTATIC, INVOKEINTERFACE):
            member = cls.member(struct.unpack_from(">H", code, pc + 1)[0])
            if member and member[0] == KEYMAPPING_CLASS and member[1] == "<init>":
                # A finished mapping; the next key string starts a new one.
                last_key = None

        if op == TABLESWITCH:
            aligned = (pc + 4) & ~3
            low, high = struct.unpack_from(">ii", code, aligned + 4)
            pc = aligned + 12 + 4 * (high - low + 1)
        elif op == LOOKUPSWITCH:
            aligned = (pc + 4) & ~3
            npairs = struct.unpack_from(">i", code, aligned + 4)[0]
            pc = aligned + 8 + 8 * npairs
        elif op == WIDE:
            pc += 6 if code[pc + 1] == 0x84 else 4
        else:
            pc += 1 + OPERANDS[op]
    return pairs


def discover_code(code: bytes, cls: ClassFile) -> list[tuple[str, str]]:
    """(mapping name, default key) for every KeyMapping this method builds.

    A constructor call is read backwards: the literals that fed it are the
    mapping's name, its GLFW default and its category (or, for the mods that
    ask InputConstants for the key by name, that name itself). Only a
    construction that carries both a name and a key is taken - anything less is
    a mod gluing its name together at runtime, and those mods are in the
    options snapshot already.
    """
    found: list[tuple[str, str]] = []
    window: list[tuple[str, object]] = []
    pc = 0
    while pc < len(code):
        op = code[pc]
        if op in (LDC, LDC_W):
            index = code[pc + 1] if op == LDC else struct.unpack_from(">H", code, pc + 1)[0]
            text = cls.string_at(index)
            if text is not None:
                window.append(("string", text))
        elif op == BIPUSH:
            window.append(("int", code[pc + 1]))
        elif op == SIPUSH:
            window.append(("int", struct.unpack_from(">h", code, pc + 1)[0]))
        elif ICONST_M1 <= op <= ICONST_5:
            window.append(("int", op - ICONST_0))
        elif op == GETSTATIC:
            member = cls.member(struct.unpack_from(">H", code, pc + 1)[0])
            if member and member[0] == INPUT_TYPE_CLASS:
                window.append(("input", member[1]))
        elif op in (INVOKESPECIAL, INVOKEVIRTUAL, INVOKESTATIC, INVOKEINTERFACE):
            member = cls.member(struct.unpack_from(">H", code, pc + 1)[0])
            if member and member[1] == "<init>" and member[0].endswith(KEYBIND_CLASSES):
                found.extend(read_construction(window[-12:]))
                window = []
            elif member and any(kind == "input" for kind, _ in window):
                # A mod may hand its name and key to a factory of its own
                # rather than to the constructor; InputConstants.Type in the
                # same breath is what makes it a key mapping either way.
                found.extend(read_construction(window[-12:]))
                window = []
            elif member:
                window.append(("call", member))

        if op == TABLESWITCH:
            aligned = (pc + 4) & ~3
            low, high = struct.unpack_from(">ii", code, aligned + 4)
            pc = aligned + 12 + 4 * (high - low + 1)
        elif op == LOOKUPSWITCH:
            aligned = (pc + 4) & ~3
            npairs = struct.unpack_from(">i", code, aligned + 4)[0]
            pc = aligned + 8 + 8 * npairs
        elif op == WIDE:
            pc += 6 if code[pc + 1] == 0x84 else 4
        else:
            pc += 1 + OPERANDS[op]
    return found


def read_construction(window: list[tuple[str, object]]) -> list[tuple[str, str]]:
    """One KeyMapping construction: its name, and its default key if that was literal.

    A mapping needs a name and a category, and both are strings a mod almost
    always writes out. Its default key is less reliable: it may be a number in
    the code (72), a name InputConstants is asked to look up, or something
    computed - IronJetpacks passes InputConstants.UNKNOWN.getValue(). The name
    is what the layout needs, so a construction counts even when the key does
    not read, and the default is left blank rather than guessed.
    """
    strings = [value for kind, value in window if kind == "string" and value]
    numbers = [value for kind, value in window if kind == "int"]
    if any(kind == "call" and value in NAME_BUILDERS for kind, value in window):
        # The mod is assembling the name (Util.makeDescriptionId("key.mapping",
        # ...)); the literal here is a prefix, not a mapping.
        return []
    # The last literal a construction takes is its category, and a category is
    # never a mapping name: Iron's Spellbooks builds "key.irons_spellbooks." +
    # "spell_wheel" at runtime and passes key.irons_spellbooks.group_1 as the
    # category, which otherwise reads exactly like a name. When the category is
    # not in the window at all - a factory added it - there is a single string
    # and the InputConstants type beside it says the string is the name.
    candidates = strings[:-1] if len(strings) >= 2 else strings
    names = [text for text in candidates if MAPPING_NAME.match(text) and not NOT_A_NAME.search(text)]
    named_a_key = any(kind == "input" for kind, _ in window)
    keys = [text for text in strings if text.startswith(("key.keyboard.", "key.mouse."))]
    if not names or (len(strings) < 2 and not named_a_key):
        return []
    if keys:
        return [(names[0], keys[0])]
    if numbers:
        return [(names[0], key_name(numbers[-1]))]
    return [(names[0], "")]

def scan_jar(path: Path, known: set[str]):
    """Mod ids, lang entries, (key, context) evidence and mappings from one jar."""
    mod_ids: list[str] = []
    lang: dict[str, str] = {}
    lang_ru: dict[str, str] = {}
    evidence: list[tuple[str, str]] = []
    discovered: dict[str, str] = {}
    try:
        archive = zipfile.ZipFile(path)
    except zipfile.BadZipFile:
        return mod_ids, lang, lang_ru, evidence, discovered
    classes: list[ClassFile] = []
    with archive:
        names = archive.namelist()
        for toml in ("META-INF/neoforge.mods.toml", "META-INF/mods.toml"):
            if toml in names:
                text = archive.read(toml).decode("utf-8", "replace")
                mod_ids = re.findall(r'^\s*modId\s*=\s*"([^"]+)"', text, re.MULTILINE)
                break
        for name in names:
            if name.startswith("assets/") and name.endswith("/lang/en_us.json"):
                try:
                    lang.update({k: v for k, v in json.loads(archive.read(name).decode("utf-8", "replace")).items()
                                 if isinstance(v, str)})
                except json.JSONDecodeError:
                    pass
            elif name.startswith("assets/") and name.endswith("/lang/ru_ru.json"):
                try:
                    lang_ru.update({k: v for k, v in json.loads(archive.read(name).decode("utf-8", "replace")).items()
                                    if isinstance(v, str)})
                except json.JSONDecodeError:
                    pass
            elif name.endswith(".class"):
                data = archive.read(name)
                # A mod that never names KeyMapping still has key bindings if it
                # builds them through a class of its own (Cobblemon does), so the
                # cheap pre-filter has to know the same names the reader does.
                if CONTEXT_CLASS.encode() not in data and                         not any(name.encode() in data for name in KEYBIND_CLASSES):
                    continue
                try:
                    classes.append(ClassFile(data))
                except (ValueError, struct.error, IndexError):
                    continue

        # What the jar builds comes first: a mapping the options snapshot never
        # saw still has to have its context read like everyone else's.
        for cls in classes:
            if not any(name.endswith(KEYBIND_CLASSES) for name in cls.strings()):
                continue
            for code in cls.methods_code():
                discovered.update(discover_code(code, cls))
        wider = known | set(discovered)
        for cls in classes:
            if not (cls.strings() & wider):
                continue
            for code in cls.methods_code():
                evidence.extend(scan_code(code, cls, wider))
    return mod_ids, lang, lang_ru, evidence, discovered


def guess_mod(name: str, mod_ids: set[str]) -> str:
    """The mod a mapping belongs to, from the shape of its name."""
    parts = re.split(r"[._]", name)
    candidates = []
    for length in range(min(3, len(parts)), 0, -1):
        for start in range(0, min(2, len(parts) - length + 1)):
            candidates.append("_".join(parts[start:start + length]))
            candidates.append("".join(parts[start:start + length]))
    for candidate in candidates:
        if candidate in mod_ids:
            return candidate
    return ""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--options", required=True, type=Path, help="options.txt of an instance that ran the pack")
    args = parser.parse_args()

    live = read_options(args.options)
    defaults = read_options(DEFAULTS) if DEFAULTS.exists() else {}
    known = set(live) | set(defaults)
    print(f"{len(live)} mappings in {args.options.name}, {len(defaults)} in configureddefaults, {len(known)} known")

    all_mod_ids: set[str] = set()
    lang: dict[str, str] = {}
    lang_ru: dict[str, str] = {}
    lang_owner: dict[str, str] = {}
    evidence: dict[str, set[str]] = defaultdict(set)
    discovered: dict[str, str] = {}
    discovered_owner: dict[str, str] = {}
    from_jars: dict[str, str] = {}
    jars = sorted(MODS.glob("*.jar"))
    for index, jar in enumerate(jars, 1):
        mod_ids, jar_lang, jar_lang_ru, jar_evidence, jar_discovered = scan_jar(jar, known)
        all_mod_ids.update(mod_ids)
        owner = mod_ids[0] if mod_ids else jar.stem
        for key, text in jar_lang.items():
            if (key in known or LANG_CANDIDATE.search(key)) and key not in lang:
                lang[key] = text
                lang_owner[key] = owner
        for key, text in jar_lang_ru.items():
            if (key in known or LANG_CANDIDATE.search(key)) and key not in lang_ru:
                lang_ru[key] = text
        for key, context in jar_evidence:
            evidence[key].add(context)
        from_jars.update(jar_discovered)
        for key, default in jar_discovered.items():
            if key not in known and key not in discovered:
                discovered[key] = default
                discovered_owner[key] = owner
        if index % 100 == 0:
            print(f"  {index}/{len(jars)} jars", file=sys.stderr)

    # How wide the net is, said out loud: the mods whose names the bytecode
    # spells out are covered, the ones that build names at runtime are not.
    readable = len(set(from_jars) & set(live))
    print(f"{readable} of the {len(live)} mappings in the snapshot were also readable from the jars")
    if discovered:
        known |= set(discovered)
        print(f"{len(discovered)} mapping(s) only the jars know (a mod added since that options.txt):")
        for name in sorted(discovered):
            print(f"  {name} -> {discovered[name]} ({discovered_owner[name]})")

    contexts: dict[str, dict] = {}
    for name in sorted(known):
        found = evidence.get(name, set())
        if len(found) == 1:
            context, how = next(iter(found)), "bytecode"
        elif len(found) > 1:
            context, how = "UNIVERSAL", "bytecode-mixed:" + "+".join(sorted(found))
        else:
            context, how = "UNIVERSAL", "assumed"
        contexts[name] = {"context": context, "source": how}
    (HERE / "contexts.json").write_text(json.dumps(contexts, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    rows = ["name\tmod\tcontext\tcontext_source\tdefault\tlive\tseen\tenglish\trussian"]
    for name in sorted(known):
        # Where a mapping was seen decides whether the pack really has it:
        # configureddefaults still carries lines of mods LL8 has dropped.
        where = [source for source, yes in
                 (("options", name in live), ("defaults", name in defaults), ("jar", name in discovered))
                 if yes]
        mod = discovered_owner.get(name) or lang_owner.get(name) or guess_mod(name, all_mod_ids) or ("minecraft" if lang.get(name) is None and "." not in name.split(".", 1)[-1] else "")
        rows.append("\t".join([
            name,
            mod,
            contexts[name]["context"],
            contexts[name]["source"],
            defaults.get(name) or discovered.get(name, ""),
            live.get(name, ""),
            "+".join(where),
            lang.get(name, ""),
            lang_ru.get(name, ""),
        ]))
    (HERE / "registered-keys.tsv").write_text("\n".join(rows) + "\n", encoding="utf-8")

    by_context = defaultdict(int)
    by_source = defaultdict(int)
    for entry in contexts.values():
        by_context[entry["context"]] += 1
        by_source[entry["source"].split(":")[0]] += 1
    print("contexts:", dict(by_context))
    print("sources:", dict(by_source))
    print(f"wrote {HERE / 'registered-keys.tsv'} and {HERE / 'contexts.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
