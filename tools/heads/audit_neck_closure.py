"""Prove the selected donor's cut neck boundary is capped and within budget."""
import argparse
from pathlib import Path
import numpy as np
from head_export import triangles
from head_workflow import pin,read,require,verify_pins,write_fresh


def audit(fit_path,correction_path,output):
    fit=read(fit_path);c=read(correction_path);verify_pins([fit['source'],c['output']])
    require(fit['source']==c['output'] and c['closedNeckRequested'] is True,'Selected closed neck correction required')
    p,n,uv=triangles(fit['source']['path'],fit['localMatrix']);height=c['planeHeadLocalZ']
    v,ids=np.unique(np.round(p.reshape(-1,3),6),axis=0,return_inverse=True);edges={}
    for row in ids.reshape(-1,3):
        for a,b in zip(row,np.roll(row,-1)):edges.setdefault(tuple(sorted((int(a),int(b)))),[]).append((a,b))
    cut=[rows for key,rows in edges.items() if np.all(np.abs(v[list(key),2]-height)<2e-6)]
    boundaries=sum(len(rows)==1 for rows in cut);require(boundaries==0,'Open boundary remains at neck cut')
    cap_height=c.get('capHeadLocalZ',height)
    caps=p[c['capFaceIds']];require(np.all(np.abs(caps[:,:,2]-cap_height)<2e-6),'Cap moved out of declared plane')
    require(np.all(np.cross(caps[:,1]-caps[:,0],caps[:,2]-caps[:,0])[:,2]<0),'Cap faces inward')
    if c.get('taperDepthMetres',0):
        require(cap_height<height and 0<c['taperInwardScale']<1,'Connector must taper inward and down')
        require(all(len(rows)!=1 for key,rows in edges.items() if np.all(np.abs(v[list(key),2]-cap_height)<2e-6)),
                'Open boundary remains at lowered cap')
    near_edges=[key for key,rows in edges.items() if len(rows)==1 and np.max(v[list(key),2])<=height+.003]
    near=len(near_edges)
    neighbors={}
    for first,second in near_edges:
        neighbors.setdefault(first,set()).add(second);neighbors.setdefault(second,set()).add(first)
    remaining=set(neighbors);closed_loops=0
    while remaining:
        pending=[min(remaining)];component=set()
        while pending:
            node=pending.pop()
            if node in component:continue
            component.add(node);pending.extend(neighbors[node]-component)
        remaining-=component
        closed_loops+=all(len(neighbors[node])==2 for node in component)
    require(closed_loops==0,'An additional closed neck opening needs a separate cap')
    write_fresh(output,{'kind':'srn-head-neck-closure-audit','passed':True,'fit':pin(fit_path),'correction':pin(correction_path),
        'source':fit['source'],'neckCutBoundaryEdges':boundaries,'uncappedClosedNeckLoops':closed_loops,
        'nearOriginalOpenChainEdges':near,'originalChainDiagnostics':[{'positions':v[list(key)].tolist(),
             'lengthMetres':float(np.linalg.norm(v[key[0]]-v[key[1]]))} for key in near_edges],'capLoops':c['capLoops'],
        'capTriangles':len(caps),'triangles':len(p),'donorFramePreserved':True,'bodyOrRigChanged':False,
        'taperDepthMetres':c.get('taperDepthMetres',0),'taperInwardScale':c.get('taperInwardScale',1),
        'taperWallTriangles':c.get('taperWallTriangles',0),'capHeadLocalZ':cap_height,
        'limitation':'Created neck openings are closed. Existing remesh nonmanifold folds/open chains are separately reported; they are not simple closed holes that can be safely capped. Inspect their visibility in the client.',
        'clientValidated':False,'productionAccepted':False})


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('fit','correction','output'):parser.add_argument('--'+key,type=Path,required=True)
    a=parser.parse_args();audit(a.fit,a.correction,a.output)
