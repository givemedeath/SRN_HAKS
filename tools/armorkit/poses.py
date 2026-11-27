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

from . import client, registry, seams, tables
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
    # an accessory is looked at close, all the way round: a belt at the waist, headgear at the head
    'waist': {'views': ((62.0, 1.3, 'waist front', None), (152.0, 1.2, 'waist side', None), (242.0, 1.3, 'waist rear', None),
                        (332.0, 1.2, 'other waist side', None)),
              'heights': {'standing': 1.0, 'arms up': 1.0, 'arms forward': 1.0, 'sitting': 0.6, 'crouching': 0.55, 'talking': 1.0}},
    # the hips close, from a little below them: under a thigh swung forward, where its end shows (2026-11-25)
    'hips': {'views': ((62.0, 1.1, 'hips front', None), (152.0, 1.0, 'hip side', None), (242.0, 1.1, 'hips rear', None),
                       (332.0, 1.0, 'other hip side', None)),
             'heights': {'standing': 0.8, 'arms up': 0.8, 'arms forward': 0.8, 'sitting': 0.45, 'crouching': 0.4, 'talking': 0.8}},
    'head': {'views': ((62.0, 1.0, 'head front', None), (152.0, 1.0, 'head side', None), (242.0, 1.0, 'head rear', None),
                       (332.0, 1.0, 'other head side', None)),
             'heights': {'standing': 1.7, 'arms up': 1.7, 'arms forward': 1.7, 'sitting': 1.25, 'crouching': 1.1, 'talking': 1.7}},
}
PITCH = 84.0
HEAD = 86
# What an outfit is coloured in for a look in the client: six colours of the game's palettes that are not mistaken for
# one another, one per channel (blue and red cloth, yellow and purple leather, green and orange metal), so that a part
# on the wrong channel, or two garments sharing one, shows at a glance. The standard for every in-game preview and
# check (user decision 2026-11-15); until then a kind's two channels wore one colour and could not be told apart.
COLOURS = {'cloth1': 27, 'cloth2': 37, 'leather1': 33, 'leather2': 41, 'metal1': 40, 'metal2': 16}
CHANNELS = ('cloth1', 'cloth2', 'leather1', 'leather2', 'metal1', 'metal2')
POSE_SCRIPT = ('void main() { ClearAllActions(); int a=GetLocalInt(OBJECT_SELF,"ANIM"); int c=GetLocalInt(OBJECT_SELF,"CELL"); '
               'if(c>0) SetMaterialShaderUniformVec4(OBJECT_SELF,"srn_logo","LogoCell",IntToFloat(c)); '
               'if(a>0) ActionPlayAnimation(a,1.0,3600.0); }\n')
TILE = 480  # pixels a side of each capture in the sheet


def worn_colours(colours=None):
    """The six channels' colours an outfit is looked at in: `COLOURS`, with those `colours` gives in their place.
    No two channels may wear one colour: two garments on two channels would look like one."""
    worn = {**COLOURS, **(colours or {})}
    require(set(worn) == set(CHANNELS), 'A colour is given for a channel of ' + ', '.join(CHANNELS) + ': not ' + ', '.join(sorted(set(worn) - set(CHANNELS))))
    require(len(set(worn.values())) == len(CHANNELS),
            'An outfit is looked at with its six colour channels in six different colours: ' + json.dumps(worn, sort_keys=True))
    return worn


def slot_of(token):
    """The slot a part token belongs to (`chest`, `bicep` for `bicepl` and `bicepr`, and so on)."""
    found = [slot for slot, spec in registry.SLOTS.items() if token in spec['tokens']]
    require(len(found) == 1, f'{token} is no part token of a slot')
    return found[0]


def entries(slots, number, tier):
    """Registry entries for an outfit baked under `number` at `tier`, one per slot it fills, checked.

    A number in a family's thousand is that family's and names a set and a group (`registry.validate_part`):
    the check gives it the family of its block and its own name for both, since a fixture's tables need only
    the rows. Written as an accessory's whatever the number, the entries of a bake at its registry number,
    which is the bake a publication takes (README, runbook), were refused (Facility Security at 6020,
    2026-11-14)."""
    family = registry.block(number)
    named = {'families': [family], 'set': NAME.replace('_', '-'), 'group': NAME.replace('_', '-')} if family in registry.FAMILY_BLOCKS else {'families': ['accessory']}
    base = {**named, 'genderedCut': False, 'coverage': {'skin': False, 'headgear': False}, 'channels': list(CHANNELS),
            'badge': None, 'bodies': list(registry.BODIES), 'mesh': 'rigid'}
    # a neck part is headgear here: the one kind of neck part the kit makes so far (`headgear.fit`), skinned to the head
    neck = {'neckCategory': 'headgear', 'coverage': {'skin': True, 'headgear': True}, 'mesh': 'skinned', 'channels': ['skin', *CHANNELS]}
    parts = [{**base, 'slot': slot, 'number': number, 'genderedCut': slot == 'chest', 'tiers': {joint: seams.at(tier, joint) for joint in registry.SLOT_JOINTS[slot]},
              **(neck if slot == 'neck' else {})} for slot in slots]
    return registry.validate({'schemaVersion': 1, 'kind': registry.KIND, 'parts': parts})


def spec(bake_output, output, stock, haks, tlk=None, preset='body', without=(), colours=None, under=None, cells=(), body_pack=None):
    """(fixture spec, layout) for the outfit a bake wrote to `bake_output`, its resources gathered in
    `<output>/resources`, a fresh folder. `stock` is the folder of the stock parts tables, `haks` the built packs the
    fixture loads (highest priority first) and `tlk` its talk table. `layout` holds a label per shot and the
    shots per actor, for the sheet. `under` is {slot: number} of parts every actor also wears, from the packs in
    `haks` with their table rows: the published outfit an accessory is looked at on. `cells` are logo cells
    (`logo.CELLS`) the actors are set to in turn, for a part with a badge; without them every badge is blank. Every actor wears a published head of its own
    kind of body (`bodies.HEADS`); with `body_pack`, the folder of the bodies' models, the camera stands further
    off and higher by the body's height against the Human's of its gender, as `wear` does it."""
    from . import bodies
    under = dict(under or {})
    if cells:
        from . import logo
        require(all(type(cell) is int and 0 <= cell < len(logo.CELLS) for cell in cells), f'A logo cell is one of 0 to {len(logo.CELLS) - 1}: the strip has no other')
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
    require(not set(under) & set(slots), f'The bake fills {sorted(set(under) & set(slots))} itself: nothing else is worn there')
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
    stature = 1.0 if body_pack is None else bodies.statures([record['body']], body_pack)[record['body']]
    actors, shots, labels = [], [], []
    for pose, animation in CAST:
        for suffix, parts in wardrobes:
            index = len(actors)
            actors.append({'label': pose + suffix, 'body': record['body'], 'head': bodies.HEADS.get(record['body'][:3], HEAD), 'position': (20.0 + 4.0 * index, 42.0), 'parts': {**under, **parts},
                           'colours': worn_colours(colours), 'script': 'ak_pose', 'vars': {'ANIM': animation, **({'CELL': int(cells[index % len(cells)])} if cells else {})}})
            for facing, distance, view, height in camera['views']:
                shots.append({'actor': index, 'facing': facing, 'distance': round(distance * max(1.0, stature), 3), 'pitch': PITCH,
                              'height': round((camera['heights'][pose] if height is None else height) * stature, 3)})
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
