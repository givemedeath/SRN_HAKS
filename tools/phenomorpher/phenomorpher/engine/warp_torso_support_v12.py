"""Chest shoulder support in source coordinates, before contour fitting.

Existing native pivots provide connector controls, not new anatomy targets.
Protected source neck neighbors and the lower chest remain byte-exact stage1.
"""
import numpy as np


def smoothstep(values):
    t=np.clip(np.asarray(values,float),0.,1.)
    return t*t*t*(10.+t*(-15.+6.*t))


def compact_kernel(distance,support):
    r=np.clip(np.asarray(distance,float)/support,0.,1.)
    return (1.-r)**4*(4.*r+1.)


def nearest_distances(points,cloud):
    points=np.asarray(points,float);cloud=np.asarray(cloud,float)
    if not len(cloud):return np.full(len(points),np.inf)
    result=np.empty(len(points))
    for begin in range(0,len(points),256):
        delta=points[begin:begin+256,None,:]-cloud[None,:,:]
        result[begin:begin+256]=np.sqrt(np.min(np.sum(delta*delta,axis=2),axis=1))
    return result


def support_field(points,anchors,displacements,neck_cloud,low_z,low_transition,
                  support=.23,neck_protection=.02,neck_transition=.12):
    """Compact C2 displacement field with exact source-neighbor protection.

    A two-control interpolation system compensates the protective gate at each
    shoulder. It rejects a shoulder hidden in a protected region rather than
    moving the neck or lower chest to force an impossible support.
    """
    points=np.asarray(points,float);anchors=np.asarray(anchors,float);delta=np.asarray(displacements,float)
    if anchors.shape!=(2,3) or delta.shape!=(2,3) or not np.isfinite(anchors).all() or not np.isfinite(delta).all():
        raise ValueError('Two finite native shoulder controls required')
    if min(support,low_transition,neck_transition)<=0 or neck_protection<0:raise ValueError('Positive broad support transitions required')
    def gate(p):
        neck=smoothstep((nearest_distances(p,neck_cloud)-neck_protection)/neck_transition)
        lower=smoothstep((p[:,2]-low_z)/low_transition)
        return neck*lower
    anchor_gate=gate(anchors)
    if np.any(anchor_gate<.10):raise ValueError('Native shoulder control conflicts with protected neck/lower-chest region')
    anchor_kernel=compact_kernel(np.linalg.norm(anchors[:,None,:]-anchors[None,:,:],axis=2),support)
    system=anchor_gate[:,None]*anchor_kernel
    if np.linalg.cond(system)>1e8:raise ValueError('Shoulder support controls are ill-conditioned')
    coefficients=np.linalg.solve(system,delta)
    weights=gate(points)[:,None]*compact_kernel(np.linalg.norm(points[:,None,:]-anchors[None,:,:],axis=2),support)
    field=weights@coefficients
    return field,{'supportSourceMeters':support,'neckProtectionSourceMeters':neck_protection,
        'neckTransitionSourceMeters':neck_transition,'lowerProtectionTopSourceZMeters':low_z,
        'lowerTransitionSourceMeters':low_transition,'controlGate':anchor_gate.tolist(),
        'controlResidualMeters':float(np.max(np.abs(system@coefficients-delta))),
        'protectedVertexCount':int(np.sum(gate(points)==0.)),
        'maximumDisplacementMeters':float(np.max(np.linalg.norm(field,axis=1))) if len(field) else 0.,
        'kernel':'compact Wendland C2 with quintic protected-neighborhood gates'}


