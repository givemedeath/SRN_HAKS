"""Bounded static axial leg-frame refinement; no animation keys or pose IK edits."""
import copy,time
import numpy as np
from .target_contract import PART_JOINTS
from .morph_preview_pose_v13 import (evaluate_adjusted,native_keys_hash,backsolve_canonical_local_positions,static_bind_frames,pose_rigid_meshes)
from .fit_scale_position_v13a import SEGMENTS,LINKS,terminal_inventory,terminal_contact
from .fit_scale_position_v12d import geometry_hash
from .morph_motion_evidence_v14a import dense_times

TWIST_PARTS=('legl','legr','shinl','shinr')
def require(v,m):
    if not v:raise ValueError(m)
def axial_rotation(axis,radians):
    a=np.asarray(axis,float).copy();length=np.linalg.norm(a);require(length>1e-10 and np.isfinite(radians),'Finite nonzero twist axis required');a/=length
    k=np.array([[0.,-a[2],a[1]],[a[2],0.,-a[0]],[-a[1],a[0],0.]])
    return np.eye(3)+np.sin(radians)*k+(1-np.cos(radians))*(k@k)

def compile_native(baseline,source_positions,clips=('pause1','pause2')):
    """Cache exact native local keys once; vectorized candidates never edit them."""
    names=list(baseline['skeleton']);indices={n:i for i,n in enumerate(names)};parents=[baseline['skeleton'][n]['parent'] for n in names];order=[];done=set()
    def visit(i):
        if i in done:return
        if parents[i]!='null':visit(indices[parents[i]])
        done.add(i);order.append(i)
    for i in range(len(names)):visit(i)
    samples=[(clip,float(t)) for clip in clips for t in dense_times(baseline['clips'][clip])];source=[];rotation=[];addition=[]
    for clip,t in samples:
        world=evaluate_adjusted(baseline,clip,t,source_positions,1.);source.append(np.asarray([world[n] for n in names]));local=[]
        for n,p in zip(names,parents):local.append(world[n] if p=='null' else np.linalg.inv(world[p])@world[n])
        local=np.asarray(local);rotation.append(local[:,:3,:3]);addition.append(local[:,:3,3]-np.asarray([source_positions[n] for n in names]))
    return {'names':names,'indices':indices,'parents':parents,'order':order,'samples':samples,'localRotations':np.asarray(rotation),'animatedPositionAdditions':np.asarray(addition),'sourceWorldFrames':np.asarray(source)}

def compiled_pose(cache,positions,offsets,scale):
    require(np.isfinite(scale) and scale>0,'Positive scale required');require(set(offsets)<=set(cache['names']),'Unknown correction joint')
    for r in offsets.values():
        r=np.asarray(r);require(r.shape==(3,3) and np.isfinite(r).all() and np.allclose(r.T@r,np.eye(3),atol=1e-10) and abs(np.linalg.det(r)-1)<1e-10,'Proper static SO3 required')
    count=len(cache['samples']);result=np.repeat(np.eye(4)[None,None,:,:],count,axis=0);result=np.repeat(result,len(cache['names']),axis=1)
    for i in cache['order']:
        n=cache['names'][i];local=np.repeat(np.eye(4)[None,:,:],count,axis=0);local[:,:3,:3]=np.asarray(offsets.get(n,np.eye(3)))@cache['localRotations'][:,i];local[:,:3,3]=np.asarray(positions[n])+scale*cache['animatedPositionAdditions'][:,i]
        parent=cache['parents'][i];result[:,i]=local if parent=='null' else result[:,cache['indices'][parent]]@local
    return result

def candidate_from_twists(stage1,baseline,angles):
    require(len(angles)==4 and np.isfinite(angles).all(),'Four finite axial twists required');world={n:np.asarray(f).copy() for n,f in stage1['standingFrames'].items()};rotations={}
    for part,angle in zip(TWIST_PARTS,angles):
        start,end=SEGMENTS[part];r=axial_rotation(world[end][:3,3]-world[start][:3,3],angle);rotations[part]=r;world[start][:3,:3]=r@world[start][:3,:3]
    meshes=[]
    for mesh in stage1['standingMeshes']:
        joint=mesh['name'] if mesh['part']=='rig' else PART_JOINTS[mesh['part']];r=world[joint][:3,:3]@np.asarray(stage1['standingFrames'][joint])[:3,:3].T;p=np.asarray(mesh['position']);origin=np.asarray(stage1['standingFrames'][joint])[:3,3]
        meshes.append({**mesh,'position':(p-origin)@r.T+world[joint][:3,3],'faces':np.asarray(mesh['faces']).copy(),'attachmentFrame':world[joint].tolist()})
    positions,offsets=backsolve_canonical_local_positions(baseline,world,stage1['uniformScale']);bind=static_bind_frames(baseline['skeleton'],positions,local_rotation_corrections=offsets)
    return {**stage1,'standingFrames':world,'standingMeshes':meshes,'bindFrames':bind,'bindMeshes':pose_rigid_meshes(meshes,world,bind),'localPositions':positions,'localRotationOffsets':offsets,'localRotationCorrections':offsets,'localDeltas':{n:(np.asarray(positions[n])-np.asarray(baseline['skeleton'][n]['position'])*stage1['uniformScale']).tolist() for n in positions}}

