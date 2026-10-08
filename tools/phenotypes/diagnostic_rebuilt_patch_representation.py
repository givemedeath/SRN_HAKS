"""Rebuilt skin-patch pelvis descendant, verified by invariants against sealed and pinned parent authority.

The Delaunay rebuild is never re-run and no historical Python is imported. Authority chain:
  sealed original pelvis source representation (verified baseline context)
    -> parent: pinned literal native archive whose original-derived rows are checked against the sealed original
       (identity rows byte-exact, cut rows by declared barycentric replay); generated cap rows are inherited exactly,
       not replayed;
    -> rebuild: kept rows byte-exact to the parent via the lineage map except one declared, bounded displaced set;
       declared deletions, new faces and brief exceptions; new-face orientation, area, closure, cheap intersection
       and UV-island/texel-alias checks; decoded GLB relation;
    -> final: exact f64 replay of the single adopted buttock lower-edge map on the rebuild authority and f32
       replay on its decoded GLB; topology, UVs, ids and lineage unchanged.
No runtime, material, selection or acceptance approval.
"""
from pathlib import Path
from types import MappingProxyType
import sys
import numpy as np
import diagnostic_descendant_representation as base

KIND = 'diagnostic-rebuilt-patch-descendant-representation'
OPERATION = 'pelvis-rebuilt-skin-patch-and-buttock-lower-edge-extension-descendant'
OPERATIONS = ('rebuilt-skin-patch-v1', 'buttock-lower-edge-extension-v1')
FIELDS = ('kind', 'schemaVersion', 'target', 'part', 'space', 'baselineRepresentation', 'parent', 'rebuild', 'final', 'operations', 'consumers', 'physicalInputs')
PARENT_FIELDS = ('candidate', 'geometry', 'nativeCorners', 'lineage')
REBUILD_FIELDS = ('candidate', 'nativeCorners', 'lineage', 'proof')
FINAL_FIELDS = ('candidate', 'geometry', 'nativeCorners', 'lineage', 'proof')
IDENTITY = ('targetContract', 'targetContractSha256', 'targetId', 'rigRevision', 'joint', 'model', 'attachmentWorld', 'part', 'coordinateSpace', 'statureApplications')
ARCHIVE_KEYS = {'positions', 'normals', 'uvGltf', 'uvNative', 'tangents', 'sourceFaceIds', 'sourceBarycentricWeights', 'generatedCapFaceIds', 'tangentTriangleIds'}
MOVED = ('positions', 'normals', 'tangents')
# Only the user-adopted v6 fixture is representable; anything else fails closed.
ADOPTED_POLICY = ({'parentFaces': 61490, 'faces': 61158, 'keptFaces': 57193, 'deletedParentFaces': 4297, 'newFaces': 3965,
                   'newFacesByAtlas': {'2': 1740, '3': 2225}, 'islandsByAtlas': {'2': [0, 1, 2], '3': [3, 4, 5]},
                   'generatedCapFaces': 16675, 'parentCutRows': 1098, 'displacedKeptFaces': 211, 'displacedMaxMoveMetres': 0.0026,
                   'reroutedKeptFaces': 504, 'briefFacesBefore': 10582, 'briefFacesAfter': 10356, 'briefTabTrimFaces': 166,
                   'briefBowKnotFaces': 60, 'minNewFaceAreaSquareMetres': 1e-06, 'parentCutPositionTolerance': 1e-08,
                   'glbNativeTolerance': {'positions': 2e-08, 'normals': 1e-07, 'uvGltf': 2e-08, 'tangents': 1e-07},
                   'texelAliasPaddingPixels': 1.5, 'atlasPixels': 2048},)
ADOPTED_BUTTOCK = ({'e': 0.004, 'yW': 0.05, 'zTop': -0.17, 'zW': 0.04, 'b0': 0.004, 'b1': 0.016},)
BRIEF_CUTOFF = 0.021  # strictly above every adopted b0 + b1: the brief weight is exactly one beyond it
REPLAY_TOLERANCE = {'native': (1e-12, 1e-09), 'glb': (5e-08, 1e-07)}


def require(ok, message):
    if not ok:
        raise base.RepresentationError(message)


def prepare_rebuilt_patch_representation(contract_pin, *, target_path, target, part, space='working', baseline_context=None):
    if sys.flags.optimize:
        raise base.RepresentationError('Optimized assertion removal forbidden')
    try:
        return _prepare(contract_pin, target_path=target_path, target=target, part=part, space=space, baseline_context=baseline_context)
    except base.RepresentationError:
        raise
    except (KeyError, TypeError, ValueError, IndexError, OSError, AttributeError) as error:
        raise base.RepresentationError('Malformed rebuilt-patch representation input: ' + str(error)) from error


# ---------------------------------------------------------------- schema
def validate_operations(rows):
    require(isinstance(rows, list) and len(rows) == 2, 'Exactly the two adopted pelvis operations required')
    for row, kind in zip(rows, OPERATIONS):
        require(isinstance(row, dict) and row.get('kind') == kind, 'Missing, reordered or unsupported pelvis operation')
    base.keys(rows[0], ('kind', 'policy')); base.keys(rows[1], ('kind', 'parameters'))
    require(any(rows[0]['policy'] == q for q in ADOPTED_POLICY), 'Rebuild policy is not the user-adopted fixture')
    require(any(rows[1]['parameters'] == q for q in ADOPTED_BUTTOCK), 'Buttock parameters are not a user-adopted set')
    q = rows[1]['parameters']
    require(all(type(v) is float for v in q.values()) and q['b0'] + q['b1'] < BRIEF_CUTOFF, 'Typed bounded buttock parameters required')
    return rows[0]['policy'], q


