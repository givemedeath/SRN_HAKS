"""Enumerate consumed data inputs without runtime paths or generated directory scans."""
import json
from pathlib import Path


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
    elif command == 'convert-clothing':
        root = option('release'); profile = option('profile'); files.update([profile,option('source-binding'),option('input')])
        data = read(profile)
        for name in ('sourceBody','targetBody'):
            body = rooted(root, data[name]['path']); files.add(body)
            files.update(rooted(root, row['path']) for row in read(body)['files'].values())
    else:
        raise ValueError('Unknown command: '+command)
    return {p.resolve() for p in files}
