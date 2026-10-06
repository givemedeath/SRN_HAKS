"""Head safety gates, similarity transforms, palette transport and resume."""
import copy
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from head_workflow import (MOTION, Session, RECIPE, allocate_slots, fit_similarity, make_roster,
                           model_name, pin, task_fields, validate_roster, validate_target,
                           verify_package_payload, write_fresh)
from head_export import ascii_model, node_matrix, plt_bytes


class HeadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.roster = self.root / "roster.json"
        write_fresh(self.roster, make_roster())
        self.session = Session.create(self.root / "session", self.roster)
        self.views = []
        for name in ("front", "left", "back", "right"):
            path = self.root / (name+".png")
            path.write_bytes(name.encode())
            self.views.append(path)
        self.report = self.root / "reference.json"
        write_fresh(self.report, {"kind": "srn-head-review", "designId": "human-male-01",
            "stage": "reference", "passed": True, "views": ["front", "left", "back", "right"],
            "sharedScale": True, "inputs": [pin(self.roster)], "evidence": [pin(p) for p in self.views]})
        self.session.review("human-male-01", "reference", self.report)
        self.payload = {**RECIPE, "image_urls": [str(p) for p in self.views]}

    def tearDown(self):
        self.tmp.cleanup()

    def reserve(self, identity="one"):
        self.session.reserve("human-male-01", identity, "multi-image-to-3d", 20,
                             [pin(p) for p in self.views], self.payload)

    def complete(self, identity="one", credits=20):
        create = self.root / (identity+"-create.json")
        write_fresh(create, {"result": identity})
        self.session.record_task(identity, identity, "multi-image-to-3d", create)
        terminal = self.root / (identity+"-terminal.json")
        write_fresh(terminal, {"id": identity, "status": "SUCCEEDED", "consumed_credits": credits})
        self.session.settle(identity, "SUCCEEDED", credits, terminal)

    def test_roster_and_lowest_contiguous_slots(self):
        roster = make_roster()
        self.assertEqual(len(roster["entries"]), 200)
        self.assertEqual(sum(e["pilot"] for e in roster["entries"]), 4)
        occupied = ["PMH0_HEAD005.MDL", "pmh0_head021.mdl"]
        allocated = allocate_slots(roster, occupied, maximum=255)
        self.assertEqual([r["slot"] for r in allocated["entries"] if r["prefix"] == "pmh0"], list(range(22, 42)))
        self.assertEqual(allocate_slots(allocated, occupied, maximum=255), allocated)
        with self.assertRaisesRegex(ValueError, "collides"):
            allocate_slots(allocated, [*occupied, "pmh0_head022.mdl"], maximum=255)
        allocated["entries"][0]["slot"] = None
        with self.assertRaisesRegex(ValueError, "Partial"):
            allocate_slots(allocated, [], maximum=255)
        with self.assertRaises(ValueError): model_name("pmh2", 1)
        with self.assertRaises(ValueError): model_name("pmh0", 256)

    def test_paid_reservation_resume_and_two_attempt_limit(self):
        self.reserve()
        resumed = Session(self.session.root)
        self.assertEqual(resumed.credit_used(), 20)
        with self.assertRaisesRegex(ValueError, "Duplicate"): self.reserve()
        with self.assertRaisesRegex(ValueError, "outstanding"): self.reserve("two")
        self.complete()
        self.reserve("two")
        self.complete("two")
        with self.assertRaisesRegex(ValueError, "exhausted"): self.reserve("three")
        self.assertEqual(resumed.credit_used(), 40)

    def test_revision_family_has_one_spending_owner_and_shared_lock(self):
        self.session.reserve('human-male-01', 'prior', 'multi-image-to-3d', 280,
                             [pin(p) for p in self.views], self.payload)
        with self.assertRaisesRegex(ValueError, 'outstanding'):
            self.session.fork_revision(self.root/'unfinished', ['human-male-01'], 'donor', [pin(self.roster)])
        self.complete('prior', credits=280)
        active = self.session.fork_revision(self.root/'active', ['human-male-01'], 'donor', [pin(self.roster)])
        sibling = self.session.fork_revision(self.root/'sibling', ['human-male-01'], 'donor', [pin(self.roster)])
        for retired in (self.session, sibling, Session(self.session.root)):
            with self.assertRaisesRegex(ValueError, 'another active revision'):
                retired.reserve('human-male-01', 'retry', 'multi-image-to-3d', 20,
                                [pin(p) for p in self.views], self.payload)
        with active.spending_lock():
            with self.assertRaisesRegex(ValueError, 'Spending operation is active'):
                self.reserve('blocked')
        active.reserve('human-male-01', 'retry', 'multi-image-to-3d', 20,
                       [pin(p) for p in self.views], self.payload)
        self.assertEqual(Session(active.root).credit_used(), 300)
        with self.assertRaisesRegex(ValueError, 'another active revision'):
            sibling.reserve('human-male-01', 'retry', 'multi-image-to-3d', 20,
                            [pin(p) for p in self.views], self.payload)
        self.session = active
        self.complete('retry')
        next_revision = active.fork_revision(self.root/'next', ['human-male-01'], 'donor', [pin(self.roster)])
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            next_revision.reserve('human-male-01', 'retry', 'multi-image-to-3d', 20,
                                  [pin(p) for p in self.views], self.payload)
        with self.assertRaisesRegex(ValueError, 'cap exceeded'):
            next_revision.reserve('human-male-01', 'third', 'multi-image-to-3d', 20,
                                  [pin(p) for p in self.views], self.payload)

    def test_budget_recipe_and_stale_reference_rejection(self):
        with self.assertRaisesRegex(ValueError, "price"):
            self.session.reserve("human-male-01", "cheap", "multi-image-to-3d", 1,
                                 [pin(p) for p in self.views], self.payload)
        with self.assertRaisesRegex(ValueError, "cap exceeded"):
            self.session.reserve("human-male-01", "expensive", "multi-image-to-3d", 301,
                                 [pin(p) for p in self.views], self.payload)
        bad = {**self.payload, "ai_model": "latest"}
        with self.assertRaisesRegex(ValueError, "recipe"):
            self.session.reserve("human-male-01", "drift", "multi-image-to-3d", 20,
                                 [pin(p) for p in self.views], bad)
        self.views[0].write_bytes(b"changed image")
        with self.assertRaisesRegex(ValueError, "changed"): self.reserve()

    def test_task_ownership_and_unknown_charge_fail_closed(self):
        self.reserve()
        other = self.root / "wrong.json"
        write_fresh(other, {"result": "other"})
        with self.assertRaisesRegex(ValueError, "differs"):
            self.session.record_task("one", "one", "multi-image-to-3d", other)
        create = self.root / "create.json"
        write_fresh(create, {"result": {"task": {"raw": {"id": "one"}}}})
        self.session.record_task("one", "one", "multi-image-to-3d", create)
        with self.assertRaisesRegex(ValueError, "Actual consumed"):
            self.session.settle("one", "SUCCEEDED", None, create)
        with self.assertRaisesRegex(ValueError, "differs"):
            self.session.settle("one", "SUCCEEDED", 0, create)
        self.assertEqual(self.session.credit_used(), 20)
        with self.assertRaisesRegex(ValueError, "review missing"):
            self.session.publication(["human-male-01"])

    def test_runtime_remesh_target_and_owning_task(self):
        self.reserve();self.complete()
        donor=self.root/'donor.json'
        write_fresh(donor,{'kind':'srn-head-review','designId':'human-male-01','stage':'donor','passed':True,
            'parentReportSha256':pin(self.report)['sha256'],'inputs':[pin(self.roster)],
            'evidence':[pin(self.report)],'sourceUnmodified':True,'geometryInspected':True})
        self.session.review('human-male-01','donor',donor)
        recipe={'input_task_id':'one','topology':'triangle','target_polycount':9000,'target_formats':['glb']}
        for field,value in [('target_polycount',20001),('topology','ngon'),('input_task_id','unowned')]:
            with self.subTest(field=field),self.assertRaises(ValueError):
                self.session.reserve('human-male-01','bad-'+field.replace('_','-'),'remesh',5,[pin(donor)],{**recipe,field:value})
        self.session.reserve('human-male-01','remesh-good','remesh',5,[pin(donor)],recipe)
        self.assertEqual(Session(self.session.root).credit_used(),25)

    def test_remesh_local_model_url_binds_to_reviewed_donor_source(self):
        self.reserve(); self.complete()
        donor_model = self.root / 'donor_model.glb'
        donor_model.write_bytes(b'donor_bytes')
        donor = self.root / 'donor_with_source.json'
        write_fresh(donor, {
            'kind': 'srn-head-review', 'designId': 'human-male-01', 'stage': 'donor', 'passed': True,
            'parentReportSha256': pin(self.report)['sha256'], 'inputs': [pin(self.roster), pin(donor_model)],
            'evidence': [pin(self.report)], 'source': pin(donor_model),
            'sourceUnmodified': True, 'geometryInspected': True
        })
        self.session.review('human-male-01', 'donor', donor)

        sub_model = self.root / 'sub_model.glb'
        sub_model.write_bytes(b'substituted_bytes')

        remesh_payload = {'model_url': str(donor_model), 'topology': 'triangle',
                          'target_polycount': 9000, 'target_formats': ['glb']}

        # Undeclared input fails
        with self.assertRaisesRegex(ValueError, 'Remesh source omitted from declaration'):
            self.session.reserve('human-male-01', 'remesh-undeclared', 'remesh', 5,
                                 [pin(donor)], remesh_payload)

        # Declared substituted model fails donor match
        with self.assertRaisesRegex(ValueError, 'Remesh source must use the exact reviewed donor geometry'):
            self.session.reserve('human-male-01', 'remesh-substituted', 'remesh', 5,
                                 [pin(donor), pin(sub_model)],
                                 {**remesh_payload, 'model_url': str(sub_model)})

        # Declared matching donor model succeeds
        self.session.reserve('human-male-01', 'remesh-valid', 'remesh', 5,
                             [pin(donor), pin(donor_model)], remesh_payload)
        self.assertEqual(Session(self.session.root).credit_used(), 25)

    def test_rigid_fit_and_reflection_rejection(self):
        source = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]], dtype=float)
        result = fit_similarity(source, source * 3 + [4, 5, 6], 1e-8)
        np.testing.assert_allclose(result["matrix"], [[3,0,0,4],[0,3,0,5],[0,0,3,6],[0,0,0,1]], atol=1e-8)
        with self.assertRaisesRegex(ValueError, "Reflection"):
            fit_similarity(source, source * [-1, 1, 1], 1e-8)
        with self.assertRaisesRegex(ValueError, "residual"):
            fit_similarity(source, source * [1, 2, 3], 1e-8)
        with self.assertRaises(ValueError): node_matrix({"scale": [1, 2, 1]})

    def test_palette_rows_and_material_ownership(self):
        shades = np.zeros((1024, 1024), dtype=np.uint8)
        layers = shades.copy(); layers[-1] = 1; shades[-1] = 123
        payload = plt_bytes(shades, layers)
        self.assertEqual(payload[:8], b"PLT V1  ")
        self.assertEqual(payload[24:26], bytes([123, 1]))
        layers[0,0] = 2
        with self.assertRaisesRegex(ValueError, "masks"): plt_bytes(shades, layers)
        p = np.array([[[0,0,0],[1,0,0],[0,1,0]]], dtype=float)
        n = np.tile([0,0,1], (1,3,1)); uv = p[:,:,:2]
        groups = [{"kind": "palette", "triangles": [0]}]
        text = ascii_model("pmh0_head022", p, n, uv, groups)
        self.assertIn("bitmap pmh0_head022", text)
        with self.assertRaisesRegex(ValueError, "exactly one"):
            ascii_model("pmh0_head022", p, n, uv, groups * 2)
        with self.assertRaisesRegex(ValueError, "Invalid material"):
            ascii_model("pmh0_head022", p, n, uv, [{"kind":"fixed", "suffix":"../x", "triangles":[0]}])

    def test_downstream_reviews_require_approved_fit_pin(self):
        source_model = self.root / 'head_source.glb'; source_model.write_bytes(b'glb_source')
        donor = self.root / 'donor.json'
        write_fresh(donor, {
            'kind': 'srn-head-review', 'designId': 'human-male-01', 'stage': 'donor', 'passed': True,
            'parentReportSha256': pin(self.report)['sha256'], 'inputs': [pin(self.roster), pin(source_model)],
            'evidence': [pin(self.report)], 'source': pin(source_model),
            'sourceUnmodified': True, 'geometryInspected': True
        })
        self.session.review('human-male-01', 'donor', donor)

        protected = self.root / 'body.mdl'; protected.write_bytes(b'body')
        manifest = self.root / 'manifest.json'
        write_fresh(manifest, {'resources': [{'path': 'body.mdl', 'sha256': pin(protected)['sha256']}]})
        stock = []
        for name in ('rig', 'neck', 'skin', 'hair', 'animation'):
            p = self.root / name; p.write_bytes(name.encode()); stock.append(pin(p))
        target_data = {
            'schemaVersion': 1, 'kind': 'srn-head-target', 'approved': True, 'race': 'human', 'sex': 'male',
            'prefix': 'pmh0', 'phenotype': 0, 'bodyRevision': pin(manifest)['sha256'], 'bodyManifest': pin(manifest),
            'bodyResourceRoot': str(self.root), 'rig': stock[0], 'neckGeometry': stock[1], 'palettes': stock[2:4],
            'animations': stock[4:], 'headBindMatrix': [[1,0,0,0],[0,1,0,0],[0,0,1,1.75],[0,0,0,1]],
            'cranialEnvelope': [[-.1,-.1,-.06],[.1,.15,.2]], 'landmarkTolerance': .025
        }
        target_file = self.root / 'target.json'
        write_fresh(target_file, target_data)

        landmarks = [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
        sim = fit_similarity(np.array(landmarks, dtype=float), np.array(landmarks, dtype=float), target_data['landmarkTolerance'])
        fit_data = {
            'target': pin(target_file), 'source': pin(source_model),
            'sourceLandmarks': landmarks, 'targetLandmarks': landmarks, 'matrix': sim['matrix']
        }
        fit_file = self.root / 'fit.json'
        write_fresh(fit_file, fit_data)

        fitting = self.root / 'fitting.json'
        write_fresh(fitting, {
            'kind': 'srn-head-review', 'designId': 'human-male-01', 'stage': 'fitting', 'passed': True,
            'parentReportSha256': pin(donor)['sha256'],
            'inputs': [pin(self.roster), pin(target_file), pin(fit_file), pin(source_model)],
            'evidence': [pin(donor)], 'target': pin(target_file), 'fit': pin(fit_file)
        })
        self.session.review('human-male-01', 'fitting', fitting)

        # Substitute fit
        sub_fit_file = self.root / 'sub_fit.json'
        write_fresh(sub_fit_file, {**fit_data, 'matrix': [[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]]})

        # Assembly report with substituted fit rejected
        bad_assembly = self.root / 'assembly_bad.json'
        write_fresh(bad_assembly, {
            'kind': 'srn-head-review', 'designId': 'human-male-01', 'stage': 'assembly', 'passed': True,
            'parentReportSha256': pin(fitting)['sha256'],
            'inputs': [pin(self.roster), pin(target_file), pin(sub_fit_file)],
            'evidence': [pin(fitting)], 'target': pin(target_file), 'fit': pin(sub_fit_file),
            'standingReviewed': True, 'worstCaseMotionReviewed': True, 'bodyResourcesUnchanged': True,
            'motions': list(MOTION)
        })
        with self.assertRaisesRegex(ValueError, 'Fit changed after fitting'):
            self.session.review('human-male-01', 'assembly', bad_assembly)

        # Assembly report missing fit pin rejected
        missing_fit_assembly = self.root / 'assembly_missing_fit.json'
        write_fresh(missing_fit_assembly, {
            'kind': 'srn-head-review', 'designId': 'human-male-01', 'stage': 'assembly', 'passed': True,
            'parentReportSha256': pin(fitting)['sha256'],
            'inputs': [pin(self.roster), pin(target_file)],
            'evidence': [pin(fitting)], 'target': pin(target_file),
            'standingReviewed': True, 'worstCaseMotionReviewed': True, 'bodyResourcesUnchanged': True,
            'motions': list(MOTION)
        })
        with self.assertRaisesRegex(ValueError, 'Fit changed after fitting'):
            self.session.review('human-male-01', 'assembly', missing_fit_assembly)

        # Assembly report with exact approved fit accepted
        good_assembly = self.root / 'assembly_good.json'
        write_fresh(good_assembly, {
            'kind': 'srn-head-review', 'designId': 'human-male-01', 'stage': 'assembly', 'passed': True,
            'parentReportSha256': pin(fitting)['sha256'],
            'inputs': [pin(self.roster), pin(target_file), pin(fit_file)],
            'evidence': [pin(fitting)], 'target': pin(target_file), 'fit': pin(fit_file),
            'standingReviewed': True, 'worstCaseMotionReviewed': True, 'bodyResourcesUnchanged': True,
            'motions': list(MOTION)
        })
        self.session.review('human-male-01', 'assembly', good_assembly)

        # Native report with substituted fit rejected
        bad_native = self.root / 'native_bad.json'
        write_fresh(bad_native, {
            'kind': 'srn-head-review', 'designId': 'human-male-01', 'stage': 'native', 'passed': True,
            'parentReportSha256': pin(good_assembly)['sha256'],
            'inputs': [pin(self.roster), pin(target_file), pin(sub_fit_file)],
            'evidence': [pin(good_assembly)], 'target': pin(target_file), 'fit': pin(sub_fit_file),
        })
        with self.assertRaisesRegex(ValueError, 'Fit changed after fitting'):
            self.session.review('human-male-01', 'native', bad_native)

    def test_native_and_client_reviews_bind_package_pin(self):
        self.reserve(); self.complete()
        fit_geom = self.root / 'fit_pkg.glb'; fit_geom.write_bytes(b'fit_geom')
        donor = self.root / 'donor_pkg.json'
        write_fresh(donor, {
            'kind': 'srn-head-review', 'designId': 'human-male-01', 'stage': 'donor', 'passed': True,
            'parentReportSha256': pin(self.report)['sha256'], 'inputs': [pin(self.roster), pin(fit_geom)],
            'evidence': [pin(self.report)], 'source': pin(fit_geom),
            'sourceUnmodified': True, 'geometryInspected': True
        })
        self.session.review('human-male-01', 'donor', donor)

        protected = self.root / 'body_pkg.mdl'; protected.write_bytes(b'body')
        manifest = self.root / 'manifest_pkg.json'
        write_fresh(manifest, {'resources': [{'path': 'body_pkg.mdl', 'sha256': pin(protected)['sha256']}]})
        stock = []
        for name in ('rig_p', 'neck_p', 'skin_p', 'hair_p', 'animation_p'):
            p = self.root / name; p.write_bytes(name.encode()); stock.append(pin(p))
        target_data = {
            'schemaVersion': 1, 'kind': 'srn-head-target', 'approved': True, 'race': 'human', 'sex': 'male',
            'prefix': 'pmh0', 'phenotype': 0, 'bodyRevision': pin(manifest)['sha256'], 'bodyManifest': pin(manifest),
            'bodyResourceRoot': str(self.root), 'rig': stock[0], 'neckGeometry': stock[1], 'palettes': stock[2:4],
            'animations': stock[4:], 'headBindMatrix': [[1,0,0,0],[0,1,0,0],[0,0,1,1.75],[0,0,0,1]],
            'cranialEnvelope': [[-.1,-.1,-.06],[.1,.15,.2]], 'landmarkTolerance': 1e-4, 'protectedResources': stock
        }
        target_file = self.root / 'target_pkg.json'; write_fresh(target_file, target_data)

        src_landmarks = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]], dtype=float)
        fit_data = {
            'kind': 'srn-head-fit', 'source': pin(fit_geom), 'target': pin(target_file),
            'matrix': np.eye(4).tolist(), 'localMatrix': np.eye(4).tolist(),
            'sourceLandmarks': src_landmarks.tolist(), 'targetLandmarks': src_landmarks.tolist(),
            'scale': 1.0, 'reflection': False, 'residualError': 0.0
        }
        fit_file = self.root / 'fit_pkg.json'; write_fresh(fit_file, fit_data)

        fitting = self.root / 'fitting_pkg.json'
        write_fresh(fitting, {
            'kind': 'srn-head-review', 'designId': 'human-male-01', 'stage': 'fitting', 'passed': True,
            'parentReportSha256': pin(donor)['sha256'],
            'inputs': [pin(self.roster), pin(target_file), pin(fit_file), pin(fit_geom)],
            'evidence': [pin(donor)], 'target': pin(target_file), 'fit': pin(fit_file)
        })
        self.session.review('human-male-01', 'fitting', fitting)

        assembly = self.root / 'assembly_pkg.json'
        write_fresh(assembly, {
            'kind': 'srn-head-review', 'designId': 'human-male-01', 'stage': 'assembly', 'passed': True,
            'parentReportSha256': pin(fitting)['sha256'],
            'inputs': [pin(self.roster), pin(target_file), pin(fit_file)],
            'evidence': [pin(fitting)], 'target': pin(target_file), 'fit': pin(fit_file),
            'standingReviewed': True, 'worstCaseMotionReviewed': True, 'bodyResourcesUnchanged': True,
            'motions': list(MOTION)
        })
        self.session.review('human-male-01', 'assembly', assembly)

        closure_file = self.root / 'closure.json'
        write_fresh(closure_file, {'passed': True, 'neckCutBoundaryEdges': 0, 'uncappedClosedNeckLoops': 0,
                                   'source': pin(fit_geom)})
        from verify_head_hak import write_hak
        res_file = self.root / 'res.mdl'; res_file.write_bytes(b'res')
        hak_file = self.root / 'test_hak.hak'
        write_hak(hak_file, [('res', 2002, b'res')])
        other_hak = self.root / 'other_hak.hak'
        write_hak(other_hak, [('other', 2002, b'other')])

        native_base = {
            'kind': 'srn-head-review', 'designId': 'human-male-01', 'stage': 'native', 'passed': True,
            'parentReportSha256': pin(assembly)['sha256'],
            'inputs': [pin(self.roster), pin(target_file), pin(fit_file), pin(closure_file), pin(res_file), pin(hak_file)],
            'evidence': [pin(assembly)], 'target': pin(target_file), 'fit': pin(fit_file),
            'neckClosure': pin(closure_file),
            'nativeDecoded': True, 'geometryUvNormalsVerified': True, 'paletteMasksVerified': True,
            'materialTransportVerified': True, 'triangles': 5000, 'textureSize': 1024,
            'resources': [pin(res_file)], 'packageSha256': pin(hak_file)['sha256']
        }

        # Native missing package pin fails
        no_pkg = self.root / 'native_no_pkg.json'
        write_fresh(no_pkg, native_base)
        with self.assertRaisesRegex(ValueError, 'Native package pin required'):
            self.session.review('human-male-01', 'native', no_pkg)

        # Native mismatched package hash fails
        bad_hash_native = self.root / 'native_bad_hash.json'
        write_fresh(bad_hash_native, {**native_base, 'package': pin(hak_file), 'packageSha256': '1'*64})
        with self.assertRaisesRegex(ValueError, 'Native package hash mismatch'):
            self.session.review('human-male-01', 'native', bad_hash_native)

        # Native package missing native resources fails
        bad_content_native = self.root / 'native_bad_content.json'
        write_fresh(bad_content_native, {**native_base, 'package': pin(other_hak), 'packageSha256': pin(other_hak)['sha256'],
                                         'inputs': [pin(self.roster), pin(target_file), pin(fit_file), pin(closure_file), pin(res_file), pin(other_hak)]})
        with self.assertRaisesRegex(ValueError, 'Package does not contain verified native resource'):
            self.session.review('human-male-01', 'native', bad_content_native)

        # Bad payload verification receipt fails
        bad_receipt = self.root / 'bad_receipt.json'
        write_fresh(bad_receipt, {'kind': 'srn-head-hak-verification', 'hak': pin(other_hak),
                                  'payloadHashesVerified': True, 'resources': 1})
        bad_receipt_native = self.root / 'native_bad_receipt.json'
        write_fresh(bad_receipt_native, {**native_base, 'package': pin(hak_file),
                                         'payloadVerification': pin(bad_receipt),
                                         'inputs': [*native_base['inputs'], pin(bad_receipt)]})
        with self.assertRaisesRegex(ValueError, 'Package payload verification receipt invalid'):
            self.session.review('human-male-01', 'native', bad_receipt_native)

        # Receipt missing publication pin fails
        receipt_no_pub = self.root / 'receipt_no_pub.json'
        write_fresh(receipt_no_pub, {'kind': 'srn-head-hak-verification', 'hak': pin(hak_file),
                                     'payloadHashesVerified': True, 'resources': 1})
        bad_native_no_pub = self.root / 'native_no_pub.json'
        write_fresh(bad_native_no_pub, {**native_base, 'package': pin(hak_file),
                                        'payloadVerification': pin(receipt_no_pub),
                                        'inputs': [*native_base['inputs'], pin(receipt_no_pub)]})
        with self.assertRaisesRegex(ValueError, 'Package payload verification receipt requires publication pin'):
            self.session.review('human-male-01', 'native', bad_native_no_pub)

        # Receipt with unrelated publication manifest fails
        unrelated_pub = self.root / 'unrelated_pub.json'
        write_fresh(unrelated_pub, {'kind': 'srn-head-publication', 'designs': ['other-01'],
                                    'resources': [{'path': 'srn_head/other.mdl', 'sha256': '0'*64, 'bytes': 100}]})
        receipt_unrelated_pub = self.root / 'receipt_unrelated_pub.json'
        write_fresh(receipt_unrelated_pub, {'kind': 'srn-head-hak-verification', 'hak': pin(hak_file),
                                            'publication': pin(unrelated_pub),
                                            'payloadHashesVerified': True, 'resources': 1})
        bad_native_unrelated = self.root / 'native_unrelated_pub.json'
        write_fresh(bad_native_unrelated, {**native_base, 'package': pin(hak_file),
                                           'payloadVerification': pin(receipt_unrelated_pub),
                                           'inputs': [*native_base['inputs'], pin(receipt_unrelated_pub), pin(unrelated_pub)]})
        with self.assertRaisesRegex(ValueError, 'Receipt publication does not contain verified native resource'):
            self.session.review('human-male-01', 'native', bad_native_unrelated)

        # Receipt with matching publication manifest passes
        matching_pub = self.root / 'matching_pub.json'
        write_fresh(matching_pub, {'kind': 'srn-head-publication', 'designs': ['human-male-01'],
                                   'resources': [{'path': 'srn_head/' + res_file.name, 'sha256': pin(res_file)['sha256'],
                                                  'bytes': len(res_file.read_bytes())}]})
        good_receipt = self.root / 'good_receipt.json'
        write_fresh(good_receipt, {'kind': 'srn-head-hak-verification', 'hak': pin(hak_file),
                                   'publication': pin(matching_pub),
                                   'payloadHashesVerified': True, 'resources': 1})
        good_native_receipt = self.root / 'native_good_receipt.json'
        write_fresh(good_native_receipt, {**native_base, 'package': pin(hak_file),
                                          'payloadVerification': pin(good_receipt),
                                          'inputs': [*native_base['inputs'], pin(good_receipt), pin(matching_pub)]})
        fork_receipt = self.session.fork_revision(self.root / 'fork_receipt', ['human-male-01'], 'native', [pin(self.roster)])
        fork_receipt.review('human-male-01', 'native', good_native_receipt)

        # Valid direct native review passes
        good_native = self.root / 'native_good.json'
        write_fresh(good_native, {**native_base, 'package': pin(hak_file)})
        self.session.review('human-male-01', 'native', good_native)

        client_base = {
            'kind': 'srn-head-review', 'designId': 'human-male-01', 'stage': 'client', 'passed': True,
            'parentReportSha256': pin(good_native)['sha256'],
            'inputs': [pin(self.roster), pin(target_file), pin(fit_file), pin(hak_file)],
            'evidence': [pin(good_native)], 'target': pin(target_file), 'fit': pin(fit_file),
            'clientObserved': True, 'slotsSelectable': True, 'helmetsReviewed': True,
            'palettesReviewed': True, 'lightingReviewed': True, 'motions': list(MOTION),
            'packageSha256': pin(hak_file)['sha256']
        }

        # Client missing package pin fails
        no_client_pkg = self.root / 'client_no_pkg.json'
        write_fresh(no_client_pkg, client_base)
        with self.assertRaisesRegex(ValueError, 'Client package pin required'):
            self.session.review('human-male-01', 'client', no_client_pkg)

        # Client tested another package fails
        diff_client = self.root / 'client_diff_pkg.json'
        write_fresh(diff_client, {**client_base, 'package': pin(other_hak), 'packageSha256': pin(other_hak)['sha256']})
        with self.assertRaisesRegex(ValueError, 'Client tested another package'):
            self.session.review('human-male-01', 'client', diff_client)

        # Valid client review with matching package passes
        good_client = self.root / 'client_good.json'
        write_fresh(good_client, {**client_base, 'package': pin(hak_file)})
        self.session.review('human-male-01', 'client', good_client)

    def test_review_pins_exact_bytes_and_rejects_mutation_before_append(self):
        ref_report = self.root / 'reference_mutation_test.json'
        write_fresh(ref_report, {
            'kind': 'srn-head-review', 'designId': 'human-male-02', 'stage': 'reference', 'passed': True,
            'inputs': [pin(self.roster)], 'evidence': [pin(self.roster)],
            'views': ['front', 'left', 'back', 'right'], 'sharedScale': True
        })
        original_reviews = self.session.reviews
        def mutating_reviews(identity):
            ref_report.write_text('{"mutated": true}')
            return original_reviews(identity)
        self.session.reviews = mutating_reviews
        try:
            with self.assertRaisesRegex(ValueError, 'Frozen input changed'):
                self.session.review('human-male-02', 'reference', ref_report)
        finally:
            self.session.reviews = original_reviews

        ref_report.unlink()
        write_fresh(ref_report, {
            'kind': 'srn-head-review', 'designId': 'human-male-02', 'stage': 'reference', 'passed': True,
            'inputs': [pin(self.roster)], 'evidence': [pin(self.roster)],
            'views': ['front', 'left', 'back', 'right'], 'sharedScale': True
        })
        self.session.review('human-male-02', 'reference', ref_report)
        recorded = [e for e in self.session.events() if e['kind'] == 'review' and e['designId'] == 'human-male-02']
        self.assertEqual(len(recorded), 1)
        self.assertEqual(recorded[0]['report'], pin(ref_report))

    def test_reserve_multi_image_generation_binds_to_approved_reference_evidence(self):
        other_views = []
        for name in ("front2", "left2", "back2", "right2"):
            p = self.root / (name + ".png")
            p.write_bytes(name.encode())
            other_views.append(p)
        other_payload = {**RECIPE, "image_urls": [str(p) for p in other_views]}
        with self.assertRaisesRegex(ValueError, "Generation image pins must match approved reference review evidence"):
            self.session.reserve("human-male-01", "unapproved-images", "multi-image-to-3d", 20,
                                 [pin(p) for p in other_views], other_payload)

        # One substituted image among reviewed images
        sub_views = [*self.views[:3], other_views[3]]
        sub_payload = {**RECIPE, "image_urls": [str(p) for p in sub_views]}
        with self.assertRaisesRegex(ValueError, "Generation image pins must match approved reference review evidence"):
            self.session.reserve("human-male-01", "sub-image", "multi-image-to-3d", 20,
                                 [pin(p) for p in sub_views], sub_payload)

        # Duplicate image in payload
        dup_payload = {**RECIPE, "image_urls": [str(self.views[0]), str(self.views[0]), str(self.views[2]), str(self.views[3])]}
        with self.assertRaisesRegex(ValueError, "Generation image pins must match approved reference review evidence"):
            self.session.reserve("human-male-01", "dup-image", "multi-image-to-3d", 20,
                                 [pin(p) for p in self.views], dup_payload)

        # Matching views and hashes succeed
        self.session.reserve("human-male-01", "valid-reserve", "multi-image-to-3d", 20,
                             [pin(p) for p in self.views], self.payload)

    def test_fitting_review_binds_to_reviewed_donor_source(self):
        donor_model_a = self.root / "donor_a.glb"
        donor_model_a.write_bytes(b"donor_a")
        donor_model_b = self.root / "donor_b.glb"
        donor_model_b.write_bytes(b"donor_b")

        # 1. Donor report omitting source is rejected at fitting stage
        donor_no_source = self.root / "donor_no_source.json"
        write_fresh(donor_no_source, {
            "kind": "srn-head-review", "designId": "human-male-01", "stage": "donor", "passed": True,
            "parentReportSha256": pin(self.report)["sha256"], "inputs": [pin(self.roster)],
            "evidence": [pin(self.report)], "sourceUnmodified": True, "geometryInspected": True
        })
        self.session.review("human-male-01", "donor", donor_no_source)

        protected = self.root / "body_fit_test.mdl"; protected.write_bytes(b"body")
        manifest = self.root / "manifest_fit_test.json"
        write_fresh(manifest, {"resources": [{"path": "body_fit_test.mdl", "sha256": pin(protected)["sha256"]}]})
        stock = []
        for name in ("rig_ft", "neck_ft", "skin_ft", "hair_ft", "anim_ft"):
            p = self.root / name; p.write_bytes(name.encode()); stock.append(pin(p))
        target_data = {
            "schemaVersion": 1, "kind": "srn-head-target", "approved": True, "race": "human", "sex": "male",
            "prefix": "pmh0", "phenotype": 0, "bodyRevision": pin(manifest)["sha256"], "bodyManifest": pin(manifest),
            "bodyResourceRoot": str(self.root), "rig": stock[0], "neckGeometry": stock[1], "palettes": stock[2:4],
            "animations": stock[4:], "headBindMatrix": [[1,0,0,0],[0,1,0,0],[0,0,1,1.75],[0,0,0,1]],
            "cranialEnvelope": [[-.1,-.1,-.06],[.1,.15,.2]], "landmarkTolerance": .025
        }
        target_file = self.root / "target_fit_test.json"
        write_fresh(target_file, target_data)

        landmarks = [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
        sim = fit_similarity(np.array(landmarks, dtype=float), np.array(landmarks, dtype=float), target_data["landmarkTolerance"])
        fit_data_b = {
            "target": pin(target_file), "source": pin(donor_model_b),
            "sourceLandmarks": landmarks, "targetLandmarks": landmarks, "matrix": sim["matrix"]
        }
        fit_file_b = self.root / "fit_b.json"
        write_fresh(fit_file_b, fit_data_b)

        fitting_with_no_donor_source = self.root / "fitting_no_src.json"
        write_fresh(fitting_with_no_donor_source, {
            "kind": "srn-head-review", "designId": "human-male-01", "stage": "fitting", "passed": True,
            "parentReportSha256": pin(donor_no_source)["sha256"],
            "inputs": [pin(self.roster), pin(target_file), pin(fit_file_b), pin(donor_model_b)],
            "evidence": [pin(donor_no_source)], "target": pin(target_file), "fit": pin(fit_file_b)
        })
        with self.assertRaisesRegex(ValueError, "Donor review requires pinned source"):
            self.session.review("human-male-01", "fitting", fitting_with_no_donor_source)

        # 2. Donor report inspecting source A, but fitting points to source B
        donor_with_source_a = self.root / "donor_with_a.json"
        write_fresh(donor_with_source_a, {
            "kind": "srn-head-review", "designId": "human-male-01", "stage": "donor", "passed": True,
            "parentReportSha256": pin(self.report)["sha256"], "inputs": [pin(self.roster), pin(donor_model_a)],
            "evidence": [pin(self.report)], "source": pin(donor_model_a),
            "sourceUnmodified": True, "geometryInspected": True
        })
        session_fork = self.session.fork_revision(self.root / "fork", ["human-male-01"], "donor", [pin(self.roster)])
        session_fork.review("human-male-01", "donor", donor_with_source_a)

        fitting_with_mismatched_src = self.root / "fitting_mismatch.json"
        write_fresh(fitting_with_mismatched_src, {
            "kind": "srn-head-review", "designId": "human-male-01", "stage": "fitting", "passed": True,
            "parentReportSha256": pin(donor_with_source_a)["sha256"],
            "inputs": [pin(self.roster), pin(target_file), pin(fit_file_b), pin(donor_model_b)],
            "evidence": [pin(donor_with_source_a)], "target": pin(target_file), "fit": pin(fit_file_b)
        })
        with self.assertRaisesRegex(ValueError, "Fitted source differs from reviewed donor geometry"):
            session_fork.review("human-male-01", "fitting", fitting_with_mismatched_src)

        # 3. Fitting with matching source A succeeds
        fit_data_a = {
            "target": pin(target_file), "source": pin(donor_model_a),
            "sourceLandmarks": landmarks, "targetLandmarks": landmarks, "matrix": sim["matrix"]
        }
        fit_file_a = self.root / "fit_a.json"
        write_fresh(fit_file_a, fit_data_a)
        fitting_with_matching_src = self.root / "fitting_match.json"
        write_fresh(fitting_with_matching_src, {
            "kind": "srn-head-review", "designId": "human-male-01", "stage": "fitting", "passed": True,
            "parentReportSha256": pin(donor_with_source_a)["sha256"],
            "inputs": [pin(self.roster), pin(target_file), pin(fit_file_a), pin(donor_model_a)],
            "evidence": [pin(donor_with_source_a)], "target": pin(target_file), "fit": pin(fit_file_a)
        })
        session_fork.review("human-male-01", "fitting", fitting_with_matching_src)

    def test_retexture_reservation_binds_to_approved_reference_evidence_and_fit(self):
        source_model = self.root / 'retext_src.glb'; source_model.write_bytes(b'retext_src')
        donor = self.root / 'retext_donor.json'
        write_fresh(donor, {
            'kind': 'srn-head-review', 'designId': 'human-male-01', 'stage': 'donor', 'passed': True,
            'parentReportSha256': pin(self.report)['sha256'], 'inputs': [pin(self.roster), pin(source_model)],
            'evidence': [pin(self.report)], 'source': pin(source_model),
            'sourceUnmodified': True, 'geometryInspected': True
        })
        self.session.review('human-male-01', 'donor', donor)

        protected = self.root / 'body_rt.mdl'; protected.write_bytes(b'body')
        manifest = self.root / 'manifest_rt.json'
        write_fresh(manifest, {'resources': [{'path': 'body_rt.mdl', 'sha256': pin(protected)['sha256']}]})
        stock = []
        for name in ('rig_rt', 'neck_rt', 'skin_rt', 'hair_rt', 'anim_rt'):
            p = self.root / name; p.write_bytes(name.encode()); stock.append(pin(p))
        target_data = {
            'schemaVersion': 1, 'kind': 'srn-head-target', 'approved': True, 'race': 'human', 'sex': 'male',
            'prefix': 'pmh0', 'phenotype': 0, 'bodyRevision': pin(manifest)['sha256'], 'bodyManifest': pin(manifest),
            'bodyResourceRoot': str(self.root), 'rig': stock[0], 'neckGeometry': stock[1], 'palettes': stock[2:4],
            'animations': stock[4:], 'headBindMatrix': [[1,0,0,0],[0,1,0,0],[0,0,1,1.75],[0,0,0,1]],
            'cranialEnvelope': [[-.1,-.1,-.06],[.1,.15,.2]], 'landmarkTolerance': .025
        }
        target_file = self.root / 'target_rt.json'; write_fresh(target_file, target_data)

        landmarks = [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
        sim = fit_similarity(np.array(landmarks, dtype=float), np.array(landmarks, dtype=float), target_data['landmarkTolerance'])
        fit_data = {
            'target': pin(target_file), 'source': pin(source_model),
            'sourceLandmarks': landmarks, 'targetLandmarks': landmarks, 'matrix': sim['matrix']
        }
        fit_file = self.root / 'fit_rt.json'; write_fresh(fit_file, fit_data)

        fitting = self.root / 'fitting_rt.json'
        write_fresh(fitting, {
            'kind': 'srn-head-review', 'designId': 'human-male-01', 'stage': 'fitting', 'passed': True,
            'parentReportSha256': pin(donor)['sha256'],
            'inputs': [pin(self.roster), pin(target_file), pin(fit_file), pin(source_model)],
            'evidence': [pin(donor)], 'target': pin(target_file), 'fit': pin(fit_file)
        })
        self.session.review('human-male-01', 'fitting', fitting)

        assembly = self.root / 'assembly_rt.json'
        write_fresh(assembly, {
            'kind': 'srn-head-review', 'designId': 'human-male-01', 'stage': 'assembly', 'passed': True,
            'parentReportSha256': pin(fitting)['sha256'],
            'inputs': [pin(self.roster), pin(target_file), pin(fit_file)],
            'evidence': [pin(fitting)], 'target': pin(target_file), 'fit': pin(fit_file),
            'standingReviewed': True, 'worstCaseMotionReviewed': True, 'bodyResourcesUnchanged': True,
            'motions': list(MOTION)
        })
        self.session.review('human-male-01', 'assembly', assembly)

        sub_model = self.root / 'other_model.glb'; sub_model.write_bytes(b'other')
        base_retexture = {
            'model_url': str(source_model), 'multiview_image_urls': [str(p) for p in self.views],
            'texture_resolution': '2k', 'enable_original_uv': True, 'enable_pbr': True,
            'ai_model': 'meshy-7', 'remove_lighting': False, 'target_formats': ['glb']
        }

        # 1. Retexture with substituted model_url fails
        bad_model_payload = {**base_retexture, 'model_url': str(sub_model)}
        with self.assertRaisesRegex(ValueError, 'Retexture must use the exact selected fitted geometry'):
            self.session.reserve('human-male-01', 'bad-model-retext', 'retexture', 10,
                                 [pin(sub_model), *[pin(p) for p in self.views]], bad_model_payload)

        # 2. Retexture with unapproved multiview images fails
        other_views = []
        for name in ('rt_front', 'rt_left', 'rt_back', 'rt_right'):
            p = self.root / (name + '.png'); p.write_bytes(name.encode()); other_views.append(p)
        bad_images_payload = {**base_retexture, 'multiview_image_urls': [str(p) for p in other_views]}
        with self.assertRaisesRegex(ValueError, 'Retexture image pins must match approved reference review evidence'):
            self.session.reserve('human-male-01', 'bad-imgs-retext', 'retexture', 10,
                                 [pin(source_model), *[pin(p) for p in other_views]], bad_images_payload)

        # 3. Valid retexture reservation succeeds
        self.session.reserve('human-male-01', 'good-retext', 'retexture', 10,
                             [pin(source_model), *[pin(p) for p in self.views]], base_retexture)

    def test_verify_package_payload_validates_receipt_publication_manifest(self):
        hak_file = self.root / 'pkg_test.hak'; hak_file.write_bytes(b'hak_bytes')
        res_file = self.root / 'res_test.mdl'; res_file.write_bytes(b'res_bytes')

        # 1. Receipt missing publication pin fails
        receipt_no_pub = self.root / 'rec_no_pub.json'
        write_fresh(receipt_no_pub, {'kind': 'srn-head-hak-verification', 'hak': pin(hak_file),
                                     'payloadHashesVerified': True, 'resources': 1})
        with self.assertRaisesRegex(ValueError, 'Package payload verification receipt requires publication pin'):
            verify_package_payload(pin(hak_file), [pin(res_file)], receipt_pin=pin(receipt_no_pub))

        # 2. Receipt publication kind invalid fails
        bad_pub = self.root / 'bad_pub_kind.json'
        write_fresh(bad_pub, {'kind': 'wrong', 'resources': []})
        rec_bad_pub = self.root / 'rec_bad_pub.json'
        write_fresh(rec_bad_pub, {'kind': 'srn-head-hak-verification', 'hak': pin(hak_file),
                                  'publication': pin(bad_pub), 'payloadHashesVerified': True, 'resources': 1})
        with self.assertRaisesRegex(ValueError, 'Publication manifest invalid'):
            verify_package_payload(pin(hak_file), [pin(res_file)], receipt_pin=pin(rec_bad_pub))

        # 3. Receipt publication resource hash mismatch fails
        mismatch_pub = self.root / 'mismatch_pub.json'
        write_fresh(mismatch_pub, {'kind': 'srn-head-publication', 'designs': ['human-male-01'],
                                   'resources': [{'path': 'srn_head/' + res_file.name, 'sha256': '1'*64, 'bytes': 10}]})
        rec_mismatch = self.root / 'rec_mismatch.json'
        write_fresh(rec_mismatch, {'kind': 'srn-head-hak-verification', 'hak': pin(hak_file),
                                   'publication': pin(mismatch_pub), 'payloadHashesVerified': True, 'resources': 1})
        with self.assertRaisesRegex(ValueError, 'Receipt publication does not contain verified native resource'):
            verify_package_payload(pin(hak_file), [pin(res_file)], receipt_pin=pin(rec_mismatch))

        # 4. Matching publication passes
        good_pub = self.root / 'good_pub.json'
        write_fresh(good_pub, {'kind': 'srn-head-publication', 'designs': ['human-male-01'],
                               'resources': [{'path': 'srn_head/' + res_file.name, 'sha256': pin(res_file)['sha256'],
                                              'bytes': len(res_file.read_bytes())}]})
        good_rec = self.root / 'good_rec.json'
        write_fresh(good_rec, {'kind': 'srn-head-hak-verification', 'hak': pin(hak_file),
                               'publication': pin(good_pub), 'payloadHashesVerified': True, 'resources': 1})
        verify_package_payload(pin(hak_file), [pin(res_file)], receipt_pin=pin(good_rec))


if __name__ == "__main__": unittest.main()


