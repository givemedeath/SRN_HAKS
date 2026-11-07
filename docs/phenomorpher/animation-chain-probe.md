# Animation chain probe

Where should new body animations live so they reach every body and robe? Client run on 2026-11-06, NWN:EE
8193.37-17. This is a chain test with arm-raise clips, not an approval of any animation, robe or placement.

Build it with `tools/itemkit/anim_chain_probe.py`. It writes a private module to ignored `output/`. Chat commands
`cust`, `lib`, `off`, `slotc` and `slotl` switch the phase. Nothing ships.

| Clip | Layer | Pose |
|---|---|---|
| `srpcust` | Hak override of stock `a_ba_custom` | Right arm up |
| `srplib` | Thin layer directly under the body root, as in `srn_an_*` | Left arm up |

The module shows one playable race at a time: Human, Dwarf, Elf, Orc or Troll. Each has male and female actors in Fit
and Large, each bare, in robe 005 and in coat 020, using the shipped body and clothing packs. Commands `human`,
`dwarf`, `elf`, `orc` and `troll` switch race. `at <col> <row>` moves in close and `wide` moves back.

The first run used Human male Fit and Large, Human female Fit and Dwarf male Fit, and also covered the `custom4lp`
route and rigid robe 002 on Humans. The second run covered every race with the `cust` clip. `lib` was rerun on Trolls
and Orcs only.

## Results

| Case | `a_ba_custom` clip | Library clip |
|---|---|---|
| Bare body, all 20 | Plays | Plays on Humans, Dwarves, Orcs and Trolls; Elves not rerun |
| Robe 005 | Plays | Plays |
| Coat 020 | Plays, coat sleeve follows | Coat stays down, the body's hand floats where the arm should be (Human, Dwarf, Orc and Troll) |
| Played through `custom4lp` | Plays | Same as above |

- `a_ba_custom` is reached through `srn_an_dm`, `srn_fa_h0 > a_fa` and every coat chain tested (`a_ba_coat`,
  `a_fa_coat`, `a_da_coat`).
- `ReplaceObjectAnimation` applies to the robe model as well as the body, so a replaced clip resolves on the robe's
  own chain.
- `ReplaceObjectAnimation(o, "custom4lp", clip)` plus `ANIMATION_LOOPING_CUSTOM4` plays a clip on demand. That is a
  usable reload trigger.
- Robe 005 leaves the arms to the body, and robe 002 is rigid, so neither shows a robe arm following.

## Robe fit by race

No robe has been refit to these bodies. Every robe here is the stock model.

- **Troll, male and female, both phenotypes: broken.** They wear Gnome-sized stock robes. Robes 005 and 020 sit far
  below the body, the head and arms float above them, and the feet are left on the floor. This blocks robes on Trolls
  whatever the animation placement.
- **Orc:** robes 005 and 020 held together in the views taken, including a Large male coat close-up.
- **Elf, Dwarf, Human:** nothing obviously broken from the wide view. No close-up was taken. On Elf coats the hand may
  sit past the raised sleeve, which needs a close look.

## Why not `a_ba_coat_cus`

Bodies never pass through it. Their chain is `root > a_ba`, and only coats use `a_ba_coat > a_ba_coat_cus > a_ba`.
Large coats use `a_ba2_coat_cus` instead. A clip there would reach Fit coats and nothing else. `a_ba_custom` sits below
`a_ba`, so both chains reach it.

## Corrections to earlier assumptions

- An unkeyed arm kept the pose of the previous clip: after `cust`, `lib` showed both arms raised. Clips must key every
  node they own. `runtime-optimization/libraries.md` infers that unkeyed nodes take the root's frame. That inference
  does not hold for a node already moved by a previous clip.
- A clip whose node tree is not closed crashes the client on load. The first build keyed `rbicep_g` with its parent
  `torso_g` missing from the clip. `add_custom_clip` now copies the stock clip's tree and its test checks closure.

## Decision

