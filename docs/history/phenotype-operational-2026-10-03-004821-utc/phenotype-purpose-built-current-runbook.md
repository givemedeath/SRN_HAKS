# Current purpose-built part workflow

## Active continuation: left thigh, then mirrored right thigh

The user's latest “Do it” starts the recommended next part. Read [the thigh checkpoint](phenotype-thigh-checkpoint.md) first. Preserve the accepted torso/pelvis and their native materials; measure and fit the left thigh to stock hip/knee attachments, perfect it through poses, then mirror its geometry with correct surface attributes and independently validate the right attachment. Completed pelvis stages below remain immutable baseline evidence, not instructions to repeat them.

## Finished current part: Human male pelvis

### Selected pelvis continuation (2026-10-02)

The user accepts the rounded original lower exterior in the client ("looks good to me"). Preserve the current selected geometry; the horizontal/paired/angled cuts are comparison history. Final chain under `output/phenotypes/purposebuilt-pelvis-pilot-v1`:

1. `top-only-conditioned-v1`: original outward component, sole top cut/skin closure.
2. `original-rim-polish-v1`:547 outer skin vertices, maximum1.176mm, protected clothing/groin/top and unchanged topology/UVs.
3. `original-polished-residual-repair-v5`:27,526 triangles, closed manifold; zero genuine intersections in2,634 repair-against-whole-mesh candidate pairs.
4. `original-polished-material-v1`: unchanged2K map pixels and surviving sourceUVs; all true caps skin0; local repair charts explicitly reviewed. Small fixedRGB cloth/skin seam scope remains recorded, not mislabeled as a pure-cloth source.
5. `selected-d-original-polished-material-v1`: uniform scale1, proper X−4°, back10mm/up5mm applied once. GLB SHA256 `db0bdf16099068da3bb685bcb61ae93ebed115e6ddbae90990c0b55e59b8d98a`.
6. `diagnostic-native-stage-original-polished-v1` → `pelvis-only-native-prepared-original-polished-v1`: actual pelvis-only compilation; protected chest never recompiled.

Current52-resource HAK SHA256 `2ff74b9c10c8ba19f1159b603ade4eb4e00511eca1c864f4ae4fa06b82b35a5d`. `audit_pelvis_package.py` proves exact staged ERF payloads, sole custom chest/pelvis, unchanged Human appearance row, male actors, empty override and no root/animation resources. Actual screenshot/log evidence lives in each fresh `client-original-rim-*-v1/client-evidence`; review the pelvis checkpoint for remaining checks. A completed generation, topology audit or script dispatch is not a visual motion result.

Final pelvis client checks are finished; see [validation and evidence](phenotype-pelvis-validation.md). The pelvis is visually accepted and its scoped geometry/native/client gates pass; this does not promote the unfinished whole body. The next limb workflow should perfect one side, then mirror-clone it: correct mirrored face winding, normals and tangent handedness, review UV/material orientation and independently fit/animate against the opposite stock attachments. Preserve the stock rig. One thigh followed by its validated mirror is the recommended next work; it has not started.

For visible launches, use the **executable directory**, `bin/win32`, as `Start-Process -WorkingDirectory`. Repository and installation-root directories caused missing base-key/shader/mouse/logo resources and startup crashes before loading the test module. Correct form:

```powershell
Start-Process -FilePath $taskClient -WorkingDirectory (Split-Path -Parent $taskClient) -WindowStyle Normal -ArgumentList @('-userdirectory', ('"' + $taskUserDirectory + '"'), '+TestNewModule', 'srn_pheno_test')
```

Reobserve process ownership first, replace only the exact fixture PID/argv, and select a fresh computer-use window. Never spawn a default-userdir fallback alongside it. Optional FPS display and focus-pause settings belong only to the isolated test userdir; camera remains unlocked.

