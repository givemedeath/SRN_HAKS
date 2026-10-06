"""Version parent-first rig serialization without changing any node bytes."""
import argparse
from pathlib import Path
import re
import sys
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'phenotypes'))
from retarget import NODE, nodes, transforms
from head_workflow import pin, require, verify_pins, write_fresh


def prepare(source, output):
    frozen=pin(source);text=Path(source).read_text(encoding='cp1252')
    geometry_text=text.split('endmodelgeom',1)[0]
    model=re.search(r'(?m)^newmodel\s+(\S+)',text)[1]
    matches=list(NODE.finditer(geometry_text)); skel=nodes(text)
    require(len(matches)==len(skel) and model.lower() in skel, 'Unique explicit model root required')
    require(skel[model.lower()]['parent']=='null', 'Model root must be unparented')
    blocks={m[2].lower():m[0].strip() for m in matches};ordered=[]; visiting=set();done=set()
    def visit(name):
        require(name not in visiting, 'Rig hierarchy cycle')
        if name in done:return
        visiting.add(name);parent=skel[name]['parent']
        if parent!='null':
            require(parent in skel,'Missing rig parent');visit(parent)
        ordered.append(name);done.add(name);visiting.remove(name)
    for name in skel:visit(name)
    start=re.search(r'(?m)^beginmodelgeom[^\n]*\n',text).end()
    end=text.index('endmodelgeom')
    candidate=text[:start]+'\n'.join(blocks[name] for name in ordered)+'\n'+text[end:]
    before=transforms(skel);after=transforms(nodes(candidate))
    require(set(before)==set(after) and all(np.array_equal(before[name],after[name]) for name in before),
            'Rig transform changed during serialization')
    output=Path(output);require(not output.exists(),'Fresh rig serialization revision required')
    (output/'ascii').mkdir(parents=True);(output/'resources').mkdir()
    rig=output/'ascii'/(model+'.mdl');rig.write_text(candidate,encoding='cp1252',newline='\n')
    emitted=rig.read_text(encoding='cp1252')
    require({m[2].lower():m[0].strip() for m in NODE.finditer(emitted.split('endmodelgeom',1)[0])}==blocks,
            'Original node text changed')
    require(emitted[emitted.index('endmodelgeom'):]==text[end:], 'Rig animation or trailing text changed')
    verify_pins([frozen]);write_fresh(output/'serialization.json',{
        'kind':'srn-head-fixture-rig-serialization','source':frozen,'output':pin(rig),
        'nodeCount':len(skel),'parentFirstOrder':ordered,'nodeTextPreserved':True,
        'maximumFrameError':0,'animationChanged':False,'bodyGeometryChanged':False,
        'nativeValidated':False,'clientValidated':False,'productionAccepted':False})


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
    a=p.parse_args();prepare(a.source,a.output)
