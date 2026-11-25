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

Some 3,420 of the 4,226 names are those of the blueprints in the d20 Modern update module (`_mdrn_pl_*.utp`, its palette
categories used as a hint only), with spelling put right and names that stood twice numbered. A picture sheet of 112
rows taken at random matched their names, and so did the 400 or so pieces looked at for the srx02 rooms. The rest were
looked at and named here. The 745 `[mdrn]` rows
with no blueprint in that module were named from their labels and from a picture of each piece (user, 2026-11-25), so every
`[mdrn]` row has a name and a blueprint. 22310 and 22314 share one model: both are the blue dome awning.

A blueprint is named as its model, with `_` for `-`; `mdrn_<row>` where that name is the game's, envkit's or another
row's.

## The categories

Nine branches, Shadowrun City (envkit's, with city pieces added), Furniture, Interior, Technology, Containers,
Structure, Vehicles, Weapons and Bodies, Nature. They took the place of Modern Exterior, Interior and Space and
Futuristic Interior and Exterior, whose category numbers (155 to 207) most of them reuse: a module's own blueprint that
named one of those now shows under the new category of that number.

## Pictures made anew

The rooms draw old placeables at eye level, so the pictures too coarse for that were made anew, first those of the rooms,
then every one a named placeable draws (user, 2026-11-25), and the screens that showed a real desktop, program or maker's
name were redrawn for the 2070s.
- `redraw.json`: what the local Qwen edit model drew, on the layout each picture had (`tilekit redraw --bindings`). A
  `blank` box is filled before the model sees it, so an old screen or logo is not copied. A redraw that came back in other
  colours has `recolour` (the old picture's broad colours), one whose sides no longer met has `join` (`pictures.py`); nine
  whose pattern changed are enlarged instead.
- `materials.json`: the size each goes into its pack at, and the pictures enlarged only (`tilekit enlarge`): atlases of
  small parts, where a redraw would move the parts. `left` says which weak ones stay and why.
- `enlarged.json`: the rest of the weak pictures, enlarged on shared sheets (`tilekit enlarge --sheets`, `sheets.py`), and
  under `left` those that are not touched (drawn by a tile pack, a material of the same name, fine enough) and why.
- `screens.json`: the twenty device pictures with a screen in them, and `screen-pictures.json`: what those screens show,
  each drawn alone by the Qwen model from a blank picture (`tilekit screens --draw`) and laid into its device (`tilekit
  screens`). Screens drawn in code, and device pictures redrawn whole, were tried first and were not good enough.
- They go in as plain DDS pictures under their own names, so every placeable that uses one is changed, not only the rooms.
  A standard DDS holds its bottom row first, as the game reads it: a viewer shows it upside down.

`python -B -m tools.tilekit material --spec docs/placeables/<list>.json --out <folder> --enlarged <folder> --redrawn
<folder> ...` makes them again; `tools/tilekit/texels.py` finds the weak ones.
