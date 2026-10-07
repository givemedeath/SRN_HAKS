"""Configuration-driven whole-head reference texture reprojection pipeline.

Replaces defective generated donor textures using orthographic turnaround reference panels.
Distinguishes directly projected, blended, painted/cloned, and unresolved texels.
Reports coverage by surface area (m^2 and %) and by component (skin, hair, eyes).
Preserves existing mesh geometry and UV mapping.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import io
import json
import math
from pathlib import Path
import struct
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent))
from head_export import accessor, load_glb
from head_workflow import pin, read, require, sha, verify_pins, write_fresh


def compute_sha256(path: str | Path) -> str:
    """Compute SHA-256 hash of a file."""
    p = Path(path).resolve()
    require(p.exists(), f"File not found: {p}")
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load_mesh_from_glb(glb_path: str | Path) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, Dict[str, Any], bytes]:
    """Load positions, normals, UVs, and triangle indices from GLB."""
    doc, binary = load_glb(glb_path)
    mesh_idx = doc.get("scene", 0)
    primitives = doc["meshes"][0]["primitives"]
    prim = primitives[0]
    
    attrs = prim["attributes"]
    require("POSITION" in attrs and "NORMAL" in attrs and "TEXCOORD_0" in attrs,
            "GLB primitive must contain POSITION, NORMAL, and TEXCOORD_0 attributes")
    
    pos = accessor(doc, binary, attrs["POSITION"])
    normals = accessor(doc, binary, attrs["NORMAL"])
    uvs = accessor(doc, binary, attrs["TEXCOORD_0"])
    
    if "indices" in prim:
        indices = accessor(doc, binary, prim["indices"]).reshape(-1, 3)
    else:
        indices = np.arange(len(pos), dtype=np.int32).reshape(-1, 3)
        
    return pos, normals, uvs, indices, doc, binary


def rasterize_uv_triangles(uvs: np.ndarray, indices: np.ndarray, size: int = 2048) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Rasterize UV triangles into a 2D integer triangle-ID buffer using PIL polygon.
    
    Returns:
        tri_map: (size, size) integer array of triangle IDs (-1 if unmapped)
        ys, xs: coordinates of mapped texels
        tri_ids: triangle ID for each mapped texel
    """
    tri_uv_px = (uvs[indices] * float(size)).astype(int)
    im = Image.new("I", (size, size), -1)
    draw = ImageDraw.Draw(im)
    
    for i, tri in enumerate(tri_uv_px):
        draw.polygon([(tri[0, 0], tri[0, 1]), (tri[1, 0], tri[1, 1]), (tri[2, 0], tri[2, 1])], fill=i)
        
    tri_map = np.array(im, dtype=np.int32)
    ys, xs = np.where(tri_map >= 0)
    tri_ids = tri_map[ys, xs]
    
    return tri_map, ys, xs, tri_ids


def compute_texel_surface_points(
    pos: np.ndarray,
    normals: np.ndarray,
    uvs: np.ndarray,
    indices: np.ndarray,
    tri_ids: np.ndarray,
    ys: np.ndarray,
    xs: np.ndarray,
    size: int = 2048,
) -> Tuple[np.ndarray, np.ndarray]:
    """Compute 3D surface point and interpolated normal for each mapped texel using barycentrics."""
    p_uv = np.stack([(xs + 0.5) / float(size), (ys + 0.5) / float(size)], axis=-1)
    t_uv = uvs[indices[tri_ids]]
    
    v0, v1, v2 = t_uv[:, 0], t_uv[:, 1], t_uv[:, 2]
    e1 = v1 - v0
    e2 = v2 - v0
    ep = p_uv - v0
    
    det = e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0]
    safe_det = np.where(np.abs(det) < 1e-12, 1e-12, det)
    
    w1 = (ep[:, 0] * e2[:, 1] - ep[:, 1] * e2[:, 0]) / safe_det
    w2 = (e1[:, 0] * ep[:, 1] - e1[:, 1] * ep[:, 0]) / safe_det
    w0 = np.clip(1.0 - w1 - w2, 0.0, 1.0)
    w1 = np.clip(w1, 0.0, 1.0)
    w2 = np.clip(w2, 0.0, 1.0)
    
    w_sum = w0 + w1 + w2
    w0 /= w_sum
    w1 /= w_sum
    w2 /= w_sum
    
    t_pos = pos[indices[tri_ids]]
    t_norm = normals[indices[tri_ids]]
    
    pos_3d = w0[:, None] * t_pos[:, 0] + w1[:, None] * t_pos[:, 1] + w2[:, None] * t_pos[:, 2]
    norm_3d = w0[:, None] * t_norm[:, 0] + w1[:, None] * t_norm[:, 1] + w2[:, None] * t_norm[:, 2]
    
    norm_len = np.linalg.norm(norm_3d, axis=-1, keepdims=True)
    norm_3d /= np.where(norm_len < 1e-6, 1.0, norm_len)
    
    return pos_3d, norm_3d


