# MDRNEE selected-item migration — first stage

Staged 93 unchanged blueprints (12 Exact identity; 81 Visual stand-in) and 217 candidate assets. Source and ERF roundtrip hashes verified. No production pack or global table was changed.

The ERF preserves source gameplay, tags, palette IDs, and BaseItem IDs. It is an archival migration input, **not ready for import into an SRN module**. Candidate assets are a conservative first pass, not a complete runtime closure. Texture formats have not yet been consolidated; collisions have not yet been resolved.

## Remaining migration gates

- Reconcile the selected BaseItem rows against the pinned EE baseline and allocate custom rows; migrate their TLK references with deduplication.
- Review legacy properties, local variables, descriptions and palette IDs before writing SRN-ready blueprints. Match tier describes appearance suitability, not gameplay compatibility.
- Resolve external assets, special armor/helmet/ammunition mappings, TXI dependencies, and shared-pack collisions before registering a pack.
- Build the resulting HAK/ERF, verify inventories and test appearances in the toolset and game.

## Modern Clothing > Clothing

| Blueprint | Tier | SR3 match | Legacy base row | Follow-up |
|---|---|---|---:|---|
| Camo Pants (Green) & Green Jacket (_mdrn_it_camjack) | Visual stand-in | Camo Jacket (Woods) | 16 | Special appearance mapping requires inspection: armor, helmet, or ammunition |

## Modern Clothing > Light

| Blueprint | Tier | SR3 match | Legacy base row | Follow-up |
|---|---|---|---:|---|
| Undercover Vest (_mdrn_it_uvest) | Visual stand-in | Secure Vest | 21 | Direct appearance candidates found; table/property/collision review still required |

## Modern Clothing > Medium

| Blueprint | Tier | SR3 match | Legacy base row | Follow-up |
|---|---|---|---:|---|
| Concealable Vest (_mdrn_it_cvest) | Visual stand-in | Armor Vest | 21 | Direct appearance candidates found; table/property/collision review still required |

## Modern Clothing > Shields > Tower Shields

| Blueprint | Tier | SR3 match | Legacy base row | Follow-up |
|---|---|---|---:|---|
| Ballistic Shield (Metal) (_mdrn_swatshld1) | Visual stand-in | Riot Shield, Large | 57 | Direct appearance candidates found; table/property/collision review still required |
| Riot (SWAT) Shield (Polycarbonate) (_mdrn_swatshld2) | Visual stand-in | Riot Shield, Large | 57 | Direct appearance candidates found; table/property/collision review still required |

## Modern General > Computers and Consumer Electronics

| Blueprint | Tier | SR3 match | Legacy base row | Follow-up |
|---|---|---|---:|---|
| Digital Audio Recorder (_mdrn_it_audrec) | Visual stand-in | Audio Recorder [1] | 205 | Direct appearance candidates found; table/property/collision review still required |
| Scientific Geiger Counter (_mdrn_ot_geiger) | Visual stand-in | Geiger Counter | 15 | Direct appearance candidates found; table/property/collision review still required |

## Modern General > Drugs

| Blueprint | Tier | SR3 match | Legacy base row | Follow-up |
|---|---|---|---:|---|
| Anti-toxin (_mdrn_ot_antidot) | Visual stand-in | Antidote Patch [1] | 15 | Direct appearance candidates found; table/property/collision review still required |
| Adrenaline Injection (_mdrn_ot_adrenal) | Visual stand-in | Stimulant Patch [1] | 209 | Direct appearance candidates found; table/property/collision review still required |

## Modern General > Professional Equipment

| Blueprint | Tier | SR3 match | Legacy base row | Follow-up |
|---|---|---|---:|---|
| Lockpick Set (_mdrn_ot_lock) | Exact identity | Lockpick Set | 24 | Direct appearance candidates found; table/property/collision review still required |
| Electrical Toolkit (Deluxe) (_mdrn_ot_disab2) | Visual stand-in | Electronic ToolKit | 207 | Direct appearance candidates found; table/property/collision review still required |
| Electrical Toolkit (basic) (_mdrn_ot_disable) | Visual stand-in | Electronic ToolKit | 206 | Direct appearance candidates found; table/property/collision review still required |
| First Aid Kit (_mdrn_firstaid) | Visual stand-in | Basic Medkit | 206 | Direct appearance candidates found; table/property/collision review still required |
| Medical Kit (_mdrn_medikit) | Visual stand-in | Basic Medkit | 29 | Icon outside item HAK (base/other HAK check needed): iit_midmisc_186 |
| Stun Gun (_mdrn_it_stungun) | Visual stand-in | Defiance Super Shock | 28 | Model outside item HAK (base/other HAK check needed): wblcl_t_051 |
| Microphone (_mdrn_ot_mike1) | Visual stand-in | Subvocal Microphone | 15 | Direct appearance candidates found; table/property/collision review still required |
| Microphone - News (_mdrn_ot_mike2) | Visual stand-in | Subvocal Microphone | 15 | Direct appearance candidates found; table/property/collision review still required |