The newest explicit goal finishes a purpose-built muscular Human male pelvis. Read [the pelvis checkpoint](phenotype-pelvis-goal-checkpoint.md) before continuation. The torso input below is frozen, including its fit and maps; its visually sufficient shading/waist are not a repair task. Pelvis evidence does not complete the remaining whole-body gates.

Measure **visible** anatomy separately from stock cap/spike bounds. The torso covers the stomach: current torso bottom reaches pelvis-local Z−30mm; the new pelvis should emerge around −15..−25mm with only15–25mm of hidden upper overlap. Broad hips are approximately388×292mm at Z−175mm; a rounded bottom around−285mm avoids copying the stock−322mm spike. Moving thighs own proximal thigh anatomy and cap crowns; briefs stay on pelvis. Full measurements and occlusion evidence are under `purposebuilt-pelvis-pilot-v1/stock-connectors-summary-v1` and `visible-envelope-v1`.

Current selected sheet is `imagegen/source-v6.png`, SHA256 `caa87df19c92b34abfa1b23d95b89bed82f3c265870a63235bdcd08326293af2`: flatter anterior brief panel, fuller posterior seat, no visible abdomen or projecting tabs. User authorizes trimming excess thigh anatomy after the first uniform fit. References, prompts and provenance are hash-verified in the original `reference_images/normalized/purposebuilt-human-male-pelvis-v2-anatomical`. The new attempt is `purposebuilt-pelvis-pilot-v1/comfy-v2-anatomical`, prompt `1a100713-1f07-4e41-8092-ec6285dc4134`; inspect its receipt/history and never duplicate dispatch. Earlier v5 source/attempt remains immutable history, rejected because its nearly symmetric rounded front and rear are not corrected by a 180-degree flip.

**Anatomical orientation is a per-part gate.** Never copy a torso rotation into pelvis fitting without proving front/rear landmarks. Compare both orientations with actual stock and source sheet; the earlier paired-lobe pelvis has quantitative source/stock section evidence in `source-orientation-diagnosis-v1`. Similarity placement preserves source BIN, normals, tangents and maps exactly; undeclared attributes fail. Offline preview must bake effective parent transforms in disposable imports before assigning exact stock joints, otherwise a valid wrapper fit can be displayed incorrectly.

Newest selection after isolated comparisons: **try the original exterior with only the top cut**, preserving its naturally closed rounded lower ends. The earlier angled caps and later horizontal/paired-cut trials remain diagnostic history. Global Z−200mm visibly clipped the central groin; paired cuts preserved it but removed more of the lower glute/skin edge than the untouched exterior. Use `top-only-d-preview-v1` for stock-pose review; close the top with skin and repair only demonstrated inherited defects before native trial. All new caps use skin. The completed first uniform fit is `similarity-placement-v3-anatomical`, proper Z180/scale0.4163415115080963. Preserve the selected D rigid adjustment (scale1, X−4°, back10mm/up5mm), torso and stock attachments/animations. Each source exterior selection needs fresh source association and inner/outer ownership proof; successful classification alone does not establish closed/manifold topology.

Native pelvis packaging support: `compose_stock_pelvis_native.py prepare` creates a pelvis-only compile unit with five declared map/material dependencies. Run the existing native compiler there; `compose` verifies that real receipt and copies the previously tested chest ASCII/binary/material resources and real compiler provenance unchanged, with a truthful dependency union. Private stock comparator aliases are independently verified against the clean stock bank. This avoids recompiling the protected chest just because the pelvis adds dependencies. Tests/preflight do not imply a generated pelvis is compiled or accepted.

Concrete process improvements: `normalize_part_turnaround.py --layout-components` extracts complete alpha silhouettes before quadrant assignment, retaining a single isotropic scale and preventing wide silhouettes from being chopped at a sheet midline. Fixed-quadrant mode now rejects clipped silhouettes. Opaque/ambiguous component sheets fail. Source framing variations remain provenance, not independently stretched corrections. `generate_purpose_built_part.py` now declares output save nodes and can retain the actual **raw pre-remesh master**; legacy completed receipts still use their original three saves. Mode-specific remesh settings replace inherited widgets explicitly. Filtered UDF is the first pelvis variant; SDF remains an unselected experiment pending evidence of reliable raw outward winding.

