# Runtime optimization: Phase 7 client session (contract 1.0.0 vs 1.1.0)

One NWN:EE client session (build 8193.37-17) on 2026-10-14 compared contract 1.0.0 (`0866bcaf`) with
contract 1.1.0 using the same module, camera commands and timing in two isolated profiles. The
inherited-clip stop-gate passed: no visible difference. No 1.1.0 regression was seen. This records
client observations only; it creates no asset, motion or production approval, and 1.1.0 user
acceptance is still pending (`runtimeOptimization.clientValidated`/`userAccepted` stay `false` until
Phase 8).

## Fixture

`.tmp/runtime-optimization/phase7/build_fixture.py` (managed launch, declared inputs) builds one
module and two `-userdirectory` profiles. They differ only in the two body HAKs:

| Profile | `srn_body.hak` | `srn_body_tex.hak` | Packed from |
|---|---|---|---|
| v100 | 765 resources, `8b170eef…` | 263, `501fb4a1…` | 1.0.0 export, blob-checked against `0866bcaf` |
| v110 | 665 resources, `ebe5dd76…` (667,871,456 B) | 263, `ef036cc2…` (176,204,022 B) | worktree, blob-checked against HEAD |

Shared by both profiles, byte-identical:

* `srn_2da.hak` (`d810ea84…`), unchanged since 1.0.0;
* the fixture HAK, which holds the stock rural tileset renamed with grass density 0 so feet stay visible;
* the module (fixture-003 `1e02039a…`, fixture-004 `8279ff2f…`).

The module places all 20 bodies in a 5 × 4 grid: rows are Dwarf, Elf, Human, Orc and Troll; columns are F Fit, F Large, M Fit and M Large. Each body has bare parts style 1 and stock head 1. Chat commands (`!p7 …`) drive:

* the camera;
* `show <row>` (that row on the front line);
* animations;
* locomotion;
* hand equipment, armour, robe and cloak;
* unarmed combat against non-commandable dummies;
* fake spellcasting;
* knockdown, death and resurrection;
* lighting through `SetAreaLightColor`: white interior, warm interior and outdoor.

Launches went through `Launch-P7.ps1`. It hash-checks the profile and requires an empty override and no running client, then writes `client-launch-<profile>-<pid>.json`:

| Fixture | Profile | PID | Use |
|---|---|---:|---|
| fixture-003 | v100 | 25076 | stop-gate, textures |
| fixture-003 | v110 | 5780 | stop-gate, textures, sweep checks, combat, cast, knockdown, death |
| fixture-004 | v110 | 20076 | clothing, robe, cloak, death and resurrection |
| fixture-004 | v100 | 15908 | clothing comparison |

fixture-004 adds two changes:

* corpses persist (`SetIsDestroyable`). In fixture-003, `die` destroyed all 20 actors because commands applied to every row;
* `show` limits commands to the shown row.

The body HAKs are byte-identical to fixture-003.

## Stop-gate: inherited clips

These clips are owned by stock `a_ba`/`a_fa` in 1.1.0 and by the private carriers in 1.0.0. For each race row,
the same command sequence ran in both profiles. Sheets: [Elf](client/stopgate-elf.jpg),
[Orc](client/stopgate-orc.jpg), [Troll](client/stopgate-troll.jpg), [Dwarf](client/stopgate-dwarf.jpg).

| Clip | Trigger | Rows | Result |
|---|---|---|---|
| `walk_swordr`, `run_swordr` | longsword, walk and run | Elf, Orc, Troll | same pose and stride; no limb offset |
| `walk_swordl`, `run_swordl` | two short swords | Elf, Orc, Troll | same |
| `tlknorm` | `ANIMATION_LOOPING_TALK_NORMAL` | Elf, Orc | same (subtle loop) |
| `greeting` | `ANIMATION_FIREFORGET_GREETING` | Elf, Orc, Troll, Dwarf | wave plays in both. The motion is about 0.7 s long, so frames differ in phase only |
| `torchl` | torch, idle and walk | Elf, Orc, Troll, Dwarf | torch held up identically |
| `xbowr` | light crossbow | Dwarf | same |
| `run_bowl` | longbow, run | Dwarf | same |
| `salute` | `ANIMATION_FIREFORGET_SALUTE` | all | **not observable**: no salute plays in either profile, nor on the unchanged Human Fit bodies on stock `a_ba`. It is an engine or fixture limitation, so the offline result stands (inherited, within 0.1 mm / 0.05°) |

An unkeyed node taking supermodel frames would show limb or head offsets of 150–230 mm (up to 1.15 m for
`headconjure`). None appeared, which confirms the Phase 3 inference in the client.

## Textures (1K)

[Sheet](client/textures.jpg): Human F and M Fit (white, warm and outdoor light), male legs and rear, Troll M Fit, Dwarf M
Fit ankles. 1.0.0 and 1.1.0 look the same: no seam, dye bleed, blur or tone shift. Pre-existing joint
lines under warm directional light are present in both.

## Sweep checklist (Phase 6, F1–F4)

| Item | Observation (1.1.0; geometry and motion equal 1.0.0) |
|---|---|
| F1: Dwarf, Orc and Troll male ankles | No visible poke-through at row distance or in the Dwarf M close view |
| F2: male soles in `run` and kicks | Feet read as on the floor in low front views of `run` and unarmed combat. The measured 13–29 mm dip is not resolvable at gameplay distance |
| F3: female soles in `walk` | Same: no visible sinking at gameplay distance |
| F4: Elf male ankle seam | Not separately close-inspected; nothing visible at row distance |

## Further coverage (1.1.0)

[Sheet](client/v110-coverage.jpg): Orc low walk and run, Orc unarmed combat (punches and kicks), Troll fake
fireball cast, knockdown, death, and Elf death and resurrection in robes. Equipment: stock clothing, plate, robe 3, cloak.
All play without gross defects. Fit and Large sit side by side in every row.

### Stock clothing (pre-existing, same in 1.0.0)

[Sheet](client/stock-clothing.jpg): stock `nw_cloth001` on the Elf row leaves gaps between thigh and shin
and between shin and foot, and the neck is bare. The stock armour parts were authored for the stock rigs. This is identical in
1.0.0 and 1.1.0. Per user direction, the stock clothing still has to be converted through nwnarmory
with the new phenotype profiles. That is separate work, not part of this runtime release.

## Not covered

* `salute` (see above).
* Shield (`walk_shieldl`, `pausesh`) and longbow walk on Elf, Orc and Troll. Sword, dual-wield, torch, crossbow and bow
  (Dwarf) were covered.
* Mounted clips (`mount1*`), `custom3`/`custom4`/`custom6`, and Human Large `sit`/`sitdown`/`plclose*`.
  These are inherited within tolerance offline and were not triggered in the client.
* A full matrix across all lights and all rows. Light variants were captured on the texture close-ups.

Evidence: sheets and `client/sheets.json` (source capture hashes). Captures, fixture receipts,
launch receipts and client logs are in `.tmp/runtime-optimization/phase7/`.
