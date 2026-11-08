# Firearm muzzle flash and shell casing pilot

Emitters on the firearm models fire on a `detonate` event in a clip the gun plays during the shot. Nothing ships
from this pilot. The builder is `tools/itemkit/firearm_fx_pilot.py`, and output goes to ignored `output/`.

| Gate | Question | Status |
|---|---|---|
| 1. Clip matching | Which clip name does the gun play under `ReplaceObjectAnimation`? | Passed 2026-11-07 |
| 2. Hit timing | Do the `hit` events match the recoil in the fire clips? | Answered 2026-11-07: the event is ignored |
| 3. Muzzle flash | Does a flash sit on the muzzle and match the shot? | Passed on the AK-98 2026-11-07, old flash tuned |
| 4. Shell casings | Do casings arc out, drop and read at game distance? | Ejection passed 2026-11-07; default camera not checked |
| 5. SMG burst | Does each recoil get a flash and a casing? | Passed on the Ingram 2026-11-07 |
| 6. Coverage and cost | Do the effects line up on all bodies without a frame drop? | Placement and server cost passed 2026-11-07; render frame rate not measured |

## Gate 1: clip matching

**The gun plays the replaced clip name.** When a script maps `throwr` to `fire_pst_hm`, the Colt plays its own
`fire_pst_hm` clip. It doesn't play `throwr`. With no mapping, it plays `throwr`.

### Method

The Colt (`wbwsl_b_051`), Ingram (`wbwsl_m_023`) and AK-98 (`wbwxh_t_015`) were decompiled to ASCII. Each got an
`Explosion` emitter at the barrel tip, clips that send `detonate` at 0.1 s, and a small white marker that is always on.
The edited guns load from the test hak, ahead of `srn_weapon`. Twelve Human actors fired at once: male and female, Fit
and Large, bare and in robes 005 and 020.

| Build | Clips on the gun | Mapped attack | Stock attack |
|---|---|---|---|
| `stock` | `throwr`, `xbowshot`, with a red burst | No burst on any gun | Red on Colt, Ingram and AK-98 |
| `replaced` | `<stem>_<slot>` for all 15 slots, with a green burst | Green on Colt, Ingram and AK-98 | No burst |

Mapped attacks used `fire_pst` and `fire_smg` on `throwr`, and `fire_rfl` on `xbowshot`. Stock attacks cleared both
mappings first.

### Findings

- **`detonate` fires every `Explosion` emitter on the model**, whichever clip sends it and whichever nodes the clip
  lists. The first build had both colours on one gun and showed both on every shot. A flash and a casing on one gun
  can share one event, but one model can't hold different effects for different clips.
- **Every gun needs its own clip for each slot it fires from.** That's 15 clips per fire stem, built from the slot
  list. Fewer would leave some bodies with no effect. A shared animation supermodel for the guns is untested.
- **Female Large and robes work.** The `l` slot clips played, and robed actors showed the burst too.
- **The burst position needs work.** On the Colt the burst sat at the hand. On the AK-98 it sat at the chest, so
  the barrel tip found by the builder isn't the muzzle on every gun. Gate 3 needs a measured muzzle per gun.
- **Timing looked close to the shot.** Bursts appeared with the tracer, but the gate wasn't built to measure timing.

### Evidence

Screenshots are in `output/firearm-fx-pilot-gate1-evidence/`, which is ignored and stays local:

| File | Shows |
|---|---|
| `v1-both-bursts-on-stock-attack.jpg` | First build: red and green together, since `detonate` is model-wide |
| `stock-build-red-on-stock-colt.jpg` | Red on unmapped Colt attacks |
| `stock-build-red-on-stock-rifle.jpg` | Red on unmapped AK-98 attacks |
| `stock-build-none-on-mapped-colt.jpg` | No burst on mapped Colt attacks, with tracers in flight |
| `replaced-build-green-on-mapped-colt.jpg` | Green on mapped Colt attacks |
| `replaced-build-green-on-mapped-ingram.jpg` | Green on mapped Ingram attacks |
| `replaced-build-green-on-mapped-rifle.jpg` | Green on mapped AK-98 attacks |
| `replaced-build-none-on-stock-colt.jpg` | No burst on unmapped Colt attacks, with tracers in flight |

