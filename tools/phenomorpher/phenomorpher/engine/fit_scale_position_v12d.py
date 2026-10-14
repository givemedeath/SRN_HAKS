"""Canonical-standing, free-proxy uniform-part scale/position preview only.

No game model, animation, anisotropic deformation or connector acceptance is
created. Native orientations and breathing are replayed by the pose helper.
"""
import hashlib
import copy
import numpy as np
from .target_contract import PART_JOINTS
from .silhouette_model import measure
from .morph_preview_pose_v10 import evaluate_accepted,evaluate_adjusted,pose_rigid_meshes,local_positions_from_world_frames

FIT_PARTS=('pelvis','chest','bicepl','bicepr','forel','forer','legl','legr','shinl','shinr','footl','footr')
EDGE_OWNER={'torso_g':'pelvis','neck_g':'chest','head_g':'neck',
 'lbicep_g':'chest','rbicep_g':'chest','lthigh_g':'pelvis','rthigh_g':'pelvis',
 'lforearm_g':'bicepl','rforearm_g':'bicepr','lhand_g':'forel','rhand_g':'forer',
 'lshin_g':'legl','rshin_g':'legr','lfoot_g':'shinl','rfoot_g':'shinr'}
SEGMENT_PARTS={'upperArmProjectedLength':('bicepl','bicepr'),'forearmProjectedLength':('forel','forer'),'shinProjectedLength':('shinl','shinr')}
SEGMENT_JOINTS={'upperArmProjectedLength':(('lbicep_g','lforearm_g'),('rbicep_g','rforearm_g')),
 'forearmProjectedLength':(('lforearm_g','lhand_g'),('rforearm_g','rhand_g')),
 'shinProjectedLength':(('lshin_g','lfoot_g'),('rshin_g','rfoot_g'))}


def geometry_hash(meshes):
    h=hashlib.sha256()
    for m in meshes:
        h.update((m['part']+'\0'+m['name']+'\0').encode());h.update(bytes([bool(m.get('render',True))]))
        for values,dtype in ((m['position'],'<f8'),(m['faces'],'<i8')):
            a=np.asarray(values,dtype=dtype);h.update(np.asarray(a.shape,dtype='<i8').tobytes());h.update(a.tobytes())
    return h.hexdigest()


def copy_meshes(meshes):
    return [{**m,'position':np.asarray(m['position'],float).copy(),'faces':np.asarray(m['faces']).copy()} for m in meshes]


def owning_edge(name,hierarchy):
    if name in EDGE_OWNER:return EDGE_OWNER[name]
    inverse={joint:part for part,joint in PART_JOINTS.items()};parent=hierarchy[name];seen=set()
    while parent!='null' and parent not in seen:
        if parent in inverse:return inverse[parent]
        seen.add(parent);parent=hierarchy[parent]
    return None


def connected_coefficients(source_frames,hierarchy,parts,uniform_scale):
    """Linear positions with shared endpoints; scalar owner per source edge."""
    index={p:i for i,p in enumerate(parts)};n=len(parts)+3;result={};visiting=set()
    def visit(name):
        if name in result:return result[name]
        if name in visiting:raise ValueError('Cyclic canonical hierarchy')
        visiting.add(name);parent=hierarchy[name];source=np.asarray(source_frames[name])[:3,3]
        if parent=='null':
            c=source*uniform_scale;a=np.zeros((3,n));a[:,-3:]=np.eye(3)
        else:
            c,a=visit(parent);c=c.copy();a=a.copy();delta=source-np.asarray(source_frames[parent])[:3,3];owner=owning_edge(name,hierarchy)
            if owner in index:a[:,index[owner]]+=delta
            else:c+=delta*uniform_scale
        result[name]=(c,a);visiting.remove(name);return result[name]
    for name in source_frames:visit(name)
    return result


