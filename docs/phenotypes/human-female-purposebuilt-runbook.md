# Human female purpose-built execution runbook

This runbook describes the current tool interfaces and required gates for `human-female-fit-purposebuilt-v1` on `codex/human-female-purposebuilt`. It is not an acceptance receipt. Resume from the [checkpoint](../phenotype-human-female-checkpoint.md) and the target's `selection-ledger.json`; those records select the current immutable inputs and descendants. Use the [reusable plan](purposebuilt-phenotype-plan-template.md) and [goal prompt](purposebuilt-phenotype-goal-prompt.md) for new targets.

## Fixed target and publication boundary

Use Human race/appearance 6, female gender 1, phenotype 0, `pfh0`, bare style001. Preserve installed female rig, attachments, animation chains, head/neck and freshly measured stock stature. The frozen measurement is **1.837937046 m**; the stock receipt remains authoritative. Working/runtime frames are identical and runtime scale is 1. Use stock identity-sized equipment and unchanged production tables.

The physique is athletic normal/Fit. Use the human-approved common chest style for skin tone, strong painted muscle shadows/highlights and detail across every donor, retaining natural volume and original maps. The latest user-supplied Meshy torso has an opaque charcoal bra with shoulder straps explicitly accepted by the user. Keep this design during measured stock fitting and motion review; the prior strapless source remains a frozen comparison candidate. Matching regular bikini-cut briefs retain a normal waistband, ordinary leg openings and standard rear coverage. Preserve prior approved images as ancestry; the current checkpoint/ledger identifies each fresh design descendant and its unresolved camera or reconstruction limits. Chest owns the bra and pelvis owns the briefs. Style/image approval does not approve reconstruction cameras, geometry, materials or client behavior.

Keep source Troll state read-only. Keep all work local until the exact complete body passes native/offline/client/repository validation and the user gives explicit final approval of the concrete review package. Then publish a PR to `main`; merging requires separate authorization.

## Portable environment binding

Discover the bundled Python through the available workspace dependency runtime or verified repository runtime configuration; never invoke a Windows Store `python.exe` shim. Discover the primary shared bank and verify actual tool/addon paths and hashes. Do not replace historical receipts or user preferences.

Fill these PowerShell variables from current verified execution inputs. The examples do not hardcode a machine installation and must not replace existing output directories.

