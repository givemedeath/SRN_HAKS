# Stock NWN:EE race sizing compared with Shadowrun references

Saved 2026-10-01 for later race and gender expansion. This note records a sizing comparison, not completed fitting or client acceptance for those combinations.

With the current Human calibration, Shadowrun Humans closely match stock NWN:EE stature, Elves become substantially taller, Dwarves become smaller, and Orcs become slightly shorter than stock Half-Orcs. These height relationships should inform later expansion, while each race's joint placement and body proportions need separate fitting.

## Height calibration and comparison

The recorded reference heights come from `tools/phenotypes/height_targets.json`. They are assigned reference stature values, not measurements recoverable from image pixels alone. The reference images are located at `D:/source/repos/SRN_HAKS/.tools/reference_images`.

The calibration matches the reference male Human height of **1.75 m** to the measured stock male Human assembly height of **1.9339157 m**:

`target height = recorded reference height × 1.1050946857142858`

All heights below are in metres. Stock values describe phenotype 0 (Fit), assembled from stock part001 meshes with head001. The percentage compares the calibrated target with that stock assembly. Values are rounded for display; the calibration file remains the source for exact targets.

| Race and gender | Stock NWN:EE | Recorded reference | Calibrated target | Change from stock |
| --- | ---: | ---: | ---: | ---: |
| Human male | 1.933916 | 1.750 | 1.933916 | Matches |
| Human female | 1.837937 | 1.650 | 1.823406 | -0.79% |
| Elf male | 1.733691 | 1.900 | 2.099680 | +21.11% |
| Elf female | 1.638180 | 1.850 | 2.044425 | +24.80% |
| Dwarf male | 1.473464 | 1.200 | 1.326114 | -10.00% |
| Dwarf female | 1.399566 | 1.150 | 1.270859 | -9.20% |
| Half-Orc male to Orc male | 2.156261 | 1.900 | 2.099680 | -2.62% |
| Half-Orc female to Orc female | 2.106685 | 1.800 | 1.989170 | -5.58% |

The stock `appearance.2da` HEIGHT values are nominal metadata: Human 2.0, Elf 1.75, Dwarf 1.5 and Half-Orc 2.25. They differ from measured mesh stature and should not replace assembly measurements when calculating the target fit.

## Stock shoulder spacing

These measurements describe the distance between the left and right bicep attachment pivots in the stock rest skeleton. They are not outer shoulder width, muscle width, or measurements of the reference images.

| Stock race | Male pivot spacing in metres | Female pivot spacing in metres |
| --- | ---: | ---: |
| Human | 0.402015 | 0.277139 |
| Elf | 0.346016 | 0.237139 |
| Dwarf | 0.412015 | 0.393140 |
| Half-Orc | 0.602015 | 0.553139 |

The male Dwarf skeleton has slightly wider shoulder pivots than the male Human despite its shorter stature. Male Half-Orc shoulder pivots are about 50% wider than male Human pivots. Female proportions also differ substantially between races. A single height multiplier cannot reproduce those anatomical relationships.

## Implications for later expansion

### Queued task: Troll male proportions and equipment scaling

Recorded 2026-10-03 from the user's direction: **Troll male is the next phenotype
after Human male is complete.** This task is pending; documenting it does not
start Troll generation or change the current Human work.

Use the height table as a stature seed, then establish the non-height dimensions
before fitting Troll parts or batch-converting equipment. The existing
`tools/phenotypes/configurations/target-troll-male-scaled.json` is a portability
preflight, not a validated proportions or equipment profile.

- [ ] Freeze the completed Human male baseline and extract the actual stock male
  Human body, attachment and armor/clothing references. Stock Human male/female
  equipment remains the reusable source library, with identity scaling for Humans.
- [ ] Measure and document Troll shoulder and hip pivot spacing, torso width/depth,
  chest/waist/hip contours, limb segment lengths and thicknesses, neck/head fit,
  wrist/ankle connections, hand/foot size and weapon/shield attachment placement.
  Separate intended body dimensions from joint frames and visible overlap surfaces;
  do not infer these values from height alone.
- [ ] Establish one explicit Troll target rig and animation policy, with measured
  attachment frames and controller treatment. Preserve clip rotations/timing as
  declared and keep image-generation poses out of animation resources. Fit each
  purpose-built donor with uniform scaling, proper rotation and placement first;
  record any measured local refinement needed to preserve Troll anatomy.
