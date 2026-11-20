# Direct PLT repair

`tools/heads/plt_repair.py` edits a published head texture (PLT) in place, against the head's native model. Use it when the stage run that made the head is gone, or when a rerun would change approved geometry. The geometry and UVs never change. Only the (shade, channel) pair of each texel does.

The tool works for any single-PLT native model whose trimeshes sample one square texture, named after the model by default. A spec's `texture` names another texture, and the output PLT takes that name. Model and texture names are lowercase resource names of up to 16 characters. `--texture` does the same for `view` and `probe`; with a spec, it must agree with the spec's texture (or its model).

## Commands

All three take `--mdl`, `--plt`, `--palettes` (a folder with the stock `pal-*.tga` files, as in a headbatch workspace's `references/palettes`), `--embree` (the `embree4.dll` binding) and `--out`.

| Command | What it does |
|---|---|
| `view --rows 0:5,1:65,9:120 [--channels]` | Decoded views of the PLT on the model (eight angles), plus an optional channel false-colour sheet. |
| `probe --rows ... --when '{predicate}'` | Measures a selection: per-channel texel counts, plus shade, lightness and position percentiles. Writes a views sheet with the selection in magenta. Read-only. |
| `apply --spec SPEC.json` | Runs a repair spec. Writes `<texture>.plt` (the model name by default), `receipt.json`, and `before.png`, `after.png` and `changed.png` sheets. |

Run it with the bundled workspace Python (never the Windows Store `python` shim) and the bound packages on `PYTHONPATH`, for example:

```powershell
& <workspace-python> -B tools/heads/plt_repair.py apply --mdl srn_head/pfo0_head014.mdl --plt srn_head/pfo0_head014.plt --spec docs/heads/plt-repairs/pr86-v1/pfo0_head014.json --palettes <workspace>/references/palettes --embree <embree4.dll> --out <scratch>/pfo0_head014-v1
```

## Selections

Selections use the headkit predicates (`all`, `any`, `not`, `region`, `mask`, `channel`, `mapped`, `{of, center?, gt/lt/ge/le}`). Texel quantities:

- **Position:** `x`, `y`, `z` are the texel's surface point in the model's unit bounding box, in the headkit glTF frame:
  - `y` is up.
  - `z` points toward the face.
  - `x` points toward the anatomical left.
  - The ears sit at `{"of": "x", "center": 0.5, "gt": 0.4}`.
- **Texture coordinates:** `u` and `v`, top-down.
- **Current texel:** `channel` and `shade`.
- **Decoded colour** under the spec's `previewRows`: `r`, `g`, `b`, `lum`, `sat`, `red`, `rb`, `gb`.
- **Outlines:** `mask:NAME` for each `surfaceOutlines` entry.

Probe before you write an operation. A selection that looks right in one view often reaches the ears, the far side or the inside of the hair.

## Operations

Operations run in order. Each acts only on mapped texels that its `when` selects.

| Operation | Use |
|---|---|
| `fill` | Sets each texel's shade to the median of its k nearest unselected texels of the same channel (3D distance). Optional `channel` moves the texels first; `donors` restricts the donor texels. Use it for blotches and stray patches. It flattens texture, so keep the patches small. |
| `despeckle` | Replaces texels that differ by more than `threshold` shades from the median of themselves and their `neighbours` nearest texels. `side` takes `both`, `darker` or `lighter`. Use it for specks and flecks. A large `neighbours` value smears strands, so prefer 24-64. |
| `match` | Quantile-maps the selection onto a `reference` selection's shade distribution, keeping rank order. Use it for brows, or to bring one region's tone to another's. It keeps relative darkness, so a dark patch stays the darkest part of what you select. |
| `curve` | Remaps shades through piecewise-linear `points`, from 0 to 255. Use it to compress baked highlights or shadows without losing detail. |
| `clamp` | Clips shades to absolute `lo` and `hi`, or to `percentiles` of a `reference` selection, not both. |
| `relabel` | Majority vote: a texel whose neighbours mostly (`minShare`) belong to another channel moves to that channel. `to` limits the target channels. Use it for skin flecks in hair and hair bits on skin. |
| `channel`, `shade` | Set the channel, or set an absolute shade. |

`match` and `curve` take an optional `ramp` that feathers the weight from 0 at `from` to 1 at `to`. `center` measures the distance from that value, and a list of ramps multiplies. Use a ramp wherever a selection edge would otherwise show a hard step.

## Guards

- A spec pins the SHA-256 of the PLT and MDL it was measured on, and applies to no other bytes.
- The spec and each operation take only their documented keys, so a misspelled key refuses instead of falling back to a default. Parameters and preview rows are checked before any work.
- An operation that selects nothing refuses, unless it sets `allowEmpty: true`.
- An operation that changes more than `maxFraction` of the mapped texels refuses. The default is 0.25.
- Padding texels follow their nearest mapped texel wherever that texel changed, so filtering never bleeds the old value. Padding next to unchanged texels keeps its bytes.
- The receipt pins the tool, the spec, the inputs and the output. The sheets are evidence only.

## Limits found on the PR 86 heads

- **Lighting is not texture.** Dark streaks that follow deep strand grooves are geometry lit by the scene. elf-male-a's olive streaks stayed the same in the client after every hair shade was lifted to at least 64. Check whether the colour is reachable from the palette row before you edit.
- **Dim client lighting** (about half brightness in the inspect views) makes the beige end of a brown row read as olive.
- **Bright ovals on smooth scalps** are partly specular lighting. A `curve` removes the baked part, but a lit glow remains.
- **Approval:** sheets never approve appearance. Repaired heads need a client check and the user's acceptance before publication.

## Repair records

- [plt-repairs/pr86-v1](plt-repairs/pr86-v1/README.md): nine heads published in PR 86.
