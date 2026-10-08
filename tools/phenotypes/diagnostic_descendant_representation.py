"""Verify the explicit measured chest cut/cap operator and its three authorities.
No historical Python code is imported. Unsupported descendant chains fail closed.
"""
from pathlib import Path
from dataclasses import dataclass
from types import MappingProxyType
import json, hashlib, struct, sys, re
import numpy as np
from PIL import Image

class RepresentationError(ValueError):
    pass

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def strict_json(p):

    def pairs(rows):
        d = {}
        for k, v in rows:
            if k in d:
                raise RepresentationError('Duplicate JSON key: ' + k)
            d[k] = v
        return d
    return json.loads(Path(p).read_text(encoding='utf-8'), object_pairs_hook=pairs)

def keys(d, expected):
    if not isinstance(d, dict) or set(d) != set(expected):
        raise RepresentationError('Unexpected schema keys')

def checked_pin(p):
    keys(p, ('path', 'sha256'))
    if not isinstance(p['sha256'], str) or re.fullmatch('[0-9a-f]{64}', p['sha256']) is None:
        raise RepresentationError('Invalid hash')
    if not isinstance(p['path'], str) or not Path(p['path']).is_absolute() or (not Path(p['path']).is_file()):
        raise RepresentationError('Invalid physical path')
    q = str(Path(p['path']).resolve())
    if sha(q) != p['sha256']:
        raise RepresentationError('Stale physical input: ' + q)
    return (q, p['sha256'])

def read_glb(path):
    b = Path(path).read_bytes()
    if len(b) < 12 or b[:4] != b'glTF' or struct.unpack_from('<II', b, 4) != (2, len(b)):
        raise RepresentationError('Invalid GLB')
    offset = 12
    doc = None
    binpart = None
    chunks = []
    while offset < len(b):
        if offset + 8 > len(b):
            raise RepresentationError('Truncated chunk header')
        n, t = struct.unpack_from('<II', b, offset)
        offset += 8
        data = b[offset:offset + n]
        offset += n
        if n % 4 or offset > len(b):
            raise RepresentationError('Malformed chunk extent')
        chunks.append(t)
        if t == 1313821514:
            doc = json.loads(data)
        elif t == 5130562:
            binpart = data
        else:
            raise RepresentationError('Unknown GLB chunk')
    if chunks != [1313821514, 5130562]:
        raise RepresentationError('Unexpected chunk inventory')
    if doc is None or binpart is None:
        raise RepresentationError('Incomplete GLB')
    validate_document(doc, binpart)
    return (doc, binpart)

def validate_document(doc, binpart):
    if len(doc.get('meshes', [])) != 1:
        raise RepresentationError('Exactly one detached mesh required')
    nodes = doc.get('nodes', [])
    if len(nodes) != 1 or set(nodes[0]) - {'mesh', 'name'} or nodes[0].get('mesh') != 0:
        raise RepresentationError('Unexpected scene actor or node transform')
    if doc.get('scene', 0) != 0 or doc.get('scenes') != [{'nodes': [0]}]:
        raise RepresentationError('Unexpected scene graph')
    if any((k in doc for k in ['skins', 'animations', 'extensionsRequired'])):
        raise RepresentationError('Unsupported rig/extension payload')
    buffers = doc.get('buffers', [])
    if len(buffers) != 1 or set(buffers[0]) != {'byteLength'} or (not isinstance(buffers[0]['byteLength'], int)) or (not 0 <= len(binpart) - buffers[0]['byteLength'] <= 3):
        raise RepresentationError('Unexpected buffer')
    mesh = doc['meshes'][0]
    if set(mesh) - {'name', 'primitives'} or not mesh.get('primitives'):
        raise RepresentationError('Unsupported mesh fields')
    for p in mesh['primitives']:
        if set(p) - {'attributes', 'indices', 'material', 'mode'} or p.get('mode', 4) != 4:
            raise RepresentationError('Unsupported primitive mode/fields')
        at = p['attributes']
        if set(at) - {'POSITION', 'NORMAL', 'TEXCOORD_0', 'TANGENT'} or not {'POSITION', 'NORMAL', 'TEXCOORD_0'} <= set(at):
            raise RepresentationError('Unsupported vertex attributes')

