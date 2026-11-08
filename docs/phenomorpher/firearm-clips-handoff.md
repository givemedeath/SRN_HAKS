# Firearm clips and sounds: SR_NWN handoff

Everything SR_NWN needs to use the firearm animations and sounds shipped from SRN_HAKS. The source is
[givemedeath/SRN_HAKS#95](https://github.com/givemedeath/SRN_HAKS/pull/95). Check that it has merged before relying on these
packs.

Nothing plays these resources yet. SRN_HAKS supplies them, and SR_NWN owns the firing framework and the sound wiring.

## Packs

| Pack | Resource | Change |
|---|---|---|
| `srn_body` | `a_ba_custom.mdl` | Overrides the installed model: stock clips unchanged, 175 clips added, parent still `a_ba_casts` |
| `srn_sound` | 17 WAVs, listed under Sounds | New. No 2DA row references them |

- `a_ba_custom.mdl` is 2,443,937 bytes of ASCII, SHA-256 `f9e7d11e897dd57121ba28c6ebcd40c33b020d66f9e4dfbe84d7ef39edcf6fd3`.
- Body contract is 1.4.0, in `docs/phenomorpher/game-ready-assets.json`. No 2DA changed, so `ammunitiontypes.2da`,
  `weaponsounds.2da` and `visualeffects.2da` are SR_NWN's to supply.
- A game patch to `a_ba_custom` would be shadowed by this file.

## Clips

Names are `<action>_<weapon>_<slot>`. All 175 are in `a_ba_custom`, which every playable body reaches.

| Clip stem | Use | Clips | Length | `hit` event | Stock name to replace |
|---|---|---:|---:|---|---|
| `fire_rfl` | Rifle fire | 15 | 1 s | 0 s | `xbowshot` |
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
- **Pistol and SMG stance:** map `fire_pst` or `fire_smg` onto `bowrdy`, `bow`, `1hreadyr`, `1hreadyl`, `nwreadyr` and `nwreadyl`.
  Without it, the stock ready stance hides the pistol behind the body between shots.
- **Grenade:** map `custom18lp` to `throw_gren` and play `ANIMATION_LOOPING_CUSTOM18`.

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

## Open items

- **Needs a decision: sling or crossbow.** The upright-rifle finding favours sling. D377 mutes only sling row 6. Rifle and shotgun clips were tested on a crossbow-class
  weapon through `xbowshot`, firing bolts, so their native firing sound wouldn't be muted. Pistol and SMG were tested on sling.
- **SMG on `throwr`:** unconfirmed. `fire_smg` also ran on `xbowshot` in testing.
- **Native dual fire is untested.** Ranged weapons refuse any left-hand item, and `0B2B-02-firearms.md` rejects dual firearms so
  far. Dual poses were only seen on short sword stand-ins.
- **Upright rifle out of combat:** the client turns crossbow-class weapons muzzle-up whenever the creature is out of
  combat mode. Sling-class firearms, with clips mapped per gun on equip, avoid it. See `docs/items/firearm-fx-pilot.md`.
- **Shotgun:** there's no model yet, so its clips were solved on the rifle. It wasn't viewed on Elf or Orc after the rename.
- **Robes:** refit is deferred, and Trolls in robes break.
- **Close-up review** covers Human male only. Other races were checked in group shots.
- **Origin:** the nine `fire_*` WAVs have no recorded source in `PROVENANCE.md`.

## References

- Clip record and test results: [animation-chain-probe.md](animation-chain-probe.md)
- Release notes and rollback: [README.md](README.md#release-140-firearm-clips)
- Clip builder and test module: `tools/itemkit/combat_clip_pilot.py`
