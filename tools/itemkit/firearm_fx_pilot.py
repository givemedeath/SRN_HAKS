"""Pilot: muzzle flash and shell casings from emitters on the firearm models.

Gate 1 asks which clip name an attached gun plays while the body clip is swapped with `ReplaceObjectAnimation`.
`detonate` fires every Explosion emitter on the model, whichever clip sends it, so one build can't test both names.
The `stock` build puts a red burst on the stock clip names and the `replaced` build a green burst on the replaced names.
A small white marker is always on, which proves the edited model loaded.

Output goes to ignored `output/`, and nothing ships. The edited guns are ASCII copies in the test hak, which loads
before `srn_weapon`.
"""
import argparse
from functools import partial
from pathlib import Path
import re
import sys

import numpy as np

REPO = Path(__file__).resolve().parents[2]
# Appended, so these modules can share a test process with tools that have a same-named module.
if str(REPO) not in sys.path:
    sys.path.append(str(REPO))
from tools.itemkit import combat_clip_pilot as pilot

GUNS = {'colt': ('wbwsl_b_051.mdl', 'fire_pst'), 'ingram': ('wbwsl_m_023.mdl', 'fire_smg'), 'ak98': ('wbwxh_t_015.mdl', 'fire_rfl')}
STOCK_CLIPS = ('throwr', 'xbowshot')
BURST_TIME = .1
# Gate 2: recoil onsets from hand speed in the clip keys, shared by every slot. Moving `hit` to these doesn't move
# the shot: the engine launches on the stock clip's own `hit` (0.5 s in `throwr` and `xbowshot`). Diagnostic only.
HIT_TIMES = {'fire_pst': .5, 'fire_rfl': .13, 'fire_sg': .13, 'fire_smg': .1}
FIRE_CLIP = re.compile(r'(?ms)^(newanim (fire_(?:pst|rfl|sg|smg))_\S+ a_ba_custom\n)(.*?)(^doneanim )')
# Names the body plays outside the shot. A gun with no clip of the name keeps looping its last one, detonate and all.
QUIET_CLIPS = ('pause1', 'pause2', 'walk', 'run', 'xbowrdy', 'bowrdy', 'bow', '1hreadyr', '1hreadyl', 'nwreadyr', 'nwreadyl')
BURST_LIFE = 1.5
BURST_SIZE = .5
# Old mod effects (`--old-fx`), relative to the `!Combat Override System` folder. The flash is 9 sprites on stock
# `fxpa_flare`; the casing is one bouncing sprite whose sheet the old mod saved over the stock `fxpa_smoke02`.
OLD_FLASH = ('WIP/combat_ovr_v1.hak/models/wbwxh_m_154.mdl', 'muzzle_flash')
OLD_CASING = ('OLD/!DONE/gun models/wbwar_t_101.mdl', 'Casings')
OLD_CASING_SHEET = 'OLD/!DONE/gun models/fxpa_smoke02.tga'
CASING_SHEET = 'srnfx_casing'
# The old flash grows from nothing and peaks 0.2 s after the shot. Start it full and fade it out instead.
FLASH_FIELDS = {'sizeStart': .12, 'sizeEnd': .02, 'sizeStart_y': .12, 'sizeEnd_y': .02, 'alphaEnd': 0, 'lifeExp': .1}
# The old casing reads about 12 cm long. This is about 5 cm.
CASING_SIZE = .06
# The stock attack's `hit`, where the engine launches the shot.
SHOT_TIME = .5
# Ejection ports on each gun's right side (+x), placed by hand from its cross-sections.
PORTS = {'colt': (.025, .10, -.05), 'ingram': (.015, .10, -.06), 'ak98': (.031, .165, -.06)}
EMITTER = '''node emitter {name}
  parent {root}
  position {x:.5f} {y:.5f} {z:.5f}
  orientation 0 0 0 0
  wirecolor 1 1 1
  update {update}
  render Normal
  Blend Lighten
  spawnType 0
  xSize 0
  ySize 0
  inherit 1
  inherit_local 0
  inheritvel 0
  inherit_part 0
  renderorder 0
  threshold 0
  combinetime 0
  deadspace 0
  opacity 1
  colorStart {color}
  colorEnd {color}
  alphaStart 1
  alphaEnd 1
  sizeStart {size}
  sizeEnd {size}
  sizeStart_y 0
  sizeEnd_y 0
  birthrate {rate}
  lifeExp {life}
  mass 0
  spread 0
  particleRot 0
  velocity 0
  randvel 0
  bounce_co 0
  blurlength 10
  loop 0
  bounce 0
  m_isTinted 1
  Splat 0
  affectedByWind false
  texture fxpa_flare
  twosidedtex 0
  xgrid 1
  ygrid 1
  fps 1
  framestart 1
  frameend 1
  random 0
  lightningDelay 0
  lightningRadius 0
  lightningSubDiv 0
  lightningScale 0
  blastRadius 0
  blastLength 0
  p2p 0
  p2p_type Bezier
  p2p_bezier2 0
  p2p_bezier3 0
  grav 0
  Drag 0
endnode
'''
CLIP = '''newanim {clip} {root}
  length 1
  transtime 0.25
  animroot {root}
{event}  node dummy {root}
    parent NULL
  endnode
{nodes}doneanim {clip} {root}

'''
EMITTER_CLIP_NODE = '''  node emitter {name}
    parent {root}
  endnode
'''
INC = r'''
void StockAttack(){
 object target=GetObjectByTag("SRP_T");
 int n=0;object a=GetObjectByTag("SRP_A",n);
 while(GetIsObjectValid(a)){
  ReplaceObjectAnimation(a,"pause1","");ReplaceObjectAnimation(a,"pause2","");
  ReplaceObjectAnimation(a,"throwr","");ReplaceObjectAnimation(a,"xbowshot","");
  AssignCommand(a,ClearAllActions(TRUE));AssignCommand(a,ActionAttack(target));
  a=GetObjectByTag("SRP_A",++n);}
 Say("attack stock");SrpLog("phase attack stock");}
void TimedAttack(string shot,string code,string text){
 object target=GetObjectByTag("SRP_T");
 SetEventScript(target,EVENT_SCRIPT_CREATURE_ON_MELEE_ATTACKED,"srp_dmg");
 SetEventScript(target,EVENT_SCRIPT_CREATURE_ON_DAMAGED,"srp_dmg");
 SetLocalInt(GetModule(),"SRP_T0",GetMicrosecondCounter());
 Attack(shot,code,"timed "+text);}
void Speed(float speed){
 int n=0;object a=GetObjectByTag("SRP_A",n);
 while(GetIsObjectValid(a)){
  SetObjectVisualTransform(a,OBJECT_VISUAL_TRANSFORM_ANIMATION_SPEED,speed);
  a=GetObjectByTag("SRP_A",++n);}
 Say("speed "+FloatToString(speed,3,2));}
void Solo(){
 int n=1;object a=GetObjectByTag("SRP_A",n);
 while(GetIsObjectValid(a)){DestroyObject(a);a=GetObjectByTag("SRP_A",++n);}
 Say("solo "+GetName(GetObjectByTag("SRP_A",0)));}
void Behind(){
 object pc=GetFirstPC();object a=GetObjectByTag("SRP_A",0);float f=GetFacing(a);
 AssignCommand(pc,ClearAllActions(TRUE));
 AssignCommand(pc,JumpToLocation(Location(GetArea(a),GetPosition(a)-AngleToVector(f)*1.5,f)));
 DelayCommand(0.5,Camera(pc,f,3.0,75.0));Say("behind");}
'''
# Logs each attack landing on the target, in milliseconds since the timed attack began.
DAMAGE = '''#include "srp_inc"
void main(){
 int damaged=GetCurrentlyRunningEvent()==EVENT_SCRIPT_CREATURE_ON_DAMAGED;
 object a=damaged?GetLastDamager():GetLastAttacker();
 int ms=(GetMicrosecondCounter()-GetLocalInt(GetModule(),"SRP_T0"))/1000;
 SrpLog("land "+(damaged?"damaged":"attacked")+" | "+GetName(a)+" | ms="+IntToString(ms));}
'''
CHAT = '''if(text=="fstock")StockAttack();
 else if(text=="ak")Arm();
 else if(text=="lpistol")Clips("custom12lp","fire_pst",ANIMATION_LOOPING_CUSTOM12,"pistol loop");
 else if(text=="lsmg")Clips("custom14lp","fire_smg",ANIMATION_LOOPING_CUSTOM14,"smg loop");
 else if(text=="tpistol")TimedAttack("throwr","fire_pst","pistol");
 else if(text=="tsmg")TimedAttack("throwr","fire_smg","smg");
 else if(text=="trifle")TimedAttack("xbowshot","fire_rfl","rifle");
 else if(text=="tshot")TimedAttack("xbowshot","fire_sg","shotgun");
 else if(text=="slow")Speed(0.2);
 else if(text=="fast")Speed(1.0);
 else if(text=="solo")Solo();
 else if(text=="behind")Behind();
 else '''


