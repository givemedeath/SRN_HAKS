"""Configured texture repairs: 3D-selected recolors, region fills, rule-driven ownership and per-channel colour adjustment.
Selections are manifest data (bbox-relative regions, colour predicates, priority order); nothing here is head-specific."""
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import distance_transform_edt, binary_closing, binary_fill_holes
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from .common import require, pin, write
from .gltf import mesh
from .uv import raster_audit
from .rays import EmbreeScene, outer_faces
from .predicates import COMPARE, Values, when  # noqa: F401 - re-exported for texture rules

PREVIEW=np.array([[150,120,100],[30,30,30],[80,160,255],[60,90,140],[120,60,160],[160,90,200],[110,80,40],[150,110,60],[240,220,150],[230,30,40]],np.uint8)


def colour_values(rgb, extra=None):
    c=lambda i:rgb[...,i].astype(np.int16)
    factories={'r':lambda:c(0),'g':lambda:c(1),'b':lambda:c(2),'lum':lambda:rgb.sum(-1,dtype=np.int32)/3,
               'sat':lambda:rgb.max(-1).astype(np.int16)-rgb.min(-1),'red':lambda:c(0)-np.maximum(c(1),c(2)),'rb':lambda:c(0)-c(2),'gb':lambda:c(1)-c(2)}
    factories.update(extra or {});return Values(factories)


def face_mask(uv, selected, size):
    image=Image.new('L',(size,size));draw=ImageDraw.Draw(image)
    for face in np.flatnonzero(selected):draw.polygon([(u*size,v*size) for u,v in uv[face]],fill=255)
    return np.asarray(image)>0


def adjacency(positions, faces):
    """Edge-sharing faces after welding by position: UV seams split vertices but do not split the surface."""
    _,welded=np.unique(np.round(positions,6),axis=0,return_inverse=True);corners=welded.reshape(-1)[faces]
    edges=np.sort(np.stack([corners[:,[0,1]],corners[:,[1,2]],corners[:,[2,0]]],1).reshape(-1,2),1)
    _,edge=np.unique(edges,axis=0,return_inverse=True);owner=np.repeat(np.arange(len(faces)),3)
    incidence=coo_matrix((np.ones(len(owner),np.int32),(edge.reshape(-1),owner)),shape=(edge.max()+1,len(faces))).tocsr()
    result=(incidence.T@incidence).tolil();result.setdiag(0);result=result.tocsr();result.eliminate_zeros();return result


def frame(value):
    positions,faces=value['positions'],value['faces'];lo,hi=positions.min(0),positions.max(0)
    return positions[faces].mean(1),lo,hi


def crest_faces(value, rgb, op):
    """Raised midline strands above a per-slab skull envelope, grown through light-gray untextured neighbours.
    Head frame: x lateral, y up, z front; angles are about a pivot at pivotHeight of the bbox, 0 = straight back."""
    centre,lo,hi=frame(value);uv=np.asarray(value['uv']);size=len(rgb);width,height=hi[0]-lo[0],hi[1]-lo[1]
    mid=(lo[0]+hi[0])/2;lateral=np.abs(centre[:,0]-mid)
    dy=centre[:,1]-(lo[1]+op['pivotHeight']*height);dz=centre[:,2]-(lo[2]+hi[2])/2
    radius,angle=np.hypot(dy,dz),np.degrees(np.arctan2(dy,-dz))  # 0 = straight back, 90 = up
    low,high=op['angleRange'];upper=(lateral<op['midlineHalfWidth']*width)&(angle>low)&(angle<high)
    slab=np.floor((centre[:,0]-lo[0])/(op['slabWidth']*width)).astype(int)
    _,cell=np.unique(np.c_[np.floor(angle/op['angleBinDegrees']).astype(int),slab],axis=0,return_inverse=True);cell=cell.reshape(-1)
    envelope=np.full(cell.max()+1,np.inf);np.minimum.at(envelope,cell[upper],radius[upper]);skull=envelope[cell]
    band=upper&(radius>skull+op['envelopeClearance']*height)
    grow=op.get('grow',{});grown=0
    if grow.get('rounds',0):
        pixel=(uv.mean(1)*size).astype(int).clip(0,size-1);colour=rgb[pixel[:,1],pixel[:,0]].astype(float)
        gray=(colour.mean(1)>grow['grayMinimumLuminance'])&(colour.max(1)-colour.min(1)<grow['grayMaximumSpread'])
        eligible=gray&(lateral<grow['halfWidth']*width)&(radius>skull-grow['skullTolerance']*height);neighbours=adjacency(value['positions'],value['faces'])
        for _ in range(grow['rounds']):
            add=eligible&~band&(neighbours@band.astype(np.int32)>0)
            if not add.any():break
            band|=add;grown+=int(add.sum())
    stripe=band&(lateral<op['stripeHalfWidth']*width) if 'stripeHalfWidth' in op else np.zeros_like(band)
    return band,stripe,grown