```powershell
$taskRepo = '<female-worktree-absolute-path>'
$taskPython = '<bundled-workspace-python-absolute-path>'
$taskToolDirectory = '<verified-neverwinter-tool-bank-directory>'
$taskDecompiler = '<verified-nwnmdlcomp-absolute-path>'
$taskClient = '<verified-installed-nwmain.exe-absolute-path>'
$taskGameRoot = '<verified-client-installation-root>'
$taskToolchain = '<ignored-local-toolchain-binding-from-bind_shared_runtimes.py>'
$taskTargetRoot = Join-Path $taskRepo 'output/phenotypes/human-female-fit-purposebuilt-v1'
$taskMigration = Join-Path $taskTargetRoot 'tool-verification-local-v1/migration.json'
$taskTarget = Join-Path $taskTargetRoot 'stock-target-v1/target-contract.json'
$taskStock = Join-Path $taskTargetRoot 'stock'
Set-Location -LiteralPath $taskRepo

function Invoke-PhenotypeStage {
  param([string]$LaunchLeaf, [string]$Script, [string[]]$Arguments)
  $taskLaunch = Join-Path $taskTargetRoot $LaunchLeaf
  if (Test-Path -LiteralPath $taskLaunch) { throw 'Fresh launch output required' }
  & $taskPython -B (Join-Path $taskRepo 'tools/phenotypes/launch_shared_tool.py') `
    --toolchain $taskToolchain --migration-receipt $taskMigration `
    --tool python --output $taskLaunch -- -B `
    (Join-Path $taskRepo ('tools/phenotypes/'+$Script)) @Arguments
  if ($LASTEXITCODE -ne 0) { throw ('Stage failed; inspect '+$taskLaunch) }
}
```

The current local migration supersedes the initial read-only Troll configuration for new execution. Reverify its pin from the ledger before use. If its bank, helpers or configuration differ, create a new passed migration; do not rewrite `tool-verification-local-v1`. A tool path or addon version alone does not establish the loaded code. Blender execution uses the same shared launcher with `--tool blender`; it owns isolated factory background startup and the addon bootstrap.

## 1. Preserve inputs and production neighbors

Before promotion, retain the source snapshot and the independent target records. The frozen source is under `source-snapshot-v1`; inherited shared helper/config hashes are in `inherited-source.json`. Use the latest checkpoint rather than re-copying a live mutable source branch.

`non-target-preservation-baseline-v1/baseline.json` records all existing `srn_body` files with sizes, hashes, tracked status and recoverable copies. It independently checks the published male manifest. The current baseline has **72 resources, 527885123 bytes**, all non-target; no female target-owned resource existed at capture. Its `files/` tree is recovery evidence outside Git.

The female ownership allowlist is exact: fourteen `pfh0_<part>001` body units, each with `.mdl`, `.mtr`, `.plt`, `n.tga` and `r.tga`; chest/pelvis additionally own `f.mtr`, `f.tga`, `fn.tga`, `fr.tga`. This gives 78 expected female resources in the full-map adapter. Root/head/neck, other styles/phenotypes, equipment and tables are excluded. Preserve every other existing asset byte-for-byte. Existing target-named bytes, if introduced before a future baseline, also need recovery copies before replacement.

The PR scope proposal is under `pr-scope-review-v2`. It records actual local imports, literal helper references, focused test closure, cached refs and candidate paths. It is a review aid, not an instruction to stage every copied tool. Include required legacy rig/sampler/test interfaces when they are actual dependencies; this does not authorize Troll body assets, selections or delivery evidence. Recheck dynamic imports, executed helper snapshots and clean-checkout closure at final integration. Keep `output/`, `.tools/`, generation masters and built HAK/MOD archives outside Git.

## 2. Fresh installed stock basis and equipment

Use an isolated source user directory with an empty `override/`. Extract with overrides disabled. For a new extraction revision, use fresh output paths, never the existing frozen `stock/` or `stock-target-v1/`.

```powershell
Invoke-PhenotypeStage -LaunchLeaf 'stock-extraction-launch-vN' -Script 'baseline.py' -Arguments @(
  '--game-root',$taskGameRoot,'--user-directory','<isolated-empty-override-userdir>',
  '--tool-directory',$taskToolDirectory,'--output','<fresh-stock-baseline-output>')

Invoke-PhenotypeStage -LaunchLeaf 'stock-target-launch-vN' -Script 'freeze_stock_target.py' -Arguments @(
  '--stock-baseline','<fresh-stock-baseline-output>','--output','<fresh-stock-target-output>',
  '--gender','female','--target-id','human-female-fit-purposebuilt-v1')

Invoke-PhenotypeStage -LaunchLeaf 'equipment-inventory-launch-vN' -Script 'inventory_target_equipment.py' -Arguments @(
  '--game-root',$taskGameRoot,'--user-directory','<isolated-empty-override-userdir>',
  '--tool-directory',$taskToolDirectory,'--decompiler',$taskDecompiler,
  '--source-prefix','pfh0','--workers','4','--output','<fresh-equipment-inventory-output>')

Invoke-PhenotypeStage -LaunchLeaf 'held-measurements-launch-vN' -Script 'measure_held_equipment.py' -Arguments @(
  '--inventory','<verified-equipment-inventory.json>','--tool-directory',$taskToolDirectory,
  '--decompiler',$taskDecompiler,'--target-contract',$taskTarget,
  '--stock-baseline',(Join-Path $taskStock 'baseline.json'),'--output','<fresh-held-measurements-output>')

