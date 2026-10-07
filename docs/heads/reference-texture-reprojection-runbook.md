# Reference Texture Reprojection Pipeline Runbook

## Overview

This runbook documents the configuration-driven whole-head reference texture reprojection and gap repair pipeline implemented under `tools/heads/`.

The pipeline replaces defective generated donor colors by projecting authentic front, left, back, and right turnaround references onto the 3D head mesh while preserving the references' baked lighting and highlights for NWN:EE.

### Core Principles
- **True Orthographic Projection:** Aligns four orthogonal cameras ($0^\circ, 90^\circ, 180^\circ, 270^\circ$) to the 3D head cranium and hair silhouette.
- **Occlusion & Depth Buffering:** Employs a dilated camera-space depth buffer to reject occluded geometry (e.g. front face occluding rear skull, or hair locks occluding ears).
- **Grazing-Angle Attenuation:** Surfaces with normal angle $\cos \theta < 0.15$ are rejected to prevent extreme projection stretching.
- **Background Contamination Guard:** Reference background pixels (black / transparent) are strictly excluded from the atlas.
- **Feature Priority Zones:** Enforces single-view dominance around delicate features (eyes, lips, nostrils, eyebrows, ears) to completely prevent ghosting and feature doubling.
- **Targeted Gap Repair Layers:** Clones authentic skin/hair detail from the same references to cover unprojected surfaces (jaw cap, crown, behind ears, deep hair recesses).
- **Physical Surface Area Accounting:** Distinguishes directly projected, blended, painted/cloned, and unresolved texels, reporting coverage by surface area ($m^2$ and $\%$) and by anatomical component (skin, hair, eyes).
- **Zero Geometry/UV Modification:** Preserves 3D vertex coordinates, normals, and UV layouts bit-exact.

---

## Tooling & CLI Interfaces

### 1. Reprojection Engine (`reproject_reference_textures.py`)

```powershell
python tools/heads/reproject_reference_textures.py `
  --config docs/heads/reprojection-human-female-config.json `
  --output output/heads/trials/human-female-01/reprojection
```

#### Inputs
- `mesh`: Pinned GLB mesh with positions, normals, and UV coordinates.
- `donorTexture`: Pinned 2K donor base color image (used for fallback and comparison).
- `views`: Pinned reference image paths, SHA-256 hashes, and camera calibration parameters (`center`, `orthoSpan`, `offsets`).
- `componentClassification`: Pinned component JSON or mask file defining skin, hair, and eye triangles.
- `repairLayers`: Declarative repair rules for jaw cap, crown, mastoid, and inner hair.
- `blendSettings`: Dominance threshold ($0.80$), grazing limit ($0.15$), depth tolerance ($0.035$ m), and priority weights.

#### Outputs
- `repaired_atlas_2k.png`: Repaired 2048x2048 RGB color atlas.
- `textured_preview.glb`: Versioned inspection GLB with the repaired 2K atlas embedded.
- `contribution_{front,left,back,right}.png`: 2K per-view blend contribution weight maps.
- `confidence_map.png`: 2K grayscale projection confidence map.
- `coverage_type_map.png`: 2K color-coded map (Green = Direct, Blue = Blended, Amber = Cloned, Red = Unresolved).
- `comparison_sheet.png`: Side-by-side comparison between donor texture, repaired atlas, and coverage classification.
- `reprojection_receipt.json`: Provenance record with hashes, metrics, and gate results.

---

### 2. Multi-View Review Renderer (`render_reprojection_review.py`)

```powershell
python tools/heads/render_reprojection_review.py `
  --target output/heads/trials/human-female-01/reprojection/textured_preview.glb `
  --references output/heads/trials/human-female-01/references `
  --output output/heads/trials/human-female-01/reprojection/review
