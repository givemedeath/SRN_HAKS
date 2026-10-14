# Pre-publication code review

The toolkit changes were manually reviewed before the PR was opened, without
subagents or game-client use. This covers the public API/CLI, input enumeration,
shared-launch optimization, package boundary, test selection and source adoption.
It is an implementation review, not an independent external review or anatomy approval.

## Findings resolved

- Source-attribute files used by scene export were missing from the consumed input
  declaration. They are now frozen alongside motion files and checked before fitting.
- Root-relative nested recipe paths could be inspected before root containment was
  checked. Enumeration now rejects escapes before reading the nested file.
- Replay and clothing commands did not require every nested input to belong to the
  launch snapshot. They now check manifest, recipe/body and leaf pins before dispatch.
- The doctor imported a historical generator with external height settings. Only its
  three required measurement/file utilities are retained; generation services and
  historical height defaults are excluded.
- Native stock female duplicate leaf attachment dummies prevented assembly. Both are
  retained under distinct internal identities; ambiguous mesh, joint or parent names
  remain rejected.
- Duplicate packaged legacy names and build artifacts confused focused test selection.
  Imports and helper literals now resolve in context, generated package directories
  are excluded and filename lookup uses one indexed directory inventory.
- Source code and installed-wheel tests now share the portable input enumerator;
  package tests do not depend on a repository runner beside an installed wheel.
- Native inspection now labels its third decoder return correctly as a source hash
  pin, rather than unavailable attributes.

- Package source line endings are fixed to LF and staged source hashes are checked
  against the lineage ledger, so Windows checkout normalization cannot invalidate it.

## Evidence and remaining limits

Regression tests cover each resolved finding, complete Human identity CLI output,
source attribute preservation, six-clip motion policy, connector coverage, rejected
waist corners, nearly extended knees, unreachable targets and loop continuity.
The validation receipt records full existing helpers, toolkit tests, isolated wheel
installation and real native/measurement/replay/clothing smokes.

No unresolved blocking implementation finding remained at publication. The tool
still produces offline proposals. Textured baking, native export, weighted clothing,
client validation and visible anatomy approval retain their separate gates. The
body PR remains independent and unmerged for the user's requested follow-up fixes.

## PR review follow-up

The external PR review identified a mismatched ASCII encoding in attribute reading
and corrupted Unicode documentation. ASCII MDL attributes now use CP1252, matching
the existing NWN geometry decoder; regression coverage exercises an accented
material name and a Windows-1252 comment through the public API and CLI. The
intended tolerance signs and gate range are restored as UTF-8. See the additive
follow-up validation receipt; the original release receipt remains unchanged.
