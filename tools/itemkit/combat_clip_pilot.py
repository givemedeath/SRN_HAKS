"""Import pilot: old combat clips in `a_ba_custom` for all five playable races.

Takes rifle, reload, grenade and shotgun clips from the old male and female ASCII
models, keeps their rotations, rescales the root and drops everything else. Two-handed
clips then level the rifle and solve the left arm onto its fore-end per body. Every slot
gets `<action>_<weapon>_<slot>` names, and scripts map them with `ReplaceObjectAnimation`.
Output goes to ignored `output/`. Its `a_ba_custom.mdl` is what `srn_body` ships, so a change to a clip means copying the new build there
and updating the contract and the hash pin in `runtime_rules.py`. The test module, chat commands and stand-ins stay private to this pilot.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

import numpy as np

REPO = Path(__file__).resolve().parents[2]
# Appended, so these modules can share a test process with tools that have a same-named module.
if str(REPO) not in sys.path:
    sys.path.append(str(REPO))
from tools.itemkit import anim_chain_probe as probe
from tools.phenomorpher.phenomorpher.engine.anim_library import load_model
from tools.phenomorpher.phenomorpher.engine.native_motion import quaternion_matrix, sample, value

# Clips are named <action>_<weapon>_<slot>, as in fire_rfl_dm. Female Large slots add `l`, as in fire_rfl_dfl.
CLIPS = {'custom11lp': 'fire_rfl', 'custom12lp': 'fire_pst', 'custom13lp': 'fire_dpst', 'custom14lp': 'fire_smg',
         'custom15lp': 'fire_dsmg', 'custom17start': 'reload_dual', 'custom18start': 'throw_gren', 'custom19lp': 'fire_sg'}
# Troll bodies use the Gnome part prefix, but the slot is named for the race.
SLOTS = {'hm': 'pmh', 'hf': 'pfh', 'dm': 'pmd', 'df': 'pfd', 'em': 'pme', 'ef': 'pfe', 'om': 'pmo', 'of': 'pfo',
         'tm': 'pmg', 'tf': 'pfg'}
WEAPONS = {'rifle': {'parts': ('wbwxh_t_015.mdl',), 'barrel': (-.33, -.03), 'front': -.25, 'rear': -.19, 'pump': None,
                     'magazine': (0., -.05, -.12)},
           'smg': {'parts': ('wbwsl_m_023.mdl',), 'barrel': (-.32, -.14), 'front': -.10, 'rear': -.07, 'pump': None,
                   'magazine': (0., -.165, -.015)},
           'pistol': {'parts': ('wbwsl_b_051.mdl',), 'barrel': (-.14, -.02), 'front': 0., 'rear': 0., 'pump': None,
                      'fixed': (-.03, 0., .03), 'magazine': (0., -.07, .01)},
           # No shotgun is built yet. The AK-98 stands in for the barrel line and fore-end until one is.
           'shotgun': {'parts': ('wbwxh_t_015.mdl',), 'barrel': (-.33, -.03), 'front': -.30, 'rear': -.24, 'pump': -.18}}
TWO_HANDED = {'custom11lp': 'rifle', 'custom12lp': 'pistol', 'custom14lp': 'smg', 'custom19lp': 'shotgun'}
DUAL = {'custom13lp': 'pistol', 'custom15lp': 'smg'}
RELOADS = ('custom17start',)
# Crossbow-class weapons get their own ready stance, built from the shot clip's rest pose. Leave `xbowr` alone: mapping
# it folds the right forearm back over the shoulder for as long as the weapon is in combat.
READY = {'custom11lp': 'ready_rfl', 'custom19lp': 'ready_sg'}
# The engine fires on the stock clip's `hit` (0.5 s in `throwr` and `xbowshot`), not on ours. These clips kick at
# 0.13 s, so their loop is turned later to kick at 0.5 s. Ready stances still come from the unshifted first pose.
RECOIL_DELAY = {'custom11lp': .37, 'custom19lp': .37}
# Automatic rifle fire, built from the single `fire_rfl` kick: back from 0.125 s, recovered by 0.5 s. Each round's kick
# is squeezed into `span` and played at `scale`, and one kick sits at 0.5 s for the engine's shot. `fire_rfla` is full
# auto at 10 rounds a second and `fire_rflb` a three-round burst. Both loop.
RIFLE_KICK = (.125, .5)
AUTO = {'fire_rfla': {'kicks': tuple(round(.1 * i, 2) for i in range(10)), 'span': .1, 'scale': .35},
        'fire_rflb': {'kicks': (.4, .5, .6), 'span': .1, 'scale': .5}}
# Stock `xbowrdy` breathing and weight shift is laid over the hold on these nodes. The arms ride on the torso.
SWAY = ('pelvis_g', 'torso_g', 'neck_g', 'head_g')
LEGS = (('lthigh_g', 'lshin_g', 'lfoot_g'), ('rthigh_g', 'rshin_g', 'rfoot_g'))
# One reload per magazine position, chosen by weapon. The rifle clip also serves the shotgun until one is built.
RELOAD_VARIANTS = {'reload_rfl': 'rifle', 'reload_smg': 'smg', 'reload_pst': 'pistol'}
# Ranged weapons can't take the off hand, so the pilot copies these guns onto short sword parts for the left hand.
STANDINS = {'srp_dcolt': ('sr_cl36_1', 201, (51, 11, 11)), 'srp_dingr': ('sre9a211be_3', 202, (13, 23, 13))}
ARM = ('lbicep_g', 'lforearm_g', 'lhand_g')
HANDS = {'rhand', 'lhand'}
RIGHT_ARM = ('rbicep_g', 'rforearm_g', 'rhand_g')
CHAIN = ('rootdummy', 'torso_g', *RIGHT_ARM, *ARM)
PALM_CLEARANCE, REACH, MAX_PULL, RELOAD_BLEND = .015, .97, .16, .25
RELOAD_PULL = .30
# When the left palm is on the magazine during the reload: on it, away to the belt from .7 to 1.1, then back on it.
RELOAD_CONTACT = np.array([[0., 1.], [.3, 1.], [.7, 0.], [1.1, 0.], [1.47, 1.], [2., 1.]])
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
            'fixed': spec.get('fixed'), 'magazine': spec.get('magazine'),
            'correction': np.array([[1., 0., 0.], up, -barrel]), 'tiltDegrees': float(np.degrees(np.arctan(-slope)))}


def support_point(marks, z):
    """Palm contact under the fore-end at one distance along the weapon, or the weapon's fixed contact."""
    if marks.get('fixed') is not None:
        return np.array(marks['fixed'])
    fore = marks['verts'][np.abs(marks['verts'][:, 2] - z) < .03]
    return np.array([0., np.percentile(fore[:, 1], 3) - PALM_CLEARANCE, z])


