"""One client start for many built item fixtures: a shared review session.

    python -m tools.itemkit.review_session build SESSION FIXTURE_DIR [FIXTURE_DIR ...] --nwn-root GAME_INSTALL
    python -m tools.itemkit.review_session capture SESSION CAPTURES --nwn-root GAME_INSTALL [--wait SECONDS] [--items A,B]

A fixture (the fixture stage's `fixture.json`) is one item in its own module and user directory, with its own copy of
the shared packs: a client start, a full motion cycle and a gigabyte of HAK copies per item. `build` puts any number
of built fixtures of one hand into one session:

- one user directory whose HAKs are hard links to the fixtures' pinned files (a copy only across volumes);
- one module, the first fixture's with every item's blueprint, whose entry script takes the reviewed item from a
  table (`itk_items.2da` in the session's override folder) and, when an item's scripted shots are done, swaps the
  next item into the same actors' hands;
- one small HAK on top when the item HAKs carry private base-item tables: each carrier row from the package that
  uses it, with the widest appearance range.

`capture` waits for another session's client to close if asked, starts the client once and files each item's shots
in `CAPTURES/<blueprint>/` exactly as `client_capture` does for one fixture. It writes the item table itself, so a
second run captures only the items that have no finished capture yet, and `--items` picks a subset without a rebuild
(`--again` with it retakes a finished item whose shots were rejected).

Session captures are review material, never the client stage's evidence: that evidence names the item's own fixture
module and HAKs (fixture.validate_evidence), and a session runs another module. Nothing here grants an approval.
"""
import argparse
import json
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.headkit.common import pin, read, require, verify, write
from tools.itemkit import client_capture as cc
from tools.itemkit.fixture import (HEARTBEAT_ITEM, SHOT_ACTORS, SHOT_CARRY, SHOT_TOGGLE, field, link_or_copy, shot_script, shouldered)
from tools.itemkit.publish import Tools, read_erf

REPO = Path(__file__).resolve().parents[2]
MODULE, SESSION_HAK, ITEMS_TABLE = 'itk_session', 'itk_session', 'itk_items'
ITEM_LINE, SESSION_DONE, ITEM_DONE = 'ITEMKIT_ITEM ', 'ITEMKIT_SESSION done', 'ITEMKIT_SHOTS done'
CARRIES = tuple(SHOT_CARRY)                      # a carry's number in the item table is its place here
# The session's own shots, five a body where a fixture takes sixteen: front, right side, the hand close up, the attack
# stance, and one long hold over a whole attack round, from which the driver keeps the frames with the muzzle flash.
# Rows as fixture.SHOTS, each with its own hold: a burst of three pictures overran the fixture's 1.8 s.
FIRE_CHECK, HOLD, FIRE_HOLD = 'firing', 2.6, 5.0
SESSION_SHOTS = ((1, 2.0, 'front-rear-sides', 270, 3.2, 80, 1.0, HOLD), (2, 2.0, 'front-rear-sides', 180, 2.4, 80, 1.0, HOLD),
                 (3, 2.0, 'idle', 180, 1.4, 85, 0.95, HOLD), (11, 3.0, 'attacks', 180, 3.0, 82, 1.1, HOLD),
                 (12, 0.7, FIRE_CHECK, 180, 2.6, 82, 1.1, FIRE_HOLD))
SESSION_CARRY = {'hip': SESSION_SHOTS, 'shoulder': shouldered(SESSION_SHOTS)}
SESSION_CHECKS = tuple(dict.fromkeys(row[2] for row in SESSION_SHOTS))
# The female starts four steps behind the male, so her three still shots fall in his unshot steps 5 to 7 and her attack
# steps after his: an item is over when she has finished step 12, his step 16.
SESSION_OFFSET, SESSION_STEPS = 36, 17
PARK = 1 + max(row[0] for row in SESSION_SHOTS)   # the step after an actor's last shot
FIRE_CLIPS = {61: 'fire_pst', 6: 'fire_rfl'}     # the firing clip of a carrier base item unless the build names another
FIRE_CODE = re.compile(r'fire_[a-z0-9]{1,8}')
KEEP, BRIGHT = 3, 215                            # flash frames kept of a firing burst; the grey level that counts as flash
STALL = 0.5                                      # a burst that took no picture for this long may have missed the flash
CURRENT = 'GetLocalString(GetModule(),"ITK_ITEM")'
PLAN_LINE = re.compile(r'(?m)^  if\(n==\d+\) DelayCommand\([0-9.]+,ItkTry\(.*\n?')
TYPES = {'uti': 2025, 'nss': 2009, '2da': 2017}

