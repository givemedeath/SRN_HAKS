"""Connected-chart unwrap with bounded local repair and measured atlas coverage."""
import time
import numpy as np
from .common import library, require


def physical_fans(mesh, preserve_authored_seams=True):
    p=np.asarray(mesh['positions']); f=np.asarray(mesh['faces']); corners=p[f]
    _,keys=np.unique(corners.reshape(-1,3),axis=0,return_inverse=True); keys=keys.reshape(-1,3)
    parent=np.arange(len(f)*3)
    def find(a):
        while parent[a]!=a: parent[a]=parent[parent[a]]; a=parent[a]
        return a
    def union(a,b):
        a,b=find(a),find(b)
        if a!=b: parent[max(a,b)]=min(a,b)
    normal=np.cross(corners[:,1]-corners[:,0],corners[:,2]-corners[:,0]); normal/=np.maximum(np.linalg.norm(normal,axis=1)[:,None],1e-30)
    edges={}
    for fi,row in enumerate(keys):
        for a,b in ((0,1),(1,2),(2,0)):
            ka,kb=int(row[a]),int(row[b]); edges.setdefault((min(ka,kb),max(ka,kb)),[]).append((fi,a,b,ka,kb))
    uv=np.asarray(mesh['uv'])
    for incident in edges.values():
        if len(incident)!=2: continue
        x,y=incident
        if x[3]!=y[4] or x[4]!=y[3] or np.dot(normal[x[0]],normal[y[0]])<.2: continue
        if preserve_authored_seams and (not np.allclose(uv[x[0],[x[1],x[2]]],uv[y[0],[y[2],y[1]]],rtol=0,atol=1e-8)):
            continue
        union(x[0]*3+x[1],y[0]*3+y[2]); union(x[0]*3+x[2],y[0]*3+y[1])
    roots=np.asarray([find(i) for i in range(len(parent))]); _,first,index=np.unique(roots,return_index=True,return_inverse=True)
    return corners.reshape(-1,3)[first],index.reshape(-1,3).astype(np.uint32)


def raster_audit(uv,size):
    if type(size) is not int or size <= 0:
        raise ValueError('Raster size must be a positive integer')
    uv=np.asarray(uv,float)
    if uv.ndim!=3 or uv.shape[1:]!=(3,2) or not np.isfinite(uv).all() or np.any(uv<0) or np.any(uv>1):
        raise ValueError('UV coordinates must be finite triangles inside [0,1]')
    owners=np.full((size,size),-1,np.int32); overlaps=set(); degenerate=[]
    for fi,t in enumerate(uv*size):
        ab,ac=t[1]-t[0],t[2]-t[0]; det=ab[0]*ac[1]-ab[1]*ac[0]
        if abs(det)<1e-10: degenerate.append(fi); continue
        lo=np.maximum(0,np.floor(t.min(0)-.5).astype(int)); hi=np.minimum(size-1,np.ceil(t.max(0)-.5).astype(int))
        if np.any(hi<lo): continue
        y,x=np.mgrid[lo[1]:hi[1]+1,lo[0]:hi[0]+1]; q=np.stack([x+.5,y+.5],-1)-t[0]
        u=(q[...,0]*ac[1]-q[...,1]*ac[0])/det; v=(ab[0]*q[...,1]-ab[1]*q[...,0])/det
        inside=(u>1e-7)&(v>1e-7)&(u+v<1-1e-7)
        block=owners[lo[1]:hi[1]+1,lo[0]:hi[0]+1]
        prior=block[inside & (block>=0)]
        if len(prior): overlaps.update(map(int,prior)); overlaps.add(fi)
        block[inside]=fi
    counts=np.bincount(owners[owners>=0],minlength=len(uv))
    return {'mappedTexels':int(np.count_nonzero(owners>=0)),'coverageFraction':float(np.mean(owners>=0)),
            'overlapFaces':sorted(overlaps),'degenerateUvFaces':degenerate,
            'unmappedUvFaces':np.flatnonzero(counts==0).tolist(),'mappedTexelsByFace':counts.tolist()},owners


