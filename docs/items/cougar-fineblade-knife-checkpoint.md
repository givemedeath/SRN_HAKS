# Cougar Fineblade Knife continuation

Implement the user-approved plan in the parent conversation. The native family is
dagger; the private test must contain this knife and the unchanged approved Cougar
shortsword on both shipped Human bodies. Only launch the client when the user
requests it; leave all controls to the user.

Authoritative checkpoint:
`output/itemkit/cougar-fineblade-knife/checkpoint-v38.json`, SHA-256
`daea8671aaa5f994506fa423ad6b165c059e3cb1b18cc5cabdfd772ff7b0b6e8`.
Read its exact manifest, binding and ledger pointers rather than selecting the
newest-looking output. Later explicitly documented checkpoint revisions supersede
this one; historical inputs and receipts remain immutable.

Current state (v38): **user approved the 30% shorter knife's in-game appearance**
after the requested launch of the corrected fixture. Keep `all-parts-length70`
selected. The exact user statement, "looks good", and package bindings are in
`length30-user-visual-approval-v1.json`. This visual approval does not establish
the complete client check matrix or production promotion.

The user's clarification superseded v35: the whole assembly and each of its
three parts now measure 70% of original v34 length. Width, depth, UVs and diffuse
bytes are unchanged; the fixed grip origin and joined boundaries are preserved.
Whole length is 0.5339979321 native units, formerly 0.7628541887. Usable grip is
0.12823426; this is a knife-specific override, not a global grip standard change.

Use `length30-delivery-v1/delivery.json`, `private-fixture.json`, and
`validation.json`, exactly bound by the checkpoint. Both Human actors are embedded
directly in the entry area, three units ahead of the player. Entry waits for valid
actors and area, reports actual equipped items, and leaves camera control to the
user. The inherited motion script now re-equips the knife. All 84 affected tests,
native actor GFF roundtrips, native models, seven HAK resources and 21 module
resources passed. The shortsword and shipped body HAKs remain byte-identical.

The requested client launch is retained in `length30-client-launch-v1.json`.
The immutable `length30-client-startup-v1.txt` excerpt confirms both named Human
actors spawned and both actors plus the player equipped `sr_cfk`. No client
controls were used. V36 is the pre-launch package checkpoint; v37 records startup;
v38 adds the user's visual approval. Original checkpoints and receipts remain
unchanged. GPU is still released; no generation or rebake was needed.

Historical state (v35): **all knife parts are 10% shorter and ready for private
testing**. The user requested this after viewing v34 in the client. Blade/guard,
grip and pommel each have 90% of their previous native Y span; X/Z coordinates,
UVs and runtime diffuse bytes are unchanged. The shared grip centre remains
fixed, keeping joins aligned. The usable grip is now 0.16487262 native units;
this is a knife-specific departure, not a change to the global grip standard.

Use `length10-delivery-v1/delivery-v2.json` and `private-fixture-v2.json`, exactly
bound in v35. The initial v1 delivery metadata inherited an obsolete singular
fixture HAK pointer; v2 corrects that pointer without changing package bytes.
Both original receipts remain intact. Fresh native roundtrips and exact HAK
payload checks pass; the validated comparison module, shortsword and Human
HAKs were copied byte-for-byte. Counts remain 4,852 visible / 488 shadow.
Eight geometry/lit/unlit views and fresh native icons were inspected at four
threads. No generation attempt, GPU work or rebake was needed. The updated
fixture has not been launched; the prior game session and files were untouched.
Client acceptance and production promotion remain pending.

Historical state (v34): **ready for user-controlled in-game testing**. The actual
native dagger and separate both-Cougar / both-Human fixture pass native roundtrips
and exact HAK/module payload verification. The approved shortsword is unchanged.
Final budgets are 4,852 visible / 488 shadow triangles, with a 4K donor transfer
and 1K runtime diffuse; no unresolved visible bake misses remain.

Use `delivery-v1/delivery.json`, its launcher and private user directory exactly
as bound in v34. Selected icons are the explicitly reviewed native-icons-v2;
the original dim icons and all processing receipts remain immutable. The
heartbeat is deleted. GPU is released. No client was launched, no client
acceptance is claimed, and production promotion still requires user approval.
There is no remaining generation or package work for this candidate.

