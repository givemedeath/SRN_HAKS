"""Bounded original-source BODY60 and connected B3/B5 with F20 elbow equation replays.
Historical producer scripts stay inert; no geometry, material or runtime writer.
Ported from independently audited source equations. Encoded and native authorities
are replayed separately; floating construction fields never replace authored data.
"""
from pathlib import Path
import json,hashlib,numpy as np
from diagnostic_descendant_representation import read_glb,accessor,embedded_maps,RepresentationError
MathError=RepresentationError
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
pin=lambda p:{'path':str(p),'sha256':sha(p)}
def require(x, s):
    if not x:
        raise MathError(s)

def unit(x):
    n = np.linalg.norm(x, axis=-1, keepdims=True)
    require(np.isfinite(x).all() and np.all(n > 0), 'Finite nonzero vector required')
    return x / n
M = np.array([[1.0, 1.0, 1.0], [3.0, 4.0, 5.0], [6.0, 12.0, 20.0]])

def coefficients(y0, d0, dd0, y1, d1, dd1, length, *, protocol=True, inverse=False):
    p0 = y0
    p1 = d0 * length
    p2 = 0.5 * dd0 * length ** 2 if inverse else 0.5 * dd0 * length * length
    delta = y1 - p0 - p1 - p2
    first = d1 * length - p1 - 2 * p2
    second = dd1 * length ** 2 - 2 * p2 if inverse else dd1 * length * length - 2 * p2
    if protocol:
        b = np.stack([delta, first, second], axis=-2)
        c = np.einsum('ij,...jk->...ik', np.linalg.inv(M), b) if inverse else np.linalg.solve(M, b)
        if inverse:
            return (p0, p1, p2, c[..., 0, :], c[..., 1, :], c[..., 2, :])
        return (p0, p1, p2, *c)
    return (p0, p1, p2, 10 * delta - 4 * first + 0.5 * second, -15 * delta + 7 * first - second, 6 * delta - 3 * first + 0.5 * second)

def evaluate(t, c, length):
    p0, p1, p2, c3, c4, c5 = c
    t = np.asarray(t)[..., None]
    v = p0 + p1 * t + p2 * t ** 2 + c3 * t ** 3 + c4 * t ** 4 + c5 * t ** 5
    dv = (p1 + 2 * p2 * t + 3 * c3 * t ** 2 + 4 * c4 * t ** 3 + 5 * c5 * t ** 4) / length[..., None] if np.ndim(length) else (p1 + 2 * p2 * t + 3 * c3 * t ** 2 + 4 * c4 * t ** 3 + 5 * c5 * t ** 4) / length
    dd = (2 * p2 + 6 * c3 * t + 12 * c4 * t ** 2 + 20 * c5 * t ** 3) / length[..., None] ** 2 if np.ndim(length) else (2 * p2 + 6 * c3 * t + 12 * c4 * t ** 2 + 20 * c5 * t ** 3) / length ** 2
    return (v, dv, dd)

def source_spline(a, table, *, arithmetic_protocol=True):
    table = np.asarray(table, float)
    x = table[:, 0]
    y = table[:, 1:5]
    require(np.all(np.diff(x) > 0), 'Profile axis is not ordered')
    dy = np.gradient(y, x, axis=0, edge_order=2)
    ddy = np.gradient(dy, x, axis=0, edge_order=2)
    a = np.asarray(a)
    outside = (a < x[0]) | (a > x[-1])
    aa = np.clip(a, x[0], x[-1])
    i = np.clip(np.searchsorted(x, aa, side='right') - 1, 0, len(x) - 2)
    L = x[i + 1] - x[i]
    t = (aa - x[i]) / L
    c = coefficients(y[i], dy[i], ddy[i], y[i + 1], dy[i + 1], ddy[i + 1], L[..., None], protocol=arithmetic_protocol, inverse=True)
    v, d, dd = evaluate(t, c, L)
    d = np.where(outside[..., None], 0, d)
    dd = np.where(outside[..., None], 0, dd)
    return (v, d, dd)

def axial(a, row):
    a = np.asarray(a)
    b = row['part'].startswith('bicep')
    u = np.clip((0.06 - a) / 0.06, 0, 1) if b else np.clip((a + 0.15) / 0.1, 0, 1)
    w = 6 * u ** 5 - 15 * u ** 4 + 10 * u ** 3
    dw = np.where((u > 0) & (u < 1), 30 * u * u * (u - 1) ** 2, 0)
    ddw = np.where((u > 0) & (u < 1), 60 * u * (u - 1) * (2 * u - 1), 0)
    shift = row['maximumAxialRedistribution'] if b else 0.02
    return (a - shift * w, 1 + shift * dw / 0.06, -shift * ddw / 0.06 ** 2) if b else (a + shift * w, 1 + shift * dw / 0.1, shift * ddw / 0.1 ** 2)

def goal(a, row, *, arithmetic_protocol=True):
    a = np.asarray(a)
    table = np.asarray(row['denseSourceProfileTable'])
    q, fp, fpp = axial(a, row)
    ep = np.array([0.0, 0.0, 0.06, 0.06])
    zero = np.zeros(4)
    b = row['part'].startswith('bicep')
    bound = 0.06 if b else -0.08
    bv, bd, bdd = source_spline(np.array(bound), table, arithmetic_protocol=arithmetic_protocol)
    qb, fb, ffb = axial(np.array(bound), row)
    dq = bd / fb
    ddq = (bdd * fb - bd * ffb) / fb ** 3
    if b:
        qq = np.clip(q, 0, qb)
        c = coefficients(ep, zero, zero, bv, dq, ddq, float(qb), protocol=arithmetic_protocol)
        v, d, _ = evaluate(qq / float(qb), c, float(qb))
        endpoint = q < 0
        hold = a >= bound
    else:
        qq = np.clip(q, qb, 0)
        c = coefficients(bv, dq, ddq, ep, zero, zero, -float(qb), protocol=arithmetic_protocol)
        v, d, _ = evaluate((qq - qb) / -float(qb), c, -float(qb))
        endpoint = q > 0
        hold = a <= bound
    d = d * fp[..., None]
    v = np.where(endpoint[..., None], ep, v)
    d = np.where(endpoint[..., None], 0, d)
    src, ds, _ = source_spline(a, table, arithmetic_protocol=arithmetic_protocol)
    return (np.where(hold[..., None], src, v), np.where(hold[..., None], ds, d))

