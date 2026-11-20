# PR 86 heads: direct PLT repairs (v1)

On 2026-11-04, a four-view client check found visible defects on nine of the 12 heads published in PR 86. Their stage runs were deleted with the scratch data, so each head here is repaired directly on its published PLT with [plt_repair.py](../../plt-repair.md). Geometry, UVs and the MDLs are unchanged. elf-male-b (`pme0_head021`), elf-male-d (`pme0_head023`) and human-female-b (`pfh0_head029`) were clean and are untouched.

Each `<slot>.json` here is the spec. It pins the published PLT and MDL by SHA-256 and lists the operations.

## Client check, 2026-11-20

- **Build:** `srn_head`, `srn_body` and `srn_body_tex` were built from this branch.
- **Sessions:** fromBase trials of the four affected families: elf male, elf female, dwarf female and orc female. The two elf sessions were rerun after spec changes.
- **Verify:** `verify_head_trial` passed for every session.
- **Evidence:** [pr86-plt-repair-client.jpg](../../evidence/pr86-plt-repair-client.jpg). Each row shows one head, in three-quarter, three-quarter-left, back-right, back-left and front views, plus the second look. The empty tiles are fixed views that look past the head.

| Head | Slot | Defect (2026-11-04) | Repair | In client |
|---|---|---|---|---|
| orc-female-b | `pfo0_head014` | black blotches on rear hair, skin patch behind ear, dark face mottling, bright forehead stripe | rear hair tone-matched to the top hair, black floor, blotch despeckle, temple skin patch moved to hair, nape skin matched to the cheek, forehead stripe matched, face spots | rear hair is even and dark. A few dark blotches remain, smaller. A faint box edge shows above the ear. |
| elf-female-b | `pfe0_head019` | large bright oval on the shaved scalp | scalp highlights compressed by a feathered curve | the baked oval is gone. A lit glow on the smooth scalp remains (lighting). |
| dwarf-female-a | `pfd0_head013` | bright temple oval; left brow near-black, right brown | left brow moved from metal to hair and matched to the right brow; temple highlights compressed | both brows are brown. A soft light spot remains on the cheek. |
| dwarf-female-b | `pfd0_head014` | mottled grey rear scalp, stray white strands | strands filled, specks despeckled, stubble contrast compressed | clean grey stubble, no strands. |
| elf-male-c | `pme0_head022` | blocky olive and black rear hair streaks | flecks relabelled, dark outliers despeckled, hair dark end lifted | black blocks gone and the olive blocks softer. The olive is the light end of row 117 in dim light. |
| orc-female-a | `pfo0_head013` | dark patch at the hair edge behind the ear | dark skin behind the ears filled from the surrounding skin | the patch is gone and skin shows under the bun. |
| elf-female-a | `pfe0_head018` | dark specks, brown bits on rear hair | flecks relabelled, dark specks despeckled | specks gone. One small brown mark remains at the crown. |
| elf-female-c | `pfe0_head020` | dark patch at the ear/hair edge, patchy hair | flecks relabelled (skin and hair only), bright strips by the ears filled, hair specks despeckled | the strips are mostly gone and the hair is evener. |
| elf-male-a | `pme0_head020` | olive streaks in light hair | flecks and dark specks despeckled | **streaks unchanged.** They are strand-groove geometry lit by the scene's olive ambient light, not texture. A v2 lift of every hair shade to at least 64 changed nothing in the client, so it was reverted. |

## Status

- **Accepted** by the user on 2026-11-20: "Accept all nine". This covers elf-male-a with its v1 speck fix only; its streaks stay as known lighting.
- Pushed and opened as PR 183 on 2026-11-20 with the user's approval. Merging needs the user.
- Working data (runs, receipts, sheets and client sessions) is in ignored scratch: `pr86-plt-repair-20261120` and the head library workspace's `trials/client-sessions/rp*`.