## Modern General > Surveillance Gear

| Blueprint | Tier | SR3 match | Legacy base row | Follow-up |
|---|---|---|---:|---|
| Night Vision Goggles (_mdrn_it_nvgog) | Visual stand-in | Night Vision Contacts | 208 | Direct appearance candidates found; table/property/collision review still required |

## Modern General > Survival Gear

| Blueprint | Tier | SR3 match | Legacy base row | Follow-up |
|---|---|---|---:|---|
| Binoculars (standard) (_mdrn_it_binocs) | Exact identity | Binoculars | 206 | Direct appearance candidates found; table/property/collision review still required |
| Rope (150 ft.) (_mdrn_ot_rope) | Exact identity | Rope (50 meters) | 29 | Icon outside item HAK (base/other HAK check needed): iit_midmisc_190 |
| Sleeping Bag (_mdrn_it_sbag) | Exact identity | Sleeping Bag | 34 | Icon outside item HAK (base/other HAK check needed): iit_talmisc_012 |
| GPS Receiver (_mdrn_it_gps) | Visual stand-in | Nav-Dat GPS | 206 | Direct appearance candidates found; table/property/collision review still required |
| Flashlight (_mdrn_it_torch) | Visual stand-in | Flashlight, pocket | 15 | Direct appearance candidates found; table/property/collision review still required |
| Binoculars (Electro-Optical) (_mdrn_it_ebinoc) | Visual stand-in | Binoculars | 208 | Direct appearance candidates found; table/property/collision review still required |
| Flashlight (_mdrn_ot_light) | Visual stand-in | Flashlight, large | 15 | Direct appearance candidates found; table/property/collision review still required |
| Gas Mask (_mdrn_it_gasmask) | Visual stand-in | Respirator | 17 | Special appearance mapping requires inspection: armor, helmet, or ammunition |

## Modern General > Weapon Accessories

| Blueprint | Tier | SR3 match | Legacy base row | Follow-up |
|---|---|---|---:|---|
| Laser Sight (_mdrn_ot_laser) | Visual stand-in | Laser Sight | 79 | Icon outside item HAK (base/other HAK check needed): iit_thnmisc_177 |
| Electro-Optic Scope (_mdrn_ot_nscope) | Visual stand-in | Imaging Scope: Low-Light | 79 | Icon outside item HAK (base/other HAK check needed): iit_thnmisc_181 |
| Standard Scope (_mdrn_ot_scope) | Visual stand-in | Imaging Scope: Mag:1 | 79 | Icon outside item HAK (base/other HAK check needed): iit_thnmisc_177 |

## Modern Weapons > Ammunitions > Boxes & Packs

| Blueprint | Tier | SR3 match | Legacy base row | Follow-up |
|---|---|---|---:|---|
| Bolts (d20_ammo_box_100) | Exact identity | Bolts | 202 | Direct appearance candidates found; table/property/collision review still required |

## Modern Weapons > Ammunitions > Handgun

| Blueprint | Tier | SR3 match | Legacy base row | Follow-up |
|---|---|---|---:|---|
| Arrow (d20_arrow_001) | Exact identity | Arrows | 20 | Special appearance mapping requires inspection: armor, helmet, or ammunition |

## Modern Weapons > Axes > One-Handed

| Blueprint | Tier | SR3 match | Legacy base row | Follow-up |
|---|---|---|---:|---|
| Fireaxe (_mdrn_it_fireaxe) | Visual stand-in | Combat Axe | 212 | Texture outside item HAK: w_metal_tex (from waxfa_b_011.mdl); Texture outside item HAK: w_metal_tex (from waxfa_t_011.mdl) |
| Hatchet (_mdrn_it_hatchet) | Visual stand-in | Combat Axe | 38 | Model outside item HAK (base/other HAK check needed): waxhn_b_034; Model outside item HAK (base/other HAK check needed): waxhn_m_014; Model outside item HAK (base/other HAK check needed): waxhn_t_014 |

