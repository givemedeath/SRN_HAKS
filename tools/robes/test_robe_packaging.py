"""Synthetic-fixture tests for robe model building, fixture packaging helpers and source references."""
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mdl_ascii
from build_robe_fixture import read_2da, renamed_model, scripts, write_2da
from build_robe_model import node_for_faces, skeleton_nodes
from prepare_materials import plt_bytes
from prepare_reference import subject_bottom
from test_robe_core import SKIN_MODEL


class ModelBuildTests(unittest.TestCase):
    def test_skeleton_keeps_complete_parent_chain_only(self):
        stock = mdl_ascii.parse(SKIN_MODEL)
        names = [node.name for node in skeleton_nodes(stock, ["upper"])]
        self.assertEqual(names, ["rootdummy", "upper"])
        with self.assertRaises(ValueError):
            skeleton_nodes(stock, ["missing_g"])

    def test_generation_rest_puts_limb_bones_at_outfit_joints(self):
        from build_robe_model import generation_rest
        import fit_math
        extra = ("node dummy lbicep_g\n  parent upper\n  position -0.2 0.0 0.3\n  orientation 0.0 0.0 0.0 0.0\nendnode\n"
                 "node skin cloth")
        stock = mdl_ascii.parse(SKIN_MODEL.replace("node skin cloth", extra, 1))
        shoulder = np.array([-0.2, 0.0, 1.8])  # rootdummy 1.0 + upper 0.5 + 0.3
        outfit_shoulder, outfit_elbow = np.array([-0.25, 0.0, 1.75]), np.array([-0.55, 0.0, 1.45])
        transforms = {name: np.eye(4) for name in fit_math.PROXY}
        transforms["ua_L"] = fit_math.segment_transform(outfit_shoulder, outfit_elbow, shoulder, shoulder - [0, 0, 0.3])
        report = {"outfitJoints": {"shoulderL": outfit_shoulder.tolist()}, "stockTargets": {"shoulderL": shoulder.tolist()}}
        rest = generation_rest(stock, ["rootdummy", "upper", "lbicep_g"], report, transforms)
        np.testing.assert_allclose(rest["lbicep_g"][:3, 3], outfit_shoulder, atol=1e-12)
        down = rest["lbicep_g"][:3, :3] @ np.array([0, 0, -1.0])  # stock arm direction carried into the A-pose
        np.testing.assert_allclose(down, (outfit_elbow - outfit_shoulder) / np.linalg.norm(outfit_elbow - outfit_shoulder),
                                   atol=1e-12)
        np.testing.assert_allclose(rest["upper"], mdl_ascii.bind_frames(stock)["upper"])

    def test_axis_angle_round_trips_mdl_orientation(self):
        from apose_skeleton import axis_angle
        from retarget import rotations
        for axis, angle in (([0, 0, 1], 0.7), ([1, 2, -0.5], 2.1), ([0, 1, 0], 0.0)):
            matrix = rotations(np.r_[axis, angle])
            np.testing.assert_allclose(rotations(axis_angle(matrix)), matrix, atol=1e-9)

    def test_node_variant_swaps_placeholders_and_adds_stock_nodes(self):
        from robe_node_variant import variant
        stock = mdl_ascii.parse(SKIN_MODEL.replace("node skin cloth", "node dummy hand\n  parent upper\n  position 0.0 0.0 -0.4\n"
                                                   "  orientation 0.0 0.0 0.0 0.0\nendnode\nnode skin cloth", 1))
        model = variant(mdl_ascii.parse(SKIN_MODEL), "probe2", "trimesh", ["hand"], stock, rename_bitmaps=False)
        kinds = {n.key: n.kind for n in model.nodes}
        self.assertEqual(kinds, {"probe2": "dummy", "rootdummy": "trimesh", "upper": "trimesh", "hand": "trimesh",
                                 "cloth": "skin"})
        reparsed = mdl_ascii.parse(mdl_ascii.dumps(model))
        self.assertEqual(reparsed.node("upper").get("render"), "0")
        np.testing.assert_allclose(mdl_ascii.bind_frames(reparsed)["hand"], mdl_ascii.bind_frames(stock)["hand"])
        self.assertEqual(reparsed.node("cloth").parent, "probe2")
        back = variant(reparsed, "probe3", "dummy", [], None, rename_bitmaps=False)
        self.assertEqual({n.kind for n in back.nodes if n.key != "cloth"}, {"dummy"})

    def test_face_groups_emit_every_face_once_and_side_skin_by_arm(self):
        from build_robe_model import face_groups
        segments = np.array([0, 0, 1, 1, 2, 2, 0])
        tris = np.array([[0, 1, 2], [2, 3, 0], [4, 5, 6], [0, 6, 1]])  # face 0: torso majority, one left-arm vertex
        skin = np.array([True, True, False, False])
        groups = {name: selected for name, selected, _ in face_groups(tris, segments, skin, "ww", "fx", "skin")}
        self.assertEqual(groups["ww_skinl"].tolist(), [True, True, False, False])
        self.assertEqual(groups["ww_armr"].tolist(), [False, False, True, False])
        self.assertEqual(groups["ww_torso"].tolist(), [False, False, False, True])
        with self.assertRaises(Exception):
            face_groups(tris, segments, np.array([False, False, False, True]), "ww", "fx", "skin")  # skin face, no arm

    def test_stock_body_records_every_model_read(self):
        from stock_body import Body
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / "probe.mdl").write_text(SKIN_MODEL, encoding="cp1252")
            part = SKIN_MODEL.replace("probe", "probe_chest001").replace("node skin cloth", "node trimesh cloth")
            (Path(folder) / "probe_chest001.mdl").write_text(part, encoding="cp1252")
            body = Body(folder, "probe")
            self.assertEqual(sorted(p.name for p in body.sources), ["probe.mdl", "probe_chest001.mdl"])

    def test_node_reindexes_vertices_and_deduplicates_uvs(self):
        verts = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [9, 9, 9]], float)
        faces = np.array([[0, 1, 2]])
        weights = np.array([[1.0, 0.0], [0.5, 0.5], [0.0, 1.0], [1.0, 0.0]])
        corner_uv = np.array([[[0, 0], [1, 0], [0, 0]]], float)
        node = node_for_faces("cloth", faces, verts, corner_uv, weights, ["rootdummy", "upper"], "tex", 6)
        self.assertEqual(len(node.arrays["verts"]), 3)
        self.assertEqual(len(node.arrays["tverts"]), 2)
        self.assertEqual(node.arrays["weights"][1], [("rootdummy", 0.5), ("upper", 0.5)])
        reparsed = mdl_ascii.parse(mdl_ascii.dumps(_wrap(node))).node("cloth")
        np.testing.assert_allclose(reparsed.arrays["verts"], verts[:3])


