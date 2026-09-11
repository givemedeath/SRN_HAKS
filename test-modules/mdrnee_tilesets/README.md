# MDRNEE tileset smoke module

This fixture creates `output/srn_mdrnee_test.mod`, a portable NWN:EE module that declares all 24
curated HAKs produced from `mdrnee_tile.hak` and `mdrnee_audio.hak`. It contains one 16 x 16 area for each of the 18 tilesets.
Area names include the friendly tileset name and resref.

Build everything with:

```powershell
pwsh ./tools/Build-MdrneeTilesetTestModule.ps1
```

The builder verifies that all declared HAKs exist, converts generated GFF JSON with the pinned
`nwn_gff`, packs with the pinned `nwn_erf`, normalizes the archive date, reopens the module, and
writes `output/srn_mdrnee_test.receipt.json` with module and HAK hashes.

For a Toolset test, copy the MOD to the NWN user `modules` directory and the 24 declared HAKs to
the user `hak` directory. Open the module and inspect each named area. For an in-game test, start
as a DM and use the area chooser; the entry area is **D20 Modern Exterior (`mt_dgt04`)**.

Every area initially repeats its configured seed tile across the grid, leaving enough room to paint
the largest 8 x 8 palette group found in these tilesets and to resolve terrain transitions away from
the area boundary. Most tilesets use tile 0. D20 Office Interiors UDP uses tile 13 because it is the
uniform blank `Wall` tile matching the SET's `Default=Wall` declaration. The fixture does not automatically exercise
every tile, transition, door hook, lightmap, or walkmesh. A consumer such as SR_NWN remains
responsible for representative-area generation and live validation.

## Recorded smoke result

On 2026-09-10 the operator reported that all 18 areas passed Toolset and game-client smoke testing
with the original 21 decomposed HAKs. No smoke-test defect was observed. See
`docs/imports/mdrnee_tile-deferred-work.md` for the targeted edge-table and extended palette tests.

Extended palette testing confirmed that **D20 Office Interiors UDP (`udp2`)** expects an interior
Wall-first workflow. Start from the filled `Wall` area, paint `Office_Vinyl`, `Office_Wood`,
`Office_Alum`, or another floor terrain over it, and then paint that terrain's associated features
and groups. Merely enlarging the former all-Service area did not establish this prerequisite. The
source edge table and count-normalized repaired SET are active, and the generated area starts from
the uniform blank Wall tile 13. The earlier apparent repair failure was isolated to the precreated
area: a new UDP2 area in the same module painted correctly, and comparison showed the fixture had
used tile 12, a Service Entry group tile, rather than the blank Wall filler.