## Modern Weapons > Bladed > Daggers

| Blueprint | Tier | SR3 match | Legacy base row | Follow-up |
|---|---|---|---:|---|
| Switchblade (_mdrn_it_knife03) | Exact identity | Switchblade | 22 | Direct appearance candidates found; table/property/collision review still required |
| Combat Knife (_mdrn_it_knife05) | Visual stand-in | Survival Knife | 22 | Direct appearance candidates found; table/property/collision review still required |

## Modern Weapons > Bladed > Shortswords

| Blueprint | Tier | SR3 match | Legacy base row | Follow-up |
|---|---|---|---:|---|
| Machete (_mdrn_it_knife01) | Visual stand-in | Survival Knife | 0 | Model outside item HAK (base/other HAK check needed): wswss_b_011 |

## Modern Weapons > Blunts > Clubs

| Blueprint | Tier | SR3 match | Legacy base row | Follow-up |
|---|---|---|---:|---|
| Police Baton (d20_melee004) | Visual stand-in | Extendable Baton | 28 | Model outside item HAK (base/other HAK check needed): wblcl_t_051 |

## Modern Weapons > Improvised Weapons

| Blueprint | Tier | SR3 match | Legacy base row | Follow-up |
|---|---|---|---:|---|
| Chainsaw (_mdrn_it_csaw) | Exact identity | Chainsaw(Chainsaw) | 60 | Texture outside item HAK: fxpa_smoke01 (from wspsc_m_014.mdl) |
| Brass Knuckles (_mdrn_it_brasskn) | Exact identity | Brass Knuckles | 36 | Direct appearance candidates found; table/property/collision review still required |

## Modern Weapons > Polearms

| Blueprint | Tier | SR3 match | Legacy base row | Follow-up |
|---|---|---|---:|---|
| Harpoon (_mdrn_it_harpnsp) | Exact identity | Harpoon | 58 | Direct appearance candidates found; table/property/collision review still required |

## Modern Weapons > Ranged Weapons > Dual Handgun

| Blueprint | Tier | SR3 match | Legacy base row | Follow-up |
|---|---|---|---:|---|
| Beretta 92FS .22 (dual-wield) (_mdrn_it_92dual) | Visual stand-in | Beretta Model 101T | 61 | Direct appearance candidates found; table/property/collision review still required |
| Beretta 92FS .22 (off-hand) (_mdrn_it_92off) | Visual stand-in | Beretta Model 101T | 213 | Direct appearance candidates found; table/property/collision review still required |
| Colt .38 Detective (dual-wield) (_mdrn_it_c6dual) | Visual stand-in | Colt Asp | 61 | Direct appearance candidates found; table/property/collision review still required |
| Colt .38 Detective (off-hand) (_mdrn_it_c6off) | Visual stand-in | Colt Asp | 213 | Direct appearance candidates found; table/property/collision review still required |
| Colt 1911 .45 (dual-wield) (_mdrn_it_c45dual) | Visual stand-in | Colt Manhunter | 61 | Direct appearance candidates found; table/property/collision review still required |
| Colt 1911 .45 (off-hand) (_mdrn_it_c45off) | Visual stand-in | Colt Manhunter | 213 | Direct appearance candidates found; table/property/collision review still required |
| Desert Eagle 0.50AE (dual-wield) (_mdrn_it_eagdual) | Visual stand-in | Ares Predator III | 61 | Direct appearance candidates found; table/property/collision review still required |
| Desert Eagle 0.50AE (off-hand) (_mdrn_it_eagoff) | Visual stand-in | Ares Predator III | 213 | Direct appearance candidates found; table/property/collision review still required |
| Glock 17 9mm (dual-wield) (_mdrn_it_glkdual) | Visual stand-in | Ares Predator III | 61 | Direct appearance candidates found; table/property/collision review still required |
| Glock 17 9mm (off-hand) (_mdrn_it_glkoff) | Visual stand-in | Ares Predator III | 213 | Direct appearance candidates found; table/property/collision review still required |
| H&K USP 9mm (dual-wield) (_mdrn_it_hkudual) | Visual stand-in | Ares Predator III | 61 | Direct appearance candidates found; table/property/collision review still required |
| H&K USP 9mm (off-hand) (_mdrn_it_hkuoff) | Visual stand-in | Ares Predator III | 213 | Direct appearance candidates found; table/property/collision review still required |
| Colt Python .357 Revolver (dual-wield) (_mdrn_it_357dual) | Visual stand-in | Ruger Super Warhawk | 61 | Direct appearance candidates found; table/property/collision review still required |
| Colt Python .357 Revolver (off-hand) (_mdrn_it_357off) | Visual stand-in | Ruger Super Warhawk | 213 | Direct appearance candidates found; table/property/collision review still required |
| S&W M29 .44 Magnum Revolver (dual-wield) (_mdrn_it_44dual) | Visual stand-in | Ruger Super Warhawk | 61 | Direct appearance candidates found; table/property/collision review still required |
| S&W M29 .44 Magnum Revolver (off-hand) (_mdrn_it_44off) | Visual stand-in | Ruger Super Warhawk | 213 | Direct appearance candidates found; table/property/collision review still required |
| Webley .38 British Bulldog (dual-wield) (d20_smarms013dl) | Visual stand-in | Ruger Super Warhawk | 61 | Direct appearance candidates found; table/property/collision review still required |
| Webley .38 British Bulldog (off-hand) (d20_smarms013off) | Visual stand-in | Ruger Super Warhawk | 213 | Direct appearance candidates found; table/property/collision review still required |
| Baby Browning .25 (dual-wield) (_mdrn_it_bbydual) | Visual stand-in | Browning Max-Power | 61 | Direct appearance candidates found; table/property/collision review still required |
| Baby Browning .25 (off-hand) (_mdrn_it_bbyoff) | Visual stand-in | Browning Max-Power | 213 | Direct appearance candidates found; table/property/collision review still required |

