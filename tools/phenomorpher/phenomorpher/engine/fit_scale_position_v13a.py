"""Connected native-pivot similarities with hard source-terminal contact gates."""
import numpy as np
import copy,hashlib,time
from .target_contract import PART_JOINTS
from .silhouette_model import measure
from .fit_scale_position_v12d import geometry_hash,copy_meshes
from .morph_preview_pose_v13 import evaluate_adjusted,pose_rigid_meshes,local_positions_from_world_frames,static_bind_frames,backsolve_canonical_local_positions
from .morph_coupled_v12d import terminal_mask,link_terminal_controls as original_link_terminal_controls

SEGMENTS={'bicepl':('lbicep_g','lforearm_g'),'bicepr':('rbicep_g','rforearm_g'),'forel':('lforearm_g','lhand_g'),'forer':('rforearm_g','rhand_g'),
 'legl':('lthigh_g','lshin_g'),'legr':('rthigh_g','rshin_g'),'shinl':('lshin_g','lfoot_g'),'shinr':('rshin_g','rfoot_g')}
LINKS=(('chest','pelvis'),('chest','bicepl'),('chest','bicepr'),('bicepl','forel'),('bicepr','forer'),('forel','handl'),('forer','handr'),('pelvis','legl'),('pelvis','legr'),('legl','shinl'),('legr','shinr'),('shinl','footl'),('shinr','footr'))

def require(value,message):
    if not value:raise ValueError(message)

def shortest_rotation(source,target):
    a=np.asarray(source,float);b=np.asarray(target,float);na=np.linalg.norm(a);nb=np.linalg.norm(b)
    require(na>1e-10 and nb>1e-10,'Nonzero source and destination segment required');a=a/na;b=b/nb;c=float(np.clip(a@b,-1.,1.));v=np.cross(a,b)
    if c>1.-1e-14:return np.eye(3)
    if c<-1.+1e-12:
        axis=np.cross(a,np.eye(3)[int(np.argmin(np.abs(a)))]);axis/=np.linalg.norm(axis);return 2*np.outer(axis,axis)-np.eye(3)
    k=np.array([[0.,-v[2],v[1]],[v[2],0.,-v[0]],[-v[1],v[0],0.]])
    result=np.eye(3)+k+k@k/(1.+c);require(np.allclose(result.T@result,np.eye(3),atol=1e-10) and np.linalg.det(result)>0.,'Proper rotation required');return result

def segment_similarity(source_start,source_end,target_start,target_end):
    a,b,c,d=[np.asarray(p,float) for p in (source_start,source_end,target_start,target_end)];rotation=shortest_rotation(b-a,d-c);scale=float(np.linalg.norm(d-c)/np.linalg.norm(b-a));require(np.isfinite(scale) and scale>0.,'Positive uniform segment scale required')
    return scale,rotation,c-scale*rotation@a

def triangles_intersect(a,b,tolerance=1e-9):
    """Convex triangle SAT including coplanar in-plane separation axes."""
    a=np.asarray(a,float);b=np.asarray(b,float);ea=np.roll(a,-1,axis=1)-a;eb=np.roll(b,-1,axis=1)-b
    na=np.cross(ea[:,0],ea[:,1]);nb=np.cross(eb[:,0],eb[:,1]);valid=(np.linalg.norm(na,axis=1)>1e-12)&(np.linalg.norm(nb,axis=1)>1e-12)
    axes=[na,nb]+[np.cross(ea[:,i],eb[:,j]) for i in range(3) for j in range(3)]+[np.cross(na,ea[:,i]) for i in range(3)]+[np.cross(nb,eb[:,i]) for i in range(3)]
    for axis in axes:
        norm=np.linalg.norm(axis,axis=1);unit=np.divide(axis,norm[:,None],out=np.zeros_like(axis),where=norm[:,None]>1e-12)
        pa=np.einsum('nvi,ni->nv',a,unit);pb=np.einsum('nvi,ni->nv',b,unit)
        separated=(pa.max(1)<pb.min(1)-tolerance)|(pb.max(1)<pa.min(1)-tolerance);valid&=~((norm>1e-12)&separated)
    return valid

