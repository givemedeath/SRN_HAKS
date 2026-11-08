# Published heads vs polish-v1 channel rules (audit, 2026-10-27)

This audit checks every head in `srn_head` on `origin/main` against the race heads polish-v1 rules (runbook rows 83-85 in [race-heads-v1-runbook.md](race-heads-v1-runbook.md)):
- **Rule 83:** every mapped PLT channel is tone-matched to a stock reference.
- **Rule 84:** the channel convention is 0 skin, 1 hair, 2 metal, 8 bone, 9 ink.
- **Rule 85:** metal rules are checked against the baked metallic map.

It is read-only. Nothing was repaired, and no published file changed. The working data is in the batch folder `race-heads-v1/published-audit/` (ignored scratch):
- `plt-audit.json`, `runs-audit.json`, `troll-metal-audit.json` and `repair-inputs.json`.
- The locator and reconstruction scripts.

## Scope

`srn_head` publishes 34 heads, all trolls: 18 female (`pfg0_head010`-`023`, `032`, `090`-`092`) and 16 male (`pmg0_head015`-`030`).

| Finding | Heads | Repair |
|---|---|---|
| Hair, metal and tattoo channels not tone-matched (quantile gap to the reference 15-219 shades) | all 34 | palette |
| Skin not tone-matched (gap 26-58 shades) | `pfg0_head032`, `090`, `091`, `092` | palette |
| Channel convention deviations | `pmg0_head016` (horns on hair), `pmg0_head018` (horns on hair, tusks on 9, scalp stripes on 8), `pmg0_head019` (horns and tusks on 9); possibly `pfg0_head016` (hair bands on hair) | ownership; changes their in-game colour pickers, so this needs the user's call |
| Metal ownership to review (neutral metallic texels on skin, or metal rules with no metallic texels) | `pfg0_head013`, `014`, `012`; `pmg0_head017`, `018`, `020`, `026`, `027` | ownership, after a look |
| Not neck-cut (the 2026-10-25 neck-cut replacement covered 30 other heads) | `pfg0_head032`, `090`, `091`, `092` (to verify) | geometry |

Skin is tone-matched on all 30 headkit heads (gap 3.3 shades or less).
- Baked metallic is unreliable on `pmg0_head019` and `pmg0_head028`: hair and horns are flagged as metallic.
- `pfg0_head017` and `pmg0_head021` put an iris or lens on a tattoo channel. The convention allows that.

## Sources and repair route

**29 heads with headkit runs.** These are `pfg0_head010`-`023` and `pmg0_head016`-`030`, in `S:/Scratch/claude-scratch/troll-*`. Each was matched to its run by the SHA-256 of the published PLT and MDL against the export and native outputs.
- **What exists.** For every run, every manifest input is present with its pinned hash, including `raw.glb` and `field.npz`, and every stage output exists.
- **Recommended route: imported checkpoints.** Start a fresh headkit run per head that imports the approved UV mesh, 4K bake, metallic map and fit matrix as reviewed checkpoints. Then rerun only ownership, palette, export, native and render on the current toolkit.
  - Geometry and UVs stay byte-identical to the published heads.
  - The files this needs are listed with SHA-256 in `repair-inputs.json`: 0.43 GB, all verified against the original receipts. `pfg0_head013` (troll-female-07) uses the reviewed manual matrix in its manifest instead of a fit proposal.
- **Why the old runs can't be resumed in place:**
  - Their receipts pin this worktree's tool files by absolute path, and those files have changed since.
  - Batch 2's exact toolkit (20 heads) can be rebuilt from git: snapshot S0 matches every stage's code version. It still fails those absolute-path file pins.
  - Female batch 1 and `pmg0_head016`-`020` ran their stages under mixed toolkit versions (the neck-cut reruns came later), so no single tree keeps them fresh.
- **Why not a full rerun from prepare:** it would change the approved geometry, through the new neck-cut snapping and reduction.

**5 heads without a located run.**
- **`pmg0_head015` (troll-male-01).** Its run folder `S:/Scratch/claude-scratch/troll-male-01` (`finish-v3/run`) is referenced by other receipts but no longer exists on any drive or in the archives. Only the published MDL and PLT remain.
- **`pfg0_head032`, `090`, `091`, `092`.** These predate headkit (attempts 63, 68, 73 and 74). They have partial artefacts in the shared tool root:
  - `091` (head73) and `092` (attempt 74): UV mesh plus 1K shade and layer maps (`headkit-verification-20261020-v1`, `headkit-pr54-*`).
  - `032`: a repaired UV head (`head-production-candidates/troll-female-03-attempt63-v20-rc1`).
  - `090`: only comparison evidence.
- **Route for all five:** remap each layer of the published PLT by rank onto its stock reference. This works because nearest-colour shades within a row follow luminance. Layer moves would use the MDL's UVs and the decoded colour.
  - The published MDL and PLT are in git, so these inputs are durable.
  - The neck-cut repair for the four older heads would start from the published MDL.

## Risk

The 29 run-backed heads' repair inputs exist only in ignored scratch on `S:`, with no archive copy. The minimal set is 0.43 GB. The full run folders with the GPU outputs are far larger.
