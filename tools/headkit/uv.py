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
    # Pieces of one chart touching at a corner are packed together and stay continuous, so they count as one.
    if charts is None:charts=chart_ids(uv,'vertex')
    from scipy.ndimage import distance_transform_edt
    nearest=owners[tuple(distance_transform_edt(owners<0,return_distances=False,return_indices=True))]
    failing=[]
    for fi in faces:
        points=np.vstack([uv[fi],uv[fi].mean(0)])*size;pixel=np.clip(np.floor(points).astype(int),0,size-1)
        if np.any(charts[nearest[pixel[:,1],pixel[:,0]]]!=charts[fi]):failing.append(int(fi))
    return {'size':size,'count':len(faces),'limit':limit,'failingFaces':failing,'passed':not failing}


def gutter_audit(uv,size,owners=None,charts=None):
    if owners is None: _,owners=raster_audit(uv,size)
    if charts is None:charts=chart_ids(uv,'vertex')
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
    declare a lower floor, at least 20%, only with a recorded review; the gutter floor itself never relaxes. Down to
    15% needs the review to record the user's approval (userApproved: race heads v1 dwarf-female-c, whose kept hanging
    bob fragments into ~2,000 charts that no chart option packs above 19%); the gutter floor still holds."""
    policy=policy or {};floor=policy.get('minimumCoverage',.30);review=policy.get('coverageReview')
    if type(floor) not in (int,float) or not .15<=floor<=1:raise ValueError('UV coverage floor must be 0.15..1')
    if floor<.30:
        require(isinstance(review,dict) and review.get('reviewed') is True and isinstance(review.get('notes'),str)
                and bool(review['notes'].strip()),'A UV coverage floor below 30% needs a recorded review')
        require(floor>=.20 or review.get('userApproved') is True,'A UV coverage floor below 20% needs the user\'s approval in its review')
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


PAGE=2048  # every re-pack lands on one square page of this many texels


def _pack_options(xatlas,padding,texels_per_unit=0.0,brute_force=False):
    """With density 0 xatlas estimates one and grows an unbounded atlas whose UVs are normalised to its used extents,
    so a 3:1 atlas stretches a square texture; only the charting pass, whose units are unknown, packs that way. An
    explicit density bounds the pack to one square PAGE (a chart that does not fit spills onto another page)."""
    pack=xatlas.PackOptions();pack.resolution=PAGE;pack.padding=padding;pack.bilinear=True;pack.bruteForce=brute_force
    pack.texels_per_unit=float(texels_per_unit)
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


def _inradius(q):
    """Inradius of a normalised UV triangle in 1K texels."""
    twice=abs((q[1,0]-q[0,0])*(q[2,1]-q[0,1])-(q[1,1]-q[0,1])*(q[2,0]-q[0,0]))
    perimeter=sum(np.linalg.norm(q[k]-q[(k+1)%3]) for k in range(3));return twice/perimeter*1024 if perimeter else 0


def _own_chart(corners,dims,density,index,longest=16):
    """Planar single-triangle chart in the base atlas units: it cannot overlap itself, is grown until its inradius
    is at least 1.5 texels at 1K so it owns texels at every audited resolution, and gets a unique origin so the
    packer cannot weld it to another chart. Growth is uniform only until the longest edge reaches `longest` 1K
    texels; past that a sliver is widened across its longest edge instead. Grown uniformly, a 3D sliver became a
    chart thousands of texels long (troll-male-02 face 8143: 7301 x 7 first-pack texels) that set the atlas width."""
    e1=corners[1]-corners[0];normal=np.cross(e1,corners[2]-corners[0]);e1=e1/np.linalg.norm(e1)
    e2=np.cross(normal/np.linalg.norm(normal),e1);q=(corners-corners[0])
    q=np.c_[q@e1/dims[0],q@e2/dims[1]]*density;inradius=_inradius(q)
    if inradius<1.5:
        edges=[np.linalg.norm(q[(k+1)%3]-q[k])*1024 for k in range(3)];k=int(np.argmax(edges))
        q=q*min(1.5/max(inradius,1e-6),max(1.0,longest/max(edges[k],1e-9)))
        start=q[k];along=(q[(k+1)%3]-start)/np.linalg.norm(q[(k+1)%3]-start);across=np.array([-along[1],along[0]])
        apex=(k+2)%3;height=(q[apex]-start)@across or 1e-9
        for _ in range(64):
            if _inradius(q)>=1.5:break
            height*=1.5/max(_inradius(q),1e-9)*1.001;q[apex]=start+((q[apex]-start)@along)*along+height*across
    return q+[3+.25*(index%64),3+.25*(index//64)]


def _repack(xatlas,base_uv,dims,density,corners,own,padding,scale):
    """Pack-only pass over the charted layout plus own charts (seconds, not minutes) onto one square PAGE, charts
    measured in first-pack texels and placed at `scale` page texels each. An unbounded re-pack let one extra own
    chart flip a near-square layout to 3:1, halving 1K density on one axis and failing new faces every round. A spill
    lowers the density 3% per pack, then the scale is bisected between the last spill and the first fit (to 0.5%) to
    recover coverage. Density never rises above the given scale; the fitted scale is returned for the next round."""
    layout=base_uv.copy();labels=chart_ids(base_uv).astype(np.int64);dims=np.asarray(dims,float)
    # Charts smaller than a few 1K texels have no texel of their own, so their padding colour comes from whichever
    # chart the packer puts next to them; grow them about their centroid before packing instead of chasing them.
    twice=np.abs((layout[:,1,0]-layout[:,0,0])*(layout[:,2,1]-layout[:,0,1])-(layout[:,1,1]-layout[:,0,1])*(layout[:,2,0]-layout[:,0,0]))
    area=np.bincount(labels,weights=twice/2*1024*1024,minlength=labels.max()+1)
    for chart in np.flatnonzero(area<6):
        faces=labels==chart;centre=layout[faces].reshape(-1,2).mean(0)
        layout[faces]=centre+(layout[faces]-centre)*np.sqrt(6/max(area[chart],1e-9))
    for face in own:labels[face]=-1-face
    def pack(scale):
        # Own charts are sized on the page they land on (1.5 1K texels of inradius there), then held in first-pack units.
        page=np.full(2,PAGE/scale)
        for face in own:layout[face]=_own_chart(corners[face],page,density,face)*page/dims
        keys=np.c_[np.repeat(labels,3),np.round(layout.reshape(-1,2),6)]
        _,index=np.unique(keys,axis=0,return_inverse=True);index=index.reshape(-1,3)
        points=np.zeros((index.max()+1,2),np.float32);points[index.reshape(-1)]=layout.reshape(-1,2)*dims
        atlas=xatlas.Atlas();atlas.add_uv_mesh(points,index.astype(np.uint32))
        atlas.generate(pack_options=_pack_options(xatlas,padding,scale))  # brute force packs tall atlases
        return (atlas,index) if atlas.atlas_count==1 else None
    fitted=spilled=None
    for _ in range(64):
        packed=pack(scale)
        if packed:fitted=(scale,packed)
        else:spilled=scale
        if fitted is None:scale*=.97
        elif spilled is None or spilled/fitted[0]<1.005:break
        else:scale=float(np.sqrt(spilled*fitted[0]))
    if fitted is None:raise ValueError('UV re-pack spilled onto more than one atlas page')
    scale,(atlas,index)=fitted
    mapping,new_indices,new_uv=atlas[0]
    if not np.array_equal(mapping[new_indices],index):raise ValueError('UV re-pack changed face order')
    return new_uv[new_indices].astype(np.float64),(atlas.width,atlas.height),atlas.chart_count,scale


def face_region(positions,faces):
    """Front face triangles in the glTF frame (+y up, +z front): centroid in the front 35% of the depth, normal facing front
    (z > .3) and below the top 20% of the height (the crown). Also returns the triangle areas."""
    corners=np.asarray(positions,float)[faces];n=np.cross(corners[:,1]-corners[:,0],corners[:,2]-corners[:,0])
    area=np.linalg.norm(n,axis=1)/2;normal=n/np.maximum(2*area[:,None],1e-12);centre=corners.mean(1)
    lo,hi=np.asarray(positions,float).min(0),np.asarray(positions,float).max(0)
    return (centre[:,2]>hi[2]-.35*(hi[2]-lo[2]))&(normal[:,2]>.3)&(centre[:,1]<lo[1]+.8*(hi[1]-lo[1])),area


def face_priority(xatlas,uv,positions,faces,ratio,padding):
    """Scale every chart about its centroid by the area-weighted sqrt(ratio) of its face triangles (1 elsewhere), then pack-only
    onto one square PAGE with the scale bisected to fill it, so the face gets `ratio` x the rest's texel density (step 1 of
    docs/heads/head-texture-quality-plan.md: 7.9 vs 9.1 texels/cm on a uniform unwrap; stock heads give the face ~2.8x)."""
    face,area=face_region(positions,faces);weight=np.where(face,np.sqrt(ratio),1.0)
    labels=chart_ids(uv,shared='vertex').astype(np.int64);layout=uv.copy()
    for chart in np.unique(labels):
        selected=labels==chart;w=np.average(weight[selected],weights=area[selected]+1e-12);centre=layout[selected].reshape(-1,2).mean(0)
        layout[selected]=centre+(layout[selected]-centre)*w
    keys=np.c_[np.repeat(labels,3),np.round(layout.reshape(-1,2),7)]
    _,index=np.unique(keys,axis=0,return_inverse=True);index=index.reshape(-1,3)
    points=np.zeros((index.max()+1,2),np.float32);points[index.reshape(-1)]=layout.reshape(-1,2)*PAGE
    def pack(scale):
        atlas=xatlas.Atlas();atlas.add_uv_mesh(points,index.astype(np.uint32));atlas.generate(pack_options=_pack_options(xatlas,padding,scale))
        return atlas if atlas.atlas_count==1 else None
    fitted=spilled=None;scale=.5
    for _ in range(40):
        atlas=pack(scale)
        if atlas:fitted=(scale,atlas);scale=scale*1.15 if spilled is None else float(np.sqrt(scale*spilled))
        else:spilled=scale;scale=scale*.87 if fitted is None else float(np.sqrt(fitted[0]*spilled))
        if fitted and spilled and spilled/fitted[0]<1.005:break
    if fitted is None:raise ValueError('Face-priority re-pack spilled onto more than one atlas page')
    scale,atlas=fitted;mapping,new_indices,new_uv=atlas[0]
    if not np.array_equal(mapping[new_indices],index):raise ValueError('Face-priority re-pack changed face order')
    new_uv=new_uv[new_indices].astype(np.float64)
    def density(values,selected):
        twice=np.abs((values[:,1,0]-values[:,0,0])*(values[:,2,1]-values[:,0,1])-(values[:,1,1]-values[:,0,1])*(values[:,2,0]-values[:,0,0]))
        return float(twice[selected].sum()/2/max(area[selected].sum(),1e-12))
    measured=density(new_uv,face)/max(density(new_uv,~face),1e-12) if face.any() and (~face).any() else None
    return new_uv,{'ratio':ratio,'faceTriangles':int(face.sum()),'packScale':scale,'charts':int(atlas.chart_count),
                   'measuredDensityRatio':measured}


def unwrap(mesh,bindings,policy=None):
    begun=time.perf_counter();policy=policy or {}
    maximum_groups=policy.get('maximumLocalGroups')
    if maximum_groups is not None:
        require(type(maximum_groups) is int and 2<=maximum_groups<=256,'Invalid local group limit')
    xatlas=library(bindings,'xatlas')
    preserve_seams=policy.get('preserveAuthoredSeams',True)
    if type(preserve_seams) is not bool:raise ValueError('explicit boolean authored-seam policy required')
    subtexel_fraction=policy.get('maximumSubtexelFraction',.005);floor,review=coverage_floor(policy)
    vertices,indices=physical_fans(mesh,preserve_authored_seams=preserve_seams);corners=np.asarray(vertices,float)[indices]
    charted=time.perf_counter();base,base_dims,density,count=_chart(xatlas,vertices,indices,policy);charted=time.perf_counter()-charted
    new_uv,dims,padding,own,attempts=base,base_dims,8,set(),[]
    # Re-packs start at the first pack's density on the square page; a spill only ever lowers it (see _repack).
    scale=PAGE/max(base_dims);packed=charted
    def fail(message):
        error=ValueError(message);error.attempts=attempts;return error
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
                         'atlasDimensions':list(dims),'effectivePadding1024':effective,'packSeconds':packed,
                         'pageTexelsPerFirstPackTexel':None if round_index==0 else scale,
                         'subtexel':{size:{k:v for k,v in s.items() if k!='failingFaces'} for size,s in subtexel.items()},
                         'nearbyChartPixelsByRadius1024':gutters['1024']['nearbyChartPixelsByRadius']})
        thin=min(effective)<4 or gutters['1024']['nearbyChartPixelsByRadius']['1']
        if not bad and not thin:break
        # The smallest padding that keeps 4 px at 1K on the re-pack page: more costs coverage, less fails the floor.
        needed=int(np.ceil(4.2*PAGE/1024))
        if bad:own|=set(map(int,bad));padding=max(padding,needed)
        elif min(effective)<4:padding=max(padding+1,needed)
        elif padding<32:padding=min(32,padding*2)
        else:raise fail('Could not meet the measured 1K UV gutter floor with padding <=32')
        if maximum_groups is not None:
            require(len(own)+1<=maximum_groups,'Local repair exceeds explicit group limit')
        packed=time.perf_counter()
        try:new_uv,dims,count,scale=_repack(xatlas,base,base_dims,density,corners,sorted(own),padding,scale)
        except ValueError as exc:raise fail(str(exc)) from exc
        packed=time.perf_counter()-packed
    else:raise fail(f"UV still has {f'{len(bad)} bad faces' if bad else 'thin 1K gutters'} after {len(attempts)-1} pack-only repair rounds")
    if metrics['2048']['coverageFraction']<floor:
        raise fail(f"Insufficient useful UV coverage ({metrics['2048']['coverageFraction']:.3f} at 2K, padding {padding})")
    if count>max(256,int(len(indices)*.3)):raise fail('Severe UV fragmentation')
    ratio=policy.get('faceDensity',1);face=None
    require(type(ratio) in (int,float) and 1<=ratio<=4,'faceDensity must be a number from 1 to 4')
    if ratio!=1:
        # Face priority after the repairs: a pack-only pass over the audited layout, then every audit again on the result.
        new_uv,face=face_priority(xatlas,new_uv,mesh['positions'],mesh['faces'],float(ratio),padding);charts=chart_ids(new_uv,'vertex')
        for size in (4096,2048,1024):
            metrics[str(size)],owners[size]=raster_audit(new_uv,size)
            subtexel[str(size)]=subtexel_audit(new_uv,size,metrics[str(size)],owners[size],0.0 if size==4096 else subtexel_fraction,charts)
            if metrics[str(size)]['overlapFaces'] or metrics[str(size)]['degenerateUvFaces'] or subtexel[str(size)]['failingFaces']:
                raise fail(f'Face-priority layout fails the {size} UV audit')
        gutters={str(size):gutter_audit(new_uv,size,owners[size],charts) for size in (2048,1024)};dims=(PAGE,PAGE);count=face['charts']
        if gutters['1024']['nearbyChartPixelsByRadius']['1']:raise fail('Face-priority layout has thin 1K gutters')
        if metrics['2048']['coverageFraction']<floor:raise fail(f"Insufficient useful UV coverage after face priority ({metrics['2048']['coverageFraction']:.3f} at 2K)")
    result=dict(mesh,uv=np.asarray(new_uv,np.float64),chart_ids=chart_ids(new_uv),uv_pending_unwrap=False)
    return result,{**({'facePriority':face} if face else {}),'charts':count,'atlasDimensions':list(dims),'pixelAudits':metrics,'gutters':gutters,
                   'geometryUnchanged':True,'preserveAuthoredSeams':preserve_seams,'elapsedSeconds':time.perf_counter()-begun,
                   'chartingSeconds':charted,'attempts':attempts,'ownCharts':sorted(own),
                   'chosenPadding':padding,'maximumSubtexelFraction':subtexel_fraction,'coverageFloor':floor,'coverageReview':review,
                   'subtexel':{size:{k:v for k,v in s.items() if k!='failingFaces'} for size,s in subtexel.items()},
                   'effectivePadding2K':[padding*2048/dims[0],padding*2048/dims[1]],
                   'effectivePadding1024':[padding*1024/dims[0],padding*1024/dims[1]],
                   'visualReview':'required'}


def _pack(xatlas,vertices,indices,groups,padding=8):
    atlas=xatlas.Atlas()
    remaps=[]
    for face_ids in groups:
        used,inverse=np.unique(indices[face_ids],return_inverse=True)
        atlas.add_mesh(vertices[used].astype(np.float32),inverse.reshape(-1,3).astype(np.uint32))
        remaps.append(used)
    charts=xatlas.ChartOptions(); charts.fix_winding=False; charts.max_iterations=1
    pack=xatlas.PackOptions();pack.resolution=2048;pack.padding=padding;pack.bilinear=True
    atlas.generate(chart_options=charts,pack_options=pack)
    if atlas.atlas_count!=1: raise ValueError('UV output must be one atlas')
    uv=np.empty((len(indices),3,2));count=0
    for i,face_ids in enumerate(groups):
        mapping,new_indices,new_uv=atlas[i]
        if not np.array_equal(vertices[remaps[i][mapping[new_indices]]],vertices[indices[face_ids]]):
            raise ValueError('UV processing changed ordered geometry')
        uv[face_ids]=new_uv[new_indices];count+=atlas.get_mesh_chart_count(i)
    return uv,atlas,count
