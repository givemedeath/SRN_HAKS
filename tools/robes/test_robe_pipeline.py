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
        flipped = fit_math.rotation_between(np.array([1.0, 0, 0]), np.array([-1.0, 0, 0]))
        np.testing.assert_allclose(flipped @ [1, 0, 0], [-1, 0, 0], atol=1e-12)
        self.assertAlmostEqual(np.linalg.det(flipped), 1.0)

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

    def test_dual_quaternion_blend_keeps_joint_volume(self):
        quarter = np.eye(4)
        quarter[:3, :3] = fit_math.rotation_between(np.array([1.0, 0, 0]), np.array([0, 1.0, 0]))
        point, weights = np.array([[1.0, 0.0, 0.0]]), np.array([[0.5, 0.5]])
        linear = (0.5 * np.eye(4) + 0.5 * quarter) @ np.r_[point[0], 1]
        dq = fit_math.blend_dual_quaternion(point, weights, [np.eye(4), quarter])
        self.assertAlmostEqual(np.linalg.norm(linear[:3]), np.sqrt(0.5), places=6)  # averaging collapses
        self.assertAlmostEqual(np.linalg.norm(dq[0]), 1.0, places=6)               # rotation blend does not
        shifted = np.eye(4)
        shifted[:3, 3] = [0.1, -0.2, 0.3]
        stretched = fit_math.segment_transform(np.zeros(3), np.array([0, 0, 1.0]), np.zeros(3), np.array([0, 0, 1.5]))
        for matrix in (shifted, stretched):
            pts = np.random.default_rng(4).normal(size=(5, 3))
            np.testing.assert_allclose(fit_math.blend_dual_quaternion(pts, np.ones((5, 1)), [matrix]),
                                       (np.c_[pts, np.ones(5)] @ matrix.T)[:, :3], atol=1e-9)

    def test_visible_parts_follow_hide_flags(self):
        hide = {column: 1 for column in fit_math.HIDE_PARTS}
        hide.update(HIDENECK=0, HIDEHEAD=0)
        self.assertEqual(fit_math.visible_parts(hide), ["neck", "head"])

    def test_lattice_moves_only_movable_points(self):
        body = np.array([[-1, -1, 0], [1, -1, 0], [1, 1, 0], [-1, 1, 0]], float)
        faces = np.array([[0, 1, 2], [0, 2, 3]])
        points = np.array([[0.0, 0.0, 0.002], [0.01, 0.0, 0.002]])
        moved, _, _, _ = fit_math.lattice_inflate(points, np.array([True, True]), body, faces, 0.01, iterations=10,
                                                  fade=0.05, movable=np.array([True, False]))
        self.assertGreater(moved[0, 2], points[0, 2])
        np.testing.assert_allclose(moved[1], points[1])

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

    def test_nearest_handles_points_far_from_every_cell(self):
        reference = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 2.0, 0.0]])
        index, gap = nearest(reference, np.array([[0.9, 0.05, 0.0], [0.001, 0.0, 0.0]]))
        self.assertEqual(index.tolist(), [1, 0])
        np.testing.assert_allclose(gap, [np.hypot(0.1, 0.05), 0.001])

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
        report = {"kind": "srn-robe-model-comparison", "missingNodes": [], "addedNodes": [], "kindChanges": [],
                  "parentChanges": [],
                  "maximumBindTranslationError": 1e-5, "maximumBindRotationError": 0.0,
                  "meshes": [{"maximumPositionError": 1e-5, "maximumWeightError": 0.001,
                              "sampledDeformation": {"maximumDisplacementError": 0.0014}}]}
        worst = measure([report])
        self.assertAlmostEqual(max(2 * worst["deformation"], BOUNDS["deformation"]), 0.0028)
        dropped = dict(report, meshes=[dict(report["meshes"][0], faces=[12, 11])])
        mesh = report["meshes"][0]
        lossy = [dict(report, meshes=[dict(mesh, maximumCornerPositionError=0.01)]),
                 dict(report, meshes=[dict(mesh, maximumReferenceFaceGap=0.01)]),
                 dict(report, meshes=[dict(mesh, maximumFaceCentroidError=0.01)]),
                 dict(report, meshes=[dict(mesh, uvPresent=[True, False])]),
                 dict(report, meshes=[dict(mesh, render=["0", "1"])]),
                 dict(report, meshes=[dict(mesh, bitmap=["robe", "null"])]),
                 dict(report, header={"supermodel": ["pmh0", "pmh0"], "animationScale": ["1.0", "0.5"]})]
        measure([dict(report, header={"supermodel": ["pmh0", "PMH0"], "classification": ["character", "CHARACTER"],
                                      "animationScale": ["1", "1.0"]})])
        for broken in (dict(report, missingNodes=["torso_g"]), dict(report, addedNodes=["extra_g"]), dropped, *lossy):
            with self.assertRaises(ValueError):
                measure([broken])

    def test_verdict_rejects_added_nodes(self):
        from compare_skin_models import verdict
        report = {"missingNodes": [], "addedNodes": ["extra_g"], "kindChanges": [], "parentChanges": [],
                  "header": {"supermodel": ["pmh0", "pmh0"], "animationScale": ["1.0", "1.0"]},
                  "maximumBindTranslationError": 0.0,
                  "maximumBindRotationError": 0.0, "meshes": []}
        tolerances = {"bindTranslation": 1e-6, "bindRotation": 1e-6}
        self.assertIn("structure", str(verdict(report, tolerances)))
        self.assertNotIn("structure", str(verdict(dict(report, addedNodes=[]), tolerances)))
        mesh = {"node": "cloth", "bitmap": ["a", "a"], "uvPresent": [True, True], "maximumCornerPositionError": 0.0}
        clean = dict(report, addedNodes=[], meshes=[mesh])
        loose = {"position": 1e-5, "uv": 1e-4, "weight": 1e-3, "weightSum": 2e-3, "deformation": 1e-3, **tolerances}
        self.assertEqual(verdict(clean, loose)["failures"], [])
        self.assertIn("cloth: render state", verdict(dict(clean, meshes=[dict(mesh, render=["1", "0"])]), loose)["failures"])
        self.assertIn("cloth: UV presence", verdict(dict(clean, meshes=[dict(mesh, uvPresent=[True, False])]), loose)["failures"])
        self.assertIn("cloth: face pairing",
                      verdict(dict(clean, meshes=[dict(mesh, maximumCornerPositionError=0.01)]), loose)["failures"])

    def test_verdict_rejects_animation_header_changes(self):
        from types import SimpleNamespace
        from compare_skin_models import animation_content, verdict
        clip = "newanim pause1 pmh0_robe004\n  length 2.0\ndoneanim pause1 pmh0_robe004\n"
        left = SimpleNamespace(animations=[{"name": "pause1", "model": "pmh0_robe004", "text": clip}])
        renamed = SimpleNamespace(animations=[{"name": "pause1", "model": "pmh0_robe052",
                                               "text": clip.replace("004", "052").replace("2.0", "2.00000")}])
        self.assertEqual(animation_content(left), animation_content(renamed))
        report = {"missingNodes": [], "addedNodes": [], "kindChanges": [], "parentChanges": [],
                  "header": {"supermodel": ["pmh0", "pmh0"], "animationScale": ["1.0", "1.0"],
                             "animationContent": [animation_content(left), animation_content(renamed)]},
                  "maximumBindTranslationError": 0.0, "maximumBindRotationError": 0.0, "meshes": []}
        tolerances = {"bindTranslation": 1e-6, "bindRotation": 1e-6}
        self.assertEqual(verdict(report, tolerances)["failures"], [])
        scaled = dict(report, header=dict(report["header"], animationScale=["1.0", "0.9"]))
        self.assertIn("animation scale", verdict(scaled, tolerances)["failures"])
        dropped = dict(report, header=dict(report["header"], animationContent=[animation_content(left), []]))
        self.assertIn("local animations", verdict(dropped, tolerances)["failures"])
        twice = SimpleNamespace(animations=left.animations * 2)
        self.assertNotEqual(animation_content(twice), animation_content(left))
        reclassed = dict(report, header=dict(report["header"], classification=["character", "EFFECT"]))
        self.assertIn("classification", verdict(reclassed, tolerances)["failures"])
        self.assertNotIn("classification", verdict(dict(report, header=dict(
            report["header"], classification=["character", "CHARACTER"])), tolerances)["failures"])

    def test_reference_coverage_sees_a_dropped_opposite_winding_face(self):
        from compare_skin_models import reference_coverage
        front = np.array([[0.0, 0, 0], [1, 0, 0], [0, 1, 0]])
        back = front[::-1].copy()
        other = front + [5.0, 0, 0]
        reference = np.stack([front, back, other])
        self.assertEqual(reference_coverage(reference, np.stack([back, other, front])), 0.0)
        # Same face count and centroids, but the back face was duplicated as a front face.
        self.assertGreater(reference_coverage(reference, np.stack([front, front, other])), 1e-3)
        # Distinct coplanar triangles with one centroid and one normal still need their own corners.
        first = np.array([[0.0, 0, 0], [3, 0, 0], [0, 3, 0]])
        second = np.array([[2.0, 0, 0], [2, 3, 0], [-1, 0, 0]])
        self.assertEqual(reference_coverage(np.stack([first, second]), np.stack([second, first])), 0.0)
        self.assertGreater(reference_coverage(np.stack([first, second]), np.stack([first, first])), 1e-3)

    def test_reverse_weight_error_needs_both_seam_copies(self):
        from compare_skin_models import reverse_weight_error
        reference = np.array([[0.0, 0, 0], [0.0, 0, 0], [1.0, 0, 0]])
        reference_weights = np.array([[1.0, 0], [0.0, 1], [1.0, 0]])
        both = np.array([[0.0, 0, 0], [0.0, 0, 0], [1.0, 0, 0]])
        merged = np.array([[0.0, 0, 0], [1.0, 0, 0]])
        self.assertEqual(reverse_weight_error(reference, both, reference_weights, reference_weights[[1, 0, 2]], [0, 1, 2]), 0.0)
        self.assertEqual(reverse_weight_error(reference, merged, reference_weights, reference_weights[[0, 2]], [0, 0, 1]), 1.0)

    def test_image_edit_collects_images_and_models_need_glb(self):
        import meshy_robe
        from unittest import mock
        for resource, name, ok in (("image-to-image", "edit.png", True), ("image-to-image", "model.glb", False),
                                   ("remesh", "model.glb", True), ("remesh", "edit.png", False)):
            with tempfile.TemporaryDirectory() as folder:
                session = Session.create(Path(folder) / "session", 40, ["workwear"])
                task = Path(folder) / "task.json"
                task.write_text("{}")
                session.append("submitted", requestId="r1", taskId="t1", resource=resource, inputsUnchanged=True)
                session.append("settled", requestId="r1", taskId="t1", resource=resource, status="SUCCEEDED",
                               credits=9, task=pin(task))
                bank = Path(folder) / "bank"

                def download(_binding, _arguments, _out, bank=bank, name=name):
                    bank.mkdir()
                    (bank / name).write_bytes(b"x")
                    return 0, bank

                with mock.patch.object(meshy_robe, "invoke", download), \
                        mock.patch.object(meshy_robe, "load_binding", lambda _path: {}):
                    if ok:
                        self.assertEqual(len(meshy_robe.collect(session, "r1", "binding", Path(folder) / "op", bank)), 1)
                    else:
                        with self.assertRaises(ValueError):
                            meshy_robe.collect(session, "r1", "binding", Path(folder) / "op", bank)

    def test_invoke_pins_the_launcher_and_refuses_a_changed_binding(self):
        import meshy_robe
        from unittest import mock
        with tempfile.TemporaryDirectory() as folder:
            launcher = Path(folder) / "npm.cmd"
            launcher.write_text("v1")
            binding_file = Path(folder) / "binding.json"
            binding_file.write_text(json.dumps({"command": ["npm.cmd", meshy_robe.CLI_PACKAGE], "workspace": folder}))
            binding = meshy_robe.load_binding(binding_file)

            def swap(*_args, **_kwargs):
                binding_file.write_text("{}")
                return mock.Mock(returncode=0)

            with mock.patch.object(meshy_robe.shutil, "which", lambda _name: str(launcher)), \
                    mock.patch.object(meshy_robe.subprocess, "run", swap):
                with self.assertRaises(ValueError):
                    meshy_robe.invoke(binding, ["status"], Path(folder) / "op")
            operation = json.loads((Path(folder) / "op" / "operation.json").read_text())
            self.assertIn("binding.json", operation["launchInputsChanged"])
            self.assertEqual(Path(operation["executable"]["path"]).name, "npm.cmd")
            with mock.patch.object(meshy_robe.shutil, "which", lambda _name: None):
                with self.assertRaises(ValueError):
                    meshy_robe.invoke(binding, ["status"], Path(folder) / "op2")

    def test_review_measures_rank_compression_and_collapse(self):
        from deformation_review import measures
        calm = {"penetration": {"deepest": 0.0}, "stretch": {"maximum": 1.0}, "compression": {"minimum": 0.9},
                "collapse": {"flagged": 0}}
        crushed = dict(calm, compression={"minimum": 0.2}, collapse={"flagged": 5})
        self.assertGreater(measures(crushed)["compression"], measures(calm)["compression"])
        self.assertGreater(measures(crushed)["collapse"], measures(calm)["collapse"])

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
            import deformation_review
            from unittest import mock
            real = deformation_review.sha
            helper = str(Path(sys.modules["rig_pose_audit"].__file__))
            with mock.patch.object(deformation_review, "sha", lambda path: "changed" if str(path) == helper else real(path)):
                self.assertNotEqual(first, donor_cache_key(donor, body, samples))  # pose helper code is in the key
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

    def test_image_edit_needs_pinned_references(self):
        request = {"requestId": "e1", "outfit": "workwear", "operation": "image-to-image", "estimatedCredits": 9,
                   "inputs": [], "payload": {"ai_model": "nano-banana-pro", "prompt": "A-pose", "reference_image_urls": []}}
        with self.assertRaises(ValueError):
            validate_request(request)

    def test_model_operations_must_request_glb(self):
        base = {"requestId": "m1", "outfit": "workwear", "operation": "remesh", "estimatedCredits": 5, "inputs": [],
                "payload": {"input_task_id": "t", "topology": "triangle", "target_polycount": 20000}}
        self.assertIn("glb,fbx", validate_request(base)[validate_request(base).index("--target-formats") + 1])
        broken = dict(base, payload=dict(base["payload"], target_formats=["fbx"]))
        with self.assertRaises(ValueError):
            validate_request(broken)

    def test_derived_task_must_build_on_an_attributable_success(self):
        with tempfile.TemporaryDirectory() as folder:
            session = Session.create(Path(folder) / "session", 60, ["workwear"])
            request_file = Path(folder) / "request.json"
            request_file.write_text("{}")
            remesh = {"requestId": "m1", "outfit": "workwear", "operation": "remesh", "estimatedCredits": 5,
                      "inputs": [], "payload": {"input_task_id": "t1"}}
            with self.assertRaises(ValueError):
                session.reserve(remesh, pin(request_file), None)  # unknown task
            session.append("submitted", requestId="r0", taskId="t1", resource="image-to-3d", inputsUnchanged=False)
            session.append("settled", requestId="r0", taskId="t1", resource="image-to-3d", status="SUCCEEDED", credits=30)
            with self.assertRaises(ValueError):
                session.reserve(remesh, pin(request_file), None)  # succeeded but not attributable
            session.append("submitted", requestId="r1", taskId="t2", resource="image-to-3d", inputsUnchanged=True)
            session.append("settled", requestId="r1", taskId="t2", resource="image-to-3d", status="SUCCEEDED", credits=30)
            session.reserve(dict(remesh, payload={"input_task_id": "t2"}), pin(request_file), None)

    def test_collect_holds_the_session_lock(self):
        import meshy_robe
        with tempfile.TemporaryDirectory() as folder:
            session = Session.create(Path(folder) / "session", 40, ["workwear"])
            session.lock()
            with self.assertRaises(ValueError):
                meshy_robe.collect(session, "r1", Path(folder) / "binding.json", Path(folder) / "op", Path(folder) / "bank")
            with self.assertRaises(ValueError):
                meshy_robe.wait(session, "r1", Path(folder) / "binding.json", Path(folder) / "op2")

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

    def test_refused_submission_cannot_be_collected_and_settles_once(self):
        import meshy_robe
        from unittest import mock
        with tempfile.TemporaryDirectory() as folder:
            session = Session.create(Path(folder) / "session", 40, ["workwear"])
            request = self.request(folder)
            request_file = Path(folder) / "request.json"
            request_file.write_text(json.dumps(request))
            approval = Path(folder) / "approval.json"
            approval.write_text("{}")
            session.reserve(request, pin(request_file), pin(approval))
            session.append("submitted", requestId="r1", taskId="t1", resource="image-to-3d", inputsUnchanged=False)
            task = Path(folder) / "task.json"
            task.write_text("{}")
            session.append("settled", requestId="r1", taskId="t1", resource="image-to-3d", status="SUCCEEDED",
                           credits=30, task=pin(task))
            with mock.patch.object(meshy_robe, "invoke", side_effect=AssertionError("CLI must not run")):
                with self.assertRaises(ValueError):
                    meshy_robe.collect(session, "r1", Path(folder) / "binding.json", Path(folder) / "op", Path(folder) / "bank")
                with self.assertRaises(ValueError):
                    meshy_robe.wait(session, "r1", Path(folder) / "binding.json", Path(folder) / "op2")

    def test_dispatch_records_then_refuses_inputs_changed_during_upload(self):
        import meshy_robe
        from unittest import mock
        with tempfile.TemporaryDirectory() as folder:
            session = Session.create(Path(folder) / "session", 40, ["workwear"])
            request = self.request(folder)
            request_file = Path(folder) / "request.json"
            request_file.write_text(json.dumps(request))
            approval = Path(folder) / "approval.json"
            approval.write_text(json.dumps({"kind": "srn-robe-reference-approval", "outfit": "workwear",
                                            "request": {"sha256": meshy_robe.sha(request_file)}, "userInstruction": "go"}))
            binding = Path(folder) / "binding.json"
            binding.write_text("{}")

            def upload_swaps_image(_binding, _arguments, out):
                Path(request["payload"]["image_url"]).write_bytes(b"other")
                response = Path(out) / "stdout.json"
                response.write_text(json.dumps({"result": {"task_id": "t1"}}))
                return 0, response

            with mock.patch.object(meshy_robe, "invoke", upload_swaps_image):
                with self.assertRaises(ValueError):
                    meshy_robe.dispatch(session, request_file, binding, approval, Path(folder))
            submitted = [e for e in session.events() if e["kind"] == "submitted"]
            self.assertEqual([(e["taskId"], e["inputsUnchanged"]) for e in submitted], [("t1", False)])


if __name__ == "__main__":
    unittest.main()
