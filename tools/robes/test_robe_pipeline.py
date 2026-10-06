"""Synthetic-fixture tests for fitting math, comparison, tolerances and the Meshy policy."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fit_math
from compare_skin_models import nearest, smoothing_edges
from deformation_review import donor_cache_key
from freeze_tolerances import BOUNDS, measure
from meshy_robe import Session, validate_request
from robe_common import pin


class FitMathTests(unittest.TestCase):
    def test_segment_transform_maps_joints_and_preserves_radius(self):
        matrix = fit_math.segment_transform(np.array([0, 0, 1.0]), np.array([0.5, 0, 0.5]),
                                            np.array([0, 0, 1.0]), np.array([0, 0, 0.4]))
        apply = lambda p: (matrix @ np.r_[p, 1])[:3]
        np.testing.assert_allclose(apply([0, 0, 1.0]), [0, 0, 1.0], atol=1e-12)
        np.testing.assert_allclose(apply([0.5, 0, 0.5]), [0, 0, 0.4], atol=1e-12)
        offset = np.array([0, 0.1, 0])  # perpendicular to the segment: length kept
        self.assertAlmostEqual(np.linalg.norm(apply(np.array([0, 0, 1.0]) + offset) - [0, 0, 1.0]), 0.1)

    def test_rotation_between_is_proper(self):
        rotation = fit_math.rotation_between(np.array([1.0, 0, 0]), np.array([0, 1.0, 0]))
        np.testing.assert_allclose(rotation @ [1, 0, 0], [0, 1, 0], atol=1e-12)
        self.assertAlmostEqual(np.linalg.det(rotation), 1.0)

    def test_front_rotation_is_half_turn(self):
        np.testing.assert_allclose(fit_math.rotate_front(np.array([[1.0, 2.0, 3.0]]), "-Y"), [[-1, -2, 3]])
        with self.assertRaises(ValueError):
            fit_math.rotate_front(np.zeros((1, 3)), "+X")

    def test_lattice_leaves_clear_points_unchanged(self):
        body = np.array([[0, 0, 0], [0.1, 0, 0], [0, 0.1, 0]], float)
        faces = np.array([[0, 1, 2]])
        points = np.array([[0.02, 0.02, 0.5], [0.03, 0.02, 0.6]])
        moved, history, _, _ = fit_math.lattice_inflate(points, np.array([True, True]), body, faces, 0.006)
        np.testing.assert_allclose(moved, points)
        self.assertEqual(history[0]["violations"], 0)

    def test_lattice_pushes_violations_out(self):
        rng = np.random.default_rng(3)
        body = np.array([[-1, -1, 0], [1, -1, 0], [1, 1, 0], [-1, 1, 0]], float)
        faces = np.array([[0, 1, 2], [0, 2, 3]])
        points = np.c_[rng.uniform(-0.2, 0.2, (60, 2)), np.full(60, 0.002)]
        moved, history, signed, _ = fit_math.lattice_inflate(points, np.ones(60, bool), body, faces, 0.01,
                                                             iterations=30, fade=0.05)
        self.assertLess(history[-1]["violations"], history[0]["violations"])
        self.assertTrue(np.all(moved[:, 2] > points[:, 2]))

    def test_generation_pose_inverts_proxy_transforms_per_bone(self):
        transforms = {name: np.eye(4) for name in fit_math.PROXY}
        transforms["fa_L"] = fit_math.segment_transform(np.array([0, 0, 1.0]), np.array([0.5, 0, 0.5]),
                                                        np.array([0, 0, 1.0]), np.array([0, 0, 0.4]))
        bind_point = np.array([[0.0, 0.0, 0.7]])
        posed = fit_math.pose_weighted(bind_point, np.array([[1.0, 0.0]]), ["lforearm_g", "torso_g"], transforms)
        np.testing.assert_allclose((transforms["fa_L"] @ np.r_[posed[0], 1])[:3], bind_point[0], atol=1e-12)
        unchanged = fit_math.pose_weighted(bind_point, np.array([[0.0, 1.0]]), ["lforearm_g", "torso_g"], transforms)
        np.testing.assert_allclose(unchanged, bind_point)
        frames = fit_math.generation_pose_frames({"lforearm_g": np.eye(4), "pelvis_g": np.eye(4)}, transforms)
        np.testing.assert_allclose(frames["lforearm_g"], np.linalg.inv(transforms["fa_L"]))
        np.testing.assert_allclose(frames["pelvis_g"], np.eye(4))

    def test_lattice_stops_when_violations_plateau(self):
        body = np.array([[-1, -1, 0], [1, -1, 0], [1, 1, 0], [-1, 1, 0]], float)
        faces = np.array([[0, 1, 2], [0, 2, 3]])
        points = np.array([[0.0, 0.0, 0.002]])
        _, history, _, _ = fit_math.lattice_inflate(points, np.array([True]), body, faces, 0.01, iterations=30,
                                                   fade=1e6, min_improvement=0.5)
        self.assertTrue(any(row.get("stoppedEarly") for row in history))
        self.assertLess(len(history), 10)


class ComparisonTests(unittest.TestCase):
    def test_nearest_matches_reordered_points(self):
        reference = np.random.default_rng(1).uniform(-1, 1, (50, 3))
        order = np.random.default_rng(2).permutation(50)
        index, gap = nearest(reference, reference[order] + 1e-6)
        np.testing.assert_array_equal(index, order)
        self.assertLess(gap.max(), 1e-5)

    def test_smoothing_edges_ignore_renumbering(self):
        verts = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [1, 1, 0]], float)
        left = np.array([[0, 1, 2, 1, 0, 0, 0, 0], [1, 3, 2, 1, 0, 0, 0, 0]])
        renumbered = left.copy()
        renumbered[:, 3] = 4
        hard = left.copy()
        hard[1, 3] = 2
        self.assertEqual(smoothing_edges(left, verts, renumbered, verts), 0)
        self.assertEqual(smoothing_edges(left, verts, hard, verts), 1)

    def test_tolerances_use_measured_or_representation_bound(self):
        report = {"kind": "srn-robe-model-comparison", "missingNodes": [], "kindChanges": [], "parentChanges": [],
                  "maximumBindTranslationError": 1e-5, "maximumBindRotationError": 0.0,
                  "meshes": [{"maximumPositionError": 1e-5, "maximumWeightError": 0.001,
                              "sampledDeformation": {"maximumDisplacementError": 0.0014}}]}
        worst = measure([report])
        self.assertAlmostEqual(max(2 * worst["deformation"], BOUNDS["deformation"]), 0.0028)
        broken = dict(report, missingNodes=["torso_g"])
        with self.assertRaises(ValueError):
            measure([broken])

    def test_donor_cache_key_tracks_inputs_and_samples(self):
        class Stub:
            pass
        with tempfile.TemporaryDirectory() as folder:
            for name in ("pmh0_robe004", "pmh0", "pmh0_chest001"):
                (Path(folder) / (name + ".mdl")).write_text(name, encoding="ascii")
            donor, body = Stub(), Stub()
            donor.path, donor.chain = Path(folder) / "pmh0_robe004.mdl", ["pmh0_robe004", "pmh0"]
            body.directory, body.prefix, body.parts = folder, "pmh0", {"chest": {}}
            samples = [{"clip": "walk", "time": 0.0}]
            first = donor_cache_key(donor, body, samples)
            self.assertEqual(first, donor_cache_key(donor, body, samples))
            self.assertNotEqual(first, donor_cache_key(donor, body, [{"clip": "walk", "time": 0.5}]))
            (Path(folder) / "pmh0.mdl").write_text("changed", encoding="ascii")
            self.assertNotEqual(first, donor_cache_key(donor, body, samples))


class MeshyPolicyTests(unittest.TestCase):
    def request(self, folder, **payload):
        image = Path(folder) / "reference.png"
        image.write_bytes(b"png")
        base = {"image_url": str(image), "should_texture": True, "enable_pbr": True, "texture_resolution": "4k",
                "pose_mode": "a-pose", "target_formats": ["glb"]}
        base.update(payload)
        return {"requestId": "r1", "outfit": "workwear", "operation": "image-to-3d", "estimatedCredits": 30,
                "inputs": [pin(image)], "payload": base}

    def test_generation_requires_textured_4k_a_pose(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertIn("--pose-mode", validate_request(self.request(folder)))
            with self.assertRaises(ValueError):
                validate_request(self.request(folder, texture_resolution="2k"))

    def test_remesh_respects_face_budget(self):
        request = {"requestId": "m1", "outfit": "workwear", "operation": "remesh", "estimatedCredits": 5,
                   "inputs": [], "payload": {"input_task_id": "t", "topology": "triangle", "target_polycount": 150000}}
        with self.assertRaises(ValueError):
            validate_request(request)

    def test_session_enforces_cap_approval_and_single_open_job(self):
        with tempfile.TemporaryDirectory() as folder:
            session = Session.create(Path(folder) / "session", 40, ["workwear"])
            request = self.request(folder)
            request_file = Path(folder) / "request.json"
            request_file.write_text(json.dumps(request))
            with self.assertRaises(ValueError):
                session.reserve(request, pin(request_file), None)
            approval = Path(folder) / "approval.json"
            approval.write_text("{}")
            session.reserve(request, pin(request_file), pin(approval))
            second = dict(request, requestId="r2", operation="remesh", estimatedCredits=5)
            with self.assertRaises(ValueError):
                session.reserve(second, pin(request_file), None)
            session.append("settled", requestId="r1", status="SUCCEEDED", credits=30)
            with self.assertRaises(ValueError):
                session.reserve(dict(second, estimatedCredits=15), pin(request_file), None)
            self.assertEqual(session.committed(), 30)


if __name__ == "__main__":
    unittest.main()
