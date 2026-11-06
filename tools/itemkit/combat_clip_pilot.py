"""Import pilot: old combat clips in `a_ba_custom` for Human, Orc and Troll bodies.

Takes rifle, reload, grenade and shotgun clips from the old male and female ASCII
models, keeps their rotations, rescales the root and drops everything else. Human
male clips keep their `customN` names. Other slots get their own names and scripts
map them with `ReplaceObjectAnimation`. Nothing ships. Output goes to ignored `output/`.
"""
import argparse
import json
from pathlib import Path
import re
import sys

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO), str(REPO / 'tools/itemkit')]
import anim_chain_probe as probe
from tools.phenomorpher.phenomorpher.engine.anim_library import load_model
from tools.phenomorpher.phenomorpher.engine.native_motion import sample

CLIPS = {'custom11lp': '11lp', 'custom12lp': '12lp', 'custom14lp': '14lp', 'custom16start': '16st',
         'custom18start': '18st', 'custom19lp': '19lp'}
SLOTS = {'hm': 'pmh', 'hf': 'pfh', 'om': 'pmo', 'of': 'pfo', 'gm': 'pmg', 'gf': 'pfg'}
SOURCES = {'m': ('a_ba_non_combat', 'a_ba'), 'f': ('a_fa', 'a_fa')}
RIFLE = 'sra84e4660_5'
BLOCK = re.compile(r'(?ms)^\s*node (\w+) (\S+)(.*?)^\s*endnode')
KEY_HEADER = re.compile(r'(?m)^\s*(position|orientation)key(?:[ \t]+(\d+))?[ \t]*\r?$')


def read_keys(block):
    """Key tables of one node, in either the `endlist` or the counted ASCII form."""
    keys = {}
    for header in KEY_HEADER.finditer(block):
        lines = block[header.end():].lstrip('\r\n').splitlines()
        if header[2]:
            rows = lines[:int(header[2])]
        else:
            rows = lines[:next(i for i, line in enumerate(lines) if line.strip() == 'endlist')]
        keys[header[1]] = np.array([[float(v) for v in line.split()] for line in rows])
    if len(keys) != len(re.findall(r'(?m)^\s*\w+key\b', block)):
        raise ValueError('Key tables were not all read')
    return keys


def read_clip(text, name):
    """One clip as header fields, events and per-node keys, with node names lowered."""
    match = re.search(r'(?ms)^newanim ' + re.escape(name) + r' \S+\n(.*?)^doneanim', text)
    if not match:
        raise ValueError('Missing clip ' + name)
    body = match[1]
    if re.search(r'(?m)^\s*\w*bezierkey', body):
        raise ValueError(name + ': bezier keys are not handled')
    clip = {'length': float(re.search(r'(?m)^\s*length\s+(\S+)', body)[1]),
            'transition': float(re.search(r'(?m)^\s*transtime\s+(\S+)', body)[1]),
            'animroot': re.search(r'(?m)^\s*animroot\s+(\S+)', body)[1],
            'events': re.findall(r'(?m)^\s*event\s+(\S+)\s+(\S+)', body), 'nodes': {}}
    for _, node, block in BLOCK.findall(body):
        clip['nodes'][node.lower()] = read_keys(block)
    return clip


def quaternions(rows):
    """Axis-angle orientation keys as xyzw quaternions."""
    axis, angle = rows[:, 1:4], rows[:, 4] / 2
    lengths = np.linalg.norm(axis, axis=1, keepdims=True)
    unit = np.divide(axis, lengths, out=np.zeros_like(axis), where=lengths > 1e-12)
    return np.column_stack((unit * np.sin(angle)[:, None], np.cos(angle)))


def retarget(clip, tree_names, stock_bind, target_bind):
    """Keep rotations on rig nodes and fit the root key to the target. Limb positions are dropped."""
    scale = target_bind[2] / stock_bind[2]
    delta = target_bind - stock_bind * scale
    keys, dropped = {}, sorted(set(clip['nodes']) - tree_names)
    for node, row in clip['nodes'].items():
        if node not in tree_names:
            continue
        kept = {}
        if 'orientation' in row:
            kept['orientation'] = row['orientation']
        if node == 'rootdummy' and 'position' in row:
            moved = row['position'].copy()
            moved[:, 1:4] = moved[:, 1:4] * scale + delta
            kept['position'] = moved
        if kept:
            keys[node] = kept
    return {**clip, 'nodes': keys}, dropped


