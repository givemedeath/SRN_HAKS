"""Anatomy-first bounded similarities; no exact image-joint chase or motion IK."""
import time
import numpy as np
from .target_contract import PART_JOINTS
from .silhouette_model import measure
from .fit_scale_position_v12d import geometry_hash,copy_meshes
from .fit_scale_position_v13a import shortest_rotation,source_terminal_evidence,terminal_contact,LINKS
from .morph_preview_pose_v13 import (evaluate_adjusted,pose_rigid_meshes,local_positions_from_world_frames,
    backsolve_canonical_local_positions,static_bind_frames,native_keys_hash,sample_native_times,sha)
from .morph_preview_pose_constraints_v14a import two_bone_ik
from .refine_stage1_motion_v14 import compile_native,compiled_pose

CLIPS=('pause1','pause2','walk','run','nwkickl','nwkickr')
GROUPS={'upperArm':('bicepl','bicepr'),'forearm':('forel','forer'),'thigh':('legl','legr'),'shin':('shinl','shinr')}
SEGMENTS={'bicepl':('lbicep_g','lforearm_g'),'bicepr':('rbicep_g','rforearm_g'),
 'forel':('lforearm_g','lhand_g'),'forer':('rforearm_g','rhand_g'),
 'legl':('lthigh_g','lshin_g'),'legr':('rthigh_g','rshin_g'),
 'shinl':('lshin_g','lfoot_g'),'shinr':('rshin_g','rfoot_g')}

def require(value,message):
    if not value:raise ValueError(message)

def length_targets(policy,packet,source_frames,global_scale):
    rows=(policy or {}).get('lengths',(policy or {}).get('measurements',{}));result={}
    for group,parts in GROUPS.items():
        source=float(np.mean([np.linalg.norm(source_frames[SEGMENTS[p][1]][:3,3]-source_frames[SEGMENTS[p][0]][:3,3]) for p in parts]))*global_scale
        keys=(group+'Length',group+'ProjectedLength')
        row=next((rows[k] for k in keys if k in rows),{})
        # Only policy-authorized preferred dimensions guide this new fit.
        # Historical exact image-joint targets never become hidden hard goals.
        preferred=row.get('preferredMeters');available=preferred is not None and np.isfinite(preferred) and preferred>0
        slack=float(row.get('designSlackFraction',.05));require(0<=slack<=.2,'Explicit bounded length slack required')
        uncertainty=float(row.get('measurementUncertaintyMeters') or 0.);require(uncertainty>=0 and np.isfinite(uncertainty),'Finite measurement uncertainty required')
        confidence=row.get('confidence','low');weight=float(row.get('confidenceWeight',{'high':1.,'medium':.5,'low':.2}.get(confidence,.2)));require(np.isfinite(weight) and weight>=0,'Finite nonnegative confidence weight required')
        if row.get('guideOnly'):weight*=.25
        preferred=float(preferred) if available else source
        result[group]={'sourceScaledMeanMeters':source,'preferredMeters':preferred,'available':available,
            'designSlackFraction':slack,'measurementUncertaintyMeters':uncertainty,'confidence':confidence,
            'guideOnly':bool(row.get('guideOnly',not available)),'weight':weight,
            'preferredMultiplier':float(np.clip(preferred/source,.8,1.2)) if available else 1.,
            'unboundedPreferredMultiplier':preferred/source,'authority':'soft policy length; source asymmetry retained'}
    return result

def bilateral_factors(targets,blend):
    require(0<=blend<=1,'Bounded source/reference blend required')
    factors={p:1. for p in PART_JOINTS}
    for group,parts in GROUPS.items():
        multiplier=1.+blend*(targets[group]['preferredMultiplier']-1.)
        for part in parts:factors[part]=multiplier
    return factors

