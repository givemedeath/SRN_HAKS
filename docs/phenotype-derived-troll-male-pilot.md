# Derived Troll Male (Fit) Pilot Validation Report

**Document Version:** 1.0  
**Date:** 2026-10-05  
**Target:** Troll Male Fit (`pmg0`, Appearance row 2, RacialType row 2, Gnome replacement slot)  
**Parent Source:** Human Male Master Body (`pmh0`, Appearance 0)  
**Status:** Pilot Validation Complete (Gates 0 through 7 Certified, Standalone Package Built, In-Engine Client Inspection Verified)

---

## 1. Executive Summary

This report certifies the successful top-down derivation of the Troll Male (Fit phenotype 0, model prefix `pmg0`) variant from the accepted Human Male master body (`pmh0`). The Troll Male derivation proves the end-to-end scalability of the derived phenotype pipeline to heavily muscular, large-stature humanoid phenotypes without modifying donor master bytes.

### Core Achievements
1. **Rig Retargeting & Stature (Gates 0 & 1 - Approved):** Calibrated working height $1.9339\text{ m}$ scaled to runtime stature $2.7627\text{ m}$ via standard engine appearance scaling ($S_{\text{runtime}} = 10/7 \approx 1.4285714$). 56-node skeleton retargeting achieved exact $\max \Delta p = 0.000000\text{ m}$ deviation, preserving broad $0.5399\text{ m}$ shoulder span and exact stock weapon dummy locators (`rhand`, `lhand`).
2. **Localized Shaping (Gate 2 - Approved):** Wendland $C^2$ localized radial basis function (RBF) deformation successfully sculpted massive troll anatomy—including forward pectorals ($+25\text{ mm}$), heavy trapezius slope ($+22\text{ mm}$), deltoid lateral flare ($\pm 15\text{ mm}$), collar-like neck rim ($+18\text{ mm}$), $150\%$ enlarged hands, and $120\%$ feet—while maintaining strictly positive Jacobians ($\min J = 0.5066 > 0$), volume conservation within $\pm 0.9\%$, and zero displacement at connector boundaries ($< 10^{-12}\text{ m}$).
3. **Joint Interface Overlap (Gate 2b - Passed):** All 13 primary joint interfaces certified with positive axial overlap ($+0.7\text{ mm}$ to $+15.2\text{ mm}$), completely resolving the severe joint fluting and donor cap tearing observed in the purpose-built method.
4. **Equipment Compatibility (Gate 3 - Passed):** Audited across all 440 stock `pmg0` equipment models across 18 slots; weapon locators `rhand`/`lhand` verified exact with $0.000\text{ mm}$ drift.
5. **Native NWN Binary Compilation (Gate 4 - Passed):** 14/14 trimesh models compiled cleanly using `nwmain.exe` in isolated staging, verifying 100% normalized MikkTSpace tangent spaces ($|T|=1.0$) and normals ($|N|=1.0$) with multi-node pelvis and shared human normal/roughness map linkage (`pmh0_*n`, `pmh0_*r`), saving ~340 MiB distribution footprint.
6. **Packaging & In-Engine Client Inspection (Gates 5 & 6 - Passed):** Built standalone distribution HAK (`srn_derived_troll_test.hak`, 44 resources), test module (`srn_pheno_test.mod`), and test HAK (`srn_pheno_test.hak`, 47 resources) with verified SHA256 hashes and 0 client override files. Automated 135-second multi-phase client inspection sequence verified live in-engine.
7. **3-Way Silhouette Overlap Audit (Gate 7 - Passed):** Evaluated against canonical Shadowrun 4A concept art across Front, Side, Rear, and Proportional views. Upper Torso DICE match reached **$82.92\%$** (exceeding the $\ge 80\%$ gate), Pelvis DICE reached **$79.64\%$** (exceeding the $\ge 75\%$ gate), and Stance Width Ratio matched engine A-pose targets at **$85.40\%$**, achieving a **$+7.28\%$ convergence gain** over the stock baseline.

---

## 2. Pipeline Gate Verification Summary

All verification gates comply with the formal engineering protocols and mathematical thresholds specified in [Phenotype Pipeline: Gate Measurement Process & Verification Standards](phenotype-gate-measurement-standards.md).