def chart_ids(uv):
    """Chart connectivity requires an identical shared UV edge, not just proximity."""
    uv=np.asarray(uv); parent=list(range(len(uv))); edges={}
    def find(i):
        while parent[i]!=i: parent[i]=parent[parent[i]];i=parent[i]
        return i
    for fi,t in enumerate(uv):
        for a,b in ((0,1),(1,2),(2,0)):
            key=tuple(sorted((tuple(t[a]),tuple(t[b]))))
            edges.setdefault(key,[]).append(fi)
    for rows in edges.values():
        if len(rows)==2:
            a,b=map(find,rows);parent[max(a,b)]=min(a,b)
    _,labels=np.unique([find(i) for i in range(len(uv))],return_inverse=True)
    return labels


def gutter_audit(uv,size,owners=None):
    if owners is None: _,owners=raster_audit(uv,size)
    charts=chart_ids(uv); labels=np.full(owners.shape,-1,int); covered=owners>=0
    labels[covered]=charts[owners[covered]]
    # Distinct chart dilation collisions at radius 1/2 measure dangerous filtering gaps.
    collisions={}
    for radius in (1,2,4):
        pad=radius
        low_source=np.where(covered,labels,np.iinfo(np.int32).max)
        low_pad=np.pad(low_source,((pad,pad),(pad,pad)),constant_values=np.iinfo(np.int32).max)
        high_pad=np.pad(labels,((pad,pad),(pad,pad)),constant_values=-1)
        low=np.full(owners.shape,np.iinfo(np.int32).max,np.int32)
        high=np.full(owners.shape,-1,np.int32)
        for dy in range(-radius,radius+1):
            for dx in range(-radius,radius+1):
                y=pad+dy; x=pad+dx
                window=(slice(y,y+owners.shape[0]),slice(x,x+owners.shape[1]))
                np.minimum(low,low_pad[window],out=low)
                np.maximum(high,high_pad[window],out=high)
        collisions[str(radius)]=int(np.count_nonzero((low<high)&(high>=0)))
    return {'chartCount':int(charts.max(initial=-1)+1),'nearbyChartPixelsByRadius':collisions}


def audit_imported_uvs(value):
    """Validate imported UVs with the same gates as reviewed atlas reuse."""
    audits={}
    for size in (4096,2048,1024):
        audit,owners=raster_audit(value['uv'],size)
        require(not audit['overlapFaces'] and not audit['degenerateUvFaces'] and not audit['unmappedUvFaces'],'Imported atlas failed UV audit')
        gutters=gutter_audit(value['uv'],size,owners)
        require(audit['coverageFraction']>=.30,'Insufficient useful imported atlas coverage')
        if size==1024:require(not gutters['nearbyChartPixelsByRadius']['1'],'Imported atlas has unsafe 1K chart gutters')
        audits[str(size)]={'raster':audit,'gutters':gutters}
    require(int(chart_ids(value['uv']).max())+1<=max(256,len(value['faces'])*.3),'Severe imported chart fragmentation')
    return {'imported':True,'audits':audits,'visualReviewRequired':True}


def _pack(xatlas,vertices,indices,groups,padding=8):
    atlas=xatlas.Atlas()
    for face_ids in groups:
        atlas.add_mesh(vertices.astype(np.float32), indices[face_ids])
    charts=xatlas.ChartOptions(); charts.fix_winding=False; charts.max_iterations=1
    pack=xatlas.PackOptions();pack.resolution=2048;pack.padding=padding;pack.bilinear=True
    atlas.generate(chart_options=charts,pack_options=pack)
    if atlas.atlas_count!=1: raise ValueError('UV output must be one atlas')
    uv=np.empty((len(indices),3,2));count=0
    for i,face_ids in enumerate(groups):
        mapping,new_indices,new_uv=atlas[i]
        if not np.array_equal(vertices[mapping[new_indices]],vertices[indices[face_ids]]):
            raise ValueError('UV processing changed ordered geometry')
        uv[face_ids]=new_uv[new_indices];count+=atlas.get_mesh_chart_count(i)
    return uv,atlas,count


