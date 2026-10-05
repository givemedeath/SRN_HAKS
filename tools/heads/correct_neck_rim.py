"""Version a head-only neck trim and closed cap, preserving surviving UVs."""
import argparse
import json
from pathlib import Path
import struct
import numpy as np
from head_export import BASIS, triangles
from head_workflow import MAX_TRIANGLES, pin, read, require, verify_pins, write_fresh


def write_glb(path,p,n,uv,*,generator='SRN separately versioned head neck trim'):
    p=p.reshape(-1,3)@BASIS[:3,:3]; n=n.reshape(-1,3)@BASIS[:3,:3]
    uv=uv.reshape(-1,2).copy(); uv[:,1]=1-uv[:,1]
    arrays=[p.astype('<f4'),n.astype('<f4'),uv.astype('<f4')]
    binary=b''; views=[]; accessors=[]
    for index,array in enumerate(arrays):
        binary+=b'\0'*(-len(binary)%4); offset=len(binary); data=array.tobytes(); binary+=data
        views.append({'buffer':0,'byteOffset':offset,'byteLength':len(data),'target':34962})
        accessors.append({'bufferView':index,'componentType':5126,'count':len(array),
                          'type':'VEC2' if index==2 else 'VEC3','min':array.min(0).tolist(),'max':array.max(0).tolist()})
    doc={'asset':{'version':'2.0','generator':generator},'scene':0,
         'scenes':[{'nodes':[0]}],'nodes':[{'mesh':0}],
         'meshes':[{'primitives':[{'mode':4,'attributes':{'POSITION':0,'NORMAL':1,'TEXCOORD_0':2}}]}],
         'buffers':[{'byteLength':len(binary)}],'bufferViews':views,'accessors':accessors}
    encoded=json.dumps(doc,separators=(',',':')).encode(); encoded+=b' '*(-len(encoded)%4); binary+=b'\0'*(-len(binary)%4)
    path.write_bytes(struct.pack('<III',0x46546c67,2,28+len(encoded)+len(binary))+
                     struct.pack('<II',len(encoded),0x4e4f534a)+encoded+struct.pack('<II',len(binary),0x004e4942)+binary)


def clip(p,n,uv,height):
    result=[]; unchanged=0; removed=0; split=0
    for ps,ns,us in zip(p,n,uv):
        polygon=[np.r_[x,y,z] for x,y,z in zip(ps,ns,us)]
        if all(x[2]>=height for x in polygon): unchanged+=1
        elif all(x[2]<height for x in polygon): removed+=1; continue
        else: split+=1
        clipped=[]
        for left,right in zip(polygon,polygon[1:]+polygon[:1]):
            inside=left[2]>=height; other=right[2]>=height
            if inside: clipped.append(left)
            if inside!=other:
                t=(height-left[2])/(right[2]-left[2]); value=left+t*(right-left)
                value[3:6]/=np.linalg.norm(value[3:6]); clipped.append(value)
        for i in range(1,len(clipped)-1): result.append([clipped[0],clipped[i],clipped[i+1]])
    values=np.asarray(result); require(0<len(values)<=MAX_TRIANGLES,'Trim exceeds runtime triangle cap')
    return values[:,:,:3],values[:,:,3:6],values[:,:,6:8],{'unchangedTriangles':unchanged,'removedTriangles':removed,'splitTriangles':split}


def smooth_normals(points,angle):
    require(0<angle<=90,'Explicit normal crease angle required')
    face=np.cross(points[:,1]-points[:,0],points[:,2]-points[:,0]); length=np.linalg.norm(face,axis=1)
    require(np.all(length>1e-14),'Degenerate corrected triangle')
    unit=face/length[:,None]; ids=np.unique(np.round(points.reshape(-1,3),7),axis=0,return_inverse=True)[1].reshape(-1,3)
    neighbors={}
    for i,row in enumerate(ids):
        for vertex in row: neighbors.setdefault(int(vertex),set()).add(i)
    normals=np.empty_like(points); threshold=np.cos(np.deg2rad(angle))
    for i,row in enumerate(ids):
        for corner,vertex in enumerate(row):
            selected=[j for j in neighbors[int(vertex)] if unit[i]@unit[j]>=threshold]
            value=face[selected].sum(0); normals[i,corner]=value/np.linalg.norm(value)
    return normals


