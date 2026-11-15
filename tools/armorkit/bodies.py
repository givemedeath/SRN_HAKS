"""An outfit on every body: built from the Human bakes' kept parts, and looked at in the client from built packs.

`build` is the run that took Facility Security to the 20 bodies (2026-11-14 and -15), as the kit's own: the
Human male tinted from his kept parts, the Human female refit from him (her own chest kept where she has
one, `combine`), each race body refit from the Human of its gender, and every one of them baked at the
outfit's number. Each step is one of the kit's commands run as its own process, the race bodies several at
a time, with a log and a report per body beside its folders. It was two shell scripts with one outfit's
names and one machine's paths in them.

`check` is the look at the result: one client fixture on the packs as built, the bodies asked for side by
side in two poses and four views each, in the six contrasting colours (`poses.COLOURS`), and the outfit's
inventory icon. `poses` looks at one bake in six poses; this looks at what a publication would ship, on
many bodies at once.
"""
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import bake, client, measure, poses, registry
from . import client_fixture as fixture
from .registry import require

REPORT = 'bodies.json'  # what `build` found on each body, in its output folder
HUMANS = {'m': 'pmh0', 'f': 'pfh0'}  # the body of each gender an outfit is made on; the others are carried from it
OWN = ('chest',)  # the parts a Human female keeps of her own bake, where she has one: her chest is cut for her
# The head each kind of body is looked at with: one of the published heads of its race and gender.
HEADS = {'pmh': 86, 'pfh': 28, 'pmd': 19, 'pfd': 13, 'pme': 20, 'pfe': 18, 'pmo': 15, 'pfo': 13, 'pmg': 1, 'pfg': 1}
CAST = (('standing', 0), ('arms up', 19))  # label and the game's animation constant, as `poses.CAST` has them
# each shot as (facing in degrees, distance, label, camera height), for a Human: a taller body is looked at from further and higher
VIEWS = ((62.0, 3.2, 'front', 0.95), (242.0, 3.2, 'rear', 0.95), (62.0, 1.2, 'chest and arms', 1.15), (62.0, 1.1, 'knees', 0.5))
NAME = 'ak_bodies'  # the fixture's module
SPACING = 5.0  # metres between two actors in a row
# Actors in a row, the rows the fixture's area holds, and the metres between two rows. The rows run to and fro, so
# that the camera never goes far from one actor to the next: sent 55 m to the start of the next row it stayed where
# it was for a shot or two, and the picture under a body's label was another body's (client run, 2026-11-15).
ROW, ROWS, APART = 12, 6, 10.0
HOST = (140.0, 140.0)  # where the bare actor given the item stands: clear of every row
# The outfit as an item in a bag: the examine window, then the inventory, each announced as a shot of its own.
# It begins when the entry script says its shots are over (`fixture.DONE`), not at the time they should be:
# shots are chained and fall behind the clock on a busy client, and the item's windows would open over them
# (review of PR 162, 2026-11-15).
ICONS = '''object Mod(object it,int index,int value) {
  object n=CopyItemAndModify(it,ITEM_APPR_TYPE_ARMOR_MODEL,index,value,TRUE);
  if(!GetIsObjectValid(n)) { WriteTimestampedLogEntry("ARMORKIT icon-modify-failed index="+IntToString(index)); return it; }
  DestroyObject(it); return n;
}
void Line(string s) { WriteTimestampedLogEntry(s); }
void Bag(object pc) {
  PopUpGUIPanel(pc,GUI_PANEL_INVENTORY);
  DelayCommand(1.0,Line("ARMORKIT shot=%(second)d target=inventory valid=1"));
  DelayCommand(%(hold).1f,Line("ARMORKIT icons-done"));
}
void Show(object pc) {
  SetCutsceneMode(pc,FALSE);
  object it=CreateItemOnObject("nw_cloth001",pc);
  it=Mod(it,ITEM_APPR_ARMOR_MODEL_TORSO,%(number)d); it=Mod(it,ITEM_APPR_ARMOR_MODEL_PELVIS,%(number)d);
  SetIdentified(it,TRUE);
  AssignCommand(pc,ActionExamine(it));
  DelayCommand(1.5,Line("ARMORKIT shot=%(first)d target=examine valid=1"));
  DelayCommand(%(hold).1f,Bag(pc));
}
void Wait() {
  object pc=GetFirstPC();
  if(!GetIsObjectValid(pc) || !GetLocalInt(GetModule(),"%(done)s")) { DelayCommand(1.0,Wait()); return; }
  DelayCommand(1.0,Show(pc));
}
void main() { Wait(); }
'''