def triangle_pair_distance(a,b):
    """Exact closed-triangle clearance, including edge-interior closest pairs."""
    a=np.asarray(a,float);b=np.asarray(b,float);best=np.full(len(a),np.inf)
    for points,tri in ((a,b),(b,a)):
        u,v,w=tri[:,0],tri[:,1],tri[:,2];normal=np.cross(v-u,w-u);den=np.sum(normal*normal,axis=1)
        for point in points.transpose(1,0,2):
            signed=np.sum((point-u)*normal,axis=1);projection=point-normal*np.divide(signed,den,out=np.zeros_like(signed),where=den>1e-24)[:,None]
            signs=[np.sum(np.cross(y-x,projection-x)*normal,axis=1) for x,y in ((u,v),(v,w),(w,u))]
            inside=(np.minimum.reduce(signs)>=-1e-15)&(den>1e-24)
            best=np.minimum(best,np.where(inside,signed*signed/np.maximum(den,1e-30),np.inf))
            for x,y in ((u,v),(v,w),(w,u)):
                edge=y-x;t=np.clip(np.sum((point-x)*edge,axis=1)/np.maximum(np.sum(edge*edge,axis=1),1e-30),0,1)
                best=np.minimum(best,np.sum((point-x-t[:,None]*edge)**2,axis=1))
    for i in range(3):
        for j in range(3):
            p=a[:,i];q=b[:,j];u=a[:,(i+1)%3]-p;v=b[:,(j+1)%3]-q;w=p-q
            aa=np.sum(u*u,axis=1);bb=np.sum(u*v,axis=1);cc=np.sum(v*v,axis=1);dd=np.sum(u*w,axis=1);ee=np.sum(v*w,axis=1);den=aa*cc-bb*bb
            x=np.divide(bb*ee-cc*dd,den,out=np.zeros_like(den),where=den>1e-24);y=np.divide(aa*ee-bb*dd,den,out=np.zeros_like(den),where=den>1e-24)
            interior=(den>1e-24)&(x>=0)&(x<=1)&(y>=0)&(y<=1)
            best=np.minimum(best,np.where(interior,np.sum((w+x[:,None]*u-y[:,None]*v)**2,axis=1),np.inf))
    return np.where(triangles_intersect(a,b),0.,np.sqrt(best))


def link_terminal_controls(left,right,source_frames):
    controls=original_link_terminal_controls(left,right,source_frames)
    if left=='chest' and right=='pelvis':
        pelvis=np.asarray(source_frames['pelvis_g'])[:3,3];torso=np.asarray(source_frames['torso_g'])[:3,3]
        if np.linalg.norm(torso-pelvis)<=1e-9:
            # The published male donor authors these pivots at the same point.
            # Native neck supplies the explicit longitudinal trunk direction;
            # it does not invent another attachment or omit the waist gate.
            neck=np.asarray(source_frames['neck_g'])[:3,3]
            require(np.linalg.norm(neck-pelvis)>1e-9,'Coincident chest/pelvis pivots have no native trunk axis')
            return (torso,neck,False),(pelvis,neck,True)
    return controls


def terminal_inventory(meshes,source_frames,left,right):
    controls=link_terminal_controls(left,right,source_frames);result=[]
    for part,control in zip((left,right),controls):
        rows=[]
        for index,m in enumerate(meshes):
            if m['part']!=part or not m.get('render',True):continue
            mask=terminal_mask(m['position'],*control);faces=np.asarray(m['faces']);selected=np.flatnonzero(mask[faces].any(1));rows.extend((index,int(i)) for i in selected)
        require(rows,'Source-owned terminal triangles unavailable: '+part);result.append(rows)
    return result

