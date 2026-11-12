"""One generated outfit baked into the parts a body wears: fitted, split, laid out, coloured, tinted and written.

The stages are the kit's own (`repose`, `split`, `texture`, `export`). This module is the order they run in, and
what each face the split made is drawn as (`roles`): which are a closing's, a cap's, a pad's, which are shaded as
the cloth round them, and which lie in an armhole's shadow. Those choices were made on the first worn outfit,
siteguard-male, in the game client (docs/armorkit/pilot-corpsec.md), and the functions that carry them out only
say what "the caller" flags; this is that caller.

`bake` reads the generated colours and relief into every part, which takes minutes; `store` and `stored` keep its
result, so `tints` and `write` can be run again on it. `gates` checks what was written.
"""
import json
import shutil
from pathlib import Path

import numpy as np

from tools.headkit import gltf

from . import brief, export, measure, registry, repose, seams, split, texture
from .registry import require

ADDED = (split.CLOSING, split.CAP, split.WALL, split.PADDED)  # what the split made: it has no surface of its own on the generated outfit
DOMED = (split.CAP, split.PADDED)  # of those, what rounds a surface on past its edge and is not creased there (`export.added_normals`)
UNDER = {'legl': (split.CAP, split.WALL), 'legr': (split.CAP, split.WALL), 'pelvis': (split.CLOSING,)}  # shaded as the cloth round them (`texture.under`)
ARMHOLE = ('bicepl', 'bicepr')  # the parts closed at a shoulder: their closings lie in the armhole's shadow
SLOTS = ('chest', 'pelvis', 'shoulder', 'bicep', 'forearm', 'hand', 'thigh', 'shin', 'foot')  # the slots a generated outfit fills
BUDGET = {'chest': 6000, 'slot': 2250, 'outfit': 30000, 'texture': 1024}  # triangles a chest, another part and a whole outfit may have; texels a side
NOT_BUILT = ('seam contract: each end against its tier\'s overlap and envelope', 'clearance: no body surface showing at rest',
             'no holes or detached pieces')  # gates of docs/armorkit/plan.md that `gates` does not check yet
KEYS = ('v', 'f', 'uv', 'n', 'rgb', 'covered', 'relief', 'closing', 'cap', 'padded', 'added', 'domed', 'src', 'trimmed')  # what `store` keeps of a part
KEPT, KEPT_KIND = 'baked.json', 'srn-armorkit-baked-parts'  # the list of the parts `store` kept, and its kind


def roles(name, made):
    """What the faces of part `name` are drawn as, from what made each (`split.split`, `made`): flags per face.

    `added` are the faces the split made, `domed` those of them that are not creased at their rim. Of the
    added faces, `under` are shaded as the cloth they lie under, vertex by vertex (`texture.under`): a
    thigh's cap and its wall toward the other leg, and the pelvis's lids, of which a stride shows a hand's
    breadth. `closing`, `cap` and `padded` are `texture.tint_maps`' flags of the same names for the rest: a
    thigh's wall goes with its cap where it is not `under`.

    An upper arm's cap is none of these and is drawn as it was read, its rim's colours carried to its pole.
    That is how siteguard-male was baked when its armpits were looked at in the client, and it was not what
    was meant: the cap was to be flagged as a closing and darkened with the closings (`ARMHOLE`), and a later
    line of the bake script took it out of them again. The closings alone, darkened, turned the pale strip in
    front of the armpit into a crease, so this is kept as it was seen until the other is tried in the client."""
    made = np.asarray(made, int)
    under = UNDER.get(name, ())
    flat = [kind for kind in (split.CAP, split.WALL, split.PADDED) if kind not in under and not (kind == split.CAP and name in ARMHOLE)]
    return {'added': np.isin(made, ADDED), 'domed': np.isin(made, DOMED), 'under': np.isin(made, under),
            'closing': (made == split.CLOSING) & (split.CLOSING not in under), 'cap': np.isin(made, flat), 'padded': made == split.PADDED}


def to_field(points):
    """Points in the bodies' axes, back in the generated mesh's (`repose.load` turns them the other way)."""
    points = np.asarray(points, float)
    return np.stack([-points[:, 0], points[:, 2], points[:, 1]], axis=1)