NEXT = '''void ItkWatch(object pc); void ItkBare(object t); void ItkGive(object actor);
void ItkDrop(object actor,string old) { if(old!="") DestroyObject(GetItemPossessedBy(actor,old)); }
// An attacking actor has turned to its target: its attack and firing shots are framed from where it faces now,
// as the plan's facing frames an actor that faces north.
float ItkFacing(object t,string check,float facing) {
  if(check!="attacks" && check!="@FIRE@") return facing;
  // Where the target is, not GetFacing: mid-attack that gave a view from the front where the side was asked for.
  object target=GetLocalObject(t,"TARGET"); if(!GetIsObjectValid(target)) return facing;
  float aim=VectorToAngle(GetPosition(target)-GetPosition(t));
  float f=aim+facing-90.0; while(f>=360.0) f-=360.0; while(f<0.0) f+=360.0;
  WriteTimestampedLogEntry("ITEMKIT_AIM actor="+GetTag(t)+" aim="+FloatToString(aim,0,1)+" facing="+FloatToString(GetFacing(t),0,1)+" camera="+FloatToString(f,0,1));
  return f;
}
// An actor whose shots are taken stops and idles through the cycle's empty steps: left attacking, its muzzle flash
// was the brightest thing in the other actor's firing shot.
void ItkPark(object t) { AssignCommand(t,ClearAllActions(TRUE)); SetLocalInt(t,"STEP",30); SetLocalInt(t,"ITK_SEEN",30); }
void ItkAmmoIn(object t,int slot,string r) {
  if(GetIsObjectValid(GetItemInSlot(slot,t))) return;
  object a=GetLocalObject(t,"ITK_"+r); if(!GetIsObjectValid(a)) { a=CreateItemOnObject(r,t,99); SetLocalObject(t,"ITK_"+r,a); }
  AssignCommand(t,ActionEquipItem(a,slot));
}
// A firearm on the sling row shoots bullets and one on the crossbow row bolts; without them an attack is a punch.
void ItkAmmo(object t) { ItkAmmoIn(t,INVENTORY_SLOT_BULLETS,"nw_wambu001"); ItkAmmoIn(t,INVENTORY_SLOT_BOLTS,"nw_wambo001"); }
// The item's firing clip in place of the stock shot of either row; the weapon model plays its own clip of that name.
void ItkClip(object a,string fire) {
  ReplaceObjectAnimation(a,"throwr",""); ReplaceObjectAnimation(a,"xbowshot",""); if(fire=="") return;
  int female=GetGender(a)==GENDER_FEMALE;
  string clip=fire+"_h"+(female ? "f" : "m")+(female && GetPhenoType(a)==2 ? "l" : "");
  ReplaceObjectAnimation(a,"throwr",clip); ReplaceObjectAnimation(a,"xbowshot",clip);
}
void ItkStart(int index) {
  object m=GetModule(); string item=Get2DAString("@TABLE@","Item",index);
  if(item=="") { WriteTimestampedLogEntry("@SESSION_DONE@"); return; }
  object pc=GetFirstPC(); object male=GetObjectByTag("@MALE@"); object female=GetObjectByTag("@FEMALE@");
  string old=GetLocalString(m,"ITK_ITEM");
  if(old!=item) { ItkDrop(pc,old); ItkDrop(male,old); ItkDrop(female,old); }
  SetLocalInt(m,"ITK_INDEX",index); SetLocalString(m,"ITK_ITEM",item);
  SetLocalInt(m,"ITK_CARRY",StringToInt(Get2DAString("@TABLE@","Carry",index)));
  int i; for(i=0;i<@TOTAL@;i++) DeleteLocalInt(m,"ITK_D"+IntToString(i));
  SetLocalInt(m,"ITK_FIRED",0); SetLocalInt(m,"ITK_BUSY",0);
  SetLocalInt(male,"STEP",0); SetLocalInt(female,"STEP",@OFFSET@);
  SetLocalInt(male,"ITK_SEEN",0); SetLocalInt(female,"ITK_SEEN",@OFFSET@);
  ItkBare(male); ItkBare(female);
  string fire=Get2DAString("@TABLE@","Fire",index); ItkClip(male,fire); ItkClip(female,fire);
  DelayCommand(0.5,ItkGive(pc)); DelayCommand(0.5,ItkGive(male)); DelayCommand(0.5,ItkGive(female));
  WriteTimestampedLogEntry("@ITEM_LINE@index="+IntToString(index)+" item="+item);
  DelayCommand(4.0,ItkWatch(pc));
}
void ItkDone() { WriteTimestampedLogEntry("@ITEM_DONE@"); ItkStart(GetLocalInt(GetModule(),"ITK_INDEX")+1); }
'''