def clip_text(name, owner, clip, tree):
    lines = [f'newanim {name} {owner}', f'  length {clip["length"]:.6g}', f'  transtime {clip["transition"]:.6g}',
             f'  animroot {clip["animroot"] if clip["animroot"] == "torso_g" else "rootdummy"}']
    lines += [f'  event {time} {event}' for time, event in clip['events']]
    for kind, node, parent in tree:
        lines += [f'    node {kind} {node}', f'        parent {parent}']
        for label in ('position', 'orientation'):
            rows = clip['nodes'].get(node.lower(), {}).get(label)
            if rows is not None:
                lines.append(f'        {label}key')
                lines += ['            ' + ' '.join(f'{v:.6g}' for v in row) for row in rows]
                lines.append('        endlist')
        lines.append('    endnode')
    return '\n'.join(lines + [f'doneanim {name} {owner}', ''])


def sampled_nodes(clip, parents):
    rows = {}
    for node, keys in clip['nodes'].items():
        controls = {}
        if 'orientation' in keys:
            controls[20] = {'times': keys['orientation'][:, 0], 'values': quaternions(keys['orientation'])}
        if 'position' in keys:
            controls[8] = {'times': keys['position'][:, 0], 'values': keys['position'][:, 1:4]}
        rows[node] = {'parent': parents.get(node), 'controls': controls}
    return rows


def hand_gap(root, clip):
    """Distance between the hands mid-clip, the offline measure of a two-handed grip."""
    pose = sample(root['nodes'], sampled_nodes(clip, {n: r['parent'] for n, r in root['nodes'].items()}), clip['length'] / 2)
    return round(float(np.linalg.norm(pose['rhand'][:3, 3] - pose['lhand'][:3, 3])), 3)


def stage_animation(hak, stock_dir, source_dir, body):
    custom = (stock_dir / 'a_ba_custom.mdl').read_text(encoding='cp1252')
    tree = probe.stock_clip_tree(custom, 'a_ba_custom')
    names = {name.lower() for _, name, _ in tree}
    blocks, records = [], []
    sources = {sex: (source_dir / (f + '.mdl')).read_text(encoding='cp1252') for sex, (f, _) in SOURCES.items()}
    for slot, prefix in SLOTS.items():
        sex = slot[1]
        stock_bind = load_model(body / f'p{sex}h0.mdl')['nodes']['rootdummy']['controls'][8]['values'][0]
        roots = [load_model(body / f'{prefix}{pheno}.mdl') for pheno in (0, 2)]
        target = roots[0]['nodes']['rootdummy']['controls'][8]['values'][0]
        for name, code in CLIPS.items():
            fitted, dropped = retarget(read_clip(sources[sex], name), names, stock_bind, target)
            label = name if slot == 'hm' else f'c{code}_{slot}'
            blocks.append(clip_text(label, 'a_ba_custom', fitted, tree))
            records.append({'slot': slot, 'clip': label, 'source': name, 'droppedNodes': dropped,
                            'handGapMetres': {'fit': hand_gap(roots[0], fitted), 'large': hand_gap(roots[1], fitted)}})
    closing = 'donemodel a_ba_custom'
    if custom.count(closing) != 1:
        raise ValueError('Unexpected stock a_ba_custom shape')
    (hak / 'a_ba_custom.mdl').write_text(custom.replace(closing, ''.join(blocks) + closing), encoding='cp1252', newline='\n')
    return records


