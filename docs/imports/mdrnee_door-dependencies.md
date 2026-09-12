# MDRNEE door dependency closure

## Landed supplemental resources

Ten missing companion files now land in `srn_door`. Four were selectively extracted from
`mdrnee_placeable.hak` (SHA-256
`E90B4F15EE15D8009D843C8B2EB70C77BD835FF0ED77F1534BB5EC4963B8A159`).
Six came from the working SWLOR decomposition at `SWLOR_Haks` commit
`e349a8026ce226da1e2199295b0d9e34bc4e94f4`; every imported file matches its committed blob.

| Resource | Consumer |
|---|---|
| `chrome.dds`, `chrome.txi` | `t1doora2.mdl` |
| `tin01__metal01.dds` | `gn_door21.mdl` |
| `tin01_black.dds` | `gn_door30.mdl` |
| `gg2-h3-2.dds` | `t_door82.mdl`  IntGreen |
| `gg2-dr-grn.dds` | `t_door84.mdl`  House1 |
| `gg2-dr-gry.dds` | `t_door85.mdl`  House2 |
| `gg2-dr-wht.dds` | `t_door86.mdl`  House3 |
| `gg-msc-pnl2.dds` | `t_door91.mdl`  Green |
| `gg-msc-fence.dds` | `t_door92.mdl`  GateMtlBlk |

The machine-readable manifest records exact byte sizes, hashes, source identities, and consumers.

## Remaining missing identities

The complete scan covers all 113 staged door models, including quarantine-only ASCII
decompilations of all six binary models. After the supplemental import:

- 31 external texture identities resolve from the installed NWN:EE baseline.
- `standardmaterial` is an engine material token, not a missing file.
- Two texture identities remain absent from all 24 staged packs, the 21 source HAKs, NWN:EE, and
  the checked SWLOR tree.

### `arcology_brkn_win`

This is a surface texture on `t_door12.mdl`. It affects:

- `doortypes.2da` row 117, GlassWindow, in **D20 Shadowrun Exterior (`srt04`)**
- `genericdoors.2da` row 1010, Glass_Window

This is the remaining gap most likely to produce an obviously untextured door. Recommended landing:
`srn_door`, after locating the original texture or visually approving a compatible replacement.

### `fxpa_cloud02`

This is an emitter texture referenced by 17 models. It may disturb an opening/closing effect, but
does not supply their primary door surfaces:

- **D20 SJ Metal Interior (`sjm01`)**: `sjm_udoor_01`, `sjm_udoor_02`
- **D20 Modern Interior (`tfb01`)**: `tfb_udoor_01` through `tfb_udoor_03`
- **D20 Planetscape (`vmp01`)**: `vmp_udoor_01`, `03`, `04`, and `06`
- **D20 Alien Ruins (`vmr01`)**: `vmr_udoor_01` through `07`
- shared generic door `t1doora4`

Recommended landing: `srn_door`, after locating the original emitter texture. If it cannot be
found, animation testing should determine whether removing that emitter layer is preferable to an
invisible missing texture.

## Model-tool verification

The vendored `nwnmdlcomp.exe` successfully decompiled all six binary door models. Its compilation
mode requires a legacy NWN 1.69 `chitin.key`; the current NWN:EE-only installation does not provide
one. No door model was replaced or recompiled during this dependency repair.
