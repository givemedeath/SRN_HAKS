# Purpose-built phenotype production contract

Use individual purpose-built parts to build a coherent body, replacing actual
stock parts one at a time. The [current runbook](phenotype-purpose-built-current-runbook.md)
identifies the accepted neighbours and selected inputs. The
[completed Human delivery](phenotype-human-male-delivery.md) records the current
fourteen-part native package and completed practical client pass;
[material preservation](phenotype-body-material-process.md) records the effective
material method and dependencies. The [original foot checkpoint](phenotype-foot-checkpoint.md)
retains its offline selection history, not current task restrictions or pending
gates. Read the current runbook before executing a phase and resolve user directions
chronologically. This contract defines the reusable method, not live job state
or a new goal.

The current validation cadence collects completed offline parts, then tests the
assembled phenotype in one bulk client phase. Maintain separate statuses for
offline selection and native/client acceptance. This cadence does not authorize
a new part or client access; current user instructions own those boundaries.

The previous mixed production journal and pre-cap design template are
[archived byte-for-byte with a hash manifest](history/phenotype-production-2026-10-03-023336-utc/README.md).
They are historical evidence. Their old torso selections, empty ledger and
task restrictions are not continuation instructions.

## Freeze the target and cumulative baseline

Declare race, gender, game phenotype/body type, physique, model prefix, rig,
assembled height and equipment policy separately. Freeze the actual installed
stock resources and their extraction inventory. Assemble the baseline from
actual stock plus only the accepted replacements named by current receipts.
Keep a separate map for the next diagnostic candidate.

Human male uses the exact stock `pmh0` attachments, male supermodel/animation
chain and measured height **1.9339157 m**. Stock head/neck and unmodified parts
remain the references. Accepted neighbour resources are copied byte-for-byte
when adding another part; they are not refitted or recompiled. Generation poses
never propagate into the rig or animations. Human equipment retains identity
scale; historical Human resizing profiles and former custom limbs are excluded.

Map anatomical names explicitly to native resources and attachment joints.
Do not copy canonical ledger keys directly into a native replacement map.

| Canonical part | NWN resource suffix / preview key |
| --- | --- |
| `upperarm_l`, `upperarm_r` | `bicepl`, `bicepr` |
| `forearm_l`, `forearm_r` | `forel`, `forer` |
| `hand_l`, `hand_r` | `handl`, `handr` |
| `thigh_l`, `thigh_r` | `legl`, `legr` |
| `shin_l`, `shin_r` | `shinl`, `shinr` |
| `foot_l`, `foot_r` | `footl`, `footr` |
| `chest`, `pelvis`, `neck`, `head` | Same suffix |

Native limb declarations also bind the exact stock joint; for example,
`shinl`/`lshin_g` and `shinr`/`rshin_g`. Model-family, style and equipment-region
associations remain explicit when generalizing to another target.

## Measure, design and reconstruct

Measure real triangle sections, cap contours, local axes, joint frames and
overlap through actual stock motion. A pivot is not the visible cut plane.
Assess both actual stock neighbours and accepted custom neighbours, preserving
their current bytes. The rigid-part system requires shallow closed ends that
overlap internally while the visible anatomy remains continuous.

Create one isolated anatomical part in a consistent design family. Keep
adjoining anatomy on its own part: pelvis owns underwear/groin, thigh owns
thigh, shin owns calf, and head/neck remain separate. Define useful closed
overlap ends in the images. Preserve physique and skin detail without forcing
the whole surface onto stock geometry.

Use front/left/back/right views of the same object and one isotropic scale over
black. The four-view branch shares top alignment; the [six-view orthographic
branch](phenotype-orthographic-multiview.md) centers silhouettes and adds genuine
top/sole cameras. Review all views before reconstruction; record
differences rather than independently stretching them. Save normalized images,
original sheet, prompts and provenance under the user's
`D:/source/repos/SRN_HAKS/.tools/reference_images/normalized/` folder, with
verified working copies in the fresh part pilot.

Follow [the current isolated-part generation procedure](phenotype-purpose-built-part-generation.md)
with an explicit part configuration and the running
`SR_NWN_3d_pixal3d_multi_views` workflow. Freeze live graph/schema, settings,
views and executed helpers before submission. Submit once and preserve prompt
ID, history, raw/pre-remesh, remeshed, compact and textured masters. Inspect
receipts and queue/history after uncertainty or compaction; never replay a
pending or completed job. Retained masters distinguish generated anatomy from
remesh/decimation effects. A successful generation is not a valid-game-part gate.

