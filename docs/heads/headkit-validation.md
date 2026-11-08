# Headkit extraction: validation and limits

The fresh [operator runbook](head-generation-toolkit.md) is the supported entry point. Portable numeric evidence and exact reviewed hashes are in [headkit-validation.json](headkit-validation.json); source adoption is recorded separately in [headkit-source-adoption.json](headkit-source-adoption.json). Operational receipts, local bindings, reference images and models remain ignored and durably backed up.

| Check | Evidence |
|---|---|
| Default generation profile | Frozen actual #74 graph/settings, also used by #73; single-image checkpoint and paired geometry/appearance inputs |
| Alternate complex-head profile | Attempt51 multiview graph, distinct multiview checkpoint and20° rig, now conditioned by four smooth-clay views for geometry and the four matching detailed views for texture; role, view-order and common-frame regressions |
| Bob #73 | Imported reviewed20,000-triangle UV mesh; closed physical shell, no zero-area faces/winding conflicts; reconstructed1K PLT bytes exact; sanitized native corner/normal/UV roundtrip |
| Undercut #74 | Same checks on its own20,000-triangle source and annotations; reconstructed1K PLT bytes exact |
| Fresh native packaging | Actual isolated NWN:EE compile of #74 through the reusable runner; four stale tail bytes zeroed, other bytes unchanged, independent decoded geometry verified; HAK contains exactly MDL+PLT |
| CPU rendering | Actual generated2K appearance on #74 UV mesh; clay, color-only and material-lit smoke, four threads, no GPU or AO |
| Synthetic repair/reduction | Closed shell bypassed Alpha Wrap; collision-blocking QSlim reached120 triangles, topology/crossings and declared sampled-error gates passed |
| Synthetic UV | Connected charts; geometry retained; no degenerate/overlapping UV faces at4K/2K/1K; useful coverage measured rather than packer utilization |
| Synthetic 4K bake | Full4K CPU bake completed, then2K/1K BOX derivatives; raw coverage/fallback/clipping counts retained |
| Unit coverage (38 tests) | Input alignment/reflections/clipping gates, profile/checkpoint/view order, shared detector crop, saved-shape hashing, trilinear sampling, padding/opaque black, palette eligibility, accessory-preserving tone matching, interrupted/duplicate requests, path escapes, stale outputs and serialization-failure receipts |

The retained-head replay **does not recompute generation, reduction, tones or semantic ownership**. It imports the accepted meshes, fits and reviewed layer/shade data honestly. The new packaging output is diagnostic evidence, not a replacement production asset or a new client acceptance. Historical #73/#74 surface deviations exceeded the old0.4% research gate and were visually accepted; this extraction does not rewrite those results.