The builds were `output/firearm-fx-pilot-v2-stock` and `output/firearm-fx-pilot-v2-replaced`, using the shipped
`a_ba_custom` clips. This is one machine and one client.

### Looping clips

Build `output/firearm-fx-pilot-v3-replaced`, 2026-11-07. Human actors played `fire_pst`, `fire_smg` and `fire_rfl`
as looping clips through `custom12lp`, `custom14lp` and `custom11lp` with `ActionPlayAnimation`, as reload and loop
tests do. No attack was running.

- **Loops fire on every cycle.** All three guns showed bursts in every frame sampled over about 4 s per loop. A burst
  lasts 1.5 s and the clip 1 s, so a single burst would have faded. Frames weren't timed closely enough to prove
  exactly one burst per cycle.
- **The gun keeps firing after the body leaves the clip.** After the actors returned to stock idle (`pause1`), the
  Colts still burst at the hip 3 s and 3.5 s later. The gun has no `pause1` clip, so it seems to keep looping the
  last clip it had. Mapped attacks didn't show this in gate 1, where a stock attack after mapped fire showed no burst.
- **It doesn't stop on its own.** A retest on the same build showed bursts in every frame for 24 s of idle.
- **Empty clips fix it.** Build `output/firearm-fx-pilot-v4-quiet` adds clips with no event to each gun for
  `pause1`, `pause2`, `walk`, `run`, `xbowrdy`, `bowrdy`, `bow`, `1hreadyr`, `1hreadyl`, `nwreadyr` and `nwreadyl`
  (`QUIET_CLIPS`). The pistol loop still burst, and the bursts stopped within 2 s of idle and stayed off for 13 s.
  Mapped Colt attacks still burst and also stopped at idle.
- **Consequence:** every gun needs an empty clip for each name the body plays outside a shot. The list above covered
  idle in this test. Walk, run, ready and the other stock names weren't exercised, and names like `hturnl`, `cwalk`
  or `talk` may need adding. Building these from a list is cheap.

Evidence is in `output/firearm-fx-pilot-loop-evidence/`. The `v3-` and `v4-` files are from the retest.

## Gate 2: hit timing

**The `hit` event in a replaced clip doesn't time the shot.** The engine launches the projectile at the stock clip's
own `hit`, which is 0.5 s in both `throwr` and `xbowshot`, whatever our clip says. Moving our events changes nothing,
so none should ship. To line the shot up with the recoil, the recoil itself has to sit at 0.5 s.

### Method

One Human Female Large actor in robe 020 fired the Colt and the AK-98 at an immortal target. The game window was
recorded at 30 frames a second with ffmpeg, and frames were read by eye. The gun's burst marks a known clip time.

| Build | `hit` in the fire clips | Burst on the gun | Tracer first seen |
|---|---|---|---|
| `v8-shipped`, Colt | 0 s | 0.1 s | About 0.6 s into the clip, on both shots recorded |
| `v8-corrected`, Colt | 0.5 s | 0.5 s | One frame after the burst, about 0.53 s |
| `v8-hit09`, Colt | 0.9 s | 0.1 s | About 0.63 s into the clip |
| `v8-hit09`, AK-98 on `xbowshot` | 0.9 s | 0.1 s | About 0.65 s into the clip |

Shot times are within a frame or two: the burst and the first visible tracer each lag their event slightly.

The server agrees. With 12 actors, a logger on the target's `OnPhysicalAttacked` and `OnDamaged` events gave
634 ms from attack to damage with the shipped pistol and 649 ms with `hit` moved 0.5 s later (builds `v5-shipped`
and `v5-corrected`). Damage is applied on the engine's own schedule. A first try at slowing the actors to 20%
with `OBJECT_VISUAL_TRANSFORM_ANIMATION_SPEED` showed no visible slow-down and was dropped.

### What this means

