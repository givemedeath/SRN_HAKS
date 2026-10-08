# Reusable purpose-built phenotype creation plan

Use this plan with the [reusable goal prompt](purposebuilt-phenotype-goal-prompt.md). Fill the variables before production, resolve support and design questions from the repository and the user's instructions, then retain the completed plan with the target's evidence. The [Human female checkpoint](../phenotype-human-female-checkpoint.md) is an example of one execution, not a source of approval or exceptions for another target.

## Target variables and acceptance authority

| Variable | Fill in |
|---|---|
| Repository and PR destination | `<repository>`, base `<main-or-approved-base>`, PR target `<branch>` |
| Source local branch/worktree | `<source-branch>`, `<source-worktree>`, latest local HEAD plus uncommitted state |
| Dedicated branch and managed worktree | `codex/<target-purposebuilt>`, `<managed-worktree-name>` |
| Independent target ID | `<race>-<gender>-<phenotype>-purposebuilt-v<revision>` |
| Identity | `<race>`, `<gender>`, `<raceId>`, `<appearanceRow>`, `<phenotype>`, `<family-prefix>`, `<body-style>` |
| Rig path | `<stock-exact or supported retargeted>`, `<source-prefix>`, `<rig-revision>` |
| Stature | Fresh installed measurement `<stock-height-metres>`; working/runtime height and declared scale |
| Physique and common style | `<reference path and hash>`, `<human-approved style source/hash>`, silhouette, skin detail and shading direction |
| Fixed garment ownership | `<list of approved chest/pelvis owners>`, cut, coverage, cloth color and opacity |
| Equipment policy | `<installed identity-sized equipment or separately approved retargeted profile>` |
| Donor order and runtime ownership | `<ordered donors and required opposite parts>` |
| Target output and shared reference bank | `<target-output-root>`, `<verified-reference-bank>` |
| Operational records | `<execution-inputs>`, `<selection-ledger>`, `<checkpoint>`, `<runbook>`, `<evidence-index>` |
| Tool/runtime configuration | `<bundled-Python>`, `<shared-toolchain-config/hash>`, `<passed-migration-receipt/hash>` |
| Generation workflow | `<saved/live workflow>`, `<API endpoint>`, `<reviewed orthographic adapter>` |
| Client and capture/control | `<installed-client/path/hash>`, `<supported capture/control method>` |
| Acceptance scope | `<practical game-quality criteria>`, `<microdefect thresholds>`, `<required client/equipment matrix>` |
| Publication approval | Explicit final approval of the exact completed review package; merging is a separate action |

Define excluded work in the filled plan: additional phenotypes, custom heads, rig changes, changed equipment sizing, production table edits and unrelated assets require deliberate scope and verified support. An approval of an image establishes art direction; it does not establish reconstructed geometry, native materials, motion or client acceptance.

### Supported interfaces must be established first

The current version-2 stock-exact contract supports Human normal phenotype 0, male `pmh0` or female `pfh0`, race and appearance 6. Its installed stock hierarchy, frames and stature remain exact. The legacy retargeted contract retains its male phenotype-0 restrictions and pilot requirements. This template describes a reusable process; it does not imply that arbitrary race/gender/phenotype combinations already work in every helper, fixture, adapter or client guard.

For a new identity, audit all embedded families, gender bytes, equipment prefixes, palettes and output paths. Extend and validate the actual target contract and its dependent tools before generation. Add independent tests for the new identity while preserving existing targets. Record unsupported interfaces as open gates, rather than relabeling another target's receipts.

## 1. Isolate the latest local source state

1. Locate the requested local source branch and worktree. Record HEAD, branch, tracked modifications and non-ignored untracked files. Do not substitute a remote or stale committed state for the requested latest local state.
2. Preserve a recoverable snapshot with a patch, exact file copies, file sizes, SHA-256 hashes, status and timestamp. Verify hashes after copying. Leave the original worktree intact and retain needed ignored masters separately.
3. Create the dedicated managed worktree and named branch from that source HEAD. Bring over the required shared tools, configurations, audits and tests with their dependency closure. Record inherited file hashes. Keep unfinished source-target body assets, selections and delivery evidence out of the eventual published diff.
4. Give the target independent execution inputs, output directories, ledger, checkpoint, runbook and evidence index. Bind receipts to target ID, contract hash, rig revision and coordinate space. Do not borrow another target's accepted selections or exception records.
5. Inspect repository instructions, contribution rules and the PR template. Keep generated masters, downloaded tools and built packages outside Git. Plan the exact tracked asset/tool/documentation closure early.

