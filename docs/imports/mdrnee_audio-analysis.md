# `mdrnee_audio.hak` import analysis

- SHA-256: `012841691F5AB20EDAD8F2924DC63CC638C84CB8FD3D6A188F13388905E7742F`
- Source resources: 158
- Initially landed: 157
- Quarantined: 0
- Excluded: 1
- Base collisions: 1 (1 different)

## Tileset readiness

| Code | Friendly name | Tiles | Clean | Repairs | Non-contiguous | Structural issues | EE model dependencies | Known missing models | Recommended pack |
|---|---|---:|:---:|---:|---:|---:|---:|---:|---|

## Disposition by recommended landing

| Landing | Land | Quarantine | Exclude | Bytes |
|---|---:|---:|---:|---:|
| srn_music | 142 | 0 | 0 | 150112460 |
| srn_sound | 15 | 0 | 1 | 69204770 |

## Quarantine landing policy

- Candidate `srn_t_*` resources may be promoted after deterministic SET repair and dependency packaging; targeted engine checks should catalogue visual or walkmesh defects rather than treat them as whole-tileset failures.
- `srn_t_common` is reserved for dependencies proven to be shared by multiple promoted tilesets.
- `srn_door`, `srn_skybox`, `srn_music`, and `srn_sound` are active component destinations when a reviewed profile proves their registrations and dependencies; `srn_placeable` and `srn_fx` remain deferred.
- `.quarantine/deferred/unproven-textures` and `.quarantine/deferred/unproven-models` have no proven consumer; they stay local until ownership is established.
- `.quarantine/deferred/unused-tile-assets` contains unreferenced tile companions or variants awaiting a SET consumer.
- Missing edge models are tracked as localized known issues. Preserve the edge table unless a tested replacement or remap is available.

## Profile notes

- All 142 BMU resources land in srn_music. Fifteen WAV resources land in srn_sound; mdrnmod_barclub.wav is explicitly excluded.
- The companion mdrnee_tile profile supplies baseline-preserving ambientmusic.2da and ambientsound.2da merges for resources registered by the legacy bundle.
- Ten WAV effects are direct-use resources without global ambient table rows; five landed mdrnmod_* WAV loops are registered by the merged ambient sound table.
