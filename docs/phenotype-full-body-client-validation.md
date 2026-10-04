# Complete Human male client validation

Updated 2026-10-03. The latest user direction authorizes automated NWN:EE tests
after the complete body is ready and requires a full-body animation reference
sheet. The practical hand work is closed; finish validation and delivery without
further cosmetic source trials. Root owns client control, packaging and local GPU
scheduling. The practical complete Human male validation pass is finished and
ready for user review with the limits below. This records completed offline and
actual client work, superseding its earlier pending/unexecuted-only description. Use the
[checkpoint](phenotype-goal-checkpoint.md) for later evidence. No purging is authorized.

## Readiness and package identity

The final body contains fourteen custom style001 Human male parts: chest, pelvis,
and both upper arms, forearms, gripping hands, thighs, shins and feet. Its actual
body-only inventory must contain exactly 72 declared resources: five per part
plus the accepted pelvis fixed-underwear material and texture. Stock neck and
provisional head remain installed references. Preserve the 32 accepted-six
resource bytes, original male rig/controllers, measured 1.9339157 m bind height
and Human equipment identity sizing. Bare shoulder/belt styles remain 0; optional
stock equipment shoulders are separate coverage cases.

`effective_body_contract.py` must validate actual native bytes, source ASCII,
compiler ancestry, material bindings and `completeBodySelected=true`. Both hand
native gates, cumulative offline poses and practical equipment review are complete.
The isolated test HAK also contains declared stock comparison and fixture
resources, so its total is larger than the 72-resource production body.

The retained `native-twelve-v1` HAK is partial history: twelve models, 62 resources,
SHA256 `b405fefd5fca901f86c079b1e2530294da320fd1210dd33dd9eba0d7afc93213`.
It lacks the new gripping hands and must not become the final test authority.
Both the final-sheet builder and pose-batch helper reject that actual inventory.

| Final evidence item | Current status |
| --- | --- |
| Complete14 inventory and body-only HAK | `human-male-complete-goal-v1/native-fourteen-v1`: fourteen parts/72 resources; all native12 62 and accepted-six 32 bytes exact. HAK SHA256 `01524cd39ad111021d30ba9a7c2241fdf8ef3afc7eb77f04346907d423d9f7c2`. |
| Isolated fixture and preflight | `client-fourteen-skin3-motion-v2`: reviewed 114-resource test HAK, exact current body binding, private stock comparator and unlocked camera. Per-run MOD/receipt hashes belong to the actual launch, not a later rebuild. |
| Whole-body offline images/sheet | Eight primary custom views and 42 stock/custom comparison views completed in upperarm pilot `final-fourteen-pose-batch-v1`; completed sheet in goal `offline-animation-reference-v1`. |
| Runtime palette3/original lighting, PID40868 | More than 17 minutes: actual melee, Magic Missile, death/resurrection and transitions, camera and floor checks observed. |
| Runtime palette8/directional lighting, PID26740 | About eight minutes: 12 m walking route and running return, crouch and cast observed; skin definition and fixed cloth preserved. |
| Final kneeling/side inspection, PID48948 | Completed held `WORSHIP` cycle, including arm-raised and bowing phases from the side. Whole-body framing and caps were practically reviewed. |
| Eight-category actual client sheet and consolidated validation | Complete in goal `client-animation-reference-v2` and `client-validation-v1.json`; eight reviewed observation receipts and filtered logs in `client-reviewed-evidence-v1` bind all three actual runs and package hashes. |

Current inventory SHA256 is
`cc1f7a2c3a8c561311625db85af56995efe6b2a7e4a3767ec581be716d2b3304`.
Both hands have exact native P/N/UV FLOAT32 transport and completed tangent/sign
and material dependency audits. Independent final14/material/fixture peer
receipts are in the upperarm pilot. Passed native audits need no repetition for
camera or module-only revisions. Historical native8/native12 and protocol-only
receipts remain preparation history; completed execution receipts are current.

## Direct launch and isolation

For user review, use the goal's
[Launch-HumanMale.ps1](phenotypes/evidence/human-male-complete-goal-v1/Launch-HumanMale.ps1).
Its default `Motion` restores the exact tested PID26740 module/receipt;
`-Mode Gameplay` selects PID40868 and `-Mode Kneel` selects PID48948.
Each selection checks the archived receipt, MOD and shared HAK hashes before
restoring that tested fixture. `-NoLaunch` selects and verifies without opening
the client. The current selection is `Motion`, recorded in
`client-fixture-selection.json`; the final delivery preflight passed with
`clientLaunched=false`. Wrapper SHA256:
`36262a3c451328906676c3eb9f5dbf33d8786c6cc55e795ef18caf7a4d7db384`.