ENTRY = '''void ItkGive(object actor) {
  string r=GetLocalString(GetModule(),"ITK_ITEM"); object item=GetItemPossessedBy(actor,r);
  if(!GetIsObjectValid(item)) item=CreateItemOnObject(r,actor);
  if(!GetIsObjectValid(item)) { WriteTimestampedLogEntry("ITEMKIT_ITEM_FAILED actor="+GetTag(actor)+" item="+r); return; }
  AssignCommand(actor,ClearAllActions(TRUE)); AssignCommand(actor,ActionEquipItem(item,INVENTORY_SLOT_@SLOT@));
}
void StartReview(object pc,int retries) {
  if(!GetIsObjectValid(pc) || !GetIsPC(pc)) return;
  object male=GetObjectByTag("@MALE@"); object female=GetObjectByTag("@FEMALE@");
  object area=GetArea(pc);
  if(!GetIsObjectValid(area) || !GetIsObjectValid(male) || !GetIsObjectValid(female) || GetArea(male)!=area || GetArea(female)!=area) {
    if(retries>0) DelayCommand(0.5,StartReview(pc,retries-1));
    else WriteTimestampedLogEntry("ITEMKIT_READY_FAILED area="+GetTag(area)+" male="+IntToString(GetIsObjectValid(male))+" female="+IntToString(GetIsObjectValid(female)));
    return;
  }
  // Without the capture toggle the session is a place to look by hand: the first item of the table, no camera script.
  SetLocalString(GetModule(),"ITK_ITEM",Get2DAString("@TABLE@","Item",0));
  ItkGive(pc); ItkGive(male); ItkGive(female);
  WriteTimestampedLogEntry("ITEMKIT_READY area="+GetTag(area)+" male="+GetTag(male)+" female="+GetTag(female));
  ItkBegin(pc,male,female);
}
void main() {
  object pc=GetEnteringObject(); if(!GetIsPC(pc)) return;
  @PRIOR@
  DelayCommand(0.5,StartReview(pc,20));
}
'''


def fill(text, **values):
    for key, value in values.items(): text = text.replace(f'@{key}@', str(value))
    require('@' not in re.sub(r'"[^"\n]*"', '', text), 'An unfilled marker is left in the session script')
    return text