## 2. Reverify tools and freeze installed inputs

Discover the bundled workspace Python and the repository's shared tool/addon bank. Never use the Windows Store Python shim. Verify the configured binary and addon paths and hashes, the passed migration receipt and actual loaded addon module locations. Execute phenotype tools through the verified shared launcher. Preserve historical receipts; a changed bank or configuration requires a new validated migration/launch record.

Extract installed inputs fresh with overrides disabled and an isolated empty-override user directory:

- The root, every standard body part, inherited animation chain and required head/neck meshes and material dependencies.
- Palettes and relevant tables, including race, appearance, phenotype and equipment/body-style tables.
- Representative clothing, armor, boots, gloves, robe, helmet, weapons and shields for the declared identity, with their actual source origins and dependencies.

Record native and decompiled hashes, extraction origins, exact tools, root/supermodel chain, visible joints, body contours, limb lengths, assembled height, sole position and held-equipment frames. Measure the installed stock body instead of copying a historical approximate height. Freeze attachment matrices and the authoritative stock receipt before fitting candidates.

### Rig invariants

**Stock-exact path:** `rig.mode` is `stock-exact`; runtime scale is exactly 1; working and runtime frames and heights are identical. A pinned `rig.stockReferenceReceipt` must independently prove the actual installed hierarchy and frames. Do not export private rig aliases, move binds, replace the stock head/neck or alter production tables or equipment. Reverify current installed rig/head/neck/table/palette bytes before client loading.

**Supported retargeted path:** retain the path's identity restrictions and bind-relative animation invariants. Freeze the reviewed working and runtime frames, proper rotations, timing/events, private aliases and equipment profiles. Obtain the required pilot acceptance before complete-body selection. Retargeting, Large appearance mapping and profile-specific equipment checks remain separate from stock-exact checks.

Perform one recorded working-to-runtime conversion. An identity transform still counts as the one conversion on stock-exact targets. Reject stale/cross-target inputs and repeated conversion rather than silently applying another transform.

## 3. Freeze common art direction and isolated references

Start from the user's physique reference. Obtain and record approval of a common style source for skin tone, muscle definition, texture detail, painted shadows/highlights and cloth. Preserve that source byte-for-byte with prompts, generator provenance, ancestry and approval. Keep verification copies in the shared reference bank.

Strong painted or baked albedo muscle shading can be an explicit art direction for an older renderer. Carry that style coherently across all donors while keeping the agreed natural silhouette. Preserve original maps and distinguish painted shading from optional later AO multiplication and runtime palette calibration.

Generate isolated donor sheets with genuine front, left, back, right, top and bottom views. Review anatomy, orientation, garment coverage, ownership and end surfaces before reconstruction. Repeated side views, perspective/tilted end views or inconsistent proportions must be corrected or held pending the camera gate. A human style approval does not waive the camera gate. Preserve attempts and rejected sources rather than overwriting them.

Normalize every panel with one shared isotropic scale and the documented orthographic camera bases. Record camera direction/right/up vectors in generator world, donor-local and target rig space, source crop regions, transforms, ortho span and source/output hashes. Identify anatomical anterior/posterior and left/right visually in every view. Verify how anterior projects into the top/bottom image axes; panel labels and an apparently plausible cardinal sheet do not establish those semantics.

Measure projected silhouette consistency across all six bases before reconstruction. Compare corresponding widths, heights and anterior/posterior depth envelopes under the shared isotropic scale; verify that the end-view silhouette projects the same whole object's full volume as the cardinal silhouettes. Top and bottom are whole-object orthographic end projections, not cross-sectional slices or cut-surface diagrams. Set and record practical alignment tolerances, observed discrepancies and supporting overlays. A disagreement that changes volume or orientation blocks the camera gate.

