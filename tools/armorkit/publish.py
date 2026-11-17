"""Publish baked outfits into the `srn_parts` pack: models and maps, parts tables, registry, handoff and gates.

    python -m tools.armorkit publish REGISTRY --bake DIR [--bake DIR ...] --stock FOLDER --record MODEL=FILE [...]
                                     [--brief MODEL=FILE] [--body-pack DIR] [--trial ROOT | --dry-run] [--build]
                                     [--report FILE]
    python -m tools.armorkit logos [--trial ROOT | --dry-run] [--build] [--report FILE]

`logos` is the one way a published file changes: it puts the kit's logo strip in place of the published one, for a
new logo (`relogo`). The rest of this is `publish`.

REGISTRY is the whole part registry as it stands after the publication (`registry.py`): the parts already
published, unchanged, and the new ones. Each `--bake` is the output folder of a bake compiled at the part's
registry number (`bake BRIEF OUTPUT --number N --kept KEPT --nwn-root GAME`; a refit body is baked the same way
from the folder `refit` kept its parts in). Every payload is copied byte for byte; nothing is baked or compiled
here. `--stock` is the folder of the game's own twelve `parts_*.2da` tables, and `--record` names a file of the
outfit's history to pin by its hash (the generation ledger, a generation log, a refit report), under the model
name of the brief it belongs to.

What a publication writes, under the repository or under `--trial ROOT`:

* `srn_parts/`: each model with its tint texture, material file and the maps that file names, and an inventory
  icon per gender for each chest, pelvis, belt, shoulder and robe part (`icon`); with the first part that shows a
  logo, the logo's material, shader and strip (`logo.FILES`), once for every such part;
* `srn_2da/parts_<slot>.2da`: the stock rows, padding and the registry's live rows, for every table with a live
  row (`merged`): no gap, no existing row changed;
* `docs/armorkit/parts-registry.json`, the registry, and `docs/armorkit/parts-handoff.json`, the file SR_NWN
  reads: `registry.handoff` with the pack's name and, per outfit and body, the hashes of its brief, bake record,
  history records and resources;
* `docs/armorkit/parts-copies.json`, the pack's copies list: a tint texture that is one image under several
  names is written once and its other names listed (`copies`, `tint_copies`);
* the `srn_parts` entry of `hakbuilder.json`, once, naming the copies list when there is one.

The gates (`gates`) each fail the command with the model and the reason: every body a part lists has its model
and every part its table row, every texture a model names is in the pack, no name is one `srn_body` or
`srn_armor` holds, each chest closes round the body's neck (`neck`), every icon slot has its icons, every bake
passed its own gates, every outfit has its brief and a history record, and every file published earlier, icons
included, is still the one its handoff records. Nothing is written into the
repository unless all of them pass. `--trial ROOT` writes the same tree into a new scratch folder whatever the gates
say, seeded from the repository's own `srn_2da` and `srn_parts`, and `--build` packs it there for a client check
(`build`); `--dry-run` writes nothing. The command exits 1 when a gate fails. It prints the report with the
first 40 failures; `--report FILE` writes all of it.

Publishing grants no approval: the client is the evidence, and the user's review comes before the commit.
"""
import hashlib
import json
import math
import os
import re
import shutil
import struct
import subprocess
import tempfile
from pathlib import Path

import numpy as np

from . import logo, registry, seams, tables
from .registry import require

REPO = Path(__file__).resolve().parents[2]
PACK = 'srn_parts'
TABLE_PACK = 'srn_2da'
REGISTRY = Path('docs/armorkit/parts-registry.json')
HANDOFF = Path('docs/armorkit/parts-handoff.json')
COPIES = Path('docs/armorkit/parts-copies.json')  # the pack's copies list (tools/SrnHaks.Common.psm1, Get-SrnHakCopies)
COPIES_KIND = 'srn-hak-copies'
COPY_NAME = re.compile(r'[a-z0-9_]{1,16}\.[a-z0-9]{2,4}')  # a resource file name, as Get-SrnHakCopies holds both names of a copy to
HAKBUILDER = Path('hakbuilder.json')
PROVENANCE = Path('PROVENANCE.md')
TRIAL = 'armorkit-publish-trial.json'  # what marks a folder as a trial root: a trial is written nowhere else
TRIAL_MARK = {'schemaVersion': 1, 'kind': 'srn-armorkit-publish-trial'}
CLASH = ('srn_body', 'srn_armor')  # the packs no name of ours may be found in (docs/armorkit/plan.md, Gates)
BRIEFS = Path(__file__).with_name('briefs')
HANDOFF_KIND = registry.KIND + '-handoff'
TOKEN_SLOT = {token: slot for slot, row in registry.SLOTS.items() for token in row['tokens']}
UNREADABLE = (ValueError, OSError, LookupError, struct.error)  # what reading a model or a material file that is not one raises
TEXT = ('.mtr', '.2da', '.shd')  # stored with LF in the repository (.gitattributes): a carriage return would change on commit

# The neck: the body's own neck part stands in the chest's collar, and both are closed surfaces.
NECK_END = 0.01  # metres: the neck's lowest centimetre is its end, which the chest hides
NECK_TOP = 0.01  # and its highest centimetre is where the head sits, which the chest leaves free
NECK_THROUGH = 0.002  # a point of the neck this far outside the chest shows
NECK_NEAR = 0.06  # how far a point stands outside the chest is read up to this far
NECK_GRAIN = 0.004  # the neck's own surface is read at points this far apart: its model has a few dozen vertices

# Inventory icons: the game draws an armor's picture from one tint texture per gender for each of these slots,
# `ip<m|f>_<token><number>`, 64 by 128, shade 255 where nothing is drawn (the stock ones, read from the game).
ICON_SLOTS = ('chest', 'pelvis', 'belt', 'shoulder', 'robe')
ICON_SIZE = (64, 128)  # columns, rows; row 0 is the bottom one
ICON_SCALE = 100.0  # pixels a metre: the stock chest is 53 rows tall and 48 columns wide
ICON_WAIST = 62  # the row of the waist plane: stock pelvises end on row 61 and chests begin on row 62
ICON_OVER = 4  # each pixel is drawn this many times a side and the commonest layer taken
ICON_CLEAR = 255  # the shade of a pixel nothing is drawn on
ICON_BRIGHT = 240  # the brightest shade drawn (`texture.materials`: the very top of the range comes out black)
ICON_SOURCES = {'m': 'pmh0', 'f': 'pfh0'}  # the body each gender's icon is drawn from
ICON_CLIP = {'chest': (ICON_WAIST - 1, None), 'pelvis': (None, ICON_WAIST + 1)}  # rows kept: an end under another part is not drawn


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for piece in iter(lambda: stream.read(1 << 20), b''):
            digest.update(piece)
    return digest.hexdigest()


def failure(gate, model, reason):
    return {'gate': gate, 'model': model, 'reason': reason}


def counted(failures):
    """{gate: how many of the failures are its}, for a report's `failuresByGate`."""
    by_gate = {}
    for found in failures:
        by_gate[found['gate']] = by_gate.get(found['gate'], 0) + 1
    return by_gate


def icon_name(gender, token, number):
    name = f'ip{gender}_{token}{number:03d}'
    require(len(name) <= 16, 'An icon name exceeds 16 characters: ' + name)
    return name


def icon_names(part):
    """The icons a part needs: one per gender and side, none for a slot the game draws no icon of."""
    if part['slot'] not in ICON_SLOTS:
        return []
    return [icon_name(gender, token, part['number']) for gender in ICON_SOURCES for token in registry.tokens(part)]


# --- the bakes ----------------------------------------------------------------------------------------------------

def material_maps(text):
    """The maps a material file names (`texture1 <name>` and so on)."""
    return [line.split()[1] for line in text.splitlines() if line.startswith('texture') and len(line.split()) > 1]


def suggested(record, channels=None):
    """{channel: colour} a bake's record suggests an outfit is worn in: each material's `suggested` colour (its
    brief's) on both of the material's channels, kept to `channels` where given (a registry part's). A channel
    two materials suggest different colours for gets none.

    A brief's suggested colours stopped in `bake.json`: a registry was written by hand and nothing said its
    parts left them out (review of 2026-11-15)."""
    found = {}
    for material in record.get('materials', []):
        if 'suggested' in material:
            for channel in material.get('channels', []):
                found.setdefault(channel, []).append(list(material['suggested']))
    return {channel: colours[0] for channel, colours in sorted(found.items())
            if all(colour == colours[0] for colour in colours) and (channels is None or channel in channels)}


