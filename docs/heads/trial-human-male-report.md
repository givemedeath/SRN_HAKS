# Trial Report: Human Male (`human-male-01`)

## Summary

- **Trial ID:** `human-male-01`
- **Race / Sex:** Human Male
- **Donor Source:** `D:\source\repos\SRN_HAKS\output\heads\pilot-v1\meshy\source-bank\human1-neckless-retexture-collect-v1\model.glb`
- **Donor SHA-256:** `9557bf8f0607da69b8aeaa2fe5c11099f4be672e87a2c68f18fa19e34676fe4f`
- **Donor Triangles:** 18,999
- **Cleaned Triangles:** 18,999
- **Runtime Triangles:** 19,000 (within $\le 20,000$ NWN engine limit)
- **Approved Body Target:** `docs/heads/human-male-target.json` (Contract SHA-256: `cf11650b2e793723b1e65199b54f7fc9daad452cb00d5a19f40c426926fc1793`)
- **Status:** All Offline Gates Passed: Cleanup, Retopology, Fitting, Standing Assembly, Worst-Case Motion, Native Compile & Decode Audit.

---

## Geometry, Hair & Beard Boundaries

1. **Short Hair & Beard:**
   - Evaluated component boundary suggestions on facial borders.
   - Distinct hair fibers, beard line transitions, and scalp coverage maintained within independent hair allocation.
   - Clean facial surface without hair texture projection bleed onto lips or cheeks.
2. **Anatomical Loops:**
   - Deliberate orbital rings, oral sphincter, nasolabial loops, and mandibular line protected during reduction.
   - Eyeballs in sockets preserved and correctly bounded by eyelids.
3. **Capping & Closure:**
   - Cap-only closure applied to neck rim; no neck taper, jaw trimming, or neck elongation.
   - Coincident vertices welded within $10^{-7}$ while strictly preserving UV seams.

---

## Fitting & Envelope Verification

- **Landmark Tolerance:** $0.025$ m approved in target contract.
- **Measured Maximum Error:** $0.02092$ m ($\le 0.025$ m tolerance).
- **Uniform Scale:** $0.123927$ (positive uniform scale).
- **Transformation Matrix:** Rigid proper rotation matrix with determinant $+1.0$; zero reflection or anisotropic stretch.
- **Cranial Envelope Validation:**
  - Approved Envelope: $[[-0.108, -0.130, -0.070], [0.108, 0.150, 0.205]]$
  - Fitted Model Bounds: $[[-0.10449, -0.10842, -0.06984], [0.09922, 0.13514, 0.18295]]$
  - Clearance Margin: All vertices strictly inside approved envelope boundaries with positive clearance ($0.16$ mm minimum margin at jaw cap).

---

## Standing Assembly & Measured Motion Review

- Evaluated standing assembly against protected stock neck (`pmh0_neck001.mdl`) and published body resources (`docs/phenotypes/human-male-assets.json`).
- Verified neck connector interface closure without clipping or visible gaps.
- Evaluated nine animation motion families: `idle`, `talk`, `walk`, `run`, `cast`, `combat`, `crouch`, `kneel`, `death`.
- Measured maximum displacement across animation chain; neck attachment remains stable without tearing or interpenetration.

---

## Native Compilation & Decode Audit

- **Assigned Slot:** Slot 82 (`pmh0_head082`) in `docs/heads/roster-allocated.json`.
- **Native Compiler:** Installed NWN:EE engine compiler (`nwmain.exe -compilemodel`).
- **Binary MDL Model:** `output/heads/trials/human-male-01/native/resources/pmh0_head082.mdl` ($1,486,900$ bytes).
- **Decoded Audit Findings (`audit_native_head.py`):**
  - Total Decoded Triangles: $19,000$ (palette group: $17,609$, fixed eye group: $1,391$).
  - Maximum Attribute Error: $2.98 \times 10^{-8}$ (limit $2.0 \times 10^{-6}$).
  - Normal Vectors: Unit length verified within $0.002$ tolerance.
  - Tangent Vectors: Unit lengths verified in $[0.999, 1.001]$ (limit $[0.9, 1.1]$).
  - Tangent/Normal Orthogonality: Maximum dot product $< 0.001$ (limit $< 0.02$).
  - Materials & MTRs: `NormalTangents` renderhint, `Roughness 0`, explicit texture channels verified.
  - PLT Palettes: 2-layer byte mask verified against reference skin/hair palette rows.
  - Overall Native Audit Status: **PASSED**.

---

## Retained Evidence & Artifacts

- **Geometry Audit Receipt:** `output/heads/trials/human-male-01/audit/geometry-audit.json`
- **Classification Receipt:** `output/heads/trials/human-male-01/components/components.json`
- **Cleaned Donor Source:** `output/heads/trials/human-male-01/cleanup/cleaned_donor.blend` & `cleaned_donor.glb`
- **Runtime Source:** `output/heads/trials/human-male-01/retopology/runtime.blend` & `runtime.glb`
- **Fitting Receipt:** `output/heads/trials/human-male-01/fitting/fit.json`
- **Closure Proof:** `output/heads/trials/human-male-01/fitting/closure.json`
- **Review Suite:**
  - Front view: `output/heads/trials/human-male-01/review/front.png`
  - Left side: `output/heads/trials/human-male-01/review/left.png`
  - Right side: `output/heads/trials/human-male-01/review/right.png`
  - Back view: `output/heads/trials/human-male-01/review/back.png`
  - Corrected jaw underside: `output/heads/trials/human-male-01/review/jaw-bottom.png`
  - Facial close-up: `output/heads/trials/human-male-01/review/facial-closeup.png`
  - Wireframe overlay: `output/heads/trials/human-male-01/review/wireframe.png`
  - Coronal slice: `output/heads/trials/human-male-01/review/section-coronal.png`
  - Sagittal slice: `output/heads/trials/human-male-01/review/section-sagittal.png`
- **Native Export:** `output/heads/trials/human-male-01/native/export.json`
- **Native Compilation Receipt:** `output/heads/trials/human-male-01/native/native-compile.json`
- **Native Audit Receipt:** `output/heads/trials/human-male-01/native/native-audit.json`
- **Trial Summary:** `output/heads/trials/human-male-01/trial_summary.json`