def crest(value, rgb, op, report):
    """Paint the crest faces' untextured texels (not already dark or red) with grain; the central stripe separately."""
    band,stripe,grown=crest_faces(value,rgb,op);uv=np.asarray(value['uv']);size=len(rgb)
    masks={op['name']:face_mask(uv,band,size)};masks[op['name']+'-stripe']=face_mask(uv,stripe,size)
    rgbf=rgb.astype(float);lum=rgbf.mean(2);keep=op.get('preserve',{})
    untextured=~((lum<keep.get('darkBelow',-1))|((rgbf[...,0]-rgbf[...,1:].max(-1))>keep.get('redAbove',np.inf)))
    grain=np.random.default_rng(op.get('grainSeed',0)).normal(0,op.get('grainSigma',0),rgb.shape[:2])
    painted={}
    for name,colour in ((op['name'],op['color']),(op['name']+'-stripe',op.get('stripeColor'))):
        if colour is None:continue
        selected=masks[name]&untextured;rgb[selected]=np.clip(np.asarray(colour,float)+grain[selected][:,None],0,255)
        painted[name]=int(selected.sum())
    report.update(faces=int(band.sum()),grownFaces=grown,stripeFaces=int(stripe.sum()),paintedTexels=painted)
    return masks


def face_values(value, rgb, seal_start=None):
    """Face conditions: bbox-relative centroid x/y/z, face index, the neck seal and the colour at the face's UV centroid."""
    centre,lo,hi=frame(value);rel=(centre-lo)/(hi-lo);uv=np.asarray(value['uv'])
    pixel=(uv.mean(1)*len(rgb)).astype(int).clip(0,len(rgb)-1)
    def seal():
        require(type(seal_start) is int and 0<seal_start<len(rel),'No neck seal recorded for this mesh')
        return (np.arange(len(rel))>=seal_start).astype(float)
    return colour_values(rgb[pixel[:,1],pixel[:,0]],{'x':lambda:rel[:,0],'y':lambda:rel[:,1],'z':lambda:rel[:,2],'index':lambda:np.arange(len(rel)),'seal':seal})


def fill(value, rgb, op, report, texels, regions, seal_start=None):
    """Paint selected faces flat over their own texels and the padding nearest to them; the colour is literal or the
    median of a mapped texel region outside those faces."""
    selected=when(op['faces'],face_values(value,rgb,seal_start),regions);require(selected.any(),'Fill selects no faces: '+op['name'])
    values=texels();mask=selected[values['nearest']];colour=op['color']
    if isinstance(colour,dict):
        sample=when(colour['median'],values,regions)&values['mapped']&~mask
        require(sample.any(),'Empty median sample: '+op['name']);colour=np.rint(np.median(rgb[sample],axis=0)).astype(int).tolist()
        report['medianSamples']=int(sample.sum())
    require(len(colour)==3 and all(type(c) is int and 0<=c<=255 for c in colour),'Fill colour must be three bytes')
    rgb[mask]=colour;report.update(faces=int(selected.sum()),color=colour,paintedTexels=int(mask.sum()))
    return {op['name']:mask}