Invoke-PhenotypeStage -LaunchLeaf 'stock-basis-launch-vN' -Script 'measure_stock_target_basis.py' -Arguments @(
  '--target-contract',$taskTarget,'--stock-baseline',$taskStock,
  '--equipment-inventory','<verified-equipment-inventory.json>',
  '--held-measurements','<verified-held-measurements.json>','--output','<fresh-stock-basis-output>')
```

Freeze extraction origins, native/decompiled hashes, root and inherited chain, sixteen standard parts, head/neck materials, palettes and tables. Retain measured frames, stock height, joint sections, body contours, limbs, soles and held-equipment frames. Bounds and table sizes are not collision/grip/motion acceptance. Stock-exact mode never invokes a private-rig export or equipment resizing path.

`build_target_diagnostic.py --target-contract <target> --baseline <stock> --coordinate-space working|runtime --output <fresh-dir>` prepares byte-exact stock fallback diagnostics on this mode; omit `--rig`. Identify each fallback clearly. Diagnostic copying is not a selected donor or runtime conversion.

## 3. References and approved common style

Preserve approved chest/pelvis sources and every attempt with prompts, ancestry, hashes and approval. Obtain coherent isolated donor sheets in the agreed order: chest, pelvis, left upper arm, left thigh, left shin, left foot, left forearm, left hand. Each source must provide actual front/left/back/right/top/bottom cameras; inspect anatomical anterior/posterior and left/right visually in every panel and verify how anterior projects into top/bottom image axes. Top/bottom must be whole-object orthographic end projections of the full donor volume, not cross-sectional slices or cut-surface diagrams. Record generator/world, donor-local and target direction/right/up bases and the explicit semantic permutation to the adapter slots. Do not infer those slots from written labels or a correct-looking cardinal sheet.

Measure cross-view projected silhouette consistency under one isotropic scale, including corresponding widths/heights and anterior/posterior depth envelopes. Record alignment tolerances, overlays and discrepancies; end views must represent the same complete object's projected volume as the cardinals. Reproject the reconstructed donor into all six approved bases before fitting/selection. A depth or volume mismatch must be explained and corrected; stretching a panel or relying on four plausible cardinal views cannot clear the gate. Correct repeated sides, tilted axial cameras, reversed semantics, anatomy, ownership and coverage before reconstruction.

### Open female camera issue

Reference v6 asked for cross-sections and projected away anterior torso volume. The resulting chest was observed approximately 10% shallower than the approved cardinal guidance. The reviewed adapter front is generator world -Y; anatomical anterior projects DOWN in the top image and UP in the bottom image. Current side panels may occupy the opposite adapter slots. These are open camera/volume issues requiring whole-object end projections, explicit reviewed slot permutation and six-basis silhouette measurements. This observation does not accept a reconstructed female body. Preserve the failed reference/reconstruction receipts and create corrected reviewed descendants.

Use `normalize_part_turnaround.py` with the actual observed row-major `--view-order`, `--six-views`, reviewed layout and source mask method. Options include `--layout-components`, `--layout-columns 2|3`, `--center-origin`, `--opaque-black-background` and `--axial-source`. An auxiliary axial source changes only its declared row; preserve the primary cardinal source bytes. Record shared isotropic scale, explicit semantic permutation and orthographic camera bases, and repeat the six-view anatomical/projection consistency gate. These options do not correct an incorrect camera photograph or cross-sectional slice.

A representative invocation after visual approval is:

```powershell
Invoke-PhenotypeStage -LaunchLeaf 'chest-normalization-launch-vN' -Script 'normalize_part_turnaround.py' -Arguments @(
  '--source','<approved-six-view-source.png>','--output','<fresh-normalized-views>',
  '--six-views','--layout-components','--center-origin','--opaque-black-background',
  '--layout-columns','2','--view-order','<actual-row-major-camera-order>',
  '--notes','<source approval, camera review and garment ownership evidence>')