Record the explicit semantic permutation from observed source panels to the adapter's front/left/back/right/top/bottom slots. Correct ambiguous or opposite side slots before submission; never infer the permutation from written labels alone. Avoid independent nonuniform stretching, local panel edits or silhouette cropping that conceal incompatible views. Verify the reconstructed donor's projected silhouettes against all six approved inputs before fitting/selection, and investigate any material depth/volume mismatch rather than accepting the cardinal appearance alone.

### Default donor sequence

Adapt this order only with a recorded reason and affected review gates.

| Order | Isolated donor | Typical runtime owners | Required review |
|---|---|---|---|
| 1 | Chest | `chest` | Garment coverage, neck, shoulders and waist |
| 2 | Pelvis | `pelvis` | Approved briefs/garment cut, hip/groin anatomy, waist and thigh interfaces |
| 3 | Left upper arm | `bicepl`, `bicepr` | Deltoid/biceps/triceps ownership and shoulder/elbow coverage |
| 4 | Left thigh | `legl`, `legr` | Hip, quadriceps/hamstrings and pelvis/knee coverage |
| 5 | Left shin | `shinl`, `shinr` | Calf anatomy and knee/ankle coverage |
| 6 | Left foot | `footl`, `footr` | Five toes, heel, arch, underside, ankle and floor contact |
| 7 | Left forearm | `forel`, `forer` | Elbow transition and wrist coverage |
| 8 | Left hand | `handl`, `handr` | Four fingers and thumb, approved weapon-ready grip and wrist |

Review chest, pelvis and both upper arms together before proceeding. Every addition requires a cumulative assembly review. Clearly identify diagnostic stock fallback parts; they are not completed candidate selections.

## 4. Reconstruct, fit and select donors

### User-supplied external static donors

When the user supplies a Meshy or other external textured GLB, preserve the exact original in a fresh target-specific intake before inspecting or fitting it. Use an explicit external-donor receipt containing the target/part, original path and byte hash, frozen-copy hash, decoded geometry/material inventory, original embedded-map bytes, and dependency pins. Verify the actual object and laterality from geometry and literal six-view renders; an old filename or exporter generator string does not establish the donor identity or generation service.

Record unavailable generation prompts, conditioning images, model IDs, seeds and raw/remeshed masters as unavailable. A guide supplied in this chat does not prove which image the external service used. Retain the available textured master without fabricating a successful local generation receipt or altering the original maps. Reject imported rigs, skins or animation data in the static body-part intake; preserve installed target frames and equipment attachments.

The local workflow reservation/submission gates below apply when generating a donor here. For an external static donor, replace those generation-only records with the verified external intake and its stated provenance limits, then perform the same anatomy, source attributes, wall/contact, material, fitting, repair, mirror, motion, native and literal-client acceptance checks. Every fresh fit or local correction is a separately pinned unselected descendant until those checks pass. Compare geometry-only, unlit base-color and normal-mapped views so painted detail and literal mesh shape are measured separately.

For each donor:

1. Prepare an explicit configuration against the actual reviewed workflow. A starting baseline is 1024 reference/shape resolution, 50,000 compact triangles, 2K maps and normal strength 1; adapt only with review and measured evidence. Freeze the graph/API prompt, schema, node/model identifiers, dependency hashes, seeds, remesh settings and orthographic adapter.
2. Create a fresh job output and atomic reservation. Persist a unique client ID and the exact graph before dispatch. Observe the shared queue and preserve others' work. Submit once. An uncertain response requires reservation/receipt, prompt ID, queue and history recovery; match both the persisted client ID and exact submitted graph. Lack of a response is not permission to submit again. Preserve raw, remeshed, compact and textured masters.
3. Inspect anatomy, connected components, walls, topology, crossings, normals, UVs and every map. Explicitly inspect foot undersides/toe count and gripping-hand fingers/thumb. Do not let a plausible thumbnail substitute for mesh inspection.
4. Fit by positive uniform scale, a proper rotation and translation into the measured target frames. Record transforms and protected attributes; preserve source maps, UV sampling and authored shading attributes.
5. Repair measured connector/topology defects with bounded operations, fresh receipts and protected-attribute proofs. Separately record any user-authorized anatomical correction, its measured target and protected regions. Any appearance, geometry or material change creates a reviewed descendant and reopens affected checks.
6. Mirror detached selected limbs through the actual opposite attachment frames. Independently verify positions, winding, authored normals, tangent handedness/signs, UV sampling, anatomy and animated fit on both sides.
7. Review the addition in the cumulative body from all required views and motions. Trial stages must preserve selected neighbors byte-for-byte. A changed neighbor needs a new descendant and repeated relevant joint/material/motion checks.