## Modern Weapons > Ranged Weapons > Handgun

| Blueprint | Tier | SR3 match | Legacy base row | Follow-up |
|---|---|---|---:|---|
| Sawed Off Shotgun (_mdrn_it_sawnoff) | Visual stand-in | Remington 990 Sawed-Off | 11 | Direct appearance candidates found; table/property/collision review still required |
| Beretta 92FS .22 (d20_smarms001) | Visual stand-in | Beretta Model 101T | 11 | Direct appearance candidates found; table/property/collision review still required |
| Colt .38 Detective Revolver (d20_smarms004) | Visual stand-in | Colt Asp | 11 | Direct appearance candidates found; table/property/collision review still required |
| Colt 1911 .45 (d20_smarms007) | Visual stand-in | Colt Manhunter | 11 | Direct appearance candidates found; table/property/collision review still required |
| Desert Eagle 0.50AE (_mdrn_it_eagle) | Visual stand-in | Ares Predator III | 11 | Direct appearance candidates found; table/property/collision review still required |
| H&K USP 9mm (d20_smarms003) | Visual stand-in | Ares Predator III | 11 | Direct appearance candidates found; table/property/collision review still required |
| Glock 17 9mm (d20_smarms008) | Visual stand-in | Ares Predator III | 11 | Direct appearance candidates found; table/property/collision review still required |
| S&W M29 .44 Magnum Revolver (_mdrn_it_44mag) | Visual stand-in | Ruger Super Warhawk | 11 | Direct appearance candidates found; table/property/collision review still required |
| Colt Python .357 Revolver (d20_smarms005) | Visual stand-in | Ruger Super Warhawk | 11 | Direct appearance candidates found; table/property/collision review still required |
| Webley .38 British Bulldog (d20_smarms013) | Visual stand-in | Ruger Super Warhawk | 11 | Direct appearance candidates found; table/property/collision review still required |
| Baby Browning .25 (d20_smarms002) | Visual stand-in | Browning Max-Power | 11 | Direct appearance candidates found; table/property/collision review still required |

## Modern Weapons > Ranged Weapons > Heavy

| Blueprint | Tier | SR3 match | Legacy base row | Follow-up |
|---|---|---|---:|---|
| Minigun .50 mm (d20_hvarms001) | Visual stand-in | Vindicator Minigun | 6 | Direct appearance candidates found; table/property/collision review still required |
| Negev 5.56mm Light Machine Gun (d20_hvarms006) | Visual stand-in | Ingram Valiant | 6 | Texture outside item HAK: fxpa_flare (from wbwxh_m_074.mdl); Texture outside item HAK: soff_lens (from wbwxh_m_074.mdl) |
| Mauser m/96 7.62mm Sniper Rifle (d20_hvarms004) | Visual stand-in | Remington 950 | 6 | Texture outside item HAK: fxpa_flare (from wbwxh_m_072.mdl) |
| M24 7.62mm Sniper Rifle (d20_hvarms005) | Visual stand-in | Remington 950 | 6 | Texture outside item HAK: fxpa_flare (from wbwxh_m_021.mdl) |

