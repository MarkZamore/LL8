#!/usr/bin/env python3
"""Proves launcher/controls-preset.txt has no two mappings the Controls screen marks red.

The rule is NeoForge 1.21.1's own, KeyMapping.same(), applied to every pair:

  * two mappings only conflict if their conflict contexts do - UNIVERSAL with
    everything, GUI with GUI, IN_GAME with IN_GAME;
  * a mapping with a Shift/Ctrl/Alt modifier conflicts with any mapping (in a
    conflicting context) that sits on that modifier's own key;
  * on the same key, the same modifier is a conflict; different modifiers are a
    conflict too when either mapping is UNIVERSAL/IN_GAME and one modifier is
    empty (a plain E fires under Shift+E) - only GUI mappings keep them apart.

Contexts come from contexts.json (read from the mods' bytecode where the class
gave it away, UNIVERSAL otherwise) with contexts.overrides.json on top. Also
checks the file lists every mapping in registered-keys.tsv, names only known
keys, has no duplicate lines, and keeps the four right-hand modifier keys and
Left Alt in the roles design.md gives them.

A pair listed in allowed-conflicts.json is a conflict someone decided to live
with: the screen still marks it red, and the reason is written down beside it.
An allowance that no longer matches a real conflict is itself an error, so the
file cannot quietly outlive the layout it excuses.

    python tools/keybinds/check_preset.py [--report]

Exit code 0 means the layout is clean; anything else prints why.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
PRESET = REPO / "launcher" / "controls-preset.txt"
KEYS = HERE / "registered-keys.tsv"
CONTEXTS = HERE / "contexts.json"
OVERRIDES = HERE / "contexts.overrides.json"
ALLOWED = HERE / "allowed-conflicts.json"

UNBOUND = "key.keyboard.unknown"
MODIFIERS = {"SHIFT", "CONTROL", "ALT"}
MODIFIER_KEYS = {
    "SHIFT": {"key.keyboard.left.shift", "key.keyboard.right.shift"},
    "CONTROL": {"key.keyboard.left.control", "key.keyboard.right.control"},
    "ALT": {"key.keyboard.left.alt", "key.keyboard.right.alt"},
}
KNOWN_KEYS = set(
    [f"key.keyboard.{c}" for c in "abcdefghijklmnopqrstuvwxyz0123456789"] +
    [f"key.keyboard.f{n}" for n in range(1, 26)] +
    [f"key.keyboard.keypad.{n}" for n in range(10)] +
    ["key.keyboard.keypad." + n for n in ("add", "subtract", "multiply", "divide", "decimal", "enter", "equal")] +
    ["key.keyboard." + n for n in (
        "grave.accent", "minus", "equal", "left.bracket", "right.bracket", "backslash", "semicolon",
        "apostrophe", "comma", "period", "slash", "space", "tab", "caps.lock", "enter", "backspace",
        "left.shift", "right.shift", "left.control", "right.control", "left.alt", "right.alt",
        "left.win", "right.win", "menu", "insert", "delete", "home", "end", "page.up", "page.down",
        "up", "down", "left", "right", "num.lock", "scroll.lock", "pause", "print.screen",
        "world.1", "world.2", "unknown")] +
    ["key.mouse." + n for n in ("left", "right", "middle", "4", "5", "6", "7", "8")]
)
LINE = re.compile(r"^key_(?P<name>[^:]+):(?P<key>[^:]+)(?::(?P<modifier>[A-Z]+))?$")

# NeoForge gives these vanilla mappings the IN_GAME context (Options.setForgeKeybindProperties);
# every other vanilla mapping is UNIVERSAL, which is also what a mod gets when it uses the
# vanilla constructor. This is why a screen-only mapping may share Shift with sneak but not E
# with the inventory.
VANILLA_IN_GAME = {
    "key.forward", "key.left", "key.back", "key.right", "key.jump", "key.sneak", "key.sprint",
    "key.attack", "key.chat", "key.playerlist", "key.command", "key.togglePerspective", "key.smoothCamera",
}


class Mapping:
    __slots__ = ("name", "key", "modifier", "context", "line")

    def __init__(self, name, key, modifier, context, line):
        self.name, self.key, self.modifier, self.context, self.line = name, key, modifier, context, line

    @property
    def bound(self):
        return self.key != UNBOUND


def contexts_conflict(a: str, b: str) -> bool:
    return a == "UNIVERSAL" or b == "UNIVERSAL" or a == b


def modifier_matches(modifier: str, key: str) -> bool:
    return key in MODIFIER_KEYS.get(modifier, ())


def same(this: Mapping, other: Mapping) -> bool:
    """KeyMapping.same as NeoForge 1.21.1 patches it, for bound mappings."""
    if contexts_conflict(this.context, other.context) or contexts_conflict(other.context, this.context):
        if modifier_matches(this.modifier, other.key) or modifier_matches(other.modifier, this.key):
            return True
        if this.key == other.key:
            return this.modifier == other.modifier or (
                contexts_conflict(this.context, "IN_GAME") and
                (this.modifier == "NONE" or other.modifier == "NONE"))
    return False


def load_allowances() -> dict[frozenset, str]:
    """Conflicting pairs someone signed off on: the pair by name, and why."""
    if not ALLOWED.exists():
        return {}
    listed = json.loads(ALLOWED.read_text(encoding="utf-8")).get("pairs", [])
    return {frozenset(entry["mappings"]): entry["reason"] for entry in listed}


def load_preset() -> tuple[list[Mapping], list[str]]:
    problems: list[str] = []
    contexts = json.loads(CONTEXTS.read_text(encoding="utf-8")) if CONTEXTS.exists() else {}
    overrides = json.loads(OVERRIDES.read_text(encoding="utf-8")) if OVERRIDES.exists() else {}
    mappings: list[Mapping] = []
    seen: set[str] = set()
    for number, raw in enumerate(PRESET.read_text(encoding="utf-8").splitlines(), 1):
        # A comment is a line starting with #, or a "  # ..." tail after a mapping.
        line = raw.split("  #", 1)[0].strip()
        if not line or line.startswith("#"):
            continue
        match = LINE.match(line)
        if not match:
            problems.append(f"line {number}: not a key_<name>:<key>[:<MODIFIER>] line: {raw.strip()}")
            continue
        name, key, modifier = match.group("name"), match.group("key"), match.group("modifier") or "NONE"
        if name in seen:
            problems.append(f"line {number}: {name} is listed twice")
        seen.add(name)
        if key not in KNOWN_KEYS:
            problems.append(f"line {number}: {name} names an unknown key {key}")
        if modifier != "NONE" and modifier not in MODIFIERS:
            problems.append(f"line {number}: {name} has an unknown modifier {modifier}")
        context = overrides.get(name) or (
            "IN_GAME" if name in VANILLA_IN_GAME else contexts.get(name, {}).get("context", "UNIVERSAL"))
        mappings.append(Mapping(name, key, modifier, context, number))
    return mappings, problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--report", action="store_true", help="print the per-key layout after checking")
    args = parser.parse_args()

    mappings, problems = load_preset()
    by_name = {m.name: m for m in mappings}

    # Completeness against the stock of registered mappings.
    if KEYS.exists():
        # A mapping counts as registered when the live instance wrote it down or
        # a jar was caught building it. A line only configureddefaults knows is a
        # leftover of a mod the pack no longer has.
        registered = {row["name"] for row in csv.DictReader(KEYS.open(encoding="utf-8"), delimiter="\t")
                      if {"options", "jar"} & set(row.get("seen", "options").split("+"))}
        for name in sorted(registered - set(by_name)):
            problems.append(f"{name} is registered by the pack but missing from the preset")
        for name in sorted(set(by_name) - registered):
            problems.append(f"{name} is in the preset but no installed mod registers it (re-run scan_keys.py?)")

    # The design's fixed roles: modifier keys hold what design.md says and nothing else,
    # because a stray mapping there would put every Shift/Ctrl/Alt combo in conflict.
    for name, wanted in {
        "create.keyinfo.shift_modifier": "key.keyboard.right.shift",
        "create.keyinfo.ctrl_modifier": "key.keyboard.right.control",
        "create.keyinfo.alt_modifier": "key.keyboard.right.alt",
        "key.jade.show_details": "key.keyboard.left.alt",
    }.items():
        mapping = by_name.get(name)
        if mapping and mapping.key != wanted:
            problems.append(f"{name} is on {mapping.key}; design.md puts it on {wanted}")

    # No modifier combos at all: the layout was designed without them so the
    # right-hand modifier keys could become plain keys. A combo would conflict
    # with whatever sits on that modifier's key.
    for m in mappings:
        if m.bound and m.modifier != "NONE":
            problems.append(f"line {m.line}: {m.name} uses a {m.modifier} combo; the layout has none")

    allowances = load_allowances()
    bound = [m for m in mappings if m.bound]
    conflicts: list[tuple[Mapping, Mapping]] = []
    allowed: list[tuple[Mapping, Mapping]] = []
    for i, a in enumerate(bound):
        for b in bound[i + 1:]:
            if same(a, b) or same(b, a):
                (allowed if frozenset((a.name, b.name)) in allowances else conflicts).append((a, b))
    for a, b in conflicts:
        problems.append(
            f"CONFLICT on {a.key}: {a.name} [{a.context}] vs {b.name} [{b.context}] (lines {a.line}, {b.line})")
    for pair in allowances.keys() - {frozenset((a.name, b.name)) for a, b in allowed}:
        problems.append(" and ".join(sorted(pair)) + " are allowed to conflict but do not: drop the allowance")

    by_key: dict[str, list[Mapping]] = defaultdict(list)
    for m in bound:
        by_key[m.key].append(m)

    print(f"{len(mappings)} mappings, {len(bound)} bound, {len(mappings) - len(bound)} unbound, "
          f"{len(by_key)} physical keys in use, {len(conflicts)} conflicts")
    for a, b in allowed:
        print(f"  allowed on {a.key.replace('key.keyboard.', '')}: {a.name} with {b.name}"
              f" - {allowances[frozenset((a.name, b.name))]}")
    if args.report:
        for key in sorted(by_key, key=lambda k: (not k.startswith("key.keyboard."), k)):
            print(f"  {key.replace('key.keyboard.', ''):22} " +
                  " | ".join(f"{m.name} [{m.context}]" for m in by_key[key]))
    if problems:
        print(f"\n{len(problems)} problem(s):")
        for problem in problems:
            print("  " + problem)
        return 1
    print("The preset is clean.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
