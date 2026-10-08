# Literal reference color reprojection diagnostics

The installed Pixal3D/Trellis orthographic path conditions generated geometry and texture with learned features. Its `BakeTextureFromVoxel` node samples generated voxel PBR, rather than projecting literal approved photographs. `ApplyTextureToMesh` normalizes UVs and may recompute normals/tangents. The additive CPU helpers here provide a separate **unaccepted diagnostic** route onto existing authored UVs, retaining every original GLB/BIN/map/attribute byte.

`orthographic_reference_projection.py` freezes the installed generator's Z-up cardinal camera bases, rasterizes actual surface depth/face IDs and measures matched reference silhouettes. Its mathematical front is world−Y, independent of any target's anatomical anterior. Review the semantic permutation, all six whole-object camera projections, common normalization and actual anatomical orientation separately. An attractive cardinal sheet or high silhouette IoU cannot waive outlier surfaces or garment registration errors.

`reference_color_reprojection.py` rasterizes unchanged UV texel centers to actual geometry and projects those positions into four pinned cardinal RGB/alpha images. It requires camera-frame depth agreement, front-facing geometric incidence, eroded alpha support and valid image bounds. Inequivalent UV overlaps, occluded/grazing/unseen samples and backgrounds remain unresolved. Eligible colors are bilinearly sampled and blended in linear RGB, with explicit cross-view color disagreement producing original-color fallback. This diagnostic color threshold does not classify skin versus charcoal cloth or grant garment-boundary approval.

`bake_reference_color_diagnostic.py` takes a target-bound preparation containing exact successful generation, source model, approved references, normalization, camera/depth study and controls. It writes a sidecar RGB image plus face/position/view/pixel/depth/incidence/weight/confidence lineage. The source model and original base-color, normal and ORM remain exact. It does not infer a camera warp, normalize UVs, edit artwork, submit a GPU job, pad charts, multiply AO/lighting, write native assets or change staging.

Discover the bundled Python and current verified toolbank/migration receipt. Execute through `launch_shared_tool.py`, with fresh target-specific output and launch directories:

```powershell
& $BundledPython -B tools/phenotypes/launch_shared_tool.py `
  --toolchain $Toolchain --migration-receipt $MigrationReceipt `
  --tool python --output $ProjectionLaunchOutput -- `
  -B tools/phenotypes/bake_reference_color_diagnostic.py `
  --config $ProjectionConfig --output $ProjectionOutput `
  --toolchain $Toolchain --migration-receipt $MigrationReceipt