def session_script(slot='right', previous=''):
    """The fixture's shot script with the reviewed item, its carry and the next item read at run time."""
    names = dict(TABLE=ITEMS_TABLE, MALE=SHOT_ACTORS[0][0], FEMALE=SHOT_ACTORS[1][0], SLOT=slot.upper() + 'HAND')
    base = shot_script(SESSION_SHOTS, slot, SESSION_CHECKS); plans = []
    for number, carry in enumerate(CARRIES):
        lines = PLAN_LINE.findall(shot_script(SESSION_CARRY[carry], slot, SESSION_CHECKS))
        require(len(lines) == len(SESSION_SHOTS), 'Every carry frames the same shots')
        plans.append(f'  if(GetLocalInt(GetModule(),"ITK_CARRY")=={number}) {{\n' + ''.join(lines).rstrip('\n') + '\n  }\n')
    found = PLAN_LINE.findall(base); start = base.index(found[0]); end = base.index(found[-1]) + len(found[-1])
    # Ammunition goes in while an actor stands idle after its still shots, and again before its attack steps.
    text = base[:start] + f'  if(n==4 || n==10) ItkAmmo(t);\n  if(n=={PARK}) ItkPark(t);\n' + ''.join(plans) + base[end:]
    camera = 'AssignCommand(pc,SetCameraFacing(facing,'; require(text.count(camera) == 1, 'The fixture shot script changed shape')
    text = text.replace(camera, 'AssignCommand(pc,SetCameraFacing(ItkFacing(t,check,facing),')
    done = 'void ItkDone() { WriteTimestampedLogEntry("ITEMKIT_SHOTS done"); }\n'; watch = '  DelayCommand(4.0,ItkWatch(pc));\n}\n'
    require(text.count(done) == 1 and text.count(watch) == 1 and '"ITEM_RESREF"' in text, 'The fixture shot script changed shape')
    # ItkBegin hands over to the first item before the next-item routine is put in: that routine ends on the same line.
    text = text.replace(watch, '  ItkStart(0);\n}\n')
    text = text.replace(done, fill(NEXT, **names, TOTAL=len(SESSION_SHOTS) * len(SHOT_ACTORS), OFFSET=SESSION_OFFSET, SESSION_DONE=SESSION_DONE,
                                   ITEM_LINE=ITEM_LINE, ITEM_DONE=ITEM_DONE, FIRE=FIRE_CHECK))
    entry = fill(ENTRY, **names, PRIOR=f'ExecuteScript("{previous}",GetModule());' if previous else '')
    return (text + entry).replace('"ITEM_RESREF"', CURRENT)


def session_heartbeat(script):
    """The motion heartbeat re-equipping the session's current item instead of one named item."""
    require(len(HEARTBEAT_ITEM.findall(script)) == 1, 'Fixture heartbeat must hold exactly one reviewed item')
    return HEARTBEAT_ITEM.sub('GetItemPossessedBy(OBJECT_SELF,' + CURRENT + ')', script)


def items_table(items):
    rows = ''.join(f'{index}  {row["item"]}  {CARRIES.index(row["carry"])}  {row.get("fire") or "****"}\n' for index, row in enumerate(items))
    return ('2DA V2.0\n\n   Item  Carry  Fire\n' + rows).encode('ascii')


def fixture_item(fixture_dir):
    """What a built fixture reviews, read from its own module: blueprint, hand, carry and the entry script before it."""
    fixture_dir = Path(fixture_dir).resolve(); record = read(fixture_dir/'fixture.json')
    verify([record['module'], record['hak'], *record['fixtureHaks']])
    resources = read_erf(record['module']['path']); entry = resources[('sr_it_enter', TYPES['nss'])].decode('ascii').replace(chr(13) + chr(10), chr(10))
    item = re.search(r'CreateItemOnObject\("([a-z0-9_]{1,16})",actor\)', entry)
    require(item, f'{fixture_dir}: the entry script names no reviewed item')
    slot = 'left' if 'ActionEquipItem(item,INVENTORY_SLOT_LEFTHAND)' in entry else 'right'
    carry = [name for name in CARRIES if all(line in entry for line in PLAN_LINE.findall(shot_script(SHOT_CARRY[name], slot)))]
    require(len(carry) == 1, f'{fixture_dir}: the scripted shots match no known carry')
    previous = re.search(r'ExecuteScript\("([a-z0-9_]+)",GetModule\(\)\);', entry)
    haks = {Path(row['path']).stem.lower(): row for row in record['fixtureHaks']}
    own = Path(record['hak']['path']).stem.lower()
    return {'fixture': pin(fixture_dir/'fixture.json'), 'item': item[1], 'slot': slot, 'carry': carry[0], 'previous': previous[1] if previous else '',
            'module': record['module'], 'hak': own, 'haks': haks, 'resources': resources}


