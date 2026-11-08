"""Source-bound local cavity closure with protected UVs and approved stock texture encoding."""
from pathlib import Path
import hashlib
import io
import json
import math
import numpy as np
from PIL import Image
from scipy.interpolate import RBFInterpolator
from scipy.ndimage import binary_dilation, label, maximum_filter
from scipy.spatial import cKDTree
from .common import require, pin, verify, write, library
from .gltf import load, encode, mesh, write_mesh
from .mesh import physical, topology, audit
from .diagnostics import views, VIEWS
from .uv import raster_audit

KIND = 'headkit-local-repair-baseline-v1'


def geometry_fingerprint(value):
    digest = hashlib.sha256()
    for key, dtype in (('positions','<f4'),('faces','<u4'),('uv','<f4'),('normals','<f4')):
        array=np.ascontiguousarray(value[key],dtype=dtype)
        digest.update(str(array.shape).encode());digest.update(array.tobytes())
    return digest.hexdigest()


def bundle(source, payloads, rows, output, *, palette_report=None):
    """Embed actual baseline maps in one declared GLB input, with content hashes."""
    expected={'basecolor4k','shades','layers','decoded','hairPalette'}
    require(set(payloads)==expected,'Local repair needs the approved colour, PLT maps and hair table')
    inputs=[pin(source),*[pin(p) for p in payloads.values()]]
    document,binary,_=load(Path(source).read_bytes());binary=bytearray(binary)
    records={}
    for name,path in payloads.items():
        data=Path(path).read_bytes();binary.extend(b'\0'*((-len(binary))%4));offset=len(binary);binary.extend(data)
        index=len(document['bufferViews']);document['bufferViews'].append({'buffer':0,'byteOffset':offset,'byteLength':len(data)})
        records[name]={'bufferView':index,'sha256':hashlib.sha256(data).hexdigest()}
    evidence = None
    if palette_report is not None:
        report_pin = pin(palette_report);inputs.append(report_pin)
        report = json.loads(Path(palette_report).read_text(encoding='utf-8'))
        require(report.get('rows') == rows,'Baseline palette rows differ')
        for role, name in (('shades','shades'),('ownership','layers'),('decoded','decoded')):
            require(report.get(role,{}).get('sha256') == records[name]['sha256'],
                    'Baseline palette report differs from '+name)
        hair = report.get('layers',{}).get('1',{})
        span = hair.get('shadeRange',{})
        tie = span.get('endTie')
        require(span.get('checked') is True and type(tie) in (int,float) and 0<=tie<=1,
                'Checked source hair end-tie evidence required')
        with Image.open(payloads['layers']) as image: count=int((np.asarray(image)==1).sum())
        require(count>0 and hair.get('pixels')==count,'Baseline hair pixel count differs')
        evidence={'report':report_pin,'endTie':tie,'hairTexels':count}
    document['buffers'][0]['byteLength']=len(binary)
    document.setdefault('extras',{})['headkitLocalRepair']={'kind':KIND,'rows':rows,
        'geometryFingerprint':geometry_fingerprint(mesh(source)),'maps':records,'source':inputs[0],
        **({'hairEndTieEvidence':evidence} if evidence is not None else {})}
    Path(output).write_bytes(encode(document,bytes(binary)));verify(inputs,fresh=True)
    return {'source':inputs,'output':pin(output),'kind':KIND}


def read_bundle(source):
    document,binary,_=load(Path(source).read_bytes())
    data=document.get('extras',{}).get('headkitLocalRepair',{})
    require(data.get('kind')==KIND,'A byte-bound approved local-repair baseline is required')
    value=mesh(source);require(geometry_fingerprint(value)==data['geometryFingerprint'],'Baseline geometry changed')
    maps={}
    for name,row in data['maps'].items():
        view=document['bufferViews'][row['bufferView']];start=view.get('byteOffset',0)
        payload=binary[start:start+view['byteLength']]
        require(hashlib.sha256(payload).hexdigest()==row['sha256'],'Baseline map changed: '+name)
        with Image.open(io.BytesIO(payload)) as image:
            maps[name]=np.asarray(image.convert('RGB') if name in ('basecolor4k','decoded','hairPalette') else image).copy()
    require(maps['basecolor4k'].shape==(4096,4096,3) and maps['decoded'].shape==(1024,1024,3)
            and maps['layers'].shape==maps['shades'].shape==(1024,1024),'Baseline map dimensions differ')
    require(maps['layers'].dtype==maps['shades'].dtype==np.uint8 and np.max(maps['layers'])<=9
            and np.max(maps['shades'])<255,'Resolved stock palette maps required')
    return value,data,maps


