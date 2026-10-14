"""Bounded in-memory rigid-part preview fitting; no game assets or animation edits.

All requested measurements are remeasured on the resulting triangles. Missing
ownership intersections remain unavailable. Surface/connector acceptance is never
inferred from numerical results.
"""
import hashlib
import numpy as np
from .silhouette_model import measure, cross_section
from .target_contract import PART_JOINTS

SEGMENTS = {'upperArmProjectedLength': (('lbicep_g','lforearm_g'),('rbicep_g','rforearm_g')),
            'forearmProjectedLength': (('lforearm_g','lhand_g'),('rforearm_g','rhand_g')),
            'shinProjectedLength': (('lshin_g','lfoot_g'),('rshin_g','rfoot_g'))}
ENDS = {'bicepl':'lforearm_g','bicepr':'rforearm_g','forel':'lhand_g','forer':'rhand_g',
        'legl':'lshin_g','legr':'rshin_g','shinl':'lfoot_g','shinr':'rfoot_g',
        'chest':'neck_g','neck':'head_g'}
PARTS = {'chest':('chest','pelvis'), 'waist':('chest','pelvis'),
         'midThigh':('legl','legr'), 'knee':('legl','shinl','legr','shinr'),
         'calf':('shinl','shinr'), 'ankle':('shinl','footl','shinr','footr')}
SIDE_OWNERS = {'knee': (('legl','shinl'),('legr','shinr')),
               'ankle': (('shinl','footl'),('shinr','footr'))}
DEFERRED_RADIAL_TARGETS = {'kneeWidth': 'Existing donor basis is a leg-owned terminal/cap slice, not a full knee envelope; fitting it creates a narrow stem/cuff.',
                         'kneeDepth': 'Existing donor basis is a leg-owned terminal/cap slice, not a full knee envelope; fitting it creates a narrow stem/cuff.'}


def geometry_hash(meshes):
    h=hashlib.sha256()
    for m in meshes:
        h.update((m['part']+'\0'+m['name']+'\0').encode())
        h.update(bytes([bool(m.get('render',True))]))
        for a,dtype in ((m['position'],'<f8'),(m['faces'],'<i8')):
            a=np.asarray(a,dtype=dtype);h.update(np.asarray(a.shape,dtype='<i8').tobytes());h.update(a.tobytes())
    return h.hexdigest()


def copy_meshes(meshes):
    return [{**m,'position':np.asarray(m['position']).copy(),'faces':np.asarray(m['faces']).copy()} for m in meshes]


def requested(packet):
    return {k:float(p['modelFittingMeters']) for k,p in packet['proposedTargets'].items()
            if p.get('modelFittingMeters') is not None and np.isfinite(p['modelFittingMeters']) and p['modelFittingMeters']>0}


def target_planes(packet,height,ground):
    result={}
    for section in PARTS:
        row=packet.get('views',{}).get('front',{}).get(section+'Height',{})
        fraction=row.get('value')
        if fraction is not None and np.isfinite(fraction) and 0<fraction<1:
            result[section]={'fraction':float(fraction),'z':ground+float(fraction)*height}
    return result


def smooth_factors(z,knots):
    """Positive monotone interpolation within each interval, no overshoot."""
    if not knots:
        return np.ones_like(np.asarray(z),dtype=float)
    rows=sorted(knots)
    if len({float(k[0]) for k in rows})!=len(rows) or any(not np.isfinite(k[1]) or k[1]<=0 for k in rows):
        raise ValueError('Distinct planes and positive finite factors required')
    z=np.asarray(z,dtype=float); xs=np.array([r[0] for r in rows]);ys=np.array([r[1] for r in rows])
    if len(rows)==1:
        return np.full_like(z,ys[0])
    index=np.clip(np.searchsorted(xs,z,side='right')-1,0,len(xs)-2)
    t=np.clip((z-xs[index])/(xs[index+1]-xs[index]),0,1);t=t*t*(3-2*t)
    values=ys[index]+t*(ys[index+1]-ys[index])
    values=np.where(z<xs[0],ys[0],np.where(z>xs[-1],ys[-1],values))
    return values


