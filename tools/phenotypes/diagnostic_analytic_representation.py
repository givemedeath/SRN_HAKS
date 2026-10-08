"""Analytic radial descendant of a sealed diagnostic representation (one whitelisted map, adopted parameters only).

The parent representation is re-verified in full. The descendant's literal native archive is replayed independently
from the parent's literal native positions/normals/tangents; UVs, ids and face order stay byte-identical, and the
candidate GLB must decode to the archive exactly. No runtime, material or acceptance approval.
"""
from pathlib import Path
from types import MappingProxyType
import sys
import numpy as np
import diagnostic_descendant_representation as base
import analytic_radial_maps as maps

KIND = 'diagnostic-analytic-descendant-representation'
RECEIPT_KEYS = {'analytic-chest-waist-cap-rounding-v1': 'waistCapRounding', 'analytic-thigh-upper-back-slim-top-dome-v1': 'thighUpperBackSlim'}
BASELINE_KINDS = ('diagnostic-thigh-descendant-representation', 'diagnostic-elbow-descendant-representation', 'diagnostic-shin-descendant-representation')
IDENTITY = ('targetContract', 'targetContractSha256', 'targetId', 'rigRevision', 'joint', 'model', 'attachmentWorld', 'part', 'coordinateSpace', 'statureApplications')
MOVED = ('positions', 'normals', 'tangents')


def require(ok, message):
    if not ok:
        raise base.RepresentationError(message)


def prepare_analytic_representation(contract_pin, *, target_path, target, part, space='working', baseline_context=None):
    try:
        return _prepare(contract_pin, target_path=target_path, target=target, part=part, space=space, baseline_context=baseline_context)
    except base.RepresentationError:
        raise
    except (KeyError, TypeError, ValueError, IndexError, OSError, AttributeError) as error:
        raise base.RepresentationError('Malformed analytic representation input: ' + str(error)) from error


def decode(path):
    doc, b = base.read_glb(path); rows = {'positions': [], 'normals': [], 'uvNative': []}
    nwn = lambda v: np.stack((v[..., 0], -v[..., 2], v[..., 1]), axis=-1)
    for p in doc['meshes'][0]['primitives']:
        i = base.accessor(doc, b, p['indices']).reshape(-1, 3).astype(int); at = p['attributes']
        u = base.accessor(doc, b, at['TEXCOORD_0'])[i].astype(float)
        rows['positions'].append(nwn(base.accessor(doc, b, at['POSITION'])[i].astype(float)))
        rows['normals'].append(nwn(base.accessor(doc, b, at['NORMAL'])[i].astype(float)))
        rows['uvNative'].append(np.stack((u[..., 0], 1 - u[..., 1]), axis=-1))
    return doc, b, {k: np.concatenate(v) for k, v in rows.items()}


def moved_ranges(doc):
    spans = []
    for p in doc['meshes'][0]['primitives']:
        for name in ('POSITION', 'NORMAL', 'TANGENT'):
            if name in p['attributes']:
                a = doc['accessors'][p['attributes'][name]]; v = doc['bufferViews'][a['bufferView']]
                start = v.get('byteOffset', 0) + a.get('byteOffset', 0); spans.append((start, start + 4 * a['count'] * {'VEC3': 3, 'VEC4': 4}[a['type']]))
    return spans