New body animations go in the `a_ba_custom` chain (user, 2026-11-06). Slots that need their own solve use their own
clip names, and scripts pick by race, gender and phenotype.

Costs of overriding it:

- The installed chain pin in the contract must change, as must any check that treats the stock chain as untouched.
- A game patch to `a_ba_custom` would be shadowed.
- The file is ASCII and grows with every clip. At 175 clips that added no measurable load time, as measured under Load time.
- The clips don't key coat skirt bones.

If the file gets too large, split it with new links between `a_ba_custom` and `a_ba_casts`:

```
a_ba_custom > a_ba_custom1 > a_ba_custom2 > a_ba_casts
```

Only the `setsupermodel` line of `a_ba_custom` changes, and the last new link points at `a_ba_casts`. The longest chain seen
working in the client had eight links. A split adds to that, so test it on the longest chains before relying on it.

## Existing combat clips

The old Combat Override System has these clips. None are in a shipped pack. Stock has no `custom10` to `custom20`
clips, so the names are free. `ANIMATION_LOOPING_CUSTOM10` to `CUSTOM20` are constants 30 to 40.

| Use | Clip |
|---|---|
| Chainsaw | `custom10lp` |
| Assault rifle | `custom11lp` |
| Pistol | `custom12lp` |
| Dual pistol | `custom13lp` |
| SMG | `custom14lp` |
| Dual SMG | `custom15lp` |
| Reload | `custom16start`, played as `custom16lp` |
| Dual reload | `custom17start`, played as `custom17lp` |
| Throw grenade | `custom18start` |
| Shotgun | `custom19lp` (`custom19start` and `custom19end` are not used) |

The most complete set is under `SR_NWN/OLD_SR_MOD_ASSETS/!Combat Override System/WIP/combat_ovr_v1.hak/models/animations`,
dated January 2011. It has `a_ba_non_combat` (male), `a_fa` (female), `a_da` (Dwarf male) and `a_dfa` (Dwarf female),
each with `custom11` to `custom19`. Only the male file has `custom10`. The `Combat Override Alpha` copy has no `custom19`.

Before use:

- Extract only these clips. Each file is a whole stock model and would replace every stock clip in it.
- Remove baked weapon nodes from the male clips: `Object01` to `Object05`, `WBwSl_m_121`, `world_mp5` and `ak-47-2-mesh`.
- Replace position keys. `custom11` to `custom15` key limb positions as well as `rootdummy`, and these would impose the
  source body's joints and hip height on other races. Keep rotations and retarget the root per slot.
- Check the clips against the firearm grip standard. They predate it.

## Import pilot

Client run on 2026-11-06 with `tools/itemkit/combat_clip_pilot.py`, using the January 2011 male and female clips.
Rifle, pistol, SMG, reload, grenade and shotgun clips went into `a_ba_custom`, with limb positions and baked weapons
removed and the root rescaled per slot. This is not an approval of any animation.

Firing will use native attacks, with `ReplaceObjectAnimation` swapping `xbowshot` or `throwr` per weapon. The SR_NWN
engine project owns that framework. This repo supplies the clips.

| Test | Result |
|---|---|
| Per-slot clip on `xbowshot`, native attack, Troll male and female | Plays, tracers fire |
| Rifle, SMG and shotgun clips on `xbowshot`, Troll | Attacks run, 2 rounds per 10 s |
| Pistol clip on `throwr`, Troll | Attacks run, 2 rounds per 10 s |
| SMG clip with no `hit` event | Same ammo use as the others |
| Rifle clip on `custom11lp`, Human, Orc, Troll | Plays on bare bodies, robe 005 and coat 020 |
| Reload or grenade mapped to `custom16start` or `custom18start` | No visible change |
| Same clips mapped to `custom16lp` or `custom18lp` | Plays |

