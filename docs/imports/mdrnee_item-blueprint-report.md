# MDRN item blueprint ERF analysis

The companion `d20modernupdate.erf` ERF supplies **669 UTI item blueprints** for `mdrnee_item.hak`. The HAK itself still contains no UTIs; this report joins the ERF records to its `itempal.itp` palette and `baseitems.2da` registrations.

## Reproducible source identity

| Property | Value |
|---|---|
| Source | `d20modernupdate.erf` |
| Size | 17,715,193 bytes |
| SHA-256 | `CD96273454F3C6AF55F40B683C9C0F237129D95B1BD07C68418756FE4FE71A4D` |
| All ERF resources | 5,534 |
| UTI blueprints | 669 |
| Friendly-category matches | 669 |
| Missing source `baseitems.2da` rows | 0 |

Only the UTI records are in item-import scope. The ERF also contains areas, creatures, doors, placeables, scripts, and other module resources; those remain quarantined evidence and are not proposed for `srn_item`.

## Integrity and item-property usage

- **669** distinct ResRefs across **669** blueprints; **0** repeated occurrences.
- **669 of 669** Palette IDs resolve to a friendly `itempal.itp` leaf; **0** are unmapped.
- **669 of 669** BaseItem values resolve to a row in the source `baseitems.2da`; **0** are missing.
- **403** blueprints carry **790** item-property instances. Their PropertyName and CostTable rows must be remapped with the merged 2DAs.
- **13** tag values are non-unique; this does not invalidate the blueprints, but tag-based scripts may intentionally target more than one template.

## Blueprint categories

| Top-level category | Blueprints | Used leaves |
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

## Base-item usage

| Row | Label | Item class | Blueprints |
|---:|---|---|---:|
| 0 | `shortsword` | `WSwSs` | 4 |
| 1 | `longsword` | `WSwLs` | 5 |
| 2 | `battleaxe` | `WAxBt` | 1 |
| 3 | `bastardsword` | `WSwBs` | 1 |
| 5 | `warhammer` | `WBlHw` | 2 |
| 6 | `d20_heavyweap_d10` | `WBwXh` | 18 |
| 7 | `d20_longarms_d8` | `WBwXl` | 20 |
| 8 | `d20_smallarms_d8` | `WBwLn` | 24 |
| 10 | `halberd` | `WPlHb` | 2 |
| 11 | `d20_handguns_d6` | `WBwSh` | 23 |
| 12 | `twobladedlightsaber` | `WDbLsbr` | 1 |
| 13 | `greatsword` | `WSwGs` | 2 |
| 14 | `smallshield` | `AShSw` | 1 |
| 15 | `torch` | `it_torch` | 17 |
| 16 | `armor` | `AArCl` | 130 |
| 17 | `helmet` | `helm` | 24 |
| 18 | `greataxe` | `WAxGr` | 1 |
| 20 | `arrow` | `WAmAr` | 22 |
| 21 | `belt` | `it_belt` | 5 |
| 22 | `dagger` | `WSwDg` | 5 |
| 24 | `miscsmall` | `it_smlmisc` | 49 |
| 25 | `bolt` | `WAmBo` | 23 |
| 27 | `bullet` | `WAmBu` | 17 |
| 28 | `club` | `WBlCl` | 18 |
| 29 | `miscmedium` | `it_midmisc` | 10 |
| 32 | `diremace` | `WDbMa` | 1 |
| 34 | `misclarge` | `it_talmisc` | 3 |
| 36 | `gloves` | `it_glove` | 1 |
| 38 | `handaxe` | `WAxHn` | 1 |
| 39 | `healerskit` | `it_medkit` | 1 |
| 40 | `kama` | `WSpKa` | 2 |
| 41 | `katana` | `WSwKa` | 1 |
| 42 | `lightsaber` | `WSwGlsbr` | 1 |
| 45 | `magicstaff` | `WMgSt` | 1 |
| 50 | `quarterstaff` | `WDbQs` | 1 |
| 51 | `rapier` | `WSwRp` | 1 |
| 52 | `ring` | `it_ring` | 6 |
| 56 | `largeshield` | `AShLw` | 1 |
| 57 | `towershield` | `AShTo` | 3 |
| 58 | `shortspear` | `WPlSs` | 5 |
| 60 | `sickle` | `WSpSc` | 2 |
| 61 | `d20_smallArms_d6` | `WBwSh` | 15 |
| 66 | `largebox` | `it_bigbox` | 9 |
| 69 | `cslashweapon` | `it_cr_sla` | 2 |
| 71 | `cbludgweapon` | `it_cr_blud` | 1 |
| 73 | `creatureitem` | `it_cr_item` | 5 |
| 74 | `book` | `IT_BOOK` | 20 |
| 77 | `gem` | `IT_GEM` | 10 |
| 79 | `miscthin` | `IT_THNMISC` | 5 |
| 80 | `cloak` | `cloak` | 4 |
| 81 | `grenade` | `it_x1_gren` | 9 |
| 108 | `dwarvenwaraxe` | `WAxBt` | 1 |
| 202 | `ammo_rounds` | `it_faammo` | 31 |
| 205 | `modern_thin` | `it_mdrnthn` | 11 |
| 206 | `modern_mdm` | `it_mdrnmdm` | 11 |
| 207 | `modern_large` | `it_mdrnlrg` | 6 |
| 208 | `modern_necklace` | `it_mdrnnek` | 3 |
| 209 | `modern_pills` | `it_mdrnpil` | 3 |
| 210 | `holdable` | `it_mod` | 2 |
| 211 | `holdable2` | `it_hold` | 3 |
| 212 | `fireaxe` | `WAxFa` | 1 |
| 213 | `d20_smallArms_d6` | `WBwSh` | 15 |
| 214 | `bank_note` | `it_bnknote` | 6 |
| 215 | `bank_coin` | `it_bnkcoin` | 4 |
| 314 | `fashionacc` | `WMgFs` | 1 |
| 325 | `Flowers` | `WFlwr` | 6 |
| 504 | `makeshiftbl` | `WMkBl` | 3 |
| 505 | `makeshiftbm` | `WMkBm` | 10 |
| 506 | `makeshiftbs` | `WMkBs` | 14 |
| 507 | `makeshiftss` | `WMkSs` | 1 |
| 508 | `makeshiftcs` | `WMkCs` | 1 |

## Detailed blueprints by friendly palette category

### Armor > Helmets (ID 9, 1)

| Blueprint | ResRef | Base item | Item class | Model parts | Properties |
|---|---|---|---|---|---:|
| zep_shadowhood | `zep_shadowhood` | 17 `helmet` | `helm` | 33 | 0 |

### Creature Items > Bite (ID 55, 1)

| Blueprint | ResRef | Base item | Item class | Model parts | Properties |
|---|---|---|---|---|---:|
| it_crewps012 | `it_crewps012` | 69 `cslashweapon` | `it_cr_sla` | 1 | 2 |

### Creature Items > Skin/Hide (ID 14, 4)

| Blueprint | ResRef | Base item | Item class | Model parts | Properties |
|---|---|---|---|---|---:|
| Vehicle Hardness 10 | `_mdrn_it_hard10` | 73 `creatureitem` | `it_cr_item` | 1 | 7 |
| Vehicle Hardness 15 | `_mdrn_it_hard15` | 73 `creatureitem` | `it_cr_item` | 1 | 7 |
| Vehicle Hardness 20 | `_mdrn_it_hard20` | 73 `creatureitem` | `it_cr_item` | 1 | 7 |
| Vehicle Hardness 5 | `_mdrn_it_hard5` | 73 `creatureitem` | `it_cr_item` | 1 | 7 |

### D20 Modern System Items > DM Tools (ID 113, 25)

| Blueprint | ResRef | Base item | Item class | Model parts | Properties |
|---|---|---|---|---|---:|
| D20 DM Clone Widget | `_mdrn_it_clonewd` | 24 `miscsmall` | `it_smlmisc` | 118 | 1 |
| D20 DM Clothesmaker | `_mdrn_it_clothes` | 24 `miscsmall` | `it_smlmisc` | 149 | 1 |
| D20 DM Float Widget | `_mdrn_it_floatng` | 24 `miscsmall` | `it_smlmisc` | 48 | 1 |
| D20 DM Modern Action | `_mdrn_it_dmd20` | 24 `miscsmall` | `it_smlmisc` | 240 | 1 |
| D20 DM Reload | `_mdrn_it_dmreloa` | 24 `miscsmall` | `it_smlmisc` | 216 | 1 |
| D20 DM Transmogrifier | `_mdrn_it_trans` | 24 `miscsmall` | `it_smlmisc` | 180 | 1 |
| DMFI Affliction Wand | `dmfi_afflict` | 24 `miscsmall` | `it_smlmisc` | 43 | 1 |
| DMFI Dicebag | `dmfi_dicebag` | 24 `miscsmall` | `it_smlmisc` | 178 | 1 |
| DMFI DM Wand | `dmfi_dmw` | 24 `miscsmall` | `it_smlmisc` | 129 | 1 |
| DMFI Emote Wand | `dmfi_emote` | 24 `miscsmall` | `it_smlmisc` | 229 | 1 |
| DMFI Encounter Ditto Widget | `dmfi_en_ditto` | 24 `miscsmall` | `it_smlmisc` | 195 | 1 |
| DMFI Encounter Wand | `dmfi_encounte` | 24 `miscsmall` | `it_smlmisc` | 199 | 1 |
| DMFI Exploder Widget | `dmfi_exploder` | 24 `miscsmall` | `it_smlmisc` | 105 | 1 |
| DMFI FX Wand | `dmfi_fx` | 24 `miscsmall` | `it_smlmisc` | 134 | 1 |
| DMFI Mute All NPCs Widget | `dmfi_mute` | 24 `miscsmall` | `it_smlmisc` | 131 | 1 |
| DMFI NPC/Ship Control and Tile Magic Wand | `dmfi_faction` | 24 `miscsmall` | `it_smlmisc` | 170 | 1 |
| DMFI Party 500 XP | `dmfi_500xp` | 24 `miscsmall` | `it_smlmisc` | 159 | 1 |
| DMFI Rotate Widget | `dmfi_rotate` | 24 `miscsmall` | `it_smlmisc` | 168 | 1 |
| DMFI Sound Wand | `dmfi_sound` | 24 `miscsmall` | `it_smlmisc` | 191 | 1 |
| DMFI Stop Combat Widget | `dmfi_peace` | 24 `miscsmall` | `it_smlmisc` | 17 | 1 |
| DMFI Voice Wand | `dmfi_voice` | 24 `miscsmall` | `it_smlmisc` | 2 | 1 |
| DMFI Voice Widget | `dmfi_voicewidget` | 24 `miscsmall` | `it_smlmisc` | 6 | 1 |
| DMFI XP and PC Campaign Storage Wand | `dmfi_xp` | 24 `miscsmall` | `it_smlmisc` | 46 | 1 |
| Slyn's Music Changer | `sly_musicwand` | 24 `miscsmall` | `it_smlmisc` | 78 | 1 |
| The One Ring | `dmfi_onering` | 52 `ring` | `it_ring` | 1 | 1 |

### D20 Modern System Items > Other Tools (ID 114, 18)

| Blueprint | ResRef | Base item | Item class | Model parts | Properties |
|---|---|---|---|---|---:|
| Driver's Manual | `_mdrn_drmanual` | 74 `book` | `IT_BOOK` | 39 | 0 |
| Heavy Arms Magazine | `_mdrn_rof_mag_ha` | 25 `bolt` | `WAmBo` | 11/11/11 | 2 |
| PC Autofollow Widget | `dmfi_pc_follow` | 24 `miscsmall` | `it_smlmisc` | 62 | 1 |
| PC Dicebag | `dmfi_pc_dicebag` | 79 `miscthin` | `IT_THNMISC` | 22 | 2 |
| PC Emote Widget | `pcemotewidget` | 24 `miscsmall` | `it_smlmisc` | 93 | 2 |
| Small Arms Magazine | `_mdrn_rof_mag_sa` | 20 `arrow` | `WAmAr` | 11/20/11 | 2 |
| ZLEGACY AK 74U (short assault rifle) | `d20_smarms017` | 8 `d20_smallarms_d8` | `WBwLn` | 11/61/11 | 3 |
| ZLEGACY AKM/AK 47 (7.62mmR assault rifle) | `d20_smarms016` | 8 `d20_smallarms_d8` | `WBwLn` | 11/51/11 | 3 |
| ZLEGACY Desert Eagle (0.50AE autoloader) | `d20_smarms021` | 8 `d20_smallarms_d8` | `WBwLn` | 11/111/11 | 3 |
| ZLEGACY Firearm Rounds | `_mdrn_rof_rounds` | 202 `ammo_rounds` | `it_faammo` | 0 | 0 |
| ZLEGACY FN 2000 Assault Rifle | `d20_smarms019` | 8 `d20_smallarms_d8` | `WBwLn` | 11/91/11 | 3 |
| ZLEGACY HK G-36 (5.56mm assault rifle) | `d20_smarms014` | 8 `d20_smallarms_d8` | `WBwLn` | 11/31/11 | 3 |
| ZLEGACY Light Crossbow | `d20_crosslt_001` | 7 `d20_longarms_d8` | `WBwXl` | 12/32/12 | 2 |
| ZLEGACY M 249 SAW | `d20_smarms020` | 8 `d20_smallarms_d8` | `WBwLn` | 11/101/11 | 3 |
| ZLEGACY M4 Carbine (5.56mm assault rifle) | `d20_smarms015` | 8 `d20_smallarms_d8` | `WBwLn` | 11/41/11 | 3 |
| ZLEGACY SPAS 12 (12-gauge shotgun) | `d20_smarms018` | 8 `d20_smallarms_d8` | `WBwLn` | 11/81/11 | 3 |
| ZLEGACY Thompson SMG | `d20_smarms011` | 11 `d20_handguns_d6` | `WBwSh` | 11/101/11 | 4 |
| ZLEGACY Winchester 94 (.444 hunting rifle) | `d20_smarms012` | 8 `d20_smallarms_d8` | `WBwLn` | 11/11/11 | 4 |

### D20 Modern System Items > Special Abilities (ID 115, 35)