The wrapper delegates to
[Launch-CompleteBodyClient.ps1](../tools/phenotypes/Launch-CompleteBodyClient.ps1).
For a fresh controlled fixture, that lower-level launcher accepts its directory
and the reviewed SHA256 of its actual `test-module/receipt.json`:

```powershell
& 'D:\srwt\codex\f0b3\SRN_HAKS\tools\phenotypes\Launch-CompleteBodyClient.ps1' `
  -Fixture '<final fixture inside human-male-complete-goal-v1>' `
  -ReceiptSha256 '<reviewed actual fixture receipt SHA256>'
```

This is reusable invocation syntax; actual launches are now complete. The
launcher uses bundled workspace Python
for [preflight](../tools/phenotypes/preflight_complete_body_client.py), then opens
the authorized interactive client directly with
`-userdirectory "<isolated userdir>" +TestNewModule srn_pheno_test`. Do not navigate
menus or reuse an old part-specific launcher/selector.

Preflight verifies the complete current body, accepted bytes, actual packed HAK
payload, fixture material binding, matching compiler/client executable, unlocked
camera configuration and isolated resource aliases. Its userdir has one declared
test HAK, one module and an empty override; no animation/female or extra Human
body overrides may be packed. Keep production resource directories untouched.
The stock comparator uses actual `pmh0_handl003` palettes for both hands and
`pmh0_belt003` for its belt; private `pmx0` aliases change names/bitmap bindings
only. Original appearance rows remain exact; comparator row15100 is fixture-only.

The current launcher uses `Get-Process` for its existing-client guard. It refuses
to launch over an existing `nwmain.exe`. Observe process
ownership first. Before any root-owned unload/relaunch, match the current PID,
executable and exact isolated userdir command line to the launch receipt and
archive logs. Never terminate all clients by process name or trust a historical
PID. Record actual window visibility and observe camera controls separately;
`cameraLocked=false` in a receipt is configuration evidence, not that observation.
Successful interactive launches ran outside the filesystem sandbox and produced
a visible `Skywindow`; an audio-only process does not establish visible-window
success. Wheel zoom visibly changed framing in these runs. Keyboard pan injection
did not independently establish reliable turning; the side inspection used the
fixture's explicit 180-degree facing. Do not claim pan was visually verified
from attempted key presses or unlocked configuration alone.

Each fresh launch records PID/time, userdir, working directory, actual HAK/MOD,
client, fixture receipt, preflight and launcher SHA256 values. Preflight separately
records body resource hashes and its executed code hash. Pin settings/quality and
captured logs too. The current actual launcher SHA256 is
`8c799f026ca3792f4a34c0559fe35c8c1ff1eb0b2c543908080a2f8ea4282842`;
each launch pins its exact executed preflight and package receipts.

Captures are in goal `client-evidence-v1/run-40868`, `run-26740` and `run-48948`. The fixture's
`client-evidence-run-PID` archives preserve process identity, logs and settings.
Its `client-launch-PID.json` records the per-run package/receipt pins. The fixture
directory name still says skin3 when rebuilt for palette8: use archived actual
configuration, not that directory name. Do not bind an older run to a later
`test-module/receipt.json`. All three completed runs used test HAK SHA256
`1af9fe160af8be024c3ffe761a2c7dd746a89eee3c1d7ad5117cd09e5b8ac245`;
their MOD/fixture receipts differ and remain recorded at launch. All three
clients were closed after matching their owned PID, executable and isolated
userdir through CIM verification; their logs and settings remain archived.
The consolidated [client validation](phenotypes/evidence/human-male-complete-goal-v1/client-validation-v1.json)
has SHA256 `34d752fca488cf59bb263e434aac0dea410ab20d8f8c1db016068bafc0efed90`.
`final-delivery-preflight-v1.json` has SHA256
`ca6081251f90b54657fb9bf5fdc867aac45bd8c6c12a7966b481cb6ac0b9e790`.

## Actual observations

Use the current fixture receipt's actor tags, equipment and phase definitions.
Retain action/position, worn-item, hit/spell/death logs and matching timestamps.
A scheduled command, heartbeat step or reported action does not prove the visible
animation played correctly. Inspect complete silhouettes and joints at close and
gameplay distances, from front/rear/both sides, and watch transitions continuously.