def field(P, N, T, row, *, arithmetic_protocol=True):
    P = np.asarray(P)
    Z = np.asarray(row['properAxisBasisRows'])
    C = np.asarray(row['hingeCenterOwnerLocal'])
    A = (P - C) @ Z.T
    a = A[..., 2]
    src, ds, _ = source_spline(a, row['denseSourceProfileTable'], arithmetic_protocol=arithmetic_protocol)
    target, dg = goal(a, row, arithmetic_protocol=arithmetic_protocol)
    require(np.all(src[..., 2:4] > 0) and np.all(target[..., 2:4] > 0), 'Nonpositive profile width')
    q, fp, _ = axial(a, row)
    s = target[..., 2:4] / src[..., 2:4]
    sp = s * (dg[..., 2:4] / target[..., 2:4] - ds[..., 2:4] / src[..., 2:4])
    offset = A[..., :2] - src[..., :2]
    Q = A.copy()
    Q[..., :2] = target[..., :2] + s * offset
    Q[..., 2] = q
    J = np.zeros((*a.shape, 3, 3))
    J[..., 0, 0] = s[..., 0]
    J[..., 1, 1] = s[..., 1]
    J[..., :2, 2] = dg[..., :2] + sp * offset - s * ds[..., :2]
    J[..., 2, 2] = fp
    det = s[..., 0] * s[..., 1] * fp
    protected = a >= 0.06 if row['part'].startswith('bicep') else a <= -0.15
    require(np.isfinite(Q).all() and np.isfinite(J).all() and np.all(det > 0), 'Nonpositive or nonfinite field J')
    NN = None
    TT = None
    if N is not None:
        n = N @ Z.T
        if arithmetic_protocol:
            nn = np.linalg.solve(np.swapaxes(J, -1, -2), n[..., None])[..., 0]
        else:
            nx = n[..., 0] / s[..., 0]
            ny = n[..., 1] / s[..., 1]
            nz = (n[..., 2] - J[..., 0, 2] * nx - J[..., 1, 2] * ny) / fp
            nn = np.stack([nx, ny, nz], axis=-1)
        nn *= np.linalg.norm(N, axis=-1)[..., None] / np.linalg.norm(nn, axis=-1)[..., None]
        NN = nn @ Z
        NN[protected] = N[protected]
    if T is not None:
        t = T[..., :3] @ Z.T
        tt = np.einsum('...ij,...j->...i', J, t) if arithmetic_protocol else np.stack([s[..., 0] * t[..., 0] + J[..., 0, 2] * t[..., 2], s[..., 1] * t[..., 1] + J[..., 1, 2] * t[..., 2], fp * t[..., 2]], axis=-1)
        tt *= np.linalg.norm(T[..., :3], axis=-1)[..., None] / np.linalg.norm(tt, axis=-1)[..., None]
        TT = T.copy()
        TT[..., :3] = tt @ Z
        TT[protected] = T[protected]
    Q = Q @ Z + C
    Q[protected] = P[protected]
    J[protected] = np.eye(3)
    det[protected] = 1
    return (Q, NN, TT, protected, J, {'sourceAxial': a, 'jacobianDeterminant': det, 'radialScaleXY': s, 'axialDerivative': fp})

