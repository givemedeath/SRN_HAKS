# Phase 9: PhenoMorpher toolkit upfit

The toolkit can now generate and enforce the runtime layout that contract 1.1.0 ships: root > shared
`srn_an_<race><g>` library (or the `srn_fa_h0` posture layer) > installed `a_fa`/`a_ba` chain, with
1K textures. Published assets are not regenerated, and nothing here creates an asset or client approval.
The plan is the dated revision in [plan.md](plan.md). A code review corrected the first draft before
any code was written.

## What changed

| Area | Change | Module |
|---|---|---|
| Enforce | `verify-runtime` runs the runtime layout rules: no private carriers except declared posture layers, at most one pack layer before stock, first installed link `a_fa` (female) or `a_ba` (male), installed chain reaches `a_ba`, library parent by gender plus `restorationSHA256`, shared Fit/Large supermodel, PLT/TGA at most 1024 px. A structural mode needs no game install; a deep mode also checks installed bytes. `adopt-runtime` refuses a staged release that breaks these rules. | `engine/runtime_rules.py` |
| Generate | Motion is fitted once, from the Fit body, over `a_fa`/`a_ba`. The Large root names the same top carrier, so Fit and Large can share one library. `adopt-runtime` gains `baseKind: intermediate`, which drops never-published carriers without a retirement record, and `libraryAnchor`. The release recipe is in the [toolkit README](../../../tools/phenomorpher/README.md). | `engine/retarget_v2.py`, `engine/runtime_release.py` |
| Motion baselines | New consumers resolve the published chain the way the client does. The v13/v14a loaders and `shared_female_native_contract` stay pinned to their historical sources. | `engine/motion_baseline_v2.py` |
| Rig audits | `audit-native` compares a published binary with its source, with quaternions up to sign and float32 tolerances. The ASCII-only `rig_controller_audit`/`rig_pose_audit` stay for retarget sources. | `engine/rig_native.py` |
| F5 necks | Chest–neck and neck–head links. Neck–head uses the `head001` routing alias, is diagnostic only, and is unavailable for Human Fit, which uses installed heads. | `engine/check_connector_surfaces_v16.py` |
| F6 penetration | Penetration now needs only a closed, consistently oriented surface (directed edge uses cancel), so non-manifold seams qualify. | `engine/check_connector_surfaces_v16.py` |
| Sweep | The Phase 6 script is promoted to the `sweep` command, uses v16, and adds the head alias when the pack has one. | `engine/body_sweep.py` |

Also changed:
* `texture_header` raises on formats other than PLT and TGA; previously `inventory` crashed on `None`.
* `load_model` accepts bytes.
* Other records: [superseded Human records](../../phenotypes/human-assets-superseded.md).

### Correction to F6 ([review.md](review.md))
The female parts have no open rims. The female pelvis and the feet carry non-manifold edges where submeshes
meet; every directed edge use still cancels. v15 required a 2-manifold, so penetration was unavailable only
on the links whose opposite part is a pelvis or foot, not "every connector". Male bodies were fully measured.
review.md stays historical.

## Acceptance (managed runs, branch worktree)

| Check | Result |
|---|---|
| `verify-runtime` 1.1.0, structural | passes; 375 textures |
| `verify-runtime` 1.1.0, deep (installed stock) | passes |
| `verify-runtime` 1.0.0 (export of `0866bcaf`) | fails as expected. Private carriers: 18 roots. Chain depth: 18. Stock closure: 18. Fit/Large divergence: 10. Textures above 1024 px: 81. |
| `audit-native`, 8 libraries against their pinned ASCII sources | all pass; worst 3×10⁻⁶° and 5×10⁻⁸ m |
| `anim-library extract-stock` | the key files and 33 model BIFs are frozen as inputs; the 6 stock models match the Phase 1 baseline byte for byte |
| Package suite | 133 tests pass |
| Root tools (`test_test_impact`, `test_ci_scope`, `test_ci_result`) | 48 tests pass; catalog regenerated |

### Sweep rerun on 1.1.0
All 20 bodies, static and motion (12 clips), in three managed jobs. Every job exited 0 with its inputs
unchanged. Compared with the Phase 6 sweep of the same release:

