"""The client check of a baked outfit: one actor per pose, the camera round each, in a fixture built from the bake.

A bake's output folder (`bake.run`, compiled with the game's install folder) holds the outfit's models and maps and
`bake.json`, which names them. `spec` turns that into a client fixture (`client_fixture.build`): a registry entry
per slot the outfit fills under the bake's number, the parts tables made from the stock ones with those entries
added, and an actor wearing the outfit in each pose of `CAST`, held there by its clip, with the shots of a
`PRESETS` camera round each. `without` adds, per pose, an actor wearing the outfit without some slots: the
shoulder pads' shards with the arms up showed only beside one without them. `run` starts the client on it
(`client.run`) and lays the captures out in one sheet.

Grown from the client checks of the Site Guard (docs/armorkit/plan.md): the body preset is the one every bake of
it was looked at with, the shoulders preset the one that found the pad shards. The client is the evidence; a
pass of the bake's gates is not.
"""
import json
import shutil
from pathlib import Path

from . import client, registry, tables
from . import client_fixture as fixture
from .registry import require

NAME = 'ak_poses'  # the fixture's module and hak
# label and the game's animation constant: 0 stands, conjure2 holds the arms up, conjure1 forward, then sitting in
# a chair, getting low and talking forcefully
CAST = (('standing', 0), ('arms up', 19), ('arms forward', 18), ('sitting', 6), ('crouching', 12), ('talking', 10))
# per preset, each shot as (facing in degrees, distance, label, camera height or None for the pose's `heights`)
PRESETS = {
    'body': {'views': ((62.0, 3.2, 'front', 0.95), (242.0, 3.2, 'rear', 0.95), (62.0, 1.2, 'elbows and waist', 1.15),
                       (152.0, 1.1, 'side, arm', 1.0), (62.0, 1.1, 'knees', 0.5), (242.0, 1.1, 'knees rear', 0.5),
                       (152.0, 0.9, 'ankle side', 0.2), (62.0, 0.9, 'ankles front', 0.2))},
    'shoulders': {'views': ((62.0, 1.3, 'shoulders front', None), (242.0, 1.3, 'shoulders rear', None),
                            (152.0, 1.0, 'shoulder side', None), (332.0, 1.0, 'other shoulder side', None)),
                  'heights': {'standing': 1.45, 'arms up': 1.4, 'arms forward': 1.4, 'sitting': 1.0, 'crouching': 0.85, 'talking': 1.45}},
}
PITCH = 84.0
HEAD = 86
COLOURS = {'cloth1': 22, 'cloth2': 22, 'leather1': 60, 'leather2': 60, 'metal1': 40, 'metal2': 40}
CHANNELS = ('cloth1', 'cloth2', 'leather1', 'leather2', 'metal1', 'metal2')
POSE_SCRIPT = ('void main() { ClearAllActions(); int a=GetLocalInt(OBJECT_SELF,"ANIM"); '
               'if(a>0) ActionPlayAnimation(a,1.0,3600.0); }\n')
TILE = 480  # pixels a side of each capture in the sheet


def slot_of(token):
    """The slot a part token belongs to (`chest`, `bicep` for `bicepl` and `bicepr`, and so on)."""
    found = [slot for slot, spec in registry.SLOTS.items() if token in spec['tokens']]
    require(len(found) == 1, f'{token} is no part token of a slot')
    return found[0]


def entries(slots, number, tier):
    """Registry entries for an outfit baked under `number` at `tier`, one per slot it fills, checked."""
    base = {'families': ['accessory'], 'genderedCut': False, 'coverage': {'skin': False, 'headgear': False}, 'channels': list(CHANNELS),
            'badge': None, 'bodies': list(registry.BODIES), 'mesh': 'rigid'}
    parts = [{**base, 'slot': slot, 'number': number, 'genderedCut': slot == 'chest', 'tiers': {joint: tier for joint in registry.SLOT_JOINTS[slot]}}
             for slot in slots]
    return registry.validate({'schemaVersion': 1, 'kind': registry.KIND, 'parts': parts})


