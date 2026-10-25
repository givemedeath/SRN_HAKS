"""Enumerate consumed data inputs without runtime paths or generated directory scans."""
import json
from pathlib import Path
import struct


MODEL_TYPE = 2002
RIG_ROLES = ('fitted-rig', 'rig-inheritance', 'animation-library')
ANIMATION_ROLES = RIG_ROLES + ('selected-palette', 'selected-map', 'selected-material')
# Options argparse collects as lists; every other option must appear once, spelled in full.
REPEATED = {'target', 'slot', 'clip', 'seed', 'conversion', 'compiled', 'authorized-fit-clip', 'resource-dir', 'input'}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def rooted(root, name):
    root = Path(root).resolve()
    result = (root / name).resolve()
    if not result.is_relative_to(root):
        raise ValueError('Consumed input escaped explicit root: ' + str(name))
    return result


def key_table(key):
    """One KEY V1 file: (BIF names, [(resref, resource type, BIF index)]). Shared by input enumeration
    and stock armour extraction so both read the same routing."""
    data = Path(key).read_bytes()
    if data[:8] != b'KEY V1  ':
        raise ValueError('Unsupported key file: ' + Path(key).name)
    bifs, keys, bif_table, key_offset = struct.unpack_from('<IIII', data, 8)
    if bif_table + 12*bifs > len(data) or key_offset + 22*keys > len(data):
        raise ValueError('Truncated key file: ' + Path(key).name)
    names = []
    for index in range(bifs):
        _, offset, size, _ = struct.unpack_from('<IIHH', data, bif_table + 12*index)
        names.append(data[offset:offset+size].rstrip(b'\0').decode('ascii').replace('\\', '/'))
    entries = []
    for entry in range(key_offset, key_offset + 22*keys, 22):
        kind, resource = struct.unpack_from('<HI', data, entry + 16)
        entries.append((data[entry:entry+16].rstrip(b'\0').decode('ascii').lower(), kind, resource >> 20))
    return names, entries


def installed_models(game_root, kinds=(MODEL_TYPE,)):
    """Installed key files and every BIF they route one of these resource types to (models by default):
    what resman --no-ovr reads them from."""
    game_root = Path(game_root).resolve(); files = set()
    for key in sorted((game_root/'data').glob('*.key')):
        files.add(key); names, entries = key_table(key)
        for index in sorted({bif for _, kind, bif in entries if kind in kinds}):
            if index >= len(names):
                raise ValueError('Key routes a model to a missing BIF entry: ' + key.name)
            files.add(rooted(game_root, names[index]))
    if not files:
        raise ValueError('No installed key files under --game-root')
    return files


