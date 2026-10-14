"""Bound native idle poses with preview-only local rotation/position offsets.

Female uses accepted final carriers; male uses the pinned current native owner.
No animation is emitted. Finite samples cannot certify continuous motion.
"""
import copy
import hashlib
import json
import re
from pathlib import Path
import numpy as np
from .shared_female_native_contract import ascii_bind,inherited_bind,world_pose,interpolate,qmatrix
from .target_animation_overlay import NativeIdleReader
from .target_contract import PART_JOINTS
from .silhouette_model import ascii_model
from .retarget import rotations,NODE

def require(value,message):
    if not value:raise ValueError(message)
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def verified(pin):
    path=Path(pin['path']).resolve();require(sha(path)==pin['sha256'],'Pose input hash differs: '+str(path));return path

def validate_pose_hierarchy(skeleton, clips, root, alias):
    require(root in skeleton and skeleton[root]['parent']=='null','Actor root missing')
    for name in skeleton:
        seen=set()
        while name!='null':
            require(name in skeleton and name not in seen,'Incomplete or cyclic pose hierarchy')
            seen.add(name);name=skeleton[name]['parent']
    for clip in clips.values():
        controls={root if name==alias else name for name in clip['nodes']}
        require(controls<=set(skeleton),'Animated joint absent complete bind hierarchy')

ACTOR_SOURCE_CONTRACTS={
    'pfh0':'1da54afc5ff270c8c7decc61829df0595c6568d70cdef75026f63d8e94362f51',
    'pfh2':'644185fdb13b263b1a6d767baf5acfd18ceb44c8cbe48edea3c4d1e5c0c001f1'}

def bound_female_actor(blob,row):
    root=row['root'];require(root in ACTOR_SOURCE_CONTRACTS and hashlib.sha256(blob).hexdigest()==ACTOR_SOURCE_CONTRACTS[root],
                            'Unbound female actor source compatibility')
    text=blob.decode('cp1252');geometry=text.split('endmodelgeom',1)[0];entries=list(NODE.finditer(geometry))
    require(len(entries)==57 and row['actorOwnedCarrierStaticNodes']==56,'Bound actor node inventory differs')
    require([n[2].lower() for n in entries if n[1].lower()!='dummy']==(['rootdummy'] if root=='pfh0' else []),
            'Unexpected non-dummy actor static')
    require(all(n[1].lower()=='trimesh' for n in entries if n[1].lower()!='dummy'),'Unexpected actor mesh type')
    duplicates=[n for n in entries if n[2].lower()=='impact']
    require(len(duplicates)==2 and all(n[1].lower()=='dummy' for n in duplicates),'Bound Impact duplicates differ')
    require(not re.search(r'(?mi)^\s*parent\s+impact\s*$',geometry),'Duplicate Impact has a dependent')
    actor,meshes=ascii_model(text)
    require(len(meshes)==(1 if root=='pfh0' else 0) and all(m['name']=='rootdummy' and not m['render'] for m in meshes),
            'Non-render rootdummy contract differs')
    require('impact__duplicate_2' in actor,'Bound duplicate parser identity differs')
    actor.pop('impact__duplicate_2') # Exact pinned, unreferenced duplicate; never an animated or mesh owner.
    require(len(actor)==56 and all(n.get('scale',1)==1 for n in actor.values()),'Bound actor count/scale differs')
    return {name:{'parent':node['parent'],'position':np.asarray(node['position'],float),
                  'rotation':rotations(node['orientation'])} for name,node in actor.items()}

