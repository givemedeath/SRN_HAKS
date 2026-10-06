# Shared tooling and phenotype workflow

New runs resolve shared installations from a durable tool root, verify their bytes,
and record the paths they consume. This prevents an active phenotype session from
depending on executables stored in a worktree that another session retires. Tool
migration proves tool behavior; it does not approve body geometry, equipment fit,
animations, or client rendering.

## Tool resolution

Both `tools/SrnTools.psm1` and `tools/shared_tools.py` read
`tools/shared-tools.lock.json`. They return path, version, SHA256, installation
origin, selected root, root origin and inventory hash. Root precedence is explicit
`ToolsRoot` or `--tools-root`, then `SRN_TOOLS_ROOT`, then the primary checkout's
`.tools` identified through Git worktree metadata. Bare repositories and exports
without usable Git metadata require an explicit root. Git 2.34 remains supported.

Paths are resolved through junctions and symlinks before validation. Shared tools
and installed runtimes cannot live in any linked worktree, including worktrees of
another repository. Own-checkout vendored compiler and compression tools are the
exception: their bytes and containing checkout are verified. Overrides preserve
explicit callers while enforcing the same location and byte checks. There is no
sibling-worktree search or fallback to a different version.

The portable inventory pins Neverwinter utilities 2.1.2, NWNArmory 1.3.4,
Neverblender 4.1.0 source files, and the existing vendored executables. Generated
Python caches are excluded from addon identity; added or modified source files
fail verification. Machine paths belong only in ignored local bindings. Ordinary
repository and item-import builds resolve Neverwinter utilities without requiring
Blender, NWNArmory or a Python installation.

```powershell
Import-Module ./tools/SrnTools.psm1
Resolve-SrnTool -Name erf
./tools/Bootstrap-Tools.ps1 -ToolsRoot $durableToolRoot
```

```text
<bundled-python> -B tools/shared_tools.py --tools-root <durable-root> resolve armory
```

Bootstrap keeps its directory return value and `Force` argument. A package lock
serializes publication. Downloads and extraction use unique staging paths;
archive and executable hashes must pass before publication. Every cache reuse
checks executable bytes. Completion markers are informational. A valid package
is reused unchanged, including with `Force`. A failed stage leaves an existing
package untouched; invalid replaced installations are retained under shared
`staging/replaced-*` for diagnosis. Abandoned stages are never adopted.

NWNArmory and Neverblender remain manual installs. Resolution prints the required
version and destination when missing. It never downloads these tools. Python,
Blender and NWN remain explicit installed runtimes with recorded actual hashes;
the Windows Store Python shim is rejected.

## Adopting the infrastructure

Adoption happens independently in each active target session after it takes this
change. Leave existing configurations, migrations, selections and launch receipts
unchanged. No active Troll or female worktree was migrated by this PR.

1. Install or verify the pinned tools in the durable root. Keep each consuming
   checkout's vendored compiler and compression executables.
2. Create a fresh ignored binding with `bind_shared_runtimes.py`. Supply explicit
   bundled Python and installed Blender paths. `--nwn` is optional and binds the
   runtime without launching it. Use a fresh output filename for each revision.
3. Execute new CLI and isolated addon/import smokes with `launch_shared_tool.py
   --migration-smoke`. Declare every consumed file with repeated `--input`.
4. Before those smokes, freeze `input-pins.json`: toolchain path/hash and initial
   snapshot; active worktree; source and snapshot hashes for launch helpers;
   preserved historical receipts; saved Blender preferences state; `stockAscii`
   and `equipmentInventory` path/hash pins; `sourcePrefix`; and an explicit
   `equipmentFixtures` list of fixture filenames. Use the pinned installed stock
   inventory for the target rather than a hardcoded female prefix or fixture count.
5. Run the equipment success, collision, partial-batch and corrected-transform
   smokes declared by that inventory. The finalizer requires preserved outputs,
   blocked partial acceptance, verified rigid transforms and unchanged topology,
   UVs and material ownership. It cannot accept production profiles or the client.
6. Finalize to a fresh file with `finalize_shared_tool_migration.py`. Its existing
   verification-directory layout is retained: `python-cli-smoke`,
   `armory-cli-smoke`, `blender-import-smoke`, `armory-equipment-launch`,
   `blender-import.json` and `equipment-smoke/proof.json`.
7. Use that fresh migration via `--migration-receipt` for subsequent launches.
   Helper or binding changes require fresh smoke evidence and a new migration.

