# Purpose-built muscular Human male thigh pair validation

The user-selected **Hip crown taper** donor and its stock-frame right mirror are ready after first-round native/client validation on 2026-10-02 in NWN:EE89.8193.37-17. The inspected standing, locomotion, casting, combat and death views show covered, attached joins without a major open gap or hollow cap. The user permits minor pelvis-bottom irregularity limited to crouching. The pelvis and torso were preserved unchanged. This completes the thigh-pair pass, not the whole Human body or production deployment.

## Selected inputs and package

All paths below are relative to `output/phenotypes/purposebuilt-thigh-pilot-v1`.

| Input | SHA256 |
| --- | --- |
| `left-thigh-proximal-cap-v2-proof/refined-local.glb` | `5420a77d5e9d51b7841f678d12710ce335bab16ed5ad417ae49b67f1e2950ab6` |
| `right-thigh-v2-mirror-v1/mirrored-local.glb` | `3c002789b74bfb5e94392d7c557e3105924e078f0133c47d496b1c123764b980` |
| Immutable `comfy-v1/generated/textured_00001.glb` | `1e20a6f4983b207bb3457f74fc4bf5646a231e9d428ee4e54e4fed00e2411d83` |
| Native `pmh0_legl001.mdl` | `e82617d80230c5ac3496093de84bb01ceefdb16f2c25c4b96450cd995333126c` |
| Native `pmh0_legr001.mdl` | `cfd6d71f11594756fbb54a8710f3dc687f556c63bb69dde3a5998f7abef6f033` |

The canonical test HAK is `client-pair-v2-inspection-focus-v2/userdir/hak/srn_pheno_test.hak`, SHA256 **`050b010187d4f2188bfd19056043426bd3e3dbff71f83531dc0df80a111af866`**. All reviewed paired fixtures use its identical60 payloads. It contains the four current body replacements, their declared dependencies and an isolated private stock comparator. It is a test package, not a server release. `build-archive/<SHA256>` retains the exact packed artifacts.

Protected chest GLB stays `3ae78d023ba522d94c44d9914bac0b36f35b640c42b9532015575e5572161a50`; protected pelvis GLB stays `db0bdf16099068da3bb685bcb61ae93ebed115e6ddbae90990c0b55e59b8d98a`. Their10 accepted native files were copied byte-for-byte, never recompiled or refitted.

The four normalized references, source sheet, prompt and provenance are saved in the requested `D:/source/repos/SRN_HAKS/.tools/reference_images/normalized/purposebuilt-human-male-left-thigh-v1`. Completed local multiview job `23bb7cf6-ee38-4544-a611-ea0169057fe4` retains raw/remeshed/shape/textured masters and workflow/settings receipts. Do not resubmit it.

## Actual client checks

Each reviewed fixture has PNGs and save-time/window/screenshot-ID metadata under `client-evidence`. Metadata binds the actual HAK/module hashes. Logs are copied before owned-client replacement; the final running client's log is preserved as a snapshot. The final `client-evidence-index-v2/evidence-index.json` (SHA256 `57a48351c106099d4b4412105ec7c4286e480a29723eb5a8ccad9972aef7a4e8`) binds 25 reviewed screenshots across 14 actual fixtures. Its `final-validation-receipt.json` SHA256 is `eeedb9312555919f258a61b1f77dd87db2b3db5c00c2cb1020731aa9f9f96d5f`. These hashes bind saved artifacts; they are not retroactive capture-time hashes.

| Fixture | Observed evidence |
| --- | --- |
| `client-pair-v2-inspection-focus-v2` | Front standing and rear crouch with both selected thighs. |
| `client-pair-v2-idle-rear-fixed-v3`, `client-pair-v2-idle-side-fixed-v3` | Close rear/side standing, hip and knee overlap. |
| `client-pair-v2-walk-focus-v2` | Sustained walking, turns and closer stride; real moving-position logs. |
| `client-pair-v2-run-focus-v2`, `client-pair-v2-run-front-fixed-v3` | Side/front/rear sustained running and standing turns; covered hip/knee joins. Anatomical angle changes when the actor turns along the route. |
| `client-pair-v2-kneel-focus-v2` | Actual WORSHIP transitions, including raised/bent phases. Saved rear images do not prove a fully grounded kneel. Separate offline stock clip `kneel` at time1.0 verifies the deeply flexed pose. |
| `client-pair-v2-crouch-focus-v2` | Full rear crouch at gameplay distance; attached thighs and covered knees, accepted pelvis-bottom overlap retained. |
| `client-pair-v2-conjure2-focus-v2` | Full overhead CONJURE2, attached hip/knee joins. |
| `client-pair-v2-gameplay-fixed-v3` | Actual unarmed melee stance, Magic Missile VFX, damage, death orientations and resurrection cycles. Hit logs precede spell events; action3 confirms melee. |
| `client-pair-v2-cloth-v1`, `client-pair-v2-armor-v1` | Actual stock chest016 clothing and representative full armor at identity scale; covered waist/hip/knees. No resized armor resources. |
| `client-pair-v2-skin8-v1` | Both thighs recolor with surrounding skin versus palette3; fixed briefs remain dark. |

