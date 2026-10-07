# Pilot Report: Human Female Texture Reprojection (`human-female-01`)

## Summary

- **Trial ID:** `human-female-01`
- **Race / Sex:** Human Female
- **Subject:** Adult human female head with long hair exclusively at the back
- **Mesh Source:** `output/heads/trials/human-female-01/cleanup/cleaned_donor.glb`
- **Mesh SHA-256:** `793b533c972c3ec6d975b30ba3d59668c18a1b06c7b0c11c3755902468042a4b`
- **Mesh Triangles:** 98,504
- **Donor 2K Base Color:** `output/heads/trials/human-female-01/cleanup/donor_base_color_2k.png`
- **Donor Texture SHA-256:** `f4522b9093c3fc7ffc9bde96b6eb9312068a918f4ea96bfb98ebae4539ada64c`
- **Repaired Atlas 2K:** `output/heads/trials/human-female-01/reprojection/repaired_atlas_2k.png`
- **Repaired Atlas SHA-256:** `e1625bbd2c0b5d460ef5229c1b13bab6c36f591977e663961bcd4455e2dee229`
- **Status:** **All Texture Reprojection & Quality Review Gates Passed**

---

## Pinned Reference Turnaround Panels

The four orthographic reference panels were extracted from the donor's generative turnaround condition:

| View | Relative Path | Resolution | SHA-256 | Camera Pose & Alignment |
|---|---|---|---|---|
| **Front** | `output/heads/trials/human-female-01/references/front.png` | $1024 \times 1024$ | `c9ea329df1f3eb81b985c8005bda8dd9362b2ac6b3b1864c6ef79d869178b8b3` | Center: `[0.0, -0.0029, -0.0013]`, Span: $1.080$ m |
| **Left** | `output/heads/trials/human-female-01/references/left.png` | $1024 \times 1024$ | `1e209c0c524c68bf7b6f7f3c91ed264dba77f3e5053f16c7064b82618e34e5e2` | Center: `[0.0, -0.0029, -0.0013]`, Span: $1.080$ m |
| **Back** | `output/heads/trials/human-female-01/references/back.png` | $1024 \times 1024$ | `d00d0b271529243c321e4b4135e7e73c52aa225677e0815188734b781302d3dd` | Center: `[0.0, -0.0029, -0.0013]`, Span: $1.080$ m |
| **Right** | `output/heads/trials/human-female-01/references/right.png` | $1024 \times 1024$ | `9070735ce3231803f5a0c1525a3026808e1c912660c0c8aa0c966bcb7d4b10cf` | Center: `[0.0, -0.0029, -0.0013]`, Span: $1.080$ m |

---

## Detailed Coverage & Surface Area Metrics

Physical surface area accounting is computed directly from 3D triangle areas apportioned to rasterized UV texels:

### Overall Mesh Coverage

| Category | Texel Count | Texel Share | 3D Surface Area ($m^2$) | Area Share (%) | Criteria / Action |
|---|---|---|---|---|---|
| **Directly Projected** | 1,630,648 | 69.41% | 2.6897 $m^2$ | **70.14%** | Single dominant view ($\ge 80\%$ confidence), normal angle $\cos \theta > 0.15$ |
| **Blended** | 349,161 | 14.86% | 0.5593 $m^2$ | **14.59%** | Smooth transition across cheeks, temples, and cranial margins |
| **Painted / Cloned** | 369,396 | 15.72% | 0.5685 $m^2$ | **14.82%** | Uncovered surfaces (jaw cap, crown, mastoid, inner hair) repaired from references |
| **Unresolved** | **0** | **0.00%** | **0.0000 $m^2$** | **0.00%** | Zero exposed defective donor fallback regions |
| **Total Mapped Surface** | **2,349,205** | **100.00%** | **3.8347 $m^2$** | **100.00%** | Complete watertight texture coverage |

---

### Component Breakdown

#### 1. Skin (`totalTexels: 527,957`, `totalArea: 0.8069 m²`, 21.04% of head)
- **Directly Projected:** $0.5800\text{ m}^2$ (**71.89%** of skin) — Front view dominates central face, orbital rings, lips, chin; Side views dominate lateral cheeks and auricles.
- **Blended:** $0.1608\text{ m}^2$ (**19.93%** of skin) — Smooth cosine-weighted transitions across zygomatic arch and mandibular angles.
- **Painted / Cloned:** $0.0661\text{ m}^2$ (**8.19%** of skin) — Subdued neighboring chin skin across the mandibular/neck closure plane and mastoid recesses behind the ear.
- **Unresolved:** **$0.0000\text{ m}^2$ (0.00%)**.

#### 2. Hair (`totalTexels: 1,723,622`, `totalArea: 2.8604 m²`, 74.59% of head)
- **Directly Projected:** $2.0253\text{ m}^2$ (**70.81%** of hair) — Back view dominates the long posterior curtain; Side views dominate temple strands and lateral waves.
- **Blended:** $0.3576\text{ m}^2$ (**12.50%** of hair) — Smooth interpolation between posterolateral locks and side hair.
- **Painted / Cloned:** $0.4775\text{ m}^2$ (**16.69%** of hair) — Sagittal crest hair cloned across the cranial apex and deep internal recesses.
- **Unresolved:** **$0.0000\text{ m}^2$ (0.00%)**.