# Protrusions (RUNBOOK 163): ball radius, clearance and growth in head heights; grid voxels across the bbox's longest side.
PROTRUSION={'ball':.08,'clearance':.01,'bridge':2,'grow':2,'voxels':128}
PROTRUSION_RANGES={'ball':(.02,.25),'clearance':(.002,.05),'bridge':(0,6),'grow':(0,8),'voxels':(32,256)}
GROW_FLOOR=.4    # growth toward the junction only through faces still this x the clearance outside the opened head


def solid_gap(embree, positions, faces, outer, normal, centre, lo, hi, settings):
    """Each face centroid's distance (head heights) outside the head solid opened with a ball of settings['ball']: thin parts
    (horns, ears, tusks) drop out of the opening, the skull stays. A voxel is inside when at least three of its six axis rays
    first meet an outer face from behind (the shell's cavity counts as inside; a ray out through the neck opening misses).
    Distances come in whole voxel steps, so the clearance may not be finer than one step."""
    height=hi[1]-lo[1];step=(hi-lo).max()/settings['voxels'];radius=max(1,int(round(settings['ball']*height/step)));pad=radius+2
    require(settings['clearance']>=step/height,f"Protrusion clearance {settings['clearance']} is finer than the voxel step {step/height:.4f} head heights; raise voxels")
    shape=np.ceil((hi-lo)/step).astype(int)+2*pad;origin=lo-pad*step;centres=[origin[a]+(np.arange(shape[a])+.5)*step for a in range(3)]
    # Only voxels inside the bbox: one outside it meets the head along one axis at most, so it never reaches three votes.
    box=tuple(slice(*np.flatnonzero((t>=lo[a])&(t<=hi[a]))[[0,-1]]+[0,1]) for a,t in enumerate(centres))
    grid=np.stack(np.meshgrid(*[t[b] for t,b in zip(centres,box)],indexing='ij'),-1).reshape(-1,3)
    votes=np.zeros(len(grid),np.int8);facing=normal[outer];scene=EmbreeScene(embree,positions.astype(np.float32),faces[outer].astype(np.uint32))
    try:
        for axis in np.r_[np.eye(3),-np.eye(3)]:
            for start in range(0,len(grid),1<<20):
                _,ids,_=scene.query(grid[start:start+(1<<20)],axis);votes[start:start+(1<<20)]+=(ids>=0)&(facing[np.maximum(ids,0)]@axis>0)
    finally:scene.close()
    inside=np.zeros(shape,bool);inside[box]=(votes>=3).reshape([b.stop-b.start for b in box])
    solid=binary_fill_holes(binary_closing(inside,iterations=2))   # seal stripes from misread outer faces
    # Opening with a ball by distance transforms: the same voxels as binary_opening with a ball structure, in seconds at any radius.
    eroded=distance_transform_edt(solid)>radius;require(eroded.any(),'Protrusion ball opens the whole head away; lower ball')
    opened=distance_transform_edt(~eroded)<=radius
    index=np.clip(((centre-origin)/step).astype(int),0,shape-1)
    return distance_transform_edt(~opened)[tuple(index.T)]*step/height,{'voxels':shape.tolist(),'solidVoxels':int(solid.sum()),'openedVoxels':int(opened.sum())}


