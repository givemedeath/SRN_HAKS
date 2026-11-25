# Names and blueprints of the imported placeables

An imported row of `srn_2da/placeables.2da` came with its author's label and no blueprint. `library.json` says, for
each row that has been named, what it is called, the palette category it stands in and the blueprint a builder paints
it with. `categories.json` is the category tree (user, 2026-11-25: names, blueprints and a better arrangement than the
Modern Mod's). `python -B -m tools.envkit library --game <game folder>` writes

- the label of the row, `[mdrn]` and the name
- `srn_placeable/<blueprint>.utp`: scenery, static, not usable, as an envkit blueprint is
- `srn_placeable/placeablepalstd.itp`: the game's own palette, envkit's blueprints and these

A row's number and model never change. Change a name or a category in `library.json` and run the command again. A row
imported later is named by adding an entry.

## Where the names come from

All but some sixty of the 3,481 names are those of the blueprints in the d20 Modern update module (`_mdrn_pl_*.utp`, its palette
categories used as a hint only), with spelling put right and names that stood twice numbered. A picture sheet of 112
rows taken at random matched their names, and so did the 400 or so pieces looked at for the srx02 rooms. The rest were
looked at and named here. 745 `[mdrn]` rows have no blueprint in that module and keep their labels and no blueprint.

A blueprint is named as its model, with `_` for `-`; `mdrn_<row>` where that name is the game's, envkit's or another
row's.

## The categories

Nine branches, Shadowrun City (envkit's, with city pieces added), Furniture, Interior, Technology, Containers,
Structure, Vehicles, Weapons and Bodies, Nature. They took the place of Modern Exterior, Interior and Space and
Futuristic Interior and Exterior, whose category numbers (155 to 207) most of them reuse: a module's own blueprint that
named one of those now shows under the new category of that number.
