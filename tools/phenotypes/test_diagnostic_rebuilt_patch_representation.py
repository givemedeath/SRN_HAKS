"""Portable rebuilt-patch pelvis representation invariants and fail-closed contract tests; no actual assets."""
import copy, hashlib, json, tempfile, unittest
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import diagnostic_rebuilt_patch_representation as rp
from diagnostic_descendant_representation import RepresentationError

Q = rp.ADOPTED_BUTTOCK[0]
V = np.array([[.1, 0, 0], [-.1, 0, 0], [0, .1, 0], [0, -.1, 0], [0, 0, .1], [0, 0, -.1]])
# Outward-oriented octahedron.
FACES = np.array([[0, 2, 4], [2, 1, 4], [1, 3, 4], [3, 0, 4], [2, 0, 5], [1, 2, 5], [3, 1, 5], [0, 3, 5]])


def octahedron():
    return V[FACES].astype(float)


def archive(P, src, caps):
    n = len(P); nrm = np.repeat(rp.face_normals(P)[:, None, :], 3, 1); nrm /= np.linalg.norm(nrm, axis=-1, keepdims=True)
    uv = (P[..., :2] + .1) * 2; t = np.concatenate([np.tile([1., 0, 0], (n, 3, 1)), np.ones((n, 3, 1))], -1)
    bary = np.where(src[:, None, None] >= 0, np.eye(3), np.nan)
    return {'positions': P.copy(), 'normals': nrm, 'uvGltf': uv, 'uvNative': np.stack((uv[..., 0], 1 - uv[..., 1]), -1), 'tangents': t,
            'sourceFaceIds': src.astype(np.int64), 'sourceBarycentricWeights': bary, 'generatedCapFaceIds': np.asarray(caps, np.int64),
            'tangentTriangleIds': np.arange(n)}


class Fixture:
    """Parent octahedron (face 7 generated cap, faces 0/1 brief); rebuild deletes faces 1 and 2 and refills them as new faces."""

    def __init__(self):
        P = octahedron(); src = np.array([0, 1, 2, 3, 4, 5, 6, -1])
        self.O = archive(P, np.arange(8), [])
        self.P = archive(P, src, [7])
        brief_src = np.zeros(8, bool); brief_src[[0, 1]] = True; doc = np.array([0, 0, 0, 0, 0, 0, 0, 1])
        brief = np.zeros(8, bool); brief[[0, 1]] = True
        static = {'original10582MainBriefSourceMask': brief_src, 'original191SkinExceptionSourceIds': np.array([3]), 'repairedOriginalParentFaceIds': np.array([4]),
                  'strip134ParentFaceIds': np.array([5]), 'stripGrownParentFaceIds': np.array([6])}
        self.PL = {'sourceFaceIds': src, 'sourceCutBarycentricWeights': self.P['sourceBarycentricWeights'].copy(), 'generatedCapFaceIds': np.array([7]),
                   'fixedMainBriefFaceMask': brief, 'documentFaceMaterialIds': doc, 'compilerFaceMaterialIds': np.where(brief, 4, doc), **static}
        kept = np.array([0, 3, 4, 5, 6, 7]); order = np.concatenate([kept, [1, 2]])
        R = {k: v[order].copy() if k not in ('generatedCapFaceIds', 'tangentTriangleIds') else v for k, v in self.P.items()}
        R['tangentTriangleIds'] = np.arange(8); R['generatedCapFaceIds'] = np.array([5]); R['sourceFaceIds'][6:] = -1; R['sourceBarycentricWeights'][6:] = 0
        uvn = np.array([[[.01, .01], [.04, .01], [.01, .04]], [[.51, .01], [.54, .01], [.51, .04]]]); R['uvGltf'][6:] = uvn
        R['uvNative'][6:] = np.stack((uvn[..., 0], 1 - uvn[..., 1]), -1); self.R = R
        new = np.zeros(8, bool); new[6:] = True; rdoc = np.array([0, 0, 0, 0, 0, 1, 2, 3]); rbrief = np.zeros(8, bool); rbrief[0] = True
        self.RL = {'directParentFaceIds': np.where(new, -1, np.concatenate([kept, [0, 0]])), 'rebuiltPatchFaceMask': new, 'sideLipDisplacedFaceMask': np.zeros(8, bool),
                   'farSideBandReroutedFaceMask': np.zeros(8, bool), 'generatedCapFaceIds': np.array([5]), 'deletedParentFaceIds': np.array([1, 2]),
                   'documentFaceMaterialIds': rdoc, 'compilerFaceMaterialIds': np.where(rbrief, 4, rdoc), 'fixedMainBriefFaceMask': rbrief,
                   'sourceFaceIds': R['sourceFaceIds'].copy(), 'sourceCutBarycentricWeights': np.concatenate([self.PL['sourceCutBarycentricWeights'][kept], np.zeros((2, 3, 3))]),
                   'rebuiltPatchIslandIds': np.array([-1] * 6 + [0, 3]), 'briefTabTrimParentFaceIds': np.array([1], np.int32),
                   'briefBowKnotParentFaceIds': np.zeros(0, np.int32), **static}
        self.proof = {'briefTabTrimFaceIds': {'parentFaceIds': [1]}, 'briefBowKnotFaceIds': {'parentFaceIds': []}, 'briefFacesFinal': 1,
                      'texture': {'placements': {'2': [{'island': 0, 'faces': 1, 'px': [16, 16, 70, 70]}], '3': [{'island': 3, 'faces': 1, 'px': [1040, 16, 70, 70]}]}}}
        self.policy = {**rp.ADOPTED_POLICY[0], 'parentFaces': 8, 'faces': 8, 'keptFaces': 6, 'deletedParentFaces': 2, 'newFaces': 2, 'newFacesByAtlas': {'2': 1, '3': 1},
                       'islandsByAtlas': {'2': [0], '3': [3]}, 'generatedCapFaces': 1, 'parentCutRows': 0, 'displacedKeptFaces': 0, 'reroutedKeptFaces': 0,
                       'briefFacesBefore': 2, 'briefFacesAfter': 1, 'briefTabTrimFaces': 1, 'briefBowKnotFaces': 0}