| Clip | Recoil onset in the clip | Against the 0.5 s shot | What to do |
|---|---|---|---|
| `fire_pst` | About 0.5 s | Lines up | Nothing |
| `fire_rfl`, `fire_sg` | About 0.13 s | Kick comes 0.37 s before the shot | Shift the motion later by about 0.37 s |
| `fire_smg` | First jolt about 0.1 s, about six jolts | The shot lands mid-burst | Decide how a burst maps to one native attack |

- Shifting the rifle and shotgun clips is a change to the shipped `a_ba_custom`, so it needs its own release.
  Shifting keys around the loop needs the clips to start and end on the same pose. That hasn't been checked.
- **Gun effects belong at 0.5 s.** Flash and casing `detonate` events should match the stock `hit`, not the fire clip's
  `hit`.
- The grenade's `hit` (0.5 s) is played through `custom18lp`, not an attack, so this test doesn't cover it.
- `throw_gren` and the dual clips weren't tested. Other stock attack names may have different `hit` times.

Recordings are in `output/firearm-fx-pilot-gate2/` (ignored), with the contact sheets used for timing.

## Hit timing found offline

The fire clips' `hit` events were measured against hand motion from the clip keys, on the Human male arm chain.
All ten slots share the same timing. Gate 2 showed the `hit` event isn't used, so the motion matters, not the event.

| Clip | `hit` | Motion | Result |
|---|---|---|---|
| `fire_pst` | 0 s | Kick starts about 0.5 s and peaks about 0.65 s | About 0.5 s early |
| `fire_rfl` | 0 s | Hand snaps back 12 cm between 0.13 and 0.20 s | About 0.15 s early |
| `fire_sg` | 0 s | Same snap, with 13° of muzzle rise | About 0.15 s early |
| `fire_smg` | None | About six small jolts, the first near 0.15 s | Missing |
| `fire_dpst`, `fire_dsmg` | None | Right and left kicks at different times | Missing, waits on dual fire |
| `throw_gren` | 0.5 s | Hand fastest at 0.47 s, furthest forward at 0.5 s | Correct |

## Recoil shift and the old mod's effects

Build `output/firearm-fx-pilot-v10-oldfx`, 2026-11-07. Nothing here ships yet.

### Recoil shift

`combat_clip_pilot.py` now turns `fire_rfl` and `fire_sg` (`custom11lp`, `custom19lp`) 0.37 s later around their loop
(`RECOIL_DELAY`), so the kick starts at 0.5 s with the engine's shot. Every node of both clips starts and ends on the
same pose, so the turn has no seam. Events stay where they were, and the ready stances come from the unshifted clips.
This changes the shipped `a_ba_custom`, so it needs its own release before it reaches `srn_body`.

On the AK-98, seen from behind the actor, the flash filled the muzzle one frame before the tracer appeared, and the gun
kicked back within the next frame. That's within the 50 ms frame spacing.

### Old effects

Both come from `F:\repos\SR_NWN\OLD_SR_MOD_ASSETS\!Combat Override System` (`--old-fx`):

| Effect | Source | What changed |
|---|---|---|
| Flash | `muzzle_flash01..09` in `WIP/combat_ovr_v1.hak/models/wbwxh_m_154.mdl`: nine `fxpa_flare` sprites, 10 cm apart down the barrel | Moved onto each gun's muzzle. The old sprites grow from nothing and peak 0.2 s after the shot, so the bullet left before the flash showed. They now start full (0.12) and shrink and fade over 0.1 s (`FLASH_FIELDS`) |
| Casing | `Casings39` in `OLD/!DONE/gun models/wbwar_t_101.mdl`: one `Explosion` particle, 2 m/s to the right and slightly up, with mass, bounce and a 5 s life | Put on a hand-placed ejection port per gun (`PORTS`). Size 0.15 drew a casing about 12 cm long, so it's now 0.085 (`CASING_SIZE`): about 68 by 22 mm, 1.75 times a 39 mm rifle casing (user choice, 2026-11-07). Builds up to v13 used 0.06 |
| Casing sheet | `fxpa_smoke02.tga` beside the gun models: 16 identical casings | It overwrote the stock smoke texture of that name. It's now `srnfx_casing`, redrawn as 16 frames that turn the casing side-on to end-on, played at 24 frames a second |

