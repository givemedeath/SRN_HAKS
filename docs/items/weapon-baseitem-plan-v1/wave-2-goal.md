# Wave 2 goal for the parent session

Paste the following into the parent session to activate it. Saving this file does
not start generation, replace an active goal or establish that Wave 1 passed.

---

Set this as the active goal: complete Wave 2 of the catalog weapon implementation,
covering the remaining five handling families in the proposed ten-family plan.
Deliver reviewed native candidates and a cumulative private test fixture ready
for user-controlled in-game testing.

## Scope and starting state

| Item | Stable design ID | Proposed engine route |
|---|---|---|
| Katana | sr4-katana-f7ac8ecfb3 | F4: heavy two-handed melee; BaseItem 13; WSwGs |
| Staff | sr4-staff-dc4c1668ea | F5: staffs/polearms; BaseItem 50; WDbQs |
| Throwing Knife | sr4-throwing-knife-2273b8c3cf | F11: thrown weapons; BaseItem 63; WThAx |
| Bow | sr4-bow-dd7dc09f67 | F9: bows; BaseItem 8; WBwLn |
| Whip | sr4-whip-eab35fc25c | F6: whips/flexible weapons; BaseItem 111; WWhip |

Use `docs/items/weapon-baseitem-plan-v1/README.md` and `mapping.json` as the saved
planning baseline. These five identities had conditioned reference pairs and no
hold in that snapshot; verify their current exact input and source bindings.
Do not substitute Stun Staff, Telescopic Staff, Collapsible Bow or Monofilament
Whip, or dispatch their geometry as additional Wave 2 models.

Read the current authoritative generation and reference preparation checkpoints,
`docs/items/approved-weapons.md`, and the parent session's explicit Wave 1
checkpoint. Reconcile any active or uncertain operation before dispatching.
Continue retained work for these stable identities where it exists; never reset
their ledgers or repeat terminal jobs.

Establish the actual Wave 1 disposition first. Reuse its verified native-routing
and appearance-allocation work and preserve accepted outputs. Do not restart
Wave 1 or imply its client checks passed. Carry unresolved independent checks
forward explicitly; a demonstrated shared infrastructure blocker must be resolved
or reported before spending generation attempts that depend on it.

## Routing and presentation requirements

Implement actual native routes and exact model assemblies, not just labels:

- Katana exercises the two-handed swung-melee carrier on row 13. Check hand
  occupancy, grip and blade orientation, reach and attack presentation on both
  shipped Human bodies. Preserve source proportions; do not move it to the
  one-handed family merely because it is a blade.
- Staff exercises row 50 and its distinct staff/double-ended presentation. Check
  both hand contacts, shaft alignment, swings and attachment behavior. Native
  double-weapon rules or extra attacks must not silently become Shadowrun rules.
- Throwing Knife exercises row 63. Check held orientation, release point,
  projectile orientation and return to the equipped state. Specify stack,
  depletion and inventory ownership so one logical throw cannot consume twice.
  Do not route it as an ordinary melee dagger or duplicate the approved knife.
- Bow exercises row 8. Preserve the source's limbs, string and intentional
  openings. Check the bow hand, drawing hand, arrow/nock alignment and draw/release
  presentation. Identify necessary arrow model/ammunition dependencies explicitly;
  avoid duplicating consumption between the native adapter and scripted rules.
  The firearm no-player-ammo-slot policy does not prove a bow can omit its native
  dependencies.
- Whip exercises row 111. First inspect the native donor's hierarchy and required
  flexible motion. Preserve or explicitly adapt that structure rather than
  attaching an entire rigid generated coil to the hand and calling it complete.
  Check resting silhouette, grip, extension and attack motion. If the source shape
  cannot support the required motion, report the exact rig/presentation blocker
  and a bounded remedy before expensive appearance work.

