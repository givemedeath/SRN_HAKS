"""Enumerate consumed data inputs without runtime paths or generated directory scans."""
import json
from pathlib import Path


RIG_ROLES = ('fitted-rig', 'rig-inheritance')
ANIMATION_ROLES = RIG_ROLES + ('selected-palette', 'selected-map', 'selected-material')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def rooted(root, name):
    root = Path(root).resolve()
    result = (root / name).resolve()
    if not result.is_relative_to(root):
        raise ValueError('Consumed input escaped explicit root: ' + str(name))
    return result


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
            files.update((stock.parent/row['path']).resolve() for row in read(stock)['models'].values())
            files.update(rooted(root, x['path']) for x in read(manifest)['resources'] if x['role'] in roles)
        if action == 'extract-stock':
            files.add(option('resman-cat'))
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
            files.update([plan, option('compiled'), (plan.parent/data['ascii']['path']).resolve()])
            files.update(rooted(root, row['path']) for row in data['sources'].values())
        elif action == 'repoint':
            files.add(option('input'))
        else:
            raise ValueError('Unknown anim-library action: '+action)
    else:
        raise ValueError('Unknown command: '+command)
    return {p.resolve() for p in files}
