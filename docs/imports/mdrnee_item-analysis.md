# MDRN Item HAK decomposition and analysis

## Executive summary

`mdrnee_item.hak` is an item-system asset bundle, not a blueprint library. It contains **zero UTI item blueprints**. The included `itempal.itp` defines 117 friendly palette leaves, but without UTI consumers there is no defensible way to place individual items into those categories from this HAK alone.

The useful payload is substantial: 1,006 ASCII models, 2,320 textures and sidecars, 57 sounds, 21 global 2DA tables, and one item palette. The recommended first landing is a single `srn_item` component for the reviewed item models, icons, textures, and palette; `srn_2da` receives only row-level merges against the pinned EE baseline; and `srn_sound` receives only sounds with proven consumers. Nothing is approved to land yet.

The most important findings are:

- `iprp_magcapcost.2da` is structurally invalid: row `2` occurs 34 times.
- `iprp_spells past.2da` is an archival six-row fragment with no 2DA header and a space in its resource name. It cannot be a valid NWN resource and should be excluded.
- The 57-model `WBwSl` family has no corresponding `baseitems.2da` registration in this archive. Its friendly intended category appears to be **Modern Weapons > Ranged Weapons > SMGs**, but that association is an inference and must be proven from a known-working module or source package.
- Sixteen texture identities used by actual item models are absent from both the HAK and the pinned EE baseline. A further 71 unresolved texture names occur only in bundled animation overrides and are likely body-part placeholders rather than item texture omissions.
- The archive changes 537 identities already present in EE, including 269 models and 246 TGA files. The archive's full legacy global tables and base-resource overrides must not be copied wholesale.
- There are 64 identity overlaps with SRN packs already imported. Twelve pairs are byte-identical; 55 pairs differ and require technical/visual comparison or an explicit HAK-order decision.

## Reproducible source identity

| Property | Value |
|---|---|
| Source | `mdrnee_item.hak` |
| Size | 144,158,062 bytes |
| SHA-256 | `3CE0229D041F12789BB7B4C44AA534570B8A56F4AC9F0DC75E9A018D3C0CC654` |
| Resources | 3,406 |
| Compatibility baseline | NWN:EE `89.8193.37-17`, data build `r1284` |
| Quarantine output | `.quarantine/mdrnee_item/` |
| Initially landed | 0 |
| Quarantined | 3,405 |
| Excluded | 1 (`credits.txt`, transferred to documentation) |

Reproduce the extraction and detailed supplements with:

```powershell
pwsh -NoProfile -File tools/Analyze-ItemHak.ps1 `
  -InputHak 'D:\source\repos\SRN_CC\content\staging\haks\mdrnee_item.hak' `
  -OutputRelativePath 'mdrnee_item' `
  -NwnRoot 'C:\Program Files (x86)\GOG Galaxy\Games\Neverwinter Nights Enhanced Edition' `
  -NwnUserDirectory 'C:\Users\benco\OneDrive\Documents\Neverwinter Nights'
```

`OutputRelativePath` is resolved strictly beneath the repository's predefined `.quarantine` directory.

## Resource inventory and recommended destinations

| Type | Count | EE identities changed | Recommended destination |
|---|---:|---:|---|
| TGA | 1,792 | 246 | `srn_item` after icon/model ownership review |
| MDL | 1,006 | 269 | `srn_item`; isolate only proven standalone effects later |
| DDS | 526 | 1 | `srn_item`, resolving SRN identity conflicts first |
| WAV | 57 | 4 | `srn_sound` when referenced; quarantine unreferenced audio |
| 2DA | 21 | 16 | row-level merge into `srn_2da`; never wholesale replacement |
| TXI | 2 | 0 | beside the owning item texture in `srn_item` |
| ITP | 1 | 1 | reviewed/remapped palette in `srn_item` |
| TXT | 1 | 0 | attribution documentation, not a HAK |

The manifest recommends 3,327 model/texture/palette resources for eventual `srn_item`, 21 tables for reviewed `srn_2da` merges, 57 WAVs for `srn_sound` review, and the credit file for tracked attribution. These are destinations, not approvals.

## Blueprint and palette-category findings

### Blueprint availability

There are no `.uti` resources. Consequently:

- bundled blueprint count: **0**;
- blueprints assignable to a friendly category: **0**;
- category data available: **yes**, from `itempal.itp`;
- model-family inference available: **yes**, from NWN item naming conventions and `baseitems.2da`, but it is not a substitute for blueprint evidence.

The machine-readable [category map](./mdrnee_item-category-map.json) contains every leaf ID, full friendly path, and STRREF.

### Palette overview