def terminal_contact(meshes,inventory):
    triangles=[np.asarray([meshes[i]['position'][meshes[i]['faces'][face]] for i,face in rows],float) for rows in inventory]
    a,b=triangles;blo=b.min(1);bhi=b.max(1);count=0;closest_bbox=np.inf;clearance=np.inf
    for begin in range(0,len(a),64):
        part=a[begin:begin+64];alo=part.min(1);ahi=part.max(1)
        delta=np.maximum(np.maximum(alo[:,None]-bhi[None],blo[None]-ahi[:,None]),0.);dist=np.linalg.norm(delta,axis=2);closest_bbox=min(closest_bbox,float(dist.min()))
        ia,ib=np.nonzero(dist<=1e-9)
        if len(ia):count+=int(triangles_intersect(part[ia],b[ib]).sum())
        if count:clearance=0.
        else:
            # AABB distance only prunes candidates; final clearance uses triangles.
            if not np.isfinite(clearance):
                ii,jj=np.unravel_index(np.argmin(dist),dist.shape);clearance=float(triangle_pair_distance(part[ii:ii+1],b[jj:jj+1])[0])
            ii,jj=np.nonzero(dist<=clearance+1e-12)
            if len(ii):clearance=min(clearance,float(triangle_pair_distance(part[ii],b[jj]).min()))
    return {'terminalTriangleCounts':[len(a),len(b)],'intersectingTrianglePairCount':count,'actualTerminalContact':count>0,'minimumTriangleClearanceMeters':clearance,'minimumAABBDistanceLowerBoundMeters':closest_bbox,'scope':'Actual source-owned terminal triangles intersect/touch; AABB lower bound is not a surface clearance claim'}

_SOURCE_TERMINAL_CACHE={}

def source_terminal_evidence(meshes,frames):
    """Immutable derived cache; every geometry/frame byte participates in its key."""
    digest=hashlib.sha256(geometry_hash(meshes).encode('ascii'))
    for name in sorted(frames):
        digest.update(name.encode('utf-8')+b'\0');digest.update(np.asarray(frames[name],dtype='<f8').tobytes())
    key=digest.hexdigest();started=time.monotonic();cached=key in _SOURCE_TERMINAL_CACHE
    if not cached:
        inventories={pair:terminal_inventory(meshes,frames,*pair) for pair in LINKS}
        contacts={':'.join(pair):terminal_contact(meshes,inv) for pair,inv in inventories.items()}
        _SOURCE_TERMINAL_CACHE[key]=copy.deepcopy((inventories,contacts))
    inventories,contacts=copy.deepcopy(_SOURCE_TERMINAL_CACHE[key])
    return inventories,contacts,{'cacheKey':key,'cacheHit':cached,'elapsedSeconds':time.monotonic()-started,'scope':'Derived source geometry plus every complete native canonical frame; returned values are isolated copies'}


