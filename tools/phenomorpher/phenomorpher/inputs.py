"""Enumerate consumed data inputs without runtime paths or generated directory scans."""
import json
from pathlib import Path
import struct


MODEL_TYPE = 2002
RIG_ROLES = ('fitted-rig', 'rig-inheritance', 'animation-library')
ANIMATION_ROLES = RIG_ROLES + ('selected-palette', 'selected-map', 'selected-material')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def rooted(root, name):
    root = Path(root).resolve()
    result = (root / name).resolve()
    if not result.is_relative_to(root):
        raise ValueError('Consumed input escaped explicit root: ' + str(name))
    return result


def installed_models(game_root):
    """Installed key files and every BIF they route a model to: what resman_cat --no-ovr reads models from."""
    game_root = Path(game_root).resolve(); files = set()
    for key in sorted((game_root/'data').glob('*.key')):
        data = key.read_bytes(); files.add(key)
        if data[:8] != b'KEY V1  ':
            raise ValueError('Unsupported key file: ' + key.name)
        bifs, keys, bif_table, key_table = struct.unpack_from('<IIII', data, 8)
        holding = set()
        for entry in range(key_table, key_table + 22*keys, 22):
            kind, resource = struct.unpack_from('<HI', data, entry + 16)
            if kind == MODEL_TYPE:
                holding.add(resource >> 20)
        for index in sorted(holding):
            if index >= bifs:
                raise ValueError('Key routes a model to a missing BIF entry: ' + key.name)
            _, offset, size, _ = struct.unpack_from('<IIHH', data, bif_table + 12*index)
            files.add(rooted(game_root, data[offset:offset+size].rstrip(b'\0').decode('ascii').replace('\\', '/')))
    if not files:
        raise ValueError('No installed key files under --game-root')
    return files


def consumed(arguments):
    if not arguments:
        raise ValueError('A PhenoMorpher command is required')
    command = arguments[0]
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
