# Diagnostic skin intensity staging

`target_part_stage.py` accepts `skinIntensityInputs` alongside original `materialRoles`:

```json
{
  "materialRoles": {"0": "skin"},
  "skinIntensityInputs": {
    "receipt": {"path": "ABSOLUTE_C1_LIGHTING_RECEIPT", "sha256": "PINNED_SHA256"},
    "strength": 0.65
  },
  "aoStrength": 0
}
```

The input must be a recorded `target-skin-lighting-c1-padding-diagnostic` with one of its complete declared independent strengths. This path requires working geometry, skin-only original ownership and a part outside the target's fixed garment owners. It rejects `garmentFaceInputs`, runtime geometry, repeated treatment, changed target/data/maps and unsupported ancestry. It creates a diagnostic stage, without selecting materials or accepting a client result.

`replay_stage_skin_intensity.py` verifies the retained CPU worker input, source arrays, original embedded-map archives and raw bake. It independently calculates surface normalization, every C1 geometry-mask array, ambiguous/protected pixels, deterministic empty-chart padding and every selected intensity byte. A new hash on a modified image or mask cannot substitute for replay. The raw CPU bake is reused; replay performs no new bake or GPU operation.

Only the exact untreated lighting source, an explicit measured three-corner outward normal/tangent exception, and one declared opposite-frame mirror are supported. The exception is reconstructed from the original closed geometry and pinned plan. Its complete conservative level-zero bilinear UV footprint must have zero influence and unchanged original intensity. Mirror topology, P/N/UV/tangents/signs and embedded maps are recalculated through the frozen operation configuration and actual opposite attachment frames. The same original attachment-baked intensity moves with mirrored UVs; mirror lighting quality remains a visual review item.

Historical helper resolution is specific to this optional path. An outdated Python helper pin can resolve only to an explicitly recorded matching snapshot. The receipt's own pinned helper snapshot is preferred; otherwise the snapshot must be unique. The snapshot is never executed. Missing/ambiguous helper snapshots or any changed non-helper pin fail. The new proof records the original path, historical hash and resolved snapshot; originals remain unchanged. Legacy staging keeps its existing strict source checks.

AO strengths 0, 0.15 and 0.35 each start from original color luma plus the independently replayed integer lighting delta, then apply original AO once and truncate to a byte. Strength zero and protected pixels equal legacy original-map AO. Original RGB, normal and ORM maps stay archived and byte-exact; only compiled PLT intensity changes. Roughness and normal-map staging keep their original transport rules.

`audit_target_native_part.py` independently repeats this recipe and geometry ancestry rather than trusting stage proof flags. It compares the actual compiled PLT, normal, roughness and MTR dependencies with the returned effective rows. The audit separately records derived intensity edits and unchanged original RGB/normal/roughness inputs.

Use the verified bundled-tool launcher for replay, stage and audit. For read-only replay, pass a normal stage configuration to `replay_stage_skin_intensity.py --config ... --output FRESH_DIRECTORY`. Final source-to-runtime conversion still needs an explicit current-source revalidation closure. Native/client palette 3/8 edges, stock neck and neighbors, bilateral movement and practical rendering acceptance remain separate gates; the level-zero footprint does not prove engine mip behavior.