def fit_stage1(bind_meshes,bind_frames,baseline,packet,source_proxies=None,preserve=False):
    local=local_positions_from_world_frames(baseline['skeleton'],bind_frames)
    for n,node in baseline['skeleton'].items():local.setdefault(n,np.asarray(node['position']).copy())
    source_frames=evaluate_adjusted(baseline,'pause1',0.,local,1.);source_meshes=pose_rigid_meshes(bind_meshes,bind_frames,source_frames);actual=measure(source_meshes,{n:f[:3,3].tolist() for n,f in source_frames.items()});height=float(packet['targetStatureMeters']);require(np.isfinite(height) and height>0,'Positive target stature required')
    scale=1. if preserve else height/actual['bindStatureMeters'];offsets={n:np.eye(3) for n in source_frames};inverse={joint:part for part,joint in PART_JOINTS.items()}
    if preserve:
        require(packet.get('slug') in ('human_male_fit','human_female_fit'),'Exact identity scope limited to two Human Fits')
        return {'uniformScale':1.,'sourceBindFrames':bind_frames,'sourceStandingMeshes':source_meshes,'sourceStandingFrames':source_frames,'standingMeshes':copy_meshes(source_meshes),'standingFrames':{n:f.copy() for n,f in source_frames.items()},'bindMeshes':copy_meshes(bind_meshes),'bindFrames':{n:np.asarray(f).copy() for n,f in bind_frames.items()},'sourceLocalPositions':{n:np.asarray(p).tolist() for n,p in local.items()},'localPositions':{n:np.asarray(p).tolist() for n,p in local.items()},'localDeltas':{n:(np.asarray(local[n])-np.asarray(baseline['skeleton'][n]['position'])).tolist() for n in local},'localRotationOffsets':{n:r.tolist() for n,r in offsets.items()},'localRotationCorrections':{n:r.tolist() for n,r in offsets.items()},'partScales':{p:1. for p in PART_JOINTS},'receipt':{'kind':'connected-similarity-stage1-v13a','identityPreserved':True,'uniformScale':1.,'partScales':{p:1. for p in PART_JOINTS},'shapeMorphApplied':False,'widthDepthFittingApplied':False,'rigRotationsUnchanged':True,'targetProxyAudit':'not applied; exact Human identity','bilateralStandingFloorConstraintsApplied':False,'controllerRoundtripMaximumMatrixError':0.,'surfaceJoinAcceptance':False,'productionAccepted':False,'fittingTargetsApproved':False}}
    rows=source_proxies or packet['canonicalCalibration']['sourceSurfaceCentersAndPivotOffsets'];origin=float(source_frames['pelvis_g'][0,3])*scale
    trunk=[m for m in source_meshes if m['part'] in ('pelvis','chest','neck','head') and m.get('render',True)];top=max(float(m['position'][:,2].max()) for m in trunk);ground=float(packet['canonicalCalibration'].get('targetGroundZMeters',0.));translation=np.array([0.,0.,ground+height-top*scale]);source_scaled={n:f[:3,3]*scale+translation for n,f in source_frames.items()};desired={n:p.copy() for n,p in source_scaled.items()}
    for row in rows.values():
        joint=row.get('sourceJointName');p=row.get('sourceProxyPositionMeters');target=row.get('targetProxyPositionXZMeters')
        if joint not in desired or p is None or target is None:continue
        diff=np.asarray(p)-source_frames[joint][:3,3];desired[joint][[0,2]]=np.asarray(target)+np.array([origin,0.])-scale*diff[[0,2]]
    inventories,source_contact,source_timing=source_terminal_evidence(source_meshes,source_frames);history=[];chosen=None;candidate_contact_started=time.monotonic()
    for alpha in (1.,.75,.5,.25,0.):
        positions={n:p.copy() for n,p in source_scaled.items()};transforms={p:(scale,np.eye(3),translation.copy()) for p in PART_JOINTS}
        for side in ('l','r'):
            shoulder=side+'bicep_g';elbow=side+'forearm_g';wrist=side+'hand_g';hip=side+'thigh_g';knee=side+'shin_g';ankle=side+'foot_g'
            for n in (elbow,wrist,knee):positions[n]=(1-alpha)*source_scaled[n]+alpha*desired[n]
            foot='foot'+side;points=np.concatenate([m['position'] for m in source_meshes if m['part']==foot and m.get('render',True)])
            positions[ankle]=(1-alpha)*source_scaled[ankle]+alpha*desired[ankle];positions[ankle][2]=ground+scale*(source_frames[ankle][2,3]-float(points[:,2].min()))
            transforms[foot]=(scale,np.eye(3),positions[ankle]-scale*source_frames[ankle][:3,3])
        for part,(start,end) in SEGMENTS.items():
            s,r,t=segment_similarity(source_frames[start][:3,3],source_frames[end][:3,3],positions[start],positions[end]);require(.05*scale<=s<=4.*scale,'Uniform segment scale outside explicit positive bounds');transforms[part]=(s,r,t)
        for hand,fore in [('handl','forel'),('handr','forer')]:transforms[hand]=transforms[fore]
        world={};visiting=set()
        def visit(n):
            if n in world:return world[n]
            require(n not in visiting,'Cyclic native hierarchy');visiting.add(n);parent=baseline['skeleton'][n]['parent'];part=inverse.get(n)
            if part in transforms:s,r,t=transforms[part];m=source_frames[n].copy();m[:3,:3]=r@source_frames[n][:3,:3];m[:3,3]=s*r@source_frames[n][:3,3]+t
            elif parent=='null':m=source_frames[n].copy();m[:3,3]=source_scaled[n]
            else:
                pm=visit(parent);parentpart=inverse.get(parent);s=transforms.get(parentpart,(scale,None,None))[0];r=pm[:3,:3]@source_frames[parent][:3,:3].T;m=source_frames[n].copy();m[:3,:3]=r@source_frames[n][:3,:3];m[:3,3]=pm[:3,3]+s*r@(source_frames[n][:3,3]-source_frames[parent][:3,3])
            world[n]=m;visiting.remove(n);return m
        for n in source_frames:visit(n)
        fitted=[]
        for mesh in source_meshes:
            part=mesh['part'];joint=mesh['name'] if part=='rig' else PART_JOINTS[part];s,r,t=transforms.get(part,(scale,world[joint][:3,:3]@source_frames[joint][:3,:3].T,None))
            if t is None:t=world[joint][:3,3]-s*r@source_frames[joint][:3,3]
            fitted.append({**mesh,'position':np.asarray(mesh['position'])@(s*r).T+t,'faces':np.asarray(mesh['faces']).copy(),'attachmentFrame':world[joint].tolist()})
        contacts={':'.join(pair):terminal_contact(fitted,inv) for pair,inv in inventories.items()}
        for pair in inventories:
            key=':'.join(pair);row=contacts[key];limit=source_contact[key]['minimumTriangleClearanceMeters']*min(transforms[pair[0]][0],transforms[pair[1]][0]);row.update({'sourceAuthoredClearanceMeters':source_contact[key]['minimumTriangleClearanceMeters'],'maximumSourceCalibratedClearanceMeters':limit,'sourceCalibratedTerminalGatePassed':row['minimumTriangleClearanceMeters']<=limit+1e-8,'numericalEpsilonMeters':1e-8})
        passed=all(row['sourceCalibratedTerminalGatePassed'] for row in contacts.values());history.append({'referenceSeekingFraction':alpha,'terminalContacts':contacts,'allRequiredTerminalContacts':passed})
        if passed:chosen=(world,fitted,transforms,alpha,contacts);break
    require(chosen is not None,'Stage1 terminal contact not feasible using connected uniform similarities; no pre-morph success claimed: '+str([k for k,v in history[-1]['terminalContacts'].items() if not v['sourceCalibratedTerminalGatePassed']]))
    world,fitted,transforms,alpha,contacts=chosen
    for n,node in baseline['skeleton'].items():
        parent=node['parent'];native=source_frames[n][:3,:3] if parent=='null' else source_frames[parent][:3,:3].T@source_frames[n][:3,:3];wanted=world[n][:3,:3] if parent=='null' else world[parent][:3,:3].T@world[n][:3,:3];offsets[n]=wanted@native.T
    for n in ('pelvis_g','torso_g'):require(np.allclose(offsets[n],np.eye(3),atol=1e-10),'Protected hips level / upper lean local orientation changed')
    positions,backsolved_offsets=backsolve_canonical_local_positions(baseline,world,scale);require(all(np.allclose(backsolved_offsets[n],offsets[n],atol=1e-10) for n in offsets),'Independent canonical local rotation backsolve differs');replay=evaluate_adjusted(baseline,'pause1',0.,positions,scale,local_rotation_offsets=offsets);error=max(float(np.max(np.abs(replay[n]-world[n]))) for n in world);require(error<1e-8,'Corrected local rig/native key canonical replay failed')
    corrected_bind=static_bind_frames(baseline['skeleton'],positions,local_rotation_corrections=offsets);fitted_bind=pose_rigid_meshes(fitted,world,corrected_bind);measurement=measure(fitted,{n:f[:3,3].tolist() for n,f in world.items()});sole={p:float(np.concatenate([m['position'] for m in fitted if m['part']==p and m.get('render',True)])[:,2].min()) for p in ('footl','footr')};require(all(abs(z-ground)<1e-8 for z in sole.values()),'Connected chain planted-foot constraint failed')
    scales={p:s for p,(s,r,t) in transforms.items()};proxy={}
    for key,row in rows.items():
        joint=row.get('sourceJointName');point=row.get('sourceProxyPositionMeters');target=row.get('targetProxyPositionXZMeters');part=inverse.get(joint)
        if point is None or target is None or part not in transforms:continue
        s,r,t=transforms[part];actual=(s*r@np.asarray(point)+t)[[0,2]];goal=np.asarray(target)+[origin,0.];proxy[key]={'actualXZMeters':actual.tolist(),'targetXZMeters':goal.tolist(),'residualXZMeters':(actual-goal).tolist(),'distanceMeters':float(np.linalg.norm(actual-goal)),'uncertaintyMeters':row.get('uncertaintyMeters'),'status':'contact-priority connected similarity; visible reference residual retained'}
    receipt={'kind':'connected-similarity-stage1-v13a','identityPreserved':False,'uniformScale':scale,'partScales':scales,'referenceWorldOriginXMeters':origin,'referenceSeekingFraction':alpha,'contactPriorityOverLandmarkCloseness':True,'contactTrials':history,'sourceTerminalContacts':source_contact,'sourceTerminalEvidenceTiming':source_timing,'candidateContactTrialsElapsedSeconds':time.monotonic()-candidate_contact_started,'sourceTerminalSelectionPolicy':'Native projected terminal quarter; coincident pelvis/torso uses their shared pivot-to-neck native trunk axis for opposing waist bands','requiredTerminalContacts':contacts,'allRequiredTerminalContacts':all(r['actualTerminalContact'] for r in contacts.values()),'allRequiredSourceCalibratedTerminalGates':True,'localRotationOffsets':{n:r.tolist() for n,r in offsets.items()},'rotationComposition':'constant left-local offset @ original native local rotation keys','pelvisAndTorsoLocalOrientationOffsetsIdentity':True,'nativeKeysEdited':False,'shapeMorphApplied':False,'widthDepthFittingApplied':False,'rigRotationsUnchanged':False,'bilateralStandingFloorConstraintsApplied':True,'bilateralStandingSoleZMeters':sole,'actualStandingStatureMeters':measurement['bindStatureMeters'],'targetStatureMeters':height,'statureResidualMeters':measurement['bindStatureMeters']-height,'proxyResiduals':proxy,'controllerRoundtripMaximumMatrixError':error,'sourceGeometryHash':geometry_hash(bind_meshes),'previewBindGeometryHash':geometry_hash(fitted_bind),'individualFootVertexNudgesApplied':False,'surfaceJoinAcceptance':False,'motionFitValidated':False,'productionAccepted':False,'fittingTargetsApproved':False,'limitations':['Actual standing terminal triangle contact is not motion/contour/production acceptance.','Reference seeking is reduced if connector contact fails; unsupported hidden hip targets are not invented.','Rig orientations are changed by explicit static local offsets while accepted native keys remain untouched.']}
    return {'uniformScale':scale,'sourceBindFrames':bind_frames,'sourceStandingMeshes':source_meshes,'sourceStandingFrames':source_frames,'standingMeshes':fitted,'standingFrames':world,'bindMeshes':fitted_bind,'bindFrames':corrected_bind,'sourceLocalPositions':{n:np.asarray(p).tolist() for n,p in local.items()},'localPositions':{n:np.asarray(p).tolist() for n,p in positions.items()},'localDeltas':{n:(np.asarray(positions[n])-np.asarray(baseline['skeleton'][n]['position'])*scale).tolist() for n in positions},'localRotationOffsets':{n:r.tolist() for n,r in offsets.items()},'localRotationCorrections':{n:r.tolist() for n,r in offsets.items()},'partScales':scales,'receipt':receipt}