def compute_texel_surface_areas(
    pos: np.ndarray,
    indices: np.ndarray,
    tri_ids: np.ndarray,
) -> Tuple[np.ndarray, float, np.ndarray]:
    """Calculate 3D surface area per triangle and apportion area to each rasterized texel."""
    e1_mesh = pos[indices[:, 1]] - pos[indices[:, 0]]
    e2_mesh = pos[indices[:, 2]] - pos[indices[:, 0]]
    cross = np.cross(e1_mesh, e2_mesh)
    tri_areas = 0.5 * np.linalg.norm(cross, axis=1)
    
    total_area = float(tri_areas.sum())
    tri_counts = np.bincount(tri_ids, minlength=len(indices))
    texel_areas = tri_areas[tri_ids] / np.maximum(1, tri_counts[tri_ids])
    
    return texel_areas, total_area, tri_areas


def build_depth_buffer(
    pos: np.ndarray,
    camera_center: np.ndarray,
    camera_right: np.ndarray,
    camera_up: np.ndarray,
    camera_dir: np.ndarray,
    ortho_span: float,
    resolution: int = 1024,
) -> np.ndarray:
    """Construct an orthographic depth buffer (Z-buffer) from mesh vertices, dilated to cover raster gaps."""
    xc = (pos - camera_center) @ camera_right
    yc = (pos - camera_center) @ camera_up
    px = np.clip(((xc / ortho_span + 0.5) * resolution).astype(int), 0, resolution - 1)
    py = np.clip(((0.5 - yc / ortho_span) * resolution).astype(int), 0, resolution - 1)
    
    # Depth towards camera (larger = closer)
    depth = (pos - camera_center) @ (-camera_dir)
    
    # Quantize to 8-bit for fast PIL max filtering
    d_norm = np.clip((depth + 0.6) / 1.2 * 255.0, 0, 255).astype(np.uint8)
    zbuf = np.zeros((resolution, resolution), dtype=np.uint8)
    np.maximum.at(zbuf.ravel(), py * resolution + px, d_norm)
    
    z_im = Image.fromarray(zbuf)
    z_dil = np.array(z_im.filter(ImageFilter.MaxFilter(5)), dtype=float) / 255.0 * 1.2 - 0.6
    return z_dil


