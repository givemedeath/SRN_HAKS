# Stock clothing: full conversion (`srn_armor`)

After the user approved the pilot client sheets (2026-10-16), every stock Human armour part with geometry was
converted onto the 16 non-Human bodies and published as `srn_armor`. Contract:
[`srn-armor-assets.json`](srn-armor-assets.json) `d82aa6cd…` (per-resource source, conversion and compile pins).
This records evidence only and creates no asset approval beyond the user's request to publish.

## Coverage
| Source | Bodies | Styles | Models |
|---|---|---:|---:|
| `pfh0` | `pfd0 pfe0 pfo0 pfg0` | 409 | 1,636 |
| `pfh2` | `pfd2 pfe2 pfo2 pfg2` | 379 | 1,516 |
| `pmh0` | `pmd0 pme0 pmo0 pmg0` | 387 | 1,548 |
| `pmh2` | `pmd2 pme2 pmo2 pmg2` | 370 | 1,480 |

6,180 models (764 danglymesh), 48 MB; `srn_armor.hak` `3b635e1f…` (36,841,976 bytes). Style sets:
`full-set-<source>.json`. Stock is kept for:
* robes, cloaks, heads and the bare style-001 parts that `srn_body` overrides (out of scope);
* the geometry-free foot styles `footl015/016` and `footr013/014`, which are empty on the targets too;
* male Fit hands `013`/`014`: the non-Human bodies have them, but there is no Human source and their
  texture is not installed.

`pmh2_footl014` names its mesh like its root dummy; that mesh is renamed to `<model>g` (recorded per resource
as `nameOnlyChanges`).

## Managed runs (local evidence, `.tmp/clothing`)
| Step | Launch receipt | Result |
|---|---|---|
| `armor-convert` `pfh0`/`pfh2`/`pmh0` | `launch-armor-convert-full-001-*` `3114e38b…`, `ace4f968…`, `04048f8b…` | inputs unchanged |
| `armor-convert` `pmh2` | `launch-armor-convert-full-002-pmh2` `828b02e7…` | inputs unchanged (rerun after the rename fix) |
| native compile | `compile-002`, `compile-003` `<slot>/launch` (16) | every receipt complete, inputs unchanged |
| `armor-publish` | `launch-armor-publish-002` `a3ff6987…` | 6,180 resources, 16 targets, string tails zeroed |
| `verify-armor` | `launch-verify-armor-002` | verified, no header or credential text |
| client fixture | `client/launch-fixture-002` `1abbd1ba…` | receipt `95b37c08…` |

## Gates
* Every calibration agreed with its profile; worst world-transform error 5e-11 m.
* Every compiled binary has the same meshes and faces as its ASCII, face corners within 10 µm.
* Names: ≤ 16 characters, stock part names of target bodies, none shared with `srn_body`;
  `Test-Repository -ChangedSince 0d5c64d` passes and `Build-Haks -Pack srn_armor` rebuilds and reopens 6,180 resources.
* Textures: no converted part has a stock PLT named after itself, so the engine cannot substitute a
  non-Human texture. 1,360 + 2,852 parts reference exactly what the stock target part does; the rest keep the
  Human source's references. Dead references (`torso`, `lbicep`, `pmh0_bicep163` and similar) come from the
  stock Human parts and are mostly identical on the stock targets. The Female Large Human parts reference
  uninstalled `pfh2_*` textures, as the stock non-Human Large parts reference uninstalled `p?d2_*` ones; the
  client shows them textured (below).

## Compiler memory in string fields
The client compiler leaves the bytes after the terminator of fixed string fields (model, supermodel and node
names, mesh textures 0-3) uninitialised. A first publication of this pack carried process memory there, including
HTTP session headers, in 86 models. That publication was withdrawn. `armor-publish` now zeroes every such tail and
refuses header- or credential-like text; `verify-armor` checks both. Diffing two client compiles of the same 1,840
pilot sources showed the remaining run-to-run differences are runtime pointers and single pad bytes only. Zeroing
changes no geometry (all 6,180 models decode identically) and no string the engine reads.

## Client sample (fixture-002, the committed pack)
[Sheet](client/full-sample.jpg) (taken before the string tails were zeroed; the client reads strings only up to
their terminator):
* Orc row in `nw_aarcl012` (chain and leather): all four bodies fit.
* Troll female Large in `nw_aarcl009` beside the stock Human female Large in the same item: the bare hip is the
  armour's design. Troll male Large in combat with a greatsword.
* Dwarf female Large with hands `009`, shins `018`/`020`, feet `013`/`015` (the Female Large texture fallback):
  textured, no grey or white surfaces.

Not covered by this sample: every style on every body (the pilot sheets and the offline gates cover the rest),
running, outdoor light and dangly motion beyond combat and walking.
