# Neverwinter Nights model compiler/decompiler

This directory vendors the two 32-bit Windows executables requested from the SWLOR HAK working
tree. Both files are unsigned legacy tools; their hashes are pinned below and checked before the
command-line compiler is invoked.

The command-line tool's source and two-clause BSD license are published in
`niv/nwn-tools`: https://github.com/niv/nwn-tools/blob/master/nwnmdlcomp/nwnmdlcomp.cpp

| File | Bytes | SHA-256 | Purpose |
|---|---:|---|---|
| `nwnmdlcomp.exe` | 282,112 | `0E32070C3E00A07A5F9E93B7E4A63A40DD5486B974900BBB8A0D2F4424C612BB` | Edward T. Smith/Open Knights Consortium command-line compiler and decompiler |
| `NWN_compDcomp.exe` | 57,344 | `DCD862D48D0EC63110DB4E40D15143F1F4EA74B7D25BE689DEBB662ED0CCC4AD` | MFC graphical front end |

Use the hash-checking repository wrapper for scripted work:

```powershell
pwsh ./tools/Invoke-NwnMdlComp.ps1 -Mode Decompile `
  -InputModel ./srn_door/ctp_curtain_01.mdl `
  -OutputModel ./.quarantine/model-work/ctp_curtain_01.mdl.ascii

pwsh ./tools/Invoke-NwnMdlComp.ps1 -Mode Compile `
  -InputModel ./.quarantine/model-work/ctp_curtain_01.mdl.ascii `
  -OutputModel ./.quarantine/model-work/ctp_curtain_01.mdl
```

The wrapper requires separate input and output paths, passes an explicit output filename, and
refuses a changed compiler binary. `NWN_compDcomp.exe` remains available for manual GUI use but is
not launched by repository automation.

Decompilation was smoke-tested successfully against all six binary models currently in
`srn_door`. Compilation uses the same executable, but this legacy build must open an original
NWN 1.69 `chitin.key` through its legacy install discovery before it will compile. An NWN:EE-only
installation with `nwn_base.key` does not satisfy that requirement. No legacy `chitin.key` is
available on the current host, so the compilation smoke test correctly failed without producing an
output file. The wrapper detects that failure even though the old executable returns exit code zero.