def accessor(doc, b, index):
    a = doc['accessors'][index]
    if 'sparse' in a:
        raise RepresentationError('Sparse accessor unsupported')
    v = doc['bufferViews'][a['bufferView']]
    if v.get('buffer', 0) != 0:
        raise RepresentationError('External buffer unsupported')
    dtype = {5126: '<f4', 5125: '<u4', 5123: '<u2', 5121: 'u1'}.get(a['componentType'])
    dim = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4}.get(a['type'])
    if dtype is None or dim is None:
        raise RepresentationError('Accessor type unsupported')
    item = np.dtype(dtype).itemsize
    off = v.get('byteOffset', 0) + a.get('byteOffset', 0)
    stride = v.get('byteStride', item * dim)
    if not isinstance(a['count'], int) or a['count'] <= 0 or stride < item * dim or (off < 0) or (off + (a['count'] - 1) * stride + item * dim > v.get('byteOffset', 0) + v['byteLength']) or (off + (a['count'] - 1) * stride + item * dim > len(b)):
        raise RepresentationError('Accessor outside physical buffer view')
    return np.ndarray((a['count'], dim), dtype=dtype, buffer=b, offset=off, strides=(stride, item)).copy()

def embedded_maps(doc, b):
    result = []
    for im in doc.get('images', []):
        if 'bufferView' not in im:
            raise RepresentationError('External images unsupported')
        v = doc['bufferViews'][im['bufferView']]
        o = v.get('byteOffset', 0)
        result.append(b[o:o + v['byteLength']])
    return result
_SEAL = object()

@dataclass(frozen=True)
class DiagnosticRepresentation:
    _seal: object
    _identity: tuple
    _physical: tuple
    _arrays: object
    _geometry: tuple

    def verify(self):
        if self._seal is not _SEAL:
            raise RepresentationError('Unsealed representation')
        for p, h in self._physical:
            if sha(p) != h:
                raise RepresentationError('Stale closing input: ' + p)
        return self

    @property
    def physical_inputs(self):
        return tuple(({'path': p, 'sha256': h} for p, h in self._physical))

    def array(self, authority, attribute):
        self.verify()
        try:
            dtype, shape, data = self._arrays[authority, attribute]
        except KeyError:
            raise RepresentationError('Undeclared authority/attribute')
        return np.frombuffer(data, dtype=dtype).reshape(shape)

    def geometry_proof(self, receipt, candidate, owner, space):
        self.verify()
        if owner != self._identity[1] or space != 'working':
            raise RepresentationError('Wrong geometry context')
        if checked_pin(receipt) != self._geometry[0] or checked_pin(candidate) != self._geometry[1]:
            raise RepresentationError('Wrong geometry pins')
        return MappingProxyType({'kind': 'verified-diagnostic-geometry', 'part': owner, 'coordinateSpace': space, 'statureApplications': 0, 'runtimeSupported': False})