def consumed(arguments):
    if not arguments:
        raise ValueError('A PhenoMorpher command is required')
    command = arguments[0]
    # argparse keeps the last of a repeated option and accepts --name=value; the enumeration below reads
    # the first exact token, so any spelling where the two could differ is refused.
    flags = [a for a in arguments if a.startswith('--')]
    if any('=' in a for a in flags):
        raise ValueError('Use separate option values, not --name=value: ' + next(a for a in flags if '=' in a))
    repeated = sorted({a for a in flags if flags.count(a) > 1 and a[2:] not in REPEATED})
    if repeated:
        raise ValueError('Option given more than once: ' + ', '.join(repeated))
    def values(name):
        return [Path(arguments[i+1]).resolve() for i, a in enumerate(arguments[:-1]) if a == '--' + name]
    def option(name):
        try:
            return Path(arguments[arguments.index('--'+name)+1]).resolve()
        except (ValueError, IndexError):
            raise ValueError('Missing --'+name) from None
    files = set()
    if command == 'doctor':
        return files
    if command in ('catalog','verify-assets'):
        manifest = option('manifest'); files.add(manifest)
        if command == 'verify-assets':
            root = option('root'); files.update(rooted(root, x['path']) for x in read(manifest)['resources'])
    elif command == 'measure':
        config = option('assembly'); files.add(config); data = read(config); root = option('root')
        files.update(rooted(root, row['path']) for row in [data['rig'], *data['parts'].values()])
    elif command == 'native-info':
        files.add(option('input'))
    elif command == 'candidate':
        config = option('bundle'); files.add(config)
        data=read(config)
        files.update(Path(p) for p in data['motion'].get('inputPins', {}))
        files.update(Path(mesh['sourceAttributePin']['path']) for mesh in data['bindMeshes'] if mesh.get('sourceAttributePin'))
    elif command == 'replay':
        root = option('release'); manifest = root/'recipes/manifest.json'; files.add(manifest)
        for row in read(manifest)['targets']:
            recipe = rooted(root, row['recipe']['path']); files.add(recipe)
            data = read(recipe)
            files.update(rooted(root, data[name]['path']) for name in ('highDetail','metadata','correspondence','reducedGeometry'))
    elif command == 'downsample-textures':
        manifest = option('manifest'); root = option('root'); files.add(manifest)
        files.update(rooted(root, x['path']) for x in read(manifest)['resources']
                     if x['role'] in ('selected-palette', 'selected-map', 'selected-material'))
    elif command == 'adopt-runtime':
        plan = option('plan'); root = option('root'); data = read(plan); files.add(plan)
        pins = [data['baseContract'], data['retiredResources'], data['stock'], data['textures']]
        pins += data['libraries'] + [row['restoration'] for row in data['libraries']]
        pins += data['roots'] + [row['comparison'] for row in data['roots']]
        files.update(rooted(root, pin['path']) for pin in pins)
        contract = rooted(root, data['baseContract']['path']); stock = rooted(root, data['stock']['path'])
        files.update(rooted(root, row['path']) for row in read(contract)['resources'])
        files.update(rooted(stock.parent, row['path']) for row in read(stock)['models'].values())
        receipt = rooted(root, data['textures']['path'])
        files.update(rooted(receipt.parent, row['path']) for row in read(receipt)['resources'])
    elif command == 'audit-native':
        files.update([option('published'), option('source')])
    elif command == 'sweep':
        manifest = option('manifest'); root = option('root'); data = read(manifest); files.add(manifest)
        pack = {row['path'] for row in data['resources']}
        targets = {t['modelPrefix']: t for t in data['targets']}
        prefixes = [arguments[i+1] for i, a in enumerate(arguments[:-1]) if a == '--target']
        for prefix in set(prefixes) | {f'p{p[1]}h{p[3]}' for p in prefixes}:
            if prefix not in targets:
                raise ValueError('Unknown sweep target: ' + prefix)
            files.add(rooted(root, f'srn_body/{prefix}.mdl'))
            files.update(rooted(root, 'srn_body/' + name) for name in targets[prefix]['parts'])
            if f'srn_body/{prefix}_head001.mdl' in pack:
                files.add(rooted(root, f'srn_body/{prefix}_head001.mdl'))
        if '--motion' in arguments or '--motion-only' in arguments:
            stock = option('stock'); files.add(stock)
            files.update(rooted(stock.parent, row['path']) for row in read(stock)['models'].values())
            files.update(rooted(root, x['path']) for x in data['resources'] if x['role'] in RIG_ROLES)
    elif command == 'verify-runtime':
        manifest = option('manifest'); root = option('root'); files.add(manifest)
        files.update(rooted(root, x['path']) for x in read(manifest)['resources']
                     if x['role'] in RIG_ROLES + ('selected-palette', 'selected-map'))
        if '--stock' in arguments:
            stock = option('stock'); files.add(stock)
            files.update(rooted(stock.parent, row['path']) for row in read(stock)['models'].values())
    elif command == 'rebase-roots':
        # The staged contract is checked against the runtime rules, which read palette/map headers.
        manifest = option('manifest'); root = option('root'); files.add(manifest)
        files.update(rooted(root, x['path']) for x in read(manifest)['resources']
                     if x['role'] in RIG_ROLES + ('selected-palette', 'selected-map'))
    elif command == 'retarget-v2':
        baseline = option('baseline'); fit = option('fit-converted')
        reports = [fit/'conversion.json'] + ([option('large-converted')/'conversion.json'] if '--large-converted' in arguments else [])
        files.update(reports); files.add(rooted(baseline, 'baseline.json'))
        gender = read(reports[0])['modelPrefix'][1]; stock = read(rooted(baseline, 'baseline.json'))['animations']
        files.add(rooted(baseline, f'ascii/p{gender}h0.mdl'))
        current = 'a_fa' if gender == 'f' else 'a_ba'
        while current != 'null':
            files.add(rooted(baseline, f'ascii/{current}.mdl')); current = stock[current]['supermodel']
    elif command in ('mdl-compile', 'mdl-decompile'):
        from .engine.neverblender_mdl import declared_files, lookup_files
        files.update(declared_files(option('blender'), option('neverblender')))
        if command == 'mdl-compile':
            converted = option('converted'); sources = sorted((converted/'ascii').glob('*.mdl'))
            files.update(sources)
            files.update(lookup_files([converted/'ascii', *([converted/'resources'] if (converted/'resources').is_dir() else []),
                                       *values('resource-dir')]))
            if (converted/'native-compile.json').is_file():
                files.add(converted/'native-compile.json')
        else:
            inputs = values('input'); files.update(inputs)
            files.update(lookup_files({p.parent for p in inputs} | set(values('resource-dir'))))
    elif command == 'armor-extract':
        from .engine.neverblender_mdl import declared_files
        files.add(option('resman-extract')); files.update(declared_files(option('blender'), option('neverblender')))
        files.update(installed_models(option('game-root'), (MODEL_TYPE, 3, 6, 2033, 2036)))
    elif command == 'armor-profiles':
        from .engine.stock_armor import BARE, TARGETS, source_slot
        root = option('root'); manifest = option('manifest'); stock = option('stock'); files.update([manifest, stock])
        slots = [arguments[i+1] for i, a in enumerate(arguments[:-1]) if a == '--slot'] or list(TARGETS)
        for slot in slots:
            src = source_slot(slot)
            files.update(rooted(stock.parent, f'reference/{name}') for name in [src + '.mdl'] + [f'{src}_{p}001.mdl' for p in BARE])
            files.update(rooted(root, f'srn_body/{name}') for name in [slot + '.mdl'] + [f'{slot}_{p}001.mdl' for p in BARE])
    elif command == 'armor-convert':
        from .engine.stock_armor import TARGETS, source_slot, style_set
        stock = option('stock'); styles = option('styles'); files.update([stock, option('profiles'), option('armory'), styles])
        slots = [arguments[i+1] for i, a in enumerate(arguments[:-1]) if a == '--slot'] or list(TARGETS)
        files.update(rooted(stock.parent, f'ascii/{source_slot(slot)}_{p}{s:03d}.mdl') for slot in slots for p, s in style_set(styles))
    elif command == 'armor-publish':
        files.add(option('body-manifest'))
        pairs = zip(*([Path(arguments[i+1]).resolve() for i, a in enumerate(arguments[:-1]) if a == '--' + name]
                      for name in ('conversion', 'compiled')))
        for conversion, compiled in pairs:
            files.add(conversion)
            for slot in read(conversion)['slots']:
                receipt = rooted(compiled, f'{slot}/converted/native-compile.json'); files.add(receipt)
                files.update(rooted(compiled, f'{slot}/converted/resources/{row["name"]}') for row in read(receipt)['models'])
    elif command == 'verify-armor':
        manifest = option('manifest'); root = option('root'); files.add(manifest)
        files.update(rooted(root, row['path']) for row in read(manifest)['resources'])
    elif command == 'convert-clothing':
        root = option('release'); profile = option('profile'); files.update([profile,option('source-binding'),option('input')])
        data = read(profile)
        for name in ('sourceBody','targetBody'):
            body = rooted(root, data[name]['path']); files.add(body)
            files.update(rooted(root, row['path']) for row in read(body)['files'].values())
    elif command in ('anim-library', 'compare-motion'):
        action = command if command == 'compare-motion' else arguments[1] if len(arguments) > 1 else ''
        def release(roles):
            manifest = option('manifest'); stock = option('stock'); root = option('root')
            files.update([manifest, stock])
            files.update(rooted(stock.parent, row['path']) for row in read(stock)['models'].values())
            files.update(rooted(root, x['path']) for x in read(manifest)['resources'] if x['role'] in roles)
        if action == 'extract-stock':
            files.add(option('resman-cat')); files.update(installed_models(option('game-root')))
        elif action == 'inventory':
            release(ANIMATION_ROLES)
        elif action == 'build':
            release(RIG_ROLES)
        elif action == 'compare-motion':
            release(RIG_ROLES); files.add(option('repointed'))
            if '--library' in arguments:
                files.add(option('library'))
        elif action == 'restore':
            plan = option('plan'); root = option('root'); data = read(plan)
            files.update([plan, option('compiled'), rooted(plan.parent, data['ascii']['path'])])
            files.update(rooted(root, row['path']) for row in data['sources'].values())
        elif action == 'repoint':
            files.add(option('input'))
        else:
            raise ValueError('Unknown anim-library action: '+action)
    else:
        raise ValueError('Unknown command: '+command)
    return {p.resolve() for p in files}