def validate_contract(c, part, space):
    base.keys(c, FIELDS)
    require(c['kind'] == KIND and type(c['schemaVersion']) is int and c['schemaVersion'] == 1, 'Unknown rebuilt-patch contract')
    require(c['part'] == part == 'pelvis' and c['space'] == space == 'working', 'Cross owner/space')
    for key, fields in (('parent', PARENT_FIELDS), ('rebuild', REBUILD_FIELDS), ('final', FINAL_FIELDS)):
        base.keys(c[key], fields)
    return validate_operations(c['operations'])


def contract_pins(c):
    return [c['target'], c['baselineRepresentation'], *c['parent'].values(), *c['rebuild'].values(), *c['final'].values(), *c['consumers']]


def expected_physical_inputs(c, baseline_context):
    """Exact consumed closure: sealed baseline inputs, original authority files and every contract pin."""
    expected = {str(Path(p).resolve()): h for p, h in baseline_context.inputs.items()}
    pr = baseline_context.proof
    for row in (pr['originalGeometryReceipt'], pr['candidate'], pr['originalNativeCornerArchive'], *contract_pins(c)):
        p, h = base.checked_pin({'path': row['path'], 'sha256': row['sha256']})
        require(expected.get(p, h) == h, 'Conflicting physical input digest: ' + p); expected[p] = h
    return [{'path': p, 'sha256': h} for p, h in sorted(expected.items())]


# ---------------------------------------------------------------- pure invariants
def smoothstep(t):
    t = np.clip(t, 0, 1); return t * t * (3 - 2 * t)


def brief_distance(points, brief, cutoff=BRIEF_CUTOFF, chunk=512):
    """Brute-force minimum distance, exact wherever it is below cutoff; never below cutoff otherwise (inf if no candidate)."""
    points = np.asarray(points, dtype=np.float64); out = np.full(len(points), np.inf)
    if not len(points) or not len(brief):
        return out
    order = np.argsort(points[:, 0], kind='stable')
    for s in range(0, len(order), chunk):
        idx = order[s:s + chunk]; q = points[idx]; lo = q.min(0) - cutoff; hi = q.max(0) + cutoff
        sel = brief[np.all((brief >= lo) & (brief <= hi), axis=1)]; best = np.full(len(idx), np.inf)
        for t in range(0, len(sel), 4000):
            best = np.minimum(best, np.sqrt(((q[:, None, :] - sel[None, t:t + 4000]) ** 2).sum(-1)).min(1))
        out[idx] = best
    return out


def buttock_map(p, q, brief):
    """dz = -e * S(-y/yW) * S((zTop-z)/zW) * S((dBrief-b0)/b1); part-local NWN frame, brief vertices never move."""
    p = np.asarray(p, dtype=np.float64); shape = p.shape; x = p.reshape(-1, 3).copy()
    w = smoothstep(-x[:, 1] / q['yW']) * smoothstep((q['zTop'] - x[:, 2]) / q['zW']); act = w > 0
    if act.any():
        d = brief_distance(x[act], brief); x[act, 2] -= q['e'] * (w[act] * smoothstep((d - q['b0']) / q['b1']))
    return x.reshape(shape)


def buttock_transform(p, n, t, q, brief, h=1e-6):
    """Normals by inverse transpose, tangents by push-forward re-orthogonalized; identity Jacobian rows keep authored bytes."""
    fun = lambda x: buttock_map(x, q, brief)
    J = np.empty(p.shape + (3,))
    for i in range(3):
        e = np.zeros(3); e[i] = h; J[..., :, i] = (fun(p + e) - fun(p - e)) / (2 * h)
    m = np.einsum('...ij,...j->...i', np.linalg.inv(J).swapaxes(-1, -2), n)
    m = m / np.linalg.norm(m, axis=-1, keepdims=True) * np.linalg.norm(n, axis=-1, keepdims=True)
    v = np.einsum('...ij,...j->...i', J, t[..., :3]); nn = m / np.linalg.norm(m, axis=-1, keepdims=True)
    v = v - (v * nn).sum(-1, keepdims=True) * nn; v = v / np.linalg.norm(v, axis=-1, keepdims=True) * np.linalg.norm(t[..., :3], axis=-1, keepdims=True)
    out = np.concatenate([v, t[..., 3:]], -1); ident = np.abs(J - np.eye(3)).max((-1, -2)) < 1e-8
    m[ident] = n[ident]; out[ident] = t[ident]
    return m, out


def face_normals(P):
    return np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0])


def edge_inventory(P):
    """Exact-position vertex ids, undirected edge keys, per-edge face counts and signed direction sums."""
    _, ids = np.unique(P.reshape(-1, 3), axis=0, return_inverse=True); f = ids.reshape(-1, 3)
    e = np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]])
    keys, inv, count = np.unique(np.sort(e, axis=1), axis=0, return_inverse=True, return_counts=True)
    direction = np.bincount(inv, weights=np.where(e[:, 0] < e[:, 1], 1, -1), minlength=len(keys))
    return f, keys, inv.reshape(3, -1).T, count, direction