def _prepare_chest_representation(contract_pin, *, target_path, target, part, space='working'):
    if sys.flags.optimize:
        raise RepresentationError('Optimized assertion removal forbidden')
    cp, ch = checked_pin(contract_pin)
    c = strict_json(cp)
    keys(c, ('kind', 'schemaVersion', 'target', 'part', 'space', 'stockReference', 'baseline', 'operations', 'final', 'consumers', 'physicalInputs'))
    if c['kind'] != 'diagnostic-descendant-representation' or type(c['schemaVersion']) is not int or c['schemaVersion'] != 1:
        raise RepresentationError('Unknown contract')
    if c['part'] != part or c['space'] != space or space != 'working':
        raise RepresentationError('Cross owner/space')
    tp, th = checked_pin(c['target'])
    if Path(target_path).resolve() != Path(tp) or strict_json(tp) != target:
        raise RepresentationError('Cross target')
    if target['rig']['mode'] != 'stock-exact' or target['rig']['runtimeScale'] != 1:
        raise RepresentationError('Rig unsupported')
    if checked_pin(c['stockReference']) != checked_pin(target['rig']['stockReferenceReceipt']):
        raise RepresentationError('Wrong stock receipt')
    if part != 'chest':
        raise RepresentationError('Thigh full ancestral operators not yet implemented')
    keys(c['baseline'], ('kind', 'candidate', 'geometry', 'nativeCorners'))
    if c['baseline']['kind'] != 'literal-working-glb-decoded-f32-baseline-v1':
        raise RepresentationError('Unsupported baseline')
    if len(c['operations']) != 1:
        raise RepresentationError('Skipped or unsupported chain')
    op = c['operations'][0]
    keys(op, ('kind', 'parent', 'packet', 'fixturePolicy'))
    if op['kind'] != 'bilateral-pure-skin-lateral-trim-cap-v1':
        raise RepresentationError('Unsupported operator')
    if op['fixturePolicy'] != {'cutAbsXMeters': 0.155, 'depthMeters': 0.012, 'latitudes': 8, 'leftBoundaryCount': 70, 'rightBoundaryCount': 65, 'retainedWholeFaceCount': 44756, 'generatedFaceCount': 2025, 'protectedMixedFaceId': 44950}:
        raise RepresentationError('Unsupported actual-fixture policy')
    if op['parent'] != c['baseline']['geometry']:
        raise RepresentationError('Wrong parent')
    keys(c['final'], ('candidate', 'geometry', 'nativeCorners', 'proof', 'encodedNativeLineage'))
    declared = {}
    for p in c['physicalInputs']:
        q, h = checked_pin(p)
        if q in declared:
            raise RepresentationError('Duplicate physical path')
        declared[q] = h
    if len(c['consumers']) != 1:
        raise RepresentationError('Exact consumer whitelist required')
    for p in c['consumers']:
        q, h = checked_pin(p)
        if declared.get(q) != h:
            raise RepresentationError('Undeclared consumer')
    if checked_pin({'path': __file__, 'sha256': sha(__file__)}) not in [checked_pin(p) for p in c['consumers']]:
        raise RepresentationError('Current consumer absent')
    for p in [c['target'], c['stockReference'], *c['baseline'].values(), *c['final'].values(), op['packet']]:
        if isinstance(p, dict):
            q, h = checked_pin(p)
            if declared.get(q) != h:
                raise RepresentationError('Undeclared contract input')
    packet = strict_json(checked_pin(op['packet'])[0])
    if packet['overrides']['chest'] != c['final']:
        raise RepresentationError('Wrong final packet')
    final = c['final']
    g = strict_json(final['geometry']['path'])
    sg = strict_json(c['baseline']['geometry']['path'])
    if c['baseline']['nativeCorners'] != sg['nativeCornerArchive'] or checked_pin(c['baseline']['candidate']) != checked_pin({'path': g['source'], 'sha256': g['sourceSha256']}):
        raise RepresentationError('Baseline physical authority mismatch')
    proofdoc = strict_json(final['proof']['path'])
    finite = [packet, g, proofdoc, strict_json(proofdoc['sourceCutloopProposal']['path']), strict_json(proofdoc['skinPatch']['path'])]
    reachable = set()

    def references(v):
        if isinstance(v, dict):
            if 'path' in v and 'sha256' in v:
                reachable.add(str(Path(v['path']).resolve()))
            for k, x in v.items():
                if k == 'frozenInputs' and isinstance(x, dict):
                    reachable.update((str(Path(p).resolve()) for p in x))
                else:
                    references(x)
        elif isinstance(v, list):
            for x in v:
                references(x)
        elif isinstance(v, str) and Path(v).is_absolute():
            q = str(Path(v).resolve())
            if q in declared:
                reachable.add(q)
    for d in finite:
        references(d)
    for p in [c['target'], c['stockReference'], *c['baseline'].values(), *c['final'].values(), op['packet'], *c['consumers']]:
        if isinstance(p, dict):
            reachable.add(str(Path(p['path']).resolve()))
    if set(declared) != reachable:
        raise RepresentationError('Unreachable or missing physical input')
    if g['sourceReceipt'] != c['baseline']['geometry']['path'] or g['sourceReceiptSha256'] != c['baseline']['geometry']['sha256'] or g['sourceSha256'] != c['baseline']['candidate']['sha256']:
        raise RepresentationError('Parent mismatch')
    if g['targetId'] != target['id'] or g['targetContractSha256'] != th or g['model'] != target['models'][part] or (g['rigRevision'] != target['rig']['revision']):
        raise RepresentationError('Geometry identity mismatch')
    try:
        arrays = _verify_chest(packet, declared)
    except (AssertionError, KeyError, ValueError) as e:
        raise RepresentationError('Independent chest replay rejected: ' + str(e)) from e
    frozen = MappingProxyType({k: (v.dtype.str, v.shape, v.tobytes()) for k, v in arrays.items()})
    physical = tuple(sorted(declared.items())) + ((cp, ch),)
    result = DiagnosticRepresentation(_SEAL, (target['id'], part), physical, frozen, (checked_pin(final['geometry']), checked_pin(final['candidate'])))
    return result.verify()

