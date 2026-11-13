# Running a concept sheet through envkit

One concept sheet becomes a building (a tile group) and its props (placeables). This is the order the Stuffer
Shack and the Ares Depot were run in, with the commands that now do each step. Every command is
`python -B -m tools.envkit <command>` with the bundled workspace Python, run from the repository root.

`<sheet>` is the sheet's set name (`ares-depot`), `<root>` its output root (`output/envkit/<sheet>`), `<game>`
the game install folder (the one holding `data/`). Everything under `output/` is ignored by git.

## What a sheet has in the repository

| File | What it states |
| --- | --- |
| `tools/envkit/sets/<sheet>.json` | the sheet, and each asset's crop box, kind, type and subject; `same` where another sheet's model serves |
| `tools/envkit/sets/<sheet>-meshy.json` | the plan: which assets go through Meshy, at what triangle target, under which ledger keys |
| `tools/envkit/sets/<sheet>-game.json` | each generated model's height, name, lit parts, retouching, and the building's tiles and door |

## 1. References

```
envkit crops     --set tools/envkit/sets/<sheet>.json --sheets <sheets> --output <root>/references/<run>
envkit reference --set ... --sheets <sheets> --output <root>/references/<run> --bindings <root>/references/bindings.json [--asset <a>] [--seed <n>] [--keep-going]
envkit contact   --references <root>/references/<run> --output <root>/references/<run>-contact.png
```

`reference` draws each asset alone on a plain ground with the local image model on the bound ComfyUI. The process is
shared: each job waits for the GPU lease and an empty queue (`headkit.shared_comfy.slot`), one at a time, and leaves
other sessions' jobs alone. The first failure stops the run; with `--keep-going` an asset that fails is said and
passed over, the rest are made, and the run fails at the end. `contact` puts each reference beside
its crop; read it for a changed shape, lost parts, and branding that should not be there. Draw an asset again
with another seed where it fails. Copy the chosen image of each asset to `<root>/references/selected/` under the
name it has (`<asset>-s<seed>-b0.png`): exactly one for each asset the plan names.

## 2. Meshy

The ledger (`output/envkit/stuffer-shack/meshy/ledger.json`, shared by every sheet) holds the cap, which is the
spending the user has approved. A prop costs 15 credits, a building 30 and its remesh 5.

```
envkit sheet status  --plan tools/envkit/sets/<sheet>-meshy.json --ledger <ledger> --root <root>
envkit meshy cap     --ledger <ledger> --cap <n> --reason "<who approved it, when, for what>"
envkit sheet submit  --plan ... --ledger <ledger> --root <root>
envkit sheet collect --plan ... --ledger <ledger> --root <root>
```

