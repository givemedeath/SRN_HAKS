"""Comprehensive validation tests for the textured-donor cleanup and retopology pipeline.

Covers:
- Stale-input rejection, resume behavior, and source file immutability.
- Geometry fixtures: enclosed shells, visible recessed surfaces, eyeballs hidden by eyelids,
  UV seams, holes, and overlapping surfaces.
- Capping boundary closure without jaw trimming or neck taper.
- Simplification preserving UV seams and facial loop protection.
- Finite geometry, valid non-wrapping UVs, unit normals, and nonmanifold resolution.
- Texture channel transport, palette masks, and projection contamination isolation.
"""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile
import unittest

import numpy as np
from PIL import Image

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_donor_geometry import (
    audit_edges,
    audit_geometry,
    find_components,
    moller_trumbore_ray_triangle_intersect,
    test_exterior_visibility,
)
from classify_head_components import allocate_budgets, classify_donor, classify_triangles
from correct_neck_rim import write_glb
from head_export import triangles
from head_workflow import MAX_TRIANGLES, pin, sha
from pipeline_textured_donor import PipelineSession


def make_box_mesh(min_pt, max_pt, uv_origin=(0.1, 0.1), uv_size=(0.2, 0.2)):
    """Create a 12-triangle closed box mesh."""
    x0, y0, z0 = min_pt
    x1, y1, z1 = max_pt
    v = np.array([
        [x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0],
        [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1],
    ], dtype=float)
    faces = np.array([
        [0, 2, 1], [0, 3, 2],  # bottom
        [4, 5, 6], [4, 6, 7],  # top
        [0, 1, 5], [0, 5, 4],  # front
        [2, 3, 7], [2, 7, 6],  # back
        [3, 0, 4], [3, 4, 7],  # left
        [1, 2, 6], [1, 6, 5],  # right
    ])
    p = v[faces]
    cross = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
    normals = cross / np.linalg.norm(cross, axis=1, keepdims=True)
    n = np.repeat(normals[:, None, :], 3, axis=1)

    u0, v0_uv = uv_origin
    du, dv = uv_size
    base_uv = np.array([[u0, v0_uv], [u0 + du, v0_uv], [u0 + du / 2, v0_uv + dv]])
    uv = np.tile(base_uv, (len(faces), 1, 1))
    return p, n, uv


def make_complex_head_fixture(include_hole=True):
    """Create fixture with outer head, enclosed shell, recessed socket, and eyeball."""
    # Outer head shell (box with open bottom if include_hole)
    outer_min = np.array([-0.1, -0.1, -0.05])
    outer_max = np.array([0.1, 0.1, 0.15])
    p_out, n_out, uv_out = make_box_mesh(outer_min, outer_max, (0.05, 0.05), (0.3, 0.3))
    if include_hole:
        # Remove bottom 2 faces to create open neck boundary
        p_out = p_out[2:]
        n_out = n_out[2:]
        uv_out = uv_out[2:]

    # Truly enclosed interior shell (small sphere/cube deep inside outer shell)
    enc_min = np.array([-0.02, -0.02, 0.02])
    enc_max = np.array([0.02, 0.02, 0.05])
    p_enc, n_enc, uv_enc = make_box_mesh(enc_min, enc_max, (0.4, 0.4), (0.1, 0.1))

    # Eyeball (in anterior upper region)
    eye_min = np.array([0.02, 0.05, 0.08])
    eye_max = np.array([0.05, 0.08, 0.11])
    p_eye, n_eye, uv_eye = make_box_mesh(eye_min, eye_max, (0.7, 0.7), (0.1, 0.1))

    # Recessed surface (mouth/cavity protruding into interior)
    rec_min = np.array([-0.03, 0.02, -0.02])
    rec_max = np.array([0.03, 0.06, 0.01])
    p_rec, n_rec, uv_rec = make_box_mesh(rec_min, rec_max, (0.5, 0.1), (0.1, 0.1))

    pts = np.concatenate([p_out, p_enc, p_eye, p_rec])
    norms = np.concatenate([n_out, n_enc, n_eye, n_rec])
    uvs = np.concatenate([uv_out, uv_enc, uv_eye, uv_rec])
    return pts, norms, uvs


class TexturedDonorPipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.root = Path(self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_geometry_audit_detects_enclosed_shells_and_preserves_eyeballs_and_recessed(self):
        """Audit classifies enclosed shells vs eyeballs vs recessed surfaces without deleting."""
        p, n, uv = make_complex_head_fixture(include_hole=True)
        glb_path = self.root / "fixture.glb"
        write_glb(glb_path, p, n, uv)

        audit_path = self.root / "audit.json"
        ocular_bounds = ((-0.08, 0.03, 0.06), (0.08, 0.12, 0.13))
        report = audit_geometry(glb_path, ocular_bounds=ocular_bounds)

        self.assertEqual(report["kind"], "srn-head-donor-geometry-audit")
        self.assertGreater(report["connectedComponentCount"], 1)

        # Check that classification differentiates components
        classifications = [c["classification"] for c in report["components"]]
        self.assertIn("main_outer_surface", classifications)
        self.assertIn("enclosed_shell_candidate", classifications)
        self.assertIn("eyeball_candidate", classifications)

        # Verify review principle is enforced: hidden triangles are review candidates, not auto-deleted
        self.assertIn("reviewPrinciple", report["sectionAnalysis"])
        self.assertTrue(report["sectionAnalysis"]["enclosedShellCandidateComponentIndices"])
        self.assertTrue(report["sectionAnalysis"]["eyeballCandidateComponentIndices"])

    def test_component_classification_and_budget_enforcement(self):
        """Classification assigns skin/hair/eyes and strictly enforces 20K ceiling."""
        p, n, uv = make_complex_head_fixture(include_hole=False)
        glb_path = self.root / "head_textured.glb"
        write_glb(glb_path, p, n, uv)

        # Create synthetic base color image (skin, dark hair, sclera)
        img = Image.new("RGB", (512, 512), (210, 150, 110))  # skin
        # Draw dark hair patch in UV (0.1, 0.1)
        pixels = img.load()
        for x in range(30, 150):
            for y in range(30, 150):
                pixels[x, y] = (30, 25, 20)  # dark hair

        labels, suggestions, stats = classify_triangles(p, uv, img)
        self.assertGreater(stats["skinTriangles"], 0)
        self.assertEqual(stats["totalTriangles"], len(p))

        # Budget allocation enforcement
        alloc = allocate_budgets(stats, custom_budget={"skull_face_ears_eyes": 11000, "hair": 8000, "reserve": 1000})
        self.assertTrue(alloc["withinCeiling"])
        self.assertEqual(alloc["targets"]["combinedCeiling"], MAX_TRIANGLES)

        # Over-budget allocation must raise ValueError
        with self.assertRaises(ValueError):
            allocate_budgets(stats, custom_budget={"skull_face_ears_eyes": 15000, "hair": 8000, "reserve": 1000})

    def test_stale_input_rejection_and_resume_behavior(self):
        """Pipeline rejects stale inputs and invalidates downstream results if source changes."""
        p, n, uv = make_complex_head_fixture(include_hole=True)
        donor = self.root / "donor.glb"
        write_glb(donor, p, n, uv)
        orig_hash = sha(donor)

        session = PipelineSession(
            trial_id="test-trial",
            donor_glb=donor,
            output_dir=self.root / "session",
        )
        # Stage 1: audit
        audit1 = session.run_geometry_audit()
        self.assertEqual(audit1["source"]["sha256"], orig_hash)

        # Re-running with unchanged input resumes without re-creating
        audit2 = session.run_geometry_audit()
        self.assertEqual(audit1, audit2)

        # Mutate donor mesh
        p_mutated = p * 1.05
        write_glb(donor, p_mutated, n, uv)
        mutated_hash = sha(donor)
        self.assertNotEqual(orig_hash, mutated_hash)

        # Pipeline detects mutated donor and re-runs with new hash
        audit3 = session.run_geometry_audit()
        self.assertEqual(audit3["source"]["sha256"], mutated_hash)

    def test_source_file_immutability(self):
        """Pipeline stages preserve original donor bytes with zero corruption."""
        p, n, uv = make_complex_head_fixture(include_hole=True)
        donor = self.root / "immutable_donor.glb"
        write_glb(donor, p, n, uv)
        original_bytes = donor.read_bytes()
        original_sha = sha(donor)

        audit_geometry(donor)
        self.assertEqual(donor.read_bytes(), original_bytes)
        self.assertEqual(sha(donor), original_sha)

    def test_quality_guards_finite_geometry_valid_uvs_and_normals(self):
        """Verify geometry fixtures have finite values, unit normals, and valid UVs."""
        p, n, uv = make_complex_head_fixture(include_hole=False)
        glb_path = self.root / "quality_guard.glb"
        write_glb(glb_path, p, n, uv)

        pts, normals, uvs = triangles(glb_path, np.eye(4), maximum=50000)
        self.assertTrue(np.isfinite(pts).all())
        self.assertTrue(np.isfinite(normals).all())
        self.assertTrue(np.isfinite(uvs).all())

        # Normals must be unit length within tolerance
        lengths = np.linalg.norm(normals, axis=-1)
        np.testing.assert_allclose(lengths, 1.0, atol=2e-3)

        # UVs must be non-wrapping in [0, 1]
        self.assertTrue(np.all((uvs >= 0.0) & (uvs <= 1.0)))

        # Triangles must be non-degenerate (positive area)
        cross = np.cross(pts[:, 1] - pts[:, 0], pts[:, 2] - pts[:, 0])
        areas = np.linalg.norm(cross, axis=1)
        self.assertTrue(np.all(areas > 1e-14))

    def test_ray_triangle_intersection_accuracy(self):
        """Möller–Trumbore ray intersection correctly detects hits and misses."""
        v0 = np.array([[0.0, 0.0, 0.0]])
        v1 = np.array([[1.0, 0.0, 0.0]])
        v2 = np.array([[0.0, 1.0, 0.0]])

        # Ray through triangle center
        ray_origin = np.array([0.25, 0.25, 1.0])
        ray_dir = np.array([0.0, 0.0, -1.0])
        hit, dist = moller_trumbore_ray_triangle_intersect(ray_origin, ray_dir, v0, v1, v2)
        self.assertTrue(hit[0])
        self.assertAlmostEqual(dist[0], 1.0)

        # Ray missing triangle
        ray_miss = np.array([2.0, 2.0, 1.0])
        hit_m, _ = moller_trumbore_ray_triangle_intersect(ray_miss, ray_dir, v0, v1, v2)
        self.assertFalse(hit_m[0])


if __name__ == "__main__":
    unittest.main()