def genus(vertices,faces):
    t=topology(vertices,faces);require(t['closed'],'Local seal source/result must be a closed manifold')
    # This route keeps one connected source shell; a seal must remove one handle.
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    p,f=physical(vertices,faces)
    graph=coo_matrix((np.ones(len(f)*3),(f.ravel(),np.roll(f,1,axis=1).ravel())),shape=(len(p),len(p)))
    require(connected_components(graph,directed=False,return_labels=False)==1,'Local repair requires one connected shell')
    return (2-t['physicalVertices']+len(faces)//2)//2


def cavity(value,dll,recipe):
    name=recipe['view'];size=recipe.get('size',512);seed=recipe['seed']
    require(name in VIEWS and type(size) is int and 128<=size<=512
            and len(seed)==2 and all(type(x) is int and 0<=x<size for x in seed),'Bounded source-view seed required')
    view=next(views(value,dll,size,[name]))[1];hit=view['hit'].reshape(size,size)
    corners=value['positions'][value['faces'][view['face']]]
    points=np.einsum('ij,ijk->ik',view['bary'],corners).reshape(size,size,3)
    yaw,tilt=map(math.radians,VIEWS[name])
    toward=np.array([math.sin(yaw)*math.cos(tilt),math.sin(tilt),math.cos(yaw)*math.cos(tilt)])
    right=np.array([math.cos(yaw),0,-math.sin(yaw)]);up=np.cross(toward,right)
    width=float(np.ptp(value['positions'][:,0]));depth=points@toward
    radius=recipe.get('roiPixels',18);require(type(radius) is int and 8<=radius<=32,'Bounded cavity ROI required')
    x,y=seed;roi=np.zeros_like(hit);roi[max(0,y-radius):y+radius+1,max(0,x-radius):x+radius+1]=True
    require(np.count_nonzero(roi&hit)>=32,'Too few surrounding hair rays')
    level=float(np.percentile(depth[roi&hit],75))
    deep=roi & (~hit | (depth<level-.05*width))
    parts,_=label(deep);part=parts[y,x]
    require(part>0,'Reviewed seed is not a deep opening')
    core=parts==part;yy,xx=np.where(core)
    require(len(xx)>=2 and xx.min()>max(0,x-radius) and xx.max()<min(size-1,x+radius)
            and yy.min()>max(0,y-radius) and yy.max()<min(size-1,y+radius),'Cavity reaches ROI/silhouette boundary')
    ring=binary_dilation(core,iterations=3)&~binary_dilation(core,iterations=1)&hit&(depth>level-.025*width)
    samples=points[ring];require(len(samples)>=16,'Insufficient measured cavity rim')
    origin=samples.mean(0);q=np.c_[(samples-origin)@right,(samples-origin)@up];z=(samples-origin)@toward
    # Screen tangent coordinates are independent of the seed ray's depth.
    scale=float(np.linalg.norm(np.ptp(value['positions'],axis=0)))*1.08
    if 'temple' in name:scale=float(np.ptp(value['positions'],axis=0).max())*1.08
    xy=np.c_[(xx+.5-size/2)*scale/size,(size/2-yy-.5)*scale/size]
    center=(value['positions'].min(0)+value['positions'].max(0))/2
    absolute=np.c_[(origin-center)@right,(origin-center)@up]
    xy-=absolute
    middle=(xy.min(0)+xy.max(0))/2
    return {'view':view,'core':core,'origin':origin,'q':q,'z':z,'middle':middle,'xy':xy,
            'right':right,'up':up,'toward':toward,'pixel':scale/size,'width':width,'level':level}


def solid(plan,margin,rings=2,sides=12):
    middle=plan['middle'];extent=np.max(np.abs(plan['xy']-middle),axis=0)+margin*plan['pixel']
    factor=max(1.,float(np.sqrt(np.sum(((plan['xy']-middle)/extent)**2,axis=1)).max())*1.05)
    extent*=factor
    require(extent.max()<=.08*plan['width'],'Local seal exceeds its measured scalp bound')
    xy=[middle]
    for ring in range(1,rings+1):
        xy.extend(middle+extent*ring/rings*np.c_[np.cos(np.arange(sides)*2*np.pi/sides),np.sin(np.arange(sides)*2*np.pi/sides)])
    xy=np.asarray(xy)
    f=RBFInterpolator(plan['q'],plan['z'],kernel='thin_plate_spline',smoothing=1e-7)
    height=np.clip(f(xy),plan['z'].min(),plan['z'].max())+.001*plan['width']
    top=plan['origin']+xy[:,0,None]*plan['right']+xy[:,1,None]*plan['up']+height[:,None]*plan['toward']
    thickness=.05*plan['width'];vertices=np.r_[top,top-thickness*plan['toward']];n=len(top)
    faces=[[0,1+i,1+(i+1)%sides] for i in range(sides)]
    for j in range(rings-1):
        for i in range(sides):
            a=1+j*sides+i;b=1+j*sides+(i+1)%sides;c=a+sides;d=b+sides
            faces.extend(([a,c,d],[a,d,b]))
    faces.extend((np.asarray(faces)[:,::-1]+n).tolist());base=1+(rings-1)*sides
    for i in range(sides):
        a=base+i;b=base+(i+1)%sides;faces.extend(([a,a+n,b+n],[a,b+n,b]))
    faces=np.asarray(faces,np.int32)
    if np.einsum('ij,ij->i',vertices[faces[:,0]],np.cross(vertices[faces[:,1]],vertices[faces[:,2]])).sum()<0:faces=faces[:,::-1]
    return vertices,faces,extent


def close_geometry(value,bindings,recipe):
    ml=library(bindings,'pymeshlab');P,F=physical(value['positions'],value['faces'])
    initial=genus(P,F);plan=cavity(value,bindings['embree']['path'],recipe);records=[]
    for margin in (2.,3.,4.):
        V,T,extent=solid(plan,margin)
        ms=ml.MeshSet();ms.add_mesh(ml.Mesh(P,F.astype(np.int32),f_scalar_array=np.arange(len(F),dtype=float)+1))
        ms.add_mesh(ml.Mesh(V,T,f_scalar_array=-np.ones(len(T))))
        ms.generate_boolean_union(first_mesh=0,second_mesh=1,transfer_face_quality=True)
        current=ms.current_mesh();current.compact();v,f,birth=current.vertex_matrix(),current.face_matrix(),current.face_scalar_array()
        after=genus(v,f);records.append({'marginPixels':margin,'triangles':len(f),'genusBefore':initial,'genusAfter':after})
        if after==initial-1:break
    else:raise ValueError('Bounded local closure presets did not seal exactly one handle')
    # Only this measured neighbourhood may donate triangles to the 20K budget.
    centre=plan['origin']+plan['middle'][0]*plan['right']+plan['middle'][1]*plan['up']
    p=v[f].mean(1)-centre
    radial=((p@plan['right'])/(extent[0]*2.2))**2+((p@plan['up'])/(extent[1]*2.2))**2
    local=(birth<0)|((radial<1)&(np.abs(p@plan['toward'])<.09*plan['width']))
    require(local.sum()<=.06*len(f),'Local simplification exceeds six percent of faces')
    if len(f)>20000:
        markers=np.where(local,-1.,birth)
        reducer=ml.MeshSet();reducer.add_mesh(ml.Mesh(v,f.astype(np.int32),f_scalar_array=markers))
        reducer.compute_selection_by_condition_per_face(condselect='fq < 0')
        before=len(f);chosen=int(local.sum())
        reducer.meshing_decimation_quadric_edge_collapse(targetfacenum=20000,selected=True,preserveboundary=True,
            preservenormal=True,preservetopology=True,optimalplacement=True)
        current=reducer.current_mesh();current.compact()
        if current.face_number()>20000:
            # MeshLab deployments differ in whether selected targets are absolute or selection-relative.
            reducer=ml.MeshSet();reducer.add_mesh(ml.Mesh(v,f.astype(np.int32),f_scalar_array=markers))
            reducer.compute_selection_by_condition_per_face(condselect='fq < 0')
            reducer.meshing_decimation_quadric_edge_collapse(targetfacenum=chosen-(before-20000),selected=True,
                preserveboundary=True,preservenormal=True,preservetopology=True,optimalplacement=True)
            current=reducer.current_mesh();current.compact()
        v,f,birth=current.vertex_matrix(),current.face_matrix(),current.face_scalar_array()
    require(len(f)<=20000 and genus(v,f)==initial-1,'Local seal cannot meet the unchanged topology/triangle gates')
    return v,f,birth,plan,records


def allocate_uv(old_uv,new_count,size=1024):
    """Place independent tiny charts in unused space with the existing four-pixel gutter."""
    from scipy.ndimage import binary_dilation, minimum_filter
    occupied=raster_audit(old_uv,size)[1]>=0
    for side in (8,6,4):
        cell=side+10
        valid=minimum_filter((~occupied).astype(np.uint8),size=cell,mode='constant',cval=0)>0
        candidates=np.flatnonzero(valid);blocked=occupied.copy();allocated=[]
        for index in candidates:
            cy,cx=divmod(int(index),size);y=cy-cell//2;x=cx-cell//2
            if y<0 or x<0 or y+cell>size or x+cell>size or blocked[y:y+cell,x:x+cell].any():continue
            left,top=x+5,y+5
            allocated.append(np.array([[left+.25,top+.25],[left+side-.25,top+.25],[left+.25,top+side-.25]])/size)
            blocked[y:y+cell,x:x+cell]=True
            if len(allocated)==new_count:return np.asarray(allocated,np.float32),{'chartSidePixels':side,'gutterPixels':5}
    raise ValueError('No UV space for a local repair without repacking protected charts')


def restore_uv(value,v,f,birth):
    old=birth>0;uv=np.zeros((len(f),3,2),float);normals=np.zeros((len(f),3,3),float)
    source=np.rint(birth[old]).astype(int)-1
    require(np.all(np.abs(birth[old]-source-1)<1e-6) and np.all((source>=0)&(source<len(value['faces']))),'Boolean ancestry unavailable')
    corners=value['positions'][value['faces'][source]].astype(float);points=v[f[old]]
    ab,ac=corners[:,1]-corners[:,0],corners[:,2]-corners[:,0];d=points-corners[:,0,None]
    d00=(ab*ab).sum(1);d01=(ab*ac).sum(1);d11=(ac*ac).sum(1)
    d20=(d*ab[:,None]).sum(2);d21=(d*ac[:,None]).sum(2);den=d00*d11-d01*d01
    a=(d11[:,None]*d20-d01[:,None]*d21)/den[:,None];b=(d00[:,None]*d21-d01[:,None]*d20)/den[:,None]
    bary=np.stack([1-a-b,a,b],axis=2)
    projection=np.einsum('fsk,fkc->fsc',bary,corners)
    require(float(np.linalg.norm(projection-points,axis=2).max())<1e-6 and bary.min()>-1e-4,'Protected source faces changed')
    uv[old]=np.einsum('fsk,fkc->fsc',bary,value['uv'][source])
    if value['normals'] is not None:
        normals[old]=np.einsum('fsk,fkc->fsc',bary,value['normals'][value['faces'][source]])
    else:normals[old]=np.cross(ab,ac)[:,None,:]
    new=~old
    fresh,packing=allocate_uv(value['uv'],int(new.sum()));uv[new]=fresh
    fn=np.cross(v[f[:,1]]-v[f[:,0]],v[f[:,2]]-v[f[:,0]])
    vn=np.zeros_like(v)
    for i in range(3):np.add.at(vn,f[:,i],fn)
    vn/=np.maximum(np.linalg.norm(vn,axis=1,keepdims=True),1e-20)
    normals[new]=vn[f[new]]
    normals/=np.maximum(np.linalg.norm(normals,axis=2,keepdims=True),1e-20)
    return uv,normals,new,packing


def transfer_maps(value,v,f,uv,new,plan,maps,rows,output):
    """Keep baseline pixels; fill only new charts from qualified nearby hair samples."""
    source_corners=value['positions'][value['faces']]
    centers=source_corners.mean(1);origin=plan['origin'];relative=centers-origin
    near=(np.linalg.norm(relative,axis=1)<.18*plan['width'])
    fn=np.cross(source_corners[:,1]-source_corners[:,0],source_corners[:,2]-source_corners[:,0])
    fn/=np.maximum(np.linalg.norm(fn,axis=1,keepdims=True),1e-20)
    near &= (fn@plan['toward']>.05)&(centers@plan['toward']>plan['level']-.025*plan['width'])
    weights=np.array([[1/3]*3,[.6,.2,.2],[.2,.6,.2],[.2,.2,.6],[.8,.1,.1],[.1,.8,.1],[.1,.1,.8]])
    points=np.einsum('sk,fkc->fsc',weights,source_corners[near]).reshape(-1,3)
    samples=np.einsum('sk,fkc->fsc',weights,value['uv'][near]).reshape(-1,2)
    xy=np.clip((samples*1024).astype(int),0,1023);hair=maps['layers'][xy[:,1],xy[:,0]]==1
    require(hair.sum()>=16,'Insufficient adjacent approved hair donors')
    points,samples=points[hair],samples[hair];tree=cKDTree(points)
    source_xy=np.clip((samples*1024).astype(int),0,1023)
    donor_shades=maps['shades'][source_xy[:,1],source_xy[:,0]]
    source4=np.clip((samples*4096).astype(int),0,4095);donor_rgb=maps['basecolor4k'][source4[:,1],source4[:,0]]
    layers=maps['layers'].copy();shades=maps['shades'].copy();decoded=maps['decoded'].copy()
    base=maps['basecolor4k'].copy();old_mapped=raster_audit(value['uv'],1024)[1]>=0
    max_distance=0.
    for size in (1024,4096):
        owners=raster_audit(uv,size)[1];target=(owners>=0)&new[np.maximum(owners,0)]
        yy,xx=np.where(target);which=owners[yy,xx]
        t=uv[which]*size;ab,ac=t[:,1]-t[:,0],t[:,2]-t[:,0];delta=np.c_[xx+.5,yy+.5]-t[:,0]
        den=ab[:,0]*ac[:,1]-ab[:,1]*ac[:,0]
        a=(delta[:,0]*ac[:,1]-delta[:,1]*ac[:,0])/den;b=(ab[:,0]*delta[:,1]-ab[:,1]*delta[:,0])/den
        pos=np.einsum('sk,skc->sc',np.c_[1-a-b,a,b],v[f[which]])
        distance,index=tree.query(pos,k=4);max_distance=max(max_distance,float(distance[:,0].max()))
        w=1/np.maximum(distance,1e-7);w/=w.sum(1,keepdims=True)
        if size==1024:
            require(not np.any(target&old_mapped),'New charts overwrite protected baseline texels')
            picked=np.rint((donor_shades[index]*w).sum(1)).clip(0,254).astype(np.uint8)
            shades[yy,xx]=picked;layers[yy,xx]=1;decoded[yy,xx]=maps['hairPalette'][rows['1'],picked]
            # Carry only the new chart into its reserved gutter.
            from scipy.ndimage import distance_transform_edt
            grow=binary_dilation(target,structure=np.ones((9,9)))&~old_mapped
            nearest=distance_transform_edt(~target,return_distances=False,return_indices=True)
            shades[grow]=shades[tuple(nearest[:,grow])];layers[grow]=1;decoded[grow]=decoded[tuple(nearest[:,grow])]
        else:
            base[yy,xx]=np.rint((donor_rgb[index]*w[:,:,None]).sum(1)).clip(0,255).astype(np.uint8)
            from scipy.ndimage import distance_transform_edt
            old4=raster_audit(value['uv'],4096)[1]>=0
            grow=binary_dilation(target,iterations=16)&~old4
            nearest=distance_transform_edt(~target,return_distances=False,return_indices=True)
            base[grow]=base[tuple(nearest[:,grow])]
    require(max_distance<=.1*plan['width'],'New patch donor lies outside the local hair region')
    require(np.array_equal(shades[old_mapped],maps['shades'][old_mapped])
            and np.array_equal(layers[old_mapped],maps['layers'][old_mapped]),'Protected runtime texels changed')
    output=Path(output);output.mkdir()
    Image.fromarray(base).save(output/'basecolor-4096.png')
    Image.fromarray(layers).save(output/'ownership-1024.png')
    Image.fromarray(shades).save(output/'shades-1024.png')
    Image.fromarray(decoded).save(output/'decoded-1024.png')
    return {'basecolor':pin(output/'basecolor-4096.png'),'ownership':pin(output/'ownership-1024.png'),
            'shades':pin(output/'shades-1024.png'),'decoded':pin(output/'decoded-1024.png'),
            'protectedRuntimeTexels':int(old_mapped.sum()),'maximumDonorDistance':max_distance}



def retained_hair_evidence(evidence, before_shades, before_layers, shades, layers):
    # The historical tie is rounded to three decimals. Subtract its rounding
    # uncertainty and assume every changed old hair texel belonged to that tie.
    # Added hair gets no tie credit. This is a conservative lower bound.
    old=before_layers==1;current=layers==1
    count=int(old.sum());total=int(current.sum())
    require(count==evidence['hairTexels'] and count>0 and total>0,'Hair evidence pixel counts differ')
    unchanged=int((old & current & (before_shades==shades)).sum())
    tied=max(0.,(evidence['endTie']-.0005)*count-(count-unchanged))
    return {**evidence,'unchangedHairTexels':unchanged,'outputHairTexels':total,
            'lowerBound':min(1.,tied/total)}


def repair(source,output,bindings,policy):
    recipe=policy['localSeal'];require(recipe.get('sourceSha256')==pin(source)['sha256'] and recipe.get('reviewed') is True
        and isinstance(recipe.get('notes'),str) and recipe['notes'].strip(),'Review and bind the exact local-repair source')
    require(policy.get('neck') is None and policy.get('triangleBudget',20000)==20000,'Local seal preserves the no-neck head and 20K budget')
    value,data,maps=read_bundle(source)
    output=Path(output);folder=output.parent
    write_mesh(folder/'master.glb',value['positions'],value['faces'],value['uv'],value['normals'])
    v,f,birth,plan,closure=close_geometry(value,bindings,recipe)
    uv,normals,new,packing=restore_uv(value,v,f,birth)
    write_mesh(output,v,f,uv,normals)
    result=audit(output);require(result['passed'],'Local closure failed topology/intersection audit')
    # Audit is also repeated by unwrap, with the unchanged coverage/gutter floors.
    geometry=mesh(output)
    check=next(views(geometry,bindings['embree']['path'],recipe.get('size',512),[recipe['view']]))[1]
    points=np.einsum('ij,ijk->ik',check['bary'],geometry['positions'][geometry['faces'][check['face']]])
    core=plan['core'].ravel()
    closed=check['hit'][core] & ((points[core]@plan['toward'])>plan['level']-.05*plan['width'])
    require(closed.all(),'The reviewed cavity still exposes its inner wall')
    closure.append({'cavityRays':int(core.sum()),'sealedRays':int(closed.sum())})
    images=transfer_maps(value,v,f,uv,new,plan,maps,data['rows'],folder/'local-maps')
    evidence={}
    if 'hairEndTieEvidence' in data:
        kept=retained_hair_evidence(data['hairEndTieEvidence'],maps['shades'],maps['layers'],
            np.asarray(Image.open(images['shades']['path'])),np.asarray(Image.open(images['ownership']['path'])))
        evidence['hairEndTieEvidence']=np.array(json.dumps(kept,sort_keys=True))
    np.savez_compressed(folder/'local-maps/runtime-color.npz',**evidence,kind=np.array('headkit-stock-runtime-v1'),
        shades=np.asarray(Image.open(images['shades']['path'])),layers=np.asarray(Image.open(images['ownership']['path'])),
        rgb=np.asarray(Image.open(images['decoded']['path'])),rows=np.array(json.dumps(data['rows'],sort_keys=True)),
        geometryFingerprint=np.array(geometry_fingerprint(geometry)))
    images['runtimeColor']=pin(folder/'local-maps/runtime-color.npz')
    report={'source':pin(output),'master':pin(folder/'master.glb'),'baseline':pin(source),'passed':True,
        'topology':result['topology'],'crossings':result['crossings'],'triangleBudget':20000,'neck':None,
        'localSeal':{'closurePresets':closure,'newCharts':int(new.sum()),'packing':packing,'images':images,
                     'baselineRows':data['rows'],'geometryFingerprint':geometry_fingerprint(geometry)},
        'visualReviewRequired':True}
    write(folder/'local-repair.json',report,fresh=True)
    return report
