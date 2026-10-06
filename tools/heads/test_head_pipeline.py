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
                           model_name, pin, task_fields, validate_roster, validate_target, write_fresh)
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
        donor = self.root / 'donor.json'
        write_fresh(donor, {
            'kind': 'srn-head-review', 'designId': 'human-male-01', 'stage': 'donor', 'passed': True,
            'parentReportSha256': pin(self.report)['sha256'], 'inputs': [pin(self.roster)],
            'evidence': [pin(self.report)], 'sourceUnmodified': True, 'geometryInspected': True
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

        source_model = self.root / 'head_source.glb'; source_model.write_bytes(b'glb_source')
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


if __name__ == "__main__": unittest.main()


