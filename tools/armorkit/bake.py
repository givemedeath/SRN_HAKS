"""One generated outfit baked into the parts a body wears: fitted, split, laid out, coloured, tinted and written.

The stages are the kit's own (`repose`, `split`, `texture`, `export`). This module is the order they run in, and
what each face the split made is drawn as (`roles`): which are a closing's, a cap's, a pad's, which are shaded as
the cloth round them, and which lie in an armhole's shadow. Those choices were made on the first worn outfit,
siteguard-male, in the game client (docs/armorkit/pilot-corpsec.md), and the functions that carry them out only
say what "the caller" flags; this is that caller.

`bake` reads the generated colours and relief into every part, which takes minutes; `store` and `stored` keep its
result, so `tints` and `write` can be run again on it. `gates` checks what was written. `bake` can also keep what it
gives the split (`keep_split`), so that the split alone runs again on it in seconds with the code as it stands
(`resplit`), for work on the cut.
"""
import functools
import json
import shutil
import time
from pathlib import Path

import numpy as np

from tools.headkit import gltf
from tools.robes import mesh_ops

from . import bodyskin, brief, export, measure, reduce, registry, repose, seams, split, texture
from . import ends as shaping  # `ends` here is the seam gate
from .registry import require

ADDED = (split.CLOSING, split.CAP, split.WALL, split.PADDED)  # what the split made: it has no surface of its own on the generated outfit
DOMED = (split.CAP, split.PADDED)  # of those, what rounds a surface on past its edge and is not creased there (`export.added_normals`)
UNDER = {'legl': (split.CAP, split.WALL), 'legr': (split.CAP, split.WALL), 'pelvis': (split.CLOSING,),
         'chest': (split.CLOSING,), 'handl': (split.CAP,), 'handr': (split.CAP,)}  # shaded as the cloth round them (`texture.under`)
ARMHOLE = ('bicepl', 'bicepr')  # the parts closed at a shoulder: their closings lie in the armhole's shadow
SLOTS = ('chest', 'pelvis', 'shoulder', 'bicep', 'forearm', 'hand', 'thigh', 'shin', 'foot')  # the slots a generated outfit fills
BUDGET = {'chest': 8000, 'slot': 2900, 'outfit': 40000, 'texture': 1024}  # triangles a chest, another part and a whole outfit may have; texels a side
# (user decision 2026-11-13: the outfit raised from 30,000 to 40,000 for rounded ends; a chest and eleven parts at
# their budgets come to 39,900)
END_BAND = 0.02  # metres: a part over its budget keeps every vertex this near a joint's plane, where its end is measured
SKIN_ROUNDS = 3  # a part sharing its slot with the body's skin is reduced again at most this often, as the skin beside it is counted anew
WHOLE = 'no holes or detached pieces'  # the gate `surface` answers, on the generated outfit as the bake is given it
SEAM = 'seam contract: each end against its tier\'s overlap and envelope'  # the gate `ends` answers, on a body the contract measured
HIDDEN = 'seam contract: every end closed and domed, what closes it hidden at rest and in the design bend'  # the gate `hidden` answers
NOT_BUILT = (SEAM, HIDDEN, 'clearance: no body surface showing at rest',
             WHOLE)  # gates of docs/armorkit/plan.md that `gates` does not check: WHOLE but on a fresh bake, SEAM and HIDDEN but on a measured body
UNCUT = {('neck', 'c')}  # the joints the bake leaves whole (`cut`): the neck stays on the chest as its collar
ON_PLANE = 1e-4  # metres: a point this near a joint's plane lies on it, wherever the reduction moved it along the plane
OPEN_LEAST = 0.01  # metres: a part is open on a plane when this much edge or more lies there on one face only. Less is a
# slit where a closing along another cut meets the plane: 6 mm of the chest of Facility Security female at the waist, under its hem
DOME_SLACK = 0.001  # metres: a dome may stand this much farther past its rim than the contract's `domeMost`
HIDDEN_STEP = 0.003  # a surface is sampled this densely to tell how far a point stands outside it
HIDDEN_NEAR = 0.05  # and only within this of the points measured
HINGES = {'elbow': 1.0, 'knee': -1.0}  # the way along body +Y a hinge's under part swings (`hidden`): a forearm forward, a shin back
THROUGH = 0.001  # metres: the body's own skin kept beside the outfit may stand this far out through it, no farther (`through`)
INSIDE = 0.005  # an over end is measured this far inside its joint plane, clear of the cut that made it
REACH = 2.0  # a part's section at a joint counts this many of the heaviest tier's widest envelope radius from the centre, no farther
STEP = 0.003  # an under end's surface is sampled this densely to tell how far past its plane it runs
AXIS = 0.015  # past the plane, what lies this near the joint's axis closes the end in every direction: a cap's pole
ROOM_SLACK = 0.005  # at a torso opening an end may stop this much shorter of the torso over its joint than the split stops it:
# the split reads the torso before its lids, layout and reduction
HOLE = 0.005  # an opening of the generated outfit this long round or longer, at the body's size, is a hole
DEBRIS = 0.001  # square metres: a separate piece of the generated outfit smaller than this that touches nothing else is debris
TOUCH = 0.002  # a piece of the generated outfit this near the rest of it touches it
POINT = split.POINT  # metres: two corners of a triangle this near are one point, and the model compiler drops the triangle
KEYS = ('v', 'f', 'uv', 'n', 'rgb', 'covered', 'relief', 'closing', 'cap', 'padded', 'added', 'domed', 'src', 'trimmed')  # what `store` keeps of a part
OPTIONAL = ('pad',)  # and what it keeps when a part has it: parts kept before it existed have none
KEPT, KEPT_KIND = 'baked.json', 'srn-armorkit-baked-parts'  # the list of the parts `store` kept, and its kind
SPLIT_KIND = 'srn-armorkit-split-inputs'  # what `keep_split` writes: what a bake gave the split
WORN_KIND = 'srn-armorkit-split-parts'  # what `keep_parts` writes: the parts the split made, unbaked


def roles(name, made):
    """What the faces of part `name` are drawn as, from what made each (`split.split`, `made`): flags per face.

    `added` are the faces the split made, `domed` those of them that are not creased at their rim. Of the
    added faces, `under` are shaded as the cloth they lie under, vertex by vertex (`texture.under`): a
    thigh's cap and its wall toward the other leg, the pelvis's lids, of which a stride shows a hand's
    breadth, and the chest's closings round each arm, which a lifted arm shows: drawn from their rims, they
    were fans of streaks in the pad's and the sleeve's colours (the Site Guard with its arms up, in the
    client). So is a glove's cap, which a bare forearm shows at the cuff and a bent wrist shows more of:
    drawn flat, it was a pale band round the wrist (Facility Security, in the client). `closing`, `cap` and `padded` are `texture.tint_maps`' flags of the same names for the rest: a
    thigh's wall goes with its cap where it is not `under`.

    An upper arm's cap is none of these and is drawn as it was read, its rim's colours carried to its pole.
    That is how siteguard-male was baked when its armpits were looked at in the client, and it was not what
    was meant: the cap was to be flagged as a closing and darkened with the closings (`ARMHOLE`), and a later
    line of the bake script took it out of them again. The closings alone, darkened, turned the pale strip in
    front of the armpit into a crease, so this is kept as it was seen until the other is tried in the client."""
    made = np.asarray(made, int)
    under = UNDER.get(name, ())
    flat = [kind for kind in (split.CAP, split.WALL, split.PADDED) if kind not in under and not (kind == split.CAP and name in ARMHOLE)]
    return {'added': np.isin(made, ADDED), 'domed': np.isin(made, DOMED), 'under': np.isin(made, under),
            'closing': (made == split.CLOSING) & (split.CLOSING not in under), 'cap': np.isin(made, flat), 'padded': made == split.PADDED}


def to_field(points):
    """Points in the bodies' axes, back in the generated mesh's (`repose.load` turns them the other way)."""
    points = np.asarray(points, float)
    return np.stack([-points[:, 0], points[:, 2], points[:, 1]], axis=1)