```

Use the available authorized reference generator and preserve its receipts. Image/reference production and the 3D multi-view workflow are separate stages. A fallback image workflow must be explicitly authorized and its actual graph/model configuration frozen; do not silently change the saved live workflow.

## 4. Purpose-built generation and recovery

Use the actual `SR_NWN_3d_pixal3d_multi_views` workflow and reviewed six-view adapter. Prepare an explicit target-bound configuration with 1024 reference/shape resolution, 50000 compact triangles, 2K maps, normal strength 1, frozen seeds/remesh settings and a reviewed ortho span. Retain workflow/schema, model/dependency hashes and raw/remeshed/compact/textured masters.

```powershell
Invoke-PhenotypeStage -LaunchLeaf 'chest-generation-prepare-launch-vN' -Script 'generate_purpose_built_part.py' -Arguments @(
  'prepare','--config','<reviewed-target-bound-part-config.json>',
  '--views-dir','<approved-normalized-views>','--output','<fresh-generation-directory>')

# Only after reference/configuration review and queue/reservation checks:
Invoke-PhenotypeStage -LaunchLeaf 'chest-generation-submit-launch-vN' -Script 'generate_purpose_built_part.py' -Arguments @(
  'submit','--output','<same-prepared-generation-directory>')

# Status/recovery reads the preserved submission rather than queuing another job:
Invoke-PhenotypeStage -LaunchLeaf 'chest-generation-status-launch-vN' -Script 'generate_purpose_built_part.py' -Arguments @(
  'status','--output','<same-prepared-generation-directory>')
```

The generator preserves a submission reservation, persisted client ID and exact graph before dispatch. Observe the shared queue and submit once. Recover uncertain responses from those records, prompt IDs, queue/history and exact graph/client-ID matching before retrying. Use fresh launch directories for status calls. Preserve downloaded outputs by hash and do not overwrite uncertain or rejected attempts.

## 5. Fit, ownership, repair and bilateral review

`target_part_pipeline.py --config <reviewed-config> --output <fresh-dir>` implements explicit fit, runtime and mirror operations. Fit in working space using positive uniform scale, proper rotation and translation into measured frames. Record the one runtime operation even when it is identity; reject a second conversion. Mirror detached selected limbs through actual opposite frames with an explicit measured plane. Independently check winding, authored normals, tangent signs/handedness, UV sampling, anatomy and bilateral motion.

Use `target_garment_ownership.py --mode propose|apply --config <reviewed-config> --output <fresh-dir>` for explicit face ownership when the donor shares one material. Inspect proposal masks and approve a selection before apply. Preserve original BIN, attribute accessors, material/map ancestry and complete face coverage. Keep bra/chest and regular bikini briefs/pelvis ownership exact.

Inspect all meshes for anatomy, disconnected components, wall thickness, topology, crossings and maps; inspect foot undersides/five toes and hand fingers/thumb/grip explicitly. `repair_target_part_faces.py --config <reviewed-measured-repair> --output <fresh-dir>` is for bounded measured defects. A repair is a descendant, not an edit to a selected parent.

Add each donor to a cumulative assembly and preserve selected neighbor hashes during trials. Review chest/pelvis/both upper arms together before continuing. Use current generic target pose/stock fallback and native-material bridge paths. Historical pilot material renderers and skin-only AO diagnostics do not by themselves cover cloth or all fourteen body parts; extend or select a verified full-body path before using them as evidence.

## 6. Original materials, native composition and audits

Stage each source through `target_part_stage.py --config <reviewed-stage-config> --output <fresh-dir>`. Preserve original maps, normal pixels at strength 1, UVs and authored normals. Skin is recolorable PLT; cloth is fixed opaque. Transport authored ORM-green roughness through texture3 with `Roughness 0`. Compare AO 0, 0.15 and 0.35 from the same untreated parent in assembled review. Verify skin continuity and stock female neck matching; record calibration separately from original compiler inputs.

Compose the exact selected runtime receipts, then compile with dependencies present:

```powershell
Invoke-PhenotypeStage -LaunchLeaf 'body-compose-launch-vN' -Script 'target_body_inventory.py' -Arguments @(
  '--target-contract',$taskTarget,'--coordinate-space','runtime','--complete',
  '--stage-receipt','<chest-target-stage.json>','--stage-receipt','<pelvis-target-stage.json>',
  '<repeat --stage-receipt with all twelve detached bilateral limb receipts>',
  '--output','<fresh-complete-body-composition>')