Initial stock-frame fitting remains a positive uniform transform. When the user authorizes a mesh shape correction, retain that fitted parent and record the correction separately. For example, a positive affine width change can preserve every point's position along the measured limb axis and its anterior/posterior depth; a localized breast correction can protect the back, shoulders, neck, waist and garment coverage. Define the basis, pivot, support and magnitude from measurements. Prove positive Jacobian and bounded conditioning, independently transport authored normals/tangents through the field, and verify serialized positions, winding, UVs, original maps and untouched regions. Recheck actual opposite-frame mirrors, neighbor contact and motion. Do not reduce the stock rig or runtime scale to disguise an anatomical width correction.

Record selection by exact candidate and package hashes, supported visual evidence and remaining limitations. Do not mark a donor accepted because generation or compilation succeeded.


When an explicitly reviewed diagnostic needs different texture views, freeze shape and texture conditioning separately, including their camera bases, image hashes and graph edges. Prove that the shape branch and latent connection are unchanged; exclude unintended links from the texture branch. Preserve backward compatibility when the option is omitted. Equal seeds and input graphs do not prove byte-identical remeshing or UVs: compare actual outputs and reopen affected checks for changed descendants.

Protected vertices and protected surfaces are distinct. When a deformation support boundary crosses triangles, inspect clipped face surfaces above that boundary; unchanged vertex rows alone do not prove an unchanged surface. Use measured face-aware support or reviewed splitting when whole-face protection is required, with original-corner/interpolated-attribute lineage and repeated native/visual checks.

## 5. Own materials explicitly and preserve the originals

Declare fixed garment owners in `material.fixedGarmentParts`; the current generalized full-map path allows chest/pelvis owners, while legacy retargeted targets preserve their pelvis-only behavior. Define explicit skin and garment faces. When generation shares one material, create and review ownership masks before staging. Keep the bra on chest and briefs on pelvis when that is the approved design; preserve garment cut and coverage through every fit and repair.


Review emitted/unlit base color separately from rendered normal-map or scene-light contrast. Measure broad skin intensity variation and AO coverage. AO multiplication cannot recreate painted shadows that the reconstruction removed. If a technical lighting bake is needed for the approved older-engine style, derive a separately pinned atlas from one untouched parent with frozen CPU bake settings, lights, normal strength and bounded comparison strengths. Preserve original geometry, UVs, authored normals, normal pixels, ORM and source color maps. Record compiler intensity corrections separately, protect garment and connector regions, compare neighboring parts and stock neck under every target palette, and inspect the resulting baked light under the actual client lighting matrix.

Retain original base color, normal pixels, authored ORM and original compiler inputs. Keep original UVs and authored normals protected. Use recolorable PLT skin with fixed opaque cloth and inspect garment edges/straps for palette bleed. Transport authored ORM-green roughness through texture3 with `Roughness 0` on the supported material path; do not silently replace it with a scalar.

Compare AO strengths 0, 0.15 and 0.35 as descendants of the same untreated parent and select through assembled review. Calibrate visible skin against selected neighbors and the stock neck. Record palette/color/roughness corrections separately from immutable original maps and compiler input receipts. Recompile when a compile-time dependency changes; an explicitly verified runtime material descendant must disclose its exact effective inventory and limits.

For the current full-map body adapter, with `N` body owners and `G` fixed garment owners, the body resource count is `5N + 4G`: one native model, MTR, PLT, normal TGA and roughness TGA per body owner, plus diffuse/MTR/normal/roughness cloth resources per garment owner. Fourteen parts and two garment owners imply 78 resources. This is an inventory expectation, not evidence; inspect actual filenames, extensions, hashes and dependency closure. Other adapters and retargeted rig/provisional/equipment/fixture groups can have different counts.

