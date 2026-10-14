"""Differential segment geometry preview before contour fitting.

Native rig frames/orientations remain untouched. This is a continuous affine
long-axis correction per limb, not an approved connector or animation asset.
"""
import numpy as np


SEGMENTS={
    'bicepl':('lbicep_g','lforearm_g'),'bicepr':('rbicep_g','rforearm_g'),
    'forel':('lforearm_g','lhand_g'),'forer':('rforearm_g','rhand_g'),
    'legl':('lthigh_g','lshin_g'),'legr':('rthigh_g','rshin_g'),
    'shinl':('lshin_g','lfoot_g'),'shinr':('rshin_g','rfoot_g'),
}


def segment_transform(source_start,source_end,target_start,target_end,part_scale):
    """Return affine point map and proof; terminal planes have no pin bands.

    t = dot(sourceVertex-sourceStart, sourceAxis)/sourceLength is intentionally
    not clipped: the same affine field covers all source vertices, including
    authored connector overhangs. A nonpositive axial Jacobian is rejected.
    """
    a,b,c,d=[np.asarray(p,float) for p in (source_start,source_end,target_start,target_end)]
    scale=float(part_scale)
    if any(p.shape!=(3,) or not np.isfinite(p).all() for p in (a,b,c,d)) or not np.isfinite(scale) or scale<=0:
        raise ValueError('Finite segment endpoints and positive scale required')
    vector=b-a;length=float(np.linalg.norm(vector))
    if length<=1e-9:raise ValueError('Source segment has zero length')
    axis=vector/length;target_vector=d-c;correction=target_vector-scale*vector
    matrix=scale*np.eye(3)+np.outer(correction,axis)/length
    determinant=float(np.linalg.det(matrix))
    if not np.isfinite(determinant) or determinant<=1e-12:
        raise ValueError('Segment correction reverses/collapses source axial geometry')
    translation=c-matrix@a
    proof={'sourceLengthMeters':length,'targetLengthMeters':float(np.linalg.norm(target_vector)),
           'sourceAxis':axis.tolist(),'endpointCorrectionMeters':correction.tolist(),
           'jacobian':matrix.tolist(),'jacobianDeterminant':determinant,
           'sourceStartMeters':a.tolist(),'sourceEndMeters':b.tolist(),
           'targetStartMeters':c.tolist(),'targetEndMeters':d.tolist(),
           'startResidualMeters':float(np.linalg.norm(matrix@a+translation-c)),
           'endResidualMeters':float(np.linalg.norm(matrix@b+translation-d)),
           'clippedInfluence':False,'terminalSurfaceAcceptance':False}
    return matrix,translation,proof


def warp_segments(source_standing_meshes,stage1_meshes,source_frames,stage1_frames,
                  part_scales,uniform_scale=1.,preserve=False):
    """Return (warped meshes, receipt) without mutating source or stage one.

    The source and stage-one inventories must match exactly. Input stage one
    must still be a per-part uniform similarity, ensuring this cannot silently
    re-warp already contoured geometry. Nonlimb nodes retain stage-one points.
    """
    if len(source_standing_meshes)!=len(stage1_meshes):raise ValueError('Mesh inventories differ')
    output=[];proofs={};unavailable={};maximum_uniform_error=0.
    for source,stage in zip(source_standing_meshes,stage1_meshes):
        part=source['part']
        if (source['part'],source['name'])!=(stage['part'],stage['name']) or not np.array_equal(source['faces'],stage['faces']):
            raise ValueError('Source/stage-one mesh inventory or faces changed')
        points=np.asarray(stage['position'],float).copy()
        if points.shape!=np.asarray(source['position']).shape:raise ValueError('Vertex inventory changed')
        if not preserve and part in SEGMENTS:
            start,end=SEGMENTS[part];scale=float(part_scales.get(part,uniform_scale))
            if any(j not in frames for frames in (source_frames,stage1_frames) for j in (start,end)):
                unavailable[part]='Named source/stage-one segment endpoint missing'
            else:
                ss=np.asarray(source_frames[start])[:3,3];se=np.asarray(source_frames[end])[:3,3]
                ts=np.asarray(stage1_frames[start])[:3,3];te=np.asarray(stage1_frames[end])[:3,3]
                if not np.allclose(np.asarray(source_frames[start])[:3,:3],np.asarray(stage1_frames[start])[:3,:3],atol=1e-10,rtol=0):
                    raise ValueError('Segment warp cannot silently change native rig orientation')
                expected=ts+scale*(np.asarray(source['position'])-ss)
                error=float(np.max(np.abs(expected-points))) if points.size else 0.
                maximum_uniform_error=max(maximum_uniform_error,error)
                if error>1e-8:raise ValueError('Segment warp must precede width/depth fitting')
                matrix,translation,proof=segment_transform(ss,se,ts,te,scale)
                points=np.asarray(source['position'])@matrix.T+translation
                # Preserve byte-exact stage-one identity when no correction is
                # needed instead of introducing floating-point affine noise.
                if np.array_equal(te-ts,scale*(se-ss)):points=np.asarray(stage['position']).copy()
                proof['partScale']=scale;proof['meshNodes']=proofs.get(part,{}).get('meshNodes',[])+[source['name']]
                projection=(np.asarray(source['position'])-ss)@np.asarray(proof['sourceAxis'])/proof['sourceLengthMeters']
                proof['sourceVertexInfluenceRange']=[float(projection.min()),float(projection.max())] if len(projection) else None
                proofs[part]=proof
        output.append({**stage,'position':points,'faces':np.asarray(stage['faces']).copy()})
    return output,{'kind':'continuous-differential-segment-geometry-v12','applied':not preserve,
        'preserveIdentity':bool(preserve),'segments':proofs,'unavailable':unavailable,
        'maximumStage1UniformityErrorMeters':maximum_uniform_error,
        'rigFramesChanged':False,'rigOrientationsChanged':False,'widthDepthFittingApplied':False,
        'sourceMeshInventoryPreserved':True,'facesPreserved':True,
        'limitations':['Positive affine Jacobians and exact pivot endpoints do not approve surface connectors.',
            'Torso multiple-branch attachments, terminal rings and nonlimb neighbors still require shared source-correspondence fitting.',
            'Native standing/worst-motion contact and production acceptance remain pending.'],
        'surfaceJoinAcceptance':False,'productionAccepted':False}


# Explicit alias for orchestrators using the stage name.
warp_segment_geometry=warp_segments