| Case | Concrete observation required |
| --- | --- |
| Idle | Natural stock rest and shoulder/neck/waist alignment. `PAUSE2` intentionally has pelvic tilt; label it separately from offline `pause1`. |
| Walk/run | Both support legs, turns, start/stop and return to idle; watch wrist/elbow/hip/knee/ankle overlaps and foot placement. Route logs alone are insufficient. |
| Cast/combat | Actual equipped attacks and spell casting plus entry/exit; check gripping pose, weapon/shield placement and shoulder/elbow extremes. Conjure/dodge smoke poses are separate cases. |
| Crouch/kneel | Entry, hold and recovery. `GET_LOW`/`getlowlp` and `WORSHIP`/offline `kneel` are distinct. Record the accepted inherited pelvis crouch limitation without hiding new defects. |
| Death | Observe dying motion, floor contact, final corpse and any reload/resurrection transition. Static dead-front/back poses alone do not prove gameplay death. |

In the current generic motion script, step 5 requests `PAUSE2`, step 9 queues walk
and run, step 12 requests `WORSHIP`, and step 13 requests `GET_LOW`. Steps 19/20
request static death poses. Gameplay steps 22/24/28 request actual attack, magic
missile and death. Recheck these against the exact newly built fixture; do not
infer a clip/time from these numbers or carry historical sequence selectors.

Verify actual worn-item logs and visual equipment state for representative rigid
armor, boots, bracers/gloves, helmet, weapon and shield. Review exposed body and
coverage boundaries through motion. Stock Human equipment remains identity sized;
do not add Armory scaling to compensate for a fitting defect. Include robe or
other untested stance/equipment cases in remaining limits when absent from tests.

Use matching stock/custom skin palettes 3 and 8, with actual other layer selectors,
and check fixed underwear remains fixed. Record lighting/time of day, quality,
resolution and normal/material settings. Check front/rear definition, joint color
continuity, specular/roughness response and floor contacts in more than one view.
Blender BRDF/tangents/filtering remain approximations; raw generator maps are not
runtime-material evidence. Separate lighting changes from a repeatable map defect.

The completed runs provide actual equipped gameplay/death/resurrection and
transition evidence plus idle/walk/run/crouch/cast observations. PID48948 supplies
the held `WORSHIP` cycle in side view, including arm-raised and bowing phases.
No newly detached parts or empty joint openings were observed in the inspected
frames; rounded overlaps and wrist caps can remain visible at extremes.
Palette3/original and palette8/directional
checks retained skin definition and fixed underwear behavior. Logs prove requests
and reported action state; literal captures and continuous observation provide
visual evidence.

The observed overlay was approximately 61 FPS with adaptive vsync in the small
isolated scene. Fixture `runtime-metrics-40868.json` and
`runtime-metrics-26740.json` record responding processes at the sampled times,
about 568/564 MiB working set and 2.17/2.16 GiB private bytes.
`runtime-metrics-48948.json` also records a responding process during its several
minute inspection. No crash report was produced in these three runs. VRAM was not
measured. These are sampled process figures and screenshot overlays, not
frame-time distributions or a crowd benchmark. The client is AMD64 PE32+ and
LargeAddressAware despite its `bin/win32` directory; serialized bytes and
hypothetical texture allocations are not measured resident memory.

For subsequent checks record duration, visible actors, settings, frame-rate/frame
times if available, responsiveness, resource errors and crashes. Native
mesh counts/payload sizes and texture-memory estimates accompany these observations
but do not substitute for client performance. Preserve crash reports and package
hashes before revising a failed fixture; report limits where telemetry is absent.

Retain the accepted practical limits without reopening hand cosmetics:

- Eight tiny QEM hand crossing pairs and one pinched vertex link remain, with
  zero boundary/nonmanifold/inconsistent-winding edges and degenerate faces. Do not claim every
  intersection or vertex link is clean.
- A forearm cap patch can show at the wrist crown in extreme poses; sampled
  contact rays found no new empty wrist opening.
- The inherited maximum sampled 73-degree held-dummy rotation can sweep a shaft
  through the palm; the stock mitten also penetrates. No collision-free item claim.
- Inherited accepted hip/pelvis intersection in deep crouching remains.
- Two palettes and representative stock armor/weapon/shield checks do not cover
  every palette, armor, robe, stance, weapon, crowded scene or hardware setup.