| Blueprint | ResRef | Base item | Item class | Model parts | Properties |
|---|---|---|---|---|---:|
| _mdrn_pc_fist | `_mdrn_pc_fist` | 71 `cbludgweapon` | `it_cr_blud` | 1 | 0 |
| _mdrn_pc_skin | `_mdrn_pc_skin` | 73 `creatureitem` | `it_cr_item` | 1 | 0 |
| Action Point | `actionpoint` | 77 `gem` | `IT_GEM` | 98 | 0 |
| Alien Wyrm Bite | `_mdrn_ci_biteswa` | 69 `cslashweapon` | `it_cr_sla` | 1 | 3 |
| Gadget | `_mdrn_ot_gadget` | 66 `largebox` | `it_bigbox` | 63 | 0 |
| Land Spaceship | `_mdrn_ship_end` | 24 `miscsmall` | `it_smlmisc` | 171 | 1 |
| Psi Blade | `_mdrn_it_psiblad` | 0 `shortsword` | `WSwSs` | 244/164/201 | 3 |
| Rocket Skateboard | `_mdrn_ot_skate` | 66 `largebox` | `it_bigbox` | 20 | 0 |
| Ship Defense Repair (Level 1) | `_mdrn_ship_rep1` | 52 `ring` | `it_ring` | 115 | 1 |
| Ship Defense Repair (Level 3) | `_mdrn_ship_rep3` | 52 `ring` | `it_ring` | 115 | 1 |
| Ship Defense Repair (Level 6) | `_mdrn_ship_rep6` | 52 `ring` | `it_ring` | 115 | 1 |
| Ship Weaponry - Level 1 (Huge) | `_mdrn_ship_wpn1h` | 6 `d20_heavyweap_d10` | `WBwXh` | 11/161/11 | 2 |
| Ship Weaponry - Level 1 (Large) | `_mdrn_ship_wpn1l` | 7 `d20_longarms_d8` | `WBwXl` | 11/204/11 | 2 |
| Ship Weaponry - Level 1 (Medium) | `_mdrn_ship_wpn1m` | 8 `d20_smallarms_d8` | `WBwLn` | 71/71/11 | 2 |
| Ship Weaponry - Level 1 (Small) | `_mdrn_ship_weap1` | 11 `d20_handguns_d6` | `WBwSh` | 11/114/11 | 2 |
| Ship Weaponry - Level 2 (Huge) | `_mdrn_ship_wpn2h` | 6 `d20_heavyweap_d10` | `WBwXh` | 11/161/11 | 2 |
| Ship Weaponry - Level 2 (Large) | `_mdrn_ship_wpn2l` | 7 `d20_longarms_d8` | `WBwXl` | 11/204/11 | 2 |
| Ship Weaponry - Level 2 (Medium) | `_mdrn_ship_wpn2m` | 8 `d20_smallarms_d8` | `WBwLn` | 71/71/11 | 2 |
| Ship Weaponry - Level 2 (Small) | `_mdrn_ship_weap2` | 11 `d20_handguns_d6` | `WBwSh` | 11/114/11 | 2 |
| Ship Weaponry - Level 3 (Huge) | `_mdrn_ship_wpn3h` | 6 `d20_heavyweap_d10` | `WBwXh` | 11/161/11 | 2 |
| Ship Weaponry - Level 3 (Large) | `_mdrn_ship_wpn3l` | 7 `d20_longarms_d8` | `WBwXl` | 11/204/11 | 2 |
| Ship Weaponry - Level 3 (Medium) | `_mdrn_ship_wpn3m` | 8 `d20_smallarms_d8` | `WBwLn` | 71/71/11 | 2 |
| Ship Weaponry - Level 3 (Small) | `_mdrn_ship_weap3` | 11 `d20_handguns_d6` | `WBwSh` | 11/114/11 | 2 |
| Ship Weaponry - Level 4 (Huge) | `_mdrn_ship_wpn4h` | 6 `d20_heavyweap_d10` | `WBwXh` | 11/161/11 | 2 |
| Ship Weaponry - Level 4 (Large) | `_mdrn_ship_wpn4l` | 7 `d20_longarms_d8` | `WBwXl` | 11/204/11 | 2 |
| Ship Weaponry - Level 4 (Medium) | `_mdrn_ship_wpn4m` | 8 `d20_smallarms_d8` | `WBwLn` | 71/71/11 | 2 |
| Ship Weaponry - Level 4 (Small) | `_mdrn_ship_weap4` | 11 `d20_handguns_d6` | `WBwSh` | 11/114/11 | 2 |
| Starting Occupation | `occupation` | 52 `ring` | `it_ring` | 1 | 0 |
| Starting Occupation - Military | `occupation001` | 52 `ring` | `it_ring` | 1 | 2 |
| Wealth | `wealth` | 77 `gem` | `IT_GEM` | 117 | 0 |
| Wealth from Major Breakthrough | `_mdrn_ot_majw` | 77 `gem` | `IT_GEM` | 117 | 0 |
| Wealth from Minor Breakthrough | `_mdrn_ot_minw` | 77 `gem` | `IT_GEM` | 118 | 0 |
| Wealth from Royalty 1 | `_mdrn_ot_royw1` | 77 `gem` | `IT_GEM` | 117 | 0 |
| Wealth from Royalty 2 | `_mdrn_ot_royw2` | 77 `gem` | `IT_GEM` | 118 | 0 |
| Wealth from Windfall | `_mdrn_windfallw` | 77 `gem` | `IT_GEM` | 119 | 0 |

### Miscellaneous > Books (ID 60, 18)

| Blueprint | ResRef | Base item | Item class | Model parts | Properties |
|---|---|---|---|---|---:|
| Arcane Lore | `_mdrn_it_alore` | 74 `book` | `IT_BOOK` | 137 | 1 |
| Artwork | `_mdrn_it_art` | 74 `book` | `IT_BOOK` | 82 | 1 |
| Behavioral Sciences Data | `_mdrn_it_behave` | 74 `book` | `IT_BOOK` | 108 | 1 |
| Business Information | `_mdrn_it_busines` | 74 `book` | `IT_BOOK` | 116 | 1 |
| Computer Results | `_mdrn_it_compuse` | 74 `book` | `IT_BOOK` | 22 | 1 |
| Current News | `_mdrn_it_current` | 74 `book` | `IT_BOOK` | 52 | 1 |
| Data Results | `_mdrn_it_sampdat` | 74 `book` | `IT_BOOK` | 26 | 1 |
| Gathered Information | `_mdrn_it_gaterin` | 74 `book` | `IT_BOOK` | 124 | 1 |
| Government Information | `_mdrn_it_civics` | 74 `book` | `IT_BOOK` | 75 | 1 |
| Historical Record | `_mdrn_it_history` | 74 `book` | `IT_BOOK` | 84 | 1 |
| Investigation Results | `_mdrn_it_invest` | 74 `book` | `IT_BOOK` | 73 | 1 |
| Life Sciences Data | `_mdrn_it_elife` | 74 `book` | `IT_BOOK` | 56 | 1 |
| Popular Culture Fact | `_mdrn_it_popcult` | 74 `book` | `IT_BOOK` | 15 | 1 |
| Research Results | `_mdrn_it_researc` | 74 `book` | `IT_BOOK` | 123 | 1 |
| Tactical Information | `_mdrn_it_tactics` | 74 `book` | `IT_BOOK` | 30 | 1 |
| Technological Information | `_mdrn_it_techkno` | 74 `book` | `IT_BOOK` | 115 | 1 |
| Theological Information | `_mdrn_it_theolog` | 74 `book` | `IT_BOOK` | 54 | 1 |
| Unknown Writing | `_mdrn_it_rese001` | 74 `book` | `IT_BOOK` | 83 | 1 |

### Miscellaneous > Other (ID 23, 4)

| Blueprint | ResRef | Base item | Item class | Model parts | Properties |
|---|---|---|---|---|---:|
| Candelabra | `_mdrn_it_cand2` | 15 `torch` | `it_torch` | 117 | 0 |
| Long Candle | `_mdrn_it_lgcand` | 15 `torch` | `it_torch` | 120 | 0 |
| Plate of Food | `_mdrn_it_plfood` | 15 `torch` | `it_torch` | 128 | 0 |
| Short Candle | `_mdrn_it_shcandl` | 15 `torch` | `it_torch` | 119 | 0 |

### Modern Clothing > Clothing (ID 117, 89)

| Blueprint | ResRef | Base item | Item class | Model parts | Properties |
|---|---|---|---|---|---:|
| Band & Combat Pants (Green) | `_mdrn_cl_cropt01` | 16 `armor` | `AArCl` |  | 0 |
| Band & Jeans (Blue) | `_mdrn_cl_cropt02` | 16 `armor` | `AArCl` |  | 0 |
| Camo Pants (Brown) & Black T-shirt | `_mdrn_cl_tc_blk` | 16 `armor` | `AArCl` |  | 0 |
| Camo Pants (Brown) & Brown T-shirt | `_mdrn_cl_tc_brn` | 16 `armor` | `AArCl` |  | 0 |
| Camo Pants (Green) & Green Jacket | `_mdrn_it_camjack` | 16 `armor` | `AArCl` |  | 0 |
| Camo Pants (Green) & Green T-Shirt | `_mdrn_cl_tc_grn` | 16 `armor` | `AArCl` |  | 0 |
| Coat, Long (Black) Black Shirt & Pants | `_mdrn_cl_lcoat01` | 16 `armor` | `AArCl` |  | 0 |
| Coat, Long (Brown) Brown Shirt & Pants | `_mdrn_cl_lcoa001` | 16 `armor` | `AArCl` |  | 0 |
| Coat, Long (Green) Fancy Shirt Black Pants | `_mdrn_cl_lcoat03` | 16 `armor` | `AArCl` |  | 0 |
| Coat, Long (Red) White Shirt Black Pants | `_mdrn_cl_lcoat02` | 16 `armor` | `AArCl` |  | 0 |
| Combat Pants (Black) & Bike Jacket (Black) | `_mdrn_cl_cbkljbk` | 16 `armor` | `AArCl` |  | 0 |
| Combat Pants (Black) & Black T-Shirt | `_mdrn_cl_cbktsbk` | 16 `armor` | `AArCl` |  | 0 |
| Combat Pants (Black) & Blue Muscle Top | `_mdrn_cl_cbkvblu` | 16 `armor` | `AArCl` |  | 0 |
| Combat Pants (Brown) & Bike Jacket (Black) | `_mdrn_cl_cbrljbk` | 16 `armor` | `AArCl` |  | 0 |
| Diving Suit | `_mdrn_cl_diverst` | 16 `armor` | `AArCl` |  | 0 |
| Dress, Long (Black) | `_mdrn_it_bgown` | 16 `armor` | `AArCl` |  | 0 |
| Dress, Long (Brown/Cream) | `_mdrn_cl_ldress1` | 16 `armor` | `AArCl` |  | 0 |
| Dress, Mini (Blue) | `_mdrn_cl_sdrssbl` | 16 `armor` | `AArCl` |  | 0 |
| Dress, Mini (Purple) | `_mdrn_cl_sdrsspl` | 16 `armor` | `AArCl` |  | 0 |
| Goth Gear | `_mdrn_cl_gothgl2` | 16 `armor` | `AArCl` |  | 0 |
| Goth Girl | `_mdrn_cl_gothgl` | 16 `armor` | `AArCl` |  | 0 |
| Gown (Black) | `_mdrn_it_gown005` | 16 `armor` | `AArCl` |  | 0 |
| Gown (Gold) | `_mdrn_it_gown006` | 16 `armor` | `AArCl` |  | 0 |
| Gown (Maroon) | `_mdrn_it_gown003` | 16 `armor` | `AArCl` |  | 0 |
| Gown (Pink) | `_mdrn_it_gown007` | 16 `armor` | `AArCl` |  | 0 |
| Gown (Red & White) | `_mdrn_it_gown002` | 16 `armor` | `AArCl` |  | 0 |
| Gown /w Gloves (Blue) | `_mdrn_it_gown004` | 16 `armor` | `AArCl` |  | 0 |
| Gown /w Gloves (Blue) | `_mdrn_it_gownblu` | 16 `armor` | `AArCl` |  | 0 |
| Gown /w Gloves (Green) | `_mdrn_it_gown001` | 16 `armor` | `AArCl` |  | 0 |
| Jeans (Blue) & Bike Jacket (Black) | `_mdrn_cl_jblljbk` | 16 `armor` | `AArCl` |  | 0 |
| Jeans (Blue) & Bike Jacket (Brown) | `_mdrn_cl_jblljbr` | 16 `armor` | `AArCl` |  | 0 |
| Jeans (Blue) & Black T-Shirt, Jacket (Brown) | `_mdrn_jcktjns004` | 16 `armor` | `AArCl` |  | 0 |
| Jeans (Blue) & Blouse (Blue/Brown) | `_mdrn_cl_frill01` | 16 `armor` | `AArCl` |  | 0 |
| Jeans (Blue) & Blue Shirt | `_mdrn_it_jeanwor` | 16 `armor` | `AArCl` |  | 0 |
| Jeans (Blue) & Gray Muscle Top | `_mdrn_cl_bluebgr` | 16 `armor` | `AArCl` |  | 0 |
| Jeans (Blue) & Red T-Shirt (LS) | `_mdrn_cl_jbtlsvr` | 16 `armor` | `AArCl` |  | 0 |
| Jeans (Blue) & Red T-Shirt, Long Jacket | `_mdrn_it_ljack01` | 16 `armor` | `AArCl` |  | 0 |
| Jeans (Blue) & White T-Shirt | `_mdrn_cl_jbtshtw` | 16 `armor` | `AArCl` |  | 0 |
| Jeans (Blue) & White T-Shirt, Stripe | `_mdrn_cl_jbststw` | 16 `armor` | `AArCl` |  | 0 |
| Leather Vest (Black) /w Boot Knife | `_mdrn_it_lthr001` | 16 `armor` | `AArCl` |  | 0 |
| Pajamas, Long (White) | `_mdrn_cl_pjlng01` | 16 `armor` | `AArCl` |  | 0 |
| Pajamas, Short (White) | `_mdrn_cl_pjsht01` | 16 `armor` | `AArCl` |  | 0 |
| Pants (Black) & Blue Shirt | `_mdrn_cl_bkblu` | 16 `armor` | `AArCl` |  | 0 |
| Pants (Black) & Blue T-Shirt /w Vest | `_mdrn_cl_vest002` | 16 `armor` | `AArCl` |  | 0 |
| Pants (Black) & Brown Muscle Top | `_mdrn_cl_bkmtbrn` | 16 `armor` | `AArCl` |  | 0 |
| Pants (Black) & Brown Shirt | `_mdrn_cl_bkbrown` | 16 `armor` | `AArCl` |  | 0 |
| Pants (Black) & Red Shirt | `_mdrn_cl_bkred` | 16 `armor` | `AArCl` |  | 0 |
| Pants (Black) & Red T-Shirt, Stripe | `_mdrn_cl_bkstsrd` | 16 `armor` | `AArCl` |  | 0 |
| Pants (Black) & White Shirt | `_mdrn_cl_bkwht` | 16 `armor` | `AArCl` |  | 0 |
| Pants (Black) & Yellow Shirt | `_mdrn_cl_bkyell` | 16 `armor` | `AArCl` |  | 0 |
| Pants (Black) White Shirt & Brown Jacket | `_mdrn_jcktjns001` | 16 `armor` | `AArCl` |  | 0 |
| Pants (Black) White Shirt & Grey Jacket | `_mdrn_jcktjns003` | 16 `armor` | `AArCl` |  | 0 |
| Pants (Blue) & White Shirt | `_mdrn_cl_bluewhi` | 16 `armor` | `AArCl` |  | 0 |
| Pants (Brown) & Black Shirt | `_mdrn_cl_brnblck` | 16 `armor` | `AArCl` |  | 0 |
| Pants (Brown) & Black Shirt /w Vest | `_mdrn_cl_vest001` | 16 `armor` | `AArCl` |  | 0 |
| Pants (Brown) & Blouse (Blue/Black) | `_mdrn_cl_blse01` | 16 `armor` | `AArCl` |  | 0 |
| Pants (Brown) & Green Muscle Top | `_mdrn_cl_brmtgrn` | 16 `armor` | `AArCl` |  | 0 |
| Pants (Brown) & Yellow Shirt | `_mdrn_cl_brnyell` | 16 `armor` | `AArCl` |  | 0 |
| Pants (Brown) White Shirt & Brown Jacket | `_mdrn_jcktjns002` | 16 `armor` | `AArCl` |  | 0 |
| Pants (Green) & Bike Jacket (Brown) | `_mdrn_cl_pgrljbr` | 16 `armor` | `AArCl` |  | 0 |
| Pants (Green) & Brown Shirt | `_mdrn_cl_grnbrwn` | 16 `armor` | `AArCl` |  | 0 |
| Pants (Green) Green Shirt & Brown Jacket | `_mdrn_jcktjns_04` | 16 `armor` | `AArCl` |  | 0 |
| Pants (Green) White Shirt & Green Jacket | `_mdrn_jcktjns_01` | 16 `armor` | `AArCl` |  | 0 |
| Shorts (Blue) & Blue Shirt | `_mdrn_it_blshort` | 16 `armor` | `AArCl` |  | 0 |
| Shorts (Blue) & Blue Shirt /w Bag | `_mdrn_it_blshbg` | 16 `armor` | `AArCl` |  | 0 |
| Shorts (Blue) & Red T-shirt /w Backpack | `_mdrn_it_blshbg2` | 16 `armor` | `AArCl` |  | 0 |
| Shorts (Grey) & Grey Muscle Top | `_mdrn_cl_shrts01` | 16 `armor` | `AArCl` |  | 0 |
| Skirt (Blue) Black T Shirt | `_mdrn_cl_skrtsh5` | 16 `armor` | `AArCl` |  | 0 |
| Skirt (Blue) Maroon Blouse | `_mdrn_cl_skrtsh2` | 16 `armor` | `AArCl` |  | 0 |
| Skirt (Blue) White Blouse | `_mdrn_cl_skrtsh6` | 16 `armor` | `AArCl` |  | 0 |
| Skirt (Blue) White T Shirt | `_mdrn_cl_skrtsh4` | 16 `armor` | `AArCl` |  | 0 |
| Skirt (Brown) Cream Blouse | `_mdrn_cl_skrtsh3` | 16 `armor` | `AArCl` |  | 0 |
| Skirt (Grey) Maroon Blouse | `_mdrn_cl_skrtsh1` | 16 `armor` | `AArCl` |  | 0 |
| Suit (Black) Long Jacket /w Vest | `_mdrn_it_msblack` | 16 `armor` | `AArCl` |  | 0 |
| Suit (Grey) Long Jacket /w Vest | `_mdrn_it_msbl001` | 16 `armor` | `AArCl` |  | 0 |
| Suit & Skirt, Black | `_mdrn_it_skts005` | 16 `armor` | `AArCl` |  | 0 |
| Suit & Skirt, Brown | `_mdrn_it_skts003` | 16 `armor` | `AArCl` |  | 0 |
| Suit & Skirt, Green | `_mdrn_it_skts002` | 16 `armor` | `AArCl` |  | 0 |
| Suit & Skirt, Grey | `_mdrn_it_skts004` | 16 `armor` | `AArCl` |  | 0 |
| Suit & Skirt, Red | `_mdrn_it_skts001` | 16 `armor` | `AArCl` |  | 0 |
| Suit, Black | `_mdrn_it_blksuit` | 16 `armor` | `AArCl` |  | 0 |
| Suit, Black /w Bow Tie | `_mdrn_it_blkstbw` | 16 `armor` | `AArCl` |  | 0 |
| Suit, Blue | `_mdrn_it_blusuit` | 16 `armor` | `AArCl` |  | 0 |
| Suit, Brown | `_mdrn_it_brnsuit` | 16 `armor` | `AArCl` |  | 0 |
| Suit, Green | `_mdrn_it_grsuit` | 16 `armor` | `AArCl` |  | 0 |
| Suit, Grey | `_mdrn_it_grysuit` | 16 `armor` | `AArCl` |  | 0 |
| Suit, Red | `_mdrn_it_redsuit` | 16 `armor` | `AArCl` |  | 0 |
| Vac Suit (F) | `_mdrn_it_vacsuif` | 16 `armor` | `AArCl` |  | 0 |
| Vac Suit (M) | `_mdrn_it_vacsuit` | 16 `armor` | `AArCl` |  | 0 |