def bounded_least_squares(a,b,lower,upper):
    """Small fixed scale-placement system; active bounds, no general solver."""
    a=np.asarray(a,float);b=np.asarray(b,float);lower=np.asarray(lower,float);upper=np.asarray(upper,float)
    free=list(range(a.shape[1]));fixed={};x=np.zeros(a.shape[1])
    for _ in range(a.shape[1]+1):
        rhs=b.copy()
        if fixed:
            ids=list(fixed);rhs-=a[:,ids]@np.array([fixed[i] for i in ids])
        if free:x[free]=np.linalg.lstsq(a[:,free],rhs,rcond=None)[0]
        for i,value in fixed.items():x[i]=value
        violated=[i for i in free if x[i]<lower[i] or x[i]>upper[i]]
        if not violated:return x
        for i in violated:fixed[i]=float(np.clip(x[i],lower[i],upper[i]));free.remove(i)
    raise ValueError('Scale-placement active-bound solve did not close')


def free_proxy_coefficients(source_frames,hierarchy,parts,uniform_scale,rows):
    """Keep native rotations and unobserved Y; fit visible proxy X/Z exactly.

    Unmeasured descendants inherit their parent's translation and source edge.
    A measured child overrides its X/Z pivot, so surface gaps are deliberately
    reported rather than pretending fixed source directions fit a new pose.
    """
    result=connected_coefficients(source_frames,hierarchy,parts,uniform_scale)
    index={p:i for i,p in enumerate(parts)};inverse={j:p for p,j in PART_JOINTS.items()}
    anchors={}
    for name,row in rows.items():
        joint=row.get('sourceJointName');proxy=row.get('sourceProxyPositionMeters');target=row.get('targetProxyPositionXZMeters')
        if joint not in source_frames or proxy is None or target is None:continue
        proxy=np.asarray(proxy,float);target=np.asarray(target,float)
        if proxy.shape!=(3,) or target.shape!=(2,) or not np.isfinite(proxy).all() or not np.isfinite(target).all():
            raise ValueError('Finite source/target surface proxies required')
        if joint in anchors:raise ValueError('Duplicate canonical proxy joint: '+joint)
        anchors[joint]=((row.get('part') or inverse.get(joint)),proxy-source_frames[joint][:3,3],target)
    output={}
    def visit(name):
        if name in output:return output[name]
        parent=hierarchy[name];c,a=result[name];c=c.copy();a=a.copy()
        if parent!='null':
            pc,pa=visit(parent);oldc,olda=result[parent];c+=pc-oldc;a+=pa-olda
        if name in anchors:
            part,offset,target=anchors[name]
            for axis,value in zip((0,2),target):
                c[axis]=value;a[axis]=0.
                if part in index:a[axis,index[part]]=-offset[axis]
                else:c[axis]-=offset[axis]*uniform_scale
        output[name]=(c,a);return output[name]
    for name in source_frames:visit(name)
    return output


def constrained_least_squares(a,b,equality,values,inequality,limits,initial):
    """Convex small scale system: exact equalities and persistent bounds Gx<=h.

    Violating vertex constraints remain active until their KKT multiplier says
    they can be released; this prevents alternating left/right sole selection.
    """
    a=np.asarray(a,float);b=np.asarray(b,float);e=np.asarray(equality,float);v=np.asarray(values,float)
    g=np.asarray(inequality,float);h=np.asarray(limits,float);x=np.asarray(initial,float).copy()
    q=a.T@a;rhs=a.T@b;active=[];history=[]
    for iteration in range(256):
        c=np.concatenate((e,g[active]),axis=0) if active else e
        d=np.concatenate((v,h[active])) if active else v
        matrix=np.block([[q,c.T],[c,np.zeros((len(c),len(c)))]])
        solved=np.linalg.lstsq(matrix,np.concatenate((rhs,d)),rcond=1e-12)[0];x=solved[:len(x)]
        eq_error=float(np.max(np.abs(c@x-d))) if len(c) else 0.
        if eq_error>1e-7:raise ValueError('Incompatible fixed proxy/stature constraints: '+str(eq_error))
        violation=g@x-h;worst=int(np.argmax(violation));maximum=float(violation[worst])
        history.append({'iteration':iteration,'maximumInequalityViolationMeters':maximum,'activeConstraints':len(active)})
        if maximum>1e-9:
            if worst in active:raise ValueError('Active stature inequality failed to close')
            active.append(worst);continue
        multipliers=solved[len(x)+len(e):]
        if len(active) and float(np.min(multipliers)) < -1e-8:
            active.pop(int(np.argmin(multipliers)));continue
        return x,history
    raise ValueError('Persistent stature/scale active set failed to converge')