Historical state (v33): final 4K transfer has zero visible misses. The actual
1K runtime views and corrected native icons are reviewed for private testing.
CPU session 48015 compiles and validates the native dagger and both-Cougar /
both-Human fixture through the explicit v33 delivery route. Original dim icons
and processing receipts stay unchanged. Collect the exact native delivery and
launcher before declaring ready. GPU remains released; do not launch the client.

Historical state (v32): the bounded transfer patch and measured-axis shadow proxy
pass 120 affected tests. Actual shadow preflight is closed at 488 triangles and
preserves both bore probes. CPU session 51478 runs production-v5.json in
production-run-v6 through final 1K review renders. Collect exact v32 bindings;
do not duplicate work or edit frozen sources. Inspect actual views/icons before
private native packaging. GPU remains released; client use stays with the user.

Historical state (v31): final transfer stopped on 537 texels across 13 guard/pommel
faces. The complete spatial diagnostic is bound in v31; no unresolved pixels
are accepted. Collect CPU face-review session 60015 and inspect the exact
source/target views before repair. The 120 affected tests and real Blender
pixel-read regression pass on the new unchanged freeze. GPU remains released;
actual package and combined fixture remain pending.

Historical Current state (v30): final working geometry is 4,852 visible triangles,
with 798/1,352/2,702 pommel/grip/blade-guard counts. The measured rim refinement
preserves original vertices and the through-opening. Eight matched views are
reviewed for transfer; close-up faceting remains subject to the actual 1K
runtime review. The upright reference lettering projection is accepted.

Guarded CPU session 81849 runs production-v3.json in production-run-v5 through
fit/reduce/unwrap/finish/bake, then stops for texture review. Final grip fit
already passed. Collect the exact v30 bindings; do not duplicate jobs or edit
frozen sources. The fixture uses its separate fixture-inputs-v1 manifest after
native validation; do not change the active production manifest. GPU remains
released. Native package, combined fixture and client acceptance are pending.

Current state (v29): the actual fitted donor/working mesh passes affine,
UV, native grip, topology, opening and thickness checks. Reduction reached the
triangle caps, but closer matched views rejected the angular pommel bore.
A bounded local rim refinement is running in session 42667; collect its exact
v2 result and launcher bound in the checkpoint. No new GPU work is required.
The reference lettering projection is upright and readable; final reduced
geometry and runtime transfer still require review. The prepared transfer
chain is not running. Preserve all failed candidates and the approved shortsword.

Current state (v28): the requested optimization pass is complete. Bulk mesh
reads replace Python tuples; separable gutter scans give identical results,
4.21x measured phase speed and 48.3% less tracked temporary allocation.
The final UV proof now records the correct isolated faces. Exact fitted normals
are retained independently of Blender's bounded display encoding. All 120
affected itemkit/dependency tests and the Blender fit regression pass on
unchanged freeze 47655aff... . Fresh source/runtime byte checks remain intact.

Guarded CPU chain 58045 is fitting in production-run-v4, then producing bounded
whole-shell reduction diagnostics. V28 binds the exact fit-v7 launch, config,
input path, chain, scripts and completion path. Do not edit frozen sources or
duplicate active work. Collect exact receipts and inspect the fitted/reduced
knife before acceptance. Final production inputs still need reference grip
finishing. GPU remains released; the real native package and fixture are pending.

## Historical checkpoint notes

Current state (v27): the 4K donor is reviewed and retained. The real fit
stopped when Blender decomposed the rotated transverse calibration and
changed correspondence. The maintained fitter now transforms mesh coordinates
directly and applies analytic inverse-transpose normals, preserving UVs.
All 79 affected tests and the rotated/nonuniform Blender fit smoke pass on
unchanged source. Historical failures and source receipts remain untouched.

Guarded CPU chain 90943 runs the corrected fit in production-run-v3, then
bounded whole-shell reduction diagnostics before native part cuts. V27 binds
the exact source freeze, fit-v6 launcher/inputs, chain, scripts and result paths.
Collect their receipts and visually review the fitted/reduced knife before
final processing. Do not edit these frozen sources or duplicate active work.
Final inputs still need reference grip finishing. GPU remains released;
the actual native package, combined fixture and client gates remain pending.

Current state (v26): the original-frame 4K source donor bake succeeded
(52.02% atlas coverage, two-pixel source gutters, no missing charts).
Eight matched clay/lit/unlit views are reviewed for fitting and finishing.
Generated grip lettering must be corrected before final runtime review.
The frequent sparse-voxel fallback is a measured small UDF shell offset,
not an axis mismatch; exact evidence and review are bound in v26.

