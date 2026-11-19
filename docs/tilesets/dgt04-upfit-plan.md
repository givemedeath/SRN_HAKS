# Modern Exterior (`dgt04`) Shadowrun upfit — plan

Status: revision 3, 2026-11-18. Release 1 (materials, lamps, shadows) passed the user's look gate and is in the
packs, 2026-11-19; see "Release 1 in the packs". Strata 4 and 5 are not started.

Source: `SR_NWN_Modern_Exterior_Upfit_Plan_Complete.zip` (revision 1.1, 2026-11-18), reviewed against this
repository. The package's art direction and its insistence on in-game proof stand. Its inventory, packaging and
schedule do not, for the reasons in "Corrections to the package". Where the two differ, this file is the plan.

Revision 2 re-measured every figure from the repository, added the edge tiles, measured surface coverage per
texture, replaced the texture-size figures (revision 1 had read only the TGA copies), and added desk time.
Revision 3 adds the authoring routes and time savers and redoes the desk-time table.

## Decisions (user, 2026-11-18)

| Topic | Decision |
|---|---|
| Packaging | Replace in place in `srn_t_common`, `srn_t_dgt04`, `srn_door`. No override pack. Git history is the rollback. |
| File form | Each restyled texture ships as one material file plus DDS maps. Its old TGA and DDS copies are deleted. |
| Texture authoring | Hybrid, by three routes. Tiling surfaces are derived from about a dozen master materials built from CC0 scans. Layout-bound textures that already read right are upscaled with a derived normal map. Only what looks dated is regenerated. Highrise facades are composed on their original window grid. |
| Detail level | Standard: 1024 px with normal maps for the 42 textures that cover 80% of the surface, 512 px for the next 43, the remainder near its current size. About +130 MB. |
| Geometry | Release 1 is materials only on every original tile. Detail kit and remeshing are release 2. |
| Districts | Highrise 01–03 and 05–07 corporate and maintained; `Highrise_04` stays the collapsed ruin it already is; Slums 1–3 Barrens; Apartments mixed; Warehouses industrial. |
| New terrains | Two, copied from existing highrises: mid-tier residential from `Highrise_05`, derelict but standing from `Highrise_02`. |
| Terrain names | Descriptive names for the two new terrains, and the existing numbered ones renamed to match. Names are proposed with in-game pictures in the highrise batch. |
| Shared textures | New look everywhere: Futuristic City, `udp1` and placeables that name a restyled texture take it too. Checked in game at the end. |
| Base-game textures | The stock textures the tiles draw (ten) are upscaled and given materials with their layout unchanged, so every stock model that uses them still fits. |
| Prototypes | The earlier Highrise V2 and Slums V4 work is reference only. |
| Baked signs | Redrawn as generic 2070s signs with no brand names. |
| Doors | The six textures doors share with the tiles, plus the door types that suit building entrances. Interior-style doors and all placeables are follow-ups. |
| Reviews | User approves the pilot, then one day-and-night contact sheet per batch. Ruin, Apartments, Warehouses and civic buildings are one batch. |
| Time savers | The five in "Authoring routes and time savers" (user, 2026-11-18). Parallel sessions and deferring scope were offered and not taken. |
| Release | Each phase is a pull request into a restyle branch; `main` gets one merge when the tileset is consistent. |

## Verified baseline (this repository, 2026-11-18)