| Gate | Phase | Measurement Scope | Output Receipt | Measured Value | Strict Threshold | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Gate 0** | Contract | Target stature & scale factor | `tools/phenotypes/target-matrix.json` | $1.9339\text{ m}$ work / $2.7627\text{ m}$ runtime | Contract match | **Passed** |
| **Gate 1** | Rig (CP1) | 56-node skeleton deviation | `output/phenotypes/derived-v1/rigs/troll-male/rig-receipt.json` | $\max \Delta = 0.000000\text{ m}$, locators exact | $\le 0.000000\text{ m}$ | **Approved** |
| **Gate 2** | Shaping (CP2) | Jacobians & volume delta | `output/phenotypes/derived-v1/parts/troll-male/ascii/refinement-proof.json` | $\min J = 0.5066$, $\Delta V = \pm 0.9\%$ | $J > 0$, $\Delta V \le \pm 1\%$ | **Approved** |
| **Gate 2b**| Connectors | Axial overlap across 13 joints | `output/phenotypes/derived-v1/parts/troll-male/ascii/connector-audit.json` | $+0.7\text{ mm}$ to $+15.2\text{ mm}$ (13/13) | $\Delta z > 0\text{ mm}$ (0 tears) | **Passed** |
| **Gate 3** | Equipment | 440 stock armor models & locators | `output/phenotypes/derived-troll-male-v1/review/equipment-receipt.json` | 440 models, 0 locator drift | 100% locator match | **Passed** |
| **Gate 4** | Compilation | Trimesh decode & MikkTSpace | `output/phenotypes/derived-troll-male-v1/review/native-shading-audit.json` | 14/14 compiled, 100% unit tangents | 100% unit tangents/normals | **Passed** |
| **Gate 5** | Packaging | Standalone HAK & test module | `output/phenotypes/derived-troll-male-v1/package/srn_derived_troll_test.hak` | 44 entries, clean SHA256 | Clean ERF hashes | **Passed** |
| **Gate 6** | Client Run | Override check & live run | `output/phenotypes/derived-troll-male-v1/review/client-evidence-run-13932.json` | 0 overrides, 135s sequence complete | 0 overrides, matching binary | **Passed** |
| **Gate 7** | Silhouette (CP3)| 3-way silhouette DICE overlap | `output/phenotypes/silhouette_metrics.json` | Torso $82.92\%$, Pelvis $79.64\%$ | Torso $\ge 80\%$, Core $\ge 75\%$ | **Passed** |

---

## 3. Detailed Gate Measurements

### 3.1 Gate 0 & Gate 1 (CP1): Rig Retargeting & Stature Calibration
- **Rig Scheme:** Broadened human-scaled rig adopting stock `pmg0` Gnome race slot with `a_ba` animation supermodel.
- **Stature Calibration:**
  - Working space assembly height: $1.9339\text{ m}$.
  - Engine appearance runtime scale factor: $S_{\text{runtime}} = \frac{10}{7} \approx 1.4285714$.
  - In-engine runtime stature: $2.7627\text{ m}$ (matching canonical Shadowrun reference of $2.50\text{ m} \times 1.105095 = 2.7627\text{ m}$).
- **Skeleton Node Verification:** Evaluated across all 56 skeleton nodes in `pmg0.mdl`. Maximum Euclidean position deviation: $\max \Delta p = 0.000000\text{ m}$.
- **Weapon Locators:** `rhand` and `lhand` match target contract coordinates exactly ($0.000\text{ mm}$ drift). Status: `verified-exact`.

### 3.2 Gate 2 (CP2): Localized Shaping & Inversion Prevention
- **Deformation Formulation:** Compact Wendland $C^2$ RBF field morphing:
  $$\phi(r) = (1 - r/R)^4_+ (4r/R + 1)$$
- **Sculptural Anchor Parameters:**
  - Pectorals: Forward projection $+25\text{ mm}$.
  - Trapezius: Muscle rise $+22\text{ mm}$.
  - Deltoids: Lateral flare $\pm 15\text{ mm}$.
  - Neck Rim: User-approved anatomical collar $+18\text{ mm}$.
  - Hands: Uniform scale $150\%$ for heavy Troll weapon grip.
  - Feet: Scale $120\%$ for stable ground contact.
- **Deformation Integrity:**
  - Minimum Jacobian determinant: $\min J = 0.5066 > 0$ across all 14 parts (pelvis crotch triangles preserved with $r=0.09\text{ m}$ anchor falloff). Zero inverted elements.
  - Volume Conservation: $\Delta V = \pm 0.9\%$ (strictly within $\pm 1.0\%$ threshold).
  - Connector Boundary Displacement: $\epsilon_{\text{leak}} < 10^{-12}\text{ m}$ (exactly $0.000000\text{ m}$).
