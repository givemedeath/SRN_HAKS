# Human body asset records: superseded

The PhenoMorpher body release replaced the Human body files in `srn_body`:
* 1.0.0, from PR #45, merged through #49;
* 1.1.0, merged as #49 at `9e6d507`.

These records describe the earlier Human releases and no longer match the files on `main`:

| Record | Release | Pins that still match (2026-10-15) |
|---|---|---|
| [human-female-assets.json](human-female-assets.json) | Human female v1 (#42) | 0 of 70 |
| [human-male-assets.json](human-male-assets.json) | Human male v1 | 0 of 72 |
| [human-male-v2-assets.json](human-male-v2-assets.json) | Human male v2 (#42) | 0 of 70 |

They stay unchanged as historical evidence, and so does
[`tools/phenotypes/verify_published_body.py`](../../tools/phenotypes/verify_published_body.py).
That verifier checks those records, so run against `main` it reports the replacement as a mismatch.

The current authority for every published body file is the PhenoMorpher contract
[`docs/phenomorpher/game-ready-assets.json`](../phenomorpher/game-ready-assets.json) (1.1.0). Check it with
`verify-assets` and `verify-runtime` (see the [toolkit README](../../tools/phenomorpher/README.md)).
Restore an earlier Human release from its merge commit or from the archives, never by editing these records.
