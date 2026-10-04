# Phenotype worktree disk-space assessment

Assessed 2026-10-03 after selecting both regenerated feet offline. Nothing was
deleted, moved or archived. The user requested evaluation; removal is a separate
action. Worktree: `D:/srwt/codex/f0b3/SRN_HAKS`.

## Authorized deletion completed

The later user instruction authorized deleting verified-safe items. Execution
completed on 2026-10-03: **140 duplicate HAKs and 143 regenerable caches** removed,
**22,966,562,064 logical bytes (22.97 GB)** in 283 files. All 17 HAK survivors,
selected geometry/materials and other protected inputs passed fresh pre/post
hash checks (71 protected pins). No relevant asset process was active; deletion
used individually verified literal file paths within this worktree.

All **165 review scenes remain** because they require a verified archive first.
The orphan cache also remains. Source masters, reference images, textures,
receipts and screenshots were retained. Native/client testing remains pending.

Execution receipt:
`output/phenotypes/worktree-cleanup-2026-10-03-v1/execution.json`, SHA256
`a84ce245490da59e5a1dba4e135b615bacc1cc420ffaa9930403f1c5da445cb8`.
The same directory holds `recovery-plan.json` (exact copy of the verified plan)
and `executed-helper.ps1`. Its removal entries record each old path/hash and
`restoreFrom` survivor. Preserve this map and every survivor. To replay a
historical fixture/audit, verify its survivor hash, then copy it back to the
recorded original path. Directory trees were left in place; no recursive
directory deletion occurred. Python caches regenerate from their retained source.

Drive free space rose from 45.33 to 74.95 GB during execution. That observation
may include other disk activity; the verified removal size is 22.97 GB.
The tables below describe the **pre-deletion assessment**, not remaining copies.

The scan measured **102.31 GB** of logical file bytes in 53,641 files. GB means
1,000,000,000 bytes. Allocated disk blocks, compression and deduplication savings
were not measured. Shared Git/control metadata and junction targets were skipped;
the original reference folder and installed Comfy/model libraries are outside scope.

## Recommended cleanup order

| Category | Potential worktree savings | Conditions |
| --- | ---: | --- |
| Repeated HAK payloads | **22.96 GB** | 140 byte-identical copies across 17 hash groups. Keep each recorded survivor and the exact path/hash recovery map. Restore historical paths before replaying their fixtures/audits. Check live use before removal. |
| Derived Blender review scenes | **19.39 GB** | 165 `.blend` files. Archive exact bytes with verified hashes and tested recovery before removal. They contain packed maps/models and are referenced by review receipts. Retain current v5 scenes locally until the bulk client pass unless their verified archive is readily recoverable. |
| Regenerable Python caches | **2.54 MB** | 143 untracked `.pyc` files with matching source verified. Retain one orphan cache whose matching source is absent. Check live use before removal. |

The HAK and scene categories are disjoint: together they offer **42.35 GB** of
conditional savings, about 41% of measured logical size. Review-scene savings
require storage elsewhere or a verified compressed archive; an uncompressed
move elsewhere on the same volume does not free that volume. No compression
ratio is promised. HAK deduplication keeps one full historical package per hash
without regeneration or losing unique package bytes.

The exact machine-readable plan is
`output/phenotypes/worktree-space-assessment-2026-10-03-v2/cleanup-plan.json`, SHA256
`1206b96ee455635c91d289de80382e0279fcbaba94a2ef207b4f4fcd3f6931ed`.
Its parent `assessment.json` is SHA256
`4b578a3ff6d4da7eb044e795ce5b1dc64418dac2bc5f6abcd7a2b3211e1107ba`.
The plan records every HAK survivor/copy, every scene and qualified cache, and
pins the selected foot receipt. HAK groups were actually SHA256-hashed, not
inferred from filenames or sizes. No current v5 foot or selected-runtime HAK is
in the proposed duplicate-removal list. The scanner source executed for the
inventory is frozen alongside it; the qualification step excludes the orphan cache.

Historical receipts still reference the original paths. Their bytes are not
rewritten by this plan. After a purge, audits that read removed paths will require
restoration from the mapped survivor/archive. Do not claim uninterrupted replay
until a recovery check succeeds. Literal reference counts also include inventory
records; they are conservative hints, not a complete dependency graph.

## Largest folders

| Folder under `output/phenotypes` | Logical GB | Included review-scene GB |
| --- | ---: | ---: |
| `human-male-material-repair-v1` | 31.96 | 0 |
| `purposebuilt-shin-pilot-v1` | 21.64 | 5.95 |
| `purposebuilt-thigh-pilot-v1` | 13.79 | 1.11 |
| `purposebuilt-foot-pilot-v1` | 8.40 | 4.28 |
| `purposebuilt-pelvis-pilot-v1` | 7.71 | 1.68 |
| `purposebuilt-foot-regeneration-v2` | 5.92 | 2.17 |
| `purposebuilt-foot-orthographic-v5` | 5.64 | 2.15 |
| `purposebuilt-torso-pilot-v1` | 3.66 | 1.43 |

Folder sizes include selected sources and historical evidence; **do not delete
whole folders** based on this table. Old foot folders still supply stock guides
and comparisons. Material repair, shin and thigh folders supply effective
accepted resources and their compiler/provenance dependencies.

## Retain

Keep the current v5 source masters, normalized references/prompts, fit/refinement
ancestry, corner archives, selected geometry, final maps, manifests, offline HAK,
audits and screenshots. Preserve the accepted six body parts/materials and actual
stock bank, supermodel and animation references. Preserve historical unique
masters and receipts: Comfy generation cannot be recreated merely by rerunning a
seed. Keep client evidence and saved state; this assessment targets duplicated
HAK files, not entire client user directories. Keep tracked files, unrelated dirty
work and unknown experiments.

Other generated `.tga`, `.plt`, `.mdl` and `.glb` files remain retain/archive-first.
This pass does not establish which individual copies those pipelines can safely
lose. Ignored/untracked status alone does not make an asset disposable.

## Repeat the assessment

Use a fresh output directory and the bundled workspace Python. This tool reads
and hashes; it has no deletion operation.

```powershell
$taskPython = 'C:/Users/benco/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
& $taskPython tools/phenotypes/assess_worktree_space.py --root D:/srwt/codex/f0b3/SRN_HAKS --output output/phenotypes/worktree-space-assessment-next --duplicate-extension .hak
```

Before any future recursive purge, verify each absolute target remains in this
worktree, recheck survivor hashes and active use, and preserve the recovery map
outside the directories being purged. Use native PowerShell literal paths for
Windows removal. The executed cleanup above removed only listed individual files.