def construct(boundary, sourceGeometricNormals, center, depth, sign, *, arithmetic_protocol=True):
    boundary = np.asarray(boundary, float)
    center = np.asarray(center, float)
    sg = np.asarray(sourceGeometricNormals, float)
    require(boundary.ndim == 2 and boundary.shape[1] == 3 and (len(boundary) >= 3) and (sg.shape == boundary.shape), 'Explicit source boundary and geometric N required')
    require(center.shape == (2,) and np.array_equal(center, np.zeros(2)) and ((depth, sign) in ((0.003, -1), (0.005, -1), (0.02, 1))), 'Only explicit centred B3/B5 with F20 recipe supported')
    require(np.isfinite(boundary).all() and np.all(boundary[:, 2] == 0), 'Literal finite zero-axis seam required')
    v = boundary[:, :2] - center
    rho = np.linalg.norm(v, axis=1)
    require(np.all(rho > 0), 'Zero radial boundary')
    cross = v[:, 0] * np.roll(v[:, 1], -1) - v[:, 1] * np.roll(v[:, 0], -1)
    require(np.all(cross * np.sign(np.median(cross)) > 0), 'Non-star boundary')
    angle = np.arctan2(cross, np.sum(v * np.roll(v, -1, axis=0), axis=1)).sum()
    require(abs(abs(angle) - 2 * np.pi) < 1e-12, 'Single winding boundary required')
    baseline = np.array([0, 250, 500, *range(1000, 20000, 1000), 19500, 19900], np.int64) / 1000000
    distances = baseline / 0.02 * depth
    require(len(distances) == 24 and np.all(np.diff(distances) > 0) and (distances[-1] < depth), '24 explicit normalized source stations required')
    nodes = []
    normals = []
    radialJets = []
    for d in distances:
        ratio = np.sqrt(1 - (d / depth) ** 2) if arithmetic_protocol else np.sqrt(depth * depth - d * d) / depth
        derivative = -d / (depth * depth * ratio) if arithmetic_protocol else -d / (depth * np.sqrt(depth * depth - d * d))
        require(ratio > 0 and derivative <= 0, 'Nonpositive/nonmonotone elliptical profile')
        P = np.column_stack([center + v * ratio, np.full(len(v), sign * d)])
        dd = np.column_stack([v * derivative, np.full(len(v), sign)])
        dt = np.roll(P, -1, axis=0) - np.roll(P, 1, axis=0)
        N = np.cross(dt, dd)
        N[np.sum(N[:, :2] * (P[:, :2] - center), axis=1) < 0] *= -1
        nodes.append(P)
        normals.append(unit(N))
        radialJets.append(derivative)
    nodes[0] = boundary.copy()
    nodes = np.vstack([np.concatenate(nodes), [*center, sign * depth]])
    normals = np.vstack([np.concatenate(normals), [0.0, 0.0, float(sign)]])
    n = len(v)
    faces = []
    for j in range(len(distances) - 1):
        for i in range(n):
            a = j * n + i
            b = j * n + (i + 1) % n
            c = (j + 1) * n + i
            d = (j + 1) * n + (i + 1) % n
            faces.extend([[a, b, c], [b, d, c]])
    for i in range(n):
        faces.append([(len(distances) - 1) * n + i, (len(distances) - 1) * n + (i + 1) % n, len(nodes) - 1])
    faces = np.array(faces, int)
    g = np.cross(nodes[faces[:, 1]] - nodes[faces[:, 0]], nodes[faces[:, 2]] - nodes[faces[:, 0]])
    flip = np.einsum('ij,ij->i', g, normals[faces].sum(1)) < 0
    faces[flip] = faces[flip][:, [0, 2, 1]]
    P = nodes[faces]
    N = normals[faces]
    g = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0])
    require(np.all(np.linalg.norm(g, axis=1) > 0), 'Degenerate cap triangle')
    boundaryUV = 0.5 + v / (2 * rho.max())
    uv = np.vstack([np.concatenate([0.5 + (boundaryUV - 0.5) * np.sqrt(1 - (d / 0.02) ** 2) for d in baseline]), [0.5, 0.5]])
    UV = uv[faces]
    e = P[:, 1] - P[:, 0]
    f = P[:, 2] - P[:, 0]
    u = UV[:, 1] - UV[:, 0]
    w = UV[:, 2] - UV[:, 0]
    det = u[:, 0] * w[:, 1] - u[:, 1] * w[:, 0]
    require(np.all(abs(det) > 1e-20), 'Degenerate UV chart')
    td = (e * w[:, 1, None] - f * u[:, 1, None]) / det[:, None]
    bd = (f * u[:, 0, None] - e * w[:, 0, None]) / det[:, None]
    T = np.broadcast_to(td[:, None, :], N.shape).copy()
    T = unit(T - N * np.sum(T * N, axis=-1)[..., None])
    W = np.sign(np.sum(np.cross(N, T) * bd[:, None, :], axis=-1))
    require(np.all(W != 0), 'Undefined tangent sign')
    den = np.sum(sg[:, :2] * v, axis=1)
    require(np.all(abs(den) > 1e-09), 'Unmeasurable source geometric slope')
    sourcek = -sign * sg[:, 2] / den
    attrs = {'positions': P, 'normals': N, 'uvGltf': UV, 'uvNative': np.stack([UV[..., 0], 1 - UV[..., 1]], axis=-1), 'tangents': np.concatenate([T, W[..., None]], axis=-1)}
    proof = {'nodes': nodes, 'faces': faces, 'distancesMetres': distances, 'generatedUVBaselineStationsMetres': baseline, 'sourceGeometricLogRadialSlopePerMetre': sourcek, 'sourceGeometricSecondJetCoefficient': np.zeros(n), 'sourceJetApplied': False, 'capRootFirstRadialDerivative': 0.0, 'capRootSecondRadialDerivative': -1 / (depth * depth), 'geometricC1WithTriangulatedSourceClaim': False, 'sharedSphereApplied': False, 'depthMeters': depth, 'radialFirstDerivativePerMetre': np.array(radialJets), 'normalPolicy': 'Central angular chord with analytic radial-distance derivative; authored blend is a separate generated-only operator.'}
    return (attrs, proof)

def eq(a, b):
    return a.shape == b.shape and a.dtype == b.dtype and (a.tobytes() == b.tobytes())

def raw(path):
    d, b = read_glb(path)
    out = {k: [] for k in ['positions', 'normals', 'uvGltf', 'tangents']}
    m = []

    def n(v):
        return np.stack((v[..., 0], -v[..., 2], v[..., 1]), axis=-1)
    for p in d['meshes'][0]['primitives']:
        ii = accessor(d, b, p['indices']).reshape(-1, 3).astype(int)
        a = p['attributes']
        out['positions'].append(n(accessor(d, b, a['POSITION'])[ii]))
        out['normals'].append(n(accessor(d, b, a['NORMAL'])[ii]))
        out['uvGltf'].append(accessor(d, b, a['TEXCOORD_0'])[ii])
        t = accessor(d, b, a['TANGENT'])[ii].copy()
        t[..., :3] = n(t[..., :3])
        out['tangents'].append(t)
        m.extend([p.get('material', 0)] * len(ii))
    return (d, b, {k: np.concatenate(v) for k, v in out.items()}, np.asarray(m))

def independent_field(P, N, T, row):
    return field(P, N, T, row)[:5]

def edges(P):
    ids = np.unique(P.reshape(-1, 3), axis=0, return_inverse=True)[1].reshape(-1, 3)
    e = np.sort(np.concatenate([ids[:, [0, 1]], ids[:, [1, 2]], ids[:, [2, 0]]]), axis=1)
    q, n = np.unique(e, axis=0, return_counts=True)
    return (ids, {tuple(x): int(y) for x, y in zip(q, n)})