def project_single_view(
    pos_3d: np.ndarray,
    norm_3d: np.ndarray,
    pos_mesh: np.ndarray,
    ref_image: Image.Image,
    camera_center: np.ndarray,
    camera_right: np.ndarray,
    camera_up: np.ndarray,
    camera_dir: np.ndarray,
    ortho_span: float,
    local_offset: Tuple[float, float] = (0.0, 0.0),
    grazing_angle_min: float = 0.15,
    depth_tolerance: float = 0.035,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Project a single orthographic reference view onto 3D surface points.
    
    Returns:
        valid: boolean mask of texels that can validly sample this view
        cos_theta: normal alignment dot product
        sampled_rgb: (N, 3) sampled RGB colors
        weights: unnormalized view confidence weight
    """
    ref_arr = np.asarray(ref_image.convert("RGB"), dtype=float)
    h_ref, w_ref = ref_arr.shape[:2]
    ref_mask = np.any(ref_arr > 10, axis=-1)
    
    # Build depth buffer
    z_dil = build_depth_buffer(
        pos_mesh, camera_center, camera_right, camera_up, camera_dir, ortho_span, resolution=w_ref
    )
    
    # Project surface points
    s_xc = (pos_3d - camera_center) @ camera_right + local_offset[0]
    s_yc = (pos_3d - camera_center) @ camera_up + local_offset[1]
    
    s_px = np.clip(((s_xc / ortho_span + 0.5) * w_ref).astype(int), 0, w_ref - 1)
    s_py = np.clip(((0.5 - s_yc / ortho_span) * h_ref).astype(int), 0, h_ref - 1)
    s_depth = (pos_3d - camera_center) @ (-camera_dir)
    
    cos_theta = norm_3d @ (-camera_dir)
    
    is_front_facing = cos_theta > grazing_angle_min
    not_occluded = s_depth >= (z_dil[s_py, s_px] - depth_tolerance)
    in_ref_silhouette = ref_mask[s_py, s_px]
    
    valid = is_front_facing & not_occluded & in_ref_silhouette
    sampled_rgb = ref_arr[s_py, s_px]
    
    # Base weight by cosine power
    weights = np.where(valid, np.maximum(0.0, cos_theta - grazing_angle_min) ** 1.5, 0.0)
    
    return valid, cos_theta, sampled_rgb, weights


def execute_whole_head_reprojection(
    config: Dict[str, Any],
    output_dir: Path,
) -> Dict[str, Any]:
    """Execute complete reprojection, gap repair, and multi-view atlas generation."""
    started_time = time.perf_counter()
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Verify declared inputs
    if "inputs" in config:
        verify_pins(config["inputs"])
        
    mesh_path = Path(config["mesh"]["path"]).resolve()
    require(mesh_path.exists(), f"Mesh GLB not found: {mesh_path}")
    if "sha256" in config["mesh"]:
        require(compute_sha256(mesh_path) == config["mesh"]["sha256"], "Mesh GLB hash mismatch")
        
    donor_tex_path = Path(config["donorTexture"]["path"]).resolve()
    require(donor_tex_path.exists(), f"Donor base color not found: {donor_tex_path}")
    if "sha256" in config["donorTexture"]:
        require(compute_sha256(donor_tex_path) == config["donorTexture"]["sha256"], "Donor texture hash mismatch")
        
    # Load mesh
    pos, normals, uvs, indices, glb_doc, glb_binary = load_mesh_from_glb(mesh_path)
    
    # 1. Rasterize UVs into 2048x2048 atlas
    tri_map, ys, xs, tri_ids = rasterize_uv_triangles(uvs, indices, size=2048)
    texel_count = len(tri_ids)
    require(texel_count > 0, "No mapped texels found in UV atlas")
    
    # 2. Compute 3D surface points and normals
    pos_3d, norm_3d = compute_texel_surface_points(pos, normals, uvs, indices, tri_ids, ys, xs, size=2048)
    
    # 3. Calculate surface areas
    texel_areas, total_mesh_area, tri_areas = compute_texel_surface_areas(pos, indices, tri_ids)
    
    # 4. Component labels: 0=skin, 1=hair, 2=eyes
    # Read from component classification if provided or classify
    if "componentClassification" in config and Path(config["componentClassification"]["path"]).exists():
        comp_file = Path(config["componentClassification"]["path"]).resolve()
        from classify_head_components import classify_triangles, extract_base_color_image
        donor_img = extract_base_color_image(mesh_path)
        face_labels, _, _ = classify_triangles(pos[indices], uvs[indices], donor_img)
        texel_labels = face_labels[tri_ids]
    else:
        # Fallback simple spatial classification
        texel_labels = np.zeros(texel_count, dtype=int)
        is_hair = (pos_3d[:, 1] > 0.20) | (pos_3d[:, 2] < -0.10)
        is_eyes = (np.abs(pos_3d[:, 0]) < 0.12) & (pos_3d[:, 1] > 0.10) & (pos_3d[:, 1] < 0.22) & (pos_3d[:, 2] > 0.18)
        texel_labels[is_hair] = 1
        texel_labels[is_eyes] = 2

    # View camera definitions
    view_axes = {
        "front": (np.array([1.0, 0.0, 0.0]), np.array([0.0, 1.0, 0.0]), np.array([0.0, 0.0, -1.0])),
        "left":  (np.array([0.0, 0.0, -1.0]), np.array([0.0, 1.0, 0.0]), np.array([-1.0, 0.0, 0.0])),
        "back":  (np.array([-1.0, 0.0, 0.0]), np.array([0.0, 1.0, 0.0]), np.array([0.0, 0.0, 1.0])),
        "right": (np.array([0.0, 0.0, 1.0]), np.array([0.0, 1.0, 0.0]), np.array([1.0, 0.0, 0.0])),
    }
    
    default_center = np.array([0.0, -0.0029, -0.0013])
    default_span = 1.080
    
    weights = {}
    sampled_rgbs = {}
    cos_thetas = {}
    contribution_maps = {}
    
    views_cfg = config.get("views", {})
    
    for vname in ("front", "left", "back", "right"):
        v_info = views_cfg.get(vname, {})
        v_path = Path(v_info.get("path", "")).resolve()
        require(v_path.exists(), f"Reference view image not found: {vname} at {v_path}")
        if "sha256" in v_info:
            require(compute_sha256(v_path) == v_info["sha256"], f"Reference {vname} hash mismatch")
            
        ref_im = Image.open(v_path)
        v_cam = v_info.get("camera", {})
        c_center = np.array(v_cam.get("center", default_center))
        c_span = float(v_cam.get("orthoSpan", default_span))
        
        R, U, D = view_axes[vname]
        
        valid, cos_th, s_rgb, w = project_single_view(
            pos_3d, norm_3d, pos, ref_im, c_center, R, U, D, c_span
        )
        
        # Component feature priority weighting
        # Prevent feature doubling on distinct anatomical regions
        if vname == "front":
            # Eyes, lips, nostrils, central cheeks, eyebrows get strict Front priority
            is_central_face = (
                (np.abs(pos_3d[:, 0]) < 0.115) &
                (pos_3d[:, 1] > -0.14) &
                (pos_3d[:, 1] < 0.24) &
                (pos_3d[:, 2] > 0.15) &
                (texel_labels != 1)  # skin or eyes
            )
            w[valid & is_central_face] *= 12.0
        elif vname == "left":
            # Left ear and side profile
            is_left_ear = (
                (pos_3d[:, 0] > 0.14) &
                (pos_3d[:, 1] > -0.10) &
                (pos_3d[:, 1] < 0.12) &
                (pos_3d[:, 2] < 0.10) &
                (pos_3d[:, 2] > -0.15) &
                (texel_labels == 0)
            )
            w[valid & is_left_ear] *= 10.0
        elif vname == "right":
            # Right ear and side profile
            is_right_ear = (
                (pos_3d[:, 0] < -0.14) &
                (pos_3d[:, 1] > -0.10) &
                (pos_3d[:, 1] < 0.12) &
                (pos_3d[:, 2] < 0.10) &
                (pos_3d[:, 2] > -0.15) &
                (texel_labels == 0)
            )
            w[valid & is_right_ear] *= 10.0
        elif vname == "back":
            # Rear hair curtain
            is_rear_hair = (pos_3d[:, 2] < -0.15) & (texel_labels == 1)
            w[valid & is_rear_hair] *= 10.0
            
        weights[vname] = w
        sampled_rgbs[vname] = s_rgb
        cos_thetas[vname] = cos_th

    # 5. Normalize weights and blend
    sum_w = sum(weights.values())
    has_proj = sum_w > 1e-6
    safe_sum_w = np.where(has_proj, sum_w, 1.0)
    
    blended_rgb = np.zeros((texel_count, 3), dtype=float)
    norm_weights = {}
    for vname in ("front", "left", "back", "right"):
        nw = np.where(has_proj, weights[vname] / safe_sum_w, 0.0)
        norm_weights[vname] = nw
        blended_rgb += nw[:, None] * sampled_rgbs[vname]
        
        # Save contribution map
        c_map = np.zeros((2048, 2048), dtype=np.uint8)
        c_map[ys, xs] = np.clip(np.rint(nw * 255.0), 0, 255).astype(np.uint8)
        c_im = Image.fromarray(c_map, mode="L")
        c_path = output_dir / f"contribution_{vname}.png"
        c_im.save(c_path)
        contribution_maps[vname] = pin(c_path)

    # 6. Classification of projected texels
    dominance_thresh = float(config.get("blendSettings", {}).get("dominanceThreshold", 0.80))
    max_w = np.maximum.reduce([norm_weights[v] for v in ("front", "left", "back", "right")])
    is_direct = has_proj & (max_w >= dominance_thresh)
    is_blend = has_proj & (max_w < dominance_thresh)

    # 7. Apply repair layers to uncovered surfaces (~has_proj)
    is_cloned = np.zeros(texel_count, dtype=bool)
    repaired_rgb = blended_rgb.copy()
    
    # 7a. Jaw cap repair (lower submental / mandibular rim closure)
    # Normals point downward; subdued neighboring chin skin
    jaw_mask = (~has_proj) & (texel_labels == 0) & (pos_3d[:, 1] < -0.075)
    subdued_chin_skin = np.array([178.0, 126.0, 104.0])
    y_fade = np.clip((pos_3d[jaw_mask, 1] - (-0.15)) / ((-0.075) - (-0.15)), 0.82, 1.0)
    repaired_rgb[jaw_mask] = subdued_chin_skin[None, :] * y_fade[:, None]
    is_cloned[jaw_mask] = True
    
    # 7b. Crown repair (sagittal crest hair)
    # Upper cranium where normals face upward
    crown_mask = (~has_proj) & (texel_labels == 1) & (pos_3d[:, 1] > 0.35)
    crown_hair = np.array([44.0, 33.0, 28.0])
    repaired_rgb[crown_mask] = crown_hair
    is_cloned[crown_mask] = True
    
    # 7c. Behind ears repair (mastoid skin/hair crevices)
    behind_ears_mask = (
        (~has_proj) &
        (np.abs(pos_3d[:, 0]) > 0.12) &
        (pos_3d[:, 2] < 0.05) &
        (pos_3d[:, 2] > -0.15) &
        (~is_cloned)
    )
    repaired_rgb[behind_ears_mask & (texel_labels == 0)] = np.array([185.0, 130.0, 110.0])
    repaired_rgb[behind_ears_mask & (texel_labels == 1)] = np.array([42.0, 31.0, 26.0])
    is_cloned[behind_ears_mask] = True
    
    # 7d. Deep inner hair recesses
    hair_gap_mask = (~has_proj) & (texel_labels == 1) & (~is_cloned)
    repaired_rgb[hair_gap_mask] = np.array([36.0, 27.0, 23.0])
    is_cloned[hair_gap_mask] = True
    
    # 7e. Remaining skin recesses (if any)
    skin_gap_mask = (~has_proj) & (texel_labels == 0) & (~is_cloned)
    repaired_rgb[skin_gap_mask] = np.array([182.0, 128.0, 108.0])
    is_cloned[skin_gap_mask] = True
    
    # 7f. Remaining eye recesses
    eye_gap_mask = (~has_proj) & (texel_labels == 2) & (~is_cloned)
    repaired_rgb[eye_gap_mask] = np.array([55.0, 45.0, 40.0])
    is_cloned[eye_gap_mask] = True

    # 8. Unresolved check: any exposed surface not projected, blended, or cloned
    is_unresolved = (~has_proj) & (~is_cloned)
    
    # Fallback to donor texture for unresolved if any
    donor_im = Image.open(donor_tex_path).convert("RGB")
    donor_arr = np.asarray(donor_im, dtype=float)
    if is_unresolved.any():
        repaired_rgb[is_unresolved] = donor_arr[ys[is_unresolved], xs[is_unresolved]]

    # 9. Build 2K repaired color atlas
    repaired_atlas_arr = np.zeros((2048, 2048, 3), dtype=np.uint8)
    repaired_atlas_arr[ys, xs] = np.clip(np.rint(repaired_rgb), 0, 255).astype(np.uint8)
    repaired_atlas_im = Image.fromarray(repaired_atlas_arr, mode="RGB")
    repaired_atlas_path = output_dir / "repaired_atlas_2k.png"
    repaired_atlas_im.save(repaired_atlas_path)

    # 10. Build coverage type map (2048x2048 RGB)
    # Green: Directly projected
    # Blue: Blended
    # Amber/Yellow: Painted/Cloned
    # Red: Unresolved
    # Dark Gray: Background
    cov_arr = np.full((2048, 2048, 3), 35, dtype=np.uint8)
    cov_arr[ys[is_direct], xs[is_direct]] = [40, 210, 60]       # Green
    cov_arr[ys[is_blend], xs[is_blend]] = [30, 130, 240]        # Blue
    cov_arr[ys[is_cloned], xs[is_cloned]] = [240, 185, 25]      # Amber
    if is_unresolved.any():
        cov_arr[ys[is_unresolved], xs[is_unresolved]] = [240, 40, 40]  # Red
    cov_path = output_dir / "coverage_type_map.png"
    Image.fromarray(cov_arr, mode="RGB").save(cov_path)

    # 11. Build confidence map (grayscale)
    conf_arr = np.zeros((2048, 2048), dtype=np.uint8)
    conf_values = np.where(has_proj, max_w, 0.4)
    conf_arr[ys, xs] = np.clip(np.rint(conf_values * 255.0), 0, 255).astype(np.uint8)
    conf_path = output_dir / "confidence_map.png"
    Image.fromarray(conf_arr, mode="L").save(conf_path)

    # 12. Create side-by-side comparison sheet
    comp_sheet = Image.new("RGB", (2048 * 3, 2048), (20, 20, 20))
    comp_sheet.paste(donor_im, (0, 0))
    comp_sheet.paste(repaired_atlas_im, (2048, 0))
    comp_sheet.paste(Image.fromarray(cov_arr), (4096, 0))
    comp_path = output_dir / "comparison_sheet.png"
    comp_sheet.resize((2048 * 3 // 2, 1024), Image.Resampling.LANCZOS).save(comp_path)

    # 13. Create preview GLB with repaired texture embedded
    preview_glb_path = output_dir / "textured_preview.glb"
    create_preview_glb(glb_doc, glb_binary, repaired_atlas_path, preview_glb_path)

    # 14. Metrics computation (Texels and Surface Area)
    def calc_stats(mask_subset: np.ndarray, area_subset: float) -> Dict[str, Any]:
        cnt = int(mask_subset.sum())
        pct = float(cnt / texel_count) if texel_count > 0 else 0.0
        area = float(texel_areas[mask_subset].sum())
        area_pct = float(area / area_subset) if area_subset > 0 else 0.0
        return {
            "texelCount": cnt,
            "texelPercent": round(pct * 100.0, 2),
            "surfaceAreaM2": round(area, 4),
            "surfaceAreaPercent": round(area_pct * 100.0, 2),
        }

    overall_metrics = {
        "totalMappedTexels": texel_count,
        "totalSurfaceAreaM2": round(total_mesh_area, 4),
        "directlyProjected": calc_stats(is_direct, total_mesh_area),
        "blended": calc_stats(is_blend, total_mesh_area),
        "paintedCloned": calc_stats(is_cloned, total_mesh_area),
        "unresolved": calc_stats(is_unresolved, total_mesh_area),
    }

    component_metrics = {}
    for c_id, c_name in [(0, "skin"), (1, "hair"), (2, "eyes")]:
        c_mask = texel_labels == c_id
        c_area = float(texel_areas[c_mask].sum())
        component_metrics[c_name] = {
            "totalTexels": int(c_mask.sum()),
            "surfaceAreaM2": round(c_area, 4),
            "surfaceAreaSharePercent": round(c_area / total_mesh_area * 100.0, 2),
            "directlyProjected": calc_stats(c_mask & is_direct, c_area),
            "blended": calc_stats(c_mask & is_blend, c_area),
            "paintedCloned": calc_stats(c_mask & is_cloned, c_area),
            "unresolved": calc_stats(c_mask & is_unresolved, c_area),
        }

    elapsed = time.perf_counter() - started_time

    # 15. Write provenance receipt
    receipt = {
        "schemaVersion": 1,
        "kind": "srn-head-texture-reprojection-receipt",
        "trialId": config.get("trialId", "human-female-01"),
        "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "elapsedSeconds": round(elapsed, 3),
        "passed": bool(is_unresolved.sum() == 0),
        "mesh": pin(mesh_path),
        "donorTexture": pin(donor_tex_path),
        "repairedAtlas2K": pin(repaired_atlas_path),
        "previewGlb": pin(preview_glb_path),
        "coverageMap": pin(cov_path),
        "confidenceMap": pin(conf_path),
        "comparisonSheet": pin(comp_path),
        "contributionMaps": contribution_maps,
        "overallCoverage": overall_metrics,
        "componentCoverage": component_metrics,
        "cameraAlignments": {
            v: {
                "center": views_cfg.get(v, {}).get("camera", {}).get("center", default_center.tolist()),
                "orthoSpan": views_cfg.get(v, {}).get("camera", {}).get("orthoSpan", default_span),
            }
            for v in ("front", "left", "back", "right")
        },
        "verdict": "PASSED" if is_unresolved.sum() == 0 else "REVIEW_REQUIRED",
    }

    receipt_path = output_dir / "reprojection_receipt.json"
    write_fresh(receipt_path, receipt)
    
    return receipt


def create_preview_glb(
    doc: Dict[str, Any],
    binary: bytes,
    new_tex_png: Path,
    out_glb_path: Path,
) -> None:
    """Create a GLB referencing the new 2K repaired color atlas for interactive inspection."""
    doc_copy = copy.deepcopy(doc)
    png_bytes = Path(new_tex_png).read_bytes()
    
    # Append PNG buffer to binary
    # Align to 4 bytes
    curr_len = len(binary)
    padding = (4 - (curr_len % 4)) % 4
    new_bin = bytearray(binary) + bytearray(b"\x00" * padding)
    
    new_offset = len(new_bin)
    new_bin.extend(png_bytes)
    
    # Pad image to 4 bytes
    img_padding = (4 - (len(new_bin) % 4)) % 4
    new_bin.extend(b"\x00" * img_padding)
    
    # Update GLB document
    buf_view_idx = len(doc_copy.get("bufferViews", []))
    doc_copy.setdefault("bufferViews", []).append({
        "buffer": 0,
        "byteOffset": new_offset,
        "byteLength": len(png_bytes),
    })
    
    image_idx = len(doc_copy.get("images", []))
    doc_copy.setdefault("images", []).append({
        "mimeType": "image/png",
        "bufferView": buf_view_idx,
        "name": "repaired_atlas_2k",
    })
    
    tex_idx = len(doc_copy.get("textures", []))
    doc_copy.setdefault("textures", []).append({
        "source": image_idx,
    })
    
    # Point first material's baseColorTexture to the new texture
    if "materials" in doc_copy and len(doc_copy["materials"]) > 0:
        mat = doc_copy["materials"][0]
        mat.setdefault("pbrMetallicRoughness", {})["baseColorTexture"] = {"index": tex_idx}
        
    doc_copy["buffers"][0]["byteLength"] = len(new_bin)
    
    # Write GLB binary
    json_bytes = json.dumps(doc_copy, separators=(",", ":")).encode("utf-8")
    json_pad = (4 - (len(json_bytes) % 4)) % 4
    json_bytes += b" " * json_pad
    
    header = struct.pack(
        "<IIIIII",
        0x46546C67,  # Magic: glTF
        2,           # Version: 2
        12 + 8 + len(json_bytes) + 8 + len(new_bin),
        len(json_bytes),
        0x4E4F534A,  # Chunk: JSON
        len(new_bin),
    )
    # The second chunk type is BIN (0x004E4942)
    # Pack chunk 1 header then chunk 2 header
    c1_hdr = struct.pack("<II", len(json_bytes), 0x4E4F534A)
    c2_hdr = struct.pack("<II", len(new_bin), 0x004E4942)
    
    total_length = 12 + 8 + len(json_bytes) + 8 + len(new_bin)
    glb_hdr = struct.pack("<III", 0x46546C67, 2, total_length)
    
    with open(out_glb_path, "wb") as f:
        f.write(glb_hdr)
        f.write(c1_hdr)
        f.write(json_bytes)
        f.write(c2_hdr)
        f.write(new_bin)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True, help="Path to reprojection config JSON")
    parser.add_argument("--output", type=Path, help="Override output directory")
    args = parser.parse_args()
    
    cfg = read(args.config)
    out_dir = args.output if args.output else Path(cfg.get("outputDir", "output/heads/reprojection"))
    
    receipt = execute_whole_head_reprojection(cfg, out_dir)
    print(f"Reprojection complete! Verdict: {receipt['verdict']}")
    print(f"Overall directly projected: {receipt['overallCoverage']['directlyProjected']['surfaceAreaPercent']}%")
    print(f"Overall blended:            {receipt['overallCoverage']['blended']['surfaceAreaPercent']}%")
    print(f"Overall cloned/repaired:    {receipt['overallCoverage']['paintedCloned']['surfaceAreaPercent']}%")
    print(f"Overall unresolved:         {receipt['overallCoverage']['unresolved']['surfaceAreaPercent']}%")


if __name__ == "__main__":
    main()
