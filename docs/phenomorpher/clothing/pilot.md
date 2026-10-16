# Stock clothing pilot (Human sources, 16 bodies)

Pilot results for `nw_cloth001`–`nw_cloth029`: 115 rigid parts per body, converted from the stock Human
part of the same gender and build onto the 16 non-Human bodies (1,840 models, 352 danglymesh). This
records evidence only. It creates no asset approval, and the full batch waits for user review of the
client sheets.

## Managed runs (local evidence, `.tmp/clothing`)

| Step | Launch receipt | Result |
|---|---|---|
| `armor-profiles` | `launch-armor-profiles-003/launch.json` `0431d1ae…` | 16 bodies, inputs unchanged; profiles `f1c21d83…` |
| `armor-convert` | `launch-armor-convert-pilot-002/launch.json` `a009a268…` | 1,840 models; conversion `76d66ce4…` |
| native compile | `compile-001/<slot>/launch/launch.json` (16) | every receipt complete, inputs unchanged |
| client fixture | `client/launch-fixture-001/launch.json` `e14cff72…` | receipt `f37eadb0…`, module `262f343e…` |

## Profiles
Median stock-to-new fit residual per body: 5.4–14.4 mm (Dwarf lowest, Troll highest, as the Troll
bodies are largest). Worst anisotropy 2.23 (`pmd2:neck`); flagged above 2.0: `pfd2:neck`, `pmd2:neck`.
Armory reproduced every calibration part (agreement ≤ 6e-5 scale/translate, ≤ 6e-3°; residual 0);
worst world-transform error after correction 5e-11 m.

## Offline gates
* **Texture closure:** every referenced texture resolves to a stock PLT. 1,836 of 1,840 converted parts
  reference exactly the textures of the stock target part. The other 4 (`p?{d,e,g,o}0_bicepr011`) keep the
  Human source's `pmh0_bicepl010`, which matches their UVs. No pilot name has a model-named stock PLT.
* **Names:** every resref ≤ 16 characters; none collides with `srn_body`.
* **Compile:** 1,840 binaries from the EE client. Each binary has the same meshes and faces as its
  ASCII source, with every face corner within 10 µm (the compiler splits vertices at UV seams).
* **See-through:** standing front, side and back renders with back-face culling on all 16 bodies
  (`nw_cloth001`, `nw_cloth029`) show no holes inside the outfit outline besides the open space between
  legs and between arm and torso. Where the new body is wider than the armour, nothing shows in game,
  because equipped parts replace the body parts.

## Client (2026-10-16, NWN:EE 8193.37-17)
One module and two isolated profiles that differ only in `srn_armor.hak`: `stock` (a marker only, so
the stock non-Human parts load) and `pilot` (the 1,840 compiled parts, `b73369c9…`). Body, texture
and table HAKs are byte-identical, packed from this branch and verified against HEAD.

* [Stock vs converted, `nw_cloth001`](client/compare-cloth001.jpg): the stock Dwarf parts sit oversized
  on the new Dwarf bodies (chest over the arms, bulging pelvis); the stock Gnome parts on the Troll
  bodies float apart from the body. The converted parts fit all four bodies of both races.
* [All 16 bodies, `nw_cloth001`](client/pilot-cloth001-16-bodies.jpg): Dwarf, Elf, Orc and Troll, F/M Fit
  and Large; no gaps at neck, shoulders, elbows, wrists, waist, knees or ankles.
* [Motion, `nw_cloth029`](client/pilot-cloth029-motion.jpg): Troll M Large combat and cast; Troll row
  death and walk; Dwarf row combat under warm light. No joint opens during motion.

Not covered: `run` and the outdoor light (white and warm shown), the robe items' missing robes
(robes are out of scope) and dangly motion beyond what combat and walking show.
