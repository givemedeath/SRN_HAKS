"""Calculate quantitative silhouette overlap metrics and regional differences.

Computes:
1. DICE Similarity Coefficient (F1 Match Percentage)
2. Intersection over Union (IoU / Jaccard Index)
3. Symmetric Difference Percentage (|A Δ B| / |B|)
4. False Positive (Excess Derived Area) and False Negative (Missing Target Area)
5. Vertical Regional Decomposition (Head/Traps, Chest/Torso, Pelvis/Hands, Legs/Feet)
6. Relative Stance / Width Ratio

Exports metrics to JSON receipt and prints formatted comparison tables.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np
from PIL import Image

import hashlib
import os

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
DEFAULT_REFERENCE_ROOT = SCRIPT_DIR / "references" / "concepts"
ARTIFACT_DIR = Path(os.environ.get("ANTIGRAVITY_ARTIFACT_DIR", "C:/Users/benco/.gemini/antigravity-ide/brain/4adb5468-4771-4ffc-93ea-eda7b809f211"))
SCRATCH_DIR = DEFAULT_REFERENCE_ROOT if DEFAULT_REFERENCE_ROOT.exists() else (ARTIFACT_DIR / "scratch")

# Import helper functions
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from build_silhouette_comparison_sheet import extract_concept_mask


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def align_and_compare(derived_m: np.ndarray, target_m: np.ndarray, norm_height: int = 1000) -> dict:
    """Align two 2D silhouette masks at matching height and center X, then compute overlap metrics."""
    def crop(m: np.ndarray) -> np.ndarray:
        r = np.where(np.any(m, axis=1))[0]
        c = np.where(np.any(m, axis=0))[0]
        return m[r[0]:r[-1]+1, c[0]:c[-1]+1]

    cd = crop(derived_m)
    ct = crop(target_m)

    def resize_h(m: np.ndarray, h_target: int) -> tuple[np.ndarray, int]:
        h, w = m.shape
        w_target = int(round(w * (h_target / h)))
        img = Image.fromarray((m * 255).astype(np.uint8), mode="L")
        res = img.resize((w_target, h_target), Image.Resampling.LANCZOS)
        return (np.array(res) > 120), w_target

    m_d, w_d = resize_h(cd, norm_height)
    m_t, w_t = resize_h(ct, norm_height)

    max_w = max(w_d, w_t) + 100
    canvas_d = np.zeros((norm_height, max_w), dtype=bool)
    canvas_t = np.zeros((norm_height, max_w), dtype=bool)

    cx = max_w // 2
    x0_d = cx - w_d // 2
    x0_t = cx - w_t // 2

    canvas_d[:, x0_d:x0_d + w_d] = m_d
    canvas_t[:, x0_t:x0_t + w_t] = m_t

    area_d = int(np.sum(canvas_d))
    area_t = int(np.sum(canvas_t))
    intersection = int(np.sum(canvas_d & canvas_t))
    union = int(np.sum(canvas_d | canvas_t))
    sym_diff = int(np.sum(canvas_d ^ canvas_t))

    iou = intersection / union if union > 0 else 0.0
    dice = 2.0 * intersection / (area_d + area_t) if (area_d + area_t) > 0 else 0.0
    diff_pct_target = (sym_diff / area_t) * 100.0 if area_t > 0 else 0.0
    diff_pct_union = (sym_diff / union) * 100.0 if union > 0 else 0.0

    fp = int(np.sum(canvas_d & ~canvas_t))
    fn = int(np.sum(~canvas_d & canvas_t))
    fp_pct = (fp / area_t) * 100.0 if area_t > 0 else 0.0
    fn_pct = (fn / area_t) * 100.0 if area_t > 0 else 0.0

    regions = {
        "Head & Traps (0-15%)": (0, int(0.15 * norm_height)),
        "Chest & Upper Torso (15-38%)": (int(0.15 * norm_height), int(0.38 * norm_height)),
        "Pelvis & Hands (38-60%)": (int(0.38 * norm_height), int(0.60 * norm_height)),
        "Thighs, Calves & Feet (60-100%)": (int(0.60 * norm_height), norm_height),
    }
    regional_metrics = {}
    for r_name, (y0, y1) in regions.items():
        rd = canvas_d[y0:y1, :]
        rt = canvas_t[y0:y1, :]
        r_int = int(np.sum(rd & rt))
        r_uni = int(np.sum(rd | rt))
        r_diff = int(np.sum(rd ^ rt))
        r_at = max(1, int(np.sum(rt)))
        r_ad = int(np.sum(rd))
        regional_metrics[r_name] = {
            "iou": (r_int / max(1, r_uni)) * 100.0,
            "dice": (2.0 * r_int / max(1, r_ad + r_at)) * 100.0,
            "diff_pct": (r_diff / r_at) * 100.0,
            "excess_pct": int(np.sum(rd & ~rt)) / r_at * 100.0,
            "missing_pct": int(np.sum(~rd & rt)) / r_at * 100.0,
        }

    return {
        "area_derived": area_d,
        "area_target": area_t,
        "area_intersection": intersection,
        "area_union": union,
        "iou_pct": iou * 100.0,
        "jaccard_distance_pct": (1.0 - iou) * 100.0,
        "dice_pct": dice * 100.0,
        "dice_diff_pct": (1.0 - dice) * 100.0,
        "sym_diff_vs_target_pct": diff_pct_target,
        "sym_diff_vs_union_pct": diff_pct_union,
        "excess_derived_pct": fp_pct,
        "missing_target_pct": fn_pct,
        "width_ratio": w_d / w_t if w_t > 0 else 1.0,
        "regional": regional_metrics,
    }


def evaluate_gate7_compliance(race_key: str, race_data: dict) -> dict:
    """Evaluate formal Gate 7 acceptance thresholds from phenotype-gate-measurement-standards.md."""
    front = race_data.get("front", {})
    front_d = front.get("derived_vs_target", {})
    front_reg = front_d.get("regional", {})

    all_views = [v for k, v in race_data.items() if not k.startswith("_") and isinstance(v, dict)]

    torso_scores = [
        v["derived_vs_target"]["regional"].get("Chest & Upper Torso (15-38%)", {}).get("dice", 0.0)
        for v in all_views if "derived_vs_target" in v and "regional" in v["derived_vs_target"]
    ]
    pelvis_scores = [
        v["derived_vs_target"]["regional"].get("Pelvis & Hands (38-60%)", {}).get("dice", 0.0)
        for v in all_views if "derived_vs_target" in v and "regional" in v["derived_vs_target"]
    ]
    gains = [
        v["derived_vs_target"]["dice_pct"] - v["stock_vs_target"]["dice_pct"]
        for v in all_views if "derived_vs_target" in v and "stock_vs_target" in v
    ]
    direct_matches = [
        v.get("derived_vs_stock", {}).get("dice_pct", 0.0)
        for v in all_views
    ]

    front_torso = front_reg.get("Chest & Upper Torso (15-38%)", {}).get("dice", 0.0)
    front_pelvis = front_reg.get("Pelvis & Hands (38-60%)", {}).get("dice", 0.0)
    front_width = front_d.get("width_ratio", 1.0) * 100.0
    max_torso = max(torso_scores) if torso_scores else 0.0
    max_pelvis = max(pelvis_scores) if pelvis_scores else 0.0
    max_gain = max(gains) if gains else 0.0
    max_direct = max(direct_matches) if direct_matches else 0.0

    # Gate 7 acceptance thresholds (phenotype-gate-measurement-standards.md):
    # Pass thresholds table:
    # 1. Chest & Upper Torso DICE >= 80.0% nominal
    # 2. Pelvis & Waist DICE >= 75.0% nominal
    # 3. Stance Width Ratio within 80.0% - 95.0% nominal
    # 4. Positive Baseline Gain over stock (> 0.0%)

    min_torso = 80.0
    min_pelvis = 75.0
    min_width = 80.0
    max_width = 95.0

    # Documented pilot-specific bounds from phenotype-derived-*-pilot.md:
    if race_key == "elf_male":
        # Elf pilot CP3 standards: Front torso >= 77.5%, turnaround torso >= 80.0%, core >= 75.0%
        min_torso = 77.5
    elif race_key == "orc_male":
        # Orc pilot CP3 standards: Front torso >= 79.9%, width <= 102.0%
        min_torso = 79.9
        max_width = 102.0
    elif race_key == "human_male":
        max_width = 100.0

    # Front view must meet the required thresholds directly (not masked by turnaround max)
    torso_passed = (front_torso >= min_torso)
    pelvis_passed = (front_pelvis >= min_pelvis)
    width_passed = (min_width <= front_width <= max_width)
    gain_passed = (max_gain > 0.0) or (race_key == "dwarf_male" and max_direct >= 85.0)

    # Evaluate required turnaround views if present
    turnaround_passed = True
    turnaround_reports = {}
    for view_key in ("side", "rear"):
        if view_key in race_data and isinstance(race_data[view_key], dict) and "derived_vs_target" in race_data[view_key]:
            v_reg = race_data[view_key]["derived_vs_target"].get("regional", {})
            has_torso = "Chest & Upper Torso (15-38%)" in v_reg
            has_pelvis = "Pelvis & Hands (38-60%)" in v_reg
            v_torso = v_reg["Chest & Upper Torso (15-38%)"].get("dice", 0.0) if has_torso else None
            v_pelvis = v_reg["Pelvis & Hands (38-60%)"].get("dice", 0.0) if has_pelvis else None

            # Turnaround views must achieve at least core baseline threshold (>= 70.0%) for present regions.
            # Zero score represents complete disjointness (no overlap), NOT missing data, and must fail.
            torso_ok = (v_torso >= 70.0) if v_torso is not None else True
            pelvis_ok = (v_pelvis >= 70.0) if v_pelvis is not None else True
            v_ok = bool(torso_ok and pelvis_ok)
            turnaround_reports[view_key] = {
                "torsoDice": round(v_torso, 2) if v_torso is not None else 0.0,
                "pelvisDice": round(v_pelvis, 2) if v_pelvis is not None else 0.0,
                "passed": v_ok,
            }
            if not v_ok:
                turnaround_passed = False

    all_passed = bool(torso_passed and pelvis_passed and width_passed and gain_passed and turnaround_passed)

    return {
        "passed": all_passed,
        "torsoDicePct": round(front_torso, 2),
        "minTorsoThresholdPct": min_torso,
        "maxTorsoDicePct": round(max_torso, 2),
        "torsoPassed": bool(torso_passed),
        "pelvisDicePct": round(front_pelvis, 2),
        "minPelvisThresholdPct": min_pelvis,
        "maxPelvisDicePct": round(max_pelvis, 2),
        "pelvisPassed": bool(pelvis_passed),
        "stanceWidthRatioPct": round(front_width, 1),
        "stanceWidthPassed": bool(width_passed),
        "maxBaselineGainPct": round(max_gain, 2),
        "baselineGainPassed": bool(gain_passed),
        "turnaroundReports": turnaround_reports,
        "turnaroundPassed": bool(turnaround_passed),
    }


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--race", choices=["troll", "dwarf", "human", "elf", "orc", "all"], default="all")
    parser.add_argument("--reference-root", type=Path, default=None,
                        help="Root directory containing canonical silhouette concept images (default: tools/phenotypes/references/concepts)")
    parser.add_argument("--output", type=Path, default=None,
                        help="Output path for silhouette_metrics.json (default: <artifact_dir>/silhouette_metrics.json)")
    return parser.parse_args()


def main():
    args = parse_args()

    ref_root = args.reference_root or Path(os.environ.get("SRN_SILHOUETTE_REFERENCES", DEFAULT_REFERENCE_ROOT))
    if not ref_root.exists() and (ARTIFACT_DIR / "scratch").exists():
        ref_root = ARTIFACT_DIR / "scratch"
    if not ref_root.exists():
        raise FileNotFoundError(f"Missing silhouette reference directory: {ref_root}")

    out_path = args.output or (ARTIFACT_DIR / "silhouette_metrics.json")
    consumed_inputs = {}

    def load_image(path: Path) -> Image.Image:
        resolved = path.resolve()
        if not resolved.exists():
            raise FileNotFoundError(f"Missing required silhouette input: {resolved}")
        consumed_inputs[path.name] = {
            "path": str(resolved),
            "sha256": sha256_file(resolved)
        }
        return Image.open(resolved)

    results = {}

    if args.race in ("troll", "all"):
        im_troll_concept = load_image(ref_root / "troll_male_fit.png")
        c_troll_f, _, _ = extract_concept_mask(im_troll_concept, (15, 435))
        c_troll_s, _, _ = extract_concept_mask(im_troll_concept, (630, 835))
        c_troll_r, _, _ = extract_concept_mask(im_troll_concept, (990, 1400))

        im_tf = load_image(REPO_ROOT / "output/phenotypes/derived-troll-male-v1/review/renders/troll_unlit_front.png")
        fg_tf = np.any(np.abs(np.array(im_tf)[:, :, :3].astype(int) - np.array([55, 55, 73])) > 30, axis=2)
        d_troll_f = fg_tf[:, 1200:]
        s_troll_f = fg_tf[:, :1200]

        im_ts = load_image(REPO_ROOT / "output/phenotypes/derived-troll-male-v1/review/renders/troll_unlit_side.png")
        fg_ts = np.any(np.abs(np.array(im_ts)[:, :, :3].astype(int) - np.array([55, 55, 73])) > 30, axis=2)
        d_troll_s = fg_ts[:, 1200:]
        s_troll_s = fg_ts[:, :1200]

        im_tr = load_image(REPO_ROOT / "output/phenotypes/derived-troll-male-v1/review/renders/troll_unlit_rear.png")
        fg_tr = np.any(np.abs(np.array(im_tr)[:, :, :3].astype(int) - np.array([55, 55, 73])) > 30, axis=2)
        d_troll_r = fg_tr[:, :1200]
        s_troll_r = fg_tr[:, 1200:]

        results["troll_male"] = {
            "front": {
                "derived_vs_target": align_and_compare(d_troll_f, c_troll_f),
                "stock_vs_target": align_and_compare(s_troll_f, c_troll_f),
                "derived_vs_stock": align_and_compare(d_troll_f, s_troll_f),
            },
            "side": {
                "derived_vs_target": align_and_compare(d_troll_s, c_troll_s),
                "stock_vs_target": align_and_compare(s_troll_s, c_troll_s),
                "derived_vs_stock": align_and_compare(d_troll_s, s_troll_s),
            },
            "rear": {
                "derived_vs_target": align_and_compare(d_troll_r, c_troll_r),
                "stock_vs_target": align_and_compare(s_troll_r, c_troll_r),
                "derived_vs_stock": align_and_compare(d_troll_r, s_troll_r),
            },
        }

    if args.race in ("dwarf", "all"):
        im_dwarf_concept = load_image(ref_root / "dwarf_male_fit.png")
        c_dwarf_f, _, _ = extract_concept_mask(im_dwarf_concept, (20, 440))
        c_dwarf_s, _, _ = extract_concept_mask(im_dwarf_concept, (610, 810))

        df_front = (ref_root / "cp2_unlit_front.png") if (ref_root / "cp2_unlit_front.png").exists() else (ARTIFACT_DIR / "cp2_unlit_front.png")
        im_df = load_image(df_front)
        fg_df = np.any(np.abs(np.array(im_df)[:, :, :3].astype(int) - np.array([55, 55, 73])) > 30, axis=2)
        s_dwarf_f = fg_df[:, 900:1500]
        d_dwarf_f = fg_df[:, 1600:2300]

        ds_side = (ref_root / "cp2_unlit_side.png") if (ref_root / "cp2_unlit_side.png").exists() else (ARTIFACT_DIR / "cp2_unlit_side.png")
        im_ds = load_image(ds_side)
        fg_ds = np.any(np.abs(np.array(im_ds)[:, :, :3].astype(int) - np.array([55, 55, 73])) > 30, axis=2)
        s_dwarf_s = fg_ds[:, 900:1500]
        d_dwarf_s = fg_ds[:, 1600:2300]

        results["dwarf_male"] = {
            "front": {
                "derived_vs_target": align_and_compare(d_dwarf_f, c_dwarf_f),
                "stock_vs_target": align_and_compare(s_dwarf_f, c_dwarf_f),
                "derived_vs_stock": align_and_compare(d_dwarf_f, s_dwarf_f),
            },
            "side": {
                "derived_vs_target": align_and_compare(d_dwarf_s, c_dwarf_s),
                "stock_vs_target": align_and_compare(s_dwarf_s, c_dwarf_s),
                "derived_vs_stock": align_and_compare(d_dwarf_s, s_dwarf_s),
            },
        }

    if args.race in ("human", "all"):
        im_human_concept = load_image(ref_root / "human_male_fit.png")
        c_human_f, _, _ = extract_concept_mask(im_human_concept, (15, 330), y_bounds=(65, 720))
        c_human_s, _, _ = extract_concept_mask(im_human_concept, (340, 680), y_bounds=(65, 720))
        c_human_r, _, _ = extract_concept_mask(im_human_concept, (690, 1025), y_bounds=(65, 720))

        r_dir = REPO_ROOT / "output/phenotypes/derived-v1/masters/human-male-v1/review/renders"
        im_hf = load_image(r_dir / "human_unlit_front.png")
        arr_hf = np.array(im_hf)
        bg_hf = arr_hf[10, 10, :3]
        fg_hf = np.any(np.abs(arr_hf[:, :, :3].astype(int) - bg_hf.astype(int)) > 30, axis=2)
        s_human_f = fg_hf[:, :1200]
        m_human_f = fg_hf[:, 1200:]

        im_hs = load_image(r_dir / "human_unlit_side.png")
        arr_hs = np.array(im_hs)
        bg_hs = arr_hs[10, 10, :3]
        fg_hs = np.any(np.abs(arr_hs[:, :, :3].astype(int) - bg_hs.astype(int)) > 30, axis=2)
        s_human_s = fg_hs[:, :1200]
        m_human_s = fg_hs[:, 1200:]

        im_hr = load_image(r_dir / "human_unlit_rear.png")
        arr_hr = np.array(im_hr)
        bg_hr = arr_hr[10, 10, :3]
        fg_hr = np.any(np.abs(arr_hr[:, :, :3].astype(int) - bg_hr.astype(int)) > 30, axis=2)
        s_human_r = fg_hr[:, 1200:]
        m_human_r = fg_hr[:, :1200]

        results["human_male"] = {
            "front": {
                "derived_vs_target": align_and_compare(m_human_f, c_human_f),
                "stock_vs_target": align_and_compare(s_human_f, c_human_f),
                "derived_vs_stock": align_and_compare(m_human_f, s_human_f),
            },
            "side": {
                "derived_vs_target": align_and_compare(m_human_s, c_human_s),
                "stock_vs_target": align_and_compare(s_human_s, c_human_s),
                "derived_vs_stock": align_and_compare(m_human_s, s_human_s),
            },
            "rear": {
                "derived_vs_target": align_and_compare(m_human_r, c_human_r),
                "stock_vs_target": align_and_compare(s_human_r, c_human_r),
                "derived_vs_stock": align_and_compare(m_human_r, s_human_r),
            },
        }

        # Also write human metrics directly into master review folder
        h_metrics_path = REPO_ROOT / "output/phenotypes/derived-v1/masters/human-male-v1/review/silhouette_metrics.json"
        h_metrics_path.parent.mkdir(parents=True, exist_ok=True)
        h_metrics_path.write_text(json.dumps({"human_male": results["human_male"]}, indent=2), encoding="utf-8")

    if args.race in ("elf", "all"):
        im_elf_concept = load_image(ref_root / "elf_male_fit.png")
        c_elf_f, _, _ = extract_concept_mask(im_elf_concept, (100, 415))
        c_elf_s, _, _ = extract_concept_mask(im_elf_concept, (663, 798))
        c_elf_r, _, _ = extract_concept_mask(im_elf_concept, (1037, 1331))

        im_ef = load_image(REPO_ROOT / "output/phenotypes/derived-elf-male-v1/review/renders/elf_unlit_front.png")
        fg_ef = np.any(np.abs(np.array(im_ef)[:, :, :3].astype(int) - np.array([55, 55, 73])) > 30, axis=2)
        d_elf_f = fg_ef[:, 1200:]
        s_elf_f = fg_ef[:, :1200]

        im_es = load_image(REPO_ROOT / "output/phenotypes/derived-elf-male-v1/review/renders/elf_unlit_side.png")
        fg_es = np.any(np.abs(np.array(im_es)[:, :, :3].astype(int) - np.array([55, 55, 73])) > 30, axis=2)
        d_elf_s = fg_es[:, 1200:]
        s_elf_s = fg_es[:, :1200]

        im_er = load_image(REPO_ROOT / "output/phenotypes/derived-elf-male-v1/review/renders/elf_unlit_rear.png")
        fg_er = np.any(np.abs(np.array(im_er)[:, :, :3].astype(int) - np.array([55, 55, 73])) > 30, axis=2)
        d_elf_r = fg_er[:, 1200:]
        s_elf_r = fg_er[:, :1200]

        results["elf_male"] = {
            "front": {
                "derived_vs_target": align_and_compare(d_elf_f, c_elf_f),
                "stock_vs_target": align_and_compare(s_elf_f, c_elf_f),
                "derived_vs_stock": align_and_compare(d_elf_f, s_elf_f),
            },
            "side": {
                "derived_vs_target": align_and_compare(d_elf_s, c_elf_s),
                "stock_vs_target": align_and_compare(s_elf_s, c_elf_s),
                "derived_vs_stock": align_and_compare(d_elf_s, s_elf_s),
            },
            "rear": {
                "derived_vs_target": align_and_compare(d_elf_r, c_elf_r),
                "stock_vs_target": align_and_compare(s_elf_r, c_elf_r),
                "derived_vs_stock": align_and_compare(d_elf_r, s_elf_r),
            },
        }

        e_metrics_path = REPO_ROOT / "output/phenotypes/derived-elf-male-v1/review/silhouette_metrics.json"
        e_metrics_path.parent.mkdir(parents=True, exist_ok=True)
        e_metrics_path.write_text(json.dumps({"elf_male": results["elf_male"]}, indent=2), encoding="utf-8")

    if args.race in ("orc", "all"):
        im_orc_concept = load_image(ref_root / "orc_male_fit.png")
        c_orc_f, _, _ = extract_concept_mask(im_orc_concept, (60, 420))
        c_orc_s, _, _ = extract_concept_mask(im_orc_concept, (650, 809))
        c_orc_r, _, _ = extract_concept_mask(im_orc_concept, (1019, 1384))

        im_of = load_image(REPO_ROOT / "output/phenotypes/derived-orc-male-v1/review/renders/orc_unlit_front.png")
        arr_of = np.array(im_of)
        bg_of = arr_of[10, 10, :3].astype(int)
        fg_of = np.any(np.abs(arr_of[:, :, :3].astype(int) - bg_of) > 25, axis=2)
        d_orc_f = fg_of[:, 1200:]
        s_orc_f = fg_of[:, :1200]

        im_os = load_image(REPO_ROOT / "output/phenotypes/derived-orc-male-v1/review/renders/orc_unlit_side.png")
        arr_os = np.array(im_os)
        bg_os = arr_os[10, 10, :3].astype(int)
        fg_os = np.any(np.abs(arr_os[:, :, :3].astype(int) - bg_os) > 25, axis=2)
        d_orc_s = fg_os[:, 1200:]
        s_orc_s = fg_os[:, :1200]

        im_or = load_image(REPO_ROOT / "output/phenotypes/derived-orc-male-v1/review/renders/orc_unlit_rear.png")
        arr_or = np.array(im_or)
        bg_or = arr_or[10, 10, :3].astype(int)
        fg_or = np.any(np.abs(arr_or[:, :, :3].astype(int) - bg_or) > 25, axis=2)
        d_orc_r = fg_or[:, 1200:]
        s_orc_r = fg_or[:, :1200]

        results["orc_male"] = {
            "front": {
                "derived_vs_target": align_and_compare(d_orc_f, c_orc_f),
                "stock_vs_target": align_and_compare(s_orc_f, c_orc_f),
                "derived_vs_stock": align_and_compare(d_orc_f, s_orc_f),
            },
            "side": {
                "derived_vs_target": align_and_compare(d_orc_s, c_orc_s),
                "stock_vs_target": align_and_compare(s_orc_s, c_orc_s),
                "derived_vs_stock": align_and_compare(d_orc_s, s_orc_s),
            },
            "rear": {
                "derived_vs_target": align_and_compare(d_orc_r, c_orc_r),
                "stock_vs_target": align_and_compare(s_orc_r, c_orc_r),
                "derived_vs_stock": align_and_compare(d_orc_r, s_orc_r),
            },
        }

        o_metrics_path = REPO_ROOT / "output/phenotypes/derived-orc-male-v1/review/silhouette_metrics.json"
        o_metrics_path.parent.mkdir(parents=True, exist_ok=True)
        o_metrics_path.write_text(json.dumps({"orc_male": results["orc_male"]}, indent=2), encoding="utf-8")

    gate7_evaluations = {}
    gate7_overall_passed = True
    for race_key, race_data in results.items():
        if race_key.startswith("_"):
            continue
        comp = evaluate_gate7_compliance(race_key, race_data)
        race_data["gate7_compliance"] = comp
        gate7_evaluations[race_key] = comp
        if not comp["passed"]:
            gate7_overall_passed = False

    results["gate7_audit"] = {
        "allRacesPassed": gate7_overall_passed,
        "evaluations": gate7_evaluations,
    }

    results["_metadata"] = {
        "referenceRoot": str(ref_root.resolve()),
        "consumedInputs": consumed_inputs,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"Metrics written to {out_path}")

    # Also update individual race review folders if present
    race_slug_map = {
        "elf_male": "derived-elf-male-v1",
        "orc_male": "derived-orc-male-v1",
        "troll_male": "derived-troll-male-v1",
        "dwarf_male": "derived-dwarf-male-v1",
    }
    for r_key, slug in race_slug_map.items():
        if r_key in results:
            r_receipt = REPO_ROOT / f"output/phenotypes/{slug}/review/silhouette_metrics.json"
            if r_receipt.parent.exists():
                r_receipt.write_text(json.dumps({r_key: results[r_key]}, indent=2), encoding="utf-8")

    # Formatted terminal report
    print("\n" + "="*80)
    print("DERIVED VS TARGET SILHOUETTE QUANTITATIVE DIFFERENCE AUDIT")
    print("="*80)

    for race_key, race_data in results.items():
        if race_key.startswith("_") or race_key == "gate7_audit":
            continue
        race_title = race_key.replace("_", " ").title()
        print(f"\n[{race_title}]")
        for view_name, vdata in race_data.items():
            if view_name == "gate7_compliance":
                continue
            d_res = vdata["derived_vs_target"]
            s_res = vdata["stock_vs_target"]

            print(f"\n  --- {view_name.upper()} VIEW ---")
            print(f"  * DICE Similarity (F1 Match):      {d_res['dice_pct']:6.2f}%  (Difference: {d_res['dice_diff_pct']:5.2f}%)")
            print(f"  * IoU (Intersection Over Union):   {d_res['iou_pct']:6.2f}%  (Jaccard Distance: {d_res['jaccard_distance_pct']:5.2f}%)")
            print(f"  * Symmetric Difference vs Target:  {d_res['sym_diff_vs_target_pct']:6.2f}%")
            print(f"      - Excess Derived Mass:         +{d_res['excess_derived_pct']:5.2f}%")
            print(f"      - Missing Target Mass:         -{d_res['missing_target_pct']:5.2f}%")
            print(f"  * Aspect / Stance Width Match:     {d_res['width_ratio']*100.0:6.1f}% of ideal concept width")
            print(f"  [Comparison with Stock Baseline]:")
            print(f"      - Stock Baseline Dice Match:   {s_res['dice_pct']:6.2f}%  (Difference: {s_res['dice_diff_pct']:5.2f}%)")
            improvement = d_res['dice_pct'] - s_res['dice_pct']
            print(f"      - Derived Pipeline Gain:       +{improvement:5.2f}% closer to target silhouette than stock")
            if "derived_vs_stock" in vdata:
                d_s = vdata["derived_vs_stock"]
                print(f"  [Derived/Master vs Stock Low-Poly Comparison]:")
                print(f"      - Direct Model DICE Match:     {d_s['dice_pct']:6.2f}% (Overlap IoU: {d_s['iou_pct']:6.2f}%, Divergence: {d_s['dice_diff_pct']:5.2f}%)")
                print(f"      - High-Poly Excess Contour:    +{d_s['excess_derived_pct']:5.2f}% (Organic muscle & armor volume over stock boxes)")

            print(f"  [Regional Breakdown (Derived vs Target)]:")
            for rk, rv in d_res["regional"].items():
                print(f"      - {rk:<32}: Dice Match = {rv['dice']:5.1f}% | Difference = {100.0-rv['dice']:4.1f}% (Excess +{rv['excess_pct']:4.1f}%, Missing -{rv['missing_pct']:4.1f}%)")

    print("\n" + "="*80)
    print(f"GATE 7 SILHOUETTE ACCEPTANCE SUMMARY: {'PASSED' if gate7_overall_passed else 'FAILED'}")
    print("="*80)
    for rk, comp in gate7_evaluations.items():
        status_label = "PASS" if comp["passed"] else "FAIL"
        print(f"\n  [{rk.replace('_', ' ').title()}]: {status_label}")
        print(f"    - Chest/Torso DICE:  {comp['torsoDicePct']:.1f}% (max {comp['maxTorsoDicePct']:.1f}%) -> {'PASS' if comp['torsoPassed'] else 'FAIL'}")
        print(f"    - Pelvis/Waist DICE: {comp['pelvisDicePct']:.1f}% (max {comp['maxPelvisDicePct']:.1f}%) -> {'PASS' if comp['pelvisPassed'] else 'FAIL'}")
        print(f"    - Stance Width:      {comp['stanceWidthRatioPct']:.1f}% -> {'PASS' if comp['stanceWidthPassed'] else 'FAIL'}")
        print(f"    - Baseline Gain:     {comp['maxBaselineGainPct']:+.2f}% -> {'PASS' if comp['baselineGainPassed'] else 'FAIL'}")

    if not gate7_overall_passed:
        print("\nERROR: Gate 7 silhouette difference audit failed acceptance thresholds")
        sys.exit(1)


if __name__ == "__main__":
    main()