### Modern Clothing > Heavy (ID 119, 3)

| Blueprint | ResRef | Base item | Item class | Model parts | Properties |
|---|---|---|---|---|---:|
| Combat Suit (Sci fi) | `_mdrn_cl_combath` | 16 `armor` | `AArCl` |  | 0 |
| Combat Suit (Sci fi) - Reinforced | `_mdrn_cl_combat2` | 16 `armor` | `AArCl` |  | 0 |
| Power Armour | `_mdrn_cl_powerar` | 16 `armor` | `AArCl` |  | 0 |

### Modern Clothing > Helmets (ID 120, 20)

| Blueprint | ResRef | Base item | Item class | Model parts | Properties |
|---|---|---|---|---|---:|
| Balaclava, Double Hole (Female) | `_mdrn_hm_balac02` | 17 `helmet` | `helm` | 82 | 1 |
| Balaclava, Double Hole (Male) | `_mdrn_hm_balac03` | 17 `helmet` | `helm` | 80 | 1 |
| Balaclava, Single Hole (Female) | `_mdrn_hm_balac01` | 17 `helmet` | `helm` | 83 | 1 |
| Balaclava, Single Hole (Male) | `_mdrn_hm_balac04` | 17 `helmet` | `helm` | 81 | 1 |
| Camo Helmet /w Mask (Blue) | `_mdrn_hm_camo04` | 17 `helmet` | `helm` | 35 | 0 |
| Camo Helmet /w Mask (Green) | `_mdrn_hm_camo01` | 17 `helmet` | `helm` | 35 | 1 |
| Camo Helmet /w Mask (Grey) | `_mdrn_hm_camo02` | 17 `helmet` | `helm` | 35 | 0 |
| Camo Helmet /w Mask (Khaki) | `_mdrn_hm_camo03` | 17 `helmet` | `helm` | 35 | 0 |
| Clone Helmet (Sci-fi) | `_mdrn_hm_clone01` | 17 `helmet` | `helm` | 51 | 1 |
| Combat Helmet (Sci-fi) | `_mdrn_hm_scifi01` | 17 `helmet` | `helm` | 75 | 1 |
| Diver's Helmet | `_mdrn_hm_diver` | 17 `helmet` | `helm` | 188 | 0 |
| Hat (Black) | `_mdrn_hm_hatblck` | 80 `cloak` | `cloak` | 100 | 0 |
| Hat (Brown) | `_mdrn_hm_hatbrwn` | 80 `cloak` | `cloak` | 100 | 0 |
| Hat (Green) | `_mdrn_hm_hatgren` | 80 `cloak` | `cloak` | 100 | 0 |
| Hat (Khaki) | `_mdrn_hm_hatkhki` | 80 `cloak` | `cloak` | 100 | 0 |
| Hood (Black) | `_mdrn_hm_hood01` | 17 `helmet` | `helm` | 33 | 0 |
| Power Armour Helmet | `_mdrn_hm_powerar` | 17 `helmet` | `helm` | 250 | 0 |
| SEAL Mask | `_mdrn_hm_seal01` | 17 `helmet` | `helm` | 35 | 0 |
| Vac Suit Helmet | `_mdrn_it_vachelm` | 17 `helmet` | `helm` | 75 | 0 |
| Vac Suit Helmet 2 | `_mdrn_it_vach001` | 17 `helmet` | `helm` | 52 | 0 |

### Modern Clothing > Light (ID 118, 6)

| Blueprint | ResRef | Base item | Item class | Model parts | Properties |
|---|---|---|---|---|---:|
| Jeans (Black) & White Shirt /w Combat Vest (Brown)  | `_mdrn_it_brvestw` | 16 `armor` | `AArCl` |  | 0 |
| Jeans (Blue) & White T-Shirt /w Combat Vest (Black)  | `_mdrn_cl_wout` | 16 `armor` | `AArCl` |  | 0 |
| Leather Sports Padding | `_mdrn_it_sprtpad` | 21 `belt` | `it_belt` | 62 | 1 |
| Light Undercover Shirt | `_mdrn_it_lshirt` | 21 `belt` | `it_belt` | 62 | 1 |
| Pull-up pouch vest | `_mdrn_it_pouch` | 21 `belt` | `it_belt` | 63 | 1 |
| Undercover Vest | `_mdrn_it_uvest` | 21 `belt` | `it_belt` | 61 | 1 |

### Modern Clothing > Medium (ID 124, 2)

| Blueprint | ResRef | Base item | Item class | Model parts | Properties |
|---|---|---|---|---|---:|
| Clone Armour (Sci fi) | `_mdrn_cl_clone01` | 16 `armor` | `AArCl` |  | 0 |
| Concealable Vest | `_mdrn_it_cvest` | 21 `belt` | `it_belt` | 61 | 2 |

### Modern Clothing > NPC Clothing (ID 125, 41)

| Blueprint | ResRef | Base item | Item class | Model parts | Properties |
|---|---|---|---|---|---:|
| Alien Chitin Armor | `_mdrn_cl_alien01` | 16 `armor` | `AArCl` |  | 0 |
| Alien Chitin Helmet | `_mdrn_hm_alienhl` | 17 `helmet` | `helm` | 95 | 1 |
| Alien Head | `_mdrn_hm_alien01` | 17 `helmet` | `helm` | 98 | 0 |
| Alien Head /w Helmet | `_mdrn_hm_scifisa` | 17 `helmet` | `helm` | 22 | 0 |
| Alien Head /w Scarf | `_mdrn_hm_alien02` | 17 `helmet` | `helm` | 97 | 0 |
| Apron (Green) Pants & Grey Shirt | `_mdrn_it_apron1` | 16 `armor` | `AArCl` |  | 0 |
| Apron (Red) Pants & Blue Shirt | `_mdrn_cl_redapro` | 16 `armor` | `AArCl` |  | 0 |
| Apron (White) Jeans & Red Shirt | `_mdrn_cl_whapron` | 16 `armor` | `AArCl` |  | 0 |
| Apron (White) Pants & Beige T-Shirt | `_mdrn_cl_cookapr` | 16 `armor` | `AArCl` |  | 0 |
| Apron (White) Pants & Blue Shirt | `_mdrn_it_apron2` | 16 `armor` | `AArCl` |  | 0 |
| Bandages & Camo Pants (Green) | `_mdrn_cl_bandge1` | 16 `armor` | `AArCl` |  | 0 |
| Bare Chest & Combat Pants (Brown) | `_mdrn_cl_barec01` | 16 `armor` | `AArCl` |  | 0 |
| Bare Chest & Combat Pants (Grey) | `_mdrn_cl_barec02` | 16 `armor` | `AArCl` |  | 0 |
| Bare Chest & Jeans (Blue) | `_mdrn_cl_barec03` | 16 `armor` | `AArCl` |  | 0 |
| Bare Chest & Pants (Black) | `_mdrn_cl_barec04` | 16 `armor` | `AArCl` |  | 0 |
| Future Scrubs (f) | `_mdrn_it_scru002` | 16 `armor` | `AArCl` |  | 0 |
| Girls Dress, Short (Black & White) | `_mdrn_cl_girls01` | 16 `armor` | `AArCl` |  | 0 |
| Girls Shorts (Grey) Brown Shirt | `_mdrn_cl_girls02` | 16 `armor` | `AArCl` |  | 0 |
| Green Overalls | `_mdrn_it_greenov` | 16 `armor` | `AArCl` |  | 0 |
| Harlequin - Female | `_mdrn_cl_harleqn` | 16 `armor` | `AArCl` |  | 0 |
| Lab Coat (Blue Pants) | `_mdrn_cl_scie001` | 16 `armor` | `AArCl` |  | 0 |
| Lab Coat (Brown Pants) | `_mdrn_cl_scienc1` | 16 `armor` | `AArCl` |  | 0 |
| Lab Coat (Grey Pants) | `_mdrn_cl_docgrp` | 16 `armor` | `AArCl` |  | 0 |
| Maid Uniform | `_mdrn_cl_fmaid01` | 16 `armor` | `AArCl` |  | 0 |
| Overalls, Brown | `_mdrn_it_overalb` | 16 `armor` | `AArCl` |  | 0 |
| Overalls, Green | `_mdrn_it_overall` | 16 `armor` | `AArCl` |  | 0 |
| Overalls, Grey | `_mdrn_it_overalg` | 16 `armor` | `AArCl` |  | 0 |
| Police Uniform | `_mdrn_cl_unfmpol` | 16 `armor` | `AArCl` |  | 0 |
| Random Clothing Base Outfit | `_mdrn_cl_base` | 16 `armor` | `AArCl` |  | 0 |
| Regulation Underwear | `_mdrn_it_underwr` | 16 `armor` | `AArCl` |  | 0 |
| Rusted Robot Armor | `_mdrn_cl_robot01` | 16 `armor` | `AArCl` |  | 0 |
| Rusted Robot Head | `_mdrn_hm_robot01` | 17 `helmet` | `helm` | 24 | 0 |
| Scrubs | `_mdrn_it_scru001` | 16 `armor` | `AArCl` |  | 0 |
| Security Guard Uniform (Black) | `_mdrn_cl_secgard` | 16 `armor` | `AArCl` |  | 0 |
| Security Guard Uniform (Blue) | `_mdrn_cl_secgrd2` | 16 `armor` | `AArCl` |  | 0 |
| Security Guard Uniform (Brown) | `_mdrn_cl_secgrd1` | 16 `armor` | `AArCl` |  | 0 |
| Space Marine Helmet | `_mdrn_hm_smarine` | 17 `helmet` | `helm` | 78 | 0 |
| Stasis Bodyglove | `_mdrn_it_scrubs` | 16 `armor` | `AArCl` |  | 0 |
| Underwear - Female | `_mdrn_it_undrwr1` | 16 `armor` | `AArCl` |  | 0 |
| Wedding Dress | `_mdrn_cl_wedding` | 16 `armor` | `AArCl` |  | 0 |
| White Uniform | `_mdrn_it_whunif` | 16 `armor` | `AArCl` |  | 0 |

### Modern Clothing > Shields > Large Shields (ID 122, 1)

| Blueprint | ResRef | Base item | Item class | Model parts | Properties |
|---|---|---|---|---|---:|
| Chitin Shield | `_mdrn_chitinshd2` | 56 `largeshield` | `AShLw` | 110 | 0 |

### Modern Clothing > Shields > Small Shields (ID 121, 1)

| Blueprint | ResRef | Base item | Item class | Model parts | Properties |
|---|---|---|---|---|---:|
| Trash Can Lid | `_mdrn_it_canlid` | 14 `smallshield` | `AShSw` | 44 | 2 |

### Modern Clothing > Shields > Tower Shields (ID 123, 3)

| Blueprint | ResRef | Base item | Item class | Model parts | Properties |
|---|---|---|---|---|---:|
| Ballistic Shield (Metal) | `_mdrn_swatshld1` | 57 `towershield` | `AShTo` | 50 | 1 |
| Chitin Shield | `_mdrn_chitinshld` | 57 `towershield` | `AShTo` | 20 | 1 |
| Riot (SWAT) Shield (Polycarbonate) | `_mdrn_swatshld2` | 57 `towershield` | `AShTo` | 51 | 1 |

### Modern General >  Misc. (ID 112, 46)

