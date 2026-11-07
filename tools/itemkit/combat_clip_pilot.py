"""Import pilot: old combat clips in `a_ba_custom` for all five playable races.

Takes rifle, reload, grenade and shotgun clips from the old male and female ASCII
models, keeps their rotations, rescales the root and drops everything else. Two-handed
clips then level the rifle and solve the left arm onto its fore-end per body. Human
male clips keep their `customN` names. Other slots get their own names and scripts
map them with `ReplaceObjectAnimation`. Nothing ships. Output goes to ignored `output/`.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO), str(REPO / 'tools/itemkit')]
import anim_chain_probe as probe
from tools.phenomorpher.phenomorpher.engine.anim_library import load_model
from tools.phenomorpher.phenomorpher.engine.native_motion import quaternion_matrix, sample

CLIPS = {'custom11lp': '11lp', 'custom12lp': '12lp', 'custom14lp': '14lp', 'custom16start': '16st',
         'custom18start': '18st', 'custom19lp': '19lp'}
SLOTS = {'hm': 'pmh', 'hf': 'pfh', 'dm': 'pmd', 'df': 'pfd', 'em': 'pme', 'ef': 'pfe', 'om': 'pmo', 'of': 'pfo',
         'gm': 'pmg', 'gf': 'pfg'}
WEAPONS = {'rifle': {'parts': ('wbwxh_t_015.mdl',), 'barrel': (-.33, -.03), 'front': -.25, 'rear': -.19, 'pump': None},
           'smg': {'parts': ('wbwsl_m_023.mdl',), 'barrel': (-.32, -.14), 'front': -.10, 'rear': -.07, 'pump': None},
           # No shotgun is built yet. The AK-98 stands in for the barrel line and fore-end until one is.
           'shotgun': {'parts': ('wbwxh_t_015.mdl',), 'barrel': (-.33, -.03), 'front': -.30, 'rear': -.24, 'pump': -.18}}
TWO_HANDED = {'custom11lp': 'rifle', 'custom14lp': 'smg', 'custom19lp': 'shotgun'}
ARM = ('lbicep_g', 'lforearm_g', 'lhand_g')
HANDS = {'rhand', 'lhand'}
RIGHT_ARM = ('rbicep_g', 'rforearm_g', 'rhand_g')
CHAIN = ('rootdummy', 'torso_g', *RIGHT_ARM, *ARM)
PALM_CLEARANCE, REACH, MAX_PULL = .015, .97, .16
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
    """Keep rotations on rig nodes and fit the root key to the target. Limb positions are dropped.

    Weapon attachment nodes are held flat from start to end, so no stock clip's hand rotation carries over.
    """
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
    for node in HANDS & tree_names:
        keys[node] = {'orientation': np.array([[0., 1., 0., 0., 0.], [clip['length'], 1., 0., 0., 0.]])}
    return {**clip, 'nodes': keys}, dropped


def rotation_between(a, b):
    """Smallest rotation carrying direction a onto direction b."""
    a, b = a / np.linalg.norm(a), b / np.linalg.norm(b)
    cross = np.cross(a, b)
    sine, cosine = np.linalg.norm(cross), float(a @ b)
    if sine < 1e-10:
        if cosine < 0:
            raise ValueError('Ambiguous opposite directions')
        return np.eye(3)
    k = np.array([[0, -cross[2], cross[1]], [cross[2], 0, -cross[0]], [-cross[1], cross[0], 0]]) / sine
    return np.eye(3) + sine * k + (1 - cosine) * k @ k


def matrix_quaternion(m):
    """xyzw quaternion of a rotation matrix."""
    w, x, y, z = (np.sqrt(max(0., 1 + s)) / 2 for s in (m[0, 0] + m[1, 1] + m[2, 2], m[0, 0] - m[1, 1] - m[2, 2],
                                                        m[1, 1] - m[0, 0] - m[2, 2], m[2, 2] - m[0, 0] - m[1, 1]))
    x, y, z = np.copysign(x, m[2, 1] - m[1, 2]), np.copysign(y, m[0, 2] - m[2, 0]), np.copysign(z, m[1, 0] - m[0, 1])
    return np.array([x, y, z, w]) / np.linalg.norm([x, y, z, w])


def axis_row(time, matrix):
    """One orientation key in the ASCII axis-angle form."""
    x, y, z, w = matrix_quaternion(matrix)
    sine = np.linalg.norm([x, y, z])
    axis = np.array([x, y, z]) / sine if sine > 1e-9 else np.array([1., 0., 0.])
    return [time, *axis, 2 * np.arctan2(sine, w)]


def weapon_marks(models, spec):
    """Barrel line, hand correction and support range of a weapon, in its own (rhand) frame."""
    parts = []
    for text in models:
        match = re.search(r'(?m)^\s*verts\s+(\d+)\s*\n', text)
        rows = text[match.end():].splitlines()[:int(match[1])]
        parts.append(np.array([[float(v) for v in row.split()[:3]] for row in rows]))
    verts = np.vstack([part for part in parts if len(part) > 8])
    bands = np.arange(*spec['barrel'], .03)
    top = [(z + .015, verts[(verts[:, 2] >= z) & (verts[:, 2] < z + .03), 1].max()) for z in bands]
    slope = np.polyfit(*zip(*top), 1)[0]
    barrel = np.array([0., -slope, -1.]) / np.linalg.norm([0., -slope, -1.])
    up = np.array([0., -barrel[2], barrel[1]])
    return {'barrel': barrel, 'up': up, 'verts': verts, 'front': spec['front'], 'rear': spec['rear'], 'pump': spec['pump'],
            'correction': np.array([[1., 0., 0.], up, -barrel]), 'tiltDegrees': float(np.degrees(np.arctan(-slope)))}


def support_point(marks, z):
    """Palm contact under the fore-end at one distance along the weapon."""
    fore = marks['verts'][np.abs(marks['verts'][:, 2] - z) < .03]
    return np.array([0., np.percentile(fore[:, 1], 3) - PALM_CLEARANCE, z])


def level_rifle(clip, correction):
    """Turn the right hand so the barrel lies where the old clip aimed its weapon."""
    node = clip['nodes']['rhand_g']
    rows = [axis_row(row[0], quaternion_matrix(quaternions(row[None])[0]) @ correction) for row in node['orientation']]
    return {**clip, 'nodes': {**clip['nodes'], 'rhand_g': {**node, 'orientation': np.array(rows)}}}


def limb_rotations(rig, names, before, after, wrist, hand):
    """Local rotations that put an arm's wrist and hand in place, with the source elbow as pole and its twist kept."""
    bicep, forearm, palm = names
    upper_offset, lower_offset = (rig[node]['controls'][8]['values'][0] for node in (forearm, palm))
    upper_length, lower_length = np.linalg.norm(upper_offset), np.linalg.norm(lower_offset)
    shoulder = after[bicep][:3, 3]
    distance = np.linalg.norm(wrist - shoulder)
    axis = (wrist - shoulder) / distance
    pole = before[forearm][:3, 3] - before[bicep][:3, 3]
    pole -= (pole @ axis) * axis
    pole /= np.linalg.norm(pole)
    along = (upper_length ** 2 - lower_length ** 2 + distance ** 2) / (2 * distance)
    elbow = shoulder + along * axis + np.sqrt(upper_length ** 2 - along ** 2) * pole
    upper = rotation_between(before[bicep][:3, :3] @ upper_offset, elbow - shoulder) @ before[bicep][:3, :3]
    lower = rotation_between(before[forearm][:3, :3] @ lower_offset, wrist - elbow) @ before[forearm][:3, :3]
    return after['torso_g'][:3, :3].T @ upper, upper.T @ lower, lower.T @ hand