def level_rifle(clip, correction, hand='rhand_g'):
    """Turn a hand so the barrel lies where the old clip aimed its weapon."""
    node = clip['nodes'][hand]
    rows = [axis_row(row[0], quaternion_matrix(quaternions(row[None])[0]) @ correction) for row in node['orientation']]
    return {**clip, 'nodes': {**clip['nodes'], hand: {**node, 'orientation': np.array(rows)}}}


def hold_ends(clip):
    """Start and end a reload raised, so it blends from any stance instead of dropping the arms to the sides."""
    nodes = {}
    for node, keys in clip['nodes'].items():
        rows = keys.get('orientation')
        if rows is not None and len(rows) > 2:
            rows = rows.copy()
            rows[0, 1:], rows[-1, 1:] = rows[1, 1:], rows[-2, 1:]
            keys = {**keys, 'orientation': rows}
        nodes[node] = keys
    return {**clip, 'nodes': nodes, 'transition': RELOAD_BLEND}


def limb_rotations(rig, names, before, after, wrist, hand, parent='torso_g'):
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
    elbow = shoulder + along * axis + np.sqrt(max(0., upper_length ** 2 - along ** 2)) * pole
    upper = rotation_between(before[bicep][:3, :3] @ upper_offset, elbow - shoulder) @ before[bicep][:3, :3]
    lower = rotation_between(before[forearm][:3, :3] @ lower_offset, wrist - elbow) @ before[forearm][:3, :3]
    return after[parent][:3, :3].T @ upper, upper.T @ lower, lower.T @ hand


def arm_length(rig, names):
    return sum(np.linalg.norm(rig[node]['controls'][8]['values'][0]) for node in names[1:])


def contact_weight(time):
    """How far the left palm is drawn onto the magazine at one time in the reload."""
    amount = np.interp(time, RELOAD_CONTACT[:, 0], RELOAD_CONTACT[:, 1])
    return amount * amount * (3 - 2 * amount)