class PureInvariantTests(unittest.TestCase):
    def test_pruned_brief_distance_is_exact_below_cutoff(self):
        rng = np.random.default_rng(3); pts = rng.uniform(-.2, .2, (400, 3)); brief = rng.uniform(-.05, .05, (300, 3))
        brute = np.sqrt(((pts[:, None] - brief[None]) ** 2).sum(-1)).min(1); got = rp.brief_distance(pts, brief)
        near = brute < rp.BRIEF_CUTOFF
        self.assertTrue(near.any() and (~near).any())
        np.testing.assert_array_equal(got[near], brute[near]); self.assertTrue(np.all(got[~near] >= rp.BRIEF_CUTOFF))

    def test_buttock_map_support_and_bound(self):
        rng = np.random.default_rng(5); p = rng.uniform([-.15, -.12, -.26], [.15, .07, .05], (3000, 3)); brief = np.array([[0., -.05, -.2]])
        out = rp.buttock_map(p, Q, brief)
        np.testing.assert_array_equal(out[:, :2], p[:, :2]); self.assertTrue(np.all(out[:, 2] <= p[:, 2]) and np.all(p[:, 2] - out[:, 2] <= Q['e'] * (1 + 1e-9)))
        untouched = (p[:, 1] >= 0) | (p[:, 2] >= Q['zTop']); np.testing.assert_array_equal(out[untouched], p[untouched])
        np.testing.assert_array_equal(rp.buttock_map(brief, Q, brief), brief)

    def test_buttock_transform_keeps_identity_rows_and_handedness(self):
        p = np.array([[0., .05, 0.], [.02, -.06, -.23], [.01, -.04, -.24]]); n = np.tile([0., -1, 0], (3, 1)); t = np.array([[1., 0, 0, 1], [1, 0, 0, -1], [1, 0, 0, 1]])
        nn, tt = rp.buttock_transform(p, n, t, Q, np.array([[0., -.05, -.1]]))
        np.testing.assert_array_equal(nn[0], n[0]); np.testing.assert_array_equal(tt[0], t[0]); np.testing.assert_array_equal(tt[:, 3], t[:, 3])
        np.testing.assert_allclose(np.linalg.norm(nn, axis=1), 1, atol=1e-12); np.testing.assert_allclose((tt[:, :3] * nn).sum(1), 0, atol=1e-12)

    def test_closure_detects_open_and_flipped_faces(self):
        P = octahedron(); ok = rp.closure_report(P, np.arange(8))
        self.assertEqual((ok['notTwoFaceEdges'], ok['inconsistentOrientationEdges'], ok['boundaryEdges']), (0, 0, 0))
        self.assertEqual(rp.closure_report(P[1:], np.arange(7))['notTwoFaceEdges'], 3)
        F = P.copy(); F[0] = F[0][[0, 2, 1]]; self.assertEqual(rp.closure_report(F, np.array([0]))['inconsistentOrientationEdges'], 3)

    def test_intersections(self):
        P = octahedron(); self.assertEqual(rp.intersecting_faces(P, np.arange(8)), [])
        X = np.concatenate([P, [[[.02, .02, .02], [.08, .08, .08], [.02, .03, .08]]]]); self.assertTrue(rp.intersecting_faces(X, np.array([8])))

    def test_texel_footprint_alias(self):
        a = rp.texel_footprint(np.array([[[10, 10], [20, 10], [10, 20]]]), 1.5); b = rp.texel_footprint(np.array([[[16, 16], [26, 16], [16, 26]]]), 1.5)
        c = rp.texel_footprint(np.array([[[60, 60], [70, 60], [60, 70]]]), 1.5)
        self.assertTrue(len(np.intersect1d(a, b))); self.assertFalse(len(np.intersect1d(a, c)))


