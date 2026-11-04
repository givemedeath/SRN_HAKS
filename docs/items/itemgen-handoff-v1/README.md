# Portable catalog generation handoff

This handoff contains 246 current reference-bound item manifests and their family
drafts. It preserves final input bytes, source/approval bindings, measured image
landmarks, the existing shared trial identity and the five-geometry-attempt limit.
It does not start generation, grant new reference attempts or approve native fit.

The catalog on main remains authoritative for all 286 source identities, gameplay
consolidation, parent reuse and the eight held entries. Three flechette rows are
ammunition modes, and four launcher entries use parent models. Do not generate
duplicate meshes for those rows or standalone meshes for internal/context depictions.
`alreadyPublished` flags matching stable IDs; related source/catalog names are not
permission to replace an approved asset or invent a new identity to reset attempts.

## Restore the final inputs

The verified archive is named `itemkit-catalog-generation-2026-11-03-v1` under
`archives/` in the primary checkout's durable shared tools root. Resolve that root
using `tools/shared_tools.py` / `tools/SrnTools.psm1`; do not search sibling worktrees.
The archive is outside the retiring worktree. Its machine-specific location is
retained in the local checkpoint, not this portable contract.

`archive-verification.json` pins its exact `archive-manifest.json`. The latter
lists every archived path, byte length and SHA256. Verify that manifest's hash and
all its file pins before copying. Use normal file copies, not hardlinks. Copy its
**generation** directory to a fresh ignored output directory in the new checkout:

```powershell
$archive = Join-Path $toolsRoot 'archives/itemkit-catalog-generation-2026-11-03-v1'
$restored = Join-Path $PWD 'output/itemkit/catalog-generation-handoff-v1'
if (Test-Path -LiteralPath $restored) { throw 'Use a fresh restore directory' }
Copy-Item -LiteralPath (Join-Path $archive 'generation') -Destination $restored -Recurse
```

All operational manifest paths are relative to that restored directory. The
`generationFiles` inventory in `handoff.json` includes every required image,
foreground mask, calibration image, audit, approval, grip standard and family.
These are consumed final inputs, not disposable intermediate outputs. The PR
contains the small manifests and inventories; the verified archive carries the
large exact-byte input closure, avoiding another copy of the catalog images in Git.
The archive must accompany the checkout; a Git clone alone does not contain it.

Validate through current main's maintained itemkit code, using the bundled Python
and qualified local package bindings. The input-only check deliberately does not
grant native-contract approval:

```python
import json
from pathlib import Path
from tools.headkit.common import verification_pass
from tools.itemkit.contracts import manifest

root = Path("output/itemkit/catalog-generation-handoff-v1")
index = json.loads((root / "handoff.json").read_text(encoding="utf-8"))
with verification_pass("restored-catalog-inputs"):
    for row in index["rows"]:
        manifest(root / row["manifest"], validate_native=False)
```

Begin a fresh verification pass at later dispatch/completion. Do not retain a
timestamp-only cache. No old reference authoring scripts or retry controllers
are needed. Current main's code, optimizations and native adapters are authoritative.

## Resume without resetting attempts

`resume-state.json` records the exact original ledger hash, trial ID, all 88
terminal transaction identities and reference/model identities. The exact ledger
snapshot and its authorization are in the archive's provenance objects. Bind the
existing live ledger through fresh local bindings; never overwrite a newer ledger
with this snapshot and never call `init-trial` to obtain more attempts. If moving
machines, reconcile the exact archived ledger, all later jobs and identity aliases
before adopting a relocated ledger. The readable summary is not a replacement
dispatch ledger or evidence that a runtime is currently released.

Original source/audit/approval bytes retain historical locators inside archived
provenance JSON. Those locators are evidence, not live dependencies or instructions.
Their bytes remain pinned as input roles; the portable manifests relocate all
operational paths without rewriting the original approvals. Original manifests
are archived too; portable derivatives only change the family filename and remove
machine-specific historical prose from notes, with no approval/preset/fit changes.

## Remaining generation gates

Prepare fresh local Python/Blender/Comfy bindings and migration evidence through
the maintained shared launcher. Reconcile runtime ownership and uncertain jobs
before any dispatch. Qualify the actual loaded service and calibrate cameras.
Retain the current single-image preset, clay geometry, saved-shape detailed
appearance and 200K/768-UDF donor route. No old startup binding is reusable authority.

All family files remain `pending-contract`. The 222 `catalog-object` drafts are
input preparation, not native-family routing decisions or approved final budgets.
Adopt measured native contracts, donor axes/parts, resource reservations and the
applicable grip standard before fitting/export. Rigged Bow/Whip/Crossbow and
Shield exports require their dedicated maintained adapters; do not bypass the
generic exporter's rejection. Compare both shipped Human bodies.

Do not retry the three capped references or resolve the five deferred identities
without authorization. Do not start Comfy or the client under this handoff task.
Production animation remains PhenoMorpher work; motion overlays remain test-only.
No full local regression suite was rerun. No assets, ledgers or worktrees were
deleted; this archive is not a whole-worktree retirement clearance.