def solve_support(clip, root, marks, magazine=None):
    """Key the arms for one body so the left palm stays on the fore-end, and follows the pump if there is one.

    The palm first slides back along its range. If that isn't enough the weapon is pulled toward the left shoulder.
    With a magazine point the palm goes there instead, leaving for the belt when the old clip's hand does.
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
    weights = np.ones(len(poses))
    if magazine is not None:
        marks = {**marks, 'fixed': magazine}
        weights = contact_weight(np.array(times))
    towards = [after['lbicep_g'][:3, 3] - after['rhand'][:3, 3] for _, _, after in poses]
    trials = ((pull, z) for pull in np.arange(0., (MAX_PULL if magazine is None else RELOAD_PULL) + .001, .01)
              for z in np.arange(marks['front'], marks['rear'] + .001, .01))
    for pull, z in trials:
        start = support_point(marks, z)
        end = support_point(marks, marks['pump']) if marks['pump'] is not None else start
        path = start + phases[:, None] * (end - start)
        shifts = [pull * v / np.linalg.norm(v) for v in towards]
        wrists = []
        for (_, before, after), support, shift, weight in zip(poses, path, shifts, weights):
            rifle = after['rhand']
            hand = rifle[:3, :3] @ before['rhand'][:3, :3].T @ before['lhand_g'][:3, :3]
            wrist = (rifle @ np.r_[support, 1.])[:3] + shift - hand @ palm_offset
            wrists.append((weight * wrist + (1 - weight) * after['lhand_g'][:3, 3], hand))
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
    return {**level, 'nodes': nodes, 'support': (np.array(times), path), 'pull': float(pull), 'weights': weights}


def reload_contact(clip, root):
    """Worst palm distance from the magazine over the keys where the palm should be on it."""
    parents = {name: row['parent'] for name, row in root['nodes'].items()}
    nodes = sampled_nodes(clip, parents)
    times, path = clip['support']
    gaps = []
    for time, point, weight in zip(times, path, clip['weights']):
        if weight == 1:
            pose = sample(root['nodes'], nodes, time)
            gaps.append(float(np.linalg.norm(pose['lhand'][:3, 3] - (pose['rhand'] @ np.r_[point, 1.])[:3])))
    return {'pullMetres': round(clip['pull'], 2), 'contactMetres': round(max(gaps), 4), 'contactKeys': len(gaps), 'keys': len(times)}


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


def delayed(clip, delay):
    """A looping clip turned `delay` seconds later around its loop. Events stay where they are."""
    length, nodes = clip['length'], {}
    for node, keys in clip['nodes'].items():
        moved = {}
        for kind, rows in keys.items():
            rotation = kind == 'orientation'
            source = {'times': rows[:, 0], 'values': quaternions(rows) if rotation else rows[:, 1:4]}
            times = sorted({0., length, *np.round((rows[:, 0] + delay) % length, 6)})
            out = []
            for time in times:
                pose = value(source, (time - delay) % length, rotation)
                out.append(axis_row(time, quaternion_matrix(pose)) if rotation else [time, *pose])
            moved[kind] = np.array(out)
        nodes[node] = moved
    return {**clip, 'nodes': nodes}


def kicked(clip, window, kicks, span, scale):
    """The clip held at the start of `window`, with that window's kick replayed at each of `kicks`.

    Each replay is squeezed into `span` seconds and played at `scale` of its strength. Events stay where they are."""
    start, end = window
    length, nodes = clip['length'], {}
    steps = np.linspace(0, 1, 9)
    times = sorted({0., length, *(round(k + span * f, 6) for k in kicks for f in steps if k + span * f <= length)})
    for node, keys in clip['nodes'].items():
        moved = {}
        for kind, rows in keys.items():
            rotation = kind == 'orientation'
            source = {'times': rows[:, 0], 'values': quaternions(rows) if rotation else rows[:, 1:4]}
            rest = np.asarray(value(source, start, rotation), float)
            out = []
            for time in times:
                active = [k for k in kicks if k <= time <= k + span + 1e-9]
                pose = rest
                if active:
                    kick = value(source, start + (time - active[-1]) / span * (end - start), rotation)
                    kick = np.asarray(kick, float)
                    if rotation and kick @ rest < 0:
                        kick = -kick
                    pose = rest + scale * (kick - rest)
                    if rotation:
                        pose = pose / np.linalg.norm(pose)
                out.append(axis_row(time, quaternion_matrix(pose)) if rotation else [time, *pose])
            out = np.array(out)
            # A node the kick doesn't move needs only its two end keys.
            moved[kind] = out[[0, -1]] if np.allclose(out[:, 1:], out[0, 1:], atol=1e-5) else out
        nodes[node] = moved
    return {**clip, 'nodes': nodes}


def rest_clip(clip):
    """One-second hold of a clip's first pose, with no events."""
    held = {node: {kind: np.array([[0., *rows[0, 1:]], [1., *rows[0, 1:]]]) for kind, rows in keys.items()}
            for node, keys in clip['nodes'].items()}
    return {**clip, 'length': 1., 'transition': .25, 'events': [], 'nodes': held}


