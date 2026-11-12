"""A native contract for one design on any composite melee carrier, including the hafted families.

    python -m tools.itemkit.drive contract FAMILY DESIGN_ID --wave NAME [--visible N]

Builds on the measured wave contract (stack, stock baseitems, the shipped Humans and approved weapons): extracts the
installed carrier's three stock parts and icons into a new stack layer, measures the stock grip origin and overall span
(carrier.py), allocates the visible budget from budget-policy.json by the stock length, reserves resources and writes
`contracts/<wave>/family-<name>.json` and `<DESIGN>.<wave>-contract.asset.json`.

The grip origin is measured, not reviewed in the hand: the first design fitted on a new carrier carries the both-body
hand-fit review that confirms it, exactly as the Claymore's provisional greatsword contract did.
"""
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
import numpy as np
from tools.headkit.common import ROOT, require
from .routes import ROUTES

BASE = 'contracts/wave1-f45-v1'      # the measured wave-1 contract every new one starts from
PART_SHARE = {'b': .10, 'm': .19, 't': .71}      # pommel/butt, grip, blade or head (wave-1 allocations)
SHADOW = {'b': 100, 'm': 100, 't': 300}
TWO_HAND_SPAN = 0.21516236561400143    # the Katana's measured two-hand usable length (provisional two-hand reference)


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def visible_budget(length):
    """Visible triangles for a melee weapon by its stock length, inside budget-policy.json's melee range."""
    policy = json.loads((Path(__file__).parent/'budget-policy.json').read_text(encoding='utf-8'))['categories']['melee']
    lo, hi = policy['minimum'], policy['maximum']; t = float(np.clip((length - .5) / (1.6 - .5), 0, 1))
    return int(round((lo + t * (hi - lo)) / 500) * 500)


