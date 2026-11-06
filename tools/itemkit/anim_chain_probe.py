"""Client probe: which animation layer reaches bodies and every robe family.

Adds one visible clip at each candidate layer and builds an isolated module with a
grid of bodies and robes:

* `srpcust` (right arm raised) in a hak override of the stock `a_ba_custom`.
* `srplib` (left arm raised) in a thin layer directly under the body roots, which
  behaves like adding it to `srn_an_*`.

Nothing here ships or changes a pack. All output goes to a fresh ignored directory.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path
import shutil
import subprocess
import sys

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO), str(REPO / 'tools/heads'), str(REPO / 'tools/phenotypes')]
from tools.phenomorpher.phenomorpher.engine.anim_library import PARENT_FIELD, library_text, load_model, rename
from tools.phenomorpher.phenomorpher.engine.native_motion import sample

CUSTOM_CLIP, LIBRARY_CLIP = 'srpcust', 'srplib'
HAK, MODULE = 'srn_pb_anim', 'srp_anim'
LIBRARIES = {'srn_pb_hm': ('a_ba', ['pmh0', 'pmh2']), 'srn_pb_hf': ('srn_fa_h0', ['pfh0', 'pfh2']),
             'srn_pb_dm': ('srn_an_dm', ['pmd0', 'pmd2'])}
ARM_ANGLE = 2.6  # radians from hanging, so a raised arm clears the head and any robe


def arm_quaternion(right):
    """Raise an arm out and up. In a body's frame the right arm hangs on +X."""
    half = (-ARM_ANGLE if right else ARM_ANGLE) / 2
    return np.array([0., np.sin(half), 0., np.cos(half)])


def stock_clip_tree(text, owner):
    """Node kinds and parents of a stock clip, so the probe clip has a closed tree."""
    block = text[text.index('newanim custom6lp'):text.index('doneanim custom6lp')]
    tree = re.findall(r'(?m)^\s*node (\w+) (\S+)\s+parent (\S+)', block)
    names = {name for _, name, _ in tree}
    if owner not in names or 'rbicep_g' not in names:
        raise ValueError('Unexpected stock clip tree')
    return tree


def custom_clip_text(owner, tree):
    x, y, z, w = arm_quaternion(True)
    sine = np.linalg.norm([x, y, z])
    axis = np.array([x, y, z]) / sine
    angle = 2 * np.arctan2(sine, w)
    key = ' '.join(f'{v:.6f}' for v in (*axis, angle))
    lines = [f'newanim {CUSTOM_CLIP} {owner}', '  length 1.0', '  transtime 0.2', '  animroot rootdummy']
    for kind, name, parent in tree:
        lines += [f'    node {kind} {name}', f'        parent {parent}']
        if name == 'rbicep_g':
            lines += ['        orientationkey', f'            0.0 {key}', f'            1.0 {key}', '        endlist']
        lines.append('    endnode')
    return '\n'.join(lines +[f'doneanim {CUSTOM_CLIP} {owner}', ''])


def add_custom_clip(text, owner='a_ba_custom'):
    """Insert the probe clip before `donemodel`, leaving every stock line unchanged."""
    closing = f'donemodel {owner}'
    if text.count(closing) != 1 or f'newanim {CUSTOM_CLIP} ' in text:
        raise ValueError('Unexpected stock a_ba_custom shape')
    return text.replace(closing, custom_clip_text(owner, stock_clip_tree(text, owner)) + closing)


def library_clip(stock, root_name):
    """Key only the left arm, with a tree shaped like a stock clip."""
    nodes = rename(stock['clips']['pause1']['nodes'], 'a_ba', root_name)
    kept = {n: {**r, 'controls': {}} for n, r in nodes.items()}
    kept['lbicep_g']['controls'][20] = {'times': np.array([0., 1.]), 'values': np.array([arm_quaternion(False)] * 2)}
    return {'length': 1., 'transition': .2, 'animroot': 'rootdummy', 'nodes': kept, 'events': []}


def check_pose(root, clip, node):
    """Reject a probe clip that would not visibly lift the arm on this body."""
    bind = sample(root['nodes'])
    posed = sample(root['nodes'], clip['nodes'], .5)
    shoulder = 'rbicep_g' if node == 'rhand' else 'lbicep_g'
    lift = float(posed[node][2, 3] - bind[shoulder][2, 3])
    outward = float(abs(posed[node][0, 3]) - abs(bind[node][0, 3]))
    if lift < .1 or outward < -.05:
        raise ValueError(f'{root["name"]} {node}: lift {lift:.3f}, outward {outward:.3f}')
    return round(lift, 3)


