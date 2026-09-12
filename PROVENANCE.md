# Content Provenance

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
| `srn_t_srt04` | D20 Shadowrun Exterior |
| `srn_t_tbx78` | D20 Modern Facility |
| `srn_t_tfb01` | D20 Modern Interior |
| `srn_t_tjsb0` | D20 Secret Base |
| `srn_t_udp1` | D20 Suburbs UDP |
| `srn_t_udp2` | D20 Office Interiors UDP |
| `srn_t_vac01` | D20 Space |
| `srn_t_vmp01` | D20 Planetscape |
| `srn_t_vmr01` | D20 Alien Ruins |
| `srn_t_zsf01` | D20 SciFi Base CQ |

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
withheld because no matching `t_door93.dwk` was found. Restoring that registration requires the
original walkmesh or an engine-tested derivative; the final dependency report records this gap.

## MDRNEE audio import (2026-09-10)

`mdrnee_audio.hak` was imported under the `mdrnee_audio` profile. Its verified SHA-256 is
`012841691F5AB20EDAD8F2924DC63CC638C84CB8FD3D6A188F13388905E7742F`. All 142 BMUs land in
`srn_music`; 15 WAVs land in `srn_sound`, while `mdrnmod_barclub.wav` is explicitly excluded.
Exact hashes and the one differing EE identity
collision (`it_materialcloth.wav`) are recorded in `docs/imports/mdrnee_audio-manifest.json`.

The archive accompanies the same D20 Modern content distribution and is retained under the same
operator-reviewed open-project permission described above. Several music registration labels name
commercial game properties or soundtracks. The archive contains no per-track authorship or license
metadata, so public redistribution of the music pack requires a separate provenance/legal review;
the import record does not represent that those third-party rights have been cleared.

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