def _wrap(node):
    model = mdl_ascii.Model("probe")
    root = mdl_ascii.Node("dummy", "probe")
    node.parent = "probe"
    model.nodes = [root, node]
    return model


class FixtureTests(unittest.TestCase):
    def test_2da_round_trip_keeps_row_indices(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "parts_robe.2da"
            write_2da(path, ["ACBONUS", "HIDECHEST"], {0: {"ACBONUS": "0.00", "HIDECHEST": 1}, 11: {"HIDECHEST": 0}})
            columns, rows = read_2da(path)
            self.assertEqual(columns, ["ACBONUS", "HIDECHEST"])
            self.assertEqual(rows[11], {"ACBONUS": "****", "HIDECHEST": "0"})
            body = [line.split() for line in path.read_text().splitlines()[3:]]
            self.assertEqual([int(line[0]) for line in body], list(range(12)))  # engine reads rows by position
            self.assertEqual(rows[5], {"ACBONUS": "****", "HIDECHEST": "****"})

    def test_package_checks_validated_bytes_and_row_position(self):
        from package_trial import row_line, validated_matches
        self.assertEqual(validated_matches({"a.mdl": "1", "a.plt": "2"}, {"a.mdl": "1", "a.plt": "3"}, ["a.mdl", "a.plt"]),
                         ["a.plt"])
        self.assertEqual(validated_matches({"a.mdl": "1"}, {}, ["a.mdl", "b.tga"]), ["a.mdl", "b.tga"])
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "parts_robe.2da"
            write_2da(path, ["HIDENECK"], {0: {"HIDENECK": 0}, 3: {"HIDENECK": 1}})
            self.assertEqual(row_line(path, 3).split(), ["3", "1"])
            path.write_text("2DA V2.0\n\n    HIDENECK\n0   0\n3   1\n", encoding="ascii")
            with self.assertRaises(Exception):
                row_line(path, 1)

    def test_rename_keeps_bitmaps(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "pmh0_robe004.mdl"
            path.write_text("newmodel pmh0_robe004\nnode skin Robe\n  parent pmh0_robe004\n  bitmap pmh0_robe004\n",
                            encoding="cp1252")
            text = renamed_model(path, "pmh0_robe004", "pmh0_robe010")
            self.assertIn("newmodel pmh0_robe010", text)
            self.assertIn("parent pmh0_robe010", text)
            self.assertIn("bitmap pmh0_robe004", text)

    def test_scripts_log_rows_and_cycle_every_step(self):
        generated = scripts([{"row": 11}], [11])
        self.assertIn("ITEM_APPR_ARMOR_MODEL_ROBE", generated["sr_rt_report"])
        self.assertIn("GetPhenoType", generated["sr_rt_report"])
        self.assertIn('CreateItemOnObject("sr_rt_r11",p)', generated["sr_rt_enter"])
        self.assertIn("family=re-equip", generated["sr_rt_hb"])


class MaterialAndReferenceTests(unittest.TestCase):
    def test_plt_header_and_bottom_up_rows(self):
        shades = np.array([[1, 2], [3, 4]], np.uint8)
        data = plt_bytes(shades, np.zeros_like(shades))
        self.assertEqual(data[:8], b"PLT V1  ")
        self.assertEqual(data[24:26], bytes([3, 0]))
        with self.assertRaises(ValueError):
            plt_bytes(shades, np.full_like(shades, 12))

    def test_caption_below_gap_is_excluded(self):
        image = Image.new("RGB", (40, 100))
        image.paste((200, 200, 200), (10, 5, 30, 60))   # subject
        image.paste((200, 200, 200), (10, 80, 30, 90))  # caption after a gap
        self.assertEqual(subject_bottom(image, 24, 12), 59)


if __name__ == "__main__":
    unittest.main()
