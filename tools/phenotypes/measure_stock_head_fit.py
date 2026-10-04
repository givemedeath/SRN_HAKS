"""Measure installed Human head/neck geometry for headless body fitting."""
import argparse
import json
from pathlib import Path
import numpy as np

from audit_geometry import arrays
from pipeline import digest,save_json,RACES
from retarget import NODE,nodes,transforms
from inspect_stock_joints import JOINTS


def measure(baseline, target_heights=None):
    if target_heights is None:
        target_heights=sorted({height for race in RACES.values() for height in race["height"].values()})
    directory=baseline/'ascii';prefix='pmh0'
    skeleton=directory/(prefix+'.mdl')
    world=transforms(nodes(skeleton.read_text(encoding='cp1252')))
    coordinates={};inputs={str(skeleton.resolve()):digest(skeleton)}
    for part,joint in JOINTS.items():
        path=directory/(prefix+'_'+part+'001.mdl');text=path.read_text(encoding='cp1252')
        local=transforms(nodes(text));points=[]
        for node in NODE.finditer(text.split('endmodelgeom')[0]):
            vertices=arrays(node[3],'verts')
            if not vertices:continue
            matrix=world[joint]@local[node[2].lower()]
            points.extend((matrix@np.c_[vertices,np.ones(len(vertices))].T).T[:,:3])
        if not points:raise RuntimeError('No geometry: '+part)
        coordinates[part]=np.asarray(points)
        inputs[str(path.resolve())]=digest(path)
    floor=min(p[:,2].min() for p in coordinates.values())
    top=max(p[:,2].max() for p in coordinates.values());height=top-floor
    neck_top=coordinates['neck'][:,2].max()
    # The stock neck has an isolated high rear apex, not a flat cap. A flat
    # generated cap at that maximum surrounds the stock jaw. Use the stock
    # head attachment plane and measure the neck mesh section through it.
    cap_z=float(world['head_g'][2,3])
    neck_path=directory/(prefix+'_neck001.mdl')
    neck_text=neck_path.read_text(encoding='cp1252');local=transforms(nodes(neck_text));section=[]
    for node in NODE.finditer(neck_text.split('endmodelgeom')[0]):
        vertices=arrays(node[3],'verts');faces=arrays(node[3],'faces')
        if not vertices:continue
        matrix=world['neck_g']@local[node[2].lower()]
        points=(matrix@np.c_[vertices,np.ones(len(vertices))].T).T[:,:3]
        for face in faces:
            ids=[int(i) for i in face[:3]]
            for a,b in zip(ids,ids[1:]+ids[:1]):
                p,q=points[a],points[b]
                if (p[2]-cap_z)*(q[2]-cap_z)<0:
                    section.append(p+(q-p)*(cap_z-p[2])/(q[2]-p[2]))
    section=np.unique(np.round(section,9),axis=0)
    if len(section)<3:raise RuntimeError('No stock neck section at the head attachment')
    section_min,section_max=section.min(0),section.max(0)
    result={'stockPrefix':prefix,'stockHeight':height,'stockFloor':floor,
            'neckCapTop':neck_top,'headJoint':world['head_g'][:3,3].tolist(),
            'flatNeckCapReferenceZ':cap_z,
            'flatNeckCapSection':{'points':section.tolist(),'minimum':section_min.tolist(),
                'maximum':section_max.tolist(),'centre':((section_min+section_max)/2).tolist(),
                'radii':((section_max-section_min)/2).tolist()},
            'neckJoint':world['neck_g'][:3,3].tolist(),
            'headLocalBounds':[(coordinates['head']-world['head_g'][:3,3]).min(0).tolist(),
                               (coordinates['head']-world['head_g'][:3,3]).max(0).tolist()],
            'headNeckAxialOverlap':float(neck_top-coordinates['head'][:,2].min()),
            'inputs':inputs,'targets':[],
            'limitation':'Bind geometry measurements; assembled silhouette and motion remain required.'}
    for target in target_heights:
        scale=target/height
        result['targets'].append({'fullHeight':target,'stockScale':scale,
            'headlessBodyHeight':float((cap_z-floor)*scale),
            'headlessBodyHeightFraction':float((cap_z-floor)/height),
            'headJoint':((world['head_g'][:3,3]-[0,0,floor])*scale).tolist(),
            'neckJoint':((world['neck_g'][:3,3]-[0,0,floor])*scale).tolist(),
            'neckCapTop':float((cap_z-floor)*scale)})
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--baseline',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    result=measure(args.baseline);save_json(args.output,result);print(json.dumps(result))


if __name__=='__main__':main()