def load_male_baseline(mapping_path,rig_path,rig_sha256):
    """Current pmh0 actor plus explicitly pinned a_ba ancestry; no female corrections."""
    mapping=read(mapping_path);plan_pin=mapping['familyPlanLocal'];plan=read(verified(plan_pin))
    consumed={str(Path(plan_pin['path']).resolve()):plan_pin['sha256']}
    def local(pin):
        key=str(Path(pin['path']).resolve());require(key in mapping['sourceCopies'],'Missing local male ancestor mapping')
        mapped=mapping['sourceCopies'][key];require(mapped['sha256']==pin['sha256'],'Mapped male ancestor differs')
        path=verified(mapped);consumed[str(path)]=mapped['sha256'];return path
    rig=verified({'path':rig_path,'sha256':rig_sha256});consumed[str(rig)]=rig_sha256
    text=rig.read_text(encoding='cp1252');root='pmh0';owner='a_ba'
    require(re.findall(r'(?mi)^newmodel\s+(\S+)',text)==[root],'Current male actor identity differs')
    require(re.findall(r'(?mi)^setsupermodel\s+pmh0\s+(\S+)',text)==[owner],'Male owner differs')
    require(re.findall(r'(?mi)^setanimationscale\s+(\S+)',text)==['1.0'],'Male caller scale differs')
    actor,meshes=ascii_model(text);require(not meshes,'Male rig must contain only static dummies')
    skeleton={name:{'parent':node['parent'],'position':np.asarray(node['position'],float),
                    'rotation':rotations(node['orientation'])} for name,node in actor.items()}
    require(len(skeleton)==56 and all(node.get('scale',1)==1 for node in actor.values()),'Male actor static inventory differs')
    rows=[r for r in plan['rows'] if r['winningIdleOwner']==owner]
    require(rows,'Pinned a_ba chain unavailable');row=rows[0]
    chain=row['sourceAncestry'];start=next(i for i,a in enumerate(chain) if a['name']==owner);chain=chain[start:]
    aliases={a['name'] for a in chain};expected=owner;inherited=[]
    for ancestor in chain:
        require(ancestor['name']==expected,'Explicit male ancestor ordering differs')
        native=local(ancestor['native']);static=local(ancestor['ascii']);source=static.read_text(encoding='cp1252')
        require(re.findall(r'(?mi)^newmodel\s+(\S+)',source)==[expected],'Ancestor static identity differs')
        require([v.lower() for v in re.findall(r'(?mi)^setsupermodel\s+\S+\s+(\S+)',source)]==[ancestor['parent']],'Ancestor static parent differs')
        require(float(ancestor['literalScaleToken'])==1,'Male ancestor scale differs')
        nodes,_=ascii_model(source)
        for name,node in nodes.items():
            if name in aliases or name in skeleton:continue
            require(node.get('scale',1)==1,'Inherited male local scale differs')
            skeleton[name]={'parent':root if node['parent'] in aliases else node['parent'],
                            'position':np.asarray(node['position'],float),'rotation':rotations(node['orientation'])}
            inherited.append({'name':name,'owner':expected,'sourceSha256':sha(static)})
        if expected==owner:
            decoded=NativeIdleReader(native.read_bytes()).decode({'pause1','pause2'})
            require(decoded['name']==owner and decoded['parent']==ancestor['parent'],'Native male owner identity differs')
        expected=ancestor['parent']
    require(expected=='null','Male ancestry is incomplete')
    clips={name:dict(clip,name=name) for name,clip in decoded['clips'].items()}
    require(set(clips)=={'pause1','pause2'},'Male native idle inventory differs')
    validate_pose_hierarchy(skeleton,clips,root,owner)
    for clip in clips.values():
        for node in clip['nodes'].values():
            for typ in node['controls']:require(typ in (8,20,36),'Unsupported male native controller')
    return {'row':{'root':root,'carrier':owner,'literalActorScaleToken':'1.0'},'skeleton':skeleton,
            'clips':clips,'inputPins':consumed,'baselineRoot':root,'nativeIdleOwner':owner,
            'inheritedStaticNodes':inherited,'oldCorrectiveArraysApplied':False,
            'maleMotion':'bound native a_ba pause1/pause2; finite samples only'}

