"""Preview-only two-bone leg constraints; authored native clips stay immutable."""
import numpy as np
from .morph_preview_pose_v13 import evaluate_adjusted,native_keys_hash

def require(value,message):
    if not value:raise ValueError(message)

def shortest_rotation(source,target):
    a=np.asarray(source,float);b=np.asarray(target,float);an=np.linalg.norm(a);bn=np.linalg.norm(b)
    require(an>1e-12 and bn>1e-12,'Nondegenerate bone vectors required');a=a/an;b=b/bn
    cross=np.cross(a,b);s=float(np.linalg.norm(cross));c=float(np.clip(np.dot(a,b),-1,1))
    if s<1e-12:
        if c>0:return np.eye(3)
        basis=np.eye(3)[int(np.argmin(np.abs(a)))];axis=np.cross(a,basis);axis/=np.linalg.norm(axis)
        return 2*np.outer(axis,axis)-np.eye(3)
    k=np.array([[0,-cross[2],cross[1]],[cross[2],0,-cross[0]],[-cross[1],cross[0],0]])
    return np.eye(3)+k+k@k*((1-c)/(s*s))

def two_bone_ik(hip,knee,foot,target,standing_knee=None):
    hip,knee,foot,target=[np.asarray(p,float) for p in (hip,knee,foot,target)]
    require(all(p.shape==(3,) and np.isfinite(p).all() for p in (hip,knee,foot,target)),'Finite leg anchors required')
    upper=float(np.linalg.norm(knee-hip));lower=float(np.linalg.norm(foot-knee));require(min(upper,lower)>1e-10,'Degenerate fitted leg length')
    delta=target-hip;distance=float(np.linalg.norm(delta));pole_basis='current native fitted knee plane'
    if distance>1e-12:axis=delta/distance
    else:
        axis=foot-hip
        if np.linalg.norm(axis)<1e-12:axis=knee-hip
        axis/=np.linalg.norm(axis)
    minimum=abs(upper-lower);maximum=upper+lower;reachable_distance=float(np.clip(distance,minimum,maximum))
    # At equal lengths and a target exactly at the hip there is a continuum of
    # folded solutions. Keep the fitted first-bone direction as the pole.
    if reachable_distance<1e-12:
        new_knee=hip+(knee-hip)/upper*upper;reachable=hip.copy();pole_basis='zero-distance folded source-knee direction';shell='equal-length-zero-distance-fold'
    else:
        pole=knee-hip;pole-=np.dot(pole,axis)*axis
        if np.linalg.norm(pole)<1e-10 and standing_knee is not None:
            pole=np.asarray(standing_knee,float)-hip;pole-=np.dot(pole,axis)*axis;pole_basis='canonical standing knee pole'
        if np.linalg.norm(pole)<1e-10:
            basis=np.eye(3)[int(np.argmin(np.abs(axis)))];pole=basis-np.dot(basis,axis)*axis;pole_basis='stable orthogonal numerical fallback for straight knee; no anatomical target'
        pole/=np.linalg.norm(pole)
        # At the exact reach shells the geometry is collinear. Subtracting
        # upper**2-along**2 can manufacture a sqrt(eps) knee bend after a
        # bind/pose matrix roundtrip. Evaluate these analytic cases exactly;
        # this does not enlarge reach or snap a genuinely interior target.
        if reachable_distance==maximum:
            along=upper;radius=0.;shell='outer-exact-collinear'
        elif reachable_distance==minimum:
            along=upper if upper>=lower else -upper;radius=0.;shell='inner-exact-collinear'
        else:
            along=(upper*upper-lower*lower+reachable_distance*reachable_distance)/(2*reachable_distance)
            # Factored triangle area avoids catastrophic cancellation near
            # either shell while preserving genuine interior knee bend.
            area4=(maximum-reachable_distance)*(maximum+reachable_distance)*(reachable_distance-minimum)*(reachable_distance+minimum)
            radius=float(np.sqrt(max(0.,area4))/(2*reachable_distance));shell='interior-fixed-length'
        new_knee=hip+along*axis+radius*pole;reachable=hip+reachable_distance*axis
    return new_knee,reachable,{'lengthsMeters':{'upper':upper,'lower':lower},'requestedFootMeters':target.tolist(),'reachableFootMeters':reachable.tolist(),'reachClamped':distance<minimum-1e-12 or distance>maximum+1e-12,'requestedDistanceFromHipMeters':distance,'reachableDistanceFromHipMeters':reachable_distance,'reachIntervalMeters':[minimum,maximum],'kneePoleBasis':pole_basis,'reachShellSolution':shell,'kneeRadiusMeters':0. if reachable_distance<1e-12 else radius,'requestedReachResidualMeters':float(np.linalg.norm(reachable-target))}