```

The configuration is version1, kind `literal-reference-rgb-diagnostic`, `diagnosticOnly: true`, and declares `part`, pinned `studyReceipt`, `generationReceipt`, `targetContract`, `depthToleranceSourceUnits`, `minimumGeometricIncidence`, `alphaErosionPixels` and `crossViewDifferenceShadeBytes`. The initial diagnostic requires one common 2K source color atlas, white base-color factors and UV0. Arbitrary multi-material layouts and color factors require verified support before use. The receipt declares `generator-source` coordinates; it cannot be consumed as an accepted working/runtime geometry receipt.

The lineage archive includes source UV coverage/protection/ambiguity, source face and barycentric position, all four source image pixel coordinates, depth errors, geometric incidence, eligible view masks and weights, highest-weight view, confidence, cross-view conflicts, accepted samples and original fallback. Original encoded/decoded RGB copies and exact source corner arrays are retained. CPU emission previews compare original and projected atlases from all four cardinals and four diagonals under fixed matching cameras; those views isolate texture behavior and do not prove actual engine material parity.

Before any use in production, directly review silhouette and landmark residuals, approved garment cuts and skin/cloth boundary agreement. Four cardinals omit hidden caps, undersides and under-cloth/groin surfaces. Unresolved fallback may retain unwanted generated paint. Projection can replace registered visible paint and preserve approved painted shadows, but it cannot remove actual strap/ridge geometry or relief in the original normal map. A separately bounded geometry/normal descendant, when warranted, reopens all affected checks.

The female chest trial uses exact approved midpoint-v10 references against chest-v4 without a registration warp. Its source contour errors remain disclosed; no source, garment ownership, skin palette or candidate is accepted by the diagnostic. The pelvis study additionally found that high IoU can conceal a thin separate lower-cut surface extending beyond the intended body. Such measured geometry is an independent gate before texture work.

Any future staging adapter must consume exact source/target/rig/part and chosen sidecar/lineage pins, reviewed ownership and padding descendants, and preserve source normal/ORM/UV/N/T/W/index data. It must reject unsupported controls, decode native material/layer serialization and repeat stock-neck/common-style palette3/8, cumulative motion/equipment, ordinary/HQ lighting, actual-client and final approval checks. See [baked lighting diagnostics](diagnostic-skin-lighting.md), [the reusable plan](purposebuilt-phenotype-plan-template.md) and [female execution runbook](human-female-purposebuilt-runbook.md).

## Exact visibility and role-safe region descendants

The first four-camera trial rejects large RGB differences conservatively. In the female chest diagnostic, most conspicuous visible orange fallback islands came from cross-view color disagreement, while many other unresolved atlas texels had no facing, unobstructed cardinal support. Neither an unsampled face nor a finite-view occlusion result proves an inner shell. A separate read-only audit must retain exact source face/barycentric position and individual camera blockers before revising projection policy. The current target evidence uses sourcepoint BVH escape rays, with a pinned epsilon and geometric-incidence floor; all such visibility claims remain scoped to those points and four directions.

`reference_color_semantics.py` proposes conservative reference-specific roles from the literal approved RGB/alpha: warm skin, neutral/cool charcoal, and unknown boundary/background. Dark warm muscle shading remains skin. A bilinear photo sample is known only when all four supporting source pixels have the same nonzero role. These thresholds and role-mask images require direct review; they do not grant production garment ownership or authorize a garment cut.

`reference_color_region_ownership.py` computes camera decisions from original interpolated authored unit normals in common object coordinates. Its fixed front/left/back/right camera order and positive incidence raised to a frozen bounded power determine the strongest eligible view. When every supported view has the same known skin or cloth role, their literal colors blend continuously in linear RGB. Mixed roles or unknown secondary roles select one exact known primary camera, with no skin/cloth cross-blend. An unknown primary or absence of positive eligible weight retains the original color. Object-space decisions agree across identical geometry/normals at separate UV charts; a one-camera boundary can still expose disagreement in reference garment registration and must be reviewed from diagonals.

`derive_reference_color_regions.py` takes a fresh version1 `literal-reference-rgb-region-descendant` configuration with `diagnosticOnly: true`, pinned `parentProjection`, `rayReceipt`, `semanticStudy`, `anglePower`, `paddingRadius`, `paddingMaximumSourceDistance`, `paddingMaximumNormalDegrees`, and `roleMasksDiagnostic: true`. The original successful generation, source model, approved artwork, camera study, normalization, UV coverage/protection and ray/source association remain pinned. Its output is a separate derived RGB image with exact source roles, eligible cameras, owner/mode, blend weights, incidence and padding seed/step/ambiguity lineage. The original GLB/BIN/base-color/normal/ORM/UV/N/T/W/index bytes remain unchanged.

Execute through the same verified Python launcher, using a new output and launch directory:

```powershell
& $BundledPython -B tools/phenotypes/launch_shared_tool.py `
  --toolchain $Toolchain --migration-receipt $MigrationReceipt `
  --tool python --output $RegionLaunchOutput -- `
  -B tools/phenotypes/derive_reference_color_regions.py `
  --config $RegionConfig --output $RegionOutput `
  --toolchain $Toolchain --migration-receipt $MigrationReceipt
```

Bounded chart padding is a second explicit operation into empty atlas texels only. It starts from accepted known-role mapped seeds and stops on covered, protected, or ambiguous destinations. Every competing nearest propagated seed must have the same role, sufficiently close original source positions, and compatible authored normals; disagreement blocks that destination and subsequent propagation. The radius, source-distance and normal-angle bounds are frozen. Covered unseen/unknown geometry is never filled. This helps empty chart filtering but cannot repair original covered edge pixels, photograph registration, or raised clothing relief.

The single female chest region descendant resolves135,889 of140,084 original RGB conflicts under its proposed role masks. Its24 source/repaired/role cardinal and diagonal emission images were directly reviewed. Broad orange fallback islands are largely removed and approved painted muscle shading is preserved, but thin generated inner rear strap traces, broken outer strap boundaries and shoulder/side cut mismatches remain selection blockers. No garment boundary, role mask, camera region, material, anatomy, native package or client is accepted by this diagnostic. Changes to covered residual defects require separately measured face/barycentric/reference-pixel causes and a new reviewed descendant; a global unseen fill or nearest-color copy would conceal unresolved evidence.