def surface(vertices, faces):
    """What the generated outfit, at the body's size, holds of holes and detached pieces: {`holes`: the length
    round each opening of `HOLE` or more, longest first; `debris`: the area of each separate piece smaller than
    `DEBRIS` that stands farther than `TOUCH` from the rest, largest first; `pieces`: how many separate pieces
    it is}. Vertices at one position are one point.

    It is measured on the outfit as it was generated, before it is cut: every opening the cut leaves is made
    on purpose, an over part open on its joint plane with the under part standing in it. A generated outfit is
    one closed surface: the Site Guard's first exports had openings up to 9 cm round and dozens of pieces, and
    the one worn has none. A separate piece is not a fault in itself (knee pads 0.6 cm off the trousers, the
    gloves beyond a bare forearm); a small one standing off the rest is: a crumb of 2 to 6 cm² floated in four
    exports of seven, three times in one place by a thigh."""
    vertices, faces = np.asarray(vertices, float), np.asarray(faces, int)
    weld = mesh_ops.weld_ids(vertices, split.WELD)
    edges = np.sort(np.concatenate([weld[faces][:, [0, 1]], weld[faces][:, [1, 2]], weld[faces][:, [2, 0]]]), axis=1)
    edges = edges[edges[:, 0] != edges[:, 1]]
    found, count = np.unique(edges, axis=0, return_counts=True)
    rim = found[count == 1]
    holes = []
    if len(rim):
        at = np.zeros(weld.max() + 1, int)
        at[weld] = np.arange(len(vertices))
        loop = np.asarray(mesh_ops.union_find(int(weld.max()) + 1, rim.tolist()))[rim[:, 0]]
        length = np.linalg.norm(vertices[at[rim[:, 0]]] - vertices[at[rim[:, 1]]], axis=1)
        holes = sorted((float(length[loop == label].sum()) for label in np.unique(loop)), reverse=True)
    piece = np.asarray(mesh_ops.union_find(len(faces), split.beside(vertices, faces).tolist()))
    corners = vertices[faces]
    area = np.linalg.norm(np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0]), axis=1) / 2
    labels, of = np.unique(piece, return_inverse=True)
    sizes = np.bincount(of.reshape(-1), weights=area)
    debris = []

    def sampled(chosen):  # points on the chosen faces no more than `TOUCH` apart
        used, inside = np.unique(faces[chosen], return_inverse=True)
        return measure.surface_points(vertices[used], inside.reshape(-1, 3), TOUCH)

    for label in np.flatnonzero(sizes < DEBRIS):
        mine = of.reshape(-1) == label
        points = sampled(mine)
        low, high = points.min(axis=0) - 2 * TOUCH, points.max(axis=0) + 2 * TOUCH
        near = ~mine & (corners.max(axis=1) >= low).all(axis=1) & (corners.min(axis=1) <= high).all(axis=1)  # the rest's faces round it
        if near.any() and texture.nearest(points, sampled(near), rows=32)[1].min() <= TOUCH:
            continue
        debris.append(float(sizes[label]))
    return {'holes': [hole for hole in holes if hole >= HOLE], 'debris': sorted(debris, reverse=True), 'pieces': int(len(labels))}


def ends(parts, bones, body, tier, contract=None):
    """How each end of a baked outfit meets the seam contract (docs/armorkit/seam-contract.md) at tier `tier` on
    body `body`: (report, failures), or None when the contract has no rings of that body.

    At each joint plane, for the parts of both its slots: the under end's section at the plane must lie inside
    the tier's envelope in all 16 directions, the envelope read straight from one direction's radius to the next
    (`seams.standoff`), and in each direction it is found in the end must run past the
    plane, into the over part, by the tier's minimum overlap; the over end's section `INSIDE` short of the
    plane must stand at least as far out as the envelope in each direction it is found in, which also tells it
    is open. The chest at the neck and shoulders and the pelvis at the hips are not measured: the plane cuts the
    torso wall there, not a tube (`measure.TORSO_OPENINGS`), and an under end there is asked to run into the
    torso no deeper than the torso first crosses the joint's axis, less `split.SEAT_GAP` and `ROOM_SLACK`
    (`split.room`): the Human female's shoulder stands less far over her shoulder joint than the contract's
    overlap, even bare. A part with no face at its plane does not reach
    its joint and fails, unless it shares its slot with the body's skin: the body's own part ends there then.
    Only the outfit's faces are measured, never the body's skin beside them.

    The report holds per joint and side the part at each end, the tier it meets (the least an under end fits,
    the greatest an over end opens to; None for none), and in metres how far the under end stands outside
    the envelope at most (`outside`, negative inside) and runs past the plane at least (`past`, against
    `overlap`), and how far the over end stands inside it at most (`inside`, negative outside)."""
    contract = seams.load_contract() if contract is None else contract
    if any(body not in contract['joints'][joint]['bodies'] for joint in seams.JOINTS):
        return None
    report, failures = {}, []
    for joint, spec in seams.JOINTS.items():
        report[joint] = {}
        for side in seams.sides(joint):
            letter, paired = ('l', None) if side == 'c' else (side, side)
            point, normal = seams.plane(bones, joint, letter)
            envelope = {t: np.array(seams.envelope(contract, joint, body, t, paired)) for t in registry.TIERS}
            offset = {t: contract['tierOffsets'][str(t)] for t in registry.TIERS}
            ring = envelope[0] - offset[0]
            overlap = {t: seams.overlap(contract, joint, body, t) for t in registry.TIERS}
            limit = REACH * envelope[registry.TIERS[-1]].max()
            row = {}
            under, over = (split.token(spec[key], letter) for key in ('under', 'over'))
            deepest = split.room(*_outfit(parts[over])[:2], point, normal) if joint in measure.TORSO_OPENINGS and over in parts else None
            if deepest is not None:  # an end runs into a torso no deeper than the torso stands over the joint (`split.seat_end`)
                overlap = {t: min(depth, deepest - split.SEAT_GAP - ROOM_SLACK) for t, depth in overlap.items()}
            if under in parts:
                vertices, faces, shared = _outfit(parts[under])
                widest = seams.standoff(seams.section(vertices, faces, point, normal), ring, limit=limit)[0]
                found = ~np.isnan(widest)
                if found.any():
                    past = _past(*_outfit(parts[under], pads=True)[:2], point, normal, limit)[found]  # a pad's cap runs past the plane too
                    fits = [t for t in registry.TIERS if (widest[found] <= offset[t]).all() and (past >= overlap[t]).all()]
                    outside = widest[found] - offset[tier]
                    row['under'] = {'part': under, 'tier': fits[0] if fits else None, 'outside': round(float(outside.max()), 4),
                                    'past': round(float(past.min()), 4), 'overlap': round(float(overlap[tier]), 4)}
                    if (outside > 0).any():
                        failures.append(f'{under} at the {joint}: up to {outside.max() * 100:.1f} cm outside the tier {tier} envelope, '
                                        f'in {int((outside > 0).sum())} of {seams.DIRECTIONS} directions')
                    if (past < overlap[tier]).any():
                        failures.append(f'{under} at the {joint}: {past.min() * 100:.1f} cm past the plane, short of the tier {tier} '
                                        f'overlap of {overlap[tier] * 100:.1f} cm')
                elif not shared:
                    row['under'] = {'part': under, 'tier': None}
                    failures.append(f'{under} does not reach the {joint} plane')
            if over in parts and joint not in measure.TORSO_OPENINGS:
                vertices, faces, shared = _outfit(parts[over], own=True)
                nearest = seams.standoff(seams.section(vertices, faces, point - INSIDE * normal, normal), ring, limit=limit)[1]
                found = ~np.isnan(nearest)
                if found.any():
                    opens = [t for t in registry.TIERS if (nearest[found] >= offset[t]).all()]
                    inside = offset[tier] - nearest[found]
                    row['over'] = {'part': over, 'tier': opens[-1] if opens else None, 'inside': round(float(inside.max()), 4)}
                    if (inside > 0).any():
                        failures.append(f'{over} at the {joint}: up to {inside.max() * 100:.1f} cm inside the tier {tier} envelope, '
                                        f'in {int((inside > 0).sum())} of {seams.DIRECTIONS} directions')
                elif not shared:
                    row['over'] = {'part': over, 'tier': None}
                    failures.append(f'{over} does not reach the {joint} plane')
            report[joint][side] = row
    return report, failures


def _collapsed(vertices, faces):
    """How many of the triangles `faces` have two corners within `POINT` of each other."""
    vertices, faces = np.asarray(vertices, float), np.asarray(faces, int).reshape(-1, 3)
    sides = [np.linalg.norm(vertices[faces[:, i]] - vertices[faces[:, (i + 1) % 3]], axis=1) for i in range(3)]
    return int((np.min(sides, axis=0) < POINT).sum()) if len(faces) else 0


def _outfit(part, pads=False, own=False):
    """(vertices, faces, shared) of the outfit's faces of a part: the body's skin beside them left out, and with
    `pads` false a pad over the joint (`pad`) too; with `own`, what the split added as well (`added`): an over
    end is its own surface, and the dome on from its rim (`split.lid`) is none of it."""
    keep = np.ones(len(part['f']), bool)
    for key in ('skin',) + (() if pads else ('pad',)) + (('added',) if own else ()):
        if key in part:
            keep &= ~np.asarray(part[key], bool)
    return part['v'], part['f'][keep], 'skin' in part


def _past(vertices, faces, point, normal, limit):
    """Per direction about a joint, how far a part runs past the plane against its normal, within `limit` of the centre.
    What lies within `AXIS` of the axis counts in every direction: a cap closes on one pole there, and the faces
    round it fall in whichever direction their points happen to lie."""
    height = (np.asarray(vertices, float) - point) @ normal
    faces = faces[height[faces].min(axis=1) < 0]
    depth = np.zeros(seams.DIRECTIONS)
    if not len(faces):
        return depth
    used, inside = np.unique(faces, return_inverse=True)
    points = measure.surface_points(np.asarray(vertices, float)[used], inside.reshape(-1, 3), STEP) - point
    height = points @ normal
    u, v = seams.frame(normal)
    flat = np.stack([points @ u, points @ v], axis=1)
    radius = np.linalg.norm(flat, axis=1)
    keep = (height < 0) & (radius <= limit)
    np.maximum.at(depth, seams.sectors(flat[keep]), -height[keep])
    pole = keep & (radius <= AXIS)
    return np.maximum(depth, -height[pole].min()) if pole.any() else depth


