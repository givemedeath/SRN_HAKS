# Contributing

Contributions arrive through pull requests to `main`.

Before opening a pull request:

1. Confirm that every imported asset is permitted for public redistribution and record the batch in
   `PROVENANCE.md`. No license found means do not copy.
2. Keep pack contents flat and register each pack in `hakbuilder.json`.
3. Allocate TLK entries with `tools/Allocate-StrRef.ps1`; do not renumber or reuse IDs.
4. Keep `.2da` resources in `srn_2da` and do not renumber existing rows.
5. Run `pwsh ./tools/Test-Repository.ps1 -AllPacks`.

Internal resource stems must match `[a-z0-9_]{1,16}`. File extensions must also be lowercase. A
resource larger than 15 MiB needs a documented size exception. Files at or above GitHub's 100 MiB
limit are not accepted.

Pull requests that allocate StrRefs must be brought up to date with `main` before merge. Generated
files under `output/` and downloaded tools under `.tools/` must never be committed.