| Fact | Value |
|---|---|
| `dgt04.set` | 22 terrains, 14 crossers, 556 tiles (555 models), 68 groups |
| Edge tiles (`srn_2da/dgt04_edge.2da`) | 129 rows naming 60 models; 43 are not in the set. Nine of those are in no pack: three are base-game (`tcn01_z*`), six are absent upstream (8 rows; known, `docs/imports/mdrnee_tile-deferred-work.md`) |
| Tracked inventory | `docs/tilesets/dgt04/` (`inventory.json`, `textures.csv`, `walkmesh.json`), written by `python -m tools.tilekit inventory --tileset dgt04 --out docs/tilesets/dgt04` |
| Models in scope | 467 ASCII: 433 set tiles (428 original + 5 arcology `srt04_*`) and 34 edge tiles |
| Envkit tiles (`ek_*`) | 122 compiled models with their own materials; out of scope, and the look to match |
| Textures on rendered faces | 224, over about 224,000 m² of surface |
| Coverage | 14 textures cover 50% of the surface, 42 cover 80%, 65 cover 90%, 85 cover 95%; the last 139 cover 5% |
| Largest by surface | `brick_tex19` 6.5%, `brick7` 6.0%, `concrete_08` 4.8%, `hrise_06_wall2` 4.1%, `sidewalk10` 3.8%, `concrete_10` 3.4% |
| Current size (larger copy) | 512 px: 87 textures, 55% of surface. 256 px: 70, 25%. 128 px or less: 40, 12%. 1024 px: 17, 4% |
| TGA and DDS copies | 210 textures have both; the DDS is larger for 131, the same for 78, smaller for 1 |
| Named by another tileset | 15: Futuristic City `fcx01` 13, `shp02` 5, `udp1` 4, `net01` 1, `vmp01` 1 (includes `pavement`, `glass`) |
| Named by other packs' models | about 30 by `srn_placeable` models, 6 by `srn_door` models |
| Held in `srn_door`, not the tile packs | `glass`, `dgt04_chrome`, `lab_win1`, `manhole_tex2`, `arcology_win02` |
| Base-game textures | 10 on rendered faces, about 3% of surface (`tcn01_water01` alone 2.5%); `obscuring` and `stone` are named but not drawn |
| Existing materials on original tiles | none (all 57 `.mtr` files belong to envkit buildings) |
| Building terrains | each borders only Concrete and has 6 or 8 edge-table rows. Highrises are 6–10 tiles; Slums 30–44; Apartments 18; Warehouses 9–10; Police 8; Hospital 15; Lab 7 |
| Toolset palette | holds a display name beside each resource name, so what builders read can change apart from the names in the set |

## Corrections to the package

1. **The inventory is of an older build.** It counts 429 tiles and 52 groups; the repository has 556 and 68. It
   also omits the edge tiles, which the edge table names and the set does not.
2. **"235 TXI" is wrong.** The package's reader appears to have mislabelled resource types: `srn_t_dgt04` holds
   31 DDS files and no TXI, matching its 31 "TXI". The original tiles have almost no TXI behaviour to preserve.
3. **None of the 15 "missing" textures is missing.** Four are in `srn_door`, `chainlink_fence` is DDS-only in
   `srn_t_common` (the scan looked for TGA), ten are base-game.
4. **A separate override HAK is the wrong shape here.** This repository is the source of both packs, most
   textures exist as two copies of different sizes, and same-name files in `srn_placeable` and `srn_door`
   already depend on pack order.
5. **`SR_NWN/assets/tilesets/…` and new build scripts are not needed.** The pack build, repository checks, DDS
   conversion, material writer, Toolset module preparation and client capture already exist here (envkit).
6. **Licence is recorded, not open.** `NOTICE.md` and `PROVENANCE.md` hold the D20 Modern Haks 2.2 permission.
   New entries are needed for each CC0 source, each generated texture, and the upscaled base-game textures
   (stock derivatives, as for the stock armour: a licensed NWN:EE installation is required).
7. **`Highrise_04` is not corporate.** It is a destroyed building.
8. **Sixth World identity largely exists** in the envkit groups already in the palette.
9. **Night windows are separate glow textures** (`hrise_05_wall_g`, `hrise_06_wall2_g`, `win001_unbrknn`).
   `hrise_06_wall2_g` alone is 3.4% of the surface. Each new facade needs its lit layer redrawn to match.
