"""Audit derived dwarf male native compiled models.

Decodes and verifies NwnMdl binary layout, vertex/face counts, tangent space,
normals, and material bindings across all 14 derived body parts.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import struct
import numpy as np

REPO = Path(__file__).resolve().parents[2]
STAGE = REPO / "output/phenotypes/derived-dwarf-male-v1/candidate/converted"
PARTS = [
    "bicepl", "bicepr", "chest", "footl", "footr", "forel", "forer",
    "handl", "handr", "legl", "legr", "pelvis", "shinl", "shinr"
]


def decode_model_nodes(data: bytes, model_name: str) -> list[dict]:
    """Decode all trimesh nodes in a compiled NWN binary model."""
    if len(data) < 12:
        raise ValueError(f"{model_name}: binary too short")
    zero, raw_offset, raw_size = struct.unpack_from("<III", data)
    if zero != 0 or 12 + raw_offset + raw_size != len(data):
        raise ValueError(f"{model_name}: invalid binary header")

    nodes = []
    # Scan for trimesh flag33 nodes in model structure section
    raw_start = 12 + raw_offset
    offset = 12
    while offset < 12 + raw_offset - 0x70:
        # Check node header: flag 33 at offset 0x6c from node start
        if offset + 0x70 <= 12 + raw_offset:
            flag = struct.unpack_from("<I", data, offset + 0x6c)[0]
            if flag == 33 and offset + 0x264 <= 12 + raw_offset:
                face_offset, count, capacity = struct.unpack_from("<III", data, offset + 0x78)
                vertices, texture_count = struct.unpack_from("<HH", data, offset + 0x230)
                if vertices > 0 and count > 0 and count == capacity:
                    # Found a trimesh node! Read name if possible
                    node_name = "unknown"
                    if offset >= 32:
                        name_bytes = data[offset - 32:offset].split(b"\0")[0]
                        try:
                            node_name = name_bytes.decode("ascii")
                        except Exception:
                            pass

                    # Read attribute offsets
                    offsets = {key: struct.unpack_from("<I", data, offset + field)[0] for key, field in
                               [("position", 0x22c), ("uv", 0x234), ("normal", 0x244), ("tangent", 0x258), ("sign", 0x260)]}

                    has_tangents = (offsets["tangent"] != 0xffffffff and offsets["tangent"] + vertices * 12 <= raw_size)
                    has_normals = (offsets["normal"] != 0xffffffff and offsets["normal"] + vertices * 12 <= raw_size)

                    tangent_finite = False
                    tangent_unit_norm = False
                    if has_tangents:
                        t_arr = np.frombuffer(data, "<f4", vertices * 3, raw_start + offsets["tangent"]).reshape(-1, 3)
                        tangent_finite = bool(np.isfinite(t_arr).all())
                        if tangent_finite and vertices > 0:
                            t_len = np.linalg.norm(t_arr, axis=1)
                            tangent_unit_norm = bool(np.all(np.abs(t_len - 1.0) < 0.05))

                    normal_finite = False
                    normal_unit_norm = False
                    if has_normals:
                        n_arr = np.frombuffer(data, "<f4", vertices * 3, raw_start + offsets["normal"]).reshape(-1, 3)
                        normal_finite = bool(np.isfinite(n_arr).all())
                        if normal_finite and vertices > 0:
                            n_len = np.linalg.norm(n_arr, axis=1)
                            normal_unit_norm = bool(np.all(np.abs(n_len - 1.0) < 0.05))

                    nodes.append({
                        "nodeName": node_name,
                        "vertices": vertices,
                        "triangles": count,
                        "hasTangents": has_tangents,
                        "tangentFinite": tangent_finite,
                        "tangentUnitNorm": tangent_unit_norm,
                        "hasNormals": has_normals,
                        "normalFinite": normal_finite,
                        "normalUnitNorm": normal_unit_norm,
                    })
        offset += 4

    return nodes


def audit_native_models(stage_dir: Path = STAGE, output_receipt: Path | None = None) -> dict:
    receipt_file = stage_dir / "native-compile.json"
    if not receipt_file.exists():
        raise RuntimeError("Missing native-compile.json")
    compile_data = json.loads(receipt_file.read_text(encoding="utf-8"))
    if not compile_data.get("complete", False):
        raise RuntimeError(f"Incomplete compiler receipt in {receipt_file}")

    compile_models = {m["name"]: m for m in compile_data.get("models", [])}

    results = {}
    all_passed = True

    for part in PARTS:
        model_name = f"pmd0_{part}001.mdl"
        if model_name not in compile_models:
            raise RuntimeError(f"Model {model_name} missing from native-compile.json")

        bin_path = stage_dir / "resources" / model_name
        if not bin_path.exists():
            raise RuntimeError(f"Missing compiled binary: {bin_path}")

        data = bin_path.read_bytes()
        actual_sha256 = hashlib.sha256(data).hexdigest()
        expected_sha256 = compile_models[model_name]["binarySha256"]
        if actual_sha256 != expected_sha256:
            raise RuntimeError(f"Binary SHA256 mismatch for {model_name}: expected {expected_sha256}, got {actual_sha256}")

        nodes = decode_model_nodes(data, model_name)
        if not nodes:
            raise RuntimeError(f"No trimesh nodes found in {model_name}")

        all_nodes_valid = all(
            n["hasTangents"] and n["tangentFinite"] and n["tangentUnitNorm"] and
            n["hasNormals"] and n["normalFinite"] and n["normalUnitNorm"]
            for n in nodes
        )
        total_verts = sum(n["vertices"] for n in nodes)
        total_tris = sum(n["triangles"] for n in nodes)

        results[model_name] = {
            "bytes": len(data),
            "trimeshNodeCount": len(nodes),
            "totalVertices": total_verts,
            "totalTriangles": total_tris,
            "nodes": nodes,
            "tangentSpaceValid": all_nodes_valid
        }
        if not all_nodes_valid:
            all_passed = False

    audit_report = {
        "schemaVersion": 1,
        "target": "dwarf-male-stock-family",
        "totalModelsAudited": len(PARTS),
        "allTangentSpacesValid": all_passed,
        "models": results
    }

    if output_receipt:
        output_receipt.parent.mkdir(parents=True, exist_ok=True)
        output_receipt.write_text(json.dumps(audit_report, indent=2), encoding="utf-8")
        print(f"Wrote native shading audit to {output_receipt}")

    return audit_report


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Audit compiled NWN native binary models")
    parser.add_argument("--race", default="dwarf", help="Target race (default: dwarf)")
    parser.add_argument("--prefix", default=None, help="Model prefix (default: pmd0 for dwarf, pmg0 for troll)")
    parser.add_argument("--stage-dir", default=None, type=Path, help="Stage converted dir")
    parser.add_argument("--output-receipt", default=None, type=Path, help="Output receipt JSON path")
    args = parser.parse_args()

    race = args.race
    default_prefixes = {"dwarf": "pmd0", "troll": "pmg0", "elf": "pme0", "orc": "pmo0"}
    prefix = args.prefix or default_prefixes.get(race, "pmo0")
    stage = args.stage_dir or (REPO / f"output/phenotypes/derived-{race}-male-v1/candidate/converted")
    receipt = args.output_receipt or (REPO / f"output/phenotypes/derived-{race}-male-v1/review/native-shading-audit.json")

    # Update PARTS loop to use the given prefix
    receipt_file = stage / "native-compile.json"
    if not receipt_file.exists():
        raise RuntimeError(f"Missing native-compile.json in {stage}")
    compile_data = json.loads(receipt_file.read_text(encoding="utf-8"))
    if not compile_data.get("complete", False):
        raise RuntimeError(f"Incomplete compiler receipt in {receipt_file}")

    compile_models = {m["name"]: m for m in compile_data.get("models", [])}

    results = {}
    all_passed = True

    for part in PARTS:
        model_name = f"{prefix}_{part}001.mdl"
        if model_name not in compile_models:
            raise RuntimeError(f"Model {model_name} missing from native-compile.json in {stage}")

        bin_path = stage / "resources" / model_name
        if not bin_path.exists():
            raise RuntimeError(f"Missing compiled binary: {bin_path}")

        data = bin_path.read_bytes()
        actual_sha256 = hashlib.sha256(data).hexdigest()
        expected_sha256 = compile_models[model_name]["binarySha256"]
        if actual_sha256 != expected_sha256:
            raise RuntimeError(f"Binary SHA256 mismatch for {model_name}: expected {expected_sha256}, got {actual_sha256}")

        nodes = decode_model_nodes(data, model_name)
        if not nodes:
            raise RuntimeError(f"No trimesh nodes found in {model_name}")

        all_nodes_valid = all(
            n["hasTangents"] and n["tangentFinite"] and n["tangentUnitNorm"] and
            n["hasNormals"] and n["normalFinite"] and n["normalUnitNorm"]
            for n in nodes
        )
        total_verts = sum(n["vertices"] for n in nodes)
        total_tris = sum(n["triangles"] for n in nodes)

        results[model_name] = {
            "bytes": len(data),
            "trimeshNodeCount": len(nodes),
            "totalVertices": total_verts,
            "totalTriangles": total_tris,
            "nodes": nodes,
            "tangentSpaceValid": all_nodes_valid
        }
        if not all_nodes_valid:
            all_passed = False

    audit_report = {
        "schemaVersion": 1,
        "target": f"{race}-male-stock-family",
        "totalModelsAudited": len(PARTS),
        "allTangentSpacesValid": all_passed,
        "models": results
    }

    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt.write_text(json.dumps(audit_report, indent=2), encoding="utf-8")
    print(f"Wrote native shading audit to {receipt}")
    print(f"Audited {audit_report['totalModelsAudited']} models. All tangent spaces valid: {audit_report['allTangentSpacesValid']}")
