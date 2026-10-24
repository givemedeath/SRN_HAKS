"""Immutable bake recovery bindings and strict pixel classification checks."""
import numpy as np
import hashlib
from pathlib import Path
from tools.headkit.common import require, verify, read, pin, write


def recovery_inputs(proof):
    require(proof.get('schemaVersion') == 1 and proof.get('kind') == 'item-bake-recovery', 'Unsupported recovery proof')
    rows = [proof[key] for key in ('scene','sourceScene','pixels','masks')]+proof['externalImages']
    verify(rows)
    return rows


def validate_pixels(pixels, owners, caps, misses, face_count):
    require(pixels.ndim==3 and pixels.shape[2]==4 and pixels.shape[:2]==owners.shape==caps.shape==misses.shape,
            'Recovery dimensions differ')
    require(np.issubdtype(owners.dtype,np.integer) and caps.dtype==misses.dtype==bool,
            'Explicit integer owners and boolean masks required')
    require(np.isfinite(pixels).all() and np.all((owners>=-1)&(owners<face_count)), 'Invalid retained pixels/owners')
    require(not np.any(caps & (owners<0)), 'Hidden caps must have owners')
    expected = np.all(np.abs(pixels[...,:3]-[1,0,1])<1e-5,axis=2)&(owners>=0)&~caps
    require(np.array_equal(misses, expected), 'Retained miss classification differs')
    return int(misses.sum())


def successful_pixel_hash(pixels, misses):
    digest=hashlib.sha256()
    for row, mask in zip(pixels,misses):
        digest.update(np.ascontiguousarray(row[~mask]).tobytes())
    return digest.hexdigest()


def prepare_recovery(proof_path, policy_path, output):
    """Prepare the declared input manifest for the existing Blender launcher."""
    from .contracts import code_pins
    proof_pin=pin(proof_path);policy_pin=pin(policy_path)
    proof=read(proof_path);policy=read(policy_path)
    inputs=[proof_pin,policy_pin]+recovery_inputs(proof)+code_pins()
    require(policy.get('method')=='nearest-finished-donor' and 0<policy.get('maximumDistance',0)<=.003
            and 0<policy.get('minimumNormalAlignment',0)<=1, 'Explicit bounded donor correction policy required')
    root=Path(output).resolve();root.mkdir(parents=True,exist_ok=False)
    cfg={'stage':'recover-bake','scene':proof['sourceScene']['path'],'recoveryProof':proof_pin['path'],
         'family':proof['family'],'processing':{**proof['processing'],'missCorrection':policy},
         'inputs':inputs,'output':str(root/'recovered')}
    verify(inputs)
    write(root/'worker.json',cfg,fresh=True)
    write(root/'inputs.json',inputs+[pin(root/'worker.json')],fresh=True)
    return {'config':pin(root/'worker.json'),'inputManifest':pin(root/'inputs.json')}


if __name__=='__main__':
    import argparse,json
    parser=argparse.ArgumentParser(description='Prepare a retained-bake recovery; dispatch the returned config through the verified Blender launcher.')
    parser.add_argument('--proof',required=True);parser.add_argument('--policy',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();print(json.dumps(prepare_recovery(args.proof,args.policy,args.output),indent=2))
