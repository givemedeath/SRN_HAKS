# Modern Exterior (`dgt04`) Shadowrun upfit — plan

Status: planning, revision 2, 2026-11-18. Nothing in the packs has changed yet.

Source: `SR_NWN_Modern_Exterior_Upfit_Plan_Complete.zip` (revision 1.1, 2026-11-18), reviewed against this
repository. The package's art direction and its insistence on in-game proof stand. Its inventory, packaging and
schedule do not, for the reasons in "Corrections to the package". Where the two differ, this file is the plan.

Revision 2 re-measured every figure from the repository, added the edge tiles, measured surface coverage per
texture, replaced the texture-size figures (revision 1 had read only the TGA copies), and added desk time.

## Decisions (user, 2026-11-18)

| Topic | Decision |
|---|---|
| Packaging | Replace in place in `srn_t_common`, `srn_t_dgt04`, `srn_door`. No override pack. Git history is the rollback. |
| File form | Each restyled texture ships as one material file plus DDS maps. Its old TGA and DDS copies are deleted. |
| Texture authoring | Hybrid. CC0 scanned material libraries for tiling surfaces. Generated images only for facade atlases, windows, doors and signs that must follow the original UV layout. |
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
| Reviews | User approves the pilot, then one day-and-night contact sheet per batch. |
| Release | Each phase is a pull request into a restyle branch; `main` gets one merge when the tileset is consistent. |

## Verified baseline (this repository, 2026-11-18)

| Fact | Value |
|---|---|
| `dgt04.set` | 22 terrains, 14 crossers, 556 tiles (555 models), 68 groups |
| Edge tiles (`srn_2da/dgt04_edge.2da`) | 155 rows naming 60 models; 43 are not in the set; 9 of those are base-game models |
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
- A restyled texture is one material file and its DDS maps in one pack. No older copy of that name remains in
  any pack unless recorded as a decision. No file over 15 MiB without a size exception in PROVENANCE.md.
- A base-game texture keeps its layout exactly, and any stock TXI behaviour (water above all) is shown to
  survive before the texture is accepted.
- No crack, stain or patch on a tiling texture large enough to read as a repeat across four adjacent tiles.
- Ground and road materials carry no baked lighting direction: tiles are placed in four rotations.
- Acceptance is the Toolset and the game client, day and night. Preview renders accept nothing.

## Work order

Work runs in coverage order inside each phase, so the surface players see most is done first. The 139
textures that cover the last 5% are handled by rule (resized, tone-matched, given a plain material), not
authored one at a time; any that then stands out is promoted.

### 0 — Inventory tool, review area, confirmations

- The audit that produced the baseline above, kept as a tool with tests: texture → models → tiles → terrains,
  surface per texture, copies and sizes in every pack, other users of each name, walkmesh hashes, and models
  in the tile packs that nothing names.
- A review area holding every terrain, crosser, original group and edge, with fixed camera positions, built
  on envkit's Toolset module preparation and client capture. Baseline pictures by day, night and overcast.
- Confirmations in the client on `sidewalk10`, `brick_tex19` and `hrise_05_wall`: the material file is picked
  up with no model edit; the normal map is right on all four rotations and on mirrored UVs; the night glow
  layer still shows over it. Also recorded: which of the TGA and DDS copies the client shows today, since that
  is what "before" means for 131 textures.
- Unit times recorded from here on.
- **Gate:** confirmations pass, or the mechanism changes before any authoring.

### 1 — Material standard and pilot block

- A material build tool on envkit's texture and material writer: source image and maps in, DDS set and
  material file out, old copies removed, PROVENANCE row written.
- About fifteen textures chosen from the top of the coverage list: two bricks, two concretes, sidewalk,
  asphalt, pavement, roof gravel, one corporate facade with its glow layer, Slums windows day and night, door
  trim, street lamp, metal fence.
- One block: a corporate highrise, a Slums building, a street with an intersection, a warehouse, beside a
  Stuffer Shack.
- **Gate (user):** the look by day and night beside the envkit building. This fixes the standard.

### 2 — Ground, streets and infrastructure

Roads, sidewalks, curbs, crossers, Freeway, Green_Bridge, Aqueduct, Water edges, Cliff, edge tiles. Checked on
a grid of straight, corner, T, four-way, ramp and transition tiles in all rotations. **Gate:** no new seam at
any join; road against sidewalk still reads at night.

### 3 — Building families, one batch each

Slums 1–3 → Highrise 01–03, 05–07 → `Highrise_04` ruin → Apartments → Warehouses → Police, Hospital, Lab →
doors → the by-rule remainder → the ten base-game textures. **Gate per batch:** contact sheet approved,
walkmesh hashes unchanged, repository checks pass.

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
game client at a time, shared with other sessions). "Yours" is review and decisions. Unit times assumed: a CC0
surface fitted and packed 10–15 minutes; a generated, layout-bound texture 30–45 minutes with retries; one
client capture cycle 10–15 minutes. Phase 0 and 1 record real unit times and this table is redone after the
pilot.

| Stratum | Contents | Session | Yours |
|---|---|---:|---:|
| 0 | Inventory tool, review area, baseline pictures, confirmations | 8–12 h | 15 min |
| 1 | Material build tool, 15 pilot textures, pilot block, up to two review rounds | 12–16 h | 45 min |
| 2 | Ground, streets, infrastructure, edge tiles (about 35 textures) | 10–14 h | 20 min |
| 3a | Slums 1–3 | 7–9 h | 15 min |
| 3b | Highrise 01–03, 05–07 with glow layers | 9–12 h | 20 min |
| 3c | `Highrise_04` ruin | 2–3 h | 10 min |
| 3d | Apartments | 3–4 h | 15 min |
| 3e | Warehouses | 3–4 h | 15 min |
| 3f | Police, Hospital, Lab | 5–7 h | 15 min |
| 3g | Doors: shared textures and entrance door types | 4–6 h | 15 min |
| 3h | By-rule remainder (139 textures, 5% of surface) | 4–6 h | 10 min |
| 3i | Ten base-game textures, water checked first | 3–4 h | 10 min |
| 4 | Two new terrains, descriptive names | 9–13 h | 20 min |
| 5 | Cohesion, performance, other tilesets and placeables, release | 8–11 h | 45 min |
| **Total** | | **87–121 h** | **about 4.5 h** |

Milestones by coverage: after strata 0–2, 3a and 3b most of the 42 textures that cover 80% of the surface are
done (ground, brick, concrete, the main facades), at about 46–63 session hours. Strata 3c–3i finish the
surface in a further 24–34.

## Open items

- The descriptive terrain names themselves (proposed with pictures in stratum 3b).
- Whether SR_NWN refers to terrain names anywhere (checked before stratum 4).
- Other sessions append envkit groups to `dgt04.set`; stratum 4 lands as one short-lived change to that file.
