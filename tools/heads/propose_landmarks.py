"""Measure anatomical extrema as explicit, unapproved landmark proposals."""
import argparse
from pathlib import Path
import sys
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'phenotypes'))
from prepare_effective_body_preview import mesh_corners
from head_export import triangles
from head_workflow import MAX_TRIANGLES,fit_similarity,pin,write_fresh


def extrema(points,axis,sign):
    values=points[:,axis]*sign
    return points[values>=values.max()-.001*np.ptp(values)].mean(0)


def propose(source,stock,target,output):
    points=triangles(source,np.eye(4),maximum=MAX_TRIANGLES)[0].reshape(-1,3)
    comparator=np.concatenate([row['position'].reshape(-1,3) for row in mesh_corners(Path(stock).read_text(encoding='cp1252'))])
    source_landmarks=np.array([extrema(points,0,-1),extrema(points,0,1),extrema(points,1,-1),extrema(points,1,1),extrema(points,2,1)])
    destination=np.array([extrema(comparator,0,1),extrema(comparator,0,-1),extrema(comparator,1,1),extrema(comparator,1,-1),extrema(comparator,2,1)])
    measured=fit_similarity(source_landmarks,destination,1)
    write_fresh(output,{'kind':'srn-head-landmark-proposal','source':pin(source),'targetProposal':pin(target),
        'comparator':pin(stock),'coordinateSpace':'nwn-head-local',
        'landmarkNames':['left lateral ear-width proxy','right lateral ear-width proxy','anterior nose tip','posterior occiput proxy','hair crown'],
        'sourceLandmarks':source_landmarks.tolist(),'targetLandmarks':destination.tolist(),
        'measurement':measured,'approved':False,'limitation':'Extrema are geometric proposals requiring anatomical and assembly review, not automatic fit approval.'})


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('source','stock','target','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();propose(a.source,a.stock,a.target,a.output)