def pure_similarities(meshes,source_frames,target_frames,part_scales):
    result=[]
    for mesh in meshes:
        joint=mesh['name'] if mesh['part']=='rig' else PART_JOINTS[mesh['part']]
        a=np.asarray(source_frames[joint]);b=np.asarray(target_frames[joint]);rotation=b[:3,:3]@a[:3,:3].T
        require(np.linalg.det(rotation)>0 and np.allclose(rotation.T@rotation,np.eye(3),atol=1e-10,rtol=0),'Proper SO3 part similarity required')
        scale=float(part_scales.get(mesh['part'],part_scales.get('head',1.)));require(scale>0 and np.isfinite(scale),'Positive uniform part scale required')
        result.append({**mesh,'position':b[:3,3]+scale*(np.asarray(mesh['position'])-a[:3,3])@rotation.T,
                       'faces':np.asarray(mesh['faces']).copy(),'attachmentFrame':b.tolist()})
    return result

def build_candidate(source,source_frames,baseline,target_height,factors):
    """Source-owned chain proportions, natural XY stance, static bilateral sole fit."""
    skeleton=baseline['skeleton'];owner={joint:part for part,joint in PART_JOINTS.items()};original={n:np.asarray(f,float) for n,f in source_frames.items()}
    require(set(original)==set(skeleton),'Complete canonical donor hierarchy required')
    ground=float(min(m['position'][:,2].min() for m in source if m.get('render',True)))
    ratios=[];reach_ceiling=[]
    for side in ('l','r'):
        a=np.linalg.norm(original[side+'shin_g'][:3,3]-original[side+'thigh_g'][:3,3]);b=np.linalg.norm(original[side+'foot_g'][:3,3]-original[side+'shin_g'][:3,3])
        h,k,f=[original[side+p+'_g'][:3,3] for p in ('thigh','shin','foot')]
        ratios.append((h[2]-k[2])*(factors['leg'+side]-1.)+(k[2]-f[2])*(factors['shin'+side]-1.))
        footsole=min(float(m['position'][:,2].min()) for m in source if m['part']=='foot'+side and m.get('render',True))
        length=a*factors['leg'+side]+b*factors['shin'+side];horizontal=float(np.linalg.norm(h[:2]-f[:2]))
        require(horizontal<=length,'Natural stance exceeds proposed source-owned leg reach')
        reach_ceiling.append(f[2]-footsole+np.sqrt(max(0.,length*length-horizontal*horizontal))-(h[2]-ground))
    # One shared pelvis/upper-body translation, bounded by both source stance
    # chains. No independently translated feet or invented hip measurements.
    shift=np.array([0.,0.,-ground+min(float(np.mean(ratios)),*reach_ceiling)]);placed={};owner_cache={}
    def inherited_owner(name):
        if name in owner_cache:return owner_cache[name]
        parent=skeleton[name]['parent'];owner_cache[name]=owner.get(name,inherited_owner(parent) if parent!='null' else None);return owner_cache[name]
    def place(name):
        if name in placed:return placed[name]
        parent=skeleton[name]['parent'];frame=original[name].copy()
        if parent=='null':frame[:3,3]+=shift
        else:
            p=place(parent);factor=factors.get(inherited_owner(parent),1.)
            frame[:3,3]=p[:3,3]+factor*(original[name][:3,3]-original[parent][:3,3])
        placed[name]=frame;return frame
    for n in skeleton:place(n)
    overrides={};floor_records={}
    for side in ('l','r'):
        hip,knee,ankle=[side+p+'_g' for p in ('thigh','shin','foot')]
        footpart='foot'+side;footpoints=np.concatenate([m['position'] for m in source if m['part']==footpart and m.get('render',True)])
        target=original[ankle][:3,3].copy();target[2]-=float(footpoints[:,2].min())
        h,k,f=[placed[n][:3,3] for n in (hip,knee,ankle)]
        new_knee,new_ankle,info=two_bone_ik(h,k,f,target,original[knee][:3,3]+shift)
        for name,position,rotation in ((hip,h,shortest_rotation(k-h,new_knee-h)),(knee,new_knee,shortest_rotation(f-k,new_ankle-new_knee)),(ankle,new_ankle,np.eye(3))):
            frame=placed[name].copy();frame[:3,3]=position;frame[:3,:3]=rotation@original[name][:3,:3];overrides[name]=frame
        floor_records[side]={'requestedAnkleMeters':target.tolist(),'staticReachResidualMeters':info['requestedReachResidualMeters'],'standingOnlyPositionSolve':True}
    # Recompose complete attachment subtrees once after explicit leg frames.
    world={}
    def transport(name):
        if name in world:return world[name]
        parent=skeleton[name]['parent']
        if name in overrides:frame=overrides[name].copy()
        elif parent=='null':frame=placed[name].copy()
        else:
            p=transport(parent);r=p[:3,:3]@original[parent][:3,:3].T
            frame=placed[name].copy();frame[:3,:3]=r@original[name][:3,:3]
            frame[:3,3]=p[:3,3]+r@(placed[name][:3,3]-placed[parent][:3,3])
        world[name]=frame;return frame
    for n in skeleton:transport(n)
    raw=pure_similarities(source,original,world,factors);height=measure(raw,{n:f[:3,3].tolist() for n,f in world.items()})['bindStatureMeters'];scale=float(target_height/height)
    # Normalize this homogeneous anatomy proposal once; dimensions are soft.
    for frame in world.values():frame[:3,3]*=scale
    part_scales={p:float(factors.get(p,1.)*scale) for p in PART_JOINTS}
    meshes=pure_similarities(source,original,world,part_scales)
    local,offsets=backsolve_canonical_local_positions(baseline,world,scale);bind=static_bind_frames(skeleton,local,local_rotation_corrections=offsets)
    replay=evaluate_adjusted(baseline,'pause1',0.,local,scale,local_rotation_offsets=offsets)
    error=max(float(np.abs(replay[n]-world[n]).max()) for n in world);require(error<=1e-8,'Canonical fitted rig replay failed')
    soles={side:float(min(m['position'][:,2].min() for m in meshes if m['part']=='foot'+side and m.get('render',True))) for side in ('l','r')}
    return {'standingMeshes':meshes,'standingFrames':world,'bindFrames':bind,'bindMeshes':pose_rigid_meshes(meshes,world,bind),
        'localPositions':local,'localRotationOffsets':offsets,'localRotationCorrections':offsets,'uniformScale':scale,'partScales':part_scales,
        'candidateFloor':soles,'staticFloorPositioning':floor_records,'controllerRoundtripMaximumMatrixError':error,'coordinatedSourcePelvisShiftMeters':shift.tolist()}

