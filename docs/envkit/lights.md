# Putting envkit lights out by script

Every model `tools/envkit` makes with lit parts (a sign, a screen, a shop window) ships with what a script needs
to put those lights out and bring them back. This page is the standard those files follow and how to use them
from NWScript. It is written for the projects that script against these packs (SR_NWN, SRN_NWN).

## What ships with a lit model

For a model whose material is `<name>`:

| Resource | What it is |
| --- | --- |
| `<name>.mtr` | the model's material, with its glow map in slot 5 |
| `<name>_i.dds` | the glow map: the model's own colour where it is lit, black elsewhere |
| `<name>_o.mtr` | the lights-out material: the same maps without the glow map |
| `<name>_o.dds` | a 16-pixel black texture; it gives `<name>_o` a texture of its own name, and stands in for the glow map |
| `<name>_h.mtr`, `.dds`, `.txi` | the halo, where the model has one: the light drawn round a sign, added to what is behind it |
| `ek_off.mtr`, `.dds`, `.txi` | the dark halo: one black additive sheet shared by every model, in `srn_placeable` only |

`<name>` is the model's own name for a placeable (`ek_ss_vending`). For a tile group it is the name the tiles
share, without the `_t00` that numbers them (`ek_ss_shack`). A group made of several models (a building in
pieces, a yard's fence and booth placed with it) has a material for each: its own, and `<group>p1`, `<group>p2`
and so on for the models placed in it, each with its own set of these files where it is lit.

The files are in the model's pack: `srn_placeable` for placeables, `srn_t_common` for tile groups. A model with
no lit parts has none of them.

## Which models have lights

`docs/additions/catalog.json` says so. The entry of a lit placeable or tile group has a `lights` object with the
names to use:

```json
"lights": {"lit": "ek_ss_vending", "out": "ek_ss_vending_o", "glow": "ek_ss_vending_i", "halo": "ek_ss_vending_h", "dark": "ek_off"}
```

`halo` and `dark` are absent for a model without a halo. A group with more than one lit material has a list of
these objects, one for each, and a blackout of the group swaps each. Repository verification holds the catalog and the packs
together: a model with a glow map and no `lights`, or `lights` whose files are missing, fails it.

## One object: `ReplaceObjectTexture`

For one placed object, leaving every other copy of the model lit:

```c
// Puts the lights of one envkit placeable out, or back on. sName is its model name; bHalo whether it has a halo.
void EkLights(object oThing, string sName, int bOn, int bHalo = TRUE)
{
    ReplaceObjectTexture(oThing, sName, bOn ? "" : sName + "_o");
    if (bHalo) ReplaceObjectTexture(oThing, sName + "_h", bOn ? "" : "ek_off");
}
```

- The object must not be static. A static placeable is scenery no script can reach. The blueprints of lit models
  are made not static for this reason; a builder who ticks Static on one gives up this call for it.
- It does not work on tiles: a tile is not an object.
- The replacement has to be a material, which is why `<name>_o` exists. Replacing the glow map by its own name
  with this call changes nothing.

## Light cast round a placeable

A glow map lights only the model's own faces. A placeable whose game set gives it a `light` (`{"colour": <row of
lightcolor.2da>, "at": [x, y, z]}`, metres from the object's origin) also lights the ground and characters round it,
as the stock lamp post does: its `placeables.2da` row names the colour in `LightColor` and the place in
`LightOffsetX`, `Y` and `Z`. The rail yard's light tower has one (colour 3, bright white, at its lamp heads). Its
catalog entry's `lights` are as above; put the cast light out with the faces:

```c
SetPlaceableIllumination(oThing, bOn);
RecomputeStaticLighting(GetArea(oThing));
```

The same object rules hold: not static. Checked in the client on 2026-11-13 by night: the ground round the light
tower lit, dark when put out with the call above and `EkLights`, and lit again.

## Everything a player sees: `SetTextureOverride`

For tiles, for static scenery, or for a blackout of every copy at once:

```c
// Puts out, or back on, the lights of every copy of an envkit model that oPC sees: tiles and static
// placeables as well as the rest. OBJECT_INVALID as oPC means every player then in the game.
void EkBlackout(string sName, int bOn, object oPC = OBJECT_INVALID, int bHalo = TRUE)
{
    SetTextureOverride(sName + "_i", bOn ? "" : sName + "_o", oPC);
    if (bHalo) SetTextureOverride(sName + "_h", bOn ? "" : "ek_off", oPC);
}
```

- This call swaps textures by name and knows nothing of materials, so it overrides the glow map and the halo
  sheet with dark textures. Do not override `<name>` itself with `<name>_o` here: the whole model is then drawn
  in that 16-pixel black.
- It is per player, not per object or per area: every copy of the model that player sees goes dark, wherever it
  stands. For one building among several of the same model there is no call; use a different model.
- The game's script header says `OBJECT_INVALID` applies the override to all active players, so one who joins
  afterwards is not covered: apply it again when a player enters.
- An override outlasts an area change: a player who leaves the area and comes back finds the lights still out,
  until a script puts them on again. This holds for both forms, one player and `OBJECT_INVALID`.

## Tiles by day and night

A tile's halo is already tied to the hour: the game plays the tile's `day` and `night` animations, which fade
the halo sheets out by day and in by night. The glow map itself shows at every hour. A script is only needed to
put the lights out against that, as in a power cut.

## What was checked, and how

In the game client on 2026-11-11, from the files in the packs, at night:

- `ReplaceObjectTexture` on the three lit Stuffer Shack placeables, not static: lights out, and on again.
- `ReplaceObjectTexture` on two vending machines side by side, one static and one not: the one that was not
  static went dark and the static one stayed lit, though `GetObjectByTag` found both.
- `SetTextureOverride` for one player, on the Stuffer Shack tile group and on a static vending machine beside it:
  glow and halo out with the rest of each model unchanged, and on again.
- `SetTextureOverride` for every player (`OBJECT_INVALID`), on the tile group: the same.
- `SetTextureOverride` of the tile's material name with its lights-out material: the building drew black.
- `SetTextureOverride` on the tile group, for one player and then for every player, with the player sent to a
  second area and back: the lights were still out on return, and came on again when the override was cleared.

## For those who make models

Nothing is done by hand. `tools/envkit` writes the whole set for any model whose game set names `lit` parts
(`convert.skin`), `envkit placeables` and `envkit install` copy it into the packs and write `lights` into the
catalog, and `ek_off` goes into `srn_placeable` whichever command meets it first. `convert.lights_script` and
`convert.blackout_script` write the same calls as the functions above, for test fixtures.
