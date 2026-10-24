"""Install a CPU-built shadow candidate in Blender without importing SciPy."""
import sys
from pathlib import Path
import bpy
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from tools.headkit.common import read,write,verify,require
from tools.itemkit import blender_worker as worker


def main():
    config=read(sys.argv[sys.argv.index('--')+1]);verify(config['inputs'])
    out=Path(config['output']);out.mkdir(parents=True,exist_ok=False)
    with np.load(config['source'],allow_pickle=False) as data:p=data['b_positions'];f=data['b_faces']
    worker.reset();mesh=bpy.data.meshes.new('source');mesh.from_pydata(p.tolist(),[],f.tolist());mesh.update()
    obj=bpy.data.objects.new('item_b',mesh);bpy.context.scene.collection.objects.link(obj)
    scene=out/'source.blend';bpy.ops.wm.save_as_mainfile(filepath=str(scene))
    cfg={**config,'scene':str(scene)}
    reduction=out/'reduce';reduction.mkdir();low=worker.reduce(cfg,reduction)
    require('shadowSource' in low,'Reduction did not emit early shadow source')
    cfg['scene']=str(reduction/'scene.blend')
    installed=out/'shadow';installed.mkdir();report=worker.reduce(cfg,installed,shadow=True)
    require(report['budget']['assembly']<=100 and report['topology']['b']['closedWound'],'Invalid installed shadow')
    require('scipy' not in sys.modules,'Blender imported SciPy')
    cfg['shadowCandidates']['b']['policyHash']='0'*64
    rejected=out/'stale-policy';rejected.mkdir()
    try:worker.reduce(cfg,rejected,shadow=True)
    except ValueError as exc:require('policy changed' in str(exc),'Unexpected policy error')
    else:raise AssertionError('Stale shadow policy accepted')
    verify(config['inputs']);write(out/'result.json',{'passed':True,'shadowTriangles':report['budget']['assembly'],
          'openingPreserved':True,'policyMismatchRejected':True,'scipyImportedByBlender':False},fresh=True)


if __name__=='__main__':main()