The v2 source and uniform fit are complete. `client-d-wall-v1` is a successful actual native diagnostic with initial idle viewing, not final pelvis validation; its angled caps are now superseded by the horizontal-cut trial. Preserve its receipts and tested torso native resources. Full motion, gameplay, equipment and performance evidence must use the selected final descendant and fresh client logs. Human equipment remains stock identity. `stock-armor-fixture-inputs-v1` records unchanged installed cloth/armor selections plus an explicit chest-only cloth fixture that leaves the candidate pelvis visible; no resized equipment models are introduced.

This is the operational entry point as of 2026-10-02. The current pelvis fixture replaces Human male chest and pelvis only. Stock neck/head, limbs, skeleton, attachment transforms, supermodel and animations remain stock; Human equipment stays identity. The torso waist check passed and its shading is visually sufficient to the user. Preserve the torso/maps without a shading repair. Inherited torso topology and whole-body gates remain separate. Nothing is promoted to the accepted ledger yet. Finish pelvis caps and validation before selecting the next part.

Priority is finishing Human male. Broader reusable-process gaps listed below are deferred unless one directly blocks creating, packaging or verifying the Human assets. Do not expand into other-race tooling while Human anatomy and client acceptance remain unfinished.

## Selected inputs and completed stages

All pilot paths below are relative to `output/phenotypes/purposebuilt-torso-pilot-v1` in `D:/srwt/codex/f0b3/SRN_HAKS`.

| Stage | Selected output / evidence | Carry-forward rule |
| --- | --- | --- |
| Image design/normalization | `normalized-v1/provenance.json`, `reference-copy-audit.json` | Preserve four new torso views and truthful historical guide provenance. Normalized copies are also in the original `reference_images/normalized/purposebuilt-human-male-torso-v1`. |
| Local multiview generation | `comfy-v1/generated/textured_00001.glb` | Immutable source SHA256 `905e80661f1ed5ec9b5f456e78b86441e58ed44af26617a9005b56760c438172`; prompt `a8404d03-2dbf-4cb6-93ef-fa6280ef6d5d`. No rerun needed. |
| Stock connector measurements | `stock-connectors-v1/measurements.json` | Use real stock arms/neck/pelvis. Earlier custom-arm guides are provenance, not the next seam target. |
| Similarity fitting | `similarity-placement-v5-pitch`, `selected-v5-baseline-v1/selection.json` | User-selected scale 0.5686111708925986; +10° X pitch after 180° Z, recorded anchor/pivot. No global X/Y shrink or changed rig. |
| Local waist cap/material continuation | `waist-rounded-cap-v3` | Protect upper source; outer dome and hidden inner closure get matching maps. Earlier failed cap/material variants stay historical. |
| Shared atlas | `common-cap-atlas-v2` | Two guarded cap strips in 2K atlas; retained upper sampling verified. v1 rejected. |
| Posterior then front/side taper | **`common-cap-atlas-v4-perimeter`** | Current geometry SHA256 `3ae78d023ba522d94c44d9914bac0b36f35b640c42b9532015575e5572161a50`. Preserve upper anatomy and already accepted rear taper. |
| Stock pose review | `perimeter-stock-pose-audit-v1`, `perimeter-stock-pose-review-v1` | Actual stock parts/matrices and displayScale 1; eleven reviewed offline views. |
| Native export/package | **`standalone-native-perimeter-inputs-v4`** | Exact raw corner attributes; material-aware native tangents. Only `pmh0_chest001` custom, private `pmx0` comparator fixture-only. |
| Client check | `standalone-native-perimeter-inputs-v4/client-evidence/complete-sequence-v5` | Seven screenshots, full log, build receipt and observations. Waist covered in idle/side/crouch/CONJURE1; back shading remains. CONJURE1 is not full overhead. |