def protrusion_faces(value, rgb, op, regions, embree, seal_start=None):
    """Thin parts standing out of the head (horns): outer faces more than `clearance` outside the ball-opened solid, the
    connected part holding each seed's outermost such face, opened by `bridge` face rings (a datajack plate beside a horn base
    joined troll-female-a's horn to its brows and nose), then up to `grow` rings toward the junction."""
    settings=dict(PROTRUSION,**{k:op[k] for k in PROTRUSION if k in op})
    require(set(op)<={'op','name','seeds',*PROTRUSION} and all(type(settings[k]) in ((int,) if type(PROTRUSION[k]) is int else (int,float))
            and PROTRUSION_RANGES[k][0]<=settings[k]<=PROTRUSION_RANGES[k][1] for k in PROTRUSION),'Protrusion settings out of range: '+op['name'])
    require(isinstance(op.get('seeds'),list) and op['seeds'],'Protrusion needs seed face conditions: '+op['name'])
    require(embree is not None,'Protrusion needs the bound Embree runtime')
    positions=value['positions'].astype(float);faces=value['faces'];centre,lo,hi=frame(value);height=hi[1]-lo[1]
    outer,normal=outer_faces(embree,positions,faces,height);gap,report=solid_gap(embree,positions,faces,outer,normal,centre,lo,hi,settings)
    up=outer&(gap>settings['clearance']);neighbours=adjacency(value['positions'],faces)
    _,part=connected_components(neighbours[up][:,up],directed=False);component=np.full(len(faces),-1);component[up]=part
    values=face_values(value,rgb,seal_start);middle=(lo+hi)/2;selected=np.zeros(len(faces),bool);tips=[];anchors=[]
    for number,seed in enumerate(op['seeds']):
        candidates=when(seed,values,regions)&up
        require(candidates.any(),f"Protrusion seed {number} of {op['name']} meets no face standing out of the head")
        tip=np.flatnonzero(candidates)[np.argmax(np.linalg.norm(centre[candidates]-middle,axis=1))];region=component==component[tip];core=region.copy()
        for _ in range(settings['bridge']):core&=~(neighbours@(~core).astype(np.int32)>0)
        require(not settings['bridge'] or core.any(),f"Protrusion seed {number} of {op['name']}: the part is thinner than {settings['bridge']} bridge rings")
        if settings['bridge']:
            # The opened piece holding the tip, or the one nearest it when the tip sits within the bridge rings of the edge.
            anchor=tip if core[tip] else np.flatnonzero(core)[np.argmin(np.linalg.norm(centre[core]-centre[tip],axis=1))]
            _,piece=connected_components(neighbours[core][:,core],directed=False);pieces=np.full(len(faces),-1);pieces[core]=piece;kept=pieces==pieces[anchor]
            for _ in range(settings['bridge']):kept|=region&(neighbours@kept.astype(np.int32)>0)
            region=kept;anchors.append(int(anchor))
        selected|=region;tips.append(int(tip))
    floor=outer&(gap>GROW_FLOOR*settings['clearance']);grown=0
    for _ in range(settings['grow']):
        add=floor&~selected&(neighbours@selected.astype(np.int32)>0)
        if not add.any():break
        selected|=add;grown+=int(add.sum())
    report.update(settings=settings,outerFaces=int(outer.sum()),standingOut=int(up.sum()),tips=tips,faces=int(selected.sum()),grownFaces=grown)
    if anchors!=tips[:len(anchors)]:report['bridgeAnchors']=anchors   # a tip within the bridge rings of its part's edge
    return selected,report


def texel_values(value, rgb, owners, extra=None):
    mapped=owners>=0;centre,lo,hi=frame(value);rel=(centre-lo)/(hi-lo)
    def axis(i):
        result=np.full(owners.shape,-1.0);result[mapped]=rel[owners[mapped],i];return result
    factories={'x':lambda:axis(0),'y':lambda:axis(1),'z':lambda:axis(2),'mapped':lambda:mapped,'face':lambda:owners}
    factories.update(extra or {});return colour_values(rgb,factories)


def texel_source(value, rgb):
    """Texel quantities of the current (mutated) colour map; the face raster and nearest-owner map are built once."""
    cache={}
    def texels():
        if 'owners' not in cache:
            owners=cache['owners']=raster_audit(value['uv'],len(rgb))[1];require((owners>=0).any(),'No mapped texture samples')
            cache['nearest']=owners[tuple(distance_transform_edt(owners<0,return_distances=False,return_indices=True))]
        return texel_values(value,rgb,cache['owners'],{'nearest':lambda:cache['nearest']})
    return texels


