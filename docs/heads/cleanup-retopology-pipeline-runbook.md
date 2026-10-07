# Repeatable Head Cleanup, Retopology, and Texture Pipeline Runbook

## Overview

This runbook documents the dedicated textured-donor cleanup, deliberate facial retopology, texture baking, and validation pipeline implemented under `tools/heads/`.

The pipeline enforces Neverwinter Nights' strict engine constraints:
- Combined maximum polygon budget: **$\le$ 20,000 triangles**
- Strict UV coordinate space: **$[0.0, 1.0]$ non-wrapping** atlas
- Zero neck taper, jaw trimming, or extending neck
- Preservation of racial features, eye openings, eyeballs, and hair silhouettes
- Tangent-space normal map rebaking with 4-thread CPU Cycles limit
- SHA-256 tracking of all inputs and helpers for stale-input invalidation and deterministic resume

---

## Architecture & Tools

The pipeline is structured into independent, auditable stages coordinated by `tools/heads/pipeline_textured_donor.py`:

```
Raw Donor GLB
     │
     ▼
[Stage 1: Geometry & Section Audit] (audit_donor_geometry.py)
     │  - Evaluates components, non-manifold edges, open boundaries, intersections
     │  - Evaluates sampled exterior ray visibility (26 directions + normal pairs)
     │  - Identifies enclosed shells, recessed surfaces, and eyeball candidates
     │
     ▼
[Stage 2: Component Classification & Budgeting] (classify_head_components.py)
     │  - Assigns skin, hair, eyes, and accessories
     │  - Flags boundary transition regions (eyebrows, hairline, eyelid margins)
     │  - Allocates budgets: 11K face/skull, 8K hair, 1K reserve (ceiling <= 20,000)
     │
     ▼
[Stage 3: Donor Repair & Cleanup] (cleanup_textured_donor.py)
     │  - Welds coincident vertices within 1e-7 without cracking UV seams
     │  - Removes duplicate and degenerate faces
     │  - Repairs occluding eyelid geometry over ocular openings
     │  - Removes genuinely enclosed redundant shells while strictly preserving eyeballs
     │  - Saves versioned cleaned Blender source (.blend) and cleaned donor GLB
     │
     ▼
[Stage 4: Retopology, Hair Reduction & Normal Baking] (retopologize_textured_donor.py)
     │  - Local boundary hole capping (no taper, no jaw trimming)
     │  - Sets up anatomical vertex-group protection around eyelids, lips, nostrils, ears, jaw
     │  - Simplifies hair independently, preserving silhouette, hairline, waves, and tips
     │  - Enforces combined triangle ceiling <= 20,000
     │  - Clamps UVs strictly to [0.0, 1.0] non-wrapping box
     │  - Bakes tangent-space normal map using Cycles at 4 threads (selected-to-active)
     │  - Restores materials and exports versioned runtime .blend and runtime GLB
     │
     ▼
[Stage 5: Multi-View Review & Section Renderings] (render_head_trial_review.py)
     │  - Renders front, left profile, right profile, back views
     │  - Renders correctly oriented jaw-bottom view (pitch -80 deg looking up from below)
     │  - Renders facial close-ups, wireframe overlay, coronal and sagittal section slices
     │  - Evaluates facial shape, eye openings, jaw integrity, hair silhouette, texture quality
     │
     ▼
[Stage 6: Fitting, Assembly & Native Validation] (fit_head.py, audit_native_head.py)
        - Fits landmarks to approved target contract (uniform scale, proper rotation)
        - Samples standing assembly and measured worst-case motion
        - Compiles via installed NWN native compiler (`nwmain.exe -compilemodel`)
        - Decodes binary MDL and validates attribute errors (< 2e-6), unit normals, tangents, MTR, PLT
```

---

## Budget Allocations & Quality Rules

1. **Polygon Ceilings:**
   - **Face / Skull / Ears / Eyes:** 11,000 triangles default target.
   - **Hair:** 8,000 triangles default target (simplified interior first).
   - **Reserve:** 1,000 triangles.
   - **Combined Ceiling:** Maximum 20,000 triangles across all primitives.

2. **Geometry Integrity:**
   - Coincident vertices welded within $10^{-7}$ distance only when attached loops share UV coordinates.
   - Hole capping must be local and boundary-aligned; no neck taper, jaw trimming, or neck elongation may be introduced.
   - Eyelid margins must cleanly frame ocular openings; internal eyeball spheres must be preserved.
   - Exterior visibility: hidden triangles are review candidates, never automatic deletion instructions.