def _verify_chest(packet, declared):
    c = packet['overrides']['chest']
    proof = strict_json(c['proof']['path'])
    g = strict_json(c['geometry']['path'])
    sg = strict_json(g['sourceReceipt'])
    S = dict(np.load(sg['nativeCornerArchive']['path'], allow_pickle=False))
    A = dict(np.load(c['nativeCorners']['path'], allow_pickle=False))
    L = dict(np.load(c['encodedNativeLineage']['path'], allow_pickle=False))
    owned = {}

    def verify(v):
        if isinstance(v, dict):
            if 'path' in v and 'sha256' in v:
                if not sha(v['path']) == v['sha256']:
                    raise RepresentationError('Chest replay invariant at original line 175')
                owned[v['path']] = v['sha256']
            for x in v.values():
                verify(x)
        elif isinstance(v, list):
            for x in v:
                verify(x)
    for v in [packet, proof]:
        verify(v)
    for p, h in g['frozenInputs'].items():
        if not sha(p) == h:
            raise RepresentationError('Chest replay invariant at original line 180')
        owned[p] = h
    if not (g['sourceSha256'] == sha(g['source']) and g['sourceReceiptSha256'] == sha(g['sourceReceipt'])):
        raise RepresentationError('Chest replay invariant at original line 181')
    if not (g['coordinateSpace'] == 'working' and g['statureApplications'] == 0 and (g['part'] == 'chest')):
        raise RepresentationError('Chest replay invariant at original line 181')
    for k in ['targetContract', 'targetContractSha256', 'targetId', 'rigRevision', 'joint', 'model', 'attachmentWorld']:
        if not g[k] == sg[k]:
            raise RepresentationError('Chest replay invariant at original line 182')

    def nwn(v):
        return np.stack((v[..., 0], -v[..., 2], v[..., 1]), axis=-1)

    def decode(path):
        doc, b = read_glb(path)
        rows = {k: [] for k in ['positions', 'normals', 'uvGltf', 'uvNative']}
        Ts = []
        capTids = []
        offset = 0
        for p in doc['meshes'][0]['primitives']:
            i = accessor(doc, b, p['indices']).reshape(-1, 3).astype(int)
            at = p['attributes']
            u = accessor(doc, b, at['TEXCOORD_0'])[i].astype(float)
            rows['positions'].append(nwn(accessor(doc, b, at['POSITION'])[i].astype(float)))
            rows['normals'].append(nwn(accessor(doc, b, at['NORMAL'])[i].astype(float)))
            rows['uvGltf'].append(u)
            rows['uvNative'].append(np.stack((u[..., 0], 1 - u[..., 1]), axis=-1))
            if 'TANGENT' in at:
                t = accessor(doc, b, at['TANGENT'])[i].astype(float)
                t[..., :3] = nwn(t[..., :3])
                Ts.append(t)
                capTids.extend(range(offset, offset + len(i)))
            offset += len(i)
        return (doc, b, {k: np.concatenate(v) for k, v in rows.items()}, np.concatenate(Ts) if Ts else None, np.asarray(capTids))
    sdoc, sbin, raw, _, _ = decode(g['source'])
    doc, binary, actual, T, Tids = decode(c['candidate']['path'])
    for k in raw:
        if not raw[k].tobytes() == S[k].tobytes():
            raise RepresentationError(str(k))
    for k in actual:
        if not actual[k].tobytes() == A[k].tobytes():
            raise RepresentationError(str(k))
    if not (T.tobytes() == A['tangents'].astype(float).tobytes() and np.array_equal(Tids, A['tangentTriangleIds'])):
        raise RepresentationError('Chest replay invariant at original line 195')
    if not 'TANGENT' not in doc['meshes'][0]['primitives'][0]['attributes']:
        raise RepresentationError('Chest replay invariant at original line 195')
    if not (binary[:len(sbin)] == sbin and embedded_maps(doc, binary) == embedded_maps(sdoc, sbin)):
        raise RepresentationError('Chest replay invariant at original line 196')
    if not doc['materials'][:len(sdoc['materials'])] == sdoc['materials']:
        raise RepresentationError('Chest replay invariant at original line 196')
    capmat = doc['materials'][-1].copy()
    capmat.pop('name', None)
    oldmat = sdoc['materials'][0].copy()
    oldmat.pop('name', None)
    if not capmat == oldmat:
        raise RepresentationError('Chest replay invariant at original line 196')
    for k in ['textures', 'images', 'samplers', 'nodes', 'scenes', 'scene']:
        if not doc.get(k) == sdoc.get(k):
            raise RepresentationError(str(k))
    caps = L['generatedCapFaceIds']
    start = int(caps[0])
    parents = L['directParentFaceIds'][:start]
    bary = L['sourceCutBarycentricWeights']
    if not (len(bary) == start and np.array_equal(caps, np.arange(start, len(A['positions']))) and (L['directParentFaceIds'][start:] == -1).all()):
        raise RepresentationError('Chest replay invariant at original line 198')
    whole = np.all(bary == np.eye(3), axis=(1, 2))
    if not np.array_equal(np.flatnonzero(whole), L['retainedOutputFaceIds']):
        raise RepresentationError('Chest replay invariant at original line 198')
    if not (whole.sum() == 44756 and len(caps) == 2025):
        raise RepresentationError('Chest replay invariant at original line 198')
    if not (np.max(abs(bary.sum(2) - 1)) < 2e-15 and bary.min() >= 0 and (bary.max() <= 1)):
        raise RepresentationError('Chest replay invariant at original line 199')
    for k in raw:
        x = np.einsum('fij,fjk->fik', bary, raw[k][parents])
        x[whole] = raw[k][parents[whole]]
        if k == 'positions':
            if not np.array_equal(x, L['sourceNativeBaryPositionsBeforeCanonical']):
                raise RepresentationError('Chest replay invariant at original line 202')
            x = x + L['newSplitCanonicalPositionDeltas']
        if not np.max(abs(x - L['encoded_' + k][:start])) < 2e-15:
            raise RepresentationError(str((k, 'bary replay')))
        if not L['encoded_' + k][:start][whole].tobytes() == raw[k][parents[whole]].tobytes():
            raise RepresentationError('Chest replay invariant at original line 204')
        if not A[k][:start][whole].tobytes() == raw[k][parents[whole]].tobytes():
            raise RepresentationError(str(('protected', k)))
    if not ((L['newSplitCanonicalPositionDeltas'][whole] == 0).all() and abs(L['newSplitCanonicalPositionDeltas']).max() <= 5.551115123125783e-17):
        raise RepresentationError('Chest replay invariant at original line 205')
    cut = json.loads(Path(proof['sourceCutloopProposal']['path']).read_text())
    CA = dict(np.load(cut['sourceArchive']['path']))
    affected = np.unique(np.concatenate([CA[x + '_155_crossedSourceFaces'] for x in ['left', 'right']] + [CA[x + '_155_removedWholeSourceFaces'] for x in ['left', 'right']]))
    if not np.array_equal(affected, L['sourceAffectedFaceIds']):
        raise RepresentationError('Chest replay invariant at original line 206')
    if not np.array_equal(parents[~whole], np.sort(parents[~whole])):
        raise RepresentationError('Chest replay invariant at original line 206')
    if not np.array_equal(np.unique(parents[whole]), np.setdiff1d(np.arange(len(S['positions'])), affected)):
        raise RepresentationError('Chest replay invariant at original line 206')
    if not (np.array_equal(L['protectedMixedFace44950OutputRows'], np.flatnonzero(parents == 44950)) and len(np.flatnonzero(parents == 44950)) == 1 and whole[parents == 44950].all()):
        raise RepresentationError('Chest replay invariant at original line 207')
    if not np.array_equal(L['sourceOwnershipCodes'], CA['faceRoleCodes'][parents]):
        raise RepresentationError('Chest replay invariant at original line 207')
    if not ((CA['faceRoleCodes'][affected] == 0).all() and (CA['filterPixelCounts'][affected, 1:] == 0).all() and (CA['strictInteriorPixelCounts'][affected, 1:] == 0).all()):
        raise RepresentationError('Chest replay invariant at original line 208')
    if not (np.array_equal(A['sourceFaceIds'][:start], S['sourceFaceIds'][parents]) and (A['sourceFaceIds'][start:] == -1).all()):
        raise RepresentationError('Chest replay invariant at original line 208')
    for k in actual:
        exp = L['encoded_' + k].astype(np.float32).astype(float) if k != 'uvNative' else np.stack((L['encoded_uvGltf'].astype(np.float32).astype(float)[..., 0], 1 - L['encoded_uvGltf'].astype(np.float32).astype(float)[..., 1]), axis=-1)
        if not actual[k].tobytes() == exp.tobytes():
            raise RepresentationError(str(('serialization', k)))
    if not T.tobytes() == L['encoded_generatedTangents'].astype(np.float32).astype(float).tobytes():
        raise RepresentationError('Chest replay invariant at original line 212')

    def edge_inventory(P):
        verts, ids = np.unique(P.reshape(-1, 3), axis=0, return_inverse=True)
        ids = ids.reshape(-1, 3)
        edges = np.concatenate([ids[:, [0, 1]], ids[:, [1, 2]], ids[:, [2, 0]]])
        sgn = np.where(edges[:, 0] < edges[:, 1], 1, -1)
        e, iv, count = np.unique(np.sort(edges, axis=1), axis=0, return_inverse=True, return_counts=True)
        direction = np.bincount(iv, weights=sgn)
        if not ((count == 2).all() and (direction == 0).all()):
            raise RepresentationError('Chest replay invariant at original line 214')
        return len(e)
    closure = {k: edge_inventory(P) for k, P in [('nativeDecodedF32', A['positions']), ('literalSerializedGLB', actual['positions']), ('generatedConstruction', L['encoded_positions'])]}
    patch = json.loads(Path(proof['skinPatch']['path']).read_text())
    mask = np.asarray(Image.open(patch['sourceMask']['path']))
    gr = np.array(patch['guardPixelRectXY'])
    ur = np.asarray(patch['centralChartUvRect'])
    if not (mask[gr[1]:gr[3], gr[0]:gr[2]] == 0).all():
        raise RepresentationError('Chest replay invariant at original line 216')
    if not np.array_equal(np.asarray(patch['centralChartPixelRectXY']), np.array([1284, 1292, 1292, 1300])):
        raise RepresentationError('Chest replay invariant at original line 216')
    scale = ur[2:] - ur[:2]
    if not ((scale > 0).all() and scale[0] == scale[1]):
        raise RepresentationError('Chest replay invariant at original line 216')
    capresults = []
    capoffset = start
    Tgenerated = []
    for cp in proof['caps']:
        side = cp['side']
        sign = cp['sign']
        n = cp['boundaryCount']
        br = L[side + '_sourceRetainedBoundaryRows']
        boundary = L['encoded_positions'][br[:, 0], br[:, 1]]
        axis = L[side + '_sourceAxisBoundary']
        if not np.array_equal(axis, boundary[:, [1, 2, 0]]):
            raise RepresentationError('Chest replay invariant at original line 219')
        if not (n == {'left': 70, 'right': 65}[side] and cp['depthMeters'] == 0.012 and (cp['latitudeCount'] == 8)):
            raise RepresentationError('Chest replay invariant at original line 219')
        C = np.column_stack((boundary[:, 1], boundary[:, 2])).mean(0)
        delta = boundary[:, [1, 2]] - C
        angles = np.linspace(0, np.pi / 2, 9)[:-1]
        nodes = np.vstack([np.stack((np.full(n, boundary[0, 0] + sign * 0.012 * np.sin(t)), C[0] + delta[:, 0] * np.cos(t), C[1] + delta[:, 1] * np.cos(t)), axis=-1) for t in angles])
        nodes[:n] = boundary
        nodes = np.vstack([nodes, [boundary[0, 0] + sign * 0.012, *C]])
        if not np.max(abs(nodes - L[side + '_nodesNativeConstruction'])) < 2e-15:
            raise RepresentationError('Chest replay invariant at original line 220')
        faces = []
        for r in range(7):
            for j in range(n):
                k = (j + 1) % n
                a = r * n + j
                b = r * n + k
                c = (r + 1) * n + j
                d = (r + 1) * n + k
                faces.extend([[b, a, c], [b, c, d]])
        for j in range(n):
            faces.append([7 * n + (j + 1) % n, 7 * n + j, 8 * n])
        faces = np.asarray(faces)
        if not np.array_equal(faces, L[side + '_faces']):
            raise RepresentationError('Chest replay invariant at original line 226')
        tri = nodes[faces]
        if not np.max(abs(tri - L['encoded_positions'][capoffset:capoffset + len(faces)])) < 2e-15:
            raise RepresentationError('Chest replay invariant at original line 226')
        cross = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
        N = np.zeros_like(nodes)
        for i in range(3):
            np.add.at(N, faces[:, i], cross)
        N /= np.linalg.norm(N, axis=1)[:, None]
        if not np.max(abs(N - L[side + '_originalGeometricNodeNormals'])) < 2e-15:
            raise RepresentationError('Chest replay invariant at original line 229')
        seam = L['encoded_normals'][br[:, 0], br[:, 1]].copy()
        seam /= np.linalg.norm(seam, axis=1)[:, None]
        geomN = N.copy()
        N[:n] = seam
        for r, w in [(1, 0.5), (2, 0.15)]:
            z = w * seam + (1 - w) * geomN[r * n:(r + 1) * n]
            z /= np.linalg.norm(z, axis=1)[:, None]
            N[r * n:(r + 1) * n] = z
        N /= np.linalg.norm(N, axis=1)[:, None]
        if not (np.max(abs(N - L[side + '_generatedNodeNormals'])) < 2e-15 and np.max(abs(N[faces] - L['encoded_normals'][capoffset:capoffset + len(faces)])) < 2e-15):
            raise RepresentationError('Chest replay invariant at original line 234')
        radius = np.linalg.norm(delta, axis=1).max()
        u = (nodes[:, [1, 2]] - C) / (2 * radius) + 0.5
        u = np.clip(u, 0, 1)
        uv = u[faces] * scale + ur[:2]
        if not np.max(abs(uv - L['encoded_uvGltf'][capoffset:capoffset + len(faces)])) < 2e-15:
            raise RepresentationError('Chest replay invariant at original line 235')
        dp1 = tri[:, 1] - tri[:, 0]
        dp2 = tri[:, 2] - tri[:, 0]
        du1 = u[faces][:, 1] - u[faces][:, 0]
        du2 = u[faces][:, 2] - u[faces][:, 0]
        den = du1[:, 0] * du2[:, 1] - du1[:, 1] * du2[:, 0]
        if not np.all(abs(den) > 1e-14):
            raise RepresentationError('Chest replay invariant at original line 237')
        baseT = (dp1 * du2[:, 1, None] - dp2 * du1[:, 1, None]) / den[:, None]
        baseB = (-dp1 * du2[:, 0, None] + dp2 * du1[:, 0, None]) / den[:, None]
        gn = geomN[faces]
        t = np.broadcast_to(baseT[:, None], gn.shape).copy()
        t -= gn * np.sum(gn * t, axis=2)[..., None]
        t /= np.linalg.norm(t, axis=2)[..., None]
        hand = np.where(np.sum(np.cross(gn, t) * baseB[:, None], axis=2) >= 0, 1.0, -1.0)
        nn = N[faces]
        t -= nn * np.sum(nn * t, axis=2)[..., None]
        t /= np.linalg.norm(t, axis=2)[..., None]
        expectedT = np.concatenate([t, hand[..., None]], axis=-1)
        if not np.max(abs(expectedT - L['encoded_generatedTangents'][capoffset - start:capoffset - start + len(faces)])) < 2e-15:
            raise RepresentationError('Chest replay invariant at original line 237')
        polar = np.unwrap(np.arctan2(delta[:, 1], delta[:, 0]))
        steps = np.diff(np.r_[polar, polar[0] + np.sign(np.median(np.diff(polar))) * 2 * np.pi])
        if not ((steps * np.sign(np.median(steps)) > 0).all() and abs(steps.sum()) > 6.28):
            raise RepresentationError('Chest replay invariant at original line 239')
        if not (den * np.sign(den[0]) > 0).all():
            raise RepresentationError('Chest replay invariant at original line 239')
        fan = delta[:, 0] * np.roll(delta[:, 1], -1) - delta[:, 1] * np.roll(delta[:, 0], -1)
        if not (fan * np.sign(fan[0]) > 0).all():
            raise RepresentationError('Chest replay invariant at original line 239')
        if not (sign * tri[:, :, 0] >= 0.155).all():
            raise RepresentationError('Chest replay invariant at original line 239')
        if not ((L['encoded_positions'][:start, :, 0] >= -0.155).all() and (L['encoded_positions'][:start, :, 0] <= 0.155).all()):
            raise RepresentationError('Chest replay invariant at original line 239')
        actualuv = A['uvGltf'][capoffset:capoffset + len(faces)] * 2048
        minimum = float(np.minimum(actualuv - gr[:2], gr[2:] - actualuv).min())
        if not minimum >= 4:
            raise RepresentationError('Chest replay invariant at original line 240')
        if not np.max(abs(np.linalg.norm(nn, axis=-1) - 1)) < 1e-12:
            raise RepresentationError('Chest replay invariant at original line 240')
        if not np.max(abs(np.sum(nn * t, axis=-1))) < 1e-12:
            raise RepresentationError('Chest replay invariant at original line 240')
        capresults.append({'side': side, 'boundaryVertices': n, 'generatedFaces': len(faces), 'depthMeters': 0.012, 'latitudes': 8, 'minimumOriginalSkinGuardPixels': minimum, 'normalBlendIndependentReplay': True, 'tangentChartHandednessIndependentReplay': True, 'noNewCapCrossingHalfspaceAndStarProjectionProof': True})
        capoffset += len(faces)
    if not capoffset == len(A['positions']):
        raise RepresentationError('Chest replay invariant at original line 242')
    if not np.linalg.norm(np.cross(A['positions'][:, 1] - A['positions'][:, 0], A['positions'][:, 2] - A['positions'][:, 0]), axis=-1).min() > 0:
        raise RepresentationError('Chest replay invariant at original line 242')
    for p, h in owned.items():
        if not sha(p) == h:
            raise RepresentationError('Chest replay invariant at original line 244')
        if not (str(Path(p).resolve()) in declared and declared[str(Path(p).resolve())] == h):
            raise RepresentationError(str(('undeclared physical input', p)))
    return {**{('serializedGlbF32', k): v for k, v in actual.items()}, **{('literalNativeArchive', k): v for k, v in A.items()}, **{('constructionF64', k[8:]): v for k, v in L.items() if k.startswith('encoded_')}}