```

#### Inspection Suite
Renders 20 distinct frames using Blender Cycles at 4 threads (24 samples):
1. **Front** (pitch $0^\circ$, yaw $0^\circ$)
2. **Left Profile** (pitch $0^\circ$, yaw $90^\circ$, nose pointing left)
3. **Right Profile** (pitch $0^\circ$, yaw $-90^\circ$, nose pointing right)
4. **Back** (pitch $0^\circ$, yaw $180^\circ$)
5. **Three-Quarter Left** (pitch $0^\circ$, yaw $45^\circ$)
6. **Three-Quarter Right** (pitch $0^\circ$, yaw $-45^\circ$)
7. **Crown** (pitch $+80^\circ$, looking directly down at apex)
8. **Jaw Underside** (pitch $-80^\circ$, looking directly up at neck rim)
9. **Facial Close-up** (zoomed framing on orbital and oral anatomy)
10. **Inner Hair Close-up** (zoomed framing on rear occipital hair curtain)

Each view is rendered in two lighting modes:
- `lit`: Studio 3-point key/fill/rim lighting simulating NWN:EE in-game conditions.
- `color_only`: Emission shader mode showing pure unlit texture projection without lighting shadows.

Outputs:
- `reprojection_review_sheet.png`: 4x4 matrix comparison board.
- `review_receipt.json`: Machine-readable review gate evaluations.

---

### 3. Material Export & Palette Recoloring (`export_runtime_reprojected_materials.py`)

```powershell
python tools/heads/export_runtime_reprojected_materials.py `
  --atlas output/heads/trials/human-female-01/reprojection/repaired_atlas_2k.png `
  --mesh output/heads/trials/human-female-01/cleanup/cleaned_donor.glb `
  --normal output/heads/trials/human-female-01/cleanup/normal_2k.png `
  --roughness output/heads/trials/human-female-01/cleanup/roughness_2k.png `
  --skin-palette output/heads/palettes/pal_skin01.tga `
  --hair-palette output/heads/palettes/pal_hair01.tga `
  --output output/heads/trials/human-female-01/reprojection/materials `
  --skin-row 7 `
  --hair-row 65
```

#### Outputs
- `semantic_mask_2k.png`: 2K byte mask (0=skin, 1=hair, 2=fixed eyes).
- `runtime_1024/`: 1024-square runtime PBR and PLT assets:
  - `color.png`: Rescaled diffuse texture.
  - `normal.png`: Renormalized tangent-space normal map.
  - `roughness.png`: Rescaled roughness map.
  - `shades.png`: 8-bit PLT shade indices mapped to optimal palette row.
  - `layers.png`: 8-bit PLT layer index (0 skin, 1 hair).
  - `semantic.png`: 8-bit semantic mask.
- `palette_recoloring_sheet.png`: 4-variant contact sheet testing recoloring across baseline, pale blonde, dark black, and fair red palette rows.

---

## Review Gates & Acceptance Criteria

| Gate | Requirement | Verification Method |
|---|---|---|
| **Clean Facial Features** | No ghosting, blur, or feature doubling around eyes, lips, nostrils, and eyebrows. | Visual inspection of `facial_closeup.png` and `color_only_front.png`. Verified Front priority weight $= 12.0$. |
| **Skin-to-Scalp Transitions** | Natural transition from forehead to hairline and temple fibers. | Inspection of `three_quarter_left.png` and `three_quarter_right.png`. |
| **Sharp Hair Detail** | Preserves hair locks, waves, and directional highlights from references. | Inspection of `left.png`, `right.png`, and `back.png`. |
| **Consistent Hair Flow** | Crown hair flows smoothly into lateral waves and rear curtain. | Inspection of `crown.png` and `inner_hair_closeup.png`. |
| **Zero Projection Seams** | Smooth blending between adjacent views at cheeks and temples. | Inspection of `three_quarter_*.png` and `confidence_map.png`. |
| **Zero Background Contamination** | Black/transparent reference margins never enter UV atlas. | Verification of `ref_mask` gating and `coverage_type_map.png`. |
| **Zero Unresolved Visible Patches** | All exposed surfaces must be directly projected, blended, or cloned. | `unresolved` surface area must be exactly $0.0000\text{ m}^2$ ($0.0\%$). |
| **Palette Shading Stability** | Recoloring maintains facial contrast, depth, and hair highlights. | Inspection of `palette_recoloring_sheet.png`. |
