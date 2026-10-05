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
    raise_on_failure: bool = False,
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

        # Calculate bounding box overlap spans
        z_overlap = float(overlap_span[2])
        x_overlap = float(overlap_span[0])
        y_overlap = float(overlap_span[1])

        # Project vertices along parent-to-child joint axis vector
        p_joint_name = PART_JOINTS.get(parent_part, joint_name).lower()
        c_joint_name = PART_JOINTS.get(child_part, joint_name).lower()
        p_pos = np.array(frames[p_joint_name])[:3, 3]
        c_pos = np.array(frames[c_joint_name])[:3, 3]
        axis_vec = c_pos - p_pos
        norm_axis = np.linalg.norm(axis_vec)
        u_axis = axis_vec / norm_axis if norm_axis > 1e-6 else np.array([0.0, 0.0, -1.0])

        proj_p = v_parent @ u_axis
        proj_c = v_child @ u_axis
        ol_start = max(float(proj_p.min()), float(proj_c.min()))
        ol_end = min(float(proj_p.max()), float(proj_c.max()))
        axial_overlap = max(0.0, ol_end - ol_start)

        # Boundary gap check in the 3D overlap region
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

        # Measure surface proximity on vertices near the joint interface (within 15 cm of child joint center)
        dp = np.linalg.norm(v_parent - c_pos, axis=1)
        dc = np.linalg.norm(v_child - c_pos, axis=1)
        near_p = v_parent[dp < 0.15]
        near_c = v_child[dc < 0.15]

        # Points in the axial overlap region near the joint
        in_ax_p = near_p[(near_p @ u_axis >= ol_start) & (near_p @ u_axis <= ol_end)]
        in_ax_c = near_c[(near_c @ u_axis >= ol_start) & (near_c @ u_axis <= ol_end)]

        min_surface_dist = float("inf")
        pts_c = in_ax_c if (len(in_ax_c) > 0 and len(in_ax_p) > 0) else near_c
        pts_p = in_ax_p if (len(in_ax_c) > 0 and len(in_ax_p) > 0) else near_p

        if len(pts_c) > 0 and len(pts_p) > 0:
            for i in range(0, len(pts_c), 500):
                chunk = pts_c[i:i + 500]
                d = np.min(np.linalg.norm(chunk[:, None, :] - pts_p[None, :, :], axis=2))
                if d < min_surface_dist:
                    min_surface_dist = float(d)

        has_surface_proximity = bool(min_surface_dist < 0.005)
        has_axial_overlap = bool(axial_overlap > 0.005)
        passed = bool(has_3d_overlap and has_axial_overlap and has_surface_proximity)

        if not passed:
            all_passed = False

        connector_reports.append({
            "connector": conn_label,
            "joint": joint_name,
            "parentPart": parent_part,
            "childPart": child_part,
            "has3DOverlap": has_3d_overlap,
            "axialOverlapZ": z_overlap,
            "axialOverlapMeters": axial_overlap,
            "jointAxis": [round(float(x), 4) for x in u_axis],
            "overlapSpanX": x_overlap,
            "overlapSpanY": y_overlap,
            "overlapVertexCount": overlap_vertex_count,
            "minSurfaceDistanceMeters": min_surface_dist if min_surface_dist != float("inf") else None,
            "hasSurfaceProximity": has_surface_proximity,
            "hasAxialOverlap": has_axial_overlap,
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

    if raise_on_failure and not all_passed:
        raise RuntimeError(f"Gate 2b connector audit failed for '{target_data['id']}': one or more connectors failed overlap/surface checks")

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
        surf_str = f"{c['minSurfaceDistanceMeters']*1000:.2f}mm" if c['minSurfaceDistanceMeters'] is not None else "N/A"
        print(f"  {c['connector']:16s} ({c['parentPart']} -> {c['childPart']}): Z-overlap={c['axialOverlapZ']*1000:.1f}mm, surf_dist={surf_str}, overlap_pts={c['overlapVertexCount']}, status={c['status']}")
    print(f"Report written to {args.output}")

    if not report["allConnectorsPassed"]:
        print(f"ERROR: Gate 2b connector audit failed for '{target_data['id']}': one or more connectors failed overlap/surface checks")
        sys.exit(1)


if __name__ == "__main__":
    main()