def hidden(parts, bones, body, contract=None, skin=None, left=()):
    """How what the split added to an outfit meets the seam contract's `ends` (version 3) on body `body`:
    (report, failures), or None when the contract has no rings of that body. At each joint the bake cuts (not
    `UNCUT`):

    * Closed. No part is open on the joint's plane but where a pad's half lies on it (`pad`): left open, an
      over end showed the part's inside once a bend turned the under part out of it.
    * Domed. Past the over part's rim, what closes it stands farther past the plane than the rim does on
      average, and no more than the contract's `domeMost` (and `DOME_SLACK`) farther than the rim's farthest
      point: a dome 15 cm past the hip plane, its rim 8 cm, hung below the seat as bulk (Facility Security, 2026-11-13).
    * Hidden at rest. Each point the split added to the under end off the outfit's own surface lies inside another
      of the outfit's parts or no more than the contract's `rest` outside one, and under a slot the brief leaves to
      the body (`left`) inside the body's own skin (`skin`, its parts as `measure.body` reads them, the whole body
      as one): without `skin`, that is not measured. A pad's faces are a plate's and are not measured. Nor is an
      over end's dome here: an over end is at least as wide as the envelope and an under end inside it, so the
      dome's first rings stand out over the under end by contract, as the open end and the flat lid did.
    * Hidden in the bend. Turned about the joint by the contract's design bend (`_turns`), each point of the under
      end past the plane and farther from the joint than the end's own ring on the plane lies inside the over
      part or no more than `bent` outside it. A point within that ring turns within it: a rounded end shows as
      a rounded joint.

    A point belongs to the joint of its part whose centre is nearest it. The report holds per joint and side the
    `over` and `under` parts and, in metres, each part's edge left open on the plane (`open`), how far the over
    part's dome rises past its rim's mean (`rise`) and past its farthest point (`past`), and how far what was
    added stands outside at most as the body stands (`rest`) and turned (`bent`), None where nothing was measured."""
    contract = seams.load_contract() if contract is None else contract
    if any(body not in contract['joints'][joint]['bodies'] for joint in seams.JOINTS):
        return None
    rule, left = contract.get('ends', seams.ENDS), set(left)
    keys = [(joint, side) for joint in seams.JOINTS for side in seams.sides(joint) if (joint, side) not in UNCUT]
    planes, slots, report, failures = {}, {}, {}, []
    for joint, side in keys:
        letter = 'l' if side == 'c' else side
        point, normal = seams.plane(bones, joint, letter)
        widest = np.max(seams.envelope(contract, joint, body, registry.TIERS[-1], None if side == 'c' else side))
        planes[(joint, side)] = (np.asarray(point, float), seams.unit(normal), REACH * float(widest))
        slots[(joint, side)] = tuple(split.token(seams.JOINTS[joint][key], letter) for key in ('over', 'under'))
        report.setdefault(joint, {})[side] = {'over': slots[(joint, side)][0], 'under': slots[(joint, side)][1], 'open': {},
                                              'rise': None, 'past': None, 'rest': None, 'bent': None}
    row = lambda key: report[key[0]][key[1]]
    worse = lambda key, field, value: row(key).update({field: round(max(value, row(key)[field] or 0.0), 4)})
    data = {}
    for name, part in parts.items():
        v, f = np.asarray(part['v'], float), np.asarray(part['f'], int)
        flag = lambda key: np.asarray(part.get(key, np.zeros(len(f), bool)), bool)
        mine = [key for key in keys if name in slots[key]]
        centres = np.array([planes[key][0] for key in mine]).reshape(-1, 3)
        nearest = np.linalg.norm(v[:, None] - centres[None], axis=2).argmin(axis=1) if mine else np.zeros(len(v), int)
        data[name] = {'v': v, 'f': f, 'skin': flag('skin'), 'pad': flag('pad'), 'added': _added(part) & ~flag('skin'), 'joints': mine, 'nearest': nearest}
    others = lambda name: [(data[other]['v'], data[other]['f']) for other in data if other != name]
    body_skin = [tuple(np.asarray(x) for x in mesh) for mesh in (skin or {}).values()]
    for name, part in data.items():  # closed
        v, f = part['v'], part['f']
        loose, face = _open_edges(v, f)
        loose = loose[~(part['pad'] | part['skin'])[face]]  # a pad's half is left open; the body's skin joins by matched rings
        for key in part['joints']:
            point, normal, limit = planes[key]
            along = (v - point) @ normal
            on = (np.abs(along) < ON_PLANE) & (np.linalg.norm(v - point - along[:, None] * normal, axis=1) <= limit)
            edges = loose[on[loose].all(axis=1)]
            length = float(np.linalg.norm(v[edges[:, 0]] - v[edges[:, 1]], axis=1).sum())
            row(key)['open'][name] = round(length, 4)
            if length >= OPEN_LEAST:
                failures.append(f'{name} at the {key[0]}: open on its plane, {length * 100:.1f} cm of edge')
    for key in keys:  # domed
        over = slots[key][0]
        if over not in data:
            continue
        part = data[over]
        v, f, point, normal = part['v'], part['f'], planes[key][0], planes[key][1]
        along = (v - point) @ normal
        here = part['nearest'] == part['joints'].index(key)
        closing, own = _used(v, f, part['added'] & ~part['pad']), _used(v, f, ~part['added'] & ~part['skin'])
        dome, rim = closing & here & (along > ON_PLANE), closing & own & here & (along > -ON_PLANE)
        if not (dome.any() and rim.any()):
            continue
        rise, past = float(along[dome].max() - along[rim].mean()), float(along[dome].max() - along[rim].max())
        row(key).update(rise=round(rise, 4), past=round(past, 4))
        if rise <= ON_PLANE:
            failures.append(f'{over} at the {key[0]}: not domed, what closes it stands no farther past the plane than its rim')
        if past > rule['domeMost'] + DOME_SLACK:
            failures.append(f'{over} at the {key[0]}: its dome stands {past * 100:.1f} cm past its rim, over the contract\'s {rule["domeMost"] * 100:.1f} cm')
    for name, part in data.items():  # hidden at rest
        v, f = part['v'], part['f']
        added, own = _used(v, f, part['added'] & ~part['pad']), _used(v, f, ~part['added'])
        for index, key in enumerate(part['joints']):
            over, under = slots[key]
            if name != under or (over not in data and over not in left):
                continue  # an over end's dome stands over the under part's narrower end by contract, and `domed` bounds it;
                # with nothing over an under end, nothing hides it
            meshes = body_skin if over in left else others(name)
            points = v[added & ~own & (part['nearest'] == index)]
            if not len(points) or not meshes:
                continue
            outside = ~_inside(points, meshes)
            if outside.any():
                far = _off(points[outside], meshes).max()
                worse(key, 'rest', far)
                if far > rule['rest']:
                    failures.append(f'{name} at the {key[0]}: what the split added stands up to {far * 100:.1f} cm outside the outfit as the body stands')
            else:
                worse(key, 'rest', 0.0)
    for key in keys:  # hidden in the bend
        over, under = slots[key]
        if over not in data or under not in data:
            continue
        point, normal, limit = planes[key]
        part = data[under]
        used = np.unique(part['f'][~part['skin'] & ~part['pad']])
        x = part['v'][used]
        along = (x - point) @ normal
        radial = np.linalg.norm(x - point - along[:, None] * normal, axis=1)
        ring = (np.abs(along) < 1e-3) & (radial <= limit)
        if not ring.any():
            continue
        end = x[(along < -ON_PLANE) & (radial <= limit) & (np.linalg.norm(x - point, axis=1) > radial[ring].max() + rule['bent'])]
        worse(key, 'bent', 0.0)
        middle = (bones['lbicep_g'][:3, 3] + bones['rbicep_g'][:3, 3]) / 2
        bend = float(contract['joints'][key[0]]['bodies'][body]['bend'][contract['designBend']])
        mesh, worst = [(data[over]['v'], data[over]['f'])], None
        for turn in (_turns(key[0], normal, bend, point - middle) if len(end) else ()):
            moved = point + (end - point) @ turn.T
            outside = ~_inside(moved, mesh)
            far = float(_off(moved[outside], mesh).max()) if outside.any() else 0.0
            if far > row(key)['bent']:
                worse(key, 'bent', far)
                worst = turn
        if row(key)['bent'] > rule['bent']:
            failures.append(f'{under} at the {key[0]}: turned {_way(worst, normal)} by {_degrees(worst):.0f} degrees of the design bend\'s '
                            f'{bend:.0f}, its end stands up to {row(key)["bent"] * 100:.1f} cm outside {over}')
    return report, failures