def muzzle(text):
    """The barrel tip in the gun's own frame. The barrel points down -Z on every test gun."""
    match = re.search(r'(?m)^\s*verts\s+(\d+)\s*\n', text)
    rows = text[match.end():].splitlines()[:int(match[1])]
    verts = np.array([[float(v) for v in row.split()[:3]] for row in rows])
    tip = verts[:, 2].min()
    return np.array([0., verts[verts[:, 2] < tip + .02, 1].mean(), tip])


def slots():
    return [*pilot.SLOTS, *(slot + 'l' for slot in pilot.SLOTS if slot.endswith('f'))]


def retimed_hits(text, times=HIT_TIMES):
    """Move or add the `hit` event of every rifle, shotgun, pistol and SMG fire clip to its `times` entry."""
    def retime(match):
        body = re.sub(r'(?m)^\s*event \S+ hit\n', '', match[3])
        header = re.search(r'(?m)^\s*animroot \S+\n', body)
        body = body[:header.end()] + f'  event {times[match[2]]} hit\n' + body[header.end():]
        return match[1] + body + match[4]
    text, count = FIRE_CLIP.subn(retime, text)
    if count != 15 * len(HIT_TIMES):
        raise ValueError(f'Expected {15 * len(HIT_TIMES)} fire clips, found {count}')
    return text