FPS was approximately59–61 in the small two-/three-specimen and gameplay fixtures. Multiple movement/combat cycles completed without a post-load crash. This supports practical local use, not crowded-server performance. The49,992-triangle detail budget per thigh remains explicit. Camera locks are false; wheel zoom and arrow rotation were exercised. Chat was collapsed through its observed centre triangle to expose the knees.

Rigid stock-shin and pelvis seams remain visible. Finite surface samples in `knee-overlap-audit-v2` find donor penetration shallower than stock in kneel and late running poses; the preliminary sparse stock-vertex audit is superseded. Client inspection found no major ordinary-motion protrusion warranting a distal edit. Do not thin the shaft or reopen the accepted pelvis to chase crouch-only coverage.

Screenshot `actual-dead-front.png` shows an actual prone corpse from rear/top; its filename is not an anatomical camera claim. WORSHIP images are transitions rather than proof of a grounded kneel. Dispatch logs alone were not counted as visual tests. Unobserved builds in fixture batch receipts remain build/audit evidence only.

## Geometry, materials and stock integrity

`final-v2-independent-validation-v1/validation.json` binds both actual FLOAT32 meshes:49,992 faces each, one outward closed manifold component, zero boundary/nonmanifold/winding/degenerate defects and zero genuine crossings. Independent stock-frame reflection verifies ordered positions, normals, tangent direction/handedness, reversed winding, UVs, material sampling and map bytes. Both retain20 microscopic inherited authored/geometric normal disagreements on16 source faces; no new selected-cap or mirror negatives.

The initial fit used one positive uniform scale0.571983653 and a proper rotation/placement. Muscular shaft width was retained rather than forced onto the stock surface. Only8 microscopic contact corners moved20µm for topology repair. The selected C1 crown taper changes the proximal connector; shaft through Z−10mm, knee height, UVs and maps stay exact. Normals use the local inverse Jacobian; tangents use its forward differential. The later centre-offset variant is unselected and excluded from native/client acceptance.

`left-selected-v2-native-shading-audit-v2`, `right-selected-v2-native-shading-audit-v2` and `native-limb-shading-helper-proof-v2` inspect actual compiled arrays. Source→ASCII corners are exact; source→binary P/N/UV are exact at FLOAT32 precision. Tangents are finite/unit, reflected within6.86e−7, with handedness exactly negated. Original2K color/normal PNG bytes are retained; PLT luminance, skin0 and normal TGA pixels are verified. Normal strength remains1. Source AO/MR, samplers and double-sided material flags are retained in GLB but not all represented by this native adapter; its representation is explicit in map-extraction receipts.

`stock-rig-native-provenance-v1/audit.json` verifies actual packed node child graphs, identity attachment transforms/static controllers, unchanged stock head/foot height1.9339157m and the real male `pmh0→a_ba` animation chain. Native parent back-pointer fields are not usable serialized offsets; the proof uses validated child arrays. No stock root/animation resource, female rig, former custom limb or resized Human equipment is packed. Actual package audits verify payload bytes/types, truthful independent compiler provenance, unchanged neighbours, male actors/appearance6, private stock comparator and empty override.

## Process improvements and continuation

Measure connector width/depth/centres and motion ownership, not height alone. Preserve masters and source attributes; separate uniform fitting, microscopic repair, cap operation and mirror as bound receipts. Use actual stock frames and geometry-only reflection; independently validate native tangents and opposite motion. Extract exact2K PNG bytes, compile new parts alone and compose verified neighbours without recompilation. Test the complete real package audit in addition to detached negative guards.

Five helper suites pass31 focused tests (mirror8, composition6, stage adapter5, cap field6, native shading6), with23 package negative probes and real compilation/package audits. These checks supplement the client observations. The generic stager freezes config/source/maps rather than independently freezing every recorded fit-receipt path; the final evidence proof rechecks the actual lineage. Preserve that distinction when carrying this method forward.

`launch_part_test_fixture.ps1` verifies actual package paths/hashes, current owned PID/argv and unlocked cameras, preflights settings, archives logs, waits for that process to exit and launches directly from `bin/win32` with an absolute isolated userdir. A missing fixture fails before stopping the client. No default-userdir fallback is used.

The active runbook/checkpoint now contain current sources/methods only. Prior bodies are preserved in a [dated historical archive](history/phenotype-operational-2026-10-03-004821-utc/README.md), outside the executable continuation path. The original kit README has a minimal banner to the current purpose-built process; its former content and assets are byte-preserved. Whole-body slicing/stretching recipes, unselected centre-offset caps and former custom limbs have no role in the selected package.

Preserve this completed pair with the accepted chest/pelvis. Remaining Human arms, shins/feet, final heads, broader armor/race/profile work and whole-body production gates are separate. One purpose-built shin followed by its independently validated mirror is the natural next part; it has not started.