def edge_positions(P, f, keys, select):
    """Exact position-pair identities of selected edges (ids are lexicographic, so pairs are canonical)."""
    v = np.empty((f.max() + 1, 3)); v[f.reshape(-1)] = P.reshape(-1, 3)
    return {v[i].tobytes() + v[j].tobytes() for i, j in keys[select]}


def closure_report(P, faces):
    """Every edge of the given faces is shared by exactly two consistently oriented faces."""
    f, keys, inv, count, direction = edge_inventory(P); touched = np.unique(inv[faces].reshape(-1))
    return {'edges': int(len(touched)), 'notTwoFaceEdges': int((count[touched] != 2).sum()),
            'inconsistentOrientationEdges': int(((count[touched] == 2) & (direction[touched] != 0)).sum()),
            'boundaryEdges': int((count == 1).sum()), 'nonManifoldEdges': int((count > 2).sum())}


def segment_triangle_hits(s0, s1, a, b, c, eps=1e-9):
    """Strict-interior segment/triangle crossings (Moller-Trumbore); touching and coplanar contacts are not counted."""
    d = s1 - s0; e1 = b - a; e2 = c - a; h = np.cross(d, e2); det = np.einsum('ij,ij->i', e1, h)
    ok = np.abs(det) > 1e-30; inv = np.where(ok, 1 / np.where(ok, det, 1), 0); s = s0 - a
    u = inv * np.einsum('ij,ij->i', s, h); qv = np.cross(s, e1); v = inv * np.einsum('ij,ij->i', d, qv); t = inv * np.einsum('ij,ij->i', e2, qv)
    return ok & (u > eps) & (v > eps) & (u + v < 1 - eps) & (t > eps) & (t < 1 - eps)


def intersecting_faces(P, query, chunk=256):
    """Cheap broad/narrow phase: query faces against every face with overlapping bounds and no shared vertex."""
    f = edge_inventory(P)[0]; lo = P.min(1); hi = P.max(1); hits = []
    query = np.asarray(query, dtype=np.int64)
    for s in range(0, len(query), chunk):
        qi = query[s:s + chunk]
        overlap = np.all((lo[None] <= hi[qi][:, None]) & (hi[None] >= lo[qi][:, None]), axis=2)
        a, b = np.nonzero(overlap); a = qi[a]; keep = a != b
        a, b = a[keep], b[keep]; shared = (f[a][:, :, None] == f[b][:, None, :]).any((1, 2)); a, b = a[~shared], b[~shared]
        if not len(a):
            continue
        crossed = np.zeros(len(a), bool)
        for x, y in ((a, b), (b, a)):
            for i, j in ((0, 1), (1, 2), (2, 0)):
                crossed |= segment_triangle_hits(P[x, i], P[x, j], P[y, 0], P[y, 1], P[y, 2])
        hits.extend(zip(a[crossed].tolist(), b[crossed].tolist()))
    return sorted({tuple(sorted(p)) for p in hits})


def texel_footprint(uv_pixels, pad):
    """Flat texel ids whose centres lie within pad pixels of any triangle (conservative bilinear support)."""
    rows = []
    for t in np.asarray(uv_pixels, dtype=np.float64):
        lo = np.floor(t.min(0) - pad).astype(int); hi = np.ceil(t.max(0) + pad).astype(int)
        xs, ys = np.meshgrid(np.arange(lo[0], hi[0] + 1), np.arange(lo[1], hi[1] + 1)); c = np.stack([xs.ravel() + .5, ys.ravel() + .5], 1)
        cross = lambda u, v, p: (v[0] - u[0]) * (p[:, 1] - u[1]) - (v[1] - u[1]) * (p[:, 0] - u[0])
        d1, d2, d3 = cross(t[0], t[1], c), cross(t[1], t[2], c), cross(t[2], t[0], c)
        inside = ((d1 >= 0) & (d2 >= 0) & (d3 >= 0)) | ((d1 <= 0) & (d2 <= 0) & (d3 <= 0))
        dist = np.full(len(c), np.inf)
        for u, v in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
            w = v - u; s = np.clip(((c - u) @ w) / max(float(w @ w), 1e-30), 0, 1); dist = np.minimum(dist, np.linalg.norm(c - (u + s[:, None] * w), axis=1))
        ok = inside | (dist <= pad); rows.append(ys.ravel()[ok].astype(np.int64) * 1000003 + xs.ravel()[ok])
    return np.unique(np.concatenate(rows)) if rows else np.zeros(0, np.int64)


def rows_exact(child, parent, keys, rows, parent_rows):
    return {k: bool(child[k][rows].tobytes() == parent[k][parent_rows].tobytes()) for k in keys}


# ---------------------------------------------------------------- decoding
def decode(path):
    doc, b = base.read_glb(path); rows = {'positions': [], 'normals': [], 'uvGltf': [], 'tangents': []}; materials = []
    nwn = lambda v: np.stack((v[..., 0], -v[..., 2], v[..., 1]), axis=-1)
    for p in doc['meshes'][0]['primitives']:
        i = base.accessor(doc, b, p['indices']).reshape(-1, 3).astype(int); at = p['attributes']
        require('TANGENT' in at, 'Authored tangents required in every pelvis primitive')
        rows['positions'].append(nwn(base.accessor(doc, b, at['POSITION'])[i].astype(float)))
        rows['normals'].append(nwn(base.accessor(doc, b, at['NORMAL'])[i].astype(float)))
        rows['uvGltf'].append(base.accessor(doc, b, at['TEXCOORD_0'])[i].astype(float))
        t = base.accessor(doc, b, at['TANGENT'])[i].astype(float); t[..., :3] = nwn(t[..., :3]); rows['tangents'].append(t)
        materials.extend([p['material']] * len(i))
    out = {k: np.concatenate(v) for k, v in rows.items()}; out['uvNative'] = np.stack((out['uvGltf'][..., 0], 1 - out['uvGltf'][..., 1]), axis=-1)
    return doc, b, out, np.asarray(materials, dtype=np.int64)