def coloured(document, records):
    """A registry document with each part's `colours` as the bakes of its number suggest them (`suggested`),
    and the (slot, number) of every part changed. A part no bake in `records` is of is left as it is; one its
    bakes suggest nothing for loses the colours it had, as the publication's gate asks; bakes that suggest
    different colours for one part are refused, by body."""
    wanted = {}
    for record in records:
        require(isinstance(record.get('models'), dict) and set(record['models']) <= set(TOKEN_SLOT) and 'number' in record,
                'A bake\'s record names its number and the model of each of its parts')
        for token in record['models']:
            wanted.setdefault((TOKEN_SLOT[token], record['number']), []).append(record)
    parts, changed = [], []
    for part in document['parts']:
        key = (part['slot'], part['number'])
        found = {}
        for record in wanted.get(key, []):
            found.setdefault(json.dumps(suggested(record, part['channels']), sort_keys=True), []).append(str(record.get('body')))
        require(len(found) <= 1, f'{key[0]} {key[1]}: its bakes suggest different colours: '
                + '; '.join(f'{", ".join(bodies)} {asked}' for asked, bodies in sorted(found.items())))
        asked = json.loads(next(iter(found))) if found else part.get('colours', {})
        if part.get('colours', {}) != asked:
            part = {**{name: value for name, value in part.items() if name != 'colours'}, **({'colours': asked} if asked else {})}
            changed.append(key)
        parts.append(part)
    return {**document, 'parts': parts}, changed


def shared_maps(surveyed, incoming, hashed=None):
    """(stands, texts, kept): the maps of a publication that are one image under several names, the material
    files rewritten to name the one map published for them, and whose copy that is.

    `incoming` maps each file name the publication takes to its path, `surveyed` are its bakes (`survey`,
    each with the names `taken` of it). Maps (`.tga`) of the same bytes are one map, published under a name
    that is no body's (`shared_name`: the part, the number, the kind of map and four digits of the image's
    hash, `bicepl6020n_3fa1`): `stands` maps each of the names it had to that one (without the ending), `texts`
    holds, by file name, the text of every taken material file that named one of them, naming the shared one
    instead, and `kept` maps the shared name to the one of the old names whose bake is recorded as holding
    it (the Human Fit body's before any other, then the first by name). A map only one model wears keeps
    that model's name. The first publication kept a shared map under the first body's name, so every male
    body's legs named `pfh0_*` maps and all 20 upper arms `pfd2_bicepl6020r` (review of PR 158; user
    decision 2026-11-15: fixed before the names are frozen). An outfit
    carried to the other bodies of a gender (`refit`) keeps its normal maps, so 10 of Facility Security's
    12 are the same image on ten bodies; a tint texture is never shared, the game colours a part only
    under its model's own name (user decision 2026-11-15)."""
    hashed = sha if hashed is None else hashed
    same = {}
    for name in sorted(incoming):
        if name.endswith('.tga'):
            same.setdefault(hashed(incoming[name]), []).append(name[:-4])
    # the first of each is the copy whose bake the shared map is recorded with: the Human Fit body's where it is among them
    same = {digest: sorted(names, key=lambda name: (name[2:4] != 'h0', name)) for digest, names in sorted(same.items()) if len(names) > 1}
    named = {}
    for digest, names in same.items():  # two maps of one part whose hashes begin alike: the later takes digits further along its hash
        named[digest] = next((name for name in (shared_name(names, digest[at:]) for at in range(0, len(digest) - 3, 4)) if name not in named.values()), None)
        require(named[digest] is not None, f'{names[0]} and the maps it is shared with have no name left: every part of their hash is taken')
    kept = {named[digest]: names[0] for digest, names in same.items()}
    stands = {name: named[digest] for digest, names in same.items() for name in names}
    texts = {}
    for bake in surveyed if stands else ():
        for name in sorted(bake.get('taken', ())):
            if not name.endswith('.mtr'):
                continue
            try:
                text = Path(bake['files'][name]).read_bytes().decode('ascii')
            except ValueError:
                continue  # `survey` has said so already
            lines = text.splitlines(keepends=True)
            for index, line in enumerate(lines):
                words = line.split()
                if line.startswith('texture') and len(words) > 1 and words[1] in stands:  # the lines `material_maps` reads
                    lines[index] = line.replace(words[1], stands[words[1]], 1)
            if ''.join(lines) != text:
                texts[name] = ''.join(lines)
    return stands, texts, kept


def shared_name(names, digest):
    """The name of a map several models wear: what the first of their names says after its body (`bicepl6020n`
    of `pfd0_bicepl6020n`; the first by name where the models are of several parts), and as many digits of
    the image's hash as a resource name of 16 characters leaves room for, four at most."""
    part = min(name[5:] if name[4:5] == '_' else name for name in names)
    room = min(4, 16 - len(part) - 1)
    require(room >= 2, f"{part} leaves no room in a resource name for a shared map's hash")
    return f'{part}_{digest[:room]}'


def copies(root):
    """{file name: the file of the pack it is a copy of} of the copies list under `root`; none without one.

    A tint texture is never shared by name (`shared_maps`), so a refit outfit's is one image under up to
    ten names. The pack's folder holds it once and the copies list names the others; `tools/Build-Haks.ps1`
    and `build` pack the held file under each (user decision 2026-11-15, after the storage study: 208 of
    Facility Security's 244 tint textures were copies, 254 MB of its 404). The handoff records every name.
    A list is held to what `Get-SrnHakCopies` holds it to, so that none is written or packed here that the
    repository's build refuses: both names are resource file names of one type, and no copy is a copy of a copy."""
    path = Path(root) / COPIES
    if not path.is_file():
        return {}
    held = json.loads(path.read_text(encoding='utf-8'))
    require(isinstance(held, dict) and held.get('kind') == COPIES_KIND and held.get('schemaVersion') == 1 and held.get('pack') == PACK
            and isinstance(held.get('copies'), dict) and all(isinstance(name, str) for name in held['copies'].values()),
            f'{path} is no copies list of {PACK}')
    for name, kept in held['copies'].items():
        require(COPY_NAME.fullmatch(name) and COPY_NAME.fullmatch(kept) and name.rpartition('.')[2] == kept.rpartition('.')[2] and kept not in held['copies'],
                f'{path} lists {name} as a copy of {kept}: both are resource file names of one type, and the file kept is no copy itself')
    return dict(held['copies'])


def tint_copies(hashes):
    """{file name: the name kept} of the tint textures in {file name: hash} that are one image under several
    names: the Human Fit body's is kept before any other, then the first by name (as `shared_maps` keeps a map)."""
    same = {}
    for name in sorted(hashes):
        if name.endswith('.plt'):
            same.setdefault(hashes[name], []).append(name)
    doubled = {}
    for names in same.values():
        names = sorted(names, key=lambda name: (name[2:4] != 'h0', name))
        doubled.update({name: names[0] for name in names[1:]})
    return doubled


def tint_channels(path):
    """The colour channels a tint texture's texels are on, by name (`export.LAYERS`; `layer N` for one that has none)."""
    from .export import LAYERS
    blob = Path(path).read_bytes()
    require(blob[:8] == b'PLT V1  ' and len(blob) >= 24, f'{Path(path).name} is no tint texture')
    count = int.from_bytes(blob[16:20], 'little') * int.from_bytes(blob[20:24], 'little')
    require(count and len(blob) >= 24 + 2 * count, f'{Path(path).name} is a tint texture cut short')
    names = {layer: name for name, layer in LAYERS.items()}
    return {names.get(layer, f'layer {layer}') for layer in set(blob[25:24 + 2 * count:2])}


