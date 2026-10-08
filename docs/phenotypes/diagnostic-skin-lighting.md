# Diagnostic baked skin lighting

`bake_target_skin_lighting.py` derives an **unselected diagnostic** skin intensity atlas from a pinned fitted donor. It exposes relief already present in geometry, authored normals and the original normal map. It cannot invent absent anatomy, accept a donor's orientation, repair normal defects or establish native/client material quality.

Use it only after reviewing the untreated source and the ordinary AO0/0.15/0.35 comparisons. Strong painted contrast is an explicit art direction for the female pass, not an automatic default for every phenotype. Keep the original GLB/BIN, position/normal/tangent/sign/UV/index attributes and all embedded maps unchanged. This helper writes separate atlas variants and receipts; it does not write PLT/MTR/TGA/native body resources or change `target_part_stage.py`.

## Execution

Discover the bundled workspace Python and verified shared toolbank/migration receipt for the current worktree. Run the controller through `launch_shared_tool.py` with a fresh target-specific output directory. The controller uses the same verified launcher for two factory Blender CPU workers: a camera-free linear diffuse bake, then emission-only palette previews. Pillow stays in bundled Python; no Blender package/addon installation is required.

```powershell
& $BundledPython -B tools/phenotypes/launch_shared_tool.py `
  --toolchain $Toolchain --migration-receipt $MigrationReceipt `
  --tool python --output $ControllerLaunchOutput -- `
  -B tools/phenotypes/bake_target_skin_lighting.py `
  --config $LightingConfig --output $LightingOutput `
  --toolchain $Toolchain --migration-receipt $MigrationReceipt
