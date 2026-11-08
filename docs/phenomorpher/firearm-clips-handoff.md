# Firearm clips, effects and sounds: SR_NWN handoff

Everything SR_NWN needs to use the firearm animations, gun effects and sounds shipped from SRN_HAKS. The sources are
[givemedeath/SRN_HAKS#95](https://github.com/givemedeath/SRN_HAKS/pull/95) (contract 1.4.0: clips and sounds) and
[givemedeath/SRN_HAKS#98](https://github.com/givemedeath/SRN_HAKS/pull/98) (contract 1.5.0: gun effects, automatic rifle
clips, recoil and elbow fixes, crossbow carry fix). Check that both have merged before relying on these packs.

Nothing plays these resources yet. SRN_HAKS supplies them, and SR_NWN owns the firing framework and the sound wiring.

## SR_NWN work to do

1. **Crossbow sound mute, as D442 did for slings** (user request 2026-11-07; see [Crossbow sound mute](#crossbow-sound-mute)).
   Rifles and shotguns are crossbow-class, so the crossbow miss sound plays on every shot until this lands.
2. **Map the clips on equip** with `ReplaceObjectAnimation` (see [Playing them](#playing-them)). The gun effects fire
   only when the body plays the replaced names.
3. **Decide burst and full-auto mapping** for `fire_rfla`, `fire_rflb` and `fire_smg` (see
   [Automatic fire](#automatic-fire)). Tell SRN_HAKS if a clip needs a different kick count or timing.
4. **Wire shot sounds** per weapon through `ShotSound` (see [Sounds](#sounds)).
5. **Record the new `srn_body` override** in `sr_firearm_ovr`'s rollback notes: removing `srn_body` also removes
   `a_ba_non_combat.mdl`, which brings back the stock crossbow carry and the rifle through the head out of combat.

## Packs

| Pack | Resource | Change |
|---|---|---|
| `srn_body` | `a_ba_custom.mdl` | Overrides the installed model: stock clips unchanged, 205 clips added, parent still `a_ba_casts` |
| `srn_body` | `a_ba_non_combat.mdl` | New in 1.5.0. Overrides the installed model: `xbowr` keeps its nodes but has no keys; every other clip is stock |
| `srn_weapon` | `wbwsl_b_051`, `wbwsl_b_052`, `wbwsl_b_065`, `wbwsl_m_023`, `wbwxh_t_015` | New in 1.5.0: muzzle flash and casing emitters with their clips (Colt L36 both colours, Ares Predator IV, Ingram, AK-98) |
| `srn_weapon` | `srnfx_casing.tga` | New in 1.5.0: tumbling casing sheet |
| `srn_sound` | 17 WAVs, listed under Sounds | New in 1.4.0. No 2DA row references them |

- SHA-256: `a_ba_custom.mdl` `8beffddee69cad533ac2ee09f6417f0d6331a25fcff8676818fca98e6c45167d` (3,893,497 bytes ASCII),
  `a_ba_non_combat.mdl` `708fd5b94f431e32e4991f960ddcfe16ea2bee9be07c1100f8f876be0cd9e632` (712,917 bytes ASCII). The gun
  parts' hashes are in `docs/items/approved-weapons-v1.json`, which keeps each part's pre-effects hash too.
- Body contract is 1.5.0, in `docs/phenomorpher/game-ready-assets.json`. No 2DA changed, so `ammunitiontypes.2da`,
  `weaponsounds.2da` and `visualeffects.2da` are SR_NWN's to supply.
- A game patch to `a_ba_custom` or `a_ba_non_combat` would be shadowed by these files.
- `srn_body` now changes every crossbow holder, stock crossbows included: no shoulder carry out of combat.

## Clips

Names are `<action>_<weapon>_<slot>`. All 205 are in `a_ba_custom`, which every playable body reaches.

| Clip stem | Use | Clips | Length | `hit` event | Stock name to replace |
|---|---|---:|---:|---|---|
| `fire_rfl` | Rifle fire, one shot | 15 | 1 s | 0 s | `xbowshot` |
| `fire_rfla` | Rifle full auto, 10 rounds a second | 15 | 1 s | None | `xbowshot` |
| `fire_rflb` | Rifle three-round burst | 15 | 1 s | None | `xbowshot` |
| `ready_rfl` | Rifle stance | 15 | 1 s | None | `xbowrdy` |
| `fire_sg` | Shotgun fire | 15 | 1 s | 0 s | `xbowshot` |
| `ready_sg` | Shotgun stance | 15 | 1 s | None | `xbowrdy` |
| `fire_pst` | Pistol fire | 15 | 1 s | 0 s | `throwr` |
| `fire_smg` | SMG fire | 15 | 1 s | None | `throwr` |
| `fire_dpst` | Dual pistol fire | 10 | 1 s | None | `throwr` |
| `fire_dsmg` | Dual SMG fire | 10 | 1 s | None | `throwr` |
| `reload_rfl` | Rifle reload, and shotgun until it has its own | 15 | 2 s | None | `custom16lp` |
| `reload_smg` | SMG reload | 15 | 2 s | None | `custom16lp` |
| `reload_pst` | Pistol reload | 15 | 2 s | None | `custom16lp` |
| `reload_dual` | Dual reload | 10 | 4 s | None | `custom17lp` |
| `throw_gren` | Grenade throw | 10 | 1 s | 0.5 s | `custom18lp` |

- The engine launches the shot on the stock clip's own `hit` (0.5 s in `xbowshot` and `throwr`), not on ours. In 1.5.0
  the rifle and shotgun kicks moved 0.37 s later so they land at 0.5 s; the pistol already did.
- 1.5.0 also bends the pistol support elbow down and out instead of into the chest.

### Slot

| Race | Appearance | Male | Female | Female Large |
|---|---:|---|---|---|
| Human | 15100 | `hm` | `hf` | `hfl` |
| Dwarf | 15101 | `dm` | `df` | `dfl` |
| Elf | 15102 | `em` | `ef` | `efl` |
| Orc | 15103 | `om` | `of` | `ofl` |
| Troll | 15104 | `tm` | `tf` | `tfl` |

- Male Large uses the male clip.
- Female Large is phenotype 2. Its `l` slot exists only for the 15-clip stems. `fire_dpst`, `fire_dsmg`, `reload_dual` and
  `throw_gren` use the plain female slot.
- Troll bodies use Gnome part prefixes (`pmg`, `pfg`), but the slot is `t`.
- A wrong name fails silently to the stock animation, so build names in one place.

```
string ClipSlot(object oActor, string sStem)
{
    int nType = GetAppearanceType(oActor);
    string sRace = "h";
    if (nType == 15101) sRace = "d";
    if (nType == 15102) sRace = "e";
    if (nType == 15103) sRace = "o";
    if (nType == 15104) sRace = "t";
    int bFemale = GetGender(oActor) == GENDER_FEMALE;
    string sSlot = sRace + (bFemale ? "f" : "m");
    int bShared = sStem == "fire_dpst" || sStem == "fire_dsmg" || sStem == "reload_dual" || sStem == "throw_gren";
    if (!bShared && bFemale && GetPhenoType(oActor) == 2) sSlot += "l";
    return sSlot;
}

void MapClip(object oActor, string sStock, string sStem)
{
    ReplaceObjectAnimation(oActor, sStock, sStem + "_" + ClipSlot(oActor, sStem));
}
```

## Playing them

`ReplaceObjectAnimation` works on names with no clip in the chain, and it applies to robes. No placeholder clips are needed.

- **Fire:** use native attacks. Map the stock name from the table, then `ActionAttack`.
- **Rifle and shotgun stance:** map `xbowrdy` to `ready_rfl` or `ready_sg`.
- **Never map `xbowr`.** Mapping it folds the right forearm over the shoulder for the whole of combat and reverses the rifle.
  The 1.5.0 `a_ba_non_combat` override already handles the out-of-combat carry, and `ReplaceObjectAnimation` on `xbowr`
  doesn't reach that overlay anyway.
- **Pistol and SMG stance:** map `fire_pst` or `fire_smg` onto `bowrdy`, `bow`, `1hreadyr`, `1hreadyl`, `nwreadyr` and `nwreadyl`.
  Without it, the stock ready stance hides the pistol behind the body between shots.
- **Grenade:** map `custom18lp` to `throw_gren` and play `ANIMATION_LOOPING_CUSTOM18`.

### Gun effects

Each effect gun carries its own copies of the fire clips under the same names (`fire_pst_hm` and so on), plus empty clips
for idle, walk, run and the ready names. When the body plays a replaced fire clip, the gun plays its copy and sends a
`detonate` event that fires a muzzle flash (`srn_flash01..09`) and one casing (`srn_casing`).

| Gun clip | Detonates at |
|---|---|
| `fire_pst`, `fire_rfl` | 0.5 s, on the engine's shot |
| `fire_smg` | 0.1, 0.3, 0.47, 0.63, 0.8 and 0.93 s, one per kick |
| `fire_rfla` | Every 0.1 s, 10 per clip |
| `fire_rflb` | 0.4, 0.5 and 0.6 s |
| `fire_dpst` | Right gun 0.5 s, left gun 0.73 s |
| `fire_dsmg` | 0.14, 0.34, 0.5, 0.68 and 0.85 s |

- Only the five parts above have effects. A new firearm needs them added with `tools/itemkit/firearm_fx_pilot.py`
  (its `GUNS` and `PORTS`), then `--ship`.
- The gun plays its copy only when the body plays exactly that name, so the effects stay off under stock clip names.
- The flash and casing emitters are credited to hairybrain (`PROVENANCE.md`).
- Seen in the client on Trolls only, from the shipped packs: casings eject from the AK and the Predator in and out of
  combat. The flash was confirmed in the pilot builds.

### Automatic fire

One native attack is one engine shot at 0.5 s. `fire_rfla` and `fire_smg` show several kicks around it, and
`fire_rflb` shows three. How many rounds an attack spends, how damage maps to them and whether the attack rate changes
are SR_NWN's call (user, 2026-11-07). If that changes kick counts or timing, SRN_HAKS rebuilds the clips and the gun
copies together.

### Reload at any speed

```
ReplaceObjectAnimation(oActor, "custom16lp", sClip);
AssignCommand(oActor, ClearAllActions(TRUE));
AssignCommand(oActor, ActionPlayAnimation(ANIMATION_LOOPING_CUSTOM16, fSpeed, 2.0 / fSpeed));
AssignCommand(oActor, ActionAttack(oTarget));
```

- The dual reload uses `custom17lp`, `ANIMATION_LOOPING_CUSTOM17` and `4.0 / fSpeed`.
- The duration must be clip length over speed, or the clip is cut short or holds its last frame.
- Without the `ActionAttack`, the actor drops to stock idle when the clip ends.
- A reload sent during an attack waits for the attack clip, up to about 1.5 s.
- Speeds 0.25, 0.5 and 2.0 were timed at about 8.0, 3.7 and 1.1 s, on Human male with a rifle in combat.

## Sounds

Firearm reloads are silent by user decision on 2026-11-07, so don't add a reload sound.

| Resref | Intended use | Length | SHA-256 |
|---|---|---:|---|
| `fire_lt_pistol` | Light pistol shot | 0.57 s | `8475d9a03b611a756a86f06d682b02a3416b5f62fcfce672045fd1b8eeb7dc2f` |
| `fire_hvy_pistol` | Heavy pistol shot | 1.15 s | `f31a564179401b2db013851b39db424106a82e808f8912c99756fa83d1cdb647` |
| `fire_sup_pst_smg` | Suppressed pistol or SMG shot | 0.26 s | `20fae7d8f92159564ce249509d28f3557ec3ab850080b49eca21119e09722456` |
| `fire_smg` | SMG shot | 0.39 s | `0733f3b1e84b8057e101a46f07fb2afc0281f22855417d3469c86e997b3fb7a5` |
| `fire_aslt_rifle` | Assault rifle shot | 0.85 s | `a979225f38d9960f6c6cda04220639f695b9c4706d7fbd1e6b894a2b8139b44c` |
| `fire_spt_rifle` | Sport rifle shot, from the file name | 1.30 s | `6552910f3c17b253ca7c3f440e43b2a61f87821ca9bb916d959bbe73a2339a85` |
| `fire_snp_rifle` | Sniper rifle shot, from the file name | 1.83 s | `549454453ae2de0df1eaeb3fc74e1bf334fcabd7eb6b03d02121c3dc5a3360c7` |
| `fire_sup_rifle` | Suppressed rifle shot | 0.85 s | `b55d51db4adce73f40b50f1c29e7f84d84256e9ae0775fc50cd4ef4f7b0644e4` |
| `fire_shotgun` | Shotgun shot | 1.51 s | `9e3464a25450f87bb9df68955426d48325aa361664c4ae7c50732fd1dd74a922` |
| `rocket` | Rocket launcher shot | 3.63 s | `40fe512e95eb40b9650c233d241ed518a11e76e3bad529d0e7d5b8002f7e5c9b` |
| `reload_rocket` | Rocket reload, no clip exists | 1.70 s | `80218182147dcba38730a68ad71aecd528080272d3d4cf10122f7a206a2096f6` |
| `dryfire_pistol` | Empty pistol | 0.12 s | `343e14613d639ec3ba2a20218825fcfadd36051cbc5079eef126d9a5e885b84d` |
| `dryfire_rifle` | Empty rifle | 0.14 s | `c80e1ae22325a45302f107899e9feb99b23d2ee867f071745df916a636b60ed6` |
| `ric_conc-1` | Ricochet, concrete | 0.58 s | `43a8ec357f9fdc7f7d16bec3d974d421342fdb7335376a56bac80761d9f11329` |
| `ric_conc-2` | Ricochet, concrete | 0.57 s | `63b11392e7570206cf3c9baf44ce0c69bd35503b36e8b6016aef21ae6323afbe` |
| `ric_metal-1` | Ricochet, metal | 0.73 s | `e1fb440e88fac0680be54c5a8e82feaadeebbccdfaa3691f58bc454160093593` |
| `ric_metal-2` | Ricochet, metal | 0.56 s | `6f9d545ae480c2f282df1fb266f8886989892a765285fe2a6ae86ebd1f7b4b48` |

- Shot sounds belong in `ShotSound` under your projectile sound plan, not on clip events, which would double them.
- The old mod played `ric_*`, `dryfire_*` and `rocket` from `visualeffects.2da` rows (`richochette1` to `4`, `p_ammo_empty`,
  `r_ammo_empty`, `rocket_launcher`, `missile_launcher`). They can also be `ImpactSound` or `ShotSound`.
- The intended uses come from file names and those old rows. The weapon-to-sound mapping is yours.
- `fire_sup_pst_smg` is `fire_sup_pistol_smg.wav` in `SRN_CC` staging, shortened to fit the 16-character resref limit.
- None of these has been heard in the client.

### Crossbow sound mute

Do for the crossbow what D442's `sr_firearm_ovr` did for the sling: mute the base item's swing sound in
`weaponsounds.2da`, and move the crossbow's fire sound into the bolt's `ShotSound` in `ammunitiontypes.2da` (user
request 2026-11-07). Rifles and shotguns are heavy-crossbow class (base item 6), firing bolts (ammunition family 2).

| Table | Row | Column | Stock | Override |
|---|---|---|---|---|
| `weaponsounds.2da` | 15 `Crossbow_Low` (heavy crossbow's `WeaponMatType`) | `Miss0` | `cb_sh_xbowlow1` | `****` |
| `weaponsounds.2da` | 15 | `Miss1` | `cb_sh_xbowlow2` | `****` |
| `ammunitiontypes.2da` | 1 `bolt` | `ShotSound` | `****` | `cb_sh_xbowlow1` |

- **Light crossbow:** base item 7 uses row 9 `Crossbow` (`cb_sh_xbow1`, `cb_sh_xbow2`). Mute it too only if a firearm
  will ever sit on base item 7. The bolt's single `ShotSound` would then serve both, and light crossbows would take the
  heavy sound.
- **Users** (SRN_HAKS `srn_2da`, 2026-11-07): `WeaponMatType` 15 is base item 6 only, and ammunition family 2 is base
  items 6 and 7. The shipped Heavy Crossbow (`sr6abe18c_6`) and the AK-98 (`sra84e4660_5`, `sra84e4660gl`) are both base
  item 6. The real crossbow keeps its sound through the bolt, and the rifle sounds like a crossbow until a firearm
  profile gives it `fire_aslt_rifle`. Re-run `premises.py`'s user scan on the merged tables before relying on this.
- **One sound:** `ShotSound` names one resref, so the two-sample random variation becomes one sample.
- **Elemental bolts** (rows 7, 13, 19, 25, 31) keep their own `ShotSound`, as the elemental bullets do under D442.
- **Same pack:** these cells belong in `sr_firearm_ovr` beside D442's, with `closure-table.json`, `rollback.json`,
  `firearm-profiles.json` (`secondCarrier` already names base item 6 and family 2) and `SlingPresentationPackTests`
  updated. It needs its own ruling and package entry under SR_NWN's manifest rules.
- **Nothing proves it plays.** As with the sling, check in the client that the miss sound is gone and the bolt's
  `ShotSound` plays once per shot.

## Open items

- **Crossbow class chosen for rifles (user, 2026-11-07).** The crossbow mute is SR_NWN work item 1. Pistol and SMG stay on
  the sling.
- **SMG on `throwr`:** unconfirmed. `fire_smg` also ran on `xbowshot` in testing.
- **Native dual fire is untested.** Ranged weapons refuse any left-hand item, and `0B2B-02-firearms.md` rejects dual firearms so
  far. Dual poses were only seen on short sword stand-ins.
- **Upright rifle out of combat:** fixed in contract 1.5.0. `srn_body/a_ba_non_combat.mdl` keeps stock `xbowr`'s
  nodes but drops its keys, so crossbow-class rifles stay aimed outside combat. Stock crossbows lose their shoulder carry
  too. See `docs/items/firearm-fx-pilot.md`.
- **Shotgun:** there's no model yet, so its clips were solved on the rifle. It wasn't viewed on Elf or Orc after the rename.
- **Robes:** refit is deferred, and Trolls in robes break.
- **Close-up review** covers Human male only. Other races were checked in group shots.
- **The 1.5.0 client check** covers Trolls only, which the user accepted on 2026-11-07. Default camera and frame rate
  weren't measured.
- **Origin:** the nine `fire_*` WAVs have no recorded source in `PROVENANCE.md`.

## References

- Clip record and test results: [animation-chain-probe.md](animation-chain-probe.md)
- Release notes and rollback: [Release 1.5.0](README.md#release-150-firearm-effects-and-crossbow-carry) and
  [Release 1.4.0](README.md#release-140-firearm-clips)
- Gun effects, crossbow carry root cause and evidence: [firearm-fx-pilot.md](../items/firearm-fx-pilot.md)
- Clip builder and test module: `tools/itemkit/combat_clip_pilot.py`
- Effects builder and `--ship`: `tools/itemkit/firearm_fx_pilot.py`