10. **The material mechanism is documented, not speculative.** nwn.wiki: a model's `bitmap` name is looked up
    as a material file, a material file takes precedence over DDS, PLT and TGA images of that name, and its
    render hint makes the game build tangents for models that are not compiled. All 467 models are ASCII.
11. **The schedule is dropped** in favour of gated batches with measured desk time (below).
12. **"No new terrain types" and "no terrain renames" no longer hold**, by decision.

## Constraints

- No walkmesh changes. Every original `.wok` and every `aabb` node hashes the same before and after.
- No existing tile number, crosser name or group moves in `dgt04.set`. New tiles are appended after 555.
- Release 1 edits no original model. A restyled texture keeps its name; the material file carries the change.
  One exception (user, 2026-11-18): lamp light nodes, see "Tile lamps" below. No geometry, texture name or walkmesh changes.
- A restyled texture is one material file and its DDS maps in one pack. No older copy of that name remains in
  any pack unless recorded as a decision. No file over 15 MiB without a size exception in PROVENANCE.md.
- A base-game texture keeps its layout exactly, and any stock TXI behaviour (water above all) is shown to
  survive before the texture is accepted.
- No crack, stain or patch on a tiling texture large enough to read as a repeat across four adjacent tiles.
- Ground and road materials carry no baked lighting direction: tiles are placed in four rotations.
- Acceptance is the Toolset and the game client, day and night. Preview renders accept nothing.

## Tile lamps (user decision, 2026-11-18)

The game draws a flame and a warm flicker at every *source* light a tile switches on; removing the models' flare
settings changes nothing (client captures `tkl1`, `tkl2`). A *main* light is a plain steady light. Adopted: the lamps
of tiles that have source lights and no main light are renamed from `sl1`/`sl2` to `ml1`/`ml2` and given radius 7.0
(`tilekit lamps --tileset dgt04 --out <overlay>`; capture `tkl3` shows steady cool-white pools and no flame).

- 152 tile models are changed (60 in `srn_t_dgt04`, 92 in `srn_t_common`, none used by another tileset). The command
  refuses a model whose walkmesh would change.
- 58 tiles that already have a main light are left alone; their lamps still burn as torches when their source lights
  are on. Left as they are (user, 2026-11-18).
- Builders switch these lamps on with the tile's main-light setting. An area built with source lights on goes dark at
  those tiles until it is changed; this belongs in the release notes.
- Not checked: other radii, and light colours other than white.
- Like the textures, the models stay in the review overlay until the look gate.
- Small trims cast no shadow (user, 2026-11-18): the game draws a sill's or ledge's shadow on the wall behind it as
  hard wedges, which show as triangles once a wall's picture is even. `tilekit shadows --tileset dgt04 --out <overlay>`  sets
  `shadow 0` on meshes under 2 m across their second side or 2 m long, and on flat panels of any size (shortest side
  under 0.1 m; a facade sheet or plinth face throws wedges on what is behind it). Closed building meshes keep their
  shadows (2026-11-19: 1,560 more meshes in 366 models over the first 0.75 m / 1 m rule; no wedges left in the
  block's 17 day views).
- Base-game textures (2026-11-19) come from a stock folder extracted from the game (`--stock`). The canal water keeps
  its procedural TXI: its DDS is written plain, with no mtr, and the stock TXI copied beside it. `slumbrd2` stays on
  the upscale route: Qwen copied its old posters twice.
- Night is left dark (user, 2026-11-18): brightness at night is a matter of an area's own lighting and its tile lamps,
  not of the textures.

## Release 1 in the packs (2026-11-19)

The user passed the look on the client acceptance capture (`tkacc1` block by day, overcast and night; `tkacc2` every
tile by day; `tkacc3` lamps at night) and asked for it to be applied. `python -B -m tools.tilekit apply --spec
docs/tilesets/dgt04/materials.json --overlay output/tilekit/ground/overlay10` moved it in:

- 215 textures as material files and DDS maps, in the pack that held each name (`srn_t_common` 1,105 files,
  `srn_t_dgt04` 359); the ten base-game textures in `srn_t_dgt04`. 239 old TGA and DDS copies deleted.
- `dumpster`, `dumpster_sign`, `tmi_metal01` (`srn_t_common` and `srn_placeable`) and `manhole_tex2` (`srn_door` and
  `srn_placeable`) keep a copy in both packs, as before; their maps and materials are expected overrides.
- 397 tile models with the lamp and shadow changes replace their pack copies. All 467 walkmeshes hash as the baseline. The baseline holds the `.wok` hashes of the 122 compiled models
  too (2026-11-19; no `.wok` file changed in the release), 589 in all.
- Edge tiles (user, 2026-11-19): the 31 edge-table models drawn round an area's border take the same shadow rule (388
  trims and panels; none has a source-light lamp). Looked at on an area with twelve buildings against its borders
  (`tke1` before, `tke2` after, `tke3` on the built packs) and passed; in the packs the same day.