def persistent_foot_sole_indices(vertex_owners,initial_z):
    """Select one lowest actual rendered vertex independently per owned foot."""
    result={}
    for part in ('footl','footr'):
        owned=[i for i,row in enumerate(vertex_owners) if row[0]==part]
        if not owned:raise ValueError('Both rendered feet required for standing floor authority: '+part)
        result[part]=min(owned,key=lambda i:float(initial_z[i]))
    return result


def backsolve_local_deltas(baseline,scaled_source_frames,target_frames,uniform_scale,source_local_positions=None):
    skeleton=baseline['skeleton'];deltas={};positions={}
    for name,node in skeleton.items():
        parent=node['parent'];world_delta=np.asarray(target_frames[name])[:3,3]-np.asarray(scaled_source_frames[name])[:3,3]
        if parent=='null':local_delta=world_delta
        else:
            parent_delta=np.asarray(target_frames[parent])[:3,3]-np.asarray(scaled_source_frames[parent])[:3,3]
            local_delta=np.linalg.solve(np.asarray(scaled_source_frames[parent])[:3,:3],world_delta-parent_delta)
        source_local=(source_local_positions or {}).get(name,node['position'])
        positions[name]=np.asarray(source_local,float)*uniform_scale+local_delta
        deltas[name]=positions[name]-np.asarray(node['position'],float)*uniform_scale
    return positions,deltas


def static_bind_frames(skeleton,positions):
    result={};visiting=set()
    def visit(name):
        if name in result:return result[name]
        if name in visiting:raise ValueError('Cyclic static hierarchy')
        visiting.add(name);node=skeleton[name];local=np.eye(4);local[:3,:3]=node['rotation'];local[:3,3]=positions[name]
        result[name]=local if node['parent']=='null' else visit(node['parent'])@local
        visiting.remove(name);return result[name]
    for name in skeleton:visit(name)
    return result


def mesh_joint(mesh):
    return mesh['name'] if mesh['part']=='rig' else PART_JOINTS[mesh['part']]


def uniform_parts(source_meshes,source_frames,target_frames,scales,default_scale):
    result=[]
    for mesh in source_meshes:
        joint=mesh_joint(mesh);s=float(scales.get(mesh['part'],default_scale))
        if not np.isfinite(s) or s<=0:raise ValueError('Positive uniform part scale required')
        source=np.asarray(source_frames[joint]);target=np.asarray(target_frames[joint])
        if not np.allclose(source[:3,:3],target[:3,:3],atol=1e-10,rtol=0):raise ValueError('Uniform placement cannot change orientations')
        points=target[:3,3]+s*(np.asarray(mesh['position'])-source[:3,3])
        result.append({**mesh,'position':points,'faces':np.asarray(mesh['faces']).copy(),'attachmentFrame':target.tolist()})
    return result


def standing_to_bind(meshes,standing_frames,bind_frames):
    out=[]
    for mesh in meshes:
        joint=mesh_joint(mesh);delta=np.asarray(bind_frames[joint])@np.linalg.inv(np.asarray(standing_frames[joint]))
        points=np.asarray(mesh['position'])@delta[:3,:3].T+delta[:3,3]
        out.append({**mesh,'position':points,'faces':np.asarray(mesh['faces']).copy(),'attachmentFrame':np.asarray(bind_frames[joint]).tolist()})
    return out