Use existing/native models for inexpensive behavior and attachment probes before
new geometry where possible. Reuse Wave 1's appearance allocator and existing
proved assembly contracts; implement only necessary route-specific changes.
Preserve approved appearance addresses and finishes. Keep native footprints
standardized within each family; custom UI dimensions, Shadowrun damage, skills,
effects and ammunition remain item/profile data.

Reuse approved Knife and Longsword assets to compare retained small-weapon and
common one-handed handling. Together with the four distinct Wave 1 families and
these five Wave 2 families, the test fixture should represent all ten. This is
coverage for testing, not a claim that every catalog outlier or runtime gate has
passed. Do not add another type for damage category or a weapon's name. A proven
exception requires the smallest amendment and its explicit count impact.

## Generation, fit and efficiency

I authorize using this workflow's isolated Comfy runtime for these five Wave 2
models, including starting it when genuinely available. Do not interrupt or alter
another session's runtime, worktree or model/input/output configuration. Queue
idle alone does not establish ownership release.

Use maintained itemkit launch, native packaging and recovery methods. Preserve
fresh source/runtime checks and actual consumed-input bindings at dispatch and
completion. Keep the shared ledger and at most five geometry submissions per
stable model, including historical attempts. Reconcile uncertain jobs before a
retry. Use bounded repairs; report capped or blocked items without inventing
completion or automatically substituting another design.

Use the accepted clay image for geometry and detailed color image for exact
saved-shape appearance. Preserve current presets and per-item budgets. Inspect
actual geometry before appearance; shallow grooves and harmless pixel differences
are nonblocking. Do not regenerate accepted references for cosmetic cleanup.

Use the maintained 200K UDF donor, 4K appearance/donor-transfer and 1K runtime
diffuse workflow, preserving correct coordinate frames, color space, UV gutters
and required shadow geometry. Bind flexible assets to the required native motion
before treating their fit or bake as final. Use the Cougar melee grip standard
where applicable; measure appropriate staff, bow and whip hand contacts instead
of blindly applying a sword's multiplier or usable-grip length. Review both
shipped Human bodies and retain protected proportions.

Work directly without subagents. Do not build speculative tooling or another
tracking system. Reuse exact reviews and verification results within each pass,
retain fresh boundary checks, and update only changed WIP hubs once per coherent
result. No whole-workbook rewrites or full regression suite. Run focused checks
and affected native/package builds appropriate to actual changes.

## Deliverables and stopping condition

1. Five reviewed, fitted, textured native candidates with the proposed routes,
   exact assembly metadata and focused validation evidence.
2. An additive private fixture containing the Wave 2 candidates, all completed
   Wave 1 candidates and its AK-98 launcher gameplay entry, all four previously
   approved weapons, both Colt finishes and both shipped Human bodies. Preserve
   previously accepted payloads unchanged; compare exact resources when combining.
3. A compact gallery and ten-family test matrix distinguishing reference review,
   native/package checks, hand-fit/motion review and pending client/gameplay tests.
   Include specific user tests for hand occupancy, equip/unequip, saving/reloading,
   ranged/throw consumption, bow drawing and whip motion.
4. A resumable checkpoint with exact current bindings and any bounded blockers,
   remaining attempts or gameplay dependencies. Retain required raw provenance
   through the existing pipeline without adding redundant per-step bookkeeping.

Validate native exports, required hierarchy/animation contracts, appearance IDs,
tables, icons, attachments and final package payloads. Do not claim that renders
or table checks prove actual engine attacks, consumption or flexible animation.
If a gameplay adapter is absent, identify the dependency rather than changing
another active worktree or claiming the feature is implemented.

Notify me once all planned GPU stages are finished, outputs are collected and
verified, and this workflow has actually released GPU resources through the
guarded ledger/queue procedure. Then continue remaining CPU work.

Do not launch or control the game client, promote production or expand into more
catalog items. Stop when Wave 2 is packaged for my review, or report specific
blockers if permitted work cannot advance. Final client/gameplay acceptance
remains pending until separately tested and approved.