- Meshes with no shadow line (user, 2026-11-19): 26 meshes the rule picks but which stated no shadow (the game's
  default is on) now state `shadow 0`, in the five arcology tiles `srt04_a02_01`, `a02_02`, `a04_01`, `a05_01`,
  `a05_02` and the edge tile `dgt04_z09_01` (overlay12). The arcology tiles were looked at before and after
  (`tka1`, `tka2`, grid view r13-c12) and passed; the edge tile is in no review area and was not shown. That makes
  434 changed models: 402 set tiles and 32 edge tiles.
- Old TXIs of restyled names are kept (`window_tex07` reflection, `checks` one-frame cycle): they were in place for
  the look the user passed.
- Checked on the built packs with no overlay (`tkrel1`): the views match the passed overlay views (mean difference
  0.0 by day). The canal water renders pixel for pixel as the stock water did (`tkbase1` against `tkrel2`), so its
  procedure still applies; motion itself is not shown by stills.
- Toolset (2026-11-19, by computer use on the built packs, user folder in ignored `output/tilekit/tkts1`): the review
  module opens and its block draws with the restyled textures, from above and tilted, with no missing or black
  texture. Screenshots are beside it. Painting was not tried: release 1 changes no tile, terrain or group.
- Not done: the other tilesets and placeables that name restyled textures (stratum 5).

For builders (release notes): tiles whose lamps were source lights now light them as main lights. An area built with
a tile's source lights on goes dark at those 152 tiles until its main lights are switched on in Tile Properties. The
58 tiles that already had main lights are unchanged, and their lamps still burn as torches with source lights on.
`slumbrd2` keeps its upscaled old posters: two redraws copied them.

## Authoring routes and time savers

Every texture takes one of four routes. The pilot fixes which route each family takes.

| Route | For | How | Unit time (assumed) |
|---|---|---|---|
| Master | Tiling surfaces: the 13 concretes, the bricks, asphalt, pavement, gravel, metal | About a dozen masters from CC0 scans with their own normal and roughness maps. Each named texture is a master with its own tint and wear, written by the build tool | 30–45 min per master, 2–3 min per derived texture |
| Upscale | Layout-bound textures that already read right: windows, trims, some facades, base-game textures | 2× upscale, layout unchanged, normal map derived from the result | 5–10 min |
| Compose | Highrise facades | Window grid read from the original; glass, frame and panel materials laid on the same grid; the night glow layer cut from the same mask | 15 min after a one-time grid tool |
| Regenerate | What looks dated after upscaling: signs, some doors and shopfronts | Generated image conditioned on the original layout | 30–45 min with retries |

