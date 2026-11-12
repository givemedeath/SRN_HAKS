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
envkit reference --set ... --sheets <sheets> --output <root>/references/<run> --bindings <root>/references/bindings.json [--asset <a>] [--seed <n>]
envkit contact   --references <root>/references/<run> --output <root>/references/<run>-contact.png
```

`reference` draws each asset alone on a plain ground with the local image model on the bound ComfyUI. Start a
job only when Comfy's queue is empty, one at a time: the process is shared. `contact` puts each reference beside
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

`status` says what the sheet's unsent calls cost against what the cap has left. Raise the cap only on the
user's word, and say so in the reason. `submit` finds every reference and checks the whole of what is unsent
against the cap before it sends anything; a call already in the ledger is not sent again. Meshy queues ten
tasks: a call refused for a full queue is released, and `submit` run again sends it. `collect` waits for each
call, downloads the models to `<root>/meshy/models/<key>`, keeps the building's full generation in
`<root>/meshy/masters/<key>` and remeshes it to the plan's triangles. One failed model does not stop the rest;
give it a new key in the plan (`"key": "<prefix>-<asset>-a2"`) to send it again.

## 3. The game set

```
envkit view --source <root>/meshy/models/<key> --height <metres> --model 0123 --output <root>/view
envkit view --models tools/envkit/sets/<sheet>-game.json --root <root> --model <name>:02:300:0.25 [--lit] --output <root>/view
```

The first draws a generated model square on from each side with a metre grid, before the game set names it;
the second draws a model as its game set makes it. Read the boxes of lit parts, paint, smoothing, mesh panels,
fences and the door from the grid, in metres on the finished model, and state `measuredAt` (the height they
were read at). `--lit` shows what the lit boxes light. The drawing lets deeper faces show through nearer ones:
what a surface looks like is settled in the client, not here.

Size a building by its door: scale it until the door leaf is about 2.1 m, then choose the tile group's size.
Its door hook is door type 58. Screens and signs are lit.

```
envkit game  --models ... --root <root> --output <root>/game<n>  [--model <name>]
envkit tiles --models ... --root <root> --output <root>/tiles<n> --model <building>
```

## 4. In the client

Each check builds a throwaway module and user folder under `<root>/fixtures/<name>` (a new name every run) and
captures the views. It waits while another game client runs and never closes it.

```
envkit check props  --game <game> --models ... --root <root> --name <name> --built <root>/game<n> --model <a> --model <b> [--mode night]
envkit check group  --game <game> --models ... --root <root> --name <name> --built <root>/tiles<n> --model <building> --tileset dgt04 [--mode night|near]
envkit check lights --game <game> --models ... --root <root> --name <name> --built <root>/game<n> [--built <root>/game<m>]
```

`props` shows each prop from the front, the back and the side with a figure for scale and one behind it. `group`
needs the group installed first (the tile numbers are the pack's); `near` frees the player to show which
storeys the client hides. `lights` takes the lit props from the pack, by night, and puts them out and on again
by script, so it follows `placeables`.

Look for: scale against the figure, holes and see-through faces, smeared markings, wires and thin members,
what glows by night, the roof and upper storey from above, and the door.

## 5. Into the packs

```
envkit install    --models ... --built <root>/tiles<n> --model <building> --provenance "<section>"
envkit placeables --models ... --built <root>/game<n> --provenance "<section>"
envkit blueprints --models ... --game <game>
```

Then write the sheet's section of `PROVENANCE.md` (what was generated, by what, what was retouched, what was
checked and what was left as generated), rebuild the affected packs and run repository verification.

## 6. In the Toolset

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
- The pending tile under the cursor is the group's bottom-left. A right-click turns it.
- The mouse wheel zooms the area view; the zoom buttons do nothing.
- Leave the start point's corner tile alone: the Toolset refuses to save with the start on a tile painted over.
- Save with ctrl+s, then judge by `saved`, not by the screen: it lists the group tiles laid and the doors the
  Toolset made at the hooks (appearance 58).

`check doors` gives each of those doors an area transition to a waypoint in front of the next and starts the
client with the player free in front of the first. Someone clicks each door in turn while it logs where the
player is; `stages` in what it prints is each place the player came to.

## Tests

`python -B -m unittest discover -s tools/envkit -p "test_*.py" -t .` covers the plan, the ledger, the pictures
and the layouts of the checks. The client and the Toolset themselves are not started by the tests.
