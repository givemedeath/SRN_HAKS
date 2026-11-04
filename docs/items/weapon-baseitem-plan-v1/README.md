# Weapon base-item plan: ten-family baseline

Release status: [approved weapon release packs](../approved-weapons-release.md)
records the implemented fourteen-design subset and its Cougar/Colt migration.
The mapping retains its original planning markers for the broader catalog;
it does not claim that every proposed carrier or gameplay gate is implemented.

User-selected planning baseline, saved from the side conversation.
This is a design and handoff snapshot, not an active production queue or evidence
that the proposed engine behavior has passed. Saving it does not start generation.

- [Combined Wave 1 then Wave 2 goal](waves-1-and-2-goal.md): sequential completion without an intermediate permission stop.
- [Wave 1 parent-session goal](wave-1-goal.md): copyable instructions for the parent session.
- [Wave 2 parent-session goal](wave-2-goal.md): five remaining family representatives, after reconciling Wave 1.
- [Review page](index.html): searchable families, catalog assignments, exceptions and gates.
- [Catalog mapping](mapping.json): version 3; 283 active entries and three merged source identities.

## Decisions

Minimize types by equivalent engine handling, permitted hands, required motion and
presentation. Damage category, weapon name, Shadowrun skill and inventory size do
not independently justify another type. Use scripted Shadowrun statistics and
firearm magazines/reloads; avoid player-managed native gun-ammunition slots.
Preserve melee/ranged, hand occupancy, firing/throwing styles and eligible firearm
dual wielding. The module is Shadowrun-only, so existing fantasy types may be
repurposed. Native footprints can be standardized within each family because the
custom inventory UI owns per-item dimensions. Implants and vehicle weapons belong
to their corresponding systems unless a real hand-held presentation is required.

| Family | Candidate BaseItem | ItemClass |
|---|---:|---|
| F1 Knives/light blades | 22 | WSwDg |
| F2 One-handed melee, including blades and blunt weapons | 1 | WSwLs |
| F4 Heavy two-handed melee | 13 | WSwGs |
| F5 Staffs/polearms | 50 | WDbQs |
| F6 Whips/flexible weapons | 111 | WWhip |
| F7 One-handed ranged | 61 | WBwSl |
| F8 Two-handed ranged, including longarms and crossbows | 6 | WBwXh |
| F9 Bows | 8 | WBwLn |
| F11 Thrown weapons | 63 | WThAx |
| F12 Shields | 56 | AShLw |

Family identifiers retain their original identities; gaps do not imply missing
families. Ten weapon families plus miscellaneous carrier 24 and actual gloves 36
mean twelve proposed numeric rows. Keep approved short-sword compatibility row 0;
existing armor host 16 and any proven arrow/bolt adapter dependencies 20/25 are
separate dependencies. Forearm blades/bracers do not automatically occupy Gloves.

Flechette records merge into parent ammunition modes. Integrated launcher gameplay
entries remain separate while reusing parent assemblies. Existing accepted assets
and appearance addresses remain unchanged until a separately validated migration.

## Validation still required

The selected ten-family design is approved for planning; numeric carrier IDs and
runtime presentation are candidates. The mapping records the full gates:

- Prove common one-handed blade/blunt motion, permitted hands, reach and required
  sounds; compare approved sword presentation with a baton. Damage alone does not
  justify restoring the former split.
- Prove common two-handed longarm/crossbow handling, body-size behavior, firing,
  reload and projectile profiles. Sharing a carrier does not give crossbows firearm
  magazines. Retain the knife class while checking its actual hand/equipment need.
- Prove scripted ammunition consumption, off-hand attack ownership, swapping,
  cancellation and persistence without native combat effects leaking into custom
  rules. Dual-wield support may require gameplay work beyond native asset routing.
- Prove appearance capacity and exact allowed model assemblies. The existing
  24-shape grouping in each of three slots provides only 72 grouped shapes, below
  the snapshot's 80 reference-ready F8 model owners. Test raw appearance-ID
  allocation within the byte contract, preserving approved addresses and finishes.
  A capacity bank, if necessary, is not automatically a new handling family.
- Prove unusual motion, host modes, worn supports and mounted/deployed assemblies
  in their proper systems rather than attaching every assembly to a hand.

If a shared carrier fails, record the demonstrated constraint and the smallest
necessary amendment with its count impact. Do not silently revert to older family
layouts. Native/package evidence is distinct from client and gameplay acceptance.

## Rollout

Wave 1: resume Ingram Smartgun X; generate Stun Baton, AK-98, Heavy Crossbow and
Riot Shield. The [goal](wave-1-goal.md) specifies exact identities, routes, reuse,
generation constraints, controls and completion criteria. Use existing/native
models for inexpensive carrier and appearance probes before expensive generation.
Reuse approved weapons as controls and keep their resources unchanged.

Wave 2 planned coverage: Katana, Staff, Throwing Knife, Bow and Whip. The
[saved Wave 2 goal](wave-2-goal.md) specifies their exact identities, routing,
motion requirements and cumulative test fixture. These are outside Wave 1
authorization; saving the goal does not activate it. The broader catalog mapping remains a proposal;
neither this save nor a routing assignment lifts a source hold or retry cap.

## Snapshot and portability

Mapping version 3 covers 286 original source identities: 283 active records and
three merged flechette identities. It records 216 weapon-family records, 67
system/support records and eight holds (three retry-capped and five source-deferred).
These are snapshot counts, not live production status or generated-model counts.

The original mapping SHA-256 was
`a5f99447a81b942ba19a79785a0cc8b13b3fb690c32ab7b2ed7fc034b3267ed1`.
The saved portable mapping SHA-256 is
`5f2f3a3ba91df596fde960653f3dbb9e1e4d9b6fb72546fc1e1dfa1bba98139e`.
Only workspace path strings were normalized: mapping filesystem paths are
repository-relative; review links resolve from this directory. All records,
assignments, source hashes, holds and gates were preserved. The review page embeds
the same portable mapping and needs no external JavaScript libraries.

Historical source and generated-evidence links still depend on their recorded
inputs existing. Saving this plan does not back up the workbook, reference images,
accepted assets or ignored generation outputs. Before retiring the worktree,
migrate those dependencies and stable WIP links through the established retirement
audit. Use current authoritative checkpoints and verify their exact bindings at
execution; never select a newest-looking file or treat snapshot hashes as fresh
runtime verification.

This frozen handoff is retained with the reviewed release integration. The current
released subset is recorded separately in the release guide linked above.
