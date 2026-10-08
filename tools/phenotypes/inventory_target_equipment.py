"""Freeze installed Human phenotype0 equipment without user overrides.

This is an input inventory, never an equipment acceptance receipt. Robes and
cloaks retain skin data and are declared separately from rigid armor parts.
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
import subprocess

from audit_geometry import arrays
from pipeline import digest, save_json
from retarget import NODE

PARTS = ('chest', 'pelvis', 'neck', 'belt', 'bicepl', 'bicepr', 'forel',
         'forer', 'handl', 'handr', 'legl', 'legr', 'shinl', 'shinr',
         'footl', 'footr', 'shol', 'shor', 'robe')
BARE = set(PARTS) - {'belt', 'shol', 'shor', 'robe'}
MODEL = re.compile(r'^pmh0_(' + '|'.join(PARTS) + r')(\d{3})\.mdl$')
CLOAK = re.compile(r'^pmh0_cloak_(\d{3})\.mdl$')
HELM = re.compile(r'^helm_\d{3}\.mdl$')
SHIELD = re.compile(r'^ash(?:sw|lw|ss|ls|to)_[a-z0-9_]+\.mdl$')


def select_models(names, source_prefix='pmh0'):
    if source_prefix not in ('pmh0', 'pfh0'):
        raise ValueError('Installed Human male/female phenotype0 source prefix required')
    model_pattern = re.compile(r'^' + source_prefix + r'_(' + '|'.join(PARTS) + r')(\d{3})\.mdl$')
    cloak_pattern = re.compile(r'^' + source_prefix + r'_cloak_(\d{3})\.mdl$')
    selected, excluded = [], []
    for name in sorted(set(names)):
        match = model_pattern.fullmatch(name)
        if match:
            part, style = match[1], int(match[2])
            entry = {'resource': name, 'part': part, 'style': style,
                     'category': 'robe' if part == 'robe' else 'rigid-armor'}
            (excluded if part in BARE and style == 1 else selected).append(entry)
        elif cloak_pattern.fullmatch(name):
            selected.append({'resource': name, 'part': 'cloak',
                             'style': int(cloak_pattern.fullmatch(name)[1]), 'category': 'cloak'})
        elif HELM.fullmatch(name):
            selected.append({'resource': name, 'part': 'helmet',
                             'style': int(name[5:8]), 'category': 'helmet'})
        elif SHIELD.fullmatch(name):
            selected.append({'resource': name, 'part': 'shield', 'category': 'shield'})
    return selected, excluded


def inspect_model(text):
    blocks = list(NODE.finditer(text.split('endmodelgeom', 1)[0]))
    result = []
    for block in blocks:
        body = block[3]
        def field(key):
            found = re.search(r'(?mi)^\s*' + key + r'\s+([^\n]+)', body)
            return found[1].strip() if found else None
        # weights contain bone names; do not feed them to the numeric parser.
        weights = re.search(r'(?mi)^\s*weights\s+(\d+)\s*\n', body)
        rows = body[weights.end():].splitlines()[:int(weights[1])] if weights else []
        weighted = sorted(set(token for row in rows for token in row.split()
                              if not re.fullmatch(r'[+\-\d.eE]+', token)))
        result.append({'name': block[2], 'type': block[1].lower(),
                       'parent': field('parent'), 'position': field('position'),
                       'orientation': field('orientation'), 'scale': field('scale'), 'render': field('render'),
                       'vertices': len(arrays(body, 'verts')), 'faces': len(arrays(body, 'faces')),
                       'tverts': len(arrays(body, 'tverts')), 'normals': len(arrays(body, 'normals')),
                       'weights': len(rows), 'weightedBones': weighted,
                       'weightsText': '\n'.join(rows) if rows else None,
                       'bitmap': field('bitmap'), 'materialname': field('materialname')})
    supermodel = re.search(r'(?mi)^setsupermodel\s+\S+\s+(\S+)', text)
    return {'nodes': result, 'supermodel': supermodel[1] if supermodel else None,
            'localAnimationCount': len(re.findall(r'(?mi)^newanim\s', text)),
            'meshTypes': dict(Counter(node['type'] for node in result if node['vertices'])),
            'requiresSkinBindPath': any(node['type'] == 'skin' or node['weights'] for node in result),
            'weightedBones': sorted(set(bone for node in result for bone in node['weightedBones']))}


def freeze(args):
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if (output / 'inventory.json').exists():
        raise RuntimeError('Refusing to replace a frozen equipment inventory')
    prior = json.loads(args.resume_from.read_text()) if args.resume_from else None
    source_prefix = getattr(args, 'source_prefix', 'pmh0')
    if prior and prior['sourcePrefix'] != source_prefix:
        raise RuntimeError('Prior equipment inventory belongs to a different source prefix')
    prior_resources = {row['name']: row for row in prior['models'] + prior['dependencies']} if prior else {}
    if prior:
        for row in prior_resources.values():
            if digest(Path(row['rawPath'])) != row['sha256']:
                raise RuntimeError('Frozen prior equipment input changed: ' + row['name'])
            if 'asciiPath' in row and digest(Path(row['asciiPath'])) != row['asciiSha256']:
                raise RuntimeError('Frozen prior equipment ASCII changed: ' + row['name'])
    user = args.user_directory.resolve()
    if not (user / 'override').is_dir() or any((user / 'override').iterdir()):
        raise RuntimeError('Equipment inventory requires an existing empty override directory')
    grep, cat = (args.tool_directory / ('nwn_resman_' + name + '.exe') for name in ('grep', 'cat'))
    tool_pins = {str(path.resolve()): digest(path) for path in (grep, cat, args.decompiler)}
    if prior and prior['toolPins'] != tool_pins:
        raise RuntimeError('Inventory tools differ from the prior extraction')
    base = ['--root', str(args.game_root.resolve()), '--userdirectory', str(user), '--no-ovr']
    view = subprocess.run([str(grep), *base, '--all', '--details'], capture_output=True, check=True).stdout
    view_path = output / ('installed-resman-view.complete-v2.txt' if prior else 'installed-resman-view.txt')
    view_path.write_bytes(view)
    locations = {row.split()[0].lower(): row for row in view.decode('utf-8').splitlines() if row.strip()}
    selected, excluded = select_models(locations, source_prefix)
    if not selected or {row['part'] for row in selected if row['category'] == 'rigid-armor'} != set(PARTS) - {'robe'}:
        raise RuntimeError('Installed armor inventory is incomplete')
    raw, ascii_dir = output / 'raw', output / 'ascii'
    raw.mkdir(exist_ok=True); ascii_dir.mkdir(exist_ok=True)

    def extract(name):
        if name not in locations:
            raise RuntimeError('Missing installed equipment dependency: ' + name)
        path = raw / name
        if name in prior_resources:
            return {key: prior_resources[name][key] for key in ('name', 'rawPath', 'sha256', 'bytes', 'effectiveLocation')}
        if path.exists():
            raise RuntimeError('Unreceipted extraction already exists: ' + name)
        data = subprocess.run([str(cat), *base, name], capture_output=True, check=True).stdout
        if not data:
            raise RuntimeError('Empty installed equipment dependency: ' + name)
        path.write_bytes(data)
        return {'name': name, 'rawPath': str(path), 'sha256': digest(path),
                'bytes': len(data), 'effectiveLocation': locations[name]}

    def model(entry):
        record = {**entry, **extract(entry['resource'])}
        source, target = Path(record['rawPath']), ascii_dir / entry['resource']
        if entry['resource'] in prior_resources and 'asciiPath' in prior_resources[entry['resource']]:
            pass
        elif source.read_bytes()[:4] == b'\0\0\0\0':
            result = subprocess.run([str(args.decompiler), '-d', '-e', str(source), str(target)], capture_output=True)
            if result.returncode or not target.exists():
                raise RuntimeError('Equipment decompile failed: ' + source.name + ': ' + result.stderr.decode(errors='replace'))
        else:
            target.write_bytes(source.read_bytes())
        text = target.read_text(encoding='ascii')
        if 'newmodel' not in text or 'endmodelgeom' not in text:
            raise RuntimeError('Invalid decompiled equipment: ' + source.name)
        return {**record, 'asciiPath': str(target), 'asciiSha256': digest(target), **inspect_model(text)}

    with ThreadPoolExecutor(max_workers=args.workers) as workers:
        models = list(workers.map(model, selected))
    dependencies = set()
    missing = []
    for entry in models:
        entry['renderTextureDependencies'] = []
        for node in entry['nodes']:
            if not node['vertices'] or node['render'] == '0':
                continue
            bitmap = node['bitmap']
            if bitmap and bitmap.lower() not in ('null', '****'):
                matches = {bitmap.lower() + ext for ext in ('.plt', '.tga', '.dds', '.mtr')
                           if bitmap.lower() + ext in locations}
                if not matches:
                    palette = Path(entry['resource']).stem + '.plt'
                    if palette in locations:
                        matches.add(palette)
                        entry.setdefault('unresolvedBitmapWithModelNamedPalette', []).append({'node': node['name'], 'bitmap': bitmap, 'palette': palette})
                    else:
                        missing.append({'model': entry['resource'], 'node': node['name'], 'bitmap': bitmap})
                dependencies.update(matches)
                entry['renderTextureDependencies'].extend(sorted(matches))
            material = node['materialname']
            if material and material.lower() + '.mtr' in locations:
                dependencies.add(material.lower() + '.mtr')
    dependencies.update(name for name in locations if name.startswith('parts_') and name.endswith('.2da'))
    dependencies.update({'armorparts.2da', 'baseitems.2da', 'armor.2da'})
    with ThreadPoolExecutor(max_workers=args.workers) as workers:
        resources = list(workers.map(extract, sorted(dependencies)))
    weapons = sorted(name for name in locations if re.fullmatch(r'w[a-z0-9]+_[a-z0-9_]+\.mdl', name))
    result = {'schemaVersion': 1, 'kind': 'installed-target-equipment-inputs',
              'sourcePrefix': source_prefix, 'gameRoot': str(args.game_root.resolve()),
              'userDirectory': str(user), 'overridesDisabled': True,
              'resourceViewPath': str(view_path), 'resourceViewSha256': digest(view_path), 'toolPins': tool_pins,
              'inventoryHelperSha256': digest(Path(__file__)),
              'previousInventory': {'path': str(args.resume_from.resolve()), 'sha256': digest(args.resume_from)} if prior else None,
              'excludedCustomBareStyle001': excluded, 'models': models, 'dependencies': resources,
              'weaponModelInventory': weapons, 'missingDependencies': missing,
              'countsByPart': dict(sorted(Counter(row['part'] for row in models).items())),
              'rigRevision': None, 'profilesAccepted': False, 'clientAccepted': False,
              'limitations': ['Weapon resources are enumerated; chosen weapon fixtures still require mesh/socket measurements.',
                              'Robe and cloak skin weights are retained. Rigid Armory correction must never be used for skins.',
                              'Installed resources and source topology do not prove fit or motion on a target.']}
    for path, value in tool_pins.items():
        if digest(Path(path)) != value:
            raise RuntimeError('Inventory tool changed while extracting: ' + path)
    save_json(output / 'inventory.json', result)
    print(json.dumps({'models': len(models), 'countsByPart': result['countsByPart'],
                      'skinModels': sum(row['requiresSkinBindPath'] for row in models),
                      'dependencies': len(resources), 'missingDependencies': len(missing),
                      'weaponsEnumerated': len(weapons), 'profilesAccepted': False}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-root', type=Path, required=True)
    parser.add_argument('--user-directory', type=Path, required=True)
    parser.add_argument('--tool-directory', type=Path, required=True)
    parser.add_argument('--decompiler', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--source-prefix', choices=('pmh0', 'pfh0'), default='pmh0',
                        help='Installed Human family; independent inventories cannot resume across gender')
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--resume-from', type=Path, help='Verify and reuse an archived earlier extraction; add only newly inventoried inputs')
    args = parser.parse_args()
    if not 1 <= args.workers <= 8:
        parser.error('--workers must be between 1 and 8')
    freeze(args)


if __name__ == '__main__':
    main()