class AuthorityChainTests(unittest.TestCase):
    def setUp(self):
        self.f = Fixture()

    def test_valid_fixture(self):
        f = self.f; self.assertEqual(rp.verify_parent(f.O, f.P, f.PL, f.policy)['originalIdentityRowsExact'], 7)
        report = rp.verify_rebuild(f.P, f.PL, f.R, f.RL, f.proof, f.policy)
        self.assertEqual((report['keptRowsExact'], report['newFaces'], report['newAndDisplacedIntersections']), (6, 2, 0))

    def rejected(self, mutate, message, parent=False):
        f = self.f; mutate(f)
        with self.assertRaisesRegex(RepresentationError, message):
            rp.verify_parent(f.O, f.P, f.PL, f.policy) if parent else rp.verify_rebuild(f.P, f.PL, f.R, f.RL, f.proof, f.policy)

    def test_parent_row_tamper(self): self.rejected(lambda f: f.P['positions'].__setitem__((2, 0, 0), .11), 'sealed original', parent=True)
    def test_parent_brief_tamper(self): self.rejected(lambda f: f.PL['fixedMainBriefFaceMask'].__setitem__(3, True), 'brief', parent=True)
    def test_parent_cap_inventory(self): self.rejected(lambda f: f.PL.__setitem__('generatedCapFaceIds', np.array([6])), 'cap inventory', parent=True)
    def test_kept_row_tamper(self): self.rejected(lambda f: f.R['normals'].__setitem__((1, 0, 0), .5), 'Kept rows differ')
    def test_kept_uv_tamper(self): self.rejected(lambda f: f.R['uvGltf'].__setitem__((2, 1, 0), .3), 'Kept rows differ')
    def test_new_face_flip(self):
        def flip(f):
            for k in ('positions', 'normals', 'uvGltf', 'uvNative', 'tangents'):
                f.R[k][6] = f.R[k][6][[0, 2, 1]]
        self.rejected(flip, 'open, non-manifold or flipped')
    def test_deleted_partition(self): self.rejected(lambda f: f.RL.__setitem__('deletedParentFaceIds', np.array([1, 3])), 'partition')
    def test_new_set_mismatch(self): self.rejected(lambda f: f.RL['rebuiltPatchFaceMask'].__setitem__(5, True), 'kept/new')
    def test_brief_exception_ids(self): self.rejected(lambda f: f.proof['briefTabTrimFaceIds'].__setitem__('parentFaceIds', [2]), 'Brief exception ids')
    def test_new_face_brief(self):
        def mark(f):
            f.RL['fixedMainBriefFaceMask'][6] = True; f.RL['compilerFaceMaterialIds'][6] = 4
        self.rejected(mark, 'brief')
    def test_compiler_slot(self): self.rejected(lambda f: f.RL['compilerFaceMaterialIds'].__setitem__(1, 3), 'Compiler ids')
    def test_uv_outside_island(self): self.rejected(lambda f: f.R['uvGltf'].__setitem__((6, 0, 0), .2), 'outside their declared atlas island')
    def test_static_lineage_changed(self): self.rejected(lambda f: f.RL.__setitem__('strip134ParentFaceIds', np.array([4])), 'Static parent lineage')
    def test_cap_not_inherited(self): self.rejected(lambda f: f.RL.__setitem__('generatedCapFaceIds', np.array([4])), 'Generated cap')