def cap_neck(points,normals,uv,height,taper_depth=0,inset=1,center=None):
    require(0<=taper_depth<=.06,'Neck taper depth must be between zero and 60 mm')
    require(0<inset<=1 and (taper_depth==0 or inset<1),'A downward taper requires inward scale')
    require(taper_depth==0 or center is not None,'Explicit attachment-center XY required')
    # Position welding is diagnostic only. Surviving corner P/N/UV never change.
    vertices,inverse=np.unique(np.round(points.reshape(-1,3),6),axis=0,return_inverse=True)
    edges={}
    for row in inverse.reshape(-1,3):
        for first,second in zip(row,np.roll(row,-1)):
            key=tuple(sorted((int(first),int(second))))
            edges.setdefault(key,[]).append((int(first),int(second)))
    boundary=[rows[0] for rows in edges.values() if len(rows)==1
              and all(abs(vertices[v,2]-height)<2e-6 for v in rows[0])]
    require(boundary,'No open neck boundary at the declared trim plane')
    neighbors={}
    for first,second in boundary:
        neighbors.setdefault(first,[]).append(second);neighbors.setdefault(second,[]).append(first)
    require(all(len(rows)==2 for rows in neighbors.values()),'Branching/open neck boundary; manual correction required')
    # Snap only newly cut boundary positions to the same sub-micrometre welded
    # representatives used by the cap, making the exported boundary exact.
    points=points.copy()
    flat=points.reshape(-1,3); selected=np.isin(inverse,list(neighbors))
    flat[selected]=vertices[inverse[selected]]; flat[selected,2]=height
    loops=[]; remaining=set(neighbors)
    while remaining:
        start=min(remaining); loop=[start]; remaining.remove(start); previous=start; current=min(neighbors[start])
        while current!=start:
            require(current in remaining,'Intersecting neck boundary loops')
            loop.append(current); remaining.remove(current)
            following=next(v for v in neighbors[current] if v!=previous);previous,current=current,following
        loops.append(loop)
    # Reserve an actually unused patch for the new underside UV island. Mark
    # conservative triangle bounding boxes, then require an empty 4x4 patch.
    from PIL import Image,ImageDraw,ImageFilter
    grid=512; occupied_image=Image.new('L',(grid,grid),0);draw=ImageDraw.Draw(occupied_image)
    for triangle in uv:
        draw.polygon([tuple(value) for value in triangle*(grid-1)],fill=255)
    occupied=np.asarray(occupied_image.filter(ImageFilter.MaxFilter(3)))!=0
    patch=next(((x,y) for y in range(1,grid-5) for x in range(1,grid-5)
                if not occupied[y:y+5,x:x+5].any()),None)
    require(patch is not None,'No free cap UV island; explicit atlas revision required')
    caps=[]; walls=[]
    lowered=vertices.copy()
    if center is not None:center=np.asarray(center,dtype=float)
    if taper_depth:
        require(center.shape==(2,) and np.isfinite(center).all(),'Finite attachment-center XY required')
        lowered[:,:2]=center+(vertices[:,:2]-center)*inset
        lowered[:,2]=height-taper_depth
    # Ear clipping preserves concave boundary shape instead of a center fan
    # that could bridge a concavity. Reverse the boundary for opposite winding.
    for boundary_loop in loops:
        ids=list(reversed(boundary_loop)); polygon=vertices[ids,:2]
        def cross2(a,b): return float(a[0]*b[1]-a[1]*b[0])
        area=sum(cross2(polygon[i],polygon[(i+1)%len(ids)]) for i in range(len(ids)))/2
        require(abs(area)>1e-10,'Degenerate neck opening')
        if area>0:ids.reverse()
        if taper_depth:
            for a,b in zip(ids,ids[1:]+ids[:1]):
                walls.extend([[vertices[a],vertices[b],lowered[a]],
                              [vertices[b],lowered[b],lowered[a]]])
        while len(ids)>3:
            found=False
            for i in range(len(ids)):
                a,b,c=ids[i-1],ids[i],ids[(i+1)%len(ids)]; pa,pb,pc=vertices[[a,b,c],:2]
                if cross2(pb-pa,pc-pb)>=-1e-12: continue
                others=[v for v in ids if v not in (a,b,c)]
                if any(all(cross2(right-left,vertices[v,:2]-left)<=1e-10
                           for left,right in ((pa,pb),(pb,pc),(pc,pa))) for v in others): continue
                caps.append(lowered[[a,b,c]].copy()); del ids[i]; found=True; break
            require(found,'Neck cap is self-intersecting or degenerate')
        caps.append(lowered[ids].copy())
    caps=np.asarray(caps); caps[:,:,2]=height-taper_depth
    added=np.concatenate((np.asarray(walls).reshape(-1,3,3),caps))
    low=added[:,:,:2].min((0,1)); extent=np.ptp(added[:,:,:2],axis=(0,1))
    require(np.all(extent>1e-6),'Degenerate cap span')
    cap_uv=(added[:,:,:2]-low)/extent*(3/grid)+np.asarray(patch)/grid+1/grid
    face=np.cross(added[:,1]-added[:,0],added[:,2]-added[:,0]);length=np.linalg.norm(face,axis=1)
    require(np.all(length>1e-14),'Degenerate tapered connector triangle')
    cap_normals=np.repeat((face/length[:,None])[:,None,:],3,axis=1)
    require(len(points)+len(added)<=MAX_TRIANGLES,'Closed cap exceeds runtime triangle budget')
    return (np.concatenate((points,added)),np.concatenate((normals,cap_normals)),np.concatenate((uv,cap_uv)),
            {'capTriangles':len(caps),'capLoops':len(loops),'neckBoundaryEdgesBefore':len(boundary),
             'topologyWeldPrecisionMetres':1e-6,'capUvGrid':grid,'capUvPatch':list(patch),
             'maximumBoundarySnapMetres':float(np.sqrt(3)*.5e-6),
             'taperDepthMetres':taper_depth,'taperInwardScale':inset,'taperCenterXY':None if center is None else center.tolist(),
             'capHeadLocalZ':height-taper_depth,'taperWallTriangles':len(walls),
             'taperWallFaceIds':list(range(len(points),len(points)+len(walls))),
             'connectorFaceIds':list(range(len(points),len(points)+len(added))),
             'capFaceIds':list(range(len(points)+len(walls),len(points)+len(added)))})