def ready_clip(solved, stock, scale):
    """Stance from a solved clip's first pose, moved by the stock stance's change from its own first key."""
    rest = rest_clip(solved)
    nodes = dict(rest['nodes'])
    for node in SWAY:
        rows = stock['nodes'].get(node, {}).get('orientation')
        if rows is None or 'orientation' not in nodes.get(node, {}):
            continue
        base = quaternion_matrix(quaternions(nodes[node]['orientation'][:1])[0])
        first = quaternion_matrix(quaternions(rows[:1])[0]).T
        keyed = [axis_row(row[0], base @ first @ quaternion_matrix(quaternions(row[None])[0])) for row in rows]
        nodes[node] = {**nodes[node], 'orientation': np.array(keyed)}
    moved = stock['nodes']['rootdummy']['position']
    held = nodes['rootdummy']['position'][0, 1:4]
    nodes['rootdummy'] = {**nodes['rootdummy'], 'position': np.array(
        [[row[0], *(held + scale * (row[1:4] - moved[0, 1:4]))] for row in moved])}
    return {**rest, 'nodes': nodes}


def pin_feet(stance, rest, root):
    """Key the legs so the feet stay where the hold put them while the hips move."""
    rig = root['nodes']
    parents = {name: row['parent'] for name, row in rig.items()}
    before = sample(rig, sampled_nodes(rest, parents), 0.)
    moving = sampled_nodes({**stance, 'nodes': {node: keys for node, keys in stance['nodes'].items()
                                                if node not in {name for leg in LEGS for name in leg}}}, parents)
    for leg in LEGS:
        for node in leg:
            if node in rest['nodes']:
                moving[node] = sampled_nodes({**rest, 'nodes': {node: rest['nodes'][node]}}, parents)[node]
    times = sorted({float(t) for node in ('rootdummy', 'pelvis_g') for rows in stance['nodes'].get(node, {}).values()
                    for t in rows[:, 0]})
    nodes = dict(stance['nodes'])
    keys = {node: [] for leg in LEGS for node in leg}
    for time in times:
        after = sample(rig, moving, time)
        for leg in LEGS:
            foot = before[leg[2]]
            for node, local in zip(leg, limb_rotations(rig, leg, before, after, foot[:3, 3], foot[:3, :3], parents[leg[0]])):
                keys[node].append(axis_row(time, local))
    for node, rows in keys.items():
        nodes[node] = {**nodes.get(node, {}), 'orientation': np.array(rows)}
    return {**stance, 'nodes': nodes}


def foot_drift(clip, root):
    """Largest travel of either foot over a stance, in metres."""
    parents = {name: row['parent'] for name, row in root['nodes'].items()}
    nodes = sampled_nodes(clip, parents)
    poses = [sample(root['nodes'], nodes, time) for time in np.linspace(0., clip['length'], 21)]
    return round(max(float(np.ptp([pose[foot][:3, 3] for pose in poses], axis=0).max()) for foot in ('lfoot_g', 'rfoot_g')), 3)


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


def ready_blocks(name, slot, suffix, solved, tree, stock, scale, drifts, root):
    """The `xbowrdy` stance clip for one solved crossbow-class clip, or none for other weapons."""
    if name not in READY:
        return []
    code = READY[name]
    stance = pin_feet(ready_clip(solved, stock, scale), rest_clip(solved), root)
    drifts[f'{code}_{slot}{suffix}'] = foot_drift(stance, root)
    return [clip_text(f'{code}_{slot}{suffix}', 'a_ba_custom', stance, tree)]


