"""Decode the compiled fixture rig and verify preserved bind frames."""
import argparse
from pathlib import Path
import subprocess
import sys
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'phenotypes'))
from retarget import nodes, transforms
from tool_runtime import tool
from head_workflow import pin,read,require,sha,verify_pins,write_fresh


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
    verify_pins([proof['source'],proof['output']])
    write_fresh(output,{'kind':'srn-head-native-fixture-rig-audit','passed':True,'serialization':pin(serialization),
        'compilation':pin(folder/'native-compile.json'),'binary':pin(binary),'decoded':pin(decoded),
        'nodeCount':len(original),'maximumFrameError':error,'bodyGeometryChanged':False,
        'sourceRigPreserved':True,'clientValidated':False,'productionAccepted':False})


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--serialization',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
    a=p.parse_args();audit(a.serialization,a.output)
