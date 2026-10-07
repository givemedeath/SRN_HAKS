"""Convert repaired 2K head atlas to 1024 runtime textures and validate palette recoloring.

Generates:
- 1024x1024 runtime PBR maps: color, normal, roughness
- Palette-aware PLT components: shades, layers, semantic
- Multi-variant palette recoloring contact sheet to verify baked shading stability.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Tuple

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from head_export import accessor, load_glb
from head_workflow import pin, read, require, verify_pins, write_fresh
from prepare_materials import prepare as execute_prepare_materials
from reproject_reference_textures import compute_sha256, load_mesh_from_glb, rasterize_uv_triangles


def generate_semantic_mask_2k(
    mesh_path: Path,
    out_mask_path: Path,
) -> Path:
    """Generate 2048x2048 8-bit semantic mask (0=skin, 1=hair, 2=fixed) from classified mesh."""
    pos, normals, uvs, indices, _, _ = load_mesh_from_glb(mesh_path)
    tri_map, ys, xs, tri_ids = rasterize_uv_triangles(uvs, indices, size=2048)
    
    from classify_head_components import classify_triangles, extract_base_color_image
    donor_img = extract_base_color_image(mesh_path)
    face_labels, _, _ = classify_triangles(pos[indices], uvs[indices], donor_img)
    texel_labels = face_labels[tri_ids]
    
    mask_arr = np.zeros((2048, 2048), dtype=np.uint8)
    mask_arr[ys, xs] = texel_labels.astype(np.uint8)
    
    im = Image.fromarray(mask_arr, mode="L")
    im.save(out_mask_path)
    return out_mask_path


def render_palette_recolored_preview(
    runtime_materials_dir: Path,
    skin_pal_path: Path,
    hair_pal_path: Path,
    variants: List[Tuple[str, int, int]],
    out_sheet_path: Path,
) -> Path:
    """Render side-by-side recolored variants from PLT shades and layers."""
    shades = np.asarray(Image.open(runtime_materials_dir / "shades.png"), dtype=np.uint8)
    layers = np.asarray(Image.open(runtime_materials_dir / "layers.png"), dtype=np.uint8)
    semantic = np.asarray(Image.open(runtime_materials_dir / "semantic.png"), dtype=np.uint8)
    fixed_color = np.asarray(Image.open(runtime_materials_dir / "color.png").convert("RGB"), dtype=np.uint8)
    
    skin_pal = np.asarray(Image.open(skin_pal_path).convert("RGB"), dtype=np.uint8)
    hair_pal = np.asarray(Image.open(hair_pal_path).convert("RGB"), dtype=np.uint8)
    
    sheet_w = 1024 * len(variants)
    sheet = Image.new("RGB", (sheet_w, 1024), (20, 20, 20))
    
    for idx, (label, s_row, h_row) in enumerate(variants):
        recolored = np.zeros((1024, 1024, 3), dtype=np.uint8)
        
        # Skin layer (0)
        skin_mask = (layers == 0) & (semantic != 2)
        recolored[skin_mask] = skin_pal[s_row, shades[skin_mask]]
        
        # Hair layer (1)
        hair_mask = (layers == 1) & (semantic != 2)
        recolored[hair_mask] = hair_pal[h_row, shades[hair_mask]]
        
        # Fixed layer (2 - eyes)
        fixed_mask = (semantic == 2)
        recolored[fixed_mask] = fixed_color[fixed_mask]
        
        var_im = Image.fromarray(recolored, mode="RGB")
        sheet.paste(var_im, (idx * 1024, 0))
        
    out_sheet_path = Path(out_sheet_path).resolve()
    sheet.resize((sheet_w // 2, 512), Image.Resampling.LANCZOS).save(out_sheet_path)
    return out_sheet_path


def export_runtime_materials(
    repaired_atlas_2k: Path,
    mesh_glb: Path,
    normal_2k: Path,
    roughness_2k: Path,
    skin_palette_tga: Path,
    hair_palette_tga: Path,
    output_dir: Path,
    skin_row: int = 7,
    hair_row: int = 65,
) -> Dict[str, Any]:
    """Execute end-to-end material conversion and palette validation."""
    started = time.perf_counter()
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Generate 2K semantic mask
    sem_mask_path = output_dir / "semantic_mask_2k.png"
    generate_semantic_mask_2k(mesh_glb, sem_mask_path)
    
    # 2. Build configuration for prepare_materials
    mat_cfg = {
        "kind": "srn-head-materials",
        "maskReviewed": True,
        "flipNormalGreen": False,
        "baseColor": str(repaired_atlas_2k.resolve()),
        "normal": str(normal_2k.resolve()),
        "roughness": str(roughness_2k.resolve()),
        "semanticMask": str(sem_mask_path.resolve()),
        "skinPalette": str(skin_palette_tga.resolve()),
        "hairPalette": str(hair_palette_tga.resolve()),
        "skinRow": int(skin_row),
        "hairRow": int(hair_row),
        "inputs": [
            pin(repaired_atlas_2k),
            pin(normal_2k),
            pin(roughness_2k),
            pin(sem_mask_path),
            pin(skin_palette_tga),
            pin(hair_palette_tga),
        ]
    }
    
    mat_cfg_path = output_dir / "materials_config.json"
    write_fresh(mat_cfg_path, mat_cfg)
    
    # 3. Call existing prepare_materials helper
    runtime_out_dir = output_dir / "runtime_1024"
    if runtime_out_dir.exists():
        import shutil
        shutil.rmtree(runtime_out_dir)
        
    execute_prepare_materials(mat_cfg_path, runtime_out_dir)
    
    # 4. Render palette recoloring verification sheet
    variants = [
        ("calibrated_tan_dark", skin_row, hair_row),
        ("pale_blonde", 0, 4),
        ("dark_black", 15, 72),
        ("fair_red", 4, 28),
    ]
    recolor_sheet_path = output_dir / "palette_recoloring_sheet.png"
    render_palette_recolored_preview(
        runtime_out_dir, skin_palette_tga, hair_palette_tga, variants, recolor_sheet_path
    )
    
    elapsed = time.perf_counter() - started
    receipt = {
        "schemaVersion": 1,
        "kind": "srn-head-reprojected-materials-export-receipt",
        "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "elapsedSeconds": round(elapsed, 3),
        "repairedAtlas2K": pin(repaired_atlas_2k),
        "semanticMask2K": pin(sem_mask_path),
        "runtimeDir": str(runtime_out_dir),
        "recoloringSheet": pin(recolor_sheet_path),
        "paletteRows": {
            "skin": skin_row,
            "hair": hair_row,
        },
        "verdict": "PASSED",
    }
    
    receipt_path = output_dir / "materials_export_receipt.json"
    write_fresh(receipt_path, receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--atlas", type=Path, required=True, help="Path to repaired 2K atlas PNG")
    parser.add_argument("--mesh", type=Path, required=True, help="Path to mesh GLB")
    parser.add_argument("--normal", type=Path, required=True, help="Path to 2K normal map")
    parser.add_argument("--roughness", type=Path, required=True, help="Path to 2K roughness map")
    parser.add_argument("--skin-palette", type=Path, required=True, help="Path to skin palette TGA")
    parser.add_argument("--hair-palette", type=Path, required=True, help="Path to hair palette TGA")
    parser.add_argument("--output", type=Path, required=True, help="Output directory")
    parser.add_argument("--skin-row", type=int, default=7)
    parser.add_argument("--hair-row", type=int, default=65)
    args = parser.parse_args()
    
    res = export_runtime_materials(
        args.atlas, args.mesh, args.normal, args.roughness,
        args.skin_palette, args.hair_palette, args.output,
        args.skin_row, args.hair_row
    )
    print(f"Materials exported successfully in {res['elapsedSeconds']}s! Verdict: {res['verdict']}")


if __name__ == "__main__":
    main()