def emitter_blocks(text, prefix):
    """Every geometry emitter whose name starts with `prefix`, as {name: block} with Windows line ends removed."""
    geometry = text.replace('\r\n', '\n').split('\nnewanim', 1)[0] + '\n'
    return {m[1]: m[0] for m in re.finditer(r'(?ms)^node emitter (' + re.escape(prefix) + r'\w*)\n.*?^endnode\n', geometry)}


def set_field(block, field, value):
    block, count = re.subn(r'(?m)^(\s*' + field + r')\s.*$', lambda m: f'{m[1]} {value}', block)
    if count != 1:
        raise ValueError(f'{field} appears {count} times')
    return block


def old_effects(root, text, flashes, casing, port):
    """The old flash moved onto this gun's muzzle and the old casing onto its port, renamed and re-parented."""
    tip = muzzle(text)
    first = np.array([float(v) for v in re.search(r'(?m)^\s*position (.*)$', flashes[min(flashes)])[1].split()])
    nodes = {}
    for index, (name, block) in enumerate(sorted(flashes.items()), 1):
        offset = np.array([float(v) for v in re.search(r'(?m)^\s*position (.*)$', block)[1].split()]) - first
        block = set_field(set_field(block, 'parent', root), 'position', ' '.join(f'{v:.5f}' for v in tip + offset))
        for field, value in FLASH_FIELDS.items():
            block = set_field(block, field, value)
        nodes[f'srn_flash{index:02}'] = block.replace(f'node emitter {name}\n', f'node emitter srn_flash{index:02}\n')
    (name, block), = casing.items()
    block = set_field(set_field(block, 'parent', root), 'position', ' '.join(f'{v:.5f}' for v in port))
    block = set_field(block, 'texture', CASING_SHEET)
    for field, value in (('fps', 24), ('framestart', 0), ('frameend', 15), ('sizeStart', CASING_SIZE),
                         ('sizeEnd', CASING_SIZE)):
        block = set_field(block, field, value)
    nodes['srn_casing'] = block.replace(f'node emitter {name}\n', 'node emitter srn_casing\n')
    return nodes


def tumbling_sheet(source, target):
    """The old casing sheet redrawn as a tumble: 16 frames turning the casing from side-on to end-on and back."""
    from PIL import Image
    sheet = Image.open(source).convert('RGBA')
    cell = sheet.width // 4
    casing = sheet.crop((0, 0, cell, cell))
    casing = casing.crop(casing.getbbox())
    size = 64
    scale = (size * .8) / casing.width
    out = Image.new('RGBA', (size * 4, size * 4), (0, 0, 0, 0))
    for frame in range(16):
        turn = np.cos(2 * np.pi * frame / 16)
        width = max(int(round(casing.width * scale * abs(turn))), int(round(casing.height * scale)))
        image = casing.resize((width, max(1, int(round(casing.height * scale)))), Image.LANCZOS)
        if turn < 0:
            image = image.transpose(Image.FLIP_LEFT_RIGHT)
        x, y = (frame % 4) * size + (size - image.width) // 2, (frame // 4) * size + (size - image.height) // 2
        out.alpha_composite(image, (x, y))
    out.save(target)