PHASES = r'''
string SlotOf(object a){
 int t=GetAppearanceType(a);string race="h";if(t==15103)race="o";if(t==15104)race="g";
 return race+(GetGender(a)==GENDER_FEMALE?"f":"m");}
void Map(object a,string stock,string code){
 string slot=SlotOf(a);ReplaceObjectAnimation(a,stock,slot=="hm"?"":"c"+code+"_"+slot);}
void Clips(string stock,string code,int constant,string text){
 int n=0;object a=GetObjectByTag("SRP_A",n);
 while(GetIsObjectValid(a)){
  ReplaceObjectAnimation(a,"pause1","");ReplaceObjectAnimation(a,"pause2","");
  Map(a,stock,code);
  AssignCommand(a,ClearAllActions());AssignCommand(a,ActionPlayAnimation(constant,1.0,10000.0));
  a=GetObjectByTag("SRP_A",++n);}
 Say(text);SrpLog("phase "+text);}
void LogAmmo(string text){
 int n=0;object a=GetObjectByTag("SRP_A",n);
 while(GetIsObjectValid(a)){
  SrpLog("ammo "+text+" | "+GetName(a)+" bolts="+IntToString(GetItemStackSize(GetItemInSlot(INVENTORY_SLOT_BOLTS,a)))+" bullets="+IntToString(GetItemStackSize(GetItemInSlot(INVENTORY_SLOT_BULLETS,a))));
  a=GetObjectByTag("SRP_A",++n);}}
void Attack(string shot,string code,string native,string text){
 LogAmmo(text);DelayCommand(10.0,LogAmmo(text));
 object target=GetObjectByTag("SRP_T");
 int n=0;object a=GetObjectByTag("SRP_A",n);
 while(GetIsObjectValid(a)){
  ReplaceObjectAnimation(a,"pause1","");ReplaceObjectAnimation(a,"pause2","");
  string slot=SlotOf(a);
  ReplaceObjectAnimation(a,shot,slot=="hm"?native:"c"+code+"_"+slot);
  AssignCommand(a,ClearAllActions(TRUE));AssignCommand(a,ActionAttack(target));
  a=GetObjectByTag("SRP_A",++n);}
 Say(text);SrpLog("phase "+text);}
void ArmWith(string resref,string ammo,int ammoSlot){
 int n=0;object a=GetObjectByTag("SRP_A",n);
 while(GetIsObjectValid(a)){
  object shots=CreateItemOnObject(ammo,a,99);
  object item=CreateItemOnObject(resref,a);
  AssignCommand(a,ClearAllActions(TRUE));
  AssignCommand(a,ActionEquipItem(shots,ammoSlot));
  AssignCommand(a,ActionEquipItem(item,INVENTORY_SLOT_RIGHTHAND));
  SrpLog("arm "+GetName(a)+" "+resref+" valid="+IntToString(GetIsObjectValid(item)));
  a=GetObjectByTag("SRP_A",++n);}}
void Arm(){ArmWith("''' + RIFLE + r'''","nw_wambo001",INVENTORY_SLOT_BOLTS);}
void Show(int appearance,string race){ShowRace(appearance,race);DelayCommand(3.0,Arm());}
'''
ENTER = r'''#include "srp_inc"
void main(){
 object pc=GetEnteringObject();if(!GetIsPC(pc))return;
 object module=GetModule();if(GetLocalInt(module,"SRP_READY"))return;SetLocalInt(module,"SRP_READY",1);
 ApplyEffectToObject(DURATION_TYPE_PERMANENT,SupernaturalEffect(EffectLinkEffects(EffectVisualEffect(VFX_DUR_CUTSCENE_INVISIBILITY),EffectCutsceneGhost())),pc);
 CreateObject(OBJECT_TYPE_CREATURE,"srp_tgt",Location(GetObjectByTag("sr_it_floor"),Vector(15.7,8.0,0.0),90.0),FALSE,"SRP_T");
 Show(15104,"Troll");
 DelayCommand(5.0,Camera(pc,90.0,22.0,58.0));
 SrpLog("ready");}
'''
CHAT = r'''#include "srp_inc"
void Move(object pc,float x,float y,float distance,float pitch){
 AssignCommand(pc,ClearAllActions(TRUE));
 AssignCommand(pc,JumpToLocation(Location(GetArea(pc),Vector(x,y,0.0),90.0)));
 DelayCommand(0.5,Camera(pc,90.0,distance,pitch));}
void main(){
 object pc=GetPCChatSpeaker();
 string text=GetStringLowerCase(GetPCChatMessage());
 if(text=="frifle")Attack("xbowshot","11lp","custom11lp","attack xbowshot rifle");
 else if(text=="fproof")Attack("xbowshot","18st","custom18start","attack proof grenade on xbowshot");
 else if(text=="fshot")Attack("xbowshot","19lp","custom19lp","attack xbowshot shotgun");
 else if(text=="fsmg")Attack("xbowshot","14lp","custom14lp","attack xbowshot smg no hit event");
 else if(text=="fpistol")Attack("throwr","12lp","custom12lp","attack throwr pistol");
 else if(text=="pistol")ArmWith("sr_cl36_1","nw_wambu001",INVENTORY_SLOT_BULLETS);
 else if(text=="rifle")Clips("custom11lp","11lp",ANIMATION_LOOPING_CUSTOM11,"rifle");
 else if(text=="shot")Clips("custom19lp","19lp",ANIMATION_LOOPING_CUSTOM19,"shotgun");
 else if(text=="reload")Clips("custom16start","16st",ANIMATION_LOOPING_CUSTOM16,"reload start");
 else if(text=="reloadl")Clips("custom16lp","16st",ANIMATION_LOOPING_CUSTOM16,"reload as lp");
 else if(text=="gren")Clips("custom18start","18st",ANIMATION_LOOPING_CUSTOM18,"grenade start");
 else if(text=="grenl")Clips("custom18lp","18st",ANIMATION_LOOPING_CUSTOM18,"grenade as lp");
 else if(text=="off")Idle("","stock idle");
 else if(text=="human")Show(15100,"Human");
 else if(text=="orc")Show(15103,"Orc");
 else if(text=="troll")Show(15104,"Troll");
 else if(text=="wide")Move(pc,15.7,20.0,22.0,58.0);
 else if(GetStringLeft(text,3)=="at "){
  int col=StringToInt(GetSubString(text,3,1));int row=StringToInt(GetSubString(text,5,1));
  Move(pc,5.0+6.0*IntToFloat(col)+1.2*IntToFloat(row),15.0+4.5*IntToFloat(row),7.0,72.0);}
 else return;
 SetPCChatMessage("");}
'''


