# Runtime optimization: Phase 2 Dwarf pilot libraries

Offline motion evidence for the first two shared libraries. No packaged asset,
contract or client fixture changed; this creates no motion, client or production approval.

## Pipeline

Each library ran through `tools/phenomorpher/run.py` with the Phase 1 binding and migration:

1. `anim-library build` classifies the Fit chain's 172 effective clips against stock
   (decision 3: identical structure, ≤0.1 mm, ≤0.05°, assembled drift ≤1 mm on both the
   Fit and Large rigs) and writes the library ASCII plus a restoration plan. Fit and Large
   chains must be identical apart from authorized Fit clips.
2. `tools/phenotypes/native_compile.py`, launched through `launch_shared_tool.py`, compiles it
   with the EE client's `compilemodel`.
3. `anim-library restore` copies the exact source controller key/value bytes and the stored
   event records into the compiled ranges. Any key-count or column change stops the run;
   nothing is resampled. Bytes outside those ranges are left as compiled.
4. `anim-library repoint` changes only the 64-byte supermodel field of each root.
5. `compare-motion` compares the published chain with root > library > stock.

The library node tree is the first carrier's tree, plus `belt_pelvis` from the deeper
carrier that owns it. Like `srn_fa_h0`, every node is a dummy that keeps its static position and orientation;
static mesh scale/alpha/self-illumination controllers are not carried.

## Results

| Library | Supermodel | Retained | Inherited from stock | Replaces | Library bytes |
|---|---|---:|---:|---|---:|
| `srn_an_df` | `a_fa` | 168 | 4 (`plpause1`, `run_bowl`, `torchl`, `xbowr`) | 14 carriers, 18,407,956 bytes | 2,258,216 |
| `srn_an_dm` | `a_ba` | 169 | 3 (`plpause1`, `torchl`, `xbowr`) | 10 carriers, 14,347,708 bytes | 2,175,232 |

| Root | New chain | Exact | Inherited | Worst inherited assembled drift |
|---|---|---:|---:|---:|
| `pfd0` | `pfd0 > srn_an_df > a_fa > …` | 168 | 4 | 1.9×10⁻⁸ m |
| `pfd2` | `pfd2 > srn_an_df > a_fa > …` | 167 + `2hslashl` | 4 | 1.9×10⁻⁸ m |
| `pmd0` | `pmd0 > srn_an_dm > a_ba > …` | 169 | 3 | 1.5×10⁻⁸ m |
| `pmd2` | `pmd2 > srn_an_dm > a_ba > …` | 169 | 3 | 1.5×10⁻⁸ m |

* Every retained clip is byte-exact to its published owner: keys, values, length,
  transition, raw `animroot` and stored event order.
* The female Large `2hslashl` now uses the authorized Fit clip; its largest assembled
  difference is 25 mm at `lhand_g`, as already recorded and authorized.
* Inherited clips use stock's root name and event order (simultaneous events only).

## Observations

* The compiler sorts simultaneous events into stock order and rewrites orientations through
  axis-angle (largest pre-restoration difference 2.0, a quaternion sign flip). Restoration
  removes both differences.
* Two compiles of the same ASCII decode identically, but differ in 64-bit heap addresses the
  client writes into runtime-only pointer fields. Each library's bytes are pinned by hash;
  recompiling yields a different but equivalent file.

Library hashes (restored): `srn_an_df` `880ebdd3835b758b2cafac706ffd8090e134ff1a0ba7f29aa15c861b633e6336`,
`srn_an_dm` `0c411fe7420579d051404f4d6f83ca825c56ebb174e1e1981b812c6fe380d036`.
Launch receipts and intermediate files remain ignored local evidence under
`.tmp/runtime-optimization/phase2/`.

Not yet checked: client behaviour of unkeyed nodes under a library supermodel (Phase 3
native probe) and visual client review (Phase 7).