def plan(male_kept, output, briefs, number, body_pack, *, body_textures=None, own=None, own_parts=OWN, bodies=registry.BODIES,
         packs=(), game=None, tint_cache=None):
    """{body: [step]}: the kit commands that put an outfit on each of `bodies`, in the order they run.

    `male_kept` is the folder a bake of the Human male kept his parts in (`bake --kept`), `briefs` the brief
    of each gender, {'m': file, 'f': file}, `number` the outfit's registry number and `output` the folder
    everything is written under: `<body>` the bake, `<body>-kept` the parts it is tinted from, `<body>.log`
    what the bake said, `<body>-refit.json` what the refit reported (a record a publication pins). `own` is
    the folder a bake of the Human female kept her own parts in, of which she keeps `own_parts` and takes the
    rest from the male (`<pfh0>-carried`, `combine`); without it all her parts are his, refit. A race body is
    refit from the Human of its gender as this run keeps it, so that Human is built first and must be among
    `bodies`, or lie in `output` from an earlier run. A step is {'arguments', 'stdout', 'stderr'}: a command
    of this kit and the files its output goes to."""
    output = Path(output)
    require(set(briefs) == set(HUMANS) and set(bodies) <= set(registry.BODIES) and bodies, 'An outfit is built on bodies of the 20, by a brief for each gender (m, f)')
    kept = {'m': Path(male_kept), 'f': output / (HUMANS['f'] + '-kept')}
    theirs = [name for name in bake.listing(male_kept)['parts'] if own is None or name not in own_parts]
    require(own is None or (own_parts and theirs), 'A Human female with a bake of her own keeps some of its parts and takes the others from the male')
    skin = ['--body-textures', str(body_textures)] if body_textures else []

    def refit(source_kept, target_kept, source, target, more=()):
        return ['refit', str(source_kept), str(target_kept), '--body-pack', str(body_pack), *skin, '--from', source, '--to', target, *more]

    def tint(body, parts):
        arguments = ['bake', str(briefs[body[1]]), str(output / body), '--number', str(number), '--body', body, '--body-pack', str(body_pack), *skin,
                     '--kept', str(parts)]
        for pack in packs:
            arguments += ['--pack', str(pack)]
        arguments += (['--nwn-root', str(game)] if game else []) + (['--tint-cache', str(tint_cache)] if tint_cache else [])
        return {'arguments': arguments, 'stdout': output / (body + '.json'), 'stderr': output / (body + '.log')}
    steps = {}
    for body in sorted(bodies, key=lambda body: (body not in HUMANS.values(), body)):
        gender, human = body[1], HUMANS[body[1]]
        report = {'stdout': output / (body + '-refit.json'), 'stderr': output / (body + '-refit.log')}
        if body == HUMANS['m']:
            steps[body] = [tint(body, male_kept)]
        elif body == HUMANS['f'] and own is not None:
            carried = output / (body + '-carried')
            steps[body] = [{'arguments': refit(male_kept, carried, HUMANS['m'], body, ['--seat-in', str(own), '--parts', ','.join(theirs)]), **report},
                           {'arguments': ['combine', str(briefs['f']), str(kept['f']), '--from', f'{own}={",".join(own_parts)}', '--from', f'{carried}={",".join(theirs)}'],
                            'stdout': output / (body + '-combine.json'), 'stderr': output / (body + '-combine.log')},
                           tint(body, kept['f'])]
        else:
            mine = output / (body + '-kept')  # the Human female without a bake of her own is the male's, refit whole
            source = (male_kept, HUMANS['m']) if body == HUMANS['f'] else (kept[gender], human)
            steps[body] = [{'arguments': refit(source[0], mine, source[1], body), **report}, tint(body, mine)]
    return steps


def command(arguments, stdout, stderr):
    """Run one command of this kit as its own process, its output kept in the two files: the exit code. It runs
    where this process does, so a relative path is the same folder to both."""
    root = str(Path(__file__).resolve().parents[2])
    environment = {**os.environ, 'PYTHONPATH': os.pathsep.join(filter(None, (root, os.environ.get('PYTHONPATH'))))}
    with open(stdout, 'wb') as out, open(stderr, 'wb') as err:
        return subprocess.run([sys.executable, '-B', '-m', __package__, *arguments], env=environment, stdout=out, stderr=err).returncode


