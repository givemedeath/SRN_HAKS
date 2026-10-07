# Trial Report: Human Female (`human-female-01`)

## Summary

- **Trial ID:** `human-female-01`
- **Race / Sex:** Human Female
- **Donor Source:** `D:\source\repos\SRN_HAKS\output\heads\comfy-human-female-long-back-v5\artifacts\textured-head_00001.glb`
- **Donor SHA-256:** `6b337a935d371a3d018df1c5b8a805566d1d8bfd61b911be2711eb4f565be98c`
- **Donor Triangles:** 98,504
- **Cleaned Triangles:** 98,504
- **Runtime Triangles:** 18,999 (within $\le 20,000$ NWN engine limit)
- **Status:** Geometry and Material Review Passed; Fitting and Native Export Pending Female Body Contract

---

## Comparison with Historical Reductions (v1–v4)

| Metric / Check | Historical v1 (Rejected) | Historical v4 (Rejected) | New Pipeline (`human-female-01`) | Evaluation |
|---|---|---|---|---|
| **Triangle Count** | 18,998 | 18,982 | **18,999** | Strictly within 20,000 ceiling |
| **Open Boundary Edges** | 20,388 (unwelded seams) | 46 (rear hair boundary) | **0 on critical face** (349 total in deep hair) | Seams welded preserving UV integrity |
| **UV Bounds** | $[-0.0013, 1.0053]$ (wrapping) | $[-0.0007, 1.0001]$ (wrapping) | **$[0.0, 1.0]$ strictly non-wrapping** | Resolves exporter crash |
| **Facial Loop Protection** | None (uniform decimate) | None (collapsed eyelids/lips) | **Protected orbital, oral, nasal, mandibular loops** | Anatomic feature integrity preserved |
| **Hair Silhouette** | Flattened tips & waves | Distorted rear hairline | **Independent reduction preserving silhouette, waves, tips** | Outer shape preserved |
| **Bottom View Angle** | $+90^\circ$ (misoriented crown view) | $-90^\circ$ (separate review) | **$-80^\circ$ jaw-bottom looking up from below** | Standardized jaw underside inspection |
| **Normal Map** | Retained noisy donor bake | Unbasked on decimation | **Rebaked tangent normal map via Cycles (4 threads)** | Clean normal transport, no projection bleed |

---

## Review Gates & Findings

1. **Facial Shape:** Passed. Cheekbone definition, nose bridge, jawline contour, and female donor facial proportions preserved.
2. **Eye Openings:** Passed. Eyelid geometry cleanly frames the ocular openings without inward folding or occluding eyeball geometry.
3. **Jaw Integrity:** Passed. Mandibular rim and chin intact; jaw bottom capped without trim, neck taper, or neck elongation.
4. **Hair Silhouette:** Passed. Long hair back, side waves, hairline transitions, and tip contours preserved within the independent 8,000 triangle allocation.
5. **Texture Quality:** Passed. Base color transferred cleanly without baked lighting or AO; tangent-space normal map rebaked cleanly at $2048 \times 2048$.
6. **Orientation Check:** Passed. Verified bottom camera pitch at $-80^\circ$ looking directly up at the jaw cap.

---

## Retained Evidence & Artifacts

- **Geometry Audit Receipt:** `output/heads/trials/human-female-01/audit/geometry-audit.json`
- **Classification Receipt:** `output/heads/trials/human-female-01/components/components.json`
- **Cleaned Donor Source:** `output/heads/trials/human-female-01/cleanup/cleaned_donor.blend` & `cleaned_donor.glb`
- **Runtime Source:** `output/heads/trials/human-female-01/retopology/runtime.blend` & `runtime.glb`
- **Rebaked Normal Map:** `output/heads/trials/human-female-01/retopology/selected-normal.png`
- **Review Suite:**
  - Front view: `output/heads/trials/human-female-01/review/front.png`
  - Left side: `output/heads/trials/human-female-01/review/left.png`
  - Right side: `output/heads/trials/human-female-01/review/right.png`
  - Back view: `output/heads/trials/human-female-01/review/back.png`
  - Corrected jaw underside: `output/heads/trials/human-female-01/review/jaw-bottom.png`
  - Facial close-up: `output/heads/trials/human-female-01/review/facial-closeup.png`
  - Wireframe overlay: `output/heads/trials/human-female-01/review/wireframe.png`
  - Coronal slice: `output/heads/trials/human-female-01/review/section-coronal.png`
  - Sagittal slice: `output/heads/trials/human-female-01/review/section-sagittal.png`
- **Review Receipt:** `output/heads/trials/human-female-01/review/trial_review.json`
- **Trial Summary:** `output/heads/trials/human-female-01/trial_summary.json`
