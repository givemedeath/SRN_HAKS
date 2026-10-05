# Pilot delivery at the client-testing boundary

The reusable pipeline covers preparation, Meshy task recording/collection,
fitting, materials, native validation, client fixtures and gated publication.
The revised scope stops before interactive client testing. Human and Troll male candidates are
native validated; client and production acceptance remain pending. Their runtime
resources and built HAKs remain in the ignored local bank. The publication helper
registers `srn_head` after acceptance; production configuration and `srn_2da` are
unchanged at this checkpoint.

| Design | Slot | Triangles | Current gate | Next dependency |
|---|---:|---:|---|---|
| Natural Human male | `pmh0_head082` | 19,000 | Native passed | Client review |
| Cyberware Human male | `pmh0_head083` | 19,000 | Native passed | Client review |
| Elf female | See slot catalog | Master retained | Donor passed | Approved Elf female body contract |
| Troll male | `pmg0_head014` | 19,000 | Native passed | Client review |

Actual Meshy spend is **255 of 300 credits**, including historical pilot jobs
and the 10-credit Troll retexture job.
All operations are settled or definitively reconciled; no reservations remain.
Each design used its permitted two generation attempts. Bulk production has no
budget authorization in this delivery. The final limit is **20,000 triangles**,
including hair, accessories and caps, superseding the earlier limits.

## Complete skull and jaw

New coherent four-view references and Meshy 7 donors omit the extending neck
while retaining the complete skull, chin and mandible. The operator approved
the displayed shapes. Earlier trim/taper experiments are held and unselected.
No neck taper or jaw trim is applied to the current sources.

Meshy triangle/quad reductions produced unsafe boundaries. The selected Human
heads use a separately versioned local surface LOD from the retained high-detail
pre-remesh geometry, with new selected UVs and a high-source tangent-normal bake.
All source masters and failed candidates remain local. The natural head needs
one tiny cap; the cyberware head needs 24. Cap-only processing preserves every
existing position, normal and UV. Both selected 19K heads have zero boundary,
nonmanifold and inconsistent paired edges under exact-position topology checks.

Fits use proper rotation, positive uniform scale and translation. All 72 published
body resources, proportions, stock neck, `head_g` and animation dependencies remain
unchanged. Maximum landmark errors are 20.920 mm and 10.510 mm under the reviewed
25 mm allowance. The lower cranial envelope bound is separately versioned at
-70 mm to accommodate the intact jaw; the historical fit extended 0.179 mm below
the old -65 mm bound. Standing, 82 sampled poses and the measured worst case were
reviewed offline. The 114.649 mm stock-neck displacement is a motion diagnostic,
not a measured visible gap.

## Materials and native checks

Meshy retextured the selected capped geometry with original UVs and 2K PBR maps.
Atlas checks verify exact matched UVs and bounded position correspondence.
Returned geometry and rebuilt normals are discarded; every selected source face
remains in the runtime head. Microscopic returned-mesh omissions are explicitly
recorded. Cap atlas patches are filled locally from neighboring material ownership,
with neutral normals. The local high-source normal bake is retained without a
green inversion. Runtime textures are 1024-square.

Skin/hair source palette calibration samples selected UV islands, excluding unused
service atlas fill. This fixes the cyberware head's initial overly bright skin
indices. PLT skin/hair remain recolorable; eyes and cyberware retain fixed RGB.
Actual palette bytes are decoded for offline comparison with the unchanged body
and stock neck. Engine neck shading, lighting, normal-map appearance and helmets
remain client checks.

The installed NWN compiler produced both native models in isolated staging
directories. Native decoding verified geometry, winding, UVs, normals, tangents,
material ownership, PLT bytes, normal/roughness transport and protected body hashes.
Two isolated fixtures cover ambient/directional lighting, 22 palette/helmet actors
each, and compiled idle/talk, walk/run, casting, combat, crouch/kneel and death
schedules. Their identical current `srn_head.hak` payload is pinned in
[validation-summary.json](validation-summary.json) and
[pilot-catalog.json](pilot-catalog.json). No module was launched interactively.
Actual equipment logs and character-creation slot selectability remain pending.

## Derived male bodies and Troll continuation

Merged `codex/derived-phenotypes` at `be6391b437332eeae64ca3df54e952c9749a288d`.
All five races now have male body contracts. The published Human manifest and all
72 resource hashes remain unchanged, retaining both Human head fits and native
checks. The existing Troll donor now uses an independent copy of its fourteen-part
derived body, with 44 protected runtime resources. The Elf female donor still
requires a female body contract. Additional Elf/Dwarf/Orc male designs were not
part of this four-head pilot continuation.

The Troll follows the same retained-source LOD and cap-only route: 18,986 surface
triangles plus 14 tiny caps total 19,000. Horns are excluded from the central scalp
landmark. The reviewed working envelope accommodates the intact skull, jaw and
horns; fitting remains uniform and proper. The stock Troll-family neck stays
unchanged. Review standing plus the measured worst combat sample and all nine
motion families in [the motion sheet](evidence/troll-motion-derived-v1.png).
Visible neck joining, equipment and engine shading remain client checks.

The derived root originally listed children before their parents. A separately
versioned parent-first copy compiles natively while preserving all original node
text and transforms. The decoded 56-node rig matches every parent and bind frame,
with maximum error 2.473e-7. The fixture applies the body's declared 10/7 visual
scale, keeping fitting in working coordinates. Its body HAK includes the 44
unchanged body resources, this compiled root and 28 shared normal/roughness maps.

Troll UV transfer preserves selected geometry and UVs; returned service geometry
and normals are discarded. Skin/hair are recolorable, with fixed eyes and ivory
horn/tusk surfaces. An offline palette comparison caught an overly dark automatic
calibration; the reviewed source skin row is 4, hair row 75. Both native decode
and the [palette sheet](evidence/troll-material-derived-v1.png) use the corrected
candidate. Two additional isolated lighting fixtures each contain 11 Troll actors
covering palette combinations and helmets, with verified head and body payloads.
They have compiled scripts but have not been launched interactively.

## Review and continuation

The [evidence manifest](evidence/manifest.json) pins current neckless reference
sheets/prompts, four donor turntables, Human and Troll motion/material sheets and the
unchanged stock-neck control. [NOTICE](evidence/NOTICE.md) records reference
ancestry, Meshy attribution and conditional redistribution rights. Local preview
configuration names `light`/`dark` use skin/hair selectors 3/21 and 12/5 respectively;
the names do not imply palette brightness order. All previews use four threads,
with timings in the validation record.

Resume ignored operating state from the explicit
`output/heads/pilot-v1/local/resume-ledger-derived-male-v1.json`. Verify its exact
session checkpoint, source/native bank, target, fits and fixtures. Historical
checkpoints are immutable. Source masters/pre-remesh geometry remain hash-verified
in the primary checkout's ignored source bank. Before any future checkout retirement,
preserve verified copies outside it and run the read-only retirement audit.

Client reports must observe this exact package across all palette/light/helmet/
motion cases and demonstrate selectable slots. Production acceptance additionally
reviews rights and unchanged body dependencies. Only then publish with
`publish_head_pack.py`, rebuild `srn_head.hak` and verify the entire payload against
publication pins using `verify_head_hak.py`.

Head, shared-helper, phenotype, repository and item-import regressions pass;
their log hashes and actual native/fixture reports are recorded in the validation
summary. Compiled fixtures and offline renders do not establish client acceptance.