def centered_length_loss(actual,goal):
    """Confidence-weighted guide, centered on preference without a dead zone.

    Design slack supplies the objective's unit, not an acceptance tolerance.
    Measurement uncertainty remains a separate reported quantity. Confidence
    weights carry its qualitative authority; large guide departures use linear
    Huber tails so one doubtful length cannot dominate quadratically.
    """
    if not goal['available']:return 0.
    unit=goal['preferredMeters']*max(goal['designSlackFraction'],.01)
    normalized=abs(actual-goal['preferredMeters'])/unit
    return goal['weight']*(.5*normalized**2 if normalized<=1. else normalized-.5)

def soft_length_score(candidate,source_frames,targets):
    rows={};score=0.
    for group,parts in GROUPS.items():
        values=[float(np.linalg.norm(candidate['standingFrames'][SEGMENTS[p][1]][:3,3]-candidate['standingFrames'][SEGMENTS[p][0]][:3,3])) for p in parts];actual=float(np.mean(values));goal=targets[group]
        band=goal['preferredMeters']*goal['designSlackFraction'];excess=max(0.,abs(actual-goal['preferredMeters'])-band)
        loss=centered_length_loss(actual,goal);score+=loss
        rows[group]={**goal,'actualBilateralMeters':values,'actualMeanMeters':actual,'residualMeters':actual-goal['preferredMeters'],'designPreferredHalfRangeMeters':band,'outsideDesignRangeMeters':excess,'withinDesignRange':excess==0.,'centeredGuideLoss':loss,'guideObjective':'confidence-weighted centered Huber; unit is design slack with1% numerical scale floor; uncertainty reported separately','sourceAsymmetryPreserved':True}
    return float(score),rows

