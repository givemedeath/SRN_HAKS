"""Measure the lowered cap against the protected stock neck's convex envelope."""
import argparse
import itertools
from pathlib import Path
import sys
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'phenotypes'))
from retarget import nodes
from rig_controller_audit import world_frames
from prepare_effective_body_preview import mesh_corners
from head_export import triangles
from head_workflow import pin,read,require,validate_target,verify_pins,write_fresh


def audit(fit_path,correction_path,output):
    fit=read(fit_path);c=read(correction_path);verify_pins([fit['source'],fit['target'],c['output']])
    target=validate_target(read(fit['target']['path']))
    require(c['output']==fit['source'] and c['taperDepthMetres']>0,'Exact downward tapered selection required')
    frames=world_frames(nodes(Path(target['rig']['path']).read_text(encoding='cp1252')))
    matrix=np.linalg.inv(np.asarray(target['headBindMatrix']))@frames['neck_g']
    neck=np.concatenate([m['position'].reshape(-1,3) for m in mesh_corners(Path(target['neckGeometry']['path']).read_text(encoding='cp1252'))])
    neck=np.unique(np.round(neck@matrix[:3,:3].T+matrix[:3,3],8),axis=0)
    require(4<=len(neck)<=128,'Bounded stock-neck envelope required')
    planes=[]
    for a,b,d in itertools.combinations(neck,3):
        normal=np.cross(b-a,d-a);length=np.linalg.norm(normal)
        if length<1e-10:continue
        normal/=length;distance=(neck-a)@normal
        if distance.max()<=1e-7:planes.append((normal,float(-a@normal)))
        elif distance.min()>=-1e-7:planes.append((-normal,float(a@normal)))
    require(len(planes)>=4,'Stock neck has no closed convex envelope')
    p,_,_=triangles(fit['source']['path'],fit['localMatrix']);cap=p[c['capFaceIds']].reshape(-1,3)
    clearance=min(float(-(cap@n+offset).max()) for n,offset in planes)
    require(clearance>=.002,f'Lowered cap must sit at least 2 mm inside stock neck envelope; clearance={clearance:.6f} m')
    write_fresh(output,{'kind':'srn-head-neck-connector-audit','passed':True,'fit':pin(fit_path),'correction':pin(correction_path),
        'source':fit['source'],'neckGeometry':target['neckGeometry'],'capInsideStockNeckConvexEnvelope':True,
        'minimumCapClearanceMetres':clearance,'capHeadLocalZ':c['capHeadLocalZ'],
        'taperDepthMetres':c['taperDepthMetres'],'taperInwardScale':c['taperInwardScale'],
        'bodyOrRigChanged':False,'limitation':'Standing convex-envelope containment is a numerical check; visible standing and moving anatomy require separate review.',
        'clientValidated':False,'productionAccepted':False})


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('fit','correction','output'):p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();audit(a.fit,a.correction,a.output)
