# Armor Toolkit (tools/armorkit)

## Overview
The `tools/armorkit` package is the foundation for modular clothing, armor, headgear and accessory parts on the 20 SRN bodies: a part registry, the generator for the twelve `parts_*.2da` tables, the measured seam contract and head envelopes, and an isolated client fixture builder. It follows [the armorkit plan](../../docs/armorkit/plan.md); evidence for engine behaviour is in [the spike record](../../docs/armorkit/spikes.md) and the measurements are explained in [the seam contract](../../docs/armorkit/seam-contract.md). Generation, splitting, fitting and publication are later phases and are not here yet. Nothing in this package writes into a pack.

## Interface
- `[__main__.py:main]` - Command line: `registry` (validate, write the SR_NWN handoff file), `tables` (generate and check the parts tables), `measure` (seam contract and head envelopes from pack folders), `fixture` (build and optionally run a client fixture).
- `[registry.py:validate]` / `[registry.py:load]` - Check a registry document (`srn-armorkit-registry`, schema version 1) and return its parts ordered by slot and number; `publish=True` also requires all 20 bodies.
- `[registry.py:SLOTS]` - Per slot: parts table, model tokens, the `xArmorPart_*` item fields and `ITEM_APPR_ARMOR_MODEL_*` indices.
- `[registry.py:model_name]` / `[registry.py:model_names]` / `[registry.py:texture_names]` - Resource names a part implies: `p<m|f><race><phenotype>_<slot><number>`.
- `[registry.py:block]` - The family a number's block belongs to (300-2999 accessory, 3000s civilian, 4000s workwear, 5000s corporate, 6000s security, 7000s runner, 8000s gang, 9000+ open).
- `[registry.py:handoff]` - The registry with derived table, item-field, model and texture names, as SR_NWN consumes it.
- `[tables.py:generate]` / `[tables.py:generate_all]` - Table text from stock text and registry parts: stock rows kept, gaps padded, live rows nulled.
- `[tables.py:check]` - Fails on a gap, a duplicate, a changed stock row, a registry part without a live row, or a live row no part owns.
- `[seams.py:JOINTS]` - The eight joints: over slot, under slot and the bones that define each plane.
- `[seams.py:load_contract]` / `[seams.py:envelope]` / `[seams.py:mixes]` - Read the frozen `seam-contract.json`, get a tier's per-direction envelope at a joint, and test whether two parts mix cleanly there.
- `[seams.py:section]` / `[seams.py:ring]` / `[seams.py:swing]` / `[seams.py:minimum_overlap]` - Plane sections, radial rings, joint swing and the overlap rule the contract is built from.
- `[measure.py:seam_contract]` / `[measure.py:head_envelopes]` - Rebuild the two data files from `srn_body`, `srn_head` and extracted stock animation models.
- `[measure.py:clearance]` - How far a worn part's ring stands outside the body ring at a joint.
- `[client_fixture.py:build]` - Write a fresh user directory holding a fixture hak, the packs under test and a module with scripted actors and camera shots.
- `[client.py:run]` - Start the game on a built fixture, capture the window after each shot line, stop that client and return log lines and captures.

### Subdirectories & Data Assets
- `examples/registry.json` - A small valid, publishable registry used by the tests.
- `seam-contract.json` - Seam contract version 1, measured on the c7 Human Fit bodies.
- `head-envelopes.json` - Outer bounds of the published heads per race and gender, in head-bone space.

## Invariants
- `[registry.py:validate_part]` - Part numbers start at 300; stock rows 0-200, stock models to 255 and the 256-299 buffer are never reused. Numbers stop at 65535 (the item field is a word) and every model name is at most 16 characters.
- `[registry.py:validate_part]` - A number in a family block carries that family's tag; the chest is always a separate male and female cut; a fitted part declares a tier 0-3 at each of its joints; logos sit only on shoulder parts and neck-slot lanyards; the skin channel is used exactly when skin is exposed.
- `[registry.py:validate]` - One part per slot and number; a number never belongs to two sets.
- `[tables.py:generate]` - Stock rows are copied byte for byte (201 rows, 39 for `parts_robe`); live rows are `COSTMODIFIER 0`, `ACBONUS 0.00`; padding rows are `****` in every column; rows count from 0 with no gaps up to the highest part number.
- `[seams.py:validate_contract]` - The part nearer the torso lies over the other and the chest lies over everything it touches; envelopes and minimum overlaps never shrink as the tier rises; every joint is measured on both Human Fit bodies.
- `[seams.py:mixes]` - Two parts mix cleanly at a joint when the over part's tier is at least the under part's.
- `[client.py:stop]` / `[client.py:start]` - Only a client this module started is stopped, by process id; a client that is already running blocks the run.
- `[client_fixture.py:build]` - The game install is an explicit argument; no machine path is stored in the package.

## Side Effects
- `[client_fixture.py:build]` - Creates a fresh output folder (user directory, staged resources, module sources) and resolves the pinned Neverwinter utilities through `tools/phenotypes/tool_runtime.py`, which registers the run under `.tmp/tool-dependencies`. Packs are hard-linked into the user directory where the volume allows.
- `[client.py:run]` - Starts and stops `nwmain.exe` on the fixture's own user directory, writes `settings.tml` there on first use and saves window captures.
- `[__main__.py:command_tables]` / `[__main__.py:command_measure]` - Write only to the output folder given.

## Verification
- Run: `<bundled-python> -B tools/test_impact.py --changed tools/armorkit/registry.py --run`, or `<bundled-python> -B -m unittest discover -s tools/armorkit -t .`
- `test_measure.py` reads `srn_body` and `srn_head`: it fails when a locked Human Fit body model changes or a recorded head is removed, which is the signal to re-measure.