def build(male_kept, output, briefs, number, body_pack, *, jobs=3, run=command, say=lambda *_: None, **given):
    """Build an outfit on every body `plan` names (its arguments, and those in `given`): the report, also
    written to `<output>/bodies.json`.

    The Humans are built first, then the race bodies, `jobs` bodies at a time (user decision 2026-10-07:
    three). A body none of whose folders may exist yet is refused before anything runs: bakes and kept parts
    are not written over. A step that fails stops its body there, and a race body is not begun when the
    parts it is carried from were not kept: a Human whose bake fails its gates has kept them all the same.
    The report holds, per body, its `folder`, whether its bake's gates `passed`, their `failures`, the
    outfit's `triangles`, the `seconds` it took and, where a step failed, the `failed` command with the log
    to read. A bake whose gates fail is a failed step (`bake` exits 1) that has written its record, so its
    gate failures are in the report too."""
    output = Path(output)
    steps = plan(male_kept, output, briefs, number, body_pack, **given)
    fresh = [output / (body + ending) for body in steps for ending in ('', '-kept', '-carried') if not (body == HUMANS['m'] and ending)]
    require(not [path for path in fresh if path.exists()], 'These are built already, and are not written over: ' + ', '.join(str(path) for path in fresh if path.exists()))
    for body in steps:
        human = HUMANS[body[1]]
        source = male_kept if human == HUMANS['m'] else output / (human + '-kept')
        require(body == human or human in steps or (Path(source) / bake.KEPT).is_file(), f'{body} is carried from {human}, whose parts are not kept in {source}')
    output.mkdir(parents=True, exist_ok=True)
    report = {}

    def one(body):
        began = time.monotonic()
        found = {'folder': str(output / body), 'passed': True}
        try:
            for step in steps[body]:
                if run(step['arguments'], step['stdout'], step['stderr']) != 0:
                    found.update(passed=False, failed=step['arguments'][0], log=str(step['stderr']))
                    break
            written = output / body / 'bake.json'
            if written.is_file():
                gates = json.loads(written.read_text(encoding='utf-8'))['gates']
                found.update(passed=found['passed'] and bool(gates['passed']), failures=gates['failures'], triangles=gates.get('triangles', {}).get('outfit'))
            elif 'failed' not in found:
                found.update(passed=False, failed='bake', log=str(steps[body][-1]['stderr']))  # it said it was done and wrote no record
        except (OSError, ValueError, KeyError, TypeError) as error:  # one body's fault is its own: the others' results are kept
            found.update(passed=False, failed='report', log=f'{type(error).__name__}: {error}')
        found['seconds'] = round(time.monotonic() - began, 1)
        say(f'{body}: {"passed" if found["passed"] else "FAILED" + (" at " + found["failed"] if "failed" in found else "")} in {found["seconds"]:.0f} s')
        return found
    humans = [body for body in steps if body in HUMANS.values()]
    races = [body for body in steps if body not in HUMANS.values()]
    with ThreadPoolExecutor(max_workers=max(1, int(jobs))) as pool:
        report.update(zip(humans, pool.map(one, humans)))  # neither Human waits for the other: both are made from the male's kept parts
        for body in races:
            human = HUMANS[body[1]]
            source = Path(male_kept) if human == HUMANS['m'] else output / (human + '-kept')
            if not (source / bake.KEPT).is_file():
                report[body] = {'folder': str(output / body), 'passed': False, 'failed': 'not begun', 'log': report.get(human, {}).get('log', '')}
                say(f'{body}: not begun, the parts of {human} were not kept')
        begun = [body for body in races if body not in report]
        report.update(zip(begun, pool.map(one, begun)))
    document = {'schemaVersion': 1, 'kind': 'srn-armorkit-bodies', 'number': number, 'passed': all(found['passed'] for found in report.values()), 'bodies': report}
    (output / REPORT).write_text(json.dumps(document, indent=1) + '\n', encoding='utf-8', newline='\n')
    return document


def place(index):
    """Where actor `index` stands: in rows of `ROW` that run to and fro, each next to the one before it."""
    row, along = divmod(index, ROW)
    return (12.0 + SPACING * (ROW - 1 - along if row % 2 else along), 20.0 + APART * row)


def cast(bodies, worn, statures, colours=None, heads=None, cast=CAST, views=VIEWS):
    """(actors, shots, labels) of a client check: every body of `bodies` wearing `worn` ({slot: number}) in each
    pose of `cast`, with the shots of `views` round it. `statures` gives each body's height as a share of the
    Human of its gender's: its camera stands that much further off and higher, never nearer than a Human's."""
    heads = {**HEADS, **(heads or {})}
    # A single row of 40 actors ran out of the fixture's area, 160 m a side, at the thirtieth (review of PR 162, 2026-11-15).
    require(len(bodies) * len(cast) <= ROW * ROWS, f'The fixture has room for {ROW * ROWS} actors, {len(cast)} a body: not for {len(bodies)} bodies')
    actors, shots, labels = [], [], []
    for pose, animation in cast:
        for body in bodies:
            require(body in registry.BODIES and body[:3] in heads, f'{body} is no body with a head to wear')
            index, stature = len(actors), float(statures[body])
            actors.append({'label': f'{body}, {pose}', 'body': body, 'head': heads[body[:3]], 'position': place(index), 'parts': dict(worn),
                           'colours': poses.worn_colours(colours), 'script': 'ak_pose', 'vars': {'ANIM': animation}})
            for facing, distance, view, height in views:
                shots.append({'actor': index, 'facing': facing, 'distance': round(distance * max(1.0, stature), 3), 'pitch': poses.PITCH,
                              'height': round(height * stature, 3)})
                labels.append(f'{body}, {pose}, {view}')
    return actors, shots, labels


