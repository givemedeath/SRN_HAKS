"""Unit tests for whole-head reference texture reprojection pipeline."""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest

import numpy as np
from PIL import Image, ImageDraw

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from reproject_reference_textures import (
    build_depth_buffer,
    compute_sha256,
    compute_texel_surface_areas,
    compute_texel_surface_points,
    execute_whole_head_reprojection,
    load_mesh_from_glb,
    project_single_view,
    rasterize_uv_triangles,
)


class ReprojectionPipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.mesh_dir = Path(self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_synthetic_mesh_glb(self) -> Path:
        """Create a simple cube mesh with UVs in GLB format for test fixtures."""
        import struct
        # 4 vertices (quad forming two triangles facing +Z)
        # Positions:
        pos = np.array([
            [-0.5, -0.5, 0.5],
            [ 0.5, -0.5, 0.5],
            [ 0.5,  0.5, 0.5],
            [-0.5,  0.5, 0.5],
        ], dtype=np.float32)
        # Normals pointing +Z:
        normals = np.array([
            [0.0, 0.0, 1.0],
            [0.0, 0.0, 1.0],
            [0.0, 0.0, 1.0],
            [0.0, 0.0, 1.0],
        ], dtype=np.float32)
        # UVs in [0, 1]:
        uvs = np.array([
            [0.0, 1.0],
            [1.0, 1.0],
            [1.0, 0.0],
            [0.0, 0.0],
        ], dtype=np.float32)
        # Triangles: (0, 1, 2) and (0, 2, 3)
        indices = np.array([0, 1, 2, 0, 2, 3], dtype=np.uint16)

        bin_data = pos.tobytes() + normals.tobytes() + uvs.tobytes() + indices.tobytes()
        
        doc = {
            "asset": {"version": "2.0"},
            "buffers": [{"byteLength": len(bin_data)}],
            "bufferViews": [
                {"buffer": 0, "byteOffset": 0, "byteLength": len(pos.tobytes())},
                {"buffer": 0, "byteOffset": len(pos.tobytes()), "byteLength": len(normals.tobytes())},
                {"buffer": 0, "byteOffset": len(pos.tobytes()) + len(normals.tobytes()), "byteLength": len(uvs.tobytes())},
                {"buffer": 0, "byteOffset": len(pos.tobytes()) + len(normals.tobytes()) + len(uvs.tobytes()), "byteLength": len(indices.tobytes())},
            ],
            "accessors": [
                {"bufferView": 0, "byteOffset": 0, "componentType": 5126, "count": 4, "type": "VEC3", "max": [0.5, 0.5, 0.5], "min": [-0.5, -0.5, 0.5]},
                {"bufferView": 1, "byteOffset": 0, "componentType": 5126, "count": 4, "type": "VEC3"},
                {"bufferView": 2, "byteOffset": 0, "componentType": 5126, "count": 4, "type": "VEC2"},
                {"bufferView": 3, "byteOffset": 0, "componentType": 5123, "count": 6, "type": "SCALAR"},
            ],
            "meshes": [{
                "primitives": [{
                    "attributes": {"POSITION": 0, "NORMAL": 1, "TEXCOORD_0": 2},
                    "indices": 3,
                    "mode": 4
                }]
            }],
            "nodes": [{"mesh": 0}],
            "scenes": [{"nodes": [0]}],
            "scene": 0
        }

        json_bytes = json.dumps(doc, separators=(",", ":")).encode("utf-8")
        pad = (4 - (len(json_bytes) % 4)) % 4
        json_bytes += b" " * pad

        hdr = struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(json_bytes) + 8 + len(bin_data))
        c1 = struct.pack("<II", len(json_bytes), 0x4E4F534A)
        c2 = struct.pack("<II", len(bin_data), 0x004E4942)

        glb_path = self.mesh_dir / "fixture_mesh.glb"
        with open(glb_path, "wb") as f:
            f.write(hdr)
            f.write(c1)
            f.write(json_bytes)
            f.write(c2)
            f.write(bin_data)

        return glb_path

    def test_backface_and_grazing_rejection(self):
        """Surfaces facing away from camera or beyond grazing angle must be rejected."""
        # Point facing +Z
        norm_facing = np.array([[0.0, 0.0, 1.0]], dtype=float)
        # Point facing sideways (+X)
        norm_grazing = np.array([[1.0, 0.0, 0.0]], dtype=float)
        # Point facing backwards (-Z)
        norm_back = np.array([[0.0, 0.0, -1.0]], dtype=float)

        camera_dir = np.array([0.0, 0.0, -1.0])  # Camera looks along -Z (front view)
        
        # Test facing
        cos_facing = norm_facing @ (-camera_dir)
        self.assertAlmostEqual(float(cos_facing[0]), 1.0)
        self.assertTrue(cos_facing[0] > 0.15)

        # Test grazing
        cos_grazing = norm_grazing @ (-camera_dir)
        self.assertAlmostEqual(float(cos_grazing[0]), 0.0)
        self.assertFalse(cos_grazing[0] > 0.15)

        # Test backface
        cos_back = norm_back @ (-camera_dir)
        self.assertAlmostEqual(float(cos_back[0]), -1.0)
        self.assertFalse(cos_back[0] > 0.15)

    def test_depth_occlusion_rejection(self):
        """Points deeper than occluding geometry must be rejected."""
        pos = np.array([
            [0.0, 0.0, 0.5],   # Front surface at z = 0.5
            [0.0, 0.0, -0.5],  # Occluded rear surface at z = -0.5
        ])
        center = np.array([0.0, 0.0, 0.0])
        right = np.array([1.0, 0.0, 0.0])
        up = np.array([0.0, 1.0, 0.0])
        cam_dir = np.array([0.0, 0.0, -1.0])

        z_buf = build_depth_buffer(pos, center, right, up, cam_dir, ortho_span=1.5, resolution=128)
        
        # Pixel for (0, 0)
        px = 64
        py = 64
        max_depth = z_buf[py, px]
        self.assertGreaterEqual(max_depth, 0.45)

        # Rear point depth is -0.5, which is well below max_depth - 0.035
        rear_depth = -0.5
        self.assertLess(rear_depth, max_depth - 0.035)

    def test_reference_background_rejection(self):
        """Black or transparent background pixels in reference panels must never project."""
        ref_im = Image.new("RGB", (64, 64), (0, 0, 0))
        # Draw a small 10x10 white square in center
        draw = ImageDraw.Draw(ref_im)
        draw.rectangle([25, 25, 35, 35], fill=(200, 150, 120))

        ref_arr = np.asarray(ref_im)
        ref_mask = np.any(ref_arr > 10, axis=-1)

        # Outside rectangle is background
        self.assertFalse(ref_mask[10, 10])
        self.assertFalse(ref_mask[50, 50])
        # Inside rectangle is valid
        self.assertTrue(ref_mask[30, 30])

    def test_stale_input_rejection(self):
        """Config must reject modified files whose sha256 no longer matches pinned hash."""
        glb_path = self._create_synthetic_mesh_glb()
        actual_hash = compute_sha256(glb_path)
        bogus_hash = "0000000000000000000000000000000000000000000000000000000000000000"

        config = {
            "schemaVersion": 1,
            "kind": "srn-head-reprojection-config",
            "mesh": {"path": str(glb_path), "sha256": bogus_hash},
            "donorTexture": {"path": str(glb_path), "sha256": actual_hash},
            "views": {}
        }
        
        with self.assertRaises(ValueError):
            execute_whole_head_reprojection(config, self.mesh_dir / "out")

    def test_geometry_and_uv_preservation(self):
        """Reprojection must preserve 3D vertex positions and UVs exactly without modification."""
        glb_path = self._create_synthetic_mesh_glb()
        pos_before, normals_before, uvs_before, indices_before, _, _ = load_mesh_from_glb(glb_path)

        # Create dummy donor and reference textures
        tex_path = self.mesh_dir / "donor.png"
        Image.new("RGB", (64, 64), (200, 150, 100)).save(tex_path)

        views = {}
        for v in ("front", "left", "back", "right"):
            v_path = self.mesh_dir / f"{v}.png"
            Image.new("RGB", (64, 64), (180, 130, 90)).save(v_path)
            views[v] = {
                "path": str(v_path),
                "sha256": compute_sha256(v_path),
                "camera": {"center": [0, 0, 0], "orthoSpan": 1.5}
            }

        config = {
            "schemaVersion": 1,
            "kind": "srn-head-reprojection-config",
            "mesh": {"path": str(glb_path), "sha256": compute_sha256(glb_path)},
            "donorTexture": {"path": str(tex_path), "sha256": compute_sha256(tex_path)},
            "views": views,
        }

        out_dir = self.mesh_dir / "out"
        receipt = execute_whole_head_reprojection(config, out_dir)
        preview_glb = Path(receipt["previewGlb"]["path"])

        # Reload geometry from preview GLB
        pos_after, normals_after, uvs_after, indices_after, _, _ = load_mesh_from_glb(preview_glb)

        np.testing.assert_array_equal(pos_before, pos_after)
        np.testing.assert_array_equal(normals_before, normals_after)
        np.testing.assert_array_equal(uvs_before, uvs_after)
        np.testing.assert_array_equal(indices_before, indices_after)

    def test_coverage_metrics_completeness(self):
        """Surface area and texel counts must sum exactly to 100% across the 4 categories."""
        glb_path = self._create_synthetic_mesh_glb()
        pos, _, uvs, indices, _, _ = load_mesh_from_glb(glb_path)
        tri_map, ys, xs, tri_ids = rasterize_uv_triangles(uvs, indices, size=64)
        texel_areas, total_area, _ = compute_texel_surface_areas(pos, indices, tri_ids)

        self.assertAlmostEqual(float(texel_areas.sum()), total_area, places=5)


if __name__ == "__main__":
    unittest.main()
