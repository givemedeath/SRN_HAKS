"""Bind equipment attachment measurements to the approved rig and stock source."""
import hashlib
import json
from pathlib import Path
import numpy as np
from derive_rig import read_mdl_text, verify_hierarchy_complete
from retarget import nodes, transforms
from target_contract import require


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def valid_frame(value):
    frame = np.asarray(value, dtype=float)
    require(frame.shape == (4, 4) and np.isfinite(frame).all(), "Invalid attachment matrix")
    require(np.allclose(frame[3], [0, 0, 0, 1], atol=1e-6), "Invalid homogeneous attachment matrix")
    rotation = frame[:3, :3]
    require(np.allclose(rotation.T @ rotation, np.eye(3), atol=1e-5) and np.isclose(np.linalg.det(rotation), 1, atol=1e-5), "Invalid attachment rotation")
    return frame


def verify_attachment_frames(rig_path: Path, target: dict) -> dict:
    receipt_path = rig_path.with_name("rig-receipt.json")
    receipt_hash = digest(receipt_path)
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    require(receipt.get("kind") == "derived-rig-receipt" and receipt.get("status") == "verified-exact", "Equipment requires verified rig receipt")
    require(receipt.get("targetId") == target["id"] and receipt.get("supermodel") == target["identity"]["prefix"], "Equipment rig target mismatch")
    require(Path(receipt["targetRootMdl"]).resolve() == rig_path.resolve(), "Equipment rig path mismatch")
    source_path = Path(receipt["sourceRootMdl"])
    pins = {str(receipt_path.resolve()): receipt_hash, str(rig_path.resolve()): receipt["targetRootMdlSha256"], str(source_path.resolve()): receipt["sourceRootMdlSha256"]}
    for path, expected in pins.items():
        require(digest(path) == expected, f"Equipment rig hash mismatch: {path}")
    skeletons = [nodes(read_mdl_text(p)) for p in (rig_path, source_path)]
    for skeleton in skeletons:
        verify_hierarchy_complete(skeleton)
    actual, source = [transforms(skeleton) for skeleton in skeletons]
    result = {}
    for hand, hook in (("handl", "lhand"), ("handr", "rhand")):
        grip = hook + "_g"
        require(all(name in frames for name in (grip, hook) for frames in (actual, source)), f"Missing equipment attachment frame: {hook}")
        approved_grip = valid_frame(target["rig"]["frames"]["working"][grip])
        actual_grip, actual_hook = valid_frame(actual[grip]), valid_frame(actual[hook])
        # Preserve stock weapon seating relative to the approved target grip.
        expected_hook = approved_grip @ np.linalg.inv(valid_frame(source[grip])) @ valid_frame(source[hook])
        grip_error = float(np.max(np.abs(actual_grip - approved_grip)))
        hook_error = float(np.max(np.abs(actual_hook - expected_hook)))
        require(grip_error <= 1e-4 and hook_error <= 1e-4, f"Equipment attachment transform mismatch: {hook}, grip={grip_error}, hook={hook_error}")
        result[hand] = {"attachmentFramesValid": True, "gripMatrixMaxError": grip_error, "attachmentMatrixMaxError": hook_error, "inputHashes": pins}
    for path, expected in pins.items():
        require(digest(path) == expected, f"Equipment frame input changed: {path}")
    return result
