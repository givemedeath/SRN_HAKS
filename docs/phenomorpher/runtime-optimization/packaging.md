# Runtime optimization: Phase 5 packaging (contract 1.1.0)

The Phase 3 libraries and roots and the Phase 4 textures are adopted into `srn_body` and
`srn_body_tex`. Contract [1.1.0](../game-ready-assets.json) replaces 1.0.0. Client validation
and user acceptance of 1.1.0 are still pending (`runtimeOptimization.clientValidated: false`).

## Adoption

`phenomorpher adopt-runtime` (through `tools/phenomorpher/run.py`) read one adoption plan
that pins the base contract, the retired-resource list, the installed stock chain, each
library with its restoration receipt, each repointed root with its passing motion comparison,
and the texture receipt. It refuses:

* a pin that changed, or a published resource that differs from the base contract;
* a library without an exact-payload restoration receipt, or one not parented on `a_fa`/`a_ba`;
* a root without a passing comparison of exactly those bytes and that library build;
* a texture not derived from the payload it replaces;
* a target chain that still reaches a private carrier or does not end in the installed chain.

Carriers are retired only when no target chain reaches them. It staged the files, the
contract, [retired-runtime-resources.json](../retired-runtime-resources.json),
[ASSETS.md](../ASSETS.md) (same generator layout as 1.0.0, verified to reproduce it) and a
removal list. The repository copy was applied after hash-checking every removed file. A
second run with the committed code reproduced the identical contract, retired list, index
and removal list.

| | 1.0.0 | 1.1.0 |
|---|---:|---:|
| Contract resources | 1031 | 931 |
| Resource bytes (all three packs) | 1,663,499,943 | 846,886,551 |
| Private animation carriers | 108 (+ `srn_fa_h0`) | 0 (+ `srn_fa_h0`) |
| Shared libraries | 0 | 8 |
| Repointed roots | — | 18 (`pfh0`, `pmh0` unchanged) |
| Textures above 1024 px | 81 | 0 |

New contract fields: library rows (`role: animation-library`) with their restoration
receipt hash; root rows with `supermodel` `{from, to}` and comparison hash; texture rows with
`downsampledFrom` and `size`; `installedAnimationChain` pins of the stock `a_fa > a_ba > … >
a_ba_casts` chain observed at build time; and `runtimeOptimization`. `publicationNotes` replace
the note about private closures. Retired carriers and the replaced 2048 px payloads are listed with
their 1.0.0 hashes.

## Verification

* `phenomorpher verify-assets` on contract 1.1.0: 20 targets, 931 resources, all hashes verified.
* `tools/Build-Haks.ps1 -Pack srn_body,srn_body_tex`: 665 and 263 resources,
  667,871,456 and 176,204,022 bytes.
* `tools/Test-Repository.ps1 -ChangedSince 0866bcaf`: passed. All packs were rebuilt because the
  merged `main` changed shared CI files.
* PhenoMorpher package suite and the full helper suite (the contract has no catalogued readers).