Three further savers: the ruin, Apartments, Warehouses and civic buildings are reviewed as one batch; every
batch is captured in one client start; and review uses the D20 Modern project's own outdoor test area
(`moderntestoutsid`, kept in SR_NWN's old module assets; SR_NWN has built no Modern Exterior area of its own),
a plain grid of every tile, and one block painted in the Toolset, with no program that paints terrains.

A master that repeats visibly across a wide area gets a second variant. A family whose upscale does not hold
beside the envkit building moves to Regenerate; that is a pilot finding, not a failure.

## Work order

Work runs in coverage order inside each phase, so the surface players see most is done first. The 139
textures that cover the last 5% are handled by rule (resized, tone-matched, given a plain material), not
authored one at a time; any that then stands out is promoted.

### 0 — Inventory tool, review area, confirmations

- The audit that produced the baseline above, kept as a tool with tests: texture → models → tiles → terrains,
  surface per texture, copies and sizes in every pack, other users of each name, walkmesh hashes, and models
  in the tile packs that nothing names.
- Review set with fixed camera positions, on envkit's Toolset module preparation and client capture:
  the `moderntestoutsid` area (first shown to open and look right against the current packs), a plain grid
  of every tile and edge tile, and one block painted in the Toolset. Baseline pictures by day, night and
  overcast.
- Confirmations in the client on `sidewalk10`, `brick_tex19` and `hrise_05_wall`: the material file is picked
  up with no model edit; the normal map is right on all four rotations and on mirrored UVs; the night glow
  layer still shows over it. Also recorded: which of the TGA and DDS copies the client shows today, since that
  is what "before" means for 131 textures.
- Unit times recorded from here on.
- **Gate:** confirmations pass, or the mechanism changes before any authoring.

**Result (2026-11-18): gate passed.** Tools: `tools/tilekit` (`inventory`, `walkmesh`, `review`). Review spec:
`docs/tilesets/dgt04/review.json`.

- Baseline: 270 views of the packs at commit `a0522e84` (block of 16 building terrains by day, overcast and
  night; every tile by day; `moderntestoutsid` by day, overcast and night), none captured late, 29 minutes in
  the client (6.5 s a view). Pictures and contact sheets are in the ignored `output/tilekit/tkbase1`; they are
  made again from that commit with `python -B -m tools.tilekit review --spec docs/tilesets/dgt04/review.json
  --game <game> --built <built packs> --out <folder> --name <name> --area <moderntestoutsid.are>`.
- Review lighting is envkit's check lighting (day ambient 176 grey, sun 238; night as envkit's prop night),
  with overcast between. The game's own "Exterior, Clear" numbers left these areas lit by the ambient light
  alone and too dark to judge a texture by. The sun in such an area stands low in the south, so the ground gets
  little direct light: a ground material is read by its colour and glow far more than by its normal map.
- Material file: a `.mtr` named like the texture is picked up on tile models with no model edit, on all three
  textures, over both the TGA and the DDS copy in the pack below.
- Normal map: a lattice of raised domes on `sidewalk10` is lit on the same (sun) side on the four turned
  corner tiles and the straight tiles round a crossing. Mirrored UVs were not singled out; a mirrored face
  would show at the pilot as a reversed dome and is checked there on the brick and facade textures.
- Glow: an illumination map (`texture5`) on the same material shows at full brightness at night on the ground
  and on the `hrise_05_wall` facade, with the normal map in place.
- TGA or DDS: with both copies of a name in one pack the client shows the DDS; a TGA in a pack above does
  **not** beat a DDS in a pack below (`roof_gravel1` stayed as it was). So "before" is the DDS copy for all 131
  textures that have one, and replacing a texture means removing or replacing its DDS, as already decided.
- A DDS needs its whole mip chain: one written with the top level alone drew as black with speckles at any
  distance. The material build tool writes mips with envkit's writer and checks for them.
- Framing to improve before the pilot review: two of the sixteen block views look into a roof or a wall, and
  the every-tile views are crowded. Neither is fixed yet: the views change first (spec and view code), then
  the baseline is captured again from the commit above.