def allocation(visible):
    parts = {p: int(visible * share) // 50 * 50 for p, share in PART_SHARE.items()}
    parts['t'] += visible - sum(parts.values())
    return {'visible': visible, 'shadow': sum(SHADOW.values()), 'parts': {p: {'visible': parts[p], 'shadow': SHADOW[p]} for p in 'bmt'}}


def extract_stock(game, item_class, target):
    """The installed carrier's three part models and icons, by resman lookup without overrides."""
    sys.path.insert(0, str(ROOT/'tools/phenotypes')); from tool_runtime import tool
    cat = tool('resman_cat'); target.mkdir(parents=True, exist_ok=True); rows = []
    with tempfile.TemporaryDirectory(prefix='stock-user-') as user:
        (Path(user)/'override').mkdir()
        for part in 'bmt':
            for name in (f'{item_class}_{part}_011.mdl', f'i{item_class}_{part}_011.tga'):
                data = subprocess.run([str(cat), '--root', str(game), '--userdirectory', user, '--no-ovr', name],
                                      capture_output=True, check=True).stdout
                require(data, 'Installed carrier resource missing: '+name); (target/name).write_bytes(data)
                rows.append({'resource': name, 'file': {'path': (target/name).as_posix(), 'sha256': sha(target/name)}})
    return rows


def sibling_models(wave_folder, own, item_class):
    """Model and icon names the wave's other contracts on this carrier already pinned: not yet in any stack, still taken."""
    from .contracts import model_names
    taken = set()
    for path in Path(wave_folder).glob('family-*.json'):
        if path == own: continue
        other = json.loads(path.read_text(encoding='utf-8')); index = other.get('resources', {}).get('appearanceIndex')
        if index is None or other.get('native', {}).get('itemClass') != item_class: continue
        for name in model_names(other, index).values(): taken |= {name.lower()+'.mdl', 'i'+name.lower()+'.tga'}
    return taken


def build(ws, family_name, design, wave, *, visible=None, base=BASE):
    from .carrier import assemble, decode_stock, measure
    from .contracts import family, native_contract, reserve
    from tools.headkit.common import verification_pass
    route = ROUTES.get(family_name); require(route and route.adapter == 'composite' and route.carrier, 'A composite melee family required')
    handoff = ws.handoff; source = handoff/base; target = handoff/'contracts'/wave
    if not target.exists():
        shutil.copytree(source, target)
        for old in target.glob('family*.json'): old.unlink()
    cls = route.carrier.item_class; folder = target/'stack-resources'/cls
    # Each carrier gets its own stack file: the wave's stack.json is never rewritten, so a family contracted earlier
    # in the wave keeps the stack bytes it pins.
    stack_path = target/f'stack-{cls}.json'
    if not stack_path.exists():
        stack = json.loads((target/'stack.json').read_text(encoding='utf-8')); layer = f'installed-stock-{cls}-donors'
        if not any(l.get('name') == layer for l in stack['layers']):
            game = ws.setting('nwnRoot'); require(game, 'Workspace needs nwnRoot to extract the stock carrier')
            rows = extract_stock(game, cls, folder)
            for row in rows: row['file']['path'] = Path(row['file']['path']).relative_to(target).as_posix()
            stack['layers'].insert(2, {'name': layer, 'resources': rows})
        stack_path.write_text(json.dumps(stack, indent=2), encoding='utf-8')
    stack = json.loads(stack_path.read_text(encoding='utf-8'))
    standard = json.loads((ROOT/'docs/items/weapon-grip-standard-v1.json').read_text(encoding='utf-8'))
    positions, faces = assemble([decode_stock(folder/f'{cls}_{p}_011.mdl') for p in 'bmt'])
    carrier = measure(positions, faces, standard['usableLength'], route.hold)
    grip_length = standard['usableLength'] if route.hold == 'one' else TWO_HAND_SPAN
    from PIL import Image
    from .contracts import twoda
    table = next(row['file']['path'] for l in stack['layers'] for row in l['resources'] if row['resource'].lower() == 'baseitems.2da')
    row = twoda((target/table).read_text(encoding='utf-8-sig'))[str(route.carrier.base_item)]
    footprint = [int(row['InvSlotWidth']) * 32, int(row['InvSlotHeight']) * 32]
    canvases = {p: list(Image.open(folder/f'i{cls}_{p}_011.tga').size) for p in 'bmt'}
    icons = {'iconDimensions': dict.fromkeys('bmt', footprint)}
    if any(c != footprint for c in canvases.values()): icons['iconCanvasDimensions'] = canvases
    base_family = json.loads(next(source.glob('family-*.json')).read_text(encoding='utf-8'))
    from .contracts import resource_stem
    stem = resource_stem(design)          # the intake's identity, from the whole ID: a shared suffix never shares names
    budget = allocation(visible or visible_budget(carrier['length']))
    profile = {k: base_family[k] for k in ('schemaVersion', 'kind', 'materialRoute', 'bakeSize', 'runtimeTextureSize')}
    draft = json.loads((handoff/f'{design}.family.json').read_text(encoding='utf-8'))
    profile.update(sourceExport=draft['sourceExport'], family=family_name, nativePackaging='enabled', budgets=budget,
                   allowedAssemblies=[dict.fromkeys('bmt', design)],
                   notes=(f'{design} on the installed {route.carrier.label} carrier (BaseItem {route.carrier.base_item}, {cls}). '
                          f'{budget["visible"]} visible triangles for a {carrier["length"]:.2f} m stock carrier (budget-policy.json melee range).'),
                   resources={'texturePrefix': stem, 'blueprint': stem, 'hak': stem+'h', 'module': stem+'m',
                              'displayName': ' '.join(w.capitalize() for w in design.split('-')[1:-1])},
                   native={'baseItem': route.carrier.base_item, 'itemClass': cls, 'modelType': 2,
                           'donors': {p: f'{cls}_{p}_011.mdl' for p in 'bmt'}, 'iconDonors': {p: f'i{cls}_{p}_011.tga' for p in 'bmt'},
                           **icons, 'frame': np.eye(3).tolist(), 'gripOrigin': carrier['gripOrigin'], 'gripLength': grip_length,
                           'stockSpan': carrier['span'], 'axes': {'width': 'Z', 'length': '+Y'},
                           'partAssignments': ({'b': 'butt', 'm': 'grip', 't': 'haft and head'} if route.shape == 'hafted'
                                               else {'b': 'pommel', 'm': 'grip', 't': 'blade and guard'}),
                           'measurementNotes': (f'Grip origin and stock span measured from the installed {cls} parts by tools/itemkit/carrier.py '
                                                f'({carrier["method"]}, handle run {carrier["handleRun"][0]:.3f}..{carrier["handleRun"][1]:.3f} m). '
                                                'Grip dimensions use the approved Cougar standard. The first design fitted on this carrier carries '
                                                'the both-body hand-fit review that confirms the origin.'),
                           'baseitemsSha256': base_family['native']['baseitemsSha256'], 'reviewed': True,
                           'productionStackApproved': False, 'stack': {'path': stack_path.name, 'sha256': sha(stack_path)}})
    name = design.rsplit('-', 1)[0][4:] if design.startswith('sr4-') else design
    path = target/f'family-{name}.json'; require(not path.exists(), path.name+' exists in this wave')
    with verification_pass('family-contract-'+design):
        path.write_text(json.dumps(profile, indent=2), encoding='utf-8')
        _, resources = native_contract(path, profile)
        slot = reserve(profile, {n.lower() for n in resources} | sibling_models(target, path, cls))
        profile['resources']['appearanceIndex'] = slot['modelIndex']; path.write_text(json.dumps(profile, indent=2), encoding='utf-8')
        family(path, validate_native=True)
    manifest = json.loads((handoff/f'{design}.asset.json').read_text(encoding='utf-8'))
    manifest['familyProfile'] = {'path': path.relative_to(handoff).as_posix(), 'sha256': sha(path)}
    out = handoff/f'{design}.{wave}-contract.asset.json'; require(not out.exists(), out.name+' exists')
    out.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return {'family': str(path), 'manifest': str(out), 'carrier': carrier, 'budget': budget, 'slot': slot['modelIndex']}
