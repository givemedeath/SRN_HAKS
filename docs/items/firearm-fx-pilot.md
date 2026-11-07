# Firearm muzzle flash and shell casing pilot

Emitters on the firearm models fire on a `detonate` event in a clip the gun plays during the shot. Nothing ships
from this pilot. The builder is `tools/itemkit/firearm_fx_pilot.py`, and output goes to ignored `output/`.

| Gate | Question | Status |
|---|---|---|
| 1. Clip matching | Which clip name does the gun play under `ReplaceObjectAnimation`? | Passed 2026-11-07 |
| 2. Hit timing | Do the `hit` events match the recoil in the fire clips? | Not started |
| 3. Muzzle flash | Does a flash sit on the muzzle and match the shot? | Not started |
| 4. Shell casings | Do casings arc out, drop and read at game distance? | Not started |
| 5. SMG burst | Does each recoil get a flash and a casing? | Not started |
| 6. Coverage and cost | Do the effects line up on all bodies without a frame drop? | Not started |

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
- **Consequence:** each gun needs a clip with no `detonate` for every other name the body plays, at least the idle,
  ready, walk and run names. Otherwise a flash and casing keep coming after the shot. This is unconfirmed past 3.5 s,
  and the check was cut short when another session's client took the screen.

Evidence is in `output/firearm-fx-pilot-loop-evidence/`.

## Hit timing found offline

The fire clips' `hit` events were measured against hand motion from the clip keys, on the Human male arm chain.
All ten slots share the same timing. Gate 2 corrects these and checks the result in the client.

| Clip | `hit` | Motion | Result |
|---|---|---|---|
| `fire_pst` | 0 s | Kick starts about 0.5 s and peaks about 0.65 s | About 0.5 s early |
| `fire_rfl` | 0 s | Hand snaps back 12 cm between 0.13 and 0.20 s | About 0.15 s early |
| `fire_sg` | 0 s | Same snap, with 13° of muzzle rise | About 0.15 s early |
| `fire_smg` | None | About six small jolts, the first near 0.15 s | Missing |
| `fire_dpst`, `fire_dsmg` | None | Right and left kicks at different times | Missing, waits on dual fire |
| `throw_gren` | 0.5 s | Hand fastest at 0.47 s, furthest forward at 0.5 s | Correct |
