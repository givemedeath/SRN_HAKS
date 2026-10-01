# MDRN Item HAK decomposition and analysis

## Executive summary

`mdrnee_item.hak` is an item-system asset bundle rather than a self-contained blueprint library: the HAK itself contains **zero UTI item blueprints**. The companion project-source archive `d20modernupdate.erf`, however, supplies **669 unique UTI item blueprints**. Joining those records to the HAK's `itempal.itp` and `baseitems.2da` resolves every blueprint to a friendly category and a source base-item row.

The useful HAK payload is substantial: 1,006 ASCII models, 2,320 textures and sidecars, 57 sounds, 21 global 2DA tables, and one item palette. The recommended first landing remains a curated `srn_item` component, row-level merges into `srn_2da`, and proven audio in `srn_sound`. The companion UTIs are consumer evidence and a future curated module-blueprint import; the mixed ERF must not be copied wholesale into a HAK.

The most important findings are:

- `iprp_magcapcost.2da` is structurally invalid: row `2` occurs 34 times.
- `iprp_spells past.2da` is an archival six-row fragment with no 2DA header and a space in its resource name. It cannot be a valid NWN resource and should be excluded.
- All 669 UTI ResRefs are unique; all 669 Palette IDs resolve to one of 50 used friendly leaves; and all 669 BaseItem values resolve to the source `baseitems.2da`.
- The 57-model `WBwSl` family is not used by any companion item blueprint. All eight blueprints in **Modern Weapons > Ranged Weapons > SMGs** use row `8`, item class `WBwLn`. `WBwSl` is therefore an unproven ancillary family rather than a required missing registration.
- 403 blueprints contain 790 item-property instances. Base-item, PropertyName, CostTable, subtype, and TLK remapping must update these UTIs together with the merged 2DAs.
- Six of the 16 item-facing missing texture stems are now proven reachable through companion blueprints: `01`, `ladle`, `rollingpin`, `soff_lens`, `tex_glsbr01`, and `tex_lsbr01`. The other ten are lower-priority unused-variant candidates until another consumer is found.
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

Reproduce the companion blueprint join with:

```powershell
pwsh -NoProfile -File tools/Analyze-ItemBlueprintErf.ps1 `
  -InputErf 'D:\source\repos\SRN_CC\content\staging\erf\d20modernupdate.erf' `
  -OutputRelativePath 'mdrnee_item\blueprints' `
  -ItemHakOutputRelativePath 'mdrnee_item' `
  -MatchTierPath '.\docs\imports\mdrnee_item-match-tier.json' `
  -ExpectedSha256 'CD96273454F3C6AF55F40B683C9C0F237129D95B1BD07C68418756FE4FE71A4D' `
  -ExpectedResourceCount 5534
```

The ERF analysis also constrains its `OutputRelativePath` and item-analysis input beneath `.quarantine`.

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

### Companion blueprint source

`D:\source\repos\SRN_CC\content\staging\erf\d20modernupdate.erf` is the authoritative companion found in the project sources. Its SHA-256 is `CD96273454F3C6AF55F40B683C9C0F237129D95B1BD07C68418756FE4FE71A4D`; it is 17,715,193 bytes and contains 5,534 resources, including 669 UTI item blueprints.

The ERF is a mixed module/update bundle—3,565 placeables, 271 creatures, 128 doors, 448 source scripts, 415 compiled scripts, and other module resources accompany the UTIs. Only its UTI records are used as item-import evidence. The rest remain quarantined and are not proposed for `srn_item`.

The exact ERF inventory is in the [blueprint ERF manifest](./mdrnee_item-blueprint-erf-manifest.json). The [machine-readable blueprint analysis](./mdrnee_item-blueprint-analysis.json) preserves every UTI field needed for migration, and the [detailed blueprint report](./mdrnee_item-blueprint-report.md) lists all 669 blueprints under their friendly palette paths.

### Integrity and coverage

- unique UTI ResRefs: **669 of 669**;
- friendly palette matches: **669 of 669**;
- source base-item row matches: **669 of 669**;
- used palette leaves: **50 of 117**;
- source base-item rows actually consumed: **71**;
- blueprints with properties: **403**;
- item-property instances: **790**;
- unique tags: **649**; 13 repeated tag values cover 33 blueprints and require script-aware review, but do not invalidate the records.

