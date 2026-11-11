# Additions to shared tables and tilesets

`catalog.json` in this folder lists everything the project has added, on top of what it imported, to two kinds of
shared game data:

- rows of `srn_2da/placeables.2da`
- tiles and groups of a tileset's set file

An area names a placeable by its row number and a tile by its tile number, so a number once given is never changed
or given to something else. The catalog is the record of who has which number.

Imported rows are recorded separately, under `docs/imports/*-global-row-allocations.json`. The catalog starts where
the imports end: its `baseline` gives the last imported row of the table and the number of imported tiles and groups
of each tileset that has additions.

## What repository verification enforces

`tools/Test-Repository.ps1` checks the catalog against the packs on every run, locally and in CI:

- every row of `placeables.2da` above the baseline is in the catalog, with the same model and label, and the rows
  run on without a gap
- every tile and group above a tileset's baseline is in the catalog, and each group's name, size, tile numbers and
  tile models match the set file
- every listed model (`.mdl`), tile walkmesh (`.wok`) and blueprint (`.utp`) is a file of the pack the entry names
- nothing is listed that the packs do not have

A row or tile added without its entry fails verification, and so does an entry left behind.

## Adding placeables

1. Give the model a `placeable` entry in its game set (`tools/envkit/sets/*.json`): a label, a sound row and, for a
   blueprint, a palette `category`.
2. `python -B -m tools.envkit game ...` converts the model.
3. `python -B -m tools.envkit placeables ... --provenance "<PROVENANCE.md section>"` copies its files into
   `srn_placeable`, appends its row after the table's last row and writes its catalog entry.
4. `python -B -m tools.envkit blueprints ... --game <game folder>` writes a blueprint for each catalogued model that
   has a category and rebuilds `srn_placeable/placeablepalstd.itp`.

Running step 3 again for models that already have rows replaces their files and leaves the table alone.

Rules the commands follow, and that a row added by hand must follow too:

- rows are appended; no row is renumbered, reused or left empty
- the label starts with `[envkit]`, as imported rows start with their own tag (`[mdrn]`)
- the model is named `ek_<set>_<thing>` in lowercase, at most 14 characters (12 for a tile group, whose tiles add
  `_t` and two digits); `ek_ss_` is the Stuffer Shack set

## Blueprints and the palette

A blueprint is named as its model (`ek_ss_trash.utp`) and lives in `srn_placeable`. Blueprints in a hak are not on
the Toolset's Custom tab, which lists only the module's own. They are offered on the Standard tab because
`placeablepalstd.itp` lists them: that file is the game's own palette with ours added, laid out on the category
tree in `placeablepal.itp`. It is rebuilt whole by `envkit blueprints`, so it needs the game installed; do not edit
it by hand.

Categories are the IDs of `placeablepal.itp`. Those in use:

| ID | Category | Used for |
| --- | --- | --- |
| 156 | Modern Exterior > Signs | standing signs |
| 158 | Modern Exterior > Streets | bins and street furniture |
| 161 | Modern Exterior > Structures | machines and units that stand outside |
| 162 | Modern Exterior > Misc. | clutter |
| 166 | Modern Interior > Equipment | shop equipment |
| 174 | Modern Interior > Furniture | racks and shelves |
| 200 | Modern Exterior > Wall Fixtures & Features | things hung on a wall |

A blueprint is scenery: it cannot be destroyed or used. A model with lit parts gets a blueprint that is not static,
so a script can put its lights out; the others are static.

## Adding a tile group

1. Give the model a `tiles` entry in its game set: ground texture, group name, palette label and the terrain it
   stands on in each tileset.
2. `python -B -m tools.envkit tiles ...` builds the group.
3. `python -B -m tools.envkit install ... --provenance "<PROVENANCE.md section>"` copies its files into
   `srn_t_common`, appends its tiles and group to each tileset's set file, lists it in each palette and writes its
   catalog entries, one per tileset.

A tileset's first addition needs a baseline first: add `"<name>": {"set": ..., "importedTiles": ..., "importedGroups": ...}`
under `baseline.tilesets`, with the counts the set file has before anything is added. Running step 3 again for a
group already installed rebuilds it under the tile numbers it has.

## Adding something by hand

A tile or group made without envkit (the arcology groups are the example) gets its entry by hand, with
`"madeBy": "hand"` and the same fields as the entries beside it. `source` says where it came from and `provenance`
names its section of `PROVENANCE.md`.

## Two branches adding at once

Two branches that both append will take the same numbers. Git shows it as a conflict in the table or set file and
in the catalog. The branch that merges second takes the next free numbers: revert its rows or tiles, merge, and run
its command again. Do this before any area uses the numbers.