| Item | Result |
|---|---|
| Motion, geometry, measurements, minimum-gap audit, surface distances | identical to Phase 6 |
| Penetration directions measured before | 846, values identical (only the limitation text changed) |
| Female pelvis/foot penetration (F6) | 85 directions now measured on the 10 female bodies; 6 stay unavailable on `pfd2` (below) |
| Neck links (F5) | chest–neck measured on all 20 bodies; neck–head measured on 18, unavailable on Human Fit (installed heads) |
| Neck links against the Human donor | chest–neck measured on 10 of the 16 non-Human bodies; unavailable on the Elf, Troll and Orc Fit bodies, whose neck lineage differs. Neck–head measured only on the 4 female Large bodies; elsewhere the head mesh count or lineage differs |
| Penetration overall | 1,025 of 1,040 directions measured |

The 15 unavailable directions are two asset findings. Both are diagnostic only; no asset changes.
* **`pfd2` pelvis seam:** 4 vertex pairs where `pelvis001p1` meets `pelvis001p3`, near the right hip, are
  19–27 µm apart instead of exactly coincident. That leaves 6 unbalanced edges, so penetration against
  the pelvis is unavailable for chest–pelvis and both pelvis–thigh links (self and donor). `pfd0` shares
  all 133 seam vertices exactly. The crack is far below visible size, and the check does not weld.
* **Male `head001` aliases:** the 9 male heads carry two 5-edge open loops at the eyes of the
  `head001g` mesh, so neck–head penetration is unavailable on them. The female heads are closed.

Motion values are unchanged from Phase 6: the Elf male `walk` shin–foot clearance is up to 0.6 mm worse
than the scaled donor, and the shorter bodies' soles dip up to 3.4 cm lower in motion than the donor's.

## Ledger bindings (local `.tmp`, machine-local)

| File | SHA-256 |
|---|---|
| `runtime-bindings/upfit-001.json` (Python, Blender, NWN; tools root on F:) | `793cc8475ca3aa95637741c708a8b632a680f64273821dffdc69f700af84dd99` |
| `runtime-bindings/pheno-migration-001.json` | `ed532dd60b9182e7a5fc396a9aed0a9d05f9160f71028c864740585c18242bd9` |
| `upfit/launch-extract-stock-001/launch.json` | `ab32be8f480faecd1b9fe813727790a1ecb712625abce632bd3b2b1896910a4d` |
| `upfit/stock-001/stock-models.json` | `3887f7a2690d49cf127e6a7c39a0111aff15aeea6e2b34000a09a0b70e50c16e` |
| `upfit/launch-verify-runtime-110/launch.json` | `a6b395f02aa9cfda868c801f918e334e50dd5e3715283919589cd809e0decac5` |
| `upfit/launch-verify-runtime-110-deep/launch.json` | `2e22f94a520ab91264f520457ffaa1ee59aeea543b5ba976d22c6ea6730da852` |
| `upfit/launch-verify-runtime-100/launch.json` | `0bb178c725499b1930f1fd242326db3a39ae1a816afcebb957c2d901f9804d3b` |
| `upfit/library-ascii/provenance.json` (8 copies, each equal to its restoration-plan pin) | `ea388610a8f9e7b0850486e9cbc1228402bfa91e2fd046d57a22727341662d97` |

| `upfit/launch-sweep-1/launch.json` (`pfd0 pmd2 pfe2 pme0 pfo0 pmo2 pfg2`) | `e98a916543a3d62f73b6bc38e7eec8e0be7e7633f5158559fb88b896fc39d37e` |
| `upfit/launch-sweep-2/launch.json` (`pfd2 pmd0 pfe0 pme2 pfo2 pmo0 pmg2`) | `b91d3ed6f750c3c8079d8eda2cbff461a20d125103b0eafc43c28713ad4ba158` |
| `upfit/launch-sweep-3/launch.json` (`pfh0 pmh0 pfh2 pmh2 pfg0 pmg0`) | `d88d58069b6204cb95bc382d8054775adaec2f22f0ce33bfb462e18a55655172` |

The `audit-native` launches are `upfit/launch-audit-native-<lib>/launch.json`, one per library. Sweep
outputs are in `upfit/sweep-{1,2,3}/<prefix>.json`.

## Limits
* Motion connector checks still use the 13 v13 links. The neck links are standing-only.
* Human Fit neck–head needs the installed stock heads, so it is unavailable in the pack-only sweep.
* The `retarget_v2` → client compile → `build` path is covered by unit fixtures, not yet by a real new body.
* The 1.1.0 contract bytes are unchanged, so female `2hslashl` authorization becomes a structured field only
  in the next contract version.