## Modern Weapons > Ranged Weapons > Longarms

| Blueprint | Tier | SR3 match | Legacy base row | Follow-up |
|---|---|---|---:|---|
| AKM/AK 47 7.62mm Assault Rifle (_mdrn_it_ak47) | Visual stand-in | AK-97 | 7 | Direct appearance candidates found; table/property/collision review still required |
| AKS-74U 5.45mm Assault Rifle (_mdrn_it_ak74u) | Visual stand-in | AK-97 SMG/Carbine | 7 | Texture outside item HAK: fxpa_flare (from wbwxl_m_241.mdl) |
| HK G36 5.56mm Assault Rifle (_mdrn_it_g36) | Visual stand-in | HK G38 Assault | 7 | Texture outside item HAK: fxpa_flare (from wbwxl_m_251.mdl) |
| SPAS 12-gauge Shotgun (_mdrn_it_spas12) | Visual stand-in | Franchi SPAS-22 | 7 | Direct appearance candidates found; table/property/collision review still required |
| FN2000 5.56mm Assault Rifle (_mdrn_it_fn2000) | Visual stand-in | FN HAR | 7 | Texture outside item HAK: fxpa_flare (from wbwxl_m_073.mdl) |
| M4 Carbine 5.56mm Assault Rifle (_mdrn_it_m4) | Visual stand-in | Colt M-23 | 7 | Texture outside item HAK: fxpa_flare (from wbwxl_m_021.mdl) |
| Enfield .303 Rifle (d20_hvarms_004) | Visual stand-in | Remington 950 | 7 | Direct appearance candidates found; table/property/collision review still required |
| Ithaca 37 Shotgun (_mdrn_it_ithac37) | Visual stand-in | Remington 990 | 7 | Texture outside item HAK: fxpa_flare (from wbwxl_m_043.mdl) |

## Modern Weapons > Ranged Weapons > SMGs

| Blueprint | Tier | SR3 match | Legacy base row | Follow-up |
|---|---|---|---:|---|
| Mac Ingram M10 .45 Machine Pistol (d20_macingramm10) | Visual stand-in | Ingram Smartgun Mod. 20t | 8 | Direct appearance candidates found; table/property/collision review still required |
| Uzi 9mm Submachine Gun (_mdrn_it_uzi9mm) | Visual stand-in | Uzi III | 8 | Direct appearance candidates found; table/property/collision review still required |
| H&K MP5 9mm Submachine Gun (_mdrn_it_hkmp5k) | Visual stand-in | Ingram Smartgun Mod. 20t | 8 | Direct appearance candidates found; table/property/collision review still required |
| Skorpion Vz61 .32 caliber Machine Pistol (d20_smarms006) | Visual stand-in | Colt Cobra TZ-110 | 8 | Direct appearance candidates found; table/property/collision review still required |

## Modern Weapons > Throwing

| Blueprint | Tier | SR3 match | Legacy base row | Follow-up |
|---|---|---|---:|---|
| Smoke Grenade (_mdrn_ot_smoke) | Exact identity | Smoke Grenade (A) | 81 | Direct appearance candidates found; table/property/collision review still required |
| White Phosphorus Grenade (_mdrn_ot_phosp) | Exact identity | White Phosphorus Grenade (A) | 81 | Direct appearance candidates found; table/property/collision review still required |
| Stun Grenade (_mdrn_ot_stun) | Visual stand-in | IPE Concussion Grenade (A) | 81 | Direct appearance candidates found; table/property/collision review still required |
| Fragmentation Grenade (_mdrn_ot_frag) | Visual stand-in | IPE Defensive HE Grenade (A) | 81 | Direct appearance candidates found; table/property/collision review still required |
| Tear Gas Grenade (_mdrn_ot_tear) | Visual stand-in | Gas Grenade (A) | 81 | Direct appearance candidates found; table/property/collision review still required |
| Molotov Cocktail (_mdrn_ot_molotov) | Visual stand-in | Incendary Grenade (A) | 81 | Direct appearance candidates found; table/property/collision review still required |
