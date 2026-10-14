# PhenoMorpher

PhenoMorpher is the project's maintained Python toolkit for measuring NWN bodies,
making conservative phenotype proposals and transferring static modular clothing.
Version 1.0 packages the established numerical backends behind a stable CLI/API.
It uses NumPy and Pillow; it adds no service, automatic landmark detector or new rig
system. The [game-ready bodies are a separate release](https://github.com/givemedeath/SRN_HAKS/pull/43).

## Setup and entry point

Use bundled workspace Python on desktop, never the Windows Store shim. CI uses
its explicit Python installation. Installed Python/Blender/NWN paths and local
bindings remain ignored. Read [shared tooling](../../docs/shared-tooling-and-workflow.md)
and create a fresh runtime binding and passed migration for this checkout.

For a Python-only migration, use the shared launcher in `--migration-smoke`
mode to run `-B -m phenomorpher doctor`, with `PYTHONPATH` set to this package
and an explicit input list containing its Python/JSON sources. Then finalize
that real smoke using:

```text
<workspace-python> -B tools/phenomorpher/finalize_runtime.py
  --toolchain .tmp/runtime.json --smoke .tmp/pheno-migration-smoke
  --output .tmp/pheno-migration.json
```

The finalizer requires the exact doctor command, all local package Python/JSON inputs,
and byte-matched loaded package origins. It verifies the interpreter and frozen helper/input
hashes. This CPU-only migration cannot authorize Blender, native export or client
work. For an existing wider migration, continue to use its explicit scope.

Optional installation: `<workspace-python> -m pip install --no-deps ./tools/phenomorpher`.
Help/version work without a runtime binding:

```text
<workspace-python> tools/phenomorpher/run.py --help
<workspace-python> -m phenomorpher --help
```

Data runs use the managed repository runner. It enumerates the actually consumed
files and code, dispatches through `launch_shared_tool.py`, freezes hashes before
the run and verifies them afterward. It reuses that one per-launch snapshot for
managed asset checks; there is no persistent timestamp cache. Preview/BLAS work is
capped at four threads. Every launch and artifact destination must be fresh.

```text
<workspace-python> -B tools/phenomorpher/run.py
  --toolchain .tmp/runtime.json --migration-receipt .tmp/migration.json
  --launch-output .tmp/pheno-doctor -- doctor

<workspace-python> -B tools/phenomorpher/run.py
  --toolchain .tmp/runtime.json --migration-receipt .tmp/migration.json
  --launch-output .tmp/pheno-check -- verify-assets
  --root . --manifest docs/phenomorpher/game-ready-assets.json
```

Join the displayed lines or use the shell's continuation syntax. The asset
manifest becomes available when the body PR is checked out or merged; the tool
PR can be installed/tested independently. Never guess a newest-looking artifact.

## Commands and inputs

| Command | Consumed input | Output |
|---|---|---|
| `doctor` | Code and bound Python runtime | Numerical/raster smoke and library versions |
| `catalog` | Body release manifest | Target IDs, slots, prefixes and approved bind stature |
| `verify-assets` | Manifest and every declared runtime resource | Exact hash/length verification |
| `native-info` | One rigid native/ASCII model | Node/mesh counts and available source attributes |
| `measure` | Pinned rig/part assembly sidecar | Four 2 mm/px masks, exact geometric dimensions and raster metadata |
| `candidate` | Typed geometry/frame/native-motion bundle and soft guides | Frozen first pass, morph proposal, connector report and neutral clay GLB |
| `replay` | Portable frozen reduction recipes and their source arrays | Independent exact reduced geometry replay |
| `convert-clothing` | Profile, source binding, ASCII garment and frozen body references | Fresh converted model and preservation receipt |

An assembly sidecar is schemaVersion 1, kind `PhenoMorpher-assembly`, with `rig`
and `parts` hash pins. Paths resolve inside the explicit `--root`. Part keys use
NWN ownership: chest, pelvis, neck, head, bicepl/r, forel/r, handl/r, legl/r,
shinl/r and footl/r. Each pin has `path` and `sha256`. All mesh nodes and their
complete static hierarchy are evaluated; unsupported weighted/animated part
geometry fails explicitly. Models and reference guides use metres, +Z up and
+Y front. Masks are bind/rest measurements; runtime stature is unverified.
If head geometry is omitted, the result is labelled body-only and must not be
treated as full stature. Stock heads are installed-game inputs, not toolkit data.

A candidate bundle is schemaVersion 1, kind `PhenoMorpher-candidate-inputs`, with
`bindMeshes`, `bindFrames`, `motion`, `reference` and optional `policy`. Each
mesh must carry its original `sourceAttributes` from `read_attributes` for the
editable scene and exact companion archive. Use
`phenomorpher.api.save_recipe` to preserve numeric array dtypes. The `motion`
baseline must retain the explicitly accepted source skeleton and all six original
pause1/pause2/walk/run/nwkickl/nwkickr clips, source pins, root and carrier.
Bind the latest published same-gender Human Fit donor; retain the female
**hips level + original upper lean/breathing** baseline. Runtime paths belong in
ignored local input bundles, not the portable tool package.

The public API is `phenomorpher.api`: `fit_candidate`, `audit_connectors`,
`assemble`, `measure`, `cross_section`, `rasterize`, `read_attributes`,
`convert_text`, `verify_assets` and typed recipe I/O. `fit_candidate` freezes
per-part uniform scale, rotation and coordinated chain placement before computing
one smooth anatomy pass. Reference dimensions are soft preferences. Source motion
keys stay exact and Human Fit slugs automatically take the identity path.
Geometry/frame/recipe outputs are proposals; they do not modify published assets.

The candidate GLB is a **neutral diagnostic**, with display-only derived normals.
It is not a replacement for the separately frozen textured scene, material atlas,
native compilation or client gates. Source UV/topology/ownership remain in the
saved recipe. Manually refined Large chest generation/UV/baking continues through
the existing purpose-built part pipeline; this package does not reproduce the
generative service or every historical sculpting trial. Frozen reduction replay
reproduces the selected reduced geometry from retained masters and correspondence.

Clothing parts replace body parts on the rig. The converter retains nodes,
topology, UV/material ownership, complete transforms and authored tangent signs.
It rejects repeated, inherited, cyclic, animated or weighted conversions; robes
and cloaks need a separate bind-aware route. Solid joint overlap is expected.

## Policy, validation and maintenance

Sound joints and natural motion take priority over race/build character, stature
and closer reference agreement. Keep measurement uncertainty separate from design
flexibility; defaults are ±5% segment lengths and ±10% width/depth preferences.
A connector must slope continuously: visible shelves, cuffs and pinches block it.
Do not stack failed taper corrections, chase individual scanlines or use preview
IK to conceal unsuitable raw donor motion. Surface coverage/penetration checks
supplement minimum contact, and visual standing/worst-motion review remains required.

Run the complete package tests with:

```text
<workspace-python> -B -m unittest discover -s tools/phenomorpher/phenomorpher
  -t tools/phenomorpher -v
```

The [pre-publication review](REVIEW.md) records resolved implementation findings.
The [first review follow-up](review-followup-validation.json) and
[second review follow-up](review-followup-2-validation.json) cover later corrections.
The [third follow-up](review-followup-3-validation.json) verifies the migration doctor contract.
The original release [validation receipt](validation.json) records tests, real-asset smokes
and wheel isolation. `source-lineage.json` pins the adopted project modules; their
numerical algorithms are retained with package-relative imports. Historical
version suffixes inside `engine` are implementation lineage, not public commands
or instructions to resume rejected experiments. Windows font lookup and artifact
defaults are portable/environment-based. Only the three required measurement/file
utilities were extracted from the old generator; its service and historical stature
defaults are excluded. Native leaf attachment dummies retain separate internal
identities, including stock female duplicate Impact nodes. Internal modules are not a stable API.

Use source hashes and explicit recipes for reuse, rather than repeatedly rendering
unchanged controls. Preserve historical evidence. Run focused affected tests and
the complete helper suite when shared helpers change. Offline tests create no
reference approval, anatomy approval, native/client validation or production
acceptance. Keep those statuses separate in every handoff.
