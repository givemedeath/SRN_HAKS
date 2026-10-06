# Head and gallery checkpoint — 2026-10-05

Stopped at the user's request: “record a checkpoint and stop when you can”.
Completed source is committed and pushed as
`6ba7730bccd31a356257753967de4b58632ef232` on `codex/head-pipeline-pilot`.
[PR #40](https://github.com/givemedeath/SRN_HAKS/pull/40) remains a draft targeting
`main`. Its description still needs the new male heads and gallery scope.

## Completed

- Six male candidates across all five races pass native validation, each at
  19,000 triangles: Human natural/cyberware, Elf, Dwarf, Orc and Troll.
  The Elf female donor still awaits a female body contract.
- Full skull/jaw geometry is retained. Only actual holes are capped; no neck
  trimming or tapering is applied. Body resources and fit matrices are pinned.
- Meshy spend is settled at **345 / 405 credits**, with no reservations outstanding.
- New Elf/Dwarf/Orc native palette and standing/motion evidence is reviewed and
  saved in the portable catalog and evidence manifest. Client acceptance is pending.
- Head 36, shared helper 18, phenotype 175 and gallery 5 tests pass. Full repository
  verification rebuilt/reopened all 26 packs; item-import regressions pass.
- Gallery source, scripts, portable configuration and refresh wrapper are committed.
  Its compact native smoke compiles four scripts, packages/decodes the module,
  verifies payloads and checks byte-safe door aliases and Windows-1252 labels.

## Explicit local resume bindings

Ignored checkpoint: `output/heads/male-expansion-v1/local/checkpoint-head-gallery-stop-v1.json`.
Head ledger: `output/heads/male-expansion-v1/local/resume-ledger-male-expansion-v1.json`.
Current session: `output/heads/male-expansion-v1/session-envelopes-v1`.
Selection: `output/heads/male-expansion-v1/local/working-selection-v7.json`.
The ledger pins the session's last event, migration evidence, native banks and fixtures.
Human/Troll history remains bound by the earlier derived-male ledger.

Gallery binding: `output/gallery/local/binding-v2.json`, including Human/Troll
plus all three new male ambient fixtures. The full attempt
`output/gallery/run-v6` was stopped during input verification, before launching
the child builder. It produced an input manifest but no launch completion receipt,
full build report or newly built gallery module. Preserve this attempt as history.
Compact native smoke receipt:
`output/heads/male-expansion-v1/local/gallery-native-smoke-v4-launch/launch.json`.

## Remaining work

1. Recheck the explicit binding and input hashes; start the full gallery build in
   a **fresh** output directory. Do not reuse `run-v6`. Refresh the binding if
   production HAKs or the TLK have been rebuilt since this checkpoint.
2. Verify all 26 HAK payloads, the combined candidate overlay and module payload;
   save `output/srn_gallery.mod` and `output/srn_gallery_test.hak`, then record a
   portable validation report with actual counts and hashes.
3. Update the existing PR description and inspect CI. Runs
   [37400009296](https://github.com/givemedeath/SRN_HAKS/actions/runs/37400009296)
   and [37400009297](https://github.com/givemedeath/SRN_HAKS/actions/runs/37400009297)
   were in progress when stopped; final CI success has not been established.

No interactive client test or production acceptance is claimed. No further paid
generation is needed for these three male heads. Source masters remain in the
primary checkout's ignored bank; no checkout has been retired or deleted.