Both fire on one `detonate` at 0.5 s.

### What was seen

| Gun | Flash | Casing |
|---|---|---|
| AK-98, `fire_rfl` | On the muzzle, one frame before the tracer | Out to the right, falls clear of the body |
| Colt, `fire_pst` | On the muzzle in a front view (v9). Hidden by the body from behind | Out to the right, arcs and falls, visibly tumbling |
| Ingram, `fire_smg` | Hidden by the body from behind | Out to the right, one per attack |

- One Human Female Large actor in robe 020 was recorded from 1.5 m behind with the new `behind` chat command, at about
  20 frames a second. Other bodies and the default camera height weren't checked.
- The Ingram gives one flash and one casing per attack. Mapping a burst to a native attack is still gate 5.
- **Provenance:** `gun credits.txt` beside the old gun models credits the d20mm team (Demigog for models and emitters,
  Dforce and Psionic for models) and the Urban Terror team. So the casing emitter is probably Demigog's. The flash in
  the WIP hak has no credit. Check reuse terms before anything ships.

Evidence is in `output/firearm-fx-pilot-v10-evidence/` (ignored). The v9 front views are in
`output/firearm-fx-pilot-v9-evidence/`.

## Gate 5: SMG burst

**Each kick of the SMG clip now gets its own flash and casing.** One native attack still fires one projectile and
deals damage once. The burst is only visual.

### Method

The `fire_smg` clips were sampled at 120 frames a second on every slot. The right hand moves back fastest at 0.108,
0.308, 0.475, 0.642, 0.808 and 0.942 s, and the muzzle pitches up at the same times. All ten slots match. The gun's
`fire_smg_<slot>` clips send `detonate` at 0.1, 0.3, 0.47, 0.63, 0.8 and 0.93 s (`KICK_TIMES`), and every other
stem keeps a single event at 0.5 s. A `detonate` fires both the flash and the casing.

Build `output/firearm-fx-pilot-v11-burst`. One Human Female Large actor in robe 020 attacked with the Ingram on
`throwr`. It was recorded from behind at about 20 frames a second.

### Findings

- **Six separate flashes, each followed by its own casing out to the right.** In one attack they came at 1.80, 2.05,
  2.25, 2.46, 2.67 and 2.82 s on the recording. Each flash was gone before the next one.
- **The bursts are spaced a little wider than the clip keys.** The spacing is 0.15 to 0.25 s against 0.13 to 0.2 s in
  the clip. The whole burst took about 1 s instead of 0.83 s. The frame timing is too coarse to say whether the attack
  plays the clip slower or the capture is uneven.
- **The tracer appeared between the third and fourth flashes,** about 0.1 s after the third. The third kick is the one
  meant to match the native 0.5 s shot, so the shot lands inside the burst.
- Dual SMGs (`fire_dsmg`) aren't covered. Their kicks come at different times for each hand, and they wait on dual
  fire.

Evidence is in `output/firearm-fx-pilot-v11-evidence/` (ignored).

## Looping rifle fire

Build `output/firearm-fx-pilot-v11-burst`, 2026-11-07. The question was whether a looping fire clip could stand in
for full-auto or burst fire. One Human Female Large actor in robe 020 played the shifted `fire_rfl` as a looping clip
(the `rifle` chat command: `custom11lp` with `ActionPlayAnimation`). No attack was running.

- **Every cycle fires once, on the kick.** Flashes came at 0.45, 1.46 and 2.50 s on the recording, about 1 s apart,
  the clip length. In each cycle the gun kicked back on the same frame as the flash, and a casing ejected right and
  fell. The 0.37 s shift has no visible seam at the loop point.
- **It stops at idle.** After the `off` command no flash or casing showed for 8 s, as the empty clips from the
  looping test intended.
- **One shot a second isn't full auto.** `fire_rfl` has one kick per 1 s cycle. Full auto or bursts need a rifle clip
  with several kicks per cycle and one `detonate` per kick, as `fire_smg` now does (`KICK_TIMES`). A shorter cycle
  would also work. Either is a new clip in `a_ba_custom`.
