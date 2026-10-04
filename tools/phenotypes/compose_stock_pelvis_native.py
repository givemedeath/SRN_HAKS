"""Prepare pelvis-only native compile inputs, then compose verified native units.

This helper never launches the compiler or game. `prepare` creates a fresh
pelvis-only converted directory for native_compile.py; `compose` consumes that
real completed receipt and the preserved chest/comparator receipts. No torso
recompilation, receipt fabrication or historical custom-body folder copying.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import shutil

import stage_stock_pelvis as stage

sha = stage.stock.sha
require = stage.stock.require
save = stage.stock.save
CHEST = stage.CHEST + '.mdl'
PELVIS = stage.MODEL + '.mdl'
COMPARATOR_SLUG = 'stock_human_male_fit'


def file_hashes(directory):
    require(directory.is_dir(), 'Missing declared directory: ' + str(directory))
    require(all(path.is_file() for path in directory.iterdir()), 'Nested/undeclared resource directory')
    return {path.name: sha(path) for path in sorted(directory.iterdir())}


def verify_native(converted, models, dependencies, client_hash):
    """Verify a real native unit with exact model/dependency ownership."""
    converted = Path(converted).resolve()
    receipt_path = converted / 'native-compile.json'
    receipt = json.loads(receipt_path.read_text())
    require(receipt.get('complete') is True and receipt.get('clientSha256') == client_hash,
            'Native unit incomplete or client hash differs')
    entries = receipt.get('models', [])
    require(len(entries) == len(models) and {row['name'] for row in entries} == set(models),
            'Native unit has missing/extra/duplicate model receipts')
    require(receipt.get('materialResourceHashes') == dependencies, 'Native unit dependency dictionary differs')
    require(set(file_hashes(converted / 'ascii')) == set(models), 'Native unit has undeclared ASCII model')
    resources = file_hashes(converted / 'resources')
    require(set(resources) == set(models) | set(dependencies), 'Native unit has missing/undeclared resources')
    for name, expected in dependencies.items(): require(resources[name] == expected, 'Native material changed: ' + name)
    for row in entries:
        name = row['name']; source = converted / 'ascii' / name; binary = converted / 'resources' / name
        require(sha(source) == row['sourceSha256'] and sha(binary) == row['binarySha256'], 'Stale compiled model: ' + name)
        require(binary.read_bytes()[:4] == b'\0\0\0\0', 'Invalid native binary: ' + name)
        require(row.get('bytes') == binary.stat().st_size, 'Native binary length differs: ' + name)
    return receipt, {'path': str(receipt_path), 'sha256': sha(receipt_path), 'models': sorted(models),
                     'materialResourceHashes': dependencies}


def combine_receipts(chest, pelvis, provenance):
    require(chest.get('complete') is True and pelvis.get('complete') is True, 'Incomplete independent native receipt')
    require(chest.get('clientSha256') == pelvis.get('clientSha256') and chest.get('clientSha256'), 'Independent compiler client hashes differ')
    require(len(chest.get('models', [])) == len(pelvis.get('models', [])) == 1
        and chest['models'][0]['name'] == CHEST and pelvis['models'][0]['name'] == PELVIS, 'Expected independent chest and pelvis units only')
    chest_deps = chest.get('materialResourceHashes', {}); pelvis_deps = pelvis.get('materialResourceHashes', {})
    require(set(chest_deps).isdisjoint(pelvis_deps), 'Independent part material ownership collides')
    return {'client': pelvis['client'], 'clientSha256': pelvis['clientSha256'],
        'materialResourceHashes': {**chest_deps, **pelvis_deps},
        'models': copy.deepcopy(chest['models'] + pelvis['models']), 'complete': True,
        'composition': {'kind': 'verified-independent-native-units', 'compiledHere': False,
            'chestRecompiled': False, 'perModelReceipts': provenance}}


def verify_stage(root):
    root = Path(root).resolve(); receipt_path = root / 'stock-pelvis-stage.json'
    receipt = json.loads(receipt_path.read_text()); config = receipt['configuration']; slug = config['slug']
    require(receipt.get('frozenTorsoBytesExact') is True and receipt.get('stockControllersModified') is False
        and receipt.get('equipmentMode') == 'stock-identity' and receipt.get('diagnosticOnly') is True,
        'Require declared stock pelvis stage preserving frozen torso/rig')
    require(receipt.get('rawAttributeAsciiProof', {}).get('union', {}).get('everySourceFaceExactlyOnce') is True,
            'Stage lacks exact semantic source-face union proof')
    # Validate original input association and immutable stage payloads, never trust
    # a changed stage merely because its conversion.json was edited afterward.
    for path, expected in receipt['frozenInputs'].items(): stage.verify_file(path, expected, 'Original stage input')
    for relative, expected in receipt['stagedFiles'].items():
        path = (root / relative).resolve(); require(path.is_relative_to(root), 'Stage receipt path escapes root')
        stage.verify_file(path, expected, 'Original staged payload')
    converted = root / slug / 'converted'; conversion = json.loads((converted / 'conversion.json').read_text())
    require(conversion.get('geometryStatus') == 'single-stock-part-diagnostic'
        and conversion.get('equipmentMode', 'stock-identity') == 'stock-identity'
        and conversion.get('rigMode') == 'stock-exact-game-fallback'
        and [part['model'] for part in conversion['parts']] == [stage.CHEST, stage.MODEL], 'Undeclared stock replacement model set')
    require(set(file_hashes(converted / 'ascii')) == {CHEST, PELVIS}, 'Stage has undeclared ASCII models')
    resources = file_hashes(converted / 'resources')
    require(set(resources) == stage.CHEST_RESOURCES | stage.PELVIS_MATERIALS, 'Prepare expects untouched pre-compile stage only')
    require(resources == conversion['ownedResourceHashes'], 'Stage owned resource hashes differ')
    frozen = config['frozenTorso']; require({name: resources[name] for name in stage.CHEST_RESOURCES} == frozen['resourceHashes'],
                                         'Frozen chest resources differ')
    require(sha(converted / 'ascii' / CHEST) == frozen['asciiSha256'], 'Frozen chest ASCII differs')
    preserved_receipt = root / 'preserved-torso/native-compile.json'
    stage.verify_file(preserved_receipt, frozen['nativeReceiptSha256'], 'Preserved chest native receipt')
    original_chest, _, _ = stage.verify_torso(config)
    chest, chest_provenance = verify_native(original_chest, {CHEST},
        {name: digest for name, digest in frozen['resourceHashes'].items() if name != CHEST}, frozen['clientSha256'])
    require(chest_provenance['sha256'] == sha(preserved_receipt), 'Imported chest receipt association differs')
    return root, converted, receipt, conversion, chest, chest_provenance


def prepare(root, output):
    root, converted, receipt, conversion, chest, chest_origin = verify_stage(root)
    output = Path(output).resolve(); output.mkdir(exist_ok=False)
    unit = output / 'pelvis-compile-unit/converted'
    (unit / 'ascii').mkdir(parents=True); (unit / 'resources').mkdir()
    shutil.copyfile(converted / 'ascii' / PELVIS, unit / 'ascii' / PELVIS)
    for name in stage.PELVIS_MATERIALS: shutil.copyfile(converted / 'resources' / name, unit / 'resources' / name)
    dependencies = file_hashes(unit / 'resources')
    plan = {'schemaVersion': 1, 'stage': str(root), 'stageReceiptSha256': sha(root / 'stock-pelvis-stage.json'),
        'stageConversionSha256': sha(converted / 'conversion.json'), 'slug': receipt['configuration']['slug'],
        'clientSha256': chest['clientSha256'], 'pelvisCompileUnit': str(unit),
        'pelvisAsciiSha256': sha(unit / 'ascii' / PELVIS), 'pelvisMaterialResourceHashes': dependencies,
        'preservedChest': chest_origin, 'pelvisCompiled': False, 'compilerLaunched': False, 'clientLaunched': False,
        'compilerNextStep': 'Run native_compile.py on pelvisCompileUnit with a separate compile user-directory. Do not compile combined chest+pelvis stage.'}
    save(output / 'prepare.json', plan)
    shutil.copyfile(Path(__file__), output / 'executed-compose-stock-pelvis-native.py')
    return plan


def verify_comparator(stage_root, donor, client_hash):
    staged = stage_root / COMPARATOR_SLUG / 'converted'; donor = Path(donor).resolve()
    current = json.loads((staged / 'conversion.json').read_text())
    require(current.get('fixtureControl') is True and current.get('geometryStatus') == 'stock-control'
        and current.get('modelPrefix') == 'pmx0', 'Comparator must be private actual stock control')
    models = file_hashes(staged / 'ascii'); dependencies = file_hashes(staged / 'resources')
    require(all(name.startswith('pmx0') and name.endswith('.mdl') for name in models)
        and all(name.startswith('pmx0_') and name.endswith('.plt') for name in dependencies), 'Comparator resource ownership invalid')
    require(len(current['stockAliases']) == len(models) == 20, 'Unexpected stock comparator model set')
    donor_conversion = json.loads((donor / 'conversion.json').read_text())
    keys = ['sourceSha256', 'aliasSha256', 'paletteSha256']
    require([[row.get(key) for key in keys] for row in current['stockAliases']]
        == [[row.get(key) for key in keys] for row in donor_conversion['stockAliases']], 'Stock comparator donor surface/palette association differs')
    require(file_hashes(donor / 'ascii') == models, 'Comparator donor aliases differ from actual staged stock')
    native, provenance = verify_native(donor, set(models), dependencies, client_hash)
    return staged, donor, native, provenance


def compose(prepared, output, comparator_donor=None):
    prepared = Path(prepared).resolve(); plan = json.loads((prepared / 'prepare.json').read_text())
    root = Path(plan['stage']).resolve()
    stage.verify_file(root / 'stock-pelvis-stage.json', plan['stageReceiptSha256'], 'Prepared stage receipt')
    stage_root, converted, receipt, conversion, chest, chest_origin = verify_stage(root)
    stage.verify_file(converted / 'conversion.json', plan['stageConversionSha256'], 'Prepared conversion')
    unit = prepared / 'pelvis-compile-unit/converted'
    require(Path(plan['pelvisCompileUnit']).resolve() == unit, 'Compile unit escapes preparation')
    stage.verify_file(unit / 'ascii' / PELVIS, plan['pelvisAsciiSha256'], 'Prepared pelvis ASCII')
    require(sha(unit / 'ascii' / PELVIS) == sha(converted / 'ascii' / PELVIS), 'Pelvis compile source differs from stage')
    require(plan['pelvisMaterialResourceHashes'] == {name: sha(converted / 'resources' / name) for name in stage.PELVIS_MATERIALS},
            'Prepared pelvis dependencies differ from original stage')
    pelvis, pelvis_origin = verify_native(unit, {PELVIS}, plan['pelvisMaterialResourceHashes'], plan['clientSha256'])
    combined = combine_receipts(chest, pelvis, {CHEST: chest_origin, PELVIS: pelvis_origin})
    manifest = json.loads((stage_root / 'manifest.json').read_text())
    expected_slugs = {plan['slug']}
    comparator = None
    if any(row['slug'] == COMPARATOR_SLUG for row in manifest['combinations']):
        require(comparator_donor is not None, 'Declared stock comparator needs an independently verified native donor')
        comparator = verify_comparator(stage_root, comparator_donor, plan['clientSha256']); expected_slugs.add(COMPARATOR_SLUG)
    require({row['slug'] for row in manifest['combinations']} == expected_slugs
        and len(manifest['combinations']) == len(expected_slugs), 'Manifest has undeclared/duplicate specimen')
    baseline_files = file_hashes(stage_root / 'baseline')
    require(set(baseline_files) == {'human-template.json', 'ttr01.set', 'ttr01_edge.2da'}, 'Undeclared fixture baseline')
    fixture_files = file_hashes(stage_root / 'fixture-resources') if (stage_root / 'fixture-resources').exists() else {}
    require(set(fixture_files) == ({'appearance.2da'} if comparator else set()), 'Undeclared fixture-only resources')
    output = Path(output).resolve(); output.mkdir(exist_ok=False)
    destination = output / plan['slug'] / 'converted'
    (destination / 'ascii').mkdir(parents=True); (destination / 'resources').mkdir()
    for name in [CHEST, PELVIS]: shutil.copyfile(converted / 'ascii' / name, destination / 'ascii' / name)
    for name in stage.CHEST_RESOURCES | stage.PELVIS_MATERIALS:
        shutil.copyfile(converted / 'resources' / name, destination / 'resources' / name)
    shutil.copyfile(unit / 'resources' / PELVIS, destination / 'resources' / PELVIS)
    final_conversion = copy.deepcopy(conversion)
    final_conversion['ownedResourceHashes'] = file_hashes(destination / 'resources')
    final_conversion['pelvisNativeCompiled'] = True
    final_conversion['preservedNativeReceipt'] = str(output / 'native-provenance/chest-native-compile.json')
    save(destination / 'conversion.json', final_conversion); save(destination / 'native-compile.json', combined)
    provenance = output / 'native-provenance'; provenance.mkdir()
    for name, origin in [('chest-native-compile.json', chest_origin), ('pelvis-native-compile.json', pelvis_origin)]:
        shutil.copyfile(origin['path'], provenance / name)
    shutil.copyfile(stage_root / 'stock-pelvis-stage.json', provenance / 'original-stock-pelvis-stage.json')
    shutil.copyfile(stage_root / 'manifest.json', output / 'manifest.json')
    (output / 'baseline').mkdir()
    for name in baseline_files: shutil.copyfile(stage_root / 'baseline' / name, output / 'baseline' / name)
    if fixture_files:
        (output / 'fixture-resources').mkdir()
        for name in fixture_files: shutil.copyfile(stage_root / 'fixture-resources' / name, output / 'fixture-resources' / name)
    comparator_origin = None
    if comparator:
        staged_comparator, donor, native_comparator, comparator_origin = comparator
        target = output / COMPARATOR_SLUG / 'converted'
        (target / 'ascii').mkdir(parents=True); (target / 'resources').mkdir()
        for name in file_hashes(staged_comparator / 'ascii'): shutil.copyfile(staged_comparator / 'ascii' / name, target / 'ascii' / name)
        for name in file_hashes(donor / 'resources'): shutil.copyfile(donor / 'resources' / name, target / 'resources' / name)
        shutil.copyfile(staged_comparator / 'conversion.json', target / 'conversion.json')
        shutil.copyfile(donor / 'native-compile.json', target / 'native-compile.json')
    # Independently recheck the actual composed inputs as the builder will see them.
    final_native, _ = verify_native(destination, {CHEST, PELVIS}, combined['materialResourceHashes'], combined['clientSha256'])
    require(sha(destination / 'resources' / CHEST) == receipt['configuration']['frozenTorso']['resourceHashes'][CHEST], 'Composition changed frozen chest binary')
    result = {'schemaVersion': 1, 'prepared': str(prepared), 'prepareSha256': sha(prepared / 'prepare.json'),
        'originalStage': str(stage_root), 'originalStageReceiptSha256': plan['stageReceiptSha256'],
        'declaredReplacementModels': [stage.CHEST, stage.MODEL], 'stockIdentityEquipment': True,
        'nativeReceiptComposition': combined['composition'], 'comparatorNativeProvenance': comparator_origin,
        'frozenTorsoBytesExact': True, 'compilerLaunched': False, 'chestRecompiled': False,
        'packageBuilt': False, 'clientLaunched': False, 'clientAccepted': False,
        'files': {str(path.relative_to(output)): sha(path) for path in sorted(output.rglob('*')) if path.is_file()}}
    save(output / 'native-composition.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='phase', required=True)
    first = sub.add_parser('prepare'); first.add_argument('--stage', required=True, type=Path); first.add_argument('--output', required=True, type=Path)
    second = sub.add_parser('compose'); second.add_argument('--prepared', required=True, type=Path)
    second.add_argument('--output', required=True, type=Path); second.add_argument('--comparator-donor', type=Path)
    args = parser.parse_args()
    result = prepare(args.stage, args.output) if args.phase == 'prepare' else compose(args.prepared, args.output, args.comparator_donor)
    print(json.dumps({'phase': args.phase, 'output': str(args.output.resolve()), 'compilerLaunched': False,
                      'clientLaunched': False, 'chestRecompiled': False}))


if __name__ == '__main__': main()
