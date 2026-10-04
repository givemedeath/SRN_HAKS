"""Compose new independently compiled limbs with immutable accepted neighbours.

Consumes real compiler receipts; never runs the compiler or copies an old body
directory. Exact declared ownership and material hashes are checked before copy.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
from pathlib import Path
import re
import shutil

from compose_stock_pelvis_native import file_hashes, verify_native
from stage_stock_part import require, sha, save
from build_test_module import validate_owned_normal_dependencies
from stock_limb_contract import ATTACHMENTS, parse_preserved_parts, validate_new_parts, validate_receipt_lineage


PRESERVED = {'pmh0_chest001.mdl', 'pmh0_pelvis001.mdl'}
LIMBS = {'pmh0_' + part + '001.mdl' for part in ATTACHMENTS}
PROTECTED_NATIVE = {
    'pmh0_chest001.mdl': '8afdd1e81bd7b695b18ce5b88d5f1fa265e7c34043c5bc838bd012a55fb3e1be',
    'pmh0_pelvis001.mdl': 'c0d87495e6405254fa9dfb9b5ec1d144ed098ccd06a6e6290b36fced9a1a428a',
}
STOCK_HEIGHT = 1.9339157
CORRECTED_PELVIS_PLT = '990aa66b5c642d6c45ab4f1c60ceffd732cd290b53207c9c5021698dc9181690'
THIGH_ATTACHMENTS = {'pmh0_legl001.mdl': ('legl','lthigh_g'),
                     'pmh0_legr001.mdl': ('legr','rthigh_g')}
LIMB_ATTACHMENTS = {'pmh0_' + part + '001.mdl': (part, joint) for part, joint in ATTACHMENTS.items()}


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def native_unit(converted, expected, client_hash=None, material_patch_sha256=None):
    converted = Path(converted).resolve()
    receipt = load(converted / 'native-compile.json')
    client_hash = client_hash or receipt.get('clientSha256')
    require(client_hash and receipt.get('complete') is True, 'Incomplete native compiler evidence')
    require(receipt.get('clientSha256') == client_hash, 'Native compiler client differs')
    if (converted / 'material-patch.json').exists():
        require(material_patch_sha256 and sha(converted / 'material-patch.json') == material_patch_sha256,
                'Runtime palette donor requires explicit pinned material patch')
        from audit_thigh_package import verify_native as verify_runtime
        native, _ = verify_runtime(converted, expected, allow_material_patch=True)
        verified = (native, {'path':str(converted / 'native-compile.json'),
            'sha256':sha(converted / 'native-compile.json'), 'models':sorted(expected),
            'materialResourceHashes':receipt['materialResourceHashes']})
    else:
        require(not material_patch_sha256, 'Pinned material patch missing from donor')
        verified = verify_native(converted, expected, receipt['materialResourceHashes'], client_hash)
    validate_owned_normal_dependencies(converted / 'resources', receipt['materialResourceHashes'])
    return verified


def stock_identity(conversion, expected_models):
    """Reject metadata that would choose a different height or rig at packaging."""
    parts = conversion.get('parts', [])
    require(len(parts) == len(expected_models) and {row['model'] + '.mdl' for row in parts} == expected_models,
            'Conversion has undeclared/duplicate models')
    require(conversion.get('modelPrefix') == 'pmh0'
            and conversion.get('rigMode') == 'stock-exact-game-fallback'
            and conversion.get('stockOtherPartsFromGame') is True
            and conversion.get('equipmentMode', 'stock-identity') == 'stock-identity',
            'Conversion changes stock Human rig/equipment identity')
    for field in ('height', 'stockReferenceHeight'):
        value = conversion.get(field)
        require(isinstance(value, (int, float)) and math.isfinite(value)
                and abs(value - STOCK_HEIGHT) < 1e-7, 'Conversion changes stock Human height: ' + field)


def thigh_attachment(config, model):
    part, joint = LIMB_ATTACHMENTS[model]
    require(config.get('part') == part and config.get('joint') == joint,
            'Limb model/part/stock joint association differs: ' + model)


def stage_manifest(root, slug):
    manifest = load(root / 'manifest.json')
    combinations = manifest.get('combinations', [])
    require(len(combinations) == 1, 'New limb stage must contain just one specimen')
    row = combinations[0]
    require(row.get('slug') == slug and slug == 'human_male_fit' and row.get('appearance') == 6
            and row.get('raceId') == 6 and row.get('gender') == 'male' and row.get('phenotype') == 0
            and not row.get('fixtureControl') and abs(row.get('height', 0) - STOCK_HEIGHT) < 1e-7,
            'New limb manifest changes candidate rig/height selection')
    return manifest


def limb_stage(root, client_hash, foot_material_pin=None):
    root = Path(root).resolve()
    receipt = load(root / 'stock-part-stage.json')
    material_proof=None
    if (root/'foot-material-patch.json').exists():
        from foot_material_contract import validate_foot_material_stage
        _,receipt,material_proof=validate_foot_material_stage(root,foot_material_pin,allow_native=True)
    else:require(not foot_material_pin,'Pinned foot material operation missing')
    config = receipt['configuration']
    model = config['model'] + '.mdl'
    require(model in LIMBS and config['prefix'] == 'pmh0' and config['gender'] == 'male'
            and config['raceId'] == 6, 'Only declared stock Human male limb replacements supported')
    thigh_attachment(config, model)
    require(receipt.get('stockControllersModified') is False and receipt.get('equipmentMode') == 'stock-identity'
            and receipt.get('diagnosticOnly') is True and receipt.get('paletteProof', {}).get('allLayer0Skin') is True,
            'Expected immutable stock rig, all-skin diagnostic limb')
    if not material_proof:
        for path, expected in receipt['frozenInputs'].items():
            require(sha(path) == expected, 'Frozen limb input changed: ' + path)
        for relative, expected in receipt['stagedFiles'].items():
            path = (root / relative).resolve()
            require(path.is_relative_to(root) and sha(path) == expected, 'Limb stage changed: ' + relative)
    converted = root / config['slug'] / 'converted'
    conversion = load(converted / 'conversion.json')
    stock_identity(conversion, {model})
    require([row['model'] + '.mdl' for row in conversion['parts']] == [model]
            and conversion.get('rigMode') == 'stock-exact-game-fallback'
            and conversion.get('geometryStatus') == 'single-stock-part-diagnostic', 'Undeclared limb stage model')
    native, provenance = native_unit(converted, {model}, client_hash)
    text = (converted / 'ascii' / model).read_text(encoding='ascii')
    require(not re.search(r'(?mi)^\s*newanim\s', text) and re.search(
        r'(?mi)^\s*setsupermodel\s+' + re.escape(config['model']) + r'\s+NULL\s*$', text),
        'Limb ASCII defines animations or changes its supermodel')
    require(native['materialResourceHashes'] == conversion['ownedResourceHashes'], 'Stage/native material association differs')
    if material_proof:receipt=dict(receipt);receipt['footMaterialProof']=material_proof
    return converted, conversion, native, provenance, receipt


def compose(args):
    preserved_models = parse_preserved_parts(getattr(args, 'preserved_parts', 'chest,pelvis'))
    preserved = args.preserved.resolve()
    preserved_receipt_path = preserved / 'native-compile.json'
    require(sha(preserved_receipt_path) == args.preserved_receipt_sha256, 'Preserved receipt hash differs')
    patch_pin = getattr(args, 'preserved_material_patch_sha256', None)
    prior, prior_provenance = native_unit(preserved, preserved_models, material_patch_sha256=patch_pin)
    parent_runtime = None
    if patch_pin:
        from material_patch_contract import validate_material_patch
        parent_runtime, _ = validate_material_patch(preserved)
    validate_receipt_lineage(prior, require_composition=preserved_models != PRESERVED)
    client_hash = prior['clientSha256']
    require({name: sha(preserved / 'resources' / name) for name in PRESERVED} == PROTECTED_NATIVE,
            'Accepted chest/pelvis binary differs')
    prior_conversion = load(preserved / 'conversion.json')
    stock_identity(prior_conversion, preserved_models)
    foot_pins=getattr(args,'foot_material_patch_sha256',None) or []
    require(len(foot_pins)==len(set(foot_pins)),'Duplicate foot material operation pins')
    used=[];units=[]
    for path in args.stage:
        material_path=path/'foot-material-patch.json';foot_pin=sha(material_path) if material_path.exists() else None
        if foot_pin:require(foot_pin in foot_pins,'Foot shade descendant requires explicit composition opt-in');used.append(foot_pin)
        units.append(limb_stage(path,client_hash,foot_pin))
    require(set(used)==set(foot_pins),'Unused foot material operation pin')
    names = [unit[2]['models'][0]['name'] for unit in units]
    validate_new_parts([unit[4]['configuration']['part'] for unit in units], preserved_models)
    if any(unit[4]['configuration']['part']=='footl' for unit in units):
        require(parent_runtime and parent_runtime.get('pmh0_pelvis001.plt') == CORRECTED_PELVIS_PLT,
            'Feet require explicitly inherited selected corrected pelvis palette')
    slug = units[0][4]['configuration']['slug']
    require(all(unit[4]['configuration']['slug'] == slug for unit in units), 'Stage slugs differ')
    manifest = stage_manifest(args.stage[0].resolve(), slug)
    require(all(stage_manifest(path.resolve(), slug) == manifest for path in args.stage), 'Limb manifests differ')
    deps = dict(prior['materialResourceHashes'])
    models = copy.deepcopy(prior['models'])
    for unit in units:
        require(set(deps).isdisjoint(unit[2]['materialResourceHashes']), 'Material ownership collision')
        deps.update(unit[2]['materialResourceHashes'])
        models.extend(copy.deepcopy(unit[2]['models']))
    baseline_hashes = file_hashes(args.stage[0].resolve() / 'baseline')
    require(set(baseline_hashes) == {'human-template.json', 'ttr01.set', 'ttr01_edge.2da'}, 'Undeclared fixture baseline')
    require(all(file_hashes(path.resolve() / 'baseline') == baseline_hashes for path in args.stage), 'Fixture baselines differ')
    comparator = args.comparator.resolve()
    control_conversion = load(comparator / 'conversion.json')
    aliases = control_conversion.get('stockAliases', [])
    require(control_conversion.get('fixtureControl') is True and control_conversion.get('modelPrefix') == 'pmx0'
            and control_conversion.get('geometryStatus') == 'stock-control', 'Expected private actual stock comparator')
    control_names = {Path(row['source']).name.replace('pmh0', 'pmx0') for row in aliases}
    require(len(control_names) == len(aliases) == 20, 'Expected exact stock comparator aliases')
    control, control_provenance = native_unit(comparator, control_names, client_hash)
    bank = Path(units[0][4]['configuration']['stockBaseline']).resolve()
    for row in aliases:
        origin = Path(row['source']).resolve()
        require(origin.is_relative_to(bank / 'ascii') and sha(origin) == row['sourceSha256'], 'Comparator stock origin differs')
        name = origin.stem.replace('pmh0', 'pmx0')
        expected_text = origin.read_text(encoding='cp1252').replace('pmh0', 'pmx0')
        if name != 'pmx0':
            expected_text = re.sub(r'(?mi)^\s*bitmap\s+\S+', '  bitmap ' + name, expected_text)
        actual_alias = comparator / 'ascii' / (name + '.mdl')
        require(actual_alias.read_text(encoding='cp1252') == expected_text
                and sha(actual_alias) == row['aliasSha256'], 'Comparator alias changed stock surface/controllers')
        if row.get('paletteSha256'):
            require(sha(bank / 'raw' / (origin.stem + '.plt')) == row['paletteSha256']
                    and sha(comparator / 'resources' / (name + '.plt')) == row['paletteSha256'], 'Comparator palette differs')
    require(len(aliases) == len(control_names), 'Comparator aliases missing')
    fixture_resources = comparator.parents[1] / 'fixture-resources'
    require(set(file_hashes(fixture_resources)) == {'appearance.2da'}, 'Expected private comparator appearance table only')
    prior_manifest = load(comparator.parents[1] / 'manifest.json')
    controls = [row for row in prior_manifest['combinations'] if row['slug'] == 'stock_human_male_fit']
    require(len(controls) == 1 and controls[0].get('fixtureControl') is True and controls[0]['gender'] == 'male'
            and controls[0]['phenotype'] == 0 and controls[0].get('raceId') == 6
            and controls[0]['appearance'] != 6, 'Private comparator manifest association differs')
    manifest['combinations'].append(copy.deepcopy(controls[0]))
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    target = output / slug / 'converted'
    (target / 'ascii').mkdir(parents=True)
    (target / 'resources').mkdir()
    provenance = output / 'native-provenance'
    provenance.mkdir()
    all_origins = [(preserved, prior, prior_provenance)] + [(u[0], u[2], u[3]) for u in units]
    source_receipts = []
    for index, (origin, native, recorded) in enumerate(all_origins):
        for name in file_hashes(origin / 'ascii'):
            shutil.copyfile(origin / 'ascii' / name, target / 'ascii' / name)
        for name in file_hashes(origin / 'resources'):
            shutil.copyfile(origin / 'resources' / name, target / 'resources' / name)
        name = 'unit-' + str(index) + '-native-compile.json'
        shutil.copyfile(origin / 'native-compile.json', provenance / name)
        source_receipts.append(recorded)
    combined = {'client': prior['client'], 'clientSha256': client_hash, 'complete': True,
                'models': models, 'materialResourceHashes': deps,
                'composition': {'kind': 'verified-independent-native-units', 'compiledHere': False,
                                'acceptedNeighboursRecompiled': False, 'sourceReceipts': source_receipts}}
    conversion = copy.deepcopy(prior_conversion)
    conversion['parts'] += [copy.deepcopy(u[1]['parts'][0]) for u in units]
    conversion['ownedResourceHashes'] = file_hashes(target / 'resources')
    conversion['equipmentMode'] = 'stock-identity'
    conversion['limbNativeCompiled'] = True
    save(target / 'conversion.json', conversion)
    save(target / 'native-compile.json', combined)
    if parent_runtime:
        runtime = dict(deps); runtime['pmh0_pelvis001.plt'] = parent_runtime['pmh0_pelvis001.plt']
        save(target / 'material-patch.json', {'schemaVersion':1,
            'kind':'inherited-runtime-pelvis-skin-plt-offset', 'resource':'pmh0_pelvis001.plt',
            'parentConverted':str(preserved), 'parentPatchSha256':patch_pin,
            'parentNativeReceiptSha256':sha(preserved_receipt_path),
            'nativeReceiptSha256':sha(target / 'native-compile.json'),
            'newParts':[unit[4]['configuration']['part'] for unit in units],
            'newSha256':runtime['pmh0_pelvis001.plt'], 'runtimeMaterialResourceHashes':runtime})
    control_target = output / 'stock_human_male_fit' / 'converted'
    (control_target / 'ascii').mkdir(parents=True)
    (control_target / 'resources').mkdir()
    for directory in ['ascii', 'resources']:
        for name in file_hashes(comparator / directory):
            shutil.copyfile(comparator / directory / name, control_target / directory / name)
    for name in ['conversion.json', 'native-compile.json']:
        shutil.copyfile(comparator / name, control_target / name)
    save(output / 'manifest.json', manifest)
    (output / 'baseline').mkdir()
    for name in baseline_hashes:
        shutil.copyfile(args.stage[0].resolve() / 'baseline' / name, output / 'baseline' / name)
    (output / 'fixture-resources').mkdir()
    shutil.copyfile(fixture_resources / 'appearance.2da', output / 'fixture-resources' / 'appearance.2da')
    if parent_runtime:
        from audit_thigh_package import verify_native as verify_runtime
        verify_runtime(target, preserved_models | set(names), allow_material_patch=True)
    else:
        verify_native(target, preserved_models | set(names), deps, client_hash)
    require(all(sha(target / 'ascii' / name) == sha(preserved / 'ascii' / name) for name in preserved_models)
            and all(sha(target / 'resources' / name) == digest for name, digest in file_hashes(preserved / 'resources').items()),
            'Composition altered preserved ASCII/native/material bytes')
    require({name: sha(target / 'resources' / name) for name in PRESERVED} == PROTECTED_NATIVE, 'Composition altered preserved binary')
    record = {'schemaVersion': 1, 'declaredReplacementModels': sorted(preserved_models | set(names)),
              'helperDependencyHashes':{'stock_limb_contract.py':sha(Path(__file__).with_name('stock_limb_contract.py'))},
              'preservedModels': sorted(preserved_models), 'newLimbModels': sorted(names),
              'preservedNativeReceipt': prior_provenance, 'newLimbReceipts': source_receipts[1:],
              'comparatorNativeReceipt': control_provenance, 'acceptedNeighboursBytesExact': True,
              'footMaterialPatches':[u[4]['footMaterialProof'] for u in units if u[4].get('footMaterialProof')],
              'equipmentMode': 'stock-identity', 'compilerLaunched': False, 'clientAccepted': False,
              'files': {str(p.relative_to(output)): sha(p) for p in sorted(output.rglob('*')) if p.is_file()}}
    save(output / 'native-composition.json', record)
    print(json.dumps({'output': str(output), 'models': record['declaredReplacementModels'], 'acceptedNeighboursBytesExact': True}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', type=Path, action='append', required=True)
    parser.add_argument('--foot-material-patch-sha256',action='append',help='Explicit pin for each declared foot-only shade descendant.')
    parser.add_argument('--preserved', type=Path, required=True)
    parser.add_argument('--preserved-receipt-sha256', required=True)
    parser.add_argument('--preserved-material-patch-sha256',
                        help='Required explicit pin when donor carries the accepted runtime pelvis palette correction.')
    parser.add_argument('--preserved-parts', default='chest,pelvis',
                        help='Compatibility default chest,pelvis. Feet explicitly preserve chest,pelvis,legl,legr,shinl,shinr.')
    parser.add_argument('--comparator', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    compose(parser.parse_args())


if __name__ == '__main__':
    main()