#### 3. Eyes (`totalTexels: 97,626`, `totalArea: 0.1503 m²`, 3.92% of head)
- **Directly Projected:** $0.0844\text{ m}^2$ (**56.13%** of ocular area) — Front view provides sharp iris and pupil detail.
- **Blended:** $0.0410\text{ m}^2$ (**27.27%** of ocular area) — Peripheral sclera transition.
- **Painted / Cloned:** $0.0249\text{ m}^2$ (**16.60%** of ocular area) — Deep internal eyeball socket margin.
- **Unresolved:** **$0.0000\text{ m}^2$ (0.00%)**.

---

## Quality Gate Evaluations

1. **Facial Features:** **PASSED**. Single-view Front priority ($12\times$ weight) enforces crisp eyelid boundaries, defined lips, distinct nostril shadows, and clear eyebrows without doubling or ghosting.
2. **Skin-to-Scalp Transitions:** **PASSED**. Forehead and temple margins blend naturally into hair fibers without background contamination.
3. **Sharp Hair Detail:** **PASSED**. Authentic hair strands, waves, and baked specular highlights preserved directly from reference panels.
4. **Hair Flow Direction:** **PASSED**. Sagittal crest hair flows seamlessly from forehead over crown and merges into the rear hair curtain.
5. **No Projection Seams:** **PASSED**. Cosine-weighted angle blending eliminates harsh boundary edges between views.
6. **No Background Contamination:** **PASSED**. Bounding silhouette masks prevented black studio backgrounds from entering the atlas.
7. **No Exposed Defective Fallback Patches:** **PASSED**. All $369,396$ grazing/unprojected texels were cleanly repaired, achieving $0.0000\text{ m}^2$ unresolved area.
8. **Jaw Underside Closure:** **PASSED**. The bottom jaw cap was shaded with smooth, subdued neighboring skin tones compatible with NWN:EE neck connectors.
9. **Crown Coverage:** **PASSED**. Top-down $+80^\circ$ view confirms full hair coverage without bald spots or stretching.

---

## Runtime 1024 Material Conversion & Palette Calibration

- **Conversion Tool:** [`tools/heads/export_runtime_reprojected_materials.py`](file:///d:/srwt/codex/head-quality-pipeline/SRN_HAKS/tools/heads/export_runtime_reprojected_materials.py) via [`prepare_materials.py`](file:///d:/srwt/codex/head-quality-pipeline/SRN_HAKS/tools/heads/prepare_materials.py).
- **Runtime Textures:** Exported under `output/heads/trials/human-female-01/reprojection/materials/runtime_1024/`:
  - `color.png` ($1024 \times 1024$)
  - `normal.png` ($1024 \times 1024$, renormalized tangent normals)
  - `roughness.png` ($1024 \times 1024$)
  - `shades.png` ($1024 \times 1024$, PLT 8-bit shade indices)
  - `layers.png` ($1024 \times 1024$, PLT layer indices: 0 skin, 1 hair)
  - `semantic.png` ($1024 \times 1024$, 0 skin, 1 hair, 2 fixed eyes)
- **Palette Row Calibration:**
  - Skin: **Row 7** (natural light tan)
  - Hair: **Row 65** (dark brown)
- **Multi-Variant Palette Recoloring Test:**
  Verified across 4 character configurations in `palette_recoloring_sheet.png`:
  1. *Calibrated Natural:* Skin Row 7, Hair Row 65
  2. *Pale Blonde:* Skin Row 0, Hair Row 4
  3. *Dark Black:* Skin Row 15, Hair Row 72
  4. *Fair Red:* Skin Row 4, Hair Row 28
  All configurations maintain facial depth, lip contrast, eye socket definition, and hair highlights.

---

## Retained Artifacts & Verification Proofs

- **Configuration:** [`docs/heads/reprojection-human-female-config.json`](file:///d:/srwt/codex/head-quality-pipeline/SRN_HAKS/docs/heads/reprojection-human-female-config.json)
- **Reprojection Receipt:** `output/heads/trials/human-female-01/reprojection/reprojection_receipt.json`
- **Repaired Atlas 2K:** `output/heads/trials/human-female-01/reprojection/repaired_atlas_2k.png`
- **Textured Preview GLB:** `output/heads/trials/human-female-01/reprojection/textured_preview.glb`
- **Coverage Map:** `output/heads/trials/human-female-01/reprojection/coverage_type_map.png`
- **Confidence Map:** `output/heads/trials/human-female-01/reprojection/confidence_map.png`
- **Comparison Sheet:** `output/heads/trials/human-female-01/reprojection/comparison_sheet.png`
- **Review Suite:**
  - 10 Lit views: `output/heads/trials/human-female-01/reprojection/review/{front,left,right,back,three_quarter_left,three_quarter_right,crown,jaw_underside,facial_closeup,inner_hair_closeup}.png`
  - 10 Color-only views: `output/heads/trials/human-female-01/reprojection/review/color_only_*.png`
  - Combined review sheet: `output/heads/trials/human-female-01/reprojection/review/reprojection_review_sheet.png`
  - Review receipt: `output/heads/trials/human-female-01/reprojection/review/review_receipt.json`
- **Runtime Materials Receipt:** `output/heads/trials/human-female-01/reprojection/materials/materials_export_receipt.json`
- **Palette Recoloring Sheet:** `output/heads/trials/human-female-01/reprojection/materials/palette_recoloring_sheet.png`