def bake(document, mesh, colours, raw, body_pack, xatlas, body='pmh0', tier=2, say=lambda *_: None):
    """(parts, bones): a generated outfit as the parts body `body` wears, each with its maps.

    `document` is the outfit's brief (`brief.load`), `mesh` its exported mesh, `colours` its saved colour
    field and `raw` the generator's own high-detail mesh, whose relief the normal maps are read from.
    `body_pack` is the folder of the body's models, `xatlas` the loaded layout library, `tier` the seam tier
    the outfit is cut at. `parts` maps a part's token to its laid-out mesh (`v`, `f`, `uv`, `n`), its colours
    and relief per texel (`rgb`, `covered`, `relief`), the texels `tint_maps` is told about (`closing`, `cap`,
    `padded`), flags per face (`added`, `domed`), the brief's material of each face that is no plate's
    (`trimmed`, -1 elsewhere) and where each vertex lies on the generated mesh (`src`). `bones` is the body's
    rig. `say` is told how each stage went."""
    count = len(document['materials'])
    bones, skin = measure.body(body_pack, body)
    source, faces = repose.load(mesh)
    field, levels = texture.open_field(colours)
    read = lambda points: texture.read_field(field, levels, points)
    as_read, shown = texture.mesh_materials(to_field(source), faces, read, count)
    as_read, on_mesh = np.asarray(as_read), brief.worn(document, shown)
    metals = [k for k, material in enumerate(on_mesh) if material['kind'] == 'metal']
    kinds = np.asarray(texture.trimmed(source, faces, as_read, metals))  # a line of metal too narrow for a plate goes to what it lies on
    say('trims', int((kinds != as_read).sum()), 'faces')
    listed = [material['name'] for material in document['materials']]
    brief_of = np.array([listed.index(material['name']) for material in on_mesh] + [-1])
    carried = repose.onto_body(source, faces, bones, skin, materials=kinds, padded=''.join(document.get('pads', [])))
    v, f, source = carried['vertices'], carried['faces'], carried['source']
    raw_v, raw_f = gltf.positions(raw)
    fine, fine_levels = texture.normal_field(np.asarray(raw_v), np.asarray(raw_f))
    read_fine = lambda points: texture.read_field(fine, fine_levels, points)
    in_field = to_field(source)
    contract = seams.load_contract()
    joints = {name: matrix[:3, 3] for name, matrix in bones.items()}
    keys = [(joint, side) for joint in seams.JOINTS for side in seams.sides(joint)]
    radii = {key: float(np.max(seams.envelope(contract, key[0], body, tier, None if key[1] == 'c' else key[1]))) for key in keys}
    overlaps = {key: float(seams.overlap(contract, key[0], body, tier)) for key in keys}
    # the posed normals, and the positions and normals on the generated mesh, ride through the cut
    columns = np.concatenate([export.vertex_normals(v, f), in_field, export.vertex_normals(in_field, f)], axis=1)
    made, origins = {}, {}
    mats = kinds[carried['origin']]
    guards = {(joint, side): flags for joint in split.GUARDS for side in 'lr'
              for flags in [split.guard(v, f, mats, joints, joint, side)] if flags is not None}
    say('pads', {key: int(flags.sum()) for key, flags in guards.items()})
    result = split.split(v, f, columns, joints, radii, overlaps, reaches=split.reaches(v, f, joints, radii, sleeves=carried['sleeves']),
                         whole={('neck', 'c')}, made=made, sleeves=carried['sleeves'], guards=guards, origins=origins)
    unit = lambda rows: rows / np.maximum(np.linalg.norm(rows, axis=1, keepdims=True), 1e-12)
    seen_at = None  # the material the outfit shows at each of its vertices, read once
    parts = {}
    for name, (pv, pf, pc) in result.items():
        role = roles(name, made[name])
        of_face = np.where(origins[name] >= 0, mats[np.maximum(origins[name], 0)], -1)  # per face: its material, -1 for what the split made
        bare = (of_face >= 0) & ~np.isin(of_face, metals)  # a face that is no plate's shows no plate
        if role['under'].any():  # the cloth of the part's commonest material, where the outfit shows that colour
            if seen_at is None:
                seen_at = texture.labels(np.asarray(read(columns[:, 3:6])[0], float)[:, :3], shown['tones'])
            main = np.bincount(of_face[of_face >= 0]).argmax()
            cloth = np.zeros(len(v), bool)
            cloth[f[mats == main]] = True
            only, near = texture.under(pv, pf, made[name], v, cloth & (seen_at == main), kind=UNDER[name])
            pc = pc.copy()
            pc[only, 3:9] = columns[near, 3:9]
        size = texture.size(pv, pf)
        mapping, pf, uv = texture.layout(xatlas, pv, pf, size)
        pv, pc = pv[mapping], pc[mapping]
        rgb, covered, missed = texture.colour_map(uv, pf, pc[:, 3:6], read, size)
        if role['under'].any():
            mine = texture.face_texels(uv, pf, role['under'], size) & covered
            rgb[mine] = texture.soft_map(uv, pf, pc[:, 3:6], read, size)[mine]
        relief, _, lost = texture.normal_map(uv, pf, pc[:, 3:6], unit(pc[:, 6:9]), pv, read_fine, size, added=role['added'])
        parts[name] = {'v': pv, 'f': pf, 'uv': uv, 'n': unit(pc[:, :3]), 'rgb': rgb, 'covered': covered, 'relief': relief,
                       **{key: texture.face_texels(uv, pf, role[key], size) for key in ('closing', 'cap', 'padded')},
                       'added': role['added'], 'domed': role['domed'], 'src': pc[:, 3:6], 'trimmed': np.where(bare, brief_of[of_face], -1)}
        say(f'{name}: {size} px, {len(pf)} faces, covered {covered.mean():.0%}, no colour {missed}, no normal {lost}')
    # what the torso wears over a sleeve is drawn as the sleeve's cloth, with the sleeve's closings
    if 'chest' in parts:
        first = texture.materials(np.concatenate([part['rgb'][part['covered']] for part in parts.values()]), count)
        chest = parts['chest']
        seen = np.where(chest['covered'], texture.labels(chest['rgb'].reshape(-1, 3), first['tones']).reshape(chest['covered'].shape), -1)
        others = texture.edge_materials(seen, chest['closing'])
        for name in ARMHOLE:
            if name in parts:
                part, size = parts[name], len(parts[name]['rgb'])
                shows = texture.face_materials(part['uv'], part['f'], part['rgb'], part['covered'], first, size)
                over = texture.overlaid(part['v'], part['f'], shows, made[name] == split.CLOSING, others)
                part['closing'] = texture.face_texels(part['uv'], part['f'], (made[name] == split.CLOSING) | over, size)
    return parts, bones