| Top-level palette branch | Leaf categories |
|---|---:|
| Armor | 9 |
| Creature Items | 6 |
| D20 Modern System Items | 3 |
| Miscellaneous | 18 |
| Modern Clothing | 9 |
| Modern General | 8 |
| Modern Weapons | 25 |
| Plot Item | 1 |
| Special | 5 |
| Tutorial | 1 |
| Weapons | 32 |
| **Total** | **117** |

### D20 Modern System Items

- `113` — DM Tools
- `114` — Other Tools
- `115` — Special Abilities

### Modern General

- `107` — Computers and Consumer Electronics
- `108` — Surveillance Gear
- `109` — Professional Equipment
- `110` — Survival Gear
- `111` — Weapon Accessories
- `112` — Miscellaneous
- `116` — Drugs
- `127` — Money

### Modern Clothing

- `117` — Clothing
- `118` — Light
- `119` — Heavy
- `120` — Helmets
- `121` — Shields > Small Shields
- `122` — Shields > Large Shields
- `123` — Shields > Tower Shields
- `124` — Medium
- `125` — NPC Clothing

### Modern Weapons

- Ammunition: `185` Handgun, `186` Longarms, `187` Boxes & Packs
- Axes: `188` One-Handed, `189` Two-Handed
- Bladed: `190` Shortswords, `191` Daggers, `192` Great Swords, `193` Longswords, `194` Other
- Blunts: `195` Clubs, `196` Flails, `197` Hammers, `198` Maces, `199` Morning Star
- Ranged Weapons: `200` Heavy, `201` SMGs, `202` Handgun, `203` Dual Handgun, `204` Longarms
- Other: `205` Improvised Weapons, `206` Exotic, `207` Power Blades, `208` Polearms, `209` Throwing

Additional custom leaves are **Fashion Accessory**, **Flag**, **Holy Symbol**, **Musical Instrument**, **Falchions**, **Tridents**, **Picks**, and **Lightcrossbow**.

## Asset families

Model classification metadata is not a reliable category label: 730 weapon models are marked `Character`, while other item models use `Item`, `Other`, `Tile`, or no classification. Filename families provide the more useful screening view.

| Friendly inferred family | Prefix | Models | Registration observation |
|---|---|---:|---|
| Handguns | `WBwSh` | 170 | multiple D20 handgun/small-arms rows exist |
| Longarms | `WBwXl` | 143 | D20 longarms row exists |
| Light/small arms | `WBwLn` | 49 | D20 small-arms row exists |
| Heavy ranged weapons | `WBwXh` | 53 | D20 heavy-weapons row exists |
| Probable SMGs | `WBwSl` | 57 | **no baseitems row in this HAK** |
| Improvised/makeshift weapons | `WMk*` | 77 | rows 504–508 exist |
| Standard bladed weapons | `WSw*` | 142 | mostly base identities plus custom variants |
| Standard blunt weapons | `WBl*` | 49 | mostly base identities plus custom variants |
| Axes | `WAx*` | 22 | includes custom fire axe |
| Polearms | `WPl*` | 48 | standard and extended variants |
| Double/exotic weapons | `WDb*` | 41 | includes power-blade/lightsaber families |
| Ammunition models | `WAm*` | 18 | arrows, bolts, and bullets plus elemental variants |
| Thrown weapons | `WTh*` | 10 | axes and darts |
| Miscellaneous item world models | `it_*` | 70 | money, holdables, grenades, torches, traps, and containers |
| Animation overrides | `a_*` | 6 | global/base collision; high-risk and test separately |
| Effects/projectiles | `fx_*`, `vff_*`, `vpr_*` | 7 | keep with item system until consumers prove a separate `srn_fx` boundary |

The remaining models are shields, special weapons, and isolated support models. Exact prefix counts are in [model dependencies](./mdrnee_item-model-dependencies.json).

## Base-item registrations

`baseitems.2da` contains 510 numbered rows but only 172 rows screen as active. It is a full legacy global table with an older 57-column schema, whereas the pinned EE table has 113 rows and 67 columns. On their shared columns, 98 active overlapping rows differ, and 65 active rows lie beyond the EE table.

Useful custom row groups include:

| Group | Source rows | Notes |
|---|---|---|
| D20 firearms and ammunition | `6`, `7`, `8`, `11`, `61`, `201`, `202`, `213` | row allocation and modern combat-property linkage required |
| Modern general item bases | `205`–`211`, `214`, `215` | thin/medium/large items, necklace, pills, holdables, bank notes and coins |
| Fire axe | `212` | custom weapon base |
| Extended weapon/item bases | `300`–`314`, `316`–`325`, `327`, `330`, `350` | mixed custom and legacy community content; review individually |
| CEP cloak | `349` | exclude unless a non-CEP consumer is proven |
| Makeshift weapons | `504`–`508` | large/medium/small blunt, small slashing, and combat staff |