def heal(value, rgb, op, report, texels, regions):
    """Replace a measured pigment artifact with colors from a nearby intact surface."""
    from scipy.spatial import cKDTree
    values = texels()
    mapped = values['mapped']
    target = mapped & when(op['target'],values,regions)
    donors = mapped & ~target & when(op['donor'],values,regions)
    count = int(target.sum())
    require(0 < count <= mapped.sum()*.03 and 4 <= donors.sum() <= mapped.sum()*.05,
            'A local heal needs small measured target and donor regions')
    offset = np.asarray(op['offset'],float)
    require(offset.shape==(3,) and np.isfinite(offset).all() and np.linalg.norm(offset)<=.15,
            'Heal offset must be a local normalized XYZ displacement')
    lo = value['positions'].min(0)
    span = np.ptp(value['positions'],axis=0)
    def points(mask):
        y,x = np.nonzero(mask)
        faces = values['face'][y,x]
        triangles = value['uv'][faces]*len(rgb)
        ab,ac = triangles[:,1]-triangles[:,0],triangles[:,2]-triangles[:,0]
        delta = np.c_[x+.5,y+.5]-triangles[:,0]
        det = ab[:,0]*ac[:,1]-ab[:,1]*ac[:,0]
        require(np.all(np.abs(det)>1e-12),'Degenerate mapped donor triangle')
        u = (delta[:,0]*ac[:,1]-delta[:,1]*ac[:,0])/det
        v = (ab[:,0]*delta[:,1]-ab[:,1]*delta[:,0])/det
        corners = value['positions'][value['faces'][faces]]
        return (np.einsum('ij,ijk->ik',np.c_[1-u-v,u,v],corners)-lo)/span
    donor_points,target_points=points(donors),points(target)
    side=op.get('headSide')
    require(side in (None,'front','rear'),'Head heal side must be front or rear in unposed GLB +z-forward coordinates')
    if side is not None:
        z=np.r_[donor_points[:,2],target_points[:,2]]
        require(bool(np.all(z<=.5) if side=='rear' else np.all(z>=.5)),
                'Head heal target/donor leaves the declared '+side+' half (+z is front before fitting)')
        report.update(headSide=side,normalizedDepthRange=[float(z.min()),float(z.max())])
    distance,indices = cKDTree(donor_points).query(target_points+offset,k=4)
    require(distance[:,0].max()<=.10,'Local paint donor lies too far from its target')
    weights = 1/np.maximum(distance,.0005)
    colors = (rgb[donors][indices]*weights[:,:,None]).sum(axis=1)/weights.sum(axis=1)[:,None]
    rgb[target] = np.rint(colors).astype(np.uint8)
    report.update(paintedTexels=count,donorSamples=int(donors.sum()),maximumDistance=float(distance[:,0].max()))
    return {op['name']:target}



def material_hint(op, source):
    """An explicit local hair repair must bind geometry and explain the material decision."""
    if 'materialChannel' not in op:
        return None
    require(op.get('op') == 'heal' and type(op['materialChannel']) is int and op['materialChannel'] == 1,
            'Material heals currently support hair channel 1 only')
    require(op.get('sourceSha256') == source['sha256'],
            'Material heal must bind the exact UV mesh SHA256')
    require(isinstance(op.get('notes'), str) and op['notes'].strip(),
            'Material heal needs the observed defect and reviewed donor material')
    return {'name':op['name'], 'channel':1, 'sourceSha256':source['sha256'], 'notes':op['notes']}


def material_ownership(config, painted, source):
    """Carry a measured paint region into rules, retaining all later face/eye/ear protections."""
    hints = painted.get('ownershipHints', [])
    if not hints:
        return config
    require(config.get('mode') == 'rules', 'Material heals require rule ownership')
    digest = pin(source)['sha256']
    require(painted['source']['sha256'] == digest, 'Material heal uses another UV mesh')
    rules = []
    names = set()
    for hint in hints:
        name = hint['name']
        require(name not in names and type(hint.get('channel')) is int and hint.get('channel') == 1 and hint.get('sourceSha256') == digest
                and hint.get('mask') == painted['masks'].get(name),
                'Invalid or stale material heal ownership hint')
        names.add(name)
        rules.append({'name':'material-heal-'+name, 'channel':1,
                      'when':{'mask':name}})
    return dict(config, rules=rules+config['rules'])