def arm_length(rig, names):
    return sum(np.linalg.norm(rig[node]['controls'][8]['values'][0]) for node in names[1:])


def solve_support(clip, root, marks):
    """Key the arms for one body so the left palm stays on the fore-end, and follows the pump if there is one.

    The palm first slides back along its range. If that isn't enough the weapon is pulled toward the left shoulder.
    """
    rig = root['nodes']
    parents = {name: row['parent'] for name, row in rig.items()}
    palm_offset = rig['lhand']['controls'][8]['values'][0]
    source = sampled_nodes(clip, parents)
    level = level_rifle(clip, marks['correction'])
    posed = sampled_nodes(level, parents)
    times = sorted({float(t) for node in CHAIN for rows in level['nodes'].get(node, {}).values() for t in rows[:, 0]}
                   | {0., clip['length']})
    poses = [(time, sample(rig, source, time), sample(rig, posed, time)) for time in times]
    reach = REACH * arm_length(rig, ARM)
    right_reach = REACH * arm_length(rig, RIGHT_ARM)
    gaps = np.array([(np.linalg.inv(before['rhand']) @ before['lhand'])[2, 3] for _, before, _ in poses])
    phases = (gaps - gaps.min()) / (gaps.max() - gaps.min()) if marks['pump'] is not None else np.zeros(len(poses))
    towards = [after['lbicep_g'][:3, 3] - after['rhand'][:3, 3] for _, _, after in poses]
    trials = ((pull, z) for pull in np.arange(0., MAX_PULL + .001, .01)
              for z in np.arange(marks['front'], marks['rear'] + .001, .01))
    for pull, z in trials:
        start = support_point(marks, z)
        end = support_point(marks, marks['pump']) if marks['pump'] is not None else start
        path = start + phases[:, None] * (end - start)
        shifts = [pull * v / np.linalg.norm(v) for v in towards]
        wrists = []
        for (_, before, after), support, shift in zip(poses, path, shifts):
            rifle = after['rhand']
            hand = rifle[:3, :3] @ before['rhand'][:3, :3].T @ before['lhand_g'][:3, :3]
            wrists.append(((rifle @ np.r_[support, 1.])[:3] + shift - hand @ palm_offset, hand))
        if (all(np.linalg.norm(w - after['lbicep_g'][:3, 3]) <= reach for (w, _), (_, _, after) in zip(wrists, poses))
                and all(np.linalg.norm(after['rhand_g'][:3, 3] + shift - after['rbicep_g'][:3, 3]) <= right_reach
                        for (_, _, after), shift in zip(poses, shifts))):
            break
    else:
        raise ValueError(f'{root["name"]}: fore-end out of reach')
    keys = {node: [] for node in (*ARM, *RIGHT_ARM)}
    for (time, before, after), (wrist, hand), shift in zip(poses, wrists, shifts):
        for node, local in zip(ARM, limb_rotations(rig, ARM, before, after, wrist, hand)):
            keys[node].append(axis_row(time, local))
        if pull:
            held = after['rhand_g']
            for node, local in zip(RIGHT_ARM, limb_rotations(rig, RIGHT_ARM, before, after, held[:3, 3] + shift, held[:3, :3])):
                keys[node].append(axis_row(time, local))
    nodes = dict(level['nodes'])
    for node, rows in keys.items():
        if rows:
            nodes[node] = {**nodes.get(node, {}), 'orientation': np.array(rows)}
    return {**level, 'nodes': nodes, 'support': (np.array(times), path), 'pull': float(pull)}