def store(parts, folder):
    """Keep `bake`'s parts in `folder`, a file per part, for `stored`.

    The parts are listed in `baked.json`, written last: a folder used again for an outfit with fewer parts
    still holds the files of the parts it no longer has, and read by what lies in it, a second tint gave
    the new outfit the old one's shoulder pads. The list is taken away first, so a store that stops halfway
    leaves nothing `stored` would read."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / KEPT).unlink(missing_ok=True)
    for name, part in parts.items():
        np.savez(folder / (name + '.npz'), **{key: part[key] for key in KEYS})
    (folder / KEPT).write_text(json.dumps({'schemaVersion': 1, 'kind': KEPT_KIND, 'parts': list(parts)}, indent=1) + '\n', encoding='utf-8', newline='\n')


def stored(folder):
    """The parts `store` last kept in `folder`: those its list names, and no other file there."""
    folder = Path(folder)
    require((folder / KEPT).is_file(), f'{folder} holds no baked parts: it has no {KEPT}')
    listed = json.loads((folder / KEPT).read_text(encoding='utf-8'))
    require(isinstance(listed, dict) and listed.get('kind') == KEPT_KIND and listed.get('schemaVersion') == 1
            and isinstance(listed.get('parts'), list) and listed['parts'] and all(isinstance(name, str) for name in listed['parts']),
            f'{folder / KEPT} is no list of baked parts')
    require(all((folder / (name + '.npz')).is_file() for name in listed['parts']), f'{folder} lacks a part its {KEPT} lists')
    parts = {name: dict(np.load(folder / (name + '.npz'))) for name in listed['parts']}
    require(all(set(KEYS) <= set(part) for part in parts.values()), f'{folder} holds a file that is no baked part')
    return parts


def tints(parts, document, speck=texture.SPECK):
    """({part: (shades, layers)}, record): the tint texture of every part of a baked outfit, for `export.tint`.

    The materials are found over the whole outfit and told which of the brief's each is (`brief.worn`); a
    material's garments are told apart by where they are worn (`texture.worn_second`), and what the split
    made is drawn at the outfit's lit shades (`texture.lit_shades`). `record` holds the materials as found,
    in the order of the texels' numbers, their channels and lit shades.

    The parts are taken in the order of their names, whatever order they are given in: the materials are
    found on a sample of the texels as they come, and a fresh bake and its stored parts tinted again would
    else differ by a shade here and there."""
    count, parts = len(document['materials']), {name: parts[name] for name in sorted(parts)}
    size = lambda part: len(part['rgb'])
    found = texture.materials(np.concatenate([part['rgb'][part['covered']] for part in parts.values()]), count)
    worn = brief.worn(document, found)  # the brief's material for each the colours show: its kind is the brief's to say
    kinds = [material['kind'] for material in worn]
    channel = texture.channels(kinds)  # two channels per material: its garments are told apart by where they are worn
    slot_of = {token: slot for slot in SLOTS for token in registry.SLOTS[slot]['tokens']}
    own = {name: ~part['added'] for name, part in parts.items()}
    start = np.cumsum([0] + [len(part['src']) for part in parts.values()])
    seen = {name: texture.face_materials(part['uv'], part['f'], part['rgb'], part['covered'], found, size(part)) for name, part in parts.items()}
    second = texture.worn_second(np.concatenate([part['src'] for part in parts.values()]),
                                 np.concatenate([part['f'][own[name]] + start[i] for i, (name, part) in enumerate(parts.items())]),
                                 np.concatenate([seen[name][own[name]] for name in parts]),
                                 np.concatenate([[slot_of[name]] * int(own[name].sum()) for name in parts]), kinds)
    at = np.cumsum([0] + [int(own[name].sum()) for name in parts])
    listed = [material['name'] for material in document['materials']]
    here = {listed.index(material['name']): k for k, material in enumerate(worn)}  # the brief's material, as the texels number it
    lit = texture.lit_shades(np.concatenate([part['rgb'][part['covered'] & ~part['closing'] & ~part['cap']] for part in parts.values()]), found)
    tinted = {}
    for i, (name, part) in enumerate(parts.items()):
        rows = np.zeros((len(part['f']), count), bool)
        rows[own[name]] = second[at[i]:at[i + 1]]
        twice = texture.face_texels(part['uv'], part['f'], texture.added_second(part['v'], part['f'], part['added'], rows), size(part))
        trim = np.full(part['covered'].shape, -1)
        for material in np.unique(part['trimmed'][part['trimmed'] >= 0]):
            trim[texture.face_texels(part['uv'], part['f'], part['trimmed'] == material, size(part))] = here[int(material)]
        tinted[name] = texture.tint_maps(part['rgb'], part['covered'], found, channel, relief=part['relief'],
                                         charts=texture.chart_map(part['uv'], part['f'], size(part)), closing=part['closing'], second=twice,
                                         cap=part['cap'], padded=part['padded'], lit=lit, trim=trim,
                                         shadow=part['closing'] if name in ARMHOLE else None, speck=speck)
    record = {'materials': [{'name': material['name'], 'kind': material['kind'], 'channels': list(channel[k]),
                             'colour': np.round(found['colours'][k] * 255).astype(int).tolist(), 'lit': round(float(lit[k]), 1)}
                            for k, material in enumerate(worn)]}
    return tinted, record


def write(folder, parts, tinted, bones, body, number):
    """Write every part of a baked outfit as number `number` on `body`: {part: model name}.

    `<folder>/ascii` gets the models as ASCII and their tint textures, `<folder>/resources` the tint textures
    again, the normal maps at half size and the material files that bind them: what a pack takes, once the
    models are compiled into it (`export.compile_models`)."""
    ascii_dir, resources = Path(folder) / 'ascii', Path(folder) / 'resources'
    for made in (ascii_dir, resources):
        made.mkdir(parents=True, exist_ok=True)
    models = {}
    for name, part in parts.items():
        # closings and caps are lit as surfaces of their own
        v, f, n, uv = export.added_normals(part['v'], part['f'], part['added'], part['n'], part['uv'], domed=part['domed'])
        models[name] = export.write_part(ascii_dir, body, name, number, (v, f, uv, n), bones, tinted[name])
        texture.write_relief(resources, models[name], texture.halved(part['relief']))
        shutil.copyfile(ascii_dir / (models[name] + '.plt'), resources / (models[name] + '.plt'))
    return models


def gates(parts, models, resources, packs=()):
    """The automatic gates of docs/armorkit/plan.md that can be checked on one written outfit: a report.

    Budgets: the triangles of each part, the chest's own and the whole outfit's, and the texels a side of
    each texture (`BUDGET`). Names: no model of the outfit is one a pack in `packs` already holds (their
    length is checked as they are made, `registry.model_name`). Texture closure: every model has its tint
    texture and its material file in `resources`, and the map the material file names is there. `failures`
    lists what did not pass, `notBuilt` the gates of the plan this does not check yet: a pass here is not
    the plan's."""
    resources, failures = Path(resources), []
    faces = {name: int(len(part['f'])) for name, part in parts.items()}
    for name, number in faces.items():
        limit = BUDGET['chest'] if name == 'chest' else BUDGET['slot']
        if number > limit:
            failures.append(f'{name}: {number} triangles, over the budget of {limit}')
    if sum(faces.values()) > BUDGET['outfit']:
        failures.append(f'the outfit: {sum(faces.values())} triangles, over the budget of {BUDGET["outfit"]}')
    for name, part in parts.items():
        if len(part['rgb']) > BUDGET['texture']:
            failures.append(f'{name}: a texture of {len(part["rgb"])} texels a side, over the budget of {BUDGET["texture"]}')
    for name, model in models.items():
        for pack in packs:
            if (Path(pack) / (model + '.mdl')).exists():
                failures.append(f'{model}: {pack} holds a model of that name')
        if not (resources / (model + '.plt')).is_file():
            failures.append(f'{model}: no tint texture')
        material = resources / (model + '.mtr')
        if not material.is_file():
            failures.append(f'{model}: no material file')
        else:
            named = [line.split()[1] for line in material.read_text(encoding='ascii').splitlines() if line.startswith('texture') and len(line.split()) > 1]
            failures += [f'{model}: its material file names {image}, which is not there' for image in named if not (resources / (image + '.tga')).is_file()]
    return {'passed': not failures, 'failures': failures, 'triangles': {**faces, 'outfit': sum(faces.values())},
            'texels': {name: int(len(part['rgb'])) for name, part in parts.items()}, 'notBuilt': list(NOT_BUILT)}