def motion_metrics(candidate,source_meshes,source_frames,cache,policy):
    pose=compiled_pose(cache,candidate['localPositions'],candidate['localRotationOffsets'],candidate['uniformScale']);source_pose=cache['sourceWorldFrames'];scale=candidate['uniformScale'];standing_index=cache['samples'].index(('pause1',0.))
    support_bound=float(policy.get('supportPhaseSourceSoleMeters',.015));floor=min(float(m['position'][:,2].min()) for m in source_meshes if m.get('render',True));errors=[];sole_errors=[];support_count=0;rows=[];knee_jumps=[];loop=[]
    indices=cache['indices']
    for part in ('footl','footr'):
        name=PART_JOINTS[part];index=indices[name];points=np.concatenate([m['position'] for m in source_meshes if m['part']==part and m.get('render',True)])
        native_delta=source_pose[:,index]@np.linalg.inv(source_frames[name]);source_points=points[None]@native_delta[:,:3,:3].transpose(0,2,1)+native_delta[:,None,:3,3];source_soles=source_points[:,:,2].min(1)
        candpoints=np.concatenate([m['position'] for m in candidate['standingMeshes'] if m['part']==part and m.get('render',True)]);delta=pose[:,index]@np.linalg.inv(candidate['standingFrames'][name]);candposed=candpoints[None]@delta[:,:3,:3].transpose(0,2,1)+delta[:,None,:3,3];candidate_soles=candposed[:,:,2].min(1)
        trajectory=np.linalg.norm((pose[:,index,:3,3]-pose[standing_index,index,:3,3])-scale*(source_pose[:,index,:3,3]-source_pose[standing_index,index,:3,3]),axis=1)
        supported=source_soles<=floor+support_bound;errors.extend(trajectory[supported]);sole_errors.extend(np.abs(candidate_soles[supported]-scale*(source_soles[supported]-floor)));support_count+=int(supported.sum())
        for i,(clip,t) in enumerate(cache['samples']):rows.append({'clip':clip,'timeSeconds':t,'side':part[-1],'sourceSupportPhase':bool(supported[i]),'sourceSoleMeters':float(source_soles[i]),'candidateSoleMeters':float(candidate_soles[i]),'sourceRelativeFootTrajectoryErrorMeters':float(trajectory[i]),'airborneTreatedAsPlantFailure':False})
    for side in ('l','r'):
        ids=[indices[side+p+'_g'] for p in ('thigh','shin','foot')]
        def angles(frames):
            a=frames[:,ids[0],:3,3]-frames[:,ids[1],:3,3];b=frames[:,ids[2],:3,3]-frames[:,ids[1],:3,3]
            return np.degrees(np.arccos(np.clip(np.sum(a*b,1)/(np.linalg.norm(a,axis=1)*np.linalg.norm(b,axis=1)),-1,1)))
        ca,sa=angles(pose),angles(source_pose)
        for clip in CLIPS:
            select=[i for i,(name,_) in enumerate(cache['samples']) if name==clip]
            if len(select)>1:
                knee_jumps.append(float(max(0.,np.max(np.abs(np.diff(ca[select])))-np.max(np.abs(np.diff(sa[select]))))))
                a,b=select[0],select[-1];loop.append(float(np.linalg.norm((pose[b,ids[2],:3,3]-pose[a,ids[2],:3,3])-scale*(source_pose[b,ids[2],:3,3]-source_pose[a,ids[2],:3,3]))))
    rms=lambda x:float(np.sqrt(np.mean(np.asarray(x)**2))) if len(x) else 0.
    return {'sampleCount':len(cache['samples']),'clips':list(CLIPS),'supportSampleCount':support_count,'supportFootTrajectoryRmsMeters':rms(errors),'supportSoleRmsMeters':rms(sole_errors),
        'maximumSupportFootTrajectoryErrorMeters':float(max(errors,default=0.)),'maximumExtraKneeStepDegrees':float(max(knee_jumps,default=0.)),'maximumLoopResidualMeters':float(max(loop,default=0.)),
        'score':rms(errors)+rms(sole_errors),'supportClassification':'15mm source-sole heuristic relative to fixed standing floor; support phases remain pending visual review. Source-relative foot trajectory is diagnostic and does not establish plant slip.','samples':rows,'IKApplied':False,'motionAcceptance':False},pose

