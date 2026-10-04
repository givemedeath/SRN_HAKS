# Phenotype continuation checkpoint

**Current later direction (2026-10-03): regenerate the foot references/model
with a tapered shin overlap, directional texture definition and subtle baked
crease/AO shadowing.** Follow the foot checkpoint. Active pilot
`purposebuilt-foot-taper-v3`, single submitted job
`b40648ff-28d4-48e8-8dab-2f09016b1ee4`. The v2 pair is superseded diagnostic
history. Preserve accepted six parts/current materials. Finish feet offline
then stop; bulk client cadence remains, no active goal.

**LATEST USER DIRECTION (2026-10-03): redo foot generation and fitting to
remove the extra toe.** The prior app-restart stop is superseded. Follow
[the foot checkpoint](phenotype-foot-checkpoint.md), use a fresh left-foot
generation with early untouched sole anatomy review, fit to actual stock
feet/accepted shins, then mirror. Preserve six accepted geometry sources and
the combined-v2 material baseline committed in `9d5fcb8`. Default offline
collection/bulk client cadence remains; finish feet then await instructions.
There is no active goal. The material-task generation restrictions below are
historical and do not override this newer instruction.

**LATEST USER DIRECTION (2026-10-03), now completed: repair the flat materials on all latest
Human male parts and test the result in the game client.** This explicitly
releases the earlier client hold for the material repair and its tests.
Read [the material repair checkpoint](phenotype-body-texture-repair-checkpoint.md)
and [repair plan](phenotype-body-texture-repair-plan.md) before continuation.
Foot regeneration remains stopped; no new images/Comfy job are authorized by
this material task. Accepted geometry, stock rig and original receipts stay
immutable. The older foot-only directions below are historical context.

Updated 2026-10-03. This is the recovery index, not a second live client
journal. The material checkpoint owns the latest completed task and its client evidence.
There is no active goal. The newer material request supersedes the old client
hold; it does not authorize foot regeneration or another anatomical part.

Latest correction: both feet are shifted +3 mm stock foot-local +Y. Their
offline proof/package is saved, but a user-reported underside extra toe-like
lobe is confirmed and remains an open anatomical gate. Established methodology
is committed in `b9fa9df`; local corrections were rejected and regeneration
remains stopped. Do not call
feet finished or start another part.

The user now prefers bulk client testing after offline collection of the
phenotype's parts; this cadence does not authorize another part after feet.
Read
[the foot checkpoint](phenotype-foot-checkpoint.md). The shin pair has completed
first-round validation and pelvis skin continuity is corrected and accepted.
Read [the shin checkpoint](phenotype-shin-checkpoint.md),
[validation record](phenotype-shin-validation.md) and
[selected material correction](phenotype-pelvis-skin-continuity.md). Keep the
validated geometry, frozen client evidence and corrected pelvis PLT intact.
The preceding thigh pair is finished in `bd5ee99`; preserve its selected assets
and [validation record](phenotype-thigh-validation.md).

## Resume current work

1. Read `AGENTS.md`, this file, [the shin checkpoint](phenotype-shin-checkpoint.md)
   and [the current runbook](phenotype-purpose-built-current-runbook.md).
   Resolve user instructions chronologically; a later continuation supersedes
   a historical pause. New user directions take precedence over documents.
2. Check live goal status and Git status. Never infer a pause, completion or
   need for a duplicate goal from a historical status/PID. Change goal status
   only under the current user direction and goal-tool rules.
3. Follow the material checkpoint/validation and current latest user direction.
   Preserve completed generation, fitting, mirror and native/client receipts;
   do not replay them after compaction. Reobserve process/window ownership
   before authorized client use. Foot regeneration remains stopped.
4. Keep the selected source, accepted neighbours and exact stock rig fixed.
   Update the material checkpoint with real evidence before compaction. Leave
   unrelated changes and historical experiments untouched.

## Selected inputs and limits