def warp_torso_support(source_standing_meshes,stage1_meshes,source_frames,stage1_frames,
                       part_scales,uniform_scale=1.,preserve=False,support=.23):
    """Return (meshes, receipt), changing only eligible chest source points."""
    if len(source_standing_meshes)!=len(stage1_meshes):raise ValueError('Mesh inventories differ')
    for source,stage in zip(source_standing_meshes,stage1_meshes):
        if (source['part'],source['name'])!=(stage['part'],stage['name']) or not np.array_equal(source['faces'],stage['faces']):
            raise ValueError('Source/stage-one mesh inventory or faces changed')
    output=[{**m,'position':np.asarray(m['position']).copy(),'faces':np.asarray(m['faces']).copy()} for m in stage1_meshes]
    receipt={'kind':'native-shoulder-chest-support-v12','applied':False,'preserveIdentity':bool(preserve),
        'rigFramesChanged':False,'rigOrientationsChanged':False,'headNeckGeometryChanged':False,
        'anatomicalTargetsCreated':False,'surfaceJoinAcceptance':False,'productionAccepted':False}
    if preserve:return output,receipt
    required=('torso_g','neck_g','lbicep_g','rbicep_g')
    if any(k not in f for f in (source_frames,stage1_frames) for k in required):
        receipt['unavailable']='Native torso/neck/shoulder support frames missing';return output,receipt
    chest=[m for m in source_standing_meshes if m['part']=='chest' and len(m['position'])]
    if not chest:receipt['unavailable']='No native chest mesh';return output,receipt
    scale=float(part_scales.get('chest',uniform_scale))
    if not np.isfinite(scale) or scale<=0:raise ValueError('Positive chest uniform scale required')
    start=np.asarray(source_frames['torso_g'])[:3,3];target=np.asarray(stage1_frames['torso_g'])[:3,3]
    if any(not np.allclose(np.asarray(source_frames[k])[:3,:3],np.asarray(stage1_frames[k])[:3,:3],atol=1e-10,rtol=0) for k in required):
        raise ValueError('Chest support cannot silently change native rig orientations')
    anchors=np.asarray([source_frames[k][:3,3] for k in ('lbicep_g','rbicep_g')])
    nominal=target+scale*(anchors-start)
    desired=np.asarray([stage1_frames[k][:3,3] for k in ('lbicep_g','rbicep_g')]);delta=desired-nominal
    # The source neck mesh is an authored connector neighborhood. The fallback
    # is explicitly the existing neck pivot, never a new image landmark.
    neck=[np.asarray(m['position']) for m in source_standing_meshes if m['part']=='neck' and len(m['position'])]
    neck_cloud=np.concatenate(neck) if neck else np.asarray([source_frames['neck_g'][:3,3]])
    all_chest=np.concatenate([m['position'] for m in chest]);zmin,zmax=all_chest[:,2].min(),all_chest[:,2].max()
    low_z=float(zmin+.10*(zmax-zmin));low_transition=max(.10,min(support,.45*(zmax-zmin)))
    proofs=[]
    for index,(source,stage) in enumerate(zip(source_standing_meshes,stage1_meshes)):
        if source['part']!='chest' or not len(source['position']):continue
        points=np.asarray(source['position']);expected=target+scale*(points-start)
        if np.max(np.abs(expected-stage['position']))>1e-8:raise ValueError('Chest support must precede nonuniform contour fitting')
        field,proof=support_field(points,anchors,delta,neck_cloud,low_z,low_transition,support)
        output[index]['position']=np.asarray(stage['position'])+field;proof['meshNode']=source['name'];proofs.append(proof)
        # Zero field points use exact stage-one arrays, avoiding rounding drift.
        protected=np.all(field==0.,axis=1);output[index]['position'][protected]=np.asarray(stage['position'])[protected]
    receipt.update({'applied':bool(np.any(delta!=0.)),'shoulderCorrectionMeters':delta.tolist(),
        'nominalShoulderPositionsMeters':nominal.tolist(),'targetShoulderPositionsMeters':desired.tolist(),
        'sourceNeckProtectionBasis':'authored source neck vertices' if neck else 'native neck pivot fallback',
        'meshProofs':proofs,'lowerChestProtected':True,
        'limitations':['Native shoulder controls support chest connector placement; they do not define new chest anatomy.',
            'Shoulder ring correspondence and downstream contour compatibility require matched front/side/rear review.',
            'Positive/continuous support weights do not certify triangle geometry or motion acceptance.']})
    return output,receipt
