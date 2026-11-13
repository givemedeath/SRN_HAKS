"""Bounded projected shadow proxies in an explicit native plane; visible meshes stay intact."""
from collections import defaultdict
import numpy as np
from scipy.spatial import Delaunay, cKDTree
from PIL import Image, ImageDraw
from tools.headkit.common import require
from .geometry import corner_hash, topology, protected_checks
from pathlib import Path
from tools.headkit.common import pin,verify,write,digest


METHODS=('projected-silhouette','quadric')
# Barycentric samples of every shadow triangle (corners, edges and interior, 28 per triangle) for the surface bound.
SURFACE_SAMPLES=np.array([(i/6,j/6,1-i/6-j/6) for i in range(7) for j in range(7-i)])


def build_candidates(source, profile, processing, output, *, meshlab=None, igl=None):
    """Build in bundled Python, keeping SciPy out of Blender's separate ABI. A `quadric` proxy also needs the bound
    pymeshlab and igl modules (the runner passes its pinned libraries)."""
    from .parts import active_parts
    bound=pin(source);root=Path(output);root.mkdir(parents=True,exist_ok=False)
    settings=processing.get('shadowProxies',{})
    require(set(settings)<=set(active_parts(profile)), 'Shadow proxy names must be active parts')
    candidates={}
    with np.load(source,allow_pickle=False) as data:
        for part,policy in settings.items():
            require(policy.get('method') in METHODS,'Unknown shadow proxy method')
            p=data[part+'_positions'];f=data[part+'_faces']
            budget=profile['budgets']['parts'][part]['shadow'];probes=processing.get('openingProbes',[])
            protected={'openingProbes':probes}
            # Probes are measured on the assembly; `parts` scopes one to the parts it touches.
            thickness=[row for row in processing.get('thicknessProbes',[]) if part in row.get('parts',[part])]
            if thickness:protected['thicknessProbes']=thickness
            if policy['method']=='quadric':
                v,t,checks=quadric_proxy(p,f,protected,budget,policy,meshlab,igl,diagnostics=root/(part+'-attempts'))
            else:
                v,t,checks=silhouette_proxy(p,f,protected,budget,policy,diagnostics=root/(part+'-attempts'))
            target=root/(part+'.npz');np.savez_compressed(target,positions=v,faces=t)
            candidates[part]={'arrays':pin(target),'sourceCornerHash':corner_hash(p[f]),
                              'policyHash':digest({'settings':policy,**protected,'budget':budget}),
                              'checks':checks,'visualReviewRequired':True}
    verify([bound], fresh=True);write(root/'result.json',{'source':bound,'candidates':candidates},fresh=True)
    return candidates


