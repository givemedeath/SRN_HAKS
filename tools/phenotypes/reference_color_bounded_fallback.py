"""Copy only frozen visible fallback texels from accepted same-surface skin donors.

This is a diagnostic RGB operation. It never changes roles, source attributes or
normal/ORM maps, and it cannot establish an approved garment cut.
"""
import numpy as np

def require(condition, message):
    if not bool(condition):
        raise ValueError(message)

def original_manifold_neighbors(triangles):
    """Exact position welding is used only for the original shared-edge proof."""
    triangles = np.asarray(triangles)
    require(triangles.ndim == 3 and triangles.shape[1:] == (3, 3), 'Original triangle positions required')
    _, ids = np.unique(triangles.reshape(-1, 3), axis=0, return_inverse=True)
    ids = ids.reshape(-1, 3)
    edges = {}
    for face, row in enumerate(ids):
        for a, b in ((0, 1), (1, 2), (2, 0)):
            edges.setdefault(tuple(sorted((int(row[a]), int(row[b])))), []).append(face)
    neighbors = [set([i]) for i in range(len(triangles))]
    for members in edges.values():
        if len(members) == 2:
            a, b = members
            neighbors[a].add(b)
            neighbors[b].add(a)
    return neighbors

def validate_pairs(scope, fields, regions, contours, triangles, uniform_scale, expected_count):
    """Independently enforce all bounds on the already frozen target/donor pairs."""
    require(0 < uniform_scale and np.isfinite(uniform_scale), 'Positive uniform fitted scale required')
    coverage = np.asarray(fields['uvCoverage'], dtype=bool)
    h, w = coverage.shape
    y = np.asarray(scope['atlasY'], dtype=np.int64)
    x = np.asarray(scope['atlasX'], dtype=np.int64)
    seed = np.asarray(scope['sourceSkinDonorTexel'], dtype=np.int64)
    selected = np.asarray(scope['proposedAtMostTwoMm'], dtype=bool)
    require(y.shape == x.shape == seed.shape == selected.shape, 'Frozen pair array association differs')
    require(selected.sum() == expected_count, 'Frozen target count differs')
    require(((y >= 0) & (y < h) & (x >= 0) & (x < w)).all(), 'Target outside atlas')
    require(len(np.unique(y * w + x)) == len(y), 'Duplicate frozen target')
    y, x, seed = y[selected], x[selected], seed[selected]
    require(((seed >= 0) & (seed < h * w)).all(), 'Donor outside atlas')
    sy, sx = np.divmod(seed, w)
    require((np.maximum(abs(sy-y), abs(sx-x)) <= 4).all(), 'Donor exceeds four UV texels')
    require(((sy != y) | (sx != x)).all(), 'Self-copy cannot repair fallback')
    require(coverage[y,x].all() and coverage[sy,sx].all(), 'Covered source points required')
    protected = fields['uvProtected'] | fields['uvAmbiguous']
    require(not protected[y,x].any() and not protected[sy,sx].any(), 'Protected or overlapping UV sample rejected')
    require(not regions['accepted'][y,x].any() and not regions['paddingDestination'][y,x].any(), 'Targets must remain original fallback in parent')
    require(regions['accepted'][sy,sx].all() and (regions['ownedRole'][sy,sx] == 1).all(), 'Accepted literal skin donors required')
    require((contours['proposedPhotoRole'][y,x] == 1).all() and (contours['proposedPhotoRole'][sy,sx] == 1).all(), 'Canonical skin required at target and donor')
    require((scope['canonicalTargetPhotoRole'][selected] == 1).all() and (scope['canonicalDonorPhotoRole'][selected] == 1).all(), 'Frozen skin proposal association differs')
    require(scope['wholeFaceProposedSkin'][selected].all(), 'Mixed or unknown target face rejected')
    require(not scope['compatibleLiteralClothVeto'][selected].any(), 'Frozen compatible cloth veto rejected')
    require((scope['visibleEightDirections'][selected] & (scope['geometricIncidenceEightDirections'][selected] >= .15)).any(1).all(), 'Positive-incidence exact finite visibility required')
    owner = fields['sourceFace']
    face, donor_face = owner[y,x], owner[sy,sx]
    require(((face >= 0) & (face < len(triangles)) & (donor_face >= 0) & (donor_face < len(triangles))).all(), 'Source face association differs')
    require(np.array_equal(face, scope['sourceFace'][selected]), 'Frozen target face differs')
    positions, normals = fields['sourceBarycentricPosition'], fields['sourceAuthoredUnitNormal']
    p, dp, n, dn = positions[y,x].astype(float), positions[sy,sx].astype(float), normals[y,x].astype(float), normals[sy,sx].astype(float)
    require(np.array_equal(positions[y,x], scope['sourcePosition'][selected]) and np.array_equal(normals[y,x], scope['sourceAuthoredNormal'][selected]), 'Frozen target position/normal differs')
    require(np.isfinite(np.r_[p.ravel(),dp.ravel(),n.ravel(),dn.ravel()]).all(), 'Finite source attributes required')
    require(np.allclose(np.linalg.norm(n,axis=1),1,atol=2e-6) and np.allclose(np.linalg.norm(dn,axis=1),1,atol=2e-6), 'Authored unit normals required')
    distance = np.linalg.norm(p-dp,axis=1)*uniform_scale*1000
    dot = np.einsum('ij,ij->i',n,dn)
    require((distance <= 2 + 1e-6).all(), 'Donor exceeds two fitted millimetres')
    require(np.allclose(distance,scope['sourceDonorDistanceMm'][selected],atol=1e-6,rtol=1e-5), 'Frozen donor distance differs')
    cosine = np.cos(np.deg2rad(5))
    require((dot >= cosine-1e-7).all(), 'Donor normal differs by more than five degrees')
    neighbors = original_manifold_neighbors(triangles)
    require(all(int(b) in neighbors[int(a)] for a,b in zip(face,donor_face)), 'Donor is neither same face nor original two-face shared edge')
    # A neighboring literal cloth sample with compatible source surface prevents
    # propagation even if the stored proposal veto was corrupted.
    for dy in range(-4,5):
        for dx in range(-4,5):
            qy,qx=y+dy,x+dx
            inside=(qy>=0)&(qy<h)&(qx>=0)&(qx<w)
            indices=np.flatnonzero(inside)
            qy,qx=qy[inside],qx[inside]
            use=regions['accepted'][qy,qx]&(regions['ownedRole'][qy,qx]==2)
            indices,qy,qx=indices[use],qy[use],qx[use]
            if len(indices):
                dist=np.linalg.norm(p[indices]-positions[qy,qx],axis=1)*uniform_scale*1000
                ndot=np.einsum('ij,ij->i',n[indices],normals[qy,qx])
                adjacent=np.asarray([int(b) in neighbors[int(a)] for a,b in zip(face[indices],owner[qy,qx])])
                require(not ((dist<=2)&(ndot>=cosine)&adjacent).any(), 'Nearby compatible literal cloth prohibits propagation')
    return {'targetY':y,'targetX':x,'donorY':sy,'donorX':sx,'targetFace':face,'donorFace':donor_face,'targetPosition':p,'donorPosition':dp,'targetAuthoredNormal':n,'donorAuthoredNormal':dn,'sourceDistanceMm':distance,'normalAngleDegrees':np.degrees(np.arccos(np.clip(dot,-1,1))),'uvChebyshevDistance':np.maximum(abs(sy-y),abs(sx-x)),'finitePositiveVisibility':scope['visibleEightDirections'][selected]&(scope['geometricIncidenceEightDirections'][selected]>=.15),'frozenScopeIndex':np.flatnonzero(selected)}

def apply_frozen_copy(parent_rgb, pairs):
    parent_rgb=np.asarray(parent_rgb)
    require(parent_rgb.dtype==np.uint8 and parent_rgb.ndim==3 and parent_rgb.shape[2]==3, 'Original 8-bit RGB parent required')
    result=parent_rgb.copy()
    y,x,sy,sx=(pairs[k] for k in ('targetY','targetX','donorY','donorX'))
    # Every seed is read from the immutable parent, never from a growing result.
    result[y,x]=parent_rgb[sy,sx]
    unchanged=np.ones(parent_rgb.shape[:2],bool);unchanged[y,x]=False
    require(np.array_equal(result[unchanged],parent_rgb[unchanged]), 'Pixels outside frozen scope changed')
    return result
