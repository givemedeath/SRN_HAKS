"""Generate review configs and execute joint review packets for derived dwarf connectors."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_geometry import arrays
from target_contract import PART_JOINTS, require
from pose_preview_bridge import pose


def sha256_file(path: Path | str) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


MOTION_SAMPLES = [
    {"clip": "pause1", "time": 0.0, "standing": True, "label": "Standing Rest Pose"},
    {"clip": "plreadyr", "time": 0.5, "standing": False, "label": "Combat Ready Stance"},
    {"clip": "plslashr", "time": 0.6, "standing": False, "label": "Melee Slash Swing"},
    {"clip": "run", "time": 0.3, "standing": False, "label": "Running Stride"},
    {"clip": "gutokdf", "time": 0.5, "standing": False, "label": "Knockdown/Crouch Flexion"},
]


def connector_vertex_distances(parent: np.ndarray, child: np.ndarray) -> dict:
    """Symmetric worst-case nearest-vertex distance, with bounded working memory.

    This conservative vertex coverage check does not certify triangle interiors
    or visible anatomy. Every selected interface vertex must meet the limit.
    """
    def directed(a, b):
        nearest = np.full(len(a), np.inf)
        for i in range(0, len(a), 250):
            best = np.full(min(250, len(a) - i), np.inf)
            for j in range(0, len(b), 250):
                distances = np.sum((a[i:i+250, None, :] - b[None, j:j+250, :]) ** 2, axis=2)
                best = np.minimum(best, distances.min(axis=1))
            nearest[i:i+250] = np.sqrt(best)
        return nearest
    if not len(parent) or not len(child):
        return {"minimum": np.inf, "parentMaximum": np.inf, "childMaximum": np.inf,
                "maximum": np.inf, "parentCoverage": 0.0, "childCoverage": 0.0}
    p, c = directed(parent, child), directed(child, parent)
    return {"minimum": float(min(p.min(), c.min())), "parentMaximum": float(p.max()),
            "childMaximum": float(c.max()), "maximum": float(max(p.max(), c.max())),
            "parentCoverage": float(np.mean(p < 0.015)), "childCoverage": float(np.mean(c < 0.015))}


def evaluate_connector_motion(
    parent_path: Path,
    child_path: Path,
    parent_joint: str,
    child_joint: str,
    stock_ascii_dir: Path,
    motion_samples: list[dict] = MOTION_SAMPLES,
    prefix: str = "pmd0",
    model_ascii_dir: Path | None = None,
    rig_dir: Path | None = None,
    posed_frames: list[tuple[dict, dict]] | None = None,
) -> dict:
    """Evaluate axial overlap and connector surface proximity across animation clips."""
    text_p = parent_path.read_text(encoding="cp1252")
    text_c = child_path.read_text(encoding="cp1252")

    verts_p = np.array(arrays(text_p, "verts"), dtype=float)
    verts_c = np.array(arrays(text_c, "verts"), dtype=float)

    sample_results = []
    min_axial_overlap = float("inf")
    max_surf_dist = 0.0
    worst_clip = None

    frames_to_eval = posed_frames
    if frames_to_eval is None:
        pose_dir = rig_dir or (model_ascii_dir if (model_ascii_dir and (model_ascii_dir / f"{prefix}.mdl").exists()) else stock_ascii_dir)
        frames_to_eval = []
        for s in motion_samples:
            xforms, _ = pose(pose_dir, prefix, s["clip"], s["time"], stock_dir=stock_ascii_dir)
            frames_to_eval.append((s, xforms))

    require(bool(frames_to_eval), "Motion review requires at least one pose")
    # Freeze interface membership in the standing/reference pose. A vertex that
    # moves away during motion must remain in the measurement, even outside the
    # 15 cm neighborhood or the posed axial-overlap interval.
    reference = next((x for sample, x in frames_to_eval if sample.get("standing")), frames_to_eval[0][1])
    reference_center = reference[child_joint.lower()][:3, 3]
    def interface_mask(vertices, joint):
        frame = reference[joint.lower()]
        world = vertices @ frame[:3, :3].T + frame[:3, 3]
        return np.linalg.norm(world - reference_center, axis=1) < 0.15
    parent_interface = interface_mask(verts_p, parent_joint)
    child_interface = interface_mask(verts_c, child_joint)
    worst_surface_clip = None
    worst_surface_time = None

    for s, xforms in frames_to_eval:
        clip = s["clip"]
        t = s["time"]

        m_p = xforms[parent_joint.lower()]
        m_c = xforms[child_joint.lower()]

        # Transform to world pose
        w_p = verts_p @ m_p[:3, :3].T + m_p[:3, 3]
        w_c = verts_c @ m_c[:3, :3].T + m_c[:3, 3]

        min_p, max_p = w_p.min(axis=0), w_p.max(axis=0)
        min_c, max_c = w_c.min(axis=0), w_c.max(axis=0)

        overlap_min = np.maximum(min_p, min_c)
        overlap_max = np.minimum(max_p, max_c)
        overlap_span = overlap_max - overlap_min

        has_3d_overlap = bool(np.all(overlap_span > 0))
        z_overlap = float(overlap_span[2]) if has_3d_overlap else 0.0

        # Project along parent-to-child joint axis vector
        p_pos = m_p[:3, 3]
        c_pos = m_c[:3, 3]
        axis_vec = c_pos - p_pos
        norm_axis = np.linalg.norm(axis_vec)
        u_axis = axis_vec / norm_axis if norm_axis > 1e-6 else np.array([0.0, 0.0, -1.0])

        proj_p = w_p @ u_axis
        proj_c = w_c @ u_axis
        ol_start = max(float(proj_p.min()), float(proj_c.min()))
        ol_end = min(float(proj_p.max()), float(proj_c.max()))
        axial_overlap = max(0.0, ol_end - ol_start)

        distances = connector_vertex_distances(w_p[parent_interface], w_c[child_interface])
        min_surface_dist = distances["minimum"]
        worst_surface_dist = distances["maximum"]

        has_axial_overlap = bool(axial_overlap > 0.005)
        has_surface_proximity = bool(worst_surface_dist < 0.015)
        pose_passed = bool(has_3d_overlap and has_axial_overlap and has_surface_proximity)

        if axial_overlap < min_axial_overlap:
            min_axial_overlap = axial_overlap
            worst_clip = clip

        if worst_surface_clip is None or worst_surface_dist > max_surf_dist:
            max_surf_dist = worst_surface_dist
            worst_surface_clip = clip
            worst_surface_time = t

        sample_results.append({
            "clip": clip,
            "time": t,
            "label": s["label"],
            "standing": s.get("standing", False),
            "has3DOverlap": has_3d_overlap,
            "axialOverlapZ": z_overlap,
            "axialOverlapMeters": axial_overlap,
            "overlapSpanX": float(overlap_span[0]) if has_3d_overlap else 0.0,
            "overlapSpanY": float(overlap_span[1]) if has_3d_overlap else 0.0,
            "minSurfaceDistanceMeters": min_surface_dist if min_surface_dist != float("inf") else None,
            "maxSurfaceDistanceMeters": worst_surface_dist if np.isfinite(worst_surface_dist) else None,
            "parentToChildMaxDistanceMeters": distances["parentMaximum"] if np.isfinite(distances["parentMaximum"]) else None,
            "childToParentMaxDistanceMeters": distances["childMaximum"] if np.isfinite(distances["childMaximum"]) else None,
            "parentInterfaceCoverage": distances["parentCoverage"],
            "childInterfaceCoverage": distances["childCoverage"],
            "parentInterfaceVertexCount": int(parent_interface.sum()),
            "childInterfaceVertexCount": int(child_interface.sum()),
            "hasAxialOverlap": has_axial_overlap,
            "hasSurfaceProximity": has_surface_proximity,
            "passed": pose_passed,
        })

    return {
        "parentModel": parent_path.stem,
        "childModel": child_path.stem,
        "parentJoint": parent_joint,
        "childJoint": child_joint,
        "standingOverlapZ": sample_results[0]["axialOverlapZ"],
        "standingAxialOverlap": sample_results[0]["axialOverlapMeters"],
        "standingSurfaceDistance": sample_results[0]["maxSurfaceDistanceMeters"],
        "worstMotionOverlapZ": sample_results[0]["axialOverlapZ"],
        "worstMotionAxialOverlap": min_axial_overlap,
        "surfaceDistancePolicy": "symmetric-worst-case-nearest-interface-vertex",
        "worstMotionSurfaceDistance": max_surf_dist if np.isfinite(max_surf_dist) else None,
        "worstMotionClip": worst_surface_clip,
        "worstMotionSurfaceTime": worst_surface_time,
        "worstAxialOverlapClip": worst_clip,
        "allPosesHaveOverlap": all(r["has3DOverlap"] for r in sample_results),
        "allPosesHaveAxialOverlap": all(r["hasAxialOverlap"] for r in sample_results),
        "allPosesHaveSurfaceProximity": all(r["hasSurfaceProximity"] for r in sample_results),
        "allPosesPassed": all(r["passed"] for r in sample_results),
        "samples": sample_results,
    }


def build_all_review_packets(
    target_data: dict,
    ascii_dir: Path,
    stock_ascii_dir: Path,
    output_dir: Path,
    rig_dir: Path | None = None,
) -> dict:
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    prefix = target_data.get("rig", {}).get("targetPrefix") or target_data["identity"]["prefix"]

    if rig_dir is None:
        race = target_data.get("identity", {}).get("race", "dwarf")
        gender = target_data.get("identity", {}).get("gender", "male")
        candidate_rig = Path(f"output/phenotypes/derived-v1/rigs/{race}-{gender}")
        if candidate_rig.exists() and (candidate_rig / f"{prefix}.mdl").exists():
            rig_dir = candidate_rig
        elif (ascii_dir / f"{prefix}.mdl").exists():
            rig_dir = ascii_dir
        else:
            rig_dir = stock_ascii_dir

    pose_root = rig_dir or (ascii_dir if (ascii_dir / f"{prefix}.mdl").exists() else stock_ascii_dir)
    posed_frames = []
    for s in MOTION_SAMPLES:
        xforms, _ = pose(pose_root, prefix, s["clip"], s["time"], stock_dir=stock_ascii_dir)
        posed_frames.append((s, xforms))

    connectors = [
        ("chest", "pelvis", "torso_g", "pelvis_g", "waist"),
        ("chest", "bicepl", "torso_g", "lbicep_g", "shoulder_left"),
        ("chest", "bicepr", "torso_g", "rbicep_g", "shoulder_right"),
        ("bicepl", "forel", "lbicep_g", "lforearm_g", "elbow_left"),
        ("bicepr", "forer", "rbicep_g", "rforearm_g", "elbow_right"),
        ("forel", "handl", "lforearm_g", "lhand_g", "wrist_left"),
        ("forer", "handr", "rforearm_g", "rhand_g", "wrist_right"),
        ("pelvis", "legl", "pelvis_g", "lthigh_g", "hip_left"),
        ("pelvis", "legr", "pelvis_g", "rthigh_g", "hip_right"),
        ("legl", "shinl", "lthigh_g", "lshin_g", "knee_left"),
        ("legr", "shinr", "rthigh_g", "rshin_g", "knee_right"),
        ("shinl", "footl", "lshin_g", "lfoot_g", "ankle_left"),
        ("shinr", "footr", "rshin_g", "rfoot_g", "ankle_right"),
    ]

    reports = {}
    for p_part, c_part, p_joint, c_joint, label in connectors:
        p_path = ascii_dir / f"{prefix}_{p_part}001.mdl"
        c_path = ascii_dir / f"{prefix}_{c_part}001.mdl"
        res = evaluate_connector_motion(
            p_path, c_path, p_joint, c_joint, stock_ascii_dir,
            prefix=prefix, model_ascii_dir=ascii_dir, rig_dir=rig_dir,
            posed_frames=posed_frames,
        )
        reports[label] = res

    all_ok = all(r["allPosesPassed"] for r in reports.values())
    summary = {
        "schemaVersion": 1,
        "kind": "derived-motion-review-summary",
        "targetId": target_data["id"],
        "posePrefix": prefix,
        "allConnectorsOverlapInAllPoses": all_ok,
        "allConnectorsPassMotionSurfaces": all_ok,
        "connectorCount": len(reports),
        "motionSamplesEvaluated": len(MOTION_SAMPLES),
        "connectors": reports,
    }

    summary_file = output_dir / "motion-review-summary.json"
    summary_file.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target",
        type=Path,
        default=Path("tools/phenotypes/configurations/derived/target-dwarf-male-stock.json"),
    )
    parser.add_argument(
        "--ascii-dir",
        type=Path,
        default=Path("output/phenotypes/derived-v1/parts/dwarf-male/ascii"),
    )
    parser.add_argument(
        "--stock-ascii-dir",
        type=Path,
        default=Path("output/phenotypes/derived-v1/stock-cache/ascii"),
    )
    parser.add_argument(
        "--rig-dir",
        type=Path,
        default=None,
        help="Directory containing the derived rig root (<prefix>.mdl); defaults to output/phenotypes/derived-v1/rigs/<race>-<gender>",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/phenotypes/derived-v1/review/dwarf-male"),
    )
    args = parser.parse_args()

    target_data = json.loads(args.target.read_text(encoding="utf-8"))
    summary = build_all_review_packets(
        target_data,
        args.ascii_dir,
        args.stock_ascii_dir,
        args.output_dir,
        rig_dir=args.rig_dir,
    )
    passed = summary.get("allConnectorsPassMotionSurfaces", summary.get("allConnectorsOverlapInAllPoses", False))
    print(f"Motion review evaluation: {'PASSED (all poses overlap and meet surface tolerances)' if passed else 'FAILED'}")
    for name, c in summary["connectors"].items():
        surf_str = f"{c['worstMotionSurfaceDistance']*1000:.2f}mm" if c.get("worstMotionSurfaceDistance") else "N/A"
        ax_str = f"{c.get('worstMotionAxialOverlap', c['worstMotionOverlapZ'])*1000:.1f}mm"
        print(f"  {name:16s}: worst_axial={ax_str}, worst_surface={surf_str} (in {c['worstMotionClip']}), passed={c.get('allPosesPassed', c['allPosesHaveOverlap'])}")
    print(f"Summary written to {args.output_dir / 'motion-review-summary.json'}")

    if not passed:
        print("ERROR: Motion review failed: one or more connectors lost overlap or surface proximity in sampled poses", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