def load_accepted_female(mapping_path,root='pfh0'):
    require(root in ('pfh0','pfh2'),'Explicit normal/Large Human female baseline required')
    mapping=read(mapping_path);plan=read(verified(mapping['familyPlanLocal']))
    row=next(r for r in plan['rows'] if r['root']==root)
    consumed={str(Path(mapping['familyPlanLocal']['path']).resolve()):mapping['familyPlanLocal']['sha256'],
              str(Path(mapping['acceptedManifest']['path']).resolve()):mapping['acceptedManifest']['sha256']}
    def local(pin):
        key=str(Path(pin['path']).resolve());require(key in mapping['sourceCopies'],'Missing local source mapping')
        mapped=mapping['sourceCopies'][key];require(mapped['sha256']==pin['sha256'],'Mapped source differs')
        path=verified(mapped);consumed[str(path)]=mapped['sha256'];return path
    skeleton=bound_female_actor(local(row['sourceActorRoot']).read_bytes(),row)
    skeleton=inherited_bind(row,skeleton,local)
    carrier_pin=mapping['acceptedResources'][row['carrier']+'.mdl'];carrier=verified(carrier_pin)
    consumed[str(carrier)]=carrier_pin['sha256']
    accepted=read(verified(mapping['acceptedManifest']))
    require(accepted['resourceHashes'][row['carrier']+'.mdl']==carrier_pin['sha256'],'Carrier lacks accepted authority')
    decoded=NativeIdleReader(carrier.read_bytes()).decode({'pause1','pause2'})
    require(decoded['name']==row['carrier'] and set(decoded['clips'])=={'pause1','pause2'},'Accepted carrier identity/clip inventory differs')
    clips={name:dict(clip,name=name) for name,clip in decoded['clips'].items()}
    validate_pose_hierarchy(skeleton,clips,root,row['carrier'])
    return {'row':row,'skeleton':skeleton,'clips':clips,'inputPins':consumed,
            'acceptedCarrierSha256':carrier_pin['sha256'],'baselineRoot':root,
            'oldCorrectiveArraysApplied':False,'maleMotion':'unavailable: no bound accepted male owner chain'}

def sample_native_times(clip,include_midpoints=True):
    times={0.,float(clip['length'])}
    for node in clip['nodes'].values():
        for control in node['controls'].values():
            times.update(float(t) for t in control['times'] if 0<=t<=clip['length'])
    ordered=sorted(times)
    if include_midpoints:times.update((a+b)/2 for a,b in zip(ordered,ordered[1:]))
    return sorted(times)

def evaluate_accepted(baseline,clip_name,time):
    row=baseline['row'];clip=baseline['clips'][clip_name]
    require(0<=time<=clip['length'],'Pose time outside native clip')
    # Final carrier already contains accepted level-hip corrections. numeric=None
    # deliberately prevents applying historical correction arrays a second time.
    return world_pose(baseline['skeleton'],clip,time,row['root'],row['carrier'],float(row['literalActorScaleToken']))

def local_positions_from_world_frames(skeleton,world_frames):
    result={}
    for name,node in skeleton.items():
        if name not in world_frames:continue
        matrix=np.asarray(world_frames[name],float)
        if node['parent']=='null':result[name]=matrix[:3,3].copy()
        else:
            require(node['parent'] in world_frames,'Missing parent world frame')
            local=np.linalg.inv(np.asarray(world_frames[node['parent']],float))@matrix
            result[name]=local[:3,3].copy()
    return result

def rotation_corrections(skeleton,offsets=None,corrections=None):
    require(offsets is None or corrections is None,'Provide one rotation correction argument')
    rows=offsets if offsets is not None else (corrections or {})
    require(set(rows)<=set(skeleton),'Rotation correction joint absent accepted hierarchy')
    result={}
    for name,value in rows.items():
        r=np.asarray(value,float)
        require(r.shape==(3,3) and np.isfinite(r).all(),'Finite 3x3 rotation correction required')
        require(np.allclose(r.T@r,np.eye(3),atol=1e-10,rtol=0) and abs(float(np.linalg.det(r))-1.)<=1e-10,'Rotation correction must be proper SO3')
        result[name]=r.copy()
    return result

def native_keys_hash(baseline):
    def convert(v):
        if isinstance(v,np.ndarray):return {'dtype':str(v.dtype),'shape':list(v.shape),'bytes':v.tobytes().hex()}
        if isinstance(v,dict):return {str(k):convert(x) for k,x in v.items()}
        if isinstance(v,(list,tuple)):return [convert(x) for x in v]
        if isinstance(v,np.generic):return v.item()
        return v
    return hashlib.sha256(json.dumps(convert(baseline['clips']),sort_keys=True,separators=(',',':')).encode()).hexdigest()