- Nonfatal `Empty field label in MODULE.ifo` warnings remain in archived logs;
  no missing-body-resource error or crash was reported in these runs.

## Offline batch and reference sheets

The CPU-only helper is
`output/phenotypes/purposebuilt-upperarm-pilot-v1/prepare_final_pose_batch.py`,
SHA256 `6e7a98c3fc0bd6738413222b3368d74efb4aea49472300016f89439ab4160590`.
It requires the actual final14 effective preview receipt/hash and explicit numeric
camera scales. Example arguments, executed by root using bundled workspace Python:

```text
prepare_final_pose_batch.py
  --preview-receipt <actual final14 preview-export.json>
  --preview-receipt-sha256 <actual SHA256>
  --camera-scale <measured single-body orthographic scale>
  --comparison-camera-scale <measured paired-body orthographic scale>
  --skin-row 3
  --output <fresh directory beneath purposebuilt-upperarm-pilot-v1>
```

It pins complete14/72 ownership, actual material preview/source arrays and both
palette-matched stock/custom maps, then archives `pose_preview.py` and its imported
helpers. It prepares eight custom-only category frames, front views with death
shown from above for the complete silhouette. Separate stock/custom front/rear/left
comparisons cover those eight cases plus six bounded supplemental poses. Root
serializes GPU execution; this helper launches no renders. Comparable poses retain
an explicit shared scale within each batch, and actual camera matrices/projection/
scale belong in numeric render receipts. Check fingertips, head, feet and corpse
remain in frame. Within-clip samples/endpoints are not executed engine blending.

Preparation and actual incomplete12 rejection are documented in upperpilot
`final-pose-batch-helper-proof-v1/proof.json`, SHA256
`8c437a7ac991c0ba36bb2f78f24c39ec609781db78dacaa8aca5844cd898765a`.
Positive final14 execution is now complete: eight primary custom views and
42 stock/custom comparisons. Two primary framing repairs, cast and death, are in
upperarm pilot `final-fourteen-primary-framing-repairs-v1` and pinned by the sheet.
Use actual numeric camera/render receipts, not the historical preparation-only
`rendersExecuted=false` protocol declaration, for completed execution status.

The completed [offline sheet](phenotypes/evidence/human-male-complete-goal-v1/offline-animation-reference-v1/animation-reference-sheet.png)
and `offline-animation-reference-v1/reference-sheet.json` cover all eight
categories with literal source images and package/controller/camera receipts.
PNG SHA256 `7980c97d555795231e14c001bb901ad4b590a8b1cc5ec9394501dd61400ecf53`.
Root reviewed the complete offline sheet's layout and full-body framing.

Use [build_animation_reference_sheet.py](../tools/phenotypes/build_animation_reference_sheet.py)
after actual capture review. Make distinct `offline-controller` and `nwn-ee-client`
sheets covering idle, walk, run, cast, combat, crouch, kneel and death. Pin complete
effective inventory, relevant HAK/MOD, each literal source image and matching receipt.
Captions identify exact offline clip/time or observed client state, palette and
remaining limitations. Set `fullBodyReviewed=true` only after viewing the actual
full-body source. The builder retains aspect ratio, archives its config/code and
hashes sheet outputs; it cannot repair anatomy or turn a command log into visual
acceptance.

The completed [actual client sheet](phenotypes/evidence/human-male-complete-goal-v1/client-animation-reference-v2/animation-reference-sheet.png)
covers all eight categories using captures from the three completed runs.
PNG SHA256 `97a054eeebaf44dae69aa0653d8f940c248481560db0502e37e4ca2d7d4c730b`;
`client-animation-reference-v2/reference-sheet.json` SHA256
`e2fa181169213db32582c2143ee888a1ee4d23b15f92d0c4909367cbff816694`.
The root review in `animation-sheet-review-v1.json`, SHA256
`e76bdad93e4d976383ff4f05c68a5673a3f3d590e524efb57366872b4ff4db40`,
proves exact source and literal viewport pixels for each category and records
complete-sheet/full-body review. Panels are uniformly resized for layout only;
engine colors and source captures are preserved. The practical Human pass is
complete; the disclosed limits remain part of user review rather than an
exhaustive production certification. Implementation is committed as `ed74212`;
the final handoff is recorded in `human-male-complete-goal-v1/final-delivery-v1.json`.