These source row numbers are not reserved allocations in SRN. They must be mapped into reviewed user slots, with every dependent table, UTI in consuming modules, script constant, and TLK reference updated together.

## Global 2DA assessment

| Table | Source rows | Active | EE baseline | Changed overlapping active rows | New active rows | Recommendation |
|---|---:|---:|:---:|---:|---:|---|
| `ammunitiontypes.2da` | 36 | 36 | yes | 18 | 0 | merge only modern ammunition behavior changes |
| `baseitems.2da` | 510 | 172 | yes | 98 | 65 | allocate required custom bases; reject full table |
| `inventorysnds.2da` | 34 | 34 | yes | 0 | 1 | add only lightsaber sound row if used |
| `iprp_ammotype.2da` | 5 | 5 | yes | 0 | 2 | merge Ballistic/Energy-style additions with TLK remap |
| `iprp_combatdam.2da` | 5 | 5 | yes | 0 | 2 | merge only referenced additions |
| `iprp_costtable.2da` | 33 | 33 | yes | 3 | 2 | preserve EE rows and allocate custom cost tables |
| `iprp_damagecost.2da` | 34 | 34 | yes | 0 | 3 | merge referenced additions |
| `iprp_damagetype.2da` | 17 | 17 | yes | 1 | 2 | review changed row plus additions |
| `iprp_feats.2da` | 89 | 89 | yes | 22 | 26 | high-risk; merge referenced rows only |
| `iprp_magazine.2da` | 4 | 4 | no | — | 4 | custom table; validate consumer plumbing |
| `iprp_magcapcost.2da` | 3 unique | 3 | no | — | 3 | **reject until duplicate row labels are repaired** |
| `iprp_onhitspell.2da` | 302 | 131 | yes | 0 | 1 | retain only proven new active row |
| `iprp_rangedam.2da` | 5 | 5 | no | — | 5 | custom Ballistic/Energy ranged-damage table |
| `iprp_rateoffire.2da` | 3 | 3 | no | — | 3 | custom single/semi/automatic table |
| `iprp_spells past.2da` | malformed | 0 | no | — | 0 | exclude as archival fragment |
| `iprp_spells.2da` | 546 | 522 | yes | 0 | 6 | merge the six additions only if scripts/spells exist |
| `itempropdef.2da` | 200 | 90 | yes | 5 | 3 | high-risk definition table; map dependencies first |
| `itemprops.2da` | 153 | 90 | yes | 80 | 3 | high-risk global table; never wholesale replace |
| `ranges.2da` | 14 | 14 | yes | 11 | 0 | legacy behavioral changes; preserve EE unless proven necessary |
| `visualeffects.2da` | 10,100 | 756 | yes | 80 | 0 | extract only rows supplying bundled effects |
| `weaponsounds.2da` | 110 | 30 | yes | 7 | 8 | merge only sound rows required by retained weapon bases |

All custom STRREFs must go through the canonical deduplicating TLK importer before any 2DA or palette is promoted.

## Model dependency closure

The 1,006 ASCII models reference 651 distinct texture stems:

- 524 are supplied by this HAK;
- 40 resolve to the pinned EE baseline;
- 87 remain unresolved;
- all six distinct supermodel references resolve to either this HAK or EE.

Of the 87 unresolved texture stems, 71 are referenced only by the six global animation models. The 16 item-facing gaps are:

| Missing texture stem | Affected models |
|---|---|
| `01` | `wbwxl_m_025`, `wbwxl_m_026`, `wswgs_m_105`, `wswls_m_105`, `wswls_m_106` |
| `anakin2saber2` | `wswglsbr_b_041` |
| `box06`, `cylinder02` | `wbwsl_m_071` |
| `dblsaber1` | `wdblsbr_b_012` |
| `dgmetal` | `wbwxh_m_083` |
| `dual_visceron` | `wdblsbr_b_013` |
| `g_wambu_001` | `wambu_001` |
| `ladle` | `wmkbs_b_062`, `wmkbs_m_062`, `wmkbs_t_062` |
| `lens` | `wbwxl_m_141` |
| `mg-silencer` | `wbwxh_m_022` |
| `rollingpin` | `wblcl_m_111` |
| `rsw` | `wbwsh_m_221`, `wbwsh_m_222` |
| `soff_lens` | `wbwxh_m_074`, `wbwxl_m_072` |
| `tex_glsbr01` | `wswglsbr_b_011` |
| `tex_lsbr01` | `wdblsbr_m_011` |

Search the remaining MDRNEE HAKs and known-working D20 Modern modules for these exact identities before deciding whether each is an actual visual defect or a harmless unused variant.

## Sound linkage

