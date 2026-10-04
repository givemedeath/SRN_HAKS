# Current isolated-part generation procedure

Updated 2026-10-03 UTC. Read the [current runbook](phenotype-purpose-built-current-runbook.md)
and [material preservation](phenotype-body-material-process.md) for
the current cumulative geometry/material baseline. The
[completed Human delivery](phenotype-human-male-delivery.md) records the current
native selection and actual client results. The [original foot checkpoint](phenotype-foot-checkpoint.md)
retains offline-stage history, not current deferred gates or stop instructions.
This procedure applies to each new purpose-built
part; completed attempts are preserved and never replayed merely after compaction.
The previous mixed torso journal is [archived byte-for-byte](history/phenotype-generation-2026-10-03-015634-utc/README.md).

## Design and normalize the isolated part

Measure the actual stock part, joint frames and neighbouring overlap first.
Keep the stock rig/controllers, native Human height and accepted neighbouring
assets fixed. Design only the requested anatomical part, with shallow closed
overlap ends; adjoining anatomy belongs to its own part. Stock neck/head and
equipment remain separate unless the current task explicitly changes them.

Create front, left, back and right views of the same object; use genuine top
and sole inputs where the [orthographic six-view branch](phenotype-orthographic-multiview.md)
is selected. Use one isotropic scale and a consistent image origin. The old
four-view branch top-aligns; the orthographic branch centers bounds. Review anatomy and
orientation together; independently cropping or stretching each view can change
depth/width proportions. `normalize_part_turnaround.py --layout-components`
supports the current shared-scale normalization. Preserve its source sheet,
prompt, masks, panels and provenance, and save matching normalized copies under
the user's `D:/source/repos/SRN_HAKS/.tools/reference_images/normalized/` folder.

Treat scale/sole alignment in generated image prompts as intentions until
measured. The first foot sheet retained a 6.42% medial/lateral length difference
and an 18-pixel normalized sole-height difference. Shared isotropic normalization
correctly preserves these discrepancies; it does not make four views exact
orthographic observations. Review the reconstructed anatomy before deciding
whether the discrepancy warrants another image attempt. Do not stretch views
to conceal it. Front/back source GLB orientation may also be reversed despite
correct reference labels; establish actual toe/heel/medial anatomy and use a
proper rotation when warranted.

The shared normalizer accepts six-view layouts with two columns or explicit
`--layout-columns 3` (front/left/back, then right/top/bottom). Axial silhouettes
may legitimately be smaller than side views: `--end-view-min-area-ratio` is an
explicit measured exception for top/bottom only, within 0.05–0.25. Side-view
minimums, disconnected extra-object rejection and source-boundary clipping guards
remain strict. Record the chosen threshold and measured disparities; do not make
a weak sheet pass by silently changing all component guards.

Inspect genuine end-axis anatomy before dispatch. A duplicated finger/nail row
or a dorsal oblique view relabelled as underside is a reference defect. Preserve
the rejected sheet and any unsubmitted request, correct through image generation,
then normalize a fresh descendant and reinspect every panel. Editing one view
can change the other five; requested invariance is not byte-exact proof.

Freeze external copies with `freeze_part_references.py`; include source sheet,
exact prompts, normalized images/alpha/provenance, executed normalizer, current
configuration and all actual edit parents with their lineage. Inspect this receipt
before retries. A new intended job is distinct from replaying an uncertain job.

The conditioning inputs are 1024-square `front.png`, `left.png`,
`back.png`, `right.png`, plus `top.png`/`bottom.png` for the explicit six-view
branch, composited over black. `LoadImage` IMAGE output does
not automatically apply alpha as intended conditioning. View order is
front/left/back/right at azimuths 0/90/180/270 degrees; top/sole use elevations
+90/-90. The original built-in node uses perspective and level cameras; it
cannot consume top/sole simply by changing labels. Confirm the live node
schema and framing before preparation. The current image-conditioned branch
does not consume the written anatomy prompt as text conditioning, so the
images must communicate the intended shape.

## Freeze an explicit configuration and live workflow

Every new part must pass an explicit `--config` to `prepare`.
`generate_purpose_built_part.py` now rejects preparation without a configuration;
it cannot silently select the historical Human chest settings. Frozen helpers
in completed attempts retain their executed behavior and are not rewritten.
Use a fresh part-specific configuration and output directory. Record the part,
workflow, service, image size/order, explicit projection and FOV or orthographic
span, seeds, shape resolution, triangle
budget, remesh mode and every mode-specific input, texture/normal resolutions,
and bake-reference policy. Set `retainRawMaster: true` for new attempts.

Completed preparations freeze their executed `config.json`. Later corrections
to a working design configuration or task scope must not rewrite that frozen
copy or the normalized-reference provenance. The foot working configuration's
old upper-arm continuation was removed after the user's stop-after-feet
instruction; the executed original remains immutable evidence of the job.