- Native attacks were only run on Trolls. Orcs and Humans were tested with the looped clip.
- Ammo shows a missing `hit` event doesn't stop the attack. Damage and tracer timing without it weren't checked.
- `ANIMATION_LOOPING_CUSTOM16` and `CUSTOM18` appear to play the `lp` name, so one-shot clips need an `lp` name or mapping.
- The source limb position keys equal the stock bind, and the source root rotation keys are zero, so dropping them
  lost nothing. The bladed stance is authored.
- `a_ba_custom` grew from 97 KB to 596 KB for 36 clips, about 14 KB per clip. Load time wasn't measured.

The grip is not good enough yet. The rifle clip only moves arms by rotation, so the distance between the hands grows
with the body while the rifle does not:

| Slot | Fit | Large |
|---|---:|---:|
| Human male | 0.357 m | 0.357 m |
| Human female | 0.328 m | 0.367 m |
| Orc male | 0.460 m | 0.460 m |
| Orc female | 0.423 m | 0.476 m |
| Troll male | 0.595 m | 0.600 m |
| Troll female | 0.561 m | 0.634 m |

The first male grenade build had no keys, because that clip stores keys in a counted form the parser skipped. `read_keys`
now reads both forms and refuses any key table it did not read.

## Support arm solve

Client run on 2026-11-06, build `output/combat-clip-pilot-v7`. The pilot now solves `custom11lp` and `custom19lp` per slot
against the AK-98 (`wbwxh_t_015`). This is a pilot result, not an approval of the pose or the rifle fit. The firearm grip
standard was not re-measured: it sizes weapons, and these clips don't change the rifle or its hand attachment.

- The AK-98 sits about 14° muzzle-up in its model frame, so the old clip would aim high. `rhand_g` gets a fixed correction
  that puts the barrel on the old clip's aim.
- The left arm is solved by two-bone IK at every key, using the source elbow as the pole. The left palm sits under the
  fore-end, and the hand keeps its source orientation relative to the rifle.
- The palm starts 0.25 m ahead of the grip. If the arm would need more than 97% of its length, the palm slides back along
  the fore-end, as far as 0.19 m. The build fails if it still can't reach.
- All five races are in the pilot. Rows 15101 (Dwarf) and 15102 (Elf) were added.
- Female Large shoulders are wider, so those slots get their own clips with an `l` suffix, such as `c11lp_hfl`. Male Large
  shares the Fit clip.

| Slot | Palm distance from grip | Contact error, Fit | Contact error, Large |
|---|---:|---:|---:|
| Human male | 0.25 m | 1.2 mm | 1.2 mm |
| Human female | 0.25 m | 1.4 mm | 1.3 mm |
| Dwarf male | 0.22 m | 2.0 mm | 2.1 mm |
| Dwarf female | 0.23 m | 1.8 mm | 2.3 mm |
| Elf male | 0.25 m | 1.2 mm | 2.3 mm |
| Elf female | 0.25 m | 1.4 mm | 1.2 mm |
| Orc male | 0.25 m | 1.2 mm | 1.2 mm |
| Orc female | 0.25 m | 1.2 mm | 1.3 mm |
| Troll male | 0.25 m | 1.2 mm | 7.1 mm |
| Troll female | 0.25 m | 1.0 mm | 1.1 mm |

These are `custom11lp` figures. The worst across both clips is 7.1 mm. The barrel error against the old aim is 0° on every
slot.

Client results:

- Human, Dwarf, Elf, Orc and Troll all show both hands on the rifle, with the muzzle forward and level, on bare bodies,
  robe 005 and coat 020. The non-Troll views are group shots, and the only close-up is Troll male.
- Weapons only appear in combat stance. The `hold` command maps the clip onto `xbowrdy` and `xbowr`, so the pose stays up
  between shots. The stock crossbow stance otherwise shows between shots, because only `xbowshot` is replaced.
- The Trolls' rifle is unscaled, so it looks small on them. Their arms reach it with bent elbows.
- The butt doesn't reach the shoulder. The clip is a chest-height hold.
- `a_ba_custom` grew to 1.1 MB for 70 clips in this build. Load time still wasn't measured.

## SMG and shotgun solve

