"""Reproduce frozen reduction from retained high-detail geometry and correspondence.

No simplification library, .tmp path, original checkout or client required.
Outputs are fresh geometry archives; protected scenes and native files are read-only.
"""
import argparse,json,hashlib
from pathlib import Path
import numpy as np
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(root,entry):
    p=(root/entry['path']).resolve()
    if not p.is_relative_to(root.resolve()) or sha(p)!=entry['sha256']:raise ValueError('Invalid input pin')
    return p
def run(root,output):
    if output.exists():raise ValueError('Fresh output required')
    output.mkdir(parents=True);results=[]
    for entry in json.loads((root/'recipes/manifest.json').read_text())['targets']:
        recipe=json.loads(read(root,entry['recipe']).read_text());z=np.load(read(root,recipe['highDetail']));expected=np.load(read(root,recipe['reducedGeometry']));meta=json.loads(read(root,recipe['metadata']).read_text());m=next(m for m in meta['meshes'] if m['part']=='chest' and m.get('render',True));corr=np.load(read(root,recipe['correspondence']));arrays={k:z[k] for k in z.files}
        p=arrays[m['positionsKey']];f=arrays[m['facesKey']];arrays[m['positionsKey']]=(p[f[corr['sourceTriangle']]]*corr['barycentric'][:,:,None]).sum(1);arrays[m['facesKey']]=corr['faces']
        if set(arrays)!=set(expected.files) or any(not np.array_equal(v,expected[k]) for k,v in arrays.items()):raise ValueError('Reproduction mismatch '+recipe['target'])
        np.savez_compressed(output/(recipe['target']+'.npz'),**arrays);results.append(dict(target=recipe['target'],everyGeometryArrayExact=True,triangles=len(corr['faces'])))
    (output/'report.json').write_text(json.dumps(dict(targets=results,sourceBodiesWritten=False,clientUsed=False),indent=2)+'\n');return results
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--release',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();print(json.dumps(run(a.release,a.output)))
