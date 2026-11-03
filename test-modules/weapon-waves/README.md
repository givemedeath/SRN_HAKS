# Approved weapon waves: reproducible private review module

The user approved the repaired Waves 1 and 2 in the NWN:EE client on
2026-11-03 and requested this PR. This directory publishes the exact reviewed
native resources, not the generation experiments or machine-specific bindings.
The independent pipeline PR is not needed to build these already compiled assets.

## Contents

| Pair | Weapon | Blueprint |
| --- | --- | --- |
| 1 | Ingram Smartgun X | `sre9a211be_3` |
| 2 | Stun Baton | `sr_stbaton` |
| 3 | AK-98 | `sra84e4660_5` |
| 4 | Heavy Crossbow | `sr6abe18c_6` |
| 5 | Riot Shield | `sr800e341u` |
| 6 | Katana | `srf7ac8ec` |
| 7 | Staff | `srdc4c1668` |
| 8 | Throwing Knife | `sr2273b8c` |
| 9 | Bow | `srdd7dc09` |
| 10 | Whip | `sreab35fc` |

The AK-98 launcher (`sra84e4660gl`) remains a separate gameplay entry using its
parent model. The module also supplies the four previously approved weapons,
including both Colt L36 finishes. Both shipped Human bodies have reviewers.
Blueprint names above are confirmed by the native resource inventory; embedded
display descriptions remain the original private-candidate metadata.

The Katana has its corrected blade/hilt alignment, a 180-degree cutting-edge
reversal around the grip axis, and a 40% longer blade with unchanged grip/guard.
Crossbow cords have straight endpoint-weighted geometry and stock-timed release
and recovery. The Bow has the enlarged span and retains native `bowshot` motion.
Ingram uses corrected native model orientation and custom one-handed firing;
AK/Crossbow support-hand poses are retained. The fixture includes the saved-game
environment fix and a startup guard for actor staging, without diagnostic pauses.

## Build and load

Use the repository's pinned `nwn_erf` tool. Run from the repository root:

```powershell
Import-Module ./tools/SrnHaks.Common.psm1 -Force
$erf = Get-SrnTool -Name erf
$source = Join-Path (Get-Location) 'test-modules/weapon-waves'
$out = Join-Path (Get-Location) 'output/weapon-waves-pr'
New-Item -ItemType Directory -Force -Path $out | Out-Null
foreach ($folder in Get-ChildItem "$source/haks" -Directory) {
    & $erf -c -e HAK -f "$out/$($folder.Name).hak" $folder.FullName
    if ($LASTEXITCODE) { throw "Failed: $($folder.Name)" }
}
& $erf -c -e MOD -f "$out/sw_weapon_w2.mod" "$source/module"
if ($LASTEXITCODE) { throw 'Module build failed' }
```

Copy the resulting module/HAKs into a **separate NWN user directory**. Supply the
existing release `srn_body.hak` and `srn_body_tex.hak` (c7 Humans / PhenoMorpher
1.3.0); they are dependencies, not duplicate content in this publication. The
module IFO preserves the exact tested HAK order and requires no custom TLK.
The module starts on the Katana pair. Click the male reviewer for the next pair
or the female reviewer for a 60-second action test. Launching remains manual.

Do not install the private table and motion overrides globally. `sw1_humans`
contains the fixture appearance table; `sre9a211beh` contains its effective
baseitems table. `sw_f7motion` overrides the two Human roots only to insert the
additive animation library above their existing supermodel chains. Actual motion
replacement is selected per actor/item in `module/sr_f7_inc.nss`. This is not a
general firearm ammunition/reload implementation or qualification of other bodies.
The production `srn_*` packs and existing four-weapon publication remain unchanged.

## Verification and evidence

`manifest.json` identifies all 202 packed payloads by SHA-256 and retains original
archive hashes. Repacking may change archive ordering/header bytes, so compare
resource payloads, not rebuilt archive bytes. `validation.json` records fresh
rebuild/readback checks. The `review/` images show actual client views of the final
Katana and Crossbow; they are not offline render substitutes. Both completed
12 attacks/shots per Human in the final bounded checks. Earlier sampled reviews
covered the other weapons, Shield combat/run and save/reload. These are bounded
observations, not exhaustive armor, offhand, race or animation-clearance coverage.

This PR proposes the reviewed private assets for review. It does not deploy a
server/module, alter production packs, or change combat balance. No full regression
suite was rerun.
