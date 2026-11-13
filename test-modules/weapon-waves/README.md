# Itemkit comparison module

The weapons are released from the normal `srn_weapon` pack, with their carrier
table in `srn_2da`. This directory contains only the separate comparison module,
its environment and its experimental motion overlay. There are no duplicate
weapon HAKs or module-local copies of the released weapon blueprints.

See [the release guide](../../docs/items/approved-weapons-release.md) for the
weapon designs, grouping assignments and normal pack build.

## Build the test fixture

Build the normal packs first, then run from the repository root:

```powershell
Import-Module ./tools/SrnHaks.Common.psm1 -Force
$erf = Get-SrnTool -Name erf
$source = Join-Path (Get-Location) 'test-modules/weapon-waves'
$out = Join-Path (Get-Location) 'output/weapon-waves-test'
New-Item -ItemType Directory -Force -Path $out | Out-Null
foreach ($folder in Get-ChildItem "$source/haks" -Directory) {
    & $erf -c -e HAK -f "$out/$($folder.Name).hak" $folder.FullName
    if ($LASTEXITCODE) { throw "Failed: $($folder.Name)" }
}
& $erf -c -e MOD -f "$out/sw_weapon_w2.mod" "$source/module"
if ($LASTEXITCODE) { throw 'Module build failed' }
```

Use a separate NWN user directory. Supply the released `srn_weapon.hak` and
`srn_2da.hak`, the existing `srn_body.hak` and `srn_body_tex.hak`, plus the two
fixture HAKs built above. The module IFO records the priority order. It starts
on Cougar Knife pair 11; click the male reviewer for the next pair or the female
for a 60-second action test. There are twenty-two distinct male/female NPC pairs:
the ten Wave 1/2 designs, all three Cougar blades, both Colt finishes, the Vibro
Blades Sword, the Ares Predator IV and the five melee wave 2 designs (Ceramic
Knife, Extendable Baton, Tomahawk, Baseball Bat, Stun Staff). The Cougar, Colt,
Vibro, Predator and melee wave 2 pairs occupy the southern row and are included in
the full selector cycle. The Vibro and Predator pairs were added 2026-11-05. In
this module's client the selector stages both pairs and both bodies hold the
weapon (static inspection); their 60-second attack tests were not run. The five
melee wave 2 pairs (`sw5_`) were added 2026-11-13 and have not been run in this
module's client. Each was reviewed in its own itemkit fixture instead. Both
shipped Human bodies are represented for every weapon/finish.
Launching and client controls remain manual.

`sw_f7motion` and `sr_f7_*` are itemkit experiments only. They retain the approved
Ingram, AK and Crossbow body poses; the test F7 selector also recognizes both Colt
finishes. They do not ship in the normal release packs. Production weapon
animations will be implemented through the PhenoMorpher toolkit. Do not install
these prototype roots or event hooks globally.

The original client review captures remain in `review/`. The original 202-payload
manifest and validation report are retained there as historical approval evidence
from commit `5b105893bf187529c84bd0a81ebca9fe0d5e4447`; their old private-HAK paths
describe that commit, not the restructured layout. The current `manifest.json`
and `validation.json` describe this fixture's current payloads and dependencies.
The new grouping migration has native/package checks; a fresh in-game review of
that migration is not claimed.
