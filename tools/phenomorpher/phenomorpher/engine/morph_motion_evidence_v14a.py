"""Broader source-owned native motion evidence; accepted standing stays exact."""
import copy,json,hashlib,re
from pathlib import Path
import numpy as np
from .morph_preview_pose_v13 import (read,verified,sha,require,validate_pose_hierarchy,
    evaluate_adjusted,pose_rigid_meshes,native_keys_hash,sample_native_times)
from .target_animation_overlay import NativeIdleReader

REQUESTED=('walk','run','nwkickl','nwkickr')

def load_broader_motion(baseline,mapping_path):
    """Resolve first owning clip in the hash-bound Human ancestry, never by filename."""
    mapping=read(mapping_path);plan=read(verified(mapping['familyPlanLocal']))
    root=baseline['row']['root'];carrier=baseline['row']['carrier']
    if root in ('pfh0','pfh2'):
        row=next(r for r in plan['rows'] if r['root']==root)
        chain=row['sourceAncestry']
    else:
        row=next(r for r in plan['rows'] if r['winningIdleOwner']=='a_ba')
        first=next(i for i,r in enumerate(row['sourceAncestry']) if r['name']=='a_ba')
        chain=row['sourceAncestry'][first:]
    result=copy.deepcopy(baseline);result['inputPins']=dict(baseline['inputPins'])
    result['inputPins'][str(Path(mapping['familyPlanLocal']['path']).resolve())]=mapping['familyPlanLocal']['sha256']
    winners={};expected=chain[0]['name'];aliases={r['name'] for r in chain}
    for ancestor in chain:
        require(ancestor['name']==expected,'Motion ancestry ordering differs')
        original=ancestor['native'];key=str(Path(original['path']).resolve())
        require(key in mapping['sourceCopies'],'Missing durable native motion owner')
        pin=mapping['sourceCopies'][key];require(pin['sha256']==original['sha256'],'Motion owner copy differs')
        path=verified(pin);result['inputPins'][str(path)]=pin['sha256']
        blob=path.read_bytes()
        if blob[:4]!=b'\x00\x00\x00\x00':
            text=blob.decode('cp1252')
            require(re.findall(r'(?mi)^newmodel\s+(\S+)',text)==[ancestor['name']],'ASCII motion owner identity differs')
            require(re.findall(r'(?mi)^setsupermodel\s+\S+\s+(\S+)',text)==[ancestor['parent']],'ASCII motion ancestry differs')
            owned={n.lower() for n in re.findall(r'(?mi)^newanim\s+(\S+)',text)}
            require(not owned.intersection(REQUESTED),'Requested motion is ASCII-owned; native-only decoder cannot pass over it')
            expected=ancestor['parent'];continue
        decoded=NativeIdleReader(blob).decode(set(REQUESTED))
        require(decoded['name']==ancestor['name'] and decoded['parent']==ancestor['parent'],'Native motion owner chain differs')
        require(decoded['scale']==1.,'Unsupported native motion owner scale')
        for name,clip in decoded['clips'].items():
            if name in winners:continue
            converted=copy.deepcopy(clip);nodes={}
            for node,data in converted['nodes'].items():
                alias=carrier if node in aliases else node
                require(alias not in nodes,'Motion root alias collision')
                nodes[alias]=data
            converted['nodes']=nodes;converted['name']=name
            converted['resolvedNativeOwner']=ancestor['name']
            result['clips'][name]=converted
            winners[name]={'owner':ancestor['name'],'path':str(path),'sha256':pin['sha256'],
                'rootAliasOnly':True,'nativeControllerValuesModified':False}
        expected=ancestor['parent']
    require(expected=='null','Motion ancestry incomplete')
    require(set(winners)==set(REQUESTED),'Missing requested native motion clips')
    validate_pose_hierarchy(result['skeleton'],result['clips'],root,carrier)
    result['broaderMotionOwners']=winners
    require(native_keys_hash({'clips':{n:result['clips'][n] for n in baseline['clips']}})==native_keys_hash(baseline),'Accepted standing clips changed')
    return result

def dense_times(clip,subdivisions=4):
    require(type(subdivisions) is int and 1<=subdivisions<=16,'Bounded positive motion subdivisions required')
    times=sample_native_times(clip,include_midpoints=False)
    return sorted(set(times+[a+(b-a)*j/subdivisions for a,b in zip(times,times[1:]) for j in range(1,subdivisions)]))

def evaluate_motion_evidence(baseline,result,source_result=None):
    before=native_keys_hash(baseline);rows=[]
    source_result=result if source_result is None else source_result
    for name in REQUESTED:
        for time in dense_times(baseline['clips'][name]):
            world=evaluate_adjusted(baseline,name,time,result['localPositions'],result['uniformScale'],local_rotation_offsets=result.get('localRotationOffsets'))
            source_world=evaluate_adjusted(baseline,name,time,source_result['localPositions'],source_result['uniformScale'],local_rotation_offsets=source_result.get('localRotationOffsets'))
            meshes=pose_rigid_meshes(result['bindMeshes'],result['bindFrames'],world)
            source_meshes=pose_rigid_meshes(source_result['bindMeshes'],source_result['bindFrames'],source_world)
            soles={};source_soles={}
            for part in ('footl','footr'):
                soles[part]=float(np.concatenate([m['position'] for m in meshes if m['part']==part and m.get('render',True)])[:,2].min())
                source_soles[part]=float(np.concatenate([m['position'] for m in source_meshes if m['part']==part and m.get('render',True)])[:,2].min())
            feet={n:float(np.linalg.norm(world[n][:3,3]-source_world[n][:3,3])) for n in ('lfoot_g','rfoot_g')}
            score=max(abs(soles[p]-source_soles[p]) for p in soles)
            rows.append({'clip':name,'timeSeconds':time,'jointWorldMatrices':{n:m.tolist() for n,m in world.items()},
                'soleZMeters':soles,'comparisonSoleZMeters':source_soles,'footJointDifferenceMeters':feet,
                'maximumSoleDifferenceMeters':score,'nativeOrientationAndBreathingKeysPreserved':True})
    require(native_keys_hash(baseline)==before,'Source animation controller keys changed')
    for path,h in baseline['inputPins'].items():require(sha(path)==h,'Bound motion source changed')
    worst=max(rows,key=lambda r:(r['maximumSoleDifferenceMeters'],max(r['footJointDifferenceMeters'].values())))
    return {'kind':'source-owned-broader-native-motion-evidence-v14','samples':rows,
        'sampleCount':len(rows),'clips':list(REQUESTED),'resolvedOwners':baseline['broaderMotionOwners'],
        'keysSha256Before':before,'keysSha256After':native_keys_hash(baseline),
        'measuredWorstSample':{k:worst[k] for k in ('clip','timeSeconds','maximumSoleDifferenceMeters')},
        'comparisonBasis':'declared source result; same native clip and time, actual geometry soles',
        'airborneFeetAreNotPlantFailures':True,'poseFloorNormalizationApplied':False,
        'motionAcceptance':False,'nativeValidated':False,'clientValidated':False,'productionAccepted':False,
        'limitations':['Finite native-key interval quarter samples; continuous motion and client behavior unverified',
            'Accepted level-hips standing carriers retained; locomotion/kicks use original source-owned native clips unchanged']}
