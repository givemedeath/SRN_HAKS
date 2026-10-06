"""Cap closed boundary loops without trimming, tapering or moving donor surfaces."""
import argparse
from pathlib import Path
import shutil
import numpy as np
from PIL import Image,ImageDraw,ImageFilter
from correct_neck_rim import write_glb
from head_export import triangles
from head_workflow import MAX_TRIANGLES,pin,require,verify_pins,write_fresh


def boundary_loops(points):
    vertices,ids=np.unique(points.reshape(-1,3),axis=0,return_inverse=True)
    edges={}
    for row in ids.reshape(-1,3):
        for a,b in zip(row,np.roll(row,-1)):edges.setdefault(tuple(sorted((int(a),int(b)))),[]).append((int(a),int(b)))
    boundary=[rows[0] for rows in edges.values() if len(rows)==1]
    outgoing={};incoming={}
    for a,b in boundary:outgoing.setdefault(a,[]).append(b);incoming.setdefault(b,[]).append(a)
    require(set(outgoing)==set(incoming) and all(len(outgoing[v])==len(incoming[v])==1 for v in outgoing),
            'Branching/open or inconsistently wound boundary requires donor review; no surface is altered')
    remaining=set(outgoing);loops=[]
    while remaining:
        start=min(remaining);loop=[];current=start
        while current in remaining:
            loop.append(current);remaining.remove(current);current=outgoing[current][0]
        require(current==start and len(loop)>=3,'Boundary is not a simple closed hole')
        loops.append(loop)
    return vertices,loops


def add_caps(points,normals,uv):
    vertices,loops=boundary_loops(points)
    if not loops:return points.copy(),normals.copy(),uv.copy(),[]
    grid=512;occupied_image=Image.new('L',(grid,grid),0);draw=ImageDraw.Draw(occupied_image)
    for triangle in uv:draw.polygon([tuple(p) for p in triangle*(grid-1)],fill=255)
    occupied=np.array(occupied_image.filter(ImageFilter.MaxFilter(3)))!=0
    additions=[];normal_additions=[];uv_additions=[];records=[]
    def cross(a,b):return float(a[0]*b[1]-a[1]*b[0])
    for loop in loops:
        # Reverse original directed edges so the cap shares opposite winding.
        ordered=list(reversed(loop));polygon=vertices[ordered];center=polygon.mean(0)
        basis=np.linalg.svd(polygon-center,full_matrices=False)[2][:2].T
        projected=(vertices-center)@basis
        area=sum(cross(projected[a],projected[b]) for a,b in zip(ordered,ordered[1:]+ordered[:1]))/2
        require(abs(area)>1e-12,'Hole has no stable projection; no surface is altered')
        sign=1 if area>0 else -1;remaining=ordered.copy();faces=[]
        while len(remaining)>3:
            found=False
            for i,b in enumerate(remaining):
                a,c=remaining[i-1],remaining[(i+1)%len(remaining)];pa,pb,pc=projected[[a,b,c]]
                if sign*cross(pb-pa,pc-pb)<=1e-14:continue
                others=[v for v in remaining if v not in (a,b,c)]
                if any(all(sign*cross(right-left,projected[v]-left)>=-1e-12
                           for left,right in ((pa,pb),(pb,pc),(pc,pa))) for v in others):continue
                faces.append([a,b,c]);del remaining[i];found=True;break
            require(found,'Self-intersecting/degenerate hole requires review; no surface is altered')
        faces.append(remaining)
        caps=vertices[np.asarray(faces)];normal=np.cross(caps[:,1]-caps[:,0],caps[:,2]-caps[:,0]);length=np.linalg.norm(normal,axis=1)
        require(np.all(length>1e-14),'Degenerate cap face')
        patch=next(((x,y) for y in range(1,grid-5) for x in range(1,grid-5) if not occupied[y:y+5,x:x+5].any()),None)
        require(patch is not None,'No unused cap UV patch; explicit atlas revision required')
        x,y=patch;occupied[y:y+5,x:x+5]=True
        low=projected[ordered].min(0);extent=np.ptp(projected[ordered],axis=0)
        require(np.all(extent>1e-8),'Degenerate cap UV projection')
        tex=(projected[np.asarray(faces)]-low)/extent*(3/grid)+np.asarray(patch)/grid+1/grid
        first=len(points)+sum(len(a) for a in additions)
        records.append({'boundaryVertices':len(loop),'faces':list(range(first,first+len(caps))),
                        'uvGrid':grid,'uvPatch':list(patch),'bounds':[polygon.min(0).tolist(),polygon.max(0).tolist()]})
        additions.append(caps);normal_additions.append(np.repeat((normal/length[:,None])[:,None,:],3,axis=1));uv_additions.append(tex)
    result=[np.concatenate([old,*new]) for old,new in ((points,additions),(normals,normal_additions),(uv,uv_additions))]
    require(len(result[0])<=MAX_TRIANGLES,'Caps exceed the final head triangle limit')
    _,remaining=boundary_loops(result[0]);require(not remaining,'Closed boundary remains after capping')
    return *result,records


def cap(source,output):
    source_pin=pin(source);p,n,uv=triangles(source,np.eye(4));pp,nn,uu,records=add_caps(p,n,uv)
    destination=Path(output);require(not destination.exists(),'Fresh cap-only revision required');destination.mkdir(parents=True)
    target=destination/'runtime.glb'
    if records:write_glb(target,pp,nn,uu,generator='SRN cap-only closure; original skull and jaw surface preserved')
    else:shutil.copyfile(source,target)
    returned=triangles(target,np.eye(4))
    error=max(float(np.abs(a-b[:len(a)]).max()) for a,b in zip((p,n,uv),returned))
    require(error<=1e-6,'Cap export altered the original surface')
    verify_pins([source_pin]);write_fresh(destination/'closure.json',{'kind':'srn-head-cap-only-closure','passed':True,
        'source':source_pin,'output':pin(target),'inputTriangles':len(p),'triangles':len(pp),'capTriangles':len(pp)-len(p),
        'holesCapped':len(records),'holes':records,'originalSurfaceMaximumAttributeError':error,
        'originalSurfacePreserved':True,'trimApplied':False,'taperApplied':False,'originalVerticesMoved':False,
        'remainingClosedBoundaryLoops':0,'neckCutBoundaryEdges':0,'uncappedClosedNeckLoops':0,
        'clientValidated':False,'productionAccepted':False})


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();cap(args.source,args.output)