def leg_centers(z,frames,side):
    """One piecewise thigh/knee/ankle centreline for both neighboring meshes.

    Use the same extrapolation above/below the joints, including overlapping
    leg/shin vertices. This prevents independent axes from splitting the join.
    """
    names=(side+'thigh_g',side+'shin_g',side+'foot_g')
    points=np.array([frames[name][:3,3] for name in names])
    order=np.argsort(points[:,2]);points=points[order]
    heights=points[:,2]
    if np.any(np.diff(heights)<=1e-9):
        raise ValueError('Distinct leg joint heights required for shared centreline')
    z=np.asarray(z,dtype=float)
    index=np.clip(np.searchsorted(heights,z,side='right')-1,0,1)
    t=(z-heights[index])/(heights[index+1]-heights[index])
    return points[index]+t[:,None]*(points[index+1]-points[index])


def build_frames(source_frames,hierarchy,scale,ground,lengths):
    source={k:np.asarray(v,dtype=float) for k,v in source_frames.items()}
    target={}; visiting=set(); pivot=np.array([0.,0.,ground])
    specified={child:float(lengths[key]) for key,pairs in SEGMENTS.items() if key in lengths for _,child in pairs}
    def visit(name):
        if name in target:return target[name]
        if name in visiting:raise ValueError('Joint hierarchy cycle')
        visiting.add(name);parent=hierarchy[name]
        value=source[name].copy()
        if parent=='null':value[:3,3]=pivot+scale*(source[name][:3,3]-pivot)
        else:
            if parent not in source:raise ValueError('Missing source frame parent')
            delta=source[name][:3,3]-source[parent][:3,3];length=np.linalg.norm(delta)
            factor=specified[name]/length if name in specified and length>1e-12 else scale
            value[:3,3]=visit(parent)[:3,3]+delta*factor
        target[name]=value;visiting.remove(name);return value
    for name in source:visit(name)
    return target


def axial_assembly(meshes,source_frames,target_frames,scale,ground):
    result=[];pivot=np.array([0.,0.,ground])
    for mesh in meshes:
        part=mesh['part'];joint=PART_JOINTS.get(part)
        points=np.asarray(mesh['position']);end=ENDS.get(part)
        if joint and joint in source_frames:
            start=np.asarray(source_frames[joint])[:3,3]; destination=np.asarray(target_frames[joint])[:3,3]
            delta=points-start
            if end and end in source_frames:
                old=np.asarray(source_frames[end])[:3,3]-start;new=np.asarray(target_frames[end])[:3,3]-destination
                length=np.linalg.norm(old)
                if length>1e-12:
                    axis=old/length;t=delta@axis
                    mapped=destination+(delta-t[:,None]*axis)*scale+t[:,None]/length*new
                else:mapped=destination+delta*scale
            else:mapped=destination+delta*scale
        else:mapped=pivot+(points-pivot)*scale
        row={**mesh,'position':mapped,'faces':np.asarray(mesh['faces']).copy()}
        if joint and joint in target_frames:row['attachmentFrame']=np.asarray(target_frames[joint]).tolist()
        result.append(row)
    return result


def orthogonal_arm_width(meshes,start,end):
    """Exact triangle slice normal to frontal XZ bone axis at its midpoint."""
    start=np.asarray(start,float);end=np.asarray(end,float);axis=end-start
    normal=np.array([axis[0],0.,axis[2]]);length=np.linalg.norm(normal)
    if length<=1e-10:return None
    normal/=length;direction=np.array([normal[2],0.,-normal[0]]);mid=(start+end)/2
    values=[]
    for mesh in meshes:
        if not mesh.get('render',True):continue
        for face in mesh['faces']:
            vertices=np.asarray(mesh['position'])[face];distance=(vertices-mid)@normal
            for i,j in ((0,1),(1,2),(2,0)):
                if abs(distance[i])<=1e-9:values.append(float(vertices[i]@direction))
                if distance[i]*distance[j]<0:
                    p=vertices[i]+distance[i]/(distance[i]-distance[j])*(vertices[j]-vertices[i])
                    values.append(float(p@direction))
    return float(max(values)-min(values)) if len(values)>=2 else None