No fresh GPU generation was submitted, and the newly named ComfyUI adapters were not installed into or used to restart the shared instance. Adapter installation/restart and an operator-reviewed trial remain prerequisites for a first live use of the extracted toolkit. The multiview graph is retained from a successful historical route (blank-orbit geometry, front-only texture); its current smooth-clay geometry and four-view detailed texture conditioning has had only the unguarded diagnostic GPU run described in [Unguarded multiview trial](#unguarded-multiview-trial-2026-10-22), not a guarded end-to-end validation.

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


Collection/render-example/imported-shade review: **69 focused toolkit tests pass** plus the dependency-catalog consistency check. Every configured render map role is now declared as a pinned example input. Terminal collection receipts are pinned in the ledger and reused only after verifying their recorded evidence, inputs and outputs; matching partial history, memory samples and receipts can resume after interruption, while conflicting evidence is preserved. Regressions cover successful, failed and failed-validation recollection, tampering, and original-directory binding. Native export rejects shade255 and non-1K/non-grayscale shade inputs while preserving valid0/254 shades and accessory layers. A fresh shared-launcher CPU replay of retained #74 still reproduces its 20,000-triangle source, PLT and sanitized native bytes exactly; no GPU or production assets were changed.


Ownership image-mode review: imported labels now require eight-bit `L` images in quantization, native export, tone matching and source-view ownership projection. RGB, palette-indexed and higher-bit images are rejected before label conversion; valid0..9 IDs remain unchanged. **74 affected tests pass** plus dependency-catalog consistency, with explicit non-L regressions and an all-ten-channel preservation check. A fresh shared-launcher CPU replay of retained #74 still reproduces the native/PLT bytes exactly, without GPU work or production changes.


Imported-ownership binding review: imported1K and4K masks now require explicit review tied to the active UV mesh SHA in every consuming runner path, including tone, palette and direct runtime-shade export. When the UV mesh is derived, consumers record the approved unwrap dependency so cached outputs cannot bypass a revoked UV review. **78 affected tests pass**, plus dependency-catalog consistency. A fresh shared-launcher CPU export of retained #74 reproduces its approved PLT bytes exactly using reviewed imported ownership; all inputs, outputs and durable copies were hash-verified. No GPU or production assets were changed.


Export/texture-lineage review: Comfy export requires explicit approval of the exact pinned export source before staging. Tone inputs/output must be actual4K before2K/1K derivatives. Imported color, shade and render-atlas roles now require approved exact texture and active UV-mesh hashes; derived UV dependencies retain their review gates on reuse. The earlier configuration validation ran1,776 helper tests successfully with two explicit unavailable-fixture skip events; after the lineage changes, **86 focused headkit tests pass** plus catalogue consistency. A fresh shared-launcher CPU export of retained #74 reproduces its approved PLT exactly with reviewed shade/ownership inputs. Inputs, outputs and durable copies are verified; no GPU or production assets changed.


Runtime/source/render review: the CLI now matches recorded toolchain, migration, Python, tools bank and configured Blender against the actual verified launcher; stage receipts retain that identity. Request/source snapshots require complete configured Comfy/Pixal implementation-tree membership and bytes, rechecked on submission, collection and terminal reuse. Nonempty render plans must produce every requested size/mode/camera frame before success. **97 affected tests pass**, plus catalogue consistency. A fresh four-thread shared-launcher CPU render of retained #74 produced all6 front-view2K/1K frames,6 sheets and8 atlas images with verified dimensions, hashes and runtime identity. This is render evidence, not new visual/production approval. No GPU job or production change occurred.


Tone-mask fallback review (2026-10-20): a reviewed 1K ownership mask can now drive the 4K tone stage when no 4K mask is supplied. The runner validates the discrete labels, expands by nearest-neighbor filtering, records both source and expanded-mask pins, and retains the approved unwrap dependency when the UV mesh is derived. 100 affected headkit tests and 18 dependency-catalog regressions pass. Coverage includes exact nearest expansion, malformed masks, and rejection after UV-review revocation.


Resumable render and collection review (2026-10-20): textured Blender renders now reject absent, out-of-atlas or degenerate UVs before mesh import; clay-only renders remain available. Production render plans require clay, color-only and material-lit frames at each requested size. A reduced material-mode set is accepted only when explicitly marked `diagnostic: true`, and that diagnostic status is recorded with the render receipt. Comfy ledger locks use OS-managed exclusion: named Windows mutexes and Unix `flock` both release automatically when a process terminates, avoiding abandoned PID files. Collection resumes verify and reuse matching history and memory-sample files, and can republish an already-written matching collection receipt after interruption without overwriting evidence. New regressions cover missing/flat UVs, incomplete production modes, terminated lock owners, and partial collection recovery.

Checkpoint-loader provenance review (2026-10-20): each prepared request now freezes the Comfy loader category, selected filename, resolved-path identity and reviewed bytes. Immediately before dispatch, the installed adapter asks ComfyUI's own `folder_paths` resolver for the exact loader path and rehashes that file. A duplicate filename resolving from another model root, changed bytes, or an outdated adapter is rejected as a preflight failure before `/prompt`; it does not consume a generation attempt. Install the current adapter and restart ComfyUI before preparing model-backed requests, and prepare again after changing model search paths. Regressions cover same-name files in separate roots, changed selected bytes, unsupported loaders and no-submit attempt accounting.


## Controlled startup replaces live-object inspection (2026-10-21)

Later integration: [headkit/itemkit reconciliation](../items/headkit-integration.md)
retains controlled startup and restores the item branch's loaded-code checks.
The following paragraph describes the original 2026-10-21 revision.

The active runtime contract now uses an offline frozen deployment manifest and a controlled process session (runtime schema 3). The prior source/object verifier and all of its research cases remain available at commit `7d2259fef471406343e0dba0db66fb82f7f71f6c`; an exact byte archive is retained with the ignored controlled-startup evidence. Historical validation entries above describe their original revisions and do not certify the replacement. The new suite exercises startup, changed source/runtime/settings, session restart, unmanaged-server refusal, occupied-port refusal, isolated script import and request preflight using CPU fixtures and fake servers. Geometry, UV, appearance, review, PLT, loader-model and native-export gates are retained. No real ComfyUI adapter installation, server restart, GPU job or production-asset change is part of this migration. A first live controlled deployment remains an operator step after the intended deployment and scheduler endpoint are available.

## Unguarded multiview trial (2026-10-22)

A new male Troll head (`troll-male-01`) gave the first GPU run of `pixal-multiview-v1` with smooth-clay geometry roles and four detailed appearance roles. Prompts came from this branch's `comfy.compile_graph`, and inputs were staged as `request_stage` stages them. Generation ran directly against a plain local ComfyUI. **This was not the guarded toolkit path:** there was no controlled startup, ledger, request receipt or `submit`/`collect`. The installed `srn_headkit` adapter predates `managed_startup.py`, and controlled startup still has not been run live. No production, native or client approval follows from this trial.

| Step | Result |
|---|---|
| Design | Flux.2 dev (turbo LoRA) front design, user-approved. Flux.2 could not keep the asymmetric cyberware, crest height or horns consistent across separate views or a turnaround sheet, so its views were rejected. |
| References | Bootstrap only: a single-image Pixal3D mesh and texture of the approved design (MoGe FOV 32.2°). Its untextured rear crest was recolored in the atlas by a 3D-selected, color-gated mask. Blender 4.0 rendered clay and textured views at 0/90/180/270° with one 20° rig. `prepare_multiview` passed: clay/detail IoU ≥ 0.9999 and identical cranial metrics. Landmarks are projections of shared 3D points; the crown sits at the crest base. |
| Geometry (370 s) | Shape and every recorded feature match the inputs from all four sides. The surface is faceted and crumpled, with horizontal banding on the rear skull and neck. Approved only to exercise the appearance stage. |
| Appearance (362 s) | The rear is textured from the back view; skin, horns, bands, rings and scar transfer. The cybereye lost its red lens, the rear crest stripe faded and the tattoos are faint. Review used a remesh/decimate/unwrap bake, not the toolkit export path. |

The references are renders of the bootstrap head. This trial therefore checks the new role wiring and reconstruction from consistent views; it does not show that multiview outperforms single image on independently authored four-view references. The bootstrap, failed bootstrap appearance and multiview submissions were not recorded in a headkit attempt ledger. Generated assets and receipts remain ignored scratch evidence.
