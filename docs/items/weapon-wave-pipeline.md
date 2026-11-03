# Weapon wave pipeline changes

This change retains the generation, fitting and native-export improvements used
for the approved weapon waves. The approved assets and private test module are
published independently in PR #73. Neither change promotes the fixture's private
table or Human motion overrides into the production packs.

## Generation and verification

- Optional preparation identity binds an unsent request to verified startup.
  Dispatch under the queue lock and completion still perform fresh live checks.
  Legacy callers keep their full preparation check.
- Reuse source parsing and indexes within verification, while checking live
  callback bytecode and conditional instance settings. Serialize memory-heavy
  verification passes and stream startup-proven object checks without retaining
  their instances/functions.
- Combine saved-shape appearance with the qualified 200K / 768-resolution UDF
  donor export. Preserve raw shape/appearance outputs and permit an independent
  working-shell export without changing the color donor contract.

## Fitting, baking and native export

- Extend measured native contracts to the additional weapon families, including
  rigged Bow/Whip and the two-handed firearm carrier. Preserve explicit native
  part assignments, budgets, icon sizes and resource collision checks.
- Preserve mating rims during reduction, support small-coordinate UV charting,
  and recover selected bake misses using explicit sampling patches. The original
  appearance frame remains authoritative.
- Export exact native skin corner attributes, shadows and animation controllers;
  retain original weapon clips when adding body-animation aliases. Qualify
  binary NeverBlender roundtrips separately from display normals.
- Keep one-handed firearm motion additive and private. Fixture repair retains
  save/reload environment resources, waits for a valid player area and clears
  queued reviewer actions before staging.

The measured stage timings and limitations are in [four-weapon-lessons.md](four-weapon-lessons.md).
In particular, avoiding a separate donor dispatch saved approximately one
five-minute export cycle in the Katana run. This is not evidence that every item
now finishes within two hours.

## Scope and validation

Temporary catalog image retry runners, machine bindings, generated assets and
historical run receipts are excluded. Existing local work is preserved separately.
The dependency catalog is regenerated from the complete tracked documentation.
Validation uses the affected helper modules and native package checks; the full
regression suite is not rerun. GitHub's existing catch-all CI rules can request a
full suite for new resource paths or catalog changes; that run must be cancelled
for this review under the user's explicit validation constraint.
