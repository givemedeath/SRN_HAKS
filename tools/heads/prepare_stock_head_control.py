"""Create a geometry-only stock-head comparator without changing game assets."""
import argparse
from pathlib import Path
import sys
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'phenotypes'))
from prepare_effective_body_preview import mesh_corners
from correct_neck_rim import write_glb
from head_workflow import pin,read,require,write_fresh


def prepare(source,assembly,target,output):
    output=Path(output);require(not output.exists(),'Fresh control output required');output.mkdir(parents=True)
    rows=mesh_corners(Path(source).read_text(encoding='cp1252'))
    p,n,uv=[np.concatenate([row[key] for row in rows]) for key in ('position','normal','uv')]
    write_glb(output/'stock-head.glb',p,n,uv)
    write_fresh(output/'fit.json',{'source':pin(output/'stock-head.glb'),'target':pin(target),
        'localMatrix':np.eye(4).tolist(),'previewOnly':True,'comparatorSource':pin(source)})
    control=read(assembly);control['kind']='srn-head-stock-control-preview';control['heads']=[{'fit':pin(output/'fit.json')}]
    write_fresh(output/'assembly.json',control)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('source','assembly','target','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();prepare(a.source,a.assembly,a.target,a.output)