def apply_material_hints(labels, painted, features, mapped):
    """Honor a reviewed local hair heal after soft parsing, never over anatomical protections."""
    from scipy.ndimage import binary_dilation
    hints = painted.get('ownershipHints', [])
    if not hints:
        return labels
    required = ('eye','iris','ear','lips','nose')
    require(all(name in features for name in required), 'Material heal needs eye/iris/ear/lip/nose protections')
    blocked = np.logical_or.reduce([features[name] > .5 for name in required])
    blocked |= binary_dilation(features['eye'] > .5, iterations=12)
    selected = np.zeros_like(mapped)
    for hint in hints:
        with Image.open(hint['mask']['path']) as image:
            require(image.mode == 'L' and image.size == (4096,4096), 'Material heal needs its exact 4K mask')
            active = (np.asarray(image) > 0) & mapped
        require(not np.any(active & blocked), 'Material heal intersects protected eyes, nose, lips or ears')
        require(np.all(np.isin(labels[active], (0,1))), 'Material heal intersects another material channel')
        selected |= active
    result = labels.copy()
    result[selected] = 1
    return result


def audit_material_hints(labels, onek, painted, mapped):
    """Refuse semantic overrides or runtime downsampling that loses a declared hair repair."""
    reports = []
    for hint in painted.get('ownershipHints', []):
        with Image.open(hint['mask']['path']) as image:
            require(image.mode == 'L' and image.size == (4096,4096), 'Material heal needs its exact 4K mask')
            mask = np.asarray(image) > 0
            # Eight of sixteen rounds to 128 in an L image, but is a tie, not a hair majority.
            counts=mask.reshape(1024,4,1024,4).sum(axis=(1,3))
            runtime=counts>8
        active = mask & mapped
        require(0 < active.sum() <= mapped.sum()*.03 and runtime.any(), 'Material heal exceeds its local limit or has no runtime interior')
        report = {'name':hint['name'], 'channel':hint['channel'], 'mappedTexels':int(active.sum()),
                  'runtimeTexels':int(runtime.sum()), 'boundaryTies':int(np.sum(counts==8)), 'wrong4k':int(np.sum(labels[active] != hint['channel'])),
                  'wrong1k':int(np.sum(onek[runtime] != hint['channel']))}
        reports.append(report)
        require(report['wrong4k'] == 0 and report['wrong1k'] == 0,
                f"Material heal conflicts with feature protection or loses its runtime channel: {hint['name']}; wrong 4K={report['wrong4k']}/{report['mappedTexels']}, 1K={report['wrong1k']}/{report['runtimeTexels']}")
    return reports