def load(pin):
    with np.load(base.checked_pin(pin)[0], allow_pickle=False) as z:
        return {k: z[k].copy() for k in z.files}


def strip_moved(doc):
    keep = lambda pr: {**pr, 'attributes': {k: v for k, v in pr['attributes'].items() if k not in ('POSITION', 'NORMAL', 'TANGENT')}}
    return {**doc, 'accessors': None, 'bufferViews': None, 'buffers': None, 'meshes': [{**m, 'primitives': [keep(pr) for pr in m['primitives']]} for m in doc['meshes']]}


# ---------------------------------------------------------------- authority checks
def verify_parent(O, P, PL, policy):
    """Parent original-derived rows against the sealed original archive; generated cap rows are inherited, not replayed."""
    n = len(P['positions']); src = PL['sourceFaceIds']; bary = PL['sourceCutBarycentricWeights']
    require(n == policy['parentFaces'] and set(P) == ARCHIVE_KEYS and np.array_equal(P['sourceFaceIds'], src), 'Parent archive schema/count differs')
    require(np.array_equal(np.flatnonzero(src < 0), PL['generatedCapFaceIds']) and np.array_equal(PL['generatedCapFaceIds'], P['generatedCapFaceIds'])
            and len(PL['generatedCapFaceIds']) == policy['generatedCapFaces'], 'Parent generated cap inventory differs')
    require(np.all(src < len(O['positions'])), 'Parent source face outside sealed original')
    ident = np.all(bary == np.eye(3), axis=(1, 2)) & (src >= 0); cut = (src >= 0) & ~ident
    require(int(cut.sum()) == policy['parentCutRows'], 'Parent cut row inventory differs')
    exact = rows_exact(P, O, ('positions', 'normals', 'uvGltf', 'uvNative', 'tangents'), ident, src[ident])
    require(all(exact.values()), 'Parent original rows differ from sealed original authority: ' + str(exact))
    w = bary[cut]; errors = {}
    require(np.all(w >= 0) and float(np.abs(w.sum(2) - 1).max(initial=0)) <= 1e-07, 'Parent cut barycentric weights invalid')
    for k in ('positions', 'normals', 'uvGltf', 'uvNative', 'tangents'):
        errors[k] = float(np.abs(P[k][cut] - np.einsum('fij,fjk->fik', w, O[k][src[cut]])).max(initial=0))
    require(errors['positions'] <= policy['parentCutPositionTolerance'] and max(v for k, v in errors.items() if k != 'positions') <= 1e-12, 'Parent cut rows differ from barycentric replay')
    brief = (src >= 0) & PL['original10582MainBriefSourceMask'][np.maximum(src, 0)]
    require(np.array_equal(brief, PL['fixedMainBriefFaceMask']) and int(brief.sum()) == policy['briefFacesBefore'], 'Parent brief mask is not the sealed original brief')
    require(np.array_equal(PL['compilerFaceMaterialIds'] == 4, brief), 'Parent brief is not compiler slot 4')
    return {'originalIdentityRowsExact': int(ident.sum()), 'originalCutRows': int(cut.sum()), 'cutReplayMaximumErrors': errors,
            'inheritedGeneratedCapRowsNotReplayed': int((src < 0).sum()), 'briefFaces': int(brief.sum())}