def _local_groups(indices,bad,max_fraction=.03):
    bad=set(map(int,bad)); edges={}
    for i,row in enumerate(indices):
        for a,b in ((0,1),(1,2),(2,0)):
            edges.setdefault(tuple(sorted((int(row[a]),int(row[b])))),[]).append(i)
    expanded=set(bad)
    for rows in edges.values():
        if bad.intersection(rows): expanded.update(rows)
    if len(expanded)>len(indices)*max_fraction:
        raise ValueError('Required UV repair exceeds bounded local scope')
    adjacent={i:set() for i in expanded}
    for rows in edges.values():
        for a in rows:
            if a in expanded: adjacent[a].update(b for b in rows if b in expanded and b!=a)
    groups=[];pending=set(expanded)
    while pending:
        stack=[pending.pop()];component=[]
        while stack:
            i=stack.pop();component.append(i)
            next_ids=adjacent[i]&pending;pending-=next_ids;stack.extend(next_ids)
        groups.append(np.asarray(sorted(component),int))
    healthy=np.asarray(sorted(set(range(len(indices)))-expanded),int)
    if healthy.size: groups.insert(0,healthy)
    if len(groups)>17: raise ValueError('Local UV repair would fragment too many charts')
    return groups


def unwrap(mesh,bindings,policy=None):
    begun=time.perf_counter();policy=policy or {}
    xatlas=library(bindings,'xatlas')
    preserve_seams=policy.get('preserveAuthoredSeams',True)
    if type(preserve_seams) is not bool:raise ValueError('explicit boolean authored-seam policy required')
    vertices,indices=physical_fans(mesh,preserve_authored_seams=preserve_seams)
    attempts=[];groups=[np.arange(len(indices))];new_uv=atlas=count=metrics=owners=gutters=None;chosen_padding=None
    # At most two packing upgrades (8 -> 16 -> 32). A single bounded local repair
    # may restart packing from the original padding after fixing overlap faces.
    for local_iteration in range(2):
        repair_needed=False
        for padding in (8,16,32):
            new_uv,atlas,count=_pack(xatlas,vertices,indices,groups,padding=padding)
            metrics={};owners={}
            for size in (2048,1024):metrics[str(size)],owners[size]=raster_audit(new_uv,size)
            bad=sorted({face for audit in metrics.values()
                        for key in ('overlapFaces','degenerateUvFaces','unmappedUvFaces') for face in audit[key]})
            gutters={str(size):gutter_audit(new_uv,size,owners[size]) for size in (2048,1024)}
            effective=[padding*1024/atlas.width,padding*1024/atlas.height]
            attempt={'padding':padding,'localRepair':bool(local_iteration),'groups':[len(x) for x in groups],
                     'badFaceCount':len(bad),'charts':count,'atlasDimensions':[atlas.width,atlas.height],
                     'effectivePadding1024':effective,
                     'nearbyChartPixelsByRadius1024':gutters['1024']['nearbyChartPixelsByRadius']}
            attempts.append(attempt)
            if bad:
                if local_iteration:
                    raise ValueError(f'UV still has {len(bad)} bad faces after bounded local repair')
                groups=_local_groups(indices,bad);repair_needed=True
                break
            if min(effective)<4 or gutters['1024']['nearbyChartPixelsByRadius']['1']:
                continue
            chosen_padding=padding
            break
        if chosen_padding is not None:
            break
        if repair_needed:
            continue
        raise ValueError('Could not meet the measured 1K UV gutter floor with padding <=32')
    if chosen_padding is None:
        raise ValueError('UV packing did not meet its measured geometry and gutter gates')
    if metrics['2048']['coverageFraction']<float(policy.get('minimumCoverage',.30)):raise ValueError('Insufficient useful UV coverage')
    if count>max(256,int(len(indices)*.3)):raise ValueError('Severe UV fragmentation')
    result=dict(mesh,uv=np.asarray(new_uv,np.float64),chart_ids=chart_ids(new_uv),uv_pending_unwrap=False)
    return result,{'charts':count,'atlasDimensions':[atlas.width,atlas.height],'pixelAudits':metrics,'gutters':gutters,
                   'geometryUnchanged':True,'preserveAuthoredSeams':preserve_seams,'elapsedSeconds':time.perf_counter()-begun,'attempts':attempts,
                   'chosenPadding':chosen_padding,
                   'effectivePadding2K':[chosen_padding*2048/atlas.width,chosen_padding*2048/atlas.height],
                   'effectivePadding1024':[chosen_padding*1024/atlas.width,chosen_padding*1024/atlas.height],
                   'visualReview':'required'}