def survey(folder):
    """One bake's output folder as a publication reads it: its record, the files of each of its models and what
    is wrong with it, as (model, reason) pairs. A folder that is no bake at all is refused.

    A drawn piece (`brassard`; its record says `drawn`) is made from no brief, and its tint texture has no
    material file. A piece that shows a logo (its record's `logo`) brings the logo's files, `logo.FILES`, and
    is refused when it was drawn for another strip than the kit's own: SR_NWN stores the cells."""
    folder = Path(folder)
    path = folder / 'bake.json'
    require(path.is_file(), f'{folder} holds no bake: it has no bake.json')
    record = json.loads(path.read_text(encoding='utf-8'))
    require(isinstance(record, dict) and isinstance(record.get('models'), dict) and record['models']
            and isinstance(record.get('model'), str) and record.get('body') in registry.BODIES and type(record.get('number')) is int
            and isinstance(record.get('gates'), dict), f'{path} is no bake record')
    body, number, resources = record['body'], record['number'], folder / 'resources'
    files, wrong = {}, []
    drawn = record.get('drawn') is True  # said, not guessed: an outfit's record that lost its materials is still held to its brief
    if 'logo' in record:
        if record['logo'] != logo.record():
            wrong.append((f'{body} {record["model"]}', 'it was drawn for another logo strip than the kit\'s: draw it again'))
        for name in logo.FILES:
            if not (resources / name).is_file():
                wrong.append((f'{body} {record["model"]}', f'the bake holds no {name}'))
            else:
                files[name] = resources / name
    if not record['gates'].get('passed'):
        wrong.append((f'{body} {record["model"]}', 'its bake did not pass its own gates: ' + '; '.join(record['gates'].get('failures', []))[:400]))
    if record.get('compiled') != len(record['models']):
        wrong.append((f'{body} {record["model"]}', 'its models were not compiled: bake it with --nwn-root'))
    for token, model in record['models'].items():
        require(token in TOKEN_SLOT and model == registry.model_name(body, token, number), f'{path}: {model} is not the model of {token} {number} on {body}')
        names = [model + '.mdl', model + '.plt'] + ([] if drawn else [model + '.mtr'])
        material = resources / (model + '.mtr')
        if material.is_file():
            try:
                names += [name + '.tga' for name in material_maps(material.read_text(encoding='ascii'))]
            except ValueError:
                wrong.append((model, 'its material file is not ASCII text'))
        for name in names:
            if not (resources / name).is_file():
                wrong.append((model, f'the bake holds no {name}'))
            else:
                files[name] = resources / name
        compiled = resources / (model + '.mdl')
        if compiled.is_file():
            with compiled.open('rb') as stream:
                if stream.read(4) != bytes(4):
                    wrong.append((model, 'the model is not compiled'))
    return {'folder': folder, 'record': record, 'sha256': sha(path), 'files': files, 'wrong': wrong, 'drawn': drawn}


def brief_of(model, given, folder=BRIEFS):
    """The brief file of a bake's model: the one given for it, or the only one of that model in the briefs folder."""
    if model in given:
        path = Path(given[model])
        require(path.is_file(), f'{path} is no brief file')
        require(json.loads(path.read_text(encoding='utf-8')).get('model') == model, f'{path} is not the brief of {model}')
        return path
    read = ((path, json.loads(path.read_text(encoding='utf-8'))) for path in sorted(Path(folder).glob('*.json')))
    found = [path for path, document in read if isinstance(document, dict) and document.get('model') == model]
    require(len(found) < 2, f'{len(found)} briefs are of the model {model}: name the one the outfit was baked from (--brief {model}=FILE)')
    return found[0] if found else None


# --- the tables ---------------------------------------------------------------------------------------------------

def merged(parts, stock, existing):
    """{table: text} of every parts table that has a live row or is already in `existing`, the pack's folder.

    Each is made from the game's own table in `stock` and the registry (`tables.generate`), checked against both
    (`tables.check`: no gap, no duplicate, stock rows unchanged) and against the table already there (`kept`).
    The text has the line ends the pack's tables are stored with."""
    made = {}
    for table in registry.TABLES:
        there = Path(existing) / (table + '.2da')
        if not registry.numbers(parts, tables.TABLE_SLOT[table]) and not there.is_file():
            continue
        source = Path(stock) / (table + '.2da')
        require(source.is_file(), f'{stock} holds no {table}.2da: --stock is the folder of the game\'s own parts tables')
        stock_text = source.read_bytes().decode('cp1252')
        text = tables.generate(table, stock_text, parts)
        tables.check(table, text, parts, stock_text)
        if there.is_file():
            kept(table, there.read_bytes().decode('cp1252'), text)
        made[table] = text.replace('\r\n', '\n')
    return made


def kept(table, before, after):
    """Fail unless every row of the table as it was is in the new one unchanged; a padding row may become live."""
    columns, rows = tables.parse(before)
    new_columns, new_rows = tables.parse(after)
    require(columns == new_columns, f'{table}: the column row would change')
    require(len(new_rows) >= len(rows), f'{table}: the table would lose rows {len(new_rows)} to {len(rows) - 1}')
    for number, row in enumerate(rows):
        require(row == new_rows[number] or all(cell == tables.PADDING for cell in row),
                f'{table}: row {number} would change from {" ".join(row)} to {" ".join(new_rows[number])}')


def live(table, text, part, parsed=None):
    """Whether the table's row for a part is the live row the registry implies. `parsed`, a dictionary, keeps
    each table's parsed rows between calls."""
    if parsed is None or table not in parsed:
        held = tables.parse(text)
        if parsed is not None:
            parsed[table] = held
    columns, rows = held if parsed is None else parsed[table]
    return part['number'] < len(rows) and rows[part['number']] == tables.live_row(columns, part)


# --- the neck -----------------------------------------------------------------------------------------------------

def turn(axis, degrees):
    """The rotation by `degrees` about a unit `axis`."""
    x, y, z = axis
    cross = np.array([[0.0, -z, y], [z, 0.0, -x], [-y, x, 0.0]])
    angle = math.radians(degrees)
    return np.eye(3) + math.sin(angle) * cross + (1 - math.cos(angle)) * cross @ cross


def apart(points, corners):
    """Per point and triangle, the distance from the point to the triangle: (points, n) for `corners`, (n, 3, 3)."""
    a, b, c = corners[None, :, 0], corners[None, :, 1], corners[None, :, 2]
    p = points[:, None]
    normal = np.cross(b - a, c - a)
    size = np.linalg.norm(normal, axis=2)
    normal = normal / np.maximum(size, 1e-30)[..., None]
    off = np.einsum('pfi,pfi->pf', p - a, normal)
    foot = p - off[..., None] * normal
    within = np.ones(off.shape, bool)
    least = np.full(off.shape, np.inf)
    for start, end in ((a, b), (b, c), (c, a)):
        along = end - start
        within &= np.einsum('pfi,pfi->pf', np.cross(along, foot - start), normal) >= 0
        share = np.clip(np.einsum('pfi,pfi->pf', p - start, along) / np.maximum(np.einsum('pfi,pfi->pf', along, along), 1e-30), 0.0, 1.0)
        least = np.minimum(least, np.linalg.norm(p - (start + share[..., None] * along), axis=2))
    return np.where(within & (size > 1e-18), np.abs(off), least)


def away(points, corners):
    """Per point, its distance to the nearest of the triangles `corners`, (n, 3, 3)."""
    return apart(points, corners).min(axis=1)


def unjoined(points, shown, top, grain):
    """Which of `points` show (`shown`) and are joined to none of those in `top` through points that show: the
    points are sorted into cells two grains a side, and a cell is joined to the 26 round it."""
    cells = np.floor(points[shown] / (2 * grain)).astype(np.int64)
    held = {tuple(cell) for cell in cells.tolist()}
    reached = {tuple(cell) for cell in cells[top[shown]].tolist()}
    edge = list(reached)
    steps = [(i, j, k) for i in (-1, 0, 1) for j in (-1, 0, 1) for k in (-1, 0, 1) if (i, j, k) != (0, 0, 0)]
    while edge:
        x, y, z = edge.pop()
        for i, j, k in steps:
            beside = (x + i, y + j, z + k)
            if beside in held and beside not in reached:
                reached.add(beside)
                edge.append(beside)
    out = np.zeros(len(points), bool)
    out[np.flatnonzero(shown)] = [tuple(cell) not in reached for cell in cells.tolist()]
    return out


