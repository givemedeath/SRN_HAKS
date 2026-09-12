# `mdrnee_placeable.hak` import analysis

- SHA-256: `E90B4F15EE15D8009D843C8B2EB70C77BD835FF0ED77F1534BB5EC4963B8A159`
- Source resources: 15256
- Initially landed: 15254
- Quarantined: 0
- Excluded: 2
- Base collisions: 14 (14 different)

## Tileset readiness

| Code | Friendly name | Tiles | Clean | Repairs | Non-contiguous | Structural issues | EE model dependencies | Known missing models | Recommended pack |
|---|---|---:|:---:|---:|---:|---:|---:|---:|---|

## Disposition by recommended landing

| Landing | Land | Quarantine | Exclude | Bytes |
|---|---:|---:|---:|---:|
| .quarantine/deferred/miscellaneous | 0 | 0 | 2 | 1331 |
| srn_2da | 2 | 0 | 0 | 6702249 |
| srn_placeable | 15246 | 0 | 0 | 1289802165 |
| srn_sound | 6 | 0 | 0 | 1156862 |

## Quarantine landing policy

- Candidate `srn_t_*` resources may be promoted after deterministic SET repair and dependency packaging; targeted engine checks should catalogue visual or walkmesh defects rather than treat them as whole-tileset failures.
- `srn_t_common` is reserved for dependencies proven to be shared by multiple promoted tilesets.
- `srn_placeable` is an active component destination for this reviewed profile; its global table rows and palette transforms remain separately validated.
- `.quarantine/deferred/unproven-textures` and `.quarantine/deferred/unproven-models` have no proven consumer; they stay local until ownership is established.
- `.quarantine/deferred/unused-tile-assets` contains unreferenced tile companions or variants awaiting a SET consumer.
- Missing edge models are tracked as localized known issues. Preserve the edge table unless a tested replacement or remap is available.

## Profile notes

- All 15,254 non-credit resources are imported: placeable assets and palette into srn_placeable, six WAVs into srn_sound, and two baseline-preserving global tables into srn_2da.
- placeables.2da retains exactly 4752 rows whose model identity is supplied by this HAK. The other 25248 legacy/base/CEP rows are omitted; current EE rows remain unchanged.
- The 60 self-contained rows occupying OS_RESERVED markers are treated as reviewed empty reservations, not active EE collisions. No active EE placeable row is replaced.
- placeableobjsnds.2da adds only row 59 (Brush), used by 32 bundled foliage appearances; legacy row 50 and all CEP_RESERVED/USER filler rows are omitted.
- placeablepal.itp removes the single CEP Specific category and remaps every remaining custom STRREF through the canonical deduplicating TLK registry.
- Cross-HAK texture identities remain declared explicitly. The 30 unequal-dimension identities use the greater pixel-area source. The 32 visually equivalent equal-resolution DDS variants use the reviewed exception registry: 31 smoke-tested tile copies and the smaller DXT1 `tmi_metal01.dds` placeable copy. All staged cross-pack duplicate bytes are now identical.
- The malformed source identity p_eng blk01.pwk is landed as p_eng_blk01.pwk to match its model companion; the original name and bytes remain preserved in quarantine.