def fit_errors(clip, source, root, marks):
    """Worst palm-to-fore-end distance and barrel error against the old clip's aim, over the clip."""
    parents = {name: row['parent'] for name, row in root['nodes'].items()}
    gaps, aims = [], []
    for time in np.linspace(0., clip['length'], 21):
        pose = sample(root['nodes'], sampled_nodes(clip, parents), time)
        wanted = -sample(root['nodes'], sampled_nodes(source, parents), time)['rhand'][:3, 2]
        times, path = clip['support']
        point = [np.interp(time, times, path[:, axis]) for axis in range(3)]
        target = (pose['rhand'] @ np.r_[point, 1.])[:3]
        gaps.append(float(np.linalg.norm(pose['lhand'][:3, 3] - target)))
        barrel = pose['rhand'][:3, :3] @ marks['barrel']
        aims.append(float(np.degrees(np.arccos(np.clip(barrel @ wanted, -1, 1)))))
    return {'supportZ': round(float(clip['support'][1][:, 2].min()), 2), 'pullMetres': round(clip['pull'], 2), 'contactMetres': round(max(gaps), 4),
            'aimDegrees': round(max(aims), 3)}


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


def stage_animation(hak, stock_dir, source_dir, body, weapons):
    custom = (stock_dir / 'a_ba_custom.mdl').read_text(encoding='cp1252')
    tree = probe.stock_clip_tree(custom, 'a_ba_custom')
    names = {name.lower() for _, name, _ in tree}
    blocks, records = [], []
    sources = {sex: (source_dir / (f + '.mdl')).read_text(encoding='cp1252') for sex, (f, _) in SOURCES.items()}
    for slot, prefix in SLOTS.items():
        sex = slot[1]
        stock_bind = load_model(body / f'p{sex}h0.mdl')['nodes']['rootdummy']['controls'][8]['values'][0]
        roots = [load_model(body / f'{prefix}{pheno}.mdl') for pheno in (0, 2)]
        binds = [root['nodes']['rootdummy']['controls'][8]['values'][0] for root in roots]
        for name, code in CLIPS.items():
            raw, dropped = retarget(read_clip(sources[sex], name), names, stock_bind, binds[0])
            label = name if slot == 'hm' else f'c{code}_{slot}'
            row = {'slot': slot, 'clip': label, 'source': name, 'droppedNodes': dropped}
            if name not in TWO_HANDED:
                blocks.append(clip_text(label, 'a_ba_custom', raw, tree))
                row['handGapMetres'] = {'fit': hand_gap(roots[0], raw), 'large': hand_gap(roots[1], raw)}
                records.append(row)
                continue
            marks = weapons[TWO_HANDED[name]]
            solved = solve_support(raw, roots[0], marks)
            blocks.append(clip_text(label, 'a_ba_custom', solved, tree))
            row['fit'] = fit_errors(solved, raw, roots[0], marks)
            if sex == 'f':
                wide, _ = retarget(read_clip(sources[sex], name), names, stock_bind, binds[1])
                large = solve_support(wide, roots[1], marks)
                blocks.append(clip_text(label + 'l', 'a_ba_custom', large, tree))
                row['large'] = fit_errors(large, wide, roots[1], marks)
            else:
                row['large'] = fit_errors(solved, raw, roots[1], marks)
            records.append(row)
    closing = 'donemodel a_ba_custom'
    if custom.count(closing) != 1:
        raise ValueError('Unexpected stock a_ba_custom shape')
    (hak / 'a_ba_custom.mdl').write_text(custom.replace(closing, ''.join(blocks) + closing), encoding='cp1252', newline='\n')
    return records