def motion_metrics(candidate,cache,ground=0.):
    frames=compiled_pose(cache,candidate['localPositions'],candidate['localRotationOffsets'],candidate['uniformScale']);standing=cache['samples'].index(('pause1',0.));residual=[];excursion=[];surface=[];sole=[];pen=[];per_sample=np.zeros(len(frames))
    for part in ('footl','footr'):
        joint=PART_JOINTS[part];i=cache['indices'][joint];points=np.concatenate([m['position'] for m in candidate['standingMeshes'] if m['part']==part and m.get('render',True)]);origin=np.asarray(candidate['standingFrames'][joint]);delta=frames[:,i]@np.linalg.inv(origin);posed=points[None]@delta[:,:3,:3].transpose(0,2,1)+delta[:,None,:3,3]
        actual=frames[:,i,:3,3]-frames[standing,i,:3,3];accepted=(cache['sourceWorldFrames'][:,i,:3,3]-cache['sourceWorldFrames'][standing,i,:3,3])*candidate['uniformScale'];rr=np.linalg.norm(actual-accepted,axis=1);ex=np.linalg.norm(actual,axis=1);sv=np.sqrt(np.mean(np.sum((posed-posed[standing])**2,axis=2),axis=1));z=posed[:,:,2].min(1);vertical=np.abs(z-z[standing]);penetration=np.maximum(ground-z,0.);per_sample=np.maximum(per_sample,rr+sv+vertical+5*penetration)
        residual.extend(rr);excursion.extend(ex);surface.extend(sv);sole.extend(vertical);pen.extend(penetration)
    rms=lambda a:float(np.sqrt(np.mean(np.asarray(a)**2)))
    metrics={'dynamicJointResidualRmsMeters':rms(residual),'maximumDynamicJointResidualMeters':float(max(residual)),'footJointExcursionRmsMeters':rms(excursion),'maximumFootJointExcursionMeters':float(max(excursion)),'rigidFootSurfaceExcursionRmsMeters':rms(surface),'maximumRigidFootSurfaceExcursionMeters':float(max(surface)),'soleHeightMotionRmsMeters':rms(sole),'maximumSoleHeightMotionMeters':float(max(sole)),'solePenetrationRmsMeters':rms(pen),'maximumSolePenetrationMeters':float(max(pen))}
    metrics['scoreMeters']=metrics['dynamicJointResidualRmsMeters']+metrics['footJointExcursionRmsMeters']+metrics['rigidFootSurfaceExcursionRmsMeters']+2*metrics['soleHeightMotionRmsMeters']+10*metrics['solePenetrationRmsMeters']
    return metrics,frames,per_sample

