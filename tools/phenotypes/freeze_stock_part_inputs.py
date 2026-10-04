"""Freeze an allowlisted stock/fixture bank; never clone a custom body folder."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--contract', type=Path, required=True)
    p.add_argument('--tested-stage', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    contract = json.loads(a.contract.read_text())
    baseline = contract['target']['baseline']
    original = Path(baseline['asciiDirectory']).parent
    extraction_path = Path(baseline['receipt'])
    if digest(extraction_path) != baseline['receiptSha256']:
        raise ValueError('Stock extraction receipt changed')
    extraction = json.loads(extraction_path.read_text())
    extracted = {r['name']: r for r in extraction['resources']}
    stage = json.loads((a.tested_stage / 'stock-part-stage.json').read_text())
    copies = []
    for name, checksum in baseline['frozenModels'].items():
        if extracted[name]['asciiSha256'] != checksum:
            raise ValueError('Contract stock model differs from extraction: ' + name)
        copies.append((original / 'ascii' / name, 'stock/ascii/' + name, checksum, 'actual-stock-model'))
    for source, checksum in stage['frozenInputs'].items():
        path = Path(source)
        if path.parent == original / 'raw':
            if extracted[path.name]['sha256'] != checksum:
                raise ValueError('Stock raw resource differs from extraction: ' + path.name)
            copies.append((path, 'stock/raw/' + path.name, checksum, 'actual-stock-resource'))
    for name in ('human-template.json', 'ttr01.set', 'ttr01_edge.2da'):
        origin = a.tested_stage / 'baseline' / name
        expected = [v for k,v in stage['frozenInputs'].items() if Path(k).name == name]
        if len(expected) != 1 or digest(origin) != expected[0]:
            raise ValueError('Tested fixture input differs: ' + name)
        copies.append((origin, 'fixture/' + name, expected[0], 'fixture-template-only'))
    # Validate everything before creating a fresh bank.
    for origin, _, checksum, _ in copies:
        if digest(origin) != checksum:
            raise ValueError('Input bytes changed: ' + str(origin))
    a.output.mkdir(parents=True, exist_ok=False)
    inventory = {}
    for origin, relative, checksum, role in copies:
        target = a.output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(origin, target)
        if digest(target) != checksum:
            raise ValueError('Copy changed: ' + relative)
        inventory[relative] = {'sha256': checksum, 'role': role, 'provenance': str(origin.resolve())}
    receipt = {'schemaVersion': 1, 'files': inventory,
               'extractionReceipt': str(extraction_path), 'extractionReceiptSha256': digest(extraction_path),
               'customBodyAssetsCopied': False, 'productionAccepted': False}
    (a.output / 'input-inventory.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print(json.dumps({'files': len(inventory), 'bank': str(a.output), 'customBodyAssetsCopied': False}))


if __name__ == '__main__':
    main()