def contact_gate(source_meshes,source_frames,candidate,inventories,source_contacts):
    rows=[]
    for pair in LINKS:
        actual=terminal_contact(candidate['standingMeshes'],inventories[pair]);before=source_contacts[':'.join(pair)]['minimumTriangleClearanceMeters'];bound=before*min(candidate['partScales'][p] for p in pair)
        rows.append({'parts':list(pair),'status':'measured','sourceMinimumClearanceMeters':before,'candidateMinimumClearanceMeters':actual['minimumTriangleClearanceMeters'],'sourceDerivedMaximumClearanceMeters':bound,'numericEpsilonMeters':1e-8,'sourceCalibratedClearanceGate':actual['minimumTriangleClearanceMeters']<=bound+1e-8,'candidateActualContact':actual['actualTerminalContact']})
    return {'connectors':rows,'allRequiredSourceCalibratedTerminalGates':all(r['sourceCalibratedClearanceGate'] for r in rows),'allRequiredTerminalContacts':all(r['candidateActualContact'] for r in rows),'assetApprovalCreated':False}

def proxy_deviations(candidate,source_frames,packet):
    result={};owners={joint:part for part,joint in PART_JOINTS.items()};origin=float(candidate['standingFrames']['pelvis_g'][0,3])
    for name,row in packet.get('canonicalCalibration',{}).get('sourceSurfaceCentersAndPivotOffsets',{}).items():
        joint=row.get('sourceJointName');point=row.get('sourceProxyPositionMeters');target=row.get('targetProxyPositionXZMeters')
        if joint not in owners or point is None or target is None:continue
        a=source_frames[joint];b=candidate['standingFrames'][joint];r=b[:3,:3]@a[:3,:3].T
        actual=(b[:3,3]+candidate['partScales'][owners[joint]]*r@(np.asarray(point)-a[:3,3]))[[0,2]];goal=np.asarray(target)+[origin,0.]
        result[name]={'actualXZMeters':actual.tolist(),'targetXZMeters':goal.tolist(),'residualXZMeters':(actual-goal).tolist(),'distanceMeters':float(np.linalg.norm(actual-goal)),'status':'reported soft visible-surface guide; no exact joint chase','uncertaintyMeters':row.get('uncertaintyMeters')}
    return result

