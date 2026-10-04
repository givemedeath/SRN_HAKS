# Purpose-built Human male shin pair validation

Validated in the NWN:EE v89.8193.37-17 client on 2026-10-03 UTC.
The selected v3 donor and mirrored right shin complete this part's first-round
generation, geometry, native packaging and actual client checks. No major
open knee/ankle cap, floating shin or new opposite-side articulation defect
was visible in the recorded samples. This assessment covers the shin pair;
it does not complete the Human body or settle the user's subsequent pelvis
skin-color report.

Read [the selected process](phenotype-purpose-built-shin-process.md),
[fitting proof](purposebuilt-shin-fitting-pilot.md) and
[checkpoint](phenotype-shin-checkpoint.md) for lineage and continuation.
Pilot paths below are relative to `output/phenotypes/purposebuilt-shin-pilot-v1`.

## Selected assets and real package

| Input | SHA256 |
| --- | --- |
| Left `left-shin-connectors-v3-monotone/refined-local.glb` | `bde4b16194010cd42ad40d282512e1189c7c992a5ab6df06d0d24c27c5123ee7` |
| Right `right-shin-v3-mirror-v1/mirrored-local.glb` | `7efe4b5a9e85bacd1b8d23958c96fe4518e186363f5c6c8b91aed5b17b3f4e24` |
| Native left MDL | `3d4eb3c94fb8ce73114c5293e70a5edf9bf7647b32a46357e9abd9fb99e4ff63` |
| Native right MDL | `282e55060fb333789ad8b6670d5fe83d9153df67be5756829d9b07195eb278a9` |
| Paired isolated HAK | `0e9b8ca4b6878dea616254440a4afa31554c91ce786c752b0b703aee10982b4e` |
| Idle-front/review module | `477048e576b1bf0e42d8b88f213d6d239238c504b585a8e2acb143e92becd0f0` |

The 68-resource HAK replaces exactly the accepted chest, pelvis, thighs and
new shins. Its comparator and fixture resources are test-only. All 18 native
neighbour dependencies from the completed thigh baseline remain byte-exact.
Actual stock male controllers, attachment transforms, height 1.9339157 m,
stock neck/head/arms/feet and equipment identity scale are verified. Overrides
are empty; no generated poses, rig or animation replacements are packed.

Both shins use original 2K maps, normal strength 1 and authored corner normals.
Separate native shading audits decode ordered FLOAT32 positions/normals/UVs
and valid compiler-derived tangent/sign arrays. The independent pair index
`selected-v3-pair-independent-index-v1/index.json`, SHA256
`0c9662c50f3cb2a5de0365efd6b981596daa7ddff9c942be14f7d5d6cfeb729b`,
verifies closed manifold meshes, winding, zero genuine crossings, zero
negative authored-normal corners, exact UV/map retention and measured mirror
serialization tolerances. Each shin has 50,000 triangles. Finite contact rays
and pose images retain their scope; they are not every-frame seam proofs.

## Actual client checks

The foreground `human_male_fit` actor has the accepted custom neighbours and
new shins; `stock_human_male_fit` provides the installed stock comparator.
Screenshot receipts bind actual HAK/MOD/build hashes, returned window and
save time. The API supplies no separate capture timestamp. Actual screenshots
are JPEG: early files retain their original `.png` names and byte hashes;
later schema2 records use `.jpg` and explicit encoding. Do not rewrite frozen
captures to hide that format correction.