PHASES = r'''
string SlotOf(object a){
 int t=GetAppearanceType(a);string race="h";if(t==15101)race="d";if(t==15102)race="e";if(t==15103)race="o";if(t==15104)race="g";
 return race+(GetGender(a)==GENDER_FEMALE?"f":"m");}
string ClipSlot(object a,string code){
 string large=(code=="11lp"||code=="14lp"||code=="19lp")&&GetGender(a)==GENDER_FEMALE&&GetPhenoType(a)==2?"l":"";
 return SlotOf(a)+large;}
void Map(object a,string stock,string code){
 string slot=ClipSlot(a,code);ReplaceObjectAnimation(a,stock,slot=="hm"?"":"c"+code+"_"+slot);}
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
  string slot=ClipSlot(a,code);
  ReplaceObjectAnimation(a,shot,slot=="hm"?native:"c"+code+"_"+slot);
  AssignCommand(a,ClearAllActions(TRUE));AssignCommand(a,ActionAttack(target));
  a=GetObjectByTag("SRP_A",++n);}
 Say(text);SrpLog("phase "+text);}
void Hold(string code,string native){
 int n=0;object a=GetObjectByTag("SRP_A",n);
 while(GetIsObjectValid(a)){
  string slot=ClipSlot(a,code);string clip=slot=="hm"?native:"c"+code+"_"+slot;
  ReplaceObjectAnimation(a,"xbowrdy",clip);ReplaceObjectAnimation(a,"xbowr",clip);
  ReplaceObjectAnimation(a,"bowrdy",clip);ReplaceObjectAnimation(a,"bow",clip);
  ReplaceObjectAnimation(a,"1hreadyr",clip);ReplaceObjectAnimation(a,"1hreadyl",clip);
  ReplaceObjectAnimation(a,"nwreadyr",clip);ReplaceObjectAnimation(a,"nwreadyl",clip);
  a=GetObjectByTag("SRP_A",++n);}}
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
 SetImmortal(CreateObject(OBJECT_TYPE_CREATURE,"srp_tgt",Location(GetObjectByTag("sr_it_floor"),Vector(15.7,8.0,0.0),90.0),FALSE,"SRP_T"),TRUE);
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
 if(text=="hold")Hold("11lp","custom11lp");
 else if(text=="holdsmg")Hold("14lp","custom14lp");
 else if(text=="holdshot")Hold("19lp","custom19lp");
 else if(text=="ingram")ArmWith("sre9a211be_3","nw_wambu001",INVENTORY_SLOT_BULLETS);
 else if(text=="fingram")Attack("throwr","14lp","custom14lp","attack throwr ingram");
 else if(text=="side")Camera(pc,0.0,5.0,80.0);
 else if(text=="frifle")Attack("xbowshot","11lp","custom11lp","attack xbowshot rifle");
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
 else if(text=="dwarf")Show(15101,"Dwarf");
 else if(text=="elf")Show(15102,"Elf");
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
    weapons = {}
    for label, spec in WEAPONS.items():
        models = []
        for part in spec['parts']:
            binary, text = stock_dir / (part + '.bin'), stock_dir / part
            binary.write_bytes((REPO / 'srn_weapon' / part).read_bytes())
            subprocess.run([str(REPO / 'tools/vendor/nwnmdlcomp/nwnmdlcomp.exe'), '-d', '-e', str(binary), str(text)],
                           check=True, capture_output=True, timeout=120)
            models.append(text.read_text(encoding='cp1252'))
        weapons[label] = weapon_marks(models, spec)
    records = stage_animation(hak, stock_dir, Path(source_dir), REPO / 'srn_body', weapons)
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
                'weaponTiltDegrees': {label: marks['tiltDegrees'] for label, marks in weapons.items()},
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
        print(row['slot'], row['clip'], row.get('fit'), row.get('large'), row.get('handGapMetres'))
