# Wave 1 goal for the parent session

Paste the following into the parent session to activate it. This saved document
does not itself start work or modify the parent's active goal.

---

Set this as the active goal: complete Wave 1 of the catalog weapon implementation,
including the proposed base-item routing changes, and deliver a private test
package ready for user-controlled in-game testing.

Wave 1 consists of these five models:

| Item | Stable design ID | Proposed engine route |
|---|---|---|
| Ingram Smartgun X | ingram-smartgun-x | F7: one-handed ranged; BaseItem 61; WBwSl |
| Stun Baton | sr4-stun-baton-7f6ac2799c | F2: shared one-handed melee; BaseItem 1; WSwLs |
| AK-98 | sr4-ak-98-84e46602ea | F8: shared two-handed ranged; BaseItem 6; WBwXh |
| Heavy Crossbow | sr4-crossbows-heavy-6abe18c0e6 | F8: shared two-handed ranged; BaseItem 6; WBwXh |
| Riot Shield | sr4-riot-shield-800e3413e3 | F12: shield/off-hand; BaseItem 56; AShLw |

Use the ten-family planning baseline saved in
`docs/items/weapon-baseitem-plan-v1/README.md` and `mapping.json` in that directory.
The corresponding `index.html` provides the searchable review. These durable
repository documents replace the side-chat preview-folder dependency.

Read the current authoritative checkpoints and their exact bindings before acting,
especially:

- `docs/items/ingram-smartgun-x-checkpoint.md`
- `docs/items/sr4-generation-preparation-checkpoint.md`
- `docs/items/sr4-reference-images-checkpoint.md`
- `docs/items/approved-weapons.md`

Reconcile the existing Ingram operation before dispatching anything. Resume its
retained work rather than restarting it or duplicating submissions.

Implement and validate the proposed routing, rather than merely changing catalog
labels:

- Stun Baton must exercise the shared blade/blunt one-handed carrier on BaseItem 1.
  Damage category alone must not send it back to Club.
- AK-98 and Heavy Crossbow must exercise the same BaseItem 6 carrier while retaining
  their distinct gameplay identities and appropriate presentation.
- Ingram uses the one-handed ranged carrier, with suitability for off-hand use
  represented separately.
- Riot Shield uses the shield route and correct off-hand attachment.
- Keep AK-98 Grenade Launcher, `sr4-ak-98-grenade-launcher-f10df1fc82`, as a separate
  gameplay entry using the AK-98 parent model. Do not generate separate launcher
  geometry.
- Heavy Crossbow alias `sr4-heavy-crossbow-fc75fdcdc5` must reuse the canonical Heavy
  Crossbow model.
- Keep custom Shadowrun statistics, ammunition modes, scripted magazines/reloads,
  and custom inventory dimensions separate from engine carrier selection.
  Standardize native inventory footprints within each family.
- Do not assume b/m/t model-part slots determine handling categories.

Use inexpensive existing-model probes first where they can expose routing,
attachment, appearance-capacity or presentation blockers. Test the proposed
appearance-ID allocation without changing approved model IDs. Avoid producing
expensive new assets to discover a basic engine incompatibility.

I authorize starting and using this workflow's isolated Comfy runtime for all five
Wave 1 models. Preserve fresh source/runtime verification, actual consumed-input
bindings, shared-ledger reconciliation and the five-geometry-submission limit per
stable model, including historical attempts. Never reset identities or counts.

Use the accepted clay references for geometry and detailed references for
saved-shape appearance. Preserve the approved presets and per-item budgets from
their current inputs. Review actual geometry before appearance; use bounded
repairs. Shallow grooves and harmless pixel differences are nonblocking.

Follow the maintained donor and baking workflow: exact saved shape, 200K UDF donor,
4K appearance/donor transfer and 1K runtime diffuse. Preserve coordinate-frame and
color-space correctness, UV gutters and closed shadow requirements. Use the
approved firearm grip standard for firearms and Cougar melee standard where
applicable. Review fit and native placement on both shipped Human bodies.

Preserve every approved weapon and its packaging unchanged. Reuse the approved
knife, longsword and Colt as controls; use two existing Colt instances for
dual-wield comparison instead of generating another pistol.

Deliver:

1. The five reviewed, fitted and textured native candidates.
2. Explicit routing metadata and focused validation evidence for each proposed
   carrier.
3. An additive private test fixture containing all five candidates, the AK-98
   launcher gameplay entry, all four previously approved weapons, both Colt
   finishes and both shipped Human bodies.
4. A compact review gallery and checkpoint identifying completed checks, remaining
   engine/gameplay dependencies and the exact user test steps.

Validate affected native exports, tables, appearance allocation, package payloads,
icons and attachment contracts with focused checks. Do not rerun the full regression
suite. Actual dual-wield, firing, reload and other client behavior remain pending
until tested; do not claim these are proven by asset renders or table inspection.

If a proposed shared carrier fails a real engine constraint, retain the evidence
and present the smallest necessary amendment with its effect on the ten-family
count. Do not silently restore old routes or modify another worktree's gameplay
systems.

Work directly without subagents. Avoid speculative tooling, redundant reviews,
repeated workbook rewrites and unnecessary tracking. Reuse verified evidence
within each pass while preserving fresh dispatch/completion checks. Update only
affected WIP hubs.

Do not touch another session's runtime, worktree or configuration. Do not launch or
control the game client or promote production.

Notify me once all planned GPU stages have finished, their outputs are collected
and verified, and GPU resources have actually been released through the guarded
procedure. Queue idle alone is insufficient. Continue remaining CPU work afterward.

Stop after Wave 1 is packaged and ready for my in-game review. Do not expand into
Wave 2 or the rest of the catalog.
