# Content Provenance

Exceptions must be recorded here before it merges. Record the hak category and asset filename and
contributor.

## Size exceptions

Resources are limited to 15 MiB by default. A reviewed exception uses exactly this machine-readable
form, with a repository-relative path and a non-empty reason. Remove `EXAMPLE ` when adding a real
exception:

`<!-- EXAMPLE srn-size-exception {"path":"srn_example/example.dds","reason":"Reviewed reason"} -->`

There are no content batches or size exceptions in the initial scaffold.
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


<!-- srn-size-exception {"path":"srn_t_vmp01/vmp01_building01.tga","reason":"Required original D20 Planetscape tileset texture; reviewed at 16,777,260 bytes and below GitHub's hard limit."} -->