Invoke-PhenotypeStage -LaunchLeaf 'body-native-compile-launch-vN' -Script 'native_compile.py' -Arguments @(
  '--client',$taskClient,'--user-directory','<isolated-compiler-userdir>',
  '--converted','<complete-body-composition>','--with-material-resources')
```

Replace the explanatory repeated-receipt placeholder with actual argument pairs; do not pass it literally. `--reuse-from` is allowed only when the compiler independently verifies identical source/client/material dependency hashes. Compiler execution is not interactive client acceptance.

Use `audit_target_native_part.py --config <pinned-native-audit-config> --output <fresh-dir>` for independent native position/normal/UV/tangent/sign and material transport checks. Use generic connector, native cap and joint-band audits as appropriate to measured defects; freeze their inputs and actual helper snapshots. Verify the complete body has fourteen owners, six opposite pairs, both garments and exactly the supported 78-resource closure. Receipt declarations do not substitute for serialized/native or visual evidence.

Offline review must cover front/rear/both sides, both idle clips, walk/run extremes, casting/combat, crouch/kneel, damage and both death poses, with close joints/garment boundaries/hands/soles. Produce animation sheets tied to exact candidate/package hashes. Native/Blender approximations and hidden measured defects remain explicitly disclosed.

## 7. Matched native fixtures and guarded client observation

`target_fixture.py` prepares native source modules only. On stock-exact female targets it creates six profiles: stock/candidate × poses/palette/matrix, with female normal Human actors, palettes 3 and 8 and module name `srn_female_test`.

```powershell
Invoke-PhenotypeStage -LaunchLeaf 'female-fixture-sources-launch-vN' -Script 'target_fixture.py' -Arguments @(
  '--target-contract',$taskTarget,'--stock-baseline',$taskStock,
  '--tool-directory',$taskToolDirectory,'--game-root',$taskGameRoot,
  '--source-userdir','<isolated-empty-override-source-userdir>',
  '--output','<fresh-fixture-source-root>','--skin-index','3','--alternate-skin-index','8')

Invoke-PhenotypeStage -LaunchLeaf 'female-candidate-fixture-pack-launch-vN' -Script 'pack_stock_target_fixture.py' -Arguments @(
  '--target-contract',$taskTarget,'--prepared-fixture','<candidate-profile/test-module/preparation.json>',
  '--prepared-sha256','<reviewed-preparation-receipt-sha256>',
  '--tool-directory',$taskToolDirectory,'--game-root',$taskGameRoot,
  '--body-converted','<verified-complete-native-body-composition>',
  '--output','<fresh-candidate-fixture-inside-target-output>')
```

For a stock comparator select its stock profile and omit `--body-converted`. Stock fixtures pack no candidate body. Candidate fixtures require all fourteen native parts. Neither path replaces the installed rig/head/neck/tables/equipment. The source modules are diagnostic until packaging, preflight and actual observation pass.

The current idempotent source/package revision is v2. It retains one initialization per actor; an engine spawn before module entry may start pose mode, then transition once to matrix mode. Same-mode reentry does not restart actions or counters; changing mode clears actions and invalidates delayed phase callbacks. Preserve v1 evidence and do not silently replace packages already observed in the client. Native compilation and source tests establish intended scheduling; actual logs/captures must verify it.

Preflight and launch through the guarded target-aware PowerShell interface:

```powershell
$taskFixture = '<reviewed-stock-or-candidate-fixture-directory>'
$taskFixtureReceiptSha = '<reviewed-test-module-receipt-sha256>'
& (Join-Path $taskRepo 'tools/phenotypes/Launch-TargetBodyClient.ps1') `
  -TargetContract $taskTarget -Fixture $taskFixture -ReceiptSha256 $taskFixtureReceiptSha `
  -Client $taskClient -WorkspacePython $taskPython `
  -Toolchain $taskToolchain -MigrationReceipt $taskMigration -NoLaunch
```

