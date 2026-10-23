"""Connected-chart unwrap: one charting pass, pack-only repair rounds and measured atlas coverage."""
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


def chart_ids(uv,shared='edge'):
    """Chart connectivity requires an identical shared UV edge, not just proximity. With shared='vertex', faces
    meeting at an identical UV vertex also join, which is how xatlas groups a re-packed UV mesh: pieces of one
    original chart left touching at a corner are packed together and stay continuous."""
    uv=np.asarray(uv); parent=list(range(len(uv))); edges={}
    def find(i):
        while parent[i]!=i: parent[i]=parent[parent[i]];i=parent[i]
        return i
    for fi,t in enumerate(uv):
        for a,b in ((0,1),(1,2),(2,0)):
            key=tuple(sorted((tuple(t[a]),tuple(t[b]))))
            edges.setdefault(key,[]).append(fi)
    if shared=='vertex':
        corners={}
        for fi,t in enumerate(uv):
            for point in t:corners.setdefault(tuple(point),[]).append(fi)
        edges=corners
    elif shared!='edge':raise ValueError('Chart connectivity is by edge or vertex')
    for rows in edges.values():
        if shared=='vertex' or len(rows)==2:
            first=find(rows[0])
            for other in rows[1:]:
                a,b=first,find(other);first=min(a,b);parent[max(a,b)]=first
    _,labels=np.unique([find(i) for i in range(len(uv))],return_inverse=True)
    return labels


def subtexel_audit(uv,size,report,owners,max_fraction=0.0,charts=None):
    """Measured allowance for faces that own no texel at a derived resolution. Such a face passes only if,
    under its corners and centroid, the nearest mapped texel (the colour bake padding copies there) belongs
    to its own chart, and only while the count stays within the declared fraction of all faces."""
    uv=np.asarray(uv,float);faces=list(report['unmappedUvFaces'])
    if type(max_fraction) not in (int,float) or not 0<=max_fraction<=.02:raise ValueError('Sub-texel allowance must be 0..2% of faces')
    limit=int(np.ceil(max_fraction*len(uv)))
    if not faces:return {'size':size,'count':0,'limit':limit,'failingFaces':[],'passed':True}
    # Over the bound, or without an owner raster to prove the padding source, every such face fails.
    if len(faces)>limit or owners is None or not np.any(np.asarray(owners)>=0):
        return {'size':size,'count':len(faces),'limit':limit,'failingFaces':[int(f) for f in faces],'passed':False}
    if charts is None:charts=chart_ids(uv)
    from scipy.ndimage import distance_transform_edt
    nearest=owners[tuple(distance_transform_edt(owners<0,return_distances=False,return_indices=True))]
    failing=[]
    for fi in faces:
        points=np.vstack([uv[fi],uv[fi].mean(0)])*size;pixel=np.clip(np.floor(points).astype(int),0,size-1)
        if np.any(charts[nearest[pixel[:,1],pixel[:,0]]]!=charts[fi]):failing.append(int(fi))
    return {'size':size,'count':len(faces),'limit':limit,'failingFaces':failing,'passed':not failing}


def gutter_audit(uv,size,owners=None,charts=None):
    if owners is None: _,owners=raster_audit(uv,size)
    if charts is None:charts=chart_ids(uv)
    labels=np.full(owners.shape,-1,int); covered=owners>=0
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


def coverage_floor(policy=None):
    """2K coverage floor: 30% by default. Dense heads (many small charts, each needing the 4 px gutter at 1K) may
    declare a lower floor, at least 20%, only with a recorded review; the gutter floor itself never relaxes."""
    policy=policy or {};floor=policy.get('minimumCoverage',.30);review=policy.get('coverageReview')
    if type(floor) not in (int,float) or not .20<=floor<=1:raise ValueError('UV coverage floor must be 0.20..1')
    if floor<.30:
        require(isinstance(review,dict) and review.get('reviewed') is True and isinstance(review.get('notes'),str)
                and bool(review['notes'].strip()),'A UV coverage floor below 30% needs a recorded review')
        return float(floor),review
    return float(floor),None


def audit_imported_uvs(value,max_subtexel_fraction=.005,uv_policy=None):
    """Validate imported UVs with the same gates as reviewed atlas reuse."""
    audits={};floor,review=coverage_floor(uv_policy)
    for size in (4096,2048,1024):
        audit,owners=raster_audit(value['uv'],size)
        subtexel=subtexel_audit(value['uv'],size,audit,owners,0.0 if size==4096 else max_subtexel_fraction)
        require(not audit['overlapFaces'] and not audit['degenerateUvFaces'] and subtexel['passed'],'Imported atlas failed UV audit')
        audit['subtexel']={k:v for k,v in subtexel.items() if k!='failingFaces'}
        gutters=gutter_audit(value['uv'],size,owners)
        require(audit['coverageFraction']>=floor,'Insufficient useful imported atlas coverage')
        if size==1024:require(not gutters['nearbyChartPixelsByRadius']['1'],'Imported atlas has unsafe 1K chart gutters')
        audits[str(size)]={'raster':audit,'gutters':gutters}
    require(int(chart_ids(value['uv']).max())+1<=max(256,len(value['faces'])*.3),'Severe imported chart fragmentation')
    return {'imported':True,'audits':audits,'coverageFloor':floor,'coverageReview':review,'visualReviewRequired':True}