The render launcher succeeded with unchanged inputs. Its chain then refused
to overwrite a historical completion filename; preserve that older file and
use v26's exact source/render receipts. No render rerun is necessary.

CPU fit runs in session 83107 using production-v2.json and production-run-v2.
Collect fit-v2-launch/launch.json and the exact stage receipt before proceeding.
GPU remains released; native package/combined fixture and client gates remain pending.

Current state (v25): source atlas v2 cleared UV defects/sampling but failed
the 30% useful coverage gate. The corrected 4K-specific padding uses
4/8/16 with unchanged coverage, overlap, sampling and measured gutter
gates. All 79 affected itemkit tests pass on unchanged source `4be5b973...`.
Shared implementation/dependency edges remain unchanged from the prior
129-test validation. Both failed source attempts remain immutable.

Source attempt v3 runs in session 31457. Guarded chain 18977 waits for
verified success and then renders eight matched clay/lit/unlit angles
at four CPU threads. V25 binds the exact scripts, inputs and status/result
paths. Do not duplicate these jobs or edit their frozen sources. Collect
and visually inspect their actual outputs before approving donor/fit.
GPU remains released; no client activity. Actual native package and
both-Cougar fixture remain pending.

The states below are retained history. V25 and its explicit bindings govern
continuation; do not resume completed jobs or use historical source freezes
as validation of the current tooling.

Current state (v24): the first CPU source unwrap stopped on 232 residual UV
defects after bounded local repacking (392.141 seconds; inputs unchanged).
The corrected item-only source atlas retains failed candidates and uses
bounded UV-only isolation with exact healthy domains and geometry. It
qualifies the actual 4K donor sampling resolution; final 1K runtime UV
gates stay unchanged. All 129 affected tests pass on unchanged source.

Fresh CPU donor attempt v2 is running in session 53698. V24 binds
its exact config, inputs, run and launcher plus the tests and failed v1.
Collect receipts before continuing; do not duplicate the bake. Candidate
grip measurements remain unapproved pending textured material-boundary
review. GPU remains released; actual package and fixture remain pending.

Current state (v23): the per-asset decoder range correction is validated.
All 124 affected itemkit, appearance, dependency and CI-scope tests pass
on unchanged source freeze `f7051de5...`. Custom ranges bind the exact
reviewed field bytes; raw values remain untouched and clamp only after
interpolation. Legacy explicit ranges remain compatible.

The original-frame 200K source unwrap and 4K donor bake were dispatched
through verified CPU tooling in session 78397. V23 binds the exact run,
launcher, manifest, inputs and validation. Collect their receipts before
continuing; do not duplicate the job. GPU remains released; no client
activity. The actual generated knife is not packaged yet.

Current state (v22): verification optimization is complete and retained in
`docs/items/generation-verification-optimization.md`. The full 2,068-test run
(two skips) found one test-fixture path ambiguity; all 45 affected tests passed
after its correction, with runtime implementation unchanged. Fresh synthetic
dagger/combined-fixture validation passed on final freeze `af8dd5a4...`.
The exact combined validation, source freeze and smoke bindings are in v22.
Do not relabel the retained initial nonzero suite result as successful.

All seven CPU repair views are reviewed; the repaired shell is approved for
original-frame source baking. The aperture probes are on the correct axis:
glTF Z converts to negative Blender Y. Both free probes and surrounding rim
checks pass. The next operation is the bounded per-asset source decoder
policy correction, then the 4K donor bake, fitting, reduction and transfer.
No GPU work or client activity occurred during optimization. The installed
adapter remains historical; any future GPU run needs fresh installation and
verified startup/bindings. The actual generated knife is not yet packaged.

Current CPU state (v21): raw donor remains immutable. CPU repair v2 has 199,376
triangles, closed outward topology with zero boundary/nonmanifold/inconsistent
edges and zero invalid vertex links; both protected bore probes pass. It reoriented
five measured faces, capped one tiny 0.002742-unit accidental ten-edge boundary,
split touching sheets with bounded offsets, and removed only contained inward
shells. V1 stopped while diagnostic averaged vertex normals cancelled; its failure
is preserved. V2 uses explicit face normals only for intermediate diagnostics.
Inspection session 69952 renders seven matched views at four threads. Review the
actual output before accepting repair for source baking; exact bindings are in v21.

