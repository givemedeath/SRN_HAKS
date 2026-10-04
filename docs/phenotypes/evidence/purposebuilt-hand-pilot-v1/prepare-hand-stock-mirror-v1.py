"""Prepare exact detached left-to-right frame mirror after canonical fit."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

P = Path(__file__).resolve().parent
R = P.parents[2]
sys.path.insert(0, str(R / 'tools/phenotypes'))
from place_purposebuilt_pelvis import require
from stock_limb_contract import validate_mirror_association


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--placement', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    a = parser.parse_args(); out = a.output.resolve(); receipt = a.placement.resolve()
    require(out.parent == P.resolve() and not out.exists(), 'Fresh owned output required')
    placement = json.loads(receipt.read_text()); source = Path(placement['candidate'])
    root = R / 'output/phenotypes/purposebuilt-stock-inputs-v1/stock/ascii/pmh0.mdl'
    validate_mirror_association(placement, 'lhand_g', 'rhand_g')
    require(sha(source) == placement['candidateSha256'] and
            sha(root) == placement['stockRootSha256'] == '23fc893a8d18df461052ef978f33b7805da9188546833c0620b3a6014117d45a', 'Actual fitted source and stock rig required')
    config = {'schemaVersion': 1, 'source': str(source.resolve()), 'sourceSha256': sha(source),
        'sourceReceipt': str(receipt), 'sourceReceiptSha256': sha(receipt),
        'stockRoot': str(root.resolve()), 'stockRootSha256': sha(root),
        'sourceJoint': 'lhand_g', 'targetJoint': 'rhand_g',
        'planeOriginWorld': [0., 0., 0.], 'planeNormalWorld': [1., 0., 0.]}
    out.mkdir(); path = out / 'mirror-config.json'; path.write_text(json.dumps(config, indent=2) + '\n')
    (out / 'preparation.json').write_text(json.dumps({'schemaVersion': 1, 'readOnly': True,
        'mirrorConfiguration': str(path), 'configurationSha256': sha(path),
        'detachedGeometryOnly': True, 'rigOrAnimationsModified': False,
        'heldRootOffsetsRemainStock': True, 'helperSha256': sha(__file__),
        'limits': 'This prepares the exact opposite attachment-frame reflection, not a selected geometry or right-side weapon/pose proof. Original maps/UVs and transformed authored normals/tangent signs must pass the mirror tool.'}, indent=2) + '\n')
    (out / 'executed-preparation.py').write_bytes(Path(__file__).read_bytes())
    print(json.dumps({'configuration': str(path)}), flush=True)


if __name__ == '__main__':
    main()
