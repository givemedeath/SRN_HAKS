"""Node names of a tile pack's ASCII sources made one word each and the only one of their name. The suburb tiles
(udp1) were exported with names like `bridge rail` and `bridge deck`, and with several meshes of one name. A model is
read a word at a time, so those are all `bridge`: a parent named so is the first of them, and the compiler's check of
a binary against its source cannot tell them apart (76 models refused at the adoption, 2026-11-23). Here each such
node takes a name of its own, and every reference keeps the meaning it had: a parent is the first node of its word,
and an animation's nodes of one word are the geometry's, in their order."""
import re
from pathlib import Path

from . import inventory, require
from .compiled import SOURCES

LINE = re.compile(r'^([ \t]*node[ \t]+)(\w+)([ \t]+)(\S[^\r\n]*?)([ \t]*)$')
PARENT = re.compile(r'^([ \t]*parent[ \t]+)(\S[^\r\n]*?)([ \t]*)$')
LONGEST = 32  # a node's name in a compiled model


def unique(text):
    """(the model's text with every node under a name of one word that no other node has, how many were renamed)."""
    ending = '\r\n' if '\r\n' in text else '\n'; lines = text.split(ending)
    start = next((index for index, line in enumerate(lines) if re.match(r'(?i)^[ \t]*newanim[ \t]', line)), len(lines))
    words = [LINE.match(line).group(4).split()[0].lower() for line in lines[:start] if LINE.match(line)]
    whole = [LINE.match(line).group(4) for line in lines[:start] if LINE.match(line)]
    plain = {word for word in set(words) if words.count(word) == 1 and not any(' ' in name or '\t' in name for name in whole if name.split()[0].lower() == word)}
    taken = set(plain) | {name.lower() for name in whole if name.split()[0].lower() in plain}; given = {}  # word: its nodes' new names, in the geometry's order

    def fresh(name):
        stem = re.sub(r'\s+', '_', name.strip())[:LONGEST - 4]
        made = next(one for one in [stem] + [f'{stem}_{count}' for count in range(2, 999)] if one.lower() not in taken)
        taken.add(made.lower()); return made
    for name in whole:
        word = name.split()[0].lower()
        if word not in plain:
            given.setdefault(word, []).append(fresh(name))
    if not given:
        return text, 0
    seen = {}  # within the geometry or one animation: how many nodes of a word have gone by
    for index, line in enumerate(lines):
        if re.match(r'(?i)^[ \t]*newanim[ \t]', line):
            seen = {}
        at = LINE.match(line)
        if at:
            word = at.group(4).split()[0].lower()
            if word in given:
                count = seen.get(word, 0); seen[word] = count + 1
                require(count < len(given[word]), f'An animation has more nodes named {word} than the geometry')
                lines[index] = at.group(1) + at.group(2) + at.group(3) + given[word][count] + at.group(5)
            continue
        at = PARENT.match(line)
        if at and at.group(2).split()[0].lower() in given:  # the first node of the word, as the game reads a parent
            lines[index] = at.group(1) + given[at.group(2).split()[0].lower()][0] + at.group(3)
    return ending.join(lines), sum(len(names) for names in given.values())


def write(repo, pack):
    """Give the nodes of every ASCII source of an adopted tile pack unique names, in place, and tell {model: renamed}."""
    folder = Path(repo) / SOURCES / pack; require(folder.is_dir(), f'{pack} has no sources: adopt it first (tilekit compile --adopt)'); told = {}
    for path in sorted(folder.glob('*.mdl')):
        text = path.read_bytes().decode('cp1252'); new, count = unique(text)
        if count:
            require(inventory.walk_hash(new) == inventory.walk_hash(text), f'{path.stem}: the walkmesh would change')
            path.write_bytes(new.encode('cp1252')); told[path.stem.lower()] = count
    return told
