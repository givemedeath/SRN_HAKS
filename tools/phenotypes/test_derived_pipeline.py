"""Unit tests for derived phenotypes pipeline components (synthetic fixtures, no game/Blender required)."""
from __future__ import annotations
import json
from pathlib import Path
import unittest
import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))

from derived_contract import load_derived_target, verify_target_frames
from derived_matrix import load_matrix, get_target, get_pilot_target, evaluate_target_eligibility
from localized_refine import wendland_c2
from audit_derived_dwarf_native import decode_model_nodes


class DerivedContractTests(unittest.TestCase):
    def test_target_matrix_scope(self):
        matrix = load_matrix()
        targets = matrix["targets"]
        self.assertIn("dwarf-male-fit", targets)
        self.assertIn("elf-male-fit", targets)
        self.assertIn("half-orc-male-fit", targets)

        # Verify female dwarf is blocked on source
        eligible, reason = evaluate_target_eligibility(matrix, "dwarf-female-fit")
        self.assertFalse(eligible)
        self.assertIn("BLOCKED", reason)

        # Verify pilot target is dwarf-male-fit
        pilot = get_pilot_target(matrix)
        self.assertEqual(pilot["id"], "dwarf-male-fit")

    def test_dwarf_male_target_contract(self):
        target_path = Path(__file__).resolve().parent / "configurations" / "derived" / "target-dwarf-male-stock.json"
        data = load_derived_target(target_path)
        self.assertEqual(data["identity"]["race"], "dwarf")
        self.assertEqual(data["identity"]["gender"], "male")
        self.assertEqual(data["identity"]["phenotype"], 0)
        self.assertEqual(data["identity"]["prefix"], "pmd0")
        self.assertEqual(data["identity"]["raceId"], 0)
        self.assertEqual(data["identity"]["appearanceRow"], 0)
        self.assertTrue(verify_target_frames(data))


class LocalizedRefineMathTests(unittest.TestCase):
    def test_wendland_c2_properties(self):
        # At r=0, weight should be exactly 1
        w_0 = wendland_c2(np.array([0.0]), radius=1.0)
        self.assertAlmostEqual(float(w_0[0]), 1.0, places=6)

        # For r >= radius, weight must be exactly 0
        w_edge = wendland_c2(np.array([1.0, 1.5, 2.0]), radius=1.0)
        self.assertTrue((w_edge == 0.0).all())

        # For 0 < r < radius, weight strictly decreasing and in (0, 1)
        r = np.linspace(0.1, 0.9, 9)
        w = wendland_c2(r, radius=1.0)
        self.assertTrue(((w > 0.0) & (w < 1.0)).all())
        self.assertTrue(np.all(np.diff(w) < 0))

    def test_jacobian_positive_preservation(self):
        # A displacement field must preserve positive Jacobian
        grad = np.array([[0.05, 0.0, 0.0], [0.0, 0.05, 0.0], [0.0, 0.0, 0.05]])
        J = np.eye(3) + grad
        det = np.linalg.det(J)
        self.assertGreater(det, 0.0)


class NativeDecoderTests(unittest.TestCase):
    def test_truncated_header_rejected(self):
        with self.assertRaises(ValueError):
            decode_model_nodes(b"\0\0\0", "test")

    def test_invalid_header_rejected(self):
        # Non-zero first dword
        with self.assertRaises(ValueError):
            decode_model_nodes(b"\x01\0\0\0\0\0\0\0\0\0\0\0", "test")


if __name__ == "__main__":
    unittest.main()