def rotation_difference_degrees(a,b):
    if np.array_equal(np.asarray(a)[:3,:3],np.asarray(b)[:3,:3]):return 0.
    value=(np.trace(np.asarray(a)[:3,:3]@np.asarray(b)[:3,:3].T)-1.)/2.
    return float(np.degrees(np.arccos(np.clip(value,-1.,1.))))

def static_bind_frames(skeleton,positions,local_rotation_corrections=None,*,local_rotation_offsets=None):
    corrections=rotation_corrections(skeleton,local_rotation_offsets,local_rotation_corrections);result={};visiting=set()
    def visit(name):
        if name in result:return result[name]
        require(name not in visiting,'Cyclic static hierarchy');visiting.add(name);node=skeleton[name]
        local=np.eye(4);r=np.asarray(node['rotation'])
        local[:3,:3]=corrections[name]@r if name in corrections else r
        p=np.asarray(positions.get(name,node['position']),float)
        require(p.shape==(3,) and np.isfinite(p).all(),'Finite static local position required');local[:3,3]=p
        result[name]=local if node['parent']=='null' else visit(node['parent'])@local
        visiting.remove(name);return result[name]
    require(set(positions)<=set(skeleton),'Static position joint absent hierarchy')
    for name in skeleton:visit(name)
    return result

def backsolve_canonical_local_positions(baseline,desired_world_frames,uniform_scale=1.):
    """Controller-compatible local translations and left-local corrections at pause1 t0."""
    require(np.isfinite(uniform_scale) and uniform_scale>0,'Invalid rig preview scale')
    skeleton=baseline['skeleton'];require(set(desired_world_frames)==set(skeleton),'Complete desired canonical world frames required')
    native=evaluate_adjusted(baseline,'pause1',0,{},uniform_scale);positions={};corrections={}
    for name,node in skeleton.items():
        parent=node['parent'];desired=np.asarray(desired_world_frames[name],float)
        require(desired.shape==(4,4) and np.isfinite(desired).all() and np.array_equal(desired[3],np.array([0.,0.,0.,1.])),'Finite rigid homogeneous world frame required')
        local=desired if parent=='null' else np.linalg.inv(np.asarray(desired_world_frames[parent]))@desired
        old=native[name] if parent=='null' else np.linalg.inv(native[parent])@native[name]
        positions[name]=np.asarray(node['position'])*uniform_scale+local[:3,3]-old[:3,3]
        corrections[name]=local[:3,:3]@old[:3,:3].T
    return positions,rotation_corrections(skeleton,corrections=corrections)

def evaluate_adjusted(baseline,clip_name,time,new_local_positions,uniform_scale=1.,local_rotation_offsets=None,*,local_rotation_corrections=None):
    require(np.isfinite(uniform_scale) and uniform_scale>0,'Invalid rig preview scale')
    skeleton=baseline['skeleton'];row=baseline['row'];clip=baseline['clips'][clip_name]
    corrections=rotation_corrections(skeleton,local_rotation_offsets,local_rotation_corrections)
    require(set(new_local_positions)<=set(skeleton),'Adjusted joint absent accepted hierarchy')
    require(0<=time<=clip['length'],'Pose time outside native clip')
    controls={(row['root'] if n==row['carrier'] else n):v['controls'] for n,v in clip['nodes'].items()}
    require(set(controls)<=set(skeleton),'Animated joint absent accepted hierarchy')
    worlds={};visiting=set()
    def visit(name):
        if name in worlds:return worlds[name]
        require(name not in visiting,'Cyclic pose hierarchy');visiting.add(name)
        node=skeleton[name];original=node['position']
        p=np.asarray(new_local_positions.get(name,np.asarray(original)*uniform_scale),float).copy()
        require(p.shape==(3,) and np.isfinite(p).all(),'Invalid adjusted local position')
        rotation=node['rotation']
        for typ,control in controls.get(name,{}).items():
            if typ==8:
                require(name=='rootdummy','Unexpected animated translation owner')
                native=interpolate(control,time,typ)*float(row['literalActorScaleToken'])
                delta=p-np.asarray(original)*uniform_scale
                p=native*uniform_scale+delta
            elif typ==20:rotation=qmatrix(interpolate(control,time,typ))
            else:require(typ==36 and np.all(control['values']==1),'Unsupported animated local scale')
        local=np.eye(4);local[:3,:3]=corrections[name]@rotation if name in corrections else rotation;local[:3,3]=p
        worlds[name]=local if node['parent']=='null' else visit(node['parent'])@local
        visiting.remove(name);return worlds[name]
    for name in skeleton:visit(name)
    return worlds