- Time: under two hours against 6–9 estimated. Unit times so far: tool with tests 15–30 minutes; client
  capture 6.5 s a view plus about a minute to build and load (a 50-view check is 6 minutes, the full set 30).

### 1 — Material standard and pilot block

- A material build tool on envkit's texture and material writer: source image and maps in, DDS set and
  material file out, old copies removed, PROVENANCE row written.
- The first masters (brick, concrete, asphalt, pavement, gravel, metal) and about fifteen textures from the
  top of the coverage list, covering every route: two bricks, two concretes, sidewalk, asphalt, pavement and
  roof gravel from masters; one corporate facade composed with its glow layer; Slums windows day and night,
  door trim and street lamp upscaled; one sign regenerated.
- One block: a corporate highrise, a Slums building, a street with an intersection, a warehouse, beside a
  Stuffer Shack.
- **Gate (user):** the look by day and night beside the envkit building. This fixes the standard and the
  route each family takes.

**State (2026-11-18): pilot shown, gate not held.** Tool: `tilekit material` (routes `master`, `layout`,
`upscale`; district grades; DDS maps and material file) and `tilekit enlarge` (a texture doubled by the shared
ComfyUI's upscaling model before an upscale). Spec: `docs/tilesets/dgt04/materials.json`. Nothing is in the
packs: every picture so far was shown through `tilekit review --overlay`.

- Nine CC0 scans from ambientCG (1K) are the masters, in `tilekit/masters` of the shared tool root with the
  record of what was fetched. Old brick textures had oversized bricks; a scan at one repeat gives a real course.
- The game takes the first row of a DDS for the bottom of the picture. Every map is stored turned over; before
  that, lit window patterns came out upside down.
- A lit (`_g`) facade keeps its alpha and takes no glow map: one blew its windows white.
- Ground and concrete change little at play distance under the review light; the look comes from the district
  grade. The user asked for a grade per district and then a stronger one (corporate cool and dark, barrens warm
  and dark, lit windows cool except in the barrens, which stay warm).
- Windows need the upscaling model, not a resize (user). The model draws frames and lettering clean and smooths
  fine grain (blind slats, grime). A 64-pixel window gains only a sharper frame and is a candidate to redraw.
- Normal maps: a master's is the scan's own; a layout's is the scan's with guessed edges; an upscale's is guessed
  from the picture and kept weak; a by-rule texture's is flat.
- Not done: the regenerated sign, the look beside an envkit building, mirrored-UV check, and the in-game look
  at the upscaled windows and warm lit windows (client starts were put on hold by the user, who then asked for
  the next stratum without waiting for client reviews). Unit times: a master texture 2 minutes once its scan is
  chosen; a by-rule texture seconds; the upscaling model 5–10 s a doubling; a 64-view capture 8 minutes.

### 2 — Ground, streets and infrastructure

Roads, sidewalks, curbs, crossers, Freeway, Green_Bridge, Aqueduct, Water edges, Cliff, edge tiles. Checked on
a grid of straight, corner, T, four-way, ramp and transition tiles in all rotations. **Gate:** no new seam at
any join; road against sidewalk still reads at night.

**State (2026-11-18): authored, not seen in the game.** Forty textures added to the spec (the six ground
textures of the pilot were there already): every asphalt road and street on the one asphalt scan at the one
repeat, so their grain meets at a join; concretes and barriers from the three concrete scans; rust, wood,
fences, tiles, rail and manhole upscaled, the small ones through the model. A `road` grade spares painted lines
the darkening the asphalt takes. Checked without the client: every tiling texture wraps as well as it did
(seam measure 1.1–1.4 against 1.0–2.0 before); the graded road is half as bright as the graded sidewalk (38
against 73 of 255). Left for the base-game batch: `tcn01_water01` and the other stock textures. Left to the
by-rule remainder: sea plants, `lamp_dirty`, `tire_tread`, `walk`, small trims. The gate itself needs the
client: joins on the grid of road tiles, and road against sidewalk at night.

### 3 — Building families, one batch each

Slums 1–3 → Highrise 01–03, 05–07 → one batch of `Highrise_04` ruin, Apartments, Warehouses, Police, Hospital
and Lab → doors → the by-rule remainder → the ten base-game textures. Each batch is captured in one client
start. **Gate per batch:** contact sheet approved, walkmesh hashes unchanged, repository checks pass.

### 4 — New terrains and descriptive names

Copies of the `Highrise_05` and `Highrise_02` tiles (6 each) under new model names with their own textures;
walkmeshes copied unchanged; terrain entries, appended tiles, door records, a roof-access group, palette
entries and six edge-table rows each. Minimap images are reused from the source tiles. Descriptive names for
all building terrains, in the palette's display names if that is all the Toolset reads, otherwise in the set
and edge table together. **Gate:** both terrains paint, border Concrete and take doors in the Toolset; an
existing area opens unchanged; SR_NWN is checked for any use of the old names before they change.

### 5 — Cohesion and release

Wear and saturation evened out across families; frame rate, load time and pack size against the Phase 0
baseline; Futuristic City, `udp1`, the other tilesets and the placeables that name restyled textures looked at
once in game; one merge to `main`.

### Release 2 (not planned in detail)

Detail kit and selective remeshing, interior-style doors, Modern Exterior placeables, branded signage.

## Desk time

Estimates, not measurements. "Session" is working time with the machine in use (authoring, conversion, one
game client at a time, shared with other sessions). "Yours" is review and decisions. Unit times are those in
the routes table, plus 10–15 minutes for one client capture cycle. Strata 0 and 1 record real unit times and
this table is redone after the pilot. "Before" is revision 2, without the routes and time savers.

| Stratum | Contents | Before | Session | Yours |
|---|---|---:|---:|---:|
| 0 | Inventory tool, review set, baseline pictures, confirmations | 8–12 h | 6–9 h | 15 min |
| 1 | Material build tool, first masters, 15 pilot textures, pilot block, up to two review rounds | 12–16 h | 11–14 h | 45 min |
| 2 | Ground, streets, infrastructure, edge tiles (about 35 textures) | 10–14 h | 6–8 h | 20 min |
| 3a | Slums 1–3 | 7–9 h | 4–6 h | 15 min |
| 3b | Highrise 01–03, 05–07 with glow layers, grid tool | 9–12 h | 5–7 h | 20 min |
| 3c | `Highrise_04` ruin, Apartments, Warehouses, Police, Hospital, Lab | 13–18 h | 7–10 h | 30 min |
| 3d | Doors: shared textures and entrance door types | 4–6 h | 3–4 h | 15 min |
| 3e | By-rule remainder (139 textures, 5% of surface) | 4–6 h | 4–6 h | 10 min |
| 3f | Ten base-game textures, water checked first | 3–4 h | 3–4 h | 10 min |
| 4 | Two new terrains, descriptive names | 9–13 h | 7–11 h | 20 min |
| 5 | Cohesion, performance, other tilesets and placeables, release | 8–11 h | 7–10 h | 45 min |
| **Total** | | **87–121 h** | **63–89 h** | **about 4 h** |

The saving depends most on how many layout-bound textures hold up on the Upscale route. If the pilot sends
most of them to Regenerate, strata 3a and 3c return towards their "Before" figures.

Milestones by coverage: after strata 0–2, 3a and 3b most of the 42 textures that cover 80% of the surface are
done (ground, brick, concrete, the main facades), at about 32–44 session hours. Strata 3c–3f finish the
surface in a further 17–24.

## Open items

- The descriptive terrain names themselves (proposed with pictures in stratum 3b).
- Whether SR_NWN refers to terrain names anywhere (checked before stratum 4).
- Other sessions append envkit groups to `dgt04.set`; stratum 4 lands as one short-lived change to that file.