The next correction is itemkit/donor.py's remaining exact legacy range policy:
it accepts only -.02..1.032, but the knife's finite six-channel field measures
-.08642578125..1.1015625. appearance-field-range-v1.json binds the actual ranges
and proposes explicit -.087..1.102 bounds. Parameterize a finite bounded reviewed
per-asset decoder policy, preserve legacy behavior, and test it before 4K baking.
Keep raw voxels unchanged and clamp only after interpolation, as GeneratedField
already does. Do not restart GPU work. Maintained source is still the tested
54c9... baseline; no policy source change has yet been made. Later fitting/reduction,
UVs/transfer/package/fixture and visual/client gates remain pending.

Current state (v20): ALL GPU WORK IS COMPLETE. Appearance passed exact saved-shape
decode validation and is retained locally; the 199,806-triangle UDF export is
retained and all seven views reviewed. Thin blade/channel remain; bore probes at
x=.445,y=-.05 and -.04 along Z remain open. The raw UDF shell has 10 boundary edges,
197 nonmanifold edges, 392 invalid vertex links and 4 inconsistent edges. Preserve
it unchanged and create/review a CPU repair before closed-shell UV/source baking.
The field is appearance-retained-v1/node-962_00001.npz in its original frame.

GPU models were released through the shared locked queue/ledger procedure. A
16 MiB release verifier rejected the 32 MiB residual CUDA context; no models
remained. This workflow's worker PID 32392 (parent 24000, exact owned command)
was then stopped after fresh ownership/queue/ledger checks. gpu-release-v2.json
proves worker absence, port 8188 free and 11,059 MiB free GPU memory at capture.
The user is being notified once now. Do not restart Comfy for remaining CPU work.
Runtime bindings and historical receipts remain retained; other services were
untouched. Continue CPU repair, original-frame 4K donor bake, approved-grip fitting,
reduction/UV/4K transfer/1K runtime, native dagger package and both-Cougar fixture.
The heartbeat stays active; the knife is not yet ready for in-game testing.
Earlier operation text below is historical and does not resume completed chains.

Current operation (v19): saved-shape appearance token be735cb149b149deb8addfe8e5d1ed80
was submitted as e1338ff6-d8eb-4fdb-b828-6066f9efee18; guarded collection is running.
Fresh 200K UDF/768 export preparation runs in session 96952. Chain 54451 waits
for successful preparation AND successful appearance collection (including saved
shape decode equality), then submits once and collects; no automatic retry.
CPU continuation 21250 waits for successful export collection, retains the donor
and renders seven four-thread inspection views. Checkpoint v19 binds every helper,
configuration, status, completion and job path. Do not duplicate these operations.
Review the UDF donor, thin blade and bore before source bake or GPU release.
GPU release notification remains pending; appearance/export collection and donor
visual review are not yet established. Earlier continuation text is historical.

Current continuation: all seven raw geometry views were visually reviewed. The
blade, recessed channel, guard and grip pass the appearance gate. Original-frame
segments through the pommel at x=.445, y=-.05/-.04/-.03 along z=-.3..+.3 have zero
intersections, with the surrounding rim intersecting; protect this irregular bore
and recheck the UDF donor. One geometry attempt remains. Exact saved-shape
appearance preparation runs in session 90570; bounded chain 19867 waits for its
successful verified launch, then submits once and collects in appearance-job-v1.
Checkpoint v18 binds the review, manifest, configuration and chain status paths.
Do not duplicate the job. GPU work is not yet finished: appearance and the reviewed
200K UDF export still remain before guarded release and the separate notification.
The earlier paragraphs below describe retained historical states.

Latest state: local geometry retention and all seven four-thread inspection views
are complete. Checkpoint v17 binds their completion, exact manifest and inspection
receipt. Review the actual views and pommel opening before appearance; no visual
geometry approval exists yet. One geometry attempt remains.

The user also requested a separate notification when all GPU work is finished.
After accepted geometry, saved-shape appearance and the required 200K UDF export
are collected and verified, confirm no uncertain/queued owned jobs or further
planned GPU stages, use the guarded ledger/queue release on this workflow's
runtime, verify release and retain evidence, then notify once immediately. Queue
idle alone is insufficient. Continue CPU fitting/baking/packaging afterward.
The existing heartbeat now includes this milestone and remains active until the
actual knife package/fixture is ready for user-controlled in-game testing.