def spec(bake_output, output, stock, haks, tlk=None, preset='body', without=(), colours=None):
    """(fixture spec, layout) for the outfit a bake wrote to `bake_output`, its resources gathered in
    `<output>/resources`, a fresh folder. `stock` is the folder of the stock parts tables, `haks` the built packs the
    fixture loads (highest priority first) and `tlk` its talk table. `layout` holds a label per shot and the
    shots per actor, for the sheet."""
    require(preset in PRESETS, f'A camera preset is one of {sorted(PRESETS)}')
    bake_output, output = Path(bake_output), Path(output)
    record = json.loads((bake_output / 'bake.json').read_text(encoding='utf-8'))
    models = record['models']
    require(record.get('compiled') == len(models),
            f'{bake_output} holds models that were not compiled: bake it with --nwn-root first')
    slots = sorted({slot_of(token) for token in models})
    for slot in slots:
        missing = [token for token in registry.SLOTS[slot]['tokens'] if token not in models]
        require(not missing, f'The outfit fills the {slot} slot without {", ".join(missing)}: both sides are worn')
    without = tuple(dict.fromkeys(without))
    require(all(slot in slots for slot in without), f'An actor can go without only a slot the outfit fills: {", ".join(slots)}')
    require(not output.exists(), f'The client check is built into a fresh folder; this one exists: {output}')
    checked = entries(slots, record['number'], record['tier'])  # everything is checked and read before the folder is made
    given = {table: (Path(stock) / (table + '.2da')).read_bytes().decode('cp1252') for table in registry.TABLES}
    live = {table: text for table, text in tables.generate_all(given, checked).items() if tables.check(table, text, checked, given[table])['live']}
    resources = output / 'resources'
    resources.mkdir(parents=True)
    for path in (bake_output / 'resources').iterdir():
        shutil.copyfile(path, resources / path.name)
    for table, text in live.items():
        (resources / (table + '.2da')).write_bytes(text.encode('cp1252'))
    worn = {slot: record['number'] for slot in slots}
    wardrobes = [('', worn)] + ([(', without ' + ' and '.join(without), {slot: n for slot, n in worn.items() if slot not in without})] if without else [])
    camera = PRESETS[preset]
    actors, shots, labels = [], [], []
    for pose, animation in CAST:
        for suffix, parts in wardrobes:
            index = len(actors)
            actors.append({'label': pose + suffix, 'body': record['body'], 'head': HEAD, 'position': (20.0 + 4.0 * index, 42.0), 'parts': parts,
                           'colours': {**COLOURS, **(colours or {})}, 'script': 'ak_pose', 'vars': {'ANIM': animation}})
            for facing, distance, view, height in camera['views']:
                shots.append({'actor': index, 'facing': facing, 'distance': distance, 'pitch': PITCH,
                              'height': camera['heights'][pose] if height is None else height})
                labels.append(f'{pose}{suffix}, {view}')
    document = {'name': NAME, 'resources': str(resources), 'haks': [str(hak) for hak in haks], 'actors': actors, 'shots': shots,
                'scripts': {'ak_pose': POSE_SCRIPT}}
    if tlk:
        document['tlk'] = str(tlk)
    return document, {'labels': labels, 'columns': len(camera['views'])}


def build(document, layout, output, nwn_root):
    """Build the fixture into `<output>/fixture` and keep the layout beside it: the fixture's record."""
    record = fixture.build(document, Path(output) / 'fixture', nwn_root)
    (Path(output) / 'layout.json').write_text(json.dumps(layout, indent=1) + '\n', encoding='utf-8', newline='\n')
    return record


def run(nwn_root, record, layout, output, settle=1.2):
    """Run the fixture in the client (`client.run`), capturing each shot into `<output>/captures`, and lay the
    captures out in `<output>/sheet.jpg`, a row per actor: the evidence, with the sheet's path."""
    evidence = client.run(nwn_root, record, Path(output) / 'captures', settle=settle)
    evidence['sheet'] = str(sheet(evidence['captures'], layout, Path(output) / 'sheet.jpg'))
    return evidence


def sheet(captures, layout, path, tile=TILE):
    """The captures cropped to the middle of the window, a row per actor, each with its label."""
    from PIL import Image, ImageDraw
    labels, columns = layout['labels'], layout['columns']
    require(len(captures) == len(labels), f'{len(captures)} captures for {len(labels)} shots')
    rows = (len(labels) + columns - 1) // columns
    out = Image.new('RGB', (columns * tile, rows * tile))
    for k, (capture, label) in enumerate(zip(captures, labels)):
        with Image.open(capture) as opened:
            image = opened.convert('RGB')
        width, height = image.size
        side, top = int(0.78 * height), int(0.055 * height)
        image = image.crop(((width - side) // 2, top, (width + side) // 2, top + side)).resize((tile, tile))
        ImageDraw.Draw(image).text((6, 4), label, fill=(255, 255, 0))
        out.paste(image, ((k % columns) * tile, (k // columns) * tile))
    out.save(path, quality=92)
    return Path(path)
