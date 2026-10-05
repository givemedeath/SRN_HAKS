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


def evaluate_connector_motion(
    parent_path: Path,
    child_path: Path,
    parent_joint: str,
    child_joint: str,
    stock_ascii_dir: Path,
    motion_samples: list[dict] = MOTION_SAMPLES,
) -> dict:
    """Evaluate axial overlap and corner proximity across animation clips."""
    text_p = parent_path.read_text(encoding="cp1252")
    text_c = child_path.read_text(encoding="cp1252")

    verts_p = np.array(arrays(text_p, "verts"), dtype=float)
    verts_c = np.array(arrays(text_c, "verts"), dtype=float)

    sample_results = []
    min_overlap = float("inf")
    worst_clip = None

    for s in motion_samples:
        clip = s["clip"]
        t = s["time"]
        xforms, _ = pose(stock_ascii_dir, "pmd0", clip, t, stock_dir=stock_ascii_dir)

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

        has_overlap = bool(np.all(overlap_span > 0))
        z_overlap = float(overlap_span[2]) if has_overlap else 0.0

        if z_overlap < min_overlap:
            min_overlap = z_overlap
            worst_clip = clip

        sample_results.append({
            "clip": clip,
            "time": t,
            "label": s["label"],
            "standing": s.get("standing", False),
            "has3DOverlap": has_overlap,
            "axialOverlapZ": z_overlap,
            "overlapSpanX": float(overlap_span[0]) if has_overlap else 0.0,
            "overlapSpanY": float(overlap_span[1]) if has_overlap else 0.0,
        })

    return {
        "parentModel": parent_path.stem,
        "childModel": child_path.stem,
        "parentJoint": parent_joint,
        "childJoint": child_joint,
        "standingOverlapZ": sample_results[0]["axialOverlapZ"],
        "worstMotionOverlapZ": min_overlap,
        "worstMotionClip": worst_clip,
        "allPosesHaveOverlap": all(r["has3DOverlap"] for r in sample_results),
        "samples": sample_results,
    }


def build_all_review_packets(
    target_data: dict,
    ascii_dir: Path,
    stock_ascii_dir: Path,
    output_dir: Path,
) -> dict:
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    prefix = target_data["identity"]["prefix"]

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
        res = evaluate_connector_motion(p_path, c_path, p_joint, c_joint, stock_ascii_dir)
        reports[label] = res

    all_ok = all(r["allPosesHaveOverlap"] for r in reports.values())
    summary = {
        "schemaVersion": 1,
        "kind": "derived-motion-review-summary",
        "targetId": target_data["id"],
        "allConnectorsOverlapInAllPoses": all_ok,
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
    )
    print(f"Motion review evaluation: {'PASSED (all poses overlap)' if summary['allConnectorsOverlapInAllPoses'] else 'FAILED'}")
    for name, c in summary["connectors"].items():
        print(f"  {name:16s}: standing_overlap={c['standingOverlapZ']*1000:.1f}mm, worst_motion={c['worstMotionOverlapZ']*1000:.1f}mm (in {c['worstMotionClip']}), all_ok={c['allPosesHaveOverlap']}")
    print(f"Summary written to {args.output_dir / 'motion-review-summary.json'}")

    if not summary.get("allConnectorsOverlapInAllPoses", False):
        print("ERROR: Motion review failed: one or more connectors lost overlap in sampled poses", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