Current operation: geometry token `6a572abe750d437391023bf6221db4b6` was
`preflight-rejected` before `/prompt` because selected checkpoint-file hashing
exceeded the ordinary 30-second HTTP timeout. Zero of two geometry attempts were
consumed. Preserve this terminal entry and never resubmit that token. The model
verification endpoint now has the same bounded 300-second allowance as runtime
verification; byte checks, source identity, queue locking and job deadlines remain
unchanged. Both focused transport tests, the full helper suite (2,058 tests, two
skipped, exit 0) and fresh synthetic native smoke passed on unchanged codeVersion
`54c9b9c5feaf1102da25e43741178161f6aaf4a14b7bde76e70ac5246ca5433c`.
Their exact evidence and freeze bindings are in checkpoints v12/v13. Earlier
full-suite/native evidence is historical.

Fresh `geometry-request-v2.json` preparation passed (exit 0, unchanged inputs).
Bounded chain 24977 submitted token `21c4641b0da74ee7827cb9e32420f5b6`
as prompt `40909c0f-b830-4d94-b7d1-5f2313fc663c` and successfully collected in the same
`geometry-job-v2` directory. Use checkpoint v16's exact request, configuration,
helper, status and completion paths; never duplicate this operation. Its ledger
entry is now `complete`, using one of two geometry attempts. Both geometry attempts
were unused at chain start. The existing
shared ledger remains authoritative. Generated geometry needs visual review
before appearance, regardless of numerical success.

Bounded CPU continuation exec session 41563 has received the successful collection,
is retaining exact raw geometry and saved shape locally, then renders seven inspection
views at four threads through verified tooling. It cannot approve geometry,
submit appearance, retry generation or launch the client. Read checkpoint v16's
`pendingGeometryReview` bindings and its explicit status/completion files before
continuing. Review actual views and the opening before any appearance request.

Corrected calibration completed and its normalized image/mask passed visual
review. Qualified finishing cleared only two faint empty-background pixels; strict
conditioning validation passes with the mask unchanged. Retain `geometry-v1.json`,
the measured 49.61821223924617-degree camera and frozen single-image preset.
This workflow owns the verified running service; Troll has released it. The Comfy
source and adapter did not change, so do not restart it for the client timeout fix.
The following sections retain historical states and do not supersede this paragraph.

The source is retained; input analysis selects background removal. Installed dagger
donors/icons, their measurements, the effective native stack, approved grip standard
and collision-free appearance slot are prepared. `calibration-v1.json` is the active
GPU intake; `fixture-inputs-v1.json` also binds the shipped Human fixture sources and
comparison blueprint. Zero knife geometry attempts have been submitted, with two
allowed through the existing bound shared ledger. Camera/foreground calibration and
generated geometry still need their actual visual reviews.

Workflow corrections are summarized in [the audit](cougar-workflow-audit.md).
Focused validation passes 70 itemkit tests (`knife-workflow-tests-v4.log`); the full
helper run is `output/itemkit/knife-full-helper-tests-v2.log`, session 44318, with
`knife-full-helper-timings-v2.json`. It completed successfully: 2,056 tests, two
skipped, exit 0. The frozen item/head tooling and native smoke source pins match
the retained run; fresh byte checks still apply before generation.
The synthetic native smoke at `native-smoke-v1/smoke.json` passed fresh dagger
compilation, sanitation, roundtrip and combined fixture construction. It contains
tiny tetrahedra, **not generated knife geometry**; never present it as the knife.

The user explicitly chose **"Wait for the Troll session to release the shared
runtime"**. Do not stop/restart/reconfigure that session's service or use its input,
output or model configuration. Last observed port 8188 owner was PID 30888, with a
Troll-specific `main.py` command and HTTP 409 at `/headkit/runtime-identity`. An idle
queue alone does not prove release. Once the unrelated process has exited and the
runtime is available, establish this workflow's verified startup and fresh byte-bound
generation bindings, retaining the trial ledger. Runtime/helper changes require
fresh migration evidence. No stale-code or saved-shape checks may be bypassed.
The thread heartbeat `resume-cougar-knife-after-runtime-release` checks every
15 minutes, remains quiet while unchanged, and must collect the full helper result
before GPU work. Disable it when the generated knife is ready for in-game testing.

After successful validation and verified runtime availability, continue calibration,
shape generation and review, appearance on the saved shape, 200K UDF donor export,
approved grip fitting, closed working-mesh repair/reduction, final UVs and 4K donor
transfer, 1K runtime diffuse, 5,000 visible / 500 shadow caps, eight matched views,
native packaging and a separate both-Cougar fixture. Do not reuse shortsword-specific
repair exceptions or change its accepted assets. Preserve resumable checkpoints.
Client validation and production promotion remain separate gates.

