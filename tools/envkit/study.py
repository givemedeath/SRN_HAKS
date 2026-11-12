"""What the stock tiles of a tileset say, for a question about how the engine wants a tile made.

A tile group is built to rules nobody wrote down for us: which path node a tile's ground calls for, and how a stock
tile states its fade, lights, doors and day/night animation. The stock tiles of the packs answer both. `path_nodes`
checks the engine's path-node table against them: for each stock tile, are the exits its node gives on walkable ground,
and are exits of one region joined and exits of different regions apart? It was how the table and the sense a tile's
Orientation turns it in were settled (2026-11-11), and is run again before a group goes into a tileset whose tiles
were not looked at. `tiles` decompiles stock tiles and tells the lines that matter of each.

These were one-off scripts for the Stuffer Shack's tile group (2026-11-10/11)."""
import collections
import re
import struct
import subprocess
from pathlib import Path

import numpy as np

from . import require

# letter: the exits a path node gives a tile at Orientation 0, as (x, y, region), the tile's middle at (0, 0) and +y
# north (nwn.wiki's table). Exits of one region are joined by a walk across the tile; exits of two are not.
_TABLE = '''
A | (0,5)0 (-5,0)0 (5,0)0 (0,-5)0
B | (0,5)0 (-5,2.5)0 (-5,-2.5)1 (-2.5,-5)1 (2.5,-5)0 (5,0)0
C | (-2.5,5)0 (-5,0)0 (-2.5,-5)0 (2.5,-5)1 (5,0)1 (2.5,5)1
D | (-2.5,5)0 (-5,2.5)0 (-5,-2.5)1 (-2.5,-5)1 (2.5,-5)2 (5,-2.5)2 (5,2.5)3 (2.5,5)3
E | (-2.5,5)0 (-5,2.5)0 (-5,-2.5)1 (-2.5,-5)1 (2.5,-5)2 (5,0)2 (2.5,5)2
F | (-2.5,5)0 (-5,0)0 (-2.5,-5)0 (2.5,-5)0 (5,0)0 (2.5,5)0
G | (-2.5,5)0 (-5,0)0 (0,-5)0 (5,0)0 (2.5,5)0
H | (-5,0)0 (0,-5)0
I | (0,5)0 (-5,0)0 (0,-5)0
J | (-5,0)0 (0,-5)0 (5,0)1 (0,5)1
K | (-2.5,5)0 (-5,0)0 (0,-5)1 (5,-2.5)1 (5,2.5)2 (2.5,5)2
L | (0,5)0 (0,-5)0
M | (-2.5,5)0 (-2.5,-5)0 (2.5,5)1 (2.5,-5)1
N | (0,5)0
O | (-2.5,5)0 (-5,2.5)0 (-5,-2.5)1 (-2.5,-5)1 (2.5,-5)2 (5,-2.5)2 (5,2.5)1 (2.5,5)1
Q | (-2.5,5)0 (-5,0)0 (0,-5)1 (5,0)1 (2.5,5)1
R | (-2.5,-5)0 (-5,0)0 (0,5)1 (5,0)1 (2.5,-5)1
S | (-2.5,5)0 (-5,0)0 (2.5,5)1 (5,0)1
T |
U | (-5,0)0 (0,-5)1 (0,5)1 (5,0)1
V | (0,5)0 (0,-5)1 (5,0)1
W | (0,5)0 (0,-5)1 (-5,0)1
X | (0,5)0 (-5,0)1
Y | (0,5)0 (0,-5)1
Z | (-5,2.5)0 (-5,-2.5)0 (-2.5,-5)0 (2.5,-5)0 (5,0)0 (0,5)0
w | (0,5)0 (-5,0)1 (5,0)2 (0,-5)3
'''
EXITS = {line.split('|')[0].strip(): [(float(x), float(y), int(region)) for x, y, region in re.findall(r'\(([-\d.]+),([-\d.]+)\)(\d)', line)]
         for line in _TABLE.strip().splitlines()}
CLOSED = {0, 2, 7, 8, 15, 17}  # the surface materials nothing walks on
CELLS = 40  # samples across a tile
TOLD = ('tilefade', 'position', 'radius', 'color', 'multiplier', 'isdynamic', 'ambientonly', 'affectdynamic', 'shadow', 'lightpriority', 'fadinglight', 'newanim', 'length',
        'transtime', 'selfillumcolorkey', 'alphakey', 'bitmap', 'parent', 'selfillumcolor', 'alpha', 'flareradius', 'animroot', 'doneanim')
