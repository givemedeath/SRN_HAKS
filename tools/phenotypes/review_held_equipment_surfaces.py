"""Read-only held surface probes; engine attachment hypotheses never imply acceptance."""
import argparse
import json
from pathlib import Path
import shutil
import shlex
import numpy as np
from audit_native_static_equipment import decode_static_equipment
from retarget import nodes, transforms
import shared_toolchain
import target_contract as contract

ARTIFACT_ROOT=Path(__file__).resolve().parents[2]/'output/phenotypes'
SOCKETS=('head_g','head','lhand_g','rhand_g','lhand','rhand','handconjure','headconjure')


def segment_distances(p,q,a,b):
    """Broadcast exact closest distances between finite closed line segments."""
    u=q-p;v=b-a;w=p-a
    aa=np.sum(u*u,axis=-1);bb=np.sum(u*v,axis=-1);cc=np.sum(v*v,axis=-1)
    dd=np.sum(u*w,axis=-1);ee=np.sum(v*w,axis=-1);den=aa*cc-bb*bb
    valid=den>1e-24
    s=np.clip(np.divide(bb*ee-cc*dd,den,out=np.zeros_like(den),where=valid),0,1)
    t=np.clip(np.divide(bb*s+ee,cc,out=np.zeros_like(den),where=cc>1e-24),0,1)
    s=np.clip(np.divide(bb*t-dd,aa,out=np.zeros_like(den),where=aa>1e-24),0,1)
    return np.linalg.norm(w+s[...,None]*u-t[...,None]*v,axis=-1)


def point_triangle_distances(points,triangles):
    """Broadcast point-to-closed-triangle distance, retaining degenerate edges."""
    p=np.asarray(points,float);t=np.asarray(triangles,float)
    a,b,c=t[...,0,:],t[...,1,:],t[...,2,:];u=b-a;v=c-a;w=p-a
    normal=np.cross(u,v);nn=np.sum(normal*normal,axis=-1)
    signed=np.sum(w*normal,axis=-1)
    projected=w-np.divide(signed,nn,out=np.zeros_like(signed),where=nn>1e-24)[...,None]*normal
    uu=np.sum(u*u,axis=-1);uv=np.sum(u*v,axis=-1);vv=np.sum(v*v,axis=-1)
    pu=np.sum(projected*u,axis=-1);pv=np.sum(projected*v,axis=-1);den=uu*vv-uv*uv
    x=np.divide(pu*vv-pv*uv,den,out=np.zeros_like(pu),where=den>1e-24)
    y=np.divide(pv*uu-pu*uv,den,out=np.zeros_like(pv),where=den>1e-24)
    inside=(nn>1e-24)&(x>=-1e-12)&(y>=-1e-12)&(x+y<=1+1e-12)
    plane=np.divide(np.abs(signed),np.sqrt(nn),out=np.full_like(signed,np.inf),where=nn>1e-24)
    edges=np.minimum.reduce([segment_distances(p,p,a,b),segment_distances(p,p,b,c),segment_distances(p,p,c,a)])
    return np.where(inside,np.minimum(plane,edges),edges)


def segment_triangle_hits(p,q,triangles):
    """Finite nonparallel segment/triangle hits; coplanar contact uses distance."""
    a,b,c=triangles[...,0,:],triangles[...,1,:],triangles[...,2,:]
    direction=q-p;e1=b-a;e2=c-a;h=np.cross(direction,e2);det=np.sum(e1*h,axis=-1)
    inv=np.divide(1.,det,out=np.zeros_like(det),where=np.abs(det)>1e-14)
    s=p-a;u=inv*np.sum(s*h,axis=-1);qq=np.cross(s,e1)
    v=inv*np.sum(direction*qq,axis=-1);along=inv*np.sum(e2*qq,axis=-1)
    return (np.abs(det)>1e-14)&(u>=-1e-12)&(v>=-1e-12)&(u+v<=1+1e-12)&(along>=-1e-12)&(along<=1+1e-12)