def prepare_diagnostic_representation(contract_pin, *, target_path, target, part, space='working', baseline_context=None):
    if sys.flags.optimize:
        raise RepresentationError('Optimized assertion removal forbidden')
    try:
        cp, _ = checked_pin(contract_pin)
        c = strict_json(cp)
        if not isinstance(c, dict) or type(c.get('schemaVersion')) is not int or c['schemaVersion'] != 1:
            raise RepresentationError('Unknown contract')
        if c.get('kind') == 'diagnostic-shin-descendant-representation':
            from diagnostic_shin_representation import prepare_shin_representation
            context, _ = prepare_shin_representation(contract_pin, target_path=target_path, target=target, part=part, space=space, baseline_context=baseline_context)
            return context
        if c.get('kind') == 'diagnostic-elbow-descendant-representation':
            from diagnostic_elbow_representation import prepare_elbow_representation
            context, _ = prepare_elbow_representation(contract_pin, target_path=target_path, target=target, part=part, space=space, baseline_context=baseline_context)
            return context
        if c.get('kind') == 'diagnostic-thigh-descendant-representation':
            from diagnostic_thigh_representation import prepare_thigh_representation
            context, _ = prepare_thigh_representation(contract_pin, target_path=target_path, target=target, part=part, space=space, baseline_context=baseline_context)
            return context
        if baseline_context is not None:
            raise RepresentationError('Original baseline context is only supported for the explicit thigh contract')
        return _prepare_chest_representation(contract_pin, target_path=target_path, target=target, part=part, space=space)
    except RepresentationError:
        raise
    except (KeyError, TypeError, ValueError, IndexError, OSError, AttributeError) as error:
        raise RepresentationError('Malformed diagnostic representation input: ' + str(error)) from error