| Top-level friendly category | Blueprints | Used leaves |
|---|---:|---:|
| Armor | 1 | 1 |
| Creature Items | 5 | 2 |
| D20 Modern System Items | 78 | 3 |
| Miscellaneous | 22 | 2 |
| Modern Clothing | 166 | 9 |
| Modern General | 130 | 8 |
| Modern Weapons | 262 | 22 |
| Tutorial | 1 | 1 |
| Weapons | 4 | 2 |
| **Total** | **669** | **50** |

The 67 unused leaves are mostly stock palette branches plus custom placeholders. An unused leaf does not indicate a defect; it simply has no UTI in this companion ERF.

### Particularly useful category evidence

- **SMGs**: 8 blueprints, all using base-item row `8` (`d20_smallarms_d8`, `WBwLn`); none uses `WBwSl`.
- **Dual Handgun**: 30 blueprints split evenly between rows `61` and `213`, both labeled `d20_smallArms_d6` with item class `WBwSh`.
- **Handgun**: 17 category blueprints use row `11` (`d20_handguns_d6`, `WBwSh`).
- **Longarms**: 15 category blueprints use row `7` (`d20_longarms_d8`, `WBwXl`).
- **Heavy**: 15 category blueprints, of which 14 use row `6` (`d20_heavyweap_d10`, `WBwXh`) and one is a flashlight represented by the torch base.
- **Ammunition**: 90 blueprints across Handgun, Longarms, and Boxes & Packs; all 30 box/pack entries use custom row `202` (`ammo_rounds`, `it_faammo`).
- **Improvised Weapons**: 37 blueprints, including 31 consumers of makeshift rows `504`–`508`.

These records replace filename-only inference with actual toolset blueprint evidence. They also give the row-migration work a finite consumer set: every changed base-item or item-property row can now be traced to exact UTI ResRefs.

### SR3 Match Tier subset

The external `sr3-blueprint-candidates.xlsx` workbook (SHA-256 `06FFCF13C39C04B57F58E45EC75FE36D7805DBFC722B0EA97656A0492FA6F5FE`) classifies **93 of 669** blueprints as appearance candidates. Its ERF hash matches this analysis, and all 93 spreadsheet rows join uniquely by Blueprint ResRef and agree with the UTI base-item row.

| Match Tier | Blueprints | Friendly-category distribution |
|---|---:|---|
| Exact identity | 12 | Modern General: 4; Modern Weapons: 8 |
| Visual stand-in | 81 | Modern Clothing: 5; Modern General: 20; Modern Weapons: 56 |
| **Total** | **93** | |

Ten of the 12 Exact identity rows reference the official SR3 line; one references an earlier official edition and one is fan/conversion catalog data. All 81 Visual stand-ins reference the official SR3 line. Confidence across the shortlist is 38 High, 47 Medium, and 8 Low.

This subset is appearance-only. The spreadsheet does not authorize reuse of costs, properties, descriptions, scripts, combat behavior, models, icons, or 2DA definitions. Its dependency and rights columns remain advisory source fields because they were prepared without this item-HAK analysis. Current repository dependency and provenance findings control landing decisions.