def contact_sample_indices(cache,weights,max_extrema=4):
    selected={cache['samples'].index(('pause1',0.))}
    for clip in ('pause1','pause2'):
        indices=[i for i,(c,t) in enumerate(cache['samples']) if c==clip];selected.update((indices[0],indices[len(indices)//2],indices[-1]))
    selected.update(int(i) for i in np.argsort(weights)[-max_extrema:]);return sorted(selected)

def motion_contact_gates(stage1,candidate,cache,frames,indices):
    source=stage1['sourceStandingMeshes'];sf=stage1['sourceStandingFrames'];inventory={pair:terminal_inventory(source,sf,*pair) for pair in LINKS};rows=[];passed=True
    for index in indices:
        sourceworld={n:cache['sourceWorldFrames'][index,i] for i,n in enumerate(cache['names'])};world={n:frames[index,i] for i,n in enumerate(cache['names'])};sm=pose_rigid_meshes(source,sf,sourceworld);cm=pose_rigid_meshes(candidate['standingMeshes'],candidate['standingFrames'],world);gates=[]
        for pair in LINKS:
            before=terminal_contact(sm,inventory[pair]);after=terminal_contact(cm,inventory[pair]);bound=before['minimumTriangleClearanceMeters']*min(candidate['partScales'][p] for p in pair);okay=after['minimumTriangleClearanceMeters']<=bound+1e-8;passed&=okay;gates.append({'parts':list(pair),'sourceMinimumClearanceMeters':before['minimumTriangleClearanceMeters'],'candidateMinimumClearanceMeters':after['minimumTriangleClearanceMeters'],'sourceDerivedMaximumClearanceMeters':bound,'numericEpsilonMeters':1e-8,'sourceCalibratedClearanceGate':okay,'candidateActualContact':after['actualTerminalContact']})
        clip,t=cache['samples'][index];rows.append({'clip':clip,'timeSeconds':t,'connectors':gates,'allRequiredSourceCalibratedTerminalGates':all(g['sourceCalibratedClearanceGate'] for g in gates)})
    return {'samples':rows,'allSampledRequiredSourceCalibratedTerminalGates':bool(passed),'scope':'Standing, both clips endpoints/midpoint plus highest motion-score samples; finite sampled contact, not continuous/locomotion acceptance'}

def proxy_receipt(stage1,packet):
    inverse={n:p for p,n in PART_JOINTS.items()};origin=stage1['receipt']['referenceWorldOriginXMeters'];result={}
    for name,row in packet['canonicalCalibration']['sourceSurfaceCentersAndPivotOffsets'].items():
        joint=row.get('sourceJointName');point=row.get('sourceProxyPositionMeters');target=row.get('targetProxyPositionXZMeters');part=inverse.get(joint)
        if point is None or target is None or part is None:continue
        source=np.asarray(stage1['sourceStandingFrames'][joint]);world=np.asarray(stage1['standingFrames'][joint]);r=world[:3,:3]@source[:3,:3].T;actual=(world[:3,3]+float(stage1['partScales'][part])*r@(np.asarray(point)-source[:3,3]))[[0,2]];goal=np.asarray(target)+[origin,0.]
        result[name]={'actualXZMeters':actual.tolist(),'targetXZMeters':goal.tolist(),'residualXZMeters':(actual-goal).tolist(),'distanceMeters':float(np.linalg.norm(actual-goal)),'uncertaintyMeters':row.get('uncertaintyMeters'),'status':'contact-priority uniform similarity with bounded static axial motion refinement; visible proxy residual retained'}
    return result


def refine_stage1(stage1,packet,baseline,preserve=False,max_twist_degrees=6.,rounds=2,max_contact_candidates=3):
    started=time.monotonic();key_hash=native_keys_hash(baseline)
    for path,pin in baseline.get('inputPins',{}).items():
        from .morph_preview_pose_v13 import sha
        require(sha(path)==pin,'Bound native input changed')
    identity=packet.get('slug') in ('human_male_fit','human_female_fit');require(bool(preserve)==identity,'Exact Human identity scope differs');require(0<max_twist_degrees<=10 and rounds in (1,2,3),'Explicit bounded static search required')
    if preserve:
        return {**stage1,'receipt':{**stage1['receipt'],'motionStaticRefinement':{'applied':False,'status':'exact Human Fit identity retained','nativeKeysSha256Before':key_hash,'nativeKeysSha256After':native_keys_hash(baseline),'motionAccepted':False}}}
    require(set(baseline['clips'])>={'pause1','pause2'},'Both bound native idle clips required');cache=compile_native(baseline,stage1['sourceLocalPositions']);initial,initial_frames,initial_weights=motion_metrics(stage1,cache);limit=np.radians(max_twist_degrees);zero=np.zeros(4);candidates=[(initial['scoreMeters'],zero,stage1,initial,initial_frames,initial_weights)];trials=[];angles=zero.copy();best=initial['scoreMeters']
    for step in (limit,limit*.5,limit*.25)[:rounds]:
        for axis in range(4):
            choices=[]
            for sign in (-1,1):
                a=angles.copy();a[axis]=np.clip(a[axis]+sign*step,-limit,limit)
                c=candidate_from_twists(stage1,baseline,a);m,frames,w=motion_metrics(c,cache);trials.append({'axialTwistDegrees':np.degrees(a).tolist(),'metrics':m});candidates.append((m['scoreMeters'],a,c,m,frames,w));choices.append((m['scoreMeters'],a))
            score,a=min(choices,key=lambda x:x[0])
            if score<best:angles=a;best=score
    chosen=None;contacts=[];baseline_gates=motion_contact_gates(stage1,stage1,cache,initial_frames,contact_sample_indices(cache,initial_weights))
    for score,a,c,m,frames,w in sorted(candidates,key=lambda x:x[0]):
        if np.array_equal(a,zero) or len(contacts)>=max_contact_candidates:continue
        if score>=initial['scoreMeters']-1e-7:continue
        # Do not buy the score by worsening planting or a motion component.
        guarded=('dynamicJointResidualRmsMeters','footJointExcursionRmsMeters','rigidFootSurfaceExcursionRmsMeters','solePenetrationRmsMeters','maximumSolePenetrationMeters')
        if any(m[k]>initial[k]*1.05+1e-9 for k in guarded):continue
        gates=motion_contact_gates(stage1,c,cache,frames,contact_sample_indices(cache,np.maximum(w,initial_weights)));contacts.append({'axialTwistDegrees':np.degrees(a).tolist(),'metrics':m,'contactGates':gates})
        if gates['allSampledRequiredSourceCalibratedTerminalGates']:chosen=(a,c,m,gates);break
    if chosen is None:a=zero;result=stage1;final=initial;gates=baseline_gates;status='bounded static refinement insufficient; unchanged stage1 retained, motion remains unresolved'
    else:a,result,final,gates=chosen;status='bounded static axial refinement reduced sampled motion score; wider motion/visible anatomy unresolved'
    require(native_keys_hash(baseline)==key_hash,'Native keys mutated by static refinement')
    for path,pin in baseline.get('inputPins',{}).items():require(sha(path)==pin,'Bound native input changed after refinement')
    for n in ('pelvis_g','torso_g','neck_g','head_g'):
        require(np.array_equal(np.asarray(result['standingFrames'][n]),np.asarray(stage1['standingFrames'][n])),'Protected posture/head/neck changed')
    for n in stage1['standingFrames']:require(np.array_equal(np.asarray(result['standingFrames'][n])[:3,3],np.asarray(stage1['standingFrames'][n])[:3,3]),'Standing joint position changed')
    for p in ('footl','footr'):
        before=[m for m in stage1['standingMeshes'] if m['part']==p];after=[m for m in result['standingMeshes'] if m['part']==p]
        require(all(np.allclose(a['position'],b['position'],atol=1e-12,rtol=0) for a,b in zip(before,after)),'Standing foot geometry changed')
    evidence={'applied':chosen is not None,'status':status,'axialTwistDegrees':np.degrees(a).tolist(),'maximumAxialTwistDegrees':max_twist_degrees,'uniformPartScalesUnchanged':True,'standingJointPositionsUnchanged':True,'standingFeetUnchanged':True,'nativeSegmentLengthsUnchanged':True,'pelvisTorsoHeadNeckStandingFramesUnchanged':True,'nativeKeysSha256Before':key_hash,'nativeKeysSha256After':native_keys_hash(baseline),'before':initial,'after':final,'denseIdleSampleCount':len(cache['samples']),'nativeIdleClips':['pause1','pause2'],'optimizationTrials':trials,'contactCandidateTrials':contacts,'originalStage1MotionContactGates':baseline_gates,'selectedMotionContactGates':gates,'broaderLocomotionEvaluatedByOptimizer':False,'broaderMotionStatus':'Separate bound Human-chain walk/run/kick evidence required; airborne native phases are not planting errors','poseCorrectionsOrKeysWritten':False,'motionAccepted':False,'productionAccepted':False,'elapsedSeconds':time.monotonic()-started}
    positions={n:np.asarray(p).tolist() for n,p in result['localPositions'].items()};offsets={n:np.asarray(r).tolist() for n,r in result['localRotationOffsets'].items()};replay=evaluate_adjusted(baseline,'pause1',0.,positions,result['uniformScale'],local_rotation_offsets=offsets);error=max(float(np.max(np.abs(replay[n]-f))) for n,f in result['standingFrames'].items());require(error<1e-8,'Refined canonical native replay differs')
    receipt={**result['receipt'],'localRotationOffsets':offsets,'proxyResiduals':proxy_receipt(result,packet),'previewBindGeometryHash':geometry_hash(result['bindMeshes']),'controllerRoundtripMaximumMatrixError':error,'motionStaticRefinement':evidence,'motionFitValidated':False}
    return {**result,'localPositions':positions,'localRotationOffsets':offsets,'localRotationCorrections':offsets,'receipt':receipt}
