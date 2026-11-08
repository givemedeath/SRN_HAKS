# Troll head publication and gnome-slot replacement

The five newly approved heads join the existing 35 Troll heads. All 40 now occupy pmg0_head001–020 and pfg0_head001–020, ordered by their previous slot within each sex. This overrides every installed base-game gnome head (male 001–013, female 001–009).

Keep srn_head above srn_body in module HAK priority. The four slot-001 resources intentionally override the body pack fallback heads; hakbuilder.json declares those overlaps. The body assets are unchanged.

**Saved-character compatibility:** Appearance_Head stores a numeric index. Apply the table below according to the character sex and gnome/Troll model family when migrating existing characters or blueprints. Otherwise an old index can select a different head or a missing resource. No saved characters or server vaults are modified by this change.

The [portable manifest](troll-head-reindex-v1.json) records all source/output hashes, exact user publication words and changed native string offsets. Historical design, fit, client and palette evidence keeps its original slot labels.

## Slot mapping

| Previous model | Published model | Design |
|---|---|---|
| pmg0_head015 | pmg0_head001 | Published pmg0_head015 |
| pmg0_head016 | pmg0_head002 | Published pmg0_head016 |
| pmg0_head017 | pmg0_head003 | Published pmg0_head017 |
| pmg0_head018 | pmg0_head004 | Published pmg0_head018 |
| pmg0_head019 | pmg0_head005 | Published pmg0_head019 |
| pmg0_head020 | pmg0_head006 | Published pmg0_head020 |
| pmg0_head021 | pmg0_head007 | Published pmg0_head021 |
| pmg0_head022 | pmg0_head008 | Published pmg0_head022 |
| pmg0_head023 | pmg0_head009 | Published pmg0_head023 |
| pmg0_head024 | pmg0_head010 | Published pmg0_head024 |
| pmg0_head025 | pmg0_head011 | Published pmg0_head025 |
| pmg0_head026 | pmg0_head012 | Published pmg0_head026 |
| pmg0_head027 | pmg0_head013 | Published pmg0_head027 |
| pmg0_head028 | pmg0_head014 | Published pmg0_head028 |
| pmg0_head029 | pmg0_head015 | Published pmg0_head029 |
| pmg0_head030 | pmg0_head016 | Published pmg0_head030 |
| pmg0_head033 | pmg0_head017 | Approved Troll male (new) |
| pmg0_head034 | pmg0_head018 | Breakwater (new) |
| pmg0_head035 | pmg0_head019 | Ballast (new) |
| pmg0_head036 | pmg0_head020 | Vesper (new) |
| pfg0_head010 | pfg0_head001 | Published pfg0_head010 |
| pfg0_head011 | pfg0_head002 | Published pfg0_head011 |
| pfg0_head012 | pfg0_head003 | Published pfg0_head012 |
| pfg0_head013 | pfg0_head004 | Published pfg0_head013 |
| pfg0_head014 | pfg0_head005 | Published pfg0_head014 |
| pfg0_head015 | pfg0_head006 | Published pfg0_head015 |
| pfg0_head016 | pfg0_head007 | Published pfg0_head016 |
| pfg0_head017 | pfg0_head008 | Published pfg0_head017 |
| pfg0_head018 | pfg0_head009 | Published pfg0_head018 |
| pfg0_head019 | pfg0_head010 | Published pfg0_head019 |
| pfg0_head020 | pfg0_head011 | Published pfg0_head020 |
| pfg0_head021 | pfg0_head012 | Published pfg0_head021 |
| pfg0_head022 | pfg0_head013 | Published pfg0_head022 |
| pfg0_head023 | pfg0_head014 | Published pfg0_head023 |
| pfg0_head024 | pfg0_head015 | Published pfg0_head024 |
| pfg0_head026 | pfg0_head016 | Approved Troll female (new) |
| pfg0_head032 | pfg0_head017 | Published pfg0_head032 |
| pfg0_head090 | pfg0_head018 | Published pfg0_head090 |
| pfg0_head091 | pfg0_head019 | Published pfg0_head091 |
| pfg0_head092 | pfg0_head020 | Published pfg0_head092 |

## Validation

All 40 models were decoded before and after the bounded string-field rename. Reverse renaming reproduced every original MDL byte; every PLT is byte-identical. The approved male pair uses its final, enlarged client-reviewed native output. All 46 non-Troll resources are unchanged. The rebuilt srn_head.hak contains exactly the 126 expected resources and hashes.

An isolated trial loaded this rebuilt HAK above the body pack. Its client log passed all 40 expected head indices and palette assignments. This was a slot-selection smoke test; no fresh visual acceptance is claimed for the renamed assets. The five heads retain their previously reviewed four three-quarter views, motion and second-look evidence, reverified with the current capture checker. Those original galleries are copied under evidence/troll-reindex-v1; their captions show the previous indices.

Multiplayer, equipment combinations, every animation and saved-character migration were not tested in this publication pass.

## Repeatable renaming

Use run_headbatch.py --workspace DIR env tools/heads/reindex_head.py --source SOURCE.mdl --new-model pmg0_headNNN --output NEW.mdl with the bundled workspace Python. Freeze the inputs first and use a fresh staging directory. The helper edits bounded model, node and texture names, checks decoded geometry/material equality and refuses animations, unexpected external textures and unknown source-name fields. Copy the matching PLT unchanged to the new name.

For a batch, snapshot all source pairs before writing any destination: source and destination ranges can overlap. Require unique destination names, exact reverse-renaming and PLT hashes, audit cross-pack collisions, preserve unrelated resources, rebuild only the affected HAK, verify its complete payload, then run a from-base client trial. A from-base-only trial needs an unused shared fixture resource so its auxiliary HAK is nonempty. Do not put head MDLs/PLTs in that auxiliary HAK: they would hide errors in the published pack.