def run(document, output, body_pack, number, *, mesh=None, colours=None, raw=None, xatlas=None, kept=None, body='pmh0', tier=2,
        packs=(), game=None, resources=(), say=lambda *_: None):
    """Bake one outfit into `output` and check it: the record, also written as `<output>/bake.json`.

    With `mesh`, `colours`, `raw` and `xatlas` the outfit is baked (`bake`) and, where `kept` names a folder,
    stored there; without them the parts stored in `kept` are tinted and written again. `packs` are the pack
    folders a model's name may not clash with. With `game`, the game's install folder, the models are
    compiled into `<output>/resources` (`export.compile_models`, with `resources` to look animations up in):
    the models of this run and no other. An output folder used before still holds the models written then,
    under another number or for parts the outfit no longer has, and they are neither in the record nor gated."""
    fresh = [mesh, colours, raw, xatlas]
    require(all(given is not None for given in fresh) or (kept is not None and all(given is None for given in fresh)),
            'Bake an outfit from its mesh, colour field, raw mesh and the layout library, or tint the parts kept in a folder again')
    if mesh is not None:
        parts, bones = bake(document, mesh, colours, raw, body_pack, xatlas, body, tier, say)
        if kept is not None:
            store(parts, kept)
    else:
        parts, bones = stored(kept), measure.body(body_pack, body)[0]
    tinted, record = tints(parts, document)
    models = write(output, parts, tinted, bones, body, number)
    record = {'model': document['model'], 'body': body, 'tier': tier, 'number': number, 'models': models, **record,
              'gates': gates(parts, models, Path(output) / 'resources', packs)}
    if game is not None:
        compiled = export.compile_models(sorted(Path(output) / 'ascii' / (model + '.mdl') for model in models.values()),
                                         Path(output) / 'resources', game=game, resources=list(resources))
        record['compiled'] = len(compiled)
    (Path(output) / 'bake.json').write_text(json.dumps(record, indent=1) + '\n', encoding='utf-8', newline='\n')
    return record