RECORD = ('Model', 'Doors', 'MainLight1', 'SourceLight1', 'AnimLoop1', 'PathNode', 'Orientation', 'ImageMap2D')


def set_text(packs, tileset):
    path = Path(packs) / f'srn_t_{tileset}' / f'{tileset}.set'; require(path.is_file(), 'No such tileset in the packs: ' + str(path))
    return path.read_bytes().decode('cp1252').replace('\r', '')


def records(text):
    """{tile number: {key: value}} of a set file's tiles, each with its door sections under `doors`."""
    found = {}
    for number, block in re.findall(r'(?ms)^\[TILE(\d+)\]\n(.*?)(?=^\[|\Z)', text):
        found[int(number)] = {**dict(line.split('=', 1) for line in block.splitlines() if '=' in line), 'doors': []}
    for number, block in re.findall(r'(?ms)^\[TILE(\d+)DOOR\d+\]\n(.*?)(?=^\[|\Z)', text):
        found[int(number)]['doors'].append(dict(line.split('=', 1) for line in block.splitlines() if '=' in line))
    return found


def _resource(packs, tileset, name):
    return next((folder / name for folder in (Path(packs) / f'srn_t_{tileset}', Path(packs) / 'srn_t_common') if (folder / name).is_file()), None)


def walkable(wok):
    """Where a tile's walkmesh is walked on, as a CELLS by CELLS grid from its south-west corner: at each sample, the
    material of the face on top."""
    text = Path(wok).read_text(encoding='cp1252', errors='replace'); require('node aabb' in text, 'No walkmesh node in ' + str(wok))
    body = text.split('node aabb', 1)[1]

    def rows(word, kind):
        count = int(re.search(word + r' (\d+)', body)[1]); lines = body.split(word, 1)[1].splitlines()[1:count + 1]
        return np.array([[kind(value) for value in line.split()] for line in lines])

    points, faces = rows('verts', float)[:, :3], rows('faces', int); grid = np.zeros((CELLS, CELLS), bool); height = np.full((CELLS, CELLS), -np.inf)
    centres = (np.arange(CELLS) + 0.5) * 10 / CELLS - 5
    for a, b, c, *rest in faces:
        (ax, ay, az), (bx, by, bz), (cx, cy, cz) = points[[a, b, c]]; whole = (bx - ax) * (cy - ay) - (cx - ax) * (by - ay)
        if abs(whole) < 1e-9:
            continue
        for y in centres[(centres >= min(ay, by, cy)) & (centres <= max(ay, by, cy))]:
            for x in centres[(centres >= min(ax, bx, cx)) & (centres <= max(ax, bx, cx))]:
                u, w = ((x - ax) * (cy - ay) - (cx - ax) * (y - ay)) / whole, ((bx - ax) * (y - ay) - (x - ax) * (by - ay)) / whole
                if min(u, w, 1 - u - w) >= -1e-9:
                    row, column = int((y + 5) * CELLS / 10), int((x + 5) * CELLS / 10); z = az + u * (bz - az) + w * (cz - az)
                    if z >= height[row, column]:  # what is on top is what is walked on
                        height[row, column] = z; grid[row, column] = rest[-1] not in CLOSED
    return grid


def _masses(grid):
    """The grid's walkable samples numbered by the ground they are joined to, from 1."""
    out = np.zeros(grid.shape, int); count = 0
    for start in zip(*np.nonzero(grid)):
        if out[start]:
            continue
        count += 1; out[start] = count; stack = [start]
        while stack:
            row, column = stack.pop()
            for near in ((row + 1, column), (row - 1, column), (row, column + 1), (row, column - 1)):
                if 0 <= near[0] < CELLS and 0 <= near[1] < CELLS and grid[near] and not out[near]:
                    out[near] = count; stack.append(near)
    return out


def turned(exits, degrees, sense):
    """A node's exits on a tile turned by its Orientation, counter-clockwise (`ccw`) or clockwise (`cw`)."""
    out = []
    for x, y, region in exits:
        for _ in range(int(round(degrees / 90)) % 4):
            x, y = (-y, x) if sense == 'ccw' else (y, -x)
        out.append((x, y, region))
    return out