- **A loop deals no damage.** It's only an animation, so damage would have to come from a script or a native attack
  running alongside it. That's untested.

Evidence: `rifle-loop*` in `output/firearm-fx-pilot-v11-evidence/` (ignored).

## Automatic rifle clips

Build `output/firearm-fx-pilot-v12-auto`, 2026-11-07. Two new body clips for every slot, plus Female Large, built in
`combat_clip_pilot.py` from the solved, unshifted `fire_rfl` (`kicked`, `AUTO`):

| Clip | Rounds | Kicks at | Kick strength |
|---|---|---|---|
| `fire_rfla` | Full auto, 10 a second | 0.0 to 0.9 s, every 0.1 s | 35% |
| `fire_rflb` | Three-round burst, then a pause | 0.4, 0.5, 0.6 s | 50% |

- **How they're built:** the rifle's single kick goes back from 0.125 s and recovers by 0.5 s (`RIFLE_KICK`). It's
  squeezed into 0.1 s and replayed at each kick time, weakened toward the rest pose. Between kicks the clip holds the
  pose from 0.125 s. Both clips loop without a jump, and each has a kick at 0.5 s for the engine's shot.
- **Gun events:** the AK-98 gets `fire_rfla_<slot>` and `fire_rflb_<slot>` clips, with one `detonate` per kick
  (`AUTO_STEMS`, `KICK_TIMES`).
- **Size:** nodes the kick doesn't move keep only their end keys. That still leaves about 69 KB per clip, so the 30 new
  clips grow `a_ba_custom` from 2.5 MB to 3.9 MB. Fewer keys per kick would cut this.
- **New chat commands:** `lauto` and `lburst` loop the clips through `custom11lp`. `fauto` and `fburst` map them onto
  `xbowshot` for a native attack.

### What was seen

One Human Female Large actor in robe 020 with the AK-98, recorded from behind at about 23 frames a second.

- **Full auto as an attack:** a steady stream of flashes and casings for about 1.2 s, about 10 flashes, with the tracer
  mid-burst. The first round fires while the gun is still blending up from ready, since there's a kick at 0 s.
- **Burst as a loop:** three rounds about 0.1 s apart, then a pause, every cycle. Each round had a flash and a casing.
- **Back to idle:** after `lauto` then `off`, nothing showed for 6 s.
- **Not shown:** the weakened kick is hard to see at this frame rate and distance. Its strength needs a closer
  look. Damage is still one native shot per attack. Other bodies weren't checked.

Evidence is in `output/firearm-fx-pilot-v12-evidence/` (ignored).

## Gate 6: coverage and cost

Build `output/firearm-fx-pilot-v13-coverage`, 2026-11-07, the v12 build plus a `probe` chat command. Each race set has 12
actors: male and female, Fit and Large, bare and in robes 005 and 020. They were recorded with the wide camera.

| Set | Gun and clip | Result |
|---|---|---|
| Human | AK-98 `fire_rfla`, Colt `fire_pst`, Ingram `fire_smg` | Flashes on the gun for every actor and gun |
| Dwarf, Elf, Orc, Troll | AK-98 `fire_rfla` | Flashes on the gun for every actor |

- **Placement doesn't depend on the body.** The emitters ride on the gun, so they follow every slot's hand, including
  Female Large (`l` clips) and both robes.
- **No server stall.** The `probe` command logs the longest gap between 50 ms script ticks over 10 s. It read 66 ms
  with 12 Humans standing still, 67 ms with all 12 firing full auto, and 66 ms with 12 Trolls firing full auto.
- **Render frame rate wasn't measured.** The probe times the script scheduler, not drawn frames, and the screen
  capture runs too slowly to judge. Nothing visibly stuttered.
- **Casings were only specks at the wide camera** at 0.06, about 5 cm. They read at close range but barely from overhead. They are now 0.085, about 68 mm, 1.75 times a real rifle casing, as a compromise. That size is not yet checked in the client.
- **Robed Trolls render with missing body parts.** That's the all-race robe refit deferred in the animation chain
  probe, not this pilot.