Of 57 WAV files, 31 have a direct consumer in an imported 2DA or model and 26 do not. Six are already byte-identical in `srn_sound`: `dssawful.wav`, `dssawhit.wav`, `dssawidl.wav`, `dssawup.wav`, `fw_blaster.wav`, and `it_materialcloth.wav`.

The proven registrations cover lightsaber inventory/combat sounds, firearm discharge sounds, ammunition sounds, and standard inventory material sounds. `pulserifle.wav` is referenced directly by `wbwxl_m_101.mdl`. Unlinked sounds—including `gunshot.wav`, `gunshot2.wav`, `gunsilencer.wav`, `machinegun.wav`, `rapidfire.wav`, `reload.wav`, `saberon.wav`, and `saberoff.wav`—remain candidates only; scripts or blueprint/module data may be their actual consumers.

Exact consumers and the complete orphan list are in [sound linkages](./mdrnee_item-sound-linkages.json).

## Collision analysis

### Current EE

The archive has 537 same-name/different-byte collisions with the pinned EE resource view:

- 269 MDL;
- 246 TGA;
- 16 2DA;
- 4 WAV;
- 1 DDS;
- 1 ITP.

This confirms that the HAK depends partly on intentional legacy overrides. Preserve only overrides that are demonstrated by a retained item base or animation requirement; never infer that all 537 should remain.

### Existing SRN packs

There are 64 shared identities across 67 source/pack pairs: 12 identical and 55 different. The identical pairs may be omitted from `srn_item` and supplied by the existing pack. The differing pairs are concentrated in `srn_placeable` (52) plus `chrome.dds`, `dgt04_chrome.dds`, and `glass.dds` in `srn_door`.

Do not resolve the differing textures by HAK order alone. First apply the project's established policy: compare visual equivalence, retain the technically sound/higher-resolution version when they are visually equivalent, and record an explicit override only when distinct consumers genuinely require distinct bytes. The full list is in [cross-HAK collisions](./mdrnee_item-cross-hak-collisions.json).

## Provenance

`credits.txt` identifies the original D20 Modern team and later contributions by Jezira, Prole, Xialya, Vanya Mia, Taina, JKA, Forestwolf, Shemsu-Heru, Aenea, The Barbarian, Zwerkule, and Den of Assassins. Contributions span ranged weapons, SMGs, item models and icons, lightsabers and Star Wars weapons, 40K weapons, improvised and Dark Sun weapons, Predator weapons and holdables, flintlock and harpoon models, farm tools, GUI imagery, and compass changes.

The credit list establishes authorship, not redistribution terms. Before landing, locate the source package's license/readme or Neverwinter Vault terms and add the resulting evidence to `NOTICE.md` and `PROVENANCE.md`.

## Recommended landing plan

1. Locate a known-working module or source package containing the actual UTI blueprints. Use those consumers to populate the friendly palette categories and prove which base-item rows, models, sounds, and item properties are required.
2. Search the remaining MDRNEE HAKs for the 16 item-facing missing texture identities and for the absent `WBwSl` registration. Treat this as the highest-value dependency audit.
3. Create a row-allocation plan for required custom `baseitems.2da` rows and the four custom firearm-property tables. Repair `iprp_magcapcost.2da` only from authoritative consumer behavior or a clean upstream copy—not by guessing which duplicated row `2` was intended.
4. Merge only proven rows into the current EE-derived `srn_2da`, remapping dependent row references and passing every custom string through the deduplicating TLK importer.
5. Build `srn_item` initially as one component containing the retained item models, inventory icons, textures, animation overrides, and transformed `itempal.itp`. The item system is too cross-linked to split safely by visual category before blueprint evidence exists.
6. Reuse the 12 byte-identical SRN resources. Resolve the 55 differing SRN pairs through technical and visual comparison before packing.
7. Promote linked WAVs into `srn_sound`; keep the 26 unlinked WAVs quarantined until module/script evidence supplies a consumer.
8. Compile the ASCII models, build the candidate HAKs, and test representative items from every proven friendly category in the toolset and game client: palette visibility, ground model, inventory icon, equip animation, ammunition, rate of fire, reload behavior, damage type, sounds, and visual effects.

## Acceptance gates

- The manifest accounts for exactly 3,406 source resources and reproduces the pinned source hash.
- Every promoted resource has a consumer or an explicitly documented compatibility override.
- No malformed table, duplicate row label, full legacy global table, or unallocated custom row is packed.
- Every item-facing model texture resolves from `srn_item`, another declared SRN pack, or EE.
- Every retained custom STRREF is present once in the canonical TLK registry and reused when text matches.
- All differing cross-HAK identities have a documented resolution.
- Toolset and game smoke tests cover every retained base-item family, not merely palette loading.
