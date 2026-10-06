"""Copy a receipt-pinned derived body into a fresh, independent ignored bank."""
import argparse
from pathlib import Path
import shutil
from head_workflow import pin, read, require, sha, verify_pins, write_fresh


def import_body(config_path, output):
    config = read(config_path)
    require(config['kind'] == 'srn-head-derived-body-import', 'Explicit body import required')
    verify_pins([config['target'], config['compileReceipt'], *config['inputs']])
    receipt = read(config['compileReceipt']['path'])
    require(receipt.get('complete') is True and len(receipt['models']) == 14,
            'Complete fourteen-part native body receipt required')
    expected = {row['name']: row['binarySha256'] for row in receipt['models']}
    expected.update(receipt['materialResourceHashes'])
    source = Path(config['resources']).resolve()
    require(set(expected) == {p.name for p in source.iterdir() if p.is_file()},
            'Body inventory differs from compiler receipt')
    declared = {str(Path(p['path']).resolve()): p['sha256'] for p in config['inputs']}
    for name, digest in expected.items():
        require(Path(name).name == name, 'Unsafe resource name')
        path = source / name
        require(declared.get(str(path)) == digest == sha(path), 'Unpinned or changed body resource: ' + name)
    destinations = {'resources/' + name for name in expected}
    for item in config['extras']:
        relative = Path(item['destination'])
        require(not relative.is_absolute() and '..' not in relative.parts, 'Dependency destination escapes bank')
        require(relative.as_posix() not in destinations, 'Duplicate dependency destination')
        destinations.add(relative.as_posix())
        original = Path(item['source']['path']).resolve()
        require(declared.get(str(original)) == item['source']['sha256'], 'Undeclared body dependency')
    output = Path(output).resolve()
    require(not output.exists(), 'Fresh independent body bank required')
    resources = output / 'resources'; resources.mkdir(parents=True)
    rows = []
    for name, digest in sorted(expected.items()):
        shutil.copyfile(source / name, resources / name)
        require(sha(resources / name) == digest == sha(source / name), 'Body changed during copy')
        rows.append({'path': 'resources/' + name, 'sha256': digest})
    extras = []
    for item in config['extras']:
        original = Path(item['source']['path']).resolve()
        require(declared.get(str(original)) == item['source']['sha256'], 'Undeclared body dependency')
        relative = Path(item['destination'])
        require(not relative.is_absolute() and '..' not in relative.parts, 'Dependency destination escapes bank')
        destination = output / relative
        require(not destination.exists(), 'Duplicate dependency destination')
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original, destination)
        require(sha(destination) == item['source']['sha256'], 'Copied dependency changed')
        extras.append({'source': item['source'], 'copy': pin(destination)})
    verify_pins([config['target'], config['compileReceipt'], *config['inputs']])
    manifest = {'schemaVersion': 1, 'kind': 'srn-head-derived-body-bank',
                'targetId': config['targetId'], 'resources': rows,
                'sourceBranchCommit': config['sourceBranchCommit'],
                'contract': config['target'], 'compilerReceipt': config['compileReceipt'],
                'dependencyCopies': extras, 'bodyBytesChanged': False,
                'headClientValidated': False, 'productionAccepted': False}
    write_fresh(output / 'body.json', manifest)
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); import_body(args.config, args.output)