def custom_nodes(root):
    return {root['name']: {'parent': None, 'controls': {}},
            'rbicep_g': {'parent': root['nodes']['rbicep_g']['parent'],
                         'controls': {20: {'times': np.array([0., 1.]), 'values': np.array([arm_quaternion(True)] * 2)}}}}


SCRIPTS = {
    'srp_inc': r'''
void SrpLog(string s){WriteTimestampedLogEntry("SRP "+s);}
void Dress(object a,int robe){
 object item=CreateItemOnObject("nw_cloth001",a);
 object copy=CopyItemAndModify(item,ITEM_APPR_TYPE_ARMOR_MODEL,ITEM_APPR_ARMOR_MODEL_ROBE,robe,TRUE);
 DestroyObject(item);
 SrpLog("dress "+GetName(a)+" valid="+IntToString(GetIsObjectValid(copy))+" robe="+IntToString(GetItemAppearance(copy,ITEM_APPR_TYPE_ARMOR_MODEL,ITEM_APPR_ARMOR_MODEL_ROBE)));
 AssignCommand(a,ClearAllActions(TRUE));AssignCommand(a,ActionEquipItem(copy,INVENTORY_SLOT_CHEST));}
void Spawn(string res,int appearance,int pheno,string label,float x,float y,int robe){
 object a=CreateObject(OBJECT_TYPE_CREATURE,res,Location(GetObjectByTag("sr_it_floor"),Vector(x,y,0.0),270.0),FALSE,"SRP_A");
 if(appearance!=15100)SetCreatureAppearanceType(a,appearance);
 SetPhenoType(pheno,a);SetName(a,label);
 int part;for(part=0;part<18;part++)SetCreatureBodyPart(part,1,a);
 ApplyEffectToObject(DURATION_TYPE_PERMANENT,SupernaturalEffect(EffectCutsceneGhost()),a);
 if(robe>=0)DelayCommand(1.0,Dress(a,robe));
 SrpLog("spawn "+label+" appearance="+IntToString(GetAppearanceType(a))+" pheno="+IntToString(GetPhenoType(a)));}
void Column(string res,int appearance,int pheno,string name,float x,int firstRobe){
 Spawn(res,appearance,pheno,name+" bare",x,17.0,-1);
 Spawn(res,appearance,pheno,name+" r005",x,20.0,5);
 Spawn(res,appearance,pheno,name+" r020",x,23.0,20);
 if(firstRobe)Spawn(res,appearance,pheno,name+" r002",x,26.0,2);}
void Say(string text){
 int n=0;object a=GetObjectByTag("SRP_A",n);
 while(GetIsObjectValid(a)){AssignCommand(a,SpeakString(GetName(a)+": "+text));a=GetObjectByTag("SRP_A",++n);}}
void Idle(string clip,string text){
 int n=0;object a=GetObjectByTag("SRP_A",n);
 while(GetIsObjectValid(a)){
  ReplaceObjectAnimation(a,"pause1",clip);ReplaceObjectAnimation(a,"pause2",clip);
  ReplaceObjectAnimation(a,"custom4lp","");
  AssignCommand(a,ClearAllActions());AssignCommand(a,ActionPlayAnimation(ANIMATION_LOOPING_PAUSE,1.0,10000.0));
  a=GetObjectByTag("SRP_A",++n);}
 Say(text);SrpLog("phase "+text);}
void Slot(string clip,string text){
 int n=0;object a=GetObjectByTag("SRP_A",n);
 while(GetIsObjectValid(a)){
  ReplaceObjectAnimation(a,"pause1","");ReplaceObjectAnimation(a,"pause2","");
  ReplaceObjectAnimation(a,"custom4lp",clip);
  AssignCommand(a,ClearAllActions());AssignCommand(a,ActionPlayAnimation(ANIMATION_LOOPING_CUSTOM4,1.0,10000.0));
  a=GetObjectByTag("SRP_A",++n);}
 Say(text);SrpLog("phase "+text);}
''',
    'srp_enter': r'''#include "srp_inc"
void main(){
 object pc=GetEnteringObject();if(!GetIsPC(pc))return;
 object module=GetModule();if(GetLocalInt(module,"SRP_READY"))return;SetLocalInt(module,"SRP_READY",1);
 Column("srp_male",15100,0,"HM Fit",7.0,1);
 Column("srp_male",15100,2,"HM Large",11.0,0);
 Column("srp_female",15100,0,"HF Fit",15.0,1);
 Column("srp_male",15101,0,"DM Fit",19.0,0);
 DelayCommand(3.0,AssignCommand(pc,SetCameraFacing(90.0,16.0,55.0,CAMERA_TRANSITION_TYPE_SNAP)));
 SrpLog("ready");}
''',
    'srp_chat': r'''#include "srp_inc"
void main(){
 string text=GetStringLowerCase(GetPCChatMessage());
 if(text=="cust")Idle("srpcust","custom right arm");
 else if(text=="lib")Idle("srplib","library left arm");
 else if(text=="off")Idle("","stock idle");
 else if(text=="slotc")Slot("srpcust","custom4 slot custom clip");
 else if(text=="slotl")Slot("srplib","custom4 slot library clip");
 else return;
 SetPCChatMessage("");}
''',
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Tools:
    def __init__(self, directory, game_root):
        self.directory, self.game_root = Path(directory), game_root

    def run(self, name, *args):
        result = subprocess.run([str(self.directory / (name + '.exe')), *map(str, args)], capture_output=True,
                                timeout=600)
        if result.returncode:
            raise RuntimeError(name + ': ' + result.stderr.decode(errors='replace')[-2000:])
        return result.stdout

    def stock(self, name, userdir):
        return self.run('nwn_resman_cat', '--root', self.game_root, '--userdirectory', userdir, '--no-ovr', name)

    def gff(self, source, target, edit):
        working = target.with_name(target.name + '.json')
        self.run('nwn_gff', '-i', source, '-k', 'json', '-o', working)
        data = json.loads(working.read_text(encoding='utf-8'))
        edit(data)
        working.write_text(json.dumps(data), encoding='utf-8')
        self.run('nwn_gff', '-i', working, '-o', target)
        working.unlink()


def stage_animation(hak, stock_dir, body):
    stock = load_model(stock_dir / 'a_ba.mdl')
    custom = (stock_dir / 'a_ba_custom.mdl').read_text(encoding='cp1252')
    (hak / 'a_ba_custom.mdl').write_text(add_custom_clip(custom), encoding='cp1252', newline='\n')
    begin, end = PARENT_FIELD
    records = []
    for library, (parent, roots) in LIBRARIES.items():
        for index, name in enumerate(roots):
            source = body / (name + '.mdl')
            root = load_model(source)
            clip = library_clip(stock, name)
            lifts = {'left': check_pose(root, clip, 'lhand'),
                     'right': check_pose(root, {'nodes': custom_nodes(root)}, 'rhand')}
            if not index:
                nodes = rename(root['nodes'], name, library)
                mapped = {**clip, 'nodes': rename(clip['nodes'], name, library)}
                (hak / (library + '.mdl')).write_text(
                    library_text(library, parent, stock['scale'], nodes, {LIBRARY_CLIP: mapped}), encoding='ascii')
            if root['parent'] != parent:
                raise ValueError(f'{name}: expected supermodel {parent}, found {root["parent"]}')
            original = source.read_bytes()
            patched = original[:begin] + library.encode().ljust(end - begin, b'\0') + original[end:]
            (hak / source.name).write_bytes(patched)
            records.append({'root': name, 'stockParent': parent, 'probeParent': library, 'armLiftMetres': lifts})
    return records


def stage_module(stage, tools, source, game_userdir, hak_order):
    shutil.copy2(source / 'repute.fac', stage / 'repute.fac')

    def actor(resref, data):
        data['TemplateResRef']['value'] = resref
        data['Tag']['value'] = 'SRP_A'
        data['Plot']['value'] = 1
        for key in list(data):
            if key.startswith('Script'):
                data[key]['value'] = ''
        for key in ('ItemList', 'Equip_ItemList'):
            if key in data:
                data[key]['value'] = []

    tools.gff(source / 'sr_it_male.utc', stage / 'srp_male.utc', lambda d: actor('srp_male', d))
    tools.gff(source / 'sr_it_female.utc', stage / 'srp_female.utc', lambda d: actor('srp_female', d))

    def area(data):
        for key in data:
            if key.startswith('On'):
                data[key]['value'] = ''

    tools.gff(source / 'sr_it_floor.are', stage / 'sr_it_floor.are', area)
    tools.gff(source / 'sr_it_floor.git', stage / 'sr_it_floor.git', lambda d: d['Creature List'].update(value=[]))

    def info(data):
        data['Mod_HakList']['value'] = [{'__struct_id': 8, 'Mod_Hak': {'type': 'cexostring', 'value': n}}
                                        for n in hak_order]
        data['Mod_Name']['value'] = {'0': 'Animation chain probe'}
        data['Mod_Tag']['value'] = 'SRP_ANIM'
        data['Mod_Description']['value'] = {'0': 'Which layer reaches bodies and robes. Not a release.'}
        data['Mod_OnClientEntr']['value'] = 'srp_enter'
        data['Mod_OnPlrChat'] = {'type': 'resref', 'value': 'srp_chat'}
        data['Mod_OnPlrEqItm']['value'] = data['Mod_OnPlrUnEqItm']['value'] = ''
        data['Mod_Entry_X']['value'], data['Mod_Entry_Y']['value'] = 13.0, 10.0

    tools.gff(source / 'module.ifo', stage / 'module.ifo', info)
    for name, text in SCRIPTS.items():
        (stage / (name + '.nss')).write_text(text, encoding='ascii')
    for name in SCRIPTS:
        if name != 'srp_inc':
            tools.run('nwn_script_comp', '--root', tools.game_root, '--userdirectory', game_userdir, '--no-ovr',
                      stage / (name + '.nss'))
            if not (stage / (name + '.ncs')).is_file():
                raise RuntimeError('No bytecode for ' + name)


def build(output, game_root, tool_dir, game_userdir, client):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    tools = Tools(tool_dir, game_root)
    stock_dir, hak, stage = output / 'stock', output / 'stage-hak', output / 'stage-module'
    user = output / 'userdir'
    for path in (stock_dir, hak, stage, user / 'hak', user / 'modules'):
        path.mkdir(parents=True)
    for name in ('a_ba.mdl', 'a_ba_custom.mdl'):
        (stock_dir / name).write_bytes(tools.stock(name, game_userdir))
    roots = stage_animation(hak, stock_dir, REPO / 'srn_body')
    hak_order = [HAK, 'sw_reviewenv', 'srn_body_tex', 'srn_body', 'srn_2da']
    stage_module(stage, tools, REPO / 'test-modules/weapon-waves/module', game_userdir, hak_order)
    tools.run('nwn_erf', '-c', '-e', 'HAK', '-f', user / 'hak' / (HAK + '.hak'), hak)
    for name, folder in (('sw_reviewenv', REPO / 'test-modules/weapon-waves/haks/sw_reviewenv'),
                         ('srn_body_tex', REPO / 'srn_body_tex'), ('srn_body', REPO / 'srn_body'),
                         ('srn_2da', REPO / 'srn_2da')):
        tools.run('nwn_erf', '-c', '-e', 'HAK', '-f', user / 'hak' / (name + '.hak'), folder)
    module = user / 'modules' / (MODULE + '.mod')
    tools.run('nwn_erf', '-c', '-e', 'MOD', '-f', module, stage)
    from build_head_trial import launch_scripts
    cmd, ps1 = launch_scripts(MODULE, client)
    (output / 'Launch.cmd').write_bytes(cmd.encode('ascii'))
    (output / 'Launch.ps1').write_bytes(ps1.encode('utf-8'))
    files = [{'relativePath': f'userdir/hak/{n}.hak', 'sha256': sha(user / 'hak' / (n + '.hak'))} for n in hak_order]
    files.append({'relativePath': f'userdir/modules/{MODULE}.mod', 'sha256': sha(module)})
    manifest = {'kind': 'anim-chain-probe', 'files': files, 'roots': roots,
                'stock': {n: sha(stock_dir / n) for n in ('a_ba.mdl', 'a_ba_custom.mdl')},
                'clips': {CUSTOM_CLIP: 'right arm, a_ba_custom override', LIBRARY_CLIP: 'left arm, layer under root'},
                'clientObserved': False, 'productionAccepted': False}
    (output / 'runtime-manifest.json').write_text(json.dumps(manifest, indent=2))
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--game-root', required=True)
    parser.add_argument('--tool-dir', required=True)
    parser.add_argument('--game-userdir', required=True)
    parser.add_argument('--client')
    print(json.dumps(build(**vars(parser.parse_args()))['roots'], indent=1))