```text
<bundled-python> -B tools/phenotypes/bind_shared_runtimes.py
  --python <bundled-python> --blender <installed-blender>
  --tools-root <durable-root> --output .tmp/runtime-bindings/run-001.json

<bundled-python> -B tools/phenotypes/launch_shared_tool.py
  --toolchain .tmp/runtime-bindings/run-001.json
  --migration-receipt <fresh-local-migration>
  --tool blender --output <fresh-launch-directory>
  --input <consumed-stock-model> --input <consumed-preview-configuration>
  -- --python <maintained-preview-helper> -- <existing-helper-arguments>
```

These commands show arguments on separate lines for readability; join them or
use the shell's normal continuation syntax. Blender startup remains isolated:
factory preferences, background mode, four threads, and a verified shared addon
bootstrap. The bootstrap reports the paths and hashes of actually loaded modules
and does not save preferences. Python console and receipts use explicit UTF-8.
Legacy NWN model text keeps CP1252 where declared.

New launch records freeze helper/configuration/input bytes before dispatch,
preserve logs and record actual binary hashes, selected root and inventory hash.
Mid-run changes invalidate the result even if the subprocess exits successfully;
the rejected launch still retains its original pins and failure reason. Addon
source files are registered as consumed inputs. Historical schema1 configurations
remain readable; new launches also enforce the portable Armory/addon pins.

## Dependency declarations and retirement

Automatic registrations write fresh local receipts under
`.tmp/tool-dependencies` and a consumer record under the shared root's
`consumers`. Entries distinguish executable tools, required inputs and historical
provenance. Utility wrappers and phenotype tool adapters register actual resolved
tools; the launcher registers declared input files and addon sources; equipment
staging reuses its frozen input hashes; joint packets register their complete
consumed hash set. Automatic registrations conservatively remain incomplete.
Python and PowerShell registrations use the same byte-range filesystem lock;
Linux registrations preserve case-sensitive path identities.
Native compilation registers each consumed ASCII model and material file with
its frozen hash before dispatch. Reused donor receipts and binaries are pinned
and registered too; drift rejects the run before its final verification receipt.
Opaque CLI arguments and dynamic resource lookup cannot establish whole-worktree
coverage. Registration of one operation never certifies all other operations.

For complete coverage, reconcile an explicit file declaration against the current
ledger, configurations and every active operation. Include generated sources
borrowed from other worktrees. Enumerate individual files and hashes for directory
inputs; directories without an inventory cannot produce a complete declaration.
A complete declaration replaces superseded active references. A later automatic
registration marks coverage incomplete until reconciled again.

```json
{
  "references": [
    {"path": "<actual-required-file>", "role": "input", "sha256": "<verified-hash>"},
    {"path": "<actual-executable>", "role": "tool", "sha256": "<verified-hash>"},
    {"path": "<historical-parent-receipt>", "role": "provenance", "sha256": "<verified-hash>"}
  ]
}
```

```text
<bundled-python> -B tools/shared_tools.py declare --manifest <reconciled-declaration>
<bundled-python> -B tools/shared_tools.py retirement <target-worktree>
```

`Invoke-SrnRetirementAudit.ps1` exposes the same read-only audit with explicit
`-Python`, `-Worktree` and optional `-ToolsRoot`. Reports list consuming worktrees,
required paths inside the target, missing paths, hash drift and incomplete
declarations, including current Git worktrees with no registration. Historical
provenance does not count as an active dependency. `dependencyClear` requires no
active dependencies, missing files, drift or incomplete consumers.

`safeToRetire` remains false: dependency clearance does not prove ignored assets
are archived or authorize removal. The command neither copies nor deletes files.
A borrowed generated input needs a verified local or durable copy before its
source worktree is retired. Mark the old location as provenance only after
configurations and actual consumers use the verified copy. Shared kit code used
by a run must be declared with its actual source paths and hashes.

## Iteration order and joint review

Use this order for new candidate geometry:

1. Write the measured proposal against an immutable parent and protected neighbors.
2. Decode geometry and verify preservation, ownership and attachment frames.
3. Review focused joint motion in standing and measured worst-case samples.
4. Review cumulative assembly and the broader motion matrix before promotion.
5. Process maps and native materials after shape review passes.
6. Complete native attribute, equipment and final client acceptance gates.

Do not repeat expensive map bakes for a shape already failing connector review.
Positive Jacobians and contact numbers remain numerical evidence; visible
anatomy requires review. Placement defects, excess cap geometry, material
transitions and preview-import discrepancies need different remedies.

`joint_review_packet.py` produces a new read-only packet from explicit ASCII
path/hash pins for `parent`, `candidate` and `neighbor`. Each declares `joint`,
a rigid 4x4 `attachmentFrame`, and ordered 2x3 `connectorBounds`. Mesh decoding
preserves local node transforms and corner attributes. Bounds are in the declared
attachment-local NWN space before sampled joint world transforms. The configuration
also supplies target/rig/animation revisions, `asciiDirectory`, optional
`stockDirectory`, `prefix`, `contactAxis`, matched `reviewSettings` with positive
`cameraScale` and at most four threads, material input pins, and `motionSamples`
with clip/time and a standing marker.

