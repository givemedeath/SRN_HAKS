"""Measure a derived male body's frozen rig and propose a head target contract."""
import argparse
from pathlib import Path
import sys
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'phenotypes'))
from retarget import nodes
from rig_controller_audit import world_frames
from head_workflow import RACES, pin, read, require, sha, verify_pins, write_fresh


def prepare(bank, contract, neck, comparator, palettes, animations, output):
    body = read(bank); derived = read(contract)
    require(body['kind'] == 'srn-head-derived-body-bank', 'Independent derived body bank required')
    require(body['contract']['sha256'] == sha(contract), 'Derived contract changed since import')
    identity = derived['identity']; prefix = identity['prefix']
    race = 'orc' if identity['race'] == 'half-orc' else identity['race']
    require(identity['gender'] == 'male' and prefix == 'pm' + RACES[race] + '0', 'Male race family mismatch')
    root = Path(bank).resolve().parent
    for item in body['resources']:
        verify_pins([{'path': str(root / item['path']), 'sha256': item['sha256']}])
    rig = root / 'ascii' / (prefix + '.mdl')
    frames = world_frames(nodes(rig.read_text(encoding='cp1252')))
    declared = derived['rig']['frames']['working']['head_g']
    require(np.allclose(frames['head_g'], declared, atol=1e-8), 'Imported head frame differs from body contract')
    dependencies = [pin(neck), pin(comparator), *[pin(p) for p in palettes], *[pin(p) for p in animations]]
    verify_pins(dependencies)
    proposal = {'schemaVersion': 1, 'kind': 'srn-head-target', 'race': race, 'sex': 'male',
                'prefix': prefix, 'phenotype': 0, 'bodyRevision': sha(bank), 'bodyManifest': pin(bank),
                'bodyResourceRoot': str(root), 'rig': pin(rig), 'headBindMatrix': frames['head_g'].tolist(),
                'neckGeometry': pin(neck), 'palettes': [pin(p) for p in palettes],
                'animations': [pin(p) for p in animations], 'measurementOrigin': pin(comparator),
                'cranialEnvelope': [[-.108, -.13, -.07], [.108, .15, .205]],
                'landmarkTolerance': .025, 'approved': False, 'derivedContract': pin(contract),
                'runtimeScale': derived['rig']['runtimeScale'],
                'limits': 'Working-space proposal. Review cranial envelope and complete jaw before selection. Body and rig remain immutable; client appearance and resource resolution require separate validation.'}
    write_fresh(output, proposal)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('bank', 'contract', 'neck', 'comparator', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--palette', type=Path, action='append', required=True)
    p.add_argument('--animation', type=Path, action='append', required=True)
    a = p.parse_args(); prepare(a.bank, a.contract, a.neck, a.comparator, a.palette, a.animation, a.output)