Use the running `SR_NWN_3d_pixal3d_multi_views.json` workflow. `prepare` reads
the live graph and `/object_info`, validates expected node types/settings, and
freezes the graph, API template, configuration, panel bytes and executed helper
imports (`generate_purpose_built_part.py`, `pipeline.py`, `height_targets.json`).
It queues nothing. Record available server/node versions and loaded model
identifiers alongside preparation; these are distinct from freezing the Python
helpers or verifying checkpoint weight bytes. Historical server/GPU/queue
observations do not establish the current running state.
For the orthographic branch, freeze and reverify the installed additive adapter
and both reviewed upstream sources. The source saved workflow stays unchanged;
only its prepared submission variant changes conditioning node324 and image inputs.

```powershell
$taskPython = 'C:/Users/benco/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
$partConfig = 'path/to/reviewed-new-part-config.json'
$partViews = 'path/to/shared-scale-normalized-views'
$partRoot = 'path/to/fresh-part-pilot/comfy-v1'
& $taskPython tools/phenotypes/generate_purpose_built_part.py prepare --config $partConfig --views-dir $partViews --output $partRoot
# Inspect the frozen images, configuration and graph before submission.
$frozenHelper = Join-Path $partRoot 'generate_purpose_built_part.py'
& $taskPython $frozenHelper submit --output $partRoot
& $taskPython $frozenHelper status --output $partRoot
```

The paths above are placeholders, not the next part's selected configuration.
Use the bundled Python, never the Windows Store shim. Submit/collect with the
prepared helper so later source edits do not change executed provenance.

## Submit once and retain all masters

`submit` verifies frozen files, rejects an occupied queue, uploads and hashes
the exact declared four or six panels, freezes the submitted API and writes a receipt before
dispatch. A second submission in that output directory is rejected. If dispatch
is uncertain, inspect its receipt and server queue/history; do not silently
create a duplicate job. `status` preserves history and collects exactly one GLB
per declared save node, verifying existing bytes on repeated collection.

Retain the untouched `raw-master` before remesh, `remeshed-master` before final
decimation, compact `shape-master`, and `textured` GLBs with their recorded
hashes and job associations. These are source assets, not rigged/native parts.
Raw retention is optional in the helper and must be explicitly enabled in new
configurations; older preparations without it remain accurately documented.

## Inspect before fitting or adoption

Inspect actual coordinates, components, boundaries, nonmanifold edges, winding,
genuine intersections, geometric/authored normals, embedded maps and view
orientation. Ray sections should distinguish a solid exterior from thin paired
walls and folded internal surfaces. UDF remeshing can produce connected inner
and outer walls; one component, zero boundary edges or positive volume alone
does not establish a usable solid. Preserve defects and sampled uncertainties
in the receipt. Neither successful generation nor its triangle count proves
anatomical quality, moving seam coverage or a runtime performance budget.

Do not assume a new hand will reproduce the last Human hand's shell, winding,
normal or reference defects. Start with ordinary generation and inspect that
donor's actual results. If sound, proceed to fitting and native preparation.
Detailed raw/remesh fault tracing and corrective recovery are conditional on
an observed defect. SAT512 reconstruction, leak patches, fairing, normal smoothing
and the special clean-source retexture graph are not default hand steps; select
the smallest justified response from fresh evidence rather than replaying the
previous repair sequence or its parameters.

Fitting is a separate stage: first exhaust positive uniform scale, proper
rotation and placement against actual stock attachments. Do not stretch,
project onto stock surfaces or modify a master under a similarity-only receipt.
Any later justified local repair, cap, UV or material operation needs its own
bound descendant and protected-attribute proof. Mirror detached geometry only;
never mirror the skeleton or controllers.

Keep original maps and normal strength 1 unless an explicit measured material
trial calls for changes. The generator records `postFitNormalStrength` but does
not apply it during reconstruction. Native PLT/MTR export must separately
account for skin palette, fixed fabric, UV/tangent handedness, and any source
AO/metallic/roughness or sampler information not represented by that export.
Follow [the native material preservation procedure](phenotype-body-material-process.md)
before adopting a part. Extract actual AO and ORM bindings; moderate AO into
recolorable PLT shades when useful, and carry ORM green into native texture3
with explicit Roughness 0. Do not silently discard these maps or carry positive
roughness constants that mask them. A material descendant has separate runtime
provenance and leaves original geometry and compiler dependencies immutable.
Carry the selected effective materials of accepted neighbours forward, including
their color corrections. The tested Human recipe is not a universal race default.

Native compilation, clean resource ownership, isolated packaging and actual
client animation/equipment/palette checks follow fitting; generation is never
client acceptance. The current cadence collects offline parts first, retaining
native/client gates for bulk validation of the assembled phenotype after access
is released. See the [reusable production contract](phenotype-purpose-built-production.md).

## Hand design requirements

The user requires **nearly closed gripping hands**, not open/fanned fingers.
Keep fingers naturally curled as though holding a weapon handle, with coherent
knuckles and a thumb positioned for the grip. Measure the actual stock hand,
wrist and weapon attachment before designing references. Gripping is the asset
generation pose; it must not modify stock animation resources or the rig.
Design one donor and mirror only after anatomy, wrist fit and held-equipment
alignment pass. Both selected feet and gripping hands used genuine six-view
conditioning and completed native/full-body practical client checks. The hand
source needed a separately measured remesh recovery; more camera views alone
do not guarantee usable anatomy. Resolve the current checkpoint and latest user
direction; do not replay the superseded stop-after-feet or completed hand jobs.