Client run on 2026-11-06, builds `output/combat-clip-pilot-v8` to `v10`. `WEAPONS` in the pilot now holds one entry per
weapon, and `TWO_HANDED` maps each clip to its weapon. This is a pilot result, not an approval.

| Clip | Weapon | Hold | Solve |
|---|---|---|---|
| `custom11lp` | AK-98 | Shoulder height | Palm fixed under the fore-end |
| `custom14lp` | Ingram Smartgun X (`wbwsl_m_023`) | Hip height | Palm fixed 0.10 m ahead of the grip, 8.1° tilt corrected |
| `custom19lp` | AK-98 standing in for a shotgun | Shoulder height | Palm follows the pump |

- **No shotgun model exists.** `srn_weapon` holds only the AK-98 and the crossbow in the two-handed class, so `custom19lp` is
  solved against the AK-98 until a shotgun is built. Replace its `WEAPONS` entry and rebuild then.
- **`custom19lp` is a pump clip.** The source left hand travels about 0.16 m along the barrel. The first solve pinned the
  palm and removed that, so the palm now follows the source hand's phase from its front point back to 0.18 m.
- **Pull:** if sliding the palm isn't enough, the weapon moves toward the left shoulder and the right arm is solved too.
  Only Dwarves need it: 0.04 m for male `custom14lp` and 0.01 m for some `custom19lp` slots. Aim stays within 0.002°.
- The worst contact error is 9.9 mm, on `custom19lp`, where the palm moves between keys. `custom14lp` is under 2 mm except
  Troll male Large at 7.7 mm, which shares the Fit clip.
- `a_ba_custom` is now 1.2 MB for 75 clips.

Client results:

- **Ingram:** the two-handed hip hold shows on all five races, on bare bodies, robe 005 and coat 020 where they were in view.
  On Trolls it looks small.
- **Shotgun:** the left hand was seen moving along the barrel on a bare Human male, and the clip fires correctly on Dwarf
  male in live combat. The other races and Dwarf female were not checked close up.
- **Firing, Ingram on `throwr`:** all five races used 2 rounds in 10 s.
- **Firing, shotgun clip on `xbowshot`:** Human and Dwarf used 2 rounds in 10 s. So did the rifle clip on Human and Dwarf.
- **Live rifle and shotgun fire with no `hold` mapping:** the weapon points forward and the left arm supports it, on Human
  rifle and Dwarf shotgun, with the shot clip showing in bursts and the low stock ready stance between shots.

Review notes:

- **`hold` reversed the rifle in live combat** on Human and Dwarf. The cause was found later: see Crossbow ready stance.
- Judge rifle grip from live shots with no `hold`. Several frames I first read as fine or as a transitional stance came from
  this state.
- Every clip now keys `rhand` and `lhand` flat from start to end. The old clips key `rhand` once or not at all. This was
  tried as a fix for the reversal and didn't change it, but it is kept because clips must key every node they own.
- The stock target dies after about 16 rounds, and actors then leave combat stance. It is now immortal in the pilot.
- Ranged stances found so far: `xbowrdy` and `xbowr` for crossbows, `bowrdy` and `bow` for the sling class.

## Reload, dual weapons and load time

Client run on 2026-11-06, builds `output/combat-clip-pilot-v11` to `v19`. This is a pilot result, not an approval.

### Clip names

Every clip is `<action>_<weapon>_<slot>`, including Human male (user, 2026-11-06). No clip keeps a `customN` name, and the
old names are only source references.

