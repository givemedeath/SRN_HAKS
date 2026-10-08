# Workspace instructions

- Use the bundled workspace Python on desktop. Never use the Windows Store Python shim. CI uses its explicit setup-python interpreter.
- Shared tool root: explicit argument, then `SRN_TOOLS_ROOT`, then Git's primary checkout `.tools`. Use `tools/SrnTools.psm1` or `tools/shared_tools.py`; do not search other worktrees or borrow executables from them. Pinned vendored tools belong to the consuming checkout.
- Installed Python, Blender and NWN paths stay in ignored, byte-bound local runtime bindings. Shared binaries, local bindings, generated assets and run receipts stay ignored. Never put machine paths in the portable locks.
- Launch new phenotype CLI runs through `launch_shared_tool.py` with fresh local migration evidence and declare actual consumed inputs. Follow `docs/shared-tooling-and-workflow.md`. Direct historical commands remain readable; historical receipts are immutable.
- Before retiring a worktree, run the read-only retirement audit. Incomplete coverage cannot establish dependency clearance. A borrowed generated input needs a verified local or durable copy; provenance alone is historical. Audit output never authorizes deletion or proves asset backups.
- Freeze dependency snapshots before dispatch. Verify helper and input hashes afterward. Integrate a parallel candidate only while its parent and all protected neighbors still match. Preserve each target's approved proportions and rig; animation experiments are separately versioned and owned by the target session.
- Numerical connector success does not approve visible anatomy. Review standing and measured worst-case motion before expensive maps; retain cumulative assembly, broader motion, native and client gates before acceptance.
- Resolve instructions chronologically after compaction. Later directions supersede historical stops. Check current goal and latest user direction before changing goal status; a resume summary does not authorize goal changes.
- Read compact resume state from explicit ledger bindings. Reconcile missing, conflicting or stale bindings; do not choose the newest-looking filename. Preserve historical checkpoints and distinguish reference approval, working selection, native validation, client validation and production acceptance.
- Select validation from changed files and their dependencies, including before PR readiness. Run focused affected tests for helper, configuration and documentation changes; run the full helper suite when shared helpers change. Run item-import regressions when item-import code or its dependencies change. Validate and rebuild affected HAK packs when pack inputs, assets or build tooling change. Reserve full repository scans and all-pack rebuilds for changes with unknown dependency coverage, repository-wide build changes, explicit release checks or a user request. Keep preview rendering at four threads; record timings before adding concurrency.

## Human female target authority

Continue from docs/phenotype-human-female-checkpoint.md and its explicit authoritative ledger/resume bindings. Preserve the stock-exact female rig, stature, attachments, head/neck, equipment sizing and tables. Keep the separately versioned “hips level + original upper lean” experiment and shared-female animation ownership in this target session. Finalize and validate that selected posture before further hip, thigh or torso adjustments.

Shared-infrastructure adoption creates no anatomy, animation or asset approvals and does not resume a paused target goal. Historical receipts/checkpoints remain immutable. Human female PR publication still requires full target validation and explicit final user approval. Other active worktrees are read-only; do not reset, clean, purge or borrow their executable tools.

## Connector taper rule: no shelves

User rule: no shelves when tapering. A connector taper must form a continuous sloped transition between its measured starting and ending contours. Preserve the intended terminal depth/width; spread the transition across eligible anatomy instead of concentrating it into a short band. Do not multiply an existing flare in a way that leaves or introduces a flat shelf, rolled lip, cuff ledge or secondary shoulder at the join. Prefer an explicit endpoint profile, with only small smooth blends at its boundaries.

Review the actual geometry in matched front, side and rear views and in the affected animations before accepting a taper. A new visible shelf blocks that taper even if its numerical geometry checks pass. Preserve protected neighboring parts, garments, UVs, maps and authored normals with explicit lineage; source anatomical features and already approved shapes stay separately documented. The current user-approved ankle shape is preserved while its texture seam is corrected. This rule applies to future phenotype connectors as well as the ongoing torso correction.

Current female infrastructure checkpoint: `docs/phenotype-human-female-infrastructure-adoption.md`. Historical v24 checkpoint and receipts remain unchanged; this adoption does not resume the paused body goal.

Current additive source-adoption progress checkpoint: docs/phenotype-human-female-source-adoption-checkpoint.md. Read its explicit ledger bindings before continuation. Historical adoption checkpoints remain unchanged. Further animation preparation and game-client work await the pending direct user authorization after automatic approval review rejected the attached resume evidence. This pointer grants no asset or publication approval.

## Archives of retired worktrees

Retired worktrees and working data are archived at `<archive-root>` (each folder has `README.txt` and `archive-manifest.json`). Check there before treating masters or evidence as lost. The original Human male worktree (`<worktree-f0b3>`, fitted masters and generated data) is in `human-male-worktree-retirement-2026-10-03-v2`; restore with its `Restore-CompletedHumanWorktree.ps1 -Which original -Destination <new-dir> -IncludeGenerated`. It reuses objects from `human-male-working-data-2026-10-03-v1`; keep both. Restore only into a new directory; archives are read-only and never purged.
