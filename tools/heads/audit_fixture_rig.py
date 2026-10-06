"""Decode the compiled fixture rig and verify preserved bind frames."""
import argparse
from pathlib import Path
import subprocess
import sys
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'phenotypes'))
from retarget import nodes, transforms, rotations
from rig_controller_audit import controller_signature, CLIP
from tool_runtime import tool
from head_workflow import pin,read,require,sha,verify_pins,write_fresh


def animation_error(original, returned):
    before={v['clip']:v for v in controller_signature(original)}
    after={v['clip']:v for v in controller_signature(returned)}
    require(set(before)==set(after),'Native rig animation inventory changed')
    maximum=0.;rotation_error=0.;controllers=0
    for name,clip in before.items():
        a={v['name']:v for v in clip['nodes']};b={v['name']:v for v in after[name]['nodes']}
        require(set(a)==set(b),'Native animation node inventory changed')
        for node in a:
            aa=dict(a[node]['keyed']);bb=dict(b[node]['keyed'])
            require(set(aa)==set(bb),'Native animation controller inventory changed')
            for key in aa:
                x=np.asarray(aa[key]);y=np.asarray(bb[key])
                require(x.shape==y.shape,'Native animation key counts changed')
                if key=='orientationkey':
                    require(x.shape[1]==5,'Unexpected native orientation key encoding')
                    maximum=max(maximum,float(np.abs(x[:,0]-y[:,0]).max()))
                    rotation_error=max(rotation_error,max(float(np.abs(rotations(xx[1:])-rotations(yy[1:])).max()) for xx,yy in zip(x,y)))
                else:maximum=max(maximum,float(np.abs(x-y).max()))
                controllers+=1
        def duration(text):
            import re
            body=next(v[2] for v in CLIP.finditer(text) if v[1].lower()==name)
            return float(re.search(r'(?mi)^\s*length\s+(\S+)',body)[1])
        maximum=max(maximum,abs(duration(original)-duration(returned)))
    require(maximum<2e-6,'Native animation timing or controller values changed')
    # mdlcomp compresses near-identity rotation keys to zero. Compare their
    # effective rotations, rather than their arbitrary axis at zero angle.
    require(rotation_error<.002,'Native animation rotation exceeds bounded compiler quantization')
    return {'clips':len(before),'keyedControllers':controllers,'maximumTimingTranslationError':maximum,
            'maximumRotationMatrixError':rotation_error,'rotationMatrixTolerance':.002}


def audit(serialization, output):
    proof=read(serialization);verify_pins([proof['source'],proof['output']])
    source=Path(proof['output']['path']);folder=source.parent.parent
    receipt=read(folder/'native-compile.json');require(receipt['complete'] is True,'Complete native rig compilation required')
    model=next(row for row in receipt['models'] if row['name']==source.name)
    binary=folder/'resources'/source.name
    require(model['sourceSha256']==sha(source) and model['binarySha256']==sha(binary),'Native rig receipt differs')
    decoded=Path(output).with_suffix('.mdl');require(not decoded.exists(),'Fresh native rig decode required')
    subprocess.run([str(tool('mdlcomp')),'-d','-e',str(binary),str(decoded)],capture_output=True,check=True)
    original=nodes(Path(proof['source']['path']).read_text(encoding='cp1252'))
    returned=nodes(decoded.read_text(encoding='cp1252'))
    require(set(original)==set(returned),'Native rig node inventory changed')
    require(all(original[name]['parent']==returned[name]['parent'] for name in original),'Native hierarchy changed')
    before=transforms(original);after=transforms(returned)
    error=max(float(np.abs(before[name]-after[name]).max()) for name in before)
    require(error<2e-6,'Native attachment frame changed')
    animation=animation_error(Path(proof['source']['path']).read_text(encoding='cp1252'),decoded.read_text(encoding='cp1252'))
    verify_pins([proof['source'],proof['output']])
    write_fresh(output,{'kind':'srn-head-native-fixture-rig-audit','passed':True,'serialization':pin(serialization),
        'compilation':pin(folder/'native-compile.json'),'binary':pin(binary),'decoded':pin(decoded),
        'nodeCount':len(original),'maximumFrameError':error,'bodyGeometryChanged':False,
        'animationAudit':animation,
        'sourceRigPreserved':True,'clientValidated':False,'productionAccepted':False})


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--serialization',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
    a=p.parse_args();audit(a.serialization,a.output)
