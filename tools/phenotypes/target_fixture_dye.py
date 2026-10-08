"""Dye-check fixture sources for single-PLT bodies (garments in PLT cloth layers).

Derives a palette fixture source in which two actors wear the installed stock clothing item (nw_cloth001,
BaseItem 16) with every visible armour part set to the naked 001 body parts, so they show exactly the candidate
body while the engine colours its PLT dye layers from the item's colour channels (the stock mechanism that dyes
NWN underwear). All other actors stay naked (stock default dye row 0).

Dressed actors must carry the stock creature body fields themselves: the fixture spawn script only assigns head 1
and body parts to naked actors (it skips actors with an equipped chest item), so without Appearance_Head and the
BodyPart_* fields a dressed actor has head 0 and no body parts and the client draws nothing. The fields and types
follow a stock GIT creature (Appearance_Head 1; BodyPart_* 1 except belt/shoulders 0; legacy ArmorPart_RFoot 1;
Tail_New/Wings_New 0). Only sr_tm_floor.git changes; nothing is launched or accepted.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

DYES = {'tm_0': {'Cloth1Color': 88, 'Cloth2Color': 88, 'Leather1Color': 30, 'Leather2Color': 58, 'Metal1Color': 2, 'Metal2Color': 2},
        'tm_1': {'Cloth1Color': 26, 'Cloth2Color': 26, 'Leather1Color': 58, 'Leather2Color': 30, 'Metal1Color': 2, 'Metal2Color': 2}}
ARMOR_PARTS = {'ArmorPart_Belt': 0, 'ArmorPart_LBicep': 1, 'ArmorPart_LFArm': 1, 'ArmorPart_LFoot': 1, 'ArmorPart_LHand': 1,
               'ArmorPart_LShin': 1, 'ArmorPart_LShoul': 0, 'ArmorPart_LThigh': 1, 'ArmorPart_Neck': 1, 'ArmorPart_Pelvis': 1,
               'ArmorPart_RBicep': 1, 'ArmorPart_RFArm': 1, 'ArmorPart_RFoot': 1, 'ArmorPart_RHand': 1, 'ArmorPart_RShin': 1,
               'ArmorPart_RShoul': 0, 'ArmorPart_RThigh': 1, 'ArmorPart_Torso': 1, 'ArmorPart_Robe': 0}
BODY_FIELDS = {'BodyPart_Belt': 0, 'BodyPart_LBicep': 1, 'BodyPart_LFArm': 1, 'BodyPart_LFoot': 1, 'BodyPart_LHand': 1,
               'BodyPart_LShin': 1, 'BodyPart_LShoul': 0, 'BodyPart_LThigh': 1, 'BodyPart_Neck': 1, 'BodyPart_Pelvis': 1,
               'BodyPart_RBicep': 1, 'BodyPart_RFArm': 1, 'BodyPart_RHand': 1, 'BodyPart_RShin': 1, 'BodyPart_RShoul': 0,
               'BodyPart_RThigh': 1, 'BodyPart_Torso': 1, 'ArmorPart_RFoot': 1}
CHEST_SLOT_STRUCT = 2  # INVENTORY_SLOT_CHEST bit


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dressed_item(template, tag, dyes):
    """Stock clothing item showing the naked 001 parts with explicit dye channels and equipped-item fields."""
    item = copy.deepcopy(template); item.pop('__data_type', None); item['__struct_id'] = CHEST_SLOT_STRUCT
    for key, value in {**ARMOR_PARTS, **dyes}.items():
        item[key] = {'type': 'byte', 'value': value}
    item['Tag'] = {'type': 'cexostring', 'value': 'SR_DYE_'+tag.upper()}
    for key in ('XPosition', 'YPosition', 'ZPosition', 'XOrientation', 'YOrientation'):
        item[key] = {'type': 'float', 'value': 0.0}
    item['Cursed'] = {'type': 'byte', 'value': 0}
    return item


def dress_actors(git, template, dyes=None):
    """Equip the dye item on the declared actors and give them explicit stock body fields."""
    dyes = DYES if dyes is None else dyes; git = copy.deepcopy(git); dressed = {}
    for actor in git['Creature List']['value']:
        tag = actor['Tag']['value']
        if tag not in dyes:
            continue
        actor['Equip_ItemList'] = {'type': 'list', 'value': [dressed_item(template, tag, dyes[tag])]}
        actor['Appearance_Head'] = {'type': 'byte', 'value': 1}
        for key, value in BODY_FIELDS.items():
            actor[key] = {'type': 'byte', 'value': value}
        actor['Tail_New'] = {'type': 'dword', 'value': 0}; actor['Wings_New'] = {'type': 'dword', 'value': 0}
        dressed[tag] = dyes[tag]
    require(set(dressed) == set(dyes), 'Declared dye actors are missing from the fixture')
    return git, dressed


def validate_dressed_actors(actors):
    """Any actor with equipment must carry a head and every body part field (else the client draws nothing)."""
    report = {}
    for actor in actors:
        items = actor.get('Equip_ItemList', {}).get('value', [])
        if not items:
            continue
        tag = actor['Tag']['value']
        require(actor.get('Appearance_Head', {}).get('value', 0) >= 1, 'Dressed actor lacks Appearance_Head: '+tag)
        missing = [key for key in BODY_FIELDS if key not in actor]
        require(not missing, 'Dressed actor lacks stock body part fields: '+tag+' '+','.join(missing))
        require(all(actor[key]['value'] == value for key, value in BODY_FIELDS.items()), 'Dressed actor body parts differ: '+tag)
        chest = [item for item in items if item.get('__struct_id') == CHEST_SLOT_STRUCT]
        require(len(chest) == 1 and all(chest[0].get(key, {}).get('value') == value for key, value in ARMOR_PARTS.items()),
                'Dye clothing must show exactly the naked 001 body parts: '+tag)
        report[tag] = {key: chest[0][key]['value'] for key in DYES['tm_0'] if key in chest[0]}
    return report


def derive(prepared, tools, game_root, source_userdir, output):
    """Fresh dye fixture source from a prepared palette profile (target_fixture.py output)."""
    prepared = Path(prepared).resolve(); output = Path(output).resolve(); tools = Path(tools).resolve()
    require(not output.exists(), 'Fresh dye fixture source required')
    source = json.loads(prepared.read_text(encoding='utf-8')); parent = prepared.parent
    require(source.get('kind') == 'target-fixture-source' and source['profile'].endswith('-palette'), 'Prepared palette profile required')
    module = output/'test-module'; module.mkdir(parents=True)
    shutil.copytree(parent/'module-resources', module/'module-resources'); shutil.copytree(parent/'hak-resources', module/'hak-resources')
    (module/'json').mkdir()
    base = ['--root', str(game_root), '--userdirectory', str(Path(source_userdir).resolve()), '--no-ovr']
    uti = module/'json/nw_cloth001.uti'
    uti.write_bytes(subprocess.run([str(tools/'nwn_resman_cat.exe'), *base, 'nw_cloth001.uti'], check=True, capture_output=True).stdout)
    subprocess.run([str(tools/'nwn_gff.exe'), '-i', str(uti), '-o', str(uti)+'.json', '-p'], check=True, capture_output=True)
    template = json.loads(Path(str(uti)+'.json').read_text(encoding='utf-8'))
    original = module/'json/sr_tm_floor.orig.git.json'
    subprocess.run([str(tools/'nwn_gff.exe'), '-i', str(parent/'module-resources/sr_tm_floor.git'), '-o', str(original), '-p'], check=True, capture_output=True)
    git, dressed = dress_actors(json.loads(original.read_text(encoding='utf-8')), template)
    validate_dressed_actors(git['Creature List']['value'])
    edited = module/'json/sr_tm_floor.git.json'; edited.write_text(json.dumps(git, indent=1), encoding='utf-8')
    subprocess.run([str(tools/'nwn_gff.exe'), '-i', str(edited), '-o', str(module/'module-resources/sr_tm_floor.git')], check=True, capture_output=True)
    decoded = module/'json/decoded-git.json'
    subprocess.run([str(tools/'nwn_gff.exe'), '-i', str(module/'module-resources/sr_tm_floor.git'), '-o', str(decoded), '-p'], check=True, capture_output=True)
    require(json.loads(decoded.read_text(encoding='utf-8'))['Creature List'] == git['Creature List'], 'GIT round trip differs')
    user = output/'userdir'
    for name in ('hak', 'modules', 'override', 'logs', 'currentgame', 'modelcompiler', 'localvault', 'saves'):
        (user/name).mkdir(parents=True)
    packed = user/'modules'/Path(source['module']).name
    subprocess.run([str(tools/'nwn_erf.exe'), '-c', '-f', str(packed), '-e', 'MOD', str(module/'module-resources')], check=True, capture_output=True)
    record = dict(source)
    record.update(module=str(packed), moduleSha256=sha(packed), userDirectory=str(user),
                  moduleResourceHashes={p.name: sha(p) for p in sorted((module/'module-resources').iterdir())},
                  fixtureResourceHashes={p.name: sha(p) for p in sorted((module/'hak-resources').iterdir())},
                  dyeEquipment={'template': 'nw_cloth001 (installed)', 'templateSha256': sha(uti), 'slot': 'chest',
                                'parts': ARMOR_PARTS, 'actors': dressed,
                                'dressedActorBodyFields': {'Appearance_Head': 1, **BODY_FIELDS, 'Tail_New': 0, 'Wings_New': 0}},
                  parentPreparation={'path': str(prepared), 'sha256': sha(prepared)},
                  frozenInputs={str(Path(__file__).resolve()): sha(__file__), str(prepared): sha(prepared)})
    record['configuration'] = dict(source['configuration'])
    record['configuration']['equippedItems'] = ['%s: nw_cloth001 parts 001, dye %s' % (tag, value) for tag, value in dressed.items()]
    path = module/'preparation.json'; path.write_text(json.dumps(record, indent=2)+'\n', encoding='utf-8')
    return path


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('prepared', 'tools', 'game-root', 'source-userdir', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    result = derive(args.prepared, args.tools, args.game_root, args.source_userdir, args.output)
    print(json.dumps({'preparation': str(result), 'sha256': sha(result), 'clientLaunched': False}))