class FinalReplayTests(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(9); P = rng.uniform([-.1, -.1, -.25], [.1, .02, -.15], (40, 3, 3)); brief = np.zeros(40, bool); brief[:5] = True
        n = np.repeat(rp.face_normals(P)[:, None], 3, 1); n /= np.linalg.norm(n, axis=-1, keepdims=True)
        t = np.concatenate([np.tile([1., 0, 0], (40, 3, 1)), np.ones((40, 3, 1))], -1)
        self.R = archive(P, np.arange(40), []); self.R['normals'] = n; self.R['tangents'] = t
        self.RL = {'fixedMainBriefFaceMask': brief, 'documentFaceMaterialIds': np.zeros(40, np.int64)}
        bv = np.unique(P[brief].reshape(-1, 3), axis=0); flat = lambda x: x.reshape(-1, x.shape[-1])
        self.F = {k: v.copy() for k, v in self.R.items()}; self.F['positions'] = rp.buttock_map(flat(P), Q, bv).reshape(P.shape)
        N2, T2 = rp.buttock_transform(flat(P), flat(n), flat(t), Q, bv); self.F['normals'] = N2.reshape(n.shape); self.F['tangents'] = T2.reshape(t.shape)
        self.FL = copy.deepcopy(self.RL); self.doc = {'meshes': [{'primitives': []}], 'images': []}
        self.rg = {'positions': P, 'normals': n, 'uvGltf': self.R['uvGltf'], 'tangents': t}
        self.fg = {'positions': self.F['positions'], 'normals': self.F['normals'], 'uvGltf': self.R['uvGltf'], 'tangents': self.F['tangents']}

    def run_final(self):
        return rp.verify_final(self.R, self.RL, self.F, self.FL, self.doc, b'', self.rg, copy.deepcopy(self.doc), b'', self.fg, np.zeros(40, np.int64), Q)

    def test_exact_replay(self):
        report = self.run_final(); self.assertEqual(report['nativeReplayMaximumErrors']['positions'], 0.0); self.assertGreater(report['movedCorners'], 0)

    def test_position_tamper(self):
        moved = np.flatnonzero(np.any(self.F['positions'] != self.R['positions'], axis=(1, 2)))[0]; self.F['positions'][moved, 0, 2] += 1e-9
        with self.assertRaisesRegex(RepresentationError, 'native replay'): self.run_final()

    def test_unmoved_authority_tamper(self):
        self.F['uvGltf'][3, 0, 0] += 1e-6
        with self.assertRaisesRegex(RepresentationError, 'Unmoved final authority'): self.run_final()

    def test_lineage_changed(self):
        self.FL['documentFaceMaterialIds'] = np.ones(40, np.int64)
        with self.assertRaisesRegex(RepresentationError, 'lineage'): self.run_final()

    def test_glb_replay_tamper(self):
        self.fg = dict(self.fg); self.fg['normals'] = self.fg['normals'].copy(); self.fg['normals'][-1, 0, 0] += 1e-3
        with self.assertRaisesRegex(RepresentationError, 'GLB replay'): self.run_final()


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup); self.root = Path(self.tmp.name)
        self.target = {'id': 't', 'rig': {'mode': 'stock-exact', 'runtimeScale': 1}}
        self.tp = self.root / 'target.json'; self.tp.write_text(json.dumps(self.target))
        x = self.pin(self.tp)
        self.contract = {'kind': rp.KIND, 'schemaVersion': 1, 'target': x, 'part': 'pelvis', 'space': 'working', 'baselineRepresentation': x,
                         'parent': {k: x for k in rp.PARENT_FIELDS}, 'rebuild': {k: x for k in rp.REBUILD_FIELDS}, 'final': {k: x for k in rp.FINAL_FIELDS},
                         'operations': [{'kind': rp.OPERATIONS[0], 'policy': copy.deepcopy(rp.ADOPTED_POLICY[0])}, {'kind': rp.OPERATIONS[1], 'parameters': dict(Q)}],
                         'consumers': [self.pin(rp.__file__), self.pin(rp.base.__file__)], 'physicalInputs': []}

    def pin(self, p):
        return {'path': str(Path(p).resolve()), 'sha256': hashlib.sha256(Path(p).read_bytes()).hexdigest()}

    def rejected(self, mutate, message, part='pelvis'):
        c = json.loads(json.dumps(self.contract)); mutate(c); p = self.root / 'contract.json'; p.write_text(json.dumps(c))
        with self.assertRaisesRegex(RepresentationError, message):
            rp.prepare_rebuilt_patch_representation(self.pin(p), target_path=self.tp, target=self.target, part=part)

    def test_unknown_kind(self): self.rejected(lambda c: c.update(kind='diagnostic-analytic-descendant-representation'), 'Unknown rebuilt-patch contract')
    def test_schema_version_bool(self): self.rejected(lambda c: c.update(schemaVersion=True), 'Unknown rebuilt-patch contract')
    def test_extra_approval_field(self): self.rejected(lambda c: c.update(approved=True), 'Unexpected schema keys')
    def test_cross_owner(self): self.rejected(lambda c: c.update(part='chest'), 'Cross owner/space', part='chest')
    def test_runtime_space(self): self.rejected(lambda c: c.update(space='runtime'), 'Cross owner/space')
    def test_missing_final_field(self): self.rejected(lambda c: c['final'].pop('geometry'), 'Unexpected schema keys')
    def test_reordered_operations(self): self.rejected(lambda c: c['operations'].reverse(), 'reordered or unsupported')
    def test_tampered_policy(self): self.rejected(lambda c: c['operations'][0]['policy'].update(newFaces=3966), 'user-adopted fixture')
    def test_loosened_tolerance(self): self.rejected(lambda c: c['operations'][0]['policy']['glbNativeTolerance'].update(positions=1e-3), 'user-adopted fixture')
    def test_unadopted_buttock(self): self.rejected(lambda c: c['operations'][1]['parameters'].update(e=0.006), 'user-adopted set')
    def test_consumer_whitelist(self): self.rejected(lambda c: c['consumers'].pop(), 'consumer whitelist')
    def test_missing_sealed_baseline(self): self.rejected(lambda c: None, 'Sealed original pelvis source representation required')

    def test_stale_contract_pin(self):
        p = self.root / 'contract.json'; p.write_text(json.dumps(self.contract)); row = self.pin(p); p.write_text('{}')
        with self.assertRaises(RepresentationError):
            rp.prepare_rebuilt_patch_representation(row, target_path=self.tp, target=self.target, part='pelvis')

    def test_expected_closure_and_conflict(self):
        a = self.root / 'a.bin'; a.write_bytes(b'a'); pa = self.pin(a)
        ctx = SimpleNamespace(inputs={str(a): pa['sha256']}, proof={'originalGeometryReceipt': pa, 'candidate': pa, 'originalNativeCornerArchive': pa})
        rows = rp.expected_physical_inputs(self.contract, ctx); paths = {r['path'] for r in rows}
        self.assertTrue({pa['path'], str(self.tp.resolve()), str(Path(rp.__file__).resolve())} <= paths and len(paths) == len(rows))
        ctx.inputs = {str(a): '0' * 64}
        with self.assertRaisesRegex(RepresentationError, 'Conflicting'):
            rp.expected_physical_inputs(self.contract, ctx)


if __name__ == '__main__':
    unittest.main()