Tested HAK SHA256: `a684bba65be6fce33c52caf160277d4fb7605c4681575bd0c75126739c860662`. Tested module SHA256: `94b5b3a5be75febb4764d5b78a99a883e022ba4094aca245732f54fa3aafeb71`. Keep these packages/evidence immutable; later tooling cleanup does not retroactively change their receipts.

## Clean input boundary

[human-male-purposebuilt-torso-stage.json](../tools/phenotypes/configurations/human-male-purposebuilt-torso-stage.json) is the current staging config. It selects the perimeter GLB and exact color/normal hashes. It uses `output/phenotypes/purposebuilt-stock-inputs-v1`, a 50-file allowlisted bank: extracted stock models/controllers and raw palettes/table plus three fixture templates. Every stock asset matches the recorded extraction receipt; fixture templates match the tested stage. No custom-body directory is cloned. Old absolute locations remain only as provenance in the inventory and immutable past receipts.

`stage_stock_part.py` verifies the bank inventory/hash, rejects extra bank files or changed selected maps/geometry, preserves raw authored normals and records owned resources. `build_test_module.py` rejects undeclared single-part ASCII/resources and stale compile dependencies. The actual tested HAK's 46 payloads match the allowlisted staged bytes; override is empty. Evidence: `output/phenotypes/purposebuilt-carryover-audit-v1/audit.json`.

The current frozen bank can be reproduced from the verified source extraction and tested fixture with:

```powershell
$taskPython = 'C:\Users\benco\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $taskPython tools/phenotypes/freeze_stock_part_inputs.py --contract tools/phenotypes/configurations/purpose-built-human-male-production.example.json --tested-stage output/phenotypes/purposebuilt-torso-pilot-v1/standalone-native-perimeter-inputs-v4 --output output/phenotypes/purposebuilt-stock-inputs-FRESH
```

Use a fresh output; point an explicitly copied config at that bank and its new inventory hash. This copies only enumerated stock/fixture files, not prior converted parts, maps, tables, armor profiles, acceptance receipts or userdirs.

## Running the next native diagnostic

Run from the repository root. Reuse the completed source/fitting/cap/taper; do not regenerate merely to rebuild native resources.

```powershell
$taskPython = 'C:\Users\benco\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$taskClient = 'C:\Program Files (x86)\GOG Galaxy\Games\Neverwinter Nights Enhanced Edition\bin\win32\nwmain.exe'
$taskGame = 'C:\Program Files (x86)\GOG Galaxy\Games\Neverwinter Nights Enhanced Edition'
$taskTools = 'D:\source\repos\SRN_HAKS\.tools\neverwinter\2.1.2\windows-x64'
$taskStage = 'output/phenotypes/purposebuilt-torso-pilot-v1/standalone-native-FRESH'
& $taskPython tools/phenotypes/stage_stock_part.py --config tools/phenotypes/configurations/human-male-purposebuilt-torso-stage.json --output $taskStage
& $taskPython tools/phenotypes/native_compile.py --client $taskClient --user-directory "$taskStage/compiler-human-userdir" --converted "$taskStage/human_male_fit/converted" --timeout 180
& $taskPython tools/phenotypes/native_compile.py --client $taskClient --user-directory "$taskStage/compiler-stock-userdir" --converted "$taskStage/stock_human_male_fit/converted" --timeout 180
& $taskPython tools/phenotypes/build_test_module.py --output $taskStage --tool-directory $taskTools --game-root $taskGame --slugs human_male_fit,stock_human_male_fit --torso-inspection-sequence --camera-target human_male_fit --camera-pitch 75 --camera-distance 3.5 --camera-height 1.2
```