def merged_baseitems(tables):
    """One base-item table from the packages' private ones, [(carrier row, bytes)]: each row as the packages that use
    it have it, with the widest appearance range; a row no package uses must be the same in all of them."""
    split = [body.decode('latin-1').splitlines() for _, body in tables]
    require(all('"' not in line for lines in split for line in lines), 'A quoted base-item value is not merged')
    places = [{int(line.split()[0]): at for at, line in enumerate(lines) if line.split() and line.split()[0].isdigit()} for lines in split]
    require(all(set(place) == set(places[0]) and lines[2].split() == split[0][2].split() for place, lines in zip(places, split)),
            'The private base-item tables have different rows or columns')
    column = split[0][2].split().index('MaxRange') + 1; out = list(split[0])
    for row, at in places[0].items():
        versions = [(owner == row, lines[place[row]].split()) for (owner, _), lines, place in zip(tables, split, places)]
        chosen = [cells for owns, cells in versions if owns] or [cells for _, cells in versions]
        rest = lambda cells: cells[:column] + cells[column + 1:]
        require(all(rest(cells) == rest(chosen[0]) for cells in chosen), f'The packages disagree on base-item row {row} beyond its appearance range')
        out[at] = '  '.join(max(chosen, key=lambda cells: int(cells[column]) if cells[column].isdigit() else -1))
    return ('\r\n'.join(out) + '\r\n').encode('latin-1')


def build(session, fixtures, nwn_root, repo=REPO, *, resources=None, fire=None):
    """`resources`: a folder of files that win over every HAK (models with firing effects a bound pack predates).
    `fire`: {blueprint: firing clip code, or '' for none} where the carrier's usual clip is not the item's."""
    session = Path(session).resolve(); require(fixtures, 'A session needs at least one built fixture')
    items = [fixture_item(folder) for folder in fixtures]; fire = dict(fire or {})
    unknown = sorted(set(fire) - {row['item'] for row in items}); require(not unknown, f'No fixture reviews {unknown}')
    require(all(code == '' or FIRE_CODE.fullmatch(code) for code in fire.values()), 'A firing clip is named like fire_pst')
    extra = sorted(path for path in Path(resources).iterdir() if path.is_file()) if resources else []
    require(not resources or extra, f'No files in {resources}')
    require(len({path.name.lower() for path in extra}) == len(extra) and 'baseitems.2da' not in {path.name.lower() for path in extra},
            'Session resources are named once each, and the base-item table is merged from the fixtures')
    require(len({row['item'] for row in items}) == len(items), 'Two fixtures review the same blueprint')
    require(len({row['slot'] for row in items}) == 1, 'A session holds items of one hand: build shields in their own session')
    require(len({row['previous'] for row in items}) == 1, 'The fixtures come from different templates')
    session.mkdir(parents=True); staged = session/'module-resources'; staged.mkdir()
    user = session/'userdir'; (user/'hak').mkdir(parents=True); (user/'modules').mkdir(); (user/'override').mkdir()
    tools = Tools(repo, nwn_root); first = items[0]
    tools.run('erf', '-x', '-f', first['module']['path'], cwd=staged)
    for row in items[1:]:
        for (resref, kind), body in row['resources'].items():
            if kind != TYPES['uti']: continue
            target = staged/f'{resref}.uti'
            require(not target.exists() or target.read_bytes() == body, f'Two fixtures carry different blueprints named {resref}')
            target.write_bytes(body)
    # HAKs by name: the shared packs once, then every item's own. The same name must be the same bytes.
    order, bound = [], {}
    for row in items:
        for name, hak in sorted(row['haks'].items(), key=lambda entry: entry[0] == row['hak']):
            require(bound.setdefault(name, hak)['sha256'] == hak['sha256'], f'The fixtures hold different HAKs named {name}: rebuild the older fixture')
            if name not in order: order.append(name)
    own = [row['hak'] for row in items]; order = [name for name in order if name not in own] + own
    for row in items:        # each item's own HAK is read once: its blueprint's base item and its private base-item table
        archive = read_erf(bound[row['hak']]['path']); row['carrier'] = carrier(row, archive)
        row['baseitems'] = archive.get(('baseitems', TYPES['2da'])); row['fire'] = fire.get(row['item'], FIRE_CLIPS.get(row['carrier'], ''))
    tables = [(row['carrier'], row['baseitems']) for row in items if row['baseitems'] is not None]
    with tempfile.TemporaryDirectory() as work:
        merge = len({body for _, body in tables}) > 1
        if merge or extra:
            require(SESSION_HAK not in order, 'A fixture HAK already has the session HAK name')
            folder = Path(work)/'hak'; folder.mkdir()
            if merge: (folder/'baseitems.2da').write_bytes(merged_baseitems(tables))
            for path in extra: link_or_copy(path, folder/path.name.lower())
            tools.run('erf', '-c', '-e', 'HAK', '-f', user/'hak'/f'{SESSION_HAK}.hak', folder)
            order.insert(0, SESSION_HAK)        # the first HAK of the list wins a shared resource
        ifo = tools.to_json(staged/'module.ifo', work)
        ifo['Mod_HakList'] = field('list', [{'__struct_id': 8, 'Mod_Hak': field('cexostring', name)} for name in order])
        ifo['Mod_Name'] = field('cexolocstring', {'0': 'Itemkit review session'})
        tools.to_gff(ifo, staged/'module.ifo', work)
    scripts = ['sr_it_enter.nss']
    (staged/'sr_it_enter.nss').write_bytes(session_script(first['slot'], first['previous']).encode('ascii'))
    heartbeat = staged/'sr_it_hb.nss'
    if heartbeat.exists():
        heartbeat.write_bytes(session_heartbeat(heartbeat.read_bytes().decode('ascii').replace(chr(13) + chr(10), chr(10))).encode('ascii')); scripts.append('sr_it_hb.nss')
    tools.compile(staged, scripts)
    module = user/'modules'/f'{MODULE}.mod'; tools.run('erf', '-c', '-e', 'MOD', '-f', module, staged)
    for name in order:
        if name != SESSION_HAK: link_or_copy(bound[name]['path'], user/'hak'/f'{name}.hak')
    record = {'schemaVersion': 2, 'kind': 'itemkit-review-session', 'module': pin(module), 'userDirectory': str(user),
              'haks': [pin(user/'hak'/f'{name}.hak') for name in order], 'hakOrder': order, 'slot': first['slot'],
              'items': [{key: row[key] for key in ('item', 'carry', 'fire', 'fixture')} for row in items],
              'resources': [pin(path) for path in extra],
              'clientValidated': False, 'productionAccepted': False}
    write(session/'session.json', record, fresh=True)
    return record


