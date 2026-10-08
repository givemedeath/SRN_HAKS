# Gate 4 — ready for the client session (NOT launched)

The production LEAN bodies passed Gate 3 (accepted as-is with known issues:
`user-directions/2026-10-08-gate3-lean-accept.json`). Everything below is prepared and preflighted. **No client has
been launched.** Launching needs your explicit go-ahead. Run one client at a time: first confirm that
`Get-Process nwmain -ErrorAction SilentlyContinue` returns nothing.

## What was built

**Candidate srn_body** — `gate4-v1/candidate/candidate-root/srn_body`. This is a staging copy; the tracked `srn_body` is unchanged.
- It holds 140 resources: female `pfh0` 70 (from `lean-v1/chain-v1/composition`) and male `pmh0` 70 (from `human-male-fix-v2/lean-v1/chain-validation/composition`).
- Diff against the tracked pack, in `candidate/diff-manifest.json`:

  | Change | Count | Detail |
  |---|---|---|
  | Added | 70 | the female body |
  | Removed | 2 | `pmh0_pelvis001f.mtr`, `pmh0_pelvis001f.tga` |
  | Changed | 46 | male resources |
  | Unchanged | 24 | male resources, byte-identical |
  | Other files | 0 | the tracked pack holds only the 72 male v1 body files |

**Candidate HAK** — `gate4-v1/candidate-hak/srn_body.hak`, sha256 `b1d4112e…5325`, 140 resources.
- Its payload equals the staging copy byte-for-byte.
- It was built with the exact Build-Haks erf operation. Build-Haks.ps1 itself needs PowerShell 7, which is not installed (see `build.json`).

**Published-body verification** — `verification/verification.json`. `verify_published_body.verify` passes for both sexes against the schema-2 target manifests:
- the derived 70-resource closure;
- exact staged bytes;
- the rebuilt-HAK payload.

The manifests are candidates; their `clientEvidence` points at the Gate 3 record because client validation is still pending.

## Launch commands (PowerShell, from the repository root)

```powershell
Set-Location <repo>
$py  = '<python>'
$nwn = '<nwn-install>\bin\win32\nwmain.exe'
$mig = 'output\phenotypes\poly-budget-lean-ingame-v1\tool-migration-v5'
$fc  = 'output\phenotypes\human-female-fit-purposebuilt-v1\stock-target-v1\target-contract.json'
$mc  = 'output\phenotypes\human-male-fix-v2\stock-target-v2\contract\target-contract.json'
$F   = 'output\phenotypes\human-female-fit-purposebuilt-v1\completion-v1\gate4-v1\fixtures'
$M   = 'output\phenotypes\human-male-muscular-purposebuilt-v2\gate4-v1\fixtures'
function Go($c, $fx) { $h = (Get-FileHash "$fx\test-module\receipt.json" -Algorithm SHA256).Hash.ToLower()
  & tools\phenotypes\Launch-TargetBodyClient.ps1 -TargetContract $c -Fixture $fx -ReceiptSha256 $h -Client $nwn `
    -WorkspacePython $py -Toolchain "$mig\shared-tools.json" -MigrationReceipt "$mig\migration.json" }   # add -NoLaunch to re-run only the preflight

Go $fc "$F\female-palette"   # palettes 3/8, dye actors tm_0 red / tm_1 blue
Go $fc "$F\female-matrix"    # 13-step motion schedule
Go $mc "$M\male-palette"
Go $mc "$M\male-matrix"

# Candidate-HAK smoke (loads the built srn_body.hak itself; female tm_0-3, male tm_4-7; tm_0 red, tm_5 blue):
$S = "$F\hak-smoke"; Start-Process -FilePath $nwn -WorkingDirectory (Split-Path $nwn) `
  -ArgumentList @('-userdirectory', ('"' + (Resolve-Path "$S\userdir").Path + '"'), '+TestNewModule', 'srn_hak_smoke')
```

### Character creation (fixture `hak-chargen-v1`; replaces the earlier hak-smoke route, which showed an empty module list)