def exact_dimensions(meshes,joints,planes):
    result={}
    for key,owners,pairs in (
        ('upperArmWidth',('bicepl','bicepr'),SEGMENTS['upperArmProjectedLength']),
        ('forearmWidth',('forel','forer'),SEGMENTS['forearmProjectedLength'])):
        values=[]
        for part,(a,b) in zip(owners,pairs):
            if a not in joints or b not in joints:continue
            values.append(orthogonal_arm_width([m for m in meshes if m['part']==part],joints[a],joints[b]))
        result[key]=float(np.mean(values)) if len(values)==2 and all(v is not None and v>0 for v in values) else None
    for section,plane in planes.items():
        for suffix,axis in (('Width',0),('Depth',1)):
            if section in ('chest','waist'):
                selected=[m for m in meshes if m['part'] in PARTS[section]]
                value=cross_section(selected,plane['z'],axis)
            else:
                owners=SIDE_OWNERS.get(section,tuple((p,) for p in PARTS[section]))
                values=[cross_section([m for m in meshes if m['part'] in side],plane['z'],axis) for side in owners]
                value=float(np.mean(values)) if all(v is not None and v>0 for v in values) else None
            result[section+suffix]=value
    for key,pairs in SEGMENTS.items():
        values=[np.linalg.norm(np.asarray(joints[b])-joints[a]) for a,b in pairs if a in joints and b in joints]
        result[key]=float(np.mean(values)) if len(values)==2 else None
    for key,axis in (('footWidth',0),('footLength',1)):
        values=[]
        for part in ('footl','footr'):
            points=[m['position'] for m in meshes if m['part']==part and m.get('render',True)]
            if points:values.append(float(np.ptp(np.concatenate(points)[:,axis])))
        result[key]=float(np.mean(values)) if len(values)==2 else None
    return result