def paint(source, color, config, output, *, seal_start=None, embree=None):
    """Apply configured recolor/fill operations in order; each emits a 4K face mask for review and ownership rules.
    seal_start is the first face of repair's neck seal (it appends the cap after the reduced shell), so a fill can
    select {of: seal} without a per-head face index. A protrusion paints nothing: it only emits its mask (embree: the bound
    Embree DLL path)."""
    value=mesh(source);rgb=np.asarray(Image.open(color).convert('RGB')).copy()
    require(rgb.shape==(4096,4096,3),'Paint source must be an actual 4096x4096 colour map')
    operations=config.get('operations');require(isinstance(operations,list) and operations,'Configured paint operations required')
    output=Path(output);output.mkdir(parents=True,exist_ok=False);texels=texel_source(value,rgb);regions=config.get('regions',{})
    source_pin=pin(source)
    hints=[hint for op in operations if (hint := material_hint(op,source_pin)) is not None]
    masks={};reports=[]
    for op in operations:
        require(op.get('op') in ('crest','fill','protrusion','mask','heal') and isinstance(op.get('name'),str) and op['name'].replace('-','').isalnum(),'Named crest/fill/protrusion/mask operation required')
        report={'op':op['op'],'name':op['name']}
        if op['op']=='mask':
            require(set(op)=={'op','name','faces'}, 'Mask operation needs only name and spatial face conditions')
            selected=when(op['faces'],face_values(value,rgb,seal_start),regions)
            require(selected.any(), 'Mask selects no faces: '+op['name'])
            created={op['name']:face_mask(np.asarray(value['uv']),selected,len(rgb))}
            report.update(faces=int(selected.sum()),paintedTexels=0)
        elif op['op']=='heal':
            created=heal(value,rgb,op,report,texels,regions)
        elif op['op']=='protrusion':
            selected,found=protrusion_faces(value,rgb,op,regions,embree,seal_start);report.update(found)
            created={op['name']:face_mask(np.asarray(value['uv']),selected,len(rgb))}
        else:created=crest(value,rgb,op,report) if op['op']=='crest' else fill(value,rgb,op,report,texels,regions,seal_start)
        require(not set(created)&set(masks),'Duplicate paint mask name');masks.update(created);reports.append(report)
    if any(op['op']=='heal' for op in operations):
        from .textures import pad
        rgb=pad(rgb,texels()['mapped'])
    image=Image.fromarray(rgb);files={}
    for size in (4096,2048,1024):
        path=output/f'basecolor-{size}.png';(image if size==4096 else image.resize((size,size),Image.Resampling.BOX)).save(path);files[path.name]=pin(path)
    pins={}
    for name,mask in masks.items():
        path=output/f'{name}-faces-4096.png';Image.fromarray(mask.astype(np.uint8)*255).save(path);pins[name]=pin(path)
    result={'source':source_pin,'color':pin(color),'maps':files,'masks':pins,'operations':reports,'visualReviewRequired':True}
    if hints:
        result['ownershipHints']=[dict(hint,mask=pins[hint['name']]) for hint in hints]
    write(output/'paint.json',result,fresh=True);return result


def surface_outline(centres, spec):
    """Select face centres within a measured orthographic outline in the head's unit bounding box."""
    axes = spec.get('axes') if isinstance(spec, dict) else None
    require(isinstance(axes, str) and len(axes) == 2 and len(set(axes)) == 2
            and all(axis in 'xyz' for axis in axes), 'Surface outline needs two distinct axes')
    points = np.asarray(spec.get('points'), dtype=float)
    require(points.ndim == 2 and points.shape[1] == 2 and 3 <= len(points) <= 512
            and np.isfinite(points).all() and ((points >= 0) & (points <= 1)).all(),
            'Surface outline needs 3..512 normalized points')
    area = np.dot(points[:, 0], np.roll(points[:, 1], 1)) - np.dot(points[:, 1], np.roll(points[:, 0], 1))
    require(abs(area) > 1e-9, 'Surface outline has no area')
    # Even-odd crossing, evaluated on the much smaller face list before atlas padding.
    x, y = (centres[:, 'xyz'.index(axis)] for axis in axes)
    inside = np.zeros(len(centres), dtype=bool)
    for (ax, ay), (bx, by) in zip(points, np.roll(points, -1, axis=0)):
        if ay != by:
            inside ^= ((ay > y) != (by > y)) & (x < ax + (y-ay)*(bx-ax)/(by-ay))
    return inside


