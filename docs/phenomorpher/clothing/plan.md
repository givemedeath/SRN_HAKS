# Stock clothing on the PhenoMorpher bodies (NWNArmory)

Durable copy of the approved plan (2026-10-15, section C of the session plan, with the user's answers).
Revisions are appended as dated sections; this text stays as approved.

## Context
The 20 PhenoMorpher bodies (contract 1.1.0, `srn_body`) override only the bare style-001 body parts.
Every other armour style still renders the stock part, sized for the stock body, so stock clothing
shows gaps and overlaps on the new bodies. The user named this as the cause of the clothing gaps.

Decisions from the interview:
* **Scope:** pilot first, then all rigid styles.
* **Route:** NWNArmory affine (pinned `armory` 1.3.4).
* **Troll (G slot):** Human parts of the same style as the source.
* **Danglymesh:** included, after a client compile proof.
* The armour-palette hypothesis (stock non-001 parts showing the new body palette) was disproved by a
  client proof on 2026-10-15; no palette fix is needed. Model-named PLTs ship only where a rule requires.

Standing rules: no subagents unless the user asks; commit at checkpoints, push/PR with approval;
bundled Python; PhenoMorpher runs through `tools/phenomorpher/run.py` with fresh migration evidence;
at most 3 parallel runs, previews at 4 threads; historical receipts and lineage-pinned modules stay
unchanged; no `tools/phenotypes` edits (they widen CI selection).

## Plan
The code is a new toolkit module `engine/stock_armor.py` plus a CLI command. It reuses
`armory_rigid.profile_affine`, `correct_rigid` and `stage_target_rigid_equipment.armory_ini` as lineage
copies; `tools/phenotypes` is not edited. `armory_body_profile.py` is not used: it hard-codes zero
rotation, drops danglymesh and silently falls back to Python.

1. **Inputs, frozen.**
   * Pinned `armory` 1.3.4 (`tools/shared-tools.lock.json`), with its version check.
   * Stock parts for the 20 slots `p{m,f}{d,e,h,o,g}{0,2}`, extracted `--no-ovr` through the managed
     runner, which freezes the key/BIF inputs; binaries decompiled as `inventory_target_equipment.py` does.
   * Excluded: heads, robes (skinned) and the 15 bare body parts that `srn_body` overrides (`neck`,
     `chest`, `pelvis`, `bicep`/`forearm`/`hand`/`thigh`/`shin`/`foot` L/R, all style 001).
   * Kept: `belt001`, `shol001` and `shor001` are real armour.
2. **Sources.** Each slot uses its own stock parts. Troll (G slot) uses Human parts of the same style
   (`p?h0` for `p?g0`, `p?h2` for `p?g2`), because Gnome parts would need 2.4–3.8× stretches. First verify
   that style numbers correspond across races (shape, UV and texture) and report mismatches.
3. **Measured profiles.**
   * Fit one scale → rotate → translate per target × part, in Python, from the source slot's stock
     `<part>001` to the new body's `<part>001` skin mesh, chosen explicitly (the new parts are
     multi-mesh and high-poly).
   * Fit on terminal rings and extents with the B5 ring code; rotation is required (Dwarf male neck
     frame +28.6°, shins 2.6–3.0°).
   * Armory convention: scale along the part's own axes, X/Y rotations negated.
   * Belt uses the pelvis profile corrected for the `belt_g1`↔`pelvis_g` frame offset; shoulders use the
     bicep profile (`l/rshoulder_g` sits at zero offset under the bicep).
   * Record residuals; flag extreme anisotropy (Dwarf feet 0.52×, Large Dwarf forearms 0.36×) for review.
   * The published rigs have `setanimationscale 1.0`: nothing is divided out, no runtime-scale batch.
4. **Danglymesh compile proof first.** Compile one danglymesh part (e.g. `pfd0_chest005`) in the client
   and check it there. If that fails, the user decides between shipping ASCII and deferring. Dangly
   parameters are kept; whether displacement should scale with size is a pilot review question.
5. **Pilot.**
   * Set: the 29 stock clothes `nw_cloth001–029`, 115 rigid parts per body, 2,300 models, 378 of them
     danglymesh. Robes are excluded, so items 005/007/008/012/020/026 are partial.
   * Production: Armory batch per slot, `--values` same-mesh calibration ≤ 1e-5, then `correct_rigid`.
     Compile under the final stock names (compiled binaries cannot be renamed).
   * Offline gates: converted parts against neighbours (thigh–shin, shin–foot, wrist and neck gaps,
     penetration) with the v16 checks, standing and over core motion; PLT/material closure; resrefs
     ≤ 16 characters with no overlap with `srn_body`.
   * Client: Phase 7-style fixture, isolated profile, empty override folder, all 20 bodies, three
     lights, walk/run/combat/cast/death sheets.
   * **Stop for user review.**
6. **All rigid styles:** about 7,700 models, roughly 54 MB binary. Same gates at 3 runs in parallel with
   a sampled client check, into a new `srn_armor` pack with contract plus publication validation and
   `Build-Haks`. Document module attachment: the override is global, so stock NPCs wear the converted
   parts too.
7. **Out of scope:** robes, cloaks and other weighted parts; new garments; the chest–pelvis waist seam,
   which independent affines cannot repair (a review note, not a fix).

## Verification
* Danglymesh compile proof.
* Calibration ≤ 1e-5 and recorded fit residuals.
* Pilot gates pass, and the user approves the client sheets before the full batch.
* Pack build and `verify-assets` pass.

## Critical files
New `tools/phenomorpher/phenomorpher/engine/stock_armor.py` plus tests and CLI/`inputs.py` entries;
`docs/phenomorpher/clothing/*`; `srn_armor/` and its `hakbuilder.json` registration.