def through(parts, bones):
    """(report, failures): for each part that holds the body's own skin beside the outfit's (`bodyskin.worn`),
    how far that skin stands out through the rest of the part, everything the client draws over it (a
    sleeve's cloth, and the dome closing its end), each of its vertices read along the ray square out from
    the part's bone (`bones`, the rig) through it (`measure.beyond`): its most, in metres, 0 where none of it
    does. More than `THROUGH` fails. The male's sleeves carried to the Human female lay up to 1.6 cm inside
    her arm by the skin kept below their hems, which the user saw through them with her arms raised; held
    clear of it by the sleeve's cloth alone, her arm still stood up to 9 mm through the dome carried from the
    male's armpit, which the gate, reading the cloth alone too, passed, and the user saw it again
    (2026-11-13)."""
    report, failures = {}, []
    for name, part in parts.items():
        if 'skin' not in part:
            continue
        v, f, kept = np.asarray(part['v'], float), np.asarray(part['f'], int), np.asarray(part['skin'], bool)
        cloth = f[~kept]
        if not len(cloth) or not kept.any():
            continue
        slot = next(slot for slot, spec in registry.SLOTS.items() if name in spec['tokens'])
        start, end = (np.asarray(bones[bone.format(name[-1])], float)[:3, 3] for bone in split.BONE_ENDS[slot])
        outside = measure.beyond(v[np.unique(f[kept])], start, seams.unit(end - start), v, cloth)[0]
        most = max(float(np.nanmax(outside)) if np.isfinite(outside).any() else 0.0, 0.0)
        report[name] = round(most, 4)
        if most > THROUGH:
            failures.append(f'{name}: the body\'s own skin beside it stands up to {most * 100:.1f} cm out through the outfit over it')
    return report, failures


def _used(vertices, faces, which):
    """Per vertex, whether a face in `which` uses it or a copy of it at the same point: a baked part is laid out,
    its vertices doubled where the texture's islands meet, so a rim point a cap uses may be a copy of the one
    the outfit's own faces use."""
    weld = mesh_ops.weld_ids(vertices)
    return np.isin(weld, weld[faces[which].ravel()])


def _added(part):
    """Per face of a part, whether the split added it: its `added` flags, or else from what made each face (`made`)."""
    return np.asarray(part['added'], bool) if 'added' in part else np.isin(part['made'], ADDED)


def _open_edges(vertices, faces):
    """(edges, face): the edges of `faces` on one face only, vertices within `split.WELD` of each other being one
    point, as pairs of vertex numbers, and the face each is on."""
    weld = mesh_ops.weld_ids(vertices, split.WELD)
    edges = np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]])
    face = np.tile(np.arange(len(faces)), 3)
    key = np.sort(weld[edges], axis=1)
    real = key[:, 0] != key[:, 1]
    edges, face, key = edges[real], face[real], key[real]
    if not len(edges):
        return edges.reshape(0, 2), face
    _, inverse, count = np.unique(key, axis=0, return_inverse=True, return_counts=True)
    single = count[inverse.reshape(-1)] == 1
    return edges[single], face[single]


def _inside(points, meshes):
    """Per point, whether it lies inside one of the closed surfaces `meshes`, (vertices, faces) each: its winding
    number about that surface half a turn or more (`measure.winding`). A surface is asked only about the points
    within its bounds."""
    points, found = np.asarray(points, float), np.zeros(len(points), bool)
    for vertices, faces in meshes:
        vertices = np.asarray(vertices, float)
        low, high = vertices.min(axis=0), vertices.max(axis=0)
        near = ~found & (points >= low).all(axis=1) & (points <= high).all(axis=1)
        if near.any():
            found[near] = np.abs(measure.winding(points[near], vertices, faces)) >= 0.5
    return found


def _off(points, meshes, step=HIDDEN_STEP, near=HIDDEN_NEAR):
    """Per point, how far it stands from the nearest of the surfaces `meshes`, read at points `step` apart within
    `near` of the points; `near` itself where none of them comes that near."""
    points = np.asarray(points, float)
    low, high = points.min(axis=0) - near, points.max(axis=0) + near
    samples = []
    for vertices, faces in meshes:
        corners = np.asarray(vertices, float)[np.asarray(faces, int)]
        close = (corners.max(axis=1) >= low).all(axis=1) & (corners.min(axis=1) <= high).all(axis=1)
        if close.any():
            used, inside = np.unique(np.asarray(faces, int)[close], return_inverse=True)
            samples.append(measure.surface_points(np.asarray(vertices, float)[used], inside.reshape(-1, 3), step))
    if not samples:
        return np.full(len(points), near)
    return np.minimum(texture.nearest(points, np.concatenate(samples))[1], near)


def _way(turn, normal):
    """Which way of the body's (+X its left, +Y its front, +Z up) a turn swings a limb along `normal` most."""
    normal = np.asarray(normal, float)
    turned = turn @ normal
    swing = turned - (turned @ normal) * normal
    axis = int(np.argmax(np.abs(swing)))
    return ('right', 'left', 'back', 'forward', 'down', 'up')[2 * axis + int(swing[axis] > 0)]


def _degrees(turn):
    """How far a turn turns, in degrees."""
    return float(np.degrees(np.arccos(np.clip((np.trace(turn) - 1) / 2, -1.0, 1.0))))


def _turns(joint, normal, bend, out):
    """The turns of an under part about its joint that `hidden` holds its end to, as matrices, by `bend` degrees:
    an upper arm's and a thigh's as the split holds them inside the torso (`split.swung`; `out`, the way from the
    torso to the joint, for an arm); a hinge's (`HINGES`) the one way it bends, by half and all of it; any other
    forward, back and to either side by half and all of it."""
    if joint in ('shoulder', 'hip'):
        return split.swung(normal, bend, out if joint == 'shoulder' else None)
    forward = seams.unit(np.array((0.0, 1.0, 0.0)) - normal[1] * normal)
    across = np.cross(normal, forward)  # turned about this by a positive angle, the under part swings forward
    ways = [(across, HINGES[joint])] if joint in HINGES else [(axis, sign) for axis in (across, forward) for sign in (1.0, -1.0)]
    return [split.rotation(axis, sign * share * bend) for axis, sign in ways for share in (0.5, 1.0)]