def fit_contours(meshes,joints,frames,hierarchy,packet,sections=None,preserve=False,max_iterations=6,fixed_bind=False):
    """Return {meshes,joints,frames,receipt}; source arrays are never mutated.

    hierarchy maps every frame name to parent name. Input geometry is world-space
    with complete source-node transforms already evaluated. Pose evaluation belongs
    to the caller and must use the returned bind frames consistently.
    """
    source_frames={k:np.asarray(v,dtype=float).copy() for k,v in frames.items()}
    if set(source_frames)!=set(hierarchy):raise ValueError('Complete frame hierarchy required')
    source_measure=measure(meshes,joints);ground=source_measure['boundsMeters'][0][2]
    height=float(packet['targetStatureMeters']); goals=requested(packet)
    if not np.isfinite(height) or height<=0:raise ValueError('Positive target stature required')
    if preserve:
        fitted=copy_meshes(meshes);new_joints={k:list(v) for k,v in joints.items()};target_frames=source_frames
        scale=1.;profiles={};iterations=0;stature_solved=abs(source_measure['bindStatureMeters']-height)<1e-6
    else:
        def assemble_at(s):
            f=build_frames(source_frames,hierarchy,s,ground,goals)
            m=axial_assembly(meshes,source_frames,f,s,ground)
            j={k:f[k][:3,3].tolist() for k in joints}
            return m,j,f,measure(m,j)['bindStatureMeters']
        low,high=.01,10.; a=assemble_at(low)[3];b=assemble_at(high)[3]
        stature_solved=a<=height<=b
        if fixed_bind:
            scale=1.;stature_solved=abs(source_measure['bindStatureMeters']-height)<1e-6
        elif stature_solved:
            for _ in range(32):
                middle=(low+high)/2
                if assemble_at(middle)[3]<height:low=middle
                else:high=middle
            scale=(low+high)/2
        else:scale=height/source_measure['bindStatureMeters']
        if fixed_bind:
            base=copy_meshes(meshes);new_joints={k:list(v) for k,v in joints.items()};target_frames={k:v.copy() for k,v in source_frames.items()}
        else:base,new_joints,target_frames,_=assemble_at(scale)
        # Torso uses ONE continuous field for chest and pelvis; their mutual
        # surfaces see the same map. Limb groups retain their boundary factors.
        groups={'torso':('chest','pelvis'),'bicepl':('bicepl','forel'),'bicepr':('bicepr','forer'),
                'legl':('legl','shinl','footl'),'legr':('legr','shinr','footr')}
        profiles={}; measured=measure(base,new_joints); planes=target_planes(packet,measured['bindStatureMeters'],measured['boundsMeters'][0][2])
        for group,parts in groups.items():
            selected=[m['position'] for m in base if m['part'] in parts and m.get('render',True)]
            if not selected:continue
            points=np.concatenate(selected);lo,hi=float(points[:,2].min()),float(points[:,2].max())
            if hi-lo<=1e-9:continue
            profile={'parts':parts,'zBounds':[lo,hi],'x':{lo:1.,hi:1.},'y':{lo:1.,hi:1.},'keys':{}}
            wanted=('chest','waist') if group=='torso' else ('midThigh','knee','calf','ankle') if group.startswith('leg') else ()
            for section in wanted:
                if section not in planes:continue
                z=planes[section]['z']
                # A target plane outside owning geometry stays unavailable.
                if not lo+1e-6<z<hi-1e-6:continue
                for suffix,field in (('Width','x'),('Depth','y')):
                    key=section+suffix
                    corrected_knee=packet['proposedTargets'].get(key,{}).get('kneeUnionBasis') is True
                    if key in goals and (key not in DEFERRED_RADIAL_TARGETS or corrected_knee):
                        profile[field][z]=1.;profile['keys'][key]=(field,z)
            if group.startswith('leg'):
                footpart='footl' if group=='legl' else 'footr'
                footpoints=[m['position'] for m in base if m['part']==footpart and m.get('render',True)]
                footbounds=np.concatenate(footpoints)[:,2] if footpoints else None
                z=float(footbounds.min()+.25*np.ptp(footbounds)) if footbounds is not None else lo+.25*(hi-lo)
                for key,field in (('footWidth','x'),('footLength','y')):
                    if key in goals:
                        # Entire lower foot contour, broad transition to the
                        # unchanged upper ankle terminal, no short cuff band.
                        profile[field][lo]=1.;profile[field][z]=1.;profile['keys'][key]=(field,z)
            if group.startswith('bicep'):
                side='l' if group=='bicepl' else 'r'
                for key,pair in (('upperArmWidth',(side+'bicep_g',side+'forearm_g')),('forearmWidth',(side+'forearm_g',side+'hand_g'))):
                    if key in goals and all(n in new_joints for n in pair):
                        z=float(np.mean([new_joints[n][2] for n in pair]))
                        if lo+1e-6<z<hi-1e-6:
                            profile['x'][z]=1.;profile['keys'][key]=('x',z)
            profiles[group]=profile
        if fixed_bind and 'torso' in profiles:
            p=profiles['torso']
            for name in ('lbicep_g','rbicep_g','lthigh_g','rthigh_g','pelvis_g','torso_g'):
                if name not in target_frames:continue
                z=float(target_frames[name][2,3])
                if p['zBounds'][0]<z<p['zBounds'][1] and not any(abs(z-kz)<1e-6 for _,kz in p['keys'].values()):
                    p['x'][z]=1.;p['y'][z]=1.
        bind_frames={k:v.copy() for k,v in target_frames.items()}
        branch_roots=('lbicep_g','rbicep_g','lthigh_g','rthigh_g')
        def branch_for(name):
            seen=set()
            while name!='null':
                if name in branch_roots:return name
                if name in seen:raise ValueError('Joint hierarchy cycle')
                seen.add(name);name=hierarchy[name]
            return None
        def apply_profiles():
            out=copy_meshes(base)
            moved_frames={k:v.copy() for k,v in bind_frames.items()};deltas={};torso=profiles.get('torso')
            torso_center=bind_frames['pelvis_g'][:3,3] if 'pelvis_g' in bind_frames else np.zeros(3)
            if torso is not None:
                for root in branch_roots:
                    if root not in bind_frames:continue
                    old=bind_frames[root][:3,3];new=old.copy()
                    for axis,field in ((0,'x'),(1,'y')):
                        factor=float(smooth_factors(np.array([old[2]]),list(torso[field].items()))[0])
                        new[axis]=torso_center[axis]+(old[axis]-torso_center[axis])*factor
                    deltas[root]=np.zeros(3) if fixed_bind else new-old
                for name,frame in moved_frames.items():
                    root=branch_for(name)
                    if root in deltas:frame[:3,3]+=deltas[root]
                # Neighbor terminals inherit the same transverse endpoint map;
                # this is a derived geometric anchor, not a measured hip span.
                for group in ('bicepl','bicepr','legl','legr'):
                    if group not in profiles:continue
                    p=profiles[group];root=PART_JOINTS[group];z=bind_frames[root][2,3]
                    for field in ('x','y'):
                        factor=float(smooth_factors(np.array([z]),list(torso[field].items()))[0])
                        p[field][p['zBounds'][1]]=factor
            for mesh in out:
                joint=PART_JOINTS.get(mesh['part']);root=branch_for(joint) if joint and joint in hierarchy else None
                if root in deltas:mesh['position']+=deltas[root]
                if joint and joint in moved_frames:mesh['attachmentFrame']=moved_frames[joint].tolist()
                profile=next((p for p in profiles.values() if mesh['part'] in p['parts']),None)
                if profile is None:continue
                joint=PART_JOINTS[mesh['part']];start=moved_frames[joint][:3,3];end=ENDS.get(mesh['part'])
                points=mesh['position'];centers=np.repeat(start[None,:],len(points),axis=0)
                if end and end in moved_frames:
                    finish=moved_frames[end][:3,3];dz=finish[2]-start[2]
                    if abs(dz)>1e-9:centers=start+(points[:,2]-start[2])[:,None]/dz*(finish-start)
                if profile['parts'] in (('legl','shinl','footl'),('legr','shinr','footr')):
                    side='l' if profile['parts'][0]=='legl' else 'r'
                    centers=leg_centers(points[:,2],moved_frames,side)
                if profile['parts'] in (('bicepl','forel'),('bicepr','forer')):
                    side='l' if profile['parts'][0]=='bicepl' else 'r'
                    aliases={side+'thigh_g':moved_frames[side+'bicep_g'],side+'shin_g':moved_frames[side+'forearm_g'],side+'foot_g':moved_frames[side+'hand_g']}
                    centers=leg_centers(points[:,2],aliases,side)
                if profile['parts']==('chest','pelvis'):
                    # Common torso centre keeps its shared part boundary coherent.
                    centers[:,0]=torso_center[0];centers[:,1]=torso_center[1]
                for axis,field in ((0,'x'),(1,'y')):
                    factor=smooth_factors(points[:,2],list(profile[field].items()))
                    points[:,axis]=centers[:,axis]+(points[:,axis]-centers[:,axis])*factor
            return out,moved_frames
        fitted=base;iterations=0
        for iterations in range(1,max_iterations+1):
            actual=exact_dimensions(fitted,new_joints,planes);largest=0.
            for profile in profiles.values():
                for key,(field,z) in profile['keys'].items():
                    value=actual.get(key)
                    if value is None or value<=0:continue
                    ratio=goals[key]/value;largest=max(largest,abs(ratio-1))
                    factor=float(np.clip(profile[field][z]*ratio,.1,8.))
                    profile[field][z]=factor
                    if key.startswith('foot'):profile[field][profile['zBounds'][0]]=factor
            fitted,target_frames=apply_profiles()
            new_joints={k:target_frames[k][:3,3].tolist() for k in joints}
            if largest<1e-4:break
    measured=measure(fitted,new_joints); planes=target_planes(packet,measured['bindStatureMeters'],measured['boundsMeters'][0][2])
    actual=exact_dimensions(fitted,new_joints,planes)
    residuals={key:{'requestedMeters':value,'actualMeters':actual.get(key),
                   'deltaMeters':actual[key]-value if actual.get(key) is not None else None,
                   'relativeResidualPercent':100*(actual[key]/value-1) if actual.get(key) is not None else None,
                   'status':'identity preserved' if preserve else 'measured preview residual' if actual.get(key) is not None else 'owning intersection or measurement unavailable'} for key,value in goals.items()}
    for key,reason in DEFERRED_RADIAL_TARGETS.items():
        if key in residuals and not preserve and packet['proposedTargets'][key].get('kneeUnionBasis') is not True:
            residuals[key]['status']='deferred: inappropriate terminal-slice target basis'
            residuals[key]['reason']=reason
    serialized={name:{**row,'x':[[z,s] for z,s in sorted(row['x'].items())],
                         'y':[[z,s] for z,s in sorted(row['y'].items())]} for name,row in profiles.items()}
    positive=all(np.isfinite(m['position']).all() for m in fitted) and all(s>0 for p in serialized.values() for _,s in p['x']+p['y'])
    receipt={'identityPreserved':preserve,'sourceGeometryHash':geometry_hash(meshes),'previewGeometryHash':geometry_hash(fitted),
             'targetRequestedMeters':goals,'actualMeasurementsMeters':actual,'residuals':residuals,'targetPlanes':planes,
             'applied':{'supportedSegments':[] if preserve else [k for k in SEGMENTS if k in goals],
                        'widthDepthFields':[] if preserve else sorted({key for p in profiles.values() for key in p['keys']}),
                        'unknownDimensionScale':scale},'partProfiles':serialized,'iterations':iterations,
             'unavailable':[key for key in packet['proposedTargets'] if key not in goals or actual.get(key) is None],
             'deferredRadialTargets':{key:reason for key,reason in DEFERRED_RADIAL_TARGETS.items()
                 if key in goals and not preserve and packet['proposedTargets'][key].get('kneeUnionBasis') is not True},
             'kneeMeasurementBasis':'bilateral mean of same-side leg+shin projected union at explicit target knee plane; corrected proposals require kneeUnionBasis=true',
             'constraints':{'statureRequestedMeters':height,'statureActualMeters':measured['bindStatureMeters'],
                'statureResidualMeters':measured['bindStatureMeters']-height,'statureSolved':stature_solved,
                'positiveFactors':positive,'terminalProfilesPreserved':'shoulder/hip proximal terminals inherit torso factors; each whole leg+shin shares one continuous field through knee; lower shin and upper foot ankle1; torso union bounds1',
                'jointCenterPolicy':'shoulder/hip centres derived from shared torso field; descendants translated together, measured segment distances preserved; no new measured hip span inferred',
                'visualContinuity':'pending; shoulder/hip/limb neighbor joins require review; no visible shelf acceptance',
                'rigRotationsUnchanged':all(np.array_equal(source_frames[k][:3,:3],target_frames[k][:3,:3]) for k in source_frames)},
             'sourceShapeUnknownPartsPolicy':'uniform axial/attachment transform only; hidden hip/head/neck/hand shapes not inferred',
             'connectorCertification':False,'motionCertification':False,'referenceApproved':False,'productionAcceptance':False}
    if preserve and (receipt['sourceGeometryHash']!=receipt['previewGeometryHash'] or joints!=new_joints):raise ValueError('Human Fit identity failed')
    return {'meshes':fitted,'joints':new_joints,'frames':target_frames,'receipt':receipt}

