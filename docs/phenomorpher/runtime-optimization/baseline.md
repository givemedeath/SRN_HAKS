# Runtime optimization: Phase 1 baseline

Read-only inventory of the published v1.0.0 body release, before any library, root
or texture change. It creates no asset, motion or client approval.

## Inputs

| Input | Pin |
|---|---|
| Bodies release head | `0866bcaf` (remote `codex/phenomorpher-bodies-v1`, unchanged at Phase 1) |
| Merged `main` | `affbe01d` (toolkit #44 and CI scope #46) |
| Contract `docs/phenomorpher/game-ready-assets.json` v1.0.0 | `bebb864ccad91e31a77b180e1c2ce714b8227de2d7ef5a76664a0147cfd9f7cd` |
| `verify-assets` | 20 targets, 1031 resources, all hashes verified |
| Installed stock chain (`resman_cat 2.1.2 --no-ovr`, seeds `a_fa`, `a_ba`) | listed in `baseline.json` `stockModels` |
| Inventory [`baseline.json`](baseline.json) | `d7699c77c3e4bcd5218e60dc366ceb3024a7ac822d0868fca26e227908e1b259` |

The inventory was produced by `phenomorpher anim-library inventory` through
`tools/phenomorpher/run.py` with a fresh local binding and Python migration. Launch
receipts, the extracted stock models and the binding remain ignored local evidence.

Stock chain: `a_fa > a_ba > a_ba_non_combat > a_ba_med_weap > a_ba_custom (ASCII) > a_ba_casts > NULL`;
both seeds resolve 172 effective clips.

## Animation findings

* 109 private carriers, 147,686,860 bytes, store 6,041 clips for 20 roots; none is unused.
* Fit and Large effective clips are controller-identical for every race and gender,
  except the female `2hslashl`.
* Clips inheritable from stock under the approved tolerance
  (identical structure, ≤0.1 mm, ≤0.05°):

  | Roots | Inheritable | Override |
  |---|---:|---:|
  | Dwarf female / male | 4 / 3 | 168 / 169 |
  | Elf, Orc, Troll female | 25 | 147 |
  | Elf, Orc, Troll male | 25 | 147 |
  | Human female Large (`pfh2`) | 169 | 3 (`2hslashl`, `pause1`, `pause2`) |
  | Human male Large (`pmh2`) | 172 | 0 |

  Human Large therefore equals stock plus `srn_fa_h0` (female `pause1`/`pause2`), apart
  from female `2hslashl`, which takes the Fit clip as authorized. Its only other
  differences from stock are compile rounding of the ASCII `a_ba_custom` clips
  (≤3×10⁻⁵) and the renamed carrier root.
* Carriers renamed the stock root node but kept `animroot a_ba`/`a_fa`, which names
  no node in the carrier. Fifteen or sixteen clips per non-Human chain store simultaneous
  events in a different order from stock; the event sets are identical. The comparison
  normalizes both and records the raw values (`animrootRaw`, `eventOrderChanged`).
  A clip that is inherited from stock in Phase 2 takes stock's root name and event order.

## Texture findings

* Above 1024 px: 25 PLTs (all chests/pelvises) and 56 skin maps (`s20f_*`/`s20m_*`
  normal and roughness), all 2048², 914,361,336 bytes in total.
* Player body parts render with the palette named after the part model; the stored
  `texture0` name is recorded as `storedTexture0`. Every material and map resolves to a
  pack resource.
* The 18 non-Human/Large `*_head001.plt` palettes have no body-part model referencing
  them. They stay published unchanged; removing them is out of scope.