def stage_animation(hak, stock_dir, source_dir, body, weapons, stance):
    custom = (stock_dir / 'a_ba_custom.mdl').read_text(encoding='cp1252')
    tree = probe.stock_clip_tree(custom, 'a_ba_custom')
    names = {name.lower() for _, name, _ in tree}
    blocks, records, drifts = [], [], {}
    sources = {sex: (source_dir / (f + '.mdl')).read_text(encoding='cp1252') for sex, (f, _) in SOURCES.items()}
    for slot, prefix in SLOTS.items():
        sex = slot[1]
        stock_bind = load_model(body / f'p{sex}h0.mdl')['nodes']['rootdummy']['controls'][8]['values'][0]
        roots = [load_model(body / f'{prefix}{pheno}.mdl') for pheno in (0, 2)]
        binds = [root['nodes']['rootdummy']['controls'][8]['values'][0] for root in roots]
        for code, weapon in RELOAD_VARIANTS.items():
            for root, bind, suffix in ((roots[0], binds[0], ''), *(((roots[1], binds[1], 'l'),) if sex == 'f' else ())):
                raw, dropped = retarget(read_clip(sources[sex], 'custom16start'), names, stock_bind, bind)
                marks = weapons[weapon]
                solved = solve_support(hold_ends(raw), root, marks, np.array(marks['magazine']))
                label = f'{code}_{slot}{suffix}'
                blocks.append(clip_text(label, 'a_ba_custom', solved, tree))
                records.append({'slot': slot, 'clip': label, 'source': 'custom16start', 'droppedNodes': dropped,
                                'large' if suffix else 'fit': reload_contact(solved, root)})
                if sex == 'm':
                    records[-1]['large'] = reload_contact(solved, roots[1])
        for name, code in CLIPS.items():
            raw, dropped = retarget(read_clip(sources[sex], name), names, stock_bind, binds[0])
            label = f'{code}_{slot}'
            row = {'slot': slot, 'clip': label, 'source': name, 'droppedNodes': dropped}
            if name in RELOADS:
                correction = weapons['pistol']['correction']
                raw = level_rifle(level_rifle(hold_ends(raw), correction), correction, 'lhand_g')
            if name in DUAL:
                correction = weapons[DUAL[name]]['correction']
                raw = level_rifle(level_rifle(raw, correction), correction, 'lhand_g')
            if name not in TWO_HANDED:
                blocks.append(clip_text(label, 'a_ba_custom', raw, tree))
                row['handGapMetres'] = {'fit': hand_gap(roots[0], raw), 'large': hand_gap(roots[1], raw)}
                records.append(row)
                continue
            marks = weapons[TWO_HANDED[name]]
            solved = solve_support(raw, roots[0], marks)
            delay = RECOIL_DELAY.get(name)
            blocks.append(clip_text(label, 'a_ba_custom', delayed(solved, delay) if delay else solved, tree))
            if code == 'fire_rfl':
                blocks += [clip_text(f'{auto}_{slot}', 'a_ba_custom', kicked(solved, RIFLE_KICK, **spec), tree)
                           for auto, spec in AUTO.items()]
            blocks += ready_blocks(name, slot, '', solved, tree, stance, binds[0][2] / stock_bind[2], drifts, roots[0])
            row['fit'] = fit_errors(solved, raw, roots[0], marks)
            if sex == 'f':
                wide, _ = retarget(read_clip(sources[sex], name), names, stock_bind, binds[1])
                large = solve_support(wide, roots[1], marks)
                blocks.append(clip_text(label + 'l', 'a_ba_custom', delayed(large, delay) if delay else large, tree))
                if code == 'fire_rfl':
                    blocks += [clip_text(f'{auto}_{slot}l', 'a_ba_custom', kicked(large, RIFLE_KICK, **spec), tree)
                               for auto, spec in AUTO.items()]
                blocks += ready_blocks(name, slot, 'l', large, tree, stance, binds[1][2] / stock_bind[2], drifts, roots[1])
                row['large'] = fit_errors(large, wide, roots[1], marks)
            else:
                row['large'] = fit_errors(solved, raw, roots[1], marks)
            records.append(row)
    closing = 'donemodel a_ba_custom'
    if custom.count(closing) != 1:
        raise ValueError('Unexpected stock a_ba_custom shape')
    (hak / 'a_ba_custom.mdl').write_text(custom.replace(closing, ''.join(blocks) + closing), encoding='cp1252', newline='\n')
    return records, drifts