3. **Texture & Normal Map Transport:**
   - 2K donor textures preserved; 1024-square runtime maps exported.
   - Normal maps baked with CPU Cycles (`threads = 4`), cage extrusion $0.03$, max ray distance $0.08$.
   - UV coordinates strictly clamped to $[0.0, 1.0]$ to satisfy NWN engine requirements.
   - Material transport checked: `renderhint NormalTangents`, `parameter float Roughness 0`, tangent unit lengths $\in [0.9, 1.1]$, tangent/normal orthogonality $< 0.02$.

---

## Step-by-Step Execution Guide

### 1. Running the End-to-End Pipeline

```powershell
python tools/heads/pipeline_textured_donor.py `
  --trial-id <trial-id> `
  --donor <path-to-donor.glb> `
  --output output/heads/trials/<trial-id> `
  --reference <path-to-reference-sheet.png> `
  --body-contract <path-to-target-contract.json> `
  --face-budget 11000 `
  --hair-budget 8000 `
  --reserve 1000
```

### 2. Standalone Stage Execution

#### Geometry Audit
```powershell
python tools/heads/audit_donor_geometry.py `
  --source <donor.glb> `
  --output output/heads/trials/<trial-id>/audit/geometry-audit.json
```

#### Component Classification
```powershell
python tools/heads/classify_head_components.py `
  --source <donor.glb> `
  --output output/heads/trials/<trial-id>/components/components.json `
  --face-budget 11000 `
  --hair-budget 8000 `
  --reserve 1000
```

#### Blender Donor Cleanup
```powershell
& "E:\Program Files\Blender Foundation\Blender 4.0\blender.exe" `
  --factory-startup -b -t 4 `
  --python tools/heads/cleanup_textured_donor.py -- `
  --source <donor.glb> `
  --output output/heads/trials/<trial-id>/cleanup `
  --audit output/heads/trials/<trial-id>/audit/geometry-audit.json `
  --components output/heads/trials/<trial-id>/components/components.json
```

#### Blender Retopology and Normal Baking
```powershell
& "E:\Program Files\Blender Foundation\Blender 4.0\blender.exe" `
  --factory-startup -b -t 4 `
  --python tools/heads/retopologize_textured_donor.py -- `
  --source output/heads/trials/<trial-id>/cleanup/cleaned_donor.glb `
  --output output/heads/trials/<trial-id>/retopology `
  --components output/heads/trials/<trial-id>/components/components.json `
  --face-budget 11000 `
  --hair-budget 8000 `
  --reserve 1000
```

#### Multi-View Review Rendering
```powershell
& "E:\Program Files\Blender Foundation\Blender 4.0\blender.exe" `
  --factory-startup -b -t 4 `
  --python tools/heads/render_head_trial_review.py -- `
  --target output/heads/trials/<trial-id>/retopology/runtime.glb `
  --donor output/heads/trials/<trial-id>/cleanup/cleaned_donor.glb `
  --output output/heads/trials/<trial-id>/review `
  --trial-name <trial-id>
```

---

## Review Gates & Acceptance Criteria

| Gate | Verification Check | Passing Condition |
|---|---|---|
| **Donor Geometry** | `audit_donor_geometry.py` | Enclosed shells identified; eyeballs and recessed sockets preserved; non-manifold edges reported. |
| **Budget Enforcement** | `retopologize_textured_donor.py` | Total runtime triangle count $\le 20,000$. Loop protection preserved on facial rings. |
| **UV Atlas & Non-Wrapping** | `clamp_uvs_to_unit_box` | All UV coordinates strictly in $[0.0, 1.0]$. Seams preserved during weld. |
| **Normal Map Quality** | Cycles bake | Tangent-space normal map cleanly baked at $2048 \times 2048$, no projection contamination. |
| **Review Orientation** | `render_head_trial_review.py` | Jaw-bottom view pitch set to $-80^\circ$ looking up at jaw (not crown view). |
| **Fitting** | `fit_head.py` | Positive uniform scale, proper rigid rotation, maximum landmark error $\le$ tolerance. |
| **Native Validation** | `audit_native_head.py` | Complete compilation, decoded attributes match within $2 \times 10^{-6}$, unit tangents $\in [0.9, 1.1]$, orthogonality $< 0.02$. |

---

## Resume & Invalidation Protocol

- Every stage verifies upstream source hashes (`sha256`) against frozen pins.
- If upstream geometry or inputs change, downstream stages automatically invalidate their receipts and re-execute.
- If upstream inputs are unchanged, the pipeline resumes instantly from existing stage receipts without redundant computation.
- Large assets, `.blend` master sources, and runtime binaries remain in `output/` and `.tmp/` (ignored by git).
