"""Bounded positional/normal descendant of a sealed diagnostic representation (non-analytic edits, verified bounds).

Used for (a) the approved renormalisation of non-unit authored normals (identity position map) and (b) the female
thigh/shin back crease fairing. The parent representation is re-verified in full through the existing dispatch.
Independently checked here:
  * archive schema, UVs, ids, face order and every non-moved key byte-identical to the verified parent authority;
  * only corners inside the declared position envelope moved, no farther than the declared maximum; a parent-welded
    vertex moves as one; outside the envelope rows are bit-exact (identity map: positions byte-identical);
  * no new locally inverted face, every face keeps >= minimumAreaRatio of its parent area, welded closure unchanged;
  * normals/tangents equal an independent replay of bounded_descendant_rules (unit normals, transported by the
    smoothed-geometric-normal rotation, optional declared smoothing regions; tangents re-orthogonalised);
  * the candidate GLB keeps indices/UVs/images/document, changes only POSITION/NORMAL/TANGENT bytes, and decodes to
    exactly float32 of the archive (TANGENT to float32 of the replayed rule);
  * receipt lineage, identity fields and a full physical-input closure.
No runtime, material, approval or acceptance is implied.
"""
from pathlib import Path
from types import MappingProxyType
import sys
import numpy as np
import diagnostic_descendant_representation as base
import bounded_descendant_rules as rules
import fair_female_limb_creases as fair

KIND = 'diagnostic-bounded-descendant-representation'
OPERATION = 'bounded-positional-normal-descendant-v1'
BASELINE_KINDS = ('diagnostic-thigh-descendant-representation', 'diagnostic-elbow-descendant-representation', 'diagnostic-shin-descendant-representation',
                  'diagnostic-analytic-descendant-representation', 'diagnostic-rebuilt-patch-descendant-representation')
IDENTITY = ('targetContract', 'targetContractSha256', 'targetId', 'rigRevision', 'joint', 'model', 'attachmentWorld', 'part', 'coordinateSpace', 'statureApplications')
CARRIED = ('generatedCapsUntextured', 'materialRGBBindingParent', 'materialRGBBindingSupportReceipt', 'materialRGBBindingHistoricalDerivedAtlas', 'materialRGBBindingOperation')
MOVED = ('positions', 'normals', 'tangents')
OP_KEYS = ('kind', 'positionEnvelope', 'normalRule', 'minimumAreaRatio', 'generator')


def require(ok, message):
    if not ok:
        raise base.RepresentationError(message)


def to_gltf(v):
    v = np.asarray(v); return np.stack((v[..., 0], v[..., 2], -v[..., 1]), axis=-1)


def to_nwn(v):
    v = np.asarray(v); return np.stack((v[..., 0], -v[..., 2], v[..., 1]), axis=-1)


def glb_corners(doc, b):
    """Per archive corner (primitive order): (primitive index, vertex index) plus decoded NWN arrays."""
    prim_of, vert_of, rows = [], [], {'positions': [], 'normals': [], 'uvNative': [], 'tangents': []}
    for k, p in enumerate(doc['meshes'][0]['primitives']):
        i = base.accessor(doc, b, p['indices']).reshape(-1, 3).astype(np.int64); at = p['attributes']
        prim_of.append(np.full(i.shape, k)); vert_of.append(i)
        rows['positions'].append(to_nwn(base.accessor(doc, b, at['POSITION'])[i].astype(np.float64)))
        rows['normals'].append(to_nwn(base.accessor(doc, b, at['NORMAL'])[i].astype(np.float64)))
        u = base.accessor(doc, b, at['TEXCOORD_0'])[i].astype(np.float64); rows['uvNative'].append(np.stack((u[..., 0], 1 - u[..., 1]), axis=-1))
        if 'TANGENT' in at:
            t = base.accessor(doc, b, at['TANGENT'])[i].astype(np.float64); rows['tangents'].append(np.concatenate([to_nwn(t[..., :3]), t[..., 3:]], axis=-1))
        else:
            rows['tangents'].append(None)
    return np.concatenate(prim_of), np.concatenate(vert_of), rows


def attribute_span(doc, prim, name):
    a = doc['accessors'][doc['meshes'][0]['primitives'][prim]['attributes'][name]]; v = doc['bufferViews'][a['bufferView']]
    width = {'VEC3': 3, 'VEC4': 4}[a['type']]; stride = v.get('byteStride', 4 * width)
    return v.get('byteOffset', 0) + a.get('byteOffset', 0), stride, width, a['count']


