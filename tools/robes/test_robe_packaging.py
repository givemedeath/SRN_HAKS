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