| Use | Clip | Clips | Length | `hit` event | Played by |
|---|---|---:|---:|---|---|
| Rifle fire | `fire_rfl_<slot>` | 15 | 1 s | 0 s | `xbowshot` |
| Rifle ready | `ready_rfl_<slot>` | 15 | 1 s | None | `xbowrdy` |
| Shotgun fire | `fire_sg_<slot>` | 15 | 1 s | 0 s | `xbowshot` |
| Shotgun ready | `ready_sg_<slot>` | 15 | 1 s | None | `xbowrdy` |
| Pistol fire | `fire_pst_<slot>` | 15 | 1 s | 0 s | `throwr` |
| SMG fire | `fire_smg_<slot>` | 15 | 1 s | None | `throwr` |
| Dual pistol fire | `fire_dpst_<slot>` | 10 | 1 s | None | `throwr` |
| Dual SMG fire | `fire_dsmg_<slot>` | 10 | 1 s | None | `throwr` |
| Rifle reload | `reload_rfl_<slot>` | 15 | 2 s | None | `custom16lp` |
| SMG reload | `reload_smg_<slot>` | 15 | 2 s | None | `custom16lp` |
| Pistol reload | `reload_pst_<slot>` | 15 | 2 s | None | `custom16lp` |
| Dual reload | `reload_dual_<slot>` | 10 | 4 s | None | `custom17lp` |
| Grenade throw | `throw_gren_<slot>` | 10 | 1 s | 0.5 s | `custom18lp` |

- Slots are race then gender: `hm`, `hf`, `dm`, `df`, `em`, `ef`, `om`, `of`, `tm`, `tf`. Troll bodies keep their Gnome part
  prefix, but the slot says Troll.
- The 15-clip rows add an `l` slot for each female Large body, such as `fire_rfl_tfl`. Male Large shares the Fit clip.
- `ReplaceObjectAnimation` works on a name no clip has. Reload, dual reload, the grenade and the looped rifle clip all played on
  every Human actor in build v19 with no `custom11lp`, `custom16lp`, `custom17lp` or `custom18lp` in the chain, so no placeholder
  clips are needed.
- Older sections of this document use the names of their time, and `custom11lp` there means the rifle clip.

### Reload

The old reload starts and ends with the arms at bind, so a reload from a stance dropped the arms first. The left hand also
never touched the weapon. Now:

- The first and last keys hold the raised pose, with a 0.25 s blend in.
- The left palm is solved per body onto the magazine, leaves for the belt from 0.7 to 1.1 s of the 2 s clip, and comes back
  by 1.47 s. The rifle is pulled toward the left shoulder when the arm can't reach, as far as 0.21 m on Dwarf male.
- There is one reload per magazine position. Pick by weapon:

| Weapon | Clip | Magazine point in the weapon frame |
|---|---|---|
| Rifle, and the shotgun until one exists | `reload_rfl_<slot>` | (0, -0.05, -0.12) |
| SMG | `reload_smg_<slot>` | (0, -0.165, -0.015) |
| Pistol | `reload_pst_<slot>` | (0, -0.07, 0.01) |

Palm contact is under 1 mm on Fit and under 8 mm on male Large.

### Crossbow ready stance

What the stock clips do, measured with the AK-98 in the hand:

- `xbowrdy` is the stance between shots. It points the rifle forward about 10 degrees up, but it was authored for a crossbow:
  the left palm is 0.08 to 0.19 m from the fore-end on male slots, and the hold is lower than the shot clip, so the rifle bobbed
  between them each round.
- `xbowr` is not a stance. It is a 1 s overlay on `rforearm_g`, `rhand_g` and `rhand` only (`animroot rforearm_g`).

The cause of the rifle reversal is mapping `xbowr`. With only `xbowrdy` mapped the arm is correct. With `xbowr` mapped as well,
even to an overlay that holds the same pose, the right forearm folds back over the shoulder for the whole of combat, shots
included. How the engine combines it isn't known. **Never map `xbowr`.** Earlier builds mapped it through `hold`, and the pilot
no longer does.

The stance is now `ready_rfl_<slot>` for the rifle and `ready_sg_<slot>` for the shotgun, mapped onto `xbowrdy` only:

```
ReplaceObjectAnimation(oActor, "xbowrdy", "ready_rfl_" + sSlot);
```

- Each clip holds the solved shot clip's first pose, so the left palm stays on the fore-end and the rifle doesn't bob.
- The first build was a plain hold and froze the body between shots. The clips now carry stock `xbowrdy` motion: root,
  pelvis, torso, neck and head move as stock does, measured as the change from the first key and scaled by body height.
