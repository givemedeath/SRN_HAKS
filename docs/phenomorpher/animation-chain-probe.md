# Animation chain probe

Where should new body animations live so they reach every body and robe? Client run on 2026-11-06, NWN:EE
8193.37-17. This is a chain test with arm-raise clips, not an approval of any animation, robe or placement.

Build it with `tools/itemkit/anim_chain_probe.py`. It writes a private module to ignored `output/`. Chat commands
`cust`, `lib`, `off`, `slotc` and `slotl` switch the phase. Nothing ships.

| Clip | Layer | Pose |
|---|---|---|
| `srpcust` | Hak override of stock `a_ba_custom` | Right arm up |
| `srplib` | Thin layer directly under the body root, as in `srn_an_*` | Left arm up |

Actors: Human male Fit and Large, Human female Fit and Dwarf male Fit, each bare, in robe 005 and in coat 020.
Human Fit actors also wore rigid robe 002.

## Results

| Case | `a_ba_custom` clip | Library clip |
|---|---|---|
| Bare body, all four | Plays | Plays |
| Robe 005 | Plays | Plays |
| Coat 020 | Plays, coat sleeve follows | Coat stays down, the body's hand floats where the arm should be |
| Played through `custom4lp` | Plays | Same as above |

- `a_ba_custom` is reached through `srn_an_dm`, `srn_fa_h0 > a_fa` and every coat chain tested (`a_ba_coat`,
  `a_fa_coat`, `a_da_coat`).
- `ReplaceObjectAnimation` applies to the robe model as well as the body, so a replaced clip resolves on the robe's
  own chain.
- `ReplaceObjectAnimation(o, "custom4lp", clip)` plus `ANIMATION_LOOPING_CUSTOM4` plays a clip on demand. That is a
  usable reload trigger.
- Robe 005 leaves the arms to the body, and robe 002 is rigid, so neither shows a robe arm following.

## Corrections to earlier assumptions

- An unkeyed arm kept the pose of the previous clip: after `cust`, `lib` showed both arms raised. Clips must key every
  node they own. `runtime-optimization/libraries.md` infers that unkeyed nodes take the root's frame. That inference
  does not hold for a node already moved by a previous clip.
- A clip whose node tree is not closed crashes the client on load. The first build keyed `rbicep_g` with its parent
  `torso_g` missing from the clip. `add_custom_clip` now copies the stock clip's tree and its test checks closure.

## What this means for placement

`a_ba_custom` is the only tested layer that reaches coats without touching robe models. It holds one clip per name,
so slots that need their own solve use their own names and scripts pick by race, gender and phenotype.

Costs of overriding it:

- The installed chain pin in the contract must change, as must any check that treats the stock chain as untouched.
- A game patch to `a_ba_custom` would be shadowed.
- The file is ASCII and grows with every clip, so load time must be measured and it may need a binary compile.
- The clips don't key coat skirt bones.
