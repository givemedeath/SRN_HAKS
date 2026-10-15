"""Runtime layout rules for a published body contract (Phase 9 enforcement).

Every target root must reach the installed stock animation chain through at most one shared
animation library or a declared posture layer, never through private animation carriers.
Structural mode needs no game install: stock names and parents come from the contract's
installedAnimationChain (or, for older contracts, only the names in installedGameDependencies).
Deep mode also checks the installed chain bytes against an extracted stock manifest.
"""
import json
import re
from pathlib import Path

from .anim_library import RIG_ROLES, digest, load_model, stock_files, texture_header

LIBRARY_ROLE = 'animation-library'
POSTURE_CLIPS = {'pause1', 'pause2'}
STOCK_PARENTS = {'f': 'a_fa', 'm': 'a_ba'}
TEXTURE_ROLES = ('selected-palette', 'selected-map')
HEX64 = re.compile(r'^[0-9a-f]{64}$')


def stock_graph(manifest):
    """Installed animation models and their parents (None when the contract does not record them)."""
    rows = manifest.get('installedAnimationChain')
    if rows:
        return {Path(r['resource']).stem.lower(): r['parent'].lower() for r in rows}
    names = [Path(n).stem.lower() for n in manifest.get('installedGameDependencies', []) if str(n).lower().endswith('.mdl')]
    return {n: None for n in names}


