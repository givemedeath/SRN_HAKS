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
# Names the body plays outside the shot. A gun with no clip of the name keeps looping its last one, detonate and all.
QUIET_CLIPS = ('pause1', 'pause2', 'walk', 'run', 'xbowrdy', 'bowrdy', 'bow', '1hreadyr', '1hreadyl', 'nwreadyr', 'nwreadyl')
BURST_LIFE = 1.5
BURST_SIZE = .5
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
'''
CHAT = '''if(text=="fstock")StockAttack();
 else if(text=="ak")Arm();
 else if(text=="lpistol")Clips("custom12lp","fire_pst",ANIMATION_LOOPING_CUSTOM12,"pistol loop");
 else if(text=="lsmg")Clips("custom14lp","fire_smg",ANIMATION_LOOPING_CUSTOM14,"smg loop");
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


def tagged_gun(text, stem, names, quiet=False):
    """Add the marker and a burst to one decompiled gun, with clips for the `stock` or `replaced` names."""
    root = re.search(r'(?m)^newmodel (\S+)', text)[1]
    tip = muzzle(text)
    emitter, color = ('srp_red', '1 0 0') if names == 'stock' else ('srp_green', '0 1 0')
    nodes = EMITTER.format(name=emitter, root=root, x=tip[0], y=tip[1], z=tip[2], update='Explosion', color=color,
                           size=BURST_SIZE, rate=1, life=BURST_LIFE)
    nodes += EMITTER.format(name='srp_marker', root=root, x=0., y=0., z=tip[2] / 2, update='Fountain', color='1 1 1',
                            size=.08, rate=4, life=.3)
    close = f'endmodelgeom {root}'
    if text.count(close) != 1 or re.search(r'(?m)^newanim ', text):
        raise ValueError('Unexpected gun shape: ' + root)

    clip_names = STOCK_CLIPS if names == 'stock' else [f'{stem}_{slot}' for slot in slots()]
    event = f'  event {BURST_TIME} detonate\n'
    clips = ''.join(CLIP.format(clip=name, root=root, event=event, nodes=EMITTER_CLIP_NODE.format(name=emitter, root=root))
                    for name in clip_names)
    if quiet:
        clips += ''.join(CLIP.format(clip=name, root=root, event='', nodes='') for name in QUIET_CLIPS)
    head = f'setsupermodel {root} NULL\n'
    if text.count(head) != 1:
        raise ValueError('Unexpected gun header: ' + root)
    text = text.replace(head, head + 'classification Character\n') if 'classification' not in text else text
    return text.replace(close, nodes + close + '\n\n' + clips.rstrip('\n'))


def extend(names, quiet, hak, stock_dir, scripts):
    for part, stem in GUNS.values():
        text = (stock_dir / part).read_text(encoding='cp1252')
        (hak / part).write_text(tagged_gun(text, stem, names, quiet), encoding='cp1252', newline='\n')
    scripts['srp_inc'] += INC
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
    options = vars(parser.parse_args())
    result = pilot.build(extend=partial(extend, options.pop('names'), options.pop('quiet')), **options)
    print('built', result['customBytes'])
