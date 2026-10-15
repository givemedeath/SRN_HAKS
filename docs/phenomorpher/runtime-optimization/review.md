# Runtime optimization: Phase 6 offline review (contract 1.1.0)

Offline verification of contract [1.1.0](../game-ready-assets.json) against 1.0.0 at `0866bcaf`, plus a
read-only PhenoMorpher check sweep. This review creates no asset, motion, client or production approval.
Client validation stays pending (`runtimeOptimization.clientValidated: false`); the client checklist
below is the input to Phase 7.

## 1. Resource accounting

Every 1.0.0 → 1.1.0 resource change is classified; there are no unexplained changes.

| Class | Count |
|---|---:|
| Body-part MDLs, byte-identical | 300 |
| Fitted rigs, byte-identical (`pfh0`, `pmh0`) | 2 |
| Roots changed only in the supermodel field | 18 |
| Animation libraries added | 8 |
| Private carriers retired | 108 |
| Textures downsampled 2048 → 1024 | 81 |
| `srn_fa_h0` posture library, byte-identical | 1 |
| Palettes, materials, one map, head aliases, routing and 2DA files, byte-identical | 521 |

Routing: no new reference resolves to an installed-game resource other than the pinned
`a_fa > a_ba > … > a_ba_casts` chain; unreferenced resources are unchanged; private carriers go from
109 to 1 (`srn_fa_h0`); textures above 1024 px from 81 to 0. All 375 consumed textures pass header,
PLT-layer, normal-length and roughness-range checks.

## 2. Motion

`compare-motion` of the 1.0.0 chain against the 1.1.0 root > library > installed chain, for every
effective clip of all 20 bodies: all pass. The worst assembled drift is 7.8×10⁻⁷ m (Human Large,
inherited clips) and 1.3×10⁻⁷ m on the non-Human bodies. Female posture (`pause1`/`pause2`) is exact on all 10
female bodies.

Clip counts per body (Fit / Large where they differ):

| Bodies | Exact | Inherited, exact | Inherited, within 0.1 mm / 0.05° | Authorized Fit `2hslashl` |
|---|---:|---:|---:|---:|
| Dwarf F | 168 / 167 | 0 | 4 | 0 / 1 |
| Dwarf M | 169 | 0 | 3 | 0 |
| Elf, Orc, Troll F | 147 / 146 | 0 | 25 | 0 / 1 |
| Elf, Orc, Troll M | 147 | 0 | 25 | 0 |
| Human F | 2 | 170 / 158 | 0 / 11 | 0 / 1 |
| Human M | 0 | 172 / 166 | 0 / 6 | 0 |

Receipt: `.tmp/runtime-optimization/phase6/offline-002/phase6-offline.json`.

## 3. Textures: matched 2K / 1K renders

`pfh0` and `pmh0` together consume all 56 downsampled maps and all changed PLT payloads. Blender
renders (4 threads) with identical geometry and rig samples, 2K maps from 1.0.0 vs 1K maps from 1.1.0:
idle front/side/rear, worst-case `walk`, `run` and `nwkickl` frames, and neck, shoulder, waist, thigh,
knee, ankle and close-leg views.

Over 38 views: mean absolute difference ≤ 0.56/255, 99th percentile ≤ 4/255, maximum 37/255 at
cloth-edge texels, at most 0.013 % of pixels above 16/255. No seam, dye bleed or skin↔cloth
contamination is visible. Pre-existing features (ankle step, tone steps, neck stub) look the same at
2K and 1K.

Sheets: `.tmp/runtime-optimization/phase6/matched-sheets-001/` (`*-full-idle`, `*-full-motion`,
`*-close`, `pixel-differences.json`).

## 4. Read-only PhenoMorpher check sweep

All 20 bodies of 1.1.0, with the same-gender Human donor of the same build as the baseline at stature
scale (`p{g}h{build}`):

* native attributes per model (node, vertex, triangle and attribute inventory);
* geometry audit (degenerate and coincident cross-part triangles);
* `measure` (stature, segments, sections, view-mask hashes);
* terminal minimum clearance (v13c) and connector surface coverage and penetration (v15), on the
  body itself and against the donor;
* connector checks over sampled motion of the body's own effective clips — `pause1`, `pause2`,
  `walk`, `run`, `nwkickl`, `nwkickr` and the Phase 7 stop-gate clips `walk_swordr`, `run_swordl`,
  `tlknorm`, `salute`, `greeting`, `torchl` — per connector against the donor at the same normalized
  time, plus the lowest sole relative to the standing floor.

Contract-level checks: `verify-assets` (931 resources, Phase 5), `anim-library inventory` and
`compare-motion` above. `rig_pose_audit` / `rig_controller_audit` read ASCII retarget sources and do not apply to
published binaries; `anim-library inventory` and `compare-motion` cover chains, controller signatures
and clip owners for them.

### New vs pre-existing