PHASES = r'''
string SlotOf(object a){
 int t=GetAppearanceType(a);string race="h";if(t==15101)race="d";if(t==15102)race="e";if(t==15103)race="o";if(t==15104)race="t";
 return race+(GetGender(a)==GENDER_FEMALE?"f":"m");}
string ClipSlot(object a,string code){
 int shared=code=="fire_dpst"||code=="fire_dsmg"||code=="reload_dual"||code=="throw_gren";
 string large=!shared&&GetGender(a)==GENDER_FEMALE&&GetPhenoType(a)==2?"l":"";
 return SlotOf(a)+large;}
void Map(object a,string stock,string code){
 ReplaceObjectAnimation(a,stock,code+"_"+ClipSlot(a,code));}
string ReloadCode(object a){
 object gun=GetItemInSlot(INVENTORY_SLOT_RIGHTHAND,a);
 if(GetBaseItemType(gun)!=BASE_ITEM_SLING)return "reload_rfl";
 return GetTag(gun)=="sr_cl36_1"||GetTag(gun)=="sr_cl36_2"?"reload_pst":"reload_smg";}
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
void LogDual(){
 object a=GetObjectByTag("SRP_A",0);
 SrpLog("dual "+GetName(a)+" right="+GetTag(GetItemInSlot(INVENTORY_SLOT_RIGHTHAND,a))+" left="+GetTag(GetItemInSlot(INVENTORY_SLOT_LEFTHAND,a)));}
void Attack(string shot,string code,string text){
 LogAmmo(text);DelayCommand(10.0,LogAmmo(text));
 object target=GetObjectByTag("SRP_T");
 int n=0;object a=GetObjectByTag("SRP_A",n);
 while(GetIsObjectValid(a)){
  ReplaceObjectAnimation(a,"pause1","");ReplaceObjectAnimation(a,"pause2","");
  Map(a,shot,code);
  AssignCommand(a,ClearAllActions(TRUE));AssignCommand(a,ActionAttack(target));
  a=GetObjectByTag("SRP_A",++n);}
 Say(text);SrpLog("phase "+text);}
void Hold(string code){
 int n=0;object a=GetObjectByTag("SRP_A",n);
 while(GetIsObjectValid(a)){
  string clip=code+"_"+ClipSlot(a,code);
  ReplaceObjectAnimation(a,"bowrdy",clip);ReplaceObjectAnimation(a,"bow",clip);
  ReplaceObjectAnimation(a,"1hreadyr",clip);ReplaceObjectAnimation(a,"1hreadyl",clip);
  ReplaceObjectAnimation(a,"nwreadyr",clip);ReplaceObjectAnimation(a,"nwreadyl",clip);
  a=GetObjectByTag("SRP_A",++n);}}
void Ready(string code){
 int n=0;object a=GetObjectByTag("SRP_A",n);
 while(GetIsObjectValid(a)){
  ReplaceObjectAnimation(a,"xbowrdy",code==""?"":code+"_"+ClipSlot(a,code));
  a=GetObjectByTag("SRP_A",++n);}
 Say("ready "+code);}
void Probe(int left){
 object m=GetModule();int now=GetMicrosecondCounter();int last=GetLocalInt(m,"P_L");
 if(last&&now-last>GetLocalInt(m,"P_M"))SetLocalInt(m,"P_M",now-last);
 SetLocalInt(m,"P_L",now);
 if(left>0)DelayCommand(0.05,Probe(left-1));
 else SrpLog("hitch maxms="+IntToString(GetLocalInt(m,"P_M")/1000));}
void Reload(string code,int constant,float length,float speed,int resume){
 object target=GetObjectByTag("SRP_T");
 int n=0;object a=GetObjectByTag("SRP_A",n);
 while(GetIsObjectValid(a)){
  string stock=constant==ANIMATION_LOOPING_CUSTOM16?"custom16lp":"custom17lp";
  Map(a,stock,code==""?ReloadCode(a):code);
  AssignCommand(a,ClearAllActions(TRUE));
  AssignCommand(a,ActionPlayAnimation(constant,speed,length/speed));
  if(resume)AssignCommand(a,ActionAttack(target));
  a=GetObjectByTag("SRP_A",++n);}
 Say("reload "+code+" speed "+FloatToString(speed,3,2));SrpLog("reload "+code+" speed "+FloatToString(speed,3,2));}
void ArmDual(string right_ref,string left_ref,string ammo){
 int n=0;object a=GetObjectByTag("SRP_A",n);
 while(GetIsObjectValid(a)){
  object shots=CreateItemOnObject(ammo,a,99);
  object right=CreateItemOnObject(right_ref,a);object left=CreateItemOnObject(left_ref,a);
  AssignCommand(a,ClearAllActions(TRUE));
  AssignCommand(a,ActionEquipItem(shots,INVENTORY_SLOT_BULLETS));
  AssignCommand(a,ActionEquipItem(right,INVENTORY_SLOT_RIGHTHAND));
  AssignCommand(a,ActionEquipItem(left,INVENTORY_SLOT_LEFTHAND));
  a=GetObjectByTag("SRP_A",++n);}
 DelayCommand(4.0,LogDual());}
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
 DelayCommand(3.0,Show(15104,"Troll"));
 Probe(300);
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
 if(text=="hold")Ready("ready_rfl");
 else if(text=="holdsmg")Hold("fire_smg");
 else if(text=="holdshot")Ready("ready_sg");
 else if(text=="holdp")Hold("fire_pst");
 else if(text=="rdstock")Ready("");
 else if(text=="ingram")ArmWith("sre9a211be_3","nw_wambu001",INVENTORY_SLOT_BULLETS);
 else if(text=="fingram")Attack("throwr","fire_smg","attack throwr ingram");
 else if(text=="side")Camera(pc,0.0,5.0,80.0);
 else if(text=="dpistol")ArmDual("sr_cl36_1","srp_dcolt","nw_wambu001");
 else if(text=="dsmg")ArmDual("sre9a211be_3","srp_dingr","nw_wambu001");
 else if(text=="spistol")ArmDual("srp_dcolt","srp_dcolt","nw_wambu001");
 else if(text=="ssmg")ArmDual("srp_dingr","srp_dingr","nw_wambu001");
 else if(text=="lpdual")Clips("custom13lp","fire_dpst",ANIMATION_LOOPING_CUSTOM13,"dual pistol loop");
 else if(text=="lsdual")Clips("custom15lp","fire_dsmg",ANIMATION_LOOPING_CUSTOM15,"dual smg loop");
 else if(text=="fdpistol")Attack("throwr","fire_dpst","attack throwr dual pistol");
 else if(text=="fdsmg")Attack("throwr","fire_dsmg","attack throwr dual smg");
 else if(GetStringLeft(text,3)=="rl ")Reload("",ANIMATION_LOOPING_CUSTOM16,2.0,StringToFloat(GetSubString(text,3,6)),FALSE);
 else if(GetStringLeft(text,3)=="rf ")Reload("",ANIMATION_LOOPING_CUSTOM16,2.0,StringToFloat(GetSubString(text,3,6)),TRUE);
 else if(GetStringLeft(text,3)=="rd ")Reload("reload_dual",ANIMATION_LOOPING_CUSTOM17,4.0,StringToFloat(GetSubString(text,3,6)),FALSE);
 else if(text=="frifle")Attack("xbowshot","fire_rfl","attack xbowshot rifle");
 else if(text=="fproof")Attack("xbowshot","throw_gren","attack proof grenade on xbowshot");
 else if(text=="fshot")Attack("xbowshot","fire_sg","attack xbowshot shotgun");
 else if(text=="fsmg")Attack("xbowshot","fire_smg","attack xbowshot smg no hit event");
 else if(text=="fpistol")Attack("throwr","fire_pst","attack throwr pistol");
 else if(text=="pistol")ArmWith("sr_cl36_1","nw_wambu001",INVENTORY_SLOT_BULLETS);
 else if(text=="rifle")Clips("custom11lp","fire_rfl",ANIMATION_LOOPING_CUSTOM11,"rifle");
 else if(text=="shot")Clips("custom19lp","fire_sg",ANIMATION_LOOPING_CUSTOM19,"shotgun");
 else if(text=="reloadl")Clips("custom16lp","reload_rfl",ANIMATION_LOOPING_CUSTOM16,"reload as lp");
 else if(text=="grenl")Clips("custom18lp","throw_gren",ANIMATION_LOOPING_CUSTOM18,"grenade as lp");
 else if(text=="off")Idle("","stock idle");
 else if(text=="human")Show(15100,"Human");
 else if(text=="dwarf")Show(15101,"Dwarf");
 else if(text=="elf")Show(15102,"Elf");
 else if(text=="orc")Show(15103,"Orc");
 else if(text=="troll")Show(15104,"Troll");
 else if(text=="wide")Move(pc,15.7,20.0,22.0,58.0);
 else if(text=="low")Move(pc,15.7,11.0,14.0,80.0);
 else if(GetStringLeft(text,3)=="at "){
  int col=StringToInt(GetSubString(text,3,1));int row=StringToInt(GetSubString(text,5,1));
  Move(pc,5.0+6.0*IntToFloat(col)+1.2*IntToFloat(row),15.0+4.5*IntToFloat(row),7.0,72.0);}
 else return;
 SetPCChatMessage("");}
'''