Pose measurements require a complete bind hierarchy in the supplied root model.
Both cached and uncached sampling reject missing geometry parents and parent
cycles before publishing a packet. An animation found in a supermodel does not
resolve its inherited bind nodes into the root. Supply a verified complete
effective hierarchy when inheritance is needed; the sampler does not infer it
or rewrite the rig or animations.

The packet records input hashes, centers, extents, attachment frames, axial
interval overlap, closest-corner distances, pose inheritance and the worst
measured samples. It includes matched clay, unlit-color and native-material
review settings and diagnostic questions. These are review specifications and
measurements; the packet does not render or approve anatomy. Use the existing
preview renderer for image review. Native-material previews approximate engine
shading; compare against decoded/native attribute evidence when imports disagree.

Troll's selected proportions and frozen rig remain the Troll session's authority.
The female posture experiment remains a separately versioned animation change
owned by that session. No target anatomy, asset selection or animation was
extracted into this infrastructure PR.

## Faster preparation and verification

`PreparationContext` is scoped to one run. It parses each unique model/controller
resource once, decodes geometry once per semantic decoder/settings key, and
shares immutable prepared arrays and palette images. Bytes, target/rig/animation
revision, helper hashes, numpy version and settings participate in reuse identity.
Inputs are verified when accessed and at completion. Changed bytes invalidate
the context; start a fresh run. Caller-defined decoder kinds/settings must cover
their full dependency set. No prepared arrays grant approval, and cached previews
never count as client evidence.

The pose bridge preserves its existing arguments and gains optional `context`.
The maintained pose renderer and effective material exporter use preparation
contexts. The shared render helper bounds EEVEE and CPU Cycles at four threads.
Preparation counts and stage timings are recorded before proposing more concurrency.
Regenerate benchmark evidence from a clean Git export after helper changes.
The validation record pins the committed helper bytes, and clean-checkout tests
verify the complete declared helper set. This avoids binding evidence to local
line endings that differ from the committed files. Preserve older run receipts.

`tools/test_impact.py` builds a catalog of local imports, literal helper launches
and configuration dependencies. Use `--changed <repository-relative-file> --run`
for iterations. Unknown or uncovered changes and unresolved dependencies trigger
the full Python suite. Dynamic dependencies still require full-suite review;
focused selection is a convenience, not a release gate. Refresh the tracked
`tools/test-impact.json` when helpers change.

Before PR readiness run both full Python suites, full repository verification,
clean-checkout tests and affected native tool smokes. Item-import regressions run only
when `tools/Test-ItemImportScope.ps1` finds item-import changes; CI applies the same gate.
Windows/Linux CI uses an explicit selected interpreter, an explicit shared cache
root and cache keys derived from both tool locks. The copied manual Armory/Blender
installs are verified locally; CI does not download them or launch NWN.

## Current state and integration

`resume_summary.py` uses a fresh binding file that pins the authoritative ledger
path/hash and maps these fields to explicit JSON pointers: `partsBank`,
`targetRevision`, `toolMigration`, `latestDirection`, `rejectedAlternatives`,
`blockers`, `nextAction`, `referenceApproval`, `workingSelection`,
`nativeValidation`, `clientValidation` and `productionAcceptance`.
Optional dependency pins bind actual selected files as well as ledger text.
Multiple pointers for one field must agree. The direction must be unsuperseded
and its sequence must equal the ledger's `currentDirectionSequence`.

Generate to a fresh output with `--bindings` and `--output`. `verify_summary`
rejects stale ledger, binding or dependency bytes. Reconcile missing or
contradictory bindings rather than inferring authority from filenames or old
checkpoint prose. Historical checkpoints remain intact. Later human directions
always take precedence over the saved summary. It changes no goal status.

Parallel candidates may derive from an immutable parent. Before integration,
`verify_integration` checks the expected parent and protected neighbor hashes;
stale selections are rejected. This guard verifies preservation only and creates
no reference, working, native, client or production approval.

## Validation results and limits

The extraction manifest in `shared-tool-extraction.json` records reviewed helper
hashes before changes. Tool, workflow and CI/documentation changes are separate
commits within one PR. Active source worktrees and historical evidence remain
unchanged. The validation record in `shared-tool-validation.json` contains the
executed test results and representative preparation timings.

The benchmark is a synthetic CPU sampler workload, not a production render,
map bake, native compiler or client performance measurement. Real Blender and
Armory smokes verify tool execution and actual addon origin. Fresh target-local
equipment migration and visual/native/client acceptance remain required when
each session adopts this infrastructure. No client was launched for this PR.
