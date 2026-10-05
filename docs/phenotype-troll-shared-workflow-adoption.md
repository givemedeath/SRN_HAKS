# Troll adoption of shared tooling and workflow

PR #38 is integrated from `ea08b6db4ef814d44800554add6bba53e4253114` into the existing `codex/troll-male-purposebuilt` worktree. The frozen target remains `troll-male-broadened-offline-frozen-v1`, with the original contract SHA256 `65e25102a970193786a6c6bffd1b9e1ee15c9c0e323f4a83e17deb5e23e97c0a`. Tool adoption creates no body, material, equipment, animation, client or production approval.

## Current launch authority

The local runtime binding is `.tmp/runtime-bindings/troll-pr38-v2.json`. The migration receipt is `.tmp/pr38-adoption-v1/migration-v2.json`. These ignored files contain actual installed paths and hashes. They replace future launch resolution; the earlier binding, migration, selection ledger, checkpoints, execution receipts and source assets remain unchanged.

Use the merged resolver and [shared tooling runbook](shared-tooling-and-workflow.md). Shared installations resolve through the explicit root, `SRN_TOOLS_ROOT`, or Git's primary checkout `.tools`. Vendored compiler/compression tools stay in this consuming checkout. Every new launch uses the binding and passed migration above, declares consumed files, freezes helpers before dispatch and rejects drift afterward. Blender starts with factory preferences, background mode and four threads; its loaded addon modules must match the durable bank.

```text
<bundled-workspace-python> -B tools/phenotypes/launch_shared_tool.py
  --toolchain .tmp/runtime-bindings/troll-pr38-v2.json
  --migration-receipt .tmp/pr38-adoption-v1/migration-v2.json
  --tool python --output <fresh-launch-directory>
  --input <actual-consumed-file>
  --input-manifest <explicit-file-hash-manifest>
  -- <maintained-helper> <arguments>
```

Large Windows runs may use repeatable `--input-manifest` rather than exceeding the command-line limit. Each manifest has schemaVersion `1`, kind `shared-launch-inputs`, and `inputs` containing individual absolute `path`/`sha256` pins. The launcher validates and freezes the manifests and every listed file before dispatch, then verifies them again. Direct `--input` remains supported; directories and unhashed manifest entries are rejected.

## Immutable creation provenance

The frozen Troll contract and part receipts originally pinned creation helpers at live source paths. Infrastructure integration changes those source bytes. The optional binding `historicalHelperBindings` therefore points to a fresh ignored manifest of exact historical helper snapshots. Only this worktree's `tools/phenotypes/*.py` creation helpers can resolve through it. Original hashes must match preserved snapshot bytes; the target contract must remain exact. Geometry, models, maps, configuration and animation files cannot be remapped.

Historical helper snapshots are read as provenance and are never executed. Current helpers remain separately pinned and frozen in every launch. The manifest, current helpers, original snapshots and contract are verified before and after execution. No numerical tolerance or asset-preservation check is relaxed.

## Target authority and workflow

Retain approved Troll sizes, source parents, fixed rig frames, original UV/maps and animation ownership. Hands remain 150% of original; LEFT foot remains 120% uniform; shins remain 76.5% original girth with unchanged length; upper arms retain 110% girth. Preserve the approved chest/collar/traps and pelvis selection. Do not create new shelves, ridges or annular grooves. The source-supported knee proposal and fair ankle trial remain unaccepted; no further geometry work is part of this adoption.

The Human female posture experiment remains separately versioned and owned by its target session. The shared stock-exact contract path supports it without transferring its animation ownership to Troll. No female assets or animation resources are changed here.

Use run-scoped `PreparationContext`, complete verified bind hierarchies, frozen input/helper snapshots and parent/protected-neighbor checks. The adoption's joint packet compares one unchanged stock-derived foot with itself against its unchanged shin neighbor. It proves infrastructure behavior only. Future actual connector candidates still require standing and measured worst-case literal review, cumulative assembly, broader motion, native and client gates before acceptance.

Resume from the fresh explicit bindings described by [the adoption checkpoint](phenotype-troll-pr38-adoption-checkpoint.md). Keep reference approval, working selection, native validation, client validation and production acceptance distinct. Do not infer authority from file timestamps. Later user directions govern continuation; the resume summary changes no goal status.

Dependency registrations and retirement audits remain read-only with respect to former worktrees. Incomplete declarations cannot clear retirement. No archive or deletion is authorized by this adoption, and no game client is launched. Final phenotype delivery still requires all pending geometry, material, equipment, packaging and actual client evidence.