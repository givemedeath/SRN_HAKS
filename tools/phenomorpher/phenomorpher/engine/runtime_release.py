"""Stage a runtime-optimized body release from verified libraries, repointed roots and 1K textures.

Every adopted file is pinned and tied to its passing evidence; private carriers are retired
only when no published chain still reaches them. The result is a fresh staging folder with
the pack files, the next contract, the retired-resource list, the inventory index and the
list of files to remove. It never edits the repository itself.
"""
import hashlib
import json
from copy import deepcopy
from pathlib import Path

from .anim_library import NativeModel, chain, contained, load_model, stock_files

PLAN_KIND = 'PhenoMorpher-runtime-adoption-plan'
CONTRACT_KIND = 'PhenoMorpher-game-ready-bodies'
LIBRARY_ROLE = 'animation-library'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def pinned(base, pin, label):
    path = (Path(base)/pin['path']).resolve(); data = path.read_bytes()
    if digest(data) != pin['sha256']:
        raise ValueError('Pinned input changed: ' + label)
    return path, data


def dump(data):
    return json.dumps(data, indent=2) + '\n'


def assets_index(contract, intro):
    """Clickable per-pack inventory in the published ASSETS.md layout."""
    packs = {}
    for row in contract['resources']:
        pack, name = row['path'].split('/', 1); packs.setdefault(pack, []).append(name)
    lines = ['# PhenoMorpher runtime file inventory', '', intro.format(count=len(contract['resources'])), '',
             'Review the [race routing](../../srn_2da/racialtypes.2da), [phenotype routing](../../srn_2da/phenotype.2da), '
             '[table validation](table-validation.json) and [publication validation](publication-validation.json) separately.']
    for pack in sorted(packs):
        lines += ['', f'## {pack} ({len(packs[pack])} files)', '', '| Resource |', '|---|']
        lines += [f'| [{name}](../../{pack}/{name}) |' for name in sorted(packs[pack])]
    return '\n'.join(lines) + '\n'