Evidence is in `output/firearm-fx-pilot-v13-evidence/` (ignored).

## Pistol elbow, dual fire and the upright rifle

Builds `output/firearm-fx-pilot-v14-dual` and `output/firearm-fx-pilot-v15-sling`, 2026-11-07.

### Pistol support elbow

- **Problem:** in `fire_pst` the left elbow sat high and turned in, then snapped at the kick. The source clip's left
  arm hangs free, so the support-arm solve took its bend direction from that arm, which is arbitrary.
- **Fix:** for a fixed support grip with no magazine (`solve_support`), the left elbow now bends toward a fixed
  direction, down and out in the torso frame (`GRIP_ELBOW` in `tools/itemkit/combat_clip_pilot.py`). Other support
  solves keep the source arm's bend direction.
- **Result:** the elbow stays low and outside through the clip and the kick, offline and in the client
  (`output/firearm-fx-pilot-v14-evidence/pistol-elbow-zoom.jpg`).

### Dual fire

- **Engine limit:** the engine refuses a left-hand item when the right hand holds a ranged weapon. Dual guns therefore
  only show as short sword stand-ins in both hands.
- **Per-hand stand-ins:** each dual gun now has a left part (`wswss_b_201` Colt, `wswss_m_202` Ingram) and a right part
  (`wswss_b_204`, `wswss_m_205`), blueprints `srp_dcolt`/`srp_dingr` and `srp_rcolt`/`srp_ringr`. Each plays only the
  dual clip, with its own hand's kicks (`DUAL` in `tools/itemkit/firearm_fx_pilot.py`). Before this, both hands used
  the left part and flashed together at the left hand's time.
- **The real guns** also carry the dual clip with the right hand's kicks, for the day a real gun can sit in the right
  hand beside a left-hand gun.
- **Dual pistols (`spistol`, `lpdual`):** the right gun flashes, then the left 0.23 s later, once each per cycle, each
  with its own casing.
- **Dual SMGs (`ssmg`, `lsdual`):** both guns flash together on every kick.
- **Equip order matters:** arming the stand-ins straight after the sling rifle left the left hand empty, since the
  rifle was still in the right hand when the left item went on. A second `spistol` equipped both.
- **Casing size:** at close range the 0.085 casings read as a rifle-sized brass case, not a speck.

### Rifle pointing through the head

**Root cause (build v24):** out of combat, the client lays the stock `xbowr` clip from `a_ba_non_combat` over whatever
clip a crossbow holder plays, the way `walk_swordr` and `torchl` ride on the arm. `xbowr` keys only `rforearm_g`
(folded about 234°), `rhand_g` and `rhand` (turned 40°): that is the raised-forearm, muzzle-up carry. It lands on top
of our fire clips too, so the AK-98 stands up through the head. In combat the overlay is off.

**Fix, proven in the pilot, keeps crossbow class:** ship an overriding `a_ba_non_combat` whose `xbowr` keeps its nodes
but has no keys (`carry_overlays`, `CARRY_STOCK = 'srp_xbowr_still'`). In the client (build v24):

- **Idle:** the arm hangs and the rifle points muzzle-down, as on the sling test part.
- **Rifle loop out of combat:** `fire_rfl` aims forward from the start and still at 19 s.
- **Combat:** `frifle` fires forward as before. Back in idle 20 s after combat the rifle hangs muzzle-down again.

Only the model override works. `ReplaceObjectAnimation(a, "xbowr", ...)` to an empty or keyless copy changed nothing
(build v22, chat `xr <kind>`), and neither did a keyless clip named `xbowr` in `a_ba_custom` (build v23): the client
reads the overlay straight from `a_ba_non_combat`, not through the creature's chain. The override is global, so stock
crossbows lose their shoulder carry as well. A styled rifle carry can't go in `xbowr`, because the overlay also
lands on the fire clips out of combat; it belongs in per-gun idle and walk clips mapped on equip. Evidence:
`output/firearm-fx-pilot-v24-evidence` (ignored).

