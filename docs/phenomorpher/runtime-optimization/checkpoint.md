# Runtime optimization: Phase 8 checkpoint (contract 1.1.0 accepted)

Resume from this file. Contract 1.1.0 was compared with 1.0.0 in the NWN:EE client and accepted by the
user on 2026-10-14 (`runtimeOptimization.clientValidated: true`, `userAccepted: true`). Rollback is
contract 1.0.0 and its resources at `0866bcaf`. Phase 9 (the toolkit upfit) is a separate follow-up PR; see
[plan.md](plan.md).

## Ledger bindings

### Git

| Binding | Value |
|---|---|
| Branch | `codex/phenomorpher-runtime-optimization` (remote has only the plan commit `adb0689e`) |
| Base release | `codex/phenomorpher-bodies-v1` @ `0866bcaf5931735ce7cc4489681b9c933ee9257c` (kept as the 1.0.0 rollback anchor; PR #45 closed, superseded by this branch's PR) |
| `main` merged | `ea0b6678a340435c2b43bae5fc489f8f6fb13498` (via `df008031`) |
| Phase commits | baseline `6a5249db`, pilots `c08d85d2`, libraries `12a0bced`, textures `14b48832`, contract `7c163844`, inventory/managed commands `d44c6d20`, offline review `8951f1ae`, client `3e6e8160`, this checkpoint (next commit) |
| Plan | [plan.md](plan.md) SHA-256 `14f052a9368e50879e7cdf80367853f7606c1256ab9a85adb607fec72ec695a1` (with dated revisions) |

### Contract

| Binding | SHA-256 |
|---|---|
| 1.0.0 contract (`0866bcaf`) | `bebb864ccad91e31a77b180e1c2ce714b8227de2d7ef5a76664a0147cfd9f7cd` |
| 1.1.0 as adopted (`7c163844`, equals `staged-001/game-ready-assets.json`) | `4c2e1dc4a01e5d85cff55b291075932fb3d8ca3d30d69a5e3908c145506f93f8` |
| 1.1.0 accepted (this commit) | `582c25d1908854477fdff7a6b89655f6d6bef5a76c607875f0a909a681e1672a` |
| `retired-runtime-resources.json` | `10600ecb7619dcc3f9d20abf2ac8f14ef3a896e5ef95f925f6beac69396c5e51` |

The accepted contract differs from the adopted one only in `runtimeOptimization`:

* `clientValidated`, `clientEvidence`, `userAccepted` and `userAcceptedOn`;
* the evidence list, which gains packaging, review and client.

`adopt-runtime` itself still writes `false` for both flags. Acceptance is a separate, recorded user decision.

After review on PR #49, `compare-motion` reports pin the contract, the stock manifest and every old-chain model they
compared, and `adopt-runtime` requires those pins to match its plan. The Phase 5 comparison reports predate this.
They stay valid historical evidence for the adopted files, but a new adoption needs freshly generated comparisons.

### Local evidence (ignored `.tmp/`; machine-local)

| File | SHA-256 |
|---|---|
| `runtime-bindings/runtime-opt-001.json` (Python, Blender, NWN) | `3983aa8d7144da8acbdf4258c7cc2482f492485e993efa1d85d8142315760914` |
| `runtime-bindings/pheno-migration-001.json` | `bf9df5befdc570ddd0f90945647229b0ec407ab7b732fa3bd27090afbc8efd1e` |
| `runtime-bindings/blender-migration-001.json` | `7b4ccbf05880aa00600a223c2f00acb093a93fdd3b257d1e4761e004187f6f70` |
| `runtime-optimization/phase5/adoption-plan-001.json` | `c958b55d6a995f9293e932d71040ad7add6268e0215c6108f43393e9062a0882` |
| `runtime-optimization/phase5/staged-001/adoption-receipt.json` | `7cce37ad02e6ad51efa03fb187746a59e1169ce4ab2925114b5b32ad4f6e1dfd` |
| `runtime-optimization/phase5/launch-adopt-001/launch.json` | `c8b6374c0ae6cad20f0004d5ddc620553730c25ede99a3e08bfdade8ee331bd8` |
| `runtime-optimization/phase6/offline-002/phase6-offline.json` | `6555296500a3dd4b6b28b75a34e63a7aed70ef5ac159c1cc0a9a517c2e8d04ba` |
| `runtime-optimization/phase6/launch-sweep-new-{7,8,9}/launch.json` | `2ccbe71d…0756e52`, `d37f51ca…8b0a`, `9bc73ca6…0ddf` |
| `runtime-optimization/phase6/launch-sweep-old-2/launch.json` | `4e63baa3fdb71149b374c4e41af24b1d3bfabfaf1e5cd6e50d4008eda1baa5c6` |
| `runtime-optimization/phase7/fixture-003/receipt.json` | `60d6547cf59f56520b6bc12cdba3a9d474f6fc38e3d85b790bdd83d17e1671f9` |
| `runtime-optimization/phase7/fixture-004/receipt.json` | `71b059552ab60d7e3cc18179cb62e09cef2c02f67b530f27da9c0c9661064340` |
| `runtime-optimization/phase8/launch-verify-110-accepted/launch.json` | `54ebcc36c7e0f909989d670f10a913ba2ed321a819d4b8aded1d97e03d6fe8d0` |

The first sweep launches (`launch-sweep-new-{1,2,3}`) are kept but invalid: a toolkit commit landed
while they ran. The frozen rerun reproduced their outputs byte for byte. The earlier fixtures
(`fixture-001`, `fixture-002`) and their launches are superseded preparation.

## Before and after

| | 1.0.0 | 1.1.0 |
|---|---:|---:|
| Contract resources | 1,031 | 931 |
| Resource bytes (three packs) | 1,663,499,943 | 846,886,551 |
| `srn_body.hak` | 765 resources, 956,005,744 B | 665 resources, 667,871,456 B |
| `srn_body_tex.hak` | 263 resources, 704,686,326 B | 263 resources, 176,204,022 B |
| `srn_2da.hak` | 7,677,339 B | unchanged |
| Private animation carriers | 108 (+ `srn_fa_h0`) | 0 (+ `srn_fa_h0`); 8 shared libraries over installed `a_fa`/`a_ba` |
| Textures above 1024 px | 81 | 0 |

The body HAKs fall from 1,660,692,070 B to 844,075,478 B (−49 %). Body parts, rigs, UVs, stature,
attachments, female posture and skin tone are unchanged.

## Validation state

| Gate | Status | Evidence |
|---|---|---|
| Motion (offline) | all 20 bodies pass; retained clips byte-exact; inherited within 0.1 mm / 0.05° | [libraries.md](libraries.md), [review.md](review.md) |
| Textures (offline) | 375 checked; mean ≤ 0.56/255 against 2K | [textures.md](textures.md), [review.md](review.md) |
| Packaging | `verify-assets` 931/931 (adopted and accepted contracts) | [packaging.md](packaging.md) |
| Read-only sweep | nothing new in 1.1.0; F1–F4 inspect, F5–F6 tooling | [review.md](review.md) |
| Client | stop-gate passed; textures equal; no regression | [client.md](client.md) |
| User acceptance | accepted 2026-10-14 | this checkpoint |
| Push / PR | approved 2026-10-14: this branch replaces PR #45 with one PR to `main` | the PR description |

## Open items

1. PR to `main`: it replaces PR #45. GitHub stopped processing #45 after its last push (stuck on `1bdcd2ae`).
   Keep `codex/phenomorpher-bodies-v1` as the 1.0.0 rollback anchor.
2. Phase 9, the toolkit upfit (generate and enforce), as a separate PR ([plan.md](plan.md)). Fold in the tooling findings:
   * F5: neck connectors;
   * F6: penetration on open bands;
   * the rig audits that read published binaries.
3. Stock clothing gaps on these rigs (pre-existing): convert the stock wardrobe through nwnarmory with the
   new phenotype profiles. This is separate work (user direction, 2026-10-14).
4. Client coverage not exercised: `salute` (no script trigger in this build), shield and longbow walking on
   Elf, Orc and Troll, the mounted and custom clips, and Human Large `sit`. All are inherited within tolerance offline.