def pose_rigid_meshes(meshes,bind_frames,posed_frames):
    result=[]
    for mesh in meshes:
        joint=mesh['name'] if mesh['part']=='rig' else PART_JOINTS[mesh['part']].lower()
        require(joint in bind_frames and joint in posed_frames,'Mesh joint missing from pose')
        delta=np.asarray(posed_frames[joint])@np.linalg.inv(np.asarray(bind_frames[joint]))
        points=np.asarray(mesh['position'])@delta[:3,:3].T+delta[:3,3]
        result.append({**mesh,'position':points,'faces':np.asarray(mesh['faces']).copy()})
    return result

def foot_surface_bounds(meshes,bind_frames,posed_frames):
    posed=pose_rigid_meshes([m for m in meshes if m['part'] in ('footl','footr')],bind_frames,posed_frames)
    result={}
    for part in ('footl','footr'):
        points=[m['position'] for m in posed if m['part']==part and m.get('render',True)]
        require(points,'Missing visible foot surface')
        xyz=np.concatenate(points)
        result[part]={'minimumZ':float(xyz[:,2].min()),'boundsMeters':[xyz.min(0).tolist(),xyz.max(0).tolist()]}
    return result


def pose_samples(baseline,new_local_positions=None,uniform_scale=1.,foot_plant_bound_meters=.002,
                 meshes=None,bind_frames=None,declared_floor_z=None,local_rotation_offsets=None,*,local_rotation_corrections=None):
    require(np.isfinite(foot_plant_bound_meters) and foot_plant_bound_meters>0,'Explicit positive plant diagnostic bound required')
    for path,pin in baseline.get('inputPins',{}).items():require(sha(path)==pin,'Accepted pose input changed')
    corrections=rotation_corrections(baseline['skeleton'],local_rotation_offsets,local_rotation_corrections)
    key_hash=native_keys_hash(baseline)
    source_standing=evaluate_adjusted(baseline,'pause1',0,{},uniform_scale)
    candidate_standing=evaluate_adjusted(baseline,'pause1',0,new_local_positions or {},uniform_scale,local_rotation_corrections=corrections)
    rows=[]
    for name,clip in baseline['clips'].items():
        for time in sample_native_times(clip):
            source=evaluate_adjusted(baseline,name,time,{},uniform_scale)
            posed=source if new_local_positions is None and uniform_scale==1 and not corrections else evaluate_adjusted(baseline,name,time,new_local_positions or {},uniform_scale,local_rotation_corrections=corrections)
            max_displacement=max(float(np.linalg.norm(posed[n][:3,3]-source[n][:3,3])) for n in source)
            if not corrections:require(all(np.array_equal(source[n][:3,:3],posed[n][:3,:3]) for n in source),'Accepted orientation keys changed')
            feet={n:{'acceptedPositionMeters':source[n][:3,3].tolist(),'previewPositionMeters':posed[n][:3,3].tolist(),
                      'positionDriftMeters':float(np.linalg.norm(posed[n][:3,3]-source[n][:3,3])),
                      'zDriftMeters':float(posed[n][2,3]-source[n][2,3])} for n in ('lfoot_g','rfoot_g')}
            for node,foot in feet.items():
                own_delta=posed[node][:3,3]-candidate_standing[node][:3,3]
                original_delta=source[node][:3,3]-source_standing[node][:3,3]
                difference=own_delta-original_delta
                foot.update({'staticStanceDisplacementMeters':float(np.linalg.norm(candidate_standing[node][:3,3]-source_standing[node][:3,3])),
                             'candidateMotionFromOwnStandingMeters':own_delta.tolist(),
                             'scaledAcceptedMotionFromOwnStandingMeters':original_delta.tolist(),
                             'dynamicPlantResidualMeters':float(np.linalg.norm(difference)),
                             'dynamicPlantResidualXYZMeters':difference.tolist(),
                             'candidateFootExcursionMeters':float(np.linalg.norm(own_delta))})
            surfaces=foot_surface_bounds(meshes,bind_frames,posed) if meshes is not None and bind_frames is not None else None
            rows.append({'clip':name,'timeSeconds':time,'jointWorldMatrices':{n:m.tolist() for n,m in posed.items()},
                         'maximumJointDisplacementFromAcceptedMeters':max_displacement,'feet':feet,
                         'footSurfaces':surfaces,
                         'pelvisRotationDifferenceDegrees':rotation_difference_degrees(posed['pelvis_g'],source['pelvis_g']) if 'pelvis_g' in source else None,
                         'upperLeanRotationDifferenceDegrees':rotation_difference_degrees(posed['torso_g'],source['torso_g']) if 'torso_g' in source else None,
                         'nativeOrientationAndBreathingKeysPreserved':True,
                         'localRotationCorrectionsApplied':bool(corrections)})
    worst=max(rows,key=lambda r:r['maximumJointDisplacementFromAcceptedMeters'])
    foot_worst=max(rows,key=lambda r:max(f['positionDriftMeters'] for f in r['feet'].values()))
    drift=max(f['positionDriftMeters'] for f in foot_worst['feet'].values())
    dynamic_worst=max(rows,key=lambda r:max(f['dynamicPlantResidualMeters'] for f in r['feet'].values()))
    dynamic_drift=max(f['dynamicPlantResidualMeters'] for f in dynamic_worst['feet'].values())
    standing=next(r for r in rows if r['clip']=='pause1' and r['timeSeconds']==0)
    for path,pin in baseline.get('inputPins',{}).items():require(sha(path)==pin,'Accepted pose input changed during sampling')
    require(native_keys_hash(baseline)==key_hash,'Native orientation/breathing keys mutated during preview')
    return {'samples':rows,'standingSample':{'clip':'pause1','timeSeconds':0.},
            'nativeKeysSha256Before':key_hash,'nativeKeysSha256After':native_keys_hash(baseline),
            'localRotationCorrections':{n:r.tolist() for n,r in corrections.items()},
            'rotationComposition':'left-local correction @ native local orientation; hierarchical world composition',
            'standingFootJointDriftMeters':max(f['positionDriftMeters'] for f in standing['feet'].values()),
            'worstFootDrift':{'clip':foot_worst['clip'],'timeSeconds':foot_worst['timeSeconds'],'maximumDriftMeters':drift},
            'worstDynamicPlantResidual':{'clip':dynamic_worst['clip'],'timeSeconds':dynamic_worst['timeSeconds'],'maximumDriftMeters':dynamic_drift},
            'standingFootSurfaces':standing['footSurfaces'],
            'declaredFloorZ':declared_floor_z,
            'standingSoleHeightResidualMeters':max(abs(f['minimumZ']-declared_floor_z) for f in standing['footSurfaces'].values()) if standing['footSurfaces'] is not None and declared_floor_z is not None else None,
            'footPlantDiagnosticBoundMeters':foot_plant_bound_meters,
            'footPlantDiagnosticStatus':'dynamic-motion-unresolved' if dynamic_drift>foot_plant_bound_meters else 'sampled-dynamic-joint-bound-pass; standing stance and foot-surface review pending',
            'motionFitValidated':False,'perPartFootShiftsApplied':False,'poseFloorNormalizationApplied':False,
            'measuredWorstSample':{'clip':worst['clip'],'timeSeconds':worst['timeSeconds'],
            'metric':'maximum joint displacement from accepted baseline','valueMeters':worst['maximumJointDisplacementFromAcceptedMeters']},
            'limitations':['Finite endpoints/native-key/midpoint samples; continuous motion and collisions unverified',
                           'Static local rotations/positions alter preview geometry; native orientation and breathing keys are unchanged; contacts require review',
                           baseline.get('maleMotion','Native idle sampling only; runtime motion unverified')],
            'animationFilesWritten':False,'oldCorrectiveArraysApplied':False}