def _prepare(contract_pin, *, target_path, target, part, space, baseline_context):
    require(not sys.flags.optimize, 'Optimized assertion removal forbidden')
    cp, ch = base.checked_pin(contract_pin); c = base.strict_json(cp)
    base.keys(c, ('kind', 'schemaVersion', 'target', 'part', 'space', 'parentRepresentation', 'operation', 'final', 'consumers', 'physicalInputs'))
    require(c['kind'] == KIND and type(c['schemaVersion']) is int and c['schemaVersion'] == 1, 'Unknown analytic contract')
    require(c['part'] == part and c['space'] == space == 'working', 'Cross owner/space')
    tp, th = base.checked_pin(c['target']); require(Path(target_path).resolve() == Path(tp) and base.strict_json(tp) == target, 'Cross target')
    require(target['rig']['mode'] == 'stock-exact' and target['rig']['runtimeScale'] == 1, 'Rig unsupported')
    op = c['operation']; base.keys(op, ('kind', 'parameters')); kind = op['kind']
    require(kind in maps.OPERATORS and part in maps.PARTS[kind], 'Unsupported analytic operator/part')
    require(any(op['parameters'] == q for q in maps.ADOPTED[kind]), 'Parameters are not a user-adopted set')
    base.keys(c['final'], ('candidate', 'geometry', 'nativeCorners'))
    declared = {}
    for pin in c['physicalInputs']:
        p, h = base.checked_pin(pin); require(p not in declared, 'Duplicate physical path'); declared[p] = h
    consumers = {str(Path(__file__).resolve()), str(Path(maps.__file__).resolve()), str(Path(base.__file__).resolve())}
    require(len(c['consumers']) == 3 and {base.checked_pin(p)[0] for p in c['consumers']} == consumers, 'Exact current consumer whitelist required')
    # Parent: full independent verification through the existing dispatcher.
    pp, _ = base.checked_pin(c['parentRepresentation']); parent_kind = base.strict_json(pp).get('kind')
    require(parent_kind != KIND, 'Nested analytic descendants are not supported')
    parent = base.prepare_diagnostic_representation(c['parentRepresentation'], target_path=target_path, target=target, part=part, space=space,
                                                    baseline_context=baseline_context if parent_kind in BASELINE_KINDS else None)
    require(type(parent) is base.DiagnosticRepresentation, 'Sealed parent representation required')
    parent_receipt, parent_candidate = parent._geometry
    expected = {p['path']: p['sha256'] for p in parent.physical_inputs}
    for pin in [c['target'], c['parentRepresentation'], *c['final'].values(), *c['consumers']]:
        p, h = base.checked_pin(pin); expected[p] = h
    require(declared == {str(Path(p).resolve()): h for p, h in expected.items()}, 'Unreachable, missing or stale physical input')
    # Receipt lineage.
    g = base.strict_json(c['final']['geometry']['path']); sg = base.strict_json(parent_receipt[0])
    require(g['operation'] == kind and g[RECEIPT_KEYS[kind]]['parameters'] == op['parameters'], 'Receipt operation/parameters differ')
    require(base.checked_pin({'path': g['sourceReceipt'], 'sha256': g['sourceReceiptSha256']}) == parent_receipt, 'Wrong parent receipt')
    require(base.checked_pin({'path': g['source'], 'sha256': g['sourceSha256']}) == parent_candidate, 'Wrong parent candidate')
    require(base.checked_pin({'path': g['candidate'], 'sha256': g['candidateSha256']}) == base.checked_pin(c['final']['candidate']), 'Wrong final candidate')
    require(base.checked_pin(g['nativeCornerArchive']) == base.checked_pin(c['final']['nativeCorners']), 'Wrong final native archive')
    require(all(g[k] == sg[k] for k in IDENTITY) and g['coordinateSpace'] == 'working' and g['statureApplications'] == 0 and g['part'] == part, 'Geometry identity mismatch')
    require(not g.get('runtimeSelected') and not g.get('nativeAccepted') and not g.get('productionAccepted'), 'Descendant receipts carry no acceptance')
    # Independent replay from the parent's literal native authority.
    S = dict(np.load(base.checked_pin(sg['nativeCornerArchive'])[0], allow_pickle=False)); A = dict(np.load(c['final']['nativeCorners']['path'], allow_pickle=False))
    require(set(S) == set(A), 'Archive schema changed')
    for k in S:
        if k not in MOVED:
            require(S[k].dtype == A[k].dtype and S[k].tobytes() == A[k].tobytes(), 'Unmoved authority changed: ' + k)
    P0 = parent.array('literalNativeArchive', 'positions'); N0 = parent.array('literalNativeArchive', 'normals')
    require(P0.tobytes() == S['positions'].tobytes() and N0.tobytes() == S['normals'].tobytes(), 'Parent archive differs from verified parent authority')
    q = op['parameters']; mode = maps.AUTHORITY[kind]; flat = lambda X: X.reshape(-1, X.shape[-1])
    dense = 'tangents' in S and 'tangentTriangleIds' not in S
    P = maps.apply(kind, P0, q); N, T = maps.transform(kind, flat(P0), flat(N0), flat(S['tangents']) if dense else None, q); N = N.reshape(N0.shape)
    if 'tangents' in S and not dense:
        ti = S['tangentTriangleIds']; T = maps.transform_tangents(kind, P0[ti], S['tangents'], N[ti], q)
    elif dense:
        T = T.reshape(S['tangents'].shape)
    tol = {'literal-f32-decoded-glb': (2e-7, 2e-6), 'native-f64': (1e-12, 1e-9)}[mode]
    for k in ('positions', 'normals'):
        require(A[k].dtype == np.float64 and A[k].shape == S[k].shape, 'Archive dtype/shape changed: ' + k)
    if mode == 'literal-f32-decoded-glb':
        for k in ('positions', 'normals'):
            require(np.array_equal(A[k].astype(np.float32).astype(np.float64), A[k]), 'Archive must be literal f32-decoded f64: ' + k)
    dp = float(np.abs(A['positions'] - P).max()); dn = float(np.abs(A['normals'] - N).max())
    require(dp <= tol[0] and dn <= tol[1], 'Analytic replay differs: positions %.3g normals %.3g' % (dp, dn))
    report = {'operation': kind, 'authority': mode, 'maxPositionReplayError': dp, 'maxNormalReplayError': dn}
    if 'tangents' in S:
        require(A['tangents'].shape == T.shape and np.array_equal(A['tangents'][..., 3], S['tangents'][..., 3]), 'Tangent handedness changed')
        dt = float(np.abs(A['tangents'] - T).max()); require(dt <= tol[1], 'Tangent replay differs: %.3g' % dt); report['maxTangentReplayError'] = dt
    fn = lambda X: np.cross(X[:, 1] - X[:, 0], X[:, 2] - X[:, 0])
    require(int((np.einsum('ij,ij->i', fn(P0), fn(A['positions'])) <= 0).sum()) == 0, 'Face orientation flips')
    require(np.linalg.norm(fn(A['positions']), axis=-1).min() > 0, 'Degenerate face')
    # Serialized candidate: same UVs/indices/images; moved attributes in place or appended after the parent bytes.
    pdoc, pbin, praw = decode(parent_candidate[0]); doc, binary, actual = decode(c['final']['candidate']['path'])
    require(actual['uvNative'].tobytes() == praw['uvNative'].tobytes(), 'Candidate UVs changed')
    require(base.embedded_maps(doc, binary) == base.embedded_maps(pdoc, pbin), 'Candidate images changed')
    if mode == 'literal-f32-decoded-glb':
        for k in ('positions', 'normals', 'uvNative'):
            require(actual[k].tobytes() == A[k].tobytes(), 'Candidate decode differs from archive: ' + k)
    else:
        gp = maps.apply(kind, praw['positions'], q); gn = maps.transform_normals(kind, flat(praw['positions']), flat(praw['normals']), q).reshape(gp.shape)
        report['maxGlbPositionReplayError'] = float(np.abs(actual['positions'] - gp).max()); report['maxGlbNormalReplayError'] = float(np.abs(actual['normals'] - gn).max())
        require(report['maxGlbPositionReplayError'] <= 2e-7 and report['maxGlbNormalReplayError'] <= 2e-6, 'Candidate GLB replay differs')
    strip = lambda d: {**d, 'accessors': None, 'bufferViews': None, 'buffers': None, 'meshes': [{**m, 'primitives': [{**pr, 'attributes': {k: v for k, v in pr['attributes'].items() if k not in ('POSITION', 'NORMAL', 'TANGENT')}} for pr in m['primitives']]} for m in d['meshes']]}
    require(strip(doc) == strip(pdoc), 'Candidate document changed beyond moved attributes')
    if len(binary) == len(pbin):
        mask = np.zeros(len(binary), bool)
        for a, b in moved_ranges(doc):
            mask[a:b] = True
        require(moved_ranges(doc) == moved_ranges(pdoc) and np.array_equal(np.frombuffer(pbin, np.uint8)[~mask], np.frombuffer(binary, np.uint8)[~mask]), 'Unmoved candidate bytes changed')
    else:
        require(binary[:len(pbin)] == pbin and doc['accessors'][:len(pdoc['accessors'])] == pdoc['accessors'] and doc['bufferViews'][:len(pdoc['bufferViews'])] == pdoc['bufferViews'], 'Appended candidate must keep the parent buffer prefix')
    arrays = {**{('literalNativeArchive', k): v for k, v in A.items()}, **{('serializedGlbF32', k): v for k, v in actual.items()}}
    frozen = MappingProxyType({k: (v.dtype.str, v.shape, v.tobytes()) for k, v in arrays.items()})
    physical = tuple(sorted(declared.items())) + ((cp, ch),)
    result = base.DiagnosticRepresentation(base._SEAL, (target['id'], part), physical, frozen, (base.checked_pin(c['final']['geometry']), base.checked_pin(c['final']['candidate'])))
    return result.verify(), MappingProxyType(report)
