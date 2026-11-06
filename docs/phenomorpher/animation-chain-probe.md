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
- The file is ASCII and grows with every clip, so load time must be measured and it may need a binary compile.
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
| Reload | `custom16start` |
| Dual reload | `custom17start` |
| Throw grenade | `custom18start` |
| Shotgun | `custom19start`, `custom19lp`, `custom19end` |

The most complete set is under `SR_NWN/OLD_SR_MOD_ASSETS/!Combat Override System/WIP/combat_ovr_v1.hak/models/animations`,
dated January 2011. It has `a_ba_non_combat` (male), `a_fa` (female), `a_da` (Dwarf male) and `a_dfa` (Dwarf female),
each with `custom11` to `custom19`. Only the male file has `custom10`. The `Combat Override Alpha` copy has no `custom19`.

Before use:

- Extract only these clips. Each file is a whole stock model and would replace every stock clip in it.
- Remove baked weapon nodes from the male clips: `Object01` to `Object05`, `WBwSl_m_121`, `world_mp5` and `ak-47-2-mesh`.
- Replace position keys. `custom11` to `custom15` key limb positions as well as `rootdummy`, and these would impose the
  source body's joints and hip height on other races. Keep rotations and retarget the root per slot.
- `custom13lp`, `custom14lp` and `custom15lp` have no `hit` event, unlike `custom11lp`, `custom12lp` and `custom19lp`.
- `custom16`, `custom17` and `custom18` have a `start` clip only. Test how they play. The probe only tested an `lp` clip.
- Check the clips against the firearm grip standard. They predate it.

## TODO

- [ ] Refit and test all robes for all races, male and female, Fit and Large. Trolls are the known failure. Include
  close-ups, standing and raised-arm views, and every robe row, not just 005 and 020. Scheduled for a later stage.