- [ ] Derive reproducible per-part NWNArmory transforms from the approved target
  frames and fitted proportions. Record width/depth/length factors, origins,
  placement and resource substitutions for torso, pelvis, neck, belt, shoulders,
  arms, hands, thighs, shins and feet. Transform vertices and mesh-node placement
  without applying translation twice. Exclude naked part001 replacements from
  equipment batches; reuse stock clothing designs and textures.
- [ ] Treat robes separately through their skin/bone hierarchy. Measure helmet
  fit and held-equipment placement rather than inheriting a height multiplier.
- [ ] Validate representative clothing, light/heavy armor, exposed joints and
  robe coverage on the assembled Troll through idle, locomotion, casting, combat,
  crouch/kneel and death. Record offline evidence and separately authorized client
  results, then freeze the accepted scaling table/profile, commands and hashes.

Completion requires a measured proportions table, explicit target-frame/animation
contract, reusable equipment profiles and documented fit evidence. A successful
batch conversion or correct assembled height alone does not complete this task.

### Other race sizing notes

- **Human:** Male stature is the calibration anchor. The female target is only about 0.8% shorter than the stock female assembly, but female parts still require their own joint and socket measurements.
- **Elf:** The targets reverse stock NWN's shorter-than-Human Elf stature. The planned Elves are taller than Humans; fitting must account for the roughly 21% male and 25% female height increases.
- **Dwarf:** The targets are roughly 9–10% shorter than stock. Preserve the intended broad build while fitting limb lengths and attachment overlaps; do not infer body width from stature alone.
- **Orc:** Target height is close to stock Half-Orc height. The broad native skeleton still requires a separate comparison with the intended Shadowrun physique before choosing part or equipment resizing.

For each future combination, use stock assembled parts and attachment pivots as fitting references. Preserve the intended racial physique, and make any necessary mass reductions locally around joints rather than uniformly compressing the whole body. Validate neck and head placement, connected-part caps and overlap, limb alignment, and equipment fit through representative animations.

Derive equipment resizing profiles from the final fitted body. A height ratio alone is insufficient evidence for an armor scaling profile. Where stock equipment already fits, retain that fit rather than adding scaling by default.

Fit and Large variants are intended to share each combination's racial stature; this comparison measured only stock Fit assemblies. Stock Large bodies and their equipment fit remain unmeasured here. Troll targets exist in the calibration file, but this note does not compare Trolls with stock Gnomes.

## Measurement method and limits

The comparison used stock root models `p{m|f}{h|e|d|o}0.mdl` and their 16 standard bare parts: head, neck, chest, pelvis, and paired biceps, forearms, hands, thighs, shins and feet. Stock roots and archived Human parts came from `output/phenotypes/baseline`. Other race part001 resources were read from the installed NWN:EE game with `nwn_resman_cat.exe` and overrides disabled.

Vertices were transformed through each part's rest hierarchy and the stock root attachment transform. Assembly height was calculated as **highest vertex Z minus lowest vertex Z**, rather than crown Z alone. Some stock racial rest skeletons place the soles above or below Z zero. The highest and lowest vertices came from the head and feet in all eight assemblies.

The fresh male Human measurement agreed with the existing calibration within 0.000001 m. Existing calibration values were retained. These are static rest-assembly measurements; they do not establish client appearance or animation quality. Head selection, footwear, equipment and animated poses can change visible extrema. No client testing or fitting changes were performed for this comparison.

## Sources for incorporation

- `tools/phenotypes/height_targets.json`: recorded reference heights, uniform calibration factor and target limitations.
- `output/phenotypes/athletic-tpose-v12/stock-head-fit.json`: existing male Human calibration receipt.
- `output/phenotypes/baseline/ascii`: archived stock root transforms and available stock part meshes.
- `output/phenotypes/baseline/raw/appearance.2da`: stock nominal HEIGHT metadata.
- `tools/phenotypes/inspect_stock_joints.py`: stock part attachment mapping.
- Original compiler definitions used to interpret binary models: [NwnMdlNodes.h](https://github.com/niv/nwn-tools/blob/master/_NwnLib/NwnMdlNodes.h), [NwnMdlGeometry.h](https://github.com/niv/nwn-tools/blob/master/_NwnLib/NwnMdlGeometry.h), and [NwnModel.h](https://github.com/niv/nwn-tools/blob/master/_NwnLib/NwnModel.h).

Incorporate this note when expanding `docs/phenotype-implementation-plan.md` to additional races and genders. The comparisons are planning inputs; each finished combination still needs its own assembled-body, equipment and motion checks.