```

The configuration is version2, kind `target-skin-lighting-diagnostic`, `diagnosticOnly: true`, and working coordinates. It pins the supported target contract, exact part/fitted GLB/geometry receipt, explicit diagnostic normal review, stock/neighbor inputs, installed palette and human-approved style source. Each active source material must declare skin or garment; garments are legal only on the target's declared fixed owners, and stock-exact chest/pelvis owners must include cloth. Combined skin/cloth materials need a separately reviewed ownership adapter; this diagnostic does not infer ownership from colors.

Controls freeze a2048 atlas, CPU device, target-world bind frame, explicit neutral AREA lights, energies/sizes/positions, world strength, samples/seed/margin and surface-area-weighted normalization. The authored N/T/W basis and original normal pixels at strength1 drive diffuse **DIRECT** lighting with color/indirect disabled. No camera or source albedo contributes to the light field. The controller converts Blender image rows once to top-left; a disposable host mesh uses V=1-rawGLTFV once. Source accessors remain exact.

Protected connector/neck planes require measured origins and unit normals. Entire triangles crossing their protected bands remain untreated; adjoining bands fade the effect. Garment ownership and a1–4pixel zero guard take precedence over overlapping skin UVs. Unknown/wrapped UVs and nonfinite controls fail. Each strength starts from the untreated byte intensity independently: normalize linear field by sampled surface area, bound shade darkening/brightening, multiply by explicit strength and influence, round to byte, and restore all blocked pixels exactly. Do not silently stack AO or a prior lighting variant.

## Evidence and remaining gates

The output includes original map copies/hashes, exact arrays, raw linear bake, `linear-lighting-and-masks.npz` (`rawLinearRGB`, `normalizedLuminance`, `influence`, `coverage`, `garment`, `protected`), per-strength intensity and palette3/8 images, emission-only surface views, executed helper copies and verified launch/worker receipts. `lighting.json` binds target/rig/part/geometry/original parent and every derived variant. `test_target_skin_lighting.py` covers stale/cross-target inputs, source normal strength, garment ownership, CPU bounds, UV origin, overlap/crossing protection, independent strengths and unlit rejection.

Bind-space paint travels with animated limbs and can conflict with live lights or bilateral mirroring. Conservative UV/protection masks can produce visible lines or bands; source map preservation does not prove derived filtering/mips are clean. Review literal native palette layers, normal/roughness transport, stock female neck and all visible neighbors under palettes3/8, neutral/directional illumination, ordinary/HQ shaders, motion and equipment. Any padding, smoothing, calibration or AO composition becomes a fresh explicitly bounded descendant with protected-pixel/attribute lineage and repeated affected checks.

The current female arm diagnostic successfully adds unlit muscle relief, but direct review found thin atlas lines and conspicuous high-strength connector transitions. Its independently recorded source-byte protections pass; its material selection, anatomy, native compilation and client acceptance remain open. See the [female runbook](human-female-purposebuilt-runbook.md) and current checkpoint for delivery gates. Raw generation/bake outputs remain local outside Git.

## Proposed staging interface

`skinIntensityTreatment` is a **proposal only**. The stage tool now rejects unknown controls and does not consume that key; never insert it into a staging configuration before implementing and validating an explicit lighting adapter. A supported adapter must verify the exact target/rig/part, working parent and any single runtime-conversion lineage, lighting/ownership receipt hashes, chosen intensity image/hash, original map/attribute pins and protected masks. It must replace skin shade bytes only, keep cloth and original normal/ORM inputs exact, use explicit AO0 unless a separate composition was reviewed, independently decode the PLT/layer serialization, and record the effective material descendant separately from original compiler inputs. No diagnostic receipt grants selection, final approval or publication authority.

## Fresh C1 mask and chart-padding descendants

Keep the original `lighting.json`, raw CPU bake and executed helpers immutable. `derive_target_skin_lighting.py` consumes a pinned original lighting receipt plus its original configuration and writes a fresh `target-skin-lighting-c1-padding-diagnostic` descendant. Run it through the same verified bundled-Python launcher with `--config`, `--output`, `--toolchain` and `--migration-receipt`.

The controller rasterizes actual attachment-local barycentric geometry at raw GLTF texel centers. Measured strict connector bands retain exactly zero influence; the adjoining fade follows C1 smoothstep. Explicit overlapping geometry or authored-normal differences, cloth, unknown texels and the zero guard take precedence. It reconstructs the original raw light field with a surface-area normalization using top-left texel-center bilinear sampling (`uW−0.5,vH−0.5`); the historical first receipt's endpoint sampler remains untouched.

A second, separately declared operation pads only empty chart texels from covered, unprotected skin seeds. Deterministic eight-neighbor propagation travels at most the configured bounded radius, never crosses forbidden texels, and saves original seed indices and step counts. Surface dark/light bounds apply to mapped skin; unused padding may change more because it copies a declared treated skin value. Strength0 retains every untreated byte. Padding changes neither original maps nor UV/face ownership.

`c1-mask-and-padding-lineage.npz` records `influence`, `coverage`, `garment`, `ambiguous`, `strictZero`, `protected`, `ownerFace`, `positionLocal`, `authoredUnitNormal`, `normalizedLuminance`, `paddingSourceTexelIndex`, `paddingSteps` and `paddingDestination`. A consumer must independently reconstruct these fields, verify every original source/target/rig/neighbor pin and both operations, and retain known-defect samples at exact zero. `test_skin_lighting_atlas.py` covers C1 endpoints, true texel centers, geometry-based bands, inequivalent overlap protection, cloth precedence, deterministic bounded padding and untreated identity.

The female upper-arm C1/padding diagnostic reduced fine chart lines in all16 directly reviewed emission previews and lowered intensity discontinuity across a common geometric UV-seam cohort. A broad upper-cap tonal transition remains, especially at the highest strength. No strength is selected; stock-neck/common-style palette3/8, cumulative neighbor/motion, native materials and actual-client tests remain pending. The fresh receipt has two operations, so a staging proposal that accounts for only the first bake cannot silently consume it.

For literal approved-reference color projection, see [the separate diagnostic interface](diagnostic-reference-color-reprojection.md). It addresses reference RGB rather than multiplying another diffuse/AO treatment.