`-NoLaunch` checks native actor identity, exact payload ownership, empty overrides/isolated aliases, current installed stock dependency bytes, unchanged tables, identity equipment and native IFO/HAK/module-name binding. It does not observe the game. Actual loading omits `-NoLaunch` only at the authorized client stage and uses the fixture's declared module name; do not use the Human male launcher's hardcoded module. Observe ownership of any already running client before replacing it.

Confirm a supported capture/control path. Cover palettes 3/8, neutral/directional lighting, ordinary/HQ shaders, all required motions/transitions, damage, death/resurrection, soles/floor placement, character creation/load and at least 900 continuous observed gameplay seconds. Add representative clothing/light/heavy armor, boots-only, gloves-only, robe, helmet and weapons/shields; record the visible candidate regions for each. Retain exact tested package hashes, literal-client sheets, logs, responding-process checks and performance/resource measurements. Source preparation currently leaves lighting/settings/equipment observations pending; native stock fixture success does not establish those gates.

Visible holes/detachment, wrong anatomy or garment cut/coverage, giant briefs, palette bleed, unexplained seams or new equipment problems block selection. Repair the responsible descendant and repeat affected checks. Hidden microdefects need measurements, direct review and disclosed practical limits. If capture/control cannot be verified, retain offline/native work and leave client acceptance, final approval and PR publication pending.

## 8. Repository promotion and complete review package

After candidate client acceptance, promote only the exact tested 78-resource female inventory into `srn_body`, preserving every baseline non-target hash. Verify the current male manifest and a new female manifest against actual source/native/package bytes. Curate source/native/client evidence and practical limits into tracked documentation; keep full masters, downloaded tools and built packages local.

At final integration, update from `main`, resolve conflicts and repeat affected checks. Local `main` and cached `origin/main` were equal to source HEAD at scope capture; this is not a current remote check. Reassess source/test closure using actual executed stages and validate the eventual committed changes from a clean checkout, so untracked inherited tools cannot conceal missing release dependencies.

Run the required repository checks and phenotype suite with bundled Python and the verified launcher:

```powershell
pwsh -NoProfile -File ./tools/Test-Repository.ps1 -AllPacks
pwsh -NoProfile -File ./tools/Test-ItemImportTools.ps1
# From tools/phenotypes, through the verified shared Python launcher:
# -B -m unittest discover -p 'test_*.py'
```

Run tests when shared changes have settled, inspect actual failures and retain receipts. Build the production `srn_body.hak` using the registered repository build interface, independently inspect actual payloads against both manifests and smoke-test female and existing male Human selections with that rebuilt production HAK. A folder inventory is not an archive inventory. Retain flat-pack/resource-name/size-policy checks and all cross-pack ownership rules.

Before requesting final approval, prepare the final commit, full diff, PR title/body following the repository template, validated manifests, preservation proof, tool/native/client/repository receipts, exact production package hashes, offline/literal-client sheets and limitations. Include the reusable plan and goal prompt in the same reviewed PR. Present that concrete package; unresolved required gates keep approval/publication pending.

After explicit approval of the exact result, push `codex/human-female-purposebuilt`, open the PR against `main`, attach it to the chat and monitor CI. Resolve failures and repeat affected checks. Asset or implementation changes after approval require renewed final approval. Merging is a separate action.

## Evidence stages to retain