def correct(fit_path,neck,height,angle,output,closed=False,taper_depth=0,inset=1,center=None):
    fit=read(fit_path); verify_pins([fit['source'],fit['target'],pin(neck)])
    require(-.06<=height<=0,'Trim must remain in the head neck base')
    p,n,uv=triangles(fit['source']['path'],fit['localMatrix'],maximum=12000); original_count=len(p)
    p,n,uv,counts=clip(p,n,uv,height)
    if closed:
        p,n,uv,cap_counts=cap_neck(p,n,uv,height,taper_depth,inset,center); counts.update(cap_counts)
    else:require(taper_depth==0,'A tapered connector requires a closed neck')
    require(0<=angle<=90,'Normal crease must be explicit; zero preserves authored normals')
    if angle: n=smooth_normals(p,angle)
    matrix=np.asarray(fit['localMatrix']); inverse=np.linalg.inv(matrix)
    p=p@inverse[:3,:3].T+inverse[:3,3]
    n=n@matrix[:3,:3]; n/=np.linalg.norm(n,axis=2)[:,:,None]
    output=Path(output); require(not output.exists(),'Fresh neck correction required'); output.mkdir(parents=True)
    source=output/'runtime.glb'; write_glb(source,p,n,uv)
    triangles(source,np.eye(4))
    write_fresh(output/'correction.json',{'kind':'srn-head-neck-rim-correction','fit':pin(fit_path),
        'source':fit['source'],'neckGeometry':pin(neck),'output':pin(source),'planeHeadLocalZ':height,
        'operation':'clip donor below plane; interpolate boundary P/N/UV; '+('close underside in unused UV patch' if closed else 'leave underside open'),
        'bodyOrRigChanged':False,'closedNeckRequested':closed,
        'normalPolicy':'preserve authored normals' if angle==0 else 'area-weighted corner normals at explicit crease',
        'normalCreaseDegrees':angle,'normalPositionGroupingPrecision':7,
        'inputTriangles':original_count,'outputTriangles':len(p),**counts,
        'standingAccepted':False,'motionAccepted':False,'productionAccepted':False})


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('fit','neck','output'): parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--height',type=float,required=True)
    parser.add_argument('--normal-crease',type=float,required=True)
    parser.add_argument('--cap-neck',action='store_true')
    parser.add_argument('--taper-depth',type=float,default=0)
    parser.add_argument('--taper-inset',type=float,default=1)
    parser.add_argument('--taper-center',type=float,nargs=2)
    a=parser.parse_args(); correct(a.fit,a.neck,a.height,a.normal_crease,a.output,a.cap_neck,a.taper_depth,a.taper_inset,a.taper_center)