## 6. Validate the actual body and native serialization

Add focused tests that reject wrong identity, stale/cross-target inputs, violated rig invariants, repeated conversion, missing/duplicate owners, incomplete opposite pairs, missing garments, material closure failures and resource leakage. Test actual decoded fixture actors and guarded launch behavior. Run inherited phenotype regressions after shared changes.

Compile every selected part with its exact material dependencies present, using the pinned client/compiler and isolated directories. Independently decode native positions, normals, UVs, tangents and signs; compare them to the intended geometry and authored attributes. Verify complete fourteen-part ownership and the actual serialized material inventory. Declarative receipt fields do not establish attribute correctness.

Review a complete offline body from front, rear and both sides across both idle variants, walk/run stride extremes, casting, combat, crouch, kneel, damage and both death poses. Include close joint sections, garment boundaries, hand grip and soles. Produce animation sheets tied to the exact tested package hashes.

Visible holes, detached parts, incorrect anatomy, wrong/oversized garments, palette bleed, unexplained material seams and new equipment problems block selection. Fix the responsible candidate and repeat affected checks. Hidden microdefects require independent measurements, direct visual review, disclosure and an explicit practical-quality decision; another phenotype's exceptions do not transfer.

## 7. Validate matched fixtures in the actual client

Verify a supported capture/control path before claiming client validation. Build separate matched stock and candidate fixtures with decoded actors of the declared identity, isolated user directories, empty overrides and unlocked cameras. Bind the native IFO/HAK and direct launcher load to the fixture's declared module name. Hash and preflight the actual installed client, package bytes, resource inventories and effective dependencies before loading.

Cover all of the following with actual observations and literal client captures:

- The target palettes (Human female example: 3 and 8), neutral/directional lighting and ordinary/HQ shader paths.
- Sustained walk/run, casting/combat, crouch/kneel transitions, damage, death/resurrection and floor placement.
- Clothing, light/heavy armor, boots-only, gloves-only, robe, helmet and representative weapons/shields. Record which candidate regions remain visible for each combination and verify installed identity sizing or approved retargeted profiles.
- Character creation/loading and at least 900 seconds of continuous gameplay observation; retain logs, responding-process checks, resource measurements and observed performance.

Prepare literal-client animation sheets bound to exact package hashes, alongside the offline sheets. Scheduled actions, native GFF bytes, launch success and log messages do not prove visible motion or performance.

If capture/control is unavailable, preserve the independently verified offline/native work. Record the missing supported path as the blocking condition for client acceptance, final approval and PR publication. Do not mark full validation complete or publish a partial body under a full-validation claim. Distinguish measured practical limits from unresolved required gates.

## 8. Integrate the exact tested package and prepare final review

After client acceptance, promote the exact tested assets into the target pack. Hash every existing unrelated/non-target asset before and after; require preservation. Keep generated masters, downloads and built HAKs outside Git. Add a target manifest, provenance, source/native/client evidence links, practical limits, checkpoint, runbook and delivery record. Include this reusable plan and its goal prompt when required by the task.

Bring the branch up to date with the intended PR base, resolve conflicts and repeat affected validation. Run repository checks required by contribution rules and CI, including `Test-Repository.ps1 -AllPacks`, `Test-ItemImportTools.ps1` and the phenotype suite for this repository. Build the production HAK and compare its actual payload against the candidate and existing manifests. Smoke-test the new selection and existing supported selections with that rebuilt production HAK.

Prepare the final commit, full diff, proposed PR title/body using the repository template, validation receipts, package hashes, offline/client animation sheets and disclosed limits. The review package must identify the exact implemented asset/tool revisions and any remaining gate; do not ask for approval of a vague future result.

## 9. Obtain final approval, publish and follow CI

Present the complete review package and request the user's explicit final approval to publish the PR. Until then, keep work local. After approval of those exact bytes, push the approved branch, open the PR against the declared destination/base, attach it to the chat and monitor CI. Fix failures and repeat affected checks. Implementation or asset changes after approval require renewed final approval before publication of the changed result.

