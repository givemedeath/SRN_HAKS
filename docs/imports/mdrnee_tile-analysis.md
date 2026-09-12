# `mdrnee_tile.hak` import analysis

- SHA-256: `B52CFAA8823826B1262AB19836D66C0DD04797AC2DD02ED9C03FE37309C59F44`
- Source resources: 14992
- Initially landed: 13529
- Quarantined: 1462
- Excluded: 1
- Base collisions: 0 (0 different)

## Tileset readiness

| Code | Friendly name | Tiles | Clean | Repairs | Non-contiguous | Structural issues | EE model dependencies | Known missing models | Recommended pack |
|---|---|---:|:---:|---:|---:|---:|---:|---:|---|
| dgt04 | D20 Modern Exterior | 429 | False | 25 | 0 | 0 | 0 | 9 | srn_t_dgt04 |
| fcx01 | D20 Futuristic City SW | 239 | False | 21 | 0 | 0 | 0 | 0 | srn_t_fcx01 |
| fifi | D20 Bunker PHoD | 51 | False | 7 | 0 | 0 | 0 | 0 | srn_t_fifi |
| flow_pa | D20 Parking Garage | 32 | False | 12 | 0 | 0 | 0 | 0 | srn_t_flow_pa |
| nac01 | D20 ServiceDucts | 17 | False | 7 | 0 | 0 | 0 | 0 | srn_t_nac01 |
| net01 | D20 VirtuNet | 46 | True | 0 | 0 | 0 | 0 | 0 | srn_t_net01 |
| shp02 | D20 Starship Interior SW | 579 | False | 24 | 0 | 0 | 0 | 0 | srn_t_shp02 |
| sjm01 | D20 SJ Metal Interior | 153 | False | 36 | 0 | 0 | 0 | 0 | srn_t_sjm01 |
| srt04 | D20 Shadowrun Exterior | 264 | False | 48 | 0 | 0 | 0 | 0 | srn_t_srt04 |
| tbx78 | D20 Modern Facility | 84 | True | 0 | 0 | 0 | 0 | 2 | srn_t_tbx78 |
| tfb01 | D20 Modern Interior | 338 | False | 23 | 0 | 0 | 0 | 2 | srn_t_tfb01 |
| tjsb0 | D20 Secret Base | 174 | True | 0 | 0 | 0 | 0 | 2 | srn_t_tjsb0 |
| udp1 | D20 Suburbs UDP | 676 | False | 183 | 0 | 0 | 0 | 3 | srn_t_udp1 |
| udp2 | D20 Office Interiors UDP | 229 | False | 101 | 0 | 0 | 0 | 17 | srn_t_udp2 |
| vac01 | D20 Space | 16 | True | 0 | 0 | 0 | 0 | 0 | srn_t_vac01 |
| vmp01 | D20 Planetscape | 395 | False | 25 | 0 | 0 | 0 | 0 | srn_t_vmp01 |
| vmr01 | D20 Alien Ruins | 272 | False | 12 | 0 | 0 | 0 | 15 | srn_t_vmr01 |
| zsf01 | D20 SciFi Base CQ | 73 | False | 30 | 0 | 0 | 0 | 7 | srn_t_zsf01 |

## Disposition by recommended landing

| Landing | Land | Quarantine | Exclude | Bytes |
|---|---:|---:|---:|---:|
| .quarantine/deferred/miscellaneous | 0 | 0 | 1 | 1020 |
| .quarantine/deferred/unproven-models | 0 | 9 | 0 | 808767 |
| .quarantine/deferred/unproven-textures | 0 | 1382 | 0 | 42131528 |
| .quarantine/deferred/unused-tile-assets | 0 | 8 | 0 | 25812 |
| srn_2da | 15 | 1 | 0 | 1081367 |
| srn_door | 325 | 0 | 0 | 27652044 |
| srn_fx | 0 | 2 | 0 | 26738 |
| srn_placeable | 0 | 56 | 0 | 43428 |
| srn_skybox | 32 | 0 | 0 | 8216253 |
| srn_t_common | 915 | 2 | 0 | 119822689 |
| srn_t_dgt04 | 797 | 0 | 0 | 60886202 |
| srn_t_fcx01 | 1090 | 0 | 0 | 22338524 |
| srn_t_fifi | 128 | 0 | 0 | 17397662 |
| srn_t_flow_pa | 122 | 0 | 0 | 7379881 |
| srn_t_nac01 | 66 | 0 | 0 | 1597727 |
| srn_t_net01 | 106 | 0 | 0 | 3287194 |
| srn_t_shp02 | 2095 | 2 | 0 | 58783949 |
| srn_t_sjm01 | 464 | 0 | 0 | 33091898 |
| srn_t_srt04 | 18 | 0 | 0 | 613469 |
| srn_t_tbx78 | 284 | 0 | 0 | 8176128 |
| srn_t_tfb01 | 1531 | 0 | 0 | 33091601 |
| srn_t_tjsb0 | 528 | 0 | 0 | 19845713 |
| srn_t_udp1 | 2108 | 0 | 0 | 79334450 |
| srn_t_udp2 | 758 | 0 | 0 | 25265429 |
| srn_t_vac01 | 56 | 0 | 0 | 3379433 |
| srn_t_vmp01 | 1233 | 0 | 0 | 70779603 |
| srn_t_vmr01 | 601 | 0 | 0 | 32404848 |
| srn_t_zsf01 | 257 | 0 | 0 | 25958707 |