How the flip was first narrowed (builds v15 to v21):

- **Not in the files:** the AK-98 parts carry no animations, `baseitems.2da` has no rotation column for held weapons,
  and the engine names no hook other than `rhand` and `lhand`.
- **Tied to the wield type:** the same mesh and clip as a sling-class item (`srp_srifle`, part `wbwsl_*_203`) hangs
  muzzle-down in idle and stays forward through the rifle loop. As a crossbow it flips muzzle-up.
- **Tied to combat state, not the clip:** looping `fire_rfl` straight after an attack keeps the rifle forward for several
  seconds. Once the actor drops out of combat mode, about 12 s later, the same loop flips the rifle muzzle-up with the
  flash behind the head. So it shows "sometimes": whenever a rifle or shotgun clip plays outside combat mode, or while
  combat mode ends.
- **Script can't hold combat mode:** nwscript has no call that sets it.
- **Not the hook keys:** the rifle clips key `rhand` at identity on every frame. Giving it a changing tilt of 0.1° and
  then 3° (builds v18 and v19) left the crossbow just as upright out of combat. So did a changing 1.1° to 2.3° tilt
  plus a 2 mm move off each body's own hook position on every key (build v20).
- **Bow-class (build v17):** a longbow-class AK-98 (`srp_brifle`, part `wbwln_*_203`, chat `brifle`, `fbrifle` maps
  `bowshot` and the ready names) plays the rifle clip, but the engine hangs bows from `lhand`, so the gun sits in the
  support hand. In the ready stance the gun's pose in the left hand is the same on every body in rotation and within
  4 cm in position. In the fire clips the left hand turns up to 30° on the gun, because the support solve copies the
  source clip's left-hand angle frame by frame. A bow-part rifle would need the left hand locked to the gun and that
  offset baked into its model.
- **Stock clip, same flip (build v21):** the stock `xbowshot`, unmapped and played on the crossbow AK-98, points the
  rifle forward as an attack. Played straight after as a scripted loop (`custom11lp` mapped to `xbowshot`, chat `fxloop`;
  `xloop` alone, `fstock` the attack alone), the same clip shows the rifle muzzle-up within 3 s, and through the
  shot it swings over the shoulder and through the head. `GetIsInCombat` reads 0 from the first second of the loop.
  That ruled out our clips; the `xbowr` overlay above explains it. Evidence: `output/firearm-fx-pilot-v21-evidence`
  (ignored).

**Earlier fix, also proven but costs model slots:** make firearms sling-class and choose each creature's clips by the gun it holds. The game
plays `throwr` for every sling-class attack, so on equip map `throwr` to that gun's fire clip and the ready names
(`bowrdy`, `bow`, `1hreadyr`, `1hreadyl`, `nwreadyr`, `nwreadyl`) to its stance. Each creature holds one gun at a
time, so a per-creature `ReplaceObjectAnimation` on equip is enough. Chat command `fsrifle` does this for the sling
AK-98 (`ready_rfl` stance, `fire_rfl` on `throwr`). In the client (build v16):

- **In combat:** the rifle points forward through the fire clip and the stance between shots.
- **After combat:** it stays forward through the rifle loop 15 s later.
- **Idle:** it hangs muzzle-down from the right hand.

What adopting it needs, not done here:

- **A firearm base item:** a `baseitems.2da` row with `WeaponWield` 10 and the gun's own stats, not the stock sling row.
- **SR_NWN equip hook:** map `throwr` and the ready names from the equipped gun. The pilot's `ReloadCode` picks the
  reload by "not a sling", which would also need the gun kind.
- **Sound:** the D377 mute on sling row 6 then covers rifles and shotguns too, which settles the handoff's
  sling-or-crossbow question in favour of sling.
- **Checks still to run:** shotgun, the other races and bodies, and the rifle's muzzle flash on a sling part. The `203`
  test part was copied without effects.

Evidence is in `output/firearm-fx-pilot-v14-evidence/`, `output/firearm-fx-pilot-v15-evidence/` and
`output/firearm-fx-pilot-v16-evidence/` (ignored).