def moved_mask(doc, length):
    mask = np.zeros(length, bool)
    for k, p in enumerate(doc['meshes'][0]['primitives']):
        for name in ('POSITION', 'NORMAL', 'TANGENT'):
            if name in p['attributes']:
                off, stride, width, count = attribute_span(doc, k, name)
                for j in range(count):
                    mask[off + j * stride: off + j * stride + 4 * width] = True
    return mask


def glb_tangent_rows(prim, tangents):
    """Triangle rows of primitives carrying a GLB TANGENT attribute and their decoded corner tangents."""
    have = np.array([t is not None for t in tangents]); rows = np.flatnonzero(have[prim[:, 0]])
    return rows, (np.concatenate([t for t in tangents if t is not None]) if len(rows) else None)


def replay(P0, N0, P1, operation, archive, glb_tangents, glb_rows=None):
    """Independent rule replay: (N1, sparse/dense archive tangents or None, GLB tangents of glb_rows or None)."""
    spec = operation['normalRule']; T = None
    if 'tangents' in archive:
        rows = archive['tangentTriangleIds'] if 'tangentTriangleIds' in archive else None
        _, T, _ = rules.apply(P0, N0, P1, spec, tangents=archive['tangents'], tangent_rows=rows)
    N1, _, report = rules.apply(P0, N0, P1, spec)
    G = None
    if glb_tangents is not None:
        _, G, _ = rules.apply(P0, N0, P1, spec, tangents=glb_tangents, tangent_rows=glb_rows)
    return N1, T, G, report


def prepare_bounded_representation(contract_pin, *, target_path, target, part, space='working', baseline_context=None):
    try:
        return _prepare(contract_pin, target_path=target_path, target=target, part=part, space=space, baseline_context=baseline_context)
    except base.RepresentationError:
        raise
    except (KeyError, TypeError, ValueError, IndexError, OSError, AttributeError) as error:
        raise base.RepresentationError('Malformed bounded representation input: ' + str(error)) from error


def parent_context(pin, *, target_path, target, part, space, baseline_context):
    kind = base.strict_json(base.checked_pin(pin)[0]).get('kind')
    require(kind != KIND, 'Nested bounded descendants are not supported')
    ctx = baseline_context if kind in BASELINE_KINDS else None
    if kind == 'diagnostic-analytic-descendant-representation':
        from diagnostic_analytic_representation import prepare_analytic_representation
        return prepare_analytic_representation(pin, target_path=target_path, target=target, part=part, space=space, baseline_context=ctx)[0]
    if kind == 'diagnostic-rebuilt-patch-descendant-representation':
        from diagnostic_rebuilt_patch_representation import prepare_rebuilt_patch_representation
        return prepare_rebuilt_patch_representation(pin, target_path=target_path, target=target, part=part, space=space, baseline_context=ctx)[0]
    return base.prepare_diagnostic_representation(pin, target_path=target_path, target=target, part=part, space=space, baseline_context=ctx)