def check(root, manifest, stock_manifest=None, max_texture=1024, overlay=None):
    """manifest: contract path or parsed contract. overlay: {resource path: bytes} staged over root."""
    root = Path(root).resolve(); overlay = overlay or {}
    if not isinstance(manifest, dict):
        manifest = json.loads(Path(manifest).read_text(encoding='utf-8-sig'))
    def read(rel):
        return overlay[rel] if rel in overlay else (root/rel).read_bytes()
    violations = []
    def fail(rule, subject, detail):
        violations.append({'rule': rule, 'subject': subject, 'detail': detail})
    stock = stock_graph(manifest)
    if stock_manifest is not None:
        data, paths = stock_files(stock_manifest)
        for name, parent in stock.items():
            row = data['models'].get(name)
            if row is None:
                fail('installed-chain', name, 'missing from the stock manifest'); continue
            if parent is not None and row['parent'] != parent:
                fail('installed-chain', name, f'contract parent {parent}, installed {row["parent"]}')
            recorded = next((r for r in manifest.get('installedAnimationChain', []) if Path(r['resource']).stem.lower() == name), None)
            if recorded and recorded['sha256'] != row['sha256']:
                fail('installed-chain', name, 'installed bytes differ from the contract')
    # Published rigs, libraries and carriers, decoded from the pack bytes the contract pins.
    models, roles, rows = {}, {}, {}
    for row in manifest['resources']:
        if row['role'] not in RIG_ROLES:
            continue
        name = Path(row['path']).stem.lower(); blob = read(row['path'])
        if digest(blob) != row['sha256']:
            raise ValueError('Published model differs from the contract: ' + row['path'])
        models[name] = load_model(row['path'], blob); roles[name] = row['role']; rows[name] = row
    def posture(name):
        m = models[name]
        return roles[name] == 'rig-inheritance' and m['parent'] in ('a_fa', 'a_ba') and set(m['clips']) <= POSTURE_CLIPS
    chains, used_by = {}, {}
    for target in manifest['targets']:
        prefix = target['modelPrefix'].lower(); names = [prefix]
        if prefix not in models:
            fail('target-root', prefix, 'root model is not a published rig'); continue
        while names[-1] in models:
            parent = models[names[-1]]['parent'].lower()
            if parent == 'null' or parent in names:
                names.append(parent); break
            names.append(parent)
        chains[prefix] = names
        private = [n for n in names[1:] if n in models and roles[n] != LIBRARY_ROLE and not posture(n)]
        if private:
            fail('private-carrier', prefix, 'chain reaches private carriers: ' + ', '.join(private))
        layers = [n for n in names[1:] if n in models]
        if len(layers) > 1:
            fail('chain-depth', prefix, 'more than one pack layer before the stock chain: ' + ' > '.join(layers))
        first = next((n for n in names[1:] if n in stock), None)
        expected = STOCK_PARENTS.get(prefix[1])
        if first is None:
            fail('stock-closure', prefix, 'chain ends without reaching the installed chain: ' + ' > '.join(names))
        else:
            if first != expected:
                fail('stock-closure', prefix, f'first installed link is {first}, expected {expected}')
            tail = [first]
            while stock.get(tail[-1]) not in (None, 'null'):
                if stock[tail[-1]] in tail or stock[tail[-1]] not in stock:
                    fail('stock-closure', prefix, 'installed chain does not resolve: ' + stock[tail[-1]]); break
                tail.append(stock[tail[-1]])
            known = all(stock[n] is not None for n in tail)
            if known and 'a_ba' not in tail:
                fail('stock-closure', prefix, 'installed chain does not reach a_ba')
        for n in layers:
            used_by.setdefault(n, set()).add(prefix[1])
    for name in sorted(n for n in models if roles[n] == LIBRARY_ROLE):
        genders = used_by.get(name, set())
        if len(genders) > 1:
            fail('library-gender', name, 'shared by female and male roots')
        expected = STOCK_PARENTS.get(next(iter(genders))) if len(genders) == 1 else None
        if models[name]['parent'] not in ('a_fa', 'a_ba') or (expected and models[name]['parent'] != expected):
            fail('library-parent', name, f'parent {models[name]["parent"]}, expected {expected or "a_fa/a_ba"}')
        if not HEX64.match(str(rows[name].get('restorationSHA256', ''))):
            fail('library-restoration', name, 'no restorationSHA256 evidence')
        if name not in used_by:
            fail('library-unused', name, 'no target reaches this library')
    # Fit (phenotype 0) and Large (phenotype 2) of one race and gender share their immediate supermodel.
    by_slot = {}
    for target in manifest['targets']:
        prefix = target['modelPrefix'].lower()
        if prefix in models:
            by_slot.setdefault(prefix[:3], {})[prefix[3:]] = models[prefix]['parent'].lower()
    for slot, builds in sorted(by_slot.items()):
        if len(set(builds.values())) > 1:
            fail('fit-large-divergence', slot, ', '.join(f'{slot}{b} > {p}' for b, p in sorted(builds.items())))
    textures = {}
    for row in manifest['resources']:
        if row['role'] in TEXTURE_ROLES:
            try:
                if row['path'] in overlay:
                    data = overlay[row['path']][:24]
                else:
                    with (root/row['path']).open('rb') as stream:
                        data = stream.read(24)
                header = texture_header(row['path'], data)
            except ValueError as error:
                fail('texture-format', row['path'], str(error)); continue
            textures[row['path']] = header
            if max(header['width'], header['height']) > max_texture:
                fail('texture-size', row['path'], f'{header["width"]}x{header["height"]} above {max_texture}')
    counts = {}
    for v in violations:
        counts[v['rule']] = counts.get(v['rule'], 0) + 1
    return {'schemaVersion': 1, 'kind': 'PhenoMorpher-runtime-rules', 'contractVersion': manifest.get('version'),
            'mode': 'deep' if stock_manifest is not None else 'structural',
            'installedChainRecorded': all(p is not None for p in stock.values()) and bool(stock),
            'chains': {k: v for k, v in sorted(chains.items())},
            'libraries': sorted(n for n in models if roles[n] == LIBRARY_ROLE),
            'postureLayers': sorted(n for n in models if posture(n)),
            'textures': len(textures), 'maxTexture': max_texture,
            'violationCounts': counts, 'violations': violations, 'passed': not violations,
            'assetApprovalCreated': False}
