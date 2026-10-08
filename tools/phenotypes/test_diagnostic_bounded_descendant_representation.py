"""Bounded descendant representation: synthetic end-to-end verification and tamper cases (fail closed)."""
import hashlib, json, struct, tempfile, unittest
from pathlib import Path
from unittest import mock
import numpy as np
import diagnostic_descendant_representation as base
import diagnostic_bounded_descendant_representation as br
import make_bounded_descendant as mbd
import bounded_descendant_rules as rules
import fair_female_limb_creases as fair
from test_bounded_descendant_rules import tube

sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
pin = lambda p: {'path': str(Path(p).resolve()), 'sha256': sha(p)}


def write_glb(path, P, N, UV, T):
    """One primitive, one GLB vertex per corner, NWN corner arrays converted to glTF."""
    pos = br.to_gltf(P.reshape(-1, 3)).astype('<f4'); nrm = br.to_gltf(N.reshape(-1, 3)).astype('<f4')
    uv = np.stack((UV.reshape(-1, 2)[:, 0], 1 - UV.reshape(-1, 2)[:, 1]), -1).astype('<f4'); t = T.reshape(-1, 4).copy(); t[:, :3] = br.to_gltf(t[:, :3]); t = t.astype('<f4')
    idx = np.arange(len(pos), dtype='<u4'); blobs = [pos, nrm, uv, t, idx]; views, acc, binary = [], [], b''
    for k, a in enumerate(blobs):
        views.append({'buffer': 0, 'byteOffset': len(binary), 'byteLength': a.nbytes}); binary += a.tobytes()
        acc.append({'bufferView': k, 'componentType': 5125 if k == 4 else 5126, 'count': len(a), 'type': ['VEC3', 'VEC3', 'VEC2', 'VEC4', 'SCALAR'][k]})
    acc[0]['min'] = pos.min(0).tolist(); acc[0]['max'] = pos.max(0).tolist()
    doc = {'asset': {'version': '2.0'}, 'scene': 0, 'scenes': [{'nodes': [0]}], 'nodes': [{'mesh': 0}], 'materials': [{}],
           'meshes': [{'primitives': [{'attributes': {'POSITION': 0, 'NORMAL': 1, 'TEXCOORD_0': 2, 'TANGENT': 3}, 'indices': 4, 'material': 0}]}],
           'accessors': acc, 'bufferViews': views, 'buffers': [{'byteLength': len(binary)}]}
    js = json.dumps(doc).encode(); js += b' ' * (-len(js) % 4)
    Path(path).write_bytes(b'glTF' + struct.pack('<II', 2, 28 + len(js) + len(binary)) + struct.pack('<II', len(js), 0x4E4F534A) + js + struct.pack('<II', len(binary), 0x004E4942) + binary)


class BoundedRepresentationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        self.target = {'id': 't', 'rig': {'mode': 'stock-exact', 'runtimeScale': 1}}; self.tp = self.root / 'target.json'; self.tp.write_text(json.dumps(self.target))
        V, F = tube(n_theta=24, n_z=16); self.P = V[F]; self.N = fair.vertex_normals(V, F)[F] * 0.93
        rng = np.random.default_rng(0); self.UV = rng.random(self.P.shape[:2] + (2,))
        T = np.concatenate([np.tile([[0.0, 0.0, 1.0]], self.P.shape[:2] + (1,)), np.ones(self.P.shape[:2] + (1,))], -1)
        self.trows = np.arange(0, len(self.P), 5)
        self.S = {'positions': self.P, 'normals': self.N, 'uvNative': self.UV, 'uvGltf': self.UV * 1.0, 'tangents': T[self.trows], 'tangentTriangleIds': self.trows.astype(np.int64),
                  'sourceFaceIds': np.arange(len(self.P), dtype=np.int64)}
        d = self.root / 'parent'; d.mkdir(); np.savez(d / 'native-corners.npz', **self.S); write_glb(d / 'candidate-local.glb', self.P, self.N, self.UV, T)
        self.parent_receipt = d / 'geometry.json'; ident = {k: 'x' for k in br.IDENTITY}
        ident.update(part='legl', coordinateSpace='working', statureApplications=0)
        self.g0 = {'schemaVersion': 1, 'kind': 'target-part-geometry', **ident, 'candidate': str(d / 'candidate-local.glb'), 'candidateSha256': sha(d / 'candidate-local.glb'),
                   'nativeCornerArchive': pin(d / 'native-corners.npz'), 'generatedCapsUntextured': True}
        self.parent_receipt.write_text(json.dumps(self.g0))
        arrays = {('literalNativeArchive', k): v for k, v in self.S.items()}
        frozen = {k: (v.dtype.str, v.shape, v.tobytes()) for k, v in arrays.items()}
        self.parent = base.DiagnosticRepresentation(base._SEAL, ('t', 'legl'), ((str(self.tp.resolve()), sha(self.tp)),), frozen,
                                                    (base.checked_pin(pin(self.parent_receipt)), base.checked_pin(pin(d / 'candidate-local.glb'))))
        self.parent_rep = self.root / 'parent-rep.json'; self.parent_rep.write_text(json.dumps({'kind': 'diagnostic-thigh-descendant-representation'}))
        z = self.P[..., 2]; self.env = {'regions': [{'axisCentre': [0.0, 0.0], 'thetaCentre': 180.0, 'thetaHalfFull': 60.0, 'thetaHalfZero': 90.0,
                                                    'zFull': [-0.3, -0.1], 'zZero': [-0.35, -0.05], 'weight': 1.0}], 'maximumDisplacement': 0.005}

    def tearDown(self):
        self.tmp.cleanup()

    def op(self, envelope=True):
        return {'kind': br.OPERATION, 'positionEnvelope': self.env if envelope else None, 'normalRule': {'geometricSmoothing': 1, 'smoothingRegions': []},
                'minimumAreaRatio': 0.02, 'generator': {'fairing': None}}

    def child(self, name, P1, op, edit=None):
        d = self.root / name; d.mkdir(); trows, gt = br.glb_tangent_rows(*self._glb_rows()); N1, T1, G1, _ = br.replay(self.P, self.N, P1, op, self.S, gt, trows)
        A = dict(self.S); A['positions'] = P1; A['normals'] = N1; A['tangents'] = T1
        if edit:
            edit(A)
        np.savez(d / 'native-corners.npz', **A)
        prim, vert, _ = br.glb_corners(*base.read_glb(self.g0['candidate']))
        full = np.zeros(self.P.shape[:2] + (4,)); full[:] = np.concatenate([br.to_gltf(G1[..., :3]), G1[..., 3:]], -1)
        mbd.write_glb(self.g0['candidate'], d / 'candidate-local.glb', prim, vert, {'POSITION': br.to_gltf(A['positions']), 'NORMAL': br.to_gltf(A['normals']), 'TANGENT': full})
        g = {k: self.g0[k] for k in ('schemaVersion', 'kind', *br.IDENTITY, 'generatedCapsUntextured')}
        g.update(operation=br.OPERATION, boundedDescendant=op, source=self.g0['candidate'], sourceSha256=self.g0['candidateSha256'], sourceReceipt=str(self.parent_receipt),
                 sourceReceiptSha256=sha(self.parent_receipt), candidate=str(d / 'candidate-local.glb'), candidateSha256=sha(d / 'candidate-local.glb'),
                 nativeCornerArchive=pin(d / 'native-corners.npz'), runtimeSelected=False, nativeAccepted=False, productionAccepted=False)
        (d / 'geometry.json').write_text(json.dumps(g)); return d

    def _glb_rows(self):
        prim, _, raw = br.glb_corners(*base.read_glb(self.g0['candidate'])); return prim, raw['tangents']

    def contract(self, d, op, consumers=None, extra=()):
        final = {'candidate': pin(d / 'candidate-local.glb'), 'geometry': pin(d / 'geometry.json'), 'nativeCorners': pin(d / 'native-corners.npz')}
        consumers = consumers or [pin(m.__file__) for m in (br, rules, fair, base)]
        phys = {p['path']: p['sha256'] for p in self.parent.physical_inputs}
        for x in [pin(self.tp), pin(self.parent_rep), *final.values(), *consumers, *extra]:
            phys[x['path']] = x['sha256']
        c = {'kind': br.KIND, 'schemaVersion': 1, 'target': pin(self.tp), 'part': 'legl', 'space': 'working', 'parentRepresentation': pin(self.parent_rep), 'operation': op,
             'final': final, 'consumers': consumers, 'physicalInputs': [{'path': p, 'sha256': h} for p, h in sorted(phys.items())]}
        p = d / 'contract.json'; p.write_text(json.dumps(c)); return pin(p)

    def verify(self, cpin):
        with mock.patch.object(br, 'parent_context', return_value=self.parent):
            return br.prepare_bounded_representation(cpin, target_path=self.tp, target=self.target, part='legl')

    def moved(self, scale=1.0):
        U, F = fair.weld(self.P); X = U.copy(); w = rules.region_weight(U, self.env['regions']); X[:, :2] *= (1 + 0.03 * scale * w)[:, None]
        return fair.child_corners(self.P, U, X, F)

    def test_identity_renormalisation_verifies(self):
        op = self.op(False); d = self.child('id', self.P.copy(), op); rep, report = self.verify(self.contract(d, op))
        n = rep.array('literalNativeArchive', 'normals'); np.testing.assert_allclose(np.linalg.norm(n, axis=2), 1, atol=1e-12); self.assertEqual(report['movedVertices'], 0)

    def test_bounded_move_verifies(self):
        op = self.op(); d = self.child('mv', self.moved(), op); _, report = self.verify(self.contract(d, op)); self.assertGreater(report['movedVertices'], 0)

    def test_move_outside_envelope_rejected(self):
        op = self.op(); P1 = self.moved(); P1 = P1 * np.array([1.0, 1.0, 1.0]); U, F = fair.weld(self.P)
        front = np.flatnonzero(U[:, 1] > 0.04)[0]; X = U.copy(); X[front, 1] += 1e-3; P1 = fair.child_corners(self.P, U, X, F)
        d = self.child('out', P1, op)
        with self.assertRaisesRegex(base.RepresentationError, 'outside the declared envelope'):
            self.verify(self.contract(d, op))

    def test_displacement_bound_enforced(self):
        op = self.op(); d = self.child('far', self.moved(scale=8.0), op)
        with self.assertRaisesRegex(base.RepresentationError, 'Displacement exceeds'):
            self.verify(self.contract(d, op))

    def test_identity_envelope_with_moved_positions_rejected(self):
        op = self.op(False); d = self.child('idmv', self.moved(), op)
        with self.assertRaisesRegex(base.RepresentationError, 'Identity envelope moved positions'):
            self.verify(self.contract(d, op))

    def test_tampered_normals_rejected(self):
        op = self.op(False); d = self.child('tn', self.P.copy(), op, edit=lambda A: A.__setitem__('normals', A['normals'] * 1.0 + np.array([0, 0, 1e-6])))
        with self.assertRaisesRegex(base.RepresentationError, 'Normal rule replay differs|Candidate decode'):
            self.verify(self.contract(d, op))

    def test_tampered_tangent_handedness_rejected(self):
        def flip(A):
            t = A['tangents'].copy(); t[0, 0, 3] *= -1; A['tangents'] = t
        op = self.op(False); d = self.child('tt', self.P.copy(), op, edit=flip)
        with self.assertRaisesRegex(base.RepresentationError, 'handedness'):
            self.verify(self.contract(d, op))

    def test_uv_change_rejected(self):
        op = self.op(False); d = self.child('uv', self.P.copy(), op, edit=lambda A: A.__setitem__('uvNative', A['uvNative'] + 1e-3))
        with self.assertRaisesRegex(base.RepresentationError, 'Unmoved authority changed: uvNative'):
            self.verify(self.contract(d, op))

    def test_glb_normal_bytes_tampered_rejected(self):
        op = self.op(False); d = self.child('glb', self.P.copy(), op); data = bytearray((d / 'candidate-local.glb').read_bytes())
        doc, b = base.read_glb(d / 'candidate-local.glb'); off = len(data) - len(b) + doc['bufferViews'][1]['byteOffset']; data[off + 3] ^= 1
        (d / 'candidate-local.glb').write_bytes(bytes(data)); g = json.loads((d / 'geometry.json').read_text()); g['candidateSha256'] = sha(d / 'candidate-local.glb')
        (d / 'geometry.json').write_text(json.dumps(g))
        with self.assertRaisesRegex(base.RepresentationError, 'Candidate decode differs'):
            self.verify(self.contract(d, op))

    def test_receipt_operation_mismatch_rejected(self):
        op = self.op(False); d = self.child('rc', self.P.copy(), op); other = dict(op, minimumAreaRatio=0.5)
        with self.assertRaisesRegex(base.RepresentationError, 'Receipt operation differs'):
            self.verify(self.contract(d, other))

    def test_consumer_whitelist_and_closure_enforced(self):
        op = self.op(False); d = self.child('cw', self.P.copy(), op)
        with self.assertRaisesRegex(base.RepresentationError, 'consumer whitelist'):
            self.verify(self.contract(d, op, consumers=[pin(self.tp)] * 4))
        with self.assertRaisesRegex(base.RepresentationError, 'physical input'):
            self.verify(self.contract(d, op, extra=[pin(self.parent_receipt)]))

    def test_split_weld_rejected(self):
        op = self.op(); P1 = self.moved(); i = np.argwhere(np.any(P1 != self.P, axis=-1))[0]; P1 = P1.copy(); P1[i[0], i[1]] = self.P[i[0], i[1]]
        with self.assertRaises((ValueError, base.RepresentationError)):
            d = self.child('split', P1, op); self.verify(self.contract(d, op))

    def test_nested_bounded_parent_rejected(self):
        p = self.root / 'nested.json'; p.write_text(json.dumps({'kind': br.KIND}))
        with self.assertRaisesRegex(base.RepresentationError, 'Nested bounded'):
            br.parent_context(pin(p), target_path=self.tp, target=self.target, part='legl', space='working', baseline_context=None)


if __name__ == '__main__':
    unittest.main()
