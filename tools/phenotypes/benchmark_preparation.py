"""Reproducible CPU preparation benchmark; synthetic workload, no client evidence."""
import argparse
from pathlib import Path
import tempfile
import time
import numpy as np
from pose_preview_bridge import pose
from run_preparation import PreparationContext
from shared_toolchain import sha
from shared_tools import write_json

def run(samples=120,joints=80):
    with tempfile.TemporaryDirectory() as folder:
        root=Path(folder)
        skeleton=['newmodel pmh0','setsupermodel pmh0 a_ba','beginmodelgeom pmh0','node dummy pmh0','parent NULL','endnode']
        clip=['newmodel a_ba','setsupermodel a_ba NULL','beginmodelgeom a_ba','node dummy a_ba','parent NULL','endnode','endmodelgeom a_ba','newanim pause1 a_ba','length 1']
        for number in range(joints):
            name='joint'+str(number)
            skeleton += ['node dummy '+name,'parent pmh0','position 1 2 3','endnode']
            clip += ['node dummy '+name,'parent a_ba','positionkey 2','0 1 2 3','1 2 3 4','endnode']
        skeleton += ['endmodelgeom pmh0','donemodel pmh0'];clip += ['doneanim pause1 a_ba','donemodel a_ba']
        (root/'pmh0.mdl').write_text('\n'.join(skeleton),encoding='cp1252');(root/'a_ba.mdl').write_text('\n'.join(clip),encoding='cp1252')
        times=np.linspace(0,1,samples);begun=time.perf_counter()
        uncached=[pose(root,'pmh0','pause1',float(t))[0] for t in times];uncached_seconds=time.perf_counter()-begun
        begun=time.perf_counter();context=PreparationContext(target_revision='synthetic',rig_revision='80-joint-fixture',animation_revision='linear-clip',settings={'samples':samples})
        cached=[pose(root,'pmh0','pause1',float(t),context=context)[0] for t in times];cached_seconds=time.perf_counter()-begun
        for a,b in zip(uncached,cached):
            for name in a:np.testing.assert_array_equal(a[name],b[name])
        return {'kind':'pose-preparation-benchmark','workload':'synthetic NWN ASCII rigid controller fixture',
            'samples':samples,'joints':joints,'uncachedSeconds':uncached_seconds,'cachedSeconds':cached_seconds,
            'ratio':uncached_seconds/cached_seconds,'equivalence':'array-exact','preparation':context.receipt(),
            'clientEvidence':False,'limits':'CPU sampler timing only; excludes render, bake, native compilation and client performance.'}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    write_json(a.output,run(),fresh=True)