- Receipt: `output/phenotypes/derived-v1/parts/troll-male/ascii/refinement-proof.json`.

### 3.3 Gate 2b: Joint Boundary Connector Overlap Audit
- Measured across all 13 adjacent body part pairs via `tools/phenotypes/audit_derived_connectors.py`:
  - `chest` $\leftrightarrow$ `pelvis` (waist): axial overlap $+15.2\text{ mm}$, $has3DOverlap = true$.
  - `chest` $\leftrightarrow$ `bicepl`/`bicepr` (shoulders): axial overlap $+10.2\text{ mm}$, $has3DOverlap = true$.
  - `bicepl`/`bicepr` $\leftrightarrow$ `forel`/`forer` (elbows): axial overlap $+5.6\text{ mm}$, $has3DOverlap = true$.
  - `forel`/`forer` $\leftrightarrow$ `handl`/`handr` (wrists): axial overlap $+2.8\text{ mm}$, $has3DOverlap = true$.
  - `pelvis` $\leftrightarrow$ `legl`/`legr` (hips): axial overlap $+6.4\text{ mm}$, $has3DOverlap = true$.
  - `legl`/`legr` $\leftrightarrow$ `shinl`/`shinr` (knees): axial overlap $+4.9\text{ mm}$, $has3DOverlap = true$.
  - `shinl`/`shinr` $\leftrightarrow$ `footl`/`footr` (ankles): axial overlap $+0.7\text{ mm}$, $has3DOverlap = true$.
- **Result:** 13/13 joints verified with positive axial overlap ($has3DOverlap = true$, 0 tearing, 0 dark banding). Receipt: `output/phenotypes/derived-v1/parts/troll-male/ascii/connector-audit.json`.

### 3.4 Gate 3: Equipment Compatibility Audit
- Evaluated against 440 stock `pmg0` armor and weapon models extracted from base game data across 18 slots.
- Rigid attachment transforms match stock placement precisely.
- Weapon seating matches stock hand orientation with zero locator offset drift.
- Receipt: `output/phenotypes/derived-troll-male-v1/review/equipment-receipt.json`.

### 3.5 Gate 4: Native Binary Compilation & Shading Audit
- Compiled with clean `nwmain.exe` in isolated staging directory `output/phenotypes/derived-troll-male-v1/compiler-userdir`.
- Shading audit verified via `tools/phenotypes/audit_derived_dwarf_native.py`:
  - 14 compiled binary trimesh models with 0 compilation errors.
  - Finite unit MikkTSpace tangent spaces: 100% valid unit tangents ($|T|=1.0$) and normals ($|N|=1.0$) across all 14 models.
  - Multi-node pelvis geometry: `pmg0_pelvis001p` (unskinned PLT node) + `pmg0_pelvis001f` (flesh diffuse underwear node).
  - Shared human normal and roughness map linkage (`pmh0_*n`, `pmh0_*r`), saving ~340 MiB per race.
- Receipts: `native-compile.json` and `native-shading-audit.json`.

### 3.6 Gate 5: Standalone Packaging & Test Fixture
- **Standalone Distribution HAK:** `output/phenotypes/derived-troll-male-v1/package/srn_derived_troll_test.hak` (44 entries, 175,563,023 bytes, SHA256: `4049569c9b91867bdc77ea33b1d27ce2cd507521f3d027a9f645b72cae3b02ce`).
- **Comparison Test HAK:** `output/phenotypes/derived-troll-male-v1/test-stage/userdir/hak/srn_pheno_test.hak` (47 entries, 182,596,327 bytes, SHA256: `8626d4f02ff3ba78eb1f03e627d88bfda284847f4fc188c6586e6d0bee6f430f`).
- **Comparison Test Module:** `output/phenotypes/derived-troll-male-v1/test-stage/userdir/modules/srn_pheno_test.mod` (33,788 bytes, SHA256: `22b4fdf45c3c65fe55b9be18819c696643ffddcea681a50cd4092298777c744a`).

### 3.7 Gate 6: Client Preflight & In-Engine Run
- Preflight verified:
  - Client `override/` directory contains **0 files** (100% HAK isolation).
  - Client binary SHA256 matches compiler binary SHA256 (`3b7cb125...`).
  - Preflight authorization status: `READY_FOR_USER_CONFIRMATION` / `pass: true`.
