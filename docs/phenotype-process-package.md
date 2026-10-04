# Purpose-built phenotype process package

Start with [the tool entry point](../tools/phenotypes/README.md) and
[the current runbook](phenotype-purpose-built-current-runbook.md).
This package preserves the current individual-part process and its required
implementation dependencies. The completed muscular Human male is the tested
reference case; other races are not presented as validated targets.

## Active process

- [Production contract](phenotype-purpose-built-production.md): stock ownership,
  fitting, mirroring, acceptance and equipment boundaries.
- [Generation procedure](phenotype-purpose-built-part-generation.md) and
  [orthographic conditioning](phenotype-orthographic-multiview.md): coherent
  reference images, live workflow preparation, source preservation and guarded
  single submission.
- [Material preservation](phenotype-body-material-process.md): palette-compatible
  AO, roughness transport, measured skin continuity and immutable neighbours.
- [Whole-body client validation](phenotype-full-body-client-validation.md):
  isolated packaging, native checks, actual observation and literal pose sheets.
- [Current checkpoint](phenotype-goal-checkpoint.md) and
  [Human male delivery](phenotype-human-male-delivery.md): selected inputs,
  completed results and practical limits.

Future hands start with ordinary generation, inspection and fitting. Do not
assume the last Human hand's problems will recur. A sound new donor proceeds
normally; extra diagnosis or repair requires evidence from that donor.
The [hand shell diagnosis](phenotype-hand-shell-diagnosis.md) is a case record.
Its SAT512 recovery, leak patch, fairing, normal smoothing and special retexture
steps are not mandatory stages or default parameters for future hands.

## Evidence and installation boundaries

The user-accepted fourteen-part Human male runtime assets are versioned in
[`srn_body`](../srn_body), registered for the normal HAK builder, and pinned by
[the publication manifest](phenotypes/human-male-assets.json). Rebuild the HAK
with `pwsh ./tools/Build-Haks.ps1 -Pack srn_body`. Every runtime resource retains
its exact native/client-tested bytes; the archive container is a fresh build.

Selected small receipts, frozen case helpers and two animation sheets are
included under `docs/phenotypes/evidence`. Generated HAKs, generation masters,
intermediate maps, Comfy models, game resources and complete local source banks
remain outside Git.
The receipts' absolute paths and implementation commit IDs identify their
original worktree; they are not instructions to submit old jobs in a new clone.
Reproduction requires the recorded source assets and installation dependencies.

The running local ComfyUI `SR_NWN_3d_pixal3d_multi_views` workflow, bundled Python,
Blender, image-to-parts kit and NWN:EE installation are explicit prerequisites.
The orthographic installer verifies upstream sources; it does not vendor model
weights or change the saved live workflow. Current Human rig and equipment
remain at their documented stock settings.

Dated archives and recovery experiments retain their historical labels. Only
the current runbook and declared selected inventories determine continuation.
The [race-sizing plan](phenotype-race-sizing-comparison.md) records later Troll
and equipment work; including that plan does not begin the phase.

## Verification

Use the bundled workspace Python for the included unit tests:

```powershell
$taskPython = 'C:/Users/benco/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
& $taskPython -m unittest discover -s tools/phenotypes -p 'test_*.py'
```

The tests cover current generation guards, orthographic projection, normalization,
stock contracts, mirroring, material/native transport, provenance, resource costs,
reference-sheet evidence and conditional recovery tools. Testing a recovery helper
is not authorization to apply it to a sound future donor. GPU generation and
actual client execution are separate integration steps with their own receipts.

The isolated PR package passed all 107 included unit tests. The recorded Human
native/offline/client checks belong to the exact delivery described above;
this packaging step did not regenerate models or launch another client.

Byte-exact archived documents retain their original relative-link context. Use
the active index and current documents for navigation and continuation.

## Verify the published Human assets

After building `srn_body`, check the source bank and every rebuilt resource:

```powershell
& $taskPython tools/phenotypes/verify_published_body.py --hak output/srn_body.hak
```

This verifies the exact previously tested resource payload. The HAK's container
metadata can differ from the original client archive. The source manifest and
client evidence retain the original package identity. The accepted Human baseline
can be used now; the remaining races take priority over optional further polish.

The [repository publication check](phenotypes/evidence/human-male-publication-v1/validation.json)
records the 26-pack rebuild, 107 passing unit tests, repository regression check
and exact rebuilt Human payload verification.