def adopt(root, plan_path, output):
    root = Path(root).resolve(); plan_path = Path(plan_path).resolve(); output = Path(output)
    plan = json.loads(plan_path.read_text(encoding='utf-8'))
    if plan.get('kind') != PLAN_KIND or plan.get('schemaVersion') != 1:
        raise ValueError('Runtime adoption plan required')
    _, base_bytes = pinned(root, plan['baseContract'], 'base contract'); base = json.loads(base_bytes)
    if base.get('kind') != CONTRACT_KIND:
        raise ValueError('Game-ready body contract required')
    _, retired_bytes = pinned(root, plan['retiredResources'], 'retired resources'); retired = json.loads(retired_bytes)
    stock_path, stock_bytes = pinned(root, plan['stock'], 'stock manifest'); stock, stock_paths = stock_files(stock_path)
    rows = {r['path']: r for r in base['resources']}
    for row in base['resources']:
        if digest((root/row['path']).read_bytes()) != row['sha256']:
            raise ValueError('Published resource differs from the base contract: ' + row['path'])
    staged = {}; evidence = {}
    # Libraries: restored bytes with an exact-payload restoration receipt.
    libraries = {}
    for item in plan['libraries']:
        path, data = pinned(root, item, item['resource']); _, receipt_bytes = pinned(root, item['restoration'], 'restoration')
        receipt = json.loads(receipt_bytes); model = NativeModel(data).decode()
        if receipt['restored']['sha256'] != item['sha256'] or receipt.get('exactSourcePayload') is not True:
            raise ValueError('Library lacks its exact restoration receipt: ' + item['resource'])
        if model['name'] + '.mdl' != item['resource'] or model['parent'] not in ('a_ba', 'a_fa'):
            raise ValueError('Library must be a stock-parented model named like its resource: ' + item['resource'])
        target = 'srn_body/' + item['resource']
        if target in rows:
            raise ValueError('Library name collides with a published resource: ' + target)
        libraries[model['name']] = model; staged[target] = data
        evidence[target] = {'restorationSHA256': item['restoration']['sha256']}
    # Roots: supermodel-only changes with a passing motion comparison against these exact files.
    roots = {}
    for item in plan['roots']:
        path, data = pinned(root, item, item['resource']); target = 'srn_body/' + item['resource']
        old = rows.get(target)
        if not old or old['role'] != 'fitted-rig':
            raise ValueError('Repointed resource is not a published fitted rig: ' + target)
        _, report_bytes = pinned(root, item['comparison'], 'comparison'); report = json.loads(report_bytes)
        model = NativeModel(data).decode()
        if not report.get('passed') or report['target'] + '.mdl' != item['resource'] or report['repointedRoot']['sha256'] != item['sha256']:
            raise ValueError('Root lacks a passing comparison for these bytes: ' + target)
        # The comparison must have read exactly this base contract, stock chain and old-chain payloads.
        inputs = report.get('inputs') or {}
        if (inputs.get('manifest', {}).get('sha256') != plan['baseContract']['sha256']
                or inputs.get('stockManifest', {}).get('sha256') != digest(stock_bytes)):
            raise ValueError('Comparison was not made against this base contract and stock chain: ' + target)
        for entry in inputs.get('oldChain', []):
            expected = (rows.get(entry['path'], {}).get('sha256') if entry['origin'] == 'pack'
                        else stock['models'].get(entry['name'], {}).get('sha256'))
            if expected is None or expected != entry['sha256']:
                raise ValueError('Comparison used different old-chain motion: ' + target + ' ' + entry['name'])
        if [e['name'] for e in inputs.get('oldChain', [])] != report.get('oldChain'):
            raise ValueError('Comparison does not pin its whole old chain: ' + target)
        parent = model['parent']
        if report['library'] and report['library']['name'] != parent:
            raise ValueError('Comparison library differs from the root supermodel: ' + target)
        if parent in libraries and report['library']['sha256'] != digest(staged['srn_body/' + parent + '.mdl']):
            raise ValueError('Comparison used a different library build: ' + target)
        if parent not in libraries and parent not in stock_paths and ('srn_body/' + parent + '.mdl') not in rows:
            raise ValueError('Root supermodel is neither adopted, published nor stock: ' + target)
        roots[target] = parent; staged[target] = data
        evidence[target] = {'comparisonSHA256': item['comparison']['sha256'], 'supermodel': {'from': load_model(root/target)['parent'], 'to': parent}}
    # Textures: each downsampled file must come from the published payload it replaces.
    receipt_path, receipt_bytes = pinned(root, plan['textures'], 'texture receipt'); texture_receipt = json.loads(receipt_bytes)
    for row in texture_receipt['resources']:
        source = contained(receipt_path.parent, row['path']); old = rows.get(row['path'])
        if not old or old['sha256'] != row['sourceSHA256']:
            raise ValueError('Downsampled texture does not replace its published payload: ' + row['path'])
        data = source.read_bytes()
        if digest(data) != row['sha256']:
            raise ValueError('Downsampled texture changed after its receipt: ' + row['path'])
        staged[row['path']] = data
        evidence[row['path']] = {'downsampledFrom': {'sha256': old['sha256'], 'bytes': old['bytes'], 'size': row['source']},
                                 'size': row['output']}
    # Closure: every target chain must end in the installed stock chain without private carriers.
    models = {}
    for row in base['resources']:
        if row['role'] in ('fitted-rig', 'rig-inheritance'):
            name = Path(row['path']).stem
            models[name] = NativeModel(staged.get(row['path']) or (root/row['path']).read_bytes()).decode()
    models.update(libraries)
    for name, path in stock_paths.items():
        models.setdefault(name, load_model(path))
    unrepointed = [t['modelPrefix'] for t in base['targets'] if 'srn_body/' + t['modelPrefix'] + '.mdl' not in roots
                   and any(rows.get('srn_body/' + n + '.mdl', {}).get('role') == 'rig-inheritance' and n != 'srn_fa_h0'
                           for n in chain(t['modelPrefix'], models))]
    if unrepointed:
        raise ValueError('Roots still reach private carriers: ' + ', '.join(unrepointed))
    reachable = set(); missing = []
    for target in base['targets']:
        names = chain(target['modelPrefix'], models); reachable.update(names)
        first = next((i for i, n in enumerate(names) if n in stock_paths), None)
        if first is None or 'a_ba' not in names[first:] or any(n not in stock_paths for n in names[first:]):
            missing.append(target['modelPrefix'])
    if missing:
        raise ValueError('Target chains do not reach the installed stock chain: ' + ', '.join(missing))
    removed = [r for r in base['resources'] if r['role'] == 'rig-inheritance' and Path(r['path']).stem not in reachable]
    removed_paths = {r['path'] for r in removed}
    # Contract.
    contract = deepcopy(base); contract['version'] = plan['version']; resources = []
    # Libraries follow the retained Human library, or the last retained rig row.
    kept = [r['path'] for r in base['resources'] if r['role'] in ('fitted-rig', 'rig-inheritance') and r['path'] not in removed_paths]
    anchor = 'srn_body/srn_fa_h0.mdl' if 'srn_body/srn_fa_h0.mdl' in kept else kept[-1]
    anchor_model = Path(anchor).stem
    for row in base['resources']:
        if row['path'] in removed_paths:
            continue
        if row['path'] in staged:
            data = staged[row['path']]
            row = {**row, 'sha256': digest(data), 'bytes': len(data), **evidence[row['path']]}
        resources.append(row)
        if row['path'] == anchor:
            for name in sorted(libraries):
                target = 'srn_body/' + name + '.mdl'; data = staged[target]
                resources.append({'path': target, 'sha256': digest(data), 'bytes': len(data), 'role': LIBRARY_ROLE,
                                  'sourceResource': name + '.mdl', 'sourceArchive': None, 'sourceSHA256': digest(data),
                                  'nameOnlyChanges': [], **evidence[target]})
    if len(resources) != len(base['resources']) - len(removed) + len(libraries):
        raise ValueError('Library insertion point missing from the base contract')
    contract['resources'] = resources
    dependencies = []
    for row in base['modelDependencies']:
        if 'srn_body/' + row['model'] + '.mdl' in removed_paths:
            continue
        if 'srn_body/' + row['model'] + '.mdl' in roots:
            row = {**row, 'supermodel': roots['srn_body/' + row['model'] + '.mdl']}
        dependencies.append(row)
        if row['model'] == anchor_model:
            dependencies += [{'model': n, 'supermodel': libraries[n]['parent'], 'role': LIBRARY_ROLE, 'textureSlots': []}
                             for n in sorted(libraries)]
    contract['modelDependencies'] = dependencies
    contract['installedAnimationChain'] = [{'resource': n + '.mdl', **{k: stock['models'][n][k] for k in ('sha256', 'bytes', 'format', 'parent')}}
                                           for n in chain('a_fa', models)]
    contract['publicationNotes'] = [note for note in base['publicationNotes'] if not note.startswith('Original global a_*')] + plan['publicationNotes']
    contract['runtimeOptimization'] = plan['runtimeOptimization']
    for key, value in plan.get('contractFields', {}).items():
        contract[key] = value
    retired_rows = retired + [{'path': r['path'], 'sha256': r['sha256'], 'bytes': r['bytes'], 'reason': plan['retiredCarrierReason']}
                              for r in removed]
    retired_rows += [{'path': p, 'sha256': e['downsampledFrom']['sha256'], 'bytes': e['downsampledFrom']['bytes'],
                      'reason': plan['retiredTextureReason']} for p, e in sorted(evidence.items()) if 'downsampledFrom' in e]
    # Stage.
    output.mkdir(parents=True, exist_ok=False)
    for path, data in staged.items():
        target = output/'files'/path; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(data)
    (output/'game-ready-assets.json').write_text(dump(contract), encoding='utf-8', newline='\n')
    (output/'retired-runtime-resources.json').write_text(dump(retired_rows), encoding='utf-8', newline='\n')
    (output/'ASSETS.md').write_text(assets_index(contract, plan['assetsIntro']), encoding='utf-8', newline='\n')
    (output/'remove.json').write_text(dump([{'path': r['path'], 'sha256': r['sha256']} for r in removed]), encoding='utf-8', newline='\n')
    summary = {'version': plan['version'], 'libraries': len(libraries), 'repointedRoots': len(roots),
               'downsampledTextures': sum('downsampledFrom' in e for e in evidence.values()), 'retiredCarriers': len(removed),
               'retiredCarrierBytes': sum(r['bytes'] for r in removed),
               'resourcesBefore': len(base['resources']), 'resourcesAfter': len(resources),
               'bytesBefore': sum(r['bytes'] for r in base['resources']), 'bytesAfter': sum(r['bytes'] for r in resources)}
    receipt = {'schemaVersion': 1, 'kind': 'PhenoMorpher-runtime-adoption', 'plan': {'sha256': digest(plan_path.read_bytes())},
               'contract': {'sha256': digest(dump(contract).encode())}, 'summary': summary, 'assetApprovalCreated': False}
    (output/'adoption-receipt.json').write_text(dump(receipt), encoding='utf-8', newline='\n')
    return receipt
