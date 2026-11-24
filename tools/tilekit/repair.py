"""Broken animation blocks of a tileset's ASCII tile models, reported and put right.

Some tiles come with animations NeverBlender's compiler reads wrong or drops nodes from: a node without its `endnode`,
a node without its `parent`, `endlist` spelled `e n d l i s t`, and a node listed twice in one animation. `repaired`
closes the nodes, gives each the parent it has in the geometry, spells `endlist`, and drops a repeat whose lines are
the same. A repeat that differs is kept and told: which of the two the tile means is a decision. A node that needs a
parent the geometry does not have is refused by name. Lines that need nothing are left as they are, and so is a model
with nothing to repair, to the byte."""
from . import inventory, lamps, require

SPELLED = 'e n d l i s t'


def _parents(lines):
    """{node: its parent} of a model's geometry, in lower case names; the first of two nodes of a name counts."""
    found, inside, node = {}, False, None
    for line in lines:
        words = line.split(); head = words[0].lower() if words else ''
        if head == 'beginmodelgeom':
            inside = True
        elif head == 'endmodelgeom':
            inside = False
        elif inside and head == 'node' and len(words) >= 3:
            node = words[2].lower()
        elif inside and head == 'parent' and node is not None and len(words) > 1:
            found.setdefault(node, words[1]); node = None
    return found


def repaired(text):
    """(text, {closed, parented, spelled, dropped, differing}) of an ASCII model: how many of each was put right, and
    in `differing` the [animation, node] of every repeat that was kept because its lines differ."""
    ending = '\r\n' if '\r\n' in text else '\n'; lines = text.replace('\r\n', '\n').split('\n'); parents = _parents(lines)
    told = {'closed': 0, 'parented': 0, 'spelled': 0, 'dropped': 0, 'differing': []}
    out, animation, block, seen = [], None, None, {}

    def finish(closed):
        nonlocal block
        if not any(line.split()[:1] and line.split()[0].lower() == 'parent' for line in block):
            name = block[0].split()[2]
            require(name.lower() in parents, f'{animation}: the animation node {name} has no parent, and the geometry has no node of that name to take it from')
            block.insert(1, f'    parent {parents[name.lower()]}'); told['parented'] += 1
        if not closed:
            block.append('  endnode'); told['closed'] += 1
        body = [line.strip() for line in block]; key = body[0].split()[2].lower()
        if seen.get(key) == body:
            told['dropped'] += 1
        else:
            if key in seen:
                told['differing'].append([animation, body[0].split()[2]])
            seen.setdefault(key, body); out.extend(block)
        block = None
    for line in lines:
        words = line.split(); head = words[0].lower() if words else ''
        if line.strip().lower() == SPELLED:
            line = line[:len(line) - len(line.lstrip())] + 'endlist'; told['spelled'] += 1
        if head == 'newanim':
            require(animation is None and block is None, f'{animation}: the animation has no doneanim')
            animation, seen = words[1] if len(words) > 1 else '', {}
        if animation is not None and block is not None and head in ('node', 'doneanim'):
            blank = []  # blank lines before the next node are not the unclosed node's
            while block[-1].strip() == '':
                blank.insert(0, block.pop())
            finish(False); out.extend(blank)
        if head == 'doneanim':
            animation = None
        if animation is not None and head == 'node' and len(words) >= 3:
            block = [line]; continue
        if block is not None:
            block.append(line)
            if head == 'endnode':
                finish(True)
            continue
        out.append(line)
    require(animation is None, f'{animation}: the animation has no doneanim')
    if not any(told[key] for key in ('closed', 'parented', 'spelled', 'dropped')):
        return text, told
    return ending.join(out), told


def repair(repo, tileset, *, models=None, write=False):
    """{model: what was put right} of a tileset's ASCII models (`models`: only these) that need anything. Nothing is
    written without `write`; with it, the ASCII source is, and the binaries are then compiled from it (`compile`)."""
    wanted = {name.lower() for name in models} if models else None; found, seen = {}, set()
    for name, _, text, _, path in inventory.drawn_copies(repo, tileset.lower(), None, lamps.PACKS):
        if wanted is not None and name not in wanted:
            continue
        seen.add(name)
        try:
            new, told = repaired(text)
        except ValueError as error:
            raise ValueError(f'{name}: {error}') from error
        require(inventory.walk_hash(new) == inventory.walk_hash(text), f'{name}: the walkmesh would change')
        if new != text or told['differing']:
            found[name] = (path, new if new != text else None, told)
    missing = sorted((wanted or set()) - seen); require(not missing, 'No uncompiled model of the tileset is ' + ', '.join(missing))
    for path, new, _ in found.values() if write else ():  # every model read and checked before any is written
        if new is not None:
            path.write_bytes(new.encode('cp1252'))
    return {name: told for name, (_, _, told) in found.items()}