def verify_rebuild(P, PL, R, RL, rproof, policy):
    n = len(R['positions']); d = RL['directParentFaceIds']; new = RL['rebuiltPatchFaceMask']; kept = ~new
    disp = RL['sideLipDisplacedFaceMask']; rer = RL['farSideBandReroutedFaceMask']; caps = RL['generatedCapFaceIds']
    require(set(R) == ARCHIVE_KEYS and n == policy['faces'] and all(len(RL[k]) == n for k in ('directParentFaceIds', 'documentFaceMaterialIds', 'compilerFaceMaterialIds', 'fixedMainBriefFaceMask')), 'Rebuild archive schema/count differs')
    require(np.array_equal(new, d < 0) and int(kept.sum()) == policy['keptFaces'] and int(new.sum()) == policy['newFaces'], 'Declared kept/new face sets differ')
    deleted = RL['deletedParentFaceIds']
    require(len(np.unique(d[kept])) == kept.sum() and np.array_equal(np.sort(np.concatenate([deleted, d[kept]])), np.arange(len(P['positions'])))
            and len(deleted) == policy['deletedParentFaces'], 'Kept and deleted parent sets must partition the parent exactly')
    for k in ('original10582MainBriefSourceMask', 'original191SkinExceptionSourceIds', 'repairedOriginalParentFaceIds', 'strip134ParentFaceIds', 'stripGrownParentFaceIds'):
        require(np.array_equal(RL[k], PL[k]), 'Static parent lineage changed: ' + k)
    require(int(disp.sum()) == policy['displacedKeptFaces'] and not (disp & new).any() and int(rer.sum()) == policy['reroutedKeptFaces'] and not (rer & new).any(), 'Declared displaced/rerouted sets differ')
    exact = kept & ~disp
    rows = rows_exact(R, P, ('positions', 'normals', 'uvGltf', 'uvNative', 'tangents', 'sourceFaceIds'), exact, d[exact])
    require(all(rows.values()), 'Kept rows differ from the parent authority: ' + str(rows))
    require(rows_exact(R, P, ('uvGltf', 'uvNative', 'sourceFaceIds'), disp, d[disp]) == {'uvGltf': True, 'uvNative': True, 'sourceFaceIds': True}, 'Displaced rows changed UV/source ids')
    require(np.array_equal(RL['sourceCutBarycentricWeights'][kept], PL['sourceCutBarycentricWeights'][d[kept]], equal_nan=True)
            and np.array_equal(R['sourceBarycentricWeights'][kept], P['sourceBarycentricWeights'][d[kept]], equal_nan=True)
            and np.array_equal(RL['sourceFaceIds'], R['sourceFaceIds']) and np.all(R['sourceFaceIds'][new] == -1)
            and np.all(R['sourceBarycentricWeights'][new] == 0) and np.all(RL['sourceCutBarycentricWeights'][new] == 0), 'Source lineage of kept/new rows differs')
    move = np.linalg.norm(R['positions'][disp] - P['positions'][d[disp]], axis=-1)
    require(float(move.max(initial=0)) <= policy['displacedMaxMoveMetres'], 'Displaced rows exceed declared bound')
    require(int((np.einsum('ij,ij->i', face_normals(R['positions'][disp]), face_normals(P['positions'][d[disp]])) <= 0).sum()) == 0, 'Displaced face orientation flips')
    moved_points = {r.tobytes() for r in R['positions'][disp].reshape(-1, 3)} - {r.tobytes() for r in P['positions'][d[disp]].reshape(-1, 3)}
    require(not moved_points & {r.tobytes() for r in R['positions'][exact].reshape(-1, 3)}, 'Displaced vertex is shared with an exact kept row')
    # Generated caps and tangent ids.
    require(np.array_equal(RL['generatedCapFaceIds'], R['generatedCapFaceIds']) and np.array_equal(d[caps], PL['generatedCapFaceIds'])
            and not (disp[caps] | rer[caps]).any(), 'Generated cap rows are not inherited exactly')
    require(np.array_equal(R['tangentTriangleIds'], np.arange(n)) and np.array_equal(P['tangentTriangleIds'], np.arange(len(P['positions']))), 'Dense tangent ids required')
    # Materials and brief.
    doc = RL['documentFaceMaterialIds']; comp = RL['compilerFaceMaterialIds']; brief = RL['fixedMainBriefFaceMask']
    require(np.array_equal(comp, np.where(brief, 4, doc)) and set(np.unique(doc)) == {0, 1, 2, 3}, 'Compiler ids must equal document ids except brief slot 4')
    require(np.array_equal(doc >= 2, new | rer) and np.all(PL['compilerFaceMaterialIds'][d[rer]] == 0)
            and np.array_equal(doc[kept & ~rer], PL['documentFaceMaterialIds'][d[kept & ~rer]]), 'Atlas routing differs from declared reroute/new sets')
    for atlas, count in policy['newFacesByAtlas'].items():
        require(int((new & (doc == int(atlas))).sum()) == count, 'New-face atlas inventory differs')
    require(not (brief & new).any() and np.array_equal(brief[kept], PL['fixedMainBriefFaceMask'][d[kept]]) and int(brief.sum()) == policy['briefFacesAfter']
            and not (brief & (disp | rer)).any(), 'Remaining brief must be exactly the kept parent brief')
    tab, bow = RL['briefTabTrimParentFaceIds'].astype(np.int64), RL['briefBowKnotParentFaceIds'].astype(np.int64)
    require(np.array_equal(np.sort(deleted[PL['fixedMainBriefFaceMask'][deleted]]), np.sort(np.concatenate([tab, bow]))) and len(np.intersect1d(tab, bow)) == 0
            and len(tab) == policy['briefTabTrimFaces'] and len(bow) == policy['briefBowKnotFaces'], 'Deleted brief faces differ from the declared exceptions')
    require(rproof['briefTabTrimFaceIds']['parentFaceIds'] == tab.tolist() and rproof['briefBowKnotFaceIds']['parentFaceIds'] == bow.tolist()
            and rproof['briefFacesFinal'] == policy['briefFacesAfter'], 'Brief exception ids differ from the rebuild proof')
    # New faces: area, orientation, closure, intersections.
    area = np.linalg.norm(face_normals(R['positions'][new]), axis=1) / 2
    require(float(area.min()) >= policy['minNewFaceAreaSquareMetres'], 'Degenerate new face')
    closure = closure_report(R['positions'], np.flatnonzero(new | disp))
    require(closure['notTwoFaceEdges'] == 0 and closure['inconsistentOrientationEdges'] == 0, 'New/displaced faces open, non-manifold or flipped: ' + str(closure))
    pf, pk, _, pc, _ = edge_inventory(P['positions']); cf, ck, _, cc, _ = edge_inventory(R['positions'])
    require(edge_positions(R['positions'], cf, ck, cc == 1) <= edge_positions(P['positions'], pf, pk, pc == 1)
            and edge_positions(R['positions'], cf, ck, cc > 2) <= edge_positions(P['positions'], pf, pk, pc > 2), 'Rebuild introduced boundary or non-manifold edges')
    crossings = intersecting_faces(R['positions'], np.flatnonzero(new | disp))
    require(not crossings, 'New/displaced faces intersect: %d pairs' % len(crossings))
    # UV islands and texel aliasing.
    uv = R['uvGltf']; px = policy['atlasPixels']; isl = RL['rebuiltPatchIslandIds']; placements = rproof['texture']['placements']
    require(set(placements) == set(policy['islandsByAtlas']) and np.array_equal(isl >= 0, new), 'Island inventory differs')
    alias = {}
    for atlas, islands in policy['islandsByAtlas'].items():
        rects = {r['island']: r for r in placements[atlas]}; require(sorted(rects) == sorted(islands), 'Atlas islands differ')
        boxes = []
        for i in islands:
            m = isl == i; x0, y0, w, h = rects[i]['px']; q = uv[m] * px; boxes.append((x0, y0, x0 + w, y0 + h))
            require(int(m.sum()) == rects[i]['faces'] and np.all(doc[m] == int(atlas)) and 0 <= x0 and 0 <= y0 and x0 + w <= px and y0 + h <= px
                    and np.all(q[..., 0] >= x0 - 1e-6) and np.all(q[..., 0] <= x0 + w + 1e-6) and np.all(q[..., 1] >= y0 - 1e-6) and np.all(q[..., 1] <= y0 + h + 1e-6),
                    'New-face UVs outside their declared atlas island')
        for i, a in enumerate(boxes):
            for b in boxes[i + 1:]:
                require(a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1], 'Overlapping island placements')
        pad = policy['texelAliasPaddingPixels']; shared = np.intersect1d(texel_footprint(uv[new & (doc == int(atlas))] * px, pad), texel_footprint(uv[rer & (doc == int(atlas))] * px, pad))
        require(not len(shared), 'Rerouted faces alias rebuilt-patch texels'); alias[atlas] = 0
    require(np.all(uv[doc >= 2] >= 0) and np.all(uv[doc >= 2] <= 1), 'Extra-atlas UVs outside unit atlas')
    return {'keptRowsExact': int(exact.sum()), 'displacedRows': int(disp.sum()), 'displacedMaximumMoveMetres': float(move.max(initial=0)),
            'newFaces': int(new.sum()), 'deletedParentFaces': int(len(deleted)), 'minNewFaceAreaSquareMetres': float(area.min()),
            'newAndDisplacedClosure': closure, 'newAndDisplacedIntersections': 0, 'reroutedFaces': int(rer.sum()),
            'reroutedPatchTexelAliases': alias, 'briefFaces': int(brief.sum()), 'briefExceptions': {'tabTrim': len(tab), 'bowKnot': len(bow)}}