| Stage | Evidence and gate |
|---|---|
| Source and preservation | Source snapshot/inherited hashes, recoverable production baseline, published manifest verification |
| Runtime/tool bank | Execution inputs, local config/migration pins, verified launches and actual loaded addon modules |
| Installed basis | Fresh extraction/origins, stock proof/contract, measured sections/frames/equipment/soles |
| Common style/cameras | Human approval, exact sources/prompts/ancestry, six-camera reviews and normalization provenance |
| Reconstruction | Reservation, persisted client ID/exact API graph, prompt ID/queue/history, model/dependency/seed/remesh pins and masters |
| Donor selection | Anatomy/topology/maps, fit/runtime/mirror/repair/ownership proofs and cumulative neighbor hashes/reviews |
| Materials/native | Untreated parents/AO comparison/calibration, exact material closure, native compilation/attribute and connector audits |
| Offline assembly | All-pose/joint/garment/grip/sole sheets tied to exact selected package hashes and disclosed approximations |
| Literal client | Matched fixture/native GFF/preflight, supported captures, settings/palettes/lighting/equipment, 900-second observation/log/performance records |
| Production/repository | Exact tested promotion, non-target preservation, both manifests, final closure/clean-checkout checks, rebuilt HAK payload and regression smoke tests |
| Review/delivery | Exact commit/diff/PR draft, final approval, published PR/attachment, CI status and practical limits |

Keep passed checks, accepted visual decisions, measured limits and blocked required gates distinct. Never convert scheduled actions, generated images, native declarations or logs into a client acceptance claim. Update the checkpoint/ledger through their owner and preserve immutable historical evidence.

## External donors and local anatomical revisions

Freeze user-supplied Meshy/static GLBs with an honest external intake, exact source/origin/target/part hashes, decoded geometry/material inventory and original embedded image copies. Record unavailable prompts/models/seeds/raw/remeshed masters; never invent a Comfy generation receipt. No external rig or animation imports. Initial fitting remains positive uniform scale, proper rotation and translation; later authorized width/taper/rounding or topology trims are separately measured descendants with bounded support, positive Jacobian where applicable, protected cloth/central anatomy, authored normal/tangent transport, original maps/UV and unchanged neighbor proofs.

Preserve old shared helpers and receipts byte-exact. New helper versions require explicit additive archival replay/migration proofs; never rehash historical evidence to live files. Review actual isolated specimens so side-by-side occlusion does not establish false holes. User accepts .78 central thigh width and requests upper pelvis taper, lower stub trimming/rounding and hip/elbow polishing. All final native/client/approval/PR gates remain unchanged.

## Connector taper rule: no shelves

User rule: no shelves when tapering. A connector taper must form a continuous sloped transition between its measured starting and ending contours. Preserve the intended terminal depth/width; spread the transition across eligible anatomy instead of concentrating it into a short band. Do not multiply an existing flare in a way that leaves or introduces a flat shelf, rolled lip, cuff ledge or secondary shoulder at the join. Prefer an explicit endpoint profile, with only small smooth blends at its boundaries.

Review the actual geometry in matched front, side and rear views and in the affected animations before accepting a taper. A new visible shelf blocks that taper even if its numerical geometry checks pass. Preserve protected neighboring parts, garments, UVs, maps and authored normals with explicit lineage; source anatomical features and already approved shapes stay separately documented. The current user-approved ankle shape is preserved while its texture seam is corrected. This rule applies to future phenotype connectors as well as the ongoing torso correction.


## Uniform upper-arm size correction

Current user direction: reduce both upper arms' girth by10% uniformly in the radial plane about each installed shoulder-to-elbow axis. Keep axial projections, length, joint centres and frames fixed. Use .90I+.10aa^T about each shoulder centre with a the unit bone axis. There is no taper or protection band on these arms. Preserve material/UV/source attributes with correct covector transport and exact lineage; measure shoulder/elbow coverage separately rather than silently changing the requested field.


Additional uniform biceps sizing: user requests another10% in ALL3 axes atop radial90. Use literal respective installed shoulder-elbow midpoint; stock rig/frame/stature/equipment unchanged. Current working descendants de7c7c1d/ad0af137, independent rawGLB proofec2aee9d,12 matched directN images366079d2, bankv5/615pins. Total original radial.81/axial.90; length379.527→341.574mm. No taper/cap repair. Join coverage reopens because mesh ends retreat20.660/17.293mm; keep this sizing while correcting measured forearm/chest neighbors. User-facing frontpair shown, no fullbody/native/client/PR approval. Favored ankle baseline unchanged. Nativecontroller10focused+562inherited tests pass; replayable ankle staging interface remains a separate shared decision.

