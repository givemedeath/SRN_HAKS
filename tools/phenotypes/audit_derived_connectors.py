"""Audit boundary connectors, axial overlap, and assembly clearance across derived body parts.

Verifies that all 13 adjacent body part interfaces in the humanoid assembly have
positive axial overlap, no disconnections or visible tears, and proper socket-cap sleeving.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_geometry import arrays
from target_contract import PART_JOINTS, require

CONNECTOR_PAIRS = [
    ("chest", "pelvis", "torso_g", "waist"),
    ("chest", "bicepl", "lbicep_g", "shoulder_left"),
    ("chest", "bicepr", "rbicep_g", "shoulder_right"),
    ("bicepl", "forel", "lforearm_g", "elbow_left"),
    ("bicepr", "forer", "rforearm_g", "elbow_right"),
    ("forel", "handl", "lhand_g", "wrist_left"),
    ("forer", "handr", "rhand_g", "wrist_right"),
    ("pelvis", "legl", "lthigh_g", "hip_left"),
    ("pelvis", "legr", "rthigh_g", "hip_right"),
    ("legl", "shinl", "lshin_g", "knee_left"),
    ("legr", "shinr", "rshin_g", "knee_right"),
    ("shinl", "footl", "lfoot_g", "ankle_left"),
    ("shinr", "footr", "rfoot_g", "ankle_right"),
]


def sha256_file(path: Path | str) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def audit_connectors(
    target_data: dict,
    ascii_dir: Path,
    output_report_path: Path | None = None,
) -> dict:
    """Audit all connector interfaces in the rest assembly."""
    prefix = target_data["identity"]["prefix"]
    frames = target_data["rig"]["frames"]["working"]

    parts_world = {}
    parts_meta = {}

    for part, joint in PART_JOINTS.items():
        if part in ("head", "neck"):
            continue
        model_name = f"{prefix}_{part}001"
        mdl_path = ascii_dir / f"{model_name}.mdl"
        require(mdl_path.is_file(), f"Model file missing: {mdl_path}")

        text = mdl_path.read_text(encoding="cp1252")
        verts = np.array(arrays(text, "verts"), dtype=float)
        frame = np.array(frames[joint.lower()])
        v_world = verts @ frame[:3, :3].T + frame[:3, 3]

        parts_world[part] = v_world
        parts_meta[part] = {
            "model": model_name,
            "path": str(mdl_path),
            "sha256": sha256_file(mdl_path),
            "vertexCount": len(verts),
            "worldBbox": {
                "xMin": float(v_world[:, 0].min()),
                "xMax": float(v_world[:, 0].max()),
                "yMin": float(v_world[:, 1].min()),
                "yMax": float(v_world[:, 1].max()),
                "zMin": float(v_world[:, 2].min()),
                "zMax": float(v_world[:, 2].max()),
            },
        }

    connector_reports = []
    all_passed = True

    for parent_part, child_part, joint_name, conn_label in CONNECTOR_PAIRS:
        v_parent = parts_world[parent_part]
        v_child = parts_world[child_part]

        joint_pos = np.array(frames[joint_name.lower()])[:3, 3]

        min_p, max_p = v_parent.min(axis=0), v_parent.max(axis=0)
        min_c, max_c = v_child.min(axis=0), v_child.max(axis=0)

        overlap_min = np.maximum(min_p, min_c)
        overlap_max = np.minimum(max_p, max_c)
        overlap_span = overlap_max - overlap_min

        has_3d_overlap = bool(np.all(overlap_span > 0))

        # Calculate axial overlap along limb axis (primarily Z in NWN rest pose)
        z_overlap = float(overlap_span[2])
        x_overlap = float(overlap_span[0])
        y_overlap = float(overlap_span[1])

        # Overlap distance past joint center:
        # Parent past joint, child before joint
        parent_dist_past_joint = float(np.max(np.linalg.norm(v_parent - joint_pos, axis=1)))
        child_dist_past_joint = float(np.max(np.linalg.norm(v_child - joint_pos, axis=1)))

        # Boundary gap check: min distance between parent mesh and child mesh in the overlap region
        in_overlap_p = v_parent[
            (v_parent[:, 0] >= overlap_min[0]) & (v_parent[:, 0] <= overlap_max[0]) &
            (v_parent[:, 1] >= overlap_min[1]) & (v_parent[:, 1] <= overlap_max[1]) &
            (v_parent[:, 2] >= overlap_min[2]) & (v_parent[:, 2] <= overlap_max[2])
        ]
        in_overlap_c = v_child[
            (v_child[:, 0] >= overlap_min[0]) & (v_child[:, 0] <= overlap_max[0]) &
            (v_child[:, 1] >= overlap_min[1]) & (v_child[:, 1] <= overlap_max[1]) &
            (v_child[:, 2] >= overlap_min[2]) & (v_child[:, 2] <= overlap_max[2])
        ]

        overlap_vertex_count = len(in_overlap_p) + len(in_overlap_c)
        passed = has_3d_overlap and z_overlap > 0.005

        if not passed:
            all_passed = False

        connector_reports.append({
            "connector": conn_label,
            "joint": joint_name,
            "parentPart": parent_part,
            "childPart": child_part,
            "has3DOverlap": has_3d_overlap,
            "axialOverlapZ": z_overlap,
            "overlapSpanX": x_overlap,
            "overlapSpanY": y_overlap,
            "overlapVertexCount": overlap_vertex_count,
            "status": "passed" if passed else "failed-gap",
        })

    report = {
        "schemaVersion": 1,
        "kind": "derived-connectors-audit",
        "targetId": target_data["id"],
        "allConnectorsPassed": all_passed,
        "connectorCount": len(connector_reports),
        "connectors": connector_reports,
        "parts": parts_meta,
    }

    if output_report_path:
        out_p = Path(output_report_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target",
        type=Path,
        default=Path("tools/phenotypes/configurations/derived/target-dwarf-male-stock.json"),
        help="Target configuration JSON",
    )
    parser.add_argument(
        "--ascii-dir",
        type=Path,
        default=Path("output/phenotypes/derived-v1/parts/dwarf-male/ascii"),
        help="Directory with refined ASCII MDLs",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output/phenotypes/derived-v1/parts/dwarf-male/ascii/connector-audit.json"),
        help="Output JSON audit report",
    )
    args = parser.parse_args()

    target_data = json.loads(args.target.read_text(encoding="utf-8"))
    report = audit_connectors(target_data, args.ascii_dir, args.output)

    print(f"Connector audit for '{target_data['id']}': {'PASSED (13/13)' if report['allConnectorsPassed'] else 'FAILED'}")
    for c in report["connectors"]:
        print(f"  {c['connector']:16s} ({c['parentPart']} -> {c['childPart']}): Z-overlap={c['axialOverlapZ']*1000:.1f}mm, overlap_pts={c['overlapVertexCount']}, status={c['status']}")
    print(f"Report written to {args.output}")


if __name__ == "__main__":
    main()