Check each exit status before the dependent command. The clean-staging proof `carryover-clean-stage-proof-v1` reproduces the prior ASCII and maps exactly; it is not newly compiled or client-tested. A fresh build must receive its own actual native shading audit and package hashes. Launch the isolated userdir using `-userdirectory ABSOLUTE_USERDIR +TestNewModule srn_pheno_test`, verifying ownership before restarting any client. Never restart another experiment's client. [The inspection sequence](phenotype-torso-inspection-sequence.md) records timing, reset behavior and camera policy. Capture settled screenshots against the new receipt, not just animation logs.

## Applying the process to the next part

1. Measure its real stock connector surfaces/pivots and moving ownership. Use `prepare_torso_connector_guides.py --stock-arms` for torso; other parts need equivalent explicit measurements. Preserve stock neck/head.
2. Design one purpose-built part in a coherent muscular family, closed shallow overlap ends and four equal-scale views. Review the sheet before reconstruction; keep pelvis-only underwear and nearly closed gripping hands. Save original/normalized images and prompts in `reference_images`.
3. Use [the generation procedure](phenotype-purpose-built-part-generation.md): prepare/freeze the actual `SR_NWN_3d_pixal3d_multi_views` workflow, submit once, collect using the preserved job receipt. Do not assume remeshing makes a connected hollow shell solid.
4. Inspect the actual source. Use `purposebuilt_torso.py place` for one uniform scale plus proper rotation/translation; normal strength defaults to 1. The similarity search now verifies that its source-coordinate/triangle NPZ belongs to that exact GLB. New part/race fitting requires explicit target configuration; torso helpers are not a completed generic limb runner.
5. Compare against actual stock using `pose_preview.py --stock-replacement ... --baseline ... --stock-prefix pmh0 --stock-height 1.9339157`; review the declared map and run `audit_stock_replacement_preview.py`. Future cumulative maps must include only independently accepted neighbours plus the current diagnostic; ledger enforcement in the preview tool is not yet automatic.
6. Only after adequate similarity fitting, apply justified localized end/cap edits with protected-surface proof. [The fitting pilot](purposebuilt-torso-fitting-pilot.md), [waist cap](phenotype-localized-waist-cap.md) and [atlas/export guide](phenotype-purpose-built-native-cap-atlas.md) record concrete operations and rejected alternatives. Current material pixels remain unchanged; no automatic 0.35 normal reduction.
7. Export only declared replacements, compile with exact material dependencies, pack an allowlisted fixture, then complete the required native/client/palette/equipment/performance gates. Promote through the ledger only after all required evidence passes.

## Excluded historical routes and remaining limits

`purposebuilt_torso.py assemble` clones an earlier whole-body conversion and is historical-only, guarded by `--historical-custom-assembly`. Do not use it as the current assembly/staging entry. Old full-body slices, adapted Human armor/NWNArmory scaling, custom neck/root/animations, failed cap atlases and their acceptance receipts are excluded. Private appearance/tileset and `pmx0` comparator resources belong only to the isolated fixture, never a production race HAK.

The original torso sheet was informed by earlier custom-arm connector guides; preserve that fact rather than rewriting source provenance. Current fitting and surrounding parts use actual stock. Historical outputs stay available as evidence, not live defaults. [The design contract](phenotype-purpose-built-production.md) describes future promotion/race/profile policy; its pre-cap example is not the latest candidate.

The active generation configuration now records post-fit normal strength 1 as well. The completed job's frozen configuration/receipt retains its original unapplied 0.35 suggestion as historical metadata; no source map is rewritten to change that history.

This is a documented, verified Human torso pilot, not a finished universal process. Automatic cumulative-ledger preview enforcement, opaque-background normalization handling, other-part/race staging, practical budgets, full gameplay/equipment tests and Troll/NWNArmory portability still need implementation or proof. The standalone stage now rejects unsupported races rather than silently treating them as Human. Six inherited boundary edges/one nonmanifold edge remain unresolved. The earlier angular-shading screenshot concern is superseded by the user's acceptable in-game review; no shadow experiment is required now. No claim of complete production acceptance is made.