## Quarantine landing policy

- Candidate `srn_t_*` resources may be promoted after deterministic SET repair and dependency packaging; targeted engine checks should catalogue visual or walkmesh defects rather than treat them as whole-tileset failures.
- `srn_t_common` is reserved for dependencies proven to be shared by multiple promoted tilesets.
- `srn_door`, `srn_skybox`, `srn_music`, and `srn_sound` are active component destinations when a reviewed profile proves their registrations and dependencies; `srn_placeable` and `srn_fx` remain deferred.
- `.quarantine/deferred/unproven-textures` and `.quarantine/deferred/unproven-models` have no proven consumer; they stay local until ownership is established.
- `.quarantine/deferred/unused-tile-assets` contains unreferenced tile companions or variants awaiting a SET consumer.
- Missing edge models are tracked as localized known issues. Preserve the edge table unless a tested replacement or remap is available.

## Profile notes

- Post-import dependency review corrected a decomposition-only ownership swap: the 92 `mijm01_*` minimaps belong to D20 SJ Metal Interior (`srn_t_sjm01`), while the 133 `mijsb0_*` minimaps belong to D20 Secret Base (`srn_t_tjsb0`). The import profile and manifest now reproduce that assignment.
- Five source edge tables contain 48 missing model identities. UDP2's optional remap remains quarantined because Toolset testing confirmed its Wall-first terrain workflow without the remap.
- All 18 tilesets are treated as established working content. UDP2 uses the count-normalized SET for a new controlled test: comparison with a Toolset-created area showed that the generated fixture used a group tile instead of the tileset's blank Wall filler tile.
- The 142 music registrations backed by mdrnee_audio retain source rows 190-194 and 201-337. Five landed modern ambient loops move to blank EE rows 204-205 and 207-209; the oversized bar/club loop and its target row 206 remain deferred. Generic doors use EE user rows 1000 onward, and source skybox rows 7-15 extend the pinned EE baseline.
- Door remaps are 239→260, 240→261, 243→262, SET references 109→263 and 110→264 for custom rows imported from 241/242, and 255→265. The final three register the otherwise dormant SJM01 dome/gate and VMP01 wall-gate doors.
- The companion manifest records every resource and its recommended landing.
- Generic-door source row 103 (`udp1_ohfire2` / `t_door93`) is withheld because no `t_door93.dwk` exists in any reviewed source. The model remains staged in `srn_door` pending a verified walkmesh.
- Generic-door source row 21 (`Glass_Window`) uses the dedicated `Glass Window` TLK entry; the source row incorrectly reused `Wood Glass Reflect`.
- Seven ambient-music rows retain their available main battle tracks but clear optional `mus_sbat_f_*` stinger references whose BMUs are absent from the source audio HAK.

<!-- repair-results -->
## Repaired SET artifacts

Raw extraction remains byte-for-byte unchanged. Repaired SETs are generated beneath the quarantine workspace; Apply selects them for promoted packs unless `preserveRawSets` names the tileset.

| Code | Friendly name | Changes | Structural result | Readiness |
|---|---|---:|---|---|
| dgt04 | D20 Modern Exterior | 25 | clean | candidate-known-visual-walkmesh-gaps |
| fcx01 | D20 Futuristic City SW | 29 | clean | candidate-ready-targeted-validation |
| fifi | D20 Bunker PHoD | 7 | clean | candidate-ready-targeted-validation |
| flow_pa | D20 Parking Garage | 12 | clean | candidate-ready-targeted-validation |
| nac01 | D20 ServiceDucts | 7 | clean | candidate-ready-targeted-validation |
| shp02 | D20 Starship Interior SW | 24 | clean | candidate-ready-targeted-validation |
| sjm01 | D20 SJ Metal Interior | 38 | clean | candidate-ready-targeted-validation |
| srt04 | D20 Shadowrun Exterior | 48 | clean | candidate-ready-targeted-validation |
| tfb01 | D20 Modern Interior | 23 | clean | candidate-known-visual-walkmesh-gaps |
| udp1 | D20 Suburbs UDP | 183 | clean | candidate-known-visual-walkmesh-gaps |
| udp2 | D20 Office Interiors UDP | 101 | clean | candidate-known-visual-walkmesh-gaps |
| vmp01 | D20 Planetscape | 25 | clean | candidate-ready-targeted-validation |
| vmr01 | D20 Alien Ruins | 13 | clean | candidate-known-visual-walkmesh-gaps |
| zsf01 | D20 SciFi Base CQ | 30 | clean | candidate-known-visual-walkmesh-gaps |

Every changed line, old value, new value, and repaired-file hash is recorded in `repair-log.json`.

## Edge-table repair candidates

| Code | Friendly name | Resource | Remapped references | Activation |
|---|---|---|---:|---|
| udp2 | D20 Office Interiors UDP | udp2_edge.2da | 28 | optional-targeted-visual-walkmesh-comparison |

Experimental edge tables remain quarantined and do not replace the preserved source table without targeted visual and walkmesh comparison.
