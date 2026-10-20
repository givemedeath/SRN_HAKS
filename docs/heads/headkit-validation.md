# Headkit extraction: validation and limits

The fresh [operator runbook](head-generation-toolkit.md) is the supported entry point. Portable numeric evidence and exact reviewed hashes are in [headkit-validation.json](headkit-validation.json); source adoption is recorded separately in [headkit-source-adoption.json](headkit-source-adoption.json). Operational receipts, local bindings, reference images and models remain ignored and durably backed up.

| Check | Evidence |
|---|---|
| Default generation profile | Frozen actual #74 graph/settings, also used by #73; single-image checkpoint and paired geometry/appearance inputs |
| Alternate complex-head profile | Corrected attempt51 four-view geometry/front-only texture graph, distinct multiview checkpoint and20° rig; view-order/common-frame regressions |
| Bob #73 | Imported reviewed20,000-triangle UV mesh; closed physical shell, no zero-area faces/winding conflicts; reconstructed1K PLT bytes exact; sanitized native corner/normal/UV roundtrip |
| Undercut #74 | Same checks on its own20,000-triangle source and annotations; reconstructed1K PLT bytes exact |
| Fresh native packaging | Actual isolated NWN:EE compile of #74 through the reusable runner; four stale tail bytes zeroed, other bytes unchanged, independent decoded geometry verified; HAK contains exactly MDL+PLT |
| CPU rendering | Actual generated2K appearance on #74 UV mesh; clay, color-only and material-lit smoke, four threads, no GPU or AO |
| Synthetic repair/reduction | Closed shell bypassed Alpha Wrap; collision-blocking QSlim reached120 triangles, topology/crossings and declared sampled-error gates passed |
| Synthetic UV | Connected charts; geometry retained; no degenerate/overlapping UV faces at4K/2K/1K; useful coverage measured rather than packer utilization |
| Synthetic 4K bake | Full4K CPU bake completed, then2K/1K BOX derivatives; raw coverage/fallback/clipping counts retained |
| Unit coverage (38 tests) | Input alignment/reflections/clipping gates, profile/checkpoint/view order, shared detector crop, saved-shape hashing, trilinear sampling, padding/opaque black, palette eligibility, accessory-preserving tone matching, interrupted/duplicate requests, path escapes, stale outputs and serialization-failure receipts |

The retained-head replay **does not recompute generation, reduction, tones or semantic ownership**. It imports the accepted meshes, fits and reviewed layer/shade data honestly. The new packaging output is diagnostic evidence, not a replacement production asset or a new client acceptance. Historical #73/#74 surface deviations exceeded the old0.4% research gate and were visually accepted; this extraction does not rewrite those results.

No fresh GPU generation was submitted, and the newly named ComfyUI adapters were not installed into or used to restart the shared instance. Adapter installation/restart and an operator-reviewed trial remain prerequisites for a first live use of the extracted toolkit. The multiview graph is retained from a successful historical route; the newer smooth-clay preparation has not been validated end-to-end with it.

The initial generic profile intentionally rejects transformed/multiple-primitive/rigged GLBs. It does not claim automatic anatomical repair, universal race support, perfect semantic masks or automatic production readiness. A numerical pass never substitutes for the prescribed clay, texture, channel, fit and in-game review.


## PR review hardening (2026-10-20)

- Appearance request preparation rejects missing/rejected/stale generated-clay approval before staging. Approval binds both the raw mesh and saved-shape hashes; input-reference review alone is insufficient.
- Runner decisions persist as immutable hash-pinned reviews in state. Pending/rejected/stale reviews block consumers, including cached native packaging through transitive dependencies. Tests include restart, changed review bytes and mismatched receipt bindings.
- The processing example/default now produces 2048 and 1024 pixel renders, actual BOX-filtered texture derivatives, native-resolution labeled sheets and atlas images. Pillow processing stays in bundled Python; Blender needs no added image-library dependency.
- **47 focused toolkit tests pass**, plus **18 dependency-catalog regressions**. The catalogue was regenerated for the new review-image helper.
- An actual shared-launcher CPU `render` stage used the retained #74 20,000-triangle UV mesh and generated material maps. Front-view clay, color-only and material-lit renders passed at both 2048 and 1024: **6 frames, 6 sheets, 8 atlas images**, four threads, **51.0 seconds including evidence processing**, no GPU. Every emitted image hash and dimension was independently verified. This is a front-view integration smoke, not a new all-angle visual acceptance or production replacement.
- The initial direct Blender smoke failed because Blender lacked Pillow; that failed receipt is preserved. The subsequent full runner smoke passed after moving atlas/sheet work to bundled Python.


