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

Not checked: any of the 2026-11-12 work in the client or the Toolset (the user put client runs on hold): the
corrected door records as read from the packs; the fence sheets, by day and by night, which are the first
tile parts here to show a picture with an alpha channel and no material file; and the hidden top with the
setting on "near the character".

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
for their lit parts, eight of those a halo sheet as well, and a lights-out material (`<name>_o`) as
`docs/envkit/lights.md` describes; their blueprints are not static, so that a script can reach them. Three
props were retouched after the first client check. The turret came back with its barrel along the model's side
and is turned a quarter turn, so that it points to the front. The rooftop unit's colour is multiplied by 0.8:
it matched its own pale reference and stood out nearly white beside the others by day. Meshy made the fence's
chain-link mesh two solid smeared panels; its posts, rails, barbed wire and concrete base are kept, and the two
panels are redrawn by place on the model as a diamond mesh of 16 millimetre wire 90 millimetres apart, seen
through between the wires (the colour map of this one prop has an alpha channel, DXT5), with the relief map
levelled there. The right half of its concrete base still carries a smeared hazard marking.

Checked in the game client on 2026-11-11: by day and by night with their lights on, from the converted files
that were copied into the pack; the fence, turret and rooftop unit again by day after their retouching, from
front, back and side, with a figure behind the fence seen through its mesh from both faces; and by night from
the pack's files, where `ReplaceObjectTexture` put the lights of all ten lit props out and brought them back.
Checked in the Toolset the same day, from the built packs: the Standard tab lists the fifteen blueprints under
their Modern Exterior and Modern Interior categories, and a painted fence section and turret were saved with
their rows and names, the fence static and the turret not.

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