def surface_distance(first,second,tolerance=1e-8):
    """Triangle surface distance/contact only: no AABB or solid penetration claim."""
    first=np.asarray(first,float);second=np.asarray(second,float)
    if any(a.ndim!=3 or a.shape[1:]!=(3,3) or not len(a) or not np.isfinite(a).all() for a in (first,second)):
        raise ValueError('Finite nonempty triangle surfaces required')
    if not np.isfinite(tolerance) or tolerance<=0:raise ValueError('Positive surface contact tolerance required')
    best=np.inf;pair=None;contacts=0;degenerate=[]
    for a in (first,second):degenerate.append(int((np.linalg.norm(np.cross(a[:,1]-a[:,0],a[:,2]-a[:,0]),axis=1)<1e-12).sum()))
    bstart=second;bend=np.roll(second,-1,axis=1)
    for index,triangle in enumerate(first):
        # All primitive pairs are checked. There is no bounds-based collision decision.
        vertex_a=point_triangle_distances(triangle[:,None,:],second[None,:,:,:]).min(axis=0)
        vertex_b=point_triangle_distances(second,triangle).min(axis=1)
        edge=segment_distances(triangle[:,None,None,:],np.roll(triangle,-1,axis=0)[:,None,None,:],bstart[None,:,:,:],bend[None,:,:,:]).min(axis=(0,2))
        forward=segment_triangle_hits(triangle[:,None,:],np.roll(triangle,-1,axis=0)[:,None,:],second[None,:,:,:]).any(axis=0)
        reverse=segment_triangle_hits(bstart,bend,triangle).any(axis=1)
        distances=np.minimum.reduce((vertex_a,vertex_b,edge));distances=np.where(forward|reverse,0.,distances)
        contacts+=int((distances<=tolerance).sum());j=int(distances.argmin())
        if float(distances[j])<best:best=float(distances[j]);pair=[index,j]
    return {'minimumSurfaceDistanceMeters':best,'minimumTrianglePair':pair,'surfaceContactTrianglePairs':contacts,
            'surfaceContactToleranceMeters':tolerance,'triangleCounts':[len(first),len(second)],'degenerateTriangleCounts':degenerate,
            'method':'All vertex/triangle, edge/edge and finite segment/triangle pairs; no AABB classification.',
            'solidContainmentChecked':False,'penetrationDepthMeasured':False,'collisionAccepted':False}


def placed_surface(triangles,frame,scale):
    frame=np.asarray(frame,float)
    if frame.shape!=(4,4) or not np.isfinite(frame).all() or not np.allclose(frame[3],[0,0,0,1],atol=1e-12,rtol=0):raise ValueError('Rigid affine socket frame required')
    if not np.allclose(frame[:3,:3].T@frame[:3,:3],np.eye(3),atol=1e-8,rtol=0) or abs(np.linalg.det(frame[:3,:3])-1)>1e-8:raise ValueError('Proper socket rotation required')
    if not np.isfinite(scale) or scale<=0:raise ValueError('Positive explicit item-local scale required')
    return np.asarray(triangles,float)*scale@frame[:3,:3].T+frame[:3,3]


def verify_held_binding(held,target_path,data):
    contract.verify_binding(held['target'],target_path,data,'runtime')
    for name in SOCKETS:
        if not np.allclose(held['target']['socketFramesNwn'][name],contract.frame(data,name,'runtime'),atol=1e-12,rtol=0):raise ValueError('Frozen held socket frame changed: '+name)
    if held['profilesAccepted'] is not False or held['clientAccepted'] is not False:raise ValueError('Unaccepted measurement inputs required')


def native_surface(path):
    audit=decode_static_equipment(path.read_bytes())
    meshes=[mesh for mesh in audit['meshes'] if mesh['render']]
    if not meshes:raise ValueError('No rendered native triangle surface: '+path.name)
    triangles=np.concatenate([mesh['worldPositions'][mesh['faces']] for mesh in meshes])
    return triangles,{'hierarchyIdentity':audit['hierarchyIdentity'],'duplicateLabels':audit['duplicateNames'],
                      'renderedMeshes':len(meshes),'renderedVertices':sum(len(m['positions']) for m in meshes),'triangles':len(triangles),
                      'nativeNodeOffsets':[m['offset'] for m in meshes]}


def structural_equivalence(source,frozen):
    from freeze_target_rig import immutable_structure,canonical_sha
    if immutable_structure(source)!=immutable_structure(frozen):raise ValueError('Structural target changed; no measurement equivalence')
    return canonical_sha(immutable_structure(source))


