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
| Unit coverage | Input alignment/reflections/clipping gates, profile/checkpoint/view order, shared detector crop, saved-shape hashing, trilinear sampling, padding/opaque black, palette eligibility, accessory-preserving tone matching, interrupted/duplicate requests, path escapes, stale outputs and serialization-failure receipts |

The retained-head replay **does not recompute generation, reduction, tones or semantic ownership**. It imports the accepted meshes, fits and reviewed layer/shade data honestly. The new packaging output is diagnostic evidence, not a replacement production asset or a new client acceptance. Historical #73/#74 surface deviations exceeded the old0.4% research gate and were visually accepted; this extraction does not rewrite those results.

No fresh GPU generation was submitted, and the newly named ComfyUI adapters were not installed into or used to restart the shared instance. Adapter installation/restart and an operator-reviewed trial remain prerequisites for a first live use of the extracted toolkit. The multiview graph is retained from a successful historical route; the newer smooth-clay preparation has not been validated end-to-end with it.

The initial generic profile intentionally rejects transformed/multiple-primitive/rigged GLBs. It does not claim automatic anatomical repair, universal race support, perfect semantic masks or automatic production readiness. A numerical pass never substitutes for the prescribed clay, texture, channel, fit and in-game review.