def construction_splits(P, Q):
    n = len(P)
    tri = np.unique(P.reshape(-1, 3), axis=0, return_inverse=True)[1].reshape(-1, 3)
    qt = np.unique(Q.reshape(-1, 3), axis=0, return_inverse=True)[1].reshape(-1, 3)
    pairs = np.asarray([[0, 1], [1, 2], [2, 0]])
    e = np.concatenate([tri[:, x] for x in pairs])
    _, first, count = np.unique(np.sort(e, axis=1), axis=0, return_index=True, return_counts=True)
    qe = np.concatenate([qt[:, x] for x in pairs])
    _, inverse, qcount = np.unique(np.sort(qe, axis=1), axis=0, return_inverse=True, return_counts=True)
    occ = {}
    for i, key in enumerate(inverse):
        occ.setdefault(int(key), []).append(i)
    gaps = []
    for edge in np.flatnonzero(count == 1):
        idx = int(first[edge])
        key = int(inverse[idx])
        require(qcount[key] >= 2, 'Elbow literal replay invariant at audited source line 35')
        f = idx % n
        cc = pairs[idx // n]
        own = P[f, cc]
        own = own if qe[idx, 0] <= qe[idx, 1] else own[::-1]
        options = []
        for other in occ[key]:
            if other == idx:
                continue
            p = P[other % n, pairs[other // n]]
            p = p if qe[other, 0] <= qe[other, 1] else p[::-1]
            options.append(float(np.linalg.norm(p - own, axis=1).max()))
        gaps.append(min(options))
    return {'constructionBoundaryEdges': len(gaps), 'allCorrespondToExactSerializedClosedEdge': True, 'maximumMinimumEndpointSplitMeters': max(gaps, default=0.0)}

def cap_nodes(boundary, bn, center, extent, sign, protocol):
    attrs, proof = construct(boundary, bn, center, extent, sign, arithmetic_protocol=protocol)
    nodes = np.asarray(proof['nodes'])
    faces = np.asarray(proof['faces'])
    normals = np.zeros_like(nodes)
    ids, first = np.unique(faces.reshape(-1), return_index=True)
    require(np.array_equal(ids, np.arange(len(nodes))), 'Elbow literal replay invariant at audited source line 21')
    normals[ids] = attrs['normals'].reshape(-1, 3)[first]
    require(np.array_equal(normals[faces], attrs['normals']), 'Elbow literal replay invariant at audited source line 22')
    return (nodes, normals, np.asarray(proof['distancesMetres']), np.asarray(proof['sourceGeometricLogRadialSlopePerMetre']), np.asarray(proof['sourceGeometricSecondJetCoefficient']), None)

def validate_body(part, row):
    for v in row.values():
        require(sha(v['path']) == v['sha256'], 'Elbow literal replay invariant at audited source line 22')
    g = json.loads(Path(row['geometry']['path']).read_text())
    pr = json.loads(Path(row['proof']['path']).read_text())
    case = pr['measuredCase']
    a = dict(np.load(row['nativeCorners']['path']))
    old = dict(np.load(pr['parentNativeArchive']['path']))
    held = dict(np.load(row['protectedFields']['path']))
    d, b, source, mi = raw(pr['parentCandidate']['path'])
    dd, bb, actual, mj = raw(row['candidate']['path'])
    require(np.array_equal(mi, mj), 'Elbow literal replay invariant at audited source line 23')
    require(d['meshes'] == dd['meshes'] and d['nodes'] == dd['nodes'], 'Elbow literal replay invariant at audited source line 23')
    require(embedded_maps(d, b) == embedded_maps(dd, bb) and d['materials'] == dd['materials'] and (d['textures'] == dd['textures']) and (d['images'] == dd['images']), 'Elbow literal replay invariant at audited source line 23')
    for key in ['originalNativePositions', 'originalNativeNormals', 'originalNativeTangents']:
        require(eq(held[key], old[{'originalNativePositions': 'positions', 'originalNativeNormals': 'normals', 'originalNativeTangents': 'tangents'}[key]]), 'Elbow literal replay invariant at audited source line 24')
    mask = held['protectedCornerMask']
    P = old['positions'].reshape(-1, 3)
    N = old['normals'].reshape(-1, 3)
    T = old['tangents'].reshape(-1, 4)
    Q, NN, TT, protect, J = independent_field(P, N, T, case)
    require(np.array_equal(protect.reshape(mask.shape), mask), 'Elbow literal replay invariant at audited source line 25')
    det = np.linalg.det(J)
    require(det.min() > 0, 'Elbow literal replay invariant at audited source line 25')
    require(np.max(abs(det.reshape(mask.shape) - held['deformationJacobianDeterminants'])) < 3e-14, 'Elbow literal replay invariant at audited source line 25')
    errors = {}
    for key, value in [('positions', Q), ('normals', NN), ('tangents', TT)]:
        residual = float(np.max(abs(value.reshape(a[key].shape) - a[key])))
        require(residual < 2e-14, (part, key, residual))
        errors[key] = residual
        require(eq(a[key][mask], old[key][mask]), 'Elbow literal replay invariant at audited source line 28')
    for key in ['uvGltf', 'uvNative']:
        require(eq(a[key], old[key]), 'Elbow literal replay invariant at audited source line 29')
    require(np.array_equal(a['tangents'][:, :, 3], old['tangents'][:, :, 3]), 'Elbow literal replay invariant at audited source line 30')
    require(np.max(abs(np.linalg.norm(a['normals'], axis=2) - np.linalg.norm(old['normals'], axis=2))) < 1e-14, 'Elbow literal replay invariant at audited source line 30')
    require(np.max(abs(np.linalg.norm(a['tangents'][:, :, :3], axis=2) - np.linalg.norm(old['tangents'][:, :, :3], axis=2))) < 1e-14, 'Elbow literal replay invariant at audited source line 30')
    Qe, Ne, Te, pe, Je = independent_field(source['positions'].reshape(-1, 3).astype(float), source['normals'].reshape(-1, 3).astype(float), source['tangents'].reshape(-1, 4).astype(float), case)
    encodedErrors = {}
    for key, value in [('positions', Qe), ('normals', Ne), ('tangents', Te)]:
        expected = value.reshape(actual[key].shape).astype('f4')
        encodedErrors[key] = float(abs(expected - actual[key]).max())
        require(np.array_equal(expected, actual[key]), (part, 'literalF32EquationReplay', key, float(abs(expected - actual[key]).max())))
        require(eq(actual[key].reshape((-1, actual[key].shape[-1]))[pe], source[key].reshape((-1, source[key].shape[-1]))[pe]), ('protectedencoded', part, key))
    require(eq(actual['uvGltf'], source['uvGltf']), 'Elbow literal replay invariant at audited source line 34')
    indices = np.linspace(0, len(P) - 1, 384, dtype=int)
    points = P[indices]
    step = 1e-07
    fJ = np.empty((len(points), 3, 3))
    B = np.asarray(case['properAxisBasisRows'])
    for k in range(3):
        delta = np.eye(3)[k] * step
        qp = independent_field(points + delta, N[indices], T[indices], case)[0]
        qm = independent_field(points - delta, N[indices], T[indices], case)[0]
        fJ[:, :, k] = (qp - qm) / (2 * step)
    worldJ = np.einsum('ab,nbc,cd->nad', B.T, J[indices], B)
    finiteResidual = float(abs(fJ - worldJ).max())
    require(finiteResidual < 3e-07, (part, finiteResidual))
    allow = np.zeros(len(b), bool)
    for primitive in d['meshes'][0]['primitives']:
        attrs = primitive['attributes']
        vals = np.asarray(accessor(d, b, attrs['POSITION'])).astype(float)
        Pn = np.stack((vals[:, 0], -vals[:, 2], vals[:, 1]), axis=-1)
        Bc = np.asarray(case['properAxisBasisRows'])
        Cc = np.asarray(case['hingeCenterOwnerLocal'])
        axis = (Pn - Cc) @ Bc.T
        protected = axis[:, 2] >= 0.06 if part.startswith('bicep') else axis[:, 2] <= -0.15
        for name in ['POSITION', 'NORMAL', 'TANGENT']:
            ac = d['accessors'][attrs[name]]
            cols = 4 if name == 'TANGENT' else 3
            bv = d['bufferViews'][ac['bufferView']]
            offset = bv.get('byteOffset', 0) + ac.get('byteOffset', 0)
            stride = bv.get('byteStride', cols * 4)
            for vertex in np.flatnonzero(~protected):
                allow[offset + vertex * stride:offset + vertex * stride + cols * 4] = True
    require(len(bb) == len(b) and np.array_equal(np.frombuffer(bb, dtype='u1')[~allow], np.frombuffer(b, dtype='u1')[~allow]), 'Elbow literal replay invariant at audited source line 47')
    parentGeom = json.loads(Path(pr['parentGeometry']['path']).read_text())
    for key in ['targetContract', 'targetContractSha256', 'rigRevision', 'attachmentWorld', 'joint', 'model', 'statureApplications']:
        require(g[key] == parentGeom[key], 'Elbow literal replay invariant at audited source line 49')
    return {'candidate': row['candidate'], 'geometry': row['geometry'], 'nativeCorners': row['nativeCorners'], 'independentNativePNAndTResiduals': errors, 'encodedFloat32PNAndTResiduals': encodedErrors, 'minimumPositiveJacobian': float(det.min()), 'maximumPositiveJacobian': float(det.max()), 'finiteDifferenceWorldJacobian384CornerMaximumResidual': finiteResidual, 'allProtectedMainBicepAndWristPNUTBitExact': True, 'UVMapsMaterialsIndicesAndNonModifiedBytesExact': True, 'sourceAuthoredNormalTangentLengthsAndSignsPreserved': True, 'rigAndFramesExact': True, 'pass': True}

def validate_caps(part, item, cfg, skin):
    for v in item.values():
        require(sha(v['path']) == v['sha256'], v['path'])
    g = json.loads(Path(item['geometry']['path']).read_text())
    proof = json.loads(Path(item['proof']['path']).read_text())
    lineagePath = Path(item['encodedNativeLineage']['path'])
    a = dict(np.load(lineagePath))
    z = dict(np.load(item['nativeCorners']['path']))
    sg = json.loads(Path(g['sourceReceipt']).read_text())
    old = dict(np.load(sg['nativeCornerArchive']['path']))
    d, b, source, sourceMaterial = raw(g['source'])
    dd, bb, actual, actualMaterial = raw(item['candidate']['path'])
    ret = a['retainedOutputFaceIds']
    prior = a['retainedEncodedSourceFaceIds']
    caps = z['newGeneratedCapFaceIds']
    n = int(caps.min())
    require(np.array_equal(caps, np.arange(n, len(z['positions']))), 'Elbow literal replay invariant at audited source line 44')
    require(len(z['inheritedGeneratedCapFaceIds']) == 0 and (z['sourceFaceIds'][caps] == -1).all(), 'Elbow literal replay invariant at audited source line 44')
    require(np.all(a['directParentFaceIds'][caps] == -1), 'Elbow literal replay invariant at audited source line 44')
    for k in actual:
        require(actual[k][ret].tobytes() == source[k][prior].tobytes(), (part, 'actual encoded whole bits', k))
        require(z[k][ret].tobytes() == old[k][prior].tobytes(), (part, 'native whole bits', k))
        require(np.array_equal(actual[k], a['encoded_' + k].astype(np.float32)), (part, 'actual encoded construction parity', k))
    require(z['uvNative'][ret].tobytes() == old['uvNative'][prior].tobytes(), 'Elbow literal replay invariant at audited source line 49')
    require(bb[:len(b)] == b, 'Elbow literal replay invariant at audited source line 49')
    weights = a['sourceCutBarycentricWeights']
    parents = a['directParentFaceIds'][:len(weights)]
    whole = np.all(weights == np.eye(3), axis=(1, 2))
    require(np.array_equal(np.flatnonzero(whole), ret), 'Elbow literal replay invariant at audited source line 50')
    require(np.array_equal(parents[whole], prior), 'Elbow literal replay invariant at audited source line 50')
    split = ~whole
    require(len(weights) == n, 'Elbow literal replay invariant at audited source line 50')
    baryResiduals = {}
    for k in ['positions', 'normals', 'uvGltf', 'uvNative', 'tangents']:
        expected = np.einsum('fij,fjk->fik', weights, old[k][parents])
        expected[whole] = old[k][parents[whole]]
        if k == 'positions':
            expected += a['newSplitNativePositionWeldDeltas']
        require(np.array_equal(z[k][:n], expected), (part, 'native bary ancestry', k))
        baryResiduals[k] = 0.0
    require(np.all(a['newSplitNativePositionWeldDeltas'][a['newSplitCanonicalSeamIDs'] < 0] == 0), 'Elbow literal replay invariant at audited source line 56')
    require(np.max(np.abs(a['newSplitNativePositionWeldDeltas'])) <= cfg['newSplitPositionWeldPolicy']['maximumNativeBarycentricDeltaMeters'], 'Elbow literal replay invariant at audited source line 56')
    B = np.asarray(g['cuttingAxisBasisRows'])
    C = np.asarray(g['hingeCenterOwnerLocal'])
    case = cfg['parts'][part]
    sign = -1 if case['keepAbove'] else 1
    require(proof['cut'] == 0 and np.linalg.det(B) > 0 and (np.max(np.abs(B @ B.T - np.eye(3))) < 1e-14), 'Elbow literal replay invariant at audited source line 57')
    domain = proof['capDomains'][0]
    boundaryRows = np.asarray(domain['sourceRetainedBoundaryRows'])
    boundary = a['encoded_positions'][boundaryRows[:, 0], boundaryRows[:, 1]]
    sourceAxis = (source['positions'] - C) @ B.T
    literalAxisBoundary = []
    for f, j in boundaryRows:
        w = weights[f, j]
        sourceFace = parents[f]
        nonzero = np.flatnonzero(np.abs(w) > 1e-15)
        if len(nonzero) == 2:
            endpoints = sorted((tuple(np.round(q, 12)) for q in sourceAxis[sourceFace, nonzero]))
            p0, p1 = (np.asarray(endpoints[0]), np.asarray(endpoints[1]))
            fraction = (proof['cut'] - p0[2]) / (p1[2] - p0[2])
            q = p0 + fraction * (p1 - p0)
            q[2] = proof['cut']
        else:
            q = np.einsum('i,ij->j', w, sourceAxis[sourceFace])
        literalAxisBoundary.append(q)
    axisBoundary = np.asarray(literalAxisBoundary)
    row = case['anatomicalFieldRow']
    extent = row['simpleDomeDepthMetres']
    require((extent in (0.003,0.005)if part.startswith('bicep')else extent==0.02), 'Elbow literal replay invariant at audited source line 65')
    require(case['outerDepth'] == extent and row['simpleDomeCenterXY'] == [0, 0], 'Elbow literal replay invariant at audited source line 65')
    nb = len(boundary)
    stored = proof['caps'][0]
    require(stored['sourceJetApplied'] is False and stored['boundaryConformingSharedHingeSphereCore'] is False, 'Elbow literal replay invariant at audited source line 66')
    require(stored['sourceSeamFirstAndSecondRadialJetMatched'] is False, 'Elbow literal replay invariant at audited source line 66')
    require(stored['stockAngularOrCenterProfileApplied'] is False, 'Elbow literal replay invariant at audited source line 66')
    require(stored['simpleEllipticDomeDepthMetres'] == extent, 'Elbow literal replay invariant at audited source line 66')
    require(np.max(abs(axisBoundary - np.array(stored['boundaryAxisPositions']))) < 2e-14, 'Elbow literal replay invariant at audited source line 66')
    retAxis = np.einsum('fij,fjk->fik', weights, sourceAxis[parents])
    retAxis[whole] = sourceAxis[parents[whole]]
    for ff, jj in np.argwhere(np.count_nonzero(abs(weights) > 1e-15, axis=2) == 2):
        cc = np.flatnonzero(abs(weights[ff, jj]) > 1e-15)
        end = sorted((tuple(np.round(q, 12)) for q in sourceAxis[parents[ff], cc]))
        u, v = np.array(end)
        q = u + (proof['cut'] - u[2]) / (v[2] - u[2]) * (v - u)
        q[2] = proof['cut']
        retAxis[ff, jj] = q
    srcTri = retAxis[boundaryRows[:, 0]]
    bn = unit(np.cross(srcTri[:, 1] - srcTri[:, 0], srcTri[:, 2] - srcTri[:, 0]))
    require(np.max(abs(bn - np.array(stored['sourceGeometricSeamNormals']))) < 2e-12, 'Elbow literal replay invariant at audited source line 70')
    center = np.array(row['simpleDomeCenterXY'])
    require(np.array_equal(center, np.array(stored['fixedLiteralSeamCenterXY'])), 'Elbow literal replay invariant at audited source line 71')
    nodes, geometricNodesN, stations, k, second, jetrows = cap_nodes(axisBoundary, bn, center, extent, sign, True)
    independentNodes, independentNormals, otherStations, _, _, _ = cap_nodes(axisBoundary, bn, center, extent, sign, False)
    independentPositionResidual = float(abs(independentNodes - nodes).max())
    independentNormalResidual = float(abs(independentNormals - geometricNodesN).max())
    require(independentPositionResidual < 2e-14 and independentNormalResidual < 2e-12, (part, 'alternative expanded h1/h2 equation', independentPositionResidual, independentNormalResidual))
    require(np.array_equal(stations, np.array(stored['distancesMetres'])), 'Elbow literal replay invariant at audited source line 74')
    require(np.array_equal(k, np.array(stored['sourceGeometricLogRadialSlopePerMetre'])), 'Elbow literal replay invariant at audited source line 74')
    require(np.array_equal(second, np.array(stored['sourceGeometricSecondJetCoefficient'])), 'Elbow literal replay invariant at audited source line 74')
    pole = len(nodes) - 1
    faces = []
    for ring in range(len(stations) - 1):
        for j in range(nb):
            k1 = (j + 1) % nb
            x = ring * nb + j
            y = ring * nb + k1
            u = (ring + 1) * nb + j
            v = (ring + 1) * nb + k1
            faces.extend([[x, y, u], [y, v, u]])
    for j in range(nb):
        faces.append([(len(stations) - 1) * nb + j, (len(stations) - 1) * nb + (j + 1) % nb, pole])
    faces = np.array(faces)
    cross = np.cross(nodes[faces[:, 1]] - nodes[faces[:, 0]], nodes[faces[:, 2]] - nodes[faces[:, 0]])
    flip = np.einsum('ij,ij->i', cross, geometricNodesN[faces].sum(1)) < 0
    faces[flip] = faces[flip][:, [0, 2, 1]]
    ownerNodes = nodes @ B + C
    ownerNodes[:nb] = boundary
    capPResidual = float(abs(ownerNodes[faces] - a['encoded_positions'][caps]).max())
    require(capPResidual < 2e-14, (part, 'capP', capPResidual))
    nativeNodes = ownerNodes.copy()
    nativeNodes[:nb] = z['positions'][boundaryRows[:, 0], boundaryRows[:, 1]]
    require(abs(nativeNodes[faces] - z['positions'][caps]).max() < 2e-14, 'Elbow literal replay invariant at audited source line 81')
    cross = np.cross(nodes[faces[:, 1]] - nodes[faces[:, 0]], nodes[faces[:, 2]] - nodes[faces[:, 0]])
    require(np.linalg.norm(cross, axis=1).min() > 1e-14, 'Elbow literal replay invariant at audited source line 82')
    geometricNodesN = geometricNodesN @ B
    newN = geometricNodesN.copy()
    seamN = a['encoded_normals'][boundaryRows[:, 0], boundaryRows[:, 1]]
    newN[:nb] = seamN
    newN[nb:2 * nb] = unit(0.5 * seamN + 0.5 * geometricNodesN[nb:2 * nb])
    newN = unit(newN)
    nResidual = float(abs(newN[faces] - a['encoded_normals'][caps]).max())
    require(nResidual < 2e-12, (part, 'capN', nResidual))
    nativeN = newN.copy()
    nativeN[:nb] = z['normals'][boundaryRows[:, 0], boundaryRows[:, 1]]
    nativeN = unit(nativeN)
    require(abs(nativeN[faces] - z['normals'][caps]).max() < 2e-12, 'Elbow literal replay invariant at audited source line 84')
    radius = np.linalg.norm(axisBoundary[:, :2] - center, axis=1).max()
    boundaryUV = 0.5 + (axisBoundary[:, :2] - center) / (2 * radius)
    unscaled = np.vstack([np.concatenate([0.5 + (boundaryUV - 0.5) * np.sqrt(1 - (d / 0.02) ** 2) for d in np.array([0, 250, 500, *range(1000, 20000, 1000), 19500, 19900], np.int64) / 1000000]), [0.5, 0.5]])
    rect = np.array(case['skinUVPatch'])
    scale = (rect[2:] - rect[:2]) * 0.5
    offset = (rect[:2] + rect[2:]) * 0.5 - scale * 0.5
    UV = unscaled[faces] * scale + offset
    require(abs(UV - a['encoded_uvGltf'][caps]).max() < 2e-14, 'Elbow literal replay invariant at audited source line 86')

    def tangentDerivative(normal):
        tri = nodes[faces]
        uv = unscaled[faces]
        dp1 = tri[:, 1] - tri[:, 0]
        dp2 = tri[:, 2] - tri[:, 0]
        du1 = uv[:, 1] - uv[:, 0]
        du2 = uv[:, 2] - uv[:, 0]
        den = du1[:, 0] * du2[:, 1] - du1[:, 1] * du2[:, 0]
        require(np.all(abs(den) > 1e-20), 'Elbow literal replay invariant at audited source line 88')
        t = (dp1 * du2[:, 1, None] - dp2 * du1[:, 1, None]) / den[:, None]
        bitangent = (-dp1 * du2[:, 0, None] + dp2 * du1[:, 0, None]) / den[:, None]
        geomN = geometricNodesN[faces]
        tt = np.broadcast_to(t[:, None] @ B, geomN.shape).copy()
        tt = unit(tt - geomN * np.sum(tt * geomN, axis=-1)[..., None])
        bitan = bitangent @ B
        ts = np.where(np.sum(np.cross(geomN, tt) * bitan[:, None], axis=-1) >= 0, 1.0, -1.0)
        tt = unit(tt - normal * np.sum(tt * normal, axis=-1)[..., None])
        return np.concatenate([tt, ts[..., None]], axis=-1)
    expectedT = tangentDerivative(newN[faces])
    tResidual = float(abs(expectedT - a['encoded_tangents'][caps]).max())
    require(tResidual < 2e-12, (part, 'capT', tResidual))
    nativeT = a['encoded_tangents'][caps].copy()
    nativeT[..., :3] = unit(nativeT[..., :3] - nativeN[faces] * np.sum(nativeT[..., :3] * nativeN[faces], axis=-1)[..., None])
    require(abs(nativeT - z['tangents'][caps]).max() < 2e-12, 'Elbow literal replay invariant at audited source line 89')
    edgeReports = {}
    for name, P in [('native', z['positions']), ('encodedConstruction', a['encoded_positions']), ('actualF32GLB', actual['positions'])]:
        ids, counts = edges(P)
        ce = np.unique(np.sort(np.concatenate([ids[caps][:, [0, 1]], ids[caps][:, [1, 2]], ids[caps][:, [2, 0]]]), axis=1), axis=0)
        require(all((counts[tuple(e)] == 2 for e in ce)), (part, name, 'capedges'))
        N = z['normals'][caps] if name == 'native' else a['encoded_normals'][caps] if name == 'encodedConstruction' else actual['normals'][caps]
        T = z['tangents'][caps] if name == 'native' else a['encoded_tangents'][caps] if name == 'encodedConstruction' else actual['tangents'][caps]
        unitErr = float(np.max(np.abs(np.linalg.norm(N, axis=-1) - 1)))
        nt = float(np.max(np.abs(np.sum(N * T[..., :3], axis=-1))))
        require(np.isin(T[..., 3], [-1, 1]).all(), 'Elbow literal replay invariant at audited source line 92')
        if name != 'actualF32GLB':
            require(unitErr < 1e-12 and nt < 1e-12, 'Elbow literal replay invariant at audited source line 93')
        wholeBoundary = sum((n == 1 for n in counts.values()))
        wholeNonmanifold = sum((n > 2 for n in counts.values()))
        require(name == 'encodedConstruction' or wholeBoundary == wholeNonmanifold == 0, (part, name, 'whole ends'))
        edgeReports[name] = {'wholeBoundaryEdges': wholeBoundary, 'wholeNonmanifoldEdges': wholeNonmanifold, 'newCapEdgeCount': len(ce), 'allNewCapEdgeIncidenceTwo': True, 'unitNormalResidual': unitErr, 'NdotTResidual': nt}
    require(embedded_maps(d, b) == embedded_maps(dd, bb), 'Elbow literal replay invariant at audited source line 95')
    require(dd['materials'][:len(d['materials'])] == d['materials'], 'Elbow literal replay invariant at audited source line 95')
    capmid = dd['meshes'][0]['primitives'][-1]['material']
    for container, key in [('pbrMetallicRoughness', 'baseColorTexture'), ('pbrMetallicRoughness', 'metallicRoughnessTexture'), (None, 'normalTexture'), (None, 'occlusionTexture')]:
        x = d['materials'][0][container][key] if container else d['materials'][0][key]
        y = dd['materials'][capmid][container][key] if container else dd['materials'][capmid][key]
        require({k: v for k, v in x.items() if k != 'index'} == {k: v for k, v in y.items() if k != 'index'}, 'Elbow literal replay invariant at audited source line 97')
        require(dd['textures'][x['index']] == dd['textures'][y['index']], 'Elbow literal replay invariant at audited source line 97')
    support = skin['parts'][part]
    require(sha(support['supportArchive']['path']) == support['supportArchive']['sha256'], 'Elbow literal replay invariant at audited source line 98')
    occupied = np.load(support['supportArchive']['path'])['occupiedSkinMask']
    uv = actual['uvGltf'][caps].reshape(-1, 2).astype(float)
    uv[:, 1] = 1 - uv[:, 1]
    uv *= 2048
    lo = uv.min(0)
    hi = uv.max(0)
    r = np.asarray(support['pixelRectTopOrigin'])
    guard = float(np.r_[lo - r[:2], r[2:] - hi].min())
    require(guard >= 4, 'Elbow literal replay invariant at audited source line 98')
    taplo = np.floor(lo - 0.5).astype(int)
    taphi = np.floor(hi - 0.5).astype(int) + 1
    require(occupied[taplo[1]:taphi[1] + 1, taplo[0]:taphi[0] + 1].all(), 'Elbow literal replay invariant at audited source line 98')
    require(np.all(actual['uvGltf'][caps] >= 0) and np.all(actual['uvGltf'][caps] <= 1), 'Elbow literal replay invariant at audited source line 98')
    for k in ['targetContract', 'targetContractSha256', 'rigRevision', 'attachmentWorld', 'joint', 'model', 'statureApplications']:
        require(g[k] == sg[k], 'Elbow literal replay invariant at audited source line 99')
    constructionWitness = construction_splits(a['encoded_positions'], actual['positions'])
    return {'alternativeExpandedJetPositionResidualMeters': independentPositionResidual, 'alternativeExpandedJetNormalResidual': independentNormalResidual, 'retainedCurrentFieldParentAndBarycentricAncestryVerified': True, 'stockAngularAndCenterTrajectoryInactive': True, 'sourceJetNotApplied': True, 'geometricC1NotClaimed': True, 'intermediateConstructionSeamWitness': constructionWitness, 'candidate': item['candidate'], 'geometry': item['geometry'], 'nativeCorners': item['nativeCorners'], 'retainedFieldParentPNUTBitExact': True, 'cutNativeBarycentricReplayResiduals': baryResiduals, 'generatedCapPositionReplayResidualMeters': capPResidual, 'generatedCapNReplayResidual': nResidual, 'generatedCapUVTReplayResidual': tResidual, 'capDualAuthorityAndF32Readback': edgeReports, 'minimumOriginalSkinUVGuardPixels': guard, 'originalMapsAndMaterialBindingsExact': True, 'nativeFrameIdentityExact': True, 'pass': True}

def validate_generated_normal_ids(ids,sourceFaceIds,newCapFaceIds,policy):
 require(policy=='authored-seam-and-next-ring-blend-only','Unsupported generated normal policy')
 ids=np.asarray(ids);sourceFaceIds=np.asarray(sourceFaceIds);newCapFaceIds=np.asarray(newCapFaceIds)
 require(ids.ndim==1 and ids.dtype.kind in 'iu' and ids.dtype.kind!='b' and len(ids)>0,'Explicit nonempty integer cap domain required')
 require(len(np.unique(ids))==len(ids)and np.all(ids>=0)and np.all(ids<len(sourceFaceIds)),'Malformed cap domain')
 require(np.all(np.isin(ids,newCapFaceIds))and np.all(sourceFaceIds[ids]==-1),'Normal domain includes retained source or unsupported caps')
 return ids

def check_non_pnt_binary(source,actual,allowed):
 require(len(source)==len(actual)and len(source)==len(allowed),'Body buffer extent differs')
 require(np.array_equal(np.frombuffer(source,dtype='u1')[~allowed],np.frombuffer(actual,dtype='u1')[~allowed]),'Non-PNT source bytes changed')