RIG_ANCHORS = {'shoulderHeight':('lbicep_g','rbicep_g'),
               'elbowHeight':('lforearm_g','rforearm_g'),
               'wristHeight':('lhand_g','rhand_g'),
               'kneeHeight':('lshin_g','rshin_g'),
               'ankleHeight':('lfoot_g','rfoot_g')}


def monotone_map(z, knots):
    rows=sorted(knots)
    x=np.array([r[0] for r in rows],float);y=np.array([r[1] for r in rows],float)
    if len(x)<2 or not np.isfinite(x).all() or not np.isfinite(y).all() or np.any(np.diff(x)<=1e-9) or np.any(np.diff(y)<=1e-9):
        raise ValueError('Longitudinal correspondence requires strictly increasing finite source and target heights')
    z=np.asarray(z,float);i=np.clip(np.searchsorted(x,z,side='right')-1,0,len(x)-2)
    return y[i]+(z-x[i])*(y[i+1]-y[i])/(x[i+1]-x[i])


def rig_values(frames, floor):
    result={key:float(np.mean([frames[n][2,3] for n in names]))-floor
            for key,names in RIG_ANCHORS.items() if all(n in frames for n in names)}
    for key,pair in (('shoulderSpan',RIG_ANCHORS['shoulderHeight']),('kneeSpan',RIG_ANCHORS['kneeHeight']),('ankleSpan',RIG_ANCHORS['ankleHeight'])):
        if all(n in frames for n in pair):result[key]=abs(float(frames[pair[1]][0,3]-frames[pair[0]][0,3]))
    return result