def stage_standins(hak):
    """Copy each dual gun's parts to a short sword part number, so a blueprint can put it in the left hand."""
    for _, number, parts in STANDINS.values():
        for letter, part in zip('bmt', parts):
            old, new = f'wbwsl_{letter}_{part:03}', f'wswss_{letter}_{number:03}'
            (hak / (new + '.mdl')).write_bytes((REPO / 'srn_weapon' / (old + '.mdl')).read_bytes().replace(old.encode(), new.encode()))


def build(output, source_dir, game_root, tool_dir, game_userdir, client, extend=None):
    """extend(hak, stock_dir, scripts), if given, adds to the staged hak and the module scripts."""
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
    (stock_dir / 'a_ba.bin').write_bytes(tools.stock('a_ba.mdl', game_userdir))
    subprocess.run([str(REPO / 'tools/vendor/nwnmdlcomp/nwnmdlcomp.exe'), '-d', '-e', str(stock_dir / 'a_ba.bin'),
                    str(stock_dir / 'a_ba.mdl')], check=True, capture_output=True, timeout=120)
    stance = read_clip((stock_dir / 'a_ba.mdl').read_text(encoding='cp1252'), 'xbowrdy')
    records, drifts = stage_animation(hak, stock_dir, Path(source_dir), REPO / 'srn_body', weapons, stance)
    stage_standins(hak)
    hak_order = [probe.HAK, 'sw_reviewenv', 'srn_weapon', 'srn_armor', 'srn_body_tex', 'srn_body', 'srn_2da']
    scripts = {'srp_inc': probe.SCRIPTS['srp_inc'] + PHASES, 'srp_enter': ENTER, 'srp_chat': CHAT}
    if extend:
        extend(hak, stock_dir, scripts)
    probe.stage_module(stage, tools, REPO / 'test-modules/weapon-waves/module', game_userdir, hak_order, scripts)

    def target(data):
        data['TemplateResRef']['value'] = 'srp_tgt'
        data['Tag']['value'] = 'SRP_T'
        for key in data:
            if key.startswith('Script'):
                data[key]['value'] = ''

    tools.gff(REPO / 'test-modules/weapon-waves/module/sr_it_target.utc', stage / 'srp_tgt.utc', target)
    for resref, (gun, number, _) in STANDINS.items():
        def left_hand(data, resref=resref, number=number):
            data['TemplateResRef']['value'] = resref
            data['Tag']['value'] = resref
            data['BaseItem']['value'] = 0
            data['PropertiesList']['value'] = []
            for part in (1, 2, 3):
                data[f'ModelPart{part}']['value'] = number
        tools.gff(REPO / 'srn_weapon' / (gun + '.uti'), stage / (resref + '.uti'), left_hand)
    tools.run('nwn_erf', '-c', '-e', 'HAK', '-f', user / 'hak' / (probe.HAK + '.hak'), hak)
    for name, folder in (('sw_reviewenv', REPO / 'test-modules/weapon-waves/haks/sw_reviewenv'),
                         *((n, REPO / n) for n in hak_order[2:])):
        tools.run('nwn_erf', '-c', '-e', 'HAK', '-f', user / 'hak' / (name + '.hak'), folder)
    module = user / 'modules' / (probe.MODULE + '.mod')
    tools.run('nwn_erf', '-c', '-e', 'MOD', '-f', module, stage)
    sys.path[:0] = [str(REPO / 'tools/heads'), str(REPO / 'tools/phenotypes')]
    from build_head_trial import launch_scripts
    cmd, ps1 = launch_scripts(probe.MODULE, client)
    (output / 'Launch.cmd').write_bytes(cmd.encode('ascii'))
    (output / 'Launch.ps1').write_bytes(ps1.encode('utf-8'))
    files = [{'relativePath': f'userdir/hak/{n}.hak', 'sha256': probe.sha(user / 'hak' / (n + '.hak'))} for n in hak_order]
    files.append({'relativePath': f'userdir/modules/{probe.MODULE}.mod', 'sha256': probe.sha(module)})
    manifest = {'kind': 'combat-clip-pilot', 'files': files, 'clips': records, 'readyFootDriftMetres': drifts,
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
