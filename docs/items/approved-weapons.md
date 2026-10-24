# Approved weapon assets

This content-only publication contains the four user-approved weapons, with both
accepted Colt finishes. It is independent of the itemkit tooling PR #56. Models,
diffuse maps and icons are copied byte-for-byte from the accepted private
packages. Blueprint display metadata is cleaned as described below; models are
not regenerated or recompiled.

| Item | Native family | Blueprint | Appearance |
| --- | --- | --- | --- |
| Cougar Fineblade Longblade | Short sword | `sr_cougar` | `wswss_*_071` |
| Cougar Fineblade Knife | Dagger | `sr_cfk` | `wswdg_*_071` |
| Cougar Fineblade Longsword | Longsword | `sr_cfs` | `wswls_*_101` |
| Colt L36, base finish | Sling | `sr_cl36_1` | bottom `051`, top/middle `011` |
| Colt L36, cool gunmetal finish | Sling | `sr_cl36_2` | bottom `052`, top/middle `012` |

`srn_weapon` contains 44 native resources: 17 compiled models, 22 TGA diffuse/icon
maps and five UTI blueprints. The tiny invisible pistol parts are intentional
components of its tested multipart contract. They remain in the pack and budget.
All five runtime diffuse maps are 1024 square. Only each design's matching
assembly is supported; arbitrary part interchange is not qualified.

## Sling display-table change requiring review

The pistol fixture uses `ModelType=2` for BaseItem 61, `ItemClass=WBwSl`, and
extends the appearance range from 50 to 52. The operator explicitly requested
including that table change in this PR. The exact accepted table is published
in `srn_2da`, where repository policy places all 2DA resources.

This is a global display change for the Sling family, not a pistol-only switch.
Ordinary slings and other content using that row may need multipart resources
or a separate integration decision. Their compatibility has not been newly
client-tested. The pistol retains Sling gameplay rules, animations and ammunition
behavior; this publication does not implement firearm mechanics. No damage,
combat, pricing or other base-item fields are changed. The full source-table
hash and exact two-field change are recorded in the publication manifest.

Load `srn_weapon` with `srn_2da` for the reviewed pistol contract. Other HAKs that
override `baseitems.2da` require an intentional table merge; load order alone is
not a substitute for reconciling their changes. No game installation, server or
production module is modified by this PR.

## Provenance and acceptance

`approved-weapons-v1.json` records each payload hash, source archive and approval
evidence hash. The three blade HAKs and accepted pistol HAK/module remain retained
under the original ignored trial outputs. Blade blueprint sources come from the
accepted combined module; the pistol blueprint sources match its HAK and module.

Publication removes trial-only descriptions, the knife's size-experiment suffix,
and garbled punctuation in the alternate pistol name. The manifest records each
original hash and exact changed display fields. GFF roundtrips preserve every
other field and the original root structure IDs. These remain unpriced builder
templates with zero costs and empty item-property lists; no balance changes are
implied by visual approval.

The user accepted all four weapons after viewing the test module on the shipped
Human fixture. Individual animation, armor, glove and off-hand checklist cases
were not separately reported. This does not claim qualification for other bodies
or arbitrary item combinations. The Ingram Smartgun X remains on hold and is not
part of this publication.

## Validation

`approved-weapons-validation.json` records the publication checks: repository
structure passed; 17 native models decoded; 22 images and every texture reference
checked; five blueprints roundtripped with only the documented display edits.
Both affected HAKs were rebuilt and reopened, then all 44 weapon and 22 table
payload hashes were compared to their source files. The accepted original
archives remain unchanged. No full regression suite or new client run was used.

To rebuild only this publication's affected packs in PowerShell:

```powershell
./tools/Build-Haks.ps1 -Pack @('srn_weapon', 'srn_2da') -SkipTlk
```