def rule_ownership(source, color, config, *, metallic=None, masks=None, protected=False):
    """First matching rule wins (list order is priority); padding takes the label of the nearest mapped texel. With protected,
    also returns the mapped texels of hair rules marked overFaceMasks, or None when no rule marks any (face_encode keeps them hair
    where they join hair, RUNBOOK 161)."""
    value=mesh(source);rgb=np.asarray(Image.open(color).convert('RGB'))
    require(rgb.shape[0]==rgb.shape[1],'Rule ownership needs a square colour atlas')
    extra={'mask:'+name:(lambda path=path:np.asarray(Image.open(path).convert('L'))>0) for name,path in (masks or {}).items()}
    if metallic is not None:extra['metallic']=lambda:np.asarray(Image.open(metallic).convert('L'))
    owners = raster_audit(value['uv'], len(rgb))[1]
    outlines = config.get('surfaceOutlines', {})
    if outlines:
        require(isinstance(outlines, dict), 'surfaceOutlines must map names to measured outlines')
        centres, low, high = frame(value)
        relative = (centres-low)/np.maximum(high-low, 1e-12)
        for name, spec in outlines.items():
            key = 'mask:'+name
            require(key not in extra, 'Surface outline conflicts with a painted mask: '+name)
            selected = surface_outline(relative, spec)
            extra[key] = lambda selected=selected: (owners>=0) & selected[owners]
    values=texel_values(value,rgb,owners,extra);mapped=values['mapped']
    default=config.get('default',0);require(type(default) is int and 0<=default<=9,'Default channel 0..9 required')
    labels=np.full(mapped.shape,default,np.uint8);free=np.ones(mapped.shape,bool);keep=np.zeros(mapped.shape,bool);counts=[]
    for rule in config['rules']:
        require(type(rule.get('channel')) is int and 0<=rule['channel']<=9 and isinstance(rule.get('name'),str),'Named rule with channel 0..9 required')
        over=rule.get('overFaceMasks',False);require(type(over) is bool and (not over or rule['channel']==1),'overFaceMasks is a boolean on hair (1) rules')
        selected=when(rule['when'],values,config.get('regions',{}))&free&mapped;labels[selected]=rule['channel'];free&=~selected
        if over:keep|=selected
        counts.append({'name':rule['name'],'channel':rule['channel'],'texels':int(selected.sum())})
    labels=labels[tuple(distance_transform_edt(~mapped,return_distances=False,return_indices=True))]
    report={'rules':counts,'defaultTexels':int((free&mapped).sum()),'channels':{str(k):int(n) for k,n in enumerate(np.bincount(labels.reshape(-1),minlength=10)) if n}}
    return (labels,report,keep if keep.any() else None) if protected else (labels,report)


def adjust(color, ownership, config, palettes, output):
    """Per-channel colour operations without a reference image; no operations is an explicit pass-through.
    Conditions read the input colour and ownership, so operation order only matters where selections overlap."""
    rgb=np.asarray(Image.open(color).convert('RGB'));result=rgb.copy()
    with Image.open(ownership) as image:
        require(image.mode=='L','Ownership masks must be eight-bit L images');labels=np.asarray(image).copy()
    require(labels.shape==rgb.shape[:2] and np.all(labels<=9),'Discrete 0..9 ownership required')
    values=colour_values(rgb,{'channel':lambda:labels});report=[]
    for op in config.get('operations',[]):
        selected=when(op['when'],values,config.get('regions',{}))
        if op['op']=='set':
            colour=op['color'];require(len(colour)==3 and all(type(c) is int and 0<=c<=255 for c in colour),'Set colour must be three bytes')
            result[selected]=colour
        else:
            # Keep each texel's brightness, take its hue from a stock palette row (nearest scaled row luminance).
            require(op['op']=='paletteRamp' and op.get('palette') in palettes,'Unknown adjust operation or palette')
            table=np.asarray(Image.open(palettes[op['palette']]).convert('RGB'))
            require(type(op['row']) is int and 0<=op['row']<len(table) and table.shape[1]==256,'Invalid stock palette row')
            ramp=table[op['row'],:255].astype(float);brightness=ramp.mean(1)
            unique,inverse=np.unique(values['lum'][selected],return_inverse=True)
            pick=np.abs(unique[:,None]*float(op.get('luminanceScale',1))-brightness[None,:]).argmin(1)
            result[selected]=ramp[pick[inverse.reshape(-1)]].astype(np.uint8)
        report.append({'op':op['op'],'texels':int(selected.sum())})
    Image.fromarray(result).save(output)
    return {'source':pin(color),'ownership':pin(ownership),'output':pin(output),'mode':'adjust','operations':report}