def verify_rebuild_glb(pdoc, pbin, pg, pmat, rdoc, rbin, rg, rmat, P, PL, R, RL, policy):
    d = RL['directParentFaceIds']; new = RL['rebuiltPatchFaceMask']; disp = RL['sideLipDisplacedFaceMask']; exact = ~new & ~disp
    require(np.array_equal(pmat, PL['documentFaceMaterialIds']) and np.array_equal(rmat, RL['documentFaceMaterialIds']), 'GLB primitive ownership differs from lineage')
    rows = rows_exact(rg, pg, ('positions', 'normals', 'uvGltf', 'tangents'), exact, d[exact])
    require(all(rows.values()) and rg['uvGltf'][disp].tobytes() == pg['uvGltf'][d[disp]].tobytes(), 'Kept decoded GLB rows differ from parent: ' + str(rows))
    errors = {k: float(np.abs(rg[k][new | disp] - R[k][new | disp]).max()) for k in ('positions', 'normals', 'uvGltf', 'tangents')}
    require(all(errors[k] <= policy['glbNativeTolerance'][k] for k in errors), 'New/displaced GLB rows differ from native authority: ' + str(errors))
    pm = base.embedded_maps(pdoc, pbin); rm = base.embedded_maps(rdoc, rbin)
    require(rm[:len(pm)] == pm and rdoc['materials'][:2] == pdoc['materials'][:2] and rdoc.get('samplers') == pdoc.get('samplers')
            and rdoc['textures'][:len(pdoc['textures'])] == pdoc['textures'], 'Parent maps/materials not retained')
    return {'keptDecodedGlbRowsExact': int(exact.sum()), 'newAndDisplacedGlbNativeMaximumErrors': errors, 'parentImagesRetained': len(pm), 'appendedImages': len(rm) - len(pm)}