def outside(points, surface, near=NECK_NEAR):
    """Per point, how far it stands outside a closed surface, 0 inside it and `near` at most: inside is a winding
    number of half a turn or more (`measure.winding`), asked only of the points within the surface's bounds."""
    from . import measure
    vertices, faces = np.asarray(surface[0], float), np.asarray(surface[1], int)
    points = np.asarray(points, float)
    apart = np.ones(len(points), bool)
    bounded = (points >= vertices.min(axis=0)).all(axis=1) & (points <= vertices.max(axis=0)).all(axis=1)
    if bounded.any():
        apart[bounded] = np.abs(measure.winding(points[bounded], vertices, faces)) < 0.5
    out = np.zeros(len(points))
    if apart.any():
        out[apart] = near
        corners = vertices[faces]
        low, high = points[apart].min(axis=0) - near, points[apart].max(axis=0) + near
        corners = corners[(corners.max(axis=1) >= low).all(axis=1) & (corners.min(axis=1) <= high).all(axis=1)]
        if len(corners):
            rows = np.flatnonzero(apart)
            step = max(1, 200000 // len(corners))
            for start in range(0, len(rows), step):
                out[rows[start:start + step]] = np.minimum(away(points[rows[start:start + step]], corners), near)
    return out


def neck(chest, own, point, normal, bend=None, ends=seams.ENDS, grain=NECK_GRAIN):
    """How a chest closes round the body's own neck part: (measure, reasons it fails).

    The body's neck is a closed part that stands in the chest and comes out of it, and so does an outfit's
    chest: there is no hole to measure, and a plane section there cuts the torso wall (`measure.clearance`).
    What can go wrong is told on the neck's own points instead, each read against the chest's surface
    (`outside`):

    * the neck's lower end, its lowest centimetre, lies inside the chest as the body stands, no more than the
      contract's `rest` outside it, and no more than its `bent` outside with the neck turned forward, back and
      to either side by `bend` degrees, the contract's design bend, and by half of it (a neck that ends above a
      low collar shows its round end, and the hollow of the chest under it);
    * the neck shows above the collar and nowhere else: a point that stands out of the chest and is joined to
      the neck's top by no other such points is skin come through the collar's cloth;
    * the neck's top centimetre, where the head sits, stands clear of the chest.

    `chest` and `own` are (vertices, faces) in body space, `point` and `normal` the neck joint's plane. The
    neck's surface is read at points `grain` apart. The measure holds the most the end stands out at rest
    (`rest`) and turned (`bent`, None without a bend), the share of the neck that shows (`shown`), the share
    through the collar and the most it stands out (`through`), and how high above the plane the chest still
    covers the neck (`collar`)."""
    points = seams.surface_points(np.asarray(own[0], float), np.asarray(own[1], int), grain)
    point, normal = np.asarray(point, float), seams.unit(normal)
    height = (points - point) @ normal
    out = outside(points, chest)
    end, top = height <= height.min() + NECK_END, height >= height.max() - NECK_TOP
    reasons, rest, bent = [], float(out[end].max()), None
    if rest > ends['rest']:
        reasons.append(f'the lower end of the neck stands {rest * 100:.1f} cm out of the chest at rest, over the {ends["rest"] * 100:.1f} cm allowed')
    if bend is not None:
        forward = seams.unit(np.array((0.0, 1.0, 0.0)) - normal[1] * normal)
        axes = (np.cross(normal, forward), forward)
        bent = max(float(outside((points[end] - point) @ turn(axis, sign * share * bend).T + point, chest).max())
                   for axis in axes for sign in (1.0, -1.0) for share in (0.5, 1.0))
        if bent > ends['bent']:
            reasons.append(f'the lower end of the neck stands {bent * 100:.1f} cm out of the chest turned {bend:g} degrees, over the {ends["bent"] * 100:.1f} cm allowed')
    shown = out > NECK_THROUGH
    collar = float(height[~shown].max()) if (~shown).any() else None
    if (~shown[top]).any():
        reasons.append('the chest closes over the top of the neck, where the head sits')
    through = unjoined(points, shown, top, grain)  # what shows and is joined to the neck's top is the neck above the collar
    if through.any():
        reasons.append(f'the neck shows through the chest below its collar: {through.mean() * 100:.1f}% of its surface, up to {out[through].max() * 1000:.0f} mm out, '
                       f'{height[through].min() * 100:.1f} to {height[through].max() * 100:.1f} cm from the neck plane')
    return {'rest': round(rest, 4), 'bent': None if bent is None else round(bent, 4), 'collar': None if collar is None else round(collar, 4),
            'shown': round(float(shown.mean()), 3),
            'through': {'share': round(float(through.mean()), 4), 'most': round(float(out[through].max()), 4) if through.any() else 0.0}}, reasons


def chest_neck(pack, body_pack, body, model, contract=None):
    """`neck` of one chest model of the pack on its body: the body's own neck part and rig come from `body_pack`,
    the design bend from the seam contract, for a body it holds one for."""
    from . import measure
    contract = seams.load_contract() if contract is None else contract
    bones, parts = measure.body(body_pack, body)
    require('neck' in parts, f'{body_pack} holds no neck part of {body}')
    path = Path(pack[model + '.mdl'])
    point, normal = seams.plane(bones, 'neck', 'c')
    held = contract['joints']['neck']['bodies'].get(body)
    bend = held['bend'][contract['designBend']] if held else None
    return neck(measure.mesh(path.read_bytes(), model, bones[seams.BONES['chest']]), parts['neck'], point, normal, bend,
                {**seams.ENDS, **contract.get('ends', {})})


def model_textures(path, read_back=None):
    """The textures a compiled model's meshes name. A model the kit's rigid reader refuses (headgear's skin, bound
    to the head) is read back by the model tool (`export.decompiled`, or `read_back`) for its `bitmap` lines; one
    the tool cannot read either is refused."""
    from tools.headkit import native_reader
    path = Path(path)
    try:
        meshes = native_reader.decode(path.read_bytes(), path.stem, require_tangents=False)
        first = [(mesh.get('textures') or [''])[0] or '' for mesh in meshes]
    except ValueError:
        if read_back is None:
            from .export import decompiled as read_back
        first = re.findall(r'^\s*bitmap\s+(\S+)', read_back(path), re.M)
    return sorted({name.lower() for name in first if name and name.lower() != 'null'})


# --- the icons ----------------------------------------------------------------------------------------------------

def icon(meshes, waist, rows=(None, None)):
    """(shades, layers) of an inventory icon: the meshes seen from the front, each pixel the tint texel nearest
    the eye. `meshes` are (vertices in body space, faces, texture coordinates, shades, layers) each, `waist`
    the height of the body's waist plane, which lies on row `ICON_WAIST`; +X, the body's left, is the right of
    the picture. `rows` keeps only the rows from the first to the second. Each pixel is drawn `ICON_OVER`
    times a side: one drawn on less than half is left clear, and the others take their commonest layer and its
    mean shade."""
    over = ICON_OVER
    width, tall = ICON_SIZE[0] * over, ICON_SIZE[1] * over
    depth = np.full((tall, width), -np.inf)
    shade, layer = np.zeros((tall, width), np.uint8), np.zeros((tall, width), np.uint8)
    for vertices, faces, uvs, shades, layers in meshes:
        vertices, uvs, shades, layers = np.asarray(vertices, float), np.asarray(uvs, float), np.asarray(shades), np.asarray(layers)
        size = np.array(shades.shape[::-1])
        x = width / 2 + vertices[:, 0] * ICON_SCALE * over
        y = (ICON_WAIST + (vertices[:, 2] - waist) * ICON_SCALE) * over
        for a, b, c in np.asarray(faces, int):
            xs, ys = x[[a, b, c]], y[[a, b, c]]
            left, right = max(int(math.floor(xs.min())), 0), min(int(math.ceil(xs.max())), width - 1)
            low, high = max(int(math.floor(ys.min())), 0), min(int(math.ceil(ys.max())), tall - 1)
            area = (xs[1] - xs[0]) * (ys[2] - ys[0]) - (xs[2] - xs[0]) * (ys[1] - ys[0])
            if left > right or low > high or abs(area) < 1e-12:
                continue
            px, py = np.meshgrid(np.arange(left, right + 1) + 0.5, np.arange(low, high + 1) + 0.5)
            w0 = ((xs[1] - px) * (ys[2] - py) - (xs[2] - px) * (ys[1] - py)) / area
            w1 = ((xs[2] - px) * (ys[0] - py) - (xs[0] - px) * (ys[2] - py)) / area
            w2 = 1 - w0 - w1
            near = w0 * vertices[a, 1] + w1 * vertices[b, 1] + w2 * vertices[c, 1]
            window = depth[low:high + 1, left:right + 1]
            hit = (w0 >= 0) & (w1 >= 0) & (w2 >= 0) & (near > window)
            if not hit.any():
                continue
            texel = (w0[hit, None] * uvs[a] + w1[hit, None] * uvs[b] + w2[hit, None] * uvs[c]) * size
            column, row = (np.clip(np.floor(texel[:, k]).astype(int), 0, size[k] - 1) for k in (0, 1))
            window[hit] = near[hit]
            shade[low:high + 1, left:right + 1][hit] = shades[row, column]
            layer[low:high + 1, left:right + 1][hit] = layers[row, column]
    drawn = np.isfinite(depth)
    blocks = lambda image: image.reshape(ICON_SIZE[1], over, ICON_SIZE[0], over).swapaxes(1, 2).reshape(ICON_SIZE[1], ICON_SIZE[0], over * over)
    drawn, shade, layer = blocks(drawn), blocks(shade), blocks(layer)
    shades, layers = np.full(ICON_SIZE[::-1], ICON_CLEAR, np.uint8), np.zeros(ICON_SIZE[::-1], np.uint8)
    first, last = (0 if rows[0] is None else max(rows[0], 0)), (ICON_SIZE[1] - 1 if rows[1] is None else min(rows[1], ICON_SIZE[1] - 1))
    for row, column in zip(*np.nonzero(drawn.sum(axis=2) * 2 >= over * over)):
        if not first <= row <= last:
            continue
        found = layer[row, column][drawn[row, column]]
        values, counts = np.unique(found, return_counts=True)
        layers[row, column] = values[counts.argmax()]
        shades[row, column] = min(int(round(shade[row, column][drawn[row, column]][found == layers[row, column]].mean())), ICON_BRIGHT)
    return shades, layers


def icons(parts, pack, body_pack):
    """{file name: bytes} of the icons the Human Fit models in `pack` give: for each part in an icon slot and
    each gender whose Human Fit model is there, `ip<m|f>_<token><number>.plt`, drawn from that model and its
    tint texture (`icon`)."""
    from tools.headkit import native_reader
    from . import export, measure
    made, rigs = {}, {}
    for part in parts:
        if part['slot'] not in ICON_SLOTS:
            continue
        for gender, body in ICON_SOURCES.items():
            for token in registry.tokens(part):
                model = registry.model_name(body, token, part['number'])
                if model + '.mdl' not in pack or model + '.plt' not in pack:
                    continue
                if body not in rigs:
                    rigs[body] = measure.rig((Path(body_pack) / (body + '.mdl')).read_bytes())
                bone = rigs[body][seams.BONES[token]] if token in seams.BONES else np.eye(4)  # a robe has no bone of its own: it is in body space
                shades, layers = export.read_tint(Path(pack[model + '.plt']).read_bytes())
                meshes = native_reader.decode(Path(pack[model + '.mdl']).read_bytes(), model, require_tangents=False, apply_rigid_transforms=True)
                drawn = [(mesh['position'] @ bone[:3, :3].T + bone[:3, 3], mesh['faces'].astype(int), mesh['uv'], shades, layers) for mesh in meshes
                         if ((mesh.get('textures') or [''])[0] or '').lower() != logo.STRIP]  # a badge is on the logo strip, not on the tint texture
                waist = rigs[body][seams.JOINTS['waist']['centre']][2, 3]
                made[icon_name(gender, token, part['number']) + '.plt'] = export.tint(*icon(drawn, waist, ICON_CLIP.get(part['slot'], (None, None))))
    return made


# --- the gates ----------------------------------------------------------------------------------------------------

def gates(parts, pack, table_texts, body_pack, clash=(), textures=model_textures, measure_neck=chest_neck, necks=None, fresh=None, plain=()):
    """The publication gates on a pack as it would stand: a list of failures, each with its gate, the model and
    the reason (docs/armorkit/plan.md, Gates).

    `parts` is the whole registry, `pack` maps each file name of the pack to the file it is read from, and
    `table_texts` each parts table to its text.

    * `bodies`: every body a part lists has the part's models in the pack.
    * `tables`: every part has its live row in its table (`live`).
    * `closure`: every texture a model names is in the pack as a tint texture, with its material file, and so is
      each map that file names. A model names the tint texture of its own name and no other: the game colours
      an armor part's texture only under the model's name (user, 2026-11-14), so every body carries its own.
      A part with a badge names the logo strip as well, on its badge, and then the pack holds the logo's files
      (`logo.FILES`); it must name it, and no other part may. A model in `plain`, a drawn piece's, has a tint
      texture without a material file.
    * `clash`: no file of the pack is one a pack in `clash` holds.
    * `neck`: each chest closes round its body's neck (`neck`); `necks`, a dictionary, is given each chest's measure.
      With `fresh`, the file names that are new, only the chests among them are measured and only the models
      among them read for the textures they name: a published model passed when it was published, names its
      own texture, and is held to the hash recorded then (`publish`).
    * `icons`: each part in an icon slot has its icons (`icon_names`).
    * `unlisted`: every file of the pack belongs to a part of the registry.
    * `format`: a name of the pack is a lowercase resource name of at most 16 characters, and a text file holds
      no carriage return, which the repository would take out."""
    failures, listed, parsed = [], set(), {}
    clash = [Path(folder) for folder in clash]
    for part in parts:
        label = f'{part["slot"]} {part["number"]}'
        table = registry.SLOTS[part['slot']]['table']
        if table not in table_texts or not live(table, table_texts[table], part, parsed):
            failures.append(failure('tables', label, f'{table}.2da has no live row {part["number"]}'))
        for body, models in registry.model_names(part).items():
            for model in models:
                if model + '.mdl' not in pack:
                    failures.append(failure('bodies', model, f'{body} has no model of {label}: bake or refit the outfit on that body'))
                    continue
                listed.add(model + '.mdl')
                try:
                    named = textures(pack[model + '.mdl']) if fresh is None or model + '.mdl' in fresh else [model]
                except UNREADABLE as error:
                    failures.append(failure('closure', model, f'the model could not be read: {error}'))
                    continue
                if not named:
                    failures.append(failure('closure', model, 'the model names no texture'))
                read = fresh is None or model + '.mdl' in fresh
                if part['badge'] and read and logo.STRIP not in named:
                    failures.append(failure('closure', model, f'{label} has a badge and the model has no mesh on the logo strip {logo.STRIP}'))
                for texture in named:
                    if texture == logo.STRIP and part['badge']:
                        failures += [failure('closure', model, f'its badge is on the logo strip, and the pack holds no {name}') for name in logo.FILES if name not in pack]
                        continue
                    if texture != model:
                        failures.append(failure('closure', model, f'it names the texture {texture}, not its own: the game colours a part\'s tint texture only under the model\'s name'))
                    for name in (texture + '.plt', texture + '.mtr'):
                        # a drawn piece has no material file, and a published model is held to its recorded files (`published`)
                        if name.endswith('.mtr') and name not in pack and (model in plain or not read):
                            continue
                        listed.add(name)
                        if name not in pack:
                            failures.append(failure('closure', model, f'it names {texture}, and the pack holds no {name}'))
                    if texture + '.mtr' in pack:
                        try:
                            images = material_maps(Path(pack[texture + '.mtr']).read_text(encoding='ascii'))
                        except UNREADABLE:
                            images = []
                            failures.append(failure('closure', model, f'its material file {texture}.mtr is not ASCII text'))
                        for image in images:
                            listed.add(image + '.tga')
                            if image + '.tga' not in pack:
                                failures.append(failure('closure', model, f'its material file names {image}, and the pack holds no {image}.tga'))
                if part['slot'] == 'chest' and (fresh is None or model + '.mdl' in fresh):
                    try:
                        measured, reasons = measure_neck(pack, body_pack, body, model)
                    except UNREADABLE as error:
                        measured, reasons = None, [f'the neck could not be measured: {error}']
                    failures += [failure('neck', model, reason) for reason in reasons]
                    if necks is not None:
                        necks[model] = measured
        for name in icon_names(part):
            listed.add(name + '.plt')
            if name + '.plt' not in pack:
                failures.append(failure('icons', name, f'{label} has no inventory icon {name}.plt'))
    if any(part['badge'] for part in parts):
        listed.update(logo.FILES)
    for name in sorted(pack):
        stem, _, suffix = name.rpartition('.')
        if name != name.lower() or not stem or len(stem) > 16 or not all(letter.isalnum() or letter == '_' for letter in stem):
            failures.append(failure('format', name, 'not a lowercase resource name of at most 16 characters'))
        if name not in listed:
            failures.append(failure('unlisted', name, 'no part of the registry has this file'))
        for folder in clash:
            if (folder / name).is_file():
                failures.append(failure('clash', name, f'{folder.name} holds a file of that name'))
        if '.' + suffix in TEXT and b'\r' in Path(pack[name]).read_bytes():
            failures.append(failure('format', name, 'a text file with carriage returns, which the repository stores without'))
    return failures


# --- a publication ------------------------------------------------------------------------------------------------

def published(root):
    """(parts, handoff) already published under `root`: none and an empty handoff before the first publication."""
    path = Path(root) / REGISTRY
    if not path.is_file():
        return [], {'outfits': []}
    parts = registry.load(path, publish=True)
    handoff = Path(root) / HANDOFF
    require(handoff.is_file(), f'{path} is published without {HANDOFF.name}: the handoff holds what was published and its hashes, and is not made again')
    held = json.loads(handoff.read_text(encoding='utf-8'))
    files = [resource for outfit in held.get('outfits', []) if isinstance(outfit, dict) for resource in outfit.get('resources', [])] if isinstance(held, dict) else []
    require(isinstance(held, dict) and held.get('kind') == HANDOFF_KIND and isinstance(held.get('outfits'), list) and isinstance(held.get('iconFiles', []), list)
            and all(isinstance(outfit, dict) for outfit in held['outfits'])
            and all(isinstance(one, dict) and isinstance(one.get('name'), str) and isinstance(one.get('sha256'), str) for one in files + held.get('iconFiles', [])),
            f'{handoff} is no parts handoff: it names the files published and their hashes')
    return parts, held


def seed(root, repo=REPO):
    """Make `root` a trial root: marked as one, with the repository's own tables, parts pack and records copied
    in where it has none, so that a trial stands on what is published. The repository is never a trial root."""
    root, repo = Path(root).resolve(), Path(repo).resolve()
    require((root != repo and repo not in root.parents) or (repo / 'output') in root.parents or (repo / '.tmp') in root.parents,
            f'A trial is written to a scratch folder, outside the repository or under its ignored output or .tmp folder: {root}')
    require(not root.is_file(), f'{root} is a file, not a folder for a trial')
    require(not root.exists() or (root / TRIAL).is_file() or not any(root.iterdir()), f'{root} is not empty and is no trial root')
    require(not (root / TRIAL).is_file() or not json.loads((root / TRIAL).read_text(encoding='utf-8')).get('written'),
            f'{root} holds a trial publication already, and a second would read its parts as published: write the trial to a new folder')
    root.mkdir(parents=True, exist_ok=True)
    (root / TRIAL).write_text(json.dumps(TRIAL_MARK) + '\n', encoding='utf-8')
    for pack in (TABLE_PACK, PACK):
        if not (root / pack).is_dir() and (repo / pack).is_dir():
            shutil.copytree(repo / pack, root / pack)
    for record in (REGISTRY, HANDOFF, COPIES):
        if not (root / record).is_file() and (repo / record).is_file():
            (root / record).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(repo / record, root / record)
    return root


def registered(text, copied=False):
    """`hakbuilder.json`'s text with the `srn_parts` pack in its list, after `srn_armor`, and with `copied` its
    entry naming the copies list; unchanged if it is all there."""
    document = json.loads(text)
    require(json.dumps(document, indent=2) + '\n' == text, 'hakbuilder.json is not in the indent-2 form this command rewrites')
    names = [pack['Name'] for pack in document['HakList']]
    if PACK not in names:
        at = names.index('srn_armor') + 1 if 'srn_armor' in names else len(names)
        document['HakList'].insert(at, {'Name': PACK, 'Path': f'./{PACK}/', 'CompileModels': False})
    entry = next(pack for pack in document['HakList'] if pack['Name'] == PACK)
    if copied:
        entry.setdefault('Copies', './' + COPIES.as_posix())
    return json.dumps(document, indent=2) + '\n'


def build(root, packs=(PACK, TABLE_PACK), repo=REPO):
    """Pack a trial root's folders into `<root>/output/<pack>.hak` with the pinned archive tool, as
    `tools/Build-Haks.ps1` packs the repository's, and read each back: {pack: {resources, sha256, path}}."""
    from tools import shared_tools
    tool = shared_tools.resolve_tool('erf', repo)['path']
    root, built = Path(root), {}
    (root / 'output').mkdir(exist_ok=True)
    for pack in packs:
        source, target = root / pack, root / 'output' / (pack + '.hak')
        require(source.is_dir(), f'{root} has no {pack} folder to pack')
        target.unlink(missing_ok=True)
        listed = copies(root) if pack == PACK else {}
        stage = root / 'output' / f'.copies-{pack}'  # hard links to the held files, each under its copy's name
        shutil.rmtree(stage, ignore_errors=True)
        try:
            if listed:
                stage.mkdir()
                for name, held in listed.items():
                    require((source / held).is_file() and not (source / name).exists(), f'{name} is listed as a copy of {held}: the pack must hold {held} and no {name}')
                    try:
                        os.link(source / held, stage / name)
                    except OSError:
                        shutil.copyfile(source / held, stage / name)
            done = subprocess.run([tool, '-f', str(target), '--no-symlinks', '-c', str(source)] + ([str(stage)] if listed else []), capture_output=True, text=True)
        finally:
            shutil.rmtree(stage, ignore_errors=True)
        require(done.returncode == 0 and target.is_file(), f'{pack}.hak was not built: {done.stdout[-1000:]}{done.stderr[-1000:]}')
        listing = subprocess.run([tool, '-f', str(target), '-t'], capture_output=True, text=True)
        require(listing.returncode == 0, f'{pack}.hak could not be read back')
        expected = sorted([path.name for path in source.iterdir() if path.is_file()] + list(listed))
        require(sorted(line.strip() for line in listing.stdout.splitlines() if line.strip()) == expected,
                f'{pack}.hak does not hold exactly the files of its folder')
        built[pack] = {'resources': len(expected), 'sha256': sha(target), 'path': str(target)}
    return built


def publish(registry_path, bakes, stock, *, records=(), briefs=(), root=None, trial=False, dry_run=False, body_pack=None,
            repo=REPO, textures=model_textures, measure_neck=chest_neck, draw_icons=icons, channels=tint_channels):
    """Publish the bakes in `bakes` under the registry at `registry_path`: the report.

    `root` is the tree written to, the repository unless `trial` names a scratch root (`seed`). `records` are
    (model, file) pairs of history to pin and `briefs` (model, file) pairs naming a brief where the briefs
    folder does not tell. Everything is read and every gate run before the first write; the repository is
    written only when all pass, a trial root whatever they say, and nothing with `dry_run`. The report holds
    the failures, a count of them by gate, the neck measures and, once written, the files."""
    repo = Path(repo).resolve()
    require(not (trial and dry_run), 'A trial writes its scratch root; a dry run writes nothing: ask for one of them')
    require(trial or root is None, 'A root is a trial\'s scratch folder: pass trial=True with it, or no root to publish into the repository')
    parts = registry.load(registry_path, publish=True)
    surveyed = [survey(folder) for folder in bakes]
    require(surveyed, 'A publication needs at least one bake (--bake DIR)')
    root = seed(root, repo) if trial else repo
    body_pack = Path(body_pack) if body_pack else repo / 'srn_body'
    before, handoff_before = published(root)
    known = {(part['slot'], part['number']): part for part in before}
    now = {(part['slot'], part['number']): part for part in parts}
    for key, part in known.items():
        require(now.get(key) == part, f'{key[0]} {key[1]} is published and may not change or leave the registry')
    new = [part for key, part in now.items() if key not in known]
    require(new, 'The registry holds no part that is not published already')

    pack_folder = root / PACK
    pack = {path.name: path for path in pack_folder.iterdir() if path.is_file()} if pack_folder.is_dir() else {}
    failures, incoming, outfits = [], {}, []
    # A copy the pack leaves out is read from the file it is a copy of (`copies`), and held to its own recorded hash.
    listed = copies(root)
    for name, held in sorted(listed.items()):
        if name in pack:
            failures.append(failure('published', name, f'{PACK} holds this file, and its copies list names it as a copy of {held}'))
        elif held not in pack:  # `copies` has refused a list whose kept file is itself a copy
            failures.append(failure('published', name, f'the copies list names it as a copy of {held}, which {PACK} does not hold'))
    pack.update({name: pack[held] for name, held in listed.items() if name not in pack and held in pack})
    # What is published is what its handoff recorded: a file changed or gone since fails by name.
    recorded = [resource for outfit in handoff_before.get('outfits', []) for resource in outfit.get('resources', [])]
    hashed = {}

    def once(path):  # a file's hash, taken once however many names or bodies share the file
        if path not in hashed:
            hashed[path] = sha(path)
        return hashed[path]
    for resource in recorded + handoff_before.get('iconFiles', []):
        if resource['name'] not in pack:
            failures.append(failure('published', resource['name'], f'{PACK} no longer holds this published file'))
        elif once(pack[resource['name']]) != resource['sha256']:
            failures.append(failure('published', resource['name'], f'{PACK} holds another file than the one published: its hash is not the one the handoff records'))
    # And nothing else is in the pack: a file staged there by hand would stand for a model with no bake, no
    # neck measure and no hash.
    held = {resource['name'] for resource in recorded + handoff_before.get('iconFiles', [])}
    failures += [failure('published', name, f'{PACK} holds this file and its handoff records no publication of it: a new part comes from a bake')
                 for name in sorted(pack) if name not in held]
    given_records, given_briefs = {}, dict(briefs)
    for model, path in records:
        require(Path(path).is_file(), f'{path} is no file to record for {model}')
        given_records.setdefault(model, []).append(Path(path))
    wanted = {model: (part, body) for part in new for body, models in registry.model_names(part).items() for model in models}
    found_briefs, miscoloured = {}, set()
    for bake in surveyed:
        record = bake['record']
        label = f'{record["body"]} {record["model"]}'
        failures += [failure('bake', model, reason) for model, reason in bake['wrong']]
        for token, model in record['models'].items():
            if model not in wanted:
                failures.append(failure('bake', model, f'the registry has no new part {TOKEN_SLOT[token]} {record["number"]} on {record["body"]} with that side: '
                                                       'bake the outfit at its registry number, and list the slot'))
                continue
            # The bake shaped and gated the part's ends at its own tier; the registry's tiers decide what it mixes with.
            other = {joint: tier for joint, tier in wanted[model][0]['tiers'].items() if tier != record.get('tier')}
            if other:
                failures.append(failure('bake', model, f'it was baked at tier {record.get("tier")} and the registry gives {TOKEN_SLOT[token]} {record["number"]} '
                                                       + ', '.join(f'{joint} tier {tier}' for joint, tier in sorted(other.items()))))
        for slot, number in sorted({(TOKEN_SLOT[token], record['number']) for token, model in record['models'].items() if model in wanted}):
            entry = now[(slot, number)]
            asked = suggested(record, entry['channels'])
            said = (slot, number, json.dumps(asked, sort_keys=True))  # once for a part, however many bodies' bakes suggest the same
            if asked != entry.get('colours', {}) and said not in miscoloured:
                miscoloured.add(said)
                failures.append(failure('colours', f'{slot} {number}', f'the bake of {record["body"]} suggests {json.dumps(asked, sort_keys=True)} and the registry gives '
                                        f'{json.dumps(entry.get("colours", {}), sort_keys=True)}: write the bakes\' colours into it (registry FILE --colours-from BAKE)'))
        for name, path in bake['files'].items():
            if name in logo.FILES and (name in pack or name in incoming):
                # one set of logo files serves every part with a badge: recorded with the first bake that brings it
                if once(path) != once(pack[name] if name in pack else incoming[name]):
                    failures.append(failure('bake', name, f'{label} holds another {name} than the one '
                                            + ('published: put the kit\'s strip in place first (`armorkit logos`), then draw the piece again' if name in pack else 'the other bakes hold')))
                continue
            if name in pack or name in incoming:
                failures.append(failure('bake', name, f'{PACK} already holds a file of that name' if name in pack else 'two bakes hold a file of that name'))
            else:
                incoming[name] = path
                bake.setdefault('taken', set()).add(name)
        if bake['drawn']:
            found_briefs.setdefault(record['model'], (None, None))
        if record['model'] not in found_briefs:
            path = brief_of(record['model'], given_briefs)
            found_briefs[record['model']] = (path, None if path is None else {material['name'] for material in json.loads(path.read_text(encoding='utf-8')).get('materials', [])})
        brief, materials = found_briefs[record['model']]
        if bake['drawn']:
            pass  # drawn by the kit, from no brief: its history record is what drew it
        elif brief is None:
            failures.append(failure('records', label, f'no brief of {record["model"]} in {BRIEFS.name}: name it (--brief {record["model"]}=FILE)'))
        elif materials != {material['name'] for material in record.get('materials', [])}:
            failures.append(failure('records', label, f'{brief.name} lists other materials than the bake found: it is not the brief the outfit was baked from'))
        history = given_records.get(record['model'], [])
        if not history:
            failures.append(failure('records', label, f'no record of how {record["model"]} was made: pin its generation ledger or log (--record {record["model"]}=FILE)'))
        outfits.append((bake, brief, history))
    for flag, given in (('--record', given_records), ('--brief', given_briefs)):
        unknown = sorted(set(given) - {bake['record']['model'] for bake in surveyed if flag == '--record' or not bake['drawn']})
        require(not unknown, f'{flag} names a model no bake is of: {", ".join(unknown)}')

    # One image under several names is published once: the other bodies' material files name the one kept.
    stands, renamed, kept = shared_maps(surveyed, incoming, once)
    work = None
    if stands:
        work = Path(tempfile.mkdtemp(prefix='armorkit-publish-'))
        for bake in surveyed:
            for name in sorted(bake.get('taken', ())):
                if name.endswith('.tga') and name[:-4] in stands:
                    bake['taken'].discard(name)
                    source, shared = incoming.pop(name), stands[name[:-4]] + '.tga'
                    if kept[stands[name[:-4]]] == name[:-4]:  # the bake recorded as holding the shared map
                        if shared in pack or shared in incoming:
                            failures.append(failure('bake', shared, f'{PACK} already holds a file of that name'))
                        else:
                            bake['files'][shared] = incoming[shared] = source
                            bake['taken'].add(shared)
                elif name in renamed:
                    (work / name).write_bytes(renamed[name].encode('ascii'))
                    bake['files'][name] = incoming[name] = work / name
    # A part lists the colour channels its tint textures use, no more and no fewer: SR_NWN offers a colour for each.
    for part in new:
        models = [model for names in registry.model_names(part).values() for model in names if model + '.plt' in incoming]
        try:
            used = set().union(*(channels(incoming[model + '.plt']) for model in models))
        except UNREADABLE as error:
            failures.append(failure('channels', f'{part["slot"]} {part["number"]}', f'a tint texture could not be read: {error}'))
            continue
        for reason, names in (('lists {}, which none of its tint textures use', set(part['channels']) - used),
                              ('has tint textures on {}, which it does not list', used - set(part['channels']))):
            if names and models:
                failures.append(failure('channels', f'{part["slot"]} {part["number"]}', 'the registry part ' + reason.format(', '.join(sorted(names)))))
    pack.update(incoming)
    try:
        try:
            drawn = draw_icons(new, pack, body_pack)
        except UNREADABLE as error:
            drawn = {}
            failures.append(failure('icons', PACK, f'the icons could not be drawn: {error}'))
        if drawn:
            work = Path(tempfile.mkdtemp(prefix='armorkit-icons-')) if work is None else work
            for name, blob in drawn.items():
                if name in pack:
                    failures.append(failure('icons', name, f'{PACK} already holds an icon of that name'))
                    continue
                (work / name).write_bytes(blob)
                pack[name] = incoming[name] = work / name
        table_texts = merged(parts, stock, root / TABLE_PACK)
        measured = {}
        failures += gates(parts, pack, table_texts, body_pack, [repo / name for name in CLASH], textures, measure_neck, measured, set(incoming),
                          {model for bake in surveyed if bake['drawn'] for model in bake['record']['models'].values()})
        skipped = []
        provenance = (repo / PROVENANCE).read_text(encoding='utf-8') if (repo / PROVENANCE).is_file() else ''
        unnamed = [name for name in [PACK] + sorted({bake['record']['model'] for bake in surveyed}) if name not in provenance]
        if unnamed and trial:
            skipped.append(f'provenance: PROVENANCE.md names no {", ".join(unnamed)}; a trial does not need the entry, a publication does')
        elif unnamed:
            failures += [failure('provenance', name, 'PROVENANCE.md has no entry naming it: write the content entry before publishing') for name in unnamed]
        by_gate = counted(failures)
        missing = sorted({found['model'][:4] for found in failures if found['gate'] == 'bodies'})
        report = {'root': str(root), 'trial': bool(trial), 'passed': not failures, 'failures': failures, 'failuresByGate': by_gate,
                  'bodiesWithoutModels': missing, 'skipped': skipped, 'newParts': [f'{part["slot"]} {part["number"]}' for part in new],
                  'necks': measured, 'tables': sorted(table_texts), 'files': sorted(incoming), 'sharedMaps': stands, 'written': False}
        if dry_run or (failures and not trial):
            return report
        # Every source is hashed once, before the first write; the records are made from those hashes and each
        # copy is read back against its own.
        hashes = {name: sha(path) for name, path in incoming.items()}
        # A tint texture that is one image under several names is written once; the copies list names the others.
        doubled = tint_copies({name: digest for name, digest in hashes.items() if name not in drawn})  # an icon is 16 KB: kept under its own name
        report['copies'] = sorted(doubled)
        # A record is named with the folder it lies in: the stages of a generation each keep a file of one name.
        pinned = lambda path: {'name': '/'.join(path.resolve().parts[-2:]), 'sha256': once(path), 'bytes': path.stat().st_size}
        outfits = [{'model': bake['record']['model'], 'body': bake['record']['body'], 'number': bake['record']['number'], 'tier': bake['record'].get('tier'),
                    'brief': None if brief is None else {'name': brief.name, 'sha256': once(brief)},
                    'bake': {'sha256': bake['sha256'], 'materials': bake['record'].get('materials', []),
                             'triangles': triangles(bake['record'])},
                    'records': [pinned(path) for path in history],
                    'resources': [{'name': name, 'sha256': hashes[name], 'bytes': path.stat().st_size} for name, path in sorted(bake['files'].items())
                                  if name in bake.get('taken', ())]}  # a file refused for its name was not copied, and is not recorded
                   for bake, brief, history in outfits]
        document = {'schemaVersion': 1, 'kind': registry.KIND, 'parts': parts}
        shown = next((bake['record']['logo'] for bake in surveyed if 'logo' in bake['record']), handoff_before.get('logo'))
        handoff = {**registry.handoff(parts), **({'logo': shown} if shown else {}), 'pack': PACK, 'tablePack': TABLE_PACK, 'tables': sorted(table_texts),
                   'icons': sorted(name for part in parts for name in icon_names(part)),
                   'iconFiles': handoff_before.get('iconFiles', []) + [{'name': name, 'sha256': hashes[name], 'bytes': incoming[name].stat().st_size}
                                                                       for name in sorted(drawn) if name in incoming],
                   'outfits': handoff_before.get('outfits', []) + outfits}
        texts = {root / TABLE_PACK / (table + '.2da'): text.encode('cp1252') for table, text in table_texts.items()}
        texts.update({root / path: (json.dumps(value, indent=1) + '\n').encode('utf-8') for path, value in ((REGISTRY, document), (HANDOFF, handoff))})
        if listed or doubled:
            texts[root / COPIES] = (json.dumps({'schemaVersion': 1, 'kind': COPIES_KIND, 'pack': PACK, 'copies': dict(sorted({**listed, **doubled}.items()))}, indent=1) + '\n').encode('utf-8')
        if not trial:
            texts[root / HAKBUILDER] = registered((root / HAKBUILDER).read_text(encoding='utf-8'), bool(listed or doubled)).encode('utf-8')
        saved = {path: path.read_bytes() if path.is_file() else None for path in texts}
        made_pack = not pack_folder.is_dir()
        try:
            if trial:
                (root / TRIAL).write_text(json.dumps({**TRIAL_MARK, 'written': True}) + '\n', encoding='utf-8')
            pack_folder.mkdir(parents=True, exist_ok=True)
            for name, path in sorted(incoming.items()):
                if name in doubled:
                    continue
                shutil.copyfile(path, pack_folder / name)
                require(sha(pack_folder / name) == hashes[name], f'{name} was not copied whole')
            for path, blob in texts.items():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(blob)
        except BaseException:  # the tree is put back as it was: a half-written pack would pass for a published one
            for name in incoming:
                (pack_folder / name).unlink(missing_ok=True)
            if made_pack and pack_folder.is_dir() and not any(pack_folder.iterdir()):
                pack_folder.rmdir()
            for path, blob in saved.items():
                if blob is None:
                    path.unlink(missing_ok=True)
                else:
                    path.write_bytes(blob)
            if trial:
                (root / TRIAL).write_text(json.dumps(TRIAL_MARK) + '\n', encoding='utf-8')
            raise
        report['written'] = True
        if trial:
            (root / 'publish-report.json').write_text(json.dumps(report, indent=1) + '\n', encoding='utf-8', newline='\n')
        return report
    finally:
        if work is not None:
            shutil.rmtree(work, ignore_errors=True)


def relogo(*, root=None, trial=False, dry_run=False, repo=REPO, write=logo.write):
    """Put the kit's logo strip in place of the published one: the report.

    A new logo is a new picture in `logos/` and its name in `logo.CELLS`; the strip, and with another count of
    cells the shader, are then other files than the ones published, which nothing else may change. This writes
    the kit's three files (`logo.FILES`, made by `write`) over the pack's and records their hashes and the
    cells in the handoff, where the first part with a badge recorded them. No part is touched: a badge reads
    whatever strip the pack holds.

    It fails, and writes nothing into the repository, unless the pack has a published logo, its three files
    are still the ones recorded (`published`), the material, parameter and strip keep their names, and every
    published cell keeps its name and number (`cells`): SR_NWN stores a cell's number. `root`, `trial` and
    `dry_run` are `publish`'s; a trial root is written whatever the gates say."""
    repo = Path(repo).resolve()
    require(not (trial and dry_run), 'A trial writes its scratch root; a dry run writes nothing: ask for one of them')
    require(trial or root is None, 'A root is a trial\'s scratch folder: pass trial=True with it, or no root to publish into the repository')
    root = seed(root, repo) if trial else repo
    parts, handoff = published(root)
    before, now = handoff.get('logo'), logo.record()
    entries = {resource['name']: resource for outfit in handoff['outfits'] for resource in outfit.get('resources', []) if resource['name'] in logo.FILES}
    require(before and set(entries) == set(logo.FILES), f'{PACK} has no published logo to replace: the first part with a badge publishes it')
    failures = []
    for name in logo.FILES:
        if not (root / PACK / name).is_file() or sha(root / PACK / name) != entries[name]['sha256']:
            failures.append(failure('published', name, f'{PACK} holds another file than the one published, or none: its hash is not the one the handoff records'))
    failures += [failure('cells', key, f'the published logo names its {key} {before[key]}, which every badge and SR_NWN use, and the kit {now[key]}')
                 for key in ('material', 'parameter', 'strip') if before[key] != now[key]]
    for name, cell in sorted(before['cells'].items(), key=lambda item: item[1]):
        if now['cells'].get(name) != cell:
            failures.append(failure('cells', name, f'published as cell {cell} and now ' + (f'cell {now["cells"][name]}' if name in now['cells'] else 'gone')
                                    + ': a cell once given keeps its name and number, which SR_NWN stores'))
    work = Path(tempfile.mkdtemp(prefix='armorkit-logo-'))
    try:
        write(work)
        hashes = {name: sha(work / name) for name in logo.FILES}
        changed = sorted(name for name in logo.FILES if hashes[name] != entries[name]['sha256'])
        require(changed or before != now, f'The kit\'s logo strip is the one {PACK} holds: there is nothing to replace')
        report = {'root': str(root), 'trial': bool(trial), 'passed': not failures, 'failures': failures, 'failuresByGate': counted(failures), 'files': changed,
                  'cells': {'added': sorted(set(now['cells']) - set(before['cells']), key=now['cells'].get), 'kept': len(set(now['cells']) & set(before['cells']))},
                  'written': False}
        if dry_run or (failures and not trial):
            return report
        for name in logo.FILES:
            entries[name].update(sha256=hashes[name], bytes=(work / name).stat().st_size)
        handoff['logo'] = now
        targets = {root / PACK / name: (work / name).read_bytes() for name in changed}
        targets[root / HANDOFF] = (json.dumps(handoff, indent=1) + '\n').encode('utf-8')
        saved = {path: path.read_bytes() if path.is_file() else None for path in targets}
        try:
            if trial:
                (root / TRIAL).write_text(json.dumps({**TRIAL_MARK, 'written': True}) + '\n', encoding='utf-8')
            for path, blob in targets.items():
                path.write_bytes(blob)
        except BaseException:  # put back as it was: a strip without its handoff would fail every later check
            for path, blob in saved.items():
                if blob is None:
                    path.unlink(missing_ok=True)
                else:
                    path.write_bytes(blob)
            raise
        report['written'] = True
        if trial:
            (root / 'publish-report.json').write_text(json.dumps(report, indent=1) + '\n', encoding='utf-8', newline='\n')
        return report
    finally:
        shutil.rmtree(work, ignore_errors=True)


def triangles(record):
    """The triangles a bake's record counts: an outfit's whole count, an accessory's own, a paired piece's by side."""
    counted = record['gates'].get('triangles')
    return counted.get('outfit', counted) if isinstance(counted, dict) else counted


def pairs(values, what):
    """[(model, file)] of `MODEL=FILE` arguments."""
    out = []
    for value in values:
        model, found, path = value.partition('=')
        require(found and model and path, f'{what} is MODEL=FILE: {value}')
        out.append((model, path))
    return out


def command(args):
    """The `publish` command of `python -m tools.armorkit`: prints the report and returns its exit code."""
    return finish(publish(args.registry, args.bake, args.stock, records=pairs(args.record, '--record'), briefs=pairs(args.brief, '--brief'),
                          root=args.trial, trial=bool(args.trial), dry_run=args.dry_run, body_pack=args.body_pack), args)


def command_logos(args):
    """The `logos` command: the strip alone (`relogo`). Prints the report and returns its exit code."""
    return finish(relogo(root=args.trial, trial=bool(args.trial), dry_run=args.dry_run), args)


def finish(report, args):
    """Build what a report says was written, where asked (`--build`), write and print the report: the exit code."""
    failed = False
    if args.build and report['written']:
        try:  # the publication is written by now: a build that fails is said in its report, not in place of it
            if args.trial:
                report['built'] = build(report['root'])
            else:
                shell = shutil.which('pwsh') or shutil.which('powershell')
                require(shell, 'PowerShell is needed to run tools/Build-Haks.ps1')
                done = subprocess.run([shell, '-NoProfile', '-Command', f"& ./tools/Build-Haks.ps1 -Pack @('{PACK}','{TABLE_PACK}') -SkipTlk"],
                                      cwd=REPO, capture_output=True, text=True)
                require(done.returncode == 0, 'Build-Haks failed: ' + done.stdout[-2000:] + done.stderr[-2000:])
                report['built'] = [PACK, TABLE_PACK]
        except (ValueError, OSError) as error:
            failed, report['buildError'] = True, str(error)
    if getattr(args, 'report', None):
        Path(args.report).write_text(json.dumps(report, indent=1) + '\n', encoding='utf-8', newline='\n')
    shown = {**report, 'failures': report['failures'] if len(report['failures']) <= 40 else report['failures'][:40] + [f'... and {len(report["failures"]) - 40} more']}
    print(json.dumps(shown, indent=1))
    return 0 if report['passed'] and not failed else 1