def bake(document, mesh, colours, raw, body_pack, xatlas, body='pmh0', tier=2, say=lambda *_: None, body_textures=None, capture=None):
    """(parts, bones, whole): a generated outfit as the parts body `body` wears, each with its maps, and what
    it holds of holes and detached pieces (`surface`, at the body's size).

    `document` is the outfit's brief (`brief.load`), `mesh` its exported mesh, `colours` its saved colour
    field and `raw` the generator's own high-detail mesh, whose relief the normal maps are read from.
    `body_pack` is the folder of the body's models, `xatlas` the loaded layout library, `tier` the seam tier
    the outfit is cut at. `parts` maps a part's token to its laid-out mesh (`v`, `f`, `uv`, `n`), its colours
    and relief per texel (`rgb`, `covered`, `relief`), the texels `tint_maps` is told about (`closing`, `cap`,
    `padded`), flags per face (`added`, `domed`), the brief's material of each face that is no plate's
    (`trimmed`, -1 elsewhere) and where each vertex lies on the generated mesh (`src`). `bones` is the body's
    rig. `say` is told how each stage went.

    A slot the brief leaves to the body (`bare`) gets no part: what the outfit has there, a glove's cuff
    past the wrist, is cut off on the joint's plane. In a slot the brief shares with the body's skin
    (`skin`) the part also holds the body's own part where the outfit shows it, with its textures
    (`bodyskin.worn`); `body_textures` is the folder of the body's material files and maps. With `capture`, a file
    path, what the split is given is kept there too (`keep_split`)."""
    count = len(document['materials'])
    require(not document.get('skin') or body_textures is not None, "An outfit that shows the body's skin on a part needs the folder of the body's textures")
    bones, skin = measure.body(body_pack, body)
    source, faces = repose.load(mesh)
    field, levels = texture.open_field(colours)
    read = lambda points: texture.read_field(field, levels, points)
    as_read, shown = texture.mesh_materials(to_field(source), faces, read, count)
    as_read, on_mesh = np.asarray(as_read), brief.worn(document, shown)
    metals = [k for k, material in enumerate(on_mesh) if material['kind'] == 'metal']
    kinds = np.asarray(texture.trimmed(source, faces, as_read, metals))  # a line of metal too narrow for a plate goes to what it lies on
    say('trims', int((kinds != as_read).sum()), 'faces')
    listed = [material['name'] for material in document['materials']]
    brief_of = np.array([listed.index(material['name']) for material in on_mesh] + [-1])
    carried = repose.onto_body(source, faces, bones, skin, materials=kinds, padded=''.join(document.get('pads', [])))
    whole = surface(source * carried['scale'], faces)
    say('surface', whole)
    v, f, source = carried['vertices'], carried['faces'], carried['source']
    raw_v, raw_f = gltf.positions(raw)
    fine, fine_levels = texture.normal_field(np.asarray(raw_v), np.asarray(raw_f))
    read_fine = lambda points: texture.read_field(fine, fine_levels, points)
    in_field = to_field(source)
    contract = seams.load_contract()
    joints = {name: matrix[:3, 3] for name, matrix in bones.items()}
    keys = [(joint, side) for joint in seams.JOINTS for side in seams.sides(joint)]
    radii = {key: float(np.max(seams.envelope(contract, key[0], body, tier, None if key[1] == 'c' else key[1]))) for key in keys}
    # the seat stays on the pelvis, cut where the body's own pelvis ends, and each thigh ends just inside its envelope
    seat = {('hip', side): {'reach': measure.seat(skin, *seams.plane(bones, 'hip', side), side),
                            'ring': np.asarray(seams.envelope(contract, 'hip', body, tier, side), float) - shaping.MARGIN,
                            'bend': float(contract['joints']['hip']['bodies'][body]['bend'][contract['designBend']])} for side in 'lr'}
    # the upper arm leaves the chest where the body's own does, and ends just inside its envelope
    arms = {('shoulder', side): {'line': measure.armhole(skin, *seams.plane(bones, 'shoulder', side), side),
                                 'ring': np.asarray(seams.envelope(contract, 'shoulder', body, tier, side), float) - shaping.MARGIN,
                                 'bend': float(contract['joints']['shoulder']['bodies'][body]['bend'][contract['designBend']])} for side in 'lr'}
    overlaps = {key: float(seams.overlap(contract, key[0], body, tier)) + (shaping.DEEPER if key[0] in shaping.TUBES or key in seat or key in arms else 0.0)
                for key in keys}
    # the posed normals, and the positions and normals on the generated mesh, ride through the cut
    columns = np.concatenate([export.vertex_normals(v, f), in_field, export.vertex_normals(in_field, f)], axis=1)
    mats, read_as = kinds[carried['origin']], as_read[carried['origin']]
    guards = {(joint, side): flags for joint in split.GUARDS for side in 'lr'
              for flags in [split.guard(v, f, mats, joints, joint, side, read=read_as)] if flags is not None}
    say('pads', {key: int(flags.sum()) for key, flags in guards.items()})
    given = {'vertices': v, 'faces': f, 'columns': columns, 'joints': joints, 'radii': radii, 'overlaps': overlaps,
             'reaches': split.reaches(v, f, joints, radii, sleeves=carried['sleeves']), 'sleeves': carried['sleeves'], 'guards': guards,
             'seat': seat, 'arms': arms, 'bones': bones, 'body': body, 'tier': tier, 'left': sorted(left_to_body(document)),
             'shared': sorted(shared_with_body(document))}
    if capture is not None:
        keep_split(given, capture)
        say('split inputs kept in', capture)
    result, made, origins = cut(given, contract)
    own_part = functools.lru_cache(maxsize=None)(lambda name: bodyskin.body_part(body_pack, body_textures, body, name, bones))  # read once a bake
    beside = {name: lambda pv, pf, slot=slot, name=name: skin_beside(own_part(name), bones, slot, name, pv, pf)
              for slot in document.get('skin', []) for name in registry.SLOTS[slot]['tokens'] if name in result}
    result = within_budget(result, made, origins, given['joints'], given['radii'], beside, left_to_body(document), say)
    unit = lambda rows: rows / np.maximum(np.linalg.norm(rows, axis=1, keepdims=True), 1e-12)
    seen_at = None  # the material the outfit shows at each of its vertices, read once
    parts = {}
    left = left_to_body(document)
    for name, (pv, pf, pc) in result.items():
        if name in left:  # the body's: what the outfit has there is cut off on the joint's plane, and no map is made of it
            say(f'{name}: left to the body, {len(pf)} faces of the outfit cut off')
            continue
        role = roles(name, made[name])
        pad = pad_flags(made[name], origins[name], guards)  # the seam gate leaves a pad over a joint out
        of_face = np.where(origins[name] >= 0, mats[np.maximum(origins[name], 0)], -1)  # per face: its material, -1 for what the split made
        bare = (of_face >= 0) & ~np.isin(of_face, metals)  # a face that is no plate's shows no plate
        if role['under'].any():  # the cloth of the part's commonest material, where the outfit shows that colour
            if seen_at is None:
                seen_at = texture.labels(np.asarray(read(columns[:, 3:6])[0], float)[:, :3], shown['tones'])
            main = np.bincount(of_face[of_face >= 0]).argmax()
            cloth = np.zeros(len(v), bool)
            cloth[f[mats == main]] = True
            only, near = texture.under(pv, pf, made[name], v, cloth & (seen_at == main), kind=UNDER[name])
            pc = pc.copy()
            pc[only, 3:9] = columns[near, 3:9]
        size = texture.size(pv, pf)
        mapping, pf, uv = texture.layout(xatlas, pv, pf, size)
        pv, pc = pv[mapping], pc[mapping]
        rgb, covered, missed = texture.colour_map(uv, pf, pc[:, 3:6], read, size)
        if role['under'].any():
            mine = texture.face_texels(uv, pf, role['under'], size) & covered
            rgb[mine] = texture.soft_map(uv, pf, pc[:, 3:6], read, size)[mine]
        relief, _, lost = texture.normal_map(uv, pf, pc[:, 3:6], unit(pc[:, 6:9]), pv, read_fine, size, added=role['added'])
        parts[name] = {'v': pv, 'f': pf, 'uv': uv, 'n': unit(pc[:, :3]), 'rgb': rgb, 'covered': covered, 'relief': relief,
                       **{key: texture.face_texels(uv, pf, role[key], size) for key in ('closing', 'cap', 'padded')},
                       'added': role['added'], 'domed': role['domed'], 'src': pc[:, 3:6], 'trimmed': np.where(bare, brief_of[of_face], -1), 'pad': pad}
        say(f'{name}: {size} px, {len(pf)} faces, covered {covered.mean():.0%}, no colour {missed}, no normal {lost}')
    # what the torso wears over a sleeve is drawn as the sleeve's cloth, with the sleeve's closings
    if 'chest' in parts:
        first = texture.materials(np.concatenate([part['rgb'][part['covered']] for part in parts.values()]), count)
        chest = parts['chest']
        seen = np.where(chest['covered'], texture.labels(chest['rgb'].reshape(-1, 3), first['tones']).reshape(chest['covered'].shape), -1)
        others = texture.edge_materials(seen, texture.face_texels(chest['uv'], chest['f'], made['chest'] == split.CLOSING, len(chest['rgb'])))
        for name in ARMHOLE:
            if name in parts:
                part, size = parts[name], len(parts[name]['rgb'])
                shows = texture.face_materials(part['uv'], part['f'], part['rgb'], part['covered'], first, size)
                over = texture.overlaid(part['v'], part['f'], shows, made[name] == split.CLOSING, others)
                part['closing'] = texture.face_texels(part['uv'], part['f'], (made[name] == split.CLOSING) | over, size)
    return skinned(parts, document, body_pack, body_textures, body, bones, say, own_part), bones, whole


def cut(given, contract=None):
    """The split as a bake runs it, on what `bake` gives it (`keep_split`): (parts, made, origins) as `split.split`
    returns them and fills them in. Each end at a tube joint is shaped to the contract (`ends.shaper`), the hips
    are cut on the body's seat and the shoulders on its armhole, and the neck is left whole. An end under a
    slot the brief leaves to the body lies on the body's skin and is shaped skin-tight (`ends.BARE`), its cap
    stepping in under the skin at the plane (`ends.TUCK`)."""
    contract = seams.load_contract() if contract is None else contract
    made, origins = {}, {}
    bare = bare_joints(given)
    result = split.split(given['vertices'], given['faces'], given['columns'], given['joints'], given['radii'], given['overlaps'],
                         reaches=given['reaches'], whole=UNCUT, made=made, sleeves=given['sleeves'], guards=given['guards'],
                         origins=origins, shape=shaping.shaper(given['bones'], contract, given['body'], given['tier'], given['guards'], bare=bare),
                         deep=shaping.TUBES, seat=given['seat'], arms=given['arms'], tucks={key: shaping.TUCK for key in bare},
                         ends=contract.get('ends'))
    return result, made, origins


def bare_joints(given):
    """The (joint, side) pairs of the shaped joints (`ends.TUBES`) whose over slot the brief leaves to the body
    (`given['left']`): an end under one lies on the body's own skin."""
    left = set(given.get('left', ()))
    return {(joint, side) for joint in shaping.TUBES for side in seams.sides(joint)
            if split.token(seams.JOINTS[joint]['over'], 'l' if side == 'c' else side) in left}