def fit_stage1(bind_meshes,bind_frames,baseline,packet,source_proxies=None,preserve=False):
    source_locals=local_positions_from_world_frames(baseline['skeleton'],bind_frames)
    for name,node in baseline['skeleton'].items():source_locals.setdefault(name,np.asarray(node['position'],float).copy())
    source_frames=evaluate_adjusted(baseline,'pause1',0.,source_locals,uniform_scale=1.)
    source_meshes=pose_rigid_meshes(bind_meshes,bind_frames,source_frames)
    source_measure=measure(source_meshes,{k:v[:3,3].tolist() for k,v in source_frames.items()})
    height=float(packet['targetStatureMeters']);source_height=source_measure['bindStatureMeters']
    if not np.isfinite(height) or height<=0:raise ValueError('Positive target stature required')
    scale=1. if preserve else height/source_height
    scaled_frames=evaluate_adjusted(baseline,'pause1',0.,{k:np.asarray(v)*scale for k,v in source_locals.items()},uniform_scale=scale)
    skeleton=baseline['skeleton'];hierarchy={k:v['parent'] for k,v in skeleton.items()}
    calibration=packet.get('canonicalCalibration',{});rows=source_proxies or calibration.get('sourceSurfaceCentersAndPivotOffsets',{})
    if not isinstance(rows,dict):raise ValueError('Named canonical source/reference proxy rows required')
    # Reference X is centered on its pelvis axis; native accepted standing may
    # carry an actor translation. Fit all observed/unobserved parts in ONE frame.
    reference_origin=0. if preserve else float(scaled_frames['pelvis_g'][0,3])
    rows=copy.deepcopy(rows)
    for row in rows.values():
        if row.get('targetProxyPositionXZMeters') is not None:
            row['targetProxyPositionXZMeters'][0]+=reference_origin
        if row.get('targetProxyPositionMeters') is not None:
            row['targetProxyPositionMeters'][0]+=reference_origin
    parts=[p for p in FIT_PARTS if any(m['part']==p for m in bind_meshes)]
    coefficients=free_proxy_coefficients(source_frames,hierarchy,parts,scale,rows);index={p:i for i,p in enumerate(parts)}
    a=[];b=[];observations=[];priors=[];n=len(parts)+3
    inverse={joint:part for part,joint in PART_JOINTS.items()}
    for name,row in rows.items():
        joint=row.get('sourceJointName');source_proxy=row.get('sourceProxyPositionMeters')
        target=row.get('targetProxyPositionXZMeters');target3=row.get('targetProxyPositionMeters')
        if joint not in coefficients or source_proxy is None or (target is None and target3 is None):continue
        source_proxy=np.asarray(source_proxy,float);offset=source_proxy-source_frames[joint][:3,3]
        if source_proxy.shape!=(3,) or not np.isfinite(source_proxy).all():raise ValueError('Finite canonical surface proxy required')
        part=(row.get('part') or inverse.get(joint));c,coef=coefficients[joint];c=c.copy();coef=coef.copy()
        if part in index:coef[:,index[part]]+=offset
        else:c+=offset*scale
        target_xz=np.asarray(target if target is not None else [target3[0],target3[2]],float)
        if target_xz.shape!=(2,) or not np.isfinite(target_xz).all():raise ValueError('Finite frontal target proxy required')
        uncertainty=max(.01,float(row.get('uncertaintyMeters') or .02));weight=1/uncertainty
        for axis,value in zip((0,2),target_xz):a.append(coef[axis]*weight);b.append((value-c[axis])*weight)
        observations.append({'name':name,'joint':joint,'part':part,'offset':offset,'targetXZ':target_xz,'c':c,'coef':coef,'uncertainty':uncertainty})
    # Dimensionless scale priors retain unknown anatomy; measured major lengths
    # get explicit stronger priors without silently treating them as rotations.
    for part in parts:
        row=np.zeros(n);row[index[part]]=4.;a.append(row);b.append(4.*scale);priors.append({'part':part,'scale':scale,'basis':'unknown dimensions retain stature-scale donor'})
    for key,pairs in SEGMENT_JOINTS.items():
        target=packet.get('proposedTargets',{}).get(key,{}).get('modelFittingMeters')
        if target is None:continue
        for part,(start,end) in zip(SEGMENT_PARTS[key],pairs):
            if part not in index:continue
            length=np.linalg.norm(source_frames[end][:3,3]-source_frames[start][:3,3])
            if length<=1e-10:continue
            wanted=float(target)/length;row=np.zeros(n);row[index[part]]=12.;a.append(row);b.append(12.*wanted)
            priors.append({'part':part,'scale':wanted,'basis':key,'requestedMeters':float(target)})
    for axis in range(3):
        row=np.zeros(n);row[len(parts)+axis]=.25 if axis!=1 else 25.;a.append(row);b.append(0.)
    def vertex_expression(mesh,point):
        joint=mesh_joint(mesh);c,coef=coefficients[joint];c=c.copy();coef=coef.copy()
        offset=point-source_frames[joint][:3,3]
        if mesh['part'] in index:coef[:,index[mesh['part']]]+=offset
        else:c+=offset*scale
        return c,coef
    stature_equations=[];target_ground=float(calibration.get('targetGroundZMeters',0.))
    def active_stature_rows(candidate):
        extrema=[]
        for mesh in source_meshes:
            if not mesh.get('render',True) or not len(mesh['position']):continue
            values=[]
            for point in mesh['position']:
                c,coef=vertex_expression(mesh,point);values.append(c[2]+coef[2]@candidate)
            extrema.extend([(float(min(values)),mesh,mesh['position'][int(np.argmin(values))]),
                            (float(max(values)),mesh,mesh['position'][int(np.argmax(values))])])
        low=min(extrema,key=lambda x:x[0]);high=max(extrema,key=lambda x:x[0]);rows=[];rhs=[]
        for record,target in ((low,target_ground),(high,target_ground+height)):
            c,coef=vertex_expression(record[1],record[2]);rows.append(coef[2]*1000000.);rhs.append((target-c[2])*1000000.)
        return rows,rhs,high[0]-low[0]
    if preserve:
        part_scales={p:1. for p in PART_JOINTS};target_frames={k:v.copy() for k,v in source_frames.items()};local_positions={k:np.asarray(v).copy() for k,v in source_locals.items()};local_deltas={k:local_positions[k]-np.asarray(skeleton[k]['position']) for k in skeleton};replay=target_frames
        fitted=copy_meshes(source_meshes);target_bind={k:np.asarray(v).copy() for k,v in bind_frames.items()};fitted_bind=copy_meshes(bind_meshes);solution=np.array([1.]*len(parts)+[0.,0.,0.]);roundtrip=0.;ground_shift=0.
    else:
        lo=np.array([.05*scale]*len(parts)+[-np.inf]*3);hi=np.array([4.*scale]*len(parts)+[np.inf]*3)
        solution=bounded_least_squares(a,b,lo,hi)
        vertex_rows=[];vertex_constants=[];vertex_owners=[]
        for mesh in source_meshes:
            if not mesh.get('render',True):continue
            for point_index,point in enumerate(mesh['position']):
                c,coef=vertex_expression(mesh,point)
                vertex_constants.append(c[2]);vertex_rows.append(coef[2]);vertex_owners.append((mesh['part'],mesh['name'],point_index))
        vr=np.asarray(vertex_rows);vc=np.asarray(vertex_constants)
        initial_z=vc+vr@solution
        soles=persistent_foot_sole_indices(vertex_owners,initial_z);high=int(np.argmax(initial_z))
        # Each foot is grounded persistently, not merely bounded above floor.
        # Uniform owned-foot scale and proxy/pivot calibration remain one solve.
        eq=[vr[i] for i in soles.values()]+[vr[high]]
        eq_values=[target_ground-vc[i] for i in soles.values()]+[target_ground+height-vc[high]]
        bounds_a=[-vr,vr];bounds_b=[vc-target_ground,target_ground+height-vc]
        for i in range(len(parts)):
            row=np.zeros(n);row[i]=1.
            bounds_a.extend((row[None,:],-row[None,:]));bounds_b.extend((np.array([hi[i]]),np.array([-lo[i]])))
        solution,stature_equations=constrained_least_squares(a,b,eq,eq_values,np.concatenate(bounds_a),np.concatenate(bounds_b),solution)
        stature_equations.append({'persistentSoleVertices':{p:list(vertex_owners[i]) for p,i in soles.items()},'persistentCrownVertex':list(vertex_owners[high]),
                                 'allRenderedVerticesBounded':len(vr)})
        part_scales={p:scale for p in PART_JOINTS};part_scales.update({p:float(solution[i]) for p,i in index.items()})
        target_frames={k:np.asarray(v).copy() for k,v in source_frames.items()}
        for name,(c,coef) in coefficients.items():target_frames[name][:3,3]=c+coef@solution
        fitted=uniform_parts(source_meshes,source_frames,target_frames,part_scales,scale)
        floor=measure(fitted,{k:v[:3,3].tolist() for k,v in target_frames.items()})['boundsMeters'][0][2]
        ground_shift=target_ground-floor
        for frame in target_frames.values():frame[2,3]+=ground_shift
        for mesh in fitted:
            mesh['position'][:,2]+=ground_shift;mesh['attachmentFrame']=target_frames[mesh_joint(mesh)].tolist()
        solution[-1]+=ground_shift
        local_positions,local_deltas=backsolve_local_deltas(baseline,scaled_frames,target_frames,scale,source_locals)
        replay=evaluate_adjusted(baseline,'pause1',0.,local_positions,uniform_scale=scale)
        roundtrip=max(float(np.max(np.abs(replay[k]-target_frames[k]))) for k in target_frames)
        if roundtrip>1e-8:raise ValueError('Canonical native controller roundtrip failed: '+str(roundtrip))
        target_bind=static_bind_frames(skeleton,local_positions);fitted_bind=standing_to_bind(fitted,target_frames,target_bind)
        common=set(target_bind)&set(bind_frames)
        if any(not np.allclose(target_bind[k][:3,:3],np.asarray(bind_frames[k])[:3,:3],atol=1e-8,rtol=0) for k in common):
            raise ValueError('Accepted static skeleton and latest donor bind orientations disagree; no silent reorientation')
    proxy_residuals={}
    for row in observations:
        predicted=target_frames[row['joint']][:3,3]+part_scales.get(row['part'],scale)*row['offset']
        actual=predicted[[0,2]];difference=actual-row['targetXZ']
        proxy_residuals[row['name']]={'targetXZMeters':row['targetXZ'].tolist(),'actualXZMeters':actual.tolist(),'residualXZMeters':difference.tolist(),'distanceMeters':float(np.linalg.norm(difference)),
            'uncertaintyMeters':row['uncertainty'],'sourcePivotOffsetMeters':(-row['offset']).tolist(),
            'measurementBasis':'transported source surface-centre correspondence; not re-extracted destination union envelope',
            'status':'free frontal-proxy placement with fixed native orientations; surface join reconciliation pending'}
    edges=[]
    for name,parent in hierarchy.items():
        if parent=='null':continue
        owner=owning_edge(name,hierarchy);s=part_scales.get(owner,scale)
        expected=s*(source_frames[name][:3,3]-source_frames[parent][:3,3]);actual=target_frames[name][:3,3]-target_frames[parent][:3,3]
        edges.append({'child':name,'parent':parent,'owner':owner,'uniformScale':s,'endpointResidualMeters':float(np.linalg.norm(actual-expected))})
    fitted_measure=measure(fitted,{k:v[:3,3].tolist() for k,v in target_frames.items()})
    sole_heights={p:float(np.concatenate([m['position'] for m in fitted if m['part']==p and m.get('render',True)])[:,2].min()) for p in ('footl','footr') if any(m['part']==p and m.get('render',True) for m in fitted)}
    if not preserve and (len(sole_heights)!=2 or any(abs(z-target_ground)>1e-7 for z in sole_heights.values())):raise ValueError('Bilateral standing soles failed common floor constraints')
    receipt={'kind':'canonical-standing-uniform-part-scale-position-v12d','bilateralStandingSoleZMeters':sole_heights,'bilateralStandingFloorConstraintsApplied':not preserve,'referenceWorldOriginXMeters':reference_origin,'referenceCoordinateBasis':'reference X relative to pelvis; native global translation retained consistently','placementMode':'free-frontal-proxy-pivots-native-rotations',
        'pose':{'clip':'pause1','timeSeconds':0.,'acceptedNativeOrientationAndBreathingReplayed':True},
        'uniformScale':scale,'partScales':part_scales,'sourceGeometryHash':geometry_hash(bind_meshes),'previewBindGeometryHash':geometry_hash(fitted_bind),
        'sourceStandingGeometryHash':geometry_hash(source_meshes),'previewStandingGeometryHash':geometry_hash(fitted),'identityPreserved':bool(preserve),
        'rigRotationsUnchanged':all(np.allclose(target_frames[k][:3,:3],source_frames[k][:3,:3],atol=1e-12,rtol=0) for k in target_frames),
        'controllerRoundtripMaximumMatrixError':roundtrip,'sourceStandingStatureMeters':source_height,'targetStatureMeters':height,
        'actualStandingStatureMeters':fitted_measure['bindStatureMeters'],'statureResidualMeters':fitted_measure['bindStatureMeters']-height,
        'groundTranslationMeters':ground_shift,'individualFootNudgesApplied':False,'proxyResiduals':proxy_residuals,'scalePriors':priors,'connectedEdges':edges,
        'statureActiveVertexEquations':stature_equations,'statureSolved':abs(fitted_measure['bindStatureMeters']-height)<1e-6,
        'maximumConnectedEndpointResidualMeters':max((r['endpointResidualMeters'] for r in edges),default=0.),'shapeMorphApplied':False,'widthDepthFittingApplied':False,
        'partUniformityProof':{'transformation':'targetPivot + positivePartScale * (sourceStandingVertex - sourcePivot)','meshNodesPreserved':True,'facesPreserved':True},
        'limitations':['Measured surface proxies set frontal X/Z positions; unobserved depth retains native standing lineage.',
            'Independent uniform part scales and new joint positions can leave endpoint gaps or overlaps; stage-two coupled joins require geometry review.',
            'Hidden hip anatomy, arm depth, native motion contact, runtime and production acceptance remain unverified.'],
        'fittingTargetsApproved':False,'motionFitValidated':False,'productionAccepted':False}
    receipt['constraints']={'positiveUniformPartScales':all(np.isfinite(s) and s>0 for s in part_scales.values()),
        'statureSolved':receipt['statureSolved'],'statureResidualMeters':receipt['statureResidualMeters'],
        'rigRotationsUnchanged':receipt['rigRotationsUnchanged'],'nativeControllerRoundtripMaximumMatrixError':roundtrip,
        'connectedEndpointMaximumResidualMeters':receipt['maximumConnectedEndpointResidualMeters'],
        'surfaceJoinAcceptance':'pending; pivot continuity does not approve surface contour continuity'}
    if preserve and geometry_hash(bind_meshes)!=geometry_hash(fitted_bind):raise ValueError('Human Fit bind identity failed')
    return {'uniformScale':scale,'sourceBindFrames':{k:np.asarray(v).copy() for k,v in bind_frames.items()},'sourceStandingMeshes':source_meshes,'sourceStandingFrames':source_frames,
        'standingMeshes':fitted,'standingFrames':target_frames,'bindMeshes':fitted_bind,'bindFrames':target_bind,
        'sourceLocalPositions':{k:np.asarray(v).tolist() for k,v in source_locals.items()},
        'localPositions':{k:np.asarray(v).tolist() for k,v in local_positions.items()},'localDeltas':{k:np.asarray(v).tolist() for k,v in local_deltas.items()},
        'sourceRelativeLocalDeltas':{k:(np.asarray(local_positions[k])-np.asarray(source_locals[k])*scale).tolist() for k in local_positions},
        'partScales':part_scales,'receipt':receipt}