def _pack_options(xatlas,padding,brute_force=False):
    pack=xatlas.PackOptions();pack.resolution=2048;pack.padding=padding;pack.bilinear=True;pack.bruteForce=brute_force
    return pack


def _chart(xatlas,vertices,indices,policy):
    """The one expensive xatlas pass: chart and pack the whole mesh. Retries only re-pack (see _repack)."""
    atlas=xatlas.Atlas();atlas.add_mesh(vertices.astype(np.float32),indices)
    charts=xatlas.ChartOptions();charts.fix_winding=False
    for key,value in {'max_iterations':1,**policy.get('chartOptions',{})}.items():setattr(charts,key,value)
    atlas.generate(chart_options=charts,pack_options=_pack_options(xatlas,8))
    if atlas.atlas_count!=1:raise ValueError('UV output must be one atlas')
    mapping,new_indices,new_uv=atlas[0]
    if not np.array_equal(vertices[mapping[new_indices]],vertices[indices]):raise ValueError('UV processing changed ordered geometry')
    return new_uv[new_indices].astype(np.float64),(atlas.width,atlas.height),atlas.texels_per_unit,atlas.chart_count


def _own_chart(corners,dims,density,index):
    """Planar single-triangle chart in the base atlas units: it cannot overlap itself, is grown until its inradius
    is at least 1.5 texels at 1K so it owns texels at every audited resolution, and gets a unique origin so the
    packer cannot weld it to another chart."""
    e1=corners[1]-corners[0];normal=np.cross(e1,corners[2]-corners[0]);e1=e1/np.linalg.norm(e1)
    e2=np.cross(normal/np.linalg.norm(normal),e1);q=(corners-corners[0])
    q=np.c_[q@e1/dims[0],q@e2/dims[1]]*density
    twice=abs((q[1,0]-q[0,0])*(q[2,1]-q[0,1])-(q[1,1]-q[0,1])*(q[2,0]-q[0,0]))
    perimeter=sum(np.linalg.norm(q[k]-q[(k+1)%3]) for k in range(3));inradius=twice/perimeter*1024 if perimeter else 0
    if inradius<1.5:q=q*(1.5/max(inradius,1e-6))
    return q+[3+.25*(index%64),3+.25*(index//64)]


def _repack(xatlas,base_uv,dims,density,corners,own,padding):
    """Pack-only pass over the charted layout plus own charts (seconds, not minutes)."""
    layout=base_uv.copy();labels=chart_ids(base_uv).astype(np.int64)
    # Charts smaller than a few 1K texels have no texel of their own, so their padding colour comes from whichever
    # chart the packer puts next to them; grow them about their centroid before packing instead of chasing them.
    twice=np.abs((layout[:,1,0]-layout[:,0,0])*(layout[:,2,1]-layout[:,0,1])-(layout[:,1,1]-layout[:,0,1])*(layout[:,2,0]-layout[:,0,0]))
    area=np.bincount(labels,weights=twice/2*1024*1024,minlength=labels.max()+1)
    for chart in np.flatnonzero(area<6):
        faces=labels==chart;centre=layout[faces].reshape(-1,2).mean(0)
        layout[faces]=centre+(layout[faces]-centre)*np.sqrt(6/max(area[chart],1e-9))
    for face in own:layout[face]=_own_chart(corners[face],dims,density,face);labels[face]=-1-face
    keys=np.c_[np.repeat(labels,3),np.round(layout.reshape(-1,2),6)]
    _,index=np.unique(keys,axis=0,return_inverse=True);index=index.reshape(-1)
    points=np.zeros((index.max()+1,2),np.float32);points[index]=layout.reshape(-1,2)
    atlas=xatlas.Atlas();atlas.add_uv_mesh(points,index.reshape(-1,3).astype(np.uint32))
    atlas.generate(pack_options=_pack_options(xatlas,padding))  # brute force packs tall atlases that stretch a square texture
    if atlas.atlas_count!=1:raise ValueError('UV re-pack spilled onto more than one atlas page')
    mapping,new_indices,new_uv=atlas[0]
    if not np.array_equal(mapping[new_indices],index.reshape(-1,3)):raise ValueError('UV re-pack changed face order')
    return new_uv[new_indices].astype(np.float64),(atlas.width,atlas.height),atlas.chart_count


def unwrap(mesh,bindings,policy=None):
    begun=time.perf_counter();policy=policy or {}
    xatlas=library(bindings,'xatlas')
    preserve_seams=policy.get('preserveAuthoredSeams',True)
    if type(preserve_seams) is not bool:raise ValueError('explicit boolean authored-seam policy required')
    subtexel_fraction=policy.get('maximumSubtexelFraction',.005);floor,review=coverage_floor(policy)
    vertices,indices=physical_fans(mesh,preserve_authored_seams=preserve_seams);corners=np.asarray(vertices,float)[indices]
    charted=time.perf_counter();base,base_dims,density,count=_chart(xatlas,vertices,indices,policy);charted=time.perf_counter()-charted
    new_uv,dims,padding,own,attempts=base,base_dims,8,set(),[]
    # Faces that overlap, degenerate or fail the sub-texel rule become own charts; thin gutters raise the padding.
    # Every retry is pack-only, so the bound is on rounds, not on how many repaired faces there are.
    for round_index in range(int(policy.get('maximumRepackRounds',10))+1):
        # Re-packed pieces of one original chart that touch at a corner are packed together, so audits label
        # charts by shared UV vertices, as xatlas does.
        metrics={};owners={};subtexel={};charts=chart_ids(new_uv,'vertex');bad=set()
        for size in (4096,2048,1024):
            metrics[str(size)],owners[size]=raster_audit(new_uv,size)
            subtexel[str(size)]=subtexel_audit(new_uv,size,metrics[str(size)],owners[size],0.0 if size==4096 else subtexel_fraction,charts)
            bad.update(metrics[str(size)]['overlapFaces']);bad.update(metrics[str(size)]['degenerateUvFaces']);bad.update(subtexel[str(size)]['failingFaces'])
        gutters={str(size):gutter_audit(new_uv,size,owners[size],charts) for size in (2048,1024)}
        effective=[padding*1024/dims[0],padding*1024/dims[1]]
        attempts.append({'round':round_index,'padding':padding,'ownCharts':len(own),'badFaceCount':len(bad),'charts':count,
                         'atlasDimensions':list(dims),'effectivePadding1024':effective,
                         'subtexel':{size:{k:v for k,v in s.items() if k!='failingFaces'} for size,s in subtexel.items()},
                         'nearbyChartPixelsByRadius1024':gutters['1024']['nearbyChartPixelsByRadius']})
        thin=min(effective)<4 or gutters['1024']['nearbyChartPixelsByRadius']['1']
        if not bad and not thin:break
        # The smallest padding that keeps 4 px at 1K for this atlas size: more costs coverage, less fails the floor.
        needed=int(np.ceil(4.2*max(dims)/1024))
        if bad:own|=set(map(int,bad));padding=max(padding,needed)
        elif min(effective)<4:padding=max(padding+1,needed)
        elif padding<32:padding=min(32,padding*2)
        else:raise ValueError('Could not meet the measured 1K UV gutter floor with padding <=32')
        new_uv,dims,count=_repack(xatlas,base,base_dims,density,corners,sorted(own),padding)
    else:
        reason=f'{len(bad)} bad faces' if bad else 'thin 1K gutters'
        error=ValueError(f'UV still has {reason} after {len(attempts)-1} pack-only repair rounds')
        error.attempts=attempts;raise error
    if metrics['2048']['coverageFraction']<floor:
        error=ValueError(f"Insufficient useful UV coverage ({metrics['2048']['coverageFraction']:.3f} at 2K, padding {padding})")
        error.attempts=attempts;raise error
    if count>max(256,int(len(indices)*.3)):raise ValueError('Severe UV fragmentation')
    result=dict(mesh,uv=np.asarray(new_uv,np.float64),chart_ids=chart_ids(new_uv),uv_pending_unwrap=False)
    return result,{'charts':count,'atlasDimensions':list(dims),'pixelAudits':metrics,'gutters':gutters,
                   'geometryUnchanged':True,'preserveAuthoredSeams':preserve_seams,'elapsedSeconds':time.perf_counter()-begun,
                   'chartingSeconds':charted,'attempts':attempts,'ownCharts':sorted(own),
                   'chosenPadding':padding,'maximumSubtexelFraction':subtexel_fraction,'coverageFloor':floor,'coverageReview':review,
                   'subtexel':{size:{k:v for k,v in s.items() if k!='failingFaces'} for size,s in subtexel.items()},
                   'effectivePadding2K':[padding*2048/dims[0],padding*2048/dims[1]],
                   'effectivePadding1024':[padding*1024/dims[0],padding*1024/dims[1]],
                   'visualReview':'required'}