| Check | Actual fixture/evidence | Observed result |
| --- | --- | --- |
| Donor first | `client-left-v3-idle-front-v1`, `client-left-v3-idle-side-v1` | Full-join front/maximized and side frames show covered ends without the rejected v2 cuff/flange. The first small front frame crops feet and cannot prove ankle coverage. |
| Pair idle | `client-pair-v3-idle-{front,side,rear}-v1` | Both knees/ankles and feet visible; retained muscular calves, coherent mirror, no major exposed cap. Small contour changes at moving boundaries remain. |
| Deep flexion | `client-pair-v3-crouch-side-v1`, `client-pair-v3-kneel-side-v1` | Visible shin joins stay connected. Client kneel uses actual WORSHIP; it is distinct from the offline grounded-kneel sample. Previously accepted pelvis/proximal-thigh crouch quirks remain unchanged. |
| Held casting | `client-pair-v3-casting-front-v1` | Two actual CONJURE1 hand phases with covered joints in offset stance. Finite samples, not a full-cycle recording. |
| Walking/turns | `client-pair-v3-walk-side-v1` | Outward and return-stride images, lifted rear foot, repeated 24 m routes and turns corroborated by position/cycle logs. No major open joins seen. Wheel zoom-out preserves coherent gameplay silhouette. |
| Running/turns | `client-pair-v3-run-side-v1` | Planted-foot and raised/flexed-knee strides, repeated routes/turns in logs; visible joins remain assembled. |
| Real gameplay/transitions | `client-pair-v3-gameplay-v1` | Actual unarmed punch, spell107 events, damage, prone death and resurrection/restarted combat. Full-join death frame supersedes the earlier cropped nearer foot. No shin displacement after resurrection. |
| Skin palette | `client-pair-v3-palette-front-v1` | Palette8 recolors both shins and stock feet consistently with adjacent thighs; dark underwear remains fixed. Compared with actual palette3 front evidence. This is not acceptance of pelvis skin continuity. |
| Low stock boots | `client-pair-v3-boots-side-v1` | Actual stock Foot004 only, new shin001 still visible; both low boot edges meet without gross gaps. Worn-item log confirms equipment. |
| Stock full armor | `client-pair-v3-armor-front-v1` | Actual outfit worn with waist/hips/legs covered and stock identity scaling. Selects stock shin013, so proves coverage/ownership rather than exposed custom-shin appearance. |

Actual client debug FPS is approximately 59–61 in the small flat fixture,
including running and gameplay. No fatal client error occurred in this pass.
This is practical inspection of a few actors with adaptive VSync, not a
crowded-server performance budget or uncapped benchmark. Full weapon, robe,
every boot style, every skin index and every animation frame remain broader
whole-body coverage. Original GLTF AO/MR, sampler and double-sided flags are
not all translated by the narrow native adapter.

Every tested camera is unlocked. Wheel zoom works in idle and movement; a
single Left key did not show an observable orbit, so it is not a proven pan
test. No camera locks or limits that pin pitch/distance are introduced.

## Evidence and remaining boundary

`paired-v3-validation-fixture-batch-v1/index.json` freezes the eleven final
fixture commands, actual package audits and hashes; `complete-proof.json`
binds unchanged 2K maps and stock equipment inputs. The original paired
front and fresh final review fixture have the same HAK/MOD bytes.
`root-tool-verification-v1/proof.json` records 29 passing focused tool checks;
actual native/package regressions remain separate from client observations.
`selected-v3-client-evidence-index-v1/index.json`, SHA256
`bcb274a710d67e29903ffc973f64d76c7a691d108f38e581d454e73926eeb376`,
binds 15 fixtures and 26 actual images. `verification.json` SHA256
`3e8a0820925f9879d80fc8d558c98993ffc85864f1d79a4215743c004c9119b6`
verifies those references. The independent review rehashed 196 files and
confirmed all 15 package pairs and screenshot associations, with 28 immutable
final log files from 14 exited fixtures. Current live logs are excluded.

The user subsequently noticed a pelvis skin mismatch. A closer actual front
diagnostic is saved as
`client-pair-v3-review-front-v1/client-evidence/pelvis-skin-close-before.jpg`.
The exposed pelvis strips appear flatter and warmer/lighter than adjacent
thighs in that view. The separate material correction is now tested and accepted
by the user; see [the selected material record](phenotype-pelvis-skin-continuity.md).
Shin geometry, accepted body geometry and fitting are unchanged. The corrected
HAK changes only the pelvis PLT; the frozen shin receipts and images remain
unchanged. No new body part starts automatically.
