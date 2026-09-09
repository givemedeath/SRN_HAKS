## Summary

Describe the content or tooling change and the consuming project(s).

## Rights and provenance

- [ ] I reviewed the rights for every added or changed asset.
- [ ] I updated `PROVENANCE.md` for each content batch.
- [ ] I preserved all required third-party license and attribution notices.

## Content integrity

- [ ] `pwsh ./tools/Test-Repository.ps1` passes locally.
- [ ] New ResRefs are lowercase, valid, and at most 16 characters.
- [ ] TLK IDs were created with `Allocate-StrRef.ps1` and this branch was current with `main` first.
- [ ] Any intentional cross-HAK override is declared in `hakbuilder.json`.

## Downstream testing

List the module/client/server checks performed, or explain why they are not applicable.