User shape feedback: 'biceps are looking good'. Freeze exact additionaluniform90 biceps de7c/ad0a and originalN/UV/maps as the favored shape baseline. Repair measured forearm/chest joins around this geometry; this is not fullbody/native/client/publication approval.

Waist user direction: rejected pinched coupled trial c737d0d5 never exported. Keep current broader bankv5 waist unchanged; user says 'don't worry about the waist defects' and requests fixing all OTHER joint alignment issues. Stop further waist repairs. Document known waist cap/collar artifacts as practical limits. Fix neck/shoulder/elbow/wrist/hip/knee joins with favored biceps/ankles/.78 thigh shaft/hand grip/stock rig intact. Latest two fullbody views624c7cc6 shown; no finalbody/native/client or PR approval.

Checkpoint v17: preserve user-fixed waist. Other elbow/wrist/hip/knee/neck polish remains in measured diagnostic review, no new working exports or selection. Shared source-detail dispatch0a164d71 and580-test suitea5eb1502 are verified; no candidate native/client acceptance. Use the v17 ledger evidence and preserve all failed/executed trials.

Checkpoint v18: bankv6 forearm repairs integrated (4af49233/637pins), fixedwaist/12otherowners exact. Combinedneck export, quadratic knees, wrists and hips remain pendingworkingreview. Original-source chest face ownershipb2e25e38/strictvalidationb07bf4bd approved; no finaldescendant/body/native/client/PRacceptance. See concise v18 checkpoint and preserved v17 copies for detailed immutable history.

Checkpointv19 currentoverride: user requests chest1.10Z height andneck/shoulder/waistrealignment from workingbankv7/409d44b1. PreviouswaistSTOP superseded onlyforchestregistration; widerwaistX/Y/rejectedpinch unchanged. See currentcheckpoint/ledger; noheightassetexport or finalapproval yet.

Checkpointv20supersedesv19: whole1.10Ztorso rejectedandneverexported; latestuserrequests rigid smallchestZrise pluslowerwaistgradualdownstretch fromworking409d44b1/bankv7. Alsoremove persistentfemalehipposture: trace actualanimationbias first, noanimationwritesyet. Seev20currentledger/checkpoint; finalvalidation/PRapprovalpending.

Checkpointv21: bankv10 integrates the user-approved10mm rigid torso rise/20mm lower-waist extension, wrists and C2 knees. User chose level hips with originalupperlean for all sharedfemale races; actual animation/native/client coverage pending. See current checkpoint/ledger for exact receipts and remaining pelvis/material gates.

Checkpoint v22: bankv10 unchanged; current torso ownership reviewed and working-native compile completed, but strict tangent audit failed. Calibration provisional,616inherited tests pass. User-selected global levelhips/originalupperlean uses proposed12root+12carrier overlay; one Human pilot only. Pelvis connected-track restoration/material closure pending. See current checkpoint/ledger; no native/client/final publication acceptance.

Checkpoint v23: bankv10 unchanged; actual T-only torso derivative and current bicepl/handr strict native audits pass. Root reviewed assembled palette controls; knee-cap bands and pelvis material/geometry closure remain pending. One Human animation native payload derivative preserves original upper-body arrays; final source-native family curves and literal-client pilot still pending. See current checkpoint/ledger. No runtime/fullbody/client/production/final publication acceptance.

Restart checkpoint v24: user requested pause for app restart. No active task jobs; Human final source-native compile not dispatched. Finalize hips-level/original-upper-lean native and client correction across shared female standing races before any further hip/thigh/torso adjustments. Exact resume sequence/evidence in ledger restartCheckpoint. Body bankv10 unchanged; pelvis numeric trial visually rejected/unexported, material proposals frozen;645tests passed. No final/runtime/client/production/publication acceptance.
