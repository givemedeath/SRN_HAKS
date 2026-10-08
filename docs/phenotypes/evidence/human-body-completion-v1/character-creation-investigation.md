# Why character creation could not be tested in the isolated fixture userdir

These findings come only from files and logs; no client was launched.

**Sources compared**
- **Isolated userdir:** `fixtures/hak-smoke/userdir`, after the user's Gate 4 session.
- **Normal userdir:** `<userdir>` (the normal NWN user directory).
  - Read only: `nwn.ini`, `settings.tml`, `logs\nwengineLog.txt`.
  - The CD key file was not read beyond its section names.

## What the files show
1. **The alias layout is fine.**
   - The client completed our `nwn.ini` `[Alias]` block with the same alias set as the normal userdir.
   - `MODULES` points at `userdir\modules`, which holds `srn_hak_smoke.mod`.
   - The engine log has the same key tables as the normal one, including `nwn_base_loc` with 0 entries (that is normal for English) and the same "undefined alias" warning.
   - So a missing userdir folder is **not** the cause.
2. **The New Game module browser is the NUI content index**, keyed by module UUID.
   - The normal `settings.tml` stores its state under `ui.nui.persistence."ContentIndex::Browser"`, with `selected_module = "ee172d7d-…"` and `collapsed_repositories`.
   - The modules are identified by UUID.
3. **Our fixture modules have no module identity.**
   - `target_fixture.documents()` writes `module.ifo` without `Mod_ID` or `Mod_UUID`. The decoded `packed-ifo.json` has only the 24 `Mod_*` gameplay fields.
   - Modules saved by the toolset carry these identities.
   - **Most likely cause of the empty "Local" list:** the content index skips, or cannot key, modules that have no identity.
   - `+TestNewModule` loads by resref, so it does not go through the index; that is why the fixtures themselves load.
4. **GOG sign-in fails in the isolated userdir** (`GOG: Authentication failed: 2`), and there is no `cdkey.ini` there. The normal userdir has `cdkey.ini` and no such failure.
   - It is plausible that the client hides licence-gated or online-backed lists (content repositories, some option lists) when sign-in fails. This is unconfirmed.
   - The CD key is a credential; it was not copied and must not be copied by an agent.
5. **The blank Options lists have no direct log evidence.**
   - The likeliest causes are (4) or the fresh first-run `settings.tml` / `nwnplayer.ini`. The isolated `nwnplayer.ini` holds only `[Server Options]`.
   - A missing-resource cause is ruled out: the base key tables load in full (113,483 entries).

## Proposed ways to test character creation (each needs your go-ahead to launch)
- **A — preferred, no browser needed.**
  - Derive a character-creation fixture from the HAK-smoke source whose `module.ifo` carries a fresh `Mod_UUID` and `Mod_ID`, packed and preflighted like the smoke fixture.
  - Start it with `-userdirectory <dir> +TestNewModule srn_hak_smoke`. Then open Character Creation from the in-module menu if this build offers it.
  - Otherwise use the main-menu New Game list, which should then index the module.
- **B — sign-in check.**
  - You copy your own `cdkey.ini` into a fresh isolated test userdir yourself, launch it, and check the module list and Options panels.
  - If the lists appear, (4) is confirmed.
  - The fixture tools must keep refusing to read or copy key files.
- **C — normal userdir.** Character creation in your normal userdir with the candidate HAK placed there. This changes your live install, so it needs explicit permission and a revert plan; the isolated route is preferred.

For each sex, check:
- creation previews the new body;
- palette 3/8 skin choices;
- default underwear dye;
- head selection with the new neck seam.

Then enter the module with the created character.

## Outcome (Gate 4 session, 2026-10-08)
- With the identity fields added (`hak-chargen-v1`), the New Game module list was **still empty**, and so was the **Official** tab. The empty browser was therefore **not** caused by the missing module ID.
- The most likely cause is now the failed GOG sign-in / missing `cdkey.ini` in isolated userdirs (finding 4 above). This is not proven.
- The `Mod_ID` fix (`target_fixture.module_identity`, commit `de58007`) is harmless and stays: fixtures now match the stock module.ifo identity fields.
- **Character creation was tested and passed** by launching straight into the module's character select, without the browser:
  `nwmain.exe -userdirectory "<hak-chargen-v1\userdir>" +LoadNewModule srn_hak_chargen`.
  - A female Human Fighter (default skin) and a male Human Fighter were created and entered the game.
  - With their starting outfits removed, both showed the LEAN bodies with cream (undyed) garments.
  - Heads and necks were fine.
  - Evidence: `gate4-v1/client-session-v2.json`.
