# PhenoMorpher

PhenoMorpher is the project's maintained Python toolkit for measuring NWN bodies,
making conservative phenotype proposals and transferring static modular clothing.
Version 1.0 packages the established numerical backends behind a stable CLI/API.
It uses NumPy and Pillow; it adds no service, automatic landmark detector or new rig
system. The [shipped Human bodies](https://github.com/givemedeath/SRN_HAKS/pull/42)
provide the donor assets. The [full phenotype body release](https://github.com/givemedeath/SRN_HAKS/pull/45)
is packaged separately; its manifest and assets are not included in this toolkit.

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
| `anim-library extract-stock` | Pinned `resman_cat`, installed game (`--no-ovr`; its key files and every model BIF are frozen as inputs) and seed models | Fresh stock-chain folder with `stock-models.json` hash pins |
| `anim-library inventory` | Body manifest, its rigs/carriers/textures/materials and the stock pins | Root chains, nearest clip owners, stock deltas, texture headers and usage |
| `anim-library build` | Body manifest rigs/carriers, stock pins, Fit/Large roots | Library ASCII, clip classification and restoration plan |
| `anim-library restore` | Plan, its ASCII and source carriers, EE-compiled library | Library with exact source controller and event bytes |
| `anim-library repoint` | One native root | Root with only its supermodel field changed |
| `compare-motion` | Body manifest rigs/carriers, stock pins, library and repointed root | Per-clip exact/inherited/authorized status and assembled drift |
| `downsample-textures` | Body manifest palettes, maps and materials | Fresh folder of 2:1-reduced textures above the size cap and a receipt |
| `adopt-runtime` | Adoption plan pins: base contract, libraries, roots, comparisons, texture receipt, stock | Staged pack files, next contract, retired list, inventory index and removal list; refuses a staged release that breaks the runtime rules |
| `verify-runtime` | Contract, its rigs/libraries/carriers and palettes/maps; optional stock pins | Runtime layout rules: no private carriers, stock-terminated chains, library parent and evidence, Fit/Large supermodel, textures at most 1024 px |
| `audit-native` | One published binary model and its source (ASCII or binary) | Normalised clip controller and static rig (hierarchy, node types, bind transforms) comparison, quaternions up to sign |
| `sweep` | Contract, the targets' and donors' rigs, parts and head aliases; for motion also every rig and the stock pins | Per-body native, geometry, measurement and v16 connector (neck, penetration) report, optional motion connectors; an explicit `--clip` that a chain cannot resolve fails the run, and default clips that cannot are listed as unavailable |
| `retarget-v2` | Fit (and optional Large) `conversion.json`, stock `baseline.json`, the Human rig of that gender and the stock `a_fa`/`a_ba` chain | Fit-fitted carrier chain, Fit and Large roots naming its top carrier, and `retarget-v2.json` |
| `armor-extract` | Pinned extractor and decompiler, installed game (`--no-ovr`; key files and the BIFs holding models and textures) | Fresh stock Human armour parts (ASCII), their textures and fit references, with `stock-armor.json` pins |
| `armor-profiles` | Body manifest, its target rigs and bare parts, the stock inventory and its Human references | One scale/rotate/translate per target body and part, with residuals and anisotropy flags |
| `armor-convert` | Stock inventory and the selected Human parts, profiles, pinned NWNArmory, a style set | Calibrated Armory batch per body, corrected and renamed ASCII parts, `conversion.json` |
| `armor-publish` | Body manifest, `conversion.json` files each paired with its compile root (receipts and binaries) | The `srn_armor` pack folder and its hash-pinned contract |
| `verify-armor` | Armour contract and every pack resource | Exact pack inventory, hashes, lengths, native binaries and target-body names |

## Runtime release recipe (new or regenerated bodies)

Every PhenoMorpher step runs through `run.py` with fresh migration evidence; client compiles run
`tools/phenotypes/native_compile.py` through `launch_shared_tool.py`. No step runs a module directly.

1. Run `retarget-v2 --fit-converted <fit> --large-converted <large> --baseline <stock baseline>`. It fits one carrier
   chain from the Fit body over `a_fa`/`a_ba`, and the Large root names the same top carrier. The carriers are an
   unpublished intermediate.
2. Compile the carriers and roots in the EE client and list them in an intermediate manifest. Keep that manifest as
   durable evidence.
3. Run `anim-library build` (with `--authorized-fit-clip` where approved), compile the library in the client, then
   `anim-library restore`.
4. Run `anim-library repoint` for the Fit and Large roots, then `compare-motion` for each.
5. Run `downsample-textures` for every palette or map above 1024 px.
6. Run `adopt-runtime` with `baseKind: intermediate` for a new body, or `published` to replace a release. It refuses a
   staged release that breaks the runtime rules.
7. Run `verify-runtime` on the adopted contract, then `verify-assets` and the client review.

## Stock armour recipe (`srn_armor`)

Converts the stock Human armour parts onto the 16 non-Human bodies, which were built from the Human bodies
(plan and evidence: `docs/phenomorpher/clothing/`).

1. `armor-extract` the stock Human parts, then `armor-profiles` against the body manifest.
2. `armor-convert` once per Human source with its style set (`docs/phenomorpher/clothing/full-set-<source>.json`)
   and its four `--slot` bodies.
3. Compile each body's parts in the EE client with `tools/phenotypes/native_compile.py`.
4. `armor-publish` every conversion with its compile root, then `verify-armor`, `Build-Haks -Pack srn_armor` and
   the client review.

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
The [fourth follow-up](review-followup-4-validation.json) covers resolved-path inventory
uniqueness and coplanar section extents.
The [fifth follow-up](review-followup-5-validation.json) covers floating-point
coplanarity and current body-release links.
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