def judge(grid, exits):
    """(exits on walkable ground, exits, pairs of exits rightly joined or apart, pairs) of a tile's node on its ground."""
    mass = _masses(grid); at = []
    for x, y, region in exits:
        row, column = (min(CELLS - 1, max(0, int((value + 5) * CELLS / 10 - (value == 5)))) for value in (y, x))
        near = mass[max(0, row - 1):row + 2, max(0, column - 1):column + 2]; found = near[near > 0]
        at.append((int(collections.Counter(found.tolist()).most_common(1)[0][0]) if len(found) else 0, region))
    pairs = [(a, b) for index, a in enumerate(at) for b in at[index + 1:] if a[0] and b[0]]
    return sum(1 for ground, _ in at if ground), len(at), sum(1 for a, b in pairs if (a[0] == b[0]) == (a[1] == b[1])), len(pairs)


def path_nodes(packs, tilesets):
    """The path-node table against the stock tiles of tilesets, turning each tile by its Orientation each way: {ccw,
    cw: {tiles, exitsOnGround: [on, of], pairsRight: [right, of], letters: {letter: the same}}}. The sense the engine
    turns a tile in is the one whose exits land on ground and whose pairs come out right; a letter that does badly in
    both is one the table has wrong. Our own tiles (ek_) are left out: they are what the table is used to make."""
    score = {sense: collections.defaultdict(lambda: np.zeros(5, int)) for sense in ('ccw', 'cw')}
    for tileset in tilesets:
        for record in records(set_text(packs, tileset)).values():
            model = record.get('Model', '').lower(); wok = _resource(packs, tileset, model + '.wok')
            if wok is None or record.get('PathNode') not in EXITS or model.startswith('ek_'):
                continue
            grid = walkable(wok)
            for sense in score:
                score[sense][record['PathNode']] += [1, *judge(grid, turned(EXITS[record['PathNode']], float(record.get('Orientation', 0)), sense))]
    told = lambda row: {'tiles': int(row[0]), 'exitsOnGround': [int(row[1]), int(row[2])], 'pairsRight': [int(row[3]), int(row[4])]}
    require(any(score.values()), 'No stock tile with a walkmesh and a known path node in ' + ', '.join(tilesets))
    return {sense: {**told(sum(letters.values())), 'letters': {letter: told(letters[letter]) for letter in sorted(letters)}} for sense, letters in score.items()}


def told(model_text):
    """The lines of a decompiled tile model that say how it fades, is lit and is animated: every node, then under it
    what it states of those (a position only for a light or a dummy, which is where a light or a door stands)."""
    out, node = [], None
    for line in model_text.splitlines():
        word = line.split()
        if not word:
            continue
        if word[0] == 'node':
            node = line.strip(); out.append(node)
        elif node and word[0] in TOLD and (word[0] != 'position' or ' light ' in node or ' dummy ' in node):
            out.append('    ' + line.strip()[:110])
    return out


def tiles(packs, tileset, numbers, output, *, tool=None):
    """Decompile stock tiles of a tileset into `output` and tell of each {tile, record, doors, lines, minimap}: its
    set-file keys that matter, its door sections, the lines of its model (`told`) and its minimap's size."""
    found = records(set_text(packs, tileset)); output = Path(output); output.mkdir(parents=True, exist_ok=True); rows = []
    missing = [number for number in numbers if number not in found]; require(not missing, f'{tileset} has no tile ' + ', '.join(map(str, missing)))
    if tool is None:
        from tools.armorkit import toolchain
        tool = toolchain.cleanmodels()['path']
    for number in numbers:
        record = found[number]; model = record['Model']; row = {'tile': number, 'record': {key: record.get(key) for key in RECORD}, 'doors': record['doors']}
        source = _resource(packs, tileset, f'{model}.mdl'); target = output / f'{model}.mdl'
        if source is None:
            row['error'] = 'model not in the packs'
        else:
            target.unlink(missing_ok=True)  # what an earlier run left is not what this one made
            result = subprocess.run([str(tool), 'decompile', '--overwrite', str(source), str(target)], capture_output=True, text=True)
            if result.returncode == 0 and target.is_file():
                row['lines'] = told(target.read_text(encoding='cp1252', errors='replace'))
            else:
                row['error'] = 'decompile failed: ' + (result.stdout + result.stderr)[-300:]
        image = _resource(packs, tileset, f'{record.get("ImageMap2D")}.tga')
        if image is not None:
            data = image.read_bytes(); wide, high, depth = struct.unpack_from('<HHB', data, 12); row['minimap'] = {'file': image.name, 'size': [wide, high], 'bits': depth, 'type': data[2]}
        rows.append(row)
    return rows