def motion_contact_gate(source,source_frames,source_local,baseline,candidate,inventories,policy,motion):
    selected={(clip,float(t)) for clip in ('pause1','pause2') for t in (0.,baseline['clips'][clip]['length']/2,baseline['clips'][clip]['length'])}
    selected.update((clip,float(baseline['clips'][clip]['length']/4)) for clip in ('walk','run','nwkickl','nwkickr'))
    for row in policy.get('motionSamples',[]):selected.add((row['clip'],float(row['timeSeconds'])))
    worst=max(motion['samples'],key=lambda row:row['sourceRelativeFootTrajectoryErrorMeters']);selected.add((worst['clip'],worst['timeSeconds']))
    rows=[]
    for clip,t in sorted(selected):
        require(clip in CLIPS and 0<=t<=baseline['clips'][clip]['length'],'Bound source-owned motion sample required')
        source_world=evaluate_adjusted(baseline,clip,t,source_local,1.)
        world=evaluate_adjusted(baseline,clip,t,candidate['localPositions'],candidate['uniformScale'],local_rotation_offsets=candidate['localRotationOffsets'])
        sm=pose_rigid_meshes(source,source_frames,source_world);cm=pose_rigid_meshes(candidate['standingMeshes'],candidate['standingFrames'],world);connectors=[]
        for pair in LINKS:
            before=terminal_contact(sm,inventories[pair]);after=terminal_contact(cm,inventories[pair]);bound=before['minimumTriangleClearanceMeters']*min(candidate['partScales'][p] for p in pair)
            connectors.append({'parts':list(pair),'status':'measured','sourceMinimumClearanceMeters':before['minimumTriangleClearanceMeters'],'candidateMinimumClearanceMeters':after['minimumTriangleClearanceMeters'],'sourceDerivedMaximumClearanceMeters':bound,'numericEpsilonMeters':1e-8,'sourceCalibratedClearanceGate':after['minimumTriangleClearanceMeters']<=bound+1e-8})
        rows.append({'clip':clip,'timeSeconds':t,'connectors':connectors,'allRequiredSourceCalibratedTerminalGates':all(r['sourceCalibratedClearanceGate'] for r in connectors)})
        if not rows[-1]['allRequiredSourceCalibratedTerminalGates']:
            return {'samples':rows,'allSelectedPoseGates':False,'evaluationStoppedOnFailedCandidate':True,'IKApplied':False,'motionAcceptance':False}
    return {'samples':rows,'allSelectedPoseGates':True,'evaluationStoppedOnFailedCandidate':False,'IKApplied':False,'motionAcceptance':False,'scope':'Both idle endpoints/midpoints, four exact quarter native phases and largest trajectory-error sample; source-owned standing terminal triangle eligibility'}

