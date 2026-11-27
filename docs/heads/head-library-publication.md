# Publishing head-library heads

`tools/headbatch/publish_library.py` moves client-reviewed heads from a headbatch workspace into `srn_head`. It reruns
nothing. Each head's files are the exact MDL and PLT bytes its final private-client review loaded, taken from that review
session's trial HAK. Publication needs the user's authorization, as before; the tool only makes the steps repeatable.

Both published library records reproduce with it: [head-library-40-v1](head-library-40-v1.md) and
[head-library-trolls-v1](head-library-trolls-v1.md) (manifest content, galleries and resources, byte for byte).

## Commands

Run it with the bundled workspace Python (never the Windows Store `python` shim) and Pillow on `PYTHONPATH`.

| Command | What it does |
|---|---|
| `stage --workspace W --repo R --name NAME --created DATE --prefix troll-` | Publishes every checkpointed head whose name starts with the prefix, or `--heads a,b,c`. Writes `srn_head/<slot>.mdl` and `.plt`, `docs/heads/evidence/NAME/<slot>-client.jpg` and `docs/heads/NAME.json`, plus `OUT/NAME-draft.md`. `--dry-run` writes the repository files under `OUT/repo` instead. |
| `verify --hak output/srn_head.hak --manifest docs/heads/NAME.json [--manifest ...] [--revision RECORD ...]` | Checks that a built HAK holds every resource of the manifests byte for byte. A `--revision` record (rows of `path`, `fromSHA256`, `sha256`, `bytes`) names later bytes that replace a pin; the manifest stays as written. The Human male heads `pmh0_head086` to `092` were rescaled by `docs/phenomorpher/neck-c8/release-1.6.0.json`, so pass it with `head-library-40-v1.json`. |

## What `stage` checks

For each head it:

1. Takes the head's row from the newest workspace checkpoint that lists it (`runtime/batch-NN-checkpoint-M.json`). The
   batch number comes from the file name.
2. Follows the row's client session to its trial and finds the native source the trial packed: a native attempt
   (`heads/HEAD/run/native/attempt-NN`) or a client fit variant (`trials/fit-variants/TRIAL/HEAD`).
3. Refuses unless the slot's MDL and PLT are in exactly one trial HAK and equal the native source's bytes.
4. Builds the gallery from the session's captures: four three-quarter views, a motion frame and the second look's front.
   It crops each view with the boxes in `tools/headbatch/library-crops.json` (per head family, for example
   `troll-male`; `default` for the rest) and reduces them; it never edits textures or geometry.

The manifest's triangles and material come from the export receipt the native attempt pinned by hash (a fit
variant without a native receipt is read only when the head has one export attempt; otherwise name its attempt with
`reviewedNativeAttempt`). A dry run warns where the real stage would refuse an existing manifest or gallery. Nothing reaches the repository until every head has resolved
and every target path is checked. Gallery JPEG bytes depend on the Pillow version, so restaging an existing
publication needs the Pillow that made it. An existing resource with different bytes refuses, and so
does an existing manifest of the same name. The manifest refuses to hold a local path.

## Inputs the checkpoint may lack

`--overrides FILE` takes `{head: {session?, reviewNotes?, reviewedNativeAttempt?}}`. PR 177 used it for three Human male
heads whose final review was a fit-variant session the checkpoint did not name; `reviewedNativeAttempt` names the
native attempt a fit variant was made from and refuses for a trial that packed a native attempt itself. `--notes` sets the manifest's
top-level note (for example, how `designSubmissions` was recorded). `--review` sets who reviewed the heads and on whose
authority; the default is the operator review the user delegated. An override for a head that is not being staged, or
an unknown override key, refuses. A session's relative `trial` path is read from the workspace, and every crop box
must be four non-negative integers.

## After staging

1. Write the record from `OUT/NAME-draft.md`. The draft has the slot table, galleries and loading note. Write the
   user-accepted exceptions and known limitations from the manifest's `reviewNotes`, quoting the user.
2. Add a `PROVENANCE.md` entry.
3. Rebuild and verify: `Test-Repository.ps1 -ChangedSince origin/main`, then `publish_library.py verify` against every
   library manifest, with every revision record of a published head (`--revision`).
4. Ask the user whether to re-measure the armorkit head envelopes (`python -m tools.armorkit measure --only heads`). Both
   library publications did, by the user's decision.

## Crop boxes

Client tours frame heads differently by race. The Troll tours at 1536×864 frame heads off-centre, so their boxes were
measured on four heads per sex. For a new family, build a dry run, look at every gallery, and add boxes to
`library-crops.json` where a head is cut off.
