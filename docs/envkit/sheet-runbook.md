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

A generic sheet's building view takes `"unbranded": true` in the set: it is drawn without company or place names,
keeping generic words such as FREIGHT (the rail yard, user 2026-11-12). Name a sign's text in the subject so the model
need not guess its letters. A view the sheet does not draw, or draws of another building, is turned from the chosen
reference of one it does: `"turn": {"from": "<view>", "to": "<what it is seen from>"}`, drawn with `--selected` like a
cut (the rail yard's rear, whose corner view showed another building than its front, user 2026-11-13)). The model
tends to draw a turned rear with the gable on the left whichever corner it is asked for; work out which side that puts
the detailed wall on, and where it is the wrong one, cut with `"mirror": true` (the reference flipped left to right
first, its box in the flipped picture). Mirror only a reference without lettering. A rear that is to be the front's
plain mirror image takes `"drawn": true` beside its mirrored cut and is never redrawn: the redraw of a flipped front
draws the block the front's way round again (Aurora Warrens, user 2026-11-15). Before generating a building's
pieces, check that each side wall is the same material in every piece that shows it, that the dock doors match, and
that nothing large (a trailer, a skip) stands in front of the doors: the generator fuses it into the wall.

A building is drawn without its perimeter fence (user, 2026-11-17: "we need to make sure we don't do any more
perimeter fences via meshy and add them in post processing"). Every building prompt says to leave out the fence, its
gate, gate posts and razor wire, and any chain-link, railing or wire standing in front of a wall, and a set whose
building subject or notes ask for one is refused (a note may say to remove it). The fence is built afterwards: the
game set's `fence` parts, or fence sections placed in the group. Where the model has no posts the game set builds
them (`built` bars for posts and rails; the `fence` sheets hang between them), and a built fence is generally topped
with spiral barbed wire (user, 2026-11-17): a `built` `{"coil": [from, to], "radius": 0.25, "pitch": 0.5}` along each
run, its axis its radius over the top rail: two strands wound opposite ways, which cross as concertina wire's loops do. The Shiawase Barrens power station was generated with
its fence in both views: the fence came back as open frames, its chain-link printed on the rear wall, the transformers
and the roller door, and the surface behind its razor wire smudged. Look at each chosen building reference for a fence
before selecting it.

Images that are already clean references on white (made apart from the concept sheets, one object to an image) come
in as a sheet of their own: compose them on white into `<sheets>/NNb_<what>.png`, give the set a box round each and
`"drawn": true`, and `reference` takes each crop as it is, with a receipt naming its hash, and sends nothing to ComfyUI.
The rail freight depot (`56b_rail_freight_depot.png`, 2026-11-13) is the first: four images the operator generated
with ChatGPT from one shared design, a warehouse front and rear, a loading platform and a gantry crane, which replaced
the yard sheet's warehouse. Prompt such a set piece by piece in one conversation, after an overview, with the shared
dimensions and materials in every prompt and each view's handedness named (which wall is on which side).

```
envkit enlarge --root <root> --bindings <root>/references/bindings.json
```

A reference goes to Meshy at 2048 pixels or more on its longer side (user, 2026-11-14), and the local model draws
at about one megapixel. `enlarge` writes each chosen reference to `<root>/references/sent` under the same name:
doubled by the shared ComfyUI's `RealESRGAN_x2plus.pth` where it is smaller, copied where it is not. This sharpens
what was drawn and adds nothing to it. The chosen references in `selected` stay as they are, since a building's
pieces are cut from them in their own pixels. `sheet submit` finds each asset's reference in `selected` and sends
the picture of that name in `sent`; it refuses a smaller picture, and refuses `sent` where it does not hold the
references chosen now (one missing, one made from another picture, one whose enlarging failed). Run `enlarge`
again after choosing another reference. Another seed's picture lies beside the one enlarged before, which stays
as history and is not sent; one chosen again under the same name, or the receipt of an enlarging that failed, is
refused until the picture in `sent` and its record are taken away. `--bindings` is needed only where a reference
is doubled.

## 2. Meshy

The ledger holds the cap, which is the spending the user has approved. A prop costs 15 credits, a building 30 and
its remesh 5. There is one ledger for every sheet, session and worktree: `envkit/meshy-ledger.json` in the shared
tool root (`SRN_TOOLS_ROOT`, else the primary checkout's `.tools`), which every command finds by itself and which
stays where it is when a worktree retires. Every change is made under a lock, so sessions may spend against it at
once, and every change writes the day's copy to `envkit/meshy-ledger-copies/<date>.json` beside it: the tool root
is in no repository and no archive, so read a lost ledger back from the latest copy: copy that file to
`envkit/meshy-ledger.json`. Where copies lie beside a missing ledger, every command says so and `meshy init`
refuses to start an empty one in its place, which would forget every credit counted. `--ledger <file>` names
another ledger (a trial's own; an empty name is refused); do not keep the shared one in a worktree's output
again. The paths an entry records (`task`, `downloaded`, the triangle counts) are where the files lay in the
worktree that made the call, in full since 2026-11-17; older entries hold them as they were given, mostly from
their worktree's root. A call is waited for and downloaded in one worktree, and a download elsewhere says where
the task record lies. `status` and every `sheet` command print the `ledger` they worked under.

```
envkit sheet status  --plan tools/envkit/sets/<sheet>-meshy.json --root <root>
envkit meshy cap     --cap <n> --reason "<who approved it, when, for what>"
envkit sheet submit  --plan ... --root <root>
envkit sheet collect --plan ... --root <root>
```

`status` says what the sheet's unsent calls cost (`unsentCredits`) against what the cap has left. Raise the cap only on the
user's word, and say so in the reason. `submit` finds every chosen reference's picture in `<root>/references/sent` and checks the whole of what is unsent
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
were read at, or `{"height": ..., "lift": ...}` with each of `lift`, `turn`, `signTilt` and `length` the model states,
since the boxes are on the model as lifted, turned, tilted and drawn out. Change any of them and the set is refused until
the boxes are read again. `--lit` shows what the lit boxes light. The drawing lets deeper faces show through nearer ones:
what a surface looks like is settled in the client, not here. `--eye` draws it in perspective as the game does, a face
only from its front: a hole there is a hole in the game.

A model scaled to its height can still come out the wrong length (the rail yard's 20 ft container came out 3.5 m long
at its 2.6 m height): `length` draws it out along the longer side of its footprint to that many metres, its height and
width kept. Every model is looked at from all round and above as it is converted, and a face seen mostly from behind
is turned round (`turnedFaces` in the report): from 2% to a quarter of each of the rail yard's 25 Meshy models was
wound inside out, a hole in the game. A hole with nothing in it at all is closed with `close`, three of the model's own
vertices a face, read from `envkit view --eye`.

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

A sheet's buildings can be both: each its own group, for a builder to place alone, and together one large group of
the whole site, which paints a district in one go (user, 2026-11-13: the rail yard's depot is 8 by 8 tiles, its
warehouse, dock warehouse, control tower, office and service bay with the platform, crane and two tracks).
Containers, light towers and rolling stock are props, placed by the builder, not parts of the site. A site with
rails is laid out round its tracks (user: the first layout did not lend itself to "realistic track placement and
train movement"): each track straight through the whole group and out at both edges, on a tile row's centre so track
tiles beside the group meet it, with 1.93 metres either side of its centre clear up to 5.2 metres; a platform's edge
1.7 metres from its track's centre, and the platform clear of the buildings, since a deck 1.28 metres up meets
no door of theirs (user: the depot's platform, laid across its warehouse's dock apron and half its gable, was "not
working out with the warehouse building"; it now stands beside the warehouse, its stairs towards the warehouse's
door, two metres off); a crane's runway along the tracks, its legs outside their corridors, and clear
of buildings all the way across (user: "there would be nowhere for the crane to move here"). The track is built, not
generated: `envkit track` writes a 10 metre straight piece of standard-gauge track on ballast as a model folder
(rails 1.435 metres apart, a sleeper every 0.625 metres, every map seamless along it, 0.31 metres high), and the
game set lays it `underfoot` as a part, one piece on each tile of the row, centred on the tile's column.
`envkit track --piece merge` writes a 30 metre merge, three tiles: a through track with a switch 1.5 metres in, from
which a second track curves off on 15 metre curves, crosses at 27 degrees and runs on beside it 10 metres away, on
the next row (user: "can you make the tracks merge" at both ends of the depot). A main line's turnouts are far
gentler; at the game's scale it reads as a yard crossover. The two tracks share long sleepers until they are 3.2
metres apart. Laid at both ends of two tracks, turned half round at the far end, it makes a passing loop with one
track out at each end, each on its row's centre; the crane then travels between the switches.
`envkit track --piece crane` writes a 10 metre crane runway: two crane rails a metre apart, 0.23 metres high, clipped
to a concrete ground beam, laid underfoot under each of a gantry crane's legs (user: "i think we need to add the crane
tracks, we'll need those as a prop anyway and the scene looks weird without it"). A generated crane can come back
standing on its own short rails (the depot's did, about a metre apart and 0.23 metres high): take them off with a
`clear` box under each leg, check its wheels are kept, and lay the runway on their line, so the wheels meet the
built rails. The runway is a placeable too, for cranes a builder places. A part laid
underfoot is drawn but not surveyed, so the ground is walked flat across it and it may run off the group's edges,
where a raised slab is refused; it stands no higher than the knee. A
part is never a group itself, so a building in both has a second entry of the same source and height without
`tiles` (`ek_rf_towerx`), and its standalone group and the site's must agree on that height. A group places at most
nine different models. No model may be named like another's file (its maps' `_n`, `_s`, `_r`, `_i`, `_o`, `_h`,
a group's `_t` tiles and `p` parts): the set is refused, since one would write over the other in the pack.
`envkit view --models ... --model <site> --eye ...` draws the whole site with its parts before it is cut into tiles.

```
envkit track --output <root>/track/<piece>-s<seed>  [--piece straight|merge|crane] [--seed <seed>]
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

`placeables` writes a prop's light into its row only as `envkit game` measured it from the model (the report's
`lightAt`): a light moved in the game set since, or given to a prop converted before it had one, is refused until
the prop is converted again, so that none goes into the table where the game would draw its flare in the air.

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
room to stand on, pale green ground with room that no walk from round the group is planned onto, red the
building, orange the lesser things in the way and ground too narrow to stand on, which
`tiles` closes: a walk would be planned through a gap no character fits, as it was through the gaps between the
Saeder-Krupp yard's fence sections; dark green in a picture built before 2026-11-12); a
group built before it existed is built again first. Run `walk` in both tilesets (`tile.py` says why). The check
area is 9 tiles across, or as many as hold the group with 3 tiles of ground round it (`checks.area_size`: the 8 by 8
depot's is 14), and a walk shot is held longer in a larger area (`checks.walk_hold`). A capture made after its
shot has passed shows the next view under the wrong name: the depot's client stalled 20 seconds and its log came
late. Such captures are kept as `-late.png` and the check is refused; run it again. `lights`
takes the lit props from the pack, by night, and puts them out and on again by script. Look for the roof and upper
storey from above, the door, and every lit part going out and coming back.

Then write the sheet's section of `PROVENANCE.md` (what was generated, by what, what was retouched, what was
checked and what was left as generated), rebuild the affected packs and run repository verification.

## 7. In the Toolset

Painting the group in the Toolset is the only proof that a builder can.

```
envkit toolset prepare --user <root>/toolset<n>/user --game <game> [--size 12]
envkit toolset saved   --user <root>/toolset<n>/user
envkit check doors     --game <game> --user <root>/toolset<n>/user --output <root>/toolset<n>/doors
envkit toolset retire  --user <root>/toolset<n>/user
```

`prepare` needs the packs built into `output/`. It makes a user folder of its own with a module of one plain
area for each tileset (8 tiles square; `--size` makes them larger, and a group as wide as the area leaves no
corner for the start point: the Rail Freight Depot's 8 by 8 was painted in 12-tile areas), and prints how the
Toolset is started on it (working directory: the Toolset's own folder). The folder's `hak` is a junction to `output/`: run `retire` before deleting the folder, or the built
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
  The numbers count down the tree as the Toolset shows it, from 0, and it lists categories by name, not in the
  palette file's order (2026-11-14: Modern Exterior is 5 and Modern Interior 6 of 14, where the file has them
  12 and 13, and a path read from the file selected a stock bookcase). `-Do reach -Index 1 -Root <n> -Child 0`
  opens one category to read its subcategories; read the selected name before placing.
- The wheel over the palette zooms the area view if the view has the focus, a long way for each notch.
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

All 60 FRFZ sheets have a set file: the first 55 came in one batch, and the Denver rail freight yard
(`56_denver_rail_freight_yard.png`, 2026-11-12), three street shops (`57_pulse_tech_matrix_gear_shop.png`,
`58_chop_shop_cyberware_clinic.png` and `59_iron_sight_arms_gun_shop.png`, 2026-11-14) and the Barrens power
station (`60_shiawase_barrens_power_station.png`, 2026-11-17) were brought in later with `onboard`, as a sheet that
comes later is. Sheet 60 is sheet 6's Shiawase substation drawn again for the Barrens (user, 2026-11-17): the same
building worn down, on one fenced slab with an open yard, one door (the way down to the utility tunnels) and one
roller door. It was drawn with the Codex CLI's image tool from sheet 6 and revised from its own drawing; where
`boxes` joins a hero to the title block or a row of props to its heading, as it did there, state the boxes by hand
and read them back with `crops`. A sheet from outside the batch is copied into `<sheets>` under its
`NN_<what>.png` name. `boxes` needs scipy, which the bundled Python lacks: put the pinned itemkit library folder
(`.tools/itemkit-python-v1` of the shared tool root) on `PYTHONPATH` for it. The same commands review the sets against each other when props are to be reused. `<sheets>` is the folder
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

A set's subject or notes reworded by hand leaves the file out of the kit's layout, and its check refuses it for
spacing alone: `envkit onboard layout --set <set file>` writes it again as the kit lays a set out.

## When something looks wrong

- **Part of the picture is smudged, or has a mesh printed on it, while the rest is crisp** (the power station: a
  warning sign crisp below the height of the fence's razor wire and smudged above it; user, 2026-11-17: "most of the
  texture is crisp and only some parts look smeared. Are those detectable and repairable in a systematic way?"). The
  generator makes a thing drawn in front of a surface into geometry of its own and invents the surface behind it,
  which it draws soft; what was seen through a framed mesh it prints onto the surface behind.
  `envkit smears --source <root>/meshy/models/<key> --height <metres> --view front --view back --output <scratch>`
  finds both from the model's geometry, seen from each side a reference was drawn from square on (`front`, `back`,
  `east`, `west`), and lets the picture confirm each point: `smudged` (behind something nearer, and holding less fine
  detail than the cleanly seen surface), `printed` (inside a frame of nearer things, and holding more) and `plain`
  (the geometry points at it and the picture shows nothing wrong). It writes `smears.json`, the patches largest first
  with their boxes in metres on the model as `view` stands it, and `marked`, a copy of the model with the patches
  painted on (red smudged, yellow printed, blue plain): draw it with `view --source <scratch>/marked --height
  <metres>`, or `--eye` through a game set of one line. It needs scipy, as `onboard boxes` does. On the power
  station its red lay on the bands behind the razor wire and its yellow on the fence panels printed on the walls; a
  bare wall between two pipe runs was marked too, partly yellow, so a patch is a place to look. On a front crowded
  with balconies, pipes and awnings (Aurora Warrens) most of the wall is behind something and most of it is marked,
  nearly all `plain`: its `smudged` there has not been checked by eye. Surface no reference saw is invented whole and
  comes out as detailed as the rest, so it is counted (`shares.unseen`) and not listed. State a `smooth`, `copy` or
  `paint` from a patch's box; a repair is no sharper than the map (the power station's has 43 texels a metre against
  108 to 300 on a prop), so a sign or lettering that must read close up wants a piece of its own or a prop.
- **A lit part does not light.** `envkit view ... --lit` counts for each lit part the texels its box holds and
  the texels it lights (`litParts`). A box that holds much and lights nothing is on the wrong part of the
  model, or on a part too dark to shine.
- **A lit strip sits beside its window or sign** (above it, short of one end, or shifted as the camera moves).
  A lit part with no colour test lights everything in its box, the wall round a recessed window too, and a box
  read off a drawing too fine for the texture is read wrong: the Iron Sight Arms range windows were lit 0.35
  metres too high and the shop's sign 0.25 metres short of one end (operator, 2026-11-14). Draw a building at
  60 to 120 pixels to the metre, where its texels still touch, and bound the box in depth (y on a front wall)
  to the lit surface itself: glass in a recess stands behind the wall's face. `litParts` gives each part's
  `planes`, the depths its light stands at with their shares; a window that shows the wall's depth as a second
  plane is lighting the wall. Each lit part spreads from halo cards of its own, just in front of its own
  foremost light, so name a sign, the windows under it and the strip lights over them as separate parts. A small part named on
  its own (a scanner, a lock panel, a lamp on a post) keeps its card however small it is; a stray end of a large
  part under 0.05 m² gets none (`glow.MAIN`: a check of the four older sets on 2026-11-15 found eight small parts
  that cards of each part's own would have left without a glow). The measure is what the part shows on the
  upright side it lights most, not its whole light: a lamp that shines mostly downward shows little on any side,
  and the Pulse Tech repair bench's lamp lens had no card until it was (2026-11-15).
  For a model with a halo, `litParts` also gives each part's `standOff`: how far in front of its light the card
  that spreads it stands. About nothing is a card of its own; 0.3 metres or more is another part's card, and the
  glow will hang in front of the part and slide off it from a slant; `null` is no card, a part that only glows on
  its own surface (one that faces up or down, or a stray end).
  Look at every lit part close and from a slant in the night check. A prop's boxes are bounded in depth the same
  way: the shooting booths' lane-screen box ran front to back and lit rust specks on the back and the hazard
  stripes on the dividers.
- **A window, lamp or half of a prop stays dark at night** while its twin glows. The lit boxes were drawn for
  the side that was looked at: the Iron Sight Arms range wing has the same window strip on its far wall, its
  rifle cabinet a second door the generator drew dark, and its roof mast two amber lamps, all found unlit by the
  operator or after (2026-11-14). Draw every side by day before stating the lit parts
  (`--model <name>:0123`), roof gear included, and light or note each window, screen and lamp drawn there.
  `view --lit` lists `mirrors`: where a lit part's box, turned over the model's middle left to right or front
  to back, lands on as much surface with far less of it lit. Look at each by day; a sign's mirror is a bare
  back wall and is left. A half the generator drew dark takes the lit half's picture with `copy` and a lit part
  of its own, its `value` set lower, the copy being a little duller. In the night check, look at the far side
  too.
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
- **A roller or bay door is one flat colour, its slats lost** (the Ghost Riders garage: a flat dark blue with a few
  stray flecks; user, 2026-11-15: "garage and bay doors seem to have problems on a lot of the meshy models, can we
  add reusable checks and repairs for that?"). `game` and `tiles` look for it on every model: each upright panel the
  size of a door that the picture draws in one flat colour, starting near the ground, is an entry of `blankPanels`
  in the report and a note (`convert.blank_panels`) that gives the `smooth` entry which draws it again as slats.
  Look at the panel with `view --eye`; where it is a door, copy the entry into the game set, pull its box in to the
  door's own edges (clear of the jambs, a strip light over it, bollards in front), add a `colour` where the
  generator's shade is wrong, and build again: a panel whose middle lies in a `smooth` box with `slats` is told no
  more. A painted steel plate and the inner face of a wall read the same and are left: a note is a place to look.
  Slats drawn finer than the texels (the moiré above) are not found by this check; the repair is the same.
- **Flames, a fire or a torch came back as a solid, still mesh** (the Ghost Riders burn barrel; user, 2026-11-15:
  "we should remove the flames from the barrel and add that as a vfx"). Take the flames off with a `clear` box
  from just above what burns and state the fire: `"fire": [{"part": ..., "at": [x, y, z], "width": metres}]`, on
  the finished model, at the fire's foot. The game then draws the stock medium flame's own flames there
  (`convert.fire_lines`), scaled to the width, by day and by night. A placeable only; a fire further than 0.3
  metres from the model is refused. A fire that should light the ground takes a `light` in an orange row of
  `lightcolor.2da` (31) at its foot, and what it burns down to is a bed of embers (the next row). A model
  with a fire is compiled by `convert.compile_placeable`: a twin without the fire passes the usual read-back check,
  and the model itself is decompiled again and must hold its fire and every face. A script puts the fire out and
  lights it again by the model's animations (`docs/envkit/lights.md`, A fire), so the prop is placed not static and
  `check lights` stands it among the lit props. A model with a fire takes no `lit` parts: one script for both
  left the flame burning (client, 2026-11-16), and such a set is refused. What should glow on it is its bed of
  embers; a lamp on it is another prop. See the flames in `check props` by day and by night.
- **Embers are one flat glowing colour** (the Ghost Riders barrels: a block built under the charred wood in the
  colour of one glowing texel and lit; user, 2026-11-16: "the embers in the barrel don't look like embers"). A
  built member is one colour all over, and a lit box only brightens what the picture already draws. State the bed
  instead: `"embers": [{"part": ..., "at": [x, y, z], "radius": metres}]`, the middle of its rim on the finished
  model. It is a low mound of its own (`convert.ember_beds`) with a picture of its own, `<name>_e`: dark lumps of
  charcoal under ash with the fire in the gaps between them (`convert.ember_picture`), shown as bright by night as
  by day and left glowing when a script puts the fire out. A placeable only; a bed stated away from the model is
  refused, and so is one over 0.6 m in radius, whose lumps would be too large to read as coals. A prop with a fire
  or a bed of embers says whether it casts a light, as a lit one does (`light`: a row for a fire, null for embers). See it from above in `check props` by day and by night: `view` does not draw it.
- **A floor marking or pad came back as a wedge**, thick at the back and thin at the front (the Ghost Riders parking
  pad, drawn from a slant: half a metre thick at its back at its true width). Scale it by `height` until its
  footprint is right (`view` gives the bounds), then `"level": 0.03` lays its top flat at that thickness, what
  stands proud of the top (wheel stops) left as proud (`convert.levelled`), and `"underfoot": true` gives its
  placeable no block to walk into. Boxes are measured on the model as levelled (`measuredAt` states `level`).
- **A placeable on legs cannot be walked under** (a gantry crane, a canopy on posts: its collision is one block on
  its whole footprint; user, 2026-11-15: "the crane placeable should NOT block walking underneath it"). State
  `"walkUnder": true`: the placeable gets a block for each part of it that stands under head height, told apart
  where 0.6 m of clear ground lies between (`convert.standing`), and the report's `walkBlocks` says how many. Only
  the `.pwk` changes. Every prop that spans something is asked this when its set is written.
- **A raised floor a character should walk on is closed** (a loading bay, a dock apron). A broad flat floor up to
  0.75 m high is walked at its own height (`tile.DECK`, `DECK_AREA`); a higher one, or one under 9 m², is closed.
  `walk.png` shows which. A floor up to 1.5 m high (`tile.PLATFORM`), a loading platform, is walked on where stairs
  lead up to it: steps no taller than 0.35 m down to the ground, no steeper than 1.25 rise over run overall
  (`tile.RISER`, `STAIR`). The walkmesh climbs the stairs, and the platform's edge is closed elsewhere, so no walk
  steps off it (user: "the stairs up onto platform, and the platform itself should be walkable", the rail freight
  depot, 2026-11-13). Without stairs it stays closed. A platform across a tile line is walked by short walks: no
  path node can say a way onto it or along it from tile to tile, since every exit lies at a side's middle, off the
  platform. In the depot a walker went up the stairs from the ground and nine metres along the deck over a tile
  line; one sent twenty metres along it gave up after eight, and ones sent onto its far end from the ground stopped
  at its edge. `walk.png` draws such ground pale, and the check sends no long walk there.
- **Something the generator stood on the floor leaves too narrow a way** (orange on `walk.png` where a character
  must pass, or a `tiles` note of walk cells no walk is planned onto). A path needs a metre clear. Take the thing away with
  `clear`: `{"part": ..., "box": ...}` on the finished model takes every face whose middle lies in the box. Start the
  box a couple of centimetres above the floor, so the floor stays and what stands on it goes, and draw the place again:
  marks the thing left painted on the floor stay. A box that takes nothing is refused.
- **A walker walks straight at its target and stops at the first wall** (a walk check's walker stopped on the
  straight line from where it started). The engine found no route it could follow and gave up. It plans a long walk
  over the tiles' path nodes, from one exit to the next, each at the middle of a side. It does not go far aside round
  a wall between two exits, and a target on a tile split into regions can be taken for the wrong region's ground.
  `tiles` states a side as an exit only where it opens within 3 m of its middle (`tile.REACH`), joins two exits only
  where a walk between them stays within 2 m of the straight way (`tile.ASIDE`), and chooses the group's nodes
  together so walks reach the most ground (`tile.path_nodes`; the report gives each tile's node, and as `offPath` the
  ground no walk is planned onto). The engine takes a target by a side for that side's own: of nodes that reach as
  much, `tiles` takes those that leave no exit cut off from every way out, and notes any it cannot (`tile.cut_off`).
  The rail freight depot's walkers to its warehouse door and its crane's north leg, on the line between its middle
  columns where both tiles had left their shared side alone, walked straight at them (2026-11-13). Its south
  walker, bound for ground by a tile's west side whose east side opened into the service bay's yard, still gave up
  until that tile was stated without its east side (W, no turn). Where walkers still give up, try other nodes for
  the tiles they were bound for:
  edit `PathNode` and `Orientation` of those tiles in the installed set files (copy them aside first), rerun the walk
  check, and state what works under `tiles.nodes` in the game set (`{"t12": {"node": "A", "turn": 0}}`). Then
  rebuild and install. The Saeder-Krupp yard states three this way, and so does the rail freight depot. Walks into
  its service bay's fenced yard, open only at its east end, arrived from the north and walked straight into the fence
  from the south or the east, from outside the group or inside it. The tile east of the yard joined its south and east
  sides to the west side that opens into the yard, past the fence's end. Stated J turned 90 (south with east, north
  with west), walks from the south go round by the next tiles and come in from the north. The tile north of the yard
  had its south side open onto the metre of yard behind the north fence, and a walk to the ground just north of that
  fence was planned into the yard. Stated I turned 270, without its south side, that walk arrives (2026-11-13). To find
  which way in fails, send walkers from chosen starts: a scratch script that wraps `checks.walk_plan` and calls
  `checks.group`, as the walk check does. A short walk into ground with one far way in
  (`pocket-near`) can still give up where long walks arrive: say so in the provenance. A walker that stops near its
  target with something drawn in the way between (`walk.png`) has not arrived, however near: the depot's walker from
  the next tile into the service bay's fenced yard stopped against the fence, half a metre from a target just inside
  it, and passed the check that way until it looked across the gap (`checks.walled`, 2026-11-13).
- **The `west` or `east` walker of a group two rows deep stops in the middle of the north row, whatever nodes are
  stated.** Its target is the last open ground straight in from the middle of that side, which in a group of two
  rows lies on the line between them, and where the building fills its tiles from side to side that ground is a
  narrow strip at the group's edge. The walker comes from the far north corner, is planned into the north tile by its
  north side and finds no way down the strip. Before changing nodes, send walkers of your own to the same spot from
  the next tile out on that side and from the south corner, with the scratch wrapper above. If they arrive, the
  ground is reached and only the one long walk gives up: say so in the provenance, with the starts that arrived.
  Aurora Warrens' west walker stopped at the same spot under three settings of its nodes, and Night Bazaar's west and
  east walkers both stopped so; in each the walkers from beside and from the south corner arrived (2026-11-16).
- **Walkers into a fenced yard arrive in the tile that holds its gateway and give up in the next.** A planned walk
  did not cross from one tile to the next inside the Shiawase Barrens power station's fenced yard, which stands on
  the building's slab: as a 3 by 2 group with one gateway in the middle tile, walkers to the door and the middle of
  the yard arrived and those to its east and west ends walked straight at the fence, with the nodes chosen and with
  the end tiles stated; as a 2 by 2 group with the one gateway in the west tile, the walker to the door in the east
  tile gave up as well (2026-11-17, both tilesets, five builds). Give every tile of the yard a gateway of its own on
  the middle of a side that faces out, and state each of those tiles a node of that one side (`N`, turned), so no
  walk is planned from tile to tile inside the fence: with a vehicle gateway before the roller door and a personnel
  gateway before the tunnel door, every walker arrived. Fit the site to as few tiles as hold it first: at three tiles
  wide the fences ran through the middles of the end tiles.
- **A walk check that passed fails after a rebuild that changed nothing walkable** (an underfoot part, a `clear`).
  A rebuild can draw every tile's walkmesh faces a little differently, and a walk the engine can only just plan
  comes out either way. The depot's crane rails and the crane's own stub rails taken away left `walk.png` the same,
  yet its walker to the ground beside the crane's north leg then walked straight at it every time, in both tilesets
  (2026-11-13). The leg's edge lay on the line between two tiles, on the middle of their shared side, where the
  engine puts the exit between them. Swapping the tiles' walkmeshes back one by one showed it was those two tiles
  alone. Moved a metre north, clear of the side's middle, it arrived. So run the walk check again after every
  rebuild, and keep the edge of anything long and heavy that crosses a tile line off the middle of that side by a
  metre or more where the layout allows.
- **Two faces on one plane, both facing out.** A generator makes a thin sheet of two faces back to back; the back
  one ties with the front from outside, so `convert.turn_faces` took it for a face wound wrong and turned it onto the
  front, where the game may draw either. It now leaves such a face as it is (`convert.back_to_back`): from a third to
  over half of what it turned on each of the rail yard's models were such faces (2026-11-13).
- **A flat side shows a lighter or darker triangle only from some angles** (on whichever flat panel is seen
  side-on). That is the area's sky reflected in a large smooth face, not the model: the rail yard's boxcar showed it
  on either side, turned either way round, with its maps flat and its faces split small (client, 2026-11-13).
  Leave it.
- **What stands behind a prop shows through it** (through the gaps of a slatted lid, through an opening in a wall).
  The generator drew the box from outside only, so its far walls are not drawn from inside. `"inside": true` on the
  model in the game set gives every face a back (`convert.backed`; twice the triangles), and the opening shows the
  prop's own inside: the rail yard's dumpster (user: "the dumpster has some see through spots", 2026-11-13), and
  likewise a slit at its 20 ft container's door end and an opening under the back of its dock's roller door. Closing
  faces (`close`) would stretch the picture across such an opening. Use it only where an opening shows: a closed box
  never needs it.
- **A prop is the wrong size beside the figure.** Read the doors, wheels and lamps, not the whole: the rail yard's
  office module stood 3 metres to its ridge, sounding right, but its walls were 2 metres and its doors about 1.7; its
  light tower's lamp heads were nearly 2 metres across at 7.5 metres tall (user: "the office? It's tiny", 2026-11-13).
  Set `height` again (with the boxes of any lit part scaled to match and `measuredAt` with them).
- **A placeable a character should walk on** (a platform, a deck, a dock). The game stands characters only on the
  tiles' walkmeshes; a placeable's walkmesh (`.pwk`) only keeps them out, whatever its faces' materials. Tried in the
  client on 2026-11-13: the loading platform placed static with a walkmesh of a walkable deck, walkable stairs up to
  it and closed sides; the walkers sent onto the deck, by the stairs and from beside it, stopped on the ground at its
  edge. A floor to walk on is a part of a tile group (`tiles.parts`), as the rail freight depot's platform is; as a
  placeable it is scenery to walk round.
- **A railway car's wheels miss the rails, or sink into them.** A generator draws the trucks under the car's sides:
  the rail yard's four cars had the backs of their wheels 0.75 to 0.9 m either side of their middle, where a
  standard-gauge wheelset's stand 0.68, so the wheels ran 0.15 to 0.2 m outside the rails; and stood on the ground,
  they sank the track's height into them (user: "fix the wheel spacing on the rolling stock", 2026-11-13). Read the
  trucks' spans along the car, the top of the trucks and where the wheels' backs stand, from end views cut through
  the wheels, and state them as `wheels` (`convert.gauged`); lift the car by `track.HEIGHT` (0.312). Check it on laid
  track in the client, low along the rails and beside each truck.
- **A hole of many corners in a wall, or a gap the client shows where the model looks closed.** A generator leaves
  slits and gaps with a dozen or more corners (the rail yard's warehouse wall and crane leg sills, user, 2026-11-13).
  Find the rim from a z-buffered elevation (open edges are the faces' edges used once) and state a point on it as
  `fill` (`convert.filled`), not face by face as `close`. Where the faces are there but wound inward, the client shows
  a gap all the same: give the faces in a box backs (`inside: [{box}]`, `convert.backed`). Check both from every side.
  A fill is drawn between its rim's own corners, and where the picture draws those far apart it shows a streak of
  whatever lies between them (the wedge at the foot of the Chop Shop clinic's back wall, 2026-11-14): give the
  fill a `picture`, a point on the wall beside it, and it is drawn wholly in the wall's colour there.
- **A sign spelt wrong.** Paint the stray strokes over in the sign's ground colour (`paint`), measured on a texel
  elevation of the letters (the rail yard's tower read "PREIGHT"; its P's bowl and bar were painted to make an F).
- **Wavy handrails, missing stairs or a leg out of place.** A generator cannot hold a long thin rail straight, leaves
  off stairs to a raised deck and may draw a leg in from its corner (the rail yard's stair tower and walkway, user,
  2026-11-13). Take the wavy rails off with `clear` rods (`{from, to, radius}`) along the flights and boxes on the
  landings, and build straight ones (`built`: `railing` paths on the surface walked, `stairs` from the foot's nosing
  to the deck's edge), coloured from a point of the model's own steel. Move a stray leg whole with `move` (`{box,
  by}`); what tied it on is taken away, so clear what is left standing. Check the treads, rails and leg in the client.
- **Smeared glass.** A generator may draw a window's glass in several layers that share their picture with other
  faces, so `paint` misses some of it (the rail yard's office module, 2026-11-13). Cover each pane with a thin built
  bar (`built`, `bar`, coloured from a dark glass point) just in front of the layers, inside its frame, measured from
  the frame's profile across the window; build a frame-grey bar over a mullion drawn light. Check both faces.
- **A lamp glows but lights nothing round it** (a light tower, a street lamp). A glow map lights only the model's
  own faces. Give its `placeable` a `light` (`{"colour": <lightcolor.2da row>, "at": [x, y, z]}`, at the lamp) so
  its row casts light as the stock lamp post's does (user, of the rail yard's light tower: "Yes, try it",
  2026-11-13). `check lights` puts it out and on with the faces; the ground should go dark and come back.
  Decide it for every lit prop when its game set is written: the set is refused until a lit prop's `placeable`
  states `light`, a light for what should be bright (a lamp, a floodlight, a work light) and `null` for what only
  glows (a screen, a sign, an indicator, strip lights in a case). The Chop Shop clinic's surgical lamp was
  converted with glowing lenses and no light (user, 2026-11-14: "the lamp needs a light", "make sure you are
  checking for when props need lights from now on", "it should only be for things that should be bright"). A cast light
  is for what lights the area round it as well as glowing (user, 2026-11-15, of a hand scanner terminal and a
  console whose top lamps had been given lights: "just the glow is fine"): a terminal's or console's lamp bar,
  a status lamp and a screen take `null`. A small lamp on a prop takes row 1 (DimWhite); rows 2 and 3 are for
  floodlights and tower lamps, and hang a flare as wide as the prop on a small one. A row
  holds one light: of several lamps on one prop it stands at one of them, at or just inside its housing (where, and
  why not under the lens or between two lamps, is told next). See it in `check props --mode night`, the ground and
  the figures lit round it.
  The game draws a star-shaped flare where the light stands. It shows through a thin part of the model round it
  (a beam 0.2 metres thick, a lamp's housing) and is hidden only by what stands well in front of it. One light
  for two lamps apart (a gate's posts) or a row of them (three booths), set between or above them, hangs a star in
  the air or on a bare beam: the Ares and Saeder-Krupp gates' and the Iron Sight Arms booths' lights did
  (2026-11-14). So a light stands at a lamp, where the flare is the lamp's: of two lamps apart at one of them, of a
  row at the middle one, at or just inside its housing. Warning beacons only glow. `game` refuses a light more
  than 0.3 metres from the model (`convert.light_gap`) and reports the distance as `lightFromModel`.
- **A glass front, window or cover came back as its frame alone**, or drawn solid (the Chop Shop clinic's
  cyberware case: the two bars of its slanted front and nothing between them; user, 2026-11-14: "Fix the case
  glass too"). State the panes as `glass`: `[{"corners": [3 to 8 points round a flat pane]}]`, with a
  `colour` (`[r, g, b]`) and a `strength` (0 to 1) where the pale blue-grey sheen it has without them will not
  do. Read the corners from the frame's own vertices in the converted model's source file; a bowed bar takes two
  panes. Each pane is a node of its own, seen from both sides, showing `<name>_g`, a picture added to what is
  behind it: a pane laid over what is behind it (a node's `alpha`) hid the halo of the lights inside the case.
  A placeable only: a tile group does not draw it. See it in `check props` by day and by night, the halos of
  the lights behind it too.
- **Half of a sign or emblem is smeared** while its other half is clean, on something drawn the same both ways
  (the Chop Shop clinic's banner: the right half of its caduceus, on both faces of the cloth). `copy` with
  `"mirror": true` lays the clean half over it from the middle outwards; measure the middle on a gridded
  `--eye` view. A repeating band beside it (stripes) takes a plain `copy` from a whole number of repeats away;
  where the band sags along its length the copy meets it a step out, and `rise` (metres, the height of the step)
  takes the copy from that much higher.
- **A label or sticker the generator invented on a plain panel** (the Chop Shop clinic's vending machine: an
  orange label with scribbled lettering on both sides and the back). A copy keeps each height's own band of the
  wall, so it cannot come from the clean panel above or below: cover each half of the label with the panel beside
  it at the same heights, `"mirror": true`, the two boxes the same length, so that the panel runs on unbroken at
  the label's edges. A faint patch is left where the streaks of the panel stop at the box's top and bottom.
- **A hole only one side shows.** The front, back and side of the client check miss a gap under a rear rim, a
  slot between lids, a length of pole wound inward (the Chop Shop clinic's bin, dumpster and lamp, 2026-11-14).
  `game` reports `seenFromBehind`: the largest patch of the model seen from behind, in cm², and the way it was
  looked at. Look from that way with `--eye` (the game draws nothing there, so the background shows): a hole into
  a box takes `"inside": true`, a part wound inward `inside` boxes. Glass the generator wound inward reads as an
  open front and is left (the clinic's cyberware case, about 1,800 cm² from above). Review every prop from its
  four corners, above and below before the client check, beside its reference.
- **A pale, blocky patch across a window or doorway**, cutting off what is drawn behind it. The generator laid a
  stray face or two over the opening, a square metre each, drawn as a smear: the Pulse Tech shop's left window
  pane (operator, 2026-11-15: "the front window has a pretty major defect. I'm surprised you didn't see that";
  it showed in the gridded front view and was passed over). The full generation has it too, so another reduction
  does not mend it (5 credits spent finding that out), and a `copy` over it stays blocky, the face having few
  texels. `tiles` tells them: each large face lying just in front of fine detail that looks the same way is a
  note and an entry of `veils` in its report, with its size, its middle and how much of it the detail covers
  (`convert.veils`). Look at each close up; take a stray one out with a `clear` box that holds its middle alone,
  narrow in depth, and what the generator drew behind it shows. A pane the generator meant, with the room drawn
  behind it, is told too and is left (one in that shop's west window), so a note is a place to look, not a fault.
  Before stating a building's lit parts, draw every window and the door close up in perspective (`--eye`, 80
  pixels to the metre or more, square on and from a slant) and compare each with the reference: the see-through
  square-on drawings and a view of the whole front do not show it. Never draw a building's full generation
  (`meshy/masters`) with `view`: it took 47 GB of memory and stopped another session's client run.
- **A model of an older sheet has to be converted again** and its sources went into an archive with the worktree
  that made it. `envkit restore --archive <archive> --models <game set> --model <name> --output <folder of your
  own>` copies each model's whole source folder out, checked against the archive's hashes, and prints the root
  to give `game`, `tiles` and `view`. The archive is only read. A folder restored by hand with the model and its
  colour map alone serves `view` and fails `game` at the first missing map (2026-11-15).
- **A question about how the engine wants a tile made.** `envkit study tiles --tileset <tileset> --tile <n>
  --output <scratch>` decompiles stock tiles and tells their fade, light, door and animation lines.
  `envkit study pathnodes --tileset <tileset>` checks the path-node table against a tileset's stock tiles,
  turning each by its Orientation both ways; run it before a group goes into a tileset whose tiles were not
  looked at.

## Tests

`python -B -m unittest discover -s tools/envkit -p "test_*.py" -t .` covers the plan, the ledger, the pictures,
the set files `onboard` writes and the layouts of the checks. The client and the Toolset themselves are not started by the tests.

Before a pull request, after main is merged in, run the catalog check CI's Scope job runs:
`python -B tools/ci_scope.py --check-catalog --base origin/main --full-reason '' --output <scratch>/plan.json`.
`tools/Test-Repository.ps1` does not run it. A test that reads a new file (an envkit test that came to import
headkit's design module, 2026-11-14) leaves `tools/test-impact.json` stale, Scope fails on it and every other
job is skipped. Where it reports the catalog stale, write it again with
`python -B tools/test_impact.py --write-catalog tools/test-impact.json` and commit the file.