def build(output, source_dir, game_root, tool_dir, game_userdir, client):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    tools = probe.Tools(tool_dir, game_root)
    stock_dir, hak, stage = output / 'stock', output / 'stage-hak', output / 'stage-module'
    user = output / 'userdir'
    for path in (stock_dir, hak, stage, user / 'hak', user / 'modules'):
        path.mkdir(parents=True)
    (stock_dir / 'a_ba_custom.mdl').write_bytes(tools.stock('a_ba_custom.mdl', game_userdir))
    records = stage_animation(hak, stock_dir, Path(source_dir), REPO / 'srn_body')
    hak_order = [probe.HAK, 'sw_reviewenv', 'srn_weapon', 'srn_armor', 'srn_body_tex', 'srn_body', 'srn_2da']
    scripts = {'srp_inc': probe.SCRIPTS['srp_inc'] + PHASES, 'srp_enter': ENTER, 'srp_chat': CHAT}
    probe.stage_module(stage, tools, REPO / 'test-modules/weapon-waves/module', game_userdir, hak_order, scripts)

    def target(data):
        data['TemplateResRef']['value'] = 'srp_tgt'
        data['Tag']['value'] = 'SRP_T'
        for key in data:
            if key.startswith('Script'):
                data[key]['value'] = ''

    tools.gff(REPO / 'test-modules/weapon-waves/module/sr_it_target.utc', stage / 'srp_tgt.utc', target)
    tools.run('nwn_erf', '-c', '-e', 'HAK', '-f', user / 'hak' / (probe.HAK + '.hak'), hak)
    for name, folder in (('sw_reviewenv', REPO / 'test-modules/weapon-waves/haks/sw_reviewenv'),
                         *((n, REPO / n) for n in hak_order[2:])):
        tools.run('nwn_erf', '-c', '-e', 'HAK', '-f', user / 'hak' / (name + '.hak'), folder)
    module = user / 'modules' / (probe.MODULE + '.mod')
    tools.run('nwn_erf', '-c', '-e', 'MOD', '-f', module, stage)
    from build_head_trial import launch_scripts
    cmd, ps1 = launch_scripts(probe.MODULE, client)
    (output / 'Launch.cmd').write_bytes(cmd.encode('ascii'))
    (output / 'Launch.ps1').write_bytes(ps1.encode('utf-8'))
    files = [{'relativePath': f'userdir/hak/{n}.hak', 'sha256': probe.sha(user / 'hak' / (n + '.hak'))} for n in hak_order]
    files.append({'relativePath': f'userdir/modules/{probe.MODULE}.mod', 'sha256': probe.sha(module)})
    manifest = {'kind': 'combat-clip-pilot', 'files': files, 'clips': records,
                'customBytes': (hak / 'a_ba_custom.mdl').stat().st_size,
                'clientObserved': False, 'productionAccepted': False}
    (output / 'runtime-manifest.json').write_text(json.dumps(manifest, indent=2))
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--source-dir', required=True)
    parser.add_argument('--game-root', required=True)
    parser.add_argument('--tool-dir', required=True)
    parser.add_argument('--game-userdir', required=True)
    parser.add_argument('--client')
    result = build(**vars(parser.parse_args()))
    print(result['customBytes'])
    for row in result['clips']:
        print(row['slot'], row['clip'], row['droppedNodes'], row['handGapMetres'])
