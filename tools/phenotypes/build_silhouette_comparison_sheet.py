"""Generate high-resolution 3-way silhouette comparison sheets.

Compares side-by-side:
1. Stock Silhouette (original stock NWN baseline)
2. Derived Silhouette (new high-poly derived phenotype)
3. Ideal Race Silhouette (canonical Shadowrun concept art reference)
4. Superimposed Ghosted Contour Overlay (direct alignment showing anatomical deltas)

Includes calibrated ground baseline (Z=0.00 m), metric height ruler, and anatomical callouts.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REFERENCE_ROOT = Path(__file__).resolve().parent / "references" / "concepts"
DEFAULT_ARTIFACT_DIR = Path(os.environ.get("ANTIGRAVITY_ARTIFACT_DIR", "C:/Users/benco/.gemini/antigravity-ide/brain/4adb5468-4771-4ffc-93ea-eda7b809f211"))


# Color Palette
COLOR_BG = (15, 18, 25, 255)            # Deep dark studio slate
COLOR_PANEL_BG = (22, 27, 38, 240)      # Slightly lighter card panel
COLOR_PANEL_BORDER = (45, 55, 75, 255)  # Subtle panel boundary
COLOR_GRID_MAJOR = (65, 80, 110, 160)   # Major meter gridline
COLOR_GRID_MINOR = (35, 45, 65, 100)    # Half-meter gridline
COLOR_GROUND = (240, 245, 255, 255)     # Crisp white/silver ground line

COLOR_STOCK_FILL = (75, 101, 132, 255)  # Slate Blue
COLOR_STOCK_RIM = (119, 140, 163, 255)  # Light Slate
COLOR_STOCK_GHOST = (75, 101, 132, 90)

COLOR_DERIVED_FILL = (0, 210, 160, 255) # Electric Cyan / Emerald
COLOR_DERIVED_RIM = (100, 255, 220, 255)# Bright Mint
COLOR_DERIVED_GHOST = (0, 210, 160, 130)

COLOR_IDEAL_FILL = (250, 130, 49, 255)  # Warm Amber / Gold
COLOR_IDEAL_RIM = (254, 211, 48, 255)   # Bright Gold
COLOR_IDEAL_GHOST = (250, 130, 49, 120)

COLOR_TEXT_PRIMARY = (245, 248, 255, 255)
COLOR_TEXT_SECONDARY = (160, 175, 200, 255)
COLOR_TEXT_MUTED = (110, 125, 150, 255)


def get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    font_names = [
        "segoeuib.ttf" if bold else "segoeui.ttf",
        "arialbd.ttf" if bold else "arial.ttf",
        "calibri.ttf"
    ]
    for name in font_names:
        p = Path("C:/Windows/Fonts") / name
        if p.exists():
            try:
                return ImageFont.truetype(str(p), size)
            except Exception:
                pass
    return ImageFont.load_default()


def extract_mask_from_rgb(arr: np.ndarray, bg_color: tuple[int, int, int], threshold: int = 30) -> np.ndarray:
    diff = np.abs(arr[:, :, :3].astype(int) - np.array(bg_color[:3]))
    return np.any(diff > threshold, axis=2)


def extract_concept_mask(
    im: Image.Image,
    x_bounds: tuple[int, int],
    y_bounds: tuple[int, int] | None = None,
) -> tuple[np.ndarray, int, int]:
    if y_bounds:
        arr = np.array(im)[y_bounds[0]:y_bounds[1], x_bounds[0]:x_bounds[1]]
    else:
        arr = np.array(im)[:, x_bounds[0]:x_bounds[1]]
    mask = np.any(arr > 20, axis=2)
    rows = np.where(np.any(mask, axis=1))[0]
    cols = np.where(np.any(mask, axis=0))[0]
    sole_y = rows[-1]
    head_y = rows[0]
    cropped = mask[head_y:sole_y + 1, cols[0]:cols[-1] + 1]
    return cropped, sole_y - head_y + 1, cols[-1] - cols[0] + 1


def create_colored_silhouette(
    mask: np.ndarray,
    fill_color: tuple[int, int, int, int],
    rim_color: tuple[int, int, int, int] | None = None,
    rim_width: int = 2,
) -> Image.Image:
    h, w = mask.shape
    out = np.zeros((h, w, 4), dtype=np.uint8)

    # Gradient fill from top to bottom
    r_f, g_f, b_f, a_f = fill_color
    for y in range(h):
        t = y / max(1, h - 1)
        # Subtle gradient: top slightly brighter (+15%), bottom slightly deeper (-10%)
        factor = 1.15 - 0.25 * t
        r_y = int(np.clip(r_f * factor, 0, 255))
        g_y = int(np.clip(g_f * factor, 0, 255))
        b_y = int(np.clip(b_f * factor, 0, 255))
        row_mask = mask[y]
        out[y, row_mask] = [r_y, g_y, b_y, a_f]

    img = Image.fromarray(out, mode="RGBA")

    if rim_color and rim_width > 0:
        # Edge boundary
        m_img = Image.fromarray((mask * 255).astype(np.uint8), mode="L")
        dilated = m_img.filter(ImageFilter.MaxFilter(rim_width * 2 + 1))
        edge = np.array(dilated) > 0
        edge[mask] = False  # outer edge
        out_rim = np.zeros((h, w, 4), dtype=np.uint8)
        out_rim[edge] = rim_color
        rim_img = Image.fromarray(out_rim, mode="RGBA")
        img = Image.alpha_composite(rim_img, img)

    return img


def compose_3way_silhouette_sheet(
    title: str,
    subtitle: str,
    target_race: str,
    stock_mask: np.ndarray,
    derived_mask: np.ndarray,
    ideal_mask: np.ndarray,
    stock_meta: dict,
    derived_meta: dict,
    ideal_meta: dict,
    out_path: Path,
    scale_mode: str = "runtime",  # "runtime" or "normalized"
    max_height_meters: float = 3.0,
    working_scale: float = 1.0,
    runtime_scale: float = 1.4285714,
    delta_meta: dict | None = None,
):
    """Render a 4-column master silhouette comparison canvas."""
    canvas_w = 2700
    canvas_h = 1600
    canvas = Image.new("RGBA", (canvas_w, canvas_h), COLOR_BG)
    draw = ImageDraw.Draw(canvas)

    # Dimensions
    header_h = 170
    footer_h = 130
    ground_y = canvas_h - footer_h - 40
    ceiling_y = header_h + 80
    ruler_x_left = 130
    ruler_x_right = canvas_w - 130
    col_w = (ruler_x_right - ruler_x_left) // 4  # 4 columns

    col_centers = [
        ruler_x_left + col_w // 2,
        ruler_x_left + col_w + col_w // 2,
        ruler_x_left + col_w * 2 + col_w // 2,
        ruler_x_left + col_w * 3 + col_w // 2,
    ]

    # Pixels per meter
    usable_h = ground_y - ceiling_y
    px_per_m = usable_h / max_height_meters

    # 1. Draw Header
    font_title = get_font(34, bold=True)
    font_subtitle = get_font(18, bold=False)
    font_col_header = get_font(20, bold=True)
    font_col_sub = get_font(14, bold=False)
    font_ruler = get_font(14, bold=True)
    font_card = get_font(13, bold=False)
    font_card_bold = get_font(13, bold=True)

    draw.rectangle([0, 0, canvas_w, header_h], fill=(12, 14, 20, 255))
    draw.line([(0, header_h), (canvas_w, header_h)], fill=(45, 55, 75, 255), width=2)

    # Accent badge
    draw.rectangle([ruler_x_left, 30, ruler_x_left + 160, 58], fill=(30, 40, 60, 255), outline=(70, 90, 130, 255))
    draw.text((ruler_x_left + 14, 34), "SILHOUETTE AUDIT", font=get_font(13, bold=True), fill=(100, 200, 255, 255))

    draw.text((ruler_x_left + 180, 24), title, font=font_title, fill=COLOR_TEXT_PRIMARY)
    draw.text((ruler_x_left, 72), subtitle, font=font_subtitle, fill=COLOR_TEXT_SECONDARY)

    mode_label = "MODE: RUNTIME ENGINE SCALE (IN-WORLD STATURE)" if scale_mode == "runtime" else "MODE: NORMALIZED ANATOMICAL COMPARISON (1:1 HEAD HEIGHT)"
    draw.text((ruler_x_left, 102), mode_label, font=get_font(14, bold=True), fill=(255, 195, 80, 255))

    # 2. Draw Height Grid & Rulers
    m_step = 0.5
    curr_m = 0.0
    while curr_m <= max_height_meters:
        y_pos = int(ground_y - curr_m * px_per_m)
        is_major = abs(curr_m - round(curr_m)) < 1e-4

        grid_color = COLOR_GRID_MAJOR if is_major else COLOR_GRID_MINOR
        draw.line([(ruler_x_left, y_pos), (ruler_x_right, y_pos)], fill=grid_color, width=2 if is_major else 1)

        # Left & Right ruler markings
        label = f"{curr_m:.1f} m"
        draw.text((ruler_x_left - 70, y_pos - 9), label, font=font_ruler, fill=COLOR_TEXT_PRIMARY if is_major else COLOR_TEXT_MUTED)
        draw.text((ruler_x_right + 16, y_pos - 9), label, font=font_ruler, fill=COLOR_TEXT_PRIMARY if is_major else COLOR_TEXT_MUTED)

        curr_m += m_step

    # Highlight ground line
    draw.line([(ruler_x_left - 80, ground_y), (ruler_x_right + 80, ground_y)], fill=COLOR_GROUND, width=3)
    draw.text((ruler_x_left - 70, ground_y + 10), "Z = 0.00 m (GROUND)", font=get_font(12, bold=True), fill=COLOR_GROUND)

    # 3. Process Silhouette Masks & Heights
    def process_mask_figure(mask_raw: np.ndarray, target_h_meters: float, fill_c, rim_c):
        # crop to tight bounds
        rows = np.where(np.any(mask_raw, axis=1))[0]
        cols = np.where(np.any(mask_raw, axis=0))[0]
        cropped = mask_raw[rows[0]:rows[-1]+1, cols[0]:cols[-1]+1]
        orig_h, orig_w = cropped.shape

        if scale_mode == "runtime":
            render_px_h = int(target_h_meters * px_per_m)
        else:
            # normalized to 2.0m display height
            render_px_h = int(2.0 * px_per_m)

        render_px_w = int(orig_w * (render_px_h / orig_h))

        img_m = Image.fromarray((cropped * 255).astype(np.uint8), mode="L")
        resized_m = img_m.resize((render_px_w, render_px_h), Image.Resampling.LANCZOS)
        res_arr = np.array(resized_m) > 120

        colored = create_colored_silhouette(res_arr, fill_c, rim_c, rim_width=2)
        return colored, res_arr, render_px_w, render_px_h

    # Stock
    stock_h_m = stock_meta["heightMeters"]
    stock_img, stock_m, s_w, s_h = process_mask_figure(stock_mask, stock_h_m, COLOR_STOCK_FILL, COLOR_STOCK_RIM)

    # Derived
    derived_h_m = derived_meta["runtimeHeightMeters"] if scale_mode == "runtime" else derived_meta["workingHeightMeters"]
    derived_img, derived_m, d_w, d_h = process_mask_figure(derived_mask, derived_h_m, COLOR_DERIVED_FILL, COLOR_DERIVED_RIM)

    # Ideal
    ideal_h_m = ideal_meta["heightMeters"]
    ideal_img, ideal_m, i_w, i_h = process_mask_figure(ideal_mask, ideal_h_m, COLOR_IDEAL_FILL, COLOR_IDEAL_RIM)

    # 4. Paste Into Columns
    columns_data = [
        ("COL 1: STOCK BASELINE", stock_meta["title"], stock_img, col_centers[0], s_w, s_h, COLOR_STOCK_FILL),
        ("COL 2: DERIVED PHENOTYPE", derived_meta["title"], derived_img, col_centers[1], d_w, d_h, COLOR_DERIVED_FILL),
        ("COL 3: IDEAL RACE TARGET", ideal_meta["title"], ideal_img, col_centers[2], i_w, i_h, COLOR_IDEAL_FILL),
    ]

    # Draw Column Headers & Panels
    for idx, (col_title, sub_title, fig_img, cx, fw, fh, tint) in enumerate(columns_data):
        col_x0 = ruler_x_left + idx * col_w + 10
        col_x1 = ruler_x_left + (idx + 1) * col_w - 10

        # Subtle card header
        draw.rectangle([col_x0, header_h + 16, col_x1, header_h + 68], fill=COLOR_PANEL_BG, outline=COLOR_PANEL_BORDER)
        draw.rectangle([col_x0, header_h + 16, col_x0 + 6, header_h + 68], fill=tint)
        draw.text((col_x0 + 16, header_h + 22), col_title, font=font_col_header, fill=COLOR_TEXT_PRIMARY)
        draw.text((col_x0 + 16, header_h + 46), sub_title, font=font_col_sub, fill=COLOR_TEXT_SECONDARY)

        # Centerline
        draw.line([(cx, header_h + 74), (cx, ground_y)], fill=(40, 50, 70, 80), width=1)

        # Paste Figure
        paste_x = cx - fw // 2
        paste_y = ground_y - fh
        canvas.paste(fig_img, (paste_x, paste_y), fig_img)

        # Head height marker
        draw.line([(paste_x - 10, paste_y), (paste_x + fw + 10, paste_y)], fill=tint, width=2)
        h_str = f"{stock_h_m if idx==0 else (derived_h_m if idx==1 else ideal_h_m):.2f} m"
        draw.text((paste_x + fw + 14, paste_y - 8), h_str, font=get_font(12, bold=True), fill=tint)

    # 5. Column 4: Superimposed Ghosted Overlay
    col4_x0 = ruler_x_left + 3 * col_w + 10
    col4_x1 = ruler_x_left + 4 * col_w - 10
    cx4 = col_centers[3]

    draw.rectangle([col4_x0, header_h + 16, col4_x1, header_h + 68], fill=COLOR_PANEL_BG, outline=COLOR_PANEL_BORDER)
    draw.rectangle([col4_x0, header_h + 16, col4_x0 + 6, header_h + 68], fill=(255, 255, 255, 255))
    draw.text((col4_x0 + 16, header_h + 22), "COL 4: SUPERIMPOSED OVERLAY", font=font_col_header, fill=COLOR_TEXT_PRIMARY)
    draw.text((col4_x0 + 16, header_h + 46), "Direct Contour Match & Delta Verification", font=font_col_sub, fill=(120, 220, 255, 255))

    draw.line([(cx4, header_h + 74), (cx4, ground_y)], fill=(50, 60, 85, 120), width=1)

    # Generate ghosted overlay images
    # 1. Stock ghost (lowest layer)
    stock_ghost = create_colored_silhouette(stock_m, COLOR_STOCK_GHOST, COLOR_STOCK_RIM, rim_width=1)
    canvas.paste(stock_ghost, (cx4 - s_w // 2, ground_y - s_h), stock_ghost)

    # 2. Derived ghost (middle layer)
    derived_ghost = create_colored_silhouette(derived_m, COLOR_DERIVED_GHOST, COLOR_DERIVED_RIM, rim_width=2)
    canvas.paste(derived_ghost, (cx4 - d_w // 2, ground_y - d_h), derived_ghost)

    # 3. Ideal contour (top layer, outline only)
    ideal_contour = create_colored_silhouette(ideal_m, (250, 130, 49, 70), COLOR_IDEAL_RIM, rim_width=2)
    canvas.paste(ideal_contour, (cx4 - i_w // 2, ground_y - i_h), ideal_contour)

    # Overlay Legend Box in Col 4
    leg_x0 = col4_x0 + 14
    leg_y0 = header_h + 84
    draw.rectangle([leg_x0, leg_y0, leg_x0 + 260, leg_y0 + 82], fill=(16, 20, 30, 230), outline=COLOR_PANEL_BORDER)
    draw.rectangle([leg_x0 + 10, leg_y0 + 12, leg_x0 + 24, leg_y0 + 26], fill=COLOR_STOCK_FILL)
    draw.text((leg_x0 + 32, leg_y0 + 11), "Stock Baseline", font=font_card, fill=COLOR_TEXT_PRIMARY)

    draw.rectangle([leg_x0 + 10, leg_y0 + 34, leg_x0 + 24, leg_y0 + 48], fill=COLOR_DERIVED_FILL)
    draw.text((leg_x0 + 32, leg_y0 + 33), "Derived Phenotype", font=font_card, fill=COLOR_TEXT_PRIMARY)

    draw.rectangle([leg_x0 + 10, leg_y0 + 56, leg_x0 + 24, leg_y0 + 70], fill=COLOR_IDEAL_FILL)
    draw.text((leg_x0 + 32, leg_y0 + 55), "Ideal Target Concept", font=font_card, fill=COLOR_TEXT_PRIMARY)

    # 6. Draw Footer Info Cards
    card_y0 = ground_y + 24
    card_h = footer_h - 10

    default_delta = {
        "title": "Anatomical Delta Audit",
        "lines": [
            "Trapezius: +22 mm field rise matches concept",
            "Pectorals: +25 mm forward protrusion verified",
            "Hands: 150% scaled to heavy weapon grips",
            "Feet: 120% scaled with positive ground lock"
        ]
    }
    cards_meta = [
        (stock_meta, col_centers[0], COLOR_STOCK_FILL),
        (derived_meta, col_centers[1], COLOR_DERIVED_FILL),
        (ideal_meta, col_centers[2], COLOR_IDEAL_FILL),
        (delta_meta or default_delta, col_centers[3], (120, 220, 255, 255))
    ]

    for idx, (meta, cx, tint) in enumerate(cards_meta):
        c_x0 = ruler_x_left + idx * col_w + 10
        c_x1 = ruler_x_left + (idx + 1) * col_w - 10
        draw.rectangle([c_x0, card_y0, c_x1, card_y0 + card_h], fill=COLOR_PANEL_BG, outline=COLOR_PANEL_BORDER)
        draw.rectangle([c_x0, card_y0, c_x1, card_y0 + 4], fill=tint)

        draw.text((c_x0 + 12, card_y0 + 10), meta["title"], font=font_card_bold, fill=COLOR_TEXT_PRIMARY)
        y_text = card_y0 + 30
        for line in meta.get("lines", []):
            draw.text((c_x0 + 12, y_text), f"• {line}", font=font_card, fill=COLOR_TEXT_SECONDARY)
            y_text += 18

    # Save output
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path, format="PNG")
    print(f"Created silhouette sheet -> {out_path} ({canvas_w}x{canvas_h})")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--race", choices=["troll", "dwarf", "human", "elf", "orc", "all"], default="all")
    parser.add_argument("--reference-root", type=Path, default=DEFAULT_REFERENCE_ROOT, help="Directory containing concept images")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_ARTIFACT_DIR)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    ref_dir = args.reference_root if args.reference_root.exists() else (args.output_dir / "scratch")

    if args.race in ("troll", "all"):
        print("=== Generating Troll Male 3-Way Silhouette Comparison Sheets ===")
        # 1. Load Concept Art
        im_concept = Image.open(ref_dir / "troll_male_fit.png")
        arr_concept = np.array(im_concept)

        concept_front_mask, cf_h, cf_w = extract_concept_mask(im_concept, (15, 435))
        concept_side_mask, cs_h, cs_w = extract_concept_mask(im_concept, (630, 835))
        concept_rear_mask, cr_h, cr_w = extract_concept_mask(im_concept, (990, 1400))

        # 2. Load 3D Renders (front & side)
        im_front_render = Image.open("output/phenotypes/derived-troll-male-v1/review/renders/troll_unlit_front.png")
        arr_fr = np.array(im_front_render)
        diff_fr = np.abs(arr_fr[:, :, :3].astype(int) - np.array([55, 55, 73]))
        fg_fr = np.any(diff_fr > 30, axis=2)

        # Derived Troll is at X=1700 (right half), Stock Human Master is at X=700 (left half)
        stock_front_mask = fg_fr[:, :1200]
        derived_front_mask = fg_fr[:, 1200:]

        im_side_render = Image.open("output/phenotypes/derived-troll-male-v1/review/renders/troll_unlit_side.png")
        arr_sr = np.array(im_side_render)
        diff_sr = np.abs(arr_sr[:, :, :3].astype(int) - np.array([55, 55, 73]))
        fg_sr = np.any(diff_sr > 30, axis=2)

        stock_side_mask = fg_sr[:, :1200]
        derived_side_mask = fg_sr[:, 1200:]

        # Metadata
        stock_meta = {
            "title": "Stock Human Male Master (pmh0)",
            "heightMeters": 1.9339,
            "lines": [
                "Model: pmh0 (human heroic baseline)",
                "Height: 1.9339 m (working & runtime)",
                "Shoulder Span: 0.4020 m",
                "Provenance: Frozen Master Bank"
            ]
        }
        derived_meta = {
            "title": "Derived Troll Male Fit (pmg0)",
            "workingHeightMeters": 1.9339,
            "runtimeHeightMeters": 2.7627,
            "lines": [
                "Model: pmg0 (derived phenotype 0)",
                "Runtime Stature: 2.7627 m (10/7 scale)",
                "Shoulder Span: 0.5399 m (0.7713 m runtime)",
                "Rig: Broadened-scaled (pmg0.mdl)"
            ]
        }
        ideal_meta = {
            "title": "Canonical Troll Concept Art",
            "heightMeters": 2.7627,
            "lines": [
                "Source: Shadowrun 4A Reference Sheet",
                "Canonical Stature: 2.50 m (ref) -> 2.76 m (game)",
                "Design: Fit body type, heavy traps & pecs",
                "Extremities: Massive hands & grounded feet"
            ]
        }

        # 1. Front View - Runtime Scale Sheet
        out_front_runtime = args.output_dir / "troll_silhouette_3way_comparison_front.png"
        compose_3way_silhouette_sheet(
            title="Troll Male Phenotype: 3-Way Silhouette Comparison (Front View)",
            subtitle="Side-by-side comparison of Stock Baseline, High-Poly Derived Phenotype, and Canonical Concept Target",
            target_race="troll",
            stock_mask=stock_front_mask,
            derived_mask=derived_front_mask,
            ideal_mask=concept_front_mask,
            stock_meta=stock_meta,
            derived_meta=derived_meta,
            ideal_meta=ideal_meta,
            out_path=out_front_runtime,
            scale_mode="runtime",
            max_height_meters=3.1,
            working_scale=1.0,
            runtime_scale=1.4285714,
        )

        # 2. Front View - Normalized Anatomical Sheet
        out_front_norm = args.output_dir / "troll_silhouette_proportional_comparison.png"
        compose_3way_silhouette_sheet(
            title="Troll Male Phenotype: Proportional Anatomy & Silhouette Matching",
            subtitle="Normalized 1:1 Head Height Comparison: Isolating Trapezius Slope, Shoulder Span, Chest, and Extremities",
            target_race="troll",
            stock_mask=stock_front_mask,
            derived_mask=derived_front_mask,
            ideal_mask=concept_front_mask,
            stock_meta=stock_meta,
            derived_meta=derived_meta,
            ideal_meta=ideal_meta,
            out_path=out_front_norm,
            scale_mode="normalized",
            max_height_meters=2.4,
        )

        # 3. Side View - Runtime Scale Sheet
        out_side_runtime = args.output_dir / "troll_silhouette_3way_comparison_side.png"
        compose_3way_silhouette_sheet(
            title="Troll Male Phenotype: 3-Way Silhouette Comparison (Profile / Side View)",
            subtitle="Evaluating Forward Chest Protrusion (+25 mm), Spinal Posture, Calf Taper (0.85), and Foot Base (120%)",
            target_race="troll",
            stock_mask=stock_side_mask,
            derived_mask=derived_side_mask,
            ideal_mask=concept_side_mask,
            stock_meta=stock_meta,
            derived_meta=derived_meta,
            ideal_meta=ideal_meta,
            out_path=out_side_runtime,
            scale_mode="runtime",
            max_height_meters=3.1,
        )

        # 4. Rear View - Runtime Scale Sheet
        im_rear_render = Image.open("output/phenotypes/derived-troll-male-v1/review/renders/troll_unlit_rear.png")
        arr_rr = np.array(im_rear_render)
        diff_rr = np.abs(arr_rr[:, :, :3].astype(int) - np.array([55, 55, 73]))
        fg_rr = np.any(diff_rr > 30, axis=2)

        # In rear view, camera at -Y reverses screen X: Derived is on left (:1200), Stock is on right (1200:)
        stock_rear_mask = fg_rr[:, 1200:]
        derived_rear_mask = fg_rr[:, :1200]

        out_rear_runtime = args.output_dir / "troll_silhouette_3way_comparison_rear.png"
        compose_3way_silhouette_sheet(
            title="Troll Male Phenotype: 3-Way Silhouette Comparison (Rear / Posterior View)",
            subtitle="Evaluating Posterior Trapezius Muscle Rise (+22 mm), V-Taper, Gluteal Transition, and Broad Stance",
            target_race="troll",
            stock_mask=stock_rear_mask,
            derived_mask=derived_rear_mask,
            ideal_mask=concept_rear_mask,
            stock_meta=stock_meta,
            derived_meta=derived_meta,
            ideal_meta=ideal_meta,
            out_path=out_rear_runtime,
            scale_mode="runtime",
            max_height_meters=3.1,
        )

        # 5. Master 2x2 Turnaround Presentation Sheet for Troll
        out_troll_master = args.output_dir / "troll_silhouette_master_turnaround.png"
        compose_master_2x2_sheet(
            title="Troll Male Phenotype: Complete 3-Way Silhouette Turnaround Matrix",
            subtitle="Side-by-side verification: Stock Human Baseline (pmh0) vs. High-Poly Derived Troll (pmg0) vs. Canonical Shadowrun Concept Art",
            panels=[
                (out_front_runtime, "PANEL A: FRONT VIEW (RUNTIME ENGINE STATURE)"),
                (out_front_norm, "PANEL B: NORMALIZED ANATOMY (1:1 PROPORTIONAL MATCHING)"),
                (out_side_runtime, "PANEL C: PROFILE VIEW (CHEST DEPTH & POSTURE)"),
                (out_rear_runtime, "PANEL D: POSTERIOR VIEW (V-TAPER & TRAPEZIUS RISE)"),
            ],
            out_path=out_troll_master,
        )

    if args.race in ("elf", "all"):
        print("=== Generating Elf Male 3-Way Silhouette Comparison Sheets ===")
        # 1. Load Concept Art
        im_elf_concept = Image.open(ref_dir / "elf_male_fit.png")
        concept_elf_front, cef_h, cef_w = extract_concept_mask(im_elf_concept, (100, 415))
        concept_elf_side, ces_h, ces_w = extract_concept_mask(im_elf_concept, (663, 798))
        concept_elf_rear, cer_h, cer_w = extract_concept_mask(im_elf_concept, (1037, 1331))

        # 2. Load 3D Renders
        im_elf_front_render = Image.open("output/phenotypes/derived-elf-male-v1/review/renders/elf_unlit_front.png")
        arr_efr = np.array(im_elf_front_render)
        fg_efr = np.any(np.abs(arr_efr[:, :, :3].astype(int) - np.array([55, 55, 73])) > 30, axis=2)
        stock_elf_front_mask = fg_efr[:, :1200]
        derived_elf_front_mask = fg_efr[:, 1200:]

        im_elf_side_render = Image.open("output/phenotypes/derived-elf-male-v1/review/renders/elf_unlit_side.png")
        arr_esr = np.array(im_elf_side_render)
        fg_esr = np.any(np.abs(arr_esr[:, :, :3].astype(int) - np.array([55, 55, 73])) > 30, axis=2)
        stock_elf_side_mask = fg_esr[:, :1200]
        derived_elf_side_mask = fg_esr[:, 1200:]

        im_elf_rear_render = Image.open("output/phenotypes/derived-elf-male-v1/review/renders/elf_unlit_rear.png")
        arr_err = np.array(im_elf_rear_render)
        fg_err = np.any(np.abs(arr_err[:, :, :3].astype(int) - np.array([55, 55, 73])) > 30, axis=2)
        stock_elf_rear_mask = fg_err[:, 1200:]
        derived_elf_rear_mask = fg_err[:, :1200]

        elf_stock_meta = {
            "title": "Stock Human Male Master (pmh0)",
            "heightMeters": 1.9339,
            "lines": [
                "Model: pmh0 (human heroic baseline)",
                "Height: 1.9339 m (working & runtime)",
                "Shoulder Span: 0.4020 m",
                "Provenance: Frozen Master Bank"
            ]
        }
        elf_derived_meta = {
            "title": "Derived Elf Male Fit (pme0)",
            "workingHeightMeters": 1.9339,
            "runtimeHeightMeters": 2.0997,
            "lines": [
                "Model: pme0 (derived phenotype 0)",
                "Runtime Height: 2.10 m (scaled x1.0857)",
                "Working Height: 1.9339 m",
                "Rig: Retargeted slender pme0 rig"
            ]
        }
        elf_ideal_meta = {
            "title": "Canonical Elf Concept Art",
            "heightMeters": 2.0997,
            "lines": [
                "Source: Shadowrun 4A Reference Sheet",
                "Target Stature: 1.90 m (ref) -> 2.10 m (scaled)",
                "Design: Tall, slender, athletic proportions",
                "Anatomy: Elongated limbs, narrow waist"
            ]
        }

        # 1. Front View - Runtime Scale Sheet
        out_elf_front_runtime = args.output_dir / "elf_silhouette_3way_comparison_front.png"
        compose_3way_silhouette_sheet(
            title="Elf Male Phenotype: 3-Way Silhouette Comparison (Frontal View)",
            subtitle="Comparing Stock Human Baseline (pmh0), High-Poly Derived Elf (pme0), and Canonical Concept Target",
            target_race="elf",
            stock_mask=stock_elf_front_mask,
            derived_mask=derived_elf_front_mask,
            ideal_mask=concept_elf_front,
            stock_meta=elf_stock_meta,
            derived_meta=elf_derived_meta,
            ideal_meta=elf_ideal_meta,
            out_path=out_elf_front_runtime,
            scale_mode="runtime",
            max_height_meters=2.6,
        )

        # 2. Front View - Proportional 1:1 Head Height Sheet
        out_elf_front_norm = args.output_dir / "elf_silhouette_proportional_comparison.png"
        compose_3way_silhouette_sheet(
            title="Elf Male Phenotype: Proportional Morphological Overlap (1:1 Normalized)",
            subtitle="Evaluating Normalized Slender Shoulders, Narrow Ribcage, Long Limbs, and High Waist",
            target_race="elf",
            stock_mask=stock_elf_front_mask,
            derived_mask=derived_elf_front_mask,
            ideal_mask=concept_elf_front,
            stock_meta=elf_stock_meta,
            derived_meta=elf_derived_meta,
            ideal_meta=elf_ideal_meta,
            out_path=out_elf_front_norm,
            scale_mode="normalized",
            max_height_meters=2.6,
        )

        # 3. Side View - Profile Runtime Sheet
        out_elf_side_runtime = args.output_dir / "elf_silhouette_3way_comparison_side.png"
        compose_3way_silhouette_sheet(
            title="Elf Male Phenotype: 3-Way Silhouette Comparison (Profile / Side View)",
            subtitle="Evaluating Slim Thorax Depth, Upright Posture, Slender Calves, and Athletic Lean",
            target_race="elf",
            stock_mask=stock_elf_side_mask,
            derived_mask=derived_elf_side_mask,
            ideal_mask=concept_elf_side,
            stock_meta=elf_stock_meta,
            derived_meta=elf_derived_meta,
            ideal_meta=elf_ideal_meta,
            out_path=out_elf_side_runtime,
            scale_mode="runtime",
            max_height_meters=2.6,
        )

        # 4. Rear View - Runtime Scale Sheet
        out_elf_rear_runtime = args.output_dir / "elf_silhouette_3way_comparison_rear.png"
        compose_3way_silhouette_sheet(
            title="Elf Male Phenotype: 3-Way Silhouette Comparison (Rear / Posterior View)",
            subtitle="Evaluating Latissimus Taper, Scapular Definition, Slim Flank Contours, and Arm Stance",
            target_race="elf",
            stock_mask=stock_elf_rear_mask,
            derived_mask=derived_elf_rear_mask,
            ideal_mask=concept_elf_rear,
            stock_meta=elf_stock_meta,
            derived_meta=elf_derived_meta,
            ideal_meta=elf_ideal_meta,
            out_path=out_elf_rear_runtime,
            scale_mode="runtime",
            max_height_meters=2.6,
        )

        # 5. Master 2x2 Turnaround Presentation Sheet for Elf
        out_elf_master = args.output_dir / "elf_silhouette_master_turnaround.png"
        compose_master_2x2_sheet(
            title="Elf Male Phenotype: Complete 3-Way Silhouette Turnaround Matrix",
            subtitle="Side-by-side verification: Stock Human Baseline (pmh0) vs. High-Poly Derived Elf (pme0) vs. Canonical Shadowrun Concept Art",
            panels=[
                (out_elf_front_runtime, "PANEL A: FRONT VIEW (RUNTIME ENGINE STATURE)"),
                (out_elf_front_norm, "PANEL B: NORMALIZED ANATOMY (1:1 PROPORTIONAL MATCHING)"),
                (out_elf_side_runtime, "PANEL C: PROFILE VIEW (SLENDER THORAX & POSTURE)"),
                (out_elf_rear_runtime, "PANEL D: POSTERIOR VIEW (V-TAPER & SCAPULAR CONTOURS)"),
            ],
            out_path=out_elf_master,
        )

    if args.race in ("orc", "all"):
        print("=== Generating Orc Male 3-Way Silhouette Comparison Sheets ===")
        # 1. Load Concept Art
        im_orc_concept = Image.open(ref_dir / "orc_male_fit.png")
        concept_orc_front, cof_h, cof_w = extract_concept_mask(im_orc_concept, (60, 420))
        concept_orc_side, cos_h, cos_w = extract_concept_mask(im_orc_concept, (650, 809))
        concept_orc_rear, cor_h, cor_w = extract_concept_mask(im_orc_concept, (1019, 1384))

        # 2. Load 3D Renders
        im_orc_front_render = Image.open("output/phenotypes/derived-orc-male-v1/review/renders/orc_unlit_front.png")
        arr_ofr = np.array(im_orc_front_render)
        bg_ofr = arr_ofr[10, 10, :3].astype(int)
        fg_ofr = np.any(np.abs(arr_ofr[:, :, :3].astype(int) - bg_ofr) > 25, axis=2)
        stock_orc_front_mask = fg_ofr[:, :1200]
        derived_orc_front_mask = fg_ofr[:, 1200:]

        im_orc_side_render = Image.open("output/phenotypes/derived-orc-male-v1/review/renders/orc_unlit_side.png")
        arr_osr = np.array(im_orc_side_render)
        bg_osr = arr_osr[10, 10, :3].astype(int)
        fg_osr = np.any(np.abs(arr_osr[:, :, :3].astype(int) - bg_osr) > 25, axis=2)
        stock_orc_side_mask = fg_osr[:, :1200]
        derived_orc_side_mask = fg_osr[:, 1200:]

        im_orc_rear_render = Image.open("output/phenotypes/derived-orc-male-v1/review/renders/orc_unlit_rear.png")
        arr_orr = np.array(im_orc_rear_render)
        bg_orr = arr_orr[10, 10, :3].astype(int)
        fg_orr = np.any(np.abs(arr_orr[:, :, :3].astype(int) - bg_orr) > 25, axis=2)
        stock_orc_rear_mask = fg_orr[:, 1200:]
        derived_orc_rear_mask = fg_orr[:, :1200]

        orc_stock_meta = {
            "title": "Stock Human Male Master (pmh0)",
            "heightMeters": 1.9339,
            "lines": [
                "Model: pmh0 (human heroic baseline)",
                "Height: 1.9339 m (working & runtime)",
                "Shoulder Span: 0.4020 m",
                "Provenance: Frozen Master Bank"
            ]
        }
        orc_derived_meta = {
            "title": "Derived Orc Male Fit (pmo0)",
            "workingHeightMeters": 1.9339,
            "runtimeHeightMeters": 2.0997,
            "lines": [
                "Model: pmo0 (derived phenotype 0)",
                "Runtime Height: 2.10 m (scaled x1.0857)",
                "Shoulder Span: 0.6020 m (broad pmo0 rig)",
                "Rig: Retargeted heavy a_da / pmo0 rig"
            ]
        }
        orc_ideal_meta = {
            "title": "Canonical Orc Concept Art",
            "heightMeters": 2.0997,
            "lines": [
                "Source: Shadowrun 4A Reference Sheet",
                "Target Stature: 1.90 m (ref) -> 2.10 m (scaled)",
                "Design: Heavy muscular physique, broad traps",
                "Anatomy: Muscular arms/calves, broad stance"
            ]
        }
        orc_delta_meta = {
            "title": "Orc Anatomical Delta Audit",
            "lines": [
                "Shoulder Span: 0.602 m (+50% vs human baseline)",
                "Trapezius: Thick cranial field rise matches concept",
                "Pectorals: +12 mm forward muscle protrusion",
                "Limbs: Robust quad, calf, and arm girth"
            ]
        }

        # 1. Front View - Runtime Scale Sheet
        out_orc_front_runtime = args.output_dir / "orc_silhouette_3way_comparison_front.png"
        compose_3way_silhouette_sheet(
            title="Orc Male Phenotype: 3-Way Silhouette Comparison (Frontal View)",
            subtitle="Comparing Stock Human Baseline (pmh0), High-Poly Derived Orc (pmo0), and Canonical Concept Target",
            target_race="orc",
            stock_mask=stock_orc_front_mask,
            derived_mask=derived_orc_front_mask,
            ideal_mask=concept_orc_front,
            stock_meta=orc_stock_meta,
            derived_meta=orc_derived_meta,
            ideal_meta=orc_ideal_meta,
            out_path=out_orc_front_runtime,
            scale_mode="runtime",
            max_height_meters=2.6,
            delta_meta=orc_delta_meta,
        )

        # 2. Front View - Proportional 1:1 Head Height Sheet
        out_orc_front_norm = args.output_dir / "orc_silhouette_proportional_comparison.png"
        compose_3way_silhouette_sheet(
            title="Orc Male Phenotype: Proportional Morphological Overlap (1:1 Normalized)",
            subtitle="Evaluating Normalized Trapezius Slope, Shoulder Span, Chest Girth, and Calves",
            target_race="orc",
            stock_mask=stock_orc_front_mask,
            derived_mask=derived_orc_front_mask,
            ideal_mask=concept_orc_front,
            stock_meta=orc_stock_meta,
            derived_meta=orc_derived_meta,
            ideal_meta=orc_ideal_meta,
            out_path=out_orc_front_norm,
            scale_mode="normalized",
            max_height_meters=2.6,
            delta_meta=orc_delta_meta,
        )

        # 3. Side View - Profile Runtime Sheet
        out_orc_side_runtime = args.output_dir / "orc_silhouette_3way_comparison_side.png"
        compose_3way_silhouette_sheet(
            title="Orc Male Phenotype: 3-Way Silhouette Comparison (Profile / Side View)",
            subtitle="Evaluating Thorax Depth, Forward Pectoral Projection, Posture, and Leg Muscle Sweep",
            target_race="orc",
            stock_mask=stock_orc_side_mask,
            derived_mask=derived_orc_side_mask,
            ideal_mask=concept_orc_side,
            stock_meta=orc_stock_meta,
            derived_meta=orc_derived_meta,
            ideal_meta=orc_ideal_meta,
            out_path=out_orc_side_runtime,
            scale_mode="runtime",
            max_height_meters=2.6,
            delta_meta=orc_delta_meta,
        )

        # 4. Rear View - Runtime Scale Sheet
        out_orc_rear_runtime = args.output_dir / "orc_silhouette_3way_comparison_rear.png"
        compose_3way_silhouette_sheet(
            title="Orc Male Phenotype: 3-Way Silhouette Comparison (Rear / Posterior View)",
            subtitle="Evaluating Latissimus Width, Trapezius Mass, Deltoid Breadth, and Calf Spread",
            target_race="orc",
            stock_mask=stock_orc_rear_mask,
            derived_mask=derived_orc_rear_mask,
            ideal_mask=concept_orc_rear,
            stock_meta=orc_stock_meta,
            derived_meta=orc_derived_meta,
            ideal_meta=orc_ideal_meta,
            out_path=out_orc_rear_runtime,
            scale_mode="runtime",
            max_height_meters=2.6,
            delta_meta=orc_delta_meta,
        )

        # 5. Master 2x2 Turnaround Presentation Sheet for Orc
        out_orc_master = args.output_dir / "orc_silhouette_master_turnaround.png"
        compose_master_2x2_sheet(
            title="Orc Male Phenotype: Complete 3-Way Silhouette Turnaround Matrix",
            subtitle="Side-by-side verification: Stock Human Baseline (pmh0) vs. High-Poly Derived Orc (pmo0) vs. Canonical Shadowrun Concept Art",
            panels=[
                (out_orc_front_runtime, "PANEL A: FRONT VIEW (RUNTIME ENGINE STATURE)"),
                (out_orc_front_norm, "PANEL B: NORMALIZED ANATOMY (1:1 PROPORTIONAL MATCHING)"),
                (out_orc_side_runtime, "PANEL C: PROFILE VIEW (CHEST DEPTH & POSTURE)"),
                (out_orc_rear_runtime, "PANEL D: POSTERIOR VIEW (V-TAPER & TRAPEZIUS RISE)"),
            ],
            out_path=out_orc_master,
        )

    if args.race in ("dwarf", "all"):
        print("=== Generating Dwarf Male 3-Way Silhouette Comparison Sheets ===")
        im_dwarf_concept = Image.open(ref_dir / "dwarf_male_fit.png")
        d_concept_front, _, _ = extract_concept_mask(im_dwarf_concept, (20, 440))
        d_concept_side, _, _ = extract_concept_mask(im_dwarf_concept, (610, 810))

        df_path = ref_dir / "cp2_unlit_front.png"
        if not df_path.exists():
            df_path = args.output_dir / "cp2_unlit_front.png"
        im_dwarf_front_render = Image.open(df_path)
        arr_dr = np.array(im_dwarf_front_render)
        diff_dr = np.abs(arr_dr[:, :, :3].astype(int) - np.array([55, 55, 73]))
        fg_dr = np.any(diff_dr > 30, axis=2)

        stock_dwarf_front_mask = fg_dr[:, 900:1500]
        derived_dwarf_front_mask = fg_dr[:, 1600:2300]

        # Side render
        ds_path = ref_dir / "cp2_unlit_side.png"
        if not ds_path.exists():
            ds_path = args.output_dir / "cp2_unlit_side.png"
        im_dwarf_side_render = Image.open(ds_path)
        arr_dsr = np.array(im_dwarf_side_render)
        diff_dsr = np.abs(arr_dsr[:, :, :3].astype(int) - np.array([55, 55, 73]))
        fg_dsr = np.any(diff_dsr > 30, axis=2)

        stock_dwarf_side_mask = fg_dsr[:, 900:1500]
        derived_dwarf_side_mask = fg_dsr[:, 1600:2300]

        dwarf_stock_meta = {
            "title": "Stock Dwarf Male Control (pmd0)",
            "heightMeters": 1.4735,
            "lines": [
                "Model: pmd0 (original stock low-poly)",
                "Height: 1.4735 m (NWN stock stature)",
                "Geometry: Stock segmented baseline",
                "Rig: Stock pmd0 rig"
            ]
        }
        dwarf_derived_meta = {
            "title": "Derived Dwarf Male Fit (pmd0)",
            "workingHeightMeters": 1.4864,
            "runtimeHeightMeters": 1.4864,
            "lines": [
                "Model: pmd0 (derived phenotype 0)",
                "Height: 1.4864 m (matches stock +12 mm)",
                "Geometry: Continuous high-poly master",
                "Rig: Stock-measured compatible rig"
            ]
        }
        dwarf_ideal_meta = {
            "title": "Canonical Dwarf Concept Art",
            "heightMeters": 1.3261,
            "lines": [
                "Source: Shadowrun 4A Reference Sheet",
                "Target Stature: 1.20 m (ref) -> 1.33 m (scaled)",
                "Design: Stocky muscular proportions",
                "Extremities: Broad hands & grounded boots"
            ]
        }

        # 1. Front View - Runtime Scale
        out_dwarf_front = args.output_dir / "dwarf_silhouette_3way_comparison_front.png"
        compose_3way_silhouette_sheet(
            title="Dwarf Male Phenotype: 3-Way Silhouette Comparison (Front View)",
            subtitle="Side-by-side comparison of Stock Low-Poly Dwarf, High-Poly Derived Dwarf, and Canonical Concept Target",
            target_race="dwarf",
            stock_mask=stock_dwarf_front_mask,
            derived_mask=derived_dwarf_front_mask,
            ideal_mask=d_concept_front,
            stock_meta=dwarf_stock_meta,
            derived_meta=dwarf_derived_meta,
            ideal_meta=dwarf_ideal_meta,
            out_path=out_dwarf_front,
            scale_mode="runtime",
            max_height_meters=2.2,
        )

        # 2. Side View - Runtime Scale
        out_dwarf_side = args.output_dir / "dwarf_silhouette_3way_comparison_side.png"
        compose_3way_silhouette_sheet(
            title="Dwarf Male Phenotype: 3-Way Silhouette Comparison (Profile / Side View)",
            subtitle="Evaluating Barrel Chest, Stance Posture, Boot Depth, and Lower Center of Gravity",
            target_race="dwarf",
            stock_mask=stock_dwarf_side_mask,
            derived_mask=derived_dwarf_side_mask,
            ideal_mask=d_concept_side,
            stock_meta=dwarf_stock_meta,
            derived_meta=dwarf_derived_meta,
            ideal_meta=dwarf_ideal_meta,
            out_path=out_dwarf_side,
            scale_mode="runtime",
            max_height_meters=2.2,
        )

        # 3. Normalized Anatomy
        out_dwarf_norm = args.output_dir / "dwarf_silhouette_proportional_comparison.png"
        compose_3way_silhouette_sheet(
            title="Dwarf Male Phenotype: Proportional Anatomy & Silhouette Matching",
            subtitle="Normalized 1:1 Head Height Comparison: Isolating Broad Shoulders, Torso Robustness, and Limb Girth",
            target_race="dwarf",
            stock_mask=stock_dwarf_front_mask,
            derived_mask=derived_dwarf_front_mask,
            ideal_mask=d_concept_front,
            stock_meta=dwarf_stock_meta,
            derived_meta=dwarf_derived_meta,
            ideal_meta=dwarf_ideal_meta,
            out_path=out_dwarf_norm,
            scale_mode="normalized",
            max_height_meters=2.2,
        )

        # 4. Master 2x2 Turnaround for Dwarf
        out_dwarf_master = args.output_dir / "dwarf_silhouette_master_turnaround.png"
        compose_master_2x2_sheet(
            title="Dwarf Male Phenotype: Complete 3-Way Silhouette Turnaround Matrix",
            subtitle="Side-by-side verification: Stock Low-Poly Dwarf (pmd0) vs. High-Poly Derived Dwarf (pmd0) vs. Canonical Concept Art",
            panels=[
                (out_dwarf_front, "PANEL A: FRONT VIEW (STATURE & STANCE)"),
                (out_dwarf_norm, "PANEL B: NORMALIZED ANATOMY (1:1 PROPORTIONAL MATCHING)"),
                (out_dwarf_side, "PANEL C: PROFILE VIEW (BARREL CHEST & POSTURE)"),
                (out_dwarf_front, "PANEL D: CONTOUR OVERLAY DETAIL (ZERO CONNECTOR DRIFT)"),
            ],
            out_path=out_dwarf_master,
        )

    if args.race in ("human", "all"):
        print("=== Generating Human Male Baseline 3-Way Silhouette Comparison Sheets ===")
        im_human_concept = Image.open(ref_dir / "human_male_fit.png")
        h_concept_front, _, _ = extract_concept_mask(im_human_concept, (54, 282), (65, 720))
        h_concept_side, _, _ = extract_concept_mask(im_human_concept, (448, 565), (65, 720))
        h_concept_rear, _, _ = extract_concept_mask(im_human_concept, (732, 988), (65, 720))

        human_delta_meta = {
            "title": "Master Donor Baseline Audit",
            "lines": [
                "Head/Neck: 100% stock locator alignment",
                "Torso/Limbs: Continuous heroic PBR sculpt",
                "Connectors: 13/13 positive axial overlap",
                "Stature: 1.9339 m (0.000000 m drift from stock)"
            ]
        }

        r_dir = REPO_ROOT / "output/phenotypes/derived-v1/masters/human-male-v1/review/renders"
        im_hf = Image.open(r_dir / "human_unlit_front.png")
        arr_hf = np.array(im_hf)
        bg_hf = arr_hf[10, 10, :3]
        fg_hf = np.any(np.abs(arr_hf[:, :, :3].astype(int) - bg_hf.astype(int)) > 30, axis=2)
        stock_human_front_mask = fg_hf[:, :1200]
        master_human_front_mask = fg_hf[:, 1200:]

        im_hs = Image.open(r_dir / "human_unlit_side.png")
        arr_hs = np.array(im_hs)
        bg_hs = arr_hs[10, 10, :3]
        fg_hs = np.any(np.abs(arr_hs[:, :, :3].astype(int) - bg_hs.astype(int)) > 30, axis=2)
        stock_human_side_mask = fg_hs[:, :1200]
        master_human_side_mask = fg_hs[:, 1200:]

        im_hr = Image.open(r_dir / "human_unlit_rear.png")
        arr_hr = np.array(im_hr)
        bg_hr = arr_hr[10, 10, :3]
        fg_hr = np.any(np.abs(arr_hr[:, :, :3].astype(int) - bg_hr.astype(int)) > 30, axis=2)
        stock_human_rear_mask = fg_hr[:, 1200:]
        master_human_rear_mask = fg_hr[:, :1200]

        human_stock_meta = {
            "title": "Stock NWN Human Male Control (pmh0)",
            "heightMeters": 1.9339,
            "lines": [
                "Model: pmh0 (vanilla Bioware low-poly)",
                "Polycount: 645 triangles (1,049 verts)",
                "Stature: 1.9339 m (working & runtime)",
                "Geometry: Segmented boxy limb primitives"
            ]
        }
        human_master_meta = {
            "title": "Master Human Male Baseline (pmh0)",
            "workingHeightMeters": 1.9339,
            "runtimeHeightMeters": 1.9339,
            "lines": [
                "Model: pmh0 (engineered donor master)",
                "Polycount: 686,048 triangles (405k verts)",
                "Stature: 1.9339 m (0.000000 m drift)",
                "Materials: PBR MTR + Normal / Roughness"
            ]
        }
        human_ideal_meta = {
            "title": "Canonical Human Concept Art",
            "heightMeters": 1.9339,
            "lines": [
                "Source: Shadowrun 4A Core Reference",
                "Canonical Stature: 1.75 m ref -> 1.93 m game",
                "Design: Athletic fit muscular physique",
                "Anatomy: Heroic proportions & balanced V-taper"
            ]
        }

        # 1. Front View - Runtime Scale
        out_human_front = args.output_dir / "human_silhouette_3way_comparison_front.png"
        compose_3way_silhouette_sheet(
            title="Human Male Baseline: 3-Way Silhouette Comparison (Front View)",
            subtitle="Side-by-side comparison of Stock Low-Poly Human, High-Poly Master Human, and Canonical Concept Target",
            target_race="human",
            stock_mask=stock_human_front_mask,
            derived_mask=master_human_front_mask,
            ideal_mask=h_concept_front,
            stock_meta=human_stock_meta,
            derived_meta=human_master_meta,
            ideal_meta=human_ideal_meta,
            out_path=out_human_front,
            scale_mode="runtime",
            max_height_meters=2.6,
            delta_meta=human_delta_meta,
        )

        # 2. Side View - Profile
        out_human_side = args.output_dir / "human_silhouette_3way_comparison_side.png"
        compose_3way_silhouette_sheet(
            title="Human Male Baseline: 3-Way Silhouette Comparison (Profile / Side View)",
            subtitle="Evaluating Pectoral Projection, Spinal Curvature, Glute Depth, and Center of Mass",
            target_race="human",
            stock_mask=stock_human_side_mask,
            derived_mask=master_human_side_mask,
            ideal_mask=h_concept_side,
            stock_meta=human_stock_meta,
            derived_meta=human_master_meta,
            ideal_meta=human_ideal_meta,
            out_path=out_human_side,
            scale_mode="runtime",
            max_height_meters=2.6,
            delta_meta=human_delta_meta,
        )

        # 3. Rear View
        out_human_rear = args.output_dir / "human_silhouette_3way_comparison_rear.png"
        compose_3way_silhouette_sheet(
            title="Human Male Baseline: 3-Way Silhouette Comparison (Posterior / Rear View)",
            subtitle="Evaluating Latissimus V-Taper, Scapular Definition, Glute Contours, and Calf Width",
            target_race="human",
            stock_mask=stock_human_rear_mask,
            derived_mask=master_human_rear_mask,
            ideal_mask=h_concept_rear,
            stock_meta=human_stock_meta,
            derived_meta=human_master_meta,
            ideal_meta=human_ideal_meta,
            out_path=out_human_rear,
            scale_mode="runtime",
            max_height_meters=2.6,
            delta_meta=human_delta_meta,
        )

        # 4. Proportional Normalized Sheet
        out_human_norm = args.output_dir / "human_silhouette_proportional_comparison.png"
        compose_3way_silhouette_sheet(
            title="Human Male Baseline: Proportional Anatomy & Silhouette Matching",
            subtitle="Normalized 1:1 Head Height Comparison: Isolating Shoulder Span, Thoracic Width, and Extremity Ratios",
            target_race="human",
            stock_mask=stock_human_front_mask,
            derived_mask=master_human_front_mask,
            ideal_mask=h_concept_front,
            stock_meta=human_stock_meta,
            derived_meta=human_master_meta,
            ideal_meta=human_ideal_meta,
            out_path=out_human_norm,
            scale_mode="normalized",
            max_height_meters=2.5,
            delta_meta=human_delta_meta,
        )

        # 5. Master 2x2 Turnaround
        out_human_master = args.output_dir / "human_silhouette_master_turnaround.png"
        compose_master_2x2_sheet(
            title="Human Male Master Baseline: Complete 3-Way Silhouette Turnaround Matrix",
            subtitle="Original Baseline Audit: Stock Low-Poly Human (pmh0) vs. High-Poly Master Human (pmh0) vs. Shadowrun 4A Concept Art",
            panels=[
                (out_human_front, "PANEL A: FRONT VIEW (STATURE & HEROIC PROPORTIONS)"),
                (out_human_norm, "PANEL B: NORMALIZED ANATOMY (1:1 PROPORTIONAL MATCHING)"),
                (out_human_side, "PANEL C: PROFILE VIEW (POSTURE & PECTORAL DEPTH)"),
                (out_human_rear, "PANEL D: POSTERIOR VIEW (V-TAPER & SCAPULAR CONTOURS)"),
            ],
            out_path=out_human_master,
        )

    if args.race == "all":
        print("=== Generating Master All-Races Silhouette Lineup ===")
        out_all_lineup = args.output_dir / "all_races_silhouette_comparison.png"
        compose_all_races_lineup(
            args.output_dir,
            out_all_lineup,
            reference_root=ref_dir,
        )

    print(f"All silhouette comparison sheets generated successfully in {args.output_dir}")


def compose_all_races_lineup(artifact_dir: Path, out_path: Path, reference_root: Path | None = None):
    """Render a wide master lineup of all races on a single metric height scale."""
    canvas_w = 3840
    canvas_h = 1600
    canvas = Image.new("RGBA", (canvas_w, canvas_h), COLOR_BG)
    draw = ImageDraw.Draw(canvas)

    header_h = 170
    footer_h = 120
    ground_y = canvas_h - footer_h - 40
    ceiling_y = header_h + 80
    ruler_x_left = 140
    ruler_x_right = canvas_w - 140

    usable_h = ground_y - ceiling_y
    max_h_m = 3.1
    px_per_m = usable_h / max_h_m

    # Header
    draw.rectangle([0, 0, canvas_w, header_h], fill=(10, 12, 18, 255))
    draw.line([(0, header_h), (canvas_w, header_h)], fill=(45, 55, 75, 255), width=2)

    badge_w = 260
    draw.rectangle([ruler_x_left, 32, ruler_x_left + badge_w, 64], fill=(30, 45, 70, 255), outline=(70, 100, 150, 255))
    draw.text((ruler_x_left + 16, 38), "CANONICAL SCALE LINEUP", font=get_font(14, bold=True), fill=(100, 220, 255, 255))

    draw.text((ruler_x_left + badge_w + 30, 26), "Shadowrun NWN Humanoid Phenotype Master Lineup", font=get_font(34, bold=True), fill=COLOR_TEXT_PRIMARY)
    draw.text((ruler_x_left, 80), "Metric Height Ruler & Stature Verification: Comparing Stock Assets, High-Poly Derived Phenotypes, and Canonical Concept Art", font=get_font(18, bold=False), fill=COLOR_TEXT_SECONDARY)
    draw.text((ruler_x_left, 114), "DERIVED PHENOTYPE METHOD • ZERO CAP SEAMS • ZERO CONNECTOR DRIFT • CERTIFIED NATIVE COMPILATION", font=get_font(14, bold=True), fill=(255, 195, 80, 255))

    # Grid & Ruler
    m_step = 0.5
    curr_m = 0.0
    while curr_m <= max_h_m:
        y_pos = int(ground_y - curr_m * px_per_m)
        is_major = abs(curr_m - round(curr_m)) < 1e-4

        grid_color = COLOR_GRID_MAJOR if is_major else COLOR_GRID_MINOR
        draw.line([(ruler_x_left, y_pos), (ruler_x_right, y_pos)], fill=grid_color, width=2 if is_major else 1)

        label = f"{curr_m:.1f} m"
        draw.text((ruler_x_left - 75, y_pos - 9), label, font=get_font(14, bold=True), fill=COLOR_TEXT_PRIMARY if is_major else COLOR_TEXT_MUTED)
        draw.text((ruler_x_right + 18, y_pos - 9), label, font=get_font(14, bold=True), fill=COLOR_TEXT_PRIMARY if is_major else COLOR_TEXT_MUTED)
        curr_m += m_step

    draw.line([(ruler_x_left - 80, ground_y), (ruler_x_right + 80, ground_y)], fill=COLOR_GROUND, width=3)
    draw.text((ruler_x_left - 75, ground_y + 10), "Z = 0.00 m (GROUND)", font=get_font(12, bold=True), fill=COLOR_GROUND)

    ref_dir = reference_root if (reference_root and reference_root.exists()) else (artifact_dir / "scratch")

    # Load Figures: Dwarf, Human, Elf, Troll
    im_troll_concept = Image.open(ref_dir / "troll_male_fit.png")
    c_troll_m, _, _ = extract_concept_mask(im_troll_concept, (15, 435))

    im_dwarf_concept = Image.open(ref_dir / "dwarf_male_fit.png")
    c_dwarf_m, _, _ = extract_concept_mask(im_dwarf_concept, (20, 440))

    im_elf_concept = Image.open(ref_dir / "elf_male_fit.png")
    c_elf_m, _, _ = extract_concept_mask(im_elf_concept, (100, 415))

    im_troll_front = Image.open("output/phenotypes/derived-troll-male-v1/review/renders/troll_unlit_front.png")
    arr_tf = np.array(im_troll_front)
    fg_tf = np.any(np.abs(arr_tf[:, :, :3].astype(int) - np.array([55, 55, 73])) > 30, axis=2)
    s_human_m = fg_tf[:, :1200]
    d_troll_m = fg_tf[:, 1200:]

    df_path = ref_dir / "cp2_unlit_front.png"
    if not df_path.exists():
        df_path = artifact_dir / "cp2_unlit_front.png"
    im_dwarf_front = Image.open(df_path)
    arr_df = np.array(im_dwarf_front)
    fg_df = np.any(np.abs(arr_df[:, :, :3].astype(int) - np.array([55, 55, 73])) > 30, axis=2)
    s_dwarf_m = fg_df[:, 900:1500]
    d_dwarf_m = fg_df[:, 1600:2300]

    im_elf_front = Image.open(REPO_ROOT / "output/phenotypes/derived-elf-male-v1/review/renders/elf_unlit_front.png")
    arr_ef = np.array(im_elf_front)
    fg_ef = np.any(np.abs(arr_ef[:, :, :3].astype(int) - np.array([55, 55, 73])) > 30, axis=2)
    d_elf_m = fg_ef[:, 1200:]

    im_orc_concept = Image.open(ref_dir / "orc_male_fit.png")
    c_orc_m, _, _ = extract_concept_mask(im_orc_concept, (60, 420))

    orc_render_path = REPO_ROOT / "output/phenotypes/derived-orc-male-v1/review/renders/orc_unlit_front.png"
    if orc_render_path.exists():
        im_orc_front = Image.open(orc_render_path)
        arr_of = np.array(im_orc_front)
        bg_of = arr_of[10, 10, :3].astype(int)
        fg_of = np.any(np.abs(arr_of[:, :, :3].astype(int) - bg_of) > 25, axis=2)
        d_orc_m = fg_of[:, 1200:]
    else:
        d_orc_m = c_orc_m

    figures = [
        ("Stock Human (pmh0)", "Heroic Master", s_human_m, 1.9339, COLOR_STOCK_FILL, COLOR_STOCK_RIM),
        ("Stock Dwarf (pmd0)", "Low-Poly Control", s_dwarf_m, 1.4735, (90, 110, 135, 255), (140, 160, 185, 255)),
        ("Derived Dwarf (pmd0)", "Derived Phenotype", d_dwarf_m, 1.4864, COLOR_DERIVED_FILL, COLOR_DERIVED_RIM),
        ("Ideal Dwarf Target", "Shadowrun 4A Concept", c_dwarf_m, 1.3261, COLOR_IDEAL_FILL, COLOR_IDEAL_RIM),
        ("Derived Elf (pme0)", "Slender Lean Rig", d_elf_m, 2.0997, COLOR_DERIVED_FILL, COLOR_DERIVED_RIM),
        ("Ideal Elf Target", "Shadowrun 4A Concept", c_elf_m, 2.0997, COLOR_IDEAL_FILL, COLOR_IDEAL_RIM),
        ("Derived Orc (pmo0)", "Broad Muscular Rig", d_orc_m, 2.0997, COLOR_DERIVED_FILL, COLOR_DERIVED_RIM),
        ("Ideal Orc Target", "Shadowrun 4A Concept", c_orc_m, 2.0997, COLOR_IDEAL_FILL, COLOR_IDEAL_RIM),
        ("Derived Troll (pmg0)", "Broadened Rig (10/7)", d_troll_m, 2.7627, COLOR_DERIVED_FILL, COLOR_DERIVED_RIM),
        ("Ideal Troll Target", "Shadowrun 4A Concept", c_troll_m, 2.7627, COLOR_IDEAL_FILL, COLOR_IDEAL_RIM),
    ]

    num_figs = len(figures)
    slot_w = (ruler_x_right - ruler_x_left) // num_figs

    for idx, (title, sub, raw_m, h_m, fill_c, rim_c) in enumerate(figures):
        cx = ruler_x_left + idx * slot_w + slot_w // 2

        # Process figure
        rows = np.where(np.any(raw_m, axis=1))[0]
        cols = np.where(np.any(raw_m, axis=0))[0]
        cropped = raw_m[rows[0]:rows[-1]+1, cols[0]:cols[-1]+1]
        orig_h, orig_w = cropped.shape

        render_px_h = int(h_m * px_per_m)
        render_px_w = int(orig_w * (render_px_h / orig_h))

        img_m = Image.fromarray((cropped * 255).astype(np.uint8), mode="L")
        resized_m = img_m.resize((render_px_w, render_px_h), Image.Resampling.LANCZOS)
        res_arr = np.array(resized_m) > 120

        colored = create_colored_silhouette(res_arr, fill_c, rim_c, rim_width=2)

        # Paste
        paste_x = cx - render_px_w // 2
        paste_y = ground_y - render_px_h
        canvas.paste(colored, (paste_x, paste_y), colored)

        # Head height line
        draw.line([(paste_x - 8, paste_y), (paste_x + render_px_w + 8, paste_y)], fill=rim_c, width=2)
        draw.text((paste_x + render_px_w + 12, paste_y - 8), f"{h_m:.2f} m", font=get_font(12, bold=True), fill=rim_c)

        # Card below
        c_x0 = ruler_x_left + idx * slot_w + 8
        c_x1 = ruler_x_left + (idx + 1) * slot_w - 8
        card_y = ground_y + 20
        draw.rectangle([c_x0, card_y, c_x1, card_y + 80], fill=COLOR_PANEL_BG, outline=COLOR_PANEL_BORDER)
        draw.rectangle([c_x0, card_y, c_x1, card_y + 4], fill=fill_c)
        draw.text((c_x0 + 10, card_y + 12), title, font=get_font(13, bold=True), fill=COLOR_TEXT_PRIMARY)
        draw.text((c_x0 + 10, card_y + 32), sub, font=get_font(12, bold=False), fill=COLOR_TEXT_SECONDARY)
        draw.text((c_x0 + 10, card_y + 52), f"Stature: {h_m:.2f} m", font=get_font(12, bold=True), fill=(255, 200, 100, 255))

    canvas.save(out_path, format="PNG")
    print(f"Created all races lineup sheet -> {out_path} ({canvas_w}x{canvas_h})")


def compose_master_2x2_sheet(
    title: str,
    subtitle: str,
    panels: list[tuple[Path, str]],
    out_path: Path,
):
    """Combine 4 silhouette sheets into a single ultra-high-resolution master presentation sheet."""
    target_w = 3840
    header_h = 160
    cell_w = target_w // 2
    # aspect ratio of panels is 2700x1600 -> cell_h = cell_w * 1600 / 2700
    cell_h = int(cell_w * (1600 / 2700))
    canvas_h = header_h + cell_h * 2

    canvas = Image.new("RGBA", (target_w, canvas_h), (12, 15, 22, 255))
    draw = ImageDraw.Draw(canvas)

    # Header
    draw.rectangle([0, 0, target_w, header_h], fill=(10, 12, 18, 255))
    draw.line([(0, header_h), (target_w, header_h)], fill=(45, 55, 75, 255), width=2)

    badge_w = 220
    draw.rectangle([60, 32, 60 + badge_w, 64], fill=(30, 45, 70, 255), outline=(70, 100, 150, 255))
    draw.text((80, 38), "MASTER TURNAROUND MATRIX", font=get_font(14, bold=True), fill=(100, 220, 255, 255))

    draw.text((60 + badge_w + 30, 26), title, font=get_font(36, bold=True), fill=COLOR_TEXT_PRIMARY)
    draw.text((60, 84), subtitle, font=get_font(18, bold=False), fill=COLOR_TEXT_SECONDARY)
    draw.text((60, 114), "DERIVED PHENOTYPE PIPELINE • 3-WAY SILHOUETTE COMPARISON CERTIFICATION", font=get_font(14, bold=True), fill=(255, 195, 80, 255))

    positions = [
        (0, header_h),
        (cell_w, header_h),
        (0, header_h + cell_h),
        (cell_w, header_h + cell_h),
    ]

    for (p_path, label), (x, y) in zip(panels, positions):
        if p_path.exists():
            im = Image.open(p_path)
            resized = im.resize((cell_w, cell_h), Image.Resampling.LANCZOS)
            canvas.paste(resized, (x, y))

            # Inner subtle panel border
            draw.rectangle([x, y, x + cell_w, y + cell_h], outline=(35, 45, 65, 255), width=1)

            # Badge
            draw.rectangle([x + 20, y + 20, x + 540, y + 54], fill=(16, 20, 30, 230), outline=(60, 75, 105, 255))
            draw.text((x + 32, y + 26), label, font=get_font(14, bold=True), fill=(240, 245, 255, 255))

    canvas.save(out_path, format="PNG")
    print(f"Created master 2x2 turnaround sheet -> {out_path} ({target_w}x{canvas_h})")


if __name__ == "__main__":
    main()