`status` says what the sheet's unsent calls cost (`unsentCredits`) against what the cap has left. Raise the cap only on the
user's word, and say so in the reason. `submit` finds every reference and checks the whole of what is unsent
against the cap before it sends anything; a call already in the ledger is not sent again. Meshy holds ten
tasks at once, so `submit` sends what the queue has room for and says which calls it held back: run `collect`,
then `submit` again, until `collect` lists nothing `unsent`. `collect` waits for each call, downloads the models to
`<root>/meshy/models/<key>`, keeps the building's full generation in `<root>/meshy/masters/<key>` and remeshes
it to the plan's triangles. One failed model does not stop the rest, and `failed` lists it on every run until it
is dealt with. The CLI never sends a key twice, so a call that failed or was refused goes again under a new key
in the plan (`"key": "<prefix>-<asset>-a2"`; for a failed remesh, the building's `"remesh"` key alone). A
triangle target changed in the plan, or another reference selected, needs a new key too: `collect` refuses a
call that was sent for another target and `submit` one that was sent with another reference. A building
generated again under a new key needs a new `"remesh"` key with it: `collect` refuses a remesh that was made
from an earlier generation. `collect` ends
in an error while any call has no working model, and `status` lists as `unplanned` whatever the set holds that
the plan makes nothing of.

## 3. The game set

```
envkit view --source <root>/meshy/models/<key> --height <metres> [--source <key2> --height <metres> ...] --model 01 --output <root>/view [--page <root>/view/all.png]
envkit view --models tools/envkit/sets/<sheet>-game.json --root <root> --model <name>:02:300:0.25 [--lit] --output <root>/view
```

The first draws generated models square on from each side with a metre grid, before the game set names them, each
at a first guess of its height (`--source` and `--height` repeat in pairs); `--page` also puts every model drawn on
one page, to compare the props of a sheet at a glance. The second draws a model as its game set makes it. Read the boxes of lit parts, paint, smoothing, mesh panels,
fences and the door from the grid, in metres on the finished model, and state `measuredAt`: the height they
were read at, or `{"height": ..., "lift": ...}` with each of `lift`, `turn` and `signTilt` the model states,
since the boxes are on the model as lifted, turned and tilted. Change any of them and the set is refused until
the boxes are read again. `--lit` shows what the lit boxes light. The drawing lets deeper faces show through nearer ones:
what a surface looks like is settled in the client, not here.

Size a building by its door: scale it until the door leaf is about 2.1 m, then choose the tile group's size.
Its door hook is door type 58. Screens and signs are lit.

### A building in pieces, and a group of several models

A generation gets one 4K texture, which spreads thin over a large building (the yard at its door's size: 47
texels a metre, against about 190 on a prop). Such a building is made in pieces (user, 2026-11-12): each piece's views
are set assets with a `cut` (`{"from": "<whole view>", "box": [x0, y0, x1, y1]}`, in pixels of that view's chosen
reference), drawn by `envkit reference --selected <root>/references/selected`, set on white so that a cut edge is
redrawn as the end of a block, and generated under the plan's `pieces` (`{"<piece>": {"views": [...], "triangles":
n}}`). The pieces keep the one drawing's proportions and colours.

Given a front and a rear view of differing outlines, Meshy makes one face faithfully and the other plain (the yard's
west and centre pieces: faithful rears, plain fronts). Generate the plain face again from its own view alone as a
piece of its own and stand the two back to back in the group, each one's plain wall inside the other. Scale each pair
to one width and the building by its door; line the fronts up by their parapets. `envkit tiles` holds the group's
own model and every placed model that is no placeable to the building budget together; to come within it, give a
piece a lower `triangles` and a new `remesh` key (5 credits: the generation is remeshed again).

The group is the concept's whole scene, not one mesh: the game set's `tiles.parts` places other models of the set
in it (`{"model": ..., "at": [x, y, z], "turn": 0|90|180|270}`, in metres on the group's own model), each drawn
with its own picture under the group's names (`<group>p1`, ...), cut into the same tiles and walked round. A prop
of the sheet stays a placeable as well.

```
envkit game  --models ... --root <root> --output <root>/game<n>  [--model <name>]
envkit tiles --models ... --root <root> --output <root>/tiles<n> --model <building>
```

## 4. Props in the client

Each client check builds a throwaway module and user folder under `<root>/fixtures/<name>` (a new name every
run) and captures the views. It waits while another game client runs and never closes it.

```
envkit check props --game <game> --models ... --root <root> --name <name> --built <root>/game<n> --model <a> --model <b> [--mode night]
```

Each prop is shown from the front, the back and the side with a figure for scale and one behind it, straight
from the converted folder: nothing is in the packs yet. Look for scale against the figure, holes and see-through
faces, smeared markings, wires and thin members, and what glows by night. Correct the game set and convert
again until they hold.

## 5. Into the packs

```
envkit install    --models ... --built <root>/tiles<n> --model <building> --provenance "<section>"
envkit placeables --models ... --built <root>/game<n> --provenance "<section>"
envkit blueprints --models ... --game <game>
```

## 6. The group and the lights in the client

```
envkit check group  --game <game> --models ... --root <root> --name <name> --built <root>/tiles<n> --model <building> --tileset dgt04 [--mode night|near|walk]
envkit check lights --game <game> --models ... --root <root> --name <name> --built <root>/game<n> [--built <root>/game<m>]
```

Both read the packs, so they follow step 5. `group` lays the pack's tile numbers with the built models, and
refuses where the pack holds another build: a building built again is installed again first. `near` frees the
player to show which storeys the client hides; `night` also puts out every lit model of the group, its own and its
parts', and brings them back (`out`, `out-behind`, `lit-again`). `walk` sends walkers from the far corners of the
area to the door, to each side of the building and onto the ground a walk must go furthest round to reach (a fenced
yard), with one more onto that ground from the next tile out, and logs where they are every shot; it refuses the
group if a walker stops more than a metre short, after writing `captures/walks.json`. The walkers' targets come
from `walk.png`, which `tiles` writes beside the tile sources (a pixel a walk cell, north up: green ground with
room to stand on, dark green ground too narrow for that, red the building, orange the lesser things in the way); a
group built before it existed is built again first. Run `walk` in both tilesets (`tile.py` says why). `lights`
takes the lit props from the pack, by night, and puts them out and on again by script. Look for the roof and upper
storey from above, the door, and every lit part going out and coming back.

Then write the sheet's section of `PROVENANCE.md` (what was generated, by what, what was retouched, what was
checked and what was left as generated), rebuild the affected packs and run repository verification.

## 7. In the Toolset

Painting the group in the Toolset is the only proof that a builder can.

```
envkit toolset prepare --user <root>/toolset<n>/user --game <game>
envkit toolset saved   --user <root>/toolset<n>/user
envkit check doors     --game <game> --user <root>/toolset<n>/user --output <root>/toolset<n>/doors
envkit toolset retire  --user <root>/toolset<n>/user
```

`prepare` needs the packs built into `output/`. It makes a user folder of its own with a module of one plain
area for each tileset, and prints how the Toolset is started on it (working directory: the Toolset's own
folder). The folder's `hak` is a junction to `output/`: run `retire` before deleting the folder, or the built
packs go with it.

By computer use (access is asked for `nwtoolset.exe` by that name):

- `tools/envkit/Toolset.ps1 -Do front -Class TfrmFrame` before every batch of clicks; the opening dialogue is
  `TdlgWelcome`.
- The palette trees ignore simulated clicks on their expanders. `-Do reach -Index 1 -Root 1 -Child <n>` opens
  Groups and selects its n-th item; `-Do expand -Index <tree>` lists a tree.
- Check the name of the selected group before painting: neighbouring rows are easy to hit.
- The pending tile under the cursor is the group's bottom-left. A right-click turns it a quarter, anticlockwise,
  and the tile under the cursor turns with the group: after a half turn it is the top-right.
- The palette's object buttons ignore simulated clicks too: `-Do tab -Index 5` shows the placeables, `-Do tab
  -Index 9` the tiles again, and `-Do path -Index 1 -Path <category>/<subcategory>/<n>` selects a blueprint.
- The mouse wheel zooms the area view while the view has the focus; the zoom buttons do nothing.
- Leave the start point's corner tile alone: the Toolset refuses to save with the start on a tile painted over.
- Save with File > Save (ctrl+s did nothing, 2026-11-12), then judge by `saved`, not by the screen: it lists the
  group tiles laid, the doors the Toolset made at the hooks (appearance 58) and the envkit props placed, each
  with its `placeables.2da` row, name and static setting.

Paint the group straight in one toolset folder and turned in another (a quarter turn in one tileset and a half
in the other), and place a few of the sheet's props, lit and static, from both categories.

`check doors` gives each of those doors an area transition to a waypoint in front of the next and starts the
client with the player free in front of the first. Someone clicks each door in turn while it logs where the
player is; `stages` in what it prints is each place the player came to. Run it on both folders.

## A new sheet, and a review of the sets

All 56 FRFZ sheets have a set file: the first 55 came in one batch, and the Denver rail freight yard
(`56_denver_rail_freight_yard.png`, 2026-11-12) was brought in later with `onboard`, as a sheet that comes later
is. The same commands review the sets against each other when props are to be reused. `<sheets>` is the folder
holding the concept sheets, each named `NN_<what>.png`. `boxes` finds drawings on a white sheet; ask for one on
white if a sheet comes dark (the rail yard's first version was, and half its drawings went unfound).

```
envkit onboard boxes   --sheet <sheets>/NN_<what>.png --output <scratch>/boxes.png [--split <row>]
envkit onboard sets    --spec <scratch>/spec.txt --sheets <sheets>
envkit onboard crops   --set tools/envkit/sets/<sheet>.json --sheets <sheets> --output <scratch>/crops.png
envkit onboard overlay --sheets <sheets> --output <scratch>/overlay
envkit onboard audit   --sheets <sheets>
envkit onboard types   --sheets <sheets> --output <scratch>/types.png --type <type> [--type <type>]
envkit onboard same    --sheets <sheets> --output <scratch>/same [--only <sheet>]
envkit onboard revise  --decisions <scratch>/decisions.txt
```

`boxes` proposes a numbered box round each thing drawn on the sheet (T for the building views, P for the prop
set). A spec names them, one block a sheet:

```
@ <sheet> NN
building-hero | B | | corrugated warehouse with a loading dock | 96 56 524 364 | Ignore the caption.
terminal | access-terminal | =ares-depot/checkpoint-terminal | freestanding access terminal | 76 516 204 644
gate | vehicle-gate | ~Branding: Gate with the yard's name. | sliding yard gate | 296 516 464 644
```

The third field is empty for the original of its type, `=set/asset` for a prop another sheet's model serves,
`~what differs` for a variant and `~!what differs` for a variant drawn unbranded. `sets` writes the set files
and refuses a spec the kit would not accept with the sets already there (a type shared without saying so, a box
off the sheet); a set that exists is not written over. `crops` shows each name on its crop, `overlay` every
sheet with its boxes on it, `audit` what a reading would not catch (the sheet changed, boxes overlapping, a
brand word in a prop that is no sign), `types` the made props of a type side by side and `same` each reused
prop beside the one it reuses. What a review decides goes in a decisions file and `revise` applies it, all of
it or none:

```
<sheet>/<asset> | =set/asset            the same as that prop
<sheet>/<asset> | ~what differs         a variant (~! drawn unbranded)
<sheet>/<asset> | ^                     the original of its type
<sheet>/<asset> | !                     drawn unbranded
<sheet>/<asset> | type <name>           another type
<sheet>/<asset> | box x0 y0 x1 y1       another crop box
+ <sheet>/<asset> | <type> | <relation> | <subject> | x0 y0 x1 y1     a prop the set missed
* <old-type> > <new-type>               a type renamed in every set
```

Several actions on one line apply in order (`... | ^ | type yard-gate`).

## When something looks wrong

- **A lit part does not light.** `envkit view ... --lit` counts for each lit part the texels its box holds and
  the texels it lights (`litParts`). A box that holds much and lights nothing is on the wrong part of the
  model, or on a part too dark to shine.
- **A square-on view does not show it** (inside a hole, under an overhang, through a fence).
  `envkit view --models ... --root <root> --model <name> --eye <label>=ex,ey,ez,tx,ty,tz[,fov[,reach]] --output <scratch>`
  draws the model as it will ship, fence sheets and all, from an eye at `ex,ey,ez` looking at `tx,ty,tz`, in
  metres on the finished model. `--eye` repeats.
- **The parts of a group do not line up** (fronts, parapets, a piece's height against its neighbour's). Draw the
  group from far off through a long lens, the eye level with its target, with `--grid 0.5`: a line every half metre
  on the upright plane through the target, labelled each metre in x or y and z
  (`--eye front=0,70,7,0,0,7,16,200 --grid 0.5`). Read heights off the grid for what stands on that plane; what
  stands nearer the eye is drawn larger.
- **A roller door, shutter or grille comes back as a wavy moiré.** The generator drew slats finer than its texels.
  Smooth the door with `slats` as well: `{"part": ..., "box": ..., "radius": 0.08, "slats": 0.12}` takes the pattern
  off and draws a joint every 0.12 m up the model. Keep lettering out of the boxes (one under it, one over it and one
  either side), and read the boxes off the texture rather than by eye. A pitch under four texels is refused.
- **A raised floor a character should walk on is closed** (a loading bay, a dock apron). A broad flat floor up to
  0.75 m high is walked at its own height (`tile.DECK`, `DECK_AREA`); a higher one, or one under 9 m², is closed.
  `walk.png` shows which.
- **Something the generator stood on the floor leaves too narrow a way** (dark green on `walk.png` where a character
  must pass, or a `tiles` note of walk cells no exit reaches). A path needs a metre clear. Take the thing away with
  `clear`: `{"part": ..., "box": ...}` on the finished model takes every face whose middle lies in the box. Start the
  box a couple of centimetres above the floor, so the floor stays and what stands on it goes, and draw the place again:
  marks the thing left painted on the floor stay. A box that takes nothing is refused.
- **A question about how the engine wants a tile made.** `envkit study tiles --tileset <tileset> --tile <n>
  --output <scratch>` decompiles stock tiles and tells their fade, light, door and animation lines.
  `envkit study pathnodes --tileset <tileset>` checks the path-node table against a tileset's stock tiles,
  turning each by its Orientation both ways; run it before a group goes into a tileset whose tiles were not
  looked at.

## Tests

`python -B -m unittest discover -s tools/envkit -p "test_*.py" -t .` covers the plan, the ledger, the pictures,
the set files `onboard` writes and the layouts of the checks. The client and the Toolset themselves are not started by the tests.