def evaluate_constrained(baseline,clip,time,stage_result,preserve=False):
    """Return full evaluated world frames and a no-approval constraint receipt.

    Target feet follow native source motion relative to each candidate's own
    standing foot. They are never locked to a fabricated image/floor target.
    Static corrections are composed before this transient preview-only IK.
    """
    before=native_keys_hash(baseline);scale=float(stage_result['uniformScale']);require(np.isfinite(scale) and scale>0,'Positive stature scale required')
    offsets=stage_result.get('localRotationOffsets',stage_result.get('localRotationCorrections'))
    native=evaluate_adjusted(baseline,clip,time,stage_result['localPositions'],scale,local_rotation_offsets=offsets)
    standing={n:np.asarray(m,float) for n,m in stage_result['standingFrames'].items()}
    require(set(native)==set(standing),'Complete standing frames required')
    standing_identity=clip=='pause1' and time==0
    if preserve or standing_identity:
        result={n:(standing[n].copy() if standing_identity else m.copy()) for n,m in native.items()}
        require(native_keys_hash(baseline)==before,'Native keys changed during identity preview')
        return result,{'kind':'native-trajectory-two-bone-preview-v14a','preserveHumanFitIdentity':bool(preserve),'standingIdentityPreserved':standing_identity,'constraintsApplied':False,'upperWorldFramesExact':True,'legs':{},'nativeKeysSha256Before':before,'nativeKeysSha256After':before,'assetApprovalCreated':False,'motionAcceptance':False,'productionAccepted':False}
    source_locals=stage_result['sourceLocalPositions'];source=evaluate_adjusted(baseline,clip,time,source_locals,1.)
    source_standing=evaluate_adjusted(baseline,'pause1',0,source_locals,1.)
    overrides={};legs={};leg_roots=set()
    for side in ('l','r'):
        hip_name=side+'thigh_g';knee_name=side+'shin_g';foot_name=side+'foot_g';leg_roots.add(hip_name)
        require(all(n in native for n in (hip_name,knee_name,foot_name)),'Complete native two-bone leg required')
        hip=native[hip_name][:3,3];knee=native[knee_name][:3,3];foot=native[foot_name][:3,3]
        target=standing[foot_name][:3,3]+scale*(source[foot_name][:3,3]-source_standing[foot_name][:3,3])
        if np.linalg.norm(target-foot)<1e-12:
            new_knee=knee.copy();reachable=foot.copy();info={'lengthsMeters':{'upper':float(np.linalg.norm(knee-hip)),'lower':float(np.linalg.norm(foot-knee))},'requestedFootMeters':target.tolist(),'reachableFootMeters':reachable.tolist(),'reachClamped':False,'kneePoleBasis':'exact fitted native pose; target already met','requestedReachResidualMeters':0.}
        else:new_knee,reachable,info=two_bone_ik(hip,knee,foot,target,standing[knee_name][:3,3])
        new_hip=native[hip_name].copy();new_hip[:3,:3]=shortest_rotation(knee-hip,new_knee-hip)@new_hip[:3,:3]
        new_shin=native[knee_name].copy();new_shin[:3,:3]=shortest_rotation(foot-knee,reachable-new_knee)@new_shin[:3,:3];new_shin[:3,3]=new_knee
        new_foot=native[foot_name].copy();new_foot[:3,3]=reachable
        overrides.update({hip_name:new_hip,knee_name:new_shin,foot_name:new_foot})
        info.update({'hipJoint':hip_name,'kneeJoint':knee_name,'footJoint':foot_name,'actualFootMeters':reachable.tolist(),'actualKneeMeters':new_knee.tolist(),'requestedResidualMeters':float(np.linalg.norm(reachable-target)),'reachableResidualMeters':0.,'actualLengthsMeters':{'upper':float(np.linalg.norm(new_knee-hip)),'lower':float(np.linalg.norm(reachable-new_knee))},'footOrientationPreserved':np.array_equal(new_foot[:3,:3],native[foot_name][:3,:3]),'targetTrajectoryBasis':'own candidate standing foot + statureScale * unit source native trajectory from source standing'})
        legs[side]=info
    skeleton=baseline['skeleton'];affected={};result={};visiting=set()
    def in_leg(name):
        if name in affected:return affected[name]
        parent=skeleton[name]['parent'];affected[name]=name in leg_roots or (parent!='null' and in_leg(parent));return affected[name]
    def visit(name):
        if name in result:return result[name]
        require(name not in visiting,'Cyclic native hierarchy');visiting.add(name);parent=skeleton[name]['parent']
        if name in overrides:world=overrides[name].copy()
        elif not in_leg(name):world=native[name].copy()
        else:
            require(parent!='null','Leg descendant must have a parent')
            parent_world=visit(parent)
            if np.array_equal(parent_world[:3,:3],native[parent][:3,:3]):
                world=native[name].copy();world[:3,3]+=parent_world[:3,3]-native[parent][:3,3]
            else:
                local=np.linalg.inv(native[parent])@native[name];world=parent_world@local
        result[name]=world;visiting.remove(name);return world
    for name in native:visit(name)
    protected=[n for n in native if not in_leg(n)]
    require(all(np.array_equal(result[n],native[n]) for n in protected),'Protected pelvis/upper world frames changed')
    require(all(np.isfinite(m).all() and np.allclose(m[:3,:3].T@m[:3,:3],np.eye(3),atol=1e-9,rtol=0) and abs(np.linalg.det(m[:3,:3])-1)<1e-9 for m in result.values()),'Finite proper rigid constraint frames required')
    after=native_keys_hash(baseline);require(after==before,'Native orientation/breathing keys changed')
    return result,{'kind':'native-trajectory-two-bone-preview-v14a','constraintsApplied':True,'rotationOnlyPreview':True,'localPositionsOrClipsWritten':False,'preserveHumanFitIdentity':False,'standingIdentityPreserved':False,'upperWorldFramesExact':True,'protectedWorldFrameNames':protected,'legs':legs,'nativeKeysSha256Before':before,'nativeKeysSha256After':after,'targetFootFloorNormalized':False,'boneStretchApplied':False,'childPropagation':'native old-local transform composed once with constrained parent; foot world rotation counter-preserved','assetApprovalCreated':False,'motionAcceptance':False,'productionAccepted':False,'limitations':['Two-bone joint targets do not certify foot surface planting or triangle contact in motion','Unreachable native-relative targets clamp to exact fixed-length reach and remain explicit residuals','Transient pose constraints are preview-only; broader clips/runtime validation remain required']}