def carrier(row, archive):
    """The base item a fixture's blueprint is carried on, from the blueprint in its own HAK (`archive`) or module."""
    from tools import combat_release_manifest as crm
    body = archive.get((row['item'], TYPES['uti'])) or row['resources'].get((row['item'], TYPES['uti']))
    require(body is not None, f"No blueprint {row['item']} in its fixture")
    return crm.parse_gff(body).get('BaseItem')


def finished(folder):
    record = Path(folder)/'capture.json'
    return record.is_file() and read(record).get('finished') is True


def bright(image):
    """How much of a picture is bright, in pixels of a 640 x 360 copy."""
    return image.convert('L').resize((640, 360)).point(lambda value: 255 if value >= BRIGHT else 0).histogram()[255]


def fire_burst(client, process, user, folder, row, previous_read, hold=FIRE_HOLD):
    """Watch one firing shot for its whole hold and keep the pictures with the most flash: the brightest is frame 1,
    the one the contact sheet shows. A flash lasts a tenth of a second, so the pictures are scored as they are taken
    and only the kept ones are written. `flash` is the brightest picture's bright area over the burst's dimmest: no
    one picture is the baseline, so a flash in the first picture counts. A burst that stopped taking pictures for
    `STALL` seconds may have missed the flash and is rejected, never filed as a gun without one."""
    body = cc.BODIES.get(row['target']); require(body and row['valid'], f"Shot {row['shot']} has no actor to look at")
    ends = previous_read + hold - .4; kept = []; taken = 0; least = None; gap = 0.0; last = time.monotonic()
    while last < ends:
        image = client.grab(process.pid); now = time.monotonic(); gap = max(gap, now - last); last = now
        score = bright(image); least = score if least is None else min(least, score); taken += 1
        kept = sorted(kept + [(score, -taken, image)], key=lambda entry: entry[:2], reverse=True)[:KEEP]
    late = time.monotonic() > previous_read + hold
    order = [kept[at] for at in (1, 0, 2) if at < len(kept)] if len(kept) > 1 else kept      # the best is frame 1
    names = []
    for frame, (_, _, image) in enumerate(order):
        name = f"{body}-{row['check']}-{row['shot']:02d}-{frame}.png"; client.save(image, Path(folder)/name); names.append(name)
    newest = cc.shot_rows(client.log_lines(user, cc.PREFIX))[-1]['shot']
    rejected = ('next shot began' if newest != row['shot'] else 'burst overran the shot hold' if late else
                'burst stalled' if gap > STALL or not kept else None)
    return {**row, 'body': body, 'captures': names, 'pictures': taken, 'longestGap': round(gap, 2), 'flash': kept[0][0] - least if kept else 0,
            **({'rejected': rejected} if rejected else {})}