def verify_final(R, RL, F, FL, rdoc, rbin, rg, fdoc, fbin, fg, fmat, q):
    require(set(F) == set(R) and all(F[k].dtype == R[k].dtype and F[k].shape == R[k].shape for k in R), 'Final archive schema changed')
    for k in R:
        if k not in MOVED:
            require(F[k].tobytes() == R[k].tobytes(), 'Unmoved final authority changed: ' + k)
    require(set(FL) == set(RL) and all(FL[k].tobytes() == RL[k].tobytes() and FL[k].dtype == RL[k].dtype for k in RL), 'Final lineage differs from rebuild lineage')
    brief = RL['fixedMainBriefFaceMask']; bv = np.unique(R['positions'][brief].reshape(-1, 3), axis=0)
    flat = lambda x: x.reshape(-1, x.shape[-1])
    P2 = buttock_map(flat(R['positions']), q, bv).reshape(R['positions'].shape)
    N2, T2 = buttock_transform(flat(R['positions']), flat(R['normals']), flat(R['tangents']), q, bv)
    errors = {'positions': float(np.abs(F['positions'] - P2).max()), 'normals': float(np.abs(F['normals'] - N2.reshape(R['normals'].shape)).max()),
              'tangents': float(np.abs(F['tangents'] - T2.reshape(R['tangents'].shape)).max())}
    tol = REPLAY_TOLERANCE['native']
    require(errors['positions'] <= tol[0] and errors['normals'] <= tol[1] and errors['tangents'] <= tol[1], 'Buttock native replay differs: ' + str(errors))
    require(np.array_equal(F['tangents'][..., 3], R['tangents'][..., 3]), 'Tangent handedness changed')
    for k in MOVED:
        require(F[k][brief].tobytes() == R[k][brief].tobytes(), 'Brief rows moved')
    require(int((np.einsum('ij,ij->i', face_normals(F['positions']), face_normals(R['positions'])) <= 0).sum()) == 0
            and float(np.linalg.norm(face_normals(F['positions']), axis=1).min()) > 0, 'Final face flips or degeneracy')
    move = float(np.linalg.norm(F['positions'] - R['positions'], axis=-1).max()); require(move <= q['e'] * (1 + 1e-9), 'Final move exceeds declared depth')
    cf = closure_report(F['positions'], np.zeros(0, np.int64)); cr = closure_report(R['positions'], np.zeros(0, np.int64))
    require((cf['boundaryEdges'], cf['nonManifoldEdges']) == (cr['boundaryEdges'], cr['nonManifoldEdges']), 'Final map changed exact closure')
    # Serialized candidate: same document except moved attributes; f32 replay of the same map on the rebuild GLB.
    require(strip_moved(fdoc) == strip_moved(rdoc) and base.embedded_maps(fdoc, fbin) == base.embedded_maps(rdoc, rbin), 'Final document changed beyond moved attributes')
    require(fg['uvGltf'].tobytes() == rg['uvGltf'].tobytes() and np.array_equal(fmat, RL['documentFaceMaterialIds']), 'Final GLB UV/ownership changed')
    require(fbin[:len(rbin)] == rbin, 'Final GLB must keep the rebuild buffer prefix')
    gp = buttock_map(flat(rg['positions']), q, bv).reshape(rg['positions'].shape)
    gn, gt = buttock_transform(flat(rg['positions']), flat(rg['normals']), flat(rg['tangents']), q, bv)
    gerr = {'positions': float(np.abs(fg['positions'] - gp).max()), 'normals': float(np.abs(fg['normals'] - gn.reshape(rg['normals'].shape)).max()),
            'tangents': float(np.abs(fg['tangents'] - gt.reshape(rg['tangents'].shape)).max())}
    tol = REPLAY_TOLERANCE['glb']
    require(gerr['positions'] <= tol[0] and gerr['normals'] <= tol[1] and gerr['tangents'] <= tol[1], 'Buttock GLB replay differs: ' + str(gerr))
    return {'nativeReplayMaximumErrors': errors, 'glbReplayMaximumErrors': gerr, 'maximumMoveMetres': move,
            'movedCorners': int((np.linalg.norm(F['positions'] - R['positions'], axis=-1) > 0).sum()), 'briefRowsExact': True, 'closure': cf}


def verify_receipt(g, c, target, th, part, baseline_receipt):
    require(g.get('schemaVersion') == 2 and g.get('kind') == 'target-part-geometry' and g.get('operation') == OPERATION, 'Final geometry receipt kind/operation differs')
    require(all(g[k] == baseline_receipt[k] for k in IDENTITY) and g['coordinateSpace'] == 'working' and g['statureApplications'] == 0 and g['part'] == part,
            'Geometry identity mismatch')
    require(g['targetContractSha256'] == th and g['targetId'] == target['id'] and g['model'] == target['models'][part], 'Cross target/model')
    require(base.checked_pin({'path': g['candidate'], 'sha256': g['candidateSha256']}) == base.checked_pin(c['final']['candidate'])
            and base.checked_pin(g['nativeCornerArchive']) == base.checked_pin(c['final']['nativeCorners'])
            and base.checked_pin({'path': g['source'], 'sha256': g['sourceSha256']}) == base.checked_pin(c['parent']['candidate'])
            and base.checked_pin({'path': g['sourceReceipt'], 'sha256': g['sourceReceiptSha256']}) == base.checked_pin(c['parent']['geometry'])
            and base.checked_pin(g['lineage']) == base.checked_pin(c['final']['lineage']), 'Final receipt pins differ from contract')
    require(g.get('runtimeSelected') is False and g.get('nativeAccepted') is False and g.get('productionAccepted') is False, 'Descendant receipts carry no acceptance')


