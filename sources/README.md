# ASCII sources of compiled pack models

The packs ship compiled tile models. Their ASCII sources are kept here (user, 2026-11-20).

- **Layout:** `sources/<pack>/<model>.mdl` is the source of `<pack>/<model>.mdl`.
- **Who uses which:**
  - the game loads the binary in the pack;
  - the tile tools (`tools/tilekit`) read and write the source.
- **`compiled.json`** pins each source to the binary compiled from it, by SHA-256. The tests fail when:
  - a source changes without a compile;
  - a pack binary changes by hand;
  - a tile pack with sources ships an ASCII model;
  - a material (`.mtr`) of an adopted pack changes after the compile.
- **Materials:** cleanmodels gives a mesh tangents only where its material says it is normal-mapped. So
  `compiled.json` also records a digest of the adopted packs' materials, and of the other packs' materials the sources
  name (`manhole_tex2` is srn_placeable's and srn_door's). A compile always looks in every adopted pack and in those
  borrowed materials. When a material changes, every binary is out of date: `tilekit apply` of a material spec recompiles
  them all, and `tilekit compile` without `--model` does too.

## Why

A compiled model loads several times faster than ASCII. On the dgt04 review areas, packed ASCII loaded in 3.8–6.8 s,
and compiled in 1.1–2.0 s, against a 0.9–2.1 s baseline (2026-11-20). The game looks the same either way.

## Compiling

NeverBlender compiles the models, in one headless Blender:

```powershell
python -B -m tools.tilekit compile --blender "<blender.exe>" --addon "<the NeverBlender add-on folder, with cleanmodels>"
```

- **What it compiles:** without `--model`, every source whose binary is missing or out of date.
- **When:** `tilekit apply --blender ... --addon ...` writes changed tile models here and compiles them in one step.
- **Adopting a pack:** `--adopt <pack>` moves a tile pack's ASCII models here before compiling.

## The audit

Before any binary is written, each one is checked against its source:

- **Decoded rig:** hierarchy, node types and bind transforms, within 10 µm and 0.001°.
- **Round trip:** an animation the decoder cannot compare, or a model with a node name used twice, is decompiled
  again and compared node by node and key by key.
- **Dropped nodes:** the only difference allowed is the animation nodes the compiler says it left out, which are
  recorded in `compiled.json`.

One failure writes nothing.

## Repaired sources

Three sources had broken emitter animations: `dgt04_e09_21`, `dgt05_a00_01` and `dgt05_a01_01`. Their animation
nodes were unclosed, had no parent, and ended with a spaced-out `e n d l i s t`. The compiler then lost birthrate keys
that the client's ASCII reader keeps, so the compiled chimney smoke was thinner.

They were repaired on 2026-11-20:

- each animation node closed;
- each node given its geometry parent;
- `endlist` spelled properly;
- the repeats this left removed.

Compiled from the repaired sources, the smoke and water match the original ASCII in the client: no pixel differs by
more than 40, by day or night.
