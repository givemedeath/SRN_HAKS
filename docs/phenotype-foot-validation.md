# Human male feet: completed offline validation

This is the original standalone offline foot validation record. Its later-client
and stop-after-cleanup statements describe that task's historical scope. Both
selected v5 feet subsequently passed native and full-body practical client
checks; see [the current delivery](phenotype-human-male-delivery.md) and
[checkpoint](phenotype-goal-checkpoint.md). Do not treat the old restrictions
below as current instructions.

Updated 2026-10-03. Both orthographic v5 feet are selected for the later bulk
phenotype client pass. No NWN access, new native compilation or client test was
performed in this foot task. Older foot/material client evidence cannot validate
this geometry. Stop after the requested [space assessment](phenotype-worktree-space-assessment.md).

All receipt paths below are relative to
`D:/srwt/codex/f0b3/SRN_HAKS/output/phenotypes/purposebuilt-foot-orthographic-v5`.
Selection: `selected-offline-v1/selection.json`, SHA256
`9e077056214e6fee4e8692db38b97c2fca9786cda1d476416325dea80b751db4`.
Final independent audit: `final-offline-audit-v1/audit.json`, SHA256
`5c66aaaaa9e716006d393c625a64153c32a0d5d1b7b9d5c050b4808e800792e9`.

## Completed evidence

| Gate | Actual evidence |
| --- | --- |
| References | Six complete centered, shared-scale orthographic views; 19 reference/prompt/provenance files copied exactly to the user's `reference_images` folder. |
| Model generation | One completed six-view Comfy job `89c4f5aa-dcdf-4d6f-ad0c-72951d033c6a`, four preserved masters and frozen workflow/source dependencies. |
| Anatomy | Untouched and final color/clay top, sole, side and underside review: five toes, no extra underside digit. Minor generated forefoot/sole irregularity remains. |
| Stock fit | Proper Z180 rotation, positive uniform length fit, stock sole datum and explicit +3 mm forward placement. No rig/animation/height changes. |
| Hidden overlap | Local ankle taper above +5 mm; crown radius 65%, maximum movement 15.503 mm. Lower foot P/N/T and all UV/maps remain exact outside the declared scope. |
| Final geometry | Both complete serialized audits: 49,938 triangles, one closed component, zero crossings, boundary/nonmanifold/winding/degenerate/bad-vertex-link defects. |
| Authored attributes | Retained ordered P/N/UV/T exact through contact repair/mapping; local taper transports normals/tangents explicitly. 263 inherited negative normal corners on small faces remain, with no all-negative face. |
| Patch mapping | Seven measured patches; actual UV-derived tangent agreement >0.99999996. 84 boundary color samples: max 6.53/255, mean 0.32. Original maps exact. |
| Opposite side | Actual ordered geometry/normal/UV/tangent mirror proof in stock frames; reversed winding/tangent sign. Mirrored palette, roughness and normal maps exact. |
| Materials | Fresh current-shin calibration: explicit -19 shade shift, new-foot-only AO strength .35 and roughness transport. Normal strength 1, original normal pixels. |
| Skin joins | Four area-weighted ankle bands after calibration/AO: foot minus shin mean shade -0.199 to +0.472; protected connectors and non-skin bytes exact. Runtime palettes remain pending. |
| Stock poses | Nine cases: idle, kneel, crouch, two walk, two run, cast and death; 63 close views plus full comparisons. Same stock joint matrices and display scale 1. |
| Finite contacts | 162 comparable central foot/shin rays across the nine cases; no axial gap above 1 mm. This does not prove complete moving surface coverage. |
| Collection | Actual HAK inventory/payloads: 32 accepted neighbour resources byte-exact, 10 new foot resources; no fixture/supermodel/animation overrides. |

Detail is in `tapered-full-audit-v1`, `right-foot-full-audit-v1`,
`contact-material-independent-v2.json` and `paired-offline-pose-review-v1`.
Source Blender previews do not simulate repaired PLTs or engine lighting.

The collected file is
`paired-body-collection-v1/offline-foot-pair-native-pending.hak`, SHA256
`75177c18a454a44e7c905bcd0c3b55a9567d3cce811980e065b8c6b09b1c4b74`.
It mixes six native neighbours with two ASCII foot models and is **an offline
collection, not a validated game package**.

27 relevant regression checks passed across normalization (4), projection (4),
generation CLI (3), material repair (8), offline collection (6) and taper (2).
The actual model/geometry/material/package audits provide separate evidence.

## Deferred bulk engine gates

Compile new feet with frozen material dependencies, then decode and verify
native tangents/handedness, normals and UV transport. Validate skin palettes,
normal orientation, boots, mipmaps, close/gameplay appearance, continuous
transitions and practical performance. Approximately 50K triangles per foot
have not passed an engine performance budget.

Ground contact needs engine review: idle sole depth differs from stock by about
1 mm and sampled walk plant by less than .003 mm; death-pose sole is approximately
10–11 mm below stock. Other raised poses reflect foot shape and pitch. Sampled
poses/rays do not establish floor interaction or all transitions. Bind clean
bulk client captures/logs to exact package hashes.

Earlier evidence is [archived](history/phenotype-foot-regeneration-2026-10-03/phenotype-foot-validation.md).