def quadric_proxy(vertices, faces, processing, budget, settings, meshlab, igl, *, diagnostics=None):
    """The part's own closed surface collapsed to its shadow budget by a topology- and normal-preserving quadric, for
    parts whose cross-section varies around the axis (a projected silhouette there overstates the thickness probes).
    Each quality threshold is one bounded attempt; the first that stays closed, within budget and within
    `maximumDistance` of the source and keeps every protected probe is accepted. Blender's plain collapse, the
    default shadow, has none of these checks until the assembly is measured."""
    require(meshlab is not None and igl is not None, 'A quadric shadow needs the bound pymeshlab and igl')
    p=np.asarray(vertices,float);f=np.asarray(faces)
    require(p.ndim==2 and p.shape[1]==3 and np.isfinite(p).all(), 'Finite shadow source required')
    require(f.ndim==2 and f.shape[1]==3 and np.issubdtype(f.dtype,np.integer) and len(f) and f.min()>=0 and f.max()<len(p), 'Valid shadow triangles required')
    require(type(budget) is int and 12<=budget<=500, 'Bounded per-part shadow budget required')
    require(topology(p,f)['closedWound'], 'A quadric shadow needs a closed outward source part')
    limit=settings.get('maximumDistance',.006);qualities=settings.get('qualityThresholds',[.3,.5,.1])
    require(type(limit) in (int,float) and 0<limit<=.02, 'Bounded quadric shadow distance required')
    # Vertices stay near the source, but a large triangle between them can cut across a curve or bridge a recess, so
    # the surface itself (vertices and triangle interiors) has its own, looser bound: the 300-triangle staff head
    # measured 5.6-7.8 mm at its vertices and 15-20 mm across its triangles.
    surface_limit=settings.get('maximumSurfaceDistance',.025)
    require(type(surface_limit) in (int,float) and limit<=surface_limit<=.04, 'Bounded quadric shadow surface distance required')
    require(isinstance(qualities,list) and 1<=len(qualities)<=5 and all(type(q) in (int,float) and 0<=q<=1 for q in qualities),
            'Bounded quadric quality thresholds required')
    # Faces around each thickness-probe end are kept as they are (like the visible reduction's seam band), so the
    # probes measure the source surface itself; the collapse spends the rest of the budget elsewhere.
    radius=settings.get('probeRadius',.006);require(type(radius) in (int,float) and 0<=radius<=.02, 'Bounded probe protection radius required')
    ends=np.asarray([point for row in processing.get('thicknessProbes',[]) for point in row['points']],float).reshape(-1,3)
    centres=p[f].mean(1);protected=np.zeros(len(f),bool)
    for end in ends:protected|=np.linalg.norm(centres-end,axis=1)<=radius
    require(int(protected.sum())<=budget//2, 'Protected probe faces alone use half the shadow budget')
    if diagnostics is not None:diagnostics=Path(diagnostics);diagnostics.mkdir(parents=True,exist_ok=False)
    attempts=[];accepted=None
    for quality in qualities:
        # The selected-face collapse counts only the selected faces; a protected patch's rim can leave it a few over,
        # so the target steps down by the overshoot (at most three bounded passes).
        target=budget-4-int(protected.sum());t=None
        for _ in range(3):
            if target<4:break                                   # recorded below; the next threshold still gets its try
            ms=meshlab.MeshSet();ms.add_mesh(meshlab.Mesh(p,f.astype(np.int32),f_scalar_array=(~protected).astype(float)))
            ms.meshing_remove_duplicate_vertices();ms.compute_selection_by_scalar_per_face(minq=.5,maxq=1.,inclusive=True)
            ms.meshing_decimation_quadric_edge_collapse(targetfacenum=target,selected=True,preservetopology=True,preserveboundary=True,
                                                        preservenormal=True,planarquadric=True,qualitythr=float(quality))
            ms.meshing_remove_unreferenced_vertices();m=ms.current_mesh();v=m.vertex_matrix();t=m.face_matrix().astype(np.int64)
            if len(t)<=budget:break
            target-=len(t)-budget
        if t is None:
            attempts.append({'qualityThreshold':quality,'error':'Protected probe faces leave no shadow budget to collapse'});continue
        report=topology(v,t);row={'qualityThreshold':quality,'triangles':len(t),'closedWound':report['closedWound'],'topology':report}
        attempts.append(row)
        if diagnostics is not None:np.savez_compressed(diagnostics/f'quality-{quality}.npz',positions=v,faces=t)
        try:
            require(len(t)<=budget and report['closedWound'],'Invalid shadow topology/budget')
            distance=float(np.sqrt(igl.point_mesh_squared_distance(v,p,f.astype(np.int64))[0]).max());row['maximumDistance']=distance
            require(distance<=limit,'Quadric shadow left the source surface')
            interior=np.einsum('bk,tkd->tbd',SURFACE_SAMPLES,v[t]).reshape(-1,3)
            surface=float(np.sqrt(igl.point_mesh_squared_distance(interior,p,f.astype(np.int64))[0]).max());row['surfaceDistance']=surface
            require(surface<=surface_limit,'Quadric shadow triangles cut away from the source surface')
            # The other direction is recorded for the visual review, not gated: a shadow simplifies by design, but a
            # large gap points at a fin or spike the collapse removed.
            gap=float(np.sqrt(igl.point_mesh_squared_distance(p,v,t)[0]).max());row['sourceToShadowDistance']=gap
            opening=protected_checks(v,t,processing)
            accepted=(v,t,report,opening,distance,surface,gap);break
        except ValueError as exc:row['error']=str(exc)
    if diagnostics is not None:write(diagnostics/'attempts.json',attempts,fresh=True)
    require(accepted is not None, 'Quadric shadow failed acceptance checks: '+str(attempts))
    v,t,report,opening,distance,surface,gap=accepted
    return v,t,{'attempts':attempts,'topology':report,'openings':opening,'maximumSourceDistance':distance,
        'maximumSurfaceDistance':surface,'maximumSourceGap':gap,
        'probeProtectedFaces':int(protected.sum()),'method':'quadric','visualReviewRequired':True,'visibleGeometryUnchanged':True}


def cross2(a,b):
    return a[...,0]*b[...,1]-a[...,1]*b[...,0]


def silhouette_proxy(vertices, faces, processing, budget, settings, *, diagnostics=None):
    original=np.asarray(vertices,float);f=np.asarray(faces)
    require(original.ndim==2 and original.shape[1]==3 and np.isfinite(original).all(), 'Finite shadow source required')
    require(f.ndim==2 and f.shape[1]==3 and np.issubdtype(f.dtype,np.integer) and len(f) and f.min()>=0 and f.max()<len(original), 'Valid shadow triangles required')
    require(type(budget) is int and 12<=budget<=500, 'Bounded per-part shadow budget required')
    basis=np.asarray(settings.get('basis',np.eye(3)),float);origin=np.asarray(settings.get('origin',[0,0,0]),float)
    require(basis.shape==(3,3) and origin.shape==(3,) and np.isfinite(basis).all() and np.isfinite(origin).all()
            and np.allclose(basis.T@basis,np.eye(3),atol=1e-8) and np.linalg.det(basis)>0, 'Right-handed orthonormal shadow frame required')
    p=(original-origin)@basis
    resolution=settings.get('resolution',1024);tolerances=settings.get('tolerances',[2,3,4,6,8])
    require(type(resolution) is int and 128<=resolution<=2048, 'Bounded silhouette resolution required')
    require(isinstance(tolerances,list) and 1<=len(tolerances)<=5 and all(type(t) is int and 1<=t<=8 for t in tolerances)
            and tolerances==sorted(set(tolerances)), 'Bounded ordered silhouette tolerances required')
    extent=float(np.ptp(p[:,1:],axis=0).max());require(extent>1e-9, 'Empty projected silhouette')
    depth_radius=settings.get('depthRadius',extent*.002);minimum_thickness=settings.get('minimumThickness',extent*.001)
    require(0<depth_radius<=extent*.05 and 0<minimum_thickness<=extent*.02, 'Bounded local shadow depth required')
    minimum_iou=settings.get('minimumIoU',.95);require(.95<=minimum_iou<=1, 'Shadow IoU cannot be weakened below .95')
    if diagnostics is not None:diagnostics=Path(diagnostics);diagnostics.mkdir(parents=True,exist_ok=False)
    low=p[:,1:].min(0);span=np.ptp(p[:,1:],axis=0);scale=(resolution-24)/float(span.max())
    xy=(p[:,1:]-low)*scale+12
    # Contour vertices alone can miss a thick interior surface. Retain measured
    # opposed-depth contacts as interior triangulation controls, after proving
    # those contacts against the actual source with the same distance bounds.
    control_depths={}
    if processing.get('thicknessProbes'):
        protected_checks(original,f,processing)
        for probe in processing['thicknessProbes']:
            ends=(np.asarray(probe['points'],float)-origin)@basis
            if np.linalg.norm(ends[0,1:]-ends[1,1:])>extent*1e-7:continue
            point=tuple((ends[:,1:].mean(0)-low)*scale+12)
            bounds=tuple(sorted(ends[:,0]))
            require(point not in control_depths or np.allclose(control_depths[point],bounds,atol=1e-10,rtol=0),
                    'Conflicting shadow thickness contacts')
            control_depths[point]=bounds
    controls=np.asarray(list(control_depths),float).reshape(-1,2)
    tree=cKDTree(p[:,1:])
    canvas=Image.new('1',(resolution,resolution));draw=ImageDraw.Draw(canvas)
    for t in xy[f]:draw.polygon([tuple(v) for v in t],fill=1)
    mask=np.asarray(canvas)
    closing=settings.get('closingPixels',0)
    require(type(closing) is int and closing in (0,1), 'Only zero or one pixel silhouette closing is supported')
    if closing:
        from scipy.ndimage import binary_closing
        mask=binary_closing(mask,iterations=closing)

    edges=[]
    for y,x in zip(*np.nonzero(mask)):
        if not mask[y-1,x]:edges.append(((x,y),(x+1,y)))
        if not mask[y,x+1]:edges.append(((x+1,y),(x+1,y+1)))
        if not mask[y+1,x]:edges.append(((x+1,y+1),(x,y+1)))
        if not mask[y,x-1]:edges.append(((x,y+1),(x,y)))
    following=defaultdict(list)
    for a,b in edges:following[a].append(b)
    loops=[]
    while following:
        start=next(iter(following));current=start;loop=[]
        while True:
            loop.append(current);choices=following[current];next_point=choices.pop()
            if not choices:del following[current]
            current=next_point
            if current==start:break
            require(current in following,'Open pixel silhouette boundary')
        points=np.asarray(loop,float)
        area=abs(np.sum(points[:,0]*np.roll(points[:,1],-1)-points[:,1]*np.roll(points[:,0],-1)))/2
        if area>=.5:loops.append(points)

    def rdp(points,tolerance):
        if len(points)<=2:return points
        delta=points[-1]-points[0];length=np.linalg.norm(delta)
        distances=np.linalg.norm(points-points[0],axis=1) if not length else np.abs(cross2(delta,points-points[0]))/length
        index=int(np.argmax(distances))
        if distances[index]<=tolerance:return points[[0,-1]]
        return np.r_[rdp(points[:index+1],tolerance)[:-1],rdp(points[index:],tolerance)]

    attempts=[];accepted=None
    for tolerance in tolerances:

        contours=[]
        for loop in loops:
            split=int(np.argmax(np.linalg.norm(loop-loop[0],axis=1)))
            contours.append(np.r_[rdp(loop[:split+1],tolerance)[:-1],rdp(np.r_[loop[split:],loop[:1]],tolerance)[:-1]])
        for refinement in range(12):
            points=np.unique(np.concatenate([*contours,controls]),axis=0);lookup={tuple(p):i for i,p in enumerate(points)}
            triangles=Delaunay(points).simplices
            edges={tuple(sorted((int(a),int(b)))) for face in triangles for a,b in ((face[0],face[1]),(face[1],face[2]),(face[2],face[0]))}
            missing=0;refined=[]
            for contour in contours:
                new=[]
                for a,b in zip(contour,np.roll(contour,-1,axis=0)):
                    new.append(a)
                    if tuple(sorted((lookup[tuple(a)],lookup[tuple(b)]))) not in edges:
                        new.append((a+b)*.5);missing+=1
                refined.append(np.asarray(new))
            if not missing:break
            contours=refined
        require(missing==0,'Could not preserve simplified contour edges')
        # All contour edges exist, so centroid parity classifies complete triangles.
        centers=points[triangles].mean(1);inside=np.zeros(len(centers),bool)
        for contour in contours:
            for a,b in zip(contour,np.roll(contour,-1,axis=0)):
                if a[1]==b[1]:continue
                inside^=((a[1]>centers[:,1])!=(b[1]>centers[:,1])) & (centers[:,0]<(b[0]-a[0])*(centers[:,1]-a[1])/(b[1]-a[1])+a[0])
        triangles=triangles[inside]
        t=points[triangles];sign=cross2(t[:,1]-t[:,0],t[:,2]-t[:,0]);triangles[sign<0]=triangles[sign<0][:,[0,2,1]]
        # Keep disconnected source components. Resolve only vertex-touching
        # junctions, with bounded edits and mandatory silhouette/probe checks.
        for repair in range(32):
            links=defaultdict(list)
            for fi,face in enumerate(triangles):
                for a,b in ((face[0],face[1]),(face[1],face[2]),(face[2],face[0])):links[tuple(sorted((a,b)))].append(fi)
            degree=defaultdict(int)
            for edge,incident in links.items():
                if len(incident)==1:
                    for vertex in edge:degree[vertex]+=1
            junctions=[v for v,d in degree.items() if d>2]
            if not junctions:break
            incident=np.flatnonzero(np.isin(triangles,junctions).any(1));t=points[triangles[incident]]
            areas=np.abs(cross2(t[:,1]-t[:,0],t[:,2]-t[:,0]));triangles=np.delete(triangles,incident[int(np.argmin(areas))],axis=0)
        else:raise ValueError('Planar shadow junction repair exceeded bounded pass')
        used,inverse=np.unique(triangles,return_inverse=True);points=points[used];triangles=inverse.reshape(-1,3);n=len(points)
        incidence=defaultdict(list)
        for a,b,c in triangles:
            for edge in ((a,b),(b,c),(c,a)):incidence[tuple(sorted(edge))].append(edge)
        boundary=[v[0] for v in incidence.values() if len(v)==1]
        yz=(points-12)/scale+low
        depth=[]
        for index,point in enumerate(yz):
            bound=control_depths.get(tuple(points[index]))
            if bound is None:
                distance,_=tree.query(point)
                neighbors=tree.query_ball_point(point,float(distance)+depth_radius)
                values=p[neighbors,0];lo,hi=float(values.min()),float(values.max())
            else:lo,hi=bound
            center=(lo+hi)/2;half=max((hi-lo)/2,minimum_thickness/2);depth.append((center-half,center+half))
        depth=np.asarray(depth)
        vertices=np.r_[np.c_[depth[:,0],yz],np.c_[depth[:,1],yz]]
        faces=np.r_[triangles[:,[0,2,1]],triangles+n,np.array([[a,b,b+n] for a,b in boundary]),np.array([[a,b+n,a+n] for a,b in boundary])]
        report=topology(vertices,faces);row={'tolerancePixels':tolerance,'triangles':len(faces),'closedWound':report['closedWound'],'topology':report};attempts.append(row)
        if diagnostics is not None:np.savez_compressed(diagnostics/(str(tolerance)+'.npz'),positions=vertices@basis.T+origin,faces=faces)
        try:
            require(len(faces)<=budget and report['closedWound'],'Invalid shadow topology/budget')
            world=vertices@basis.T+origin
            opening=protected_checks(world,faces,processing)
            check=Image.new('1',(resolution,resolution));d=ImageDraw.Draw(check)
            for tri in points[triangles]:d.polygon([tuple(v) for v in tri],fill=1)
            silhouette=np.asarray(check);iou=float(np.count_nonzero(silhouette&mask)/np.count_nonzero(silhouette|mask));row['sideSilhouetteIoU']=iou
            require(iou>=minimum_iou,'Shadow silhouette deviation exceeds five percent')
            accepted=(world,faces,report,opening,iou);break
        except ValueError as exc:row['error']=str(exc)
    if diagnostics is not None:write(diagnostics/'attempts.json',attempts,fresh=True)
    require(accepted is not None, 'Silhouette proxy failed acceptance checks: '+str(attempts))
    vertices,faces,report,opening,iou=accepted
    return vertices,faces,{'attempts':attempts,'topology':report,'openings':opening,'sideSilhouetteIoU':iou,
        'frame':{'basis':basis.tolist(),'origin':origin.tolist()},'depthMethod':'local-source-envelope',
        'verifiedThicknessControls':len(control_depths),
        'visualReviewRequired':True,'visibleGeometryUnchanged':True}