def fit_stage1(bind_meshes,bind_frames,baseline,packet,policy=None,preserve=False):
    started=time.monotonic();policy=policy or {};keys=native_keys_hash(baseline);require(set(baseline['clips'])>=set(CLIPS),'All six source-owned native clips required')
    for path,h in baseline.get('inputPins',{}).items():require(sha(path)==h,'Native source pin differs')
    source_local=local_positions_from_world_frames(baseline['skeleton'],bind_frames)
    for n,node in baseline['skeleton'].items():source_local.setdefault(n,np.asarray(node['position']).copy())
    source_frames=evaluate_adjusted(baseline,'pause1',0.,source_local,1.);source=pose_rigid_meshes(bind_meshes,bind_frames,source_frames)
    measured=measure(source,{n:f[:3,3].tolist() for n,f in source_frames.items()});height=float(packet['targetStatureMeters']);require(np.isfinite(height) and height>0,'Positive target stature required')
    common={'sourceBindFrames':{n:np.asarray(f).copy() for n,f in bind_frames.items()},'sourceStandingMeshes':source,'sourceStandingFrames':source_frames,'sourceLocalPositions':{n:np.asarray(p).tolist() for n,p in source_local.items()}}
    if preserve:
        require(packet.get('slug') in ('human_male_fit','human_female_fit'),'Exact identity restricted to Human Fits')
        identity={n:np.eye(3).tolist() for n in source_frames}
        return {**common,'uniformScale':1.,'partScales':{p:1. for p in PART_JOINTS},'standingMeshes':copy_meshes(source),'standingFrames':{n:f.copy() for n,f in source_frames.items()},'bindMeshes':copy_meshes(bind_meshes),'bindFrames':{n:np.asarray(f).copy() for n,f in bind_frames.items()},'localPositions':common['sourceLocalPositions'],'localRotationOffsets':identity,'localRotationCorrections':identity,'localDeltas':{n:(source_local[n]-np.asarray(baseline['skeleton'][n]['position'])).tolist() for n in source_local},'receipt':{'kind':'anatomy-first-stage1-v15a','identityPreserved':True,'uniformScale':1.,'partScales':{p:1. for p in PART_JOINTS},'referenceGuidesApplied':False,'IKApplied':False,'nativeKeysSha256Before':keys,'nativeKeysSha256After':native_keys_hash(baseline),'productionAccepted':False,'fittingTargetsApproved':False}}
    targets=length_targets(policy,packet,source_frames,height/measured['bindStatureMeters']);cache=compile_native(baseline,source_local,clips=CLIPS)
    inventories,source_contacts,timing=source_terminal_evidence(source,source_frames);trials=[];eligible=[];baseline_motion=None
    blends=policy.get('referenceBlendCandidates',[0.,.25,.5,.75,1.]);require(1<=len(blends)<=5 and blends[0]==0.,'Uniform source fallback must be first in bounded search')
    for blend in blends:
        candidate=build_candidate(source,source_frames,baseline,height,bilateral_factors(targets,float(blend)));reference_score,dimensions=soft_length_score(candidate,source_frames,targets)
        motion,poses=motion_metrics(candidate,source,source_frames,cache,policy);contact=contact_gate(source,source_frames,candidate,inventories,source_contacts)
        if float(blend)==0.:baseline_motion=motion
        require(baseline_motion is not None,'Uniform source baseline must be evaluated first')
        floor=max(abs(z) for z in candidate['candidateFloor'].values());physical=measure(candidate['standingMeshes'],{n:f[:3,3].tolist() for n,f in candidate['standingFrames'].items()});stature=abs(physical['bindStatureMeters']-height)/height
        support_limit=float(policy.get('maximumSupportFootTrajectoryErrorMeters',baseline_motion['maximumSupportFootTrajectoryErrorMeters']+.02*height))
        feasible=contact['allRequiredSourceCalibratedTerminalGates'] and floor<=float(policy.get('standingSoleToleranceMeters',1e-7)) and stature<=.01 and motion['maximumExtraKneeStepDegrees']<=float(policy.get('maximumExtraKneeStepDegrees',5.)) and motion['maximumSupportFootTrajectoryErrorMeters']<=support_limit
        regularization=float(sum((candidate['partScales'][p]/candidate['uniformScale']-1.)**2 for p in SEGMENTS)/len(SEGMENTS))
        terms={'centeredReferenceGuide':reference_score,'sourceRelativeMotionDiagnostic':float(policy.get('motionWeight',4.))*motion['score']/height,'sourceShapeRegularization':float(policy.get('sourceRegularizationWeight',.05))*regularization};score=sum(terms.values())
        trial={'referenceBlend':float(blend),'score':score,'objectiveTerms':terms,'referenceScore':reference_score,'softLengthDimensions':dimensions,'sourceRegularization':regularization,'motion':{k:v for k,v in motion.items() if k!='samples'},'maximumSupportFootTrajectoryErrorAllowedMeters':support_limit,'standingSolesMeters':candidate['candidateFloor'],'standingStatureMeters':physical['bindStatureMeters'],'contact':contact,'feasible':bool(feasible)};trials.append(trial)
        if feasible:eligible.append((score,candidate,dimensions,motion,contact,float(blend)))
    if not eligible:
        import json
        diagnostic=[{'blend':t['referenceBlend'],'soles':t['standingSolesMeters'],'failedConnectors':[r['parts'] for r in t['contact']['connectors'] if not r['sourceCalibratedClearanceGate']],'maximumSupportFootError':t['motion']['maximumSupportFootTrajectoryErrorMeters']} for t in trials]
        failure=ValueError('No anatomy-first candidate meets contact/floor/motion gates: '+json.dumps(diagnostic));failure.searchTrials=trials;raise failure
    selected=None
    for item in sorted(eligible,key=lambda value:value[0]):
        _,candidate,_,motion,_,candidate_blend=item
        dynamic_contact=motion_contact_gate(source,source_frames,source_local,baseline,candidate,inventories,policy,motion)
        next(t for t in trials if t['referenceBlend']==candidate_blend)['motionContact']=dynamic_contact
        if dynamic_contact['allSelectedPoseGates']:selected=(*item,dynamic_contact);break
    if selected is None:
        failure=ValueError('No anatomy-first standing-feasible candidate preserves selected raw native motion contacts');failure.searchTrials=trials;raise failure
    _,chosen,dimensions,motion,contact,blend,dynamic_contact=selected;world=chosen['standingFrames'];scale=chosen['uniformScale'];chosen.update(common)
    chosen['localDeltas']={n:(np.asarray(p)-np.asarray(baseline['skeleton'][n]['position'])*scale).tolist() for n,p in chosen['localPositions'].items()}
    for key in ('localPositions','localRotationOffsets','localRotationCorrections'):chosen[key]={n:np.asarray(v).tolist() for n,v in chosen[key].items()}
    require(native_keys_hash(baseline)==keys,'Native motion/breathing keys changed')
    for path,h in baseline.get('inputPins',{}).items():require(sha(path)==h,'Native source pin changed afterward')
    chosen['receipt']={'kind':'anatomy-first-stage1-v15a','toolkit':'PhenoMorpher','identityPreserved':False,'uniformScale':scale,'partScales':chosen['partScales'],'referenceBlend':blend,'searchTrials':trials,'softLengthDimensions':dimensions,'proxyResiduals':proxy_deviations(chosen,source_frames,packet),'referenceWorldOriginXMeters':float(world['pelvis_g'][0,3]),'motion':motion,'motionSamples':motion['samples'],
        'nativeKeysSha256Before':keys,'nativeKeysSha256After':native_keys_hash(baseline),'IKApplied':False,'runtimePoseConstraintsApplied':False,'pelvisTorsoSourceRotationsPreserved':all(np.array_equal(world[n][:3,:3],source_frames[n][:3,:3]) for n in ('pelvis_g','torso_g')),
        'allRequiredSourceCalibratedTerminalGates':contact['allRequiredSourceCalibratedTerminalGates'],'requiredTerminalContacts':{':'.join(r['parts']):r for r in contact['connectors']},'standingContact':contact,
        'motionContact':dynamic_contact,'allSelectedMotionContactGates':True,
        'bilateralStandingSoleZMeters':chosen['candidateFloor'],'actualStandingStatureMeters':measure(chosen['standingMeshes'],{n:f[:3,3].tolist() for n,f in world.items()})['bindStatureMeters'],
        'sourceGeometryHash':geometry_hash(bind_meshes),'previewBindGeometryHash':geometry_hash(chosen['bindMeshes']),'controllerRoundtripMaximumMatrixError':chosen['controllerRoundtripMaximumMatrixError'],'sourceTerminalPreparation':timing,'elapsedSeconds':time.monotonic()-started,
        'shapeMorphApplied':False,'widthDepthFittingApplied':False,'rigRotationsUnchanged':False,'productionAccepted':False,'fittingTargetsApproved':False,'surfaceJoinAcceptance':False,'motionFitValidated':False,
        'limitations':['Uniform each authored mesh part; differential width/depth fitting is a subsequent stage.','Measured lengths are soft bilateral guides; authored L/R asymmetry and explicit residuals retained.','Static leg floor positioning is fitted rig geometry; runtime motion evaluates original keys without per-frame IK or floor normalization.','Finite support-phase motion diagnostics do not certify continuous native/client motion; visible source caps/contours remain to review.']}
    return chosen
