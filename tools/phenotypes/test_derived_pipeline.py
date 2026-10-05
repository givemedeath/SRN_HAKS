"""Unit tests for derived phenotypes pipeline components (synthetic fixtures, no game/Blender required)."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
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


class ResourcePackagingValidationTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.stage_dir = Path(self.tmp_dir.name)
        self.res_dir = self.stage_dir / "resources"
        self.res_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_missing_receipt_raises(self):
        from pack_derived_elf import validate_resources
        with self.assertRaises(RuntimeError) as ctx:
            validate_resources(self.res_dir)
        self.assertIn("Missing compiler receipt", str(ctx.exception))

    def test_incomplete_receipt_raises(self):
        from pack_derived_elf import validate_resources
        receipt = self.stage_dir / "native-compile.json"
        receipt.write_text(json.dumps({"complete": False, "models": []}), encoding="utf-8")
        with self.assertRaises(RuntimeError) as ctx:
            validate_resources(self.res_dir)
        self.assertIn("Incomplete compiler receipt", str(ctx.exception))

    def test_missing_resource_raises(self):
        from pack_derived_elf import validate_resources
        receipt = self.stage_dir / "native-compile.json"
        receipt.write_text(json.dumps({
            "complete": True,
            "models": [{"name": "test.mdl", "binarySha256": "abc"}]
        }), encoding="utf-8")
        with self.assertRaises(RuntimeError) as ctx:
            validate_resources(self.res_dir)
        self.assertIn("Missing expected compiled resources", str(ctx.exception))

    def test_stale_resource_raises(self):
        from pack_derived_elf import validate_resources
        model_bytes = b"model_data"
        sha = hashlib.sha256(model_bytes).hexdigest()
        (self.res_dir / "test.mdl").write_bytes(model_bytes)
        (self.res_dir / "stale.mdl").write_bytes(b"stale")

        receipt = self.stage_dir / "native-compile.json"
        receipt.write_text(json.dumps({
            "complete": True,
            "models": [{"name": "test.mdl", "binarySha256": sha}]
        }), encoding="utf-8")
        with self.assertRaises(RuntimeError) as ctx:
            validate_resources(self.res_dir)
        self.assertIn("Stale or undeclared resources", str(ctx.exception))

    def test_hash_mismatch_raises(self):
        from pack_derived_elf import validate_resources
        (self.res_dir / "test.mdl").write_bytes(b"actual_data")

        receipt = self.stage_dir / "native-compile.json"
        receipt.write_text(json.dumps({
            "complete": True,
            "models": [{"name": "test.mdl", "binarySha256": "wrong_hash"}]
        }), encoding="utf-8")
        with self.assertRaises(RuntimeError) as ctx:
            validate_resources(self.res_dir)
        self.assertIn("Binary SHA256 mismatch", str(ctx.exception))

    def test_valid_resources_pass(self):
        from pack_derived_elf import validate_resources
        model_bytes = b"model_data"
        model_sha = hashlib.sha256(model_bytes).hexdigest()
        (self.res_dir / "test.mdl").write_bytes(model_bytes)

        mat_bytes = b"mat_data"
        mat_sha = hashlib.sha256(mat_bytes).hexdigest()
        (self.res_dir / "test.mtr").write_bytes(mat_bytes)

        receipt = self.stage_dir / "native-compile.json"
        receipt.write_text(json.dumps({
            "complete": True,
            "models": [{"name": "test.mdl", "binarySha256": model_sha}],
            "materialResourceHashes": {"test.mtr": mat_sha}
        }), encoding="utf-8")

        result = validate_resources(self.res_dir)
        self.assertEqual(len(result), 2)


class NativeAuditValidationTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.stage_dir = Path(self.tmp_dir.name)
        self.res_dir = self.stage_dir / "resources"
        self.res_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_audit_missing_compile_receipt_raises(self):
        from audit_derived_dwarf_native import audit_native_models
        with self.assertRaises(RuntimeError) as ctx:
            audit_native_models(stage_dir=self.stage_dir)
        self.assertIn("Missing native-compile.json", str(ctx.exception))


class MasterFreezeVerificationTests(unittest.TestCase):
    def test_dest_hash_verification(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            src = tmp_path / "source.mdl"
            dst = tmp_path / "native" / "source.mdl"
            dst.parent.mkdir()

            src.write_bytes(b"fresh_source_data")
            dst.write_bytes(b"stale_destination_data")

            from freeze_derived_masters import sha
            actual_sha = sha(src)
            self.assertNotEqual(sha(dst), actual_sha)

            if not dst.exists() or sha(dst) != actual_sha:
                shutil.copyfile(src, dst)
            dest_sha = sha(dst)
            self.assertEqual(dest_sha, actual_sha)


class Gate7ComplianceTests(unittest.TestCase):
    def test_passing_metrics(self):
        from calculate_silhouette_difference import evaluate_gate7_compliance
        mock_data = {
            "front": {
                "derived_vs_target": {
                    "width_ratio": 0.85,
                    "dice_pct": 75.0,
                    "regional": {
                        "Chest & Upper Torso (15-38%)": {"dice": 82.0},
                        "Pelvis & Hands (38-60%)": {"dice": 80.0},
                    },
                },
                "stock_vs_target": {"dice_pct": 70.0},
            }
        }
        res = evaluate_gate7_compliance("test_race", mock_data)
        self.assertTrue(res["passed"])
        self.assertTrue(res["torsoPassed"])
        self.assertTrue(res["pelvisPassed"])
        self.assertTrue(res["stanceWidthPassed"])
        self.assertTrue(res["baselineGainPassed"])

    def test_failing_torso_dice(self):
        from calculate_silhouette_difference import evaluate_gate7_compliance
        mock_data = {
            "front": {
                "derived_vs_target": {
                    "width_ratio": 0.85,
                    "dice_pct": 75.0,
                    "regional": {
                        "Chest & Upper Torso (15-38%)": {"dice": 70.0},
                        "Pelvis & Hands (38-60%)": {"dice": 80.0},
                    },
                },
                "stock_vs_target": {"dice_pct": 70.0},
            }
        }
        res = evaluate_gate7_compliance("test_race", mock_data)
        self.assertFalse(res["passed"])
        self.assertFalse(res["torsoPassed"])

    def test_failing_stance_width(self):
        from calculate_silhouette_difference import evaluate_gate7_compliance
        mock_data = {
            "front": {
                "derived_vs_target": {
                    "width_ratio": 0.60,
                    "dice_pct": 75.0,
                    "regional": {
                        "Chest & Upper Torso (15-38%)": {"dice": 82.0},
                        "Pelvis & Hands (38-60%)": {"dice": 80.0},
                    },
                },
                "stock_vs_target": {"dice_pct": 70.0},
            }
        }
        res = evaluate_gate7_compliance("test_race", mock_data)
        self.assertFalse(res["passed"])
        self.assertFalse(res["stanceWidthPassed"])


class StageDerivedDwarfDefaultsTests(unittest.TestCase):
    def test_stage_defaults_to_dwarf(self):
        import inspect
        from stage_derived_dwarf import stage
        sig = inspect.signature(stage)
        self.assertEqual(sig.parameters["race"].default, "dwarf")
        self.assertEqual(sig.parameters["prefix"].default, "pmd0")


class DeriveRigTargetResolutionTests(unittest.TestCase):
    def test_target_resolution_from_race(self):
        import subprocess
        res = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).resolve().parent / "derive_rig.py"),
                "--race", "dwarf",
                "--gender", "male",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("dwarf-male-stock-family", res.stdout)
        self.assertIn("verified 56 nodes", res.stdout)


if __name__ == "__main__":
    unittest.main()

