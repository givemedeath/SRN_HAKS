# Content Provenance

## Meshy head pilot review (2026-10-05)

Contributor: SRN project operator with Codex. The `docs/heads/evidence/` reference
PNGs and prompts originate from original SRN briefs and OpenAI image generation.
The donor and Human assembly/material PNGs render Meshy 7 generated heads,
attributed to [Meshy](https://www.meshy.ai/), with a separately versioned local
surface LOD, high-source normal bake, uniform fitting, hole caps and runtime
material preparation. The selected donors have no extending neck; no jaw trimming
or neck taper is applied. Exact filenames, original
and derivative hashes, task IDs and dispositions appear in
`docs/heads/evidence/manifest.json` and `docs/heads/pilot-catalog.json`.
The full origins, conditional Meshy CC BY 4.0 rights, attribution, modification
notice and stock-reference scope are in `docs/heads/evidence/NOTICE.md`.

This tooling/review batch publishes no runtime resources into `srn_head`:
the Human native candidates await client and rights acceptance, and Elf/Troll
remain donors pending approved bodies. The generated source/native banks, built
HAKs and operational receipts remain ignored. Existing custom body provenance
applies to rendered `srn_body` content. Installed stock neck/rig/palette/animation
files are local validation inputs and are not redistributed in this PR.

Exceptions must be recorded here before it merges. Record the hak category and asset filename and
contributor.

## Size exceptions

Resources are limited to 15 MiB by default. A reviewed exception uses exactly this machine-readable
form, with a repository-relative path and a non-empty reason. Remove `EXAMPLE ` when adding a real
exception:

`<!-- EXAMPLE srn-size-exception {"path":"srn_example/example.dds","reason":"Reviewed reason"} -->`

There are no content batches or size exceptions in the initial scaffold.

This import is delivered as a stack of one-component pull requests. The complete reviewed
provenance is introduced with the first content PR so every later intermediate tree passes the
repository's attribution check. Pack names and `docs/imports/` evidence below describe the complete
stack; those packs and reports appear incrementally, with the reports landing in the final
integration PR.

## Vendored model tooling

`tools/vendor/nwnmdlcomp/NWN_compDcomp.exe` and
`tools/vendor/nwnmdlcomp/nwnmdlcomp.exe` were copied byte-for-byte from
`SWLOR_NWN/SWLOR_Haks` on 2026-09-11 at the operator's request. They are unsigned 32-bit Windows
legacy utilities. Exact sizes, SHA-256 hashes, authorship visible in the embedded command-line help,
and usage restrictions are recorded in `tools/vendor/nwnmdlcomp/README.md`. Vendoring records
provenance and reproducibility; it does not assert a new license over either executable.

## Vendored texture tooling

`tools/vendor/nwn_crunch/` contains the Windows x64 distribution of NWN Crunch 0.9 downloaded
from Neverwinter Vault on 2026-09-11 at the operator's request. The source archive SHA-256 is
`53FCBC8BD7CBDC451EF9425C1D50C0916B20E37FD982A651CB36411DA146C198`.
The executable and archive hashes, source URL, and usage are recorded in
`tools/vendor/nwn_crunch/PROJECT.md`. NWN Crunch is distributed under the Zlib license.
## MDRNEE tileset import (2026-09-10)

Candidate content from `mdrnee_tile.hak` was analyzed under the `mdrnee_tile` import profile.
The verified source SHA-256 is
`B52CFAA8823826B1262AB19836D66C0DD04797AC2DD02ED9C03FE37309C59F44`.
The curated batch populates `srn_t_common`, `srn_door`, `srn_skybox`, `srn_2da`, and the tileset packs
listed below. The complete per-resource
origin, hash, disposition, dependency evidence, and recommended landing are recorded in
`docs/imports/mdrnee_tile-manifest.json`.

| Pack | Friendly tileset name |
|---|---|
| `srn_t_dgt04` | D20 Modern Exterior |
| `srn_t_fcx01` | D20 Futuristic City SW |
| `srn_t_fifi` | D20 Bunker PHoD |
| `srn_t_flow_pa` | D20 Parking Garage |
| `srn_t_nac01` | D20 ServiceDucts |
| `srn_t_net01` | D20 VirtuNet |
| `srn_t_shp02` | D20 Starship Interior SW |
| `srn_t_sjm01` | D20 SJ Metal Interior |
| `srn_t_tbx78` | D20 Modern Facility |
| `srn_t_tfb01` | D20 Modern Interior |
| `srn_t_tjsb0` | D20 Secret Base |
| `srn_t_udp1` | D20 Suburbs UDP |
| `srn_t_udp2` | D20 Office Interiors UDP |
| `srn_t_vac01` | D20 Space |
| `srn_t_vmp01` | D20 Planetscape |
| `srn_t_vmr01` | D20 Alien Ruins |
| `srn_t_zsf01` | D20 SciFi Base CQ |

Known upstream visual limitation: `zsf01_a01_01.mdl` references the texture
`zsf01_stonespdr`, but no matching TGA or DDS is present in the imported source HAK or the
inspected MDRNEE staging assets. The tileset remains usable, with the affected mesh potentially
showing the engine fallback texture. This is accepted as non-blocking until a provenance-compatible
source texture is located; no substitute texture is inferred or fabricated.

The source archive credits D20 Modern contributors including Stacy, Fuzzwolf, Goudea/Enki,
Jezira, Horred the Plague, JDA, Chandigar, CaveGnome, ChicoCQ, Tom Banjo, DrHoo,
Plush Hyena of Doom, Vanya Mia, Vahnhaunt, Yumi-Chan, Veldin, and the Dark Times team.
The exact upstream project was verified at
`https://gitea.raptio.us/Jaysyn/d20ModernEE`, commit
`c01271d3ba053ada6d75bc070c5cf1ab94ec29c6`. Its README identifies the repository as the d20
Modern EE development source, and `src/haks/mdrnee_tile/txt/credits.txt` carries the same tileset
credits. The repository has no LICENSE, LICENCE, COPYING, or equivalent file; public source
availability is therefore provenance evidence, not by itself a permission grant.

Redistribution instead rests on the operator-reviewed Neverwinter Vault permission for the
underlying D20 Modern Haks Version 2.2: **Open — free and open only when the consuming project is
also open**, with reuse in other projects allowed and contributor acknowledgement requested. The EE
repackage is attributed to Jaysyn and records curator Vanya Mia's permission. This repository is
publicly accessible and preserves the full attribution, so the curated import is permitted here
while those conditions remain true. These assets retain their upstream permission terms and are not
relicensed under the repository's default PolyForm license.

`srn_2da/doortypes.2da` is generated from the NWN:EE 89.8193.37-17 (`r1284`) base table with
the reviewed imported user/reserved rows substituted and relocated as recorded in the import
profile. `genericdoors.2da`, `skyboxes.2da`, `ambientmusic.2da`, and `ambientsound.2da`
are likewise generated baseline-preserving merges. The eleven companion edge tables retain their
source archive bytes.

The companion `mdrnee_tlk.tlk` has verified SHA-256
`18620A3D984410024C79BDA7647A100A0F23A1D14713B602CE37DEFC95361D0F`. Ten exact source
entries used by the merged ambient-sound and generic-door tables were migrated into the canonical
`srn.tlk`. The malformed D20 Shadowrun Exterior (`srt04`) GlassWindow value `1678190` is
outside both the EE base table and the custom-TLK range; it is repaired to the documented
synthesized text "Glass Window." Allocation,
deduplication, and 2DA replacement evidence is recorded in
`docs/imports/mdrnee_tlk-migration.md`,
`docs/imports/mdrnee_tlk-migration.json` and
`docs/imports/mdrnee_tile-string-ref-remaps.json`.

Ten supplemental door dependencies are recorded in
`docs/imports/mdrnee_door-dependency-manifest.json`. Four were selectively extracted from
`mdrnee_placeable.hak` with verified SHA-256
`E90B4F15EE15D8009D843C8B2EB70C77BD835FF0ED77F1534BB5EC4963B8A159`; six match committed
resources in the SWLOR HAK decomposition at `SWLOR_Haks` commit
`e349a8026ce226da1e2199295b0d9e34bc4e94f4`. They retain the provenance and permission terms of
their respective upstream content.

`t_door93.mdl` is retained as source content, but its `udp1_ohfire2` generic-door registration is
withheld because no matching `t_door93.dwk` was found. Its row remains blank to preserve all later generic-door appearance IDs. Restoring that registration requires the
original walkmesh or an engine-tested derivative; the final dependency report records this gap.

## MDRNEE audio import (2026-09-10)

`mdrnee_audio.hak` was imported under the `mdrnee_audio` profile. Its verified SHA-256 is
`012841691F5AB20EDAD8F2924DC63CC638C84CB8FD3D6A188F13388905E7742F`. All 142 BMUs land in
`srn_music`; 15 WAVs land in `srn_sound`, while `mdrnmod_barclub.wav` is explicitly excluded.
Exact hashes and the one differing EE identity
collision (`it_materialcloth.wav`) are recorded in `docs/imports/mdrnee_audio-manifest.json`.

The archive accompanies the same D20 Modern content distribution. The Neverwinter Vault project
page explicitly includes `mdrn21_music.rar` and publishes the collection as free and open when the
consuming project is also open, with reuse in other projects allowed and acknowledgement requested.
The operator accepts that project-level permission for this public, noncommercial NWN repository.
The archive contains no per-track authorship or license metadata, so this record does not separately
warrant ownership or clearance of any underlying third-party recording. The imported audio retains
the upstream D20 Modern/Vault terms and is not relicensed under the repository's default license.

Source: <https://www.neverwintervault.org/project/nwn1/hakpak/combined/d20-modern-haks-version-21>

## Arcology groups in Modern Exterior (2026-11-10)

D20 Shadowrun Exterior (`srt04`) differs from D20 Modern Exterior (`dgt04`) in five raised-ground tiles: an
arcology glass edge, its corner, a windowed edge and two gated openings, in the slots where Modern Exterior
has concrete walls and a stairway. Those five tile records are appended to `dgt04.set` as tiles 429-433 with
their door records, unchanged apart from terrain names spelled as Modern Exterior spells them, and offered as
five one-tile groups (`Arcology_Edge_01`, `Arcology_Edge_02_Window`, `Arcology_Corner`, `Arcology_Gate_01`,
`Arcology_Gate_02`) with matching feature entries in `dgt04palstd.itp`. They are groups so that they are
placed deliberately and never chosen at random beside the concrete walls. No existing tile or group number
in `dgt04.set` changes.

Their five models, five walkmeshes and the `arcology_torii01-03` textures move unmodified from `srn_t_srt04`
to `srn_t_common`, so that neither tileset needs the other's pack. `srn_t_srt04` keeps its own `srt04.set`
and palette and remains a supported tileset; it is not retired (it was retired the next day, see the
section after this one). `dgt05_i02_01.mdl` and `.wok`, a hospital tile both
tilesets list, moves from `srn_t_dgt04` to `srn_t_common` for the same reason: it was the one model
Shadowrun Exterior could not resolve without the Modern Exterior pack.

The windowed edge keeps its imported door type 117 (`GlassWindow`), although that `doortypes.2da` row names
`SRT04`, and no door row is added or changed. A Toolset test on 2026-11-10 showed why none is needed: when a
tile with a typed door hook is painted, the Toolset creates the hook's door itself, with the hook's door
type as its appearance, whatever tileset the row names. In a Modern Exterior area the windowed edge got a
type 117 door at its hook, and `Road_Huge_Hole` and `SubwayEntrance` got their type 58 invisible transition
doors, with no door placed by hand. The row's tileset only decides which areas list that door under
"Tileset Specific" in the door palette. The same test showed the five arcology groups in the palette, placed
three of them, and found only concrete tiles among the raised-ground tiles the Toolset chose by itself.
The other two, `Arcology_Corner` and `Arcology_Gate_02`, were placed in the Toolset on 2026-11-11: it built
the raised concrete round each, and the saved area was loaded in the game client, where both rendered with
their textures. `Arcology_Gate_02` got no door of its own, because its hook is the generic type 0, which the
Toolset leaves for the builder.
The work modifies the MDRNEE tile import under the same notice and attribution conditions.

## Shadowrun Exterior retired (`srn_t_srt04`; 2026-11-11)

The user retired D20 Shadowrun Exterior (`srt04`) on 2026-11-11. D20 Modern Exterior (`dgt04`) has held every
one of its tiles since the arcology groups were added, so the pack `srn_t_srt04` (`srt04.set` and
`srt04palstd.itp`, its only two files) is removed, with its `hakbuilder.json` entry and its area in the MDRNEE
tileset smoke module, which now has 17 areas and 24 HAKs. The last commit that holds the pack is `3122b09d`.

Tile numbers are not shared between the two sets. An area or a generator that used `srt04` moves to `dgt04`
with this map, under which all 264 `srt04` tiles name the same model as their `dgt04` tile:

| `srt04` tile | `dgt04` tile |
| --- | --- |
| 2 | 429 |
| 4 | 431 |
| 50 | 432 |
| 191 | 433 |
| 192 | 430 |
| any other tile below 191 | the same number |
| 193 and above | the number less 2 |

Only the models are the same. Under the map the two sets still differed in other tile fields when the pack was
removed (animation loops on 259 tiles, path nodes on 132, orientations on 102, minimaps on 34, and a few
visibility nodes, lights, doors and terrain corners), and in their terrain crossers, transitions and groups.
`dgt04.set` is the authority; nothing was copied across from `srt04.set` for the retirement.

`doortypes.2da` row 117 (`GlassWindow`) named `SRT04` as its tileset. Its only remaining user is `dgt04` tile
430, the windowed arcology edge, so the row now names `DGT04` and the door is listed under "Tileset Specific"
in Modern Exterior areas. The row number, model and text are unchanged.

Left as they are: the five `srt04_a0x_0y` models and walkmeshes in `srn_t_common`, which `dgt04` tiles 429-433
use; sixteen minimap images in `srn_t_dgt04` (`midg04_d35_01`, `midg04_e09_03`, `_04`, `_07`, `_09` to `_12`,
`_14`, `_16`, `_64`, `midg04_e11_05`, `midg04_f26_01` to `_04`) that only `srt04.set` named and no set names
now; the tileset's name in `srn.tlk`, whose row numbers must not move; and the `mdrnee_tile` import profile
and import records under `docs/imports`, which describe the import as it was made. Applying that profile again
would create `srn_t_srt04` again; drop it again if that is ever done. Module areas built on `srt04` do not open
without the set file and have to be moved to `dgt04` first.

## Stuffer Shack tile group (`srn_t_common`, `srn_t_dgt04`, `srn_t_udp1`; 2026-11-11)

The first envkit building: a single-storey convenience store as a 2 by 2 tile group, `Stuffer_Shack`, offered
in D20 Modern Exterior (`dgt04`, on Concrete) and D20 Suburbs (`udp1`, on Asphalt). Its four tile records are
appended to each set file (`dgt04` tiles 434-437, group 57; `udp1` tiles 676-679, group 106) and the group is
listed under Groups in each palette. No existing tile or group number changes. The four tile models
(`ek_ss_shack_t00`, `_t01`, `_t10`, `_t11`, compiled), their walkmeshes, the shared material and its maps
(`ek_ss_shack` colour, `_n`, `_s`, `_r`, glow `_i`, halo `_h`) live in `srn_t_common`, so neither tileset needs the
other's pack. The ground around the building is the `pavement` texture Modern Exterior's plain tiles use, already in
`srn_t_common`.

Origin: the concept sheet `01_stuffer_shack_convenience_store.png` was supplied by the SRN project operator (an
OpenAI-generated sheet from the operator's own brief). Its building views were redrawn locally with Qwen-Image
2.1 as plain references, and the 3D model was generated from those references by the operator's Meshy account
through the pinned `meshy-cli@0.4.0`, then remeshed by Meshy to 78,889 triangles. Attribution:
[Meshy](https://www.meshy.ai/). This is the first Meshy-made model in a production pack. The operator confirmed
on 2026-11-11 that the Meshy account is on a paid plan. Meshy's published
[licence guidance](https://help.meshy.ai/en/articles/9992001-can-i-use-meshy-assets-commercially-license-copyright-explained)
says paid users own the assets they generate from inputs they are authorized to use, so the Free-plan CC BY 4.0
condition that `docs/heads/evidence/NOTICE.md` allowed for does not apply to this model; it ships under the
repository's licence, with Meshy named here as the generator. That confirmation is the operator's statement and
was not checked against the account.

Modifications, all by `tools/envkit` (SRN project operator with Claude): the model was turned to the game's
axes and scaled to 5.6 metres; its textures were recompressed (colour 4096 DXT1, the other maps 2048); a glow
map and a halo sheet were made from its own colour for the sign, windows, door and OPEN sign; the mesh was
shared out over four tiles with a ground square each; and a walkmesh was generated from its shape, in which
the building stops movement and sight, the bollards stop movement only, and the slab is walked on at its own
height. The Meshy source, the full-detail spare, the references and the client captures stay in ignored
`output/envkit/`. Checked in the game client in a Modern Exterior area and a Suburbs area on 2026-11-11, and in
the Toolset the same day: both palettes list `Stuffer Shack 2x2` under Groups, and painting it laid the four
tiles in order with no turn (south-west, south-east, north-west, north-east), as the saved areas record. In
Modern Exterior the Toolset changed no other tile; in Suburbs it repainted the twelve tiles around the group as
its own grass-to-asphalt edges and corners.

Rebuilt later on 2026-11-11 under the same tile numbers, with what the stock tiles carry. Each tile has a
32-pixel picture for the area map (`ek_ss_shack_m00` to `_m11`, drawn from the model seen from above) and two
main lights for a builder to colour. The halo sheets fade out by day and in by night through the `day`,
`night`, `day2night` and `night2day` animations. Everything above 3 metres carries `tilefade`, with a black lid
(`ek_black`) drawn only while it is hidden. The north-west tile has a door record of type 58, the invisible
transition door this tileset already uses for its subway entrance, at the storefront door. Checked in the game
client: a coloured main light lit the building and the ground round it; the halos were absent by day and
present by night; with the client's second-storey setting on, the top and the sign's halo were hidden and the
lid shown (the setting has no effect while a script holds the camera in cutscene mode). Checked in the Toolset
in Modern Exterior: painting the group made the door by itself at the storefront, facing out; a group turned a
quarter turn before painting kept its four tiles together and its door on the turned front; Tile Properties
offered both main lights; and a highrise painted on the tiles beside the group left the group as it was. The
area map itself was not looked at in the client, and the door was not checked in Suburbs.

Rebuilt once more the same day: the signs on the east and west walls and the east window now glow, each with a
halo sheet facing out from its own wall, and the bins against the front wall stop movement without stopping
sight. Checked in the game client at night from both sides, with the sight line over the bins clear.

The group's lights-out material (`ek_ss_shack_o`) was added to `srn_t_common` the same day, so that tiles carry
the same set as lit props. A tile is no object, so its lights are put out for a player with `SetTextureOverride`
on its glow map and halo sheet; `docs/envkit/lights.md` is the account of both calls and of what was checked.

The four walkmeshes were rebuilt later on 2026-11-11, with nothing else of the group changed. The building's
shape is now followed to a quarter of a metre instead of a half, on a grid whose lines fall only where the
ground changes: 272 to 358 faces a tile where there were about 840 (the stock tiles of these two tilesets have
at most 500). The ramp onto the slab is still its outermost half metre. Checked in the game client in Modern
Exterior from the built packs: a script read the surface and the ground height at 864 points along six lines
across the group, an eighth of a metre apart, and every one agreed with the walkmesh as built; a sight line
along the west side was clear 0.1 metres outside the cells the wall closes and blocked 0.2 metres inside them; walkers reached the recess of the storefront door and a spot on the slab against the west wall
and stayed there, and one sent from the north-east to the south side went round the building. The two things
left unchecked above were checked the same day. In the client, in both tilesets, the area map showed the four
pictures in place, the roof in the middle of its dark ground, north up. In the Toolset, in Suburbs, painting
the group made one door by itself, of type 58, at the storefront and facing out, as the saved area records.
(That record read right and was wrong, as the Ares Depot's showed when its door was first used; it was written
again on 2026-11-11: see the Ares Depot tile group.)
The rebuild moved each tile's first main light with the finer survey, by about 0.15 metres on three tiles and
1.2 metres on the north-east one; a coloured main light was looked at again in the client at night and lit the
ground and the walls on every side. The area map was also looked at zoomed in, at its full 32 pixels a tile.

The path nodes of the four tiles were corrected the same day, in both set files and nowhere else. They had been
written as `H` turned 180, 270, 90 and 0, taking `H` to name the corner a building closes; it names the corner
that is walked, so each tile pointed its two exits into the building. The game plans a walk of more than about
two tiles from these nodes before it looks at a walkmesh, and walkers sent to the building from four tiles away
stopped short of it, one of them ten metres off against the east wall; nearer walks, which were all that had
been checked, go by the walkmesh and were right. `tools/envkit` now works each tile's node out from its own
ground, for a group of any size, from the engine's table of path nodes as nwn.wiki gives it (checked against
the walkmeshes of the 1,091 stock tiles of the two tilesets, which also settled that a turn is counter-clockwise).
The four tiles are now `H` 0, `H` 90, `I` 270 and `I` 270. Checked in the game client in Modern Exterior: the
same three walkers from four tiles away and more each reached their spot. Checked too with two throwaway groups
made from the same model at other sizes, three tiles by three and a single tile, which are in no pack: six
walkers from the far corners of the area reached their spots beside them, and in the Toolset the larger was
listed under Groups and laid its nine tiles in order, the single one under Features, with no other tile changed.

Later the same day the rest of what a group carries was checked at those two sizes, on throwaway groups built
with lit parts, a halo, a hidden top, main lights and a door, in no pack. In the client at night both were lit
with their halos, and with the player free their tops hid under the black lid. On the single tile the sign's
glow stayed in the air over the hidden top: one halo card held the sign and the windows under it, and a card
went or stayed whole. A halo card with lights on both sides of the hiding height is now cut there, going by
where the lit parts it spreads lie (one whose lights are all on one side stays whole, as before, and a light
that reaches less than a quarter metre across the height counts on one side only). That rule changes one card
of the shack: the east-wall card of `ek_ss_shack_t01`, from 0.40 to 4.80 metres, is cut at 3.0 metres, so the
east sign's glow now hides with the
sign while the east window's stays, as seen in the client; the other three tiles were rebuilt byte for byte the
same. In the Toolset, in Modern Exterior, painting each of the two groups made one door of type 58 at its hook,
as the saved area records.

A third throwaway group, two tiles with a walled yard whose only way in is a gap 2.5 metres wide off the middle
of the side the tiles share, showed the path nodes still wrong for such ground. A side had been counted an exit
only where it was open at its middle; walkers sent into the yard stopped at its walls, one from the far corner
of the area and one from 7.5 metres away in the next tile. With that side stated as an exit all four walkers
reached their spots, so the game finds an opening wherever it is along a side. A side is now an exit where a
metre of it is open anywhere. The shack's four tiles are therefore all `A` in both set files (each tile's strip
of pavement reaches all four of its sides), and nothing else of the shack changed. Checked in the client after
the change: the three far walkers reached their spots at the shack in Modern Exterior and in Suburbs, six
reached theirs beside the three-by-three and the single tile, and four theirs in and beside the yard.

## Stuffer Shack props (`srn_placeable`, `srn_2da`; 2026-11-11)

Ten envkit props from the same concept sheet as the Stuffer Shack tile group join `srn_placeable`, each with a
row appended to `srn_2da/placeables.2da` (22740-22749, labelled `[envkit]Stuffer Shack, ...`): vending machine
`ek_ss_vending`, ATM `ek_ss_atm`, snack rack `ek_ss_snacks`, drink case `ek_ss_drinks`, security camera
`ek_ss_camera`, rooftop unit `ek_ss_hvac`, street clutter `ek_ss_clutter`, trash can `ek_ss_trash`, recycling bin
`ek_ss_recycle` and sandwich board `ek_ss_board`. No existing row changes. Each prop is a compiled model, a
box collision file, a material file and its maps (colour 1024 or 2048, the other maps at half that).

Origin: each prop was cropped from the operator's concept sheet and redrawn locally with Qwen-Image 2.1 as a
plain reference. Seven were then generated by the operator's Meshy account through the pinned
`meshy-cli@0.4.0` at 4,000 to 11,000 triangles (attribution: [Meshy](https://www.meshy.ai/); paid plan, as the
tile group's entry above records). Three, the trash can, recycling bin and sandwich board, were generated
locally with Pixal3D on Trellis 2 in ComfyUI and reduced to 5,000 to 8,000 triangles. No third-party mesh or
texture was used.

Modifications, all by `tools/envkit` (SRN project operator with Claude): each model was turned to the game's
axes and scaled to a stated height; the locally generated ones were stood upright; the sandwich board was
rebuilt as its front sheet and a half-turned copy, because the generator invented its back; textures were
recompressed. The vending machine, ATM and drink case have a glow map and a halo sheet for their lit parts,
and a second material (`<name>_o`, with the shared black halo `ek_off`) that a script swaps in with
`ReplaceObjectTexture` to put their lights out; that needs the placed object not to be static. Checked in the
game client on 2026-11-11 from the pack's files and these table rows, lights on, out and on again. The rows
had no blueprints or palette entries at that point; both were added later the same day (below).

Converted again later on 2026-11-11 under the same rows. The collision block of each prop now follows its
footprint with the empty corners cut (an eight-sided outline; a box-shaped prop keeps its box). The security
camera hangs 2.6 metres above the spot it is placed on and has no block to walk into. Halo sheets face the way
their light does. Checked in the game client from the pack's files by day and by night, lights on, out and
on again.

Each prop also has a blueprint in `srn_placeable`, named as its model (`ek_ss_vending.utp` and so on): scenery
that cannot be destroyed or used, static except for the three lit props, whose lights a script must be able to
reach. So that the Toolset offers them, the pack carries `placeablepalstd.itp`: the game's own standard
placeable palette (104,993 bytes, SHA-256 `a682f56ff787eb675946413e1abb4e14d4512bec67ddff37ec822ed2ad1b9a65`,
read from the installed game, version 89.8193.37) with these ten blueprints added under the Modern Exterior and
Modern Interior categories of the pack's `placeablepal.itp`. Every blueprint the game's palette lists is kept
under the category it had. Made by `tools/envkit` (`envkit blueprints`). Checked in the Toolset on 2026-11-11:
the Standard tab listed the blueprints under their categories, and a painted trash can and vending machine were
saved with their rows, names and static settings.

The rows, tiles and groups this project adds are listed in `docs/additions/catalog.json`.

## Ares Depot tile group (`srn_t_common`, `srn_t_dgt04`, `srn_t_udp1`; 2026-11-11)

The second envkit building: a fortified corporate security depot with a guard tower, a vehicle door and a fenced
yard, 12.35 metres to the top of its masts, as a 3 by 3 tile group, `Ares_Depot`, offered in D20 Modern Exterior
(`dgt04`, on Concrete) and D20 Suburbs (`udp1`, on Asphalt). Its nine tile records are appended to each set file
(`dgt04` tiles 438-446, group 58; `udp1` tiles 680-688, group 107) and the group is listed under Groups in each
palette as `Ares Depot 3x3`. No existing tile or group number changes. The nine tile models (`ek_ad_depot_t00`
to `_t22`, compiled), their walkmeshes, area-map pictures (`ek_ad_depot_m00` to `_m22`), the shared
material and its maps (`ek_ad_depot` colour, `_n`, `_s`, `_r`, glow `_i`, halo `_h`) and the lights-out material
(`ek_ad_depot_o`) live in `srn_t_common`.

Origin: the concept sheet `02_ares_security_services_depot.png` was supplied by the SRN project operator (an
OpenAI-generated sheet from the operator's own brief). Its building views were redrawn locally with Qwen-Image
2.1 as plain references, and the 3D model was generated from those references by the operator's Meshy account
through the pinned `meshy-cli@0.4.0`, then remeshed by Meshy to 177,859 triangles under the 200,000-triangle
budget the operator set for larger buildings on 2026-11-11 (a first remesh to 88,454 triangles was set aside).
Attribution: [Meshy](https://www.meshy.ai/); paid plan, as the Stuffer Shack tile group's entry above records.
The name and emblem on the signs are those of a fictional corporation of the Shadowrun setting, as the concept
sheet drew them. Meshy added a second sign to the rear wall that the references do not show; its small
lettering was not legible and is painted over in the sign's own black, leaving the name and the emblem.

Modifications, all by `tools/envkit` (SRN project operator with Claude): the model was turned to the game's axes
and scaled; its textures were recompressed (colour 4096 DXT1, the other maps 2048); a glow map and a halo sheet
were made from its own colour for the roof sign and the tower windows; the mesh was shared out over nine tiles
(14,919 to 28,138 faces each, with the fence's sheets) with a ground square, a map picture and two main lights
each; everything above
5.2 metres carries `tilefade`; and a walkmesh was generated from its shape (442 to 826 faces a tile, where the
stock tiles of these two tilesets have at most 500). The north-east tile has a door record of type 58, the
invisible transition door, at the personnel door beside the vehicle door. The four corner tiles have path node
`A`, the four between them `I` (each open to the three sides away from the building), and the middle tile, all
building, `T`. The Meshy source, the full-detail spare, the references and the client captures stay in ignored
`output/envkit/`.

The group was first built at 9.5 metres on 2 by 2 tiles, the height at which the building filled four tiles.
That build was checked in the client and the Toolset and never published. Seen with a character at its door it
was too small: the door leaf measured about 1.6 metres against a figure of about 1.8. The operator chose 1.3
times that size on 2026-11-11, which makes the leaf about 2.1 metres by 0.98, and the 2 by 2 group was taken out
of the set files, palettes, pack and catalog and this one put in under the tile and group numbers it had freed.
Two things found on the first build stand. Its path nodes were first worked out with the kerbs between the
fence and the tile edge, half to three quarters of a metre wide, counted as ways through, and two of four
walkers sent from the far corners stopped short; a side now joins another only through ground a metre square
can stand on. And its first night look had a white wall beside the tower glowing and the tower windows dark;
the lit parts were restated, the tower windows by their colour.

Checked in the game client on 2026-11-11, as the 3 by 3 group. In a Modern Exterior area: by day from all four
sides and from above, with four walkers from the far corners of the area reaching the personnel door, the rear
and both sides, and the figure at the door standing under the top of its leaf; by night, where the roof sign
and the tower windows were lit and the rest was not; with `SetTextureOverride` as `docs/envkit/lights.md` gives
it, which put the lights and their halo out for the player and brought them back; with the player free and the
client's second-storey setting on always, where everything above 5.2 metres was hidden under the black lid; and
on the area map, which showed the nine pictures in place. In a Suburbs area by day: the same four walkers
reached their spots. Checked in the Toolset the same day, from the built packs: both palettes list
`Ares Depot 3x3` under Groups; painting it laid the nine tiles in order with no turn, as the saved areas
record, changed no other tile in Modern Exterior and repainted the sixteen tiles around it as asphalt edges and
corners in Suburbs; and in each it made one door by itself, of type 58, at the personnel door.

Checked further the same day, the group turned before painting and its door used as a transition. In the
Toolset, in Modern Exterior, the group was turned a quarter turn while it was pending (a right-click) and
painted: the saved area has the nine tiles turned together, no other tile changed, and the door moved and
turned with them. In the client, from that saved module, four walkers from the far corners reached the door,
the rear and both sides of the turned building. The door was then given an area transition to a waypoint in
the module's other area and clicked. The player walked up to it and nothing happened, and the blue plane the
game draws on a transition under the pointer stood out of the wall at a right angle. The door record was wrong
twice over, as `tools/envkit` wrote it, and the Stuffer Shack's with it: it was turned by the way the door
faces, where the set file wants that plus 90 degrees; and it lay on the door leaf, inside the ground the wall
closes, where no character can stand. With the saved door corrected by hand (turned a quarter turn, drawn 0.6
metres out of the wall) a click took the player to the other area, with the door's click script blank as the
Toolset leaves it, and a wooden door there linked back to it brought them out in front of the depot's door.
`tile.doorstep` now turns a hook and draws it out to open ground (the depot's by 0.625 metres, the shack's by
0.25), `convert.load_models` refuses a hook of any type but 58 (the user's rule of 2026-11-11, until further
notice), and both groups' door records were written again in both tilesets; their tiles came out of the
rebuild byte for byte the same.

The model's perimeter fence came back with nothing in its frames and its chain-link painted on the building
wall behind them, which showed when the fence was seen from an angle (the user, in the client, 2026-11-11).
On 2026-11-12 the fence was given its mesh and the wall was cleared, with no new generation. Six upright
sheets were hung in the frames (west, east, and the four short runs to the front and rear walls; 840 faces
over six of the nine tiles), cut into squares 0.76 metres a side that each show the whole of one wire
picture, `ek_ad_depot_w` (128 pixels, DXT5, 22 KB, drawn by `tools/envkit`), see-through between the wires.
The wires have a picture of their own because drawing them on the building's colour picture gave that an
alpha channel and doubled it, to 22 MB, over this repository's limit for one resource; it stays as it was,
11 MB with no alpha. The wall and walkway behind each run, from 1.75 to 4.3 metres up, were blurred over
0.12 metres and their relief levelled, which takes the painted mesh off and leaves a plain, soft grey
(`smooth` and `fence` in the game set; `convert.retouch`, `convert.sheets`). The tiles' walkmeshes, path
nodes, lights and door record came out the same; the area-map pictures changed slightly with the colour.
Looked at in plain software pictures of the finished model from each corner and along the east and west
sides: the sheets stand in their frames from pillar to pillar and the wall behind shows no mesh.

Checked in the game client and the Toolset on 2026-11-12, once the user let client runs go on. The fence, in a
Modern Exterior area from the rebuilt tiles: by day, each run seen close and slantwise from outside, both long
sides, all four corners and from above, shows wire mesh in its frames that the wall, the walkway and the far
fence are seen through, and no mesh on the wall behind; by night under the tiles' main lights the mesh takes
the light as the frames do. The sheets are the first tile parts here to show a picture with an alpha channel
and no material file, and the client draws them see-through as they are. The hidden top: with the client's
second-storey setting on its default (1, never) the top stays whatever the camera does; on 0 the top stays
while the player is seen clear of the building, at the door, beside it or far off, and goes under the black
lid when the building stands between the camera and the player; 2 (always) was checked on 2026-11-11. The
door, from the built packs: the Toolset, painting `Ares Depot 3x3` straight in Modern Exterior, made one door
of type 58 at the hook the set file now gives (0.625 metres out from the leaf, turned 180 degrees) and
changed no other tile; in the client, with only an area transition set on that door, the blue plane under
the pointer lay flat over the door's face, one click took the player to the waypoint in the other area, and
a wooden door there linked back brought them out standing on the step in front of the depot's door, 0.8
metres from the hook.

The first smoothing took the painted mesh off the wall's colour and relief only. The generator had put the
same mesh into the roughness and metallic maps of those texels, where it was left to catch a glancing light
(found measuring the maps in review, 2026-11-12: neighbouring texels differed by 3.8 and 4.3 of 255 there,
against 0.6 in the smoothed colour). `convert.textures` now smooths those two maps over the same texels and
reach, and the specular map is made from the smoothed metal; the differences fell to 0.3 and 0.4. Only the
group's roughness and specular maps changed in the rebuild. Seen again in the client by day and by night,
slantwise along the east and west fences: nothing looks different from the first check.

A third review on 2026-11-12 changed how the same work is done, and the group was built once more. Each
smoothed part is now worked on within its own texels and their margin instead of over the whole picture, and
parts are kept apart in the roughness and metallic maps as they were in the colour; the glow map is made from
the colour picture as retouched; the fence's sheets close the ground under them in the walk survey; and a
fence's ends, a door's measurements and the height of the ground under a door's hook are checked. For this
building none of that changes what is seen or walked: the models, walkmeshes, path nodes and door record came
out byte for byte the same, and the colour, roughness, specular, glow and halo pictures and five area-map
pictures differ slightly (the colour in 0.1 per cent of its texels, where smoothed parts meet; the glow in
0.001 per cent). Seen again in the client by day and by night from the same ten viewpoints: nothing looks
different from the checks before.

The Stuffer Shack's corrected door record, and both groups' doors in the Suburbs tileset, were checked in the
Toolset and the game client later on 2026-11-12, from the built packs. The Stuffer Shack was painted in a Modern
Exterior area, and the Stuffer Shack and the Ares Depot in a Suburbs area; the Toolset made a door of type 58
at each hook as it was painted and saved the three (the shack's 0.18 metres up, the depot's 0.32). Each door
was then given an area transition to a waypoint in front of the next and nothing else of it was changed, and
in the client a click on each door took the player on: from the shack in Modern Exterior to the shack in
Suburbs, from there to the depot, and from the depot back to the first.

## Ares Depot props (`srn_placeable`, `srn_2da`; 2026-11-11)

Fifteen envkit props from the same concept sheet as the Ares Depot tile group join `srn_placeable`, each with a
row appended to `srn_2da/placeables.2da` (22750-22764, labelled `[envkit]Ares Depot, ...`): reception desk
`ek_ad_desk`, surveillance console `ek_ad_console`, equipment lockers `ek_ad_lockers`, armory rack
`ek_ad_armory`, watch booth `ek_ad_booth`, vehicle gate `ek_ad_gate`, concrete barrier `ek_ad_barrier`,
checkpoint terminal `ek_ad_terminal`, drone dock `ek_ad_dronedk`, turret `ek_ad_turret`, gear crate
`ek_ad_crate`, pylon sign `ek_ad_pylon`, wall sign `ek_ad_sign`, rooftop unit `ek_ad_rooftop` and fence section
`ek_ad_fence`. No existing row
changes. Each prop is a compiled model, a collision file, a material file and its maps (colour 1024 or 2048, the
other maps at half that), and a blueprint named as its model, offered through the pack's `placeablepalstd.itp`
under the Modern Exterior and Modern Interior categories.

Origin: each prop was cropped from the operator's concept sheet and redrawn locally with Qwen-Image 2.1 as a
plain reference, then generated by the operator's Meshy account through the pinned `meshy-cli@0.4.0` at 1,623
to 12,051 triangles (attribution: [Meshy](https://www.meshy.ai/); paid plan, as the Stuffer Shack tile group's
entry above records). No third-party mesh or texture was used. The references for the equipment
lockers, armory rack, checkpoint terminal, drone dock and turret were drawn without the fictional corporation's
name and emblem; the other props keep what the sheet drew on them.

Modifications, all by `tools/envkit` (SRN project operator with Claude): each model was turned to the game's
axes and scaled to a stated height, and its textures were recompressed. The wall sign hangs 2.4 metres above
the spot it is placed on. Ten props (all but the lockers, barrier, crate, rooftop unit and fence) have a glow map
for their lit parts, nine of those a halo sheet as well, and a lights-out material (`<name>_o`) as
`docs/envkit/lights.md` describes; their blueprints are not static, so that a script can reach them. Three
props were retouched after the first client check. The turret came back with its barrel along the model's side
and is turned a quarter turn, so that it points to the front. The rooftop unit's colour is multiplied by 0.8:
it matched its own pale reference and stood out nearly white beside the others by day. Meshy made the fence's
chain-link mesh two solid smeared panels; its posts, rails, barbed wire and concrete base are kept, and the two
panels are redrawn by place on the model as a diamond mesh of 16 millimetre wire 90 millimetres apart, seen
through between the wires (the colour map of this one prop has an alpha channel, DXT5), with the relief map
levelled there. Its concrete base came back with a smeared red hazard marking on the right half of its front
and a fainter one on the right half of its back. On 2026-11-12 both were taken off by their tint, with no new
generation (`smooth` with `tint` in the game set: only the reddened texels change, each to the concrete about
it, and the rest of the face keeps its weathering; smoothing the whole face was tried first and left a plain
panel beside weathered ones), and the mesh's wires were given the posts' tone (88, 88, 85; at 118, 122, 126
they read lighter than the posts). The prop's colour, relief, roughness and specular maps changed and its model
did not. Seen in the client the same day from the converted files that were copied into the pack, by day, from
front and back, square and close on each half of the base. The model also came back with a hole: on the front
of the base's left half two of its faces lie over each other and leave a wedge between them open, through
which the ground showed. The same day it was closed with one face between three of the model's own vertices,
drawn with their own places on the picture (`close` in the game set; `convert.closed`); the model gained that
face and no vertex. The picture under the wedge had never been drawn on by the generator and held a broken
piece of the left hazard stripe, so that stripe was taken off by its tint as the smears were: the front of the
left half now shows two stripes where the back shows three, with a paler patch where the third was. Seen in
the client again from the same viewpoints. Left as generated: on the back the stripes are blurred at one
corner. The mesh was first
laid by each texel's x + y, which put the wires on the two faces of a panel out of step by the panel's
thickness; since 2026-11-12 it is laid along the way each panel runs, so one face's wires stand behind the
other's (only the colour map's alpha changed; seen in the client by day, square, slantwise and close, with a
barrier behind it seen through the mesh).

Checked in the game client on 2026-11-11: by day and by night with their lights on, from the converted files
that were copied into the pack; the fence, turret and rooftop unit again by day after their retouching, from
front, back and side, with a figure behind the fence seen through its mesh from both faces; and by night from
the pack's files, where `ReplaceObjectTexture` put the lights of all ten lit props out and brought them back.
Checked in the Toolset the same day, from the built packs: the Standard tab lists the fifteen blueprints under
their Modern Exterior and Modern Interior categories, and a painted fence section and turret were saved with
their rows and names, the fence static and the turret not.

The wall sign was first published dark. Its lit parts were boxed where the model stood before it was hung 2.4
metres up, so the boxes held none of it: its glow map was black and it had no halo, and the night check above,
which looked at the ten lit props together, did not catch it (found reading the glow map in review,
2026-11-12). The boxes were moved up with the model and the sign converted again: its glow map and model
changed and it gained a halo sheet (`ek_ad_sign_h`); its row, blueprint and other maps are as they were.
`tools/envkit` now refuses a lit, painted, smoothed or wire-mesh box that holds none of the model, and a set
whose box or fence lies wholly above or below its model. Checked in the game client the same day, from the
pack's files, by night beside the pylon sign: the sign's face and light bar are lit with a soft halo, go dark
with `ReplaceObjectTexture` and come back.


Four props light what stands round them since 2026-11-14 (operator, of the lamps of the older sets: "Yes"),
each by a light in its row of `placeables.2da`; no model or other file of theirs changed. The watch booth is
lit from its floodlight (lightcolor row 3, bright white), and the vehicle gate from its left post's top light,
the checkpoint terminal from its top lamp and the drone dock from under its arm (row 2, white). Since 2026-11-15 the terminal only glows again and the dock's light is row 1, dim white (operator, of the night
captures: "several of those prop lights are too bright", "cast lights should only be on things that should
actually cast light into an area in addition to glowing"). The armory rack, terminal, drone dock and wall sign
had their halo sheets remade the same day, each lit part measured on its best-lit upright side, from the
converted sources restored from the archive, and were seen by night in the game client. A row holds
one light, and the game draws a star-shaped flare where it stands: the gate's was first set between its posts,
where the star hung on the bare beam, and was moved to a post's lamp; its other post's light and the dock's
pillar lamps only glow. Checked in the game client the same day, by night: from the converted files of
2026-11-11, restored from the archive of the worktree they were made in
(`phenomorpher-worktree-output-2026-11-14-v1`) and the same byte for byte as the pack's, the ground and the
figures round each lit; and from the pack's files, where the lights of the ten lit props, these four's cast
light among them, were put out by script and brought back.
## Saeder-Krupp Yard tile group (`srn_t_common`, `srn_t_dgt04`, `srn_t_udp1`; 2026-11-12)

The third envkit building: a grey and yellow logistics and fabrication yard with three roller-shutter loading
docks under a Saeder-Krupp sign, a DENVER FRFZ tower bay to the west, an open crane bay to the east and a
service side to the north, with a fenced yard in front, as a 3 by 3 tile group, `SK_Yard`, offered in D20
Modern Exterior (`dgt04`, on Concrete) and D20 Suburbs (`udp1`, on Asphalt). Its nine tile records are appended
to each set file (`dgt04` tiles 447-455, group 59; `udp1` tiles 689-697, group 108) and the group is listed
under Groups in each palette as `Saeder-Krupp Yard 3x3`. No existing tile or group number changes. The nine
tile models (`ek_sk_yard_t00` to `_t22`, compiled), their walkmeshes, area-map pictures (`ek_sk_yard_m00` to
`_m22`) and the materials and maps of the ten models the group shows live in `srn_t_common`: the group's own
(`ek_sk_yard`) and one for each model placed in it (`ek_sk_yardp1` to `p9`), each with its colour, `_n`, `_s`
and `_r` maps, and for the five with lit parts a glow map `_i` and a lights-out material `_o`, four of them
with a halo `_h`.

Origin: the concept sheet `05_saeder_krupp_logistics_and_fabrication_yard.png` was supplied by the SRN project
operator (an OpenAI-generated sheet from the operator's own brief). The building is five models generated by
the operator's Meshy account through the pinned `meshy-cli@0.4.0` from references redrawn locally with
Qwen-Image 2.1. A first generation of the whole building as one model was set aside: one generation carries
one 4096-pixel picture, which on a building this size gave about 47 texels a metre against about 190 on a prop.
The operator then had it made in pieces (2026-11-12): the sheet's front and rear elevations were each cut into
a west, a centre and an east section, each section redrawn as a standalone block, and each block generated from
its front and rear views. The east block came back right on both faces. The west and centre blocks came back
with faithful rears and plain fronts, and their fronts were generated again from the front views alone; each
front stands back to back with the block it mends, each one's plain wall inside the other. The five models were
remeshed by Meshy to 41,959 (centre, rear), 31,641 (centre, front), 33,739 (west, rear), 24,905 (west, front) and
43,664 (east) triangles, 175,908 together, under the 200,000-triangle budget the operator set for larger
buildings on 2026-11-11 (the centre, centre-front and east blocks were remeshed a second time from the same
generations to come within it). Attribution: [Meshy](https://www.meshy.ai/); paid plan, as the Stuffer Shack
tile group's entry above records. The name and emblem on the sign are those of a fictional corporation of the
Shadowrun setting, as the concept sheet drew them; the sheet misspelt DENVER on the tower panel, and the
reference was drawn with it spelled right.

Modifications, all by `tools/envkit` (SRN project operator with Claude): each model was turned to the game's
axes and scaled, and placed in the group (`tiles.parts` in the game set) with five fence sections, the vehicle
gate, two utility barriers, two pallet stacks and two crate sets of the yard's own props; each model's
textures were recompressed (the building's colour 4096 DXT1, the other maps 2048). The building is sized by its
doors: the centre's rear service door, where the door record is, has a leaf of about 2.15 metres, and the west
blocks are scaled so that the annex's own door is 2.0 metres, which leaves the tower bay about 2.5 metres above
the centre's parapet; the east block's crane bay is lined up with the centre front. Glow maps were made from
the models' own colour for the sign, the lamps over the docks, two pole lamps, two floodlights, the lamp over
the west annex door and the red light on a stack, and the gate's beacons are lit as on the placeable. The
three dock doors' roller shutters came back as a wavy moiré, slats finer than the picture's texels: their faces
were smoothed and drawn again with a joint every 0.12 metres, the lettering between them left as generated
(operator, 2026-11-12). A railed-off square on the crane bay's floor, under a metre from the covered vehicle
beside it, left too narrow a way into the back of the bay and was taken off the east block (operator,
2026-11-12); the floor under it stays, with four small marks of its posts' feet painted on it. Nothing else was
retouched. The meshes were shared out over nine tiles (6,044 to 65,420 faces each) with a ground square, a map
picture and two main lights each; everything above 5.0 metres carries `tilefade`; and a walkmesh was generated
from their shape (1,456 to 2,656 faces a tile, where the stock tiles of these two tilesets have at most 500),
with ground too narrow to stand on, as between the fence's sections, closed in it. Each tile's path node was chosen
from its ground for the group as a whole (`tile.path_nodes`); three are stated in the game set (`tiles.nodes`: the
south-east tile V turned 90, the apron's H turned 270, the door's N), as the walk checks in the client showed walks
need.
The crane bay's floor and the docks' apron, 0.55 metres up, are walked at their own height and climbed over
their outer half metre. The north middle tile has a door record of type 58, the invisible transition door, at the service
door. The Meshy sources, the full-detail spares, the references and the client captures stay in ignored
`output/envkit/`.

Checked in the game client on 2026-11-12, in a Modern Exterior area laid from the pack's files: by day from
all four sides, two corners, the front and from above, and at the service door; by night, where the sign, the
lamps over the docks, the pole lamps, the floodlights, the lamp over the annex door and the gate's beacons were
lit and the rest was not; and with the player free, where everything above 5.0 metres was hidden under the
black lid. Seen from the south with the player inside the fence, the client cut the fence away about the
player's line of sight, as it cuts the lid away in the free views here and in the Ares Depot's; the fence is
whole in every other view and in the models. Painted in the Toolset the same day, in a Modern Exterior area and
in a Suburbs area, the group laid its nine tiles in order with no turn, and in each area made one door by
itself, of type 58, at the service door; in the Suburbs area the Toolset also repainted the sixteen tiles
around the group. With the two Toolset-saved areas' doors chained in the client, clicking the service door in
each took the player to the other area, where the group stood at its door as painted. Painted again turned, a
quarter turn in Modern Exterior and a half turn in Suburbs, the nine tiles turned together into their places and
the door moved and turned with them, and in the client its two doors took the player across and back again.
Four walkers sent from the far corners of a 90-metre area reached the service door, the yard inside the fence
(round the fence's ends) and both sides of the building, in a Modern Exterior area by night and a Suburbs area by
day, before the bay and apron were walked at their height. Built again with them walked and the railed-off square
taken away, walkers bound for the service door, the north and east sides, the apron and the bay gave up their walks
and walked straight at their targets until the fence or the building stopped them: the engine could not follow the
routes the tiles' path nodes planned (the old nodes joined ground outside the fence to the yard round its ends, split
the door's tile in two, and joined the bay to the apron only by the apron's south side). With the nodes chosen and
stated as above, the walk check of the same day (`envkit check group --mode walk`), in both areas, sent twelve
walkers from the far corners of the area to the service door, the four sides of the building, the apron, the front,
gap and back of the bay, the bay's far corner and the ground north of the building at two places, and one from the
next tile east into the bay's far corner: all thirteen arrived. By night `SetTextureOverride`, as `docs/envkit/lights.md` gives it, for the group's own model and the four
of its parts that are lit, put out the sign's glow, the pole lamps, the floodlights and the stack light and
brought them back; the sign's white lettering stays readable unlit, as paint.

## Saeder-Krupp Yard props (`srn_placeable`, `srn_2da`; 2026-11-12)

Fourteen envkit props from the same concept sheet as the Saeder-Krupp Yard tile group join `srn_placeable`,
each with a row appended to `srn_2da/placeables.2da` (22765-22778, labelled `[envkit]Saeder-Krupp Yard, ...`):
office desk `ek_sk_desk`, loading console `ek_sk_console`, tool lockers `ek_sk_lockers`, crate set
`ek_sk_crates`, pallet stack `ek_sk_pallets`, shipping container `ek_sk_cont`, vehicle gate `ek_sk_gate`,
forklift `ek_sk_forklift`, fuel dispenser `ek_sk_fuel`, fence section `ek_sk_fence`, security booth
`ek_sk_booth`, wall sign `ek_sk_sign`, pylon sign `ek_sk_pylon` and utility barrier `ek_sk_barrier`. No existing
row changes. The sheet's rooftop unit was not made: it is the Ares Depot's (`ek_ad_rooftop`). Each prop is a
compiled model, a collision file, a material file and its maps (colour 1024 or 2048, the other maps at half
that), and a blueprint named as its model, offered through the pack's `placeablepalstd.itp` under the Modern
Exterior and Modern Interior categories.

Origin: each prop was cropped from the operator's concept sheet and redrawn locally with Qwen-Image 2.1 as a
plain reference, then generated by the operator's Meshy account through the pinned `meshy-cli@0.4.0` at 1,713
to 12,223 triangles (attribution: [Meshy](https://www.meshy.ai/); paid plan, as the Stuffer Shack tile group's
entry above records). No third-party mesh or texture was used. The references for the office desk, tool
lockers, shipping container, forklift and fuel dispenser were drawn without the fictional corporation's name
and emblem; the crate set, vehicle gate, security booth and the two signs keep the branding the sheet drew on
them. The pallet stack is the first the concept sheets make, and stands for the two other sheets that draw one.

Modifications, all by `tools/envkit` (SRN project operator with Claude): each model was turned to the game's
axes and scaled to a stated height, and its textures were recompressed. The wall sign hangs 2.4 metres above
the spot it is placed on. Seven props (the desk, console, gate, fuel dispenser, booth and the two signs) have a
glow map for their lit parts, a halo sheet and a lights-out material (`<name>_o`) as `docs/envkit/lights.md`
describes; their blueprints are not static, so that a script can reach them. Meshy made the fence's chain-link
two solid panels; its posts, rails, razor wire and concrete base are kept, and the two panels are redrawn by
place on the model as a diamond mesh of 16 millimetre wire 90 millimetres apart in the posts' tone, seen
through between the wires (the colour map of this one prop has an alpha channel, DXT5), with the relief map
levelled there. Nothing else was retouched. The shipping container came out 3.5 metres wide at 2.6 metres tall,
against 2.44 metres for a real one, and was left as generated.

Checked in the game client on 2026-11-12: by day from front, back and side with a figure for scale, from the
converted files; and by night from the pack's files, where `ReplaceObjectTexture` put the lights of the seven
lit props out and brought them back. Checked in the Toolset the same day, from the built packs: the Standard
palette lists the eight outdoor props under Modern Exterior and the six others under Modern Interior, and a
vehicle gate, wall sign, security booth, fence section, office desk and crate set painted from it were saved with
their rows, names and tags, the fence and crates static and the four lit ones not.


Two props light what stands round them since 2026-11-14 (operator, of the lamps of the older sets: "Yes"),
each by a light in its row of `placeables.2da`; no model or other file of theirs changed. The security booth
is lit from its roof floodlight (lightcolor row 3, bright white) and the loading console from its top lamp
(row 2, white). Since 2026-11-15 the console only glows again (operator: "the other terminal needs it's cast light removed
too"); its halo sheet was remade the same day and seen by night in the game client. The vehicle gate's amber beacons and lamps are warning lights and only glow: a white light set
between them hung a star-shaped flare in the air over the gate, and was taken out again. Checked in the game
client the same day, by night: from the converted files of 2026-11-12, restored from the archive of the
worktree they were made in (`phenomorpher-worktree-output-2026-11-14-v1`) and the same byte for byte as the
pack's, the ground and the figures round each lit; and from the pack's files, where the lights of the seven
lit props, these two's cast light among them, were put out by script and brought back.
## Rail Freight Depot tile group (`srn_t_common`, `srn_t_dgt04`, `srn_t_udp1`; 2026-11-13)

A generic rail freight depot laid out round two tracks, as one 8 by 8 tile group, `RF_Depot`, offered in D20
Modern Exterior (`dgt04`, on Concrete) and D20 Suburbs (`udp1`, on Asphalt): a weathered warehouse with a RAIL
FREIGHT sign and its dock warehouse behind it, a control tower, an office and a service bay with a fenced yard, a
covered loading platform beside the south track, a gantry crane over the north track on its own runways, and the
two tracks themselves, which run straight through the group, cross over at both ends into a passing loop and leave
by its west and east edges on tile-row centres. Its 64 tile records are appended to each set file (`dgt04` tiles
456-519, group 60; `udp1` tiles 698-761, group 109) and the group is listed under Groups in each palette as `Rail
Freight Depot 8x8`. No existing tile or group number changes. The 64 tile models (`ek_rf_depot_t00` to `_t77`,
compiled), their walkmeshes, area-map pictures (`ek_rf_depot_m00` to `_m77`) and the materials and maps of the ten
models the group shows live in `srn_t_common`: the warehouse's own (`ek_rf_depot`) and one for each model placed in
it (`ek_rf_depotp1` to `p9`: the platform, crane, tower, dock warehouse, office, service bay, track merge, straight
track and crane runway), each with its colour, `_n`, `_s` and `_r` maps. Nothing in the group glows; its tiles
carry the usual two main lights.

Origin: the yard's concept sheet `56_denver_rail_yard.png` was supplied by the SRN project operator (an
OpenAI-generated sheet from the operator's own brief, made generic at the operator's word: no city or company names,
"words like Freight and relevant symbols are ok"). The control tower, office and service bay were generated from
views of it redrawn locally with Qwen-Image 2.1. The warehouse, its dock warehouse, the loading platform and the
gantry crane were generated from four images the operator made with ChatGPT from one shared design
(`56b_rail_freight_depot.png`), taken as references as they were. All seven were generated by the operator's Meshy
account through the pinned `meshy-cli@0.4.0`; the buildings were remeshed by Meshy, the office generated a second
time after the first came back washed out. The building, its own triangles and those of the models placed in it
that are not props, is 175,896 triangles, under the 200,000-triangle budget for larger buildings. Attribution:
[Meshy](https://www.meshy.ai/); paid plan, as the Stuffer Shack tile group's entry above records. The track is
not generated: `tools/envkit/track.py` builds it, a 10 metre straight piece and a 30 metre merge of standard-gauge
track on ballast (rails 1.435 metres apart on concrete sleepers every 0.625 metres), and paints its maps. It builds
the crane runway the same way: a 10 metre piece of two crane rails a metre apart, 0.23 metres high, each on a sole
plate clipped to one concrete ground beam (operator: "i think we need to add the crane tracks, we'll need those as
a prop anyway and the scene looks weird without it"). The runway is also a placeable of the game set, to go into
`srn_placeable` with the yard's props.

Modifications, all by `tools/envkit` (SRN project operator with Claude): each model was turned to the game's axes
and scaled, its faces seen from behind turned round (but not the back halves of sheets made of two faces back to
back, which the first builds turned onto their fronts) and its normals turned to its faces, and placed in the group
(`tiles.parts` in the game set): the tracks on the rows' centres, the merges at both ends (the east one turned half
round), the platform west of the warehouse with its edge 1.7 metres from the south track's centre (operator: its
first place, across the warehouse's dock apron, was "not working out"), the crane over the north track between the
switches with a leg either side of it, outside both tracks' corridors, and four runway pieces under each leg on the
line of the short rails the crane came back standing on. Those were taken off the crane (its `clear`: about 500
faces under each leg, none higher than 0.26 metres; its wheels, 0.22 metres up, kept and standing on the runway's
rails). The crane and its runways stand a metre further north than first laid, where its north leg's edge lay on the
middle of the line between two tiles (see the checks below). The other buildings stand clear of the tracks. The
containers, light towers and rolling stock of the sheet are props a builder places, not parts. Each model's textures
were recompressed (the warehouse's and the larger buildings' colour 4096 DXT1, the other maps 2048). Retouching is
described below. The meshes were shared out over 64 tiles (0 to 15,085 faces each) with a ground square, a map picture and
two main lights each; everything above 4.5 metres carries `tilefade`; and a walkmesh was generated from their shape
(18 to 1,914 faces a tile, where the stock tiles of these two tilesets have at most 500). The tracks and runways are
drawn but walked flat across. The loading platform's deck, 1.24 metres up, is walked at its height where its stairs
lead up to it: the walkmesh climbs the stairs, and the deck's edge is closed elsewhere (operator: "the stairs up onto
platform, and the platform itself should be walkable"). Each tile's path node was chosen from its ground for the
group as a whole (`tile.path_nodes`); three are stated in the game set (`tiles.nodes`: the tile south-east of the
warehouse, `t04`, W with no turn; the tile east of the service bay's yard, `t06`, J turned 90; the tile north of it,
`t15`, I turned 270), as the walk checks in the client showed walks need. The tile at the warehouse's
door, `t23`, has a door record of type 58, the invisible transition door. The Meshy sources, the references, the
track sources and the client captures stay in ignored `output/envkit/`. Three flaws the first build left were
retouched (operator: "Fix these", 2026-11-13): the tower's sign read "PREIGHT", and the right of its P's bowl and the
end of its middle bar were painted over in the sign's ground colour to make an F (`paint`); a slit 1.4 to 2.3 metres
up the warehouse's long east wall was filled between its own vertices (`fill`); and the crane's leg sills, which
showed gaps from outside, were filled where they were open and given backs where their faces were wound inward
(`fill`, `inside` boxes). The crane prop has the same changes. Seen again in the client by day on 2026-11-14
(`envkit check group --mode day`): the tower's sign reads FREIGHT. The rebuilt walkmeshes differ from the last
walk-checked build only in how they are cut (at most 0.4 square metres of walkable ground on any of seven tiles), so
the walk check was not run again.

Checked in the client on 2026-11-13 (`envkit check group --mode walk`, in a Modern Exterior and a Suburbs area 14
tiles across). Walkers sent from the area's far corners arrived, in both areas, outside the warehouse's door, at its
south side, on the ground north of the crane's north leg, at both ends of its south leg and in the service bay's
fenced yard, at its corner furthest round from the yard's way in, and so did the walker sent there from the next
tile south. That one had walked straight at it and stopped against the yard's fence in every run before, and earlier
runs had counted it as arrived, half a metre from its target across the fence; the check now refuses a walker with
something in the way between it and its target (`checks.walled`). Walkers sent from chosen starts showed every walk
into the yard from the south or the east, from outside the group or inside it, walked into the fence, and walks from
the north arrived. With the tile east of the yard stated J turned 90, so that walks from the south go round and come
in from the north, and the tile north of it stated without its south side, which opened only onto the metre of yard
behind its fence, all of them arrived in both areas: from the next tile south, from three tiles east, from inside
the group south-east and east of the yard, from north-east of it, and one from the south to the ground just north of
the yard. After the runways were laid and the crane's stub rails taken off, the walk to the ground beside
the crane's north leg gave up in every run in both areas, though nothing walkable had changed. Swapping the tiles'
walkmeshes back showed it was the two tiles the leg crosses: their shared side's middle, where the engine puts the
exit between them, lay on the leg's edge. A metre further north it arrived. On the platform, in the build before the
runways, a walker from the ground east of the stairs reached the deck at their head and one sent nine metres along
the deck, over a tile line, arrived; one sent twenty metres along it gave up after about eight, and ones sent onto
its far end from the ground stopped at its edge. Long walks to the deck are not planned (the check sends none).

Rebuilt the same day without turning the back halves of two-faced sheets onto their fronts, which changed the
walkmesh faces of many tiles though not the ground walked on; the walk check passed again in both areas, every walker
arriving.

Painted in the Toolset on 2026-11-14 from packs built from main after the merge (`envkit toolset prepare --size
12`: an area 8 tiles across, the size used before, leaves the 8 by 8 group no room beside the start point). In one
user folder the group went down unturned in a Modern Exterior and a Suburbs area, in another a quarter turn in
Modern Exterior and a half turn in Suburbs. Each painting laid all 64 tiles (456-519 and 698-761) with the turn
asked for, and made one door of type 58 at the warehouse's hook, its place and bearing turned with the group, as
the saved areas record (`envkit toolset saved`). Nine of the yard's props were placed from the palette beside it,
from both of its categories, the light tower among them; each kept its `placeables.2da` row, name and static
setting (the light tower not static, the rest static). In the client (`envkit check doors`) clicking each
warehouse door, in both folders, took the player to the other area's door.

## Rail Freight Yard props (`srn_placeable`, `srn_2da`; 2026-11-13)

Twenty-one envkit props of the same generic rail freight yard as the Rail Freight Depot tile group join
`srn_placeable`, each with a row appended to `srn_2da/placeables.2da` (22779-22799, labelled `[envkit]Rail Freight
Yard, ...`): loading platform `ek_rd_platform`, gantry crane `ek_rd_crane`, crane rail `ek_rf_runway`, switcher
locomotive `ek_rf_switcher`, boxcar `ek_rf_boxcar`, tank car `ek_rf_tankcar`, flatcar `ek_rf_flatcar`, loading dock
`ek_rf_dock`, transfer shed `ek_rf_shed`, walkway `ek_rf_walkway`, stair tower `ek_rf_stairs`, office module
`ek_rf_office`, 20 ft and 40 ft containers `ek_rf_cont20` and `ek_rf_cont40`, crates on pallets `ek_rf_crates`,
hazmat drums `ek_rf_drums`, cable reel `ek_rf_reel`, pipe stack `ek_rf_pipes`, pallet jack `ek_rf_jack`, light
tower `ek_rf_light` and dumpster `ek_rf_dumpster`. No existing row changes. Each prop is a compiled model, a
collision file, a material file and its maps (colour 1024 or 2048, the other maps at half that), and a blueprint
named as its model, offered through the pack's `placeablepalstd.itp` under Modern Exterior (Structures, Streets)
and Modern Interior (Containers). The loading platform, crane and crane rail are the models the depot group shows,
offered for builders to place on their own; the rest are the yard's props, which the group leaves out.

Origin: the yard's props were cropped from the operator's concept sheet `56_denver_rail_yard.png` and redrawn
locally with Qwen-Image 2.1 as plain references, generic as the operator asked (no city or company names; the
containers without the sheet's mark). The loading platform and the gantry crane were generated from two of the
operator's ChatGPT images of the depot (`56b_rail_freight_depot.png`), taken as references as they were. All but
the crane rail were generated by the operator's Meshy account through the pinned `meshy-cli@0.4.0`, at 3,594 to
12,710 triangles as shipped (attribution: [Meshy](https://www.meshy.ai/); paid plan, as the Stuffer Shack tile
group's entry above records); the boxcar a second time. No third-party mesh or texture was used. The crane rail is
not generated: `tools/envkit/track.py` builds it, as the depot's entry above says.

Modifications, all by `tools/envkit` (SRN project operator with Claude): each model was turned to the game's axes
and scaled to a stated height, its faces seen from behind turned round (but not the back halves of sheets made of
two faces back to back) and its normals turned to its faces, and its textures were recompressed. The containers
were drawn out along their length to 6.06 and 12.19 metres at 2.6 metres tall (they came back a third to a half
short), and the 20 ft container's open door end was closed with two faces between its own vertices. The crane's
short stub rails under its legs were taken off, as in the group. The faces of the dumpster, the 20 ft container and
the loading dock were given backs (`inside`), since the client showed what stood behind them through the gaps of the
dumpster's slatted lid (operator: "the dumpster has some see through spots"), a slit at the container's door end and
an opening under the back of the dock's roller door; each now shows its own inside there. Two came out the wrong
size and were set again (operator: "resize the office module and light tower"): the office module from 3.0 to 3.9
metres tall, where its walls had stood 2 metres and its doors about 1.7, and the light tower from 7.5 to 5.0 metres,
where its lamp heads had been nearly 2 metres across. The trucks of the switcher, boxcar, tank car and flatcar were
drawn in across the track (`wheels`), their wheels having stood 0.15 to 0.2 m outside the rails (operator: "fix the
wheel spacing on the rolling stock"): below the trucks' tops, each truck by the same measure, so that the backs of its
wheels stand 0.68 m either side of the car's middle as a standard-gauge wheelset's do, the bodies above as they were.
The four were lifted 0.312 m, the track's height, to stand on its rails. Further flaws were
retouched (operator: "Fix these", and "one of the posts on the walkway is misplaced from the corner too"): the stair
tower's wavy handrails were taken off (`clear`, rods along the flights and boxes on the landings) and straight steel
ones built in their place (`built` railings, coloured from the model's own steel); the walkway, which no stairs led
up to, was given a straight flight of eleven treads, a stringer each side and handrails up to its deck's south edge,
with its south railing built again round the head of the stairs, and its north-east leg, generated 1.7 metres in
from its corner, was moved out to it (`move`) and the brace left standing out past the corner taken off; the office
module's roof ridge was filled at two notches (`fill`) and its smeared window panes covered by thin built panes of
plain dark glass inside their frames, with a frame-grey mullion over the one drawn light (`built` bars; the generated
glass lies in up to four layers that share their picture with other faces, so painting it was not enough). The crane's leg sills were mended as in the group. The light tower's four lamp heads glow on
their front faces: it has a glow map for them, a halo sheet and a lights-out material (`ek_rf_light_o`) as
`docs/envkit/lights.md` describes, and its blueprint is not static, so that a script can reach it. It also lights the
ground round it (operator: "Yes, try it", on whether its lamps cast light): its row names light colour 3 (bright
white) 4.2 metres up and half a metre in front of its mast, at its lamp heads. Meshy drew
lenses on the backs of the heads too; those stay unlit. Its halo sheet was remade on 2026-11-15, each lit part measured on its
best-lit upright side, and seen by night in the game client; its light stays. The loading platform is scenery to
walk round: its collision is a block over its footprint, and the game does not stand characters on a placeable
(tried in the client on 2026-11-13 with a walkmesh of walkable deck and stairs: walkers sent onto it stopped on the
ground at its edge; see `docs/envkit/sheet-runbook.md`). The depot group's platform is walked on.

Checked in the game client on 2026-11-13, from the converted files, by day from front, back and side with a figure
for scale (the dock, container, office and light tower again after the changes above); the light tower, office and
dumpster again by night; and the light tower from the pack's files by night, its
lamps lit, put out by `ReplaceObjectTexture` and on again, and once more with its cast light (the ground round it
lit, dark when put out by `SetPlaceableIllumination` and `RecomputeStaticLighting`, and lit again). The four cars
were seen again standing on laid track, low along the rails and from the side: their wheels on the rails. A lighter or darker triangle shows on a flat side of the
boxcar seen side-on, on either side and with the car turned either way round: the area's sky reflected in its large
smooth panels, not the model (its maps are even there, and splitting its faces small did not change it). The
walkway, stair tower, office module and crane were seen again by day on 2026-11-14 after the retouching above: the
walkway's stairs and moved leg, the tower's straight rails, the office's glass and the crane's sills. Not yet
opened in the Toolset.

On 2026-11-15 the gantry crane's collision file `ek_rd_crane.pwk` was written again (operator: "the crane placeable
should NOT block walking underneath it"): a block under each of its two legs in place of one on its whole
footprint, 13.9 metres of open ground between them (`walkUnder` in the game set, `convert.standing`). The model was
converted again from its archived source and came out byte for byte as the pack holds it, as did its maps; only the
collision file changed. In the game client a walker sent to the middle under the beam stood there, and one sent
through from side to side went straight.

On 2026-11-16 every envkit placeable in the pack was measured for the same fault (clear ground under it that one
block on its footprint shuts; 101 models). The transfer shed `ek_rf_shed`, a roof on four posts, was the only other:
its collision file was written again with a block under each post (`walkUnder`). The model was converted again from
its archived source and came out byte for byte as the pack holds it, as did its maps. Signs and banners hung over
head height had no block already. In the game client the same day a walker sent to the middle under the roof stood
there, and one sent through from side to side went straight.

## Iron Sight Arms tile group (`srn_t_common`, `srn_t_dgt04`, `srn_t_udp1`; 2026-11-14)

A street gun shop with an indoor range: a single-storey riveted steel shop front under an IRON SIGHT ARMS sign, with a
projecting pistol sign, and a long range wing behind it, as one 2 by 3 tile group, `Iron_Sight_Arms`, offered in D20
Modern Exterior (`dgt04`, on Concrete) and D20 Suburbs (`udp1`, on Asphalt). Its six tile records are appended to each
set file (`dgt04` tiles 520-525, group 61; `udp1` tiles 762-767, group 110) and the group is listed under Groups in
each palette as `Iron Sight Arms 2x3`. No existing tile or group number changes. The six tile models
(`ek_isa_shop_t00` to `_t21`, compiled), their walkmeshes, area-map pictures (`ek_isa_shop_m00` to `_m21`) and the
materials and maps of the two models the group shows live in `srn_t_common`: the shop (`ek_isa_shop`) and the range
wing placed in it (`ek_isa_shopp1`), each with its colour, `_n`, `_s` and `_r` maps, a glow map `_i`, a halo `_h` and
a lights-out material `_o`.

Origin: the concept sheet `59_iron_sight_arms_gun_shop.png` was supplied by the SRN project operator. The building is
two models generated by the operator's Meshy account through the pinned `meshy-cli@0.4.0` from references redrawn
locally with Qwen-Image 2.1 and enlarged to 2048 pixels with RealESRGAN x2plus before they were sent (operator,
2026-11-14: Meshy is given at least 2K). The operator had it made in pieces (2026-11-14): the shop was cut from the
sheet's three-quarter view and the range wing from its side view, each redrawn as a standalone block. The shop was
generated twice: the first redraw closed its cut side with a plain grey wall, which came back blank, and the second
keeps that side as the sheet's weathered steel with its two red stripes. The two models were remeshed by Meshy to
85,257 (shop) and 84,466 (wing) triangles, 169,723 together, under the 200,000-triangle budget for larger buildings.
Attribution: [Meshy](https://www.meshy.ai/); paid plan, as the Stuffer Shack tile group's entry above records. The
shop's name is the sheet's own invention.

Modifications, all by `tools/envkit` (SRN project operator with Claude): each model was turned to the game's axes and
scaled, and its textures were recompressed (colour 4096 DXT1, the other maps 2048). The building is sized by its door:
the shop's double door has a leaf of about 2.1 metres, and the wing is scaled so that the two roofs meet at one
height. The wing stands behind the shop, turned a quarter, its RANGE wall flush with the shop's west wall; it is
narrower than the shop, so the building is an L and the two tiles east of the wing are plain ground. The wing came
back paler and greyer than the shop and is toned lightly towards it (red 0.95, green 0.90, blue 0.86; operator,
2026-11-14). Four surfaces the generator invented are covered with a stretch of the same model's own wall, height for
height (operator, 2026-11-14: "can you copy the wall texture over it?"): the plain grey block on the wing's south end
(its face and both sides), the lettering Meshy mirrored on to the wing's east wall, and the smeared mirrored lettering
on the shop's back wall where the wing does not cover it. The block on the wing's end still stands 0.6 metres out of
the wall, as generated. Glow maps were made from the models' own colour for the shop's sign, its pistol sign, its
windows and door, the strip lights over its windows, the light on its security camera, the wing's windows on both long
walls, the lamp over its door and the two amber lamps on its roof mast, each with a halo sheet of its own just in
front of it. Nothing else was retouched. The meshes were shared out over six tiles (none to 44,482 faces each) with a
ground square, a map picture and two main lights each; nothing carries `tilefade`, the building being one storey with
its rooftop units at 6.1 metres; and a walkmesh was generated from their shape (204 to 698 faces a tile, where the
stock tiles of these two tilesets have at most 500). The shop's tile has a door record of type 58, the invisible
transition door, at the double door. The Meshy sources, the full-detail spares, the references and the client captures
stay in ignored `output/envkit/`.

Checked in the game client on 2026-11-14, in a Modern Exterior area laid from the pack's files: by day from all four
sides, two corners, the front and from above, and at the door; by night, where the sign, the pistol sign, the windows
and the lamp over the wing's door were lit, and `SetTextureOverride`, as `docs/envkit/lights.md` gives it, put them
out and brought them back; and with the player free, where nothing was hidden. The first day check showed the wing's
end block torn and streaked and the shop's back wall smeared; both were covered as above and seen again by day and by
night. The operator then saw the lit strips sitting beside their signs and windows (2026-11-14): the wing's windows
were lit 0.35 metres too high, wall and all, the sign 0.25 metres short of one end, and the windows' halo stood out at
the sign's depth. The lit parts were measured again and bounded in depth to the sign's board, the glass and the lamps,
each given halo sheets of its own, and seen again by night, lit, out and lit again. The operator next found the wing's
far wall, which carries the same window strip, dark at night (2026-11-14): it was lit, with the roof mast's lamps and
the camera's light, which a survey of the texture found unlit, and seen by night from that side. The walk check
(`envkit check group --mode walk`), in both tilesets, sent five walkers from the far corner of the area to the door
and to the four sides of the building: all arrived. Painted in the Toolset on 2026-11-14 from the built packs, in both
tilesets: straight, a quarter turn (Modern Exterior) and a half turn (Suburbs). Each saved area holds the six group
tiles and one door of appearance 58 that the Toolset made at the hook, and in the client (`envkit check doors`) each
of the four doors took the player through its area transition.

## Iron Sight Arms props (`srn_placeable`, `srn_2da`; 2026-11-14)

Eleven envkit props from the same concept sheet as the Iron Sight Arms tile group join `srn_placeable`, each with a
row appended to `srn_2da/placeables.2da` (22800-22810, labelled `[envkit]Iron Sight Arms, ...`): pistol counter
`ek_isa_counter`, rifle wall `ek_isa_gunwall`, ammo shelf `ek_isa_shelf`, gunsmith bench `ek_isa_bench`, rifle cabinet
`ek_isa_cabinet`, ammo vending machine `ek_isa_vending`, hearing and eye protection rack `ek_isa_ppe`, cleaning cart
`ek_isa_cart`, paper target `ek_isa_target`, steel target `ek_isa_gong` and shooting booths `ek_isa_booths`. No
existing row changes. Each prop is a compiled model, a collision file, a material file and its maps (colour 1024 or
2048, the other maps at half that), and a blueprint named as its model, offered through the pack's
`placeablepalstd.itp`.

Origin: each prop was cropped from the operator's concept sheet and redrawn locally with Qwen-Image 2.1 as a plain
reference, enlarged to 2048 pixels with RealESRGAN x2plus, then generated by the operator's Meshy account through the
pinned `meshy-cli@0.4.0` at 1,187 to 12,032 triangles (attribution: [Meshy](https://www.meshy.ai/); paid plan, as the
Stuffer Shack tile group's entry above records). No third-party mesh or texture was used. The rifle wall was generated
twice: from a square-on reference it came back an empty frame, and it was made again from a three-quarter reference on
a thick slab.

Modifications, all by `tools/envkit` (SRN project operator with Claude): each model was turned to the game's axes and
scaled to a stated height, and its textures were recompressed. Six props have a glow map for their lit parts and a
lights-out material (`<name>_o`) as `docs/envkit/lights.md` describes: the counter's two strip lights, the bench's
lamp, the cabinet's two strip lights, the vending machine's sign, screen and products, the rack's sign and lamps, and
the booths' lane screens and overhead lamps. Two of them also light what stands round them, by a light in their rows
of `placeables.2da` (lightcolor row 2, white): the bench from its lamp and the booths from their middle overhead lamp
(operator, 2026-11-14: "recheck the iron sights props and make sure they are good as far as lights too", lights being
"only for things that should be bright"); the counter's and cabinet's strip lights, the vending machine and the rack's
sign only glow. The booths' light stood under the middle lamp and lit the middle booth far more than the outer two; it
now stands in that lamp's housing, a little forward, and the three are lit alike (2026-11-14). The game draws a flare
where a light stands: set over the booths, for evenness, it hung a star in the air, and was moved back to the lamp.
The rifle cabinet's left door, which the generator drew dark and without its strip light, takes the picture of its
right door (operator, 2026-11-14: "only half this gun cabinet is lit"). Nothing else was retouched. Left as generated:
the rifle cabinet is a plain box of 1,187 triangles with its rifles drawn behind the mesh doors, the rifle wall is
0.37 metres deep with a plain grey back, and the vending machine and the booths carry an emblem the generator invented
on their backs.

Checked in the game client on 2026-11-14: by day from front, back and side with a figure for scale, from the converted
files; by night the same way for the six lit props; and by night from the pack's files, where the lights of the six
were put out by script and brought back. The booths' lane-screen box ran front to back and lit rust specks on their
backs and dividers; it was bounded to the screens (2026-11-14), and the booths and the cabinet were seen again by
night. The bench and the booths were seen once more by night with their cast light, the ground and the figures round
them lit (2026-11-14). Four of them (vending machine, shooting booths, ammo shelf and pistol counter, from both
palette categories) were placed from the Toolset's palette on 2026-11-14 and saved with their own rows and names, the
shelf static and the three lit props not. The booths were seen again by night on 2026-11-14 with their light where it
now stands, and the six props' lights put out and brought back once more from the pack's files.
## Chop Shop Clinic tile group (`srn_t_common`, `srn_t_dgt04`, `srn_t_udp1`; 2026-11-14)

A street cyberware clinic: a single-storey concrete and steel block under a neon CHOP SHOP sign, with a display
window, a recessed double door, a roller shutter, a service door on its west side and air units on its roof, as one 2
by 2 tile group, `Chop_Shop_Clinic`, offered in D20 Modern Exterior (`dgt04`, on Concrete) and D20 Suburbs (`udp1`, on
Asphalt). Its four tile records are appended to each set file (`dgt04` tiles 526-529, group 62; `udp1` tiles 768-771,
group 111) and the group is listed under Groups in each palette as `Chop Shop Clinic 2x2`. No existing tile or group
number changes. The four tile models (`ek_csc_shop_t00` to `_t11`, compiled), their walkmeshes, area-map pictures
(`ek_csc_shop_m00` to `_m11`) and the building's material and maps live in `srn_t_common`: its colour, `_n`, `_s` and
`_r` maps, a glow map `_i`, a halo `_h` and a lights-out material `_o`.

Origin: the concept sheet `58_chop_shop_cyberware_clinic.png` was supplied by the SRN project operator. The building
is one model generated by the operator's Meshy account through the pinned `meshy-cli@0.4.0` from the sheet's
three-quarter view, redrawn locally with Qwen-Image 2.1 as a standalone block and enlarged to 2048 pixels with
RealESRGAN x2plus before it was sent, and remeshed by Meshy to 84,867 triangles. Attribution:
[Meshy](https://www.meshy.ai/); paid plan, as the Stuffer Shack tile group's entry above records. The shop's name is
the sheet's own invention.

Modifications, all by `tools/envkit` (SRN project operator with Claude): the model was turned to the game's axes and
scaled to 6.0 metres to the top of its roof units, which gives its double door a leaf of about 2.1 metres, and its
textures were recompressed (colour 4096 DXT1, the other maps 2048). A panel of smeared lettering the generator
invented on the east wall is covered with a stretch of the same wall, height for height, and a wedge left open at the
foot of the back wall is closed with two faces between its own corners, drawn in the colour of the wall beside it:
drawn with the picture between those corners they showed a streak of other walls, and were built again on 2026-11-14.
Glow maps were made from the model's own colour for the sign, the strip light over the door, the lit panels over the
shop window, the window, the doorway, the light on the security camera and the lamp over the side door, each with a
halo sheet of its own just in front of it. Nothing else was retouched: the side and back walls are plain concrete as
generated. The mesh was shared out over four tiles (2,018 to 43,114 faces each) with a ground square, a map picture
and two main lights each; nothing carries `tilefade`, the building being one storey; and a walkmesh was generated from
its shape (380 to 584 faces a tile, where the stock tiles of these two tilesets have at most 500). The front tile has
a door record of type 58, the invisible transition door, at the double door. The Meshy source, the references and the
client captures stay in ignored `output/envkit/`.

Checked in the game client on 2026-11-14, in areas laid from the pack's files: in Modern Exterior by day from all four
sides, the corners, the front, from above and at the door; by night, where the sign, the strip lights, the window, the
camera light and the side door's lamp were lit, put out by script and brought back; with the player free, near and
far; and with walkers sent to the door and to each side, none of whom stopped short; and in Suburbs by day from the
same views. The group was painted from the Toolset's palette on 2026-11-14, straight in a Modern Exterior area and
turned a quarter in a Suburbs area, and four of the sheet's props (the cross sign, the surgical light and the
cyberware case, lit, and the instrument cart, static) were placed from both palette categories; the saved module holds
the four tiles of each, a door of appearance 58 made at each hook, and the props with their own rows and names. In the
client the door of each took the player to the other. After the back wall's patch was built again the group was seen
once more from the pack's files, by day from the same views and by night, its lights put out and brought back. A
second Toolset folder, the same day, has the other two turns: the group painted turned a half in a Modern Exterior
area and straight in a Suburbs area, with the cyberware case and the cross sign (lit) and the instrument cart (static)
placed from both palette categories; the saved module holds the four tiles of each at that turn and a door of
appearance 58 made at each hook, and in the client the door of each took the player to the other.

## Chop Shop Clinic props (`srn_placeable`, `srn_2da`; 2026-11-14)

Nine envkit props from the same concept sheet as the Chop Shop Clinic tile group join `srn_placeable`, each with a row
appended to `srn_2da/placeables.2da` (22811-22819, labelled `[envkit]Chop Shop Clinic, ...`): neon cross sign
`ek_csc_cross`, hanging banner `ek_csc_banner`, cyberware case `ek_csc_case`, gurney `ek_csc_gurney`, surgical light
`ek_csc_lamp`, instrument cart `ek_csc_cart`, biohazard bin `ek_csc_bin`, medicine vending machine `ek_csc_vending`
and dumpster `ek_csc_dumpstr`. No existing row changes. Each prop is a compiled model, a collision file, a material
file and its maps (colour 1024 or 2048, the other maps at half that), and a blueprint named as its model, offered
through the pack's `placeablepalstd.itp`. The sheet's stack of cases and its bench are the Pulse Tech set's props and
were not made again.

Origin: each prop was cropped from the operator's concept sheet and redrawn locally with Qwen-Image 2.1 as a plain
reference, enlarged to 2048 pixels with RealESRGAN x2plus, then generated by the operator's Meshy account through the
pinned `meshy-cli@0.4.0` at 2,756 to 10,320 triangles (attribution: [Meshy](https://www.meshy.ai/); paid plan, as the
Stuffer Shack tile group's entry above records). No third-party mesh or texture was used.

Modifications, all by `tools/envkit` (SRN project operator with Claude): each model was turned to the game's axes and
scaled to a stated height, and its textures were recompressed. The cross sign hangs 2.4 metres up and the banner 1.9;
the bin is turned a quarter so that its symbol faces front and back. Four props have a glow map for their lit parts
and a lights-out material (`<name>_o`) as `docs/envkit/lights.md` describes: the cross sign's neon, the case's strip
lights, cybereye and knee light, the lamp's lenses, and the vending machine's cross, screen and products. The surgical
light also lights what stands round it, by a light in its row of `placeables.2da` (lightcolor row 3, bright white;
operator, 2026-11-14: "the lamp needs a light"); the other three only glow. A review of each prop from its corners,
above and below (operator, 2026-11-14: "review them thoroughly for issues") found four faults, which were mended: the
right half of the banner's caduceus and the stripes under it came back smeared on both faces of the cloth, and take
the mirror image of the clean left half and a stretch of the clean stripes; the bin showed through gaps under its rear
rim and the dumpster through the slot between its lids, and every face of each now has a back, so that they show their
own insides; and a length of the lamp's pole was wound inward and seen through from one side, and has backs too. A
second pass the same day (operator: "Can the remaining issues be fixed easily?", "Yes", "Fix the case glass too")
mended four more. The label the generator invented on both sides and the back of the vending machine is covered, each
half of it with the mirror image of the panel beside it at the same heights; a faint patch is left where the panel's
streaks stop at the label's top and bottom. The banner's copied stripes, which met the cloth's own a step out, are
taken 1.5 centimetres higher. The case's cybereye and knee light glow 1.8 times as strongly and have halo sheets
(`ek_csc_case_h`). And the case, which came back with the two bars of its slanted glass front and nothing between
them, has glass: four panes, two between the bars and one at each end, nodes of the model's own, each a pale blue-grey
sheet (`ek_csc_case_g`) added faintly to what is seen through it, as a halo is; laid over it instead, the glass hid
the halos of the lights inside the case by night. Left as generated: the lower arm of the banner's bracket is notched.

Checked in the game client on 2026-11-14: by day from front, back and side with a figure for scale, from the converted
files, the banner, bin, dumpster and lamp again after they were mended; by night the same way for the four lit props,
the ground and the figures round the lamp lit by it; and by night from the pack's files, where the lights of the four,
the lamp's cast light among them, were put out by script and brought back. After the second pass the vending machine,
the banner and the case were seen again by day from the converted files, and the case by night, its strip lights,
cybereye and knee light seen through the glass; and the four lit props' lights were put out and brought back once more
from the pack's files.

## Pulse Tech tile group (`srn_t_common`, `srn_t_dgt04`, `srn_t_udp1`; 2026-11-15)

A street Matrix gear shop: a two-storey concrete and steel block under a neon PULSE TECH sign, with a shop window and
a recessed door on its front, strip-lit windows on its upper floor and both sides, and air units and aerials on its
roof, as one 2 by 2 tile group, `Pulse_Tech`, offered in D20 Modern Exterior (`dgt04`, on Concrete) and D20 Suburbs
(`udp1`, on Asphalt). Its four tile records are appended to each set file (`dgt04` tiles 530-533, group 63; `udp1`
tiles 772-775, group 112) and the group is listed under Groups in each palette as `Pulse Tech 2x2`. No existing tile
or group number changes. The four tile models (`ek_pt_shop_t00` to `_t11`, compiled), their walkmeshes, area-map
pictures (`ek_pt_shop_m00` to `_m11`) and the building's material and maps live in `srn_t_common`: its colour, `_n`,
`_s` and `_r` maps, a glow map `_i`, a halo `_h` and a lights-out material `_o`.

Origin: the concept sheet `57_pulse_tech_matrix_gear_shop.png` was supplied by the SRN project operator. The building
is one model generated by the operator's Meshy account through the pinned `meshy-cli@0.4.0` from the sheet's
three-quarter view, redrawn locally with Qwen-Image 2.1 as a standalone block and enlarged to 2048 pixels with
RealESRGAN x2plus before it was sent, and remeshed by Meshy twice; the second reduction, asked for at 120,000
triangles, is the one used. Attribution: [Meshy](https://www.meshy.ai/); paid plan, as the Stuffer Shack tile group's
entry above records. The shop's name is the sheet's own invention.

Modifications, all by `tools/envkit` (SRN project operator with Claude): the model was turned to the game's axes and
scaled to 8.25 metres to the top of its roof units, which gives its door a leaf of about 2.1 metres, and its textures
were recompressed (colour 4096 DXT1, the other maps 2048). The operator found the shop window drawn as a pale, blocky
smear (2026-11-15): the generator had laid two large faces across the pane, in front of the window's own detail, and
they were taken out; a second reduction had not removed them. A close look at every opening afterwards found the same
across the west upper window, taken out likewise, and a hole in the red band on the east wall, closed with faces
between its own rim and drawn with the band's picture beside it. Glow maps were made from the model's own colour for
the sign, the strip lights over the shop window and the door, the shop window, the doorway, the strip lights and
windows of the upper floor, and the strip lights and windows of the east and west walls, each with a halo sheet of its
own just in front of it. Nothing else was retouched: the building stands on the slab with bollards it was generated
with, and the bins and rubbish against its walls are part of the model (operator, 2026-11-15: both can stay). The mesh
(104,238 triangles) was shared out over four tiles (6,100 to 59,106 faces each) with a ground square, a map picture
and two main lights each; nothing carries `tilefade`; and a walkmesh was generated from its shape (498 to 650 faces a
tile, where the stock tiles of these two tilesets have at most 500). The front tile has a door record of type 58, the
invisible transition door, at the door. The Meshy source, the first reduction, the references and the client captures
stay in ignored `output/envkit/`.

Checked in the game client on 2026-11-15, in areas laid from the converted files: in Modern Exterior by day from all
four sides, the corners, the front, from above and at the door; by night, where the sign, the strip lights and the
windows were lit, put out by script and brought back; and with walkers sent to the door and to each side of the
building in both tilesets, none of whom stopped short. Its halo sheets were made again the same day with the
lamp-lens rule the props' entry below gives, and the group seen again by night, lit, out and lit again. Painted in the Toolset on 2026-11-15 from the built packs, in
two folders: straight in a Modern Exterior area and turned a quarter in a Suburbs area, then turned a half in Modern
Exterior and straight in Suburbs. Each saved area holds the four group tiles at that turn and one door of appearance
58 that the Toolset made at the hook, and in the client (`envkit check doors`) each of the four doors took the player
through its area transition.

## Pulse Tech props (`srn_placeable`, `srn_2da`; 2026-11-15)

Thirteen envkit props from the same concept sheet as the Pulse Tech tile group join `srn_placeable`, each with a row
appended to `srn_2da/placeables.2da` (22820-22832, labelled `[envkit]Pulse Tech, ...`): neon chip sign `ek_pt_sign`,
hanging banner `ek_pt_banner`, display counter `ek_pt_counter`, repair bench `ek_pt_workbnch`, parts cart
`ek_pt_cart`, server rack `ek_pt_rack`, case stack `ek_pt_cases`, bench `ek_pt_seats`, commlink vending machine
`ek_pt_vending`, cable reel `ek_pt_reel`, power pack `ek_pt_power`, trash can `ek_pt_bin` and drone service pad
`ek_pt_drone`. No existing row changes. Each prop is a compiled model, a collision file, a material file and its maps
(colour 1024 or 2048, the other maps at half that), and a blueprint named as its model, offered through the pack's
`placeablepalstd.itp`.

Origin: each prop was cropped from the operator's concept sheet and redrawn locally with Qwen-Image 2.1 as a plain
reference, enlarged to 2048 pixels with RealESRGAN x2plus, then generated by the operator's Meshy account through the
pinned `meshy-cli@0.4.0` at 3,064 to 10,256 triangles (attribution: [Meshy](https://www.meshy.ai/); paid plan, as the
Stuffer Shack tile group's entry above records). No third-party mesh or texture was used.

Modifications, all by `tools/envkit` (SRN project operator with Claude): each model was turned to the game's axes and
scaled to a stated height, and its textures were recompressed. The chip sign hangs 2.4 metres up and the banner 1.9;
every face of the banner has a back, so that the cloth is seen from both sides. Seven props have a glow map for their
lit parts and a lights-out material (`<name>_o`) as `docs/envkit/lights.md` describes: the sign's neon, the counter's
strip lights and commlink screens, the repair bench's lamp, oscilloscope and meter, the server rack's indicator
lights, the vending machine's emblem, screen and product window, the power pack's two displays and the drone pad's
camera eye. The repair bench also lights what stands round it, by a light in its row of `placeables.2da` at its lamp
(lightcolor row 1, dim white; operator, 2026-11-15: "Dimmer for bench lamp", after it was first given bright white);
the other six only glow. Small lit parts keep a halo sheet of their own however small they are drawn (`glow.MAIN`,
2026-11-15), measured against what the part shows on the side it lights most: the repair bench's lamp lens, which
shines mostly downward, and one of the counter's lit parts had no halo sheet until then, and were converted again
and seen by night. Nothing else was retouched.

Checked in the game client on 2026-11-15: by day from front, back and side with a figure for scale, from the converted
files; by night the same way for the seven lit props; and the repair bench once more by night with its dimmer light,
which lights the bench and the ground beside it. Ten of them were placed from the Toolset's palette on 2026-11-15,
from both palette categories, and saved with their own rows and names: the chip sign, display counter, repair bench,
vending machine, server rack and drone pad, lit and not static, and the trash can, case stack, parts cart and hanging
banner, static.

## Ghost Riders tile group (`srn_t_common`, `srn_t_dgt04`, `srn_t_udp1`; 2026-11-15)

A gang's vehicle garage, drawn generic: a patched sheet-metal block with an open repair bay, a roller door and a
steel door on its front, a blank sign board under a red neon motorcycle, and pipes, tanks, a dish and aerials on its
roof, as one 3 by 2 tile group, `Motorpool`, offered in D20 Modern Exterior (`dgt04`, on Concrete) and D20 Suburbs
(`udp1`, on Asphalt). Its six tile records are appended to each set file (`dgt04` tiles 534-539, group 64; `udp1`
tiles 776-781, group 113) and the group is listed under Groups in each palette as `Motorpool Garage 3x2`. No existing
tile or group number changes. The six tile models (`ek_gr_garage_t00` to `_t12`, compiled), their walkmeshes, area-map
pictures (`ek_gr_garage_m00` to `_m12`) and the building's material and maps live in `srn_t_common`: its colour,
`_n`, `_s` and `_r` maps, a glow map `_i`, a halo `_h` and a lights-out material `_o`.

Origin: the concept sheet `44_ghost_riders_motorpool.png` was supplied by the SRN project operator, who had the
building made without the gang's name, murals and logos (2026-11-15); the neon motorcycle stays. The building is one
model generated by the operator's Meshy account through the pinned `meshy-cli@0.4.0` from three views of the sheet
(three-quarter, front and rear), each redrawn locally with Qwen-Image 2.1 as a standalone block without lettering and
enlarged to 2048 pixels with RealESRGAN x2plus before it was sent, and remeshed by Meshy to 120,000 triangles asked
for. Attribution: [Meshy](https://www.meshy.ai/); paid plan, as the Stuffer Shack tile group's entry above records.

Modifications, all by `tools/envkit` (SRN project operator with Claude): the model was turned to the game's axes and
scaled to 11.5 metres to the top of its aerials, which gives its steel door a leaf of about 2.1 metres, and its
textures were recompressed (colour 4096 DXT1, the other maps 2048). Its roller door came back a flat dark blue with
its slats lost; the new blank-panel check found it (`convert.blank_panels`) and it was smoothed, brought to a steel
grey and drawn again with a joint every 0.12 metres. Glow maps were made from the model's own colour for the neon
motorcycle and the strip lights over the repair bay and the roller door, each with a halo sheet of its own. Nothing
else was retouched: the building stands on the slab it was generated with, and the fence section, barrier, tyres,
drum, bollards and wheel stops round it, the sheet of metal leaning inside the bay and what stands in the bay are
part of the model. Its upper window is dark and left unlit. The mesh (104,543 triangles) was shared out over six
tiles (6,823 to 35,006 faces each) with a ground square, a map picture and two main lights each; nothing carries
`tilefade`; and a walkmesh was generated from its shape (556 to 1,110 faces a tile, where the stock tiles of these
two tilesets have at most 500). The tile under the steel door has a door record of type 58, the invisible transition
door, at the door. The repair bay's floor is not walked on: the tyres, cans and wheel stops in its mouth leave no
way in a metre wide. The Meshy sources, the references and the client captures stay in ignored `output/envkit/`.

Checked in the game client on 2026-11-15, in areas laid from the pack's tiles: in Modern Exterior by day from all
four sides, the corners, the front, from above and at the door; by night, where the neon motorcycle and the strip
lights were lit, put out by script and brought back; and with walkers sent to the door and to each side of the
building in both tilesets, none of whom stopped short.

Checked in the Toolset the same day, in two user folders of their own: both palettes list `Motorpool Garage 3x2`
under Groups, and painting it laid the six tiles and made one door of type 58 at the hook, straight in both
tilesets in the first folder and turned a quarter in Modern Exterior and a half in Suburbs in the second. In
Modern Exterior the Toolset changed no other tile; in Suburbs it repainted the fourteen tiles round the group as
asphalt edges and corners. In the game client each of the four doors, clicked, took the player to the next
(`envkit check doors`, both folders).

## Ghost Riders props (`srn_placeable`, `srn_2da`; 2026-11-15)

Fifteen envkit props from the same concept sheet as the Ghost Riders tile group join `srn_placeable`, each with a row
appended to `srn_2da/placeables.2da` (22833-22847, labelled `[envkit]Ghost Riders, ...`): repair bench `ek_gr_bench`,
parking pad `ek_gr_pad`, parts rack `ek_gr_rack`, planning table `ek_gr_table`, burn barrel `ek_gr_fire`, ember
barrel `ek_gr_embers`, motorpool sign `ek_gr_sign`, gear banner `ek_gr_banner`, tagged barrier `ek_gr_barrier`, skull
garage door `ek_gr_door`, mural wall `ek_gr_mural`, stash cases `ek_gr_cases`, fuel drums `ek_gr_drums`, fence
section `ek_gr_fence` and service locker `ek_gr_locker`. No existing row changes. Each prop is a compiled model, a
collision file, a material file and its maps (colour 1024 or 2048, the other maps at half that), and a blueprint
named as its model, offered through the pack's `placeablepalstd.itp`. The gang's name and skull are on the sign,
banner, barrier, garage door, mural wall, cases, fence and locker, which the operator had made as props of their own
so that the building stays generic (2026-11-15); the two barrels are unmarked.

Origin: each prop was cropped from the operator's concept sheet and redrawn locally with Qwen-Image 2.1 as a plain
reference, enlarged to 2048 pixels with RealESRGAN x2plus, then generated by the operator's Meshy account through the
pinned `meshy-cli@0.4.0` at 1,873 to 10,508 triangles (attribution: [Meshy](https://www.meshy.ai/); paid plan, as the
Stuffer Shack tile group's entry above records). The flames of the burn barrel are the game's own flame picture
(`fxpa_flame00`, which the base game supplies; nothing of it is in the pack). No third-party mesh or texture was
used. A burn barrel generated with flames of its own was not used (operator, 2026-11-15: "just drop the flame barrel
and copy the ember barrel and add the flames to that copy"); the sheet's floodlight mast and generator are other
sheets' props and were not made.

Modifications, all by `tools/envkit` (SRN project operator with Claude): each model was turned to the game's axes and
scaled to a stated height, and its textures were recompressed. The motorpool sign hangs 2.6 metres up and the banner
1.6; every face of the banner has a back, so that the cloth is seen from both sides. The parking pad came back a
wedge, half a metre thick at its back; its top was laid flat at 3 centimetres with its wheel stops standing on it
(`convert.levelled`), and it has no block to walk into. The two barrels are one model, a drum of charred wood: a
block was built under the wood in the colour of the model's one glowing ember and lit, a bed of embers seen between
the pieces, and the burn barrel also has a fire the game draws (an emitter node with the stock medium flame's
settings, narrowed to the drum, `convert.fire_lines`) and a light in its row of `placeables.2da` (lightcolor row 31,
orange). The fence section's right panel was redrawn as chain-link that is seen through; its left panel, a banner
the generator smeared on the front face and drew whole on the back, is left as generated. The back of the mural
wall, where the generator smeared a second mural, was smoothed to plain grey. Five props have a glow map and a
lights-out material (`<name>_o`) as `docs/envkit/lights.md` describes: the repair bench's two strip lights, the
embers of both barrels and the mural wall's two lamp lenses. The repair bench (lightcolor row 1, dim white), the
burn barrel and the mural wall (row 2, white, at its right lamp) light what stands round them; the ember barrel only
glows. Nothing else was retouched: the faint mirrored skull on the back of the garage door is the generator's.

Checked in the game client on 2026-11-15, from the converted files: by day from front, back and side with a figure
for scale, all fifteen; by night the same way for the repair bench, both barrels and the mural wall, where the
strip lights and lamps glow, the fire burns and lights the ground orange, and the lit props were put out by script
and brought back from the pack (`envkit check lights`). The machine was busy with other work and several captures
came late; each view was taken from a run that captured it in time. In the Toolset the same day the placeable
palette listed all fifteen, ten under Modern Exterior and five under Modern Interior, and ten were placed from
it and read back from the saved areas with their rows and blueprints: the burn barrel, ember barrel, mural wall and
repair bench not static, so that a script can put their lights out, and the fence section, stash cases, parking
pad, motorpool sign, parts rack and tagged barrier static.

On 2026-11-16 both barrels were built again (operator: "the embers in the barrel don't look like embers"). The block of
one glowing colour under the wood, its glow map and its lights-out material are gone. In their place each barrel has a
bed of embers of its own: a low mound under the charred wood (`convert.ember_beds`) with a picture `<name>_e` drawn
by `tools/envkit` itself (`convert.ember_picture`: dark lumps of charcoal under grey ash, the fire in the gaps between
them), shown as bright by night as by day. No third-party picture was used. The burn barrel's model also has the four
animations of the stock flame, by which a script puts its fire out and lights it again (`docs/envkit/lights.md`); its
embers glow on when the fire is out. So neither barrel has a glow map or a lights-out material any more, and neither
has `lights` in the catalog. The ember barrel's blueprint is static now, as scenery no script needs to reach; the
burn barrel's is not, for its fire. Rows, the burn barrel's blueprint and both collision files are unchanged. Checked
in the game client the same day by night, from the converted files: both beds seen from the side and from above, the fire and its light put
out by script with the embers left glowing, and lit again. The same was then seen by day, and by night from the pack's
own files beside the repair bench and the mural wall (`envkit check lights`): all three put out and on again.

## Aurora Warrens tile group (`srn_t_common`, `srn_t_dgt04`, `srn_t_udp1`; 2026-11-16)

A run-down apartment block: three storeys of patched concrete with a caged stair tower at its west end, balconies,
air units, a water tank and shacks on its roof, as one 3 by 2 tile group, `Aurora_Warrens`, offered in D20 Modern
Exterior (`dgt04`, on Concrete) and D20 Suburbs (`udp1`, on Asphalt). Its six tile records are appended to each set
file (`dgt04` tiles 540-545, group 65; `udp1` tiles 782-787, group 114) and the group is listed under Groups in each
palette as `Aurora Warrens 3x2`. No existing tile or group number changes. The six tile models (`ek_aw_block_t00` to
`_t12`, compiled), their walkmeshes, area-map pictures (`ek_aw_block_m00` to `_m12`) and the building's material and
maps live in `srn_t_common`: its colour, `_n`, `_s` and `_r` maps, a glow map `_i`, a halo `_h` and a lights-out
material `_o`.

Origin: the concept sheet `24_aurora_warrens_apartment_complex.png` was supplied by the SRN project operator. The
building is one model generated by the operator's Meshy account through the pinned `meshy-cli@0.4.0` from three
pictures of it, a three-quarter view, the front and the rear, each redrawn locally with Qwen-Image 2.1 from the sheet
as a standalone block and enlarged to 2048 pixels with RealESRGAN x2plus before it was sent, and remeshed by Meshy
once, asked for at 120,000 triangles. Attribution: [Meshy](https://www.meshy.ai/); paid plan, as the Stuffer Shack
tile group's entry above records. The building carries no name or sign (operator, 2026-11-16: buildings stay generic;
the sheet's name is on a prop, the name wall).

Modifications, all by `tools/envkit` (SRN project operator with Claude): the model was turned to the game's axes and
scaled to 15.3 metres to the top of its roof, which gives its front door a leaf of about 2.1 metres, and its textures
were recompressed (colour 4096 DXT1, the other maps 2048). Glow maps were made from the model's own colour for
nineteen parts, each measured on the wall it lies in: the strip lights over the front and rear doors, the lamp by the
west door, and the lit windows of the first and second floors and of the roof shacks, front and rear, each with a
halo sheet of its own just in front of it. Nothing else was retouched. The mesh (105,520 triangles) was shared out
over six tiles (9,886 to 28,664 faces each) with a ground square, a map picture and two main lights each; nothing
carries `tilefade`; and a walkmesh was generated from its shape (1,112 to 1,672 faces a tile, where the stock tiles
of these two tilesets have at most 500). The path nodes of the three tiles the stair tower and the front door stand
in are stated in the set (`H` and `V`, turned) rather than left to be chosen. The front middle tile has a door record
of type 58, the invisible transition door, at the front door. The Meshy source, the references and the client
captures stay in ignored `output/envkit/`.

Checked in the game client on 2026-11-16, in areas laid from the converted files: in Modern Exterior by day from all
four sides, the corners, from above and at the door; by night, where the door lights and the windows were lit, put
out by script and brought back; and with walkers sent to the door and to each side of the building in both tilesets.
Those to the door, the north, the south and the east arrived. The one sent to the west side from the far north-east
corner stopped 7.5 metres short in both tilesets, under three different settings of the path nodes: its target is a
strip of the slab under the stair tower, on the line between two tiles. Walkers sent to that same spot from the west
and from the south-west corner arrived, and so did one sent from the north-east corner to the ground 1.4 metres west
of it, so the ground there is reached; only that one long walk gives up.

Painted in the Toolset on 2026-11-17 from the built packs, with the Night Bazaar gatehouse below, in two user
folders of 12-tile areas (`envkit toolset prepare --size 12`): straight in Modern Exterior and in Suburbs in the
first, turned a quarter in Modern Exterior and a half in Suburbs in the second. Both palettes list `Aurora Warrens
3x2` under Groups; each painting laid the six tiles with their turn and the Toolset made one door of appearance 58
at the hook (`envkit toolset saved`). In Suburbs it also repainted the tiles round the group as road. Six of the
props below were placed from the palette in the first folder and four in the second (entry shack, water tank, caged
stairwell and bodega kiosk of this sheet; from Structures in Modern Exterior and Furniture in Modern Interior) and
were saved with their own rows and names, the unlit ones static. In the client (`envkit check doors`, first folder)
the four doors of the two groups were found with their transitions and the player stood free at the Warrens' door.
The operator then clicked through: the Warrens' door in Modern Exterior took the player to the gatehouse's door, and
that door to the Warrens' door in Suburbs, as the log shows. The client was closed there, so the two Suburbs doors
are not logged, and the second folder's doors were not walked.

## Aurora Warrens props (`srn_placeable`, `srn_2da`; 2026-11-16)

Thirteen envkit props from the same concept sheet as the Aurora Warrens tile group join `srn_placeable`, each with a
row appended to `srn_2da/placeables.2da` (22848-22860, labelled `[envkit]Aurora Warrens, ...`): entry shack
`ek_aw_kiosk`, caged stairwell `ek_aw_stairs`, balcony segment `ek_aw_balcony`, utility generator `ek_aw_gen`, water
tank `ek_aw_tank`, rooftop shack `ek_aw_shack`, scrap barrier `ek_aw_barrier`, bodega kiosk `ek_aw_bodega`, laundry
line `ek_aw_laundry`, trash pile `ek_aw_trash`, graffiti wall `ek_aw_graffiti`, name wall `ek_aw_namewall` and crates
on pallets `ek_aw_crates`. No existing row changes. Each prop is a compiled model, a collision file, a material file
and its maps (colour 1024 or 2048, the other maps at half that), and a blueprint named as its model, offered through
the pack's `placeablepalstd.itp`.

Origin: each prop was cropped from the operator's concept sheet and redrawn locally with Qwen-Image 2.1 as a plain
reference, enlarged to 2048 pixels with RealESRGAN x2plus, then generated by the operator's Meshy account through the
pinned `meshy-cli@0.4.0` at 4,426 to 21,190 triangles (attribution: [Meshy](https://www.meshy.ai/); paid plan, as the
Stuffer Shack tile group's entry above records). No third-party mesh or texture was used. The complex's name is the
sheet's own invention and stands on the name wall alone.

Modifications, all by `tools/envkit` (SRN project operator with Claude): each model was turned to the game's axes and
scaled to a stated height, and its textures were recompressed. The entry shack, the stairwell, the water tank, the
bodega kiosk and the laundry line have a back to every face, so that they are seen from inside and through their
frames. Two props have a glow map for their lit parts and a lights-out material (`<name>_o`) as
`docs/envkit/lights.md` describes: the strip light over the entry shack's door, and the bodega kiosk's neon sign and
drinks fridge. The entry shack also lights what stands round it, by a light in its row of `placeables.2da` at its
strip light (lightcolor row 1, dim white); the bodega kiosk only glows. Nothing else was retouched. Three things are
left as generated: the back of the name wall shows the front's lettering mirrored and garbled (the wall is about two
centimetres thick, and smoothing its back by depth spoiled its front); the back of the balcony segment has a slanted
smear; and some of the stairwell's cage panels are drawn solid.

Checked in the game client on 2026-11-16: by day from front, back and side with a figure for scale, from the converted
files; and by night from the pack's files, where the lights of the entry shack and the bodega kiosk were put out by
script and brought back, the ground by the shack lit by its light.

## Night Bazaar tile group (`srn_t_common`, `srn_t_dgt04`, `srn_t_udp1`; 2026-11-16)

A market gatehouse: two scrap-built towers of steel panel, stairs, catwalks and tarps either side of an open gateway,
on one slab, as one 3 by 2 tile group, `Night_Bazaar`, offered in D20 Modern Exterior (`dgt04`, on Concrete) and D20
Suburbs (`udp1`, on Asphalt). Its six tile records are appended to each set file (`dgt04` tiles 546-551, group 66;
`udp1` tiles 788-793, group 115) and the group is listed under Groups in each palette as `Night Bazaar Gatehouse
3x2`. No existing tile or group number changes. The six tile models (`ek_nb_gate_t00` to `_t12`, compiled), their
walkmeshes, area-map pictures (`ek_nb_gate_m00` to `_m12`) and the building's material and maps live in
`srn_t_common`: its colour, `_n`, `_s` and `_r` maps. Nothing on it is lit.

Origin: the concept sheet `35_front_range_night_bazaar.png` was supplied by the SRN project operator. The building is
one model generated by the operator's Meshy account through the pinned `meshy-cli@0.4.0` from three pictures of it, a
three-quarter view, the front and the rear, each redrawn locally with Qwen-Image 2.1 from the sheet as a standalone
block and enlarged to 2048 pixels with RealESRGAN x2plus before it was sent, and remeshed by Meshy once, asked for at
120,000 triangles. Attribution: [Meshy](https://www.meshy.ai/); paid plan, as the Stuffer Shack tile group's entry
above records. The building carries no name, sign or neon (operator, 2026-11-16: buildings stay generic); the
market's signs are props, below.

Modifications, all by `tools/envkit` (SRN project operator with Claude): the model was turned to the game's axes and
scaled to 13 metres to its highest point, which gives the door in its rear panel a leaf of about 2.1 metres, and its
textures were recompressed (colour 4096 DXT1, the other maps 2048). Nothing was retouched. The mesh (107,775
triangles) was shared out over six tiles (14,630 to 22,383 faces each) with a ground square, a map picture and two
main lights each; nothing carries `tilefade`; and a walkmesh was generated from its shape (986 to 1,912 faces a tile,
where the stock tiles of these two tilesets have at most 500); the slab, 0.4 metres high, is walked at its own
height. The rear middle tile has a door record of type 58, the invisible transition door, at the door. The Meshy
source, the references and the client captures stay in ignored `output/envkit/`.

Checked in the game client on 2026-11-16, in areas laid from the converted files: in Modern Exterior by day from all
four sides, the corners, from above and at the door; and with walkers in both tilesets. The one sent to the door
arrived. Those sent to the west and east sides from the far north corners stopped 7.7 and 10.8 metres short in both
tilesets: their targets are strips of the slab at the group's edge, on the line between two tiles. Walkers sent to
the same two spots from the next tile out and from the south corners arrived, and one sent from north of the group
to south of it arrived, so the ground is reached; only those two long walks give up
(`docs/envkit/sheet-runbook.md` has the row).

Painted in the Toolset on 2026-11-17 from the built packs, in the two user folders the Aurora Warrens entry above
describes: straight in Modern Exterior and in Suburbs, turned a quarter in Modern Exterior and a half in Suburbs.
Both palettes list `Night Bazaar Gatehouse 3x2` under Groups; each painting laid the six tiles with their turn and
the Toolset made one door of appearance 58 at the hook. The light string, bench, vendor stall, shutter booth and
tarped kiosk were placed from the palette and saved with their own rows and names. The gatehouse's door in
Modern Exterior was walked through in the client, as that entry says; its door in Suburbs was not.

## Night Bazaar props (`srn_placeable`, `srn_2da`; 2026-11-16)

Fourteen envkit props from the same concept sheet as the Night Bazaar tile group join `srn_placeable`, each with a
row appended to `srn_2da/placeables.2da` (22861-22874, labelled `[envkit]Night Bazaar, ...`): vendor stall
`ek_nb_stall`, tarped kiosk `ek_nb_kiosk`, cyberware neon sign `ek_nb_neon`, gateway sign `ek_nb_gatesign`, neon
panel `ek_nb_panel`, food cart `ek_nb_cart`, folding table `ek_nb_table`, case stack `ek_nb_cases`, portable
generator `ek_nb_gen`, shutter booth `ek_nb_booth`, bench `ek_nb_bench`, light string `ek_nb_lights`, pylon sign
`ek_nb_pylon` and fence segment `ek_nb_fence`. No existing row changes. Each prop is a compiled model, a collision
file, a material file and its maps (colour 1024 or 2048, the other maps at half that or less), and a blueprint named
as its model, offered through the pack's `placeablepalstd.itp`.

Origin: each prop was cropped from the operator's concept sheet and redrawn locally with Qwen-Image 2.1 as a plain
reference, enlarged to 2048 pixels with RealESRGAN x2plus, then generated by the operator's Meshy account through the
pinned `meshy-cli@0.4.0` at 3,721 to 19,472 triangles (attribution: [Meshy](https://www.meshy.ai/); paid plan, as the
Stuffer Shack tile group's entry above records). No third-party mesh or texture was used. The market's name and the
wording of its signs are the sheet's own invention.

Modifications, all by `tools/envkit` (SRN project operator with Claude): each model was turned to the game's axes and
scaled to a stated height, and its textures were recompressed. The cyberware sign hangs 2.2 metres up, the neon panel
2.0 and the gateway sign 6.0, over a gateway. The vendor stall, the tarped kiosk, the gateway sign, the food cart and
the shutter booth have a back to every face, so that they are seen from inside and through their frames. The fence
segment's two wire panels, generated as solid sheets, were drawn again as mesh (9 cm pitch) that is seen through. The
back of the pylon sign's board, where the generator had left the front's lettering mirrored and garbled, was smoothed
to its own red. Eight props have a glow map for their lit parts and a lights-out material (`<name>_o`) as
`docs/envkit/lights.md` describes: the vendor stall's hanging bulbs and two screens, the tarped kiosk's screen, the
neon of the cyberware sign, the gateway sign, the neon panel and the pylon sign's side panel, the strip light over
the shutter booth's shutter and the light string's bulbs. Three of them also light what stands round them, by a light
in their rows of `placeables.2da` (lightcolor row 1, dim white): the vendor stall at its bulbs, the shutter booth at
its strip light and the light string at its middle; the signs and the kiosk's screen only glow. Nothing else was
retouched.

Checked in the game client on 2026-11-16: by day from front, back and side with a figure for scale, from the converted
files; and by night from the pack's files, where the lights of the eight lit props were put out by script and brought
back, the ground under the stall, the booth and the light string lit by their lights.

## Shiawase Barrens Power Station tile group (`srn_t_common`, `srn_t_dgt04`, `srn_t_udp1`; 2026-11-17)

A worn two-storey power station of cracked concrete on one fenced slab: an overhanging control room, a transformer
bank, a roller door lettered S-1 and one steel door stencilled UTILITY TUNNEL ACCESS - T7, as one 2 by 2 tile group,
`SB_Station`, offered in D20 Modern Exterior (`dgt04`, on Concrete) and D20 Suburbs (`udp1`, on Asphalt). Its four
tile records are appended to each set file (`dgt04` tiles 552-555, group 67; `udp1` tiles 794-797, group 116) and the
group is listed under Groups in each palette as `Shiawase Barrens Power Station 2x2`. No existing tile or group number
changes. The four tile models (`ek_sb_power_t00` to `_t11`, compiled), their walkmeshes, area-map pictures
(`ek_sb_power_m00` to `_m11`) and the building's material and maps live in `srn_t_common`: its colour, `_n`, `_s` and
`_r` maps, a glow map `_i`, a halo `_h`, a lights-out material `_o` and the fence's wire picture `_w`.

Origin: the concept sheet `60_shiawase_barrens_power_station.png` was drawn for the SRN project operator with the
Codex CLI's image generation from the project's earlier Shiawase substation sheet. The building is one model
generated by the operator's Meshy account through the pinned `meshy-cli@0.4.0` from two pictures of it, the front and
the rear, each redrawn locally with Qwen-Image 2.1 from the sheet as a standalone building without its perimeter
fence and enlarged to 2048 pixels with RealESRGAN x2plus before it was sent, and remeshed by Meshy once, asked for at
200,000 triangles (`sb-2view-a2`). Two earlier generations of it, one from the front alone and one with the fence
drawn in both views, are not used: the fence came back as open frames with its chain-link printed on the walls
behind. Attribution: [Meshy](https://www.meshy.ai/); paid plan, as the Stuffer Shack tile group's entry above
records. The Shiawase name and mark on its wall are the sheet's.

Modifications, all by `tools/envkit` (SRN project operator with Claude): the model was turned to the game's axes and
scaled to 9.55 metres, which gives its door a leaf of about 2.0 metres and its slab a width that two tiles hold, and
its textures were recompressed (colour 4096 DXT1, the relief map 4096 too, the other maps 2048). Glow maps were made from the model's own
colour for seven parts (the control room windows, the lamp over the tunnel door, the strip lamp and the red lamp at
the roller door, and three floodlights), each with a halo sheet. The perimeter fence is built, not generated: round
steel posts with domed caps, stouter at the corners and the ends of a run, round top and bottom rails, concrete gateway
posts under pointed caps, chain-link sheets hung between them, and a coil of barbed wire along the top of every run,
two strands wound opposite ways. The fence shows one picture of its own, drawn by `tools/envkit`: the wire mesh, a
column of galvanised steel, streaked and rusted at the foot, and a column of pitted concrete, each in the tone of the
model's own picture at a stated point (the first build's posts were square bars in one flat colour; operator,
2026-11-17: "the posts for the fences needs to be better than a square pole"). It has two gateways in its front, 5 metres before the roller door and 3 metres before the tunnel
door, without gate leaves. Seven faces of 0.1 square metres or more came back showing a sliver of the picture drawn out
across them, the largest a square metre of the slab at the wider gateway (operator, 2026-11-17: "what is this
smear?"): each was cut into pieces and drawn with the sound surface of its own plane beside it (`convert.relaid`); one
of 0.26 square metres low on the slab's front edge found none and is as generated. The five floodlight heads (three
on poles, two on the roof) came back with their lenses drawn dark and stayed dark at night (user, 2026-11-18: "the
tower lights on the tile group aren't lit", "those lamp heads need actual lights"): the faces of each head that look
downward were painted a warm white and lit, and each head has a light of its own in its tile (warm white, 10 metres),
lit without a builder colouring a main light, by day as well as by night. A script that puts the group's lights out
darkens the lenses and leaves these five lights on: nothing was found that puts a tile's own light out. The face of
0.26 square metres named above looks into the slab and is not seen. Nothing else was retouched. The
mesh (198,529 triangles with the fence) was shared out over
four tiles (17,689 to 84,311 faces each) with a ground square, a map picture and two main lights each; what stands
above 4.2 metres carries `tilefade`; and a walkmesh was generated from its shape (402 to 1,720 faces a tile, where
the stock tiles of these two tilesets have at most 500). The path nodes of three tiles are stated in the set: each
front tile is entered by its own gateway only (`N`), since a planned walk did not cross from tile to tile inside the
fence. The strip behind the building is fenced off and is not reached. The front east tile has a door record of type
58, the invisible transition door, at the tunnel door. The Meshy source, the references and the client captures stay
in ignored `output/envkit/`.

Checked in the game client on 2026-11-17, in areas laid from the converted files: in Modern Exterior by day from all
four sides, the corners and at the door (over two runs: the client stalled in each and some captures came late; the
view from above was late in both and is not kept); by night, where the lit parts were lit, put out by script and
brought back; and with walkers in both tilesets sent from the far corners to the door, the roller door, both halves
of the yard, a corner of it and each side of the building, and from the next tile onto the yard: all arrived. On
2026-11-18 the build as it ships, with the round fence posts, the redrawn faces and the lamp lights, was checked
again: by day and with the same walkers in both tilesets (all arrived, every view on time), and by night in Modern
Exterior, where the five lamp heads glow and light the yard and the roof round them. The round gap seen in the fence
nearest the camera in close views is the client's own: it stands at the same place on the screen in views of
different parts of the fence.

Painted in the Toolset on 2026-11-18 from the built packs, in two user folders: straight in Modern Exterior and a
quarter turn in Suburbs in the first, a half turn in Modern Exterior and straight in Suburbs in the second. Each
palette lists it under Groups; each painting laid the four tiles with their turn and the Toolset made one door of
appearance 58 at the hook. The bulkhead door, tunnel vent stack and switchgear cabinet were placed from the palette
in the first folder and saved with their rows. In the client, each folder's two doors were given transitions to each
other and clicked through: the player came out in front of the other area's door both ways, in both folders.

<!-- srn-size-exception {"path":"srn_t_common/ek_sb_power_n.dds","reason":"The power station's relief map at 4096, as its colour is (user, 2026-11-17: \"Yes, full 4K normals\"); 22,369,776 bytes, below GitHub's hard limit."} -->

## Shiawase Barrens props (`srn_placeable`, `srn_2da`; 2026-11-18)

Fourteen envkit props from the same concept sheet as the Shiawase Barrens Power Station tile group join
`srn_placeable`, each with a row appended to `srn_2da/placeables.2da` (22875-22888, labelled `[envkit]Shiawase
Barrens, ...`): power transformer `ek_sb_trafo`, switchgear cabinet `ek_sb_switch`, tunnel hatch `ek_sb_hatch`, cable
drum `ek_sb_drum`, power tap pole `ek_sb_tap`, tunnel vent stack `ek_sb_vent`, cable trench cover `ek_sb_trench`,
station wall sign `ek_sb_sign`, battery bank `ek_sb_battery`, tool cart `ek_sb_cart`, bulkhead door `ek_sb_bulkhead`,
pipe run `ek_sb_pipes`, insulator stack `ek_sb_insul` and sandbag barrier `ek_sb_sandbag`. No existing row changes.
Each prop is a compiled model, a collision file, a material file and its maps (colour 1024 or 2048, the other maps at
half that or less), and a blueprint named as its model, offered through the pack's `placeablepalstd.itp`.

Origin: each prop was cropped from the operator's concept sheet and redrawn locally with Qwen-Image 2.1 as a plain
reference, enlarged to 2048 pixels with RealESRGAN x2plus, then generated by the operator's Meshy account through the
pinned `meshy-cli@0.4.0` at 2,900 to 10,162 triangles (attribution: [Meshy](https://www.meshy.ai/); paid plan, as the
Stuffer Shack tile group's entry above records; operator, 2026-11-18: "Raise the cap by 210 and do the props"). No
third-party mesh or texture was used. The station's name and the wording of its signs are the sheet's own invention.

Modifications, all by `tools/envkit` (SRN project operator with Claude): each model was turned to the game's axes and
scaled to a stated height, and its textures were recompressed. The wall sign hangs 1.6 metres up; it is one sheet,
and its back came with the front's lettering mirrored: the back half of the sheet was painted a plain steel grey and
its relief levelled, and the lettering stays as a faint stamped outline in the mesh. The switchgear cabinet came back with two wedges of its front
wound inside out, dark holes in the client, and has a back to every face. Three props have a glow map for their lit
parts and a lights-out material (`<name>_o`) as `docs/envkit/lights.md` describes: the switchgear cabinet's three
indicator panels, the battery bank's two green charge lights and its amber one, and the amber lamp over the bulkhead
door. The bulkhead door also lights what stands round it, by a light in its row of `placeables.2da` (lightcolor row
5) at its lamp; the indicators and charge lights only glow. Nothing else was retouched.

Checked in the game client on 2026-11-18: by day from front, back and side with a figure for scale, from the converted
files; and by night from the pack's files, where the lights of the three lit props were put out by script and brought
back, the ground before the bulkhead door lit by its lamp.

## Happenstance props (`srn_envprop`, `srn_2da`; 2026-11-24)

Twenty-nine envkit props from the Happenstance nightclub concept sheet's exterior join `srn_envprop` (the envkit
prop pack, as the section below records), each with a
row appended to `srn_2da/placeables.2da` (22889-22917, labelled `[envkit]Happenstance, ...`): neon sign `ek_hs_sign`,
martini neon sign `ek_hs_martini`, Casquilho Familia sign `ek_hs_familia`, entrance canopy `ek_hs_canopy`, entrance
doors `ek_hs_doors`, large and small storefront windows `ek_hs_shopwin` and `ek_hs_shopwin2`, large and small upper
windows `ek_hs_upwin` and `ek_hs_upwin2`, service door `ek_hs_svcdoor`, roll-up door `ek_hs_rolldoor`, wall light
`ek_hs_walllamp`, alley lamp `ek_hs_alleylmp`, chain bollards `ek_hs_chain`, queue stanchion `ek_hs_stanchn`, tagged
dumpster `ek_hs_dumpster`, trash bags `ek_hs_bags`, steel planter `ek_hs_planter`, utility cabinet `ek_hs_cabinet`,
electrical box `ek_hs_elecbox`, conduit bundle `ek_hs_conduit`, drainpipe `ek_hs_pipe`, twin drainpipes
`ek_hs_pipes`, wall AC unit `ek_hs_acunit`, large and small rooftop HVAC units `ek_hs_hvac` and `ek_hs_hvac2`,
turbine roof vent `ek_hs_turbine`, roof vent stack `ek_hs_ventcap` and antenna mast `ek_hs_antenna`. No existing row
changes. Each prop is a compiled model, a collision file, a material file and its maps (colour 1024 or 2048, the
other maps at half that or less), and a blueprint named as its model, offered through `srn_placeable`'s
`placeablepalstd.itp`. The sheet's building is not made: these are its props only (operator, 2026-11-24). Four more
exterior props (satellite dish, graffiti panel, curb section, sidewalk section) wait for Meshy funds, and the
sheet's interior props are not begun.

Origin: each prop was cropped from the operator's concept sheet and redrawn locally with Qwen-Image through the
shared ComfyUI as a plain reference, enlarged to 2048 pixels, then generated by the operator's Meshy account through
the pinned `meshy-cli` (attribution: [Meshy](https://www.meshy.ai/); paid plan, as the Stuffer Shack tile group's
entry above records; operator, 2026-11-24: "Raise and submit"). The martini sign's reference was drawn again and the
operator chose among the redraws. As installed the models have 1,178 to 9,210 triangles. No third-party mesh or
texture was used. The club's name and the wording of its signs are the sheet's own invention.

Modifications, all by `tools/envkit` (SRN project operator with Claude): each model was turned to the game's axes and
scaled to a stated height, and its textures were recompressed. Wall-hung props hang at a stated height (the neon sign
3.2 metres up, the upper windows 4.0, the storefront windows 0.8). Retouched:

- Entrance doors: the glass came as layers shaded in facets and ragged at the rails. Each of the four panes is a
  built bar inside its frame, coloured from the glass, which was painted one violet; the model has a back to every
  face.
- Large storefront window: the generator made it a glass box. One wall is kept and moved to the model's middle; the
  other walls, the floor, the side walls left standing across the window at both ends and a strip of glass before
  each jamb were cleared, and a frame-coloured post is built between the last pane and each jamb. Its ten panes,
  which carried dark smears, are painted and levelled to one magenta.
- Small storefront window: its six panes, on which shards were drawn, are painted one violet.
- Roll-up door: slits ran right through between its slats. A sheet is built behind them, the slats drawn as black
  streaks were smoothed and drawn again, and the model has a back to every face.
- Turbine roof vent: its top came open like a bowl and is closed with a flat lid of fourteen faces.
- Antenna mast: a stray wire running off the top of the pole was cleared.
- Casquilho Familia sign: a back to every face.

Ten props have a glow map for their lit parts and a lights-out material (`<name>_o`) as `docs/envkit/lights.md`
describes: the neon of the two neon signs, the canopy's neon bands and downlights, the glass of the entrance doors
and of the four windows, the wall light's bulb and the alley lamp. The two neon signs, the canopy and the alley lamp
also have a halo. Three light what stands round them, by a light in their rows of `placeables.2da`: the canopy and
the alley lamp (lightcolor row 2) and the wall light (row 1); the signs, doors and windows only glow.

Left as generated, and known: the drainpipe and the twin drainpipes are 0.8 metre sections, as their references were
drawn, not full runs; the turbine vent is squat with a flat top where the sheet shows a dome; the Familia sign's
back shows its lettering mirrored, and the large upper window's back a stray triangle, both hidden against a wall;
the small storefront window's panes show faint facets close up by day, and the large one's a soft sheen.

Checked in the game client on 2026-11-24: by day and by night from front, back and side with a figure for scale, from
the converted files (the four props hung at 3 metres and more were judged from copies lowered into the frame); and
by night from the pack's files, where the lights of the ten lit props were put out by script and brought back, the
ground lit by the canopy and the two lamps. Placed in the Toolset the same day from the Standard palette (Shadowrun City): the neon sign, the entrance doors, the large storefront window, the alley lamp, the tagged dumpster and the antenna mast, saved with their rows, the four lit ones not static.

## Envkit props moved to their own pack (`srn_envprop`, `srn_placeable`; 2026-11-24)

With the Happenstance props `srn_placeable` came to 2,103 MB, and a hak is not built past 2 GiB: the packer
(`nwn_erf`) refuses it, the archive's offsets being 32-bit. Every envkit prop file, 1,763 files of 865 MiB named
`ek_*` (models, collision files, materials, maps, blueprints and the shared dark halo `ek_off`), moved unchanged
from `srn_placeable` to the new pack `srn_envprop`, registered in `hakbuilder.json` (operator, 2026-11-24: "move
all envkit props to their own hak"). `srn_placeable` is left at 1,251 MiB (1,252 MiB as a built hak, `srn_envprop`
865 MiB) with the MDRNEE placeables and the two palette files; `placeablepalstd.itp` stays there, one file for every
placeable of a module, and still lists the envkit blueprints. No file's content, name or `placeables.2da` row changed, and the catalog's `pack` of each of the
178 envkit placeables now reads `srn_envprop`. The props' sections above name `srn_placeable` as the pack they
joined at the time and are left as written.

A module that uses envkit props, or an envkit tile group with lit parts (their lights-out materials name
`ek_off`), lists `srn_envprop` beside `srn_placeable`. `envkit placeables` and `blueprints` now write to
`srn_envprop` (`--pack`, `--dark-pack`), the palette to `srn_placeable` (`--palette-pack`), and `placeables`
refuses a pack it would fill past 1,900 MiB.

## MDRNEE placeable import (2026-09-11)

`mdrnee_placeable.hak` was imported in full under the `mdrnee_placeable` profile. Its verified
SHA-256 is
`E90B4F15EE15D8009D843C8B2EB70C77BD835FF0ED77F1534BB5EC4963B8A159`.
Of 15,256 source resources, 15,254 land in `srn_placeable`, `srn_sound`, or `srn_2da`; the two
credit text files are represented by this provenance record and the analysis reports rather than
packed as game resources. Exact per-resource hashes and dispositions are recorded in
`docs/imports/mdrnee_placeable-manifest.json`.

The archive's 30,000-row `placeables.2da` is a legacy aggregate containing base-game copies, empty
user allocations, and CEP reservations. The generated `srn_2da/placeables.2da` starts from the
pinned NWN:EE 89.8193.37-17 (`r1284`) baseline and imports only the 4,752 source rows whose model is
actually supplied by this HAK. No active EE placeable row is replaced. The generated
`placeableobjsnds.2da` adds only row 59 (`Brush`), used by 32 landed foliage appearances. The
single `CEP Specific` category is removed from `placeablepal.itp`; its other 141 legacy custom
references are migrated to 125 deduplicated canonical TLK entries. Allocation and transformation
evidence is recorded in the corresponding `mdrnee_placeable-*` reports under `docs/imports/`.
The malformed source identity `p_eng blk01.pwk` is repaired at landing to
`p_eng_blk01.pwk`, matching its model companion while preserving the original name and bytes in
quarantine.

Cross-checking against the tile and audio imports found 56 byte-identical `cq*.pwk` placeable
companions and two registered `shp_ceilg0*.mdl` placeables misplaced in the tile bundle. Their
canonical destination is `srn_placeable`; `udp1_a01_01.pwk` remains tile-owned. Four bundled WAVs
were already supplied byte-identically by the audio import, while two additional metallic-locker
sounds land in `srn_sound`. Shared texture identities and their order-sensitive variants are
declared in `hakbuilder.json` and documented in
`docs/imports/mdrnee_placeable-cross-hak-audit.md`.

The source credits name MGSkaggs, LOK, DOTF, DK, X12, Jezira, Brian Harrison, Chandigar UDP,
Purple Puppy, Ed Baumgarten, Vanya Mia, Chico, Aenea, Xenovant, OldTimeRadio, Plush Hyena of Doom,
VeilofShadows, DrA, Henesua, Shemsu-Heru, Cestus Dei, Amethyst Dragon, Vibrant Penumbra,
Valthrendir, Borden Haelven, and MerricksDad, with additional credited static-mesh sources recorded
in `creditdoc.txt`. This batch is covered by the same operator-reviewed open-project permission and
attribution conditions described for the MDRNEE tileset import; it is not relicensed under the
repository's default PolyForm license.


<!-- srn-size-exception {"path":"srn_t_vmp01/vmp01_building01.tga","reason":"Required original D20 Planetscape tileset texture; reviewed at 16,777,260 bytes and below GitHub's hard limit."} -->

## Accepted MDRNEE source limitations and repairs

The source archives contain no `sjm_udoor_01.dwk` or `sjm_udoor_02.dwk`; the corresponding
unreferenced SJM door registrations are therefore withheld, while their models remain available for
later recovery. D20 Parking Garage remains a group-centric legacy SET whose four named terrain and
crosser brushes have no source placement rules. UDP2 remains usable with its legacy edge behavior;
the unresolvable `gi_z*` edge references and missing `Office_Alum` edge rule are deferred polish.

No inspected staged HAK supplies `vmp01__ref01` or the 191 VMR01 `midr01_*` minimaps. Planetscape
therefore uses the EE `env_tti` environment-map fallback. Mars Interior remains usable but displays
blank custom area-map tiles until authentic minimaps are recovered. No substitute art was fabricated.

The DGT repair wraps 172 bare Blender AABB exports as standalone WOK resources without changing
geometry, corrects one internal edge-model identity, and restores evidence-backed edge/minimap metadata.
SRT04 shared-model door, crosser, and minimap records are restored from the matching packaged DGT
records. Planetscape tile 382 remains a decorative Wall Gate with `Doors=0`, matching both the
MDRNEE source and SWLOR's working decomposition; no unproven door transform was invented.

Final review also restores source-backed DGT/SRT minimap and group metadata, enables VMP's declared
height rules, aligns VMP edge aliases with its SET names, and restores ZSF stair-door visibility.

Withheld SJM doortype rows remain explicit blanks so later numeric IDs are stable. Final review also
restores Flow ramp lighting and the VMR Exterior Dais 2 walkmesh identity; fixture tooling now
resolves pinned GFF and ERF executables through the platform-aware tool manifest.

The shared chainlink_fence.dds source texture is owned by srn_t_common so both DGT tiles
and its placeable consumer close without a HAK-order duplicate. Final metadata repair also aligns Flow
door slots to model hooks, corrects SJM/SRT/ZSF minimaps, normalizes invalid ZSF boolean flags,
and binds the Planetscape palette to mp01.

## MDRNEE item analysis (2026-09-12)

`mdrnee_item.hak` was decomposed in quarantine under the `mdrnee_item` analysis profile. Its
verified SHA-256 is
`3CE0229D041F12789BB7B4C44AA534570B8A56F4AC9F0DC75E9A018D3C0CC654`, covering exactly 3,406
resources. No item resource is landed by this analysis change. Exact source hashes and proposed
destinations are recorded in `docs/imports/mdrnee_item-manifest.json`.

The archive credit file attributes earlier work to the original D20 Modern team and later item,
weapon, lightsaber, icon, GUI, animation, and holdable contributions to Jezira, Prole, Xialya,
Vanya Mia, Taina, JKA, Forestwolf, Shemsu-Heru, Aenea, The Barbarian, Zwerkule, and Den of
Assassins. The credit record establishes attribution but is not itself a standalone license. Any
future promotion must retain the operator-reviewed open-project terms described above and confirm
that the item archive belongs to the same Neverwinter Vault distribution.

The HAK contains no UTI blueprints, but the companion project-source `d20modernupdate.erf` (SHA-256
`CD96273454F3C6AF55F40B683C9C0F237129D95B1BD07C68418756FE4FE71A4D`; 17,715,193 bytes; 5,534
resources) supplies 669 item blueprints. All 669 map to the HAK's friendly `itempal.itp` categories
and source `baseitems.2da` rows. Only the UTI records are item-import evidence; the ERF's areas,
creatures, doors, placeables, scripts, and other module content remain quarantined. See
`docs/imports/mdrnee_item-analysis.md` and `docs/imports/mdrnee_item-blueprint-report.md` for the full
consumer, dependency, and global-table assessment.

The SR3 appearance crosswalk comes from `sr3-blueprint-candidates.xlsx` (SHA-256
`06FFCF13C39C04B57F58E45EC75FE36D7805DBFC722B0EA97656A0492FA6F5FE`; 68,308 bytes). The
`Candidates!A1:T97` classification and `Method!A1:B24` provenance ranges identify 12 Exact identity
and 81 Visual stand-in candidates. All 93 join uniquely to the verified companion ERF by Blueprint
ResRef and source base-item row. This crosswalk contributes classification and catalog-identity
metadata only; its advisory dependency and rights fields do not supersede this repository's source,
dependency, or licensing review.

## Purpose-built muscular Human male (2026-10-03)

`srn_body` contains the project's accepted fourteen-part Human male body: 72
native model, palette texture, normal, roughness and material resources. The
operator requested publication of this current usable baseline and prioritized
the remaining races over further optional Human polishing.

The anatomy and textures were commissioned through the project's image-generation
and local ComfyUI individual-part workflow, then fitted and refined in this
workstream. Stock NWN:EE Human male parts, attachments and animation controllers
provided the dimensional and motion reference. The stock root, supermodels,
animations, neck/head, tables, equipment and test fixture are not redistributed
in this pack. The generated content is contributed by the SRN project operator
with Codex-assisted generation, fitting, material processing and validation.

Every published resource is byte-identical to the payload of the accepted
`human_male_body.hak`, SHA256
`01524cd39ad111021d30ba9a7c2241fdf8ef3afc7eb77f04346907d423d9f7c2`.
Per-resource hashes and sizes are in
[`docs/phenotypes/human-male-assets.json`](docs/phenotypes/human-male-assets.json).
The 527,885,123-byte resource payload has no individual file above 15 MiB, so no
size exception is needed. Models are already compiled; `CompileModels` stays
false. Rebuilt archive metadata may differ while all resource bytes must match.

[The delivery record](docs/phenotype-human-male-delivery.md) identifies the actual
native/offline/client evidence, animation sheets and accepted practical limits.
Generation masters and intermediate maps remain local working assets; packaged
runtime resources are versioned here. Only an explicitly better validated
selection should supersede this baseline.

## Head expansion and inspection gallery (2026-10-05)

The [head catalog](docs/heads/pilot-catalog.json) adds Elf, Dwarf and Orc male
donors generated with Meshy 7 from original OpenAI-generated SRN references.
Reference prompts, ancestry hashes, task IDs, retained source hashes, local LOD,
cap-only changes, materials and native candidate resource pins are recorded
there and in the [evidence notice](docs/heads/evidence/NOTICE.md). Meshy attribution
and conditional redistribution terms remain explicit. These candidates are
native validated; client and production acceptance remain pending. No runtime
heads are published in a production HAK at this checkpoint.

The gallery source was original project tooling that packaged registered
resources and verified candidates in an ignored local inspection module. It was
removed from the repository on 2026-10-14 pending a redesign; it committed no
installed game resources.

## Meshy robe trial (2026-10-06)

`docs/robes/` and `tools/robes/` record a bounded conversion experiment; no trial
asset is packed into any repository HAK. Outfit concepts were supplied by the SRN
project operator. 3D outfits were generated by the operator's Meshy account through
the pinned `meshy-cli@0.4.0`; the account tier was not verified, so generated
outputs and their derivatives are treated as CC BY 4.0 ("Model created with
Meshy", https://help.meshy.ai/en/articles/10137554-what-is-the-ownership-of-the-generated-models)
until confirmed. Meshy sources, fitted candidates, textures, the trial HAK and the
test module stay in ignored `output/robes/`. Committed evidence under
`docs/robes/evidence/` is limited to small review renders of those derivatives and
carries the attribution in its NOTICE. Stock NWN:EE robes, body parts, rig and
animations were read from the installed game as dimensional and weight references
and are not redistributed. Production use requires a separate rights review.

## PhenoMorpher reviewed body phenotypes (2026-10-13)

The selected twenty Human/Dwarf/Elf/Orc/Troll female/male Fit/Large bodies
are published into `srn_body`; their appearance routing is in `srn_2da`.
Contributor: SRN project operator, with Codex-assisted fitting, UV/material
processing, native verification and client review. The latest published Human
male v2 and female body donors are retained as the derivation basis. Fit
shapes/rigs and selected Large shapes remain unchanged in this publication.

The new Large chest sources were commissioned through the operator's local
ComfyUI purpose-built Pixal3D/Trellis workflow from approved original SRN
references, fitted to the existing bodies, UV-mapped to their materials and
reduced to 5,494 male / 5,482 female triangles. Generated masters, prompts and
operational receipts remain ignored working data. No Meshy source is used for
these replacement chests. Original generated anatomy/material contributions
retain the repository's applicable original-content license.

Private fitted animation closures and stock head routing aliases are NWN
compatibility derivatives, retaining installed-game authorship rather than
claiming original ownership of stock geometry or animations. Unmodified global
stock `a_*` animations and original Human heads/textures are installed-game
dependencies. A licensed NWN:EE installation is required. This record does not
license third-party platform content under the repository's original-content
license.

The exact source archive/payload hashes, published byte counts, target routing,
name-only Fit promotions and dependency closure are recorded in
`docs/phenomorpher/game-ready-assets.json`. The operator requested publication
after client review. Representative literal client screenshots and coverage are
included alongside that contract; no image-generation edits were made to them.
Diagnostic clothing, material comparison variants, game profiles, credentials,
raw crash dumps and test module resources are excluded. Every resource is below
15 MiB; no size exception is required.

srn_body_tex contains the exact-byte selected new skin normal/roughness maps. The stock-exact phenotype.2da and whitelisted racialtypes.2da changes, including disabled Half-Elf/Halfling player selection, are recorded in docs/phenomorpher/table-validation.json. Eight permanent Troll/Orc display strings are allocated in srn_tlk; ability/feat/gameplay rules retain installed values.

## PhenoMorpher stock armour conversion (2026-10-16)

`srn_armor` contains 6,180 native armour part models for the 16 non-Human
PhenoMorpher bodies (Dwarf, Elf, Orc and Troll; female/male Fit/Large). Each is
an installed stock NWN:EE Human armour part of the same gender and build, moved
onto the new body by one measured scale/rotation/translation per body part with
the pinned NWNArmory 1.3.4, renamed to the target body's stock part name and
compiled by the NWN:EE client. They are NWN compatibility derivatives and retain
installed-game authorship; the repository's original-content license does not
relicense this stock geometry. Their textures are not redistributed: every part
keeps its stock texture references, which resolve to the installed game. A
licensed NWN:EE installation is required.

Contributor: SRN project operator, with Codex-assisted fitting, conversion and
native/client verification. The operator approved the pilot client review and
requested the full conversion. Per-resource source, profile, conversion and
compile hashes are in `docs/phenomorpher/clothing/srn-armor-assets.json`;
method and evidence are in `docs/phenomorpher/clothing/`. Robes, cloaks, heads
and the bare body parts in `srn_body` are excluded. Every resource is below
15 MiB; no size exception is required.

## Approved female Troll heads (`srn_head`)

Original SRN-generated references and Pixal3D geometry/appearance, locally cleaned,
UV-mapped, fitted and encoded as NWN:EE native models with 1024-square PLTs.
User-approved heads: attempt63 `pfg0_head032`, attempt68 Samurai `pfg0_head090`,
attempt73 Bob `pfg0_head091`, and attempt74 Undercut `pfg0_head092`.
Each head has 20,000 triangles. Fixed-string compiler tails are zeroed using the
existing armour sanitizer; geometry, material references and PLTs are unchanged.
This batch contains only four compiled MDL/PLT
pairs; source images, masters, trial tools, demo modules and generated HAKs stay
outside the production source pack. Approval does not establish exhaustive
animation, equipment or palette-combination coverage.

## Approved Cougar blades and Colt L36 (`srn_weapon`, 2026-10-24)

The project operator supplied the detailed weapon references. Pixal3D generated
the geometry and appearance; local processing fitted, reduced, UV-mapped,
transferred textures and compiled the assets for NWN:EE. Published models and
textures are the exact accepted payload: Cougar Fineblade Longblade (short sword),
Cougar Fineblade Knife, Cougar Fineblade Longsword, and Colt L36 in its base and
cool gunmetal finishes. Five item blueprints and their multipart inventory icons
are included. Blueprint display names/descriptions receive only the documented
publication cleanup; all non-display fields are preserved. User approval and
per-resource/archive hashes are recorded in
`docs/items/approved-weapons-v1.json`. Supplied branding remains part of the
reference design; this record does not assert ownership of third-party marks.

The new `srn_2da/baseitems.2da` is an installed-game compatibility derivative.
It retains the accepted fixture's two display changes to Sling row 61:
`ModelType` 0 to 2 and `MaxRange` 50 to 52. All other parsed fields and the
original table's unrelated bytes are preserved. Installed-game authorship
applies to the underlying table; a licensed NWN:EE installation is required.
The operator explicitly requested including this display-table change in the
PR for review. Its effect on ordinary Sling appearances is documented in
`docs/items/approved-weapons.md`; this is not a new compatibility approval.

Raw references, high-resolution masters, test module actors, experimental
assets, SMG preparation and generated HAK archives are excluded. Every resource
is below 15 MiB. The original accepted packages and trial history remain intact.

## Approved male Troll heads (`srn_head`)

Original SRN-generated Flux.2 designs and Pixal3D single-view geometry/appearance,
locally wrapped, shaped, UV-mapped, fitted to `pmg0_head014` proportions and
encoded as NWN:EE native models with 1024-square PLTs by the headkit pipeline.
User-approved in game (client trial `srn_trl_batch1`, 2026-10-24): troll-male-01
`pmg0_head015`, troll-male-02 `pmg0_head016`, troll-male-03 `pmg0_head017`,
troll-male-04 (design A, rigger) `pmg0_head018`, troll-male-05 `pmg0_head019` and
troll-male-06 `pmg0_head020`. Each head has 20,000 triangles; skin shades are
tone-matched to the stock Troll male heads, and horns, tusks, metal and tattoos
use PLT channels 1, 2, 8 and 9 as reviewed. Fixed-string tails were zeroed by
the native stage with the existing armour sanitizer. This batch contains only six
compiled MDL/PLT pairs; source images, masters, trial tools, demo modules and
generated HAKs stay outside the production source pack. Approval does not
establish exhaustive animation, equipment or palette-combination coverage.

## Troll heads: neck cut, female batch 1 and batch 2 (`srn_head`, 2026-10-25)

Same origin and pipeline as the approved male Troll heads above: original
SRN-generated Flux.2 designs and Pixal3D single-view geometry/appearance,
processed by the headkit pipeline into NWN:EE native models with 1024-square
PLTs (20,000 triangles each). Every head now ends under the jaw; the body's own
neck part forms the neck (`mesh.neck.cut`). All 30 compile through Blender 5.2.1
LTS with NeverBlender 4.5.1 (cleanmodels v4.10.0); decoded geometry matches the
source within 1.5e-8.

- Neck-cut replacements for troll-male-01 to 06 (`pmg0_head015`-`020`); geometry
  above the cut, UVs, materials and palette rows are unchanged.
- Female batch 1, user-approved in game (2026-10-24) and neck cut:
  troll-female-04 `pfg0_head010`, 05 `pfg0_head011`, 07 `pfg0_head013` and
  08 `pfg0_head014`.
- Batch 2: troll-female-12 `pfg0_head012`, 15-23 `pfg0_head015`-`023`, and
  troll-male-21-30 `pmg0_head021`-`030`.

All 30 heads were checked in game on the release Troll bodies (appearance 15104)
in still client trials, and every actor loaded on its expected slot. The files
are byte-identical to those trials' payloads and to the hashes pinned in each
native-stage receipt. Fixed-string compiler tails were zeroed by the native stage
where present. Only the compiled MDL/PLT pairs are included; source images,
masters, trial tools, demo modules and generated HAKs stay outside the production
source pack. Checks do not establish exhaustive animation, equipment or
palette-combination coverage.

## PhenoMorpher release 1.3.0: race lore sizing and the c7 Human lock (2026-10-27)

Derived from the project's own published PhenoMorpher bodies (contract 1.2.0), with no new external source. All
changes come from local, deterministic transforms of those models:
* uniform rest-pose stature rescales;
* Large-male joint heights set to Fit;
* a sideways lore build scale;
* the Human b13/c6 hip, knee and torso join recipes ported to the race females;
* a root raise that puts idle soles on the floor;
* per-clip root lifts in the race animation libraries (`srn_an_*`), so no race body goes further below the floor
  than it did in 1.2.0.

The c7 Human lock adds the c6 female joins, torso polish and rebuilt skin, and `pmh2` with its joint heights at Fit.
The skin re-bake reuses the published body textures. The 34 published Troll heads in `srn_head` are rescaled
uniformly by the Troll stature factor. Their geometry is otherwise unchanged, and their PLTs are unchanged.

`srn_armor` is the installed-game stock armour re-fitted to the new race bodies with NWNArmory 1.3.4, with the same
origin and licensing note as the stock armour conversion above. A licensed NWN:EE installation is required.

Models are compiled with Blender 5.2.1 and Neverblender 4.5.1 (cleanmodels v4.10.0). Fixed-string tails are zeroed,
and every published binary passes the leaked-text check.

The user approved every race body, the armour and `pmh2` in game, and approved publication on 2026-10-27. Evidence
and per-resource hashes are in `docs/phenomorpher/race-sizing/` (`plan.md`, `release-1.3.0.json`) and
`docs/phenomorpher/human-bodies-lock-c7.json`. Generated stages, client fixtures and captures stay outside the
production source packs.

## Approved Waves 1 and 2 private weapon review (2026-11-03)

The source-accurate SR4 catalog references and generated itemkit weapon assets in
`test-modules/weapon-waves` are the user-reviewed private candidates. Geometry
and appearance were produced through the retained clay/detail workflow, fitted
to the shipped Humans and converted to native resources. Katana, Crossbow, Bow,
Ingram orientation and Human weapon motion include the final reviewed repairs.
Stock-derived carrier/animation/environment resources require a licensed NWN:EE
installation. Existing approved comparison assets retain their prior provenance.
The payload manifest records exact bytes; source books, generation intermediates,
local bindings, HAK archives and body-pack duplicates are excluded. This publishes
a reproducible private test fixture, with no production promotion or new rights
claim over Shadowrun or Neverwinter Nights material.

## Approved weapon waves normal-pack integration (srn_weapon, srn_2da; 2026-11-03)

This supersedes the private layout above. The ten reviewed wave designs and
separate AK-98 launcher blueprint join the existing Cougar/Colt resources in
`srn_weapon`; no weapon geometry, material or embedded native animation is
regenerated. The Cougar long-blade knife moves to F1/row22 with equal-length
model aliases and fitted inventory icons; its original models/icons remain for
saved-item compatibility. The other Cougar and Colt assets retain their native
bytes and are explicitly assigned to the selected family plan. F2's appearance
picker MaxRange becomes111; other gameplay/table fields are preserved.

Crossbow texture pixels are unchanged under the corrected referenced resource
name. The Throwing Knife includes its reviewed shared native projectile. Resource
origins/hashes, routing migration and package validation are recorded in
`docs/items/approved-weapons-v1.json` and the release guide. The frozen grouping
plan is retained under `docs/items/weapon-baseitem-plan-v1/`.

The comparison module remains in `test-modules/weapon-waves` and consumes the
normal packs. Prototype Human motion roots and event hooks stay there exclusively
for itemkit testing. The production body packs and roots are unchanged;
production weapon animation belongs to PhenoMorpher toolkit. This PR publishes
release sources and performs no live deployment or new rights assertion.

## Troll heads: build allowance (`srn_head`, 2026-10-29)

The 34 published Troll heads in `srn_head` are derived from their own 1.3.0 binaries, with no new source. On top of
the 1.3.0 stature scaling, each head is scaled uniformly about its mesh node frame. Female heads use the square root
of the Troll stature ratio S: ×1.0729 (S 1.151). Male heads use ×1.5. The user first chose ×1.0483 (the square root of
S 1.099) for them, then chose ×1.5 after reviewing body renders. At ×1.0483 the male heads read about 20% smaller
than the base head001 and left the neck showing behind the skull. Both choices were made on 2026-10-29. Normals, UVs,
faces, materials and PLTs are unchanged.

The heads are decompiled and recompiled with Blender 5.2.1 and Neverblender 4.5.1 (cleanmodels v4.10.0). Fixed-string
tails are zeroed, and every binary passes the leaked-text check. Decoded positions equal the 1.3.0 positions × the
factor within 6e-8 (female) and 3e-8 (male). The stock-head routing aliases `srn_body/p[mf]g0_head001.mdl` belong to the PhenoMorpher contract
and are not changed. Per-head hashes are in `docs/heads/troll-build-allowance-r3.json`.

## Race heads v1: first 12 heads (`srn_head`, 2026-11-03)

Twelve generated heads join `srn_head`: five Human, four Orc, two Dwarf and one Troll. Each started from a local Flux.2 front design, then Pixal geometry and appearance, then the headkit chain with face masks, and native compile through Blender 5.2 and Neverblender. The content is contributed by the SRN project operator with Claude-assisted generation, fitting, texturing and validation. Stock palettes and body necks were local validation inputs and are not redistributed. The slots and client evidence are in `docs/heads/race-heads-v1-checkpoint.md`. This publishes no stock head, table or body change.

## Vibro Blades — Sword and Ares Predator IV (srn_weapon, srn_2da; 2026-11-05)

Same origin and pipeline as the approved weapon waves above: source-accurate SR4
catalog references (clay and detail pairs), Pixal3D single-view geometry and
saved-shape appearance generated through the shared itemkit trial ledger, then
fitted to the Cougar melee and Colt firearm grip standards, reduced, UV-mapped,
baked and compiled to NWN:EE native models. The Predator's engineering shell was
rebuilt from its textured donor surface and bakes with a reviewed four-face
sampling patch (22 of 687,404 texels) recorded in the private run. The
exact payload bytes are published in `srn_weapon`; hashes and approval statements
are in `docs/items/approved-weapons-v1.json`. `srn_2da/baseitems.2da` only
extends the F2 and Sling appearance-picker `MaxRange` values (to 121 and 65).
Generation intermediates, local bindings, HAK archives, ledger entries and client
captures stay outside the repository. The Ares and Shadowrun names, branding and
designs are third-party marks; this record asserts no ownership of them and adds
no new rights claim.

## Firearm sounds (`srn_sound`; 2026-11-07)

Seventeen WAVs were copied byte for byte from the user's `SRN_CC` staging folder, `content/staging/sounds/`, into `srn_sound`. No 2DA
row references them yet. Eight (`dryfire_*`, `ric_*`, `rocket`, `reload_rocket`) match the old Shadowrun mod's `gun sounds`
folder under `SR_NWN/OLD_SR_MOD_ASSETS`. The nine `fire_*` files have no copy in those assets, so their origin is unrecorded. The
user supplied them, but that isn't a record of their licence or recording source.

`fire_sup_pst_smg` is the staged `fire_sup_pistol_smg.wav`, shortened because 19 characters exceed the 16-character resref limit.

No resref collides with a stock `.wav` key or another WAV in this repository. The hyphenated names keep the spelling the old
`visualeffects.2da` rows used.

| File | SHA-256, first 12 |
|---|---|
| `dryfire_pistol.wav` | `343E14613D63` |
| `dryfire_rifle.wav` | `C80E1AE22325` |
| `fire_smg.wav` | `0733F3B1E84B` |
| `fire_shotgun.wav` | `9E3464A25450` |
| `fire_aslt_rifle.wav` | `A979225F38D9` |
| `fire_hvy_pistol.wav` | `F31A56417940` |
| `fire_lt_pistol.wav` | `8475D9A03B61` |
| `fire_snp_rifle.wav` | `549454453AE2` |
| `fire_spt_rifle.wav` | `6552910F3C17` |
| `fire_sup_pst_smg.wav` | `20FAE7D8F921` |
| `fire_sup_rifle.wav` | `B55D51DB4ADC` |
| `reload_rocket.wav` | `80218182147D` |
| `ric_conc-1.wav` | `43A8EC357F9F` |
| `ric_conc-2.wav` | `63B11392E757` |
| `ric_metal-1.wav` | `E1FB440E88FA` |
| `ric_metal-2.wav` | `6F9D545AE480` |
| `rocket.wav` | `40FE512E95EB` |

## Troll heads: five approved designs and gnome-slot replacement (2026-11-07)

Five new heads (four male, one female) were generated from operator-selected ImageGen designs, with clay/detail conditioning, Pixal geometry and saved-shape appearance, and headkit fitting, masks, PLT palette mapping and native compilation. The SRN project operator approved their publication after client review. The male trio designs are Breakwater, Ballast and Vesper; the earlier pair retains its approved proportions and palette textures.

All 40 Troll heads are renamed into male/female slots 001–020 to replace base-game gnome heads. The 35 existing designs have no new geometry or texture source: only bounded native name fields and resource filenames change. PLT bytes are unchanged. See docs/heads/troll-head-reindex-v1.md and its hash manifest for the complete mapping, evidence, load order and saved-character migration implications. Historical provenance entries retain their original slots.

## Firearm effects and crossbow carry (`srn_weapon`, `srn_body`; 2026-11-07)

**Emitters: credit hairybrain.** The muzzle flash and the shell casing come from hairybrain's emitters in the old
Shadowrun mod's `!Combat Override System` folder (`SR_NWN/OLD_SR_MOD_ASSETS`), credited at the user's direction:

- **Flash:** the nine `muzzle_flash01..09` emitters in `WIP/combat_ovr_v1.hak/models/wbwxh_m_154.mdl`, renamed
  `srn_flash01..09`, moved onto each gun's muzzle and retimed to start full and fade over 0.1 s. They draw the stock
  `fxpa_flare` texture.
- **Casing:** the `Casings39` emitter in `OLD/!DONE/gun models/wbwar_t_101.mdl`, renamed `srn_casing`, placed on each
  gun's ejection port and resized to 0.085.
- **Casing sheet:** `srnfx_casing.tga` is the old `fxpa_smoke02.tga` casing redrawn as 16 tumbling frames (the old
  file overwrote a stock texture name).

The gun geometry is unchanged from its approved publication. `tools/itemkit/firearm_fx_pilot.py --ship` adds the
emitters and their clips to the effect-free parts at commit `2805a5ec` and compiles them with the vendored
`nwnmdlcomp`. Compiled bytes vary between runs only in stored memory pointers; decompiles are identical.

| File | SHA-256, first 12 |
|---|---|
| `srn_weapon/wbwsl_b_051.mdl` | `99BC6299157A` |
| `srn_weapon/wbwsl_b_052.mdl` | `9ECE48AA714B` |
| `srn_weapon/wbwsl_b_065.mdl` | `69EDED3EEDD1` |
| `srn_weapon/wbwsl_m_023.mdl` | `688F616D009C` |
| `srn_weapon/wbwxh_t_015.mdl` | `621CA4693F9E` |
| `srn_weapon/srnfx_casing.tga` | `E8AA922AB82A` |
| `srn_body/a_ba_custom.mdl` | `71E091A80DF1` |
| `srn_body/a_ba_non_combat.mdl` | `708FD5B94F43` |

`a_ba_non_combat.mdl` is the installed NWN:EE model decompiled to ASCII with the keys of its `xbowr` clip removed;
it adds no new content. The `a_ba_custom.mdl` clips come from the old mod's combat clips as recorded for release 1.4.0.

## Two male Dwarf heads (srn_head; 2026-11-07)

The SRN project operator selected and approved two generated adult male Dwarf designs:
a Danny DeVito-like older Dwarf and a copper-bearded Dwarf. ImageGen supplied the
appearance and paired smooth-clay conditioning images. Pixal generated geometry
and saved-shape appearance; headbatch/headkit fitted the meshes, baked textures,
assigned PLT materials, mapped palettes and compiled native NWN:EE resources.
The user approved the final client appearance and requested publication in a
separate asset PR.

Only pmd0_head019.mdl/.plt and pmd0_head020.mdl/.plt are added. The portable
resource hashes, native checks, quality results, client evidence and known
limitations are in docs/heads/dwarf-male-pair-v1.md and its JSON manifest.
Installed stock palettes and body references were validation inputs and are
not redistributed by this change. Generated intermediates, machine bindings,
private receipts and HAK builds remain outside the repository.

## Basalt, Rime and Willowglass heads (srn_head; 2026-11-08)

The SRN project operator selected the generated Basalt and Rime male Dwarf
designs and Willowglass female Elf design with long hair. ImageGen supplied
appearance and paired clay references; Pixal supplied geometry and saved-shape
appearance. Headbatch/headkit performed fitting, repair, UVs, texture baking,
PLT ownership/palette mapping, native compilation and review. The user delegated
operator reviews through the private NWN:EE client and authorized separate
asset and tooling PRs.

Only pmd0_head021, pmd0_head022 and pfe0_head021 MDL/PLT pairs are added.
The exact client-reviewed resource hashes, submission counters, validation,
gallery evidence and limitations are in docs/heads/dwarf-elf-head-trio-v1.md
and its JSON manifest. Willowglass includes the verified local rear-temple
hair closure while preserving her selected fit and prior mapped texture.
The heads reference the game's built-in organic head materials; stock material
and palette payloads are not redistributed. Machine bindings, intermediate
models, private logs and generated HAKs remain outside the repository.

## Melee wave 1: Survival Knife, Sword, Club, Claymore (srn_weapon; 2026-11-13)

Same origin and toolchain as melee wave 2 below. The geometry was generated from source-accurate SR4 catalog references
(clay and detail pairs). For the Sword and Club these were oblique pairs drawn with the Codex app's image tool. The
geometry was then straightened, squared or thinned as recorded with each private run. The content is contributed by the
SRN project operator with Claude-assisted generation, fitting, texturing and validation. The exact payload bytes of each
user-approved run are published in `srn_weapon`, with hashes and approvals in `docs/items/approved-weapons-v1.json`. No
table change is needed. Intermediates, bindings, HAK archives, ledger entries and client captures stay outside the
repository. Shadowrun names and designs are third-party marks; this record asserts no ownership of them and adds no new
rights claim.

## Melee wave 2: Ceramic Knife, Extendable Baton, Tomahawk, Baseball Bat, Stun Staff (srn_weapon, srn_2da; 2026-11-13)

Same origin and pipeline as the Vibro sword above: SR4 catalog references, then
geometry generated from the colour detail image and saved-shape appearance, both
through the shared ComfyUI and the shared itemkit trial ledger. The itemkit
toolchain then fitted the pieces to the Cougar melee grip standard (round, two-hand
and even-section variants), reduced, UV-mapped and baked them, built quadric shadows
and compiled NWN:EE native models. The content is contributed by the SRN project
operator with Claude-assisted generation, fitting, texturing and validation. The
exact payload bytes are published in `srn_weapon`. Hashes and the user's approval
statements are in `docs/items/approved-weapons-v1.json`. `srn_2da/baseitems.2da`
only extends the F1 and F2 appearance-picker `MaxRange` values (to 111 and 181).
Generation intermediates, local bindings, HAK archives, ledger entries and client
captures stay outside the repository. Shadowrun names and designs are third-party
marks; this record asserts no ownership of them and adds no new rights claim.

## Facility Security outfit (`srn_parts`, `srn_2da`; 2026-11-15)

`srn_parts` is a new pack of modular outfit parts made with `tools/armorkit`. Its first
outfit is Facility Security, part number 6020 (set `facility-security`, group `corpsec`):
chest, pelvis, upper arms, hands, thighs, shins and feet for all 20 SRN bodies. That is
240 part models, each with a tint texture of its own name and a material file; normal
maps, and a roughness map for the upper-arm parts; four inventory icons (chest and
pelvis, one per gender). A map that is the same image on several bodies is published
once and named by each body's material file. 746 files, 423 MB.

The design follows the project operator's "Corporate Security: Facility & Patrol
Uniforms" concept sheet. The briefs are `tools/armorkit/briefs/corpsec-facility-male.json`
and `corpsec-facility-female.json` (models `corpsec-facility-male`,
`corpsec-facility-female`). Each reference image was generated locally from its brief's
prompt with the Qwen image model in the shared ComfyUI (profile `qwen21-int8-v1`), and
prepared for generation in the same ComfyUI (prepared images `7be59cf5...a64117`, male,
and `bb63e43b...a04ddb`, female). Geometry and appearance were generated locally from
those images with Pixal3D (`pixal3d_int8_convrot`, Trellis 2 shape VAE, DINOv3 image
encoder) in the same ComfyUI; one geometry submission per model. No third-party
generation service was used.

Local processing cut each outfit into the parts a body wears, fitted them to the seam
contract, reduced them, baked tint, normal and roughness textures and compiled the
models for NWN:EE. Light wear (mottling, scuffed edges, darker creases) is drawn into
the tint textures by the bake, not by the generator, and each part carries the colours
its brief suggests as a starting point for an item's colours. The Human male wears his
own outfit. The Human female wears her own generated chest and the male's other parts
carried to her body. The 18 other bodies wear the Human outfit of their gender carried
to them by `armorkit refit`; nothing was generated for them. The upper-arm parts share
their slot with the body's own skin, which is copied from `srn_body` and `srn_body_tex`
(see "PhenoMorpher reviewed body phenotypes").

`srn_2da` gains live row 6020 in seven `parts_*.2da` tables (chest, bicep, pelvis, legs,
shin, foot, hand). The tables are installed-game derivatives: the game's rows are kept
unchanged and a licensed NWN:EE installation is required. Per-file hashes, the pinned
generation records and the refit reports are in `docs/armorkit/parts-handoff.json`;
the registry is `docs/armorkit/parts-registry.json`.

Raw references, generation outputs, kept parts, bakes and trial packs stay in ignored
`output/armorkit/` and are not redistributed.

## Duty belt and logo brassard (`srn_parts`, `srn_2da`; 2026-11-17)

Two accessories join `srn_parts`, each on all 20 SRN bodies: the Facility Security
duty belt (belt 6020; brief `tools/armorkit/briefs/corpsec-duty-belt.json`, model
`corpsec-duty-belt`) and a shoulder brassard that shows a corporation's logo (shoulder
1000, both sides; model `brassard`). 92 files: 60 part models, the belt's material
files and one normal map shared by every body, one tint texture kept per piece (the
other names are listed in `docs/armorkit/parts-copies.json`), six inventory icons, and
the three logo files `srn_logo.mtr`, `srn_vslogo.shd` and `srn_logos.tga`.

The belt follows the project operator's "Corporate Security" concept sheets. Its
reference image was generated locally from the brief's prompt with the Qwen image
model in the shared ComfyUI (profile `qwen21-int8-v1`); geometry and appearance were
generated locally from it with Pixal3D in the same ComfyUI, two geometry submissions.
No third-party generation service was used for it. Local processing prepared the
piece once and fitted it over the Facility Security outfit on each body
(`armorkit accessory fit`); nothing was generated per body.

The brassard is drawn by `tools/armorkit/brassard.py`: a band round the upper arm over
the outfit's sleeve with a curved badge. Nothing was generated for it. The badge reads
one cell of the logo strip through the material `srn_logo`, whose vertex shader
`srn_vslogo` is the game's stock `vslit` with one line added; SR_NWN picks the cell
per wearer. The strip's pictures are `tools/armorkit/logos/*.png`: Ares, Renraku,
Saeder-Krupp, Wuxing, Mitsuhama, Aztechnology and Lone Star are cut from the project
operator's concept sheets; Evo, Horizon, NeoNET and Shiawase are cut from one image
drawn in the sheets' header style with the Codex app's image tool (OpenAI image
generation) and approved by the project operator. The corporation names and marks are
Shadowrun's, third-party marks; this record asserts no ownership of them and adds no
new rights claim.

`srn_2da` gains live row 6020 in `parts_belt.2da` and live row 1000 in
`parts_shoulder.2da`, installed-game derivatives as before. Per-file hashes, the
pinned generation records and the logo's material, parameter and cells are in
`docs/armorkit/parts-handoff.json`. The brassard's pinned records are
`tools/armorkit/brassard.py` and `logo.py` as they stood at commit `7743369f`, the
publication; both files have changed since. Raw references, generation outputs, fits and
trial packs stay in ignored `output/armorkit/` and are not redistributed.

## Firearm wave 1: Fichetti Security 600, Yamaha Pulsar, HK MP-5 TX, AK-97, Defiance T-250 (srn_weapon, srn_2da; 2026-11-17)

Same origin and pipeline as the Ares Predator IV above: SR4 catalog references, then
geometry generated from the colour detail image and saved-shape appearance, both
through the shared ComfyUI and the shared itemkit trial ledger. The itemkit firearm
route then fitted each gun to the Colt firearm grip standard (the Defiance by length),
squared it to its own middle plane, reduced, UV-mapped and baked it, built its shadow
and compiled NWN:EE native models. The shown model of each gun carries the muzzle
flash and casing emitters and fire clips described in `docs/items/firearm-fx-pilot.md`:
emitter settings from the operator's own earlier mod, sprites from the base game's
stock textures by name, and the casing sheet already published as `srnfx_casing.tga`.
The content is contributed by the SRN project operator with Claude-assisted
generation, fitting, texturing and validation. The exact payload bytes are published
in `srn_weapon`; hashes and the user's approval statements are in
`docs/items/approved-weapons-v1.json`. `srn_2da/baseitems.2da` only extends the F7
appearance-picker `MaxRange` (65 to 77). The Defiance's 2048 px diffuse carries its
reflection mask in an alpha channel, which puts the uncompressed TGA just over the
size limit:

<!-- srn-size-exception {"path":"srn_weapon/sr65882fcd_018.tga","reason":"Defiance T-250 diffuse with its reflection mask in alpha: the approved itemkit package's 2048 px RGBA TGA, 16,777,260 bytes, below GitHub's hard limit."} -->

The same change turns the published Ares
Predator IV, Colt L36 and Ingram Smartgun X models rigidly upright; nothing else of
theirs changes. Generation intermediates, local bindings, HAK archives, ledger
entries and client captures stay outside the repository. Shadowrun names and designs
are third-party marks; this record asserts no ownership of them and adds no new
rights claim.

## Head library: 40 client-reviewed heads (srn_head; 2026-11-18)

The SRN project operator selected 40 generated head designs, five per race and gender for Human, Elf, Dwarf and Orc.
ImageGen supplied appearance and paired clay references; Pixal supplied geometry and saved-shape appearance.
Headbatch/headkit performed fitting, repair, UVs, texture baking, PLT ownership/palette mapping, native compilation and
review. The user delegated operator reviews through the private NWN:EE client, made the geometry, budget and threshold
decisions quoted in the manifest, and authorized this publication.

Only the 40 MDL/PLT pairs listed in docs/heads/head-library-40-v1.md are added: the exact bytes each head's final client
session loaded. Resource and design hashes, submission counters, client sessions, gallery frame hashes, user-accepted
exceptions and limitations are in that document and its JSON manifest. The heads reference the game's built-in head
materials; stock material and palette payloads are not redistributed. Machine bindings, intermediate models, private
logs and generated HAKs remain outside the repository.

## Head library: 10 client-reviewed troll heads (srn_head; 2026-11-20)

The SRN project operator selected 10 generated Troll head designs, five male and five female.
ImageGen supplied appearance and paired clay references; Pixal supplied geometry and saved-shape appearance.
Headbatch/headkit performed fitting, repair, UVs, texture baking, PLT ownership/palette mapping, native compilation and
review. The user delegated operator reviews through the private NWN:EE client, made the geometry, budget and threshold
decisions quoted in the manifest, and authorized this publication.

Only the 10 MDL/PLT pairs listed in docs/heads/head-library-trolls-v1.md are added: the exact bytes each head's final
client session loaded. Resource and design hashes, client sessions, gallery frame hashes, user-accepted exceptions and
limitations are in that document and its JSON manifest. Machine bindings, intermediate models, private logs and generated
HAKs remain outside the repository.

## Modern Exterior restyle, release 1 (`srn_t_common`, `srn_t_dgt04`, `srn_door`, `srn_placeable`; 2026-11-19)

The textures D20 Modern Exterior (`dgt04`) draws are restyled in place for a 2070s Shadowrun city, under the plan in
`docs/tilesets/dgt04-upfit-plan.md`, and the look was passed by the SRN project operator in the game client on
2026-11-19 (review captures in ignored `output/tilekit/tkacc1` to `tkacc3`). Each of the 215 textures in
`docs/tilesets/dgt04/materials.json` keeps its name and is now a material file (`<name>.mtr`, normal and specular
mapped) with DDS colour, normal, specular and roughness maps (`<stem>`, `_n`, `_s`, `_r`), written by
`tools/tilekit` (SRN project operator with Claude); the canal water `tcn01_water01` is a plain DDS beside the
game's own TXI, so its moving water is kept. The old TGA and DDS copies of those names are deleted. Four names
other packs share keep a copy in each pack that held them: `dumpster`, `dumpster_sign` and `tmi_metal01` in
`srn_t_common` and `srn_placeable`, `manhole_tex2` in `srn_door` and `srn_placeable`.

Origins, by route:

- Master (43 textures): CC0 scans from [ambientCG](https://ambientcg.com/) (1K JPG), tinted, graded and stained:
  Asphalt033, Bricks032, Bricks073C, Bricks090, Bricks094, Bricks097, Concrete034, Concrete046, Concrete047A,
  CorrugatedSteel007A, CorrugatedSteel009, Gravel043, MetalPlates013, Planks023A, Road012A and Rust009. The fetched
  archives and their hashes are recorded in `tilekit/masters/fetched.json` of the shared tool root.
- Layout (56): the original D20 Modern picture's own layout kept, with the grain of one of those scans laid over it.
- Upscale (116): the original picture doubled by the upscaling model of the shared local ComfyUI, with a normal map
  derived from it. Of these, 90 were first redrawn on their own layout by an image generator (OpenAI image
  generation through the Codex CLI, or the local Qwen image edit model on the shared ComfyUI), from prompts in
  `docs/tilesets/dgt04/redraw.json`: signs carry generic 2070s wording and no brand names.
- Ten base-game textures (`tcn01_bark02`, `tcn01_barnicle02`, `tcn01_blst02`, `tcn01_bridge02`,
  `tcn01_splotch01`, `tcn01_stone18`, `tcn01_treefol02`, `tcn01_water01`, `ttr01_grass02`, `ttr01_wood03`) are
  derivatives of Neverwinter Nights: Enhanced Edition stock textures, layout unchanged, in `srn_t_dgt04`; they
  replace the stock look in any module that loads that pack. A licensed NWN:EE installation is required.

Model edits, to 434 D20 Modern tile models in `srn_t_common` and `srn_t_dgt04` (402 tiles of the set and 32 edge
tiles of `srn_2da/dgt04_edge.2da`; the upstream D20 Modern Haks 2.2 terms above apply): tile lamps on 152 models are moved from source lights, which the game draws as flames, to main
lights of radius 7 (`tilekit lamps`); small trims and flat panels cast no shadow, which the game drew as wedges on
the walls behind them (`tilekit shadows`). No walkmesh, texture name or geometry changes: all 589 walkmeshes (467 in ASCII models, 122 `.wok` files of compiled ones) hash
as `docs/tilesets/dgt04/walkmesh.json` records. Areas built with a tile's source lights on go dark at those 152
tiles until switched to main lights. Generation intermediates, scans, review captures and local bindings stay
outside the repository.

## Modern Exterior restyle, strata 4 and 5 (`srn_t_common`, `srn_t_dgt04`, `srn_2da`; 2026-11-19)

Two building terrains are added to D20 Modern Exterior (`dgt04`) as copies of existing ones, by `tools/tilekit`
(`terrain.py`, spec `docs/tilesets/dgt04/terrains.json`; SRN project operator with Claude), and the look was passed
by the SRN project operator in the game client on 2026-11-19 (review captures in ignored `output/tilekit/tkter1`,
`tkter2`):

- `Highrise_08`, Residential Block: the six `Highrise_05` tile models `dgt04_e09_50`, `dgt04_e11_10`,
  `dgt04_e10_07`, `dgt04_e12_07`, `dgt05_h41_01` and `dgt05_h46_01` copied as `srt04_r01_01` to `srt04_r06_01`,
  with the roof-access group `Highrise8_RoofAccess`.
- `Highrise_09`, Derelict Tower: the six `Highrise_02` tile models `dgt04_e05_01`, `dgt04_e08_01`, `dgt04_e06_01`,
  `dgt04_e07_01`, `dgt05_h11_01` and `dgt05_h10_01` copied as `srt04_x01_01` to `srt04_x06_01`.

The copies are derivatives of the upstream D20 Modern models (the D20 Modern Haks 2.2 terms above apply): node
names and texture names are renamed, geometry, door hooks and minimap images are the source tiles' own, and each
walkmesh is the source's unchanged (`docs/tilesets/dgt04/walkmesh.json` now holds 603 entries; the 589 earlier ones
are unchanged). The models and walkmeshes are in `srn_t_dgt04`; `dgt04.set` gains tiles 556-567 and group 68 after
every earlier entry, so tile and group numbers of existing areas do not move; `srn_2da/dgt04_edge.2da` gains ten
rows; `dgt04palstd.itp` gains their entries.

Each copy also gets its own edge tile, laid outside an area's border next to Concrete, so the border shows the
copy's textures and not its source's: `dgt05_z08_01` copied as `srt04_r07_01` for `Highrise_08` and `dgt05_z06_01`
as `srt04_x07_01` for `Highrise_09` (the `edges` of each copy in `terrains.json`; textures renamed as for the tiles,
neither has a walkmesh). Edge rows 132 and 137 name them in place of the source models. Border views in the client
(ignored `output/tilekit/tkedg0` to `tkedg3`, spec `docs/tilesets/dgt04/edges-review.json`) showed no visible
difference; the SRN project operator approved applying them on 2026-11-19.

Their twelve textures (`hr08_*` and `hr09_*`, spec `docs/tilesets/dgt04/materials-terrains.json`) are made as in
release 1, from the pictures of the textures they copy. `hr08_wall`, `hr08_wall_g`, `hr09_build` and `hr09_win08`
were redrawn by the local Qwen image edit model on the shared ComfyUI, from prompts in
`docs/tilesets/dgt04/redraw-terrains.json` (curtained, balconied flats; broken and boarded windows). The others
reuse release 1's work for their source, or take the CC0 ambientCG scans listed above (Concrete034, Concrete047A,
Gravel043).

The palette's display names of the building terrains become descriptive ("Office Block, Concrete", "Tenement,
Brick", "Warehouse, Metal Siding" and so on, in `terrains.json`); terrain names in the set and edge table are
unchanged.

Stratum 5 evens wear across families: `concrete_07` and `concrete_08` take stain 0.3, `lab_wall02` and `lab_wall05`
stain 0.2, and `lab_floor01` the street grade (`docs/tilesets/dgt04/materials.json`).

## Dynamic skies: Denver, its acid storm, Awakened peaks (`srn_skybox`, `srn_2da`; 2026-11-19)

Eight new skybox rows (16 `SRN_Denver_Dynamic`, 17 `SRN_Sprawl_AcidStorm`, 18 `SRN_Denver_Dusk_Fixed`, 19
`SRN_Denver_Night_Fixed`, 20 `SRN_Awakened_Peaks`, 21 `SRN_Awakened_Aurora`, 22 `SRN_Denver_Day_Fixed`, 23
`SRN_Awakened_Day_Fixed`) are appended to `skyboxes.2da`; no
existing row changes. `srn_skybox` gains nine sky dome models (`srn_sky{den,pk}_*.mdl`,
ASCII, written by `tools/skykit`), their materials and fallback pictures, two land panoramas in two halves with two
light masks each (`srn_sky*_pa/_pb/_ma/_mb.dds`) and the fragment shader with its include (`srn_sky_fs.shd`,
`srn_sky_math.shd`). The vertex shader is the game's own `vsvt`, referenced and not copied; the fragment shader
includes the game's `inc_standard` by name.

Origin: the pictures are under `tools/skykit/art/`, prompts beside them. Denver's start view (`denver/view_w.png`)
was drawn for the SRN project operator with the Codex CLI's image generation from the Denver skyline concept the
operator supplied; Denver's four extensions and closing join (the acid storm row shares Denver's skyline), and the peaks views and
joins, were drawn with the local Qwen-Image 2.1 profile (`qwen21-int8-v1`) on the operator's shared ComfyUI, the
peaks views as edits of that start view. Denver's land was then redrawn at about 2.8 times in 14 overlapping detail tiles with the same Qwen profile
(`art/denver/detail/`), and the peaks land at about 2x in 10 (`art/peaks/detail/`). Their face normals were estimated with MoGe-2 (`moge_2_vitl_normal_fp16`) on that ComfyUI. The sky, clouds, stars, moon, aurora, lightning,
searchlights and rain are procedural, written for this project (SRN project operator with Claude); the approach of a
material-driven animated sky in a skybox model follows the community Dynamic Skies example by Bhaal in its general
method only: no code, models or pictures of it are included.

## Universal door set (`srn_door`, `srn_2da`; 2026-11-20)

Ten generic doors are original work built in code by `tools/tilekit/doorset.py` (SRN project operator with Claude):
`srn_dr_street`, `srn_dr_shop`, `srn_dr_double`, `srn_dr_steel`, `srn_dr_shut2`, `srn_dr_shut4`, `srn_dr_load`,
`srn_dr_gate`, `srn_dr_inner` and `srn_dr_strip`, each with its walkmesh (`.dwk`), and their shared material
`srn_doors` (`.mtr` and four maps). Node layout and animation names follow the pack's own doors' structure; no
geometry or picture of another door is used. The atlas is flat colours made in code, except the `iron` cell, which
takes the CC0 ambientCG scan MetalPlates013 listed under release 1. `srn_2da/genericdoors.2da` rows 1094-1103,
empty until now, name them. The SRN project operator passed the look in the game client on 2026-11-20 (review
captures in ignored `output/tilekit/doorset-review` and `doorset-review2`).

## Modern Exterior restyle, release 2, stage 4 (remeshing) (`srn_t_dgt04`, `srn_2da`; 2026-11-20)

`Highrise_10`, "Walled Compound, Glass, Crowned", is a crowned copy of `Highrise_07` added to D20 Modern Exterior
(`dgt04`) by `tools/tilekit` (`terrain.py`, `crown.py`, `remesh.py --add --joins`; spec
`docs/tilesets/dgt04/terrains-crowned.json`; SRN project operator with Claude). Its seven tiles 568-574
(`srt04_c01_01` to `srt04_c07_01`) and its edge tile `srt04_c08_01` copy `Highrise_07`'s tiles, as the copies of
strata 4 and 5 do, and the D20 Modern Haks 2.2 terms above apply to them. Each tile keeps its source's meshes, door
hooks, lamps and walkmesh, and gains a crown made in code: a parapet, coping and cornice on each facade, and a
grating screen with steel posts and a lit band 1 m behind it. The crown draws the release 2 kit atlas
(`dgt04_kit`); no picture is new. `dgt04.set` gains terrain 24, tiles 568-574 and their rules after every earlier
entry, so existing areas do not move; `srn_2da/dgt04_edge.2da` and `dgt04palstd.itp` gain their entries. The SRN
project operator passed the look in the game client on 2026-11-20 (review captures in ignored
`output/tilekit/crown-review3` and `crown-review4`).

## Modern Exterior restyle, release 2 finish (`srn_t_dgt04`; 2026-11-20)

- `hr08_trim`, `hr09_build_g` and `hr09_win08_g` are redrawn with records. Their release 1 pictures had been placed
  by hand with none.
  - `hr08_trim` is drawn by the local Qwen image edit model on the operator's shared ComfyUI (seed 2), from release
    1's `hrise_05_trim`. The prompt is in `docs/tilesets/dgt04/redraw-terrains.json`.
  - The two derelict lit variants are composed in code by `tools/tilekit/redraw.py` from their redrawn day pictures:
    a share of whole windows lit warm where the day picture is dark (`keep`).
  - Records: ignored `output/tilekit/redrawn-terrains`. Client check: `output/tilekit/redraw3-review`.
- The jamb door hooks of tiles 359, 361 and 560 in `dgt04.set` are turned 90°. Each hook stood in its doorway's
  frame but laid the door beside the opening; turned, the door fills it (client check
  `output/tilekit/jamb-review2`).

## Compiled tile models with ASCII sources (`srn_t_common`, `srn_t_dgt04`, `sources/`; 2026-11-20)

- The 500 ASCII tile models of `srn_t_common` and `srn_t_dgt04` moved, byte for byte, to `sources/<pack>/`. The packs
  now hold binaries that NeverBlender (cleanmodels port, run headless in Blender) compiled from them, through
  `tools/tilekit/compiled.py`. The SRN project operator asked for compiled models in the packs and ASCII kept in the
  repository.
- `sources/compiled.json` pins each pair by SHA-256, with its audit. The provenance and terms of each model are those
  recorded above for it; compiling changes its form, not its content.
- Three sources were repaired, as `sources/README.md` records: `dgt04_e09_21`, `dgt05_a00_01` and `dgt05_a01_01`.
  Their emitter animations had unclosed nodes and a spaced-out `endlist`.
- Client checks on 2026-11-20:
  - the review block, by day and night, matched the packed ASCII (`output/tilekit/compiled-look`);
  - the three repaired tiles matched (`output/tilekit/emit121-fix`, `emit-fix`).

## Unified city tileset `srx01` (`srn_t_srx01`, `srn_2da`, `srn_placeable`; 2026-11-21)

- `srn_t_srx01/srx01.set`, `srx01palstd.itp` and `srn_2da/srx01_edge.2da` are written by `tools/tilekit/merge.py` from
  the set files and edge tables of `srn_t_dgt04` (D20 Modern Exterior), `srn_t_udp1` (D20 Suburbs UDP) and
  `srn_t_fcx01` (D20 Futuristic City SW), under the names in `docs/tilesets/srx01/names.json`. They hold no model,
  texture or picture: every tile draws the source packs' own files, whose provenance and terms are recorded above.
  The names, the palette layout and the generated rules between the three sets are original work of the SRN project
  operator with Claude; the operator approved the names on 2026-11-21. `docs/tilesets/srx01/merged.json` pins what
  each merge read and wrote.
- The join tiles `srn_t_srx01/srx01_j*.mdl` (sources in `sources/srn_t_srx01/`), their walkmeshes and `mi_srx01_j*.tga`
  minimaps are written by `tools/tilekit/joins.py` (`docs/tilesets/srx01/joins.json`): each is cut from the plain
  ground and straight road tiles of the three source packs above (their geometry, texture coordinates and minimap
  pictures, clipped to each side of the boundary), with a boundary strip drawn from the `dgt04_kit` atlas. They hold
  no new texture. The cutting, the boundary shapes and the strip are original work of the SRN project operator with
  Claude. `docs/tilesets/srx01/joins-built.json` pins what a build read and wrote; the models are compiled as the
  other tile packs' are (`sources/compiled.json`).
- `srn_placeable/placeablepal.itp` gains the category Shadowrun City and eleven kinds under it; the 149 envkit
  blueprints (`ek_*.utp`) move there and `placeablepalstd.itp` is rebuilt by `envkit blueprints`. Only their palette
  category changes.
- `srn_2da/doortypes.2da` rows 266-268 are copies of rows 117, 260 and 261 keyed to SRX01 (same models and names), so
  the Toolset knows those door types in the merged set.
- `srn_2da/genericdoors.2da` rows 1094-1103 take a name each from the talk table (rows 156-165).
- `srn_t_common/pavement` (the Concrete ground of `dgt04` and `srx01`; maps `pavement.dds`, `pavement_n.dds`,
  `pavement_r.dds`) is made again from the CC0 scan
  [cracked_concrete](https://polyhaven.com/a/cracked_concrete) by Dimitrios Savva, Poly Haven (1K JPG: colour,
  normal, roughness), desaturated and graded to the sidewalk's brightness by `tilekit material`
  (`docs/tilesets/dgt04/materials.json`, grade `ground`; user, 2026-11-23). It replaces the ambientCG Road012A
  asphalt it was made from before. The fetched files and their hashes are in `tilekit/masters/fetched.json` of the
  shared tool root, under `CrackedConcrete`.

## Suburbs restyle, release B (`srn_t_udp1`, `srn_t_common`, `srn_door`, `srn_placeable`; 2026-11-24)

The D20 Suburbs tiles (`udp1`, and through them the unified `srx01`) keep their own pictures: 99 textures of
`docs/tilesets/udp1/materials.json` are the originals graded by `tilekit material`, each with a relief and a
roughness map made from the picture itself. Twelve take detail from the CC0 ambientCG scans listed under Modern
Exterior release 1: the road and parking pictures (Asphalt033), the walks (Concrete047A), the red brick
(Bricks097) and the grey metal (MetalPlates013). No other outside material was added. The five scans fetched
and tried on 2026-11-23 (Grass008, WoodSiding009, PaintedBricks004, RoofingTiles003 of ambientCG; brown_planks_03
of Poly Haven) are in no pack: the user kept the originals.

The tile models are the originals, compiled by NeverBlender from `sources/srn_t_udp1/` (node names made unique by
`tilekit unique`), with day and night animations for their lit windows and lamp lenses (`tilekit daylight`) and
the shadows of one-plane meshes turned off (`tilekit shadows`). Walkmeshes are unchanged.

## Unified interior tileset `srx02` (`srn_t_srx02`, `srn_2da`, `srn_t_nac01`; 2026-11-24)

- `srn_t_srx02/srx02.set`, `srx02palstd.itp` and `srn_2da/srx02_edge.2da` are written by `tools/tilekit/merge.py` from
  the set files of `srn_t_udp2` (D20 Office Interiors UDP), `srn_t_tfb01` (D20 Modern Interior), `srn_t_tbx78` (D20
  Modern Facility) and `srn_t_nac01` (D20 ServiceDucts) and the edge tables of the first and third, under the names in
  `docs/tilesets/srx02/names.json`. They hold no model, texture or picture: every tile draws the source packs' own
  files, whose provenance and terms are recorded above. The names, the palette layout and the generated rules between
  the four sets are original work of the SRN project operator with Claude; the operator approved the names on
  2026-11-24. `docs/tilesets/srx02/merged.json` pins what each merge read and wrote.
- `srn_2da/doortypes.2da` rows 269-273 are copies of the base game's rows 24, 42, 43, 54 and 146 keyed to `SRX02`.
- `srn_t_nac01/nac01.set`: one door hook's `X==-4.75` corrected to `X=-4.75` (a typing error of the source).
