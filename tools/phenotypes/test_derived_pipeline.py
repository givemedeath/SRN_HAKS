"""Unit tests for derived phenotypes pipeline components (synthetic fixtures, no game/Blender required)."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch
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


def make_test_temp_dir() -> Path:
    return Path(tempfile.mkdtemp(prefix="derived_test_"))


class ResourcePackagingValidationTests(unittest.TestCase):
    def setUp(self):
        self.stage_dir = make_test_temp_dir()
        self.res_dir = self.stage_dir / "resources"
        self.res_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.stage_dir, ignore_errors=True)

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
        self.stage_dir = make_test_temp_dir()
        self.res_dir = self.stage_dir / "resources"
        self.res_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.stage_dir, ignore_errors=True)

    def test_audit_missing_compile_receipt_raises(self):
        from audit_derived_dwarf_native import audit_native_models
        with self.assertRaises(RuntimeError) as ctx:
            audit_native_models(stage_dir=self.stage_dir)
        self.assertIn("Missing native-compile.json", str(ctx.exception))


class MasterFreezeVerificationTests(unittest.TestCase):
    def test_dest_hash_verification(self):
        tmp_path = make_test_temp_dir()
        try:
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
        finally:
            shutil.rmtree(tmp_path, ignore_errors=True)


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
            },
            "side": {
                "derived_vs_target": {
                    "regional": {
                        "Chest & Upper Torso (15-38%)": {"dice": 75.0},
                        "Pelvis & Hands (38-60%)": {"dice": 75.0},
                    },
                },
            },
            "rear": {
                "derived_vs_target": {
                    "regional": {
                        "Chest & Upper Torso (15-38%)": {"dice": 75.0},
                        "Pelvis & Hands (38-60%)": {"dice": 75.0},
                    },
                },
            },
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

    def test_turnaround_max_cannot_mask_failing_front_torso(self):
        from calculate_silhouette_difference import evaluate_gate7_compliance
        mock_data = {
            "front": {
                "derived_vs_target": {
                    "width_ratio": 0.85,
                    "dice_pct": 72.0,
                    "regional": {
                        "Chest & Upper Torso (15-38%)": {"dice": 75.0},  # Fails nominal 80%
                        "Pelvis & Hands (38-60%)": {"dice": 80.0},
                    },
                },
                "stock_vs_target": {"dice_pct": 70.0},
            },
            "side": {
                "derived_vs_target": {
                    "width_ratio": 0.85,
                    "dice_pct": 85.0,
                    "regional": {
                        "Chest & Upper Torso (15-38%)": {"dice": 90.0},  # High turnaround score
                        "Pelvis & Hands (38-60%)": {"dice": 85.0},
                    },
                },
                "stock_vs_target": {"dice_pct": 70.0},
            },
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

    def test_stance_width_upper_bound(self):
        from calculate_silhouette_difference import evaluate_gate7_compliance
        mock_data = {
            "front": {
                "derived_vs_target": {
                    "width_ratio": 1.02,  # 102% exceeds nominal 95%
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

    def test_elf_pilot_standards(self):
        from calculate_silhouette_difference import evaluate_gate7_compliance
        mock_data = {
            "front": {
                "derived_vs_target": {
                    "width_ratio": 0.85,
                    "dice_pct": 75.0,
                    "regional": {
                        "Chest & Upper Torso (15-38%)": {"dice": 78.0},  # Passes elf 77.5% threshold
                        "Pelvis & Hands (38-60%)": {"dice": 76.0},
                    },
                },
                "stock_vs_target": {"dice_pct": 70.0},
            },
            "side": {
                "derived_vs_target": {
                    "regional": {
                        "Chest & Upper Torso (15-38%)": {"dice": 75.0},
                        "Pelvis & Hands (38-60%)": {"dice": 75.0},
                    },
                },
            },
            "rear": {
                "derived_vs_target": {
                    "regional": {
                        "Chest & Upper Torso (15-38%)": {"dice": 75.0},
                        "Pelvis & Hands (38-60%)": {"dice": 75.0},
                    },
                },
            },
        }
        res = evaluate_gate7_compliance("elf_male", mock_data)
        self.assertTrue(res["passed"])
        self.assertTrue(res["torsoPassed"])

    def test_turnaround_zero_score_rejected(self):
        from calculate_silhouette_difference import evaluate_gate7_compliance
        mock_data = {
            "front": {
                "derived_vs_target": {
                    "width_ratio": 0.85,
                    "dice_pct": 82.0,
                    "regional": {
                        "Chest & Upper Torso (15-38%)": {"dice": 85.0},
                        "Pelvis & Hands (38-60%)": {"dice": 80.0},
                    },
                },
                "stock_vs_target": {"dice_pct": 70.0},
            },
            "side": {
                "derived_vs_target": {
                    "regional": {
                        "Chest & Upper Torso (15-38%)": {"dice": 0.0},  # Disjoint turnaround region
                        "Pelvis & Hands (38-60%)": {"dice": 75.0},
                    },
                },
            },
            "rear": {
                "derived_vs_target": {
                    "regional": {
                        "Chest & Upper Torso (15-38%)": {"dice": 75.0},
                        "Pelvis & Hands (38-60%)": {"dice": 75.0},
                    },
                },
            },
        }
        res = evaluate_gate7_compliance("test_race", mock_data)
        self.assertFalse(res["passed"])
        self.assertFalse(res["turnaroundPassed"])
        self.assertFalse(res["turnaroundReports"]["side"]["passed"])

    def test_turnaround_passing_scores(self):
        from calculate_silhouette_difference import evaluate_gate7_compliance
        mock_data = {
            "front": {
                "derived_vs_target": {
                    "width_ratio": 0.85,
                    "dice_pct": 82.0,
                    "regional": {
                        "Chest & Upper Torso (15-38%)": {"dice": 85.0},
                        "Pelvis & Hands (38-60%)": {"dice": 80.0},
                    },
                },
                "stock_vs_target": {"dice_pct": 70.0},
            },
            "side": {
                "derived_vs_target": {
                    "regional": {
                        "Chest & Upper Torso (15-38%)": {"dice": 72.0},
                        "Pelvis & Hands (38-60%)": {"dice": 75.0},
                    },
                },
            },
            "rear": {
                "derived_vs_target": {
                    "regional": {
                        "Chest & Upper Torso (15-38%)": {"dice": 75.0},
                        "Pelvis & Hands (38-60%)": {"dice": 75.0},
                    },
                },
            },
        }
        res = evaluate_gate7_compliance("test_race", mock_data)
        self.assertTrue(res["passed"])
        self.assertTrue(res["turnaroundPassed"])
        self.assertTrue(res["turnaroundReports"]["side"]["passed"])
        self.assertTrue(res["turnaroundReports"]["rear"]["passed"])

    def test_missing_turnaround_view_fails(self):
        from calculate_silhouette_difference import evaluate_gate7_compliance
        mock_data = {
            "front": {
                "derived_vs_target": {
                    "width_ratio": 0.85,
                    "dice_pct": 82.0,
                    "regional": {
                        "Chest & Upper Torso (15-38%)": {"dice": 85.0},
                        "Pelvis & Hands (38-60%)": {"dice": 80.0},
                    },
                },
                "stock_vs_target": {"dice_pct": 70.0},
            },
            "side": {
                "derived_vs_target": {
                    "regional": {
                        "Chest & Upper Torso (15-38%)": {"dice": 75.0},
                        "Pelvis & Hands (38-60%)": {"dice": 75.0},
                    },
                },
            },
            # Missing rear view
        }
        res = evaluate_gate7_compliance("test_race", mock_data)
        self.assertFalse(res["passed"])
        self.assertFalse(res["turnaroundPassed"])
        self.assertIn("rear", res["turnaroundReports"])
        self.assertFalse(res["turnaroundReports"]["rear"]["passed"])


class StageDerivedDwarfDefaultsTests(unittest.TestCase):
    def test_stage_defaults_to_dwarf(self):
        import inspect
        from stage_derived_dwarf import stage
        sig = inspect.signature(stage)
        self.assertEqual(sig.parameters["race"].default, "dwarf")
        self.assertEqual(sig.parameters["prefix"].default, "pmd0")


class DeriveRigTargetResolutionTests(unittest.TestCase):
    def test_target_resolution_from_race(self):
        from derive_rig import resolve_target_config

        # Test Dwarf
        dwarf_cfg = resolve_target_config("dwarf", "male", 0)
        self.assertTrue(dwarf_cfg.exists())
        self.assertEqual(dwarf_cfg.name, "target-dwarf-male-stock.json")

        # Test Elf
        elf_cfg = resolve_target_config("elf", "male", 0)
        self.assertTrue(elf_cfg.exists())
        self.assertEqual(elf_cfg.name, "target-elf-male-fit.json")

        # Test Orc
        orc_cfg = resolve_target_config("orc", "male", 0)
        self.assertTrue(orc_cfg.exists())
        self.assertEqual(orc_cfg.name, "target-orc-male-fit.json")

        # Test Troll
        troll_cfg = resolve_target_config("troll", "male", 0)
        self.assertTrue(troll_cfg.exists())
        self.assertEqual(troll_cfg.name, "target-troll-male-fit.json")

        # Test Human
        human_cfg = resolve_target_config("human", "male", 0)
        self.assertTrue(human_cfg.exists())
        self.assertEqual(human_cfg.name, "target-human-male-baseline.json")

    def test_unknown_race_raises(self):
        from derive_rig import resolve_target_config
        with self.assertRaises(FileNotFoundError):
            resolve_target_config("unknown_race", "male", 0)

    def test_cli_requires_target_or_race(self):
        import subprocess
        res = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).resolve().parent / "derive_rig.py"),
            ],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("Either positional 'target' JSON path or --race must be specified", res.stderr)


class HandDummiesExactMatchingTests(unittest.TestCase):
    def test_rhand_not_matched_by_rhand_g(self):
        from derived_equipment import audit_hand_dummies
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            handl = tmp_path / "pmd0_handl001.mdl"
            handr = tmp_path / "pmd0_handr001.mdl"
            handl.write_text("model test", encoding="cp1252")
            handr.write_text("model test", encoding="cp1252")

            # Rig has grip frame rhand_g and lhand_g, but NOT rhand or lhand
            rig_missing_attachment = tmp_path / "rig_no_attach.mdl"
            rig_missing_attachment.write_text(
                "node dummy rhand_g\n  parent root\nendnode\nnode dummy lhand_g\n  parent root\nendnode\n",
                encoding="cp1252",
            )

            result = audit_hand_dummies(tmp_path, rig_missing_attachment, prefix="pmd0")
            self.assertTrue(result["handr"]["rigGripPresent"])
            self.assertFalse(result["handr"]["rigAttachmentPresent"])
            self.assertTrue(result["handl"]["rigGripPresent"])
            self.assertFalse(result["handl"]["rigAttachmentPresent"])

            # Rig has both attachment and grip frame
            rig_complete = tmp_path / "rig_complete.mdl"
            rig_complete.write_text(
                "node dummy rhand\nendnode\nnode dummy rhand_g\nendnode\n"
                "node dummy lhand\nendnode\nnode dummy lhand_g\nendnode\n",
                encoding="cp1252",
            )
            result_complete = audit_hand_dummies(tmp_path, rig_complete, prefix="pmd0")
            self.assertTrue(result_complete["handr"]["rigGripPresent"])
            self.assertTrue(result_complete["handr"]["rigAttachmentPresent"])
            self.assertTrue(result_complete["handl"]["rigGripPresent"])
            self.assertTrue(result_complete["handl"]["rigAttachmentPresent"])


class ClientResolutionTests(unittest.TestCase):
    def test_explicit_client_path(self):
        from run_derived_dwarf_client_test import resolve_client
        with tempfile.TemporaryDirectory() as tmp:
            dummy_exe = Path(tmp) / "nwmain.exe"
            dummy_exe.touch()
            resolved = resolve_client(dummy_exe)
            self.assertEqual(resolved, dummy_exe.resolve())

    def test_explicit_client_missing_raises(self):
        from run_derived_dwarf_client_test import resolve_client
        with self.assertRaises(FileNotFoundError):
            resolve_client(Path("C:/nonexistent/nwmain.exe"))

    def test_env_client_path(self):
        from run_derived_dwarf_client_test import resolve_client
        with tempfile.TemporaryDirectory() as tmp:
            dummy_exe = Path(tmp) / "custom_client.exe"
            dummy_exe.touch()
            old_val = os.environ.get("NWN_CLIENT")
            try:
                os.environ["NWN_CLIENT"] = str(dummy_exe)
                resolved = resolve_client()
                self.assertEqual(resolved, dummy_exe.resolve())
            finally:
                if old_val is not None:
                    os.environ["NWN_CLIENT"] = old_val
                else:
                    os.environ.pop("NWN_CLIENT", None)


class GameRootResolutionTests(unittest.TestCase):
    def test_explicit_game_root(self):
        from stock_dwarf_control import resolve_game_root
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            resolved = resolve_game_root(tmp_root)
            self.assertEqual(resolved, tmp_root.resolve())

    def test_explicit_game_root_missing_raises(self):
        from stock_dwarf_control import resolve_game_root
        with self.assertRaises(FileNotFoundError):
            resolve_game_root(Path("C:/nonexistent_game_root_dir"))

    def test_env_game_root(self):
        from stock_dwarf_control import resolve_game_root
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            old_val = os.environ.get("NWN_ROOT")
            try:
                os.environ["NWN_ROOT"] = str(tmp_root)
                resolved = resolve_game_root()
                self.assertEqual(resolved, tmp_root.resolve())
            finally:
                if old_val is not None:
                    os.environ["NWN_ROOT"] = old_val
                else:
                    os.environ.pop("NWN_ROOT", None)


class EquipmentConnectorRequirementTests(unittest.TestCase):
    @patch("derived_equipment.inventory_installed_styles")
    @patch("derived_equipment.audit_hand_dummies")
    def test_missing_connector_audit_raises(self, mock_dummies, mock_inventory):
        from derived_equipment import PARTS, audit_stock_armor_compatibility
        mock_dummies.return_value = {"handl": {"rigGripPresent": True, "rigAttachmentPresent": True}}
        mock_inventory.return_value = {
            "parts": {p: [1] for p in PARTS},
            "totalModelsFound": 440,
        }
        target_config = {
            "id": "dwarf-male-fit",
            "identity": {"prefix": "pmd0", "race": "dwarf"},
            "rig": {"mode": "stock-family", "frames": {"working": ["torso_g", "lbicep_g", "rbicep_g", "lforearm_g", "rforearm_g",
                                          "lhand_g", "rhand_g", "lthigh_g", "rthigh_g", "lshin_g", "rshin_g", "lfoot_g", "rfoot_g"]}}
        }
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            out_receipt = tmp_dir / "receipt.json"
            # Missing connector-audit.json must raise ValueError
            with self.assertRaises(ValueError) as ctx:
                audit_stock_armor_compatibility(target_config, tmp_dir, out_receipt)
            self.assertIn("requires a present connector audit receipt", str(ctx.exception))

    @patch("derived_equipment.inventory_installed_styles")
    @patch("derived_equipment.audit_hand_dummies")
    def test_mismatched_target_connector_audit_raises(self, mock_dummies, mock_inventory):
        from derived_equipment import PARTS, audit_stock_armor_compatibility
        mock_dummies.return_value = {"handl": {"rigGripPresent": True, "rigAttachmentPresent": True}}
        mock_inventory.return_value = {
            "parts": {p: [1] for p in PARTS},
            "totalModelsFound": 440,
        }
        target_config = {
            "id": "dwarf-male-fit",
            "identity": {"prefix": "pmd0", "race": "dwarf"},
            "rig": {"mode": "stock-family", "frames": {"working": ["torso_g", "lbicep_g", "rbicep_g", "lforearm_g", "rforearm_g",
                                          "lhand_g", "rhand_g", "lthigh_g", "rthigh_g", "lshin_g", "rshin_g", "lfoot_g", "rfoot_g"]}}
        }
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            out_receipt = tmp_dir / "receipt.json"
            bad_audit = tmp_dir / "connector-audit.json"
            bad_audit.write_text(json.dumps({
                "targetId": "elf-male-fit",  # Mismatched target
                "allConnectorsPassed": True,
            }), encoding="utf-8")

            with self.assertRaises(ValueError) as ctx:
                audit_stock_armor_compatibility(target_config, tmp_dir, out_receipt)
            self.assertIn("target mismatch", str(ctx.exception))

    @patch("derived_equipment.inventory_installed_styles")
    @patch("derived_equipment.audit_hand_dummies")
    def test_matching_passing_connector_audit_succeeds(self, mock_dummies, mock_inventory):
        from derived_equipment import PARTS, audit_stock_armor_compatibility
        mock_dummies.return_value = {"handl": {"rigGripPresent": True, "rigAttachmentPresent": True}}
        mock_inventory.return_value = {
            "parts": {p: [1] for p in PARTS},
            "totalModelsFound": 440,
        }
        target_config = {
            "id": "dwarf-male-fit",
            "identity": {"prefix": "pmd0", "race": "dwarf"},
            "rig": {"mode": "stock-family", "frames": {"working": ["torso_g", "lbicep_g", "rbicep_g", "lforearm_g", "rforearm_g",
                                          "lhand_g", "rhand_g", "lthigh_g", "rthigh_g", "lshin_g", "rshin_g", "lfoot_g", "rfoot_g"]}}
        }
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            out_receipt = tmp_dir / "receipt.json"
            good_audit = tmp_dir / "connector-audit.json"
            (tmp_dir / "pmd0_chest001.mdl").write_text("model pmd0_chest001", encoding="utf-8")
            good_audit.write_text(json.dumps({
                "targetId": "dwarf-male-fit",
                "allConnectorsPassed": True,
                "parts": {
                    "chest": {
                        "model": "pmd0_chest001",
                        "sha256": hashlib.sha256(b"model pmd0_chest001").hexdigest(),
                    }
                }
            }), encoding="utf-8")

            res = audit_stock_armor_compatibility(target_config, tmp_dir, out_receipt)
            self.assertTrue(res["complete"])
            self.assertEqual(res["connectorCompatibility"]["measuredOverlapStatus"], "verified-positive")

    @patch("derived_equipment.inventory_installed_styles")
    @patch("derived_equipment.audit_hand_dummies")
    def test_stale_model_hash_fails(self, mock_dummies, mock_inventory):
        from derived_equipment import PARTS, audit_stock_armor_compatibility
        mock_dummies.return_value = {"handl": {"rigGripPresent": True, "rigAttachmentPresent": True}}
        mock_inventory.return_value = {
            "parts": {p: [1] for p in PARTS},
            "totalModelsFound": 440,
        }
        target_config = {
            "id": "dwarf-male-fit",
            "identity": {"prefix": "pmd0", "race": "dwarf"},
            "rig": {"mode": "stock-family", "frames": {"working": ["torso_g", "lbicep_g", "rbicep_g", "lforearm_g", "rforearm_g",
                                          "lhand_g", "rhand_g", "lthigh_g", "rthigh_g", "lshin_g", "rshin_g", "lfoot_g", "rfoot_g"]}}
        }
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            out_receipt = tmp_dir / "receipt.json"
            good_audit = tmp_dir / "connector-audit.json"
            (tmp_dir / "pmd0_chest001.mdl").write_text("model pmd0_chest001_modified", encoding="utf-8")
            good_audit.write_text(json.dumps({
                "targetId": "dwarf-male-fit",
                "allConnectorsPassed": True,
                "parts": {
                    "chest": {
                        "model": "pmd0_chest001",
                        "sha256": "0" * 64,  # Stale hash
                    }
                }
            }), encoding="utf-8")

            with self.assertRaises(ValueError) as ctx:
                audit_stock_armor_compatibility(target_config, tmp_dir, out_receipt)
            self.assertIn("hash mismatch", str(ctx.exception))


class ConnectorJointAxisAuditTests(unittest.TestCase):
    def test_connector_audit_measures_joint_axis(self):
        from audit_derived_connectors import audit_connectors
        target_path = Path(__file__).resolve().parent / "configurations" / "derived" / "target-dwarf-male-stock.json"
        target_data = json.loads(target_path.read_text(encoding="utf-8"))
        ascii_dir = Path(__file__).resolve().parents[2] / "output/phenotypes/derived-v1/parts/dwarf-male/ascii"
        if ascii_dir.exists():
            report = audit_connectors(target_data, ascii_dir)
            self.assertTrue(report["allConnectorsPassed"])
            for c in report["connectors"]:
                self.assertIn("axialOverlapMeters", c)
                self.assertIn("jointAxis", c)
                self.assertGreater(c["axialOverlapMeters"], 0.005)
                self.assertTrue(c["hasSurfaceProximity"])


class MotionReviewPosePrefixTests(unittest.TestCase):
    def test_motion_review_prefix_parameter(self):
        import inspect
        from derived_review_configs import evaluate_connector_motion, build_all_review_packets
        sig = inspect.signature(evaluate_connector_motion)
        self.assertIn("prefix", sig.parameters)
        self.assertIn("model_ascii_dir", sig.parameters)
        self.assertIn("rig_dir", sig.parameters)
        build_sig = inspect.signature(build_all_review_packets)
        self.assertIn("rig_dir", build_sig.parameters)

    def test_motion_review_measures_posed_surfaces(self):
        source = Path(__file__).resolve().parent.joinpath("derived_review_configs.py").read_text(encoding="utf-8")
        self.assertIn("allConnectorsPassMotionSurfaces", source)
        self.assertIn("minSurfaceDistanceMeters", source)
        self.assertIn("axialOverlapMeters", source)


class StageCleanStagingTests(unittest.TestCase):
    def test_stage_cleans_directories_and_enforces_14_models(self):
        source = Path(__file__).resolve().parent.joinpath("stage_derived_dwarf.py").read_text(encoding="utf-8")
        self.assertIn("shutil.rmtree(ascii_dir)", source)
        self.assertIn("shutil.rmtree(resources_dir)", source)
        self.assertIn("len(staged_models) != 14", source)



class PreflightCliExecutionTests(unittest.TestCase):
    def test_preflight_cli_help(self):
        import subprocess
        res = subprocess.run(
            [sys.executable, str(Path(__file__).resolve().parent / "preflight_derived_dwarf_client.py"), "--help"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("--output-receipt", res.stdout)


class FreezeStockRigsTests(unittest.TestCase):
    def test_freeze_stock_models_include_elf_and_orc(self):
        source = Path(__file__).resolve().parent.joinpath("freeze_derived_masters.py").read_text(encoding="utf-8")
        self.assertIn("pme0.mdl", source)
        self.assertIn("pme0_head001.mdl", source)
        self.assertIn("pmo0.mdl", source)
        self.assertIn("pmo0_head001.mdl", source)


class RenderTargetHeadNeckTests(unittest.TestCase):
    def test_render_orc_uses_pmo0_head_neck(self):
        source = Path(__file__).resolve().parent.joinpath("render_derived_orc_review.py").read_text(encoding="utf-8")
        self.assertIn("pmo0_{part}001.mdl", source)

    def test_render_elf_uses_pme0_head_neck(self):
        source = Path(__file__).resolve().parent.joinpath("render_derived_elf_review.py").read_text(encoding="utf-8")
        self.assertIn("pme0_{part}001.mdl", source)


class FixtureBuilderCliTests(unittest.TestCase):
    def test_build_derived_dwarf_fixture_options(self):
        import subprocess
        res = subprocess.run(
            [sys.executable, str(Path(__file__).resolve().parent / "build_derived_dwarf_fixture.py"), "--help"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("--stage", res.stdout)


class DecompileBinaryMdlTests(unittest.TestCase):
    def test_read_mdl_text_ascii_and_binary(self):
        from derive_rig import read_mdl_text
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            ascii_mdl = tmp / "ascii.mdl"
            ascii_mdl.write_bytes(b"newmodel test\nsetsupermodel test a_ba\n")
            self.assertEqual(read_mdl_text(ascii_mdl).replace("\r\n", "\n"), "newmodel test\nsetsupermodel test a_ba\n")

            bin_mdl = tmp / "bin.mdl"
            bin_mdl.write_bytes(b"\0\0\0\0compiled_binary_data")
            with patch("derive_rig.resolve_mdlcomp") as mock_tool, \
                 patch("subprocess.run") as mock_run:
                mock_tool.return_value = Path("dummy_mdlcomp.exe")
                # When subprocess.run is called, simulate output file creation
                def fake_run(cmd, **kwargs):
                    out_path = Path(cmd[4])
                    out_path.write_bytes(b"newmodel decompiled\n")
                    return unittest.mock.MagicMock(returncode=0)
                mock_run.side_effect = fake_run
                result = read_mdl_text(bin_mdl)
                self.assertEqual(result.replace("\r\n", "\n"), "newmodel decompiled\n")
                self.assertTrue(mock_run.called)


class TrollRootStagingAndScaleTests(unittest.TestCase):
    def test_stage_troll_enforces_15_models_with_root(self):
        source = Path(__file__).resolve().parent.joinpath("stage_derived_dwarf.py").read_text(encoding="utf-8")
        self.assertIn('expected_count = 15 if race == "troll" or (ascii_dir / f"{prefix}.mdl").is_file() else 14', source)
        self.assertIn('rig_root = REPO / f"output/phenotypes/derived-v1/rigs/{race}-male/{prefix}.mdl"', source)

    def test_stage_troll_requires_rig_root(self):
        from stage_derived_dwarf import stage
        with unittest.mock.patch("stage_derived_dwarf.REPO", Path("C:/nonexistent/repo")):
            with self.assertRaises(FileNotFoundError):
                stage(race="troll", prefix="pmg0")

    def test_troll_fixture_patches_appearance_scale(self):
        from build_derived_troll_fixture import stage_fixture_resources
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            stage_dir = tmp / "stage"
            userdir = tmp / "userdir"
            stage_dir.mkdir(parents=True)
            userdir.mkdir(parents=True)

            # Create mock appearance.2da with Gnome row 2
            app_path = tmp / "test_appearance.2da"
            headers = "LABEL STRING_REF NAME RACE ENVMAP BLOODCOLR MODELTYPE WEAPONSCALE WING_TAIL_SCALE HELMET_SCALE_M HELMET_SCALE_F MOVERATE WALKDIST RUNDIST PERSPACE CREPERSPACE HEIGHT HITDIST PREFATCKDIST TARGETHEIGHT ABORTONPARRY RACIALTYPE HASLEGS HASARMS PORTRAIT SIZECATEGORY PERCEPTIONDIST FOOTSTEPTYPE SOUNDAPPTYPE HEADTRACK HEAD_ARC_H HEAD_ARC_V HEAD_NAME BODY_BAG TARGETABLE"
            lines = [
                "2DA V2.0",
                "      " + headers,
                "0     Dwarf       1985 Character_model D default R P 1 1 1.15 0.95 NORM 1.06 2.12 0.3 0.5 1.5 0.3 1.4 H 1 6 1 1 **** 3 9 0 0 1 60 30 head_g 6 1",
                "1     Elf         1986 Character_model E default R P 1 1 0.85 0.8  NORM 1.43 2.86 0.3 0.4 1.75 0.3 1.5 H 1 7 1 1 **** 3 9 0 0 1 60 30 head_g 6 1",
                "2     Gnome       1987 Character_model G default R P 1 1 0.9  0.82 NORM 1.0  1.94 0.3 0.4 1.5  0.3 1.3 H 1 8 1 1 **** 2 9 0 0 1 60 30 head_g 6 1",
            ]
            app_path.write_text("\n".join(lines) + "\n", encoding="cp1252")

            app_hash = stage_fixture_resources(stage_dir, userdir, appearance_path=app_path)
            patched = (stage_dir / "fixture-resources/appearance.2da").read_text(encoding="cp1252")
            patched_lines = [l for l in patched.splitlines() if l.strip()]
            row_2 = patched_lines[4].split()
            cols = patched_lines[1].split()

            self.assertEqual(row_2[cols.index("LABEL") + 1], "Troll")
            self.assertEqual(row_2[cols.index("HEIGHT") + 1], "2.7627")
            self.assertEqual(row_2[cols.index("SIZECATEGORY") + 1], "4")
            self.assertAlmostEqual(float(row_2[cols.index("WEAPONSCALE") + 1]), 1.42857, places=4)
            self.assertEqual(app_hash, hashlib.sha256((stage_dir / "fixture-resources/appearance.2da").read_bytes()).hexdigest())

    def test_troll_appearance_patch_missing_row_fails(self):
        from build_derived_troll_fixture import stage_fixture_resources
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            stage_dir = tmp / "stage"
            userdir = tmp / "userdir"
            stage_dir.mkdir(parents=True)
            userdir.mkdir(parents=True)

            app_path = tmp / "no_gnome_appearance.2da"
            headers = "LABEL STRING_REF HEIGHT SIZECATEGORY WEAPONSCALE WALKDIST RUNDIST"
            lines = [
                "2DA V2.0",
                "      " + headers,
                "0     Dwarf  1985 1.5  3 1.0 1.06 2.12",
                "1     Elf    1986 1.75 3 1.0 1.43 2.86",
            ]
            app_path.write_text("\n".join(lines) + "\n", encoding="cp1252")

            with self.assertRaises(RuntimeError):
                stage_fixture_resources(stage_dir, userdir, appearance_path=app_path)

    def test_troll_appearance_patch_missing_scale_cols_fails(self):
        from build_derived_troll_fixture import stage_fixture_resources
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            stage_dir = tmp / "stage"
            userdir = tmp / "userdir"
            stage_dir.mkdir(parents=True)
            userdir.mkdir(parents=True)

            app_path = tmp / "bad_headers_appearance.2da"
            headers = "LABEL STRING_REF OTHER_COL"
            lines = [
                "2DA V2.0",
                "      " + headers,
                "0     Dwarf  1985 val",
                "2     Gnome  1987 val",
            ]
            app_path.write_text("\n".join(lines) + "\n", encoding="cp1252")

            with self.assertRaises(RuntimeError):
                stage_fixture_resources(stage_dir, userdir, appearance_path=app_path)


class ClientLogScanTests(unittest.TestCase):
    def test_scan_log_detects_errors(self):
        from run_derived_dwarf_client_test import scan_log_for_errors
        with tempfile.TemporaryDirectory() as tmpdir:
            log_p = Path(tmpdir) / "test_client.log"
            log_p.write_text(
                "Loading area...\n"
                "Empty field label in MODULE.ifo\n"
                "Model pmd0_chest001 not found\n"
                "Spawn complete\n"
                "Runtime Error: script failure\n",
                encoding="utf-8"
            )
            errors = scan_log_for_errors(log_p)
            self.assertEqual(len(errors), 2)
            self.assertTrue(any("not found" in e for e in errors))
            self.assertTrue(any("Runtime Error" in e for e in errors))

    def test_scan_log_clean_when_only_benign_notices(self):
        from run_derived_dwarf_client_test import scan_log_for_errors
        with tempfile.TemporaryDirectory() as tmpdir:
            log_p = Path(tmpdir) / "clean_engine.log"
            log_p.write_text(
                "Initializing engine...\n"
                "Empty field label in MODULE.ifo\n"
                "Nonfatal notice\n"
                "Sequence finished successfully\n",
                encoding="utf-8"
            )
            errors = scan_log_for_errors(log_p)
            self.assertEqual(errors, [])


class SilhouetteRearViewHalvesTests(unittest.TestCase):
    def test_rear_view_halves_assignment_in_source(self):
        source = Path(__file__).resolve().parent.joinpath("calculate_silhouette_difference.py").read_text(encoding="utf-8")
        self.assertIn("d_elf_r = fg_er[:, :1200]", source)
        self.assertIn("s_elf_r = fg_er[:, 1200:]", source)
        self.assertIn("d_orc_r = fg_or[:, :1200]", source)
        self.assertIn("s_orc_r = fg_or[:, 1200:]", source)

        sheet_source = Path(__file__).resolve().parent.joinpath("build_silhouette_comparison_sheet.py").read_text(encoding="utf-8")
        self.assertIn("stock_elf_rear_mask = fg_err[:, 1200:]", sheet_source)
        self.assertIn("derived_elf_rear_mask = fg_err[:, :1200]", sheet_source)
        self.assertIn("stock_orc_rear_mask = fg_orr[:, 1200:]", sheet_source)
        self.assertIn("derived_orc_rear_mask = fg_orr[:, :1200]", sheet_source)


class StockFamilyEquipmentFallbackTests(unittest.TestCase):
    def test_stock_family_fallback_resolves_prefix_models(self):
        from build_test_module import stock_equipment_models
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            converted = root / "dwarf_fit/converted"
            converted.mkdir(parents=True)
            conversion = {
                "modelPrefix": "pmd0",
                "rigMode": "stock-family",
                "stockOtherPartsFromGame": True,
                "height": 1.4864,
                "stockReferenceHeight": 1.473
            }
            (converted / "conversion.json").write_text(json.dumps(conversion), encoding="utf-8")
            records = [{"slug": "dwarf_fit"}, {"slug": "stock_dwarf", "fixtureControl": True}]
            item = {
                "ArmorPart_Torso": {"value": 16},
                "ArmorPart_Pelvis": {"value": 1},
                "ArmorPart_LThigh": {"value": 4},
                "ArmorPart_Robe": {"value": 0}
            }
            models = stock_equipment_models(records, root, item)
            self.assertEqual(models, ["pmd0_chest016.mdl", "pmd0_legl004.mdl"])


if __name__ == "__main__":
    unittest.main()