No finding is new in 1.1.0. Body parts are byte-identical, so every static result is identical by
construction; a 1.0.0 run of the same static checks on `pfd0` and `pmg2` (with donors `pfh0`, `pmh2`)
reproduces the 1.1.0 values: native info, geometry, measurements and both connector audits are equal field for field. Assembled motion matches 1.0.0 within 7.8×10⁻⁷ m for every
effective clip, so every motion result is pre-existing too.

### Findings

Static, all 20 bodies: no degenerate triangles, no coincident cross-part triangles, every required
terminal contact and source-calibrated clearance gate passes (self and against the donor).

| # | Finding | Bodies | Class |
|---|---|---|---|
| F1 | Shin–foot overlap: 94–138 intersecting triangle pairs at every sampled frame, against 2–31 on the Human male. Identical in standing and in stock-owned clips, so it is the static ankle join. | Dwarf, Orc, Troll M (Fit and Large) | inspect in client |
| F2 | Soles below the standing floor, deeper than the scaled Human male: `run` +27–29 mm (Orc, Troll), +17 mm (Dwarf); `nwkickl`/`nwkickr` +20–29 mm (Orc, Troll), +13–16 mm (Dwarf); `walk` +8 mm (Orc, Troll). Library-owned clips carried unchanged from 1.0.0. | Dwarf, Orc, Troll M | inspect in client |
| F3 | Soles in `walk` +8–12 mm deeper than the scaled Human female (Dwarf 11–12, Troll 9, Orc 8); `pause2` +5–6 mm (Troll, Orc) and `nwkickl` +5 mm (Dwarf, Troll). | Dwarf, Orc, Troll F | inspect in client |
| F4 | Shin–foot seam opens 0.2–0.6 mm beyond the scaled donor in `walk`, `run` and kicks. | Elf M | inspect in client |
| F5 | Fit neck meshes have different topology from the Human Fit neck, so they drop out of the donor-relative connector comparison. Neck–chest and neck–head are not in the connector link set at all. | Elf, Orc, Troll Fit | adjust in tooling |
| F6 | Penetration is unavailable for every connector of the female bodies: the opposing terminal bands are open, not closed manifolds. Clearance and coverage are still measured. | all F | adjust in tooling |
| F7 | Donor-relative seam residuals up to 76 mm (Troll M chest–bicep; up to 54 mm for Dwarf hips and shoulders). They quantify the approved proportion changes against the scaled Human donor, not a defect; static gates pass. | non-Human | none (informational) |

Absolute reference: with the stock `a_fa`/`a_ba` clips, the client-approved Human bodies already dip
below the standing floor (female `walk` −31.5 mm, male `walk` −7.8 mm), so F2 and F3 are measured
relative to that accepted baseline. No finding is classed **adjust in assets**: none is new, and any
asset or animation change belongs to a separately versioned target experiment, not to this runtime
release.

### Known gaps

* No neck–chest or neck–head connector check (F5).
* No solid penetration measure for open meshes (F6).
* The 1.0.0 static checks ran on two bodies, not 20; the byte-identical body parts make the rest
  identical by construction.
* The motion baseline is the scaled Human donor, a heuristic; it is not the stock race model.

Sweep outputs: `.tmp/runtime-optimization/phase6/sweep-new-{7,8,9}/` (1.1.0) and `sweep-old-2/`
(1.0.0); receipts in the matching `launch-*` folders.A first run (`sweep-new-{1,2,3}`) was invalidated by its launcher because a
toolkit commit (`cli.py`, `test_cli_contract.py`, outside the sweep's imports) landed while it ran; the
frozen rerun passed input verification and reproduced all 20 outputs byte for byte.

## 5. Tests

* PhenoMorpher package suite: 111 tests pass, including the new `test_anim_library`,
  `test_texture_downsample`, `test_runtime_release` and `test_cli_contract` cases.
* No `tools/phenotypes` helper changed in Phase 6, so the full helper suite was not rerun; it passed in
  Phase 5.

## 6. Phase 7 client checklist

Baseline (1.0.0) vs candidate (1.1.0) in isolated `-userdirectory` profiles; the normal install is untouched.

**Stop-gate (inherited clips).** Any visible difference between baseline and candidate stops the work:

* Troll, Elf and Orc `walk_swordr`, `run_swordl`, `tlknorm`, `salute`, `greeting`;
* Dwarf `torchl`.

**Sweep findings.** These look the same in baseline and candidate; record whether each is acceptable:

1. F1 — Dwarf, Orc and Troll male ankles: bare feet and boots, standing, `walk` and `run`, close view.
2. F2 — Dwarf, Orc and Troll male feet against the floor in `run`, `nwkickl` and `nwkickr`, and in
   `walk` (Orc, Troll).
3. F3 — Dwarf, Orc and Troll female feet against the floor in `walk`, and in `pause2` (Orc, Troll).
4. F4 — Elf male ankle seam in `walk` and `run`, close view, white interior light.

**Planned coverage.**

* All 20 bodies.
* Idles, `walk`/`run`, kicks, melee and ranged, casting, sit/kneel, knockdown and death.
* Clothing, robes, cloaks, weapons and shields.
* Outdoor and white/warm interior light.
* Tone, dye and close leg views.
* Fit and Large side by side.