The current effective material baseline is **combined-v2** in
`human-male-material-repair-v1/selected-runtime-v1/selection.json`. The
[material validation](phenotype-body-texture-repair-validation.md) binds actual
tests and clean HAKs. Carry its effective PLT/MTR/roughness inventory forward;
the source GLBs below remain geometry authorities. Do not reapply AO to the
selected repaired maps or fall back to old compiler materials.

Under `output/phenotypes` in `D:/srwt/codex/f0b3/SRN_HAKS`:

- Selected left: `purposebuilt-thigh-pilot-v1/left-thigh-proximal-cap-v2-proof/refined-local.glb`,
  SHA256 `5420a77d5e9d51b7841f678d12710ce335bab16ed5ad417ae49b67f1e2950ab6`.
  User-selected label **Hip crown taper**; bind `refinement.json` in that directory.
- Selected right: `purposebuilt-thigh-pilot-v1/right-thigh-v2-mirror-v1/mirrored-local.glb`,
  SHA256 `3c002789b74bfb5e94392d7c557e3105924e078f0133c47d496b1c123764b980`.
  Bind its `mirror.json` and independent opposite-side validation.
- Protected chest: `purposebuilt-torso-pilot-v1/common-cap-atlas-v4-perimeter/common-atlas-local.glb`,
  SHA256 `3ae78d023ba522d94c44d9914bac0b36f35b640c42b9532015575e5572161a50`.
- Protected pelvis: `purposebuilt-pelvis-pilot-v1/selected-d-original-polished-material-v1/postfit-local.glb`,
  SHA256 `db0bdf16099068da3bb685bcb61ae93ebed115e6ddbae90990c0b55e59b8d98a`.
- References: hash-verified `purposebuilt-stock-inputs-v1`; actual `pmh0`
  attachments, male controllers, stock neck/head/other limbs and native height
  1.9339157 m. Human equipment remains identity-scaled.

Preserve physique and accepted neighbours. Current methodology generates one
isolated part, uses proper rotation/positive uniform fitting, applies only
proven local connector edits, mirrors geometry between measured frames and
independently validates native assets and actual motion. It does not regenerate
supermodels/animations or refit prior custom body parts. Minor crouch-only
pelvis irregularity is acceptable to the user; main standing and locomotion
joins remain required. Finished pelvis work does not finish the body, and
successful automated audits alone do not establish visual acceptance. The
finished thigh record now includes actual client evidence with its limits.

## Evidence ownership

[Material validation](phenotype-body-texture-repair-validation.md) owns current
effective material selection; [foot checkpoint](phenotype-foot-checkpoint.md)
owns its stopped anatomical stage. [Shin checkpoint](phenotype-shin-checkpoint.md) owns its finished evidence.
[Thigh checkpoint](phenotype-thigh-checkpoint.md) owns the finished
neighbour selection and evidence. [Thigh process](phenotype-purpose-built-thigh-process.md)
and [fitting record](purposebuilt-thigh-fitting-pilot.md) own current source,
fit, local-edit and mirror proof boundaries. [Current runbook](phenotype-purpose-built-current-runbook.md)
indexes commands and exact selected inputs. Normalized image/prompt provenance
is preserved in the user's original `reference_images` folder as recorded by
the shin checkpoint for this part and the thigh checkpoint for its neighbours.
No new part or broader race/profile work starts merely
because a historical document recommends it.

## Historical archive

The previous checkpoint and runbook are preserved byte-for-byte in the
[2026-10-03 archive](history/phenotype-operational-2026-10-03-004821-utc/README.md)
with exact hashes. Their mixed dated statuses, candidate suggestions and
recipes are historical, not current instructions. The
[finished pelvis checkpoint](phenotype-pelvis-goal-checkpoint.md) and
[pelvis validation](phenotype-pelvis-validation.md) retain its completed
result. The [original production specification](phenotype-production-goal.md)
and [experiment journal](phenotype-experiment-history.md) remain broader scope
and history; later user selection and the current material checkpoint govern
continuation. Do not reopen finished neighbours from their old recipes.