def capture(session, captures, nwn_root, *, wait=0, only=None, again=False, timeout=None, frames=cc.FRAMES, gap=cc.GAP, settle=cc.SETTLE):
    from tools.armorkit import client
    session = Path(session).resolve(); captures = Path(captures).resolve(); record = read(session/'session.json')
    require(record.get('schemaVersion') == 2, 'This session was built for the longer shot list: build it again')
    verify([record['module'], *record['haks']]); user = Path(record['userDirectory'])
    known = {row['item']: row for row in record['items']}
    unknown = sorted(set(only or ()) - set(known)); require(not unknown, f'Not in this session: {unknown}')
    require(not again or only, 'Name the items to capture again (--items)')
    todo = [row for row in record['items'] if (not only or row['item'] in only) and (again or not finished(captures/row['item']))]
    skipped = [row['item'] for row in record['items'] if (not only or row['item'] in only) and row not in todo]
    if not todo: return {'captured': [], 'alreadyCaptured': skipped, 'unfinished': []}
    per_item = 60 + 3 * SESSION_STEPS * 6 if timeout is None else timeout; total = len(SESSION_SHOTS) * len(SHOT_ACTORS)
    toggle = user/'override'/f'{SHOT_TOGGLE}.2da'; table = user/'override'/f'{ITEMS_TABLE}.2da'
    require(not toggle.exists(), 'A scripted-shot toggle is already in this session; another capture may be running')
    if wait: client.wait_free(wait)
    require(not client.running(), 'A game client is already running; it is not ours to reuse or close (--wait SECONDS waits for it)')
    captures.mkdir(parents=True, exist_ok=True)
    (user/'settings.tml').write_text(client.SETTINGS.format(width=1600, height=900), encoding='utf-8')
    table.write_bytes(items_table(todo)); toggle.write_bytes(cc.TOGGLE_TABLE.encode('ascii'))
    done, current, shots, seen, over = [], None, [], 0, False

    def close(item, complete, lines):
        """File one item's shots as client_capture files a fixture's: a record, an evidence draft and contact sheets."""
        folder = captures/item
        result = {'session': pin(session/'session.json'), 'item': item, 'fixture': known[item]['fixture'], 'module': record['module'],
                  'haks': record['haks'], 'finished': complete, 'shotsExpected': total, 'shots': shots,
                  'failures': [line for line in lines if 'FAILED' in line], 'clientValidated': False, 'productionAccepted': False}
        write(folder/'capture.json', result)
        write(folder/'evidence-draft.json', {'session': result['session'], 'reviewMaterialOnly': True,
                                             **cc.evidence_draft(shots, 'nwclientLog1.txt', SESSION_CHECKS)})
        cc.contact_sheets(folder)
        flash = {shot['body']: shot['flash'] for shot in shots if 'flash' in shot and not shot.get('rejected')} if known[item].get('fire') else None
        done.append({'item': item, 'finished': complete, 'shots': len(shots), 'rejected': [shot['shot'] for shot in shots if shot.get('rejected')],
                     **({'flash': flash} if flash is not None else {})})

    try:
        process = client.start(nwn_root, user, MODULE)
        try:
            deadline = time.monotonic() + 120 + per_item; previous_read = time.monotonic()
            while not over and time.monotonic() < deadline:
                time.sleep(.05)
                require(process.poll() is None, 'The client exited before the session finished')
                read_at = time.monotonic(); lines = client.log_lines(user, cc.PREFIX)
                fired = []          # this read's shots of the current item, in order; only the last can still be on screen
                for line in lines[seen:]:
                    if line.startswith(ITEM_LINE) or line.startswith(ITEM_DONE) or line.startswith(SESSION_DONE):
                        if current:
                            # The item moved on within this read: its shots' views are gone.
                            shots += [{**row, 'body': cc.BODIES.get(row['target']), 'captures': [], 'rejected': 'next shot began'} for row in fired]
                        fired = []
                    if line.startswith(ITEM_LINE):
                        current = client.parse_line(line)['item']; shots = []; folder = captures/current
                        if folder.exists(): shutil.rmtree(folder)      # an unfinished earlier attempt of this item
                        folder.mkdir(); deadline = time.monotonic() + per_item; began = read_at
                    # `seen`: seconds from the item's start to the read that found the shot, to set against the log's own times.
                    elif line.startswith('ITEMKIT_SHOT ') and current: fired += [{**row, 'seen': round(read_at - began, 1)} for row in cc.shot_rows([line])]
                    elif line.startswith(ITEM_DONE) and current: close(current, True, lines); current = None
                    elif line.startswith(SESSION_DONE): over = True
                if current and fired and fired[-1]['check'] == FIRE_CHECK:
                    shots += [{**row, 'body': cc.BODIES.get(row['target']), 'captures': [], 'rejected': 'next shot began'} for row in fired[:-1]]
                    shots.append(fire_burst(client, process, user, captures/current, fired[-1], previous_read))
                elif current and fired:
                    shots += cc.file_shots(client, process, user, captures/current, fired, previous_read, frames, gap, settle, HOLD)
                seen = len(lines); previous_read = read_at
            if current: close(current, False, client.log_lines(user, cc.PREFIX))
        finally:
            client.stop(process)
    finally:
        toggle.unlink(missing_ok=True)
    log = user/'logs'/'nwclientLog1.txt'
    for row in done:
        if log.is_file(): shutil.copyfile(log, captures/row['item']/'nwclientLog1.txt')
    left = [row['item'] for row in todo if row['item'] not in {entry['item'] for entry in done if entry['finished']}]
    return {'captured': done, 'alreadyCaptured': skipped, 'unfinished': left}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0]); commands = parser.add_subparsers(dest='command', required=True)
    b = commands.add_parser('build'); b.add_argument('session', type=Path); b.add_argument('fixtures', type=Path, nargs='+')
    b.add_argument('--resources', type=Path, help='folder of files that win over every HAK, such as models with firing effects')
    b.add_argument('--fire', action='append', default=[], metavar='BLUEPRINT=CLIP',
                   help='firing clip of one item (fire_smg, fire_sg; empty for none) where its base item\'s usual one is wrong')
    c = commands.add_parser('capture'); c.add_argument('session', type=Path); c.add_argument('captures', type=Path)
    c.add_argument('--wait', type=float, default=0, help="seconds to wait for another session's client to close first")
    c.add_argument('--items', type=lambda text: [name for name in text.split(',') if name], help='blueprints to capture, of the session')
    c.add_argument('--again', action='store_true', help='capture the named items again although they are finished (rejected shots)')
    c.add_argument('--timeout', type=float, help='seconds allowed per item')
    for command in (b, c): command.add_argument('--nwn-root', type=Path, required=True, help='game install folder (holds bin/win32/nwmain.exe)')
    a = parser.parse_args(argv)
    if a.command == 'build':
        require(all('=' in entry for entry in a.fire), '--fire takes BLUEPRINT=CLIP')
        record = build(a.session, a.fixtures, a.nwn_root, resources=a.resources, fire=dict(entry.split('=', 1) for entry in a.fire))
        result = {'session': str(a.session), 'module': record['module']['path'], 'haks': record['hakOrder'],
                  'items': {row['item']: row['fire'] for row in record['items']}}
    else:
        result = capture(a.session, a.captures, a.nwn_root, wait=a.wait, only=a.items, again=a.again, timeout=a.timeout)
    print(json.dumps(result, indent=2))
    return 1 if a.command == 'capture' and result['unfinished'] else 0


if __name__ == '__main__':
    sys.exit(main())