def _prepare(contract_pin, *, target_path, target, part, space, baseline_context):
    cp, ch = base.checked_pin(contract_pin); c = base.strict_json(cp)
    policy, q = validate_contract(c, part, space)
    tp, th = base.checked_pin(c['target']); require(Path(target_path).resolve() == Path(tp) and base.strict_json(tp) == target, 'Cross target')
    require(target['rig']['mode'] == 'stock-exact' and target['rig']['runtimeScale'] == 1, 'Rig unsupported')
    consumers = {str(Path(__file__).resolve()), str(Path(base.__file__).resolve())}
    require(len(c['consumers']) == 2 and {base.checked_pin(p)[0] for p in c['consumers']} == consumers, 'Exact current consumer whitelist required')
    module = sys.modules.get('source_representation_contract')
    require(module is not None and type(baseline_context) is module.VerifiedRepresentation, 'Sealed original pelvis source representation required')
    baseline_context.verify(); pr = baseline_context.proof
    require(dict(pr['contract']) == c['baselineRepresentation'] and pr['part'] == part and pr['targetId'] == target['id'] and pr['coordinateSpace'] == 'working', 'Cross original baseline')
    declared = {}
    for row in c['physicalInputs']:
        p, h = base.checked_pin(row); require(p not in declared, 'Duplicate physical path'); declared[p] = h
    require(declared == {r['path']: r['sha256'] for r in expected_physical_inputs(c, baseline_context)}, 'Unreachable, missing or stale physical input')
    # Pinned proofs and receipts must name exactly the contract authorities.
    rproof = base.strict_json(c['rebuild']['proof']['path']); fproof = base.strict_json(c['final']['proof']['path'])
    pins = lambda row: base.checked_pin(row)
    require(pins(rproof['parentCandidate']) == pins(c['parent']['candidate']) and pins(rproof['parentNative']) == pins(c['parent']['nativeCorners'])
            and pins(rproof['parentLineage']) == pins(c['parent']['lineage']) and pins(rproof['candidate']) == pins(c['rebuild']['candidate'])
            and pins(rproof['nativeCorners']) == pins(c['rebuild']['nativeCorners']) and pins(rproof['lineage']) == pins(c['rebuild']['lineage']), 'Rebuild proof names other authorities')
    require(rproof.get('selection') is False and rproof.get('runtimeConversion') is False and fproof.get('selection') is False and fproof.get('runtimeConversion') is False, 'Proofs carry no selection')
    require(pins(fproof['candidate']) == pins(c['final']['candidate']) and pins(fproof['nativeCorners']) == pins(c['final']['nativeCorners'])
            and pins(fproof['lineage']) == pins(c['final']['lineage']) and pins(fproof['immediateParent']['proof']) == pins(c['rebuild']['proof'])
            and pins(fproof['immediateParent']['candidate']) == pins(c['rebuild']['candidate']) and pins(fproof['immediateParent']['nativeCorners']) == pins(c['rebuild']['nativeCorners'])
            and fproof['buttockLowerEdgeExtension']['parameters'] == q, 'Final proof names other authorities or parameters')
    pg = base.strict_json(c['parent']['geometry']['path'])
    require(pins(pg['candidate']) == pins(c['parent']['candidate']) and pins(pg['nativeCorners']) == pins(c['parent']['nativeCorners'])
            and pins(pg['lineage']) == pins(c['parent']['lineage']), 'Parent receipt names other authorities')
    baseline_receipt = base.strict_json(base.checked_pin(dict(pr['originalGeometryReceipt']))[0])
    verify_receipt(base.strict_json(c['final']['geometry']['path']), c, target, th, part, baseline_receipt)
    O = load(dict(pr['originalNativeCornerArchive'])); P, PL = load(c['parent']['nativeCorners']), load(c['parent']['lineage'])
    R, RL = load(c['rebuild']['nativeCorners']), load(c['rebuild']['lineage']); F, FL = load(c['final']['nativeCorners']), load(c['final']['lineage'])
    report = {'kind': KIND, 'parentAgainstSealedOriginal': verify_parent(O, P, PL, policy), 'rebuild': verify_rebuild(P, PL, R, RL, rproof, policy)}
    pdoc, pbin, pgl, pmat = decode(c['parent']['candidate']['path']); rdoc, rbin, rgl, rmat = decode(c['rebuild']['candidate']['path'])
    fdoc, fbin, fgl, fmat = decode(c['final']['candidate']['path'])
    report['rebuildGlb'] = verify_rebuild_glb(pdoc, pbin, pgl, pmat, rdoc, rbin, rgl, rmat, P, PL, R, RL, policy)
    report['final'] = verify_final(R, RL, F, FL, rdoc, rbin, rgl, fdoc, fbin, fgl, fmat, q)
    baseline_context.verify()
    for p, h in declared.items():
        require(base.sha(p) == h, 'Changed closing input: ' + p)
    report.update(delaunayRebuildReplayed=False, historicalPythonExecuted=False, runtimeSelected=False, materialApproval=False)
    arrays = {**{('literalNativeArchive', k): v for k, v in F.items()}, **{('serializedGlbF32', k): v for k, v in fgl.items()}}
    frozen = MappingProxyType({k: (v.dtype.str, v.shape, v.tobytes()) for k, v in arrays.items()})
    physical = tuple(sorted(declared.items())) + ((cp, ch),)
    result = base.DiagnosticRepresentation(base._SEAL, (target['id'], part), physical, frozen, (base.checked_pin(c['final']['geometry']), base.checked_pin(c['final']['candidate'])))
    return result.verify(), MappingProxyType(report)