The [detailed blueprint report](./mdrnee_item-blueprint-report.md#match-tier-subset-from-the-sr3-candidate-workbook) lists all 12 Exact identity and 81 Visual stand-in rows with their friendly MDRN category and catalog identity. The [normalized Match Tier data](./mdrnee_item-match-tier.json) records the workbook SHA-256, source ranges, join checks, and all 93 classifications.

## Asset families

Model classification metadata is not a reliable category label: 730 weapon models are marked `Character`, while other item models use `Item`, `Other`, `Tile`, or no classification. Filename families provide the more useful screening view.

| Friendly inferred family | Prefix | Models | Registration observation |
|---|---|---:|---|
| Handguns | `WBwSh` | 170 | multiple D20 handgun/small-arms rows exist |
| Longarms | `WBwXl` | 143 | D20 longarms row exists |
| Light/small arms | `WBwLn` | 49 | D20 small-arms row exists |
| Heavy ranged weapons | `WBwXh` | 53 | D20 heavy-weapons row exists |
| Unused SMG-like variants | `WBwSl` | 57 | no companion UTI uses this family; quarantine unless another consumer is proven |
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

The companion UTIs reduce that broad legacy inventory to **71 actually consumed rows**. Nineteen consumed rows are above the current EE range and account for 132 blueprints. Several lower-numbered D20 rows also replace current EE identities and therefore require allocation rather than in-place overwrite.

| Proven consumer group | Source rows | Blueprint evidence |
|---|---|---|
| D20 firearms | `6`, `7`, `8`, `11`, `61`, `213` | 115 blueprints; includes Heavy, Longarms, SMGs, Handgun, and Dual Handgun |
| Ammunition boxes/packs | `202` | 31 blueprints using `it_faammo` |
| Modern general bases | `205`–`211`, `214`, `215` | 49 blueprints covering modern objects, necklaces, pills, holdables, bank notes, and coins |
| Fire axe | `212` | 1 blueprint |
| Fashion accessory and flowers | `314`, `325` | 7 blueprints |
| Makeshift weapons | `504`–`508` | 29 blueprints across blunt, slashing, and combat-staff bases |

Source row `201`, the other extended rows `300`–`313`, `316`–`324`, `327`, `330`, `349`, and `350`, and their associated assets are not used by these 669 UTIs. They should not enter the first landing merely because they are active in the legacy table. In particular, the CEP cloak at row `349` remains excluded absent a non-CEP consumer.

These source row numbers are not reserved allocations in SRN. Required rows must be mapped into reviewed user slots, with every dependent UTI `BaseItem`, item-property field, 2DA reference, script constant, and TLK reference updated together. The detailed blueprint analysis supplies the exact ResRef consumer list for each row.

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

The companion UTIs prove seven blueprints reach six of these missing texture stems:

- `01`: the two **Chainsword** blueprints (`wswls_m_105`, `wswls_m_106`);
- `ladle`: **Dipper** (`wmkbs_*_062`);
- `rollingpin`: **Rolling Pin** (`wblcl_m_111`);
- `soff_lens`: **Negev 5.56mm Light Machine Gun** (`wbwxh_m_074`);
- `tex_glsbr01`: **Lightsaber** (`wswglsbr_b_011`);
- `tex_lsbr01`: **Double Lightsaber** (`wdblsbr_m_011`).

Search the remaining MDRNEE HAKs and known-working D20 Modern modules for those six first. The other ten item-facing gaps are attached only to models not selected by this companion UTI set; retain them as lower-priority ancillary candidates unless another consumer is found.

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

1. Treat the 669 UTIs as the authoritative first-pass consumer ledger. Keep the mixed source ERF quarantined; generate a curated item-blueprint ERF or module seed only after all allocated row IDs are final.
2. Allocate and merge the proven custom base-item rows, then rewrite the exact dependent UTI `BaseItem` fields. Do not import unused active rows from the 510-row legacy aggregate.
3. Build an item-property row map from the 790 property instances. Migrate PropertyName, CostTable, subtype, parameter, spell, and TLK references as one transaction with `srn_2da`.
4. Recover the six blueprint-reachable missing texture stems first. Treat the other ten item-facing gaps and all 57 `WBwSl` models as non-blocking ancillary content until another consumer proves them necessary.
5. Repair `iprp_magcapcost.2da` from an authoritative clean source or demonstrated behavior—not by guessing which repeated row `2` values were intended—and exclude `iprp_spells past.2da`.
6. Build `srn_item` around closure for the 669 proven blueprints: retained models, inventory icons, textures, required animation overrides, and the transformed `itempal.itp`. Defer resources with no UTI, script, model, or compatibility consumer.
7. Reuse byte-identical SRN resources and resolve differing identities through the established technical/visual policy before packing. Promote proven WAVs into `srn_sound`; keep audio without a UTI, 2DA, model, or script consumer quarantined.
8. Compile the ASCII models, build the candidate HAKs, import the curated blueprint ERF into a test module, and smoke-test all 50 used friendly leaves and every one of the 71 retained base-item rows. Cover ground models, inventory icons, equip animations, ammunition, rate of fire, reload behavior, damage types, sounds, item properties, and visual effects.

## Acceptance gates

- The manifest accounts for exactly 3,406 source resources and reproduces the pinned source hash.
- Every promoted resource has a consumer or an explicitly documented compatibility override.
- No malformed table, duplicate row label, full legacy global table, or unallocated custom row is packed.
- Every item-facing model texture resolves from `srn_item`, another declared SRN pack, or EE.
- Every retained custom STRREF is present once in the canonical TLK registry and reused when text matches.
- All differing cross-HAK identities have a documented resolution.
- Toolset and game smoke tests cover every retained base-item family, not merely palette loading.