def skin_beside(own, bones, slot, name, vertices, faces):
    """How many faces of the body's own part `name` (`own`, `bodyskin.body_part`) `bodyskin.worn` keeps beside
    an outfit's part (`vertices`, `faces`) in a slot the brief shares with the body's skin."""
    start, end = (np.asarray(bones[end.format(name[-1])], float)[:3, 3] for end in split.BONE_ENDS[slot])
    return int(bodyskin.shown(own['v'], own['f'], vertices, faces, start, end).sum())


def welded(points, faces, which):
    """`faces` with the vertices at one place (`POINT`) made one, the first of them, and the faces that leaves
    with two corners at one point dropped: (faces, which), `which` cut down alike."""
    group = mesh_ops.weld_ids(points, POINT)
    first = np.full(int(group.max()) + 1, len(points))
    np.minimum.at(first, group, np.arange(len(points)))
    faces = first[group][np.asarray(faces, int)]
    whole = (faces[:, 0] != faces[:, 1]) & (faces[:, 1] != faces[:, 2]) & (faces[:, 2] != faces[:, 0])
    return faces[whole], np.asarray(which)[whole]


def within_budget(result, made, origins, joints, radii, beside=None, left=(), say=lambda *_: None):
    """The split's parts (`cut`), each part over its triangle budget (`BUDGET`) brought under it (`reduce`).

    `made` and `origins` are the split's flags per face of each part and are cut down to the faces kept.
    Nothing the split made (closings, caps, walls, gussets) loses a vertex, nor the outfit within `END_BAND`
    of a joint's plane, where the seam contract measures its ends; inside a cap a vertex may go where the
    rest cannot reach the budget, but none on the cap's rim. `beside[name](vertices, faces)` counts the body's
    own faces a part in a slot shared with the body's skin will hold (`skin_beside`): they count against its
    budget, and the part is reduced again until the two fit. Parts in `left` (the body's) are not reduced.
    Facility Security, exported at 17,000 faces, was worn at 29,396 triangles, within the whole outfit's
    budget, with seven parts over theirs: the legs carry the cargo pockets, straps and guards (2026-11-13).

    A part still over its budget then (one cut from a dense mesh, whose closings and caps are as dense as its
    rims) is reduced as a whole, what the split made too: a point on a joint's plane goes only along its line
    on the plane, its rim or where its cap meets it, so its ends stay on their planes (`reduce`'s `lines`). Its
    vertices at one place are made one first (`welded`): a lid's fan has a middle vertex per point of its line.
    The ring of an under end on its plane loses no point in any pass, a cap's included: where the ring is
    dented, a chord left by a point taken out stands outside the curve, and the end's section, which the seam
    contract measures there, stood up to a millimetre outside the envelope (Facility Security with domes,
    2026-11-13). A reduced part keeps no triangle with two corners at one point."""
    beside, out, planes = beside or {}, {}, None
    for name, (pv, pf, pc) in result.items():
        budget = BUDGET['chest'] if name == 'chest' else BUDGET['slot']
        count = beside.get(name, lambda *_: 0)
        held = 0 if name in left else count(pv, pf)  # the body's faces beside the part as it stands, counted anew as it is cut down
        if name in left or len(pf) + held <= budget:
            out[name] = (pv, pf, pc)
            continue
        own = np.zeros(len(pv), bool)
        own[pf[made[name] == split.OWN].ravel()] = True
        added = np.zeros(len(pv), bool)
        added[pf[made[name] != split.OWN].ravel()] = True
        capped = np.zeros(len(pv), bool)
        capped[pf[made[name] == split.CAP].ravel()] = True
        capped &= ~own & ~np.isin(np.arange(len(pv)), pf[(made[name] != split.CAP) & (made[name] != split.OWN)].ravel())
        planes = split.planes(joints) if planes is None else planes
        near, lines, ring = np.zeros(len(pv), bool), np.zeros(len(pv), np.int64), np.zeros(len(pv), bool)
        for bit, (key, (point, normal)) in enumerate(planes.items()):
            unit = seams.unit(normal)
            along = (pv - point) @ unit
            inside = np.linalg.norm((pv - point) - along[:, None] * unit, axis=1) < 2 * radii[key]
            near |= (np.abs(along) < END_BAND) & inside
            on_plane = (np.abs(along) < split.WELD) & inside
            # an under end's ring on its plane stays whole: where the ring is dented, a point taken out along it left a
            # chord standing outside the curve, and the end's section up to a millimetre outside the seam contract's
            # envelope (Facility Security with domes, 2026-11-13); an over end is measured inside its plane
            if split.token(seams.JOINTS[key[0]]['under'], 'l' if key[1] == 'c' else key[1]) == name:
                ring |= on_plane
            else:
                lines |= np.where(on_plane, np.int64(1) << bit, np.int64(0))
        before, kept, faces, which = len(pf), np.arange(len(pv)), pf, np.arange(len(pf))
        for locked, on in ((added | near, None), ((added & ~capped) | (near & own) | ring, None), (ring, lines)):
            if on is not None:  # the split builds one vertex per point of a line where its closings meet: made one, they reduce
                faces, which = welded(pv[kept], faces, which)
            for _ in range(SKIN_ROUNDS):
                if len(faces) + held <= budget:
                    break
                again, faces, inner = reduce.reduce(pv[kept], faces, budget - held, locked[kept], None if on is None else on[kept])
                kept, which = kept[again], which[inner]
                held = count(pv[kept], faces)
            if len(faces) + held <= budget:
                break
        corners = pv[kept][faces]
        whole = np.linalg.norm(corners - np.roll(corners, 1, axis=1), axis=2).min(axis=1) >= POINT  # no area: the compiler drops it
        faces, which = faces[whole], which[whole]
        made[name], origins[name] = made[name][which], origins[name][which]
        out[name] = (pv[kept], faces, pc[kept])
        say(f'{name}: reduced from {before} to {len(faces)} faces for its budget of {budget}')
    return out


def pad_flags(made, origins, guards):
    """Per face of a part, whether it is a pad over a joint: what the split carried round under one (`PADDED`)
    and the faces cut from a pad's own (`guards`, flags per face of the mesh split). The seam gate leaves
    them out."""
    pad = np.asarray(made) == split.PADDED
    for flags in guards.values():
        pad |= (np.asarray(origins) >= 0) & np.asarray(flags, bool)[np.maximum(origins, 0)]
    return pad


def keep_split(given, path):
    """Write what a bake gave the split (`cut`) to `path`, one .npz file with no pickled objects in it."""
    arrays = {}
    skeleton = _flat(given, arrays)
    np.savez_compressed(path, kind=np.array(SPLIT_KIND), skeleton=np.array(json.dumps(skeleton)), **arrays)
    return path


def kept_split(path):
    """What `keep_split` wrote, as it was given."""
    with np.load(path, allow_pickle=False) as data:
        require('kind' in data and str(data['kind']) == SPLIT_KIND, f'{path} holds no split inputs kept by a bake')
        return _unflat(json.loads(str(data['skeleton'])), data)


def resplit(capture, contract=None, body_pack=None):
    """The split run again with the code as it stands on what a bake kept (`keep_split`), in seconds where the bake
    takes minutes: (parts, report). `parts` maps each part a bake would bake (none the brief leaves to the body)
    to its `v`, `f`, `made` (what made each face: `split.OWN`, `split.CLOSING` and so on) and `pad` (`pad_flags`).
    The report holds the seconds the split took, the triangles of each part, those with two corners at one
    point (`gates`), and the seam contract's measure of every end (`ends`, `seams`) and of what closes it
    (`hidden`, with the seconds that took) with their `failures`; given `body_pack`, the folder of the body's
    models, what an end next to a slot left to the body added is measured against the body's skin too. Nothing
    is laid out, coloured or written: the gates of a written outfit are `run`'s."""
    given = kept_split(capture)
    began = time.monotonic()
    result, made, origins = cut(given, contract)
    left, shared = set(given.get('left', ())), set(given.get('shared', ()))
    result = within_budget(result, made, origins, given.get('joints'), given.get('radii'), left=left)  # the body's skin beside a part is not counted here
    seconds = time.monotonic() - began
    parts = {name: {'v': pv, 'f': pf, 'made': made[name], 'pad': pad_flags(made[name], origins[name], given['guards'])}
             for name, (pv, pf, _) in result.items() if name not in left}
    for name in shared & set(parts):  # a part that shares its slot with the body's skin ends where the body's part does (`ends`)
        parts[name]['skin'] = np.zeros(len(parts[name]['f']), bool)
    collapsed = {name: _collapsed(part['v'], part['f']) for name, part in parts.items()}
    failures = [f'{name}: {count} triangles with two corners at one point, which the model compiler drops' for name, count in collapsed.items() if count]
    joined = ends(parts, given['bones'], given['body'], given['tier'], contract)
    began = time.monotonic()
    skin = None if body_pack is None else measure.body(body_pack, given['body'])[1]
    covered = hidden(parts, given['bones'], given['body'], contract, skin, left)
    report = {'seconds': round(seconds, 2), 'triangles': {name: int(len(part['f'])) for name, part in parts.items()},
              'collapsed': {name: count for name, count in collapsed.items() if count},
              'seams': None if joined is None else joined[0], 'hidden': None if covered is None else covered[0],
              'hiddenSeconds': round(time.monotonic() - began, 2),
              'failures': failures + ([] if joined is None else joined[1]) + ([] if covered is None else covered[1])}
    return parts, report