- In-engine test runner (`run_derived_dwarf_client_test.py --race troll --prefix pmg0`) executed live automated 135-second inspection sequence (PID 13932, elapsed $142.3\text{ s}$):
  - Frontal idle (10s), rear idle (30s), profile idle (50s), deep crouch (70s), arm elevation (95s), latissimus flexion (115s), settlement (135s).
  - All 7 phases observed cleanly; `PHENOTYPE_TORSO_SEQUENCE_COMPLETE` received.
  - Process memory: $608.8\text{ MiB}$ working set, $1.58\text{ GiB}$ private, $25.56\text{ s}$ CPU time.
  - Zero model-loading errors or engine warnings in `nwclientLog1.txt`.
- Receipts:
  - Evidence: `output/phenotypes/derived-troll-male-v1/review/client-evidence-run-13932.json`
  - Filtered Engine Log: `output/phenotypes/derived-troll-male-v1/review/run-13932-phenotype.log` (49 verified entries)
  - Preflight: `output/phenotypes/derived-troll-male-v1/review/client-preflight-receipt.json`.

### 3.8 Gate 7 (CP3): 3-Way Silhouette & Morphological Overlap Audit
Evaluated via `build_silhouette_comparison_sheet.py` and `calculate_silhouette_difference.py`:
- **Quantitative Overlap Metrics:**
  - **Chest & Upper Torso DICE:** **$82.92\%$** (IoU $70.83\%$) -> **PASS (Gate $\ge 80\%$)**.
  - **Pelvis & Waist DICE:** **$79.64\%$** (IoU $66.16\%$) -> **PASS (Gate $\ge 75\%$)**.
  - **Stance Width Ratio:** **$85.40\%$** -> **PASS (Gate $80\% - 95\%$)**.
  - **Convergence Gain over Stock:** **$+7.28\%$** closer to canonical target than stock human master.
  - Posterior Upper Back V-Taper: **$87.41\%$ DICE match**.
- **Presentation Sheets Generated:**
  - Front View Runtime Stature: [troll_silhouette_3way_comparison_front.png](file:///C:/Users/benco/.gemini/antigravity-ide/brain/4adb5468-4771-4ffc-93ea-eda7b809f211/troll_silhouette_3way_comparison_front.png) ($2700 \times 1600$).
  - Proportional 1:1 Head Height: [troll_silhouette_proportional_comparison.png](file:///C:/Users/benco/.gemini/antigravity-ide/brain/4adb5468-4771-4ffc-93ea-eda7b809f211/troll_silhouette_proportional_comparison.png) ($2700 \times 1600$).
  - Profile / Side View: [troll_silhouette_3way_comparison_side.png](file:///C:/Users/benco/.gemini/antigravity-ide/brain/4adb5468-4771-4ffc-93ea-eda7b809f211/troll_silhouette_3way_comparison_side.png) ($2700 \times 1600$).
  - Posterior / Rear View: [troll_silhouette_3way_comparison_rear.png](file:///C:/Users/benco/.gemini/antigravity-ide/brain/4adb5468-4771-4ffc-93ea-eda7b809f211/troll_silhouette_3way_comparison_rear.png) ($2700 \times 1600$).
  - Master 2x2 Turnaround Board: [troll_silhouette_master_turnaround.png](file:///C:/Users/benco/.gemini/antigravity-ide/brain/4adb5468-4771-4ffc-93ea-eda7b809f211/troll_silhouette_master_turnaround.png) ($3840 \times 2434$).
  - Master Racial Lineup: [all_races_silhouette_comparison.png](file:///C:/Users/benco/.gemini/antigravity-ide/brain/4adb5468-4771-4ffc-93ea-eda7b809f211/all_races_silhouette_comparison.png) ($3840 \times 1600$).
- Receipt: `output/phenotypes/silhouette_metrics.json`.

---

## 4. Production Acceptance Conclusion

The Troll Male (`pmg0`) derivation fulfills all engineering, geometric, and visual acceptance criteria:
- **Zero changes to `srn_body` master bytes.**
- **Zero regression in existing human male, female, or dwarf baselines.**
- **Zero joint fluting, zero dark bands, zero donor cap seams.**
- **All 14 derived body models render cleanly with full normal mapping in native NWN:EE.**
- **Troll Male is certified production-accepted.**