| Blueprint | ResRef | Base item | Item class | Model parts | Properties |
|---|---|---|---|---|---:|
| Aluminum Travel Case | `_mdrn_ot_acase` | 66 `largebox` | `it_bigbox` | 31 | 2 |
| Backpack | `_mdrn_ot_bpack` | 66 `largebox` | `it_bigbox` | 56 | 1 |
| Ball, Large | `_mdrn_it_ball_lg` | 206 `modern_mdm` | `it_mdrnmdm` | 153 | 0 |
| Black Umbrella | `_mdrn_it_bumb` | 314 `fashionacc` | `WMgFs` | 11/11/11 | 2 |
| Briefcase | `_mdrn_it_case2` | 28 `club` | `WBlCl` | 71/102/51 | 2 |
| Bulldozer Key | `_mdrn_kt_dozer` | 24 `miscsmall` | `it_smlmisc` | 171 | 0 |
| Bunch of Carnations | `_mdrn_fl_bnch004` | 325 `Flowers` | `WFlwr` | 11/131/11 | 0 |
| Bunch of Daisies | `_mdrn_fl_bnch003` | 325 `Flowers` | `WFlwr` | 11/121/11 | 0 |
| Bunch of Flowers | `_mdrn_fl_bnch002` | 325 `Flowers` | `WFlwr` | 11/101/11 | 0 |
| Bunch of Lilies | `_mdrn_fl_bnch005` | 325 `Flowers` | `WFlwr` | 11/141/11 | 0 |
| Bunch of Roses | `_mdrn_fl_bnch001` | 325 `Flowers` | `WFlwr` | 11/151/11 | 0 |
| Bunch of Tulips | `_mdrn_fl_bnch006` | 325 `Flowers` | `WFlwr` | 11/181/11 | 0 |
| Cadillac Key | `_mdrn_kt_caddy` | 24 `miscsmall` | `it_smlmisc` | 171 | 0 |
| Chevrolet Key | `_mdrn_kt_chevy` | 24 `miscsmall` | `it_smlmisc` | 171 | 0 |
| Cigarette (men's) | `_mdrn_cigt_men` | 210 `holdable` | `it_mod` | 0 | 0 |
| Cigarette (women's) | `_mdrn_cigt_women` | 210 `holdable` | `it_mod` | 0 | 0 |
| Cigarettes | `_mdrn_ot_cigar` | 24 `miscsmall` | `it_smlmisc` | 99 | 0 |
| Contractor's Field Bag | `_mdrn_ot_cbag` | 66 `largebox` | `it_bigbox` | 10 | 1 |
| Day Pack | `_mdrn_ot_dpack` | 66 `largebox` | `it_bigbox` | 52 | 0 |
| Ear Trumpet | `d20_mw_eartrmpt` | 506 `makeshiftbs` | `WMkBs` | 82/82/82 | 2 |
| Fishing Rod | `d20_mw_fishingr` | 506 `makeshiftbs` | `WMkBs` | 81/81/81 | 2 |
| Gem, Amber | `_mdrn_it_amber` | 77 `gem` | `IT_GEM` | 59 | 0 |
| Gem, Lapiz Lazuli | `_mdrn_it_lapislz` | 77 `gem` | `IT_GEM` | 92 | 0 |
| Gem, Turquoise | `_mdrn_it_turquoi` | 77 `gem` | `IT_GEM` | 69 | 0 |
| Glass of Wine | `_mdrn_it_wine` | 211 `holdable2` | `it_hold` | 2 | 0 |
| Hand Bell (Brass) | `d20_mw_handbellb` | 506 `makeshiftbs` | `WMkBs` | 61/61/61 | 2 |
| Hand Bell (Painted) | `d20_mw_handbellp` | 506 `makeshiftbs` | `WMkBs` | 51/51/51 | 2 |
| Handbag | `_mdrn_ot_hbag` | 66 `largebox` | `it_bigbox` | 15 | 0 |
| Helicopter Key | `_mdrn_kt_heli` | 24 `miscsmall` | `it_smlmisc` | 171 | 0 |
| Hummer Key | `_mdrn_kt_hummer` | 24 `miscsmall` | `it_smlmisc` | 171 | 0 |
| Masque | `d20_mw_masque` | 506 `makeshiftbs` | `WMkBs` | 21/21/21 | 2 |
| Motorcycle Key | `_mdrn_kt_bike` | 24 `miscsmall` | `it_smlmisc` | 171 | 0 |
| Mug | `_mdrn_it_mug` | 211 `holdable2` | `it_hold` | 3 | 0 |
| Notebook | `_mdrn_it_notebk` | 74 `book` | `IT_BOOK` | 56 | 0 |
| Paint Brush | `d20_mw_paintbrsh` | 506 `makeshiftbs` | `WMkBs` | 41/41/41 | 2 |
| Paint Pallette | `d20_mw_paintpal` | 506 `makeshiftbs` | `WMkBs` | 31/31/31 | 2 |
| Patrol Box | `_mdrn_ot_pbox` | 66 `largebox` | `it_bigbox` | 63 | 1 |
| Playing Cards | `_mdrn_it_cards` | 206 `modern_mdm` | `it_mdrnmdm` | 79 | 0 |
| Puppet | `d20_mw_puppet` | 506 `makeshiftbs` | `WMkBs` | 11/11/11 | 2 |
| Range Pack | `_mdrn_ot_rpack` | 66 `largebox` | `it_bigbox` | 18 | 1 |
| Sedan Key | `_mdrn_kt_sedan` | 24 `miscsmall` | `it_smlmisc` | 171 | 0 |
| Spaceship Key | `_mdrn_kt_ship` | 24 `miscsmall` | `it_smlmisc` | 171 | 0 |
| Sportscar Key | `_mdrn_kt_sports` | 24 `miscsmall` | `it_smlmisc` | 171 | 0 |
| SUV Key | `_mdrn_kt_suv` | 24 `miscsmall` | `it_smlmisc` | 171 | 0 |
| Tank Key | `_mdrn_kt_tank` | 24 `miscsmall` | `it_smlmisc` | 171 | 0 |
| Thermos | `_mdrn_it_thermos` | 211 `holdable2` | `it_hold` | 4 | 0 |

### Modern General > Computers and Consumer Electronics (ID 107, 9)

| Blueprint | ResRef | Base item | Item class | Model parts | Properties |
|---|---|---|---|---|---:|
| 35mm Camera | `_mdrn_ot_camera` | 24 `miscsmall` | `it_smlmisc` | 104 | 0 |
| Cell Phone | `_mdrn_ot_phone` | 15 `torch` | `it_torch` | 14 | 0 |
| Digital Audio Recorder | `_mdrn_it_audrec` | 205 `modern_thin` | `it_mdrnthn` | 10 | 0 |
| Notebook Computer | `_mdrn_ot_laptop` | 29 `miscmedium` | `it_midmisc` | 128 | 2 |
| Notebook Computer (Upgraded) | `_mdrn_ot_laptp2` | 29 `miscmedium` | `it_midmisc` | 128 | 2 |
| PDA | `_mdrn_it_pda` | 205 `modern_thin` | `it_mdrnthn` | 6 | 1 |
| Portable Video Camera | `_mdrn_ot_camcord` | 15 `torch` | `it_torch` | 23 | 0 |
| Professional Walkie-Talkie | `_mdrn_ot_talkie` | 15 `torch` | `it_torch` | 19 | 0 |
| Scientific Geiger Counter | `_mdrn_ot_geiger` | 15 `torch` | `it_torch` | 10 | 0 |

### Modern General > Drugs (ID 116, 7)

| Blueprint | ResRef | Base item | Item class | Model parts | Properties |
|---|---|---|---|---|---:|
| Adrenaline Injection | `_mdrn_ot_adrenal` | 209 `modern_pills` | `it_mdrnpil` | 24 | 1 |
| Anti-toxin | `_mdrn_ot_antidot` | 15 `torch` | `it_torch` | 16 | 1 |
| Antibiotics | `_mdrn_ot_cdiseas` | 15 `torch` | `it_torch` | 16 | 1 |
| Atropine Injection | `_mdrn_ot_poison1` | 209 `modern_pills` | `it_mdrnpil` | 26 | 1 |
| Caffiene Tablets | `_mdrn_ot_caffien` | 209 `modern_pills` | `it_mdrnpil` | 5 | 1 |
| Emergency Plasma | `_mdrn_ot_plasma` | 39 `healerskit` | `it_medkit` | 7 | 1 |
| Syringe | `_mdrn_ot_syringe` | 15 `torch` | `it_torch` | 16 | 0 |

### Modern General > Money (ID 127, 11)

| Blueprint | ResRef | Base item | Item class | Model parts | Properties |
|---|---|---|---|---|---:|
| $1 Bill | `_mdrn_cu_dolr1` | 214 `bank_note` | `it_bnknote` | 4 | 1 |
| $10 Bill | `_mdrn_cu_dolr10` | 214 `bank_note` | `it_bnknote` | 9 | 1 |
| $100 Bill | `_mdrn_cu_dolr100` | 214 `bank_note` | `it_bnknote` | 5 | 1 |
| $20 Bill | `_mdrn_cu_dolr20` | 214 `bank_note` | `it_bnknote` | 6 | 1 |
| $5 Bill | `_mdrn_cu_dolr5` | 214 `bank_note` | `it_bnknote` | 7 | 1 |
| $50 Bill | `_mdrn_cu_dolr50` | 214 `bank_note` | `it_bnknote` | 8 | 1 |
| Copper Coin | `_mdrn_cu_copper` | 215 `bank_coin` | `it_bnkcoin` | 2 | 1 |
| Credit Card | `_mdrn_creditcard` | 205 `modern_thin` | `it_mdrnthn` | 51 | 1 |
| Gold Coin | `_mdrn_cu_gold` | 215 `bank_coin` | `it_bnkcoin` | 3 | 1 |
| Platinum Coin | `_mdrn_cu_plat` | 215 `bank_coin` | `it_bnkcoin` | 4 | 1 |
| Silver Coin | `_mdrn_cu_silver` | 215 `bank_coin` | `it_bnkcoin` | 1 | 1 |

### Modern General > Professional Equipment (ID 109, 27)

| Blueprint | ResRef | Base item | Item class | Model parts | Properties |
|---|---|---|---|---|---:|
| Acid Trap Kit | `_mdrn_ot_acid1` | 24 `miscsmall` | `it_smlmisc` | 132 | 2 |
| Chemical Kit | `_mdrn_ot_chemkit` | 29 `miscmedium` | `it_midmisc` | 185 | 1 |
| Demolitions Kit | `_mdrn_ot_demo` | 24 `miscsmall` | `it_smlmisc` | 94 | 1 |
| Disguise Kit | `_mdrn_it_disgkit` | 29 `miscmedium` | `it_midmisc` | 177 | 1 |
| Electrical Toolkit (basic) | `_mdrn_ot_disable` | 206 `modern_mdm` | `it_mdrnmdm` | 74 | 1 |
| Electrical Toolkit (Deluxe) | `_mdrn_ot_disab2` | 207 `modern_large` | `it_mdrnlrg` | 3 | 1 |
| Electrical Trap Kit | `_mdrn_ot_elec1` | 24 `miscsmall` | `it_smlmisc` | 117 | 2 |
| Evidence Kit (basic) | `_mdrn_it_invkit` | 206 `modern_mdm` | `it_mdrnmdm` | 3 | 1 |
| Evidence Kit (Deluxe) | `_mdrn_it_invkit2` | 207 `modern_large` | `it_mdrnlrg` | 2 | 1 |
| Explosive Trap Kit | `_mdrn_ot_expl1` | 29 `miscmedium` | `it_midmisc` | 103 | 2 |
| Fake ID | `_mdrn_it_fid` | 205 `modern_thin` | `it_mdrnthn` | 47 | 0 |
| First Aid Kit | `_mdrn_firstaid` | 206 `modern_mdm` | `it_mdrnmdm` | 39 | 2 |
| Forgery Kit | `_mdrn_it_forkit` | 206 `modern_mdm` | `it_mdrnmdm` | 55 | 0 |
| Gas Trap Kit | `_mdrn_ot_gas1` | 24 `miscsmall` | `it_smlmisc` | 134 | 2 |
| Handcuffs | `_mdrn_it_cuffs` | 206 `modern_mdm` | `it_mdrnmdm` | 78 | 0 |
| Lockpick Set | `_mdrn_ot_lock` | 24 `miscsmall` | `it_smlmisc` | 121 | 0 |
| Mechanical Toolkit (basic) | `_mdrn_ot_mechkit` | 206 `modern_mdm` | `it_mdrnmdm` | 40 | 1 |
| Mechanical Toolkit (Deluxe) | `_mdrn_ot_mechkt2` | 207 `modern_large` | `it_mdrnlrg` | 6 | 1 |
| Mechanical Trap Kit | `_mdrn_ot_mech1` | 24 `miscsmall` | `it_smlmisc` | 87 | 2 |
| Medical Kit | `_mdrn_medikit` | 29 `miscmedium` | `it_midmisc` | 186 | 1 |
| Microphone | `_mdrn_ot_mike1` | 15 `torch` | `it_torch` | 21 | 0 |
| Microphone - News | `_mdrn_ot_mike2` | 15 `torch` | `it_torch` | 22 | 0 |
| Mining Charge Kit | `_mdrn_ot_expl002` | 29 `miscmedium` | `it_midmisc` | 103 | 2 |
| Pharmacist Kit | `_mdrn_ot_pharmkt` | 29 `miscmedium` | `it_midmisc` | 201 | 1 |
| Stun Gun | `_mdrn_it_stungun` | 28 `club` | `WBlCl` | 71/101/51 | 2 |
| Surgery Kit | `_mdrn_surgkit` | 29 `miscmedium` | `it_midmisc` | 162 | 2 |
| Tripwire Trap Kit | `_mdrn_ot_trip1` | 24 `miscsmall` | `it_smlmisc` | 116 | 2 |

### Modern General > Surveillance Gear (ID 108, 10)

| Blueprint | ResRef | Base item | Item class | Model parts | Properties |
|---|---|---|---|---|---:|
| Black Box | `_mdrn_it_bbox` | 205 `modern_thin` | `it_mdrnthn` | 55 | 0 |
| Caller ID Defeater | `_mdrn_it_callid` | 205 `modern_thin` | `it_mdrnthn` | 5 | 0 |
| Cellular Interceptor | `_mdrn_ot_cint` | 206 `modern_mdm` | `it_mdrnmdm` | 28 | 1 |
| Lineman's Buttset | `_mdrn_it_trat001` | 205 `modern_thin` | `it_mdrnthn` | 11 | 0 |
| Metal Detector | `_mdrn_it_detect2` | 28 `club` | `WBlCl` | 71/101/51 | 2 |
| Metal Detector | `_mdrn_ot_count` | 15 `torch` | `it_torch` | 10 | 0 |
| Night Vision Goggles | `_mdrn_it_nvgog` | 208 `modern_necklace` | `it_mdrnnek` | 1 | 3 |
| Tap Detector | `_mdrn_it_tdet` | 205 `modern_thin` | `it_mdrnthn` | 10 | 0 |
| Telephone Line Tap | `_mdrn_it_ttap` | 205 `modern_thin` | `it_mdrnthn` | 9 | 0 |
| Telephone Line Tracer | `_mdrn_ot_ttrace` | 207 `modern_large` | `it_mdrnlrg` | 26 | 1 |

### Modern General > Survival Gear (ID 110, 17)

| Blueprint | ResRef | Base item | Item class | Model parts | Properties |
|---|---|---|---|---|---:|
| 4-Person Dome Tent | `_mdrn_it_dtent` | 34 `misclarge` | `it_talmisc` | 12 | 1 |
| 8-Person Dome Tent | `_mdrn_it_dtent2` | 34 `misclarge` | `it_talmisc` | 12 | 1 |
| Binoculars (Electro-Optical) | `_mdrn_it_ebinoc` | 208 `modern_necklace` | `it_mdrnnek` | 1 | 3 |
| Binoculars (standard) | `_mdrn_it_binocs` | 206 `modern_mdm` | `it_mdrnmdm` | 132 | 1 |
| Chemical Light Sticks | `_mdrn_it_lstick` | 205 `modern_thin` | `it_mdrnthn` | 46 | 1 |
| Climbing Gear | `_mdrn_ot_climb` | 207 `modern_large` | `it_mdrnlrg` | 1 | 1 |
| Compass | `_mdrn_ot_compass` | 24 `miscsmall` | `it_smlmisc` | 62 | 0 |
| Fire Extinguisher | `_mdrn_ot_fireext` | 79 `miscthin` | `IT_THNMISC` | 71 | 2 |
| Flash Goggles | `_mdrn_it_flgog` | 208 `modern_necklace` | `it_mdrnnek` | 4 | 1 |
| Flashlight | `_mdrn_it_torch` | 15 `torch` | `it_torch` | 24 | 1 |
| Flashlight | `_mdrn_ot_light` | 15 `torch` | `it_torch` | 13 | 1 |
| Gas Mask | `_mdrn_it_gasmask` | 17 `helmet` | `helm` | 58 | 1 |
| GPS Receiver | `_mdrn_it_gps` | 206 `modern_mdm` | `it_mdrnmdm` | 17 | 0 |
| Portable Stove | `_mdrn_it_stove` | 207 `modern_large` | `it_mdrnlrg` | 28 | 0 |
| Rope (150 ft.) | `_mdrn_ot_rope` | 29 `miscmedium` | `it_midmisc` | 190 | 1 |
| Sleeping Bag | `_mdrn_it_sbag` | 34 `misclarge` | `it_talmisc` | 12 | 1 |
| Trail Rations (10) | `_mdrn_it_trat` | 205 `modern_thin` | `it_mdrnthn` | 123 | 1 |

### Modern General > Weapon Accessories (ID 111, 3)

| Blueprint | ResRef | Base item | Item class | Model parts | Properties |
|---|---|---|---|---|---:|
| Electro-Optic Scope | `_mdrn_ot_nscope` | 79 `miscthin` | `IT_THNMISC` | 181 | 2 |
| Laser Sight | `_mdrn_ot_laser` | 79 `miscthin` | `IT_THNMISC` | 177 | 1 |
| Standard Scope | `_mdrn_ot_scope` | 79 `miscthin` | `IT_THNMISC` | 177 | 1 |

### Modern Weapons > Ammunitions > Boxes & Packs (ID 187, 30)

| Blueprint | ResRef | Base item | Item class | Model parts | Properties |
|---|---|---|---|---|---:|
| Bolts | `d20_ammo_box_100` | 202 `ammo_rounds` | `it_faammo` | 15 | 0 |
| Box of .22 Caliber Firearm Rounds | `d20_ammo_box_220` | 202 `ammo_rounds` | `it_faammo` | 3 | 0 |
| Box of .25 Caliber Firearm Rounds | `d20_ammo_box_250` | 202 `ammo_rounds` | `it_faammo` | 1 | 0 |
| Box of .303 Caliber Firearm Rounds | `d20_ammo_box_303` | 202 `ammo_rounds` | `it_faammo` | 8 | 0 |
| Box of .32 Caliber Firearm Rounds | `d20_ammo_box_320` | 202 `ammo_rounds` | `it_faammo` | 4 | 0 |
| Box of .357 Magnum Firearm Rounds | `d20_ammo_box_357` | 202 `ammo_rounds` | `it_faammo` | 9 | 0 |
| Box of .38 Caliber Firearm Rounds | `d20_ammo_box_380` | 202 `ammo_rounds` | `it_faammo` | 5 | 0 |
| Box of .44 Caliber Firearm Rounds | `d20_ammo_box_444` | 202 `ammo_rounds` | `it_faammo` | 10 | 0 |
| Box of .45 Caliber Firearm Rounds | `d20_ammo_box_450` | 202 `ammo_rounds` | `it_faammo` | 6 | 0 |
| Box of .50 Caliber Firearm Rounds | `d20_ammo_box_500` | 202 `ammo_rounds` | `it_faammo` | 0 | 0 |
| Box of 5.45mm Firearm Rounds | `d20_ammo_box_545` | 202 `ammo_rounds` | `it_faammo` | 7 | 0 |
| Box of 5.56mm Firearm Rounds | `d20_ammo_box_556` | 202 `ammo_rounds` | `it_faammo` | 11 | 0 |
| Box of 7.62mm Firearm Rounds | `d20_ammo_box_762` | 202 `ammo_rounds` | `it_faammo` | 12 | 0 |
| Box of 9mm Firearm Rounds | `d20_ammo_box_900` | 202 `ammo_rounds` | `it_faammo` | 2 | 0 |
| Box of Shotgun Shells | `d20_ammo_box_201` | 202 `ammo_rounds` | `it_faammo` | 17 | 0 |
| Box of T31 Incendiary Rockets | `d20_ammo_box_905` | 202 `ammo_rounds` | `it_faammo` | 15 | 1 |
| Case of Crossbow Bolts | `d20_bolts_001` | 202 `ammo_rounds` | `it_faammo` | 16 | 0 |
| Case of Harpoon Spears | `d20_bolts_002` | 202 `ammo_rounds` | `it_faammo` | 16 | 0 |
| Cryo Canon Pack | `d20_ammo_box_810` | 202 `ammo_rounds` | `it_faammo` | 15 | 0 |
| Cryo Power Pack | `d20_ammo_box_801` | 202 `ammo_rounds` | `it_faammo` | 13 | 0 |
| Cryo Power Pack (High Power) | `d20_ammo_box_805` | 202 `ammo_rounds` | `it_faammo` | 13 | 0 |
| Laser Power Pack | `d20_ammo_box_995` | 202 `ammo_rounds` | `it_faammo` | 14 | 0 |
| Laser Power Pack (High Power) | `d20_ammo_box_992` | 202 `ammo_rounds` | `it_faammo` | 14 | 0 |
| Plasma Canon Pack | `d20_ammo_box_815` | 202 `ammo_rounds` | `it_faammo` | 15 | 0 |
| Plasma Power Pack | `d20_ammo_box_951` | 202 `ammo_rounds` | `it_faammo` | 13 | 0 |
| Plasma Power Pack (High Power) | `d20_ammo_box_955` | 202 `ammo_rounds` | `it_faammo` | 13 | 0 |
| Quiver of Arrows | `d20_arrows_001` | 202 `ammo_rounds` | `it_faammo` | 15 | 0 |
| Sonic Power Pack | `d20_ammo_box_651` | 202 `ammo_rounds` | `it_faammo` | 13 | 0 |
| Sonic Power Pack (High Power) | `d20_ammo_box_655` | 202 `ammo_rounds` | `it_faammo` | 13 | 0 |
| Vibro Canon Pack | `d20_ammo_box_808` | 202 `ammo_rounds` | `it_faammo` | 15 | 0 |

### Modern Weapons > Ammunitions > Handgun (ID 185, 38)

| Blueprint | ResRef | Base item | Item class | Model parts | Properties |
|---|---|---|---|---|---:|
| .22 Caliber Magazine | `d20_ammo_220` | 20 `arrow` | `WAmAr` | 11/11/11 | 1 |
| .22 Caliber Magazine (dual) | `d20_ammo_221` | 27 `bullet` | `WAmBu` | 11 | 1 |
| .25 Caliber Magazine | `d20_ammo_250` | 20 `arrow` | `WAmAr` | 11/11/11 | 1 |
| .25 Caliber Magazine (dual) | `d20_ammo_251` | 27 `bullet` | `WAmBu` | 11 | 1 |
| .32 Caliber Magazine | `d20_ammo_320` | 20 `arrow` | `WAmAr` | 11/11/11 | 1 |
| .32 Caliber Magazine (dual) | `d20_ammo_321` | 27 `bullet` | `WAmBu` | 11 | 1 |
| .357 Caliber Magazine | `d20_ammo_357` | 20 `arrow` | `WAmAr` | 11/11/11 | 1 |
| .357 Caliber Magazine (dual) | `d20_ammo_358` | 27 `bullet` | `WAmBu` | 11 | 1 |
| .38 Caliber Magazine | `d20_ammo_380` | 20 `arrow` | `WAmAr` | 11/11/11 | 1 |
| .38 Caliber Magazine (dual) | `d20_ammo_381` | 27 `bullet` | `WAmBu` | 11 | 1 |
| .44 Caliber Magazine | `d20_ammo_444` | 20 `arrow` | `WAmAr` | 11/11/11 | 1 |
| .44 Caliber Magazine (dual) | `d20_ammo_446` | 27 `bullet` | `WAmBu` | 11 | 1 |
| .45 Caliber Magazine | `d20_ammo_450` | 20 `arrow` | `WAmAr` | 11/11/11 | 1 |
| .45 Caliber Magazine (dual) | `d20_ammo_452` | 27 `bullet` | `WAmBu` | 11 | 1 |
| .50 Caliber Magazine | `d20_ammo_500` | 20 `arrow` | `WAmAr` | 11/11/11 | 1 |
| .50 Caliber Magazine (dual) | `d20_ammo_502` | 27 `bullet` | `WAmBu` | 13 | 1 |
| 5.56mm Magazine of Rounds | `d20_ammo_556` | 20 `arrow` | `WAmAr` | 11/11/11 | 1 |
| 7.62mm Magazine of Rounds | `d20_ammo_762` | 20 `arrow` | `WAmAr` | 11/11/11 | 1 |
| 9mm Caliber Magazine | `d20_ammo_900` | 20 `arrow` | `WAmAr` | 11/11/11 | 1 |
| 9mm Caliber Magazine (dual) | `d20_ammo_901` | 27 `bullet` | `WAmBu` | 11 | 1 |
| Arrow | `d20_arrow_001` | 20 `arrow` | `WAmAr` | 31/31/12 | 3 |
| Loaded Cryo Pack | `d20_ammo_801` | 20 `arrow` | `WAmAr` | 11/11/11 | 2 |
| Loaded Cryo Pack (dual) | `d20_ammo_803` | 27 `bullet` | `WAmBu` | 12 | 2 |
| Loaded Cryo Pack (High Power) | `d20_ammo_805` | 20 `arrow` | `WAmAr` | 11/11/11 | 2 |
| Loaded Cryo Pack (High Power) (dual) | `d20_ammo_807` | 27 `bullet` | `WAmBu` | 12 | 2 |
| Loaded Laser Pack | `d20_ammo_995` | 20 `arrow` | `WAmAr` | 11/11/11 | 2 |
| Loaded Laser Pack (dual) | `d20_ammo_996` | 27 `bullet` | `WAmBu` | 11 | 2 |
| Loaded Laser Pack (High Power) | `d20_ammo_992` | 20 `arrow` | `WAmAr` | 11/11/11 | 2 |
| Loaded Laser Pack (High Power) (dual) | `d20_ammo_993` | 27 `bullet` | `WAmBu` | 11 | 2 |
| Loaded Plasma Pack | `d20_ammo_951` | 20 `arrow` | `WAmAr` | 11/11/11 | 2 |
| Loaded Plasma Pack (dual) | `d20_ammo_952` | 27 `bullet` | `WAmBu` | 11 | 2 |
| Loaded Plasma Pack (High Power) | `d20_ammo_955` | 20 `arrow` | `WAmAr` | 11/11/11 | 2 |
| Loaded Plasma Pack (High Power) (dual) | `d20_ammo_957` | 27 `bullet` | `WAmBu` | 11 | 2 |
| Loaded Sonic Pack | `d20_ammo_651` | 20 `arrow` | `WAmAr` | 11/11/11 | 3 |
| Loaded Sonic Pack (dual) | `d20_ammo_653` | 27 `bullet` | `WAmBu` | 11 | 3 |
| Loaded Sonic Pack (High Power) | `d20_ammo_655` | 20 `arrow` | `WAmAr` | 11/11/11 | 3 |
| Loaded Sonic Pack (High Power) (dual) | `d20_ammo_656` | 27 `bullet` | `WAmBu` | 11 | 3 |
| Magazine of Shotgun Shells | `d20_ammo_201` | 20 `arrow` | `WAmAr` | 11/11/11 | 1 |

### Modern Weapons > Ammunitions > Longarms (ID 186, 22)

| Blueprint | ResRef | Base item | Item class | Model parts | Properties |
|---|---|---|---|---|---:|
| .303 Caliber Magazine | `d20_ammo_304` | 25 `bolt` | `WAmBo` | 11/11/11 | 1 |
| .44 Caliber Magazine | `d20_ammo_445` | 25 `bolt` | `WAmBo` | 11/13/11 | 1 |
| .45 Caliber Magazine | `d20_ammo_451` | 25 `bolt` | `WAmBo` | 11/13/11 | 1 |
| .50 Caliber Magazine | `d20_ammo_501` | 25 `bolt` | `WAmBo` | 11/12/11 | 1 |
| 5.45mm Caliber Magazine | `d20_ammo_546` | 25 `bolt` | `WAmBo` | 11/12/11 | 1 |
| 5.56mm Caliber Magazine | `d20_ammo_557` | 25 `bolt` | `WAmBo` | 11/12/11 | 1 |
| 7.62mm Caliber Magazine | `d20_ammo_772` | 25 `bolt` | `WAmBo` | 11/12/11 | 1 |
| Crossbow Bolt | `d20_bolt_001` | 25 `bolt` | `WAmBo` | 14/14/14 | 3 |
| Loaded Cryo Mortar | `d20_ammo_811` | 25 `bolt` | `WAmBo` | 11/11/11 | 1 |
| Loaded Cryo Pack | `d20_ammo_802` | 25 `bolt` | `WAmBo` | 11/11/11 | 2 |
| Loaded Cryo Pack (High Power) | `d20_ammo_806` | 25 `bolt` | `WAmBo` | 11/11/11 | 2 |
| Loaded Laser Pack | `d20_ammo_994` | 25 `bolt` | `WAmBo` | 11/11/11 | 2 |
| Loaded Laser Pack (High Power) | `d20_ammo_991` | 25 `bolt` | `WAmBo` | 11/11/11 | 2 |
| Loaded Plasma Mortar | `d20_ammo_816` | 25 `bolt` | `WAmBo` | 11/11/11 | 2 |
| Loaded Plasma Pack | `d20_ammo_953` | 25 `bolt` | `WAmBo` | 11/11/11 | 2 |
| Loaded Plasma Pack (High Power) | `d20_ammo_956` | 25 `bolt` | `WAmBo` | 11/11/11 | 2 |
| Loaded Sonic Pack | `d20_ammo_652` | 25 `bolt` | `WAmBo` | 11/11/11 | 3 |
| Loaded Sonic Pack (High Power) | `d20_ammo_657` | 25 `bolt` | `WAmBo` | 11/11/11 | 3 |
| Loaded T61 Incendiary Rocket | `d20_ammo_906` | 25 `bolt` | `WAmBo` | 11/11/11 | 2 |
| Loaded Vibro Mortar | `d20_ammo_809` | 25 `bolt` | `WAmBo` | 11/11/11 | 1 |
| Magazine of Shotgun Shells | `d20_ammo_202` | 25 `bolt` | `WAmBo` | 11/12/11 | 1 |
| Slotted Bolt | `d20_ammo_101` | 25 `bolt` | `WAmBo` | 14/14/14 | 1 |

### Modern Weapons > Axes > One-Handed (ID 188, 4)

| Blueprint | ResRef | Base item | Item class | Model parts | Properties |
|---|---|---|---|---|---:|
| Battle Axe | `_mdrn_it_battlax` | 2 `battleaxe` | `WAxBt` | 11/11/11 | 1 |
| Battle Axe | `_mdrn_it_heavyax` | 108 `dwarvenwaraxe` | `WAxBt` | 11/11/11 | 1 |
| Fireaxe | `_mdrn_it_fireaxe` | 212 `fireaxe` | `WAxFa` | 11/11/11 | 2 |
| Hatchet | `_mdrn_it_hatchet` | 38 `handaxe` | `WAxHn` | 34/14/14 | 1 |

### Modern Weapons > Axes > Two-Handed (ID 189, 1)

| Blueprint | ResRef | Base item | Item class | Model parts | Properties |
|---|---|---|---|---|---:|
| Battle Axe | `_mdrn_it_greatax` | 18 `greataxe` | `WAxGr` | 11/11/11 | 1 |

### Modern Weapons > Bladed > Daggers (ID 191, 5)

| Blueprint | ResRef | Base item | Item class | Model parts | Properties |
|---|---|---|---|---|---:|
| Carving Knife | `_mdrn_it_knife02` | 22 `dagger` | `WSwDg` | 201/82/81 | 2 |
| Combat Knife | `_mdrn_it_knife05` | 22 `dagger` | `WSwDg` | 11/14/11 | 2 |
| Cut Throat Razor | `_mdrn_it_razor01` | 22 `dagger` | `WSwDg` | 31/31/31 | 3 |
| Pen Knife | `_mdrn_it_knife04` | 22 `dagger` | `WSwDg` | 201/201/201 | 2 |
| Switchblade | `_mdrn_it_knife03` | 22 `dagger` | `WSwDg` | 11/11/11 | 1 |

### Modern Weapons > Bladed > Great Swords (ID 192, 2)

| Blueprint | ResRef | Base item | Item class | Model parts | Properties |
|---|---|---|---|---|---:|
| Falchion (Sci Fi) | `_mdrn_it_scififa` | 13 `greatsword` | `WSwGs` | 71/53/71 | 1 |
| Greatsword (Sci Fi) | `_mdrn_it_scifigs` | 13 `greatsword` | `WSwGs` | 71/54/71 | 1 |

### Modern Weapons > Bladed > Longswords (ID 193, 3)

| Blueprint | ResRef | Base item | Item class | Model parts | Properties |
|---|---|---|---|---|---:|
| Longsword (Sci Fi) | `_mdrn_it_lswrd02` | 1 `longsword` | `WSwLs` | 91/102/91 | 1 |
| Longsword (Sci Fi) | `_mdrn_it_lswrd03` | 1 `longsword` | `WSwLs` | 91/101/91 | 1 |
| Sabre (Sci Fi) | `_mdrn_it_lswrd01` | 1 `longsword` | `WSwLs` | 91/107/91 | 1 |

### Modern Weapons > Bladed > Other (ID 194, 1)

| Blueprint | ResRef | Base item | Item class | Model parts | Properties |
|---|---|---|---|---|---:|
| _mdrn_it_rapier | `_mdrn_it_rapier` | 51 `rapier` | `WSwRp` | 111/111/111 | 1 |

### Modern Weapons > Bladed > Shortswords (ID 190, 3)

| Blueprint | ResRef | Base item | Item class | Model parts | Properties |
|---|---|---|---|---|---:|
| Chokuto | `_mdrn_it_chokuto` | 0 `shortsword` | `WSwSs` | 71/73/71 | 1 |
| Machete | `_mdrn_it_knife01` | 0 `shortsword` | `WSwSs` | 11/71/71 | 1 |
| Triple Bladed Dagger | `_mdrn_it_knife06` | 0 `shortsword` | `WSwSs` | 71/61/71 | 1 |

### Modern Weapons > Blunts > Clubs (ID 195, 4)

| Blueprint | ResRef | Base item | Item class | Model parts | Properties |
|---|---|---|---|---|---:|
| Bat | `d20_melee005` | 28 `club` | `WBlCl` | 71/82/51 | 1 |
| Metal Baton | `mdrn_it_batonmtl` | 28 `club` | `WBlCl` | 51/51/51 | 0 |
| Old Stool Leg | `d20_melee006` | 28 `club` | `WBlCl` | 121/121/121 | 1 |
| Police Baton | `d20_melee004` | 28 `club` | `WBlCl` | 71/81/51 | 1 |

### Modern Weapons > Blunts > Hammers (ID 197, 2)

| Blueprint | ResRef | Base item | Item class | Model parts | Properties |
|---|---|---|---|---|---:|
| Goad (Sci Fi) | `_mdrn_it_goadscf` | 5 `warhammer` | `WBlHw` | 11/21/11 | 2 |
| Warhammer (Sci Fi) | `_mdrn_it_hammrsf` | 5 `warhammer` | `WBlHw` | 11/11/11 | 1 |

### Modern Weapons > Exotic (ID 206, 4)

| Blueprint | ResRef | Base item | Item class | Model parts | Properties |
|---|---|---|---|---|---:|
| _mdrn_it_katana | `_mdrn_it_katana` | 41 `katana` | `WSwKa` | 71/81/71 | 1 |
| Fan | `_mdrn_it_fanbde` | 40 `kama` | `WSpKa` | 21/31/21 | 1 |
| Fist Blades | `_mdrn_it_fistbld` | 40 `kama` | `WSpKa` | 21/22/21 | 1 |
| Tachi | `_mdrn_it_tachi` | 3 `bastardsword` | `WSwBs` | 71/71/71 | 1 |

### Modern Weapons > Improvised Weapons (ID 205, 37)

| Blueprint | ResRef | Base item | Item class | Model parts | Properties |
|---|---|---|---|---|---:|
| Bottle | `d20_mw_bottle` | 506 `makeshiftbs` | `WMkBs` | 22/22/22 | 2 |
| Brass Knuckles | `_mdrn_it_brasskn` | 36 `gloves` | `it_glove` | 22 | 1 |
| Broken Bottle | `d20_mw_brokebot` | 507 `makeshiftss` | `WMkSs` | 11/11/11 | 2 |
| Broom | `_mdrn_it_broom1` | 505 `makeshiftbm` | `WMkBm` | 12/12/12 | 3 |
| Broom | `d20_mw_broom` | 505 `makeshiftbm` | `WMkBm` | 13/13/13 | 3 |
| Bucket (Metal) | `_mdrn_it_bucket` | 505 `makeshiftbm` | `WMkBm` | 42/11/11 | 2 |
| Bucket (Wood) | `_mdrn_it_bucket1` | 505 `makeshiftbm` | `WMkBm` | 41/11/11 | 2 |
| Cane | `_mdrn_it_cane` | 45 `magicstaff` | `WMgSt` | 181/251/253 | 3 |
| Chainsaw | `_mdrn_it_csaw` | 60 `sickle` | `WSpSc` | 14/14/14 | 3 |
| Chair | `d20_mw_chair` | 504 `makeshiftbl` | `WMkBl` | 13/13/13 | 2 |
| Cleaver | `d20_mw_cleaver` | 508 `makeshiftcs` | `WMkCs` | 11/11/11 | 1 |
| Crowbar | `d20_melee011` | 28 `club` | `WBlCl` | 122/122/122 | 2 |
| Dipper | `d20_mw_dipper` | 506 `makeshiftbs` | `WMkBs` | 62/62/62 | 2 |
| Frying Pan | `d20_melee010` | 28 `club` | `WBlCl` | 134/134/134 | 2 |
| Hay Fork | `_mdrn_it_hayfork` | 505 `makeshiftbm` | `WMkBm` | 22/11/11 | 2 |
| Hoe | `_mdrn_it_hoe` | 505 `makeshiftbm` | `WMkBm` | 23/11/11 | 2 |
| Monkey Wrench | `d20_melee007` | 28 `club` | `WBlCl` | 131/131/131 | 2 |
| Mop | `d20_melee013` | 58 `shortspear` | `WPlSs` | 181/181/181 | 3 |
| Mug | `d20_mw_mug` | 506 `makeshiftbs` | `WMkBs` | 12/12/12 | 2 |
| Old Broom | `_mdrn_it_broom2` | 505 `makeshiftbm` | `WMkBm` | 11/11/11 | 3 |
| Pan | `d20_mw_pan` | 506 `makeshiftbs` | `WMkBs` | 32/32/32 | 2 |
| Piece of 2x4 | `d20_melee001` | 28 `club` | `WBlCl` | 71/71/51 | 2 |
| Piece of 2x4 with Nails | `d20_melee002` | 28 `club` | `WBlCl` | 71/72/51 | 2 |
| Pitchfork | `_mdrn_it_pitchfk` | 505 `makeshiftbm` | `WMkBm` | 32/11/11 | 4 |
| Poker | `d20_mw_poker` | 504 `makeshiftbl` | `WMkBl` | 33/33/33 | 2 |
| Rolling Pin | `d20_mw_rollngpin` | 28 `club` | `WBlCl` | 71/111/51 | 2 |
| Rusty Chainsaw | `_mdrn_it_rcsaw` | 60 `sickle` | `WSpSc` | 14/15/14 | 3 |
| Shovel | `_mdrn_it_shovel` | 505 `makeshiftbm` | `WMkBm` | 21/11/11 | 2 |
| Shovel | `_mdrn_it_shovel1` | 505 `makeshiftbm` | `WMkBm` | 31/11/11 | 2 |
| Skillet | `d20_mw_skillet` | 506 `makeshiftbs` | `WMkBs` | 42/42/42 | 2 |
| Snooker Cue | `d20_melee003` | 28 `club` | `WBlCl` | 71/73/51 | 2 |
| Spanner | `d20_melee008` | 28 `club` | `WBlCl` | 132/132/132 | 2 |
| Spatula | `d20_mw_spatula` | 506 `makeshiftbs` | `WMkBs` | 52/52/52 | 2 |
| Stick of Wood | `_mdrn_ot_stick` | 28 `club` | `WBlCl` | 51/52/51 | 2 |
| Tree Branch | `d20_mw_branch` | 504 `makeshiftbl` | `WMkBl` | 23/23/23 | 2 |
| Walking Cane | `d20_melee012` | 28 `club` | `WBlCl` | 123/123/123 | 2 |
| Wooden Sword | `d20_melee009` | 28 `club` | `WBlCl` | 133/133/133 | 3 |

### Modern Weapons > Polearms (ID 208, 8)

| Blueprint | ResRef | Base item | Item class | Model parts | Properties |
|---|---|---|---|---|---:|
| Billhook | `_mdrn_it_billhok` | 10 `halberd` | `WPlHb` | 11/71/11 | 1 |
| Crozier (40k) | `_mdrn_it_croz40k` | 58 `shortspear` | `WPlSs` | 32/22/51 | 1 |
| Halberd (Sci Fi) | `_mdrn_it_halbdsf` | 10 `halberd` | `WPlHb` | 11/11/11 | 1 |
| Harpoon | `_mdrn_it_harpnsp` | 58 `shortspear` | `WPlSs` | 141/143/141 | 1 |
| Metal Stave | `_mdrn_it_stavem` | 50 `quarterstaff` | `WDbQs` | 11/11/11 | 1 |
| Slave Goad | `_mdrn_it_goadslv` | 58 `shortspear` | `WPlSs` | 11/71/11 | 1 |
| Spear (Sci Fi) | `_mdrn_it_spearsf` | 58 `shortspear` | `WPlSs` | 11/11/11 | 1 |
| Weighted Stave | `_mdrn_it_scifidm` | 32 `diremace` | `WDbMa` | 11/11/11 | 1 |

### Modern Weapons > Power Blades (ID 207, 4)

| Blueprint | ResRef | Base item | Item class | Model parts | Properties |
|---|---|---|---|---|---:|
| Chainsword | `_mdrn_it_cswrd01` | 1 `longsword` | `WSwLs` | 91/105/91 | 2 |
| Chainsword | `_mdrn_it_cswrd02` | 1 `longsword` | `WSwLs` | 91/106/91 | 2 |
| Double Lightsaber | `_mdrn_it_lsabr02` | 12 `twobladedlightsaber` | `WDbLsbr` | 14/11/23 | 1 |
| Lightsaber | `_mdrn_it_lsabr01` | 42 `lightsaber` | `WSwGlsbr` | 11/11/12 | 1 |

### Modern Weapons > Ranged Weapons > Dual Handgun (ID 203, 30)

| Blueprint | ResRef | Base item | Item class | Model parts | Properties |
|---|---|---|---|---|---:|
| Baby Browning .25 (dual-wield) | `_mdrn_it_bbydual` | 61 `d20_smallArms_d6` | `WBwSh` | 11/63/11 | 2 |
| Baby Browning .25 (off-hand) | `_mdrn_it_bbyoff` | 213 `d20_smallArms_d6` | `WBwSh` | 11/63/11 | 0 |
| Ballistic Blaster Pistol (dual-wield) | `_mdrn_it_bbpdual` | 61 `d20_smallArms_d6` | `WBwSh` | 11/231/11 | 4 |
| Ballistic Blaster Pistol (off-hand) | `_mdrn_it_bbpoff` | 213 `d20_smallArms_d6` | `WBwSh` | 11/231/11 | 0 |
| Beretta 92FS .22 (dual-wield) | `_mdrn_it_92dual` | 61 `d20_smallArms_d6` | `WBwSh` | 11/53/11 | 3 |
| Beretta 92FS .22 (off-hand) | `_mdrn_it_92off` | 213 `d20_smallArms_d6` | `WBwSh` | 11/53/11 | 0 |
| Colt .38 Detective (dual-wield) | `_mdrn_it_c6dual` | 61 `d20_smallArms_d6` | `WBwSh` | 11/33/11 | 3 |
| Colt .38 Detective (off-hand) | `_mdrn_it_c6off` | 213 `d20_smallArms_d6` | `WBwSh` | 11/33/11 | 0 |
| Colt 1911 .45 (dual-wield) | `_mdrn_it_c45dual` | 61 `d20_smallArms_d6` | `WBwSh` | 11/171/11 | 5 |
| Colt 1911 .45 (off-hand) | `_mdrn_it_c45off` | 213 `d20_smallArms_d6` | `WBwSh` | 11/171/11 | 0 |
| Colt Python .357 Revolver (dual-wield) | `_mdrn_it_357dual` | 61 `d20_smallArms_d6` | `WBwSh` | 11/172/11 | 4 |
| Colt Python .357 Revolver (off-hand) | `_mdrn_it_357off` | 213 `d20_smallArms_d6` | `WBwSh` | 11/172/11 | 0 |
| Cryonic Pistol (dual-wield) | `_mdrn_it_crydual` | 61 `d20_smallArms_d6` | `WBwSh` | 11/91/11 | 4 |
| Cryonic Pistol (off-hand) | `_mdrn_it_cryoff` | 213 `d20_smallArms_d6` | `WBwSh` | 11/91/11 | 0 |
| Desert Eagle 0.50AE (dual-wield) | `_mdrn_it_eagdual` | 61 `d20_smallArms_d6` | `WBwSh` | 11/73/11 | 4 |
| Desert Eagle 0.50AE (off-hand) | `_mdrn_it_eagoff` | 213 `d20_smallArms_d6` | `WBwSh` | 11/73/11 | 0 |
| Glock 17 9mm (dual-wield) | `_mdrn_it_glkdual` | 61 `d20_smallArms_d6` | `WBwSh` | 11/51/11 | 4 |
| Glock 17 9mm (off-hand) | `_mdrn_it_glkoff` | 213 `d20_smallArms_d6` | `WBwSh` | 11/51/11 | 0 |
| H&K USP 9mm (dual-wield) | `_mdrn_it_hkudual` | 61 `d20_smallArms_d6` | `WBwSh` | 11/151/11 | 3 |
| H&K USP 9mm (off-hand) | `_mdrn_it_hkuoff` | 213 `d20_smallArms_d6` | `WBwSh` | 11/151/11 | 0 |
| Laser Pistol (dual-wield) | `_mdrn_it_lasdual` | 61 `d20_smallArms_d6` | `WBwSh` | 11/113/11 | 3 |
| Laser Pistol (off-hand) | `_mdrn_it_lasoff` | 213 `d20_smallArms_d6` | `WBwSh` | 11/113/11 | 0 |
| Plasma Pistol (dual-wield) | `_mdrn_it_pldual` | 61 `d20_smallArms_d6` | `WBwSh` | 11/101/11 | 3 |
| Plasma Pistol (off-hand) | `_mdrn_it_ploff` | 213 `d20_smallArms_d6` | `WBwSh` | 11/101/11 | 0 |
| S&W M29 .44 Magnum Revolver (dual-wield) | `_mdrn_it_44dual` | 61 `d20_smallArms_d6` | `WBwSh` | 11/31/11 | 4 |
| S&W M29 .44 Magnum Revolver (off-hand) | `_mdrn_it_44off` | 213 `d20_smallArms_d6` | `WBwSh` | 11/31/11 | 0 |
| Sonic Blaster Pistol (dual-wield) | `_mdrn_it_blsdual` | 61 `d20_smallArms_d6` | `WBwSh` | 11/103/11 | 3 |
| Sonic Blaster Pistol (off-hand) | `_mdrn_it_blsoff` | 213 `d20_smallArms_d6` | `WBwSh` | 11/103/11 | 0 |
| Webley .38 British Bulldog (dual-wield) | `d20_smarms013dl` | 61 `d20_smallArms_d6` | `WBwSh` | 11/182/11 | 3 |
| Webley .38 British Bulldog (off-hand) | `d20_smarms013off` | 213 `d20_smallArms_d6` | `WBwSh` | 11/182/11 | 0 |

### Modern Weapons > Ranged Weapons > Handgun (ID 202, 17)

| Blueprint | ResRef | Base item | Item class | Model parts | Properties |
|---|---|---|---|---|---:|
| Baby Browning .25 | `d20_smarms002` | 11 `d20_handguns_d6` | `WBwSh` | 11/63/11 | 2 |
| Ballistic Blaster Pistol | `_mdrn_it_bblastr` | 11 `d20_handguns_d6` | `WBwSh` | 11/231/11 | 4 |
| Beretta 92FS .22 | `d20_smarms001` | 11 `d20_handguns_d6` | `WBwSh` | 11/53/11 | 3 |
| Colt .38 Detective Revolver | `d20_smarms004` | 11 `d20_handguns_d6` | `WBwSh` | 11/33/11 | 3 |
| Colt 1911 .45 | `d20_smarms007` | 11 `d20_handguns_d6` | `WBwSh` | 11/171/11 | 4 |
| Colt Python .357 Revolver | `d20_smarms005` | 11 `d20_handguns_d6` | `WBwSh` | 11/172/11 | 4 |
| Cryonic Pistol | `_mdrn_it_cryop` | 11 `d20_handguns_d6` | `WBwSh` | 11/91/11 | 3 |
| Desert Eagle 0.50AE | `_mdrn_it_eagle` | 11 `d20_handguns_d6` | `WBwSh` | 11/73/11 | 4 |
| Glock 17 9mm | `d20_smarms008` | 11 `d20_handguns_d6` | `WBwSh` | 11/51/11 | 4 |
| H&K USP 9mm | `d20_smarms003` | 11 `d20_handguns_d6` | `WBwSh` | 11/151/11 | 3 |
| Laser Pistol | `d20_smarms022` | 11 `d20_handguns_d6` | `WBwSh` | 11/113/11 | 3 |
| Plasma Pistol | `_mdrn_it_plpisto` | 11 `d20_handguns_d6` | `WBwSh` | 11/214/11 | 3 |
| S&W M29 .44 Magnum Revolver | `_mdrn_it_44mag` | 11 `d20_handguns_d6` | `WBwSh` | 11/31/11 | 4 |
| Sawed Off Shotgun | `_mdrn_it_sawnoff` | 11 `d20_handguns_d6` | `WBwSh` | 11/41/11 | 4 |
| Sonic Blaster Pistol | `_mdrn_it_blaster` | 11 `d20_handguns_d6` | `WBwSh` | 11/103/11 | 3 |
| Webley .38 British Bulldog | `d20_smarms013` | 11 `d20_handguns_d6` | `WBwSh` | 11/182/11 | 3 |
| Wheel Lock Pistol | `_mdrn_it_whllock` | 11 `d20_handguns_d6` | `WBwSh` | 251/247/11 | 4 |

### Modern Weapons > Ranged Weapons > Heavy (ID 200, 15)

| Blueprint | ResRef | Base item | Item class | Model parts | Properties |
|---|---|---|---|---|---:|
| Crossbow - Repeating | `_mdrn_it_crossbr` | 6 `d20_heavyweap_d10` | `WBwXh` | 11/34/11 | 4 |
| Cryonic Canon | `_mdrn_it_crycann` | 6 `d20_heavyweap_d10` | `WBwXh` | 11/12/11 | 4 |
| Cryonic Pulse Rifle | `_mdrn_it_cryrifl` | 6 `d20_heavyweap_d10` | `WBwXh` | 11/171/11 | 3 |
| Harpoon Launcher | `_mdrn_it_harpoon` | 6 `d20_heavyweap_d10` | `WBwXh` | 11/64/15 | 4 |
| Laser Pulse Rifle | `d20_hvarms002` | 6 `d20_heavyweap_d10` | `WBwXh` | 11/81/11 | 3 |
| M1A1 "Bazooka" Rocket Launcher | `_mdrn_it_m1bazka` | 6 `d20_heavyweap_d10` | `WBwXh` | 11/121/11 | 4 |
| M24 7.62mm Sniper Rifle | `d20_hvarms005` | 6 `d20_heavyweap_d10` | `WBwXh` | 11/21/11 | 5 |
| M72A3 LAW (Light Anti Tank Weapon) | `_mdrn_ot_boom` | 15 `torch` | `it_torch` | 20 | 2 |
| Mauser m/96 7.62mm Sniper Rifle | `d20_hvarms004` | 6 `d20_heavyweap_d10` | `WBwXh` | 11/72/11 | 4 |
| Minigun .50 mm | `d20_hvarms001` | 6 `d20_heavyweap_d10` | `WBwXh` | 11/14/11 | 5 |
| Negev 5.56mm Light Machine Gun | `d20_hvarms006` | 6 `d20_heavyweap_d10` | `WBwXh` | 11/74/11 | 5 |
| Plasma Canon | `_mdrn_it_placann` | 6 `d20_heavyweap_d10` | `WBwXh` | 11/31/11 | 4 |
| Plasma Pulse Rifle | `d20_hvarms003` | 6 `d20_heavyweap_d10` | `WBwXh` | 11/44/11 | 3 |
| Sonic Pulse Rifle | `d20_hvarms007` | 6 `d20_heavyweap_d10` | `WBwXh` | 11/151/11 | 3 |
| Vibro Canon | `_mdrn_it_vibcann` | 6 `d20_heavyweap_d10` | `WBwXh` | 11/23/11 | 4 |

### Modern Weapons > Ranged Weapons > Longarms (ID 204, 15)

| Blueprint | ResRef | Base item | Item class | Model parts | Properties |
|---|---|---|---|---|---:|
| AKM/AK 47 7.62mm Assault Rifle | `_mdrn_it_ak47` | 7 `d20_longarms_d8` | `WBwXl` | 11/51/11 | 4 |
| AKS-74U 5.45mm Assault Rifle | `_mdrn_it_ak74u` | 7 `d20_longarms_d8` | `WBwXl` | 11/241/11 | 4 |
| Crossbow | `_mdrn_it_crossbw` | 7 `d20_longarms_d8` | `WBwXl` | 11/214/44 | 4 |
| Cryonic Rifle | `_mdrn_it_crrifle` | 7 `d20_longarms_d8` | `WBwXl` | 11/101/11 | 4 |
| Enfield .303 Rifle | `d20_hvarms_004` | 7 `d20_longarms_d8` | `WBwXl` | 11/11/11 | 3 |
| FN2000 5.56mm Assault Rifle | `_mdrn_it_fn2000` | 7 `d20_longarms_d8` | `WBwXl` | 11/73/11 | 5 |
| HK G36 5.56mm Assault Rifle | `_mdrn_it_g36` | 7 `d20_longarms_d8` | `WBwXl` | 11/251/11 | 4 |
| Ithaca 37 Shotgun | `_mdrn_it_ithac37` | 7 `d20_longarms_d8` | `WBwXl` | 11/43/11 | 5 |
| Laser Rifle | `_mdrn_it_lrifle` | 7 `d20_longarms_d8` | `WBwXl` | 11/151/11 | 4 |
| M4 Carbine 5.56mm Assault Rifle | `_mdrn_it_m4` | 7 `d20_longarms_d8` | `WBwXl` | 11/21/11 | 3 |
| Plasma Rifle | `_mdrn_it_prifle` | 7 `d20_longarms_d8` | `WBwXl` | 11/252/11 | 4 |
| Sonic Rifle | `_mdrn_it_scrifle` | 7 `d20_longarms_d8` | `WBwXl` | 11/142/11 | 4 |
| SPAS 12-gauge Shotgun | `_mdrn_it_spas12` | 7 `d20_longarms_d8` | `WBwXl` | 11/62/11 | 5 |
| Thompson 0.45 Machine Gun | `_mdrn_it_tom` | 7 `d20_longarms_d8` | `WBwXl` | 11/12/11 | 4 |
| Winchester 94 .44 Hunting Rifle | `_mdrn_it_win94` | 7 `d20_longarms_d8` | `WBwXl` | 11/82/11 | 3 |

### Modern Weapons > Ranged Weapons > SMGs (ID 201, 8)

| Blueprint | ResRef | Base item | Item class | Model parts | Properties |
|---|---|---|---|---|---:|
| Cryonic Pulse Pistol | `_mdrn_it_cppistl` | 8 `d20_smallarms_d8` | `WBwLn` | 71/101/11 | 3 |
| H&K MP5 9mm Submachine Gun | `_mdrn_it_hkmp5k` | 8 `d20_smallarms_d8` | `WBwLn` | 71/61/11 | 4 |
| Laser Pulse Pistol | `_mdrn_it_lrifleh` | 8 `d20_smallarms_d8` | `WBwLn` | 71/91/11 | 3 |
| Mac Ingram M10 .45 Machine Pistol | `d20_macingramm10` | 8 `d20_smallarms_d8` | `WBwLn` | 71/21/11 | 5 |
| Plasma Pulse Pistol | `_mdrn_it_pppistl` | 8 `d20_smallarms_d8` | `WBwLn` | 71/111/11 | 3 |
| Skorpion Vz61 .32 caliber Machine Pistol | `d20_smarms006` | 8 `d20_smallarms_d8` | `WBwLn` | 71/11/11 | 3 |
| Sonic Pulse Pistol | `_mdrn_it_sppistl` | 8 `d20_smallarms_d8` | `WBwLn` | 71/81/11 | 3 |
| Uzi 9mm Submachine Gun | `_mdrn_it_uzi9mm` | 8 `d20_smallarms_d8` | `WBwLn` | 71/13/11 | 4 |

### Modern Weapons > Throwing (ID 209, 9)

| Blueprint | ResRef | Base item | Item class | Model parts | Properties |
|---|---|---|---|---|---:|
| Flask of Acid | `_mdrn_it_acidb` | 81 `grenade` | `it_x1_gren` | 8 | 1 |
| Flask of Hydroflouric Acid | `_mdrn_it_acidbmb` | 81 `grenade` | `it_x1_gren` | 13 | 1 |
| Fragmentation Grenade | `_mdrn_ot_frag` | 81 `grenade` | `it_x1_gren` | 12 | 1 |
| Knockout Grenade | `_mdrn_ot_knock` | 81 `grenade` | `it_x1_gren` | 11 | 1 |
| Molotov Cocktail | `_mdrn_ot_molotov` | 81 `grenade` | `it_x1_gren` | 7 | 1 |
| Smoke Grenade | `_mdrn_ot_smoke` | 81 `grenade` | `it_x1_gren` | 10 | 1 |
| Stun Grenade | `_mdrn_ot_stun` | 81 `grenade` | `it_x1_gren` | 21 | 1 |
| Tear Gas Grenade | `_mdrn_ot_tear` | 81 `grenade` | `it_x1_gren` | 14 | 1 |
| White Phosphorus Grenade | `_mdrn_ot_phosp` | 81 `grenade` | `it_x1_gren` | 22 | 1 |

### Tutorial (ID 53, 1)

| Blueprint | ResRef | Base item | Item class | Model parts | Properties |
|---|---|---|---|---|---:|
| DMFI Music Wand | `dmfi_music` | 24 `miscsmall` | `it_smlmisc` | 223 | 1 |

### Weapons > Ranged Weapons > Longbows (ID 44, 3)

| Blueprint | ResRef | Base item | Item class | Model parts | Properties |
|---|---|---|---|---|---:|
| Daikyu, Modern | `_mdrn_it_dai` | 8 `d20_smallarms_d8` | `WBwLn` | 253/253/253 | 3 |
| Longbow | `d20_longbow_001` | 8 `d20_smallarms_d8` | `WBwLn` | 14/113/12 | 3 |
| Longbow, Ornate, Modern | `_mdrn_it_ornbow` | 8 `d20_smallarms_d8` | `WBwLn` | 241/241/241 | 3 |

### Weapons > Ranged Weapons > Shortbow (ID 45, 1)

| Blueprint | ResRef | Base item | Item class | Model parts | Properties |
|---|---|---|---|---|---:|
| Shortbow | `d20_shortbow_001` | 11 `d20_handguns_d6` | `WBwSh` | 34/144/11 | 2 |

## Match Tier subset from the SR3 candidate workbook

Source: `sr3-blueprint-candidates.xlsx`; SHA-256 `06FFCF13C39C04B57F58E45EC75FE36D7805DBFC722B0EA97656A0492FA6F5FE`; classification range `Candidates!A1:T97`.

The workbook classifies **93 of 669** MDRN item blueprints as SR3 catalog candidates. Every candidate joins uniquely to this report by Blueprint ResRef and agrees on the UTI base-item row.

| Match Tier | Blueprints |
|---|---:|
| Exact identity | 12 |
| Visual stand-in | 81 |
| **Total** | **93** |

This is an appearance-only shortlist. The workbook explicitly does not transfer costs, properties, descriptions, scripts, combat behavior, models, icons, or 2DA definitions. Its dependency and rights statements were written without the item HAK analysis and remain advisory; this repository's dependency closure and provenance records control landing decisions.

### Exact identity (12)

Friendly-category distribution: Modern General: 4; Modern Weapons: 8.

| Rank | Blueprint | ResRef | Friendly MDRN category | Catalog identity | Catalog category | Source tier | Confidence |
|---:|---|---|---|---|---|---|---|
| 1 | Arrow | `d20_arrow_001` | Modern Weapons > Ammunitions > Handgun | SRG-00113 — Arrows | Weapons > Projectile weapons > Bows | `official-SR3-line` | High |
| 2 | Binoculars (standard) | `_mdrn_it_binocs` | Modern General > Survival Gear | SRG-03645 — Binoculars | Surveillance and security > Vision enhancers/Flashlights | `official-SR3-line` | High |
| 3 | Chainsaw | `_mdrn_it_csaw` | Modern Weapons > Improvised Weapons | SRG-00102 — Chainsaw(Chainsaw) | Weapons > Melee weapons > Other | `official-SR3-line` | High |
| 4 | Bolts | `d20_ammo_box_100` | Modern Weapons > Ammunitions > Boxes & Packs | SRG-00150 — Bolts | Weapons > Projectile weapons > Crossbows | `official-SR3-line` | High |
| 5 | Harpoon | `_mdrn_it_harpnsp` | Modern Weapons > Polearms | SRG-00058 — Harpoon | Weapons > Melee weapons > Clubs/Pole Arms/Staffs | `official-SR3-line` | High |
| 6 | Lockpick Set | `_mdrn_ot_lock` | Modern General > Professional Equipment | SRG-04347 — Lockpick Set | Surveillance and security > Other security-related equipment | `official-SR3-line` | High |
| 7 | Rope (150 ft.) | `_mdrn_ot_rope` | Modern General > Survival Gear | SRG-04445 — Rope (50 meters) | Survival gear > Climbing Gear | `official-SR3-line` | High |
| 8 | Sleeping Bag | `_mdrn_it_sbag` | Modern General > Survival Gear | SRG-04399 — Sleeping Bag | Survival gear > General | `official-SR3-line` | High |
| 9 | Smoke Grenade | `_mdrn_ot_smoke` | Modern Weapons > Throwing | SRG-02435 — Smoke Grenade (A) | Explosives > Grenades > Aerodynamic Grenades | `official-SR3-line` | High |
| 10 | White Phosphorus Grenade | `_mdrn_ot_phosp` | Modern Weapons > Throwing | SRG-02441 — White Phosphorus Grenade (A) | Explosives > Grenades > Aerodynamic Grenades | `official-SR3-line` | High |
| 11 | Brass Knuckles | `_mdrn_it_brasskn` | Modern Weapons > Improvised Weapons | SRG-00101 — Brass Knuckles | Weapons > Melee weapons > Other | `official-earlier-edition` | High |
| 12 | Switchblade | `_mdrn_it_knife03` | Modern Weapons > Bladed > Daggers | SRG-00037 — Switchblade | Weapons > Melee weapons > Edged weapons | `fan-or-conversion` | High |

### Visual stand-in (81)

Friendly-category distribution: Modern Clothing: 5; Modern General: 20; Modern Weapons: 56.

| Rank | Blueprint | ResRef | Friendly MDRN category | Catalog identity | Catalog category | Source tier | Confidence |
|---:|---|---|---|---|---|---|---|
| 13 | AKM/AK 47 7.62mm Assault Rifle | `_mdrn_it_ak47` | Modern Weapons > Ranged Weapons > Longarms | SRG-00948 — AK-97 | Weapons > Firearms > Assault rifles | `official-SR3-line` | High |
| 14 | AKS-74U 5.45mm Assault Rifle | `_mdrn_it_ak74u` | Modern Weapons > Ranged Weapons > Longarms | SRG-00843 — AK-97 SMG/Carbine | Weapons > Firearms > Submachine guns | `official-SR3-line` | High |
| 15 | Digital Audio Recorder | `_mdrn_it_audrec` | Modern General > Computers and Consumer Electronics | SRG-04377 — Audio Recorder [1] | Surveillance and security > Professional Audio Recorders | `official-SR3-line` | High |
| 16 | Police Baton | `d20_melee004` | Modern Weapons > Blunts > Clubs | SRG-00057 — Extendable Baton | Weapons > Melee weapons > Clubs/Pole Arms/Staffs | `official-SR3-line` | High |
| 17 | Concealable Vest | `_mdrn_it_cvest` | Modern Clothing > Medium | SRG-02629 — Armor Vest | Clothing and armor > Armor clothing | `official-SR3-line` | High |
| 18 | Stun Grenade | `_mdrn_ot_stun` | Modern Weapons > Throwing | SRG-02420 — IPE Concussion Grenade (A) | Explosives > Grenades > Aerodynamic Grenades | `official-SR3-line` | High |
| 19 | Electrical Toolkit (Deluxe) | `_mdrn_ot_disab2` | Modern General > Professional Equipment | SRG-04516 — Electronic ToolKit | Working Gear > Kit (B/R) | `official-SR3-line` | High |
| 20 | Electrical Toolkit (basic) | `_mdrn_ot_disable` | Modern General > Professional Equipment | SRG-04516 — Electronic ToolKit | Working Gear > Kit (B/R) | `official-SR3-line` | High |
| 21 | Fragmentation Grenade | `_mdrn_ot_frag` | Modern Weapons > Throwing | SRG-02422 — IPE Defensive HE Grenade (A) | Explosives > Grenades > Aerodynamic Grenades | `official-SR3-line` | High |
| 22 | HK G36 5.56mm Assault Rifle | `_mdrn_it_g36` | Modern Weapons > Ranged Weapons > Longarms | SRG-01454 — HK G38 Assault | Weapons > Firearms > Special weapons > Multi Weapon Systems > Heckler & Koch G38 System | `official-SR3-line` | High |
| 23 | Tear Gas Grenade | `_mdrn_ot_tear` | Modern Weapons > Throwing | SRG-02414 — Gas Grenade (A) | Explosives > Grenades > Aerodynamic Grenades | `official-SR3-line` | High |
| 24 | Scientific Geiger Counter | `_mdrn_ot_geiger` | Modern General > Computers and Consumer Electronics | SRG-04414 — Geiger Counter | Survival gear > Biohazard Equipment | `official-SR3-line` | High |
| 25 | GPS Receiver | `_mdrn_it_gps` | Modern General > Survival Gear | SRG-04259 — Nav-Dat GPS | Surveillance and security > Global positioning system | `official-SR3-line` | High |
| 26 | Mac Ingram M10 .45 Machine Pistol | `d20_macingramm10` | Modern Weapons > Ranged Weapons > SMGs | SRG-00875 — Ingram Smartgun Mod. 20t | Weapons > Firearms > Submachine guns | `official-SR3-line` | High |
| 27 | Laser Sight | `_mdrn_ot_laser` | Modern General > Weapon Accessories | SRG-01619 — Laser Sight | Firearm and weapon accessories > Imaging Accessories > Laser Sights | `official-SR3-line` | High |
| 28 | First Aid Kit | `_mdrn_firstaid` | Modern General > Professional Equipment | SRG-04948 — Basic Medkit | Biotech > Medical equipment > Medkits | `official-SR3-line` | High |
| 29 | Medical Kit | `_mdrn_medikit` | Modern General > Professional Equipment | SRG-04948 — Basic Medkit | Biotech > Medical equipment > Medkits | `official-SR3-line` | High |
| 30 | Minigun .50 mm | `d20_hvarms001` | Modern Weapons > Ranged Weapons > Heavy | SRG-01347 — Vindicator Minigun | Weapons > Firearms > Heavy weapons > Assault Cannons and Miniguns | `official-SR3-line` | High |
| 31 | Flashlight | `_mdrn_it_torch` | Modern General > Survival Gear | SRG-03650 — Flashlight, pocket | Surveillance and security > Vision enhancers/Flashlights | `official-SR3-line` | High |
| 32 | Ballistic Shield (Metal) | `_mdrn_swatshld1` | Modern Clothing > Shields > Tower Shields | SRG-02614 — Riot Shield, Large | Clothing and armor > Clothing and Riot Shields | `official-SR3-line` | High |
| 33 | Riot (SWAT) Shield (Polycarbonate) | `_mdrn_swatshld2` | Modern Clothing > Shields > Tower Shields | SRG-02614 — Riot Shield, Large | Clothing and armor > Clothing and Riot Shields | `official-SR3-line` | High |
| 34 | Sawed Off Shotgun | `_mdrn_it_sawnoff` | Modern Weapons > Ranged Weapons > Handgun | SRG-01104 — Remington 990 Sawed-Off | Weapons > Firearms > Shotguns | `official-SR3-line` | High |
| 35 | SPAS 12-gauge Shotgun | `_mdrn_it_spas12` | Modern Weapons > Ranged Weapons > Longarms | SRG-01085 — Franchi SPAS-22 | Weapons > Firearms > Shotguns | `official-SR3-line` | High |
| 36 | Undercover Vest | `_mdrn_it_uvest` | Modern Clothing > Light | SRG-02639 — Secure Vest | Clothing and armor > Armor clothing | `official-SR3-line` | High |
| 37 | Uzi 9mm Submachine Gun | `_mdrn_it_uzi9mm` | Modern Weapons > Ranged Weapons > SMGs | SRG-00891 — Uzi III | Weapons > Firearms > Submachine guns | `official-SR3-line` | High |
| 38 | Camo Pants (Green) & Green Jacket | `_mdrn_it_camjack` | Modern Clothing > Clothing | SRG-02758 — Camo Jacket (Woods) | Clothing and armor > Camouflage | `official-SR3-line` | High |
| 39 | Fireaxe | `_mdrn_it_fireaxe` | Modern Weapons > Axes > One-Handed | SRG-00011 — Combat Axe | Weapons > Melee weapons > Edged weapons | `official-SR3-line` | Medium |
| 40 | Hatchet | `_mdrn_it_hatchet` | Modern Weapons > Axes > One-Handed | SRG-00011 — Combat Axe | Weapons > Melee weapons > Edged weapons | `official-SR3-line` | Medium |
| 41 | Beretta 92FS .22 (dual-wield) | `_mdrn_it_92dual` | Modern Weapons > Ranged Weapons > Dual Handgun | SRG-00210 — Beretta Model 101T | Weapons > Firearms > Pistols > Light | `official-SR3-line` | Medium |
| 42 | Beretta 92FS .22 (off-hand) | `_mdrn_it_92off` | Modern Weapons > Ranged Weapons > Dual Handgun | SRG-00210 — Beretta Model 101T | Weapons > Firearms > Pistols > Light | `official-SR3-line` | Medium |
| 43 | Beretta 92FS .22 | `d20_smarms001` | Modern Weapons > Ranged Weapons > Handgun | SRG-00210 — Beretta Model 101T | Weapons > Firearms > Pistols > Light | `official-SR3-line` | Medium |
| 44 | Binoculars (Electro-Optical) | `_mdrn_it_ebinoc` | Modern General > Survival Gear | SRG-03645 — Binoculars | Surveillance and security > Vision enhancers/Flashlights | `official-SR3-line` | Medium |
| 45 | FN2000 5.56mm Assault Rifle | `_mdrn_it_fn2000` | Modern Weapons > Ranged Weapons > Longarms | SRG-00959 — FN HAR | Weapons > Firearms > Assault rifles | `official-SR3-line` | Medium |
| 46 | M4 Carbine 5.56mm Assault Rifle | `_mdrn_it_m4` | Modern Weapons > Ranged Weapons > Longarms | SRG-00953 — Colt M-23 | Weapons > Firearms > Assault rifles | `official-SR3-line` | Medium |
| 47 | Colt .38 Detective (dual-wield) | `_mdrn_it_c6dual` | Modern Weapons > Ranged Weapons > Dual Handgun | SRG-00214 — Colt Asp | Weapons > Firearms > Pistols > Light | `official-SR3-line` | Medium |
| 48 | Colt .38 Detective (off-hand) | `_mdrn_it_c6off` | Modern Weapons > Ranged Weapons > Dual Handgun | SRG-00214 — Colt Asp | Weapons > Firearms > Pistols > Light | `official-SR3-line` | Medium |
| 49 | Colt .38 Detective Revolver | `d20_smarms004` | Modern Weapons > Ranged Weapons > Handgun | SRG-00214 — Colt Asp | Weapons > Firearms > Pistols > Light | `official-SR3-line` | Medium |
| 50 | H&K MP5 9mm Submachine Gun | `_mdrn_it_hkmp5k` | Modern Weapons > Ranged Weapons > SMGs | SRG-00875 — Ingram Smartgun Mod. 20t | Weapons > Firearms > Submachine guns | `official-SR3-line` | Medium |
| 51 | Electro-Optic Scope | `_mdrn_ot_nscope` | Modern General > Weapon Accessories | SRG-01622 — Imaging Scope: Low-Light | Firearm and weapon accessories > Imaging Accessories > Scopes and Sights | `official-SR3-line` | Medium |
| 52 | Colt 1911 .45 (dual-wield) | `_mdrn_it_c45dual` | Modern Weapons > Ranged Weapons > Dual Handgun | SRG-00282 — Colt Manhunter | Weapons > Firearms > Pistols > Heavy pistols | `official-SR3-line` | Medium |
| 53 | Colt 1911 .45 (off-hand) | `_mdrn_it_c45off` | Modern Weapons > Ranged Weapons > Dual Handgun | SRG-00282 — Colt Manhunter | Weapons > Firearms > Pistols > Heavy pistols | `official-SR3-line` | Medium |
| 54 | Colt 1911 .45 | `d20_smarms007` | Modern Weapons > Ranged Weapons > Handgun | SRG-00282 — Colt Manhunter | Weapons > Firearms > Pistols > Heavy pistols | `official-SR3-line` | Medium |
| 55 | Desert Eagle 0.50AE (dual-wield) | `_mdrn_it_eagdual` | Modern Weapons > Ranged Weapons > Dual Handgun | SRG-00261 — Ares Predator III | Weapons > Firearms > Pistols > Heavy pistols | `official-SR3-line` | Medium |
| 56 | Desert Eagle 0.50AE | `_mdrn_it_eagle` | Modern Weapons > Ranged Weapons > Handgun | SRG-00261 — Ares Predator III | Weapons > Firearms > Pistols > Heavy pistols | `official-SR3-line` | Medium |
| 57 | Desert Eagle 0.50AE (off-hand) | `_mdrn_it_eagoff` | Modern Weapons > Ranged Weapons > Dual Handgun | SRG-00261 — Ares Predator III | Weapons > Firearms > Pistols > Heavy pistols | `official-SR3-line` | Medium |
| 58 | Glock 17 9mm (dual-wield) | `_mdrn_it_glkdual` | Modern Weapons > Ranged Weapons > Dual Handgun | SRG-00261 — Ares Predator III | Weapons > Firearms > Pistols > Heavy pistols | `official-SR3-line` | Medium |
| 59 | Glock 17 9mm (off-hand) | `_mdrn_it_glkoff` | Modern Weapons > Ranged Weapons > Dual Handgun | SRG-00261 — Ares Predator III | Weapons > Firearms > Pistols > Heavy pistols | `official-SR3-line` | Medium |
| 60 | H&K USP 9mm (dual-wield) | `_mdrn_it_hkudual` | Modern Weapons > Ranged Weapons > Dual Handgun | SRG-00261 — Ares Predator III | Weapons > Firearms > Pistols > Heavy pistols | `official-SR3-line` | Medium |
| 61 | H&K USP 9mm (off-hand) | `_mdrn_it_hkuoff` | Modern Weapons > Ranged Weapons > Dual Handgun | SRG-00261 — Ares Predator III | Weapons > Firearms > Pistols > Heavy pistols | `official-SR3-line` | Medium |
| 62 | H&K USP 9mm | `d20_smarms003` | Modern Weapons > Ranged Weapons > Handgun | SRG-00261 — Ares Predator III | Weapons > Firearms > Pistols > Heavy pistols | `official-SR3-line` | Medium |
| 63 | Glock 17 9mm | `d20_smarms008` | Modern Weapons > Ranged Weapons > Handgun | SRG-00261 — Ares Predator III | Weapons > Firearms > Pistols > Heavy pistols | `official-SR3-line` | Medium |
| 64 | Colt Python .357 Revolver (dual-wield) | `_mdrn_it_357dual` | Modern Weapons > Ranged Weapons > Dual Handgun | SRG-00320 — Ruger Super Warhawk | Weapons > Firearms > Pistols > Heavy pistols | `official-SR3-line` | Medium |
| 65 | Colt Python .357 Revolver (off-hand) | `_mdrn_it_357off` | Modern Weapons > Ranged Weapons > Dual Handgun | SRG-00320 — Ruger Super Warhawk | Weapons > Firearms > Pistols > Heavy pistols | `official-SR3-line` | Medium |
| 66 | S&W M29 .44 Magnum Revolver (dual-wield) | `_mdrn_it_44dual` | Modern Weapons > Ranged Weapons > Dual Handgun | SRG-00320 — Ruger Super Warhawk | Weapons > Firearms > Pistols > Heavy pistols | `official-SR3-line` | Medium |
| 67 | S&W M29 .44 Magnum Revolver | `_mdrn_it_44mag` | Modern Weapons > Ranged Weapons > Handgun | SRG-00320 — Ruger Super Warhawk | Weapons > Firearms > Pistols > Heavy pistols | `official-SR3-line` | Medium |
| 68 | S&W M29 .44 Magnum Revolver (off-hand) | `_mdrn_it_44off` | Modern Weapons > Ranged Weapons > Dual Handgun | SRG-00320 — Ruger Super Warhawk | Weapons > Firearms > Pistols > Heavy pistols | `official-SR3-line` | Medium |
| 69 | Colt Python .357 Revolver | `d20_smarms005` | Modern Weapons > Ranged Weapons > Handgun | SRG-00320 — Ruger Super Warhawk | Weapons > Firearms > Pistols > Heavy pistols | `official-SR3-line` | Medium |
| 70 | Webley .38 British Bulldog | `d20_smarms013` | Modern Weapons > Ranged Weapons > Handgun | SRG-00320 — Ruger Super Warhawk | Weapons > Firearms > Pistols > Heavy pistols | `official-SR3-line` | Medium |
| 71 | Webley .38 British Bulldog (dual-wield) | `d20_smarms013dl` | Modern Weapons > Ranged Weapons > Dual Handgun | SRG-00320 — Ruger Super Warhawk | Weapons > Firearms > Pistols > Heavy pistols | `official-SR3-line` | Medium |
| 72 | Webley .38 British Bulldog (off-hand) | `d20_smarms013off` | Modern Weapons > Ranged Weapons > Dual Handgun | SRG-00320 — Ruger Super Warhawk | Weapons > Firearms > Pistols > Heavy pistols | `official-SR3-line` | Medium |
| 73 | Molotov Cocktail | `_mdrn_ot_molotov` | Modern Weapons > Throwing | SRG-02418 — Incendary Grenade (A) | Explosives > Grenades > Aerodynamic Grenades | `official-SR3-line` | Medium |
| 74 | Flashlight | `_mdrn_ot_light` | Modern General > Survival Gear | SRG-03651 — Flashlight, large | Surveillance and security > Vision enhancers/Flashlights | `official-SR3-line` | Medium |
| 75 | Negev 5.56mm Light Machine Gun | `d20_hvarms006` | Modern Weapons > Ranged Weapons > Heavy | SRG-01321 — Ingram Valiant | Weapons > Firearms > Heavy weapons > Light Machine Guns | `official-SR3-line` | Medium |
| 76 | Mauser m/96 7.62mm Sniper Rifle | `d20_hvarms004` | Modern Weapons > Ranged Weapons > Heavy | SRG-01191 — Remington 950 | Weapons > Firearms > Rifles > Sport rifles | `official-SR3-line` | Medium |
| 77 | M24 7.62mm Sniper Rifle | `d20_hvarms005` | Modern Weapons > Ranged Weapons > Heavy | SRG-01191 — Remington 950 | Weapons > Firearms > Rifles > Sport rifles | `official-SR3-line` | Medium |
| 78 | Enfield .303 Rifle | `d20_hvarms_004` | Modern Weapons > Ranged Weapons > Longarms | SRG-01191 — Remington 950 | Weapons > Firearms > Rifles > Sport rifles | `official-SR3-line` | Medium |
| 79 | Skorpion Vz61 .32 caliber Machine Pistol | `d20_smarms006` | Modern Weapons > Ranged Weapons > SMGs | SRG-00854 — Colt Cobra TZ-110 | Weapons > Firearms > Submachine guns | `official-SR3-line` | Medium |
| 80 | Standard Scope | `_mdrn_ot_scope` | Modern General > Weapon Accessories | SRG-01623 — Imaging Scope: Mag:1 | Firearm and weapon accessories > Imaging Accessories > Scopes and Sights | `official-SR3-line` | Medium |
| 81 | Ithaca 37 Shotgun | `_mdrn_it_ithac37` | Modern Weapons > Ranged Weapons > Longarms | SRG-01103 — Remington 990 | Weapons > Firearms > Shotguns | `official-SR3-line` | Medium |
| 82 | Gas Mask | `_mdrn_it_gasmask` | Modern General > Survival Gear | SRG-04393 — Respirator | Survival gear > General | `official-SR3-line` | Medium |
| 83 | Stun Gun | `_mdrn_it_stungun` | Modern General > Professional Equipment | SRG-00829 — Defiance Super Shock | Weapons > Firearms > Tasers | `official-SR3-line` | Medium |
| 84 | Machete | `_mdrn_it_knife01` | Modern Weapons > Bladed > Shortswords | SRG-00043 — Survival Knife | Weapons > Melee weapons > Edged weapons | `official-SR3-line` | Medium |
| 85 | Combat Knife | `_mdrn_it_knife05` | Modern Weapons > Bladed > Daggers | SRG-00043 — Survival Knife | Weapons > Melee weapons > Edged weapons | `official-SR3-line` | Medium |
| 86 | Anti-toxin | `_mdrn_ot_antidot` | Modern General > Drugs | SRG-05055 — Antidote Patch [1] | Biotech > Slap patches > Antidote Patch Max 8 | `official-SR3-line` | Low |
| 87 | Baby Browning .25 (dual-wield) | `_mdrn_it_bbydual` | Modern Weapons > Ranged Weapons > Dual Handgun | SRG-00275 — Browning Max-Power | Weapons > Firearms > Pistols > Heavy pistols | `official-SR3-line` | Low |
| 88 | Baby Browning .25 (off-hand) | `_mdrn_it_bbyoff` | Modern Weapons > Ranged Weapons > Dual Handgun | SRG-00275 — Browning Max-Power | Weapons > Firearms > Pistols > Heavy pistols | `official-SR3-line` | Low |
| 89 | Baby Browning .25 | `d20_smarms002` | Modern Weapons > Ranged Weapons > Handgun | SRG-00275 — Browning Max-Power | Weapons > Firearms > Pistols > Heavy pistols | `official-SR3-line` | Low |
| 90 | Microphone | `_mdrn_ot_mike1` | Modern General > Professional Equipment | SRG-03693 — Subvocal Microphone | Surveillance and security > Communications > General | `official-SR3-line` | Low |
| 91 | Microphone - News | `_mdrn_ot_mike2` | Modern General > Professional Equipment | SRG-03693 — Subvocal Microphone | Surveillance and security > Communications > General | `official-SR3-line` | Low |
| 92 | Night Vision Goggles | `_mdrn_it_nvgog` | Modern General > Surveillance Gear | SRG-03656 — Night Vision Contacts | Surveillance and security > Vision enhancers/Flashlights | `official-SR3-line` | Low |
| 93 | Adrenaline Injection | `_mdrn_ot_adrenal` | Modern General > Drugs | SRG-05063 — Stimulant Patch [1] | Biotech > Slap patches > Stimulant Patch Max 6 | `official-SR3-line` | Low |
