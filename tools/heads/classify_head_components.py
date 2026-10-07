"""Assign skin, eyes, hair, and accessories explicitly with reviewed allocations.

Automated color and component classification provides suggestions requiring review.
Enforces the 20,000-triangle NWN ceiling (default: 11K face/skull, 8K hair, 1K reserve).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from head_export import load_glb, triangles
from head_workflow import MAX_TRIANGLES, pin, read, require, sha, verify_pins, write_fresh

DEFAULT_BUDGET = {
    "skull_face_ears_eyes": 11000,
    "hair": 8000,
    "reserve": 1000,
    "combinedCeiling": MAX_TRIANGLES,
}


def extract_base_color_image(glb_path: str | Path) -> Image.Image:
    """Extract embedded base color texture from GLB, or return neutral white."""
    doc, binary = load_glb(glb_path)
    images = doc.get("images", [])
    if not images:
        return Image.new("RGB", (2048, 2048), (200, 180, 160))

    # Look for material base color texture
    img_idx = 0
    for mat in doc.get("materials", []):
        pbr = mat.get("pbrMetallicRoughness", {})
        b_tex = pbr.get("baseColorTexture")
        if b_tex:
            tex_idx = b_tex.get("index", 0)
            textures = doc.get("textures", [])
            if tex_idx < len(textures):
                img_idx = textures[tex_idx].get("source", 0)
            break

    if img_idx < len(images):
        img_info = images[img_idx]
        if "bufferView" in img_info:
            view = doc["bufferViews"][img_info["bufferView"]]
            offset = view.get("byteOffset", 0)
            length = view["byteLength"]
            data = binary[offset:offset + length]
            import io
            return Image.open(io.BytesIO(data)).convert("RGB")

    return Image.new("RGB", (2048, 2048), (200, 180, 160))


def classify_triangles(
    points: np.ndarray,
    uvs: np.ndarray,
    base_color_img: Image.Image,
    *,
    ocular_bounds: tuple[tuple[float, float, float], tuple[float, float, float]] | None = None,
    accessory_bounds: list[tuple[tuple[float, float, float], tuple[float, float, float]]] | None = None,
    overrides: dict | None = None,
) -> tuple[np.ndarray, list[dict], dict]:
    """Classify each triangle into: 0=skin, 1=hair, 2=eyes, 3=accessories.
    
    Returns (labels, boundary_suggestions, stats).
    """
    face_count = len(points)
    w, h = base_color_img.size
    img_arr = np.asarray(base_color_img, dtype=float)

    # Sample color at triangle UV centroids
    # In glTF, UV (0,0) is top-left
    uv_centers = uvs.mean(axis=1)
    px = np.clip(np.rint(uv_centers[:, 0] * (w - 1)).astype(int), 0, w - 1)
    py = np.clip(np.rint(uv_centers[:, 1] * (h - 1)).astype(int), 0, h - 1)
    colors = img_arr[py, px, :3]

    r, g, b = colors[:, 0], colors[:, 1], colors[:, 2]
    brightness = colors.max(axis=1)
    min_val = colors.min(axis=1)
    saturation = np.where(brightness > 1e-4, (brightness - min_val) / brightness, 0.0)

    # Spatial coordinates
    centroids = points.mean(axis=1)
    min_pt = points.min(axis=(0, 1))
    max_pt = points.max(axis=(0, 1))
    extent = max_pt - min_pt

    # Default ocular bounds if not given
    if ocular_bounds is None:
        y_mid = min_pt[1] + extent[1] * 0.35
        ocular_bounds = (
            (float(min_pt[0] * 0.55), float(y_mid), float(min_pt[2] + extent[2] * 0.45)),
            (float(max_pt[0] * 0.55), float(max_pt[1]), float(min_pt[2] + extent[2] * 0.75)),
        )

    oc_low = np.array(ocular_bounds[0])
    oc_high = np.array(ocular_bounds[1])
    in_ocular = ((centroids >= oc_low) & (centroids <= oc_high)).all(axis=1)

    # Initial classifications
    labels = np.zeros(face_count, dtype=int)  # default: 0 = skin

    # Hair detection:
    # 1. Dark fibers (low brightness)
    # 2. Or rear cranial / scalp location
    is_dark_hair = (brightness < 80) & (r - b < 30) & (g - b < 25)
    is_posterior_scalp = (centroids[:, 1] < (min_pt[1] + extent[1] * 0.45)) & (
        centroids[:, 2] > (min_pt[2] + extent[2] * 0.35)
    )
    labels[is_dark_hair | is_posterior_scalp] = 1

    # Eyes detection: inside ocular bounds with eye characteristics
    # High sclera brightness or iris coloration
    is_sclera = in_ocular & (brightness > 140) & (saturation < 0.25)
    is_iris = in_ocular & (brightness < 120) & (centroids[:, 1] > oc_low[1] + (oc_high[1] - oc_low[1]) * 0.5)
    labels[is_sclera | is_iris] = 2

    # Accessories detection (horns, tusks, cyberware)
    if accessory_bounds:
        for acc_box in accessory_bounds:
            low = np.array(acc_box[0])
            high = np.array(acc_box[1])
            in_box = ((centroids >= low) & (centroids <= high)).all(axis=1)
            labels[in_box] = 3

    # Boundary and transition regions requiring review
    boundary_suggestions = []

    # 1. Eyebrows (hair overlapping facial/ocular region)
    eyebrow_box = (
        (centroids[:, 0] >= oc_low[0]) & (centroids[:, 0] <= oc_high[0])
        & (centroids[:, 1] >= oc_low[1]) & (centroids[:, 1] <= oc_high[1])
        & (centroids[:, 2] >= oc_low[2] + (oc_high[2] - oc_low[2]) * 0.7)
    )
    eyebrow_faces = np.flatnonzero(eyebrow_box & (labels == 1))
    if len(eyebrow_faces):
        boundary_suggestions.append({
            "region": "eyebrows",
            "triangleCount": len(eyebrow_faces),
            "faceIndicesSample": eyebrow_faces[:20].tolist(),
            "note": "Eyebrow geometry on facial boundary; verify skin/hair ownership",
            "reviewRequired": True,
        })

    # 2. Hairline transition (forehead / temples)
    hairline_box = (
        (centroids[:, 1] >= min_pt[1] + extent[1] * 0.3)
        & (centroids[:, 1] <= min_pt[1] + extent[1] * 0.6)
        & (centroids[:, 2] >= min_pt[2] + extent[2] * 0.7)
    )
    hairline_faces = np.flatnonzero(hairline_box)
    if len(hairline_faces):
        boundary_suggestions.append({
            "region": "hairline_transition",
            "triangleCount": len(hairline_faces),
            "faceIndicesSample": hairline_faces[:20].tolist(),
            "note": "Hairline forehead and temple strands; verify separation",
            "reviewRequired": True,
        })

    # 3. Eye surrounds (eyelid margins)
    eyelid_margin = in_ocular & ~is_sclera & ~is_iris
    eyelid_faces = np.flatnonzero(eyelid_margin)
    if len(eyelid_faces):
        boundary_suggestions.append({
            "region": "eyelid_surrounds",
            "triangleCount": len(eyelid_faces),
            "faceIndicesSample": eyelid_faces[:20].tolist(),
            "note": "Eye opening perimeter; verify eyelid opening does not occlude eyeball",
            "reviewRequired": True,
        })

    # Apply overrides if provided
    if overrides:
        for face_id in overrides.get("skinFaceIds", []):
            if 0 <= face_id < face_count:
                labels[face_id] = 0
        for face_id in overrides.get("hairFaceIds", []):
            if 0 <= face_id < face_count:
                labels[face_id] = 1
        for face_id in overrides.get("eyeFaceIds", []):
            if 0 <= face_id < face_count:
                labels[face_id] = 2
        for face_id in overrides.get("accessoryFaceIds", []):
            if 0 <= face_id < face_count:
                labels[face_id] = 3

    stats = {
        "skinTriangles": int((labels == 0).sum()),
        "hairTriangles": int((labels == 1).sum()),
        "eyeTriangles": int((labels == 2).sum()),
        "accessoryTriangles": int((labels == 3).sum()),
        "totalTriangles": face_count,
    }
    return labels, boundary_suggestions, stats


def allocate_budgets(
    triangle_counts: dict,
    custom_budget: dict | None = None,
) -> dict:
    """Enforce combined 20,000-triangle budget ceiling and standard allocations."""
    budget = dict(DEFAULT_BUDGET)
    if custom_budget:
        budget.update(custom_budget)

    combined_target = (
        budget["skull_face_ears_eyes"] + budget["hair"] + budget["reserve"]
    )
    require(
        combined_target <= budget["combinedCeiling"],
        f"Budget target {combined_target} exceeds ceiling {budget['combinedCeiling']}",
    )
    require(
        budget["combinedCeiling"] <= MAX_TRIANGLES,
        f"Combined ceiling exceeds 20,000 NWN limit: {budget['combinedCeiling']}",
    )

    allocation = {
        "targets": {
            "skull_face_ears_eyes": budget["skull_face_ears_eyes"],
            "hair": budget["hair"],
            "reserve": budget["reserve"],
            "combinedCeiling": budget["combinedCeiling"],
        },
        "donorCounts": triangle_counts,
        "withinCeiling": True,
    }
    return allocation


def classify_donor(
    source_path: str | Path,
    output_path: str | Path,
    *,
    custom_budget: dict | None = None,
    overrides_path: str | Path | None = None,
) -> dict:
    """Run full component classification and budget allocation."""
    started = time.monotonic()
    source_pin = pin(source_path)
    p, n, uv = triangles(source_path, np.eye(4), maximum=500000)

    overrides = None
    overrides_pin = None
    if overrides_path:
        overrides = read(overrides_path)
        overrides_pin = pin(overrides_path)

    base_color = extract_base_color_image(source_path)
    labels, suggestions, stats = classify_triangles(p, uv, base_color, overrides=overrides)

    allocation = allocate_budgets(stats, custom_budget)

    report = {
        "kind": "srn-head-component-classification",
        "passed": True,
        "source": source_pin,
        "overrides": overrides_pin,
        "triangleCount": len(p),
        "componentStats": stats,
        "budgetAllocation": allocation,
        "boundarySuggestions": suggestions,
        "labelDistribution": {
            "skin": int((labels == 0).sum()),
            "hair": int((labels == 1).sum()),
            "eyes": int((labels == 2).sum()),
            "accessories": int((labels == 3).sum()),
        },
        "reviewPrinciple": (
            "Assign skin, eyes, hair, and accessories explicitly. "
            "Automated classifications are suggestions requiring review."
        ),
        "combinedCeilingEnforced": MAX_TRIANGLES,
        "elapsedSeconds": round(time.monotonic() - started, 4),
    }

    out = Path(output_path)
    write_fresh(out, report)
    # Save label array as .npy for downstream consumption
    np.save(out.with_suffix(".labels.npy"), labels)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--overrides", type=Path)
    parser.add_argument("--face-budget", type=int, default=11000)
    parser.add_argument("--hair-budget", type=int, default=8000)
    parser.add_argument("--reserve", type=int, default=1000)
    args = parser.parse_args()

    require(not args.output.exists(), "Fresh output receipt required")
    custom = {
        "skull_face_ears_eyes": args.face_budget,
        "hair": args.hair_budget,
        "reserve": args.reserve,
        "combinedCeiling": MAX_TRIANGLES,
    }
    report = classify_donor(
        args.source, args.output, custom_budget=custom, overrides_path=args.overrides
    )
    print(json.dumps({
        "classification": str(args.output),
        "triangles": report["triangleCount"],
        "skin": report["componentStats"]["skinTriangles"],
        "hair": report["componentStats"]["hairTriangles"],
        "eyes": report["componentStats"]["eyeTriangles"],
        "accessories": report["componentStats"]["accessoryTriangles"],
    }))


if __name__ == "__main__":
    main()