## Fit, refine and mirror

Exhaust positive uniform scale, proper rotation and translation into the stock
part frame before local mesh edits. Compare fixed front/rear/side and relevant
motion poses at native scale. Preserve authored geometry and maps in this
phase; reject hidden axis shrinking, stretching and global surface projection.

When placement cannot solve a measured defect, declare a separate bounded
operation: region, parent receipt/hash, displacement/profile, protected faces
and expected result. Cap closure, connector rounding, microscopic topology
repair and material preparation have distinct receipts. Preserve unaffected
coordinates, UVs, normals, material ownership and face lineage. Transport
normals through the inverse Jacobian and tangents through the forward
differential when appropriate. Do not globally recompute authored normals or
discard muscle volume to conceal a seam.

Validate the actual serialized candidate for closure/manifoldness, winding,
degenerates, duplicates and genuine crossings. Distinguish intentional overlap
with a neighbour from self-intersection. Bound targeted repairs with affected
face/corner ancestry and recheck the protected region. Geometry diagnostics
do not confer visual acceptance or authorize broader edits.

Inspect hidden anatomical views before donor adoption as well as assembled poses.
For feet, explicitly count toe tips from the sole and oblique underside; five-toe
imagery and a manifold mesh do not prove the reconstruction has only five toes.
Record any extra lobe as an anatomical gate even if every package test passes.

Check the actual rendered FLOAT32 arrays, not just a higher-precision working
archive. A closed manifold can still self-intersect at touching vertex fans;
recheck crossings and vertex links after local repairs. If added triangles cross
an atlas seam, map those new faces into a measured coherent chart and derive
their tangents from the serialized UV differential. Copying boundary UV/T values
alone can produce a wrong chart or tangent frame. Keep retained attributes exact.

Mirror only the selected detached donor geometry between the actual opposite
stock attachment frames. Reverse winding and tangent handedness; preserve UV
sampling, material maps and authored magnitudes. Never reflect skeletons or
animation resources. Independently inspect the opposite side's anatomy,
attachments, native arrays and motion before accepting the pair.
For offline collection, independently prove serialized reflection and sampled
pose coverage first; retain native-array and live motion checks as pending.

## Preserve materials and native provenance

Retain original embedded 2K map bytes and normal strength unless an explicit
material operation is selected. Match new cap charts to their adjoining skin;
preserve cloth ownership for repaired cloth surfaces. Keep source AO/roughness,
sampler and material flags in masters, and record what the native adapter
actually represents. A PLT/normal adapter must not claim full PBR equivalence.

Follow [native material preservation](phenotype-body-material-process.md) as a
required adoption step. Hash and inspect actual source AO/ORM channels and
factors. Bake a restrained, explicit AO contribution into PLT shades if useful;
retain palette recoloring and protected connectors. Extract ORM green to native
texture3 and explicitly disable a positive roughness override with Roughness 0.
Do not bind AO as height or packed ORM as an arbitrary NWN texture. Preserve
normal pixels/strength and fabric ownership. Test both ordinary and High Quality
shader paths: normals require appropriate light and roughness-map processing
depends on the installed shader path. Record source-map limitations rather than
claiming invented detail. Preserve the selected runtime material descendants
when composing later parts; exact old compile receipts remain historical parents.

The current Human repair validates output bytes, bounds, zero-influence pixels,
mirrored maps, native TBN, clean HAK payloads and client palette/lighting/pose
comparisons. That material repair alone did not close the older feet's anatomical
gate. The regenerated v5 feet subsequently passed their own anatomy, native and
full-body practical client checks, as recorded in the current delivery. Keep
material evidence separate from anatomy and whole-body acceptance.

Compare packed skin shade indices at actual visible native UV regions with
accepted neighbours, excluding garments and unused atlas pixels. Independent
generation can produce different luminance even when RGB skin appears similar.
Check at least two skin palettes in the assembled client. A selected runtime
PLT-only correction needs explicit derivative provenance; preserve original
compiler inputs and separately declare effective runtime dependencies. Carry
the accepted corrected map forward. The measured
[pelvis correction](phenotype-pelvis-skin-continuity.md) records this boundary;
its offset and six-part package inventory are specific to that baseline.