def keep_parts(parts, path):
    """Write the parts `resplit` made to one .npz file: `<part>__v`, `<part>__f`, `<part>__made` and `<part>__pad`."""
    np.savez_compressed(path, kind=np.array(WORN_KIND), **{f'{name}__{key}': part[key] for name, part in parts.items()
                                                           for key in ('v', 'f', 'made', 'pad')})
    return path


def _flat(value, arrays):
    """`value` as JSON, its arrays put in `arrays` under names of their own; tuples, sets and keys that are not
    strings are kept as what they were."""
    if isinstance(value, np.ndarray):
        name = f'a{len(arrays)}'
        arrays[name] = value
        return {'array': name}
    if isinstance(value, dict):
        return {'dict': [[_flat(key, arrays), _flat(item, arrays)] for key, item in value.items()]}
    if isinstance(value, (list, tuple, set, frozenset)):
        kind = 'list' if isinstance(value, list) else 'tuple' if isinstance(value, tuple) else 'set'
        return {kind: [_flat(item, arrays) for item in (sorted(value, key=repr) if kind == 'set' else value)]}
    if isinstance(value, np.generic):
        value = value.item()
    require(value is None or isinstance(value, (bool, int, float, str)), f'Split inputs hold a {type(value).__name__}, which is not kept')
    return {'value': value}


def _unflat(skeleton, arrays):
    (kind, value), = skeleton.items()
    if kind == 'array':
        return np.asarray(arrays[value])
    if kind == 'dict':
        return {_unflat(key, arrays): _unflat(item, arrays) for key, item in value}
    if kind in ('list', 'tuple', 'set'):
        items = [_unflat(item, arrays) for item in value]
        return items if kind == 'list' else tuple(items) if kind == 'tuple' else set(items)
    return value


def left_to_body(document):
    """The parts of the slots the brief leaves to the body (`bare`): `bake` makes none of them."""
    return {name for slot in document.get('bare', []) for name in registry.SLOTS[slot]['tokens']}


def shared_with_body(document):
    """The parts of the slots the brief shares with the body's skin (`skin`)."""
    return {name for slot in document.get('skin', []) for name in registry.SLOTS[slot]['tokens']}


def skinned(parts, document, body_pack, body_textures, body, bones, say=lambda *_: None, own_part=None):
    """The baked parts with the body's own part beside the outfit's in each slot the brief shares with the
    body's skin (`skin`, `bodyskin.worn`). `own_part(name)`, if given, is the body's part as already read."""
    parts = dict(parts)
    for slot in document.get('skin', []):
        for name in registry.SLOTS[slot]['tokens']:
            if name in parts:
                own = own_part(name) if own_part else bodyskin.body_part(body_pack, body_textures, body, name, bones)
                start, end = (np.asarray(bones[end.format(name[-1])], float)[:3, 3] for end in split.BONE_ENDS[slot])
                parts[name] = bodyskin.worn(parts[name], own, start, end, BUDGET['texture'])
                say(f'{name}: {int(parts[name]["skin"].sum())} of the body\'s {len(own["f"])} faces beside the outfit\'s, {len(parts[name]["rgb"])} px')
    return parts