- The arms ride on the torso. The legs are solved each key so the feet stay planted. Without that, feet slid up to 0.07 m on
  Trolls. Foot drift is now under 1 mm on all 30 stance clips.
- `xbowrdy` was copied from `a_ba` for both genders. Female stock motion wasn't used.

Client results, build v18:

- Bare Human male, close up, 22 s of live fire: the rifle stayed forward with the body moving, and a reload at speed 1 ran and
  returned to the stance.
- `hold` and `frifle` on all five races, and `holdshot` and `fshot` on Human, in group shots: no reversal on any actor.
- Barrel aim over the clips, measured offline on all 10 slots: 1.4 to 3.6 degrees up while firing, -2.2 to 1.4 degrees in the
  stance, and within 0.5 degrees of straight ahead.

### Variable reload speed

The engine plays a reload for any speed with these three lines:

```
ReplaceObjectAnimation(oActor, "custom16lp", sClip);
AssignCommand(oActor, ActionPlayAnimation(ANIMATION_LOOPING_CUSTOM16, fSpeed, 2.0 / fSpeed));
AssignCommand(oActor, ActionAttack(oTarget));
```

`2.0` is the clip length. The dual reload uses `custom17lp`, `ANIMATION_LOOPING_CUSTOM17` and `4.0`. The duration must be
the clip length over the speed, or the clip is cut short or holds its last frame. Without the `ActionAttack`, the actor drops
to its stock idle when the clip ends.

| Speed | Expected | Measured in timed frames |
|---:|---:|---:|
| 0.25 | 8.0 s | 8.0 s |
| 0.5 | 4.0 s | about 3.7 s |
| 2.0 | 1.0 s | about 1.1 s |

Timed on bare Human male rifle in combat. Frame gaps are about 0.05 s, but the ends of the clip blend, so treat the measures
as about 0.2 s either way. The 2.0 result came from the motion trace, and only the reload's end was checked in frames.

### Dual weapons

- **Ranged weapons can't take the left hand.** With a sling-class weapon in the right hand, a left-hand item is refused, even
  a melee item. This matches `design/0b/packages/0B2B-02-firearms.md` in SR_NWN, which rejects dual firearms so far.
- To see the poses, the pilot copies the Colt and Ingram onto short sword parts 201 and 202 and equips one in each hand
  (`spistol`, `ssmg`). Both guns then show, with `custom13lp` and `custom15lp` looping.
- Native dual firing has not been tested, because both stand-ins are melee weapons. `fdpistol` fires with one gun only.
- `custom17lp` plays both reload passes in 4 s on every race. The left gun stays in the left hand while it travels to the belt.

### Client results

Sweep of all five races, 12 actors each: bare, robe 005 and coat 020, male and female, Fit and Large. The views were group
shots, with close-ups on Human male only.

| Clip | Human | Dwarf | Elf | Orc | Troll |
|---|---|---|---|---|---|
| Rifle, shotgun on `xbowshot` | Plays | Plays | Rifle plays, shotgun not viewed | Rifle plays, shotgun not viewed | Plays |
| Pistol, SMG on `throwr` | Plays, pistol on male only | Plays | Plays | Plays | Plays |
| Reload, rifle | Plays | Plays | Plays | Plays | Plays |
| Reload, SMG and pistol | Plays, pistol on male only | Plays | Plays | Plays | Plays |
| Dual pistol, dual SMG, on stand-ins | Pistol on male only | Plays | Plays | Plays | Plays |
| Dual reload | Plays on stand-ins | Plays | Plays | Plays | Plays |
| Grenade | Plays | Plays | Plays | Plays | Plays |

Review notes:

- **The rifle stays forward during a reload in combat.** Out of combat it stands upright in the hand, muzzle up, through the
  same clip. The cause isn't known. Reloads out of combat need a look before the engine relies on them.
