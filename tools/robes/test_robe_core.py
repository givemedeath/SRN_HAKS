"""Synthetic-fixture tests for robe weight, ASCII skin, mesh and skinning helpers."""
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mdl_ascii
import lbs
from mesh_ops import geodesic_labels, islands, neighbours, slice_loops, weld_ids
from robe_weights import from_pairs, limit_and_normalize, to_pairs, validate
from stock_body import closest_on_triangles

SKIN_MODEL = """#MAXMODEL ASCII
newmodel probe
setsupermodel probe NULL
classification character
setanimationscale 1.0
beginmodelgeom probe
node dummy probe
  parent NULL
endnode
node dummy rootdummy
  parent probe
  position 0.0 0.0 1.0
  orientation 0.0 0.0 0.0 0.0
endnode
node dummy upper
  parent rootdummy
  position 0.0 0.0 0.5
  orientation 0.0 0.0 0.0 0.0
endnode
node skin cloth
  parent probe
  position 0.0 0.0 0.0
  orientation 0.0 0.0 0.0 0.0
  bitmap probe_tex
  verts 3
    0.0 0.0 1.0
    1.0 0.0 1.5
    0.0 1.0 2.0
  tverts 3
    0.0 0.0 0.0
    1.0 0.0 0.0
    0.0 1.0 0.0
  faces 1
    0 1 2 1 0 1 2 0
  weights 3
    rootdummy 1.0
    rootdummy 0.5 upper 0.5
    upper 1.0
endnode
endmodelgeom probe
donemodel probe
"""


class WeightTests(unittest.TestCase):
    def test_limit_keeps_four_largest_and_normalizes(self):
        result = limit_and_normalize(np.array([[5, 4, 3, 2, 1.0]]), 4, 0.001)
        self.assertEqual(int((result > 0).sum()), 4)
        self.assertAlmostEqual(float(result.sum()), 1.0)
        self.assertEqual(float(result[0, 4]), 0.0)

    def test_unweighted_vertex_rejected(self):
        with self.assertRaises(ValueError):
            limit_and_normalize(np.array([[0.0, 0.0]]))

    def test_validate_flags_invalid_bones_and_limits(self):
        matrix, bones = from_pairs([[("a", 0.5), ("b", 0.4)], [("ghost", 1.0)]])
        report = validate(matrix, bones, ["a", "b"], sum_tolerance=0.01, bone_limit=2)
        self.assertFalse(report["pass"])
        self.assertEqual(report["invalidBones"], ["ghost"])
        self.assertEqual(report["verticesOverSumTolerance"], 1)

    def test_pairs_round_trip(self):
        matrix, bones = from_pairs([[("a", 0.25), ("b", 0.75)]])
        self.assertEqual(to_pairs(matrix, bones)[0][0], ("b", 0.75))


class AsciiTests(unittest.TestCase):
    def test_skin_node_round_trip(self):
        model = mdl_ascii.parse(SKIN_MODEL)
        again = mdl_ascii.parse(mdl_ascii.dumps(model))
        self.assertEqual(again.names(), model.names())
        cloth = again.node("cloth")
        self.assertEqual(cloth.kind, "skin")
        self.assertEqual(cloth.arrays["weights"][1], [("rootdummy", 0.5), ("upper", 0.5)])
        np.testing.assert_allclose(cloth.arrays["verts"], model.node("cloth").arrays["verts"])

    def test_bind_frames_compose_parents(self):
        frames = mdl_ascii.bind_frames(mdl_ascii.parse(SKIN_MODEL))
        np.testing.assert_allclose(frames["upper"][:3, 3], [0, 0, 1.5])

    def test_write_refuses_overwrite(self):
        model = mdl_ascii.parse(SKIN_MODEL)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "probe.mdl"
            mdl_ascii.write(path, model)
            with self.assertRaises(FileExistsError):
                mdl_ascii.write(path, model)


class SkinningTests(unittest.TestCase):
    def setUp(self):
        self.rig = lbs.Rig.__new__(lbs.Rig)
        self.rig.model = mdl_ascii.parse(SKIN_MODEL)
        self.rig.bind = mdl_ascii.bind_frames(self.rig.model)

    def test_bind_frames_reproduce_rest_positions(self):
        node = self.rig.model.node("cloth")
        np.testing.assert_allclose(lbs.skin(self.rig, node, self.rig.bind), lbs.bind_world(self.rig, node))

    def test_translated_bone_moves_weighted_share(self):
        node = self.rig.model.node("cloth")
        frames = dict(self.rig.bind)
        moved = frames["upper"].copy()
        moved[:3, 3] += [0, 0, 0.2]
        frames["upper"] = moved
        posed = lbs.skin(self.rig, node, frames)
        np.testing.assert_allclose(posed[:, 2] - lbs.bind_world(self.rig, node)[:, 2], [0, 0.1, 0.2])