Further provenance/concurrency review: **56 focused toolkit tests pass**, including nine new regressions for missing/unrelated/conflicting replay pins, changed artifacts during replay, resolved path aliases, and deterministic release/submission interleavings in both directions. The dependency-catalog consistency check passes. A fresh shared-launcher CPU replay of retained #74 binds all five consumed roles and reproduces its 20,000-triangle closed source, PLT and sanitized native bytes exactly; it performs no generation, repair, compilation or GPU work. Model release now requires the same reconciled ledger as submission, and holds that lock through both the idle check and `/free` request.


Xatlas dependency-boundary review: UV unwrapping now uses the common byte-pinned library loader with the full local bindings, enforcing the declared durable tools bank before importing xatlas. **60 focused toolkit tests pass**, including rejection of external/prefix-sibling directories, changed dependency bytes and unexpected cached module paths. A fresh shared-launcher CPU unwrap of the retained 120-triangle synthetic donor passed: ordered corners and normals unchanged, no 2K/4K UV overlaps, 2K mapped coverage 0.5928010941, 6.719 seconds. No GPU or production assets were involved.


Collection/render-example/imported-shade review: **69 focused toolkit tests pass** plus the dependency-catalog consistency check. Every configured render map role is now declared as a pinned example input. Terminal collection receipts are pinned in the ledger and reused only after verifying their recorded evidence, inputs and outputs; history/memory/receipt files use exclusive creation, and legacy/partial evidence is preserved. Regressions cover successful, failed and failed-validation recollection, tampering, and original-directory binding. Native export rejects shade255 and non-1K/non-grayscale shade inputs while preserving valid0/254 shades and accessory layers. A fresh shared-launcher CPU replay of retained #74 still reproduces its 20,000-triangle source, PLT and sanitized native bytes exactly; no GPU or production assets were changed.


Ownership image-mode review: imported labels now require eight-bit `L` images in quantization, native export, tone matching and source-view ownership projection. RGB, palette-indexed and higher-bit images are rejected before label conversion; valid0..9 IDs remain unchanged. **74 affected tests pass** plus dependency-catalog consistency, with explicit non-L regressions and an all-ten-channel preservation check. A fresh shared-launcher CPU replay of retained #74 still reproduces the native/PLT bytes exactly, without GPU work or production changes.


Imported-ownership binding review: imported1K and4K masks now require explicit review tied to the active UV mesh SHA in every consuming runner path, including tone, palette and direct runtime-shade export. When the UV mesh is derived, consumers record the approved unwrap dependency so cached outputs cannot bypass a revoked UV review. **78 affected tests pass**, plus dependency-catalog consistency. A fresh shared-launcher CPU export of retained #74 reproduces its approved PLT bytes exactly using reviewed imported ownership; all inputs, outputs and durable copies were hash-verified. No GPU or production assets were changed.


Export/texture-lineage review: Comfy export requires explicit approval of the exact pinned export source before staging. Tone inputs/output must be actual4K before2K/1K derivatives. Imported color, shade and render-atlas roles now require approved exact texture and active UV-mesh hashes; derived UV dependencies retain their review gates on reuse. The earlier configuration validation ran1,776 helper tests successfully with two explicit unavailable-fixture skip events; after the lineage changes, **86 focused headkit tests pass** plus catalogue consistency. A fresh shared-launcher CPU export of retained #74 reproduces its approved PLT exactly with reviewed shade/ownership inputs. Inputs, outputs and durable copies are verified; no GPU or production assets changed.