def store(parts, folder, document=None):
    """Keep `bake`'s parts in `folder`, a file per part, for `stored`.

    The parts are listed in `baked.json`, written last: a folder used again for an outfit with fewer parts
    still holds the files of the parts it no longer has, and read by what lies in it, a second tint gave
    the new outfit the old one's shoulder pads. The list is taken away first, so a store that stops halfway
    leaves nothing `stored` would read. With it are the slots `document`, the brief the parts were baked
    from, leaves to the body and shares with its skin (`declared`): the parts alone do not show a slot left
    to the body that the brief no longer leaves, since that slot has no part either way."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / KEPT).unlink(missing_ok=True)
    for name, part in parts.items():
        np.savez(folder / (name + '.npz'), **{key: part[key] for key in KEYS + tuple(key for key in OPTIONAL + bodyskin.KEYS if key in part)})
    slots = {key: sorted((document or {}).get(key, [])) for key in ('bare', 'skin')}
    (folder / KEPT).write_text(json.dumps({'schemaVersion': 1, 'kind': KEPT_KIND, 'parts': list(parts), **slots}, indent=1) + '\n',
                               encoding='utf-8', newline='\n')


def listing(folder):
    """The list `store` wrote in `folder`, checked: its `parts`, and its `bare` and `skin` slots, none for parts
    kept before the list held them."""
    folder = Path(folder)
    require((folder / KEPT).is_file(), f'{folder} holds no baked parts: it has no {KEPT}')
    listed = json.loads((folder / KEPT).read_text(encoding='utf-8'))
    named = lambda value: isinstance(value, list) and all(isinstance(name, str) for name in value)
    require(isinstance(listed, dict) and listed.get('kind') == KEPT_KIND and listed.get('schemaVersion') == 1
            and named(listed.get('parts')) and listed['parts'] and all(named(listed.get(key, [])) for key in ('bare', 'skin')),
            f'{folder / KEPT} is no list of baked parts')
    return {'parts': listed['parts'], **{key: listed.get(key, []) for key in ('bare', 'skin')}}


def declared(folder):
    """{'bare': slots, 'skin': slots}: what the brief the parts in `folder` were baked from left to the body and
    shared with its skin (`store`)."""
    listed = listing(folder)
    return {key: set(listed[key]) for key in ('bare', 'skin')}


def stored(folder):
    """The parts `store` last kept in `folder`: those its list names, and no other file there."""
    folder = Path(folder)
    listed = listing(folder)
    require(all((folder / (name + '.npz')).is_file() for name in listed['parts']), f'{folder} lacks a part its {KEPT} lists')
    parts = {name: dict(np.load(folder / (name + '.npz'))) for name in listed['parts']}
    require(all(set(KEYS) <= set(part) for part in parts.values()), f'{folder} holds a file that is no baked part')
    return parts


def tints(parts, document, speck=texture.SPECK):
    """({part: (shades, layers)}, record): the tint texture of every part of a baked outfit, for `export.tint`.

    The materials are found over the whole outfit and told which of the brief's each is (`brief.worn`); a
    material's garments are told apart by where they are worn (`texture.worn_second`), and what the split
    made is drawn at the outfit's lit shades (`texture.lit_shades`). `record` holds the materials as found,
    in the order of the texels' numbers, their channels and lit shades.

    The parts are taken in the order of their names, whatever order they are given in: the materials are
    found on a sample of the texels as they come, and a fresh bake and its stored parts tinted again would
    else differ by a shade here and there."""
    count, parts = len(document['materials']), {name: parts[name] for name in sorted(parts)}
    size = lambda part: len(part['rgb'])
    found = texture.materials(np.concatenate([part['rgb'][part['covered']] for part in parts.values()]), count)
    worn = brief.worn(document, found)  # the brief's material for each the colours show: its kind is the brief's to say
    kinds = [material['kind'] for material in worn]
    channel = texture.channels(kinds)  # two channels per material: its garments are told apart by where they are worn
    slot_of = {token: slot for slot in SLOTS for token in registry.SLOTS[slot]['tokens']}
    own = {name: ~part['added'] & ~part.get('skin', np.zeros(len(part['f']), bool)) for name, part in parts.items()}  # the outfit's own surface: not the split's, not the body's
    start = np.cumsum([0] + [len(part['src']) for part in parts.values()])
    seen = {name: texture.face_materials(part['uv'], part['f'], part['rgb'], part['covered'], found, size(part)) for name, part in parts.items()}
    second = texture.worn_second(np.concatenate([part['src'] for part in parts.values()]),
                                 np.concatenate([part['f'][own[name]] + start[i] for i, (name, part) in enumerate(parts.items())]),
                                 np.concatenate([seen[name][own[name]] for name in parts]),
                                 np.concatenate([[slot_of[name]] * int(own[name].sum()) for name in parts]), kinds)
    at = np.cumsum([0] + [int(own[name].sum()) for name in parts])
    listed = [material['name'] for material in document['materials']]
    here = {listed.index(material['name']): k for k, material in enumerate(worn)}  # the brief's material, as the texels number it
    lit = texture.lit_shades(np.concatenate([part['rgb'][part['covered'] & ~part['closing'] & ~part['cap']] for part in parts.values()]), found)
    tinted = {}
    for i, (name, part) in enumerate(parts.items()):
        rows = np.zeros((len(part['f']), count), bool)
        rows[own[name]] = second[at[i]:at[i + 1]]
        twice = texture.face_texels(part['uv'], part['f'], texture.added_second(part['v'], part['f'], part['added'], rows), size(part))
        trim = np.full(part['covered'].shape, -1)
        for material in np.unique(part['trimmed'][part['trimmed'] >= 0]):
            trim[texture.face_texels(part['uv'], part['f'], part['trimmed'] == material, size(part))] = here[int(material)]
        tinted[name] = texture.tint_maps(part['rgb'], part['covered'], found, channel, relief=part['relief'],
                                         charts=texture.chart_map(part['uv'], part['f'], size(part)), closing=part['closing'], second=twice,
                                         cap=part['cap'], padded=part['padded'], lit=lit, trim=trim,
                                         shadow=part['closing'] if name in ARMHOLE else None, speck=speck)
        tinted[name] = bodyskin.tinted(part, tinted[name])  # the body's skin keeps its own shade and layer
    record = {'materials': [{'name': material['name'], 'kind': material['kind'], 'channels': list(channel[k]),
                             'colour': np.round(found['colours'][k] * 255).astype(int).tolist(), 'lit': round(float(lit[k]), 1)}
                            for k, material in enumerate(worn)]}
    return tinted, record


def write(folder, parts, tinted, bones, body, number):
    """Write every part of a baked outfit as number `number` on `body`: {part: model name}.

    `<folder>/ascii` gets the models as ASCII and their tint textures, `<folder>/resources` the tint textures
    again, the normal maps at half size and the material files that bind them: what a pack takes, once the
    models are compiled into it (`export.compile_models`)."""
    ascii_dir, resources = Path(folder) / 'ascii', Path(folder) / 'resources'
    for made in (ascii_dir, resources):
        made.mkdir(parents=True, exist_ok=True)
    models = {}
    for name, part in parts.items():
        # closings and caps are lit as surfaces of their own
        v, f, n, uv = export.added_normals(part['v'], part['f'], part['added'], part['n'], part['uv'], domed=part['domed'])
        models[name] = export.write_part(ascii_dir, body, name, number, (v, f, uv, n), bones, tinted[name])
        if 'skin_at' in part:  # the body's normal map is already at half its size or less, and its roughness is a map
            texture.write_relief(resources, models[name], part['relief'], rough=part['skin_rough'] / 255)
        else:
            texture.write_relief(resources, models[name], texture.halved(part['relief']))
        shutil.copyfile(ascii_dir / (models[name] + '.plt'), resources / (models[name] + '.plt'))
    return models


def gates(parts, models, resources, packs=(), whole=None, joined=None, covered=None, skin=None):
    """The automatic gates of docs/armorkit/plan.md that can be checked on one written outfit: a report.

    Budgets: the triangles of each part, the chest's own and the whole outfit's, and the texels a side of
    each texture (`BUDGET`), and no triangle with two corners at one point (`POINT`). Names: no model of the outfit is one a pack in `packs` already holds (their
    length is checked as they are made, `registry.model_name`). Texture closure: every model has its tint
    texture and its material file in `resources`, and the map the material file names is there. `failures`
    lists what did not pass, `notBuilt` the gates of the plan this does not check yet: a pass here is not
    the plan's. With `whole`, what `surface` found on the generated outfit, a hole of `HOLE` or more round
    and a crumb of debris fail too, and the report holds it as `surface`; parts tinted again from a kept
    folder come without it, and that gate stays under `notBuilt`. With `joined`, what `ends` found, each end
    that misses the seam contract fails, and the report holds it as `seams`; on a body the contract has no
    rings of, that gate stays under `notBuilt`. So it is with `covered`, what `hidden` found, as `hidden`.
    With `skin`, what `through` found, the body's skin standing out through the outfit beside it fails too,
    and the report holds it as `through`."""
    resources, failures = Path(resources), []
    faces = {name: int(len(part['f'])) for name, part in parts.items()}
    for name, number in faces.items():
        limit = BUDGET['chest'] if name == 'chest' else BUDGET['slot']
        if number > limit:
            failures.append(f'{name}: {number} triangles, over the budget of {limit}')
    if sum(faces.values()) > BUDGET['outfit']:
        failures.append(f'the outfit: {sum(faces.values())} triangles, over the budget of {BUDGET["outfit"]}')
    for name, part in parts.items():
        if len(part['rgb']) > BUDGET['texture']:
            failures.append(f'{name}: a texture of {len(part["rgb"])} texels a side, over the budget of {BUDGET["texture"]}')
        collapsed = _collapsed(*_outfit(part, pads=True)[:2])  # the outfit's faces: the body's skin beside them is the body's
        if collapsed:  # the seam gate would still measure them, though nothing of them shows or compiles
            failures.append(f'{name}: {collapsed} triangles with two corners at one point, which the model compiler drops')
    for name, model in models.items():
        for pack in packs:
            if (Path(pack) / (model + '.mdl')).exists():
                failures.append(f'{model}: {pack} holds a model of that name')
        if not (resources / (model + '.plt')).is_file():
            failures.append(f'{model}: no tint texture')
        material = resources / (model + '.mtr')
        if not material.is_file():
            failures.append(f'{model}: no material file')
        else:
            named = [line.split()[1] for line in material.read_text(encoding='ascii').splitlines() if line.startswith('texture') and len(line.split()) > 1]
            failures += [f'{model}: its material file names {image}, which is not there' for image in named if not (resources / (image + '.tga')).is_file()]
    if whole is not None:
        failures += [f'the generated outfit: an opening {hole * 100:.1f} cm round' for hole in whole['holes']]
        failures += [f'the generated outfit: a piece of {piece * 1e4:.1f} cm² standing apart from the rest' for piece in whole['debris']]
    if joined is not None:
        failures += joined[1]
    if covered is not None:
        failures += covered[1]
    if skin is not None:
        failures += skin[1]
    checked = {WHOLE: whole is not None, SEAM: joined is not None, HIDDEN: covered is not None}
    return {'passed': not failures, 'failures': failures, 'triangles': {**faces, 'outfit': sum(faces.values())},
            'texels': {name: int(len(part['rgb'])) for name, part in parts.items()},
            **({} if whole is None else {'surface': whole}), **({} if joined is None else {'seams': joined[0]}),
            **({} if covered is None else {'hidden': covered[0]}), **({} if skin is None else {'through': skin[0]}), 'notBuilt': [gate for gate in NOT_BUILT if not checked.get(gate)]}


def run(document, output, body_pack, number, *, mesh=None, colours=None, raw=None, xatlas=None, kept=None, body='pmh0', tier=2,
        packs=(), game=None, resources=(), say=lambda *_: None, body_textures=None, capture=None):
    """Bake one outfit into `output` and check it: the record, also written as `<output>/bake.json`.

    With `mesh`, `colours`, `raw` and `xatlas` the outfit is baked (`bake`) and, where `kept` names a folder,
    stored there; without them the parts stored in `kept` are tinted and written again, if they were baked
    with the slots the brief leaves to the body or shares with its skin. `body_textures` is
    the folder of the body's material files and maps, for a brief that shows the body's skin. `packs` are the pack
    folders a model's name may not clash with. With `game`, the game's install folder, the models are
    compiled into `<output>/resources` (`export.compile_models`, with `resources` to look animations up in):
    the models of this run and no other. An output folder used before still holds the models written then,
    under another number or for parts the outfit no longer has, and they are neither in the record nor gated.
    `capture`, with a fresh bake, is the file what the split is given is kept in (`keep_split`, `resplit`)."""
    fresh = [mesh, colours, raw, xatlas]
    require(capture is None or mesh is not None, 'Split inputs are kept from a fresh bake: parts tinted again are split already')
    require(all(given is not None for given in fresh) or (kept is not None and all(given is None for given in fresh)),
            'Bake an outfit from its mesh, colour field, raw mesh and the layout library, or tint the parts kept in a folder again')
    if mesh is not None:
        parts, bones, whole = bake(document, mesh, colours, raw, body_pack, xatlas, body, tier, say, body_textures, capture)
        if kept is not None:
            store(parts, kept, document)
    else:
        parts, whole = stored(kept), None
        require(declared(kept) == {key: set(document.get(key, [])) for key in ('bare', 'skin')}
                and not left_to_body(document) & set(parts) and {name for name, part in parts.items() if 'skin' in part} == shared_with_body(document) & set(parts),
                f"{kept} holds parts baked for other slots left to the body or shared with its skin than the brief's: bake the outfit again")
        bones = measure.body(body_pack, body)[0]
    tinted, record = tints(parts, document)
    models = write(output, parts, tinted, bones, body, number)
    own = measure.body(body_pack, body)[1]
    covered = hidden(parts, bones, body, skin=own, left=left_to_body(document))
    record = {'model': document['model'], 'body': body, 'tier': tier, 'number': number, 'models': models, **record,
              'gates': gates(parts, models, Path(output) / 'resources', packs, whole, ends(parts, bones, body, tier), covered, through(parts, bones))}
    if game is not None:
        compiled = export.compile_models(sorted(Path(output) / 'ascii' / (model + '.mdl') for model in models.values()),
                                         Path(output) / 'resources', game=game, resources=list(resources))
        record['compiled'] = len(compiled)
    (Path(output) / 'bake.json').write_text(json.dumps(record, indent=1) + '\n', encoding='utf-8', newline='\n')
    return record