class MeshTests(unittest.TestCase):
    def two_squares(self):
        square = np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]], float)
        verts = np.vstack([square, square + [3, 0, 0]])
        tris = np.array([[0, 1, 2], [0, 2, 3], [4, 5, 6], [4, 6, 7]])
        return verts, tris

    def test_weld_and_islands(self):
        verts, tris = self.two_squares()
        self.assertEqual(len(np.unique(weld_ids(np.vstack([verts, verts[:1]])))), 8)
        labels, _ = islands(verts, tris)
        self.assertEqual(len(np.unique(labels)), 2)

    def test_slice_counts_separate_components(self):
        verts, tris = self.two_squares()
        loops = slice_loops(verts, tris, 0, 0.5)
        self.assertEqual(len(loops), 1)
        self.assertEqual(len(slice_loops(np.vstack([verts]), tris, 1, 0.5)), 2)

    def test_geodesic_labels_follow_connectivity(self):
        verts, tris = self.two_squares()
        rows, cols = neighbours(tris, len(verts))
        labels, distance = geodesic_labels(verts, rows, cols, [np.array([0]), np.array([4])])
        self.assertTrue(np.all(labels[:4] == 0) and np.all(labels[4:] == 1))
        self.assertAlmostEqual(float(distance[2]), np.sqrt(2))

    def test_closest_point_regions_and_sides(self):
        verts = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], float)
        faces = np.array([[0, 1, 2]])
        points = np.array([[0.2, 0.2, 0.5], [0.2, 0.2, -0.5], [2.0, -1.0, 0.0]])
        closest, distance, _, side = closest_on_triangles(points, verts, faces)
        np.testing.assert_allclose(distance[:2], [0.5, 0.5])
        np.testing.assert_allclose(side[:2], [1, -1])
        np.testing.assert_allclose(closest[2], [1, 0, 0])



class RigSourceTests(unittest.TestCase):
    def test_rig_pins_the_bytes_of_every_model_read(self):
        import hashlib
        with tempfile.TemporaryDirectory() as folder:
            model, base = Path(folder) / "probe.mdl", Path(folder) / "base.mdl"
            model.write_text(SKIN_MODEL, encoding="cp1252")
            base.write_text(SKIN_MODEL.replace("probe", "base"), encoding="cp1252")
            rig = lbs.Rig(model, ["probe", "base"], folder)
            self.assertEqual([Path(s["path"]).name for s in rig.sources], ["probe.mdl", "base.mdl"])
            self.assertEqual(rig.sources[1]["sha256"], hashlib.sha256(base.read_bytes()).hexdigest())



class ParserGuardTests(unittest.TestCase):
    def test_unknown_counted_field_is_rejected(self):
        text = SKIN_MODEL.replace("  bitmap probe_tex\n", "  bitmap probe_tex\n  aabb 2\n    0.0 0.0 0.0 1.0 1.0 1.0 -1\n    0.0 0.0 0.0 1.0 1.0 1.0 0\n")
        with self.assertRaises(ValueError):
            mdl_ascii.parse(text)

class SharedCorrectionTests(unittest.TestCase):
    def test_rigid_hands_bind_glove_vertices_to_the_hand_past_the_band(self):
        from robe_weights import limb_corrections
        bones = ["torso_g", "lbicep_g", "lforearm_g", "lhand_g", "rhand_g"]
        points = np.array([[-0.5, 0, 1.0], [-0.52, 0, 1.0], [-0.6, 0, 1.0]])  # before, inside, past the wrist band
        weights = np.array([[0, 0, 1.0, 0, 0], [0, 0, 0.6, 0.4, 0], [0, 0, 0.5, 0.5, 0]])
        joints = {"wristL": [-0.5, 0, 1.0], "fingertipL": [-0.7, 0, 1.0], "wristR": [0.5, 0, 1.0], "fingertipR": [0.7, 0, 1.0]}
        counts = limb_corrections(weights, points, np.array([1, 1, 1]), bones, {"rigidHands": {"wristBand": 0.04}}, joints)
        np.testing.assert_allclose(weights[0], [0, 0, 1, 0, 0])
        np.testing.assert_allclose(weights[1], [0, 0, 0.3, 0.7, 0])
        np.testing.assert_allclose(weights[2], [0, 0, 0, 1, 0])
        self.assertEqual((counts["rigidHandL"], counts["wristBandL"]), (1, 1))

    def test_skin_colour_rule(self):
        from robe_common import skin_colour
        rgb = np.array([[0.8, 0.6, 0.45], [0.5, 0.5, 0.5], [0.2, 0.3, 0.6], [0.05, 0.03, 0.02]])
        self.assertEqual(skin_colour(rgb).tolist(), [True, False, False, False])

    def test_closest_point_chunking_does_not_change_results(self):
        rng = np.random.default_rng(3)
        verts = rng.normal(size=(30, 3))
        faces = rng.integers(0, 30, size=(40, 3))
        faces = faces[(faces[:, 0] != faces[:, 1]) & (faces[:, 1] != faces[:, 2]) & (faces[:, 0] != faces[:, 2])]
        points = rng.normal(size=(50, 3))
        whole = closest_on_triangles(points, verts, faces, chunk=50)
        small = closest_on_triangles(points, verts, faces, budget=len(faces) * 24 * 3)  # three points per chunk
        for left, right in zip(whole, small):
            np.testing.assert_allclose(left, right)

if __name__ == "__main__":
    unittest.main()