This fixture is the HAK smoke plus a `module.ifo` that carries the stock identity and event fields. Those are a fresh 16-byte VOID `Mod_ID` plus creator, expansion, event and list fields, each checked against the field types of the shipped *The Dark Ranger's Treasure* module. The module name is `srn_hak_chargen`. It loads the exact candidate `srn_body.hak` (`b1d4112e…`) from its own fresh isolated userdir.

```powershell
$C = (Resolve-Path "$F\hak-chargen-v1\userdir").Path
Start-Process -FilePath $nwn -WorkingDirectory (Split-Path $nwn) -ArgumentList @('-userdirectory', ('"' + $C + '"'))   # main menu; no +TestNewModule
```

Menu path, to do once for a female and once for a male Human:
1. **New Game**, then the **Local** (or Other modules) list, then select **srn_hak_chargen** and confirm Load / Play.
2. **New** (create character): Gender Female (then Male), Race Human, Appearance (default body).
   - Skin colour: palette 3 for one character and 8 for the other.
   - Pick a head.
   - Underwear shows the default (cream) dye.
3. Finish creation with any class and the Recommended options, then **Play**. The character enters `sr_tm_floor` beside the fixture actors (tm_0–3 female, tm_4–7 male).

What to check:
- the creation preview shows the new body;
- the neck and head seam with the selected head;
- the palette;
- after entering, the same body in game.

**If the module list is still empty:** the remaining hypothesis is the failed GOG sign-in in isolated userdirs, since they have no `cdkey.ini`. You would need to place your own `cdkey.ini` in this userdir yourself (see `character-creation-investigation.md`).

Preflight: `hak-chargen-v1/test-module/receipt.json`, sha256 `f4a99d47…d30c`, pass. It covers HAK bytes and payload exact, `[srn_hak_chargen, srn_body]`, 4 female and 4 male actors, dressed-actor fields, an isolated userdir with an empty override, the module ID present (`KAXSfHotQxaVCGFA1F7XiQ==`) with every stock IFO field present and typed, entry area `sr_tm_floor`, and not a saved game.

## Preflights (`-NoLaunch`, all passed; clientLaunched false)

| Fixture | Receipt sha256 | Preflight file |
|---|---|---|
| female-palette | `a612510f…557b` | `client-preflight-5070…` (dressed dye actors tm_0/tm_1 verified) |
| female-matrix | `521732ca…c788` | `client-preflight-6809…` |
| male-palette | `2b2da5da…41bd` | `client-preflight-e7a3…` (dressed dye actors verified) |
| male-matrix | `f0ab55cd…48fa4` | `client-preflight-b759…` |
| hak-smoke | `42d74931…116f` | `hak-smoke/test-module/receipt.json` (`preflight.pass` true) |

The HAK-smoke preflight checks:
- HAK bytes equal the candidate;
- the body payload is 70 `pfh0` + 70 `pmh0`, exact;
- the fixture HAK contains only `sr_tm.set` and `sr_tm_edge.2da`;
- the module binds `[srn_hak_smoke, srn_body]`;
- 4 female and 4 male Human actors on palettes 3/8;
- dressed actors carry the stock body fields;
- the userdir is isolated and the override is empty.

The male fixtures live in the repository packer's own target area, `output/phenotypes/human-male-muscular-purposebuilt-v2/gate4-v1/`, which was created for this. No bypass was added.

## Checklist (observe in the client)
- [ ] Palettes 3 and 8 side by side, for both sexes.
- [ ] Dyes:
  - [ ] Female brief and bra take red (88) and blue (26); undyed is cream (stock behaviour).
  - [ ] Male brief takes the dyes.
  - [ ] Dressed actors are visible.
- [ ] Motions in the matrix fixtures: idle, walk, run, cast, attack, crouch, kneel, death and resurrection.
  - [ ] Joints, hands and feet.
  - [ ] Brief edges and the bra edge.
- [ ] Damage, death and resurrection; soles visible when dead-front / dead-back.
- [ ] Character creation with both sexes from the HAK-smoke userdir.
- [ ] Male neck with stock heads (plus a couple of other heads in character creation).
- [ ] HAK smoke: both sexes render from the built `srn_body.hak`; no missing-texture or log errors (check `userdir\logs`).
- [ ] Known accepted issues, still present:
  - male waistband top edge and dark band;
  - female cream blotching, bra-back flecks, upper-back dash.