Deliver the PR URL, final commit, validation status and disclosed limits. Do not merge without separate explicit authorization.

## Evidence and handoff checklist

Maintain an evidence index with exact pins and a status of pending, failed, passed or accepted for each gate. At minimum, include the source snapshot, target/stock receipts, tool/migration pins, common style approval, normalized six-view sources or literal external-donor views, generation reservation/submission/history or truthful external intake/provenance limits, masters and selected descendants, transform/mirror/repair/material/native audits, cumulative offline reviews, client fixture/preflight/capture/performance records, repository checks, production HAK inventories, non-target preservation, final approval and PR/CI delivery.

A resumable checkpoint states the current approved design, exact selected hashes, uncertain jobs and their recovery paths, available execution prerequisites, remaining gates and next action. Preserve historical evidence and label diagnostics honestly. A limitation is a measured accepted practical bound; a blocked gate is required work that remains incomplete. Neither becomes a passed gate by changing its label.

## Connector taper rule: no shelves

User rule: no shelves when tapering. A connector taper must form a continuous sloped transition between its measured starting and ending contours. Preserve the intended terminal depth/width; spread the transition across eligible anatomy instead of concentrating it into a short band. Do not multiply an existing flare in a way that leaves or introduces a flat shelf, rolled lip, cuff ledge or secondary shoulder at the join. Prefer an explicit endpoint profile, with only small smooth blends at its boundaries.

Review the actual geometry in matched front, side and rear views and in the affected animations before accepting a taper. A new visible shelf blocks that taper even if its numerical geometry checks pass. Preserve protected neighboring parts, garments, UVs, maps and authored normals with explicit lineage; source anatomical features and already approved shapes stay separately documented. Preserve previously approved geometry during separate texture calibration unless the user reopens the shape decision. This rule applies to every purpose-built phenotype connector.

## Explicit animation changes and native derivatives

Preserve installed animations by default. When the user explicitly requests an animation change, record the selected posture, inherited animation owners, affected races and phenotypes, and excluded controls before implementation. Keep static rig frames, head/neck, attachment and equipment sizing proofs separate from the animation overlay. Preserve untouched native controller payloads, original upper-body motion when requested, clip timing/events and inherited renderable ownership. A carrier dummy must not shadow an ancestor-owned robe or shoulder mesh. Use native float32 timestamp words to merge sampling grids, then validate continuous motion, planted soles, transitions and the declared race matrix in the actual client. Preserve male and mounted/joust controls when those are excluded from the authorized scope.

If the installed compiler fails a required native tangent check, preserve its original output and receipt. A bounded postcompile correction needs an explicit operation, a distinct descendant receipt, independent actual-byte replay and strict proof that every non-target byte remains exact. Keep source geometry, authored normals, UVs, handedness, material maps and compiler provenance intact. Never relabel the modified binary as the original compiled result or relax the failed check. Compare normal-mapped parent and descendant views before selection, and retain ordinary/HQ client checks as separate gates. Neutral CPU shading previews do not reproduce the game's shader quality paths.

Use finite visual evidence to assess material corrections. Uniform skin intensity offsets may improve stock-neck matching while leaving bright joint caps or garment-edge clipping visible. Keep the original texture parents and accepted geometry fixed; measure and review any local correction independently. A numerical donor rule is a screening measure, not proof of matching painted skin shading. Document unresolved donors, physical garment aliases and normal-map limits instead of silently treating them as skin or complete closure.

## Physical body-part end closure

Close every physical end opening on the body parts. Generated caps must use reviewed skin texture/color, explicit skin ownership and a verified UV donor with filter padding. Shape the caps and their joins against the measured stock anatomy and affected animations; preserve protected neighbors, garment coverage and the no-shelves rule.

Independently decode the actual serialized meshes and native attribute archives, recording each authority separately. Check literal edge incidence, opposed winding, degenerate faces and cap self/body crossings without coordinate rounding or an unrecorded weld. Reopen these checks after any geometry revision. Measure arithmetic-only archive splits explicitly against the actual serialized surface; keep inherited nonmanifold defects, moving-part contact and visual acceptance as separate gates. Closed topology alone creates no anatomy, material, client or production acceptance.