- A reload sent during an attack waits for the attack clip to finish, up to about 1.5 s.
- Between pistol shots with no `hold`, the stock `throwr` ready stance hides the pistol behind the body. `holdp` maps the
  sling stances to `custom12lp` and fixes this, like `holdsmg` for the Ingram. No reversal showed in the group shots.
- Trolls in robes still break as listed under Robe fit by race.
- The sweep table predates the stance change and the rename. Builds v18 and v19 changed the stance clips, removed the `xbowr`
  mapping and renamed clips. After the rename, on v19, Human was rechecked, then rifle fire and reload on all 12 actors of
  Dwarf, Elf, Orc and Troll, SMG reload on Elf, Orc and Troll, and pistol and dual pistol reload on Elf and Orc. An offline
  check found all 175 names the script builds in the model, none missing.
- Contact figures only prove the palm reaches the point. The rifle and Colt reloads were judged close up on Human male only,
  and the Ingram reload only in group shots.

### Load time

Three client runs each on build v19, swapping only `a_ba_custom`. Ready is process start to the module's enter script. Worst
gap is the longest script tick gap over the first 15 s, which covers spawning and dressing 12 actors.

| `a_ba_custom` | Size | Ready, median | Worst gap, median |
|---|---:|---:|---:|
| Stock | 97 KB | 3.33 s | 559 ms |
| ASCII with 175 clips | 2.44 MB | 3.24 s | 558 ms |
| Compiled with 175 clips | 2.75 MB | 3.24 s | 560 ms |

- **The clips add no measurable load time.** All three match within run-to-run noise, so splitting into `a_ba_custom1` and
  `a_ba_custom2` isn't needed for load time.
- **Compiling doesn't help.** The binary is larger and no faster. Compile with `## compileloadedasciimodels` in the client, as
  `nwnmdlcomp -c` can't find the game and `nwmain compilemodel` crashed on this file.
- The stock worst gap comes from one good run. One other gave no result, and the 49.9 s gap was the game being paused by
  hand during the run. The stock figure is the least reliable of the three.
- This is one machine with a warm disk, on a test module of 12 actors. It doesn't cover a full module or a cold start.


## TODO

- [ ] Refit and test all robes for all races, male and female, Fit and Large. Trolls are the known failure. Include
  close-ups, standing and raised-arm views, and every robe row, not just 005 and 020. Scheduled for a later stage.

## Firearm sounds

The 16 WAVs are in `srn_sound`. Nothing plays them yet. SR_NWN owns the wiring, and its full weapon-to-sound mapping is deferred
(`design/combat/PROJECTILE-SOUND-INTEGRATION-PLAN.md`, D377).

| Sound | Intended trigger, from the file names and old rows |
|---|---|
| `fire_lt_pistol`, `fire_hvy_pistol`, `fire_sup_pistol`, `fire_aslt_rifle`, `fire_spt_rifle`, `fire_snp_rifle`, `fire_sup_rifle`, `fire_shotgun` | `ShotSound` in `ammunitiontypes.2da`, picked per weapon by the engine |
| `ric_conc-1`, `ric_conc-2`, `ric_metal-1`, `ric_metal-2` | Old `visualeffects.2da` rows `richochette1` to `4`, or `ImpactSound` |
| `dryfire_pistol`, `dryfire_rifle` | Old rows `p_ammo_empty` and `r_ammo_empty` |
| `rocket` | Old rows `rocket_launcher` and `missile_launcher`, or `ShotSound` |
| `reload_rocket` | No old row found, and no rocket reload clip exists yet |

- Fire sounds don't go on clip events. The plan plays them through `ShotSound`, so a clip event would double them.
- D377 mutes only the sling sound row, but the rifle and shotgun clips here play on a crossbow-class weapon through `xbowshot`.
  The two need reconciling before rifles can use this path.
- The set has no firearm reload sound. The old `firearm_reload1` isn't among these files.
- No SMG fire sound is named. A mapping must pick from the eight above or get a new sound.
