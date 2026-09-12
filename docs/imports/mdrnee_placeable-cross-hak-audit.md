# `mdrnee_placeable.hak` cross-HAK audit

This audit compares the full placeables archive with the previously imported `mdrnee_tile.hak`, `mdrnee_audio.hak` landing packs, and every current `srn_*` source directory.

- Placeable resources: 15256
- Tile archive overlaps: 161 (95 byte-identical, 66 differing variants)
- Confirmed misplaced companions in the tile bundle: 56 `cq*.pwk` files and two `shp_ceilg0*.mdl` files; all are canonicalized in `srn_placeable`.
- Tile-owned exception: `udp1_a01_01.pwk` accompanies a UDP1 tile model and remains in the UDP1 tileset pack.
- The invalid source identity `p_eng blk01.pwk` is landed byte-for-byte as `p_eng_blk01.pwk`, matching its `p_eng_blk01.mdl` companion; the malformed name remains preserved only in quarantine.
- Audio overlap: four WAVs were already imported byte-identically from `mdrnee_audio.hak`; two additional metallic-locker WAVs now land in `srn_sound`.
- Differing texture identities: 64; 59 have direct or indirect consumers in both archives. They are retained as declared order-sensitive overrides rather than silently substituted.

## CEP filtering result

- `placeables.2da` imports only the 4,752 rows whose model exists in this HAK; 25,248 legacy/base/CEP rows are omitted.
- Current EE rows are preserved. The selected source rows use only empty user/reserved slots or rows beyond the EE baseline.
- `placeableobjsnds.2da` imports only row 59 (`Brush`), which is used by 32 landed appearances.
- `placeablepal.itp` drops the single `CEP Specific` category and remaps 170 occurrences across 141 legacy references to 125 deduplicated canonical TLK entries.

## Differing tile/placeable identities

| Resource | Type | Placeable consumers | Tile consumers | Tile owners | Decision |
|---|---|---:|---:|---|---|
| asteroid1.dds | dds | 6 | 9 | shp02, vac01 | shared-identity-order-sensitive |
| cockpit.dds | dds | 16 | 9 | shp02 | shared-identity-order-sensitive |
| comp1glass.dds | dds | 2 | 1 | shp02 | shared-identity-order-sensitive |
| credits.txt | txt | 2 | 2 |  | excluded-attribution |
| dgt04__ref01.dds | dds | 1 | 9 | shp02 | shared-identity-order-sensitive |
| dgt04_black.dds | dds | 6 | 113 | dgt04, srt04 | shared-identity-order-sensitive |
| dgt04_chrome.dds | dds | 46 | 60 | dgt04, fcx01, srt04 | shared-identity-order-sensitive |
| dgt04_wood02.dds | dds | 0 | 0 |  | shared-identity-order-sensitive |
| dumpster_sign.dds | dds | 2 | 4 | dgt04, srt04 | shared-identity-order-sensitive |
| dumpster.dds | dds | 10 | 10 | dgt04, srt04 | shared-identity-order-sensitive |
| gg-conc.dds | dds | 18 | 20 | udp1, udp2 | shared-identity-order-sensitive |
| gg-conc3.dds | dds | 17 | 2 | udp2 | shared-identity-order-sensitive |
| gg2-bark.dds | dds | 7 | 71 | udp1, udp2 | shared-identity-order-sensitive |
| gg2-forbase1.dds | dds | 2 | 86 | udp1 | shared-identity-order-sensitive |
| gg2-msc-leaf2.dds | dds | 3 | 64 | udp1 | shared-identity-order-sensitive |
| gg2-msc-leaf2a.dds | dds | 1 | 64 | udp1 | shared-identity-order-sensitive |
| gg2-wd-pl.dds | dds | 2 | 12 | udp1, udp2 | shared-identity-order-sensitive |
| glass.dds | dds | 136 | 179 | dgt04, fcx01, shp02, srt04 | shared-identity-order-sensitive |
| green.dds | dds | 15 | 24 |  | shared-identity-order-sensitive |
| manhole_tex2.dds | dds | 0 | 2 | dgt04, srt04 | shared-identity-order-sensitive |
| red.dds | dds | 75 | 63 |  | shared-identity-order-sensitive |
| shiny_elevator.dds | dds | 0 | 1 |  | shared-identity-order-sensitive |
| shp_ceilg02.mdl | mdl | 2 | 2 |  | shared-identity-order-sensitive |
| shp_clg02.dds | dds | 1 | 126 | shp02 | shared-identity-order-sensitive |
| shp_clg03.dds | dds | 1 | 87 | shp02 | shared-identity-order-sensitive |
| shp_clg04.dds | dds | 1 | 39 | shp02 | shared-identity-order-sensitive |
| shp_navpanel.dds | dds | 2 | 2 | shp02 | shared-identity-order-sensitive |
| shp_panel08.dds | dds | 2 | 2 | shp02 | shared-identity-order-sensitive |
| shp_panel09.dds | dds | 2 | 2 | shp02 | shared-identity-order-sensitive |
| shp02_floor04.dds | dds | 2 | 125 | shp02 | shared-identity-order-sensitive |
| shp02_wall03.dds | dds | 24 | 41 | shp02 | shared-identity-order-sensitive |
| shp02_wall03.tga | tga | 24 | 41 | shp02 | shared-identity-order-sensitive |
| streetlamp.dds | dds | 1 | 0 |  | shared-identity-order-sensitive |
| tinsiding.dds | dds | 2 | 4 | shp02 | shared-identity-order-sensitive |
| tmi_metal01.dds | dds | 2 | 24 | dgt04, srt04 | shared-identity-order-sensitive |
| udp1-aircond.dds | dds | 3 | 33 | udp1 | shared-identity-order-sensitive |
| udp1-asph.dds | dds | 2 | 373 | udp1 | shared-identity-order-sensitive |
| udp1-dumpster.dds | dds | 3 | 1 |  | shared-identity-order-sensitive |
| udp1-gogas.dds | dds | 2 | 1 | udp1 | shared-identity-order-sensitive |
| udp1-gogas2.dds | dds | 1 | 1 | udp1 | shared-identity-order-sensitive |
| udp1-h6-sdg.dds | dds | 5 | 15 | udp1 | shared-identity-order-sensitive |
| udp1-metal.dds | dds | 7 | 3 |  | shared-identity-order-sensitive |
| udp1-msc-stngl2.dds | dds | 3 | 1 | udp1 | shared-identity-order-sensitive |
| udp1-mtl-grd-b.dds | dds | 2 | 3 | udp1 | shared-identity-order-sensitive |
| udp1-mtl-grd-r.dds | dds | 2 | 6 | udp1 | shared-identity-order-sensitive |
| udp1-mtl-grd-y.dds | dds | 2 | 3 | udp1 | shared-identity-order-sensitive |
| udp1-mtl-grid.dds | dds | 5 | 37 | udp1, udp2 | shared-identity-order-sensitive |
| udp1-mtl-gry.dds | dds | 12 | 123 | udp1, udp2 | shared-identity-order-sensitive |
| udp1-mtl-rvt.dds | dds | 2 | 1 | udp1 | shared-identity-order-sensitive |
| udp1-mtl-ss-b.dds | dds | 1 | 1 | udp1 | shared-identity-order-sensitive |
| udp1-mtl-ss-dr.dds | dds | 4 | 42 | udp1 | shared-identity-order-sensitive |
| udp1-mtl-ss-dy.dds | dds | 1 | 2 | udp1 | shared-identity-order-sensitive |
| udp1-mtl-ss-g.dds | dds | 2 | 1 | udp1 | shared-identity-order-sensitive |
| udp1-mtl-vents.dds | dds | 2 | 10 | udp1 | shared-identity-order-sensitive |
| udp1-net-chr.dds | dds | 2 | 2 | udp1 | shared-identity-order-sensitive |
| udp1-net-wh.dds | dds | 3 | 1 | udp1 | shared-identity-order-sensitive |
| udp1-pave.dds | dds | 10 | 361 | udp1 | shared-identity-order-sensitive |
| udp1-pnt-wh1.dds | dds | 3 | 10 | udp1, udp2 | shared-identity-order-sensitive |
| udp1-pnt-wh3.dds | dds | 5 | 3 | udp1 | shared-identity-order-sensitive |
| udp1-tile-rdst.dds | dds | 1 | 1 | udp1 | shared-identity-order-sensitive |
| udp1-wd-fnc.dds | dds | 6 | 168 | udp1 | shared-identity-order-sensitive |
| udp1-wd-grd1.dds | dds | 6 | 53 | udp1, udp2 | shared-identity-order-sensitive |
| v_skyhop.dds | dds | 2 | 3 | shp02 | shared-identity-order-sensitive |
| window.dds | dds | 87 | 402 | shp02 | shared-identity-order-sensitive |
| xwing_mini.dds | dds | 0 | 5 | shp02 | shared-identity-order-sensitive |
| yellow.dds | dds | 13 | 9 |  | shared-identity-order-sensitive |