def statures(bodies, body_pack):
    """{body: its head's height as a share of the Human of its gender's}, read from the bodies' models."""
    height = {body: float(measure.rig((Path(body_pack) / (body + '.mdl')).read_bytes())['head_g'][2, 3])
              for body in {*bodies, *(HUMANS[body[1]] for body in bodies)}}
    return {body: height[body] / height[HUMANS[body[1]]] for body in bodies}


def published(parts, number, bodies=None):
    """(slots, bodies) of outfit `number` among a registry's `parts`: the slots it fills, and of `bodies` (all the
    outfit lists, when none are asked for) those every one of its parts is made for, in the registry's order."""
    mine = [part for part in parts if part['number'] == number]
    require(mine, f'The registry holds no part numbered {number}')
    made = [body for body in registry.BODIES if all(body in part['bodies'] for part in mine)]
    missing = [body for body in bodies or () if body not in made]
    require(not missing, f'Outfit {number} is not made for {", ".join(missing)}')
    return [part['slot'] for part in mine], list(bodies or made)


def check_spec(bodies, slots, number, haks, body_pack, *, tlk=None, colours=None, heads=None, hold=fixture.HOLD, icons=True):
    """(fixture spec, layout) of the client check of outfit `number`, worn on `slots`, on `bodies`, from the
    built packs `haks` (highest priority first: the parts pack and its tables before the bodies' and heads').
    With `icons` a bare Human male beside them is given the outfit as an item, and its examine window and
    inventory icon are two more shots. Nothing of a bake is read: the fixture shows what the packs hold."""
    require(bodies and len(set(bodies)) == len(bodies), 'The client check takes bodies, each once')
    require(slots and all(slot in registry.SLOTS for slot in slots), f'An outfit is worn on slots of {sorted(registry.SLOTS)}')
    actors, shots, labels = cast(bodies, {slot: number for slot in slots}, statures(bodies, body_pack), colours, heads)
    scripts = {'ak_pose': poses.POSE_SCRIPT}
    if icons:
        actors.append({'label': 'icon host', 'body': HUMANS['m'], 'head': {**HEADS, **(heads or {})}['pmh'], 'position': HOST, 'bare': True, 'script': 'ak_icons'})
        scripts['ak_icons'] = ICONS % {'number': number, 'first': len(shots), 'second': len(shots) + 1, 'hold': hold, 'done': fixture.DONE}
    document = {'name': NAME, 'haks': [str(hak) for hak in haks], 'actors': actors, 'shots': shots, 'scripts': scripts, 'hold': hold, 'size': 16}
    if tlk:
        document['tlk'] = str(tlk)
    return document, {'labels': labels, 'columns': len(VIEWS), 'icons': bool(icons)}


def check(document, layout, output, nwn_root, *, run=False, wait=None, settle=1.2):
    """Build the client check into the fresh folder `output` and, with `run`, look: the fixture's record, with
    the `evidence` where it ran. The captures are laid out in `<output>/sheet.jpg`, a row per body and pose,
    and the two of the icon kept as `icon-examine.png` and `icon-inventory.png`. `wait` is the seconds to
    wait for another session's client to close first."""
    output = Path(output)
    require(not output.exists(), f'The client check is built into a fresh folder; this one exists: {output}')
    output.mkdir(parents=True)
    record = poses.build(document, layout, output, nwn_root)
    if run:
        if wait:
            client.wait_free(wait)
        count, hold = len(layout['labels']), record.get('hold', fixture.HOLD)
        evidence = client.run(nwn_root, record, output / 'captures', settle=settle, until='icons-done' if layout['icons'] else 'done',
                              timeout=record['start'] + (record['shots'] + 2) * hold + 300 + record['shots'] * hold)  # room for shots that fall behind
        captures = evidence['captures']
        evidence['sheet'] = str(poses.sheet(captures[:count], layout, output / 'sheet.jpg'))
        for capture, name in zip(captures[count:], ('icon-examine.png', 'icon-inventory.png')):
            Path(output / name).write_bytes(Path(capture).read_bytes())
        (output / 'evidence.json').write_text(json.dumps(evidence, indent=1) + '\n', encoding='utf-8', newline='\n')
        record['evidence'] = evidence
    return record
