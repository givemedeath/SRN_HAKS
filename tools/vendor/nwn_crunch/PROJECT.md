# NWN Crunch - Enhanced Edition

This directory vendors the Windows x64 distribution of NWN Crunch 0.9. It is the repository's
canonical converter for BioWare/NWN DDS, standard DDS, PNG, TGA, and BMP textures.

- Project: https://neverwintervault.org/project/nwnee/other/tool/nwn-crunch-enhanced-edition
- Download: `nwn_crunch_windows64_ee.zip`
- Downloaded: 2026-09-11
- Archive size: 413,255 bytes
- Archive SHA-256: `53FCBC8BD7CBDC451EF9425C1D50C0916B20E37FD982A651CB36411DA146C198`
- Matching source archive SHA-256: `3BFA17D070FE37E615AA362163B5F7CC8754AA1323B866504AAF40D917CD23F1`
- `nwn_crunch.exe` size: 815,616 bytes
- `nwn_crunch.exe` SHA-256: `6AABE212EE8A4A5C166801C3C7830239E3EB15910F2743232C33666BC91AA46C`
- License: Zlib; the matching source distribution's unmodified notice is retained as `LICENSE.txt`

Use the hash-checking repository wrapper:

```powershell
pwsh ./tools/Invoke-NwnCrunch.ps1 `
  -InputTexture ./.quarantine/mdrnee_tile/raw/manhole_tex2.dds `
  -OutputTexture ./.quarantine/texture-work/manhole_tex2.png `
  -OutputFormat png
```

The default `MipMode=UseSource` preserves the source mip chain when the target format supports
it. PNG, TGA, and BMP outputs contain the top-level image, as expected for those formats.
