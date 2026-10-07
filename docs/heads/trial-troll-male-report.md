# Trial Report: Troll Male (`troll-male-01`)

## Summary

- **Trial ID:** `troll-male-01`
- **Race / Sex:** Troll Male
- **Donor Source:** `D:\source\repos\SRN_HAKS\output\heads\pilot-v1\meshy\source-bank\troll-neckless-retexture-derived-collect-v1\model.glb`
- **Donor SHA-256:** `a937078310c8f152d1264c7ff592036ba1e05d048479e0a2d21a2245b0a34079`
- **Donor Triangles:** 18,984
- **Cleaned Triangles:** 18,984
- **Runtime Triangles:** 18,998 (within $\le 20,000$ NWN engine limit)
- **Approved Body Target:** `docs/heads/troll-male-target.json` (Contract SHA-256: `331380741b4235de6758f3235a3359444fbc154b2b58b53d8b5894430c28d5c9`)
- **Status:** All Applicable Offline Gates Passed: Cleanup, Retopology, Fitting, Standing Assembly, Worst-Case Motion, Native Compile & Decode Audit.

---

## Racial Features & Accessory Geometry

1. **Prominent Facial Anatomy:**
   - Exaggerated heavy brow ridge and supraorbital tori preserved with anatomical edge flow.
   - Deep ear structure and auricular margin loop protection enforced.
   - Broad mandibular arch and chin contour maintained without flattening or distortion.
2. **Tusks & Horns:**
   - Lower jaw tusk geometry preserved with distinct surface boundary transitions.
   - Cranial horns on posterolateral scalp retained without decimation collapse or silhouette degradation.
3. **Closure & Capping:**
   - Watertight boundary verification; zero boundary edge cracks.
   - No neck taper, jaw trimming, or extending neck applied.

---

## Fitting & Envelope Verification

- **Landmark Tolerance:** $0.035$ m approved in target contract.
- **Measured Maximum Error:** $0.03246$ m ($\le 0.035$ m tolerance).
- **Uniform Scale:** $0.129923$ (positive uniform scale).
- **Transformation Matrix:** Proper rigid rotation with determinant $+1.0$; zero reflection or shear.
- **Cranial Envelope Validation:**
  - Approved Envelope: $[[-0.170, -0.170, -0.085], [0.170, 0.200, 0.250]]$
  - Fitted Model Bounds: $[[-0.12326, -0.10717, -0.08388], [0.11994, 0.14918, 0.17663]]$
  - Clearance Margin: Intact tusks, horns, and jaw fit strictly inside the approved envelope with positive margin in all dimensions ($1.12$ mm clearance at lowest jaw/neck coordinate).

---

## Standing Assembly & Motion Review

- Evaluated standing assembly against derived troll body contract (`derived-bank/troll-male/body.json`, revision `27a401ec8455fb71f226b75cd498140d1cea15cefe052902ffb28ede31243b99`).
- Verified neck interface closure against stock neck reference without clipping into torso geometry.
- Evaluated animation families across the preserved animation chain (`a_ba*.mdl`).
- Measured maximum motion displacement; prominent horns and tusks maintain proper spatial relationships without self-intersection or body collision.

---

## Native Compilation & Decode Audit

- **Assigned Slot:** Slot 14 (`pmg0_head014`).
- **Native Compiler:** Installed NWN:EE engine compiler (`nwmain.exe -compilemodel`).
- **Binary MDL Model:** `output/heads/trials/troll-male-01/native/resources/pmg0_head014.mdl` ($1,486,888$ bytes).
- **Decoded Audit Findings (`audit_native_head.py`):**
  - Total Decoded Triangles: $18,998$ (palette group: $16,983$, fixed eyes: $2,015$).
  - Maximum Attribute Error: $2.98 \times 10^{-8}$ (limit $2.0 \times 10^{-6}$).
  - Normal Vectors: Unit lengths verified within $0.002$ tolerance.
  - Tangent Vectors: Unit lengths verified in $[0.999, 1.001]$ (limit $[0.9, 1.1]$).
  - Tangent/Normal Orthogonality: Maximum dot product $< 0.001$ (limit $< 0.02$).
  - Materials & MTRs: `NormalTangents` renderhint, `Roughness 0`, explicit texture channels verified.
  - PLT Palettes: Byte masks verified against reference palette rows.
  - Overall Native Audit Status: **PASSED**.

---

## Retained Evidence & Artifacts

- **Geometry Audit Receipt:** `output/heads/trials/troll-male-01/audit/geometry-audit.json`
- **Classification Receipt:** `output/heads/trials/troll-male-01/components/components.json`
- **Cleaned Donor Source:** `output/heads/trials/troll-male-01/cleanup/cleaned_donor.blend` & `cleaned_donor.glb`
- **Runtime Source:** `output/heads/trials/troll-male-01/retopology/runtime.blend` & `runtime.glb`
- **Fitting Receipt:** `output/heads/trials/troll-male-01/fitting/fit.json`
- **Closure Proof:** `output/heads/trials/troll-male-01/fitting/closure.json`
- **Review Suite:**
  - Front view: `output/heads/trials/troll-male-01/review/front.png`
  - Left side: `output/heads/trials/troll-male-01/review/left.png`
  - Right side: `output/heads/trials/troll-male-01/review/right.png`
  - Back view: `output/heads/trials/troll-male-01/review/back.png`
  - Corrected jaw underside: `output/heads/trials/troll-male-01/review/jaw-bottom.png`
  - Facial close-up: `output/heads/trials/troll-male-01/review/facial-closeup.png`
  - Wireframe overlay: `output/heads/trials/troll-male-01/review/wireframe.png`
  - Coronal slice: `output/heads/trials/troll-male-01/review/section-coronal.png`
  - Sagittal slice: `output/heads/trials/troll-male-01/review/section-sagittal.png`
- **Native Export:** `output/heads/trials/troll-male-01/native/export.json`
- **Native Compilation Receipt:** `output/heads/trials/troll-male-01/native/native-compile.json`
- **Native Audit Receipt:** `output/heads/trials/troll-male-01/native/native-audit.json`
- **Trial Summary:** `output/heads/trials/troll-male-01/trial_summary.json`