def _prepare(contract_pin, *, target_path, target, part, space, baseline_context):
    require(not sys.flags.optimize, 'Optimized assertion removal forbidden')
    cp, ch = base.checked_pin(contract_pin); c = base.strict_json(cp)
    base.keys(c, ('kind', 'schemaVersion', 'target', 'part', 'space', 'parentRepresentation', 'operation', 'final', 'consumers', 'physicalInputs'))
    require(c['kind'] == KIND and type(c['schemaVersion']) is int and c['schemaVersion'] == 1, 'Unknown bounded contract')
    require(c['part'] == part and c['space'] == space == 'working', 'Cross owner/space')
    tp, _ = base.checked_pin(c['target']); require(Path(target_path).resolve() == Path(tp) and base.strict_json(tp) == target, 'Cross target')
    require(target['rig']['mode'] == 'stock-exact' and target['rig']['runtimeScale'] == 1, 'Rig unsupported')
    op = c['operation']; base.keys(op, OP_KEYS); require(op['kind'] == OPERATION, 'Unknown bounded operation')
    env = op['positionEnvelope']
    if env is not None:
        base.keys(env, ('regions', 'maximumDisplacement'))
        require(env['regions'] and isinstance(env['maximumDisplacement'], float) and 0 < env['maximumDisplacement'] <= 0.03, 'Bounded envelope required')
        for r in env['regions']:
            rules.check_region(r)
    base.keys(op['normalRule'], ('geometricSmoothing', 'smoothingRegions'))
    require(type(op['normalRule']['geometricSmoothing']) is int and 0 <= op['normalRule']['geometricSmoothing'] <= 16, 'Bounded smoothing iterations required')
    for r in op['normalRule']['smoothingRegions']:
        rules.check_region(r)
    require(isinstance(op['minimumAreaRatio'], float) and 0 < op['minimumAreaRatio'] < 1, 'Explicit minimum area ratio required')
    base.keys(c['final'], ('candidate', 'geometry', 'nativeCorners'))
    declared = {}
    for pin in c['physicalInputs']:
        p, h = base.checked_pin(pin); require(p not in declared, 'Duplicate physical path'); declared[p] = h
    consumers = {str(Path(m.__file__).resolve()) for m in (sys.modules[__name__], rules, fair, base)}
    require(len(c['consumers']) == 4 and {base.checked_pin(p)[0] for p in c['consumers']} == consumers, 'Exact current consumer whitelist required')
    parent = parent_context(c['parentRepresentation'], target_path=target_path, target=target, part=part, space=space, baseline_context=baseline_context)
    require(type(parent) is base.DiagnosticRepresentation, 'Sealed parent representation required')
    parent_receipt, parent_candidate = parent._geometry
    expected = {p['path']: p['sha256'] for p in parent.physical_inputs}
    for pin in [c['target'], c['parentRepresentation'], *c['final'].values(), *c['consumers']]:
        p, h = base.checked_pin(pin); expected[p] = h
    require(declared == {str(Path(p).resolve()): h for p, h in expected.items()}, 'Unreachable, missing or stale physical input')
    # Receipt lineage and identity.
    g = base.strict_json(c['final']['geometry']['path']); sg = base.strict_json(parent_receipt[0])
    require(g.get('operation') == OPERATION and g.get('boundedDescendant') == op, 'Receipt operation differs from the contract')
    require(base.checked_pin({'path': g['sourceReceipt'], 'sha256': g['sourceReceiptSha256']}) == parent_receipt, 'Wrong parent receipt')
    require(base.checked_pin({'path': g['source'], 'sha256': g['sourceSha256']}) == parent_candidate, 'Wrong parent candidate')
    require(base.checked_pin({'path': g['candidate'], 'sha256': g['candidateSha256']}) == base.checked_pin(c['final']['candidate']), 'Wrong final candidate')
    require(base.checked_pin(g['nativeCornerArchive']) == base.checked_pin(c['final']['nativeCorners']), 'Wrong final native archive')
    require(all(g[k] == sg[k] for k in IDENTITY) and g['coordinateSpace'] == 'working' and g['statureApplications'] == 0 and g['part'] == part, 'Geometry identity mismatch')
    require(all(g.get(k) == sg.get(k) for k in CARRIED), 'Carried parent lineage fields changed')
    require(not g.get('runtimeSelected') and not g.get('nativeAccepted') and not g.get('productionAccepted'), 'Descendant receipts carry no acceptance')
    # Archive authority.
    S = dict(np.load(base.checked_pin(sg['nativeCornerArchive'])[0], allow_pickle=False)); A = dict(np.load(c['final']['nativeCorners']['path'], allow_pickle=False))
    require(set(S) == set(A), 'Archive schema changed')
    for k in S:
        if k not in MOVED:
            require(S[k].dtype == A[k].dtype and S[k].shape == A[k].shape and S[k].tobytes() == A[k].tobytes(), 'Unmoved authority changed: ' + k)
        else:
            require(A[k].dtype == np.float64 and A[k].shape == S[k].shape and np.isfinite(A[k]).all(), 'Archive dtype/shape changed: ' + k)
    for k in MOVED:
        if k in S:
            require(parent.array('literalNativeArchive', k).tobytes() == S[k].tobytes(), 'Parent archive differs from verified parent authority: ' + k)
    P0, N0, P1 = S['positions'], S['normals'], A['positions']
    U0, F = fair.weld(P0)
    try:
        U1, moved = rules.child_vertices(P0, P1, F, U0)
    except ValueError as error:
        raise base.RepresentationError(str(error))
    disp = np.linalg.norm(U1 - U0, axis=1)
    if env is None:
        require(P1.tobytes() == P0.tobytes(), 'Identity envelope moved positions')
    else:
        inside = rules.region_weight(U0, env['regions']) > 0
        require(not np.any(moved & ~inside), 'Moved vertex outside the declared envelope')
        require(float(disp.max()) <= env['maximumDisplacement'], 'Displacement exceeds the declared bound')
    a0 = np.linalg.norm(fair.face_normals(U0, F), axis=1); a1 = np.linalg.norm(fair.face_normals(U1, F), axis=1)
    require(np.all(a1 >= op['minimumAreaRatio'] * a0) and np.all(a1 > 0), 'Collapsed or degenerate face')
    require(not np.any(fair.inverted_faces(U1, F) & ~fair.inverted_faces(U0, F)), 'Face orientation flips')
    # Normals / tangents: independent replay.
    pdoc, pbin = base.read_glb(parent_candidate[0]); doc, binary = base.read_glb(c['final']['candidate']['path'])
    pprim, pvert, praw = glb_corners(pdoc, pbin); prim, vert, raw = glb_corners(doc, binary)
    require(len(pprim) == len(P0) and np.array_equal(pprim, prim) and np.array_equal(pvert, vert), 'Candidate indices/corner order changed')
    require([t is None for t in praw['tangents']] == [t is None for t in raw['tangents']], 'GLB TANGENT presence changed')
    trows, glb_t = glb_tangent_rows(pprim, praw['tangents'])
    N1, T1, G1, report = replay(P0, N0, P1, op, S, glb_t, trows)
    dn = float(np.abs(A['normals'] - N1).max()); require(dn <= 1e-12, 'Normal rule replay differs: %.3g' % dn)
    require(np.allclose(np.linalg.norm(A['normals'], axis=2), 1, atol=1e-12, rtol=0), 'Unit authored normals required')
    report = dict(report, maxNormalReplayError=dn)
    if 'tangents' in S:
        require(np.array_equal(A['tangents'][..., 3], S['tangents'][..., 3]), 'Tangent handedness changed')
        dt = float(np.abs(A['tangents'] - T1).max()); require(dt <= 1e-12, 'Tangent rule replay differs: %.3g' % dt); report['maxTangentReplayError'] = dt
    # Serialized candidate.
    require(np.concatenate(raw['uvNative']).tobytes() == np.concatenate(praw['uvNative']).tobytes(), 'Candidate UVs changed')
    require(base.embedded_maps(doc, binary) == base.embedded_maps(pdoc, pbin), 'Candidate images changed')
    f32 = lambda x: np.asarray(x).astype(np.float32).astype(np.float64)
    require(np.array_equal(np.concatenate(raw['positions']), f32(A['positions'])) and np.array_equal(np.concatenate(raw['normals']), f32(A['normals'])),
            'Candidate decode differs from float32 of the archive')
    if G1 is not None:
        require(np.array_equal(glb_tangent_rows(prim, raw['tangents'])[1], f32(G1)),
                'Candidate TANGENT differs from the replayed rule')
    strip = lambda d: {**d, 'accessors': [{k: v for k, v in a.items() if k not in ('min', 'max')} for a in d['accessors']]}
    require(strip(doc) == strip(pdoc), 'Candidate document changed beyond moved attribute bounds')
    require(len(binary) == len(pbin), 'Candidate buffer length changed')
    mask = moved_mask(doc, len(binary))
    require(np.array_equal(np.frombuffer(pbin, np.uint8)[~mask], np.frombuffer(binary, np.uint8)[~mask]), 'Unmoved candidate bytes changed')
    report.update(movedVertices=int(moved.sum()), maximumDisplacement=float(disp.max()), minimumAreaRatio=float((a1 / np.maximum(a0, 1e-300)).min()))
    arrays = {**{('literalNativeArchive', k): v for k, v in A.items()}, **{('serializedGlbF32', k): np.concatenate(v) for k, v in raw.items() if k != 'tangents'}}
    frozen = MappingProxyType({k: (v.dtype.str, v.shape, v.tobytes()) for k, v in arrays.items()})
    physical = tuple(sorted(declared.items())) + ((cp, ch),)
    result = base.DiagnosticRepresentation(base._SEAL, (target['id'], part), physical, frozen, (base.checked_pin(c['final']['geometry']), base.checked_pin(c['final']['candidate'])))
    return result.verify(), MappingProxyType(report)