def freeze_bridge(source_path,source,frozen_path,freeze_path,pin):
    frozen=contract.load(frozen_path);receipt=json.loads(freeze_path.read_text())
    if receipt.get('kind')!='offline-rig-freeze' or receipt.get('rigStructureOfflineAccepted') is not True:raise ValueError('Explicit accepted offline structural freeze required')
    if receipt['sourceContractSha256']!=contract.sha(source_path) or Path(receipt['sourceContract']).resolve()!=source_path.resolve():raise ValueError('Freeze source contract differs')
    contract.verify_binding(receipt['target'],frozen_path,frozen,'working')
    for gate in ('bodyGeometryAccepted','materialsAccepted','equipmentAccepted','clientAccepted','productionAccepted','bodyReceiptsRebound'):
        if receipt.get(gate) is not False:raise ValueError('Freeze acceptance scope exceeds measurement-only bridge: '+gate)
    pin(frozen_path);pin(freeze_path)
    helper=Path(__file__).with_name('freeze_target_rig.py')
    expected=next(value for path,value in frozen['frozenInputs'].items() if Path(path).name=='freeze_target_rig.py')
    pin(helper,expected)
    structure=structural_equivalence(source,frozen)
    if receipt['structureSha256']!=structure:raise ValueError('Frozen structure digest differs')
    expected_models={(space,model) for space in ('working','runtime') for model in source['rig']['privateAliases'].values()}
    rows=receipt['modelCopies']
    if len(rows)!=len(expected_models) or {(row['space'],row['model']) for row in rows}!=expected_models:raise ValueError('Exact private model byte closure required')
    for row in rows:
        original=source_path.parent/row['space']/'ascii'/(row['model']+'.mdl');destination=frozen_path.parent/row['space']/'ascii'/(row['model']+'.mdl')
        if Path(row['source']).resolve()!=original.resolve() or Path(row['destination']).resolve()!=destination.resolve():raise ValueError('Private model source/destination ownership differs')
        pin(original,row['sha256']);pin(destination,row['sha256'])
    return {'kind':'held-measurement-structural-equivalence-only','structuralTarget':contract.binding(frozen_path,frozen,'runtime'),
            'freezeReceipt':{'path':str(freeze_path.resolve()),'sha256':contract.sha(freeze_path)},'structureSha256':structure,
            'allWorkingRuntimeFramesExact':True,'allPrivateModelCopiesByteExact':True,'privateModelCopiesChecked':len(rows),
            'measurementGeometryEquivalent':True,'originalMeasurementReceiptBindingChanged':False,'priorReceiptsRebound':False,'priorProfilesAdopted':False,
            'equipmentAcceptanceInherited':False,'clientAcceptanceInherited':False,
            'limitation':'Numerical equivalence only. The main measurement receipt retains its v6 binding; new target/profile/geometry/client acceptance must be explicit.'}

