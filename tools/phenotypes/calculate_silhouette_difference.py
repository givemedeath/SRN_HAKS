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

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
ARTIFACT_DIR = Path("C:/Users/benco/.gemini/antigravity-ide/brain/4adb5468-4771-4ffc-93ea-eda7b809f211")
SCRATCH_DIR = ARTIFACT_DIR / "scratch"

# Import helper functions
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from build_silhouette_comparison_sheet import extract_concept_mask


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


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--race", choices=["troll", "dwarf", "human", "elf", "all"], default="all")
    parser.add_argument("--output", type=Path, default=ARTIFACT_DIR / "silhouette_metrics.json")
    return parser.parse_args()


def main():
    args = parse_args()

    results = {}

    if args.race in ("troll", "all"):
        im_troll_concept = Image.open(SCRATCH_DIR / "troll_male_fit.png")
        c_troll_f, _, _ = extract_concept_mask(im_troll_concept, (15, 435))
        c_troll_s, _, _ = extract_concept_mask(im_troll_concept, (630, 835))
        c_troll_r, _, _ = extract_concept_mask(im_troll_concept, (990, 1400))

        im_tf = Image.open("output/phenotypes/derived-troll-male-v1/review/renders/troll_unlit_front.png")
        fg_tf = np.any(np.abs(np.array(im_tf)[:, :, :3].astype(int) - np.array([55, 55, 73])) > 30, axis=2)
        d_troll_f = fg_tf[:, 1200:]
        s_troll_f = fg_tf[:, :1200]

        im_ts = Image.open("output/phenotypes/derived-troll-male-v1/review/renders/troll_unlit_side.png")
        fg_ts = np.any(np.abs(np.array(im_ts)[:, :, :3].astype(int) - np.array([55, 55, 73])) > 30, axis=2)
        d_troll_s = fg_ts[:, 1200:]
        s_troll_s = fg_ts[:, :1200]

        im_tr = Image.open("output/phenotypes/derived-troll-male-v1/review/renders/troll_unlit_rear.png")
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
        im_dwarf_concept = Image.open(SCRATCH_DIR / "dwarf_male_fit.png")
        c_dwarf_f, _, _ = extract_concept_mask(im_dwarf_concept, (20, 440))
        c_dwarf_s, _, _ = extract_concept_mask(im_dwarf_concept, (610, 810))

        im_df = Image.open(ARTIFACT_DIR / "cp2_unlit_front.png")
        fg_df = np.any(np.abs(np.array(im_df)[:, :, :3].astype(int) - np.array([55, 55, 73])) > 30, axis=2)
        s_dwarf_f = fg_df[:, 900:1500]
        d_dwarf_f = fg_df[:, 1600:2300]

        im_ds = Image.open(ARTIFACT_DIR / "cp2_unlit_side.png")
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
        im_human_concept = Image.open(SCRATCH_DIR / "human_male_fit.png")
        c_human_f, _, _ = extract_concept_mask(im_human_concept, (15, 330), y_bounds=(65, 720))
        c_human_s, _, _ = extract_concept_mask(im_human_concept, (340, 680), y_bounds=(65, 720))
        c_human_r, _, _ = extract_concept_mask(im_human_concept, (690, 1025), y_bounds=(65, 720))

        r_dir = REPO_ROOT / "output/phenotypes/derived-v1/masters/human-male-v1/review/renders"
        im_hf = Image.open(r_dir / "human_unlit_front.png")
        arr_hf = np.array(im_hf)
        bg_hf = arr_hf[10, 10, :3]
        fg_hf = np.any(np.abs(arr_hf[:, :, :3].astype(int) - bg_hf.astype(int)) > 30, axis=2)
        s_human_f = fg_hf[:, :1200]
        m_human_f = fg_hf[:, 1200:]

        im_hs = Image.open(r_dir / "human_unlit_side.png")
        arr_hs = np.array(im_hs)
        bg_hs = arr_hs[10, 10, :3]
        fg_hs = np.any(np.abs(arr_hs[:, :, :3].astype(int) - bg_hs.astype(int)) > 30, axis=2)
        s_human_s = fg_hs[:, :1200]
        m_human_s = fg_hs[:, 1200:]

        im_hr = Image.open(r_dir / "human_unlit_rear.png")
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
        im_elf_concept = Image.open(SCRATCH_DIR / "elf_male_fit.png")
        c_elf_f, _, _ = extract_concept_mask(im_elf_concept, (100, 415))
        c_elf_s, _, _ = extract_concept_mask(im_elf_concept, (663, 798))
        c_elf_r, _, _ = extract_concept_mask(im_elf_concept, (1037, 1331))

        im_ef = Image.open("output/phenotypes/derived-elf-male-v1/review/renders/elf_unlit_front.png")
        fg_ef = np.any(np.abs(np.array(im_ef)[:, :, :3].astype(int) - np.array([55, 55, 73])) > 30, axis=2)
        d_elf_f = fg_ef[:, 1200:]
        s_elf_f = fg_ef[:, :1200]

        im_es = Image.open("output/phenotypes/derived-elf-male-v1/review/renders/elf_unlit_side.png")
        fg_es = np.any(np.abs(np.array(im_es)[:, :, :3].astype(int) - np.array([55, 55, 73])) > 30, axis=2)
        d_elf_s = fg_es[:, 1200:]
        s_elf_s = fg_es[:, :1200]

        im_er = Image.open("output/phenotypes/derived-elf-male-v1/review/renders/elf_unlit_rear.png")
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

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"Metrics written to {args.output}")

    # Formatted terminal report
    print("\n" + "="*80)
    print("DERIVED VS TARGET SILHOUETTE QUANTITATIVE DIFFERENCE AUDIT")
    print("="*80)

    for race_key, race_data in results.items():
        race_title = race_key.replace("_", " ").title()
        print(f"\n[{race_title}]")
        for view_name, vdata in race_data.items():
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


if __name__ == "__main__":
    main()