def tagged_gun(text, stem, names, quiet=False, burst_time=BURST_TIME, effects=None):
    """Add emitters to one decompiled gun, with clips for the `stock` or `replaced` names that fire them.

    Without `effects` it gets the test burst and the white marker. With `effects` ({node name: emitter block}) it gets
    those instead, fired at SHOT_TIME."""
    root = re.search(r'(?m)^newmodel (\S+)', text)[1]
    tip = muzzle(text)
    if effects:
        nodes, listed, burst_time = ''.join(effects.values()), list(effects), SHOT_TIME
    else:
        emitter, color = ('srp_red', '1 0 0') if names == 'stock' else ('srp_green', '0 1 0')
        nodes = EMITTER.format(name=emitter, root=root, x=tip[0], y=tip[1], z=tip[2], update='Explosion', color=color,
                               size=BURST_SIZE, rate=1, life=BURST_LIFE)
        nodes += EMITTER.format(name='srp_marker', root=root, x=0., y=0., z=tip[2] / 2, update='Fountain',
                                color='1 1 1', size=.08, rate=4, life=.3)
        listed = [emitter]
    close = f'endmodelgeom {root}'
    if text.count(close) != 1 or re.search(r'(?m)^newanim ', text):
        raise ValueError('Unexpected gun shape: ' + root)

    clip_names = STOCK_CLIPS if names == 'stock' else [f'{stem}_{slot}' for slot in slots()]
    event = f'  event {burst_time} detonate\n'
    listing = ''.join(EMITTER_CLIP_NODE.format(name=name, root=root) for name in listed)
    clips = ''.join(CLIP.format(clip=name, root=root, event=event, nodes=listing) for name in clip_names)
    if quiet:
        clips += ''.join(CLIP.format(clip=name, root=root, event='', nodes='') for name in QUIET_CLIPS)
    head = f'setsupermodel {root} NULL\n'
    if text.count(head) != 1:
        raise ValueError('Unexpected gun header: ' + root)
    text = text.replace(head, head + 'classification Character\n') if 'classification' not in text else text
    return text.replace(close, nodes + close + '\n\n' + clips.rstrip('\n'))


def extend(names, quiet, corrected, hit_at, old_fx, hak, stock_dir, scripts):
    """corrected: move fire clip `hit` events to HIT_TIMES and burst the gun at the same time.
    hit_at: move every fire clip `hit` to this time instead, keeping the burst at clip start as a marker.
    old_fx: the old mod's `!Combat Override System` folder; fit its flash and casing in place of the test burst."""
    times = {stem: hit_at for stem in HIT_TIMES} if hit_at is not None else HIT_TIMES if corrected else None
    if old_fx:
        old_fx = Path(old_fx)
        flashes = emitter_blocks((old_fx / OLD_FLASH[0]).read_text(encoding='cp1252'), OLD_FLASH[1])
        casing = emitter_blocks((old_fx / OLD_CASING[0]).read_text(encoding='cp1252'), OLD_CASING[1])
        if len(flashes) != 9 or len(casing) != 1:
            raise ValueError(f'Expected 9 old flashes and 1 casing, found {len(flashes)} and {len(casing)}')
        tumbling_sheet(old_fx / OLD_CASING_SHEET, hak / (CASING_SHEET + '.tga'))
    for label, (part, stem) in GUNS.items():
        text = (stock_dir / part).read_text(encoding='cp1252')
        burst = HIT_TIMES[stem] if corrected and hit_at is None else BURST_TIME
        root = re.search(r'(?m)^newmodel (\S+)', text)[1]
        effects = old_effects(root, text, flashes, casing, PORTS[label]) if old_fx else None
        (hak / part).write_text(tagged_gun(text, stem, names, quiet, burst, effects), encoding='cp1252', newline='\n')
    if times:
        custom = hak / 'a_ba_custom.mdl'
        custom.write_text(retimed_hits(custom.read_text(encoding='cp1252'), times), encoding='cp1252', newline='\n')
    scripts['srp_inc'] += INC
    scripts['srp_dmg'] = DAMAGE
    marker = 'if(text=="hold")'
    if scripts['srp_chat'].count(marker) != 1:
        raise ValueError('Unexpected chat script')
    scripts['srp_chat'] = scripts['srp_chat'].replace(marker, CHAT + marker)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ('output', 'source-dir', 'game-root', 'tool-dir', 'game-userdir'):
        parser.add_argument('--' + option, required=True)
    parser.add_argument('--client')
    parser.add_argument('--names', choices=('stock', 'replaced'), required=True)
    parser.add_argument('--quiet', action='store_true', help='Add empty clips for the names in QUIET_CLIPS')
    parser.add_argument('--corrected-hits', action='store_true', help='Move fire clip hit events to HIT_TIMES')
    parser.add_argument('--hit-at', type=float, help='Diagnostic: put every fire clip hit event at this time')
    parser.add_argument('--old-fx', help="The old mod's '!Combat Override System' folder, for its flash and casing")
    options = vars(parser.parse_args())
    hooks = partial(extend, options.pop('names'), options.pop('quiet'), options.pop('corrected_hits'), options.pop('hit_at'),
                    options.pop('old_fx'))
    result = pilot.build(extend=hooks, **options)
    print('built', result['customBytes'])
