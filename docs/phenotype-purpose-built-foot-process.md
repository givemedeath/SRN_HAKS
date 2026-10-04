# Purpose-built foot process

Current scope and job state come from [the foot checkpoint](phenotype-foot-checkpoint.md).
Historical trials are archived rather than copied into the active recipe.

## Design and generation

Use actual stock ankle/heel/toe/sole dimensions and accepted shin sections.
Generate exactly five toes and review sole/underside before fitting. Include a
normal closed ankle end; avoid teaching the generator a pointed taper or shin
shaft. Add any hidden overlap taper after uniform fitting using measured scope.
Use restrained directional lighting and crease/arch shadowing for definition,
without hard cast shadows, embossed texture anatomy or AO-as-height.

Keep orthographic perspective and normal object orientation. Six-view support
uses front/left/back/right plus top and sole with [the additive camera adapter](phenotype-orthographic-multiview.md).
Normalize complete connected silhouettes with one isotropic magnification and
centered framing; preserve view disparities in provenance. AI turnaround views
are not photogrammetrically calibrated, so reconstruction must be reviewed.

Freeze images, prompts, live workflow, installed camera sources, model identifiers,
settings/seeds and all four masters. Inspect receipts before retrying uncertain
jobs. Keep unsuccessful trials as separate evidence, never overwrite them.

## Fit, local refinement and mirror

Inspect color and clay from front/rear/medial/lateral/top/sole/oblique angles.
Infer an ankle anchor from measured sections; a source bounding-box center is
not an authored joint. Fit by positive uniform scale, proper rotation and
placement first. Preserve toe proportions, stock height/rig and six neighbours.
The requested small anterior placement offset is evidence to evaluate, not
permission for broad stretching.

Local taper/topology/cap edits require explicit scope, maximum displacement,
frozen ancestry and actual FLOAT32 validation. Preserve unaffected P/N/UV/T/maps.
Small fan contacts may be split within measured physical bounds; do not copy a
previous source's contact count or forced face list. Added chart patches require
actual sampled color seam checks as well as coherent UVs and derived tangents.
Do not hide broad defects with smoothing. Mirror only a perfected donor through
stock frames, reverse winding/tangent sign and independently review the child.

## Materials, collection and limits

Use current effective accepted-six resources byte-exact; do not bake AO twice.
Follow [material preservation](phenotype-body-material-process.md): new controlled
palette AO/roughness descendants, original maps and explicit normal strength.
Measure UV-used ankle skin against current shin materials, then document any
shade shift instead of inheriting an old foot/pelvis correction. Source-color
Blender renders do not represent palette/shader runtime appearance.

Offline motion review and clean ASCII/native-mixed body collection can precede
bulk engine testing. Label new feet native/client-pending. Complete actual native
TBN/palette/boot/ground/performance checks in the later authorized bulk pass.
After completing feet, evaluate requested worktree space savings and await
instructions. Future hands require nearly closed gripping
fingers and a weapon-ready thumb; do not start them in this foot task.

## Lessons retained from rejected trials

- Same-raw 50K/100K v3 comparison retained identical raw geometry and deformation:
  polygon count did not fix the anatomical source problem.
- Tilted v4 images were explicitly rejected; its own job was safely interrupted.
- Original four-view node has only level side cameras and perspective projection;
  changing image labels cannot add genuine top/sole conditioning.
- Five visible toes in a reference do not prove the reconstructed underside has
  no extra lobe. Early actual sole review is mandatory.
- A coherent new UV chart can still sample a visibly different color. The v2
  contact patch's maximum 58/255 seam difference prevented final adoption.

## Improvements proven in v5

- Ordinary closed ankle images plus true parallel top/sole cameras reconstructed
  a five-toe donor without the earlier extra underside digit or pointed shaft.
- Contact budgets and measured separation probes are bound to each source audit.
  Failure saves diagnostics; a tiny sliver may be removed only within measured
  face-count, extent, area and volume limits. It is not general component deletion.
- Check new caps after actual FLOAT32 serialization. A valid projected ring can
  still cross nearby retained faces; expand only by measured crossing faces.
- Map each local patch separately and rank original charts by actual sampled
  boundary color as well as projection. This reduced max color step to 6.53/255.
- Post-fit smooth radial ankle taper preserves lower-foot anatomy and original
  UV/maps; normal/tangent changes have differential and independent attribute proof.
- Calibrate only the new parts against the current effective shin maps. New-foot
  -19 shade offset and controlled AO/roughness leave 32 accepted resources exact.

Do not reuse these numerical values as universal defaults. Measurements, source
topology, material boundaries and opposite-side proof must be repeated per part.
The [current validation record](phenotype-foot-validation.md) distinguishes
completed offline evidence from deferred engine gates.

## Current recipe and recorded execution

The active reusable preset is
`tools/phenotypes/configurations/purpose-built-human-male-left-foot-orthographic-v5.json`.
Do not use the rejected v2/v3 generation presets as defaults. Prepared Comfy
helpers and dependencies are frozen in the current pilot's `comfy-v1`; an
existing completed job is inspected rather than resubmitted.

Under `output/phenotypes/purposebuilt-foot-orthographic-v5`, the selected chain is:

| Stage | Frozen inputs/receipt |
| --- | --- |
| Reference design/normalization | `image-design-v1`, `normalized-v1/provenance.json`, `reference-copy-audit-v1.json` |
| Uniform fit | `left-foot-length-config-v1.json`, `left-foot-length-fit-v1`; recorded `prepare-fit-trials-v1.py` |
| Contact repair | `left-foot-local-contact-repair-v4/repair.json` with executed helper/config and measured source/probe/prior-cap audit pins |
| Patch materials | `left-foot-coherent-chart-v2/mapping.json`, original embedded maps and sampled color proof |
| Hidden ankle taper | `left-foot-hidden-taper-v2/taper.json`, `executed-config.json`, `executed-helper.py` |
| Mirror | `right-foot-mirror-v1/mirror.json` with actual stock-frame association |
| Skin/material descendants | `left-foot-skin-minus19-v1`, `right-foot-skin-minus19-v1`, `foot-materials-combined-v1/material-operation.json` |
| Motion | `paired-offline-pose-review-v1/commands.json`; nine stock-control comparisons and close-view receipts |
| Collection/selection | `paired-body-collection-v1/body-resource-manifest.json`, `final-offline-audit-v1/audit.json`, `selected-offline-v1/selection.json` |

Use frozen executed configurations/helpers and fresh output paths when an actual
new trial is intended. Some measured stock/shin inputs reside in older pilot
folders; they are pinned measurements, not inherited rejected geometry recipes.
Keep them or provide byte-exact recoverable archives before removing old output.
The [space assessment](phenotype-worktree-space-assessment.md) does not authorize
deleting those dependencies.

Prior detailed recipes/receipts are [archived](history/phenotype-foot-regeneration-2026-10-03/README.md).