Bind fitted/refined/mirrored receipt ancestry before staging. Export only the
declared part with its authored corner positions, normals and UVs. Compile
each new part independently with its exact MTR/PLT/normal dependencies present;
`NormalTangents` requires compile-time material availability. Decode the actual
binary to verify source/ASCII/native transport, finite tangent arrays and
handedness. A binary header or compiler exit alone is insufficient.

Compose the new native unit with the explicit accepted donor model set and
pinned receipt. Verify recursive independent compiler provenance and copy all
preserved ASCII, binaries and dependencies exactly. Keep the private stock
comparator separate. Current shin commands explicitly preserve
`chest,pelvis,legl,legr`; foot commands preserve those plus `shinl,shinr`.
Compatibility defaults for historical thigh commands
must not choose a shin baseline silently. Undeclared models, root/animation
overrides, cross-family mirrors and overlapping ownership fail the contract.

When client access is held, use `compose_stock_limb_offline.py` only for an
explicit offline collection. Keep the clean declared body resources separate
from a comparator/test HAK. Preserve accepted native bytes, export new ASCII
parts, and record unexecuted native compile commands with exact material
dependencies. Do not invent native receipts, client evidence or a tested module.
An explicit PLT correction is a separate stage descendant tied to the selected
geometry and visible-UV calibration; regenerate those associations after a
placement change even when the source atlas is unchanged.

## Package, observe and retain acceptance boundaries

The following client gates belong to the bulk assembled-phenotype phase after
the user releases access. Offline pose renders, topology/material proofs and
resource audits can complete a part's offline selection without claiming these
gates have passed. Keep their fixtures, selected hashes and test cases ready.

Build fresh isolated HAK/module fixtures and audit their actual ERF payloads,
types, actor selections, appearance/phenotype mapping, native provenance and
empty override. Record exact HAK/module/configuration hashes. Keep camera
controls unlocked and use settled fixed-angle/held-pose fixtures plus sustained
walk/run and gameplay routes. Logs establish commanded/observed action state;
screenshots establish visible results. Keep both scopes distinct.

Review the same candidate through relevant idle, stride, flexion, casting,
combat, damage/death, palette and equipment conditions. Record actual stability,
resource cost and observed performance with practical limitations. Reobserve
the exact owned PID/argv/window before client replacement; preserve logs and
use the guarded absolute-userdir launcher. Respect concurrent client work.

Equipment tests declare their actual bodypart selections. Full stock armor can
hide a custom limb; it cannot substitute for bare limb seam evidence. A
boots-only test combination must trace its stock item fields and installed
foot resources while leaving the candidate shin visible. Human tests use stock
equipment at identity scale, with no resized model overrides.

Acceptance binds source/design, moving attachment coverage, geometry/normals,
materials/palette, native compilation, package integrity, actual client motion,
equipment and stability/performance evidence. Promote only the exact reviewed
candidate, recording permitted limitations and tests not observed. A user
selection, offline preview, dispatch log, compile success or package audit
alone is not full acceptance. Preserve accepted bytes and receipts, update the
cumulative replacement map, then start the next authorized part. Broader
production packaging and `phenotypes.2da` mapping require their own validated
target/table inventory; a finished local part is not whole-body deployment.

## Reuse for other targets

Measure each target against the stock Human height basis and explicitly record
its race slot, physique, part family and deliberate rig policy. Troll replaces
the default Gnome race slot as requested; that branch still requires validated
race/appearance/phenotype mappings and target-specific assembled motion checks.
Do not reuse Human resize profiles or old whole-body assets as racial inputs.

Targets needing NWNArmory profiles derive them from their accepted cumulative
assembly and actual equipment groups. Bind calibration, body/equipment/tool
hashes, mapped anatomical regions and profile parameters; validate worn items
through native motion and palette tests. A body revision reopens affected
profile checks. Those profiles and remaining race/gender/body-type production
are future phases, not claims made by this Human part contract.

The older production schema, Human example and validator are preserved in the
[dated design-template archive](history/phenotype-production-2026-10-03-023336-utc/README.md).
Their original files remain historical design/configuration artifacts; the
example is a frozen pre-cap state, not a live accepted-part ledger. The
validator checks that design contract and referenced bytes; it is not a
production runner. Current phase helpers and receipt-bound runbook inputs are
the executable continuation path.