def review(args):
    shared_toolchain.load(args.shared_toolchain,args.migration);data=contract.load(args.target_contract)
    inventory=json.loads(args.inventory.read_text());held=json.loads(args.held_receipt.read_text());baseline=json.loads(args.stock_baseline.read_text())
    verify_held_binding(held,args.target_contract,data)
    if held['sourceInventory']['sha256']!=contract.sha(args.inventory):raise ValueError('Held source inventory differs')
    output=args.output.resolve()
    if output.exists() or not output.is_relative_to(ARTIFACT_ROOT.resolve()):raise ValueError('Fresh isolated held diagnostic output required')
    pins={}
    def freeze(path,expected=None):
        path=Path(path).resolve();actual=contract.sha(path)
        if expected is not None and actual!=expected:raise ValueError('Frozen source changed: '+str(path))
        pins[str(path)]=actual;return path
    for path in (args.inventory,args.held_receipt,args.native_source_audit,args.stock_baseline,args.target_contract,args.shared_toolchain,args.migration,Path(__file__),Path(__file__).with_name('audit_native_static_equipment.py'),Path(__file__).with_name('retarget.py'),Path(__file__).with_name('target_contract.py')):freeze(path)
    bridge=None
    if bool(args.structural_target_contract)!=bool(args.structural_freeze):raise ValueError('Both structural target and freeze receipt required')
    if args.structural_target_contract:bridge=freeze_bridge(args.target_contract,data,args.structural_target_contract,args.structural_freeze,freeze)
    stock=args.stock_baseline.resolve().parent;resources={row['name']:row for row in baseline['resources']}
    native_reference=json.loads(args.native_source_audit.read_text())
    if native_reference.get('kind')!='native-held-static-input-audit' or native_reference['decoderSha256']!=contract.sha(Path(__file__).with_name('audit_native_static_equipment.py')):raise ValueError('Frozen native source decoder differs')
    appearance=freeze(stock/'raw/appearance.2da',resources['appearance.2da']['sha256'])
    table_lines=[line.strip() for line in appearance.read_text(encoding='cp1252').splitlines() if line.strip()]
    if table_lines[0]!='2DA V2.0':raise ValueError('Expected installed appearance table')
    headers=shlex.split(table_lines[1]);table_rows={}
    for number in (2,6):
        line=next(line for line in table_lines[2:] if line.split()[0]==str(number));values=shlex.split(line)
        if len(values)!=len(headers)+1:raise ValueError('Appearance row field count differs')
        table_rows[str(number)]={key.lower():value for key,value in zip(headers,values[1:])}
    if table_rows['6']['label']!='Human' or float(table_rows['6']['helmet_scale_m'])!=1.05:raise ValueError('Installed Human male helmet input differs')
    skeleton=freeze(stock/'ascii/pmh0.mdl',resources['pmh0.mdl']['asciiSha256']);source_frames=transforms(nodes(skeleton.read_text(encoding='ascii')))
    local={};metadata={};body_human={};body_runtime={}
    for part,joint in (('head','head_g'),('neck','neck_g')):
        name='pmh0_'+part+'001.mdl';path=freeze(stock/'raw'/name,resources[name]['sha256'])
        local[part],metadata[part]=native_surface(path)
        body_human[part]=placed_surface(local[part],source_frames[joint],1.)
        body_runtime[part]=placed_surface(local[part],contract.frame(data,joint,'runtime'),data['rig']['runtimeScale'])
    equipment={row['resource']:row for row in inventory['models']};weapons={row['resource']:row for row in held['weaponSamples']}
    selections={'helmet001':['helm_001.mdl'],'helmet019':['helm_019.mdl'],
                'longsword011':['wswls_b_011.mdl','wswls_m_011.mdl','wswls_t_011.mdl'],
                'largeShield011':['ashls_b_011.mdl','ashls_m_011.mdl','ashls_t_011.mdl']}
    selected={};component_sources={}
    for label,names in selections.items():
        pieces=[];info=[]
        for name in names:
            row=equipment.get(name) or weapons.get(name)
            if row is None:raise ValueError('Declared frozen representative missing: '+name)
            raw=freeze(row['rawPath'],row.get('rawSha256') or row['sha256']);freeze(row['asciiPath'],row['asciiSha256'])
            tri,meta=native_surface(raw);pieces.append(tri);info.append({'resource':name,'rawPath':str(raw),'sha256':contract.sha(raw),**meta})
        selected[label]=np.concatenate(pieces);component_sources[label]=info
    output.mkdir(parents=True);archive={'source_'+key:value for key,value in local.items()};probes=[]
    for label,tri in selected.items():
        origin=point_triangle_distances(np.zeros(3),tri).min()
        if label.startswith('helmet'):
            stock_surface=placed_surface(tri,source_frames['head_g'],1.05)
            for socket in ('head_g','head'):
                placed=placed_surface(tri,contract.frame(data,socket,'runtime'),1.05*data['rig']['runtimeScale']);archive[label+'_'+socket]=placed
                probes.append({'resourceGroup':label,'socketHypothesis':socket,'itemScaleHypothesis':1.05*data['rig']['runtimeScale'],
                    'sourceHumanComparisonSocketHypothesis':'head_g','sourceHumanItemScaleHypothesis':1.05,
                    'sourceOriginToNearestSurfaceMeters':float(origin),'targetSocketFrame':contract.frame(data,socket,'runtime').tolist(),
                    'sourceSocketFrame':source_frames['head_g'].tolist(),'itemAxesPolicy':'Source-exported axes with no added rotation or translation.',
                    'sourceHumanSurfaceDistances':{key:surface_distance(stock_surface,value) for key,value in body_human.items()},
                    'targetSurfaceDistances':{key:surface_distance(placed,value) for key,value in body_runtime.items()},
                    'engineSocketHypothesisAccepted':False,'engineItemScaleHypothesisAccepted':False,'bodyVisibilityAccepted':False,'gripAccepted':False,'collisionAccepted':False})
        else:
            sockets=('rhand','rhand_g') if label=='longsword011' else ('lhand','lhand_g')
            for socket in sockets:
                for scale in (1.,data['rig']['runtimeScale']):
                    placed=placed_surface(tri,contract.frame(data,socket,'runtime'),scale);archive[label+'_'+socket+'_'+str(scale)]=placed
                    probes.append({'resourceGroup':label,'socketHypothesis':socket,'itemScaleHypothesis':scale,'sourceOriginToNearestSurfaceMeters':float(origin),
                        'targetSocketFrame':contract.frame(data,socket,'runtime').tolist(),'sourceSocketFrame':source_frames[socket].tolist(),
                        'itemAxesPolicy':'Source-exported component axes/common origin; no added rotation, translation or composition offset.',
                        'targetSurfaceDistances':{key:surface_distance(placed,value) for key,value in body_runtime.items()},
                        'engineSocketHypothesisAccepted':False,'engineItemScaleHypothesisAccepted':False,'componentAssemblyAccepted':False,
                        'bodyVisibilityAccepted':False,'gripAccepted':False,'collisionAccepted':False})
    archive.update({'human_'+key:value for key,value in body_human.items()});archive.update({'target_'+key:value for key,value in body_runtime.items()})
    np.savez_compressed(output/'literal-triangle-probes.npz',**archive)
    for path,pin in pins.items():
        if contract.sha(path)!=pin:raise ValueError('Frozen source changed during diagnostic')
    shutil.copyfile(Path(__file__),output/'executed-review_held_equipment_surfaces.py')
    receipt={'schemaVersion':1,'kind':'target-held-equipment-surface-diagnostic',**contract.binding(args.target_contract,data,'runtime'),
             'coordinatePolicy':'Target body local geometry scaled once by runtimeScale and attached to declared target frame. Item-local probe scale is a separate explicit engine hypothesis; global item files never change.',
             'sourceMeasurements':{'path':str(args.held_receipt.resolve()),'sha256':contract.sha(args.held_receipt)},'nativeSourceAudit':{'path':str(args.native_source_audit.resolve()),'sha256':contract.sha(args.native_source_audit)},
             'sharedToolchain':{'path':str(args.shared_toolchain.resolve()),'sha256':contract.sha(args.shared_toolchain)},'toolMigration':{'path':str(args.migration.resolve()),'sha256':contract.sha(args.migration)},
             'sourceHumanSocketFrames':{key:source_frames[key].tolist() for key in SOCKETS},'targetSocketFrames':{key:contract.frame(data,key,'runtime').tolist() for key in SOCKETS},
             'provisionalBodySourceSurfaces':metadata,'representativeSourceComponents':component_sources,'probes':probes,'frozenInputs':pins,
             'installedAppearanceRows':table_rows,'appearanceTableSemantics':'Source row values only; HEAD_NAME does not establish the held attachment controller or engine item scale application.',
             'literalTriangles':{'path':str(output/'literal-triangle-probes.npz'),'sha256':contract.sha(output/'literal-triangle-probes.npz')},
             'structuralEquivalence':bridge,'globalResourcesUntouched':True,'geometryExported':False,'productionResourcesWritten':False,'runtimeSelectionChanged':False,
             'targetFrozen':data['rig'].get('pilotAccepted',False),'profilesAccepted':False,'collisionReviewsAccepted':False,'materialBindingsAccepted':False,'productionAccepted':False,'clientAccepted':False,
             'limitations':['Socket/scale alternatives are explicit unaccepted transform hypotheses, not engine placement proof.',
                            'Minimum surface distance/contact is not solid penetration, collision or body visibility proof.',
                            'Only original provisional stock head and neck surfaces are available; accepted gripping hand/forearm/torso/body surfaces remain pending.',
                            'Component common-origin placement is preserved; engine item component assembly is unverified.',
                            'Bind pose only; all motion, hidden head/neck behavior, handedness and engine item sizing require literal client evidence.',
                            'All held/global/Human/female resources remain read-only; any future target change invalidates this receipt binding.']}
    (output/'review.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'receipt':str(output/'review.json'),'sha256':contract.sha(output/'review.json'),'probes':len(probes),'collisionAccepted':False}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for field in ('inventory','held-receipt','native-source-audit','stock-baseline','target-contract','shared-toolchain','migration','output'):parser.add_argument('--'+field,type=Path,required=True)
    parser.add_argument('--structural-target-contract',type=Path);parser.add_argument('--structural-freeze',type=Path)
    review(parser.parse_args())