## Runtime released, 2026-10-22

The Troll process exited and port 8188 was free before this workflow started its
own service. `runtime-knife-v2/process-v2.json` binds the new startup (parent PID
24000, worker PID 32392); it uses this workflow's model configuration and local
user directory, never the Troll paths. It is still initializing. Require successful
`/headkit/runtime-identity` verification before dispatch. All 1,221 source files
match the previous frozen inventory and the installed adapter matches this checkout.
The ledger has no uncertain jobs and the knife remains at zero of two attempts.
The pending calibration configuration is bound in checkpoint v4. Use the ignored
`output/itemkit/knife_launch_v1.py CONFIG` driver to create operation-scoped inputs
and launch the maintained CLI through verified shared tooling. Historical startup
records remain retained; process.json failed because its user directory was absent,
then that directory was created before process-v2.json started.

## Verified runtime and isolated CPU packages

The own service completed startup and live verification; checkpoint v5 binds its
identity (1,221 source files, 18,530 runtime files, 731 loaded sources). The frozen
item/head codeVersion remains unchanged. Initial calibration preparation correctly
rejected 324 new bytecode-cache files in the shared Python package folder. All
2,583 original pinned files were unchanged. Those exact files (178,994,345 bytes)
were copied and reverified into a dedicated durable package folder; the shared
folder was left untouched. Active bindings are the checkpoint's
`runtime-knife-v2/local-isolated-v2.json`, with fresh successful Python and isolated
four-thread Blender migration smokes. All 70 itemkit tests pass in that environment
(22.071 seconds). The earlier sandbox test was interrupted and its log retained.
The first new Blender smoke invocation was rejected before execution because the
launcher owns background flags; corrected fresh migration-v2 evidence passed.

Calibration request preparation is running in exec session 83710. Its exact
configuration, intended request output and launch receipt path are in checkpoint
v5. Collect this operation before creating another request. The driver uses the
freshly retained live proof for this preparation pass; submission still performs
its own fresh live runtime/source/model checks under the shared lock. No knife
job has been submitted and neither geometry attempt has been spent.

## Calibration dispatch pending

Calibration preparation succeeded through the verified launcher (exit 0, inputs
unchanged). Checkpoint v6 binds its exact request, token and launch receipt. The
guarded submission is running in exec session 25329. Its output argument names
a directory `calibration-submit-v1.json` (despite the suffix); submission-intent.json
and submission.json belong inside it. Do not resubmit token
`115262f95d6e41a3b73e8a47fefd6d67`; collect the pending launch and inspect the existing
shared ledger first. This is calibration, so both knife geometry attempts remain.
The submission launcher consumes the already explicit prepared input pins plus
its own verified CPU packages/helpers; it retains fresh live dispatch checks.

## Corrected foreground calibration in progress

Checkpoint v7 supersedes the earlier pending operations. The first calibration
executed successfully, but its foreground mask filled the visible daylight sliver
through the pommel. Its collection also used a different output directory and
therefore failed validation for missing submission-intent.json. Preserve that
terminal ledger state and receipt; do not retry the old token or reset history.
The follow-up audit records both issues separately.

The reviewed correction removes only 131 daylight pixels, keeps every source RGB
pixel and the outer mask unchanged, and retains the tube wall and bronze rim.
The active calibration manifest and correction/review/launch pins are explicit in
checkpoint v7. Its input analysis selects preserve-alpha, so BiRefNet is not run
again. Fresh calibration request preparation runs in session 89852; the bounded
chain in session 34585 waits for its successful launch receipt, then submits and
collects using the same job directory. It uses existing guarded CLI operations,
stops on failure without retries, and cannot submit geometry. Read its explicitly
bound status/completion files and ledger before any new action. Successful
normalized output still needs visual review before geometry. Both knife geometry
attempts remain available. The owning service is this workflow's verified runtime,
not Troll; do not restart or replace it during this continuation.

Latest operation update: corrected preserve-alpha request preparation passed
(exit 0, unchanged inputs, unchanged codeVersion). Checkpoint v8 binds its request
and preparation receipt. Token `a8daafd75d674f35a692eefc0ede9744` is being submitted/collected
by the existing chain (exec session 34585). Do not duplicate that operation. Its
status and completion paths remain the authoritative operational pointers.
