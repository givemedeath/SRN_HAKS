# PhenoMorpher game-ready bodies

Version 1.0 publishes twenty reviewed bodies: Human, Dwarf, Elf, Orc and Troll,
female and male, Fit and Large. Use
[game-ready-assets.json](game-ready-assets.json) as the current resource and
target contract. Previous Human delivery manifests remain historical records.

The user approved these shapes and requested publication on 2026-10-13 after
the final client and clothing checks. This release changes resource routing and
skin/material defaults; it does not reshape any approved body or change its rig.
The selected female posture is **hips level + original upper lean/breathing**.

## Build and consume

Native models, PLTs and private fitted animation closures land
in the flat `srn_body` pack. Required material descriptors and new skin maps land in `srn_body_tex`, keeping the body pack below the bundler's 2 GB limit. Appearance, race and phenotype tables land in `srn_2da`.

```powershell
./tools/Build-Haks.ps1 -Pack srn_body,srn_body_tex,srn_2da
```

Attach all three built HAKs to your module and set its custom TLK to `srn`. Place `srn_2da` above another appearance
table provider and use the target contract rather than the old diagnostic HAKs.
The published appearance rows are 15100 Human, 15101 Dwarf, 15102 Elf,
15103 Orc and 15104 Troll. Gender is 0 male / 1 female. Phenotype is **0 Fit /
2 Large**, and all fifteen body/neck part numbers default to **1**. No tone237
button or test script is needed. Do not substitute stock phenotype 1 for Large.

Trolls intentionally occupy the project's **Gnome body slot G**, as established
by the derived target policy. Dwarf D, Elf E, Human H and Half-Orc O bodies also
replace the corresponding slot's part001 resources. This is a project body
replacement pack; it does not preserve stock bodies in those slots. Half-Elves
share Human resources, and Halflings are outside the release.

The selected Fit model237 and its palette are promoted to part001. Only fixed
model/node name fields change in those model binaries; raw geometry, UVs,
lighting attributes, transforms and animation data remain exact. Large native
models, fitted rigs and selected texture payloads are copied byte-for-byte.
The dependency inventory records original archive and payload hashes. No
diagnostic garments, alternate skin comparisons, test areas or global stock
animation overrides are published.

## Validation and limits

[Client coverage](client-coverage.json) records the original reviewed selections.
[Publication verification](publication-validation.json) records source matching,
dependency closure and the rebuilt pack inventories. The coverage's historical
`productionAccepted: false` fields describe the earlier review fixture, not the
later user instruction to publish this selected release.

Client checks covered all twenty bodies in white/warm indoor and outdoor light,
sampled idles, walk/run, both kicks, casting, representative solid close/loose/
plate clothing and sword, greatsword, bow and shield combat. Useful joint overlap
and the accepted imperfect Large waist transition remain intentional.

The Large chests have 5,494 male / 5,482 female triangles, compared with 5,500
for the Fit chest. Skin uses the selected no-grain detail and tone correction;
garment and material-map resolutions retain their reviewed payloads. Original
stock head001 geometry supplies context. Finished race-specific heads, a complete
armor wardrobe, weighted robes/cloaks and exhaustive palette/frame testing are
separate work. Bind stature is measured; absolute client height is not calibrated.
The previously observed client exit crash remains unsymbolicated and was also
present before this package; the final checks had no in-session crash.

PhenoMorpher tooling is delivered in a separate PR. This asset pack can be built
and consumed using the repository's existing HAK bundler without that toolkit.

## Race and phenotype tables

The installed table schema and row IDs are retained. `racialtypes.2da` maps
Dwarf 0, Elf 1, Troll 2, Orc 5 and Human 6 to their release appearances. Troll
and Orc display names use permanent entries in `srn.tlk`; underlying ability
adjustments, feat tables, constants and all other gameplay fields retain the
installed defaults. Half-Elf 4 and Halfling 3 have `PlayerRace=0` and remain
available for existing NPC/save data. These changes do not rebalance races or
rewrite existing creature instances.

`phenotype.2da` is stock-exact: 0 Normal/Fit, 1 hidden Skinny with an unset display
name and fallback 0, and 2 Large. No Skinny body set is added. Mounted/joust
variants retain their stock table entries but are outside this body release's
client validation. See [table verification](table-validation.json).

The runtime folders contain only the selected dependency closure. The 84 superseded Human maps/materials were removed from packaging and remain recoverable in Git history. No model, palette, rig or selected material/map payload was changed by this cleanup.