def fit_target(meshes,joints,frames,hierarchy,packet,sections=None,preserve=False,max_iterations=6):
    """V11 shared longitudinal surface/rig correspondence followed by contours.

    Every longitudinal plane is an explicit manual surface proxy, not inferred
    hip anatomy. Absolute joint targets constrain one shared continuous map.
    Incompatible absolute segment/height goals remain measured residuals.
    """
    if preserve:
        result=fit_contours(meshes,joints,frames,hierarchy,packet,sections,preserve=True,max_iterations=max_iterations)
        result['receipt']['refinement']={'identityBypass':True,'groundTranslationMeters':0.,'rigRotationsUnchanged':True}
        return result
    source_measure=measure(meshes,joints);floor=float(source_measure['boundsMeters'][0][2]);source_height=source_measure['bindStatureMeters']
    height=float(packet['targetStatureMeters']); scale=height/source_height
    refinement=packet.get('refinement',{});anchor_targets=refinement.get('rigTargets',{})
    knots={floor:floor,floor+source_height:floor+height};bindings=[]
    for section,row in refinement.get('sectionCorrespondences',{}).items():
        a=row.get('humanReferenceFraction');b=row.get('targetReferenceFraction')
        if a is not None and b is not None:
            if not (0<float(a)<1 and 0<float(b)<1):raise ValueError('Section correspondence outside stature')
            knots[floor+float(a)*source_height]=floor+float(b)*height
            bindings.append({'section':section,'sourceFraction':float(a),'targetFraction':float(b)})
    # Absolute above-floor rig anchors supplement the surface correspondences.
    # Separate sides retain their measured/source asymmetry about the mean.
    for key,names in RIG_ANCHORS.items():
        goal=anchor_targets.get(key,{}).get('modelFittingMeters')
        if goal is None or not all(n in frames for n in names):continue
        source_z=float(np.mean([np.asarray(frames[n])[2,3] for n in names]))
        knots[source_z]=floor+float(goal)
    ordered=sorted(knots.items());monotone_map(np.array([floor,floor+source_height]),ordered)
    base=copy_meshes(meshes);mapped_frames={k:np.asarray(v,float).copy() for k,v in frames.items()}
    for mesh in base:
        mesh['position'][:,0:2]*=scale
        mesh['position'][:,2]=monotone_map(mesh['position'][:,2],ordered)
    for frame in mapped_frames.values():
        frame[:2,3]*=scale;frame[2,3]=float(monotone_map(np.array([frame[2,3]]),ordered)[0])
    span_field=[]
    for key,pair in (('shoulderSpan',RIG_ANCHORS['shoulderHeight']),('kneeSpan',RIG_ANCHORS['kneeHeight']),('ankleSpan',RIG_ANCHORS['ankleHeight'])):
        span_goal=anchor_targets.get(key,{}).get('modelFittingMeters')
        if span_goal is None:continue
        if not all(n in mapped_frames for n in pair):raise ValueError('Span joints unavailable')
        z=float(np.mean([mapped_frames[n][2,3] for n in pair]))
        oldspan=abs(mapped_frames[pair[1]][0,3]-mapped_frames[pair[0]][0,3])
        if oldspan<=1e-9:raise ValueError('Positive source joint span required')
        span_field.append((z,float(span_goal)/oldspan))
    if span_field:
        span_field.sort();span_field=[(floor,span_field[0][1])]+span_field+[(floor+height,span_field[-1][1])]
        center=float(mapped_frames.get('pelvis_g',np.eye(4))[0,3])
        for mesh in base:
            p=mesh['position'];p[:,0]=center+(p[:,0]-center)*smooth_factors(p[:,2],span_field)
        for frame in mapped_frames.values():
            frame[0,3]=center+(frame[0,3]-center)*float(smooth_factors(np.array([frame[2,3]]),span_field)[0])
    # With fixed vertical anchors, preserve absolute segment lengths in XY when
    # feasible. Never scale the anchored assembly again to hide conflicts.
    adjusted={k:v.copy() for k,v in mapped_frames.items()};conflicts=[]
    goals=requested(packet)
    for key,pairs in SEGMENTS.items():
        if key not in goals:continue
        for parent,child in pairs:
            if parent not in adjusted or child not in adjusted:continue
            delta=adjusted[child][:3,3]-adjusted[parent][:3,3];dz=delta[2];length=goals[key]
            if key=='shinProjectedLength' and any(anchor_targets.get(k,{}).get('modelFittingMeters') is not None for k in ('kneeSpan','ankleSpan')):
                if abs(np.linalg.norm(delta)-length)>1e-6:
                    conflicts.append({'key':key,'child':child,'status':'absolute knee/ankle height and span anchors take priority; segment residual retained'})
                continue
            if abs(dz)>length+1e-9:
                conflicts.append({'key':key,'child':child,'verticalSeparationMeters':abs(float(dz)),'requestedMeters':length,'status':'incompatible with absolute height anchors'})
                continue
            radial=np.linalg.norm(delta[:2]);desired=np.sqrt(max(0.,length*length-dz*dz))
            if radial<=1e-10 and desired>1e-9:
                conflicts.append({'key':key,'child':child,'status':'horizontal direction unavailable; no inferred direction'})
                continue
            new=adjusted[child][:3,3].copy()
            if radial>1e-10:new[:2]=adjusted[parent][:2,3]+delta[:2]*(desired/radial)
            move=new-adjusted[child][:3,3]
            for name in adjusted:
                cursor=name;seen=set()
                while cursor!='null' and cursor not in seen:
                    if cursor==child:
                        adjusted[name][:3,3]+=move;break
                    seen.add(cursor);cursor=hierarchy[cursor]
    base=axial_assembly(base,mapped_frames,adjusted,1.,floor)
    mapped_joints={k:adjusted[k][:3,3].tolist() for k in joints}
    result=fit_contours(base,mapped_joints,adjusted,hierarchy,packet,sections,max_iterations=max_iterations,fixed_bind=True)
    # One complete-assembly floor correction only. No individual foot nudge.
    current_floor=float(measure(result['meshes'],result['joints'])['boundsMeters'][0][2]);translation=floor-current_floor
    for mesh in result['meshes']:mesh['position'][:,2]+=translation
    for frame in result['frames'].values():frame[2,3]+=translation
    result['joints']={k:result['frames'][k][:3,3].tolist() for k in joints}
    for mesh in result['meshes']:
        joint=PART_JOINTS.get(mesh['part'])
        if joint in result['frames']:mesh['attachmentFrame']=result['frames'][joint].tolist()
    receipt=result['receipt'];receipt['sourceGeometryHash']=geometry_hash(meshes);receipt['previewGeometryHash']=geometry_hash(result['meshes'])
    actual_measure=measure(result['meshes'],result['joints']);actual=rig_values(result['frames'],floor)
    receipt['rigLandmarksMeters']=actual
    receipt['rigTargetResiduals']={key:{'requestedMeters':row['modelFittingMeters'],'actualMeters':actual.get(key),
        'deltaMeters':actual[key]-row['modelFittingMeters'] if key in actual else None,
        'status':row.get('status'),'uncertaintyMeters':row.get('uncertaintyMeters')}
        for key,row in anchor_targets.items() if row.get('modelFittingMeters') is not None}
    for key,row in receipt['rigTargetResiduals'].items():
        receipt['residuals']['rig:'+key]={**row,'relativeResidualPercent':None if row['actualMeters'] is None else 100*(row['actualMeters']/row['requestedMeters']-1)}
        receipt['targetRequestedMeters']['rig:'+key]=row['requestedMeters']
    receipt['refinement']={'longitudinalMap':[[a,b] for a,b in ordered],'sectionCorrespondences':bindings,
        'shoulderSpanField':span_field,'groundTranslationMeters':translation,'individualFootNudgesApplied':False,
        'segmentAnchorConflicts':conflicts,'rigRotationsUnchanged':all(np.array_equal(np.asarray(frames[k])[:3,:3],result['frames'][k][:3,:3]) for k in frames),
        'scope':'manual surface/rig correspondences; no hidden hip target; standing and motion contact unvalidated'}
    receipt['applied']['unknownDimensionScale']=scale
    receipt['constraints']['statureActualMeters']=actual_measure['bindStatureMeters']
    receipt['constraints']['statureResidualMeters']=actual_measure['bindStatureMeters']-height
    receipt['constraints']['statureSolved']=abs(actual_measure['bindStatureMeters']-height)<1e-6
    planes=target_planes(packet,actual_measure['bindStatureMeters'],floor)
    receipt['targetPlanes']=planes;receipt['actualMeasurementsMeters']=exact_dimensions(result['meshes'],result['joints'],planes)
    receipt['actualMeasurementsMeters'].update({'rig:'+key:value for key,value in actual.items()})
    for key,row in receipt['residuals'].items():
        value=receipt['actualMeasurementsMeters'].get(key);row['actualMeters']=value
        row['deltaMeters']=None if value is None else value-row['requestedMeters']
        row['relativeResidualPercent']=None if value is None else 100*(value/row['requestedMeters']-1)
        if any(c['key']==key for c in conflicts):row['status']='incompatible absolute segment/height constraints; measured residual retained'
    receipt['applied']['supportedSegments']=[key for key in SEGMENTS if key in goals and not any(c['key']==key for c in conflicts)]
    receipt['armWidthMeasurementBasis']='bilateral mean owned-part triangle slice at bone midpoint; normal=projected XZ bone axis; span along perpendicular projected XZ direction; no inferred depth'
    return result