Consumer counts include direct model references and indirect material, TXI, and table references. Exact hashes, appearance rows, consumer lists, source ownership, and all 161 overlap decisions are recorded in `mdrnee_placeable-cross-hak-audit.json`.

## Resolution normalization

Byte inequality does not by itself establish a visible conflict. NWN Crunch inspection found 30
of the 64 differing texture identities have unequal dimensions. The staged packs now carry the
greater pixel-area source variant for each of those identities:

- 25 use the higher-resolution tile-archive source.
- 5 use the higher-resolution placeable-archive source.
- 28 lower-resolution staged copies were replaced byte-for-byte with the selected source.
- `red.dds` and `yellow.dds` already had only their higher-resolution placeable copies staged.

The lower-resolution originals remain unchanged in quarantine. The deterministic selections,
dimensions, hashes, and affected packs are recorded in
`mdrnee_texture-resolution-normalization.json` and can be reproduced with
`tools/Resolve-MdrneeTextureResolution.ps1 -Apply`. Equal-resolution byte variants are not
changed by this rule.

## Equal-resolution equivalence exceptions

Visual comparison found the 32 remaining staged DDS variants to be equivalent artwork. NWN Crunch
also decoded every copy successfully. The following explicit selection policy removes their
runtime order sensitivity while keeping every consuming pack self-contained:

- Select the tile-archive bytes for 31 resources. Both candidates have matching dimensions,
  encoding, and complete mip-chain size; the tile content has passed smoke testing.
- Select the placeable-archive bytes for `tmi_metal01.dds`. Its DXT1 copy is 2,764 bytes; the
  tile copy is 5,508-byte DXT5 with a completely opaque alpha channel, so DXT5 preserves no useful
  additional data.
- Propagate the selected bytes to every staged pack containing that resource identity.
- Preserve every superseded source variant unchanged in quarantine.

The complete exception registry is `mdrnee_texture-equivalence-exceptions.json`; apply it with
`tools/Resolve-MdrneeEquivalentTextures.ps1 -Apply`. The declarations remain in
`hakbuilder.json` as reviewed cross-pack exceptions, but their staged bytes are now identical.
