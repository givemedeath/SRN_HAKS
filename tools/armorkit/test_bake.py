"""The bake's own choices and checks: what each face the split made is drawn as, what is kept, written and gated.

The stages it runs are tested where they live (test_repose, test_split, test_texture, test_export). Its whole run
needs a generated outfit and a body, and is checked against the first worn outfit instead
(docs/armorkit/pilot-corpsec.md)."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from . import bake, bodyskin, export, measure, registry, seams, split, texture
from .test_split import tube


def box(centre=(0.0, 0.0, 0.0), side=0.1):
    """A closed cube: (vertices, faces), wound outward."""
    v = (np.array([(x, y, z) for x in (0, 1) for y in (0, 1) for z in (0, 1)], float) - 0.5) * side + centre
    f = np.array([(0, 1, 3), (0, 3, 2), (4, 6, 7), (4, 7, 5), (0, 4, 5), (0, 5, 1), (2, 3, 7), (2, 7, 6), (0, 2, 6), (0, 6, 4), (1, 5, 7), (1, 7, 3)])
    return v, f


def joined(*meshes):
    """Meshes as one: (vertices, faces)."""
    base = np.cumsum([0] + [len(v) for v, _ in meshes])
    return np.concatenate([v for v, _ in meshes]), np.concatenate([f + b for (_, f), b in zip(meshes, base)])


def contract(ring=0.04, overlaps=(0.02, 0.03, 0.04, 0.06), rings=None):
    """A seam contract of one body, `test`, whose body ring is `ring` round at every joint but those `rings` names."""
    rings = {joint: (rings or {}).get(joint, ring) for joint in seams.JOINTS}
    tiers = {str(t): {'minimumOverlap': overlap} for t, overlap in zip(registry.TIERS, overlaps)}
    return {'tierOffsets': {str(t): offset for t, offset in seams.TIER_OFFSETS.items()},
            'joints': {joint: {'bodies': {'test': {'sides': {side: {'bodyRing': [rings[joint]] * seams.DIRECTIONS} for side in seams.sides(joint)},
                                                   'tiers': tiers}}} for joint in seams.JOINTS}}


def rig():
    """Bones far apart, the left arm along +X: its shoulder, elbow and wrist planes are x = 0, 0.3 and 0.55, their normal +X."""
    at = {'lbicep_g': (0, 0, 0), 'lforearm_g': (0.3, 0, 0), 'lhand_g': (0.55, 0, 0), 'rbicep_g': (0, 5, 0), 'rforearm_g': (-0.3, 5, 0),
          'rhand_g': (-0.55, 5, 0), 'neck_g': (0, -5, 1.6), 'torso_g': (0, -5, 1.1), 'lthigh_g': (0, -10, 0), 'lshin_g': (0, -10, -0.4),
          'lfoot_g': (0, -10, -0.8), 'rthigh_g': (0, -15, 0), 'rshin_g': (0, -15, -0.4), 'rfoot_g': (0, -15, -0.8)}
    bones = {name: np.eye(4) for name in at}
    for name, point in at.items():
        bones[name][:3, 3] = point
    return bones


def arm(start, end, radius):
    """A part along the left arm: {'v', 'f'} of an open tube."""
    v, f, _ = tube((start, 0, 0), (end, 0, 0), radius, around=32, along=8)
    return {'v': v, 'f': f}


def closed(start, end, radius, near='flat', far='flat', depth=0.03, shape=None):
    """A part along the left arm, {'v', 'f', 'added'}: a tube from x = `start` to `end`, each end closed as asked: `flat`
    (a lid), `dome` (a dome on past it, `shape` the depth and most as `split.lid` takes them), `cap` (`depth` back past
    it) or None (open)."""
    shape = shape or {}
    v, f, t = tube((start, 0, 0), (end, 0, 0), radius, around=32, along=8)
    own = len(f)
    for x, way, kind in ((start, -1.0, near), (end, 1.0, far)):
        point, normal = np.array((x, 0.0, 0.0)), np.array((way, 0.0, 0.0))
        if kind == 'cap':
            more = split.cap(v, t, f, len(v), point, -normal, depth, 2 * radius, bounded=False)
        elif kind is not None:
            more = split.lid(v, t, f, len(v), point, normal, 2 * radius, **({'dome': [(point, normal)], **shape} if kind == 'dome' else {}))
        else:
            continue
        v, t, f = np.concatenate([v, more[0]]), np.concatenate([t, more[1]]), np.concatenate([f, more[2]])
    return {'v': v, 'f': f, 'added': np.arange(len(f)) >= own}


def laid_out(part):
    """`part` as a bake lays it out: what the split added drawn on copies of the points it shares with the outfit's own faces."""
    v, f, added = part['v'], part['f'].copy(), part['added']
    shared = np.intersect1d(f[added].ravel(), f[~added].ravel())
    copy = np.arange(len(v))
    copy[shared] = len(v) + np.arange(len(shared))
    f[added] = copy[f[added]]
    return {**part, 'v': np.concatenate([v, v[shared]]), 'f': f}


def part(faces=1, size=4):
    """A baked part of `faces` triangles with flat maps of `size` texels a side."""
    v = np.array([(0.0, 0.0, 0.0), (0.1, 0.0, 0.0), (0.0, 0.1, 0.0)])
    f = np.tile([[0, 1, 2]], (faces, 1))
    relief = np.zeros((size, size, 3)); relief[..., 2] = 1.0
    none = np.zeros((size, size), bool)
    return {'v': v, 'f': f, 'uv': v[:, :2] * 5, 'n': np.tile([[0.0, 0.0, 1.0]], (3, 1)), 'rgb': np.full((size, size, 3), 0.5),
            'covered': ~none, 'relief': relief, 'closing': none, 'cap': none, 'padded': none, 'added': np.zeros(faces, bool),
            'domed': np.zeros(faces, bool), 'src': v, 'trimmed': np.full(faces, -1)}


class BakeTests(unittest.TestCase):
    def test_a_parts_texture_is_named_by_all_it_is_drawn_from_and_read_again_under_that_name(self):
        one = np.arange(6, dtype=float).reshape(2, 3)
        name = bake.digest(one, {'b': 1, 'a': one}, ('cloth', None), 0.3)
        self.assertEqual(name, bake.digest(one.copy(), {'a': one, 'b': 1}, ('cloth', None), 0.3))
        for other in ((one + 1, {'b': 1, 'a': one}, ('cloth', None), 0.3), (one.reshape(3, 2), {'b': 1, 'a': one}, ('cloth', None), 0.3),
                      (one.astype(np.float32), {'b': 1, 'a': one}, ('cloth', None), 0.3), (one, {'b': 2, 'a': one}, ('cloth', None), 0.3),
                      (one, {'b': 1, 'a': one}, ('leather', None), 0.3), (one, {'b': 1, 'a': one}, ('cloth', None), 0.4)):
            self.assertNotEqual(name, bake.digest(*other))
        self.assertNotEqual(bake.digest([1, 2], 3), bake.digest([1], 2, 3))  # where a list ends is part of the name
        drawn = []
        draw = lambda: drawn.append(1) or (np.full((4, 4), 170, np.uint8), np.full((4, 4), 4, np.uint8))
        self.assertEqual((bake.drawn(None, None, draw)[0][0, 0], len(drawn)), (170, 1))  # no cache: drawn, nothing kept
        with tempfile.TemporaryDirectory() as folder:
            cache = Path(folder) / 'cache'
            first = bake.drawn(cache, name, draw)
            again = bake.drawn(cache, name, lambda: self.fail('drawn again'))
            self.assertTrue(np.array_equal(first[0], again[0]) and np.array_equal(first[1], again[1]))
            self.assertEqual(([path.name for path in cache.iterdir()], len(drawn)), ([name + '.npz'], 2))
            (cache / (name + '.npz')).write_bytes(b'cut short')  # a file that cannot be read is drawn and written again
            self.assertEqual((bake.drawn(cache, name, draw)[0][0, 0], len(drawn)), (170, 3))
            bake.drawn(cache, name, lambda: self.fail('drawn again'))
            bake.drawn(cache, 'other', draw)
            self.assertEqual(len(drawn), 4)

    def test_a_bake_says_how_long_each_stage_took(self):
        said, ticks = [], iter([10.0, 12.5, 12.5, 20.0, 21.0])
        mark, seconds = bake.stages(said.append, clock=lambda: next(ticks))
        mark('split'); mark('nothing'); mark('reduce'); mark('split')  # a stage marked twice is added up
        self.assertEqual(seconds, {'split': 3.5, 'nothing': 0.0, 'reduce': 7.5})
        self.assertEqual(said, ['time: split 2.5 s', 'time: nothing 0.0 s', 'time: reduce 7.5 s', 'time: split 3.5 s'])

    def test_what_the_split_made_is_drawn_by_the_part_it_is_on(self):
        made = np.array([split.OWN, split.CLOSING, split.CAP, split.GUSSET, split.WALL, split.PADDED])
        flags = lambda name, key: bake.roles(name, made)[key].tolist()
        for name in ('chest', 'forel', 'shinr', 'legl', 'pelvis', 'bicepl'):  # the pelvis's strip is its own surface, like any face of the outfit
            self.assertEqual(flags(name, 'added'), [False, True, True, False, True, True])
            self.assertEqual(flags(name, 'domed'), [False, False, True, False, False, True])
            self.assertEqual(flags(name, 'padded'), [False, False, False, False, False, True])
        # a part like any other: its closing a closing, and its cap a cap with what grew from a pad's rim
        self.assertEqual(flags('shinr', 'closing'), [False, True, False, False, False, False])
        self.assertEqual(flags('shinr', 'cap'), [False, False, True, False, True, True])
        self.assertFalse(any(flags('shinr', 'under')))
        # a thigh's cap and its wall toward the other leg are shaded as the cloth round them, and so not drawn as a cap
        self.assertEqual(flags('legl', 'under'), [False, False, True, False, True, False])
        self.assertEqual(flags('legl', 'cap'), [False, False, False, False, False, True])
        self.assertEqual(flags('legl', 'closing'), [False, True, False, False, False, False])
        # a glove's cap at the wrist likewise, which a bare forearm shows at the cuff
        for name in ('handl', 'handr'):
            self.assertEqual(flags(name, 'under'), [False, False, True, False, False, False])
            self.assertEqual(flags(name, 'cap'), [False, False, False, False, True, True])
        # the pelvis's lids likewise, and so not drawn as closings
        self.assertEqual(flags('pelvis', 'under'), [False, True, False, False, False, False])
        self.assertFalse(any(flags('pelvis', 'closing')))
        self.assertEqual(flags('pelvis', 'cap'), [False, False, True, False, True, True])
        # and the chest's closings round each arm, which a lifted arm shows
        self.assertEqual(flags('chest', 'under'), [False, True, False, False, False, False])
        self.assertFalse(any(flags('chest', 'closing')))
        # an upper arm's cap is neither a cap nor a closing: it is drawn as read, as the first outfit was seen
        for name in bake.ARMHOLE:
            self.assertEqual(flags(name, 'closing'), [False, True, False, False, False, False])
            self.assertEqual(flags(name, 'cap'), [False, False, False, False, True, True])
            self.assertFalse(any(flags(name, 'under')))

    def test_points_go_back_to_the_generated_meshs_axes(self):
        self.assertEqual(bake.to_field(np.array([(1.0, 2.0, 3.0)])).tolist(), [[-1.0, 3.0, 2.0]])

    def test_baked_parts_are_kept_and_read_back(self):
        with tempfile.TemporaryDirectory() as folder:
            parts = {'chest': part(3), 'pelvis': part(2, size=8)}
            bake.store(parts, Path(folder) / 'kept')
            back = bake.stored(Path(folder) / 'kept')
            self.assertEqual(sorted(back), ['chest', 'pelvis'])
            for name in parts:
                self.assertEqual(set(back[name]), set(bake.KEYS))
                self.assertTrue(all(np.array_equal(back[name][key], parts[name][key]) for key in bake.KEYS))
            with self.assertRaises(ValueError):
                bake.stored(Path(folder) / 'nothing')
            # the folder used again for an outfit with fewer parts: the pelvis's file is still there, and is not read
            bake.store({'chest': part(2)}, Path(folder) / 'kept')
            self.assertTrue((Path(folder) / 'kept' / 'pelvis.npz').is_file())
            again = bake.stored(Path(folder) / 'kept')
            self.assertEqual((list(again), len(again['chest']['f'])), (['chest'], 2))
            np.savez(Path(folder) / 'kept' / 'shinl.npz', v=np.zeros((3, 3)))  # a file of another kind beside them is not a part
            self.assertEqual(list(bake.stored(Path(folder) / 'kept')), ['chest'])
            listing = Path(folder) / 'kept' / bake.KEPT
            listing.write_text(json.dumps({'schemaVersion': 1, 'kind': bake.KEPT_KIND, 'parts': ['chest', 'shinl']}))  # listed, and no part
            with self.assertRaises(ValueError):
                bake.stored(Path(folder) / 'kept')
            listing.write_text(json.dumps({'schemaVersion': 1, 'kind': bake.KEPT_KIND, 'parts': ['chest', 'forel']}))  # listed, and not there
            with self.assertRaises(ValueError):
                bake.stored(Path(folder) / 'kept')
            listing.unlink()  # files without a list: a store that stopped halfway, or a folder of something else
            with self.assertRaises(ValueError):
                bake.stored(Path(folder) / 'kept')

    def written(self, folder, parts):
        tinted = {name: (np.full(one['covered'].shape, 170), np.full(one['covered'].shape, export.LAYERS['cloth1'])) for name, one in parts.items()}
        return bake.write(folder, parts, tinted, {'torso_g': np.eye(4), 'pelvis_g': np.eye(4)}, 'pmh0', 332)

    def test_an_outfit_is_written_as_models_tints_maps_and_materials(self):
        with tempfile.TemporaryDirectory() as folder:
            models = self.written(folder, {'chest': part(), 'pelvis': part()})
            self.assertEqual(models, {'chest': 'pmh0_chest332', 'pelvis': 'pmh0_pelvis332'})
            self.assertEqual(sorted(path.name for path in (Path(folder) / 'ascii').iterdir()),
                             ['pmh0_chest332.mdl', 'pmh0_chest332.plt', 'pmh0_pelvis332.mdl', 'pmh0_pelvis332.plt'])
            self.assertEqual(sorted(path.name for path in (Path(folder) / 'resources').iterdir()),
                             ['pmh0_chest332.mtr', 'pmh0_chest332.plt', 'pmh0_chest332n.tga', 'pmh0_chest332r.tga', 'pmh0_pelvis332.mtr', 'pmh0_pelvis332.plt', 'pmh0_pelvis332n.tga',
                              'pmh0_pelvis332r.tga'])  # a roughness map each: the game draws a tinted part by it, not by a number
            shades, layers = export.read_tint((Path(folder) / 'resources' / 'pmh0_chest332.plt').read_bytes())
            self.assertTrue((shades == 170).all() and (layers == export.LAYERS['cloth1']).all())

    def test_holes_and_crumbs_of_the_generated_outfit_are_found_and_separate_pieces_are_not_faults(self):
        v, f = box(side=0.1)
        self.assertEqual(bake.surface(v, f), {'holes': [], 'debris': [], 'pieces': 1})
        seamed = f.copy()
        seamed[:2] = np.where(f[:2] < 4, f[:2] + 8, f[:2])  # a texture seam: two faces on their own copies of four vertices
        self.assertEqual(bake.surface(np.concatenate([v, v[:4]]), seamed), {'holes': [], 'debris': [], 'pieces': 1})
        self.assertTrue(np.allclose(bake.surface(v, f[1:])['holes'], [0.2 + 0.1 * np.sqrt(2)]))  # one face gone: an opening round its edges
        pin = box((0.0, 0.0, 0.05), 0.001)  # an opening under `HOLE` round, on a crumb set into the surface
        self.assertEqual(bake.surface(*joined((v, f), (pin[0], pin[1][1:]))), {'holes': [], 'debris': [], 'pieces': 2})
        crumb, pad, sunk = box((0.1, 0.0, 0.0), 0.01), box((0.085, 0.0, 0.0), 0.05), box((0.05, 0.0, 0.0), 0.01)
        found = bake.surface(*joined((v, f), crumb))
        self.assertTrue(found['holes'] == [] and found['pieces'] == 2 and np.allclose(found['debris'], [6 * 0.01 ** 2]))
        self.assertEqual(bake.surface(*joined((v, f), pad))['debris'], [])  # a pad standing off the rest is a piece, not debris
        self.assertEqual(bake.surface(*joined((v, f), sunk))['debris'], [])  # a crumb set into the rest touches it

    def test_crumbs_of_the_generated_outfit_are_dropped_before_it_is_baked_and_much_debris_is_left_for_the_gate(self):
        v, f = box(side=0.1)
        crumb, pad = box((0.1, 0.0, 0.0), 0.01), box((0.085, 0.0, 0.0), 0.05)
        flags, areas, pieces = bake.loose(*joined((v, f), pad, crumb))
        self.assertEqual((flags.tolist(), pieces), ([False] * 24 + [True] * 12, 3))
        self.assertTrue(np.allclose(areas, [6 * 0.01 ** 2]))
        kept_v, kept_f, dropped = bake.swept(*joined((v, f), crumb, pad))
        self.assertTrue(np.allclose(dropped, [6 * 0.01 ** 2]))
        self.assertTrue(np.array_equal(kept_v, np.concatenate([v, pad[0]])) and np.array_equal(kept_f, np.concatenate([f, pad[1] + 8])))  # only the vertices left in use
        self.assertEqual(bake.surface(kept_v, kept_f)['debris'], [])
        # read at the body's size: half as large, the outfit's crumb is one at twice its size
        small = joined((v, f), crumb)
        self.assertTrue(np.allclose(bake.swept(small[0] / 2, small[1], 2.0)[2], [6 * 0.01 ** 2]))
        whole = bake.swept(v, f)
        self.assertTrue(np.array_equal(whole[0], v) and np.array_equal(whole[1], f) and whole[2] == [])  # nothing loose: as it was
        # more loose than a crumb is: left in, for the gate to fail and the export to be looked at
        many = joined((v, f), *[box((0.1 + 0.02 * k, 0.0, 0.0), 0.01) for k in range(2)])
        with mock.patch.object(bake, 'SWEPT', 6 * 0.01 ** 2 * 1.5):
            self.assertEqual((len(bake.swept(*many)[1]), bake.swept(*many)[2]), (len(many[1]), []))
        self.assertEqual(len(bake.surface(*many)['debris']), 2)

    def test_faces_the_client_would_show_a_hole_at_are_turned_out_and_what_is_left_fails(self):
        bones = rig()
        sleeve = closed(0.05, 0.3, 0.04)  # along the left arm's bone, closed flat at both ends
        normals = np.tile([[0.0, 0.0, 1.0]], (len(sleeve['v']), 1))
        self.assertEqual(bake.facing({'bicepl': sleeve}, bones), ({'bicepl': 0.0}, []))
        faces, kept, turned = bake.faced_out('bicepl', sleeve['v'], sleeve['f'], normals, bones)
        self.assertTrue(np.array_equal(faces, sleeve['f']) and np.array_equal(kept, normals) and turned == 0)
        inward = sleeve['f'].copy(); inward[[3, 4, 40]] = inward[[3, 4, 40]][:, ::-1]  # three of its faces wound to face the arm
        report, failures = bake.facing({'bicepl': {**sleeve, 'f': inward}}, bones)
        self.assertGreater(report['bicepl'], bake.FACING)
        self.assertRegex(failures[0], r'^bicepl: 3 faces of \d+\.\d cm² turned in with nothing behind them, where the client shows a hole$')
        faces, kept, turned = bake.faced_out('bicepl', sleeve['v'], inward, normals, bones)
        self.assertTrue(np.array_equal(faces, sleeve['f']) and turned == 3)
        self.assertTrue(np.array_equal(kept, normals))  # every vertex of theirs is another face's too: no normal is turned
        # a vertex only such faces use has its normal turned with them
        own = np.concatenate([sleeve['v'], sleeve['v'][inward[3]]])
        alone = inward.copy(); alone[3] = len(sleeve['v']) + np.arange(3)
        _, kept, turned = bake.faced_out('bicepl', own, alone, np.tile([[0.0, 0.0, 1.0]], (len(own), 1)), bones)
        self.assertTrue(turned == 3 and (kept[-3:] == [0.0, 0.0, -1.0]).all() and (kept[:-3] == [0.0, 0.0, 1.0]).all())
        # two faces that share a vertex of their own, turned out in two reads: its normal is turned once both are
        beside = next(k for k in range(len(sleeve['f'])) if k != 3 and len(np.intersect1d(sleeve['f'][3], sleeve['f'][k])))
        theirs = np.unique(sleeve['f'][[3, beside]])
        copy = np.arange(len(sleeve['v'])); copy[theirs] = len(sleeve['v']) + np.arange(len(theirs))
        apart = sleeve['f'].copy(); apart[[3, beside]] = copy[apart[[3, beside]]]
        both = np.concatenate([sleeve['v'], sleeve['v'][theirs]])
        reads = iter([[3], [beside], []])
        with mock.patch.object(bake.measure, 'seen_through', side_effect=lambda v, f, within: np.isin(np.arange(len(f)), next(reads))):
            _, kept, turned = bake.faced_out('bicepl', both, apart, np.tile([[0.0, 0.0, 1.0]], (len(both), 1)), bones)
        self.assertTrue(turned == 2 and (kept[len(sleeve['v']):] == [0.0, 0.0, -1.0]).all() and (kept[:len(sleeve['v'])] == [0.0, 0.0, 1.0]).all())
        # a part with no bone of two ends is read round its middle, and copies of its vertices (a layout's) do not move it
        copied = np.concatenate([sleeve['v'], sleeve['v'][:7]])
        again = sleeve['f'].copy(); again[again < 7] += len(sleeve['v'])
        again[0] = sleeve['f'][0]  # both a vertex and its copy are used
        middle = bake.within(bones, 'pelvis', sleeve['v'], sleeve['f'])
        self.assertTrue(np.allclose(bake.within(bones, 'pelvis', copied, again), middle, atol=1e-9) and middle.shape == (len(again), 3))
        self.assertFalse(np.allclose(copied[np.unique(again)].mean(axis=0), middle[0], atol=1e-6))  # counted per vertex it would
        # a face turned out may bare another: it is read until none is found, each read one face here
        bared = iter([[3], [4], [40], [7], [9], []])
        with mock.patch.object(bake.measure, 'seen_through', side_effect=lambda v, f, within: np.isin(np.arange(len(f)), next(bared))):
            faces, _, turned = bake.faced_out('bicepl', sleeve['v'], sleeve['f'], normals, bones)
        self.assertEqual(turned, 5)
        self.assertTrue(np.array_equal(faces[[3, 4, 40, 7, 9]], sleeve['f'][[3, 4, 40, 7, 9]][:, ::-1]) and next(bared, None) is None)
        # the body's own skin beside the outfit is neither read nor counted as what lies under a face
        skin = arm(0.05, 0.3, 0.03)
        worn = {'v': np.concatenate([sleeve['v'], skin['v']]), 'f': np.concatenate([inward, skin['f'][:, ::-1] + len(sleeve['v'])]),
                'skin': np.arange(len(inward) + len(skin['f'])) >= len(inward)}
        self.assertEqual(bake.facing({'bicepl': worn}, bones)[0], report)
        # a part with a bone of one end, or on a rig without its bone, is read round its own middle
        v, f = box(side=0.1)
        f = f.copy(); f[5] = f[5][::-1]
        for name, some in (('pelvis', bones), ('chest', {})):
            self.assertEqual(len(bake.facing({name: {'v': v, 'f': f}}, some)[1]), 1)
            self.assertEqual(bake.faced_out(name, v, f, np.zeros((8, 3)), some)[2], 1)

    def test_an_end_at_a_torso_opening_is_asked_to_run_no_deeper_than_the_torso_stands_over_the_joint(self):
        bones, terms = rig(), contract(rings={'shoulder': 0.08})
        short = {'bicepl': arm(-0.025, 0.3, 0.075)}  # 2.5 cm past the shoulder plane, where tier 2 asks 4 cm
        self.assertEqual(bake.ends(short, bones, 'test', 2, terms)[1],
                         ['bicepl at the shoulder: 2.5 cm past the plane, short of the tier 2 overlap of 4.0 cm'])
        # the torso's top crosses the arm's axis 3 cm past the plane: an end runs no deeper than that, less the gaps
        top = {'v': np.array([(-0.03, -0.2, -0.2), (-0.03, 0.2, -0.2), (-0.03, 0.2, 0.2), (-0.03, -0.2, 0.2)]), 'f': np.array([(0, 1, 2), (0, 2, 3)])}
        arms = lambda chest: [failure for failure in bake.ends({**short, 'chest': chest}, bones, 'test', 2, terms)[1] if failure.startswith('bicepl')]
        self.assertEqual(arms(top), [])
        report = bake.ends({**short, 'chest': top}, bones, 'test', 2, terms)[0]
        self.assertAlmostEqual(report['shoulder']['l']['under']['overlap'], 0.03 - split.SEAT_GAP - bake.ROOM_SLACK, places=4)
        self.assertEqual(len(arms(arm(-0.3, 0.0, 0.2))), 1)  # a torso round the axis asks it all

    def test_each_end_is_held_to_its_tiers_envelope_and_overlap_at_its_joint(self):
        # the elbow's body ring 4 cm round: tier 2 envelope 6.5 cm, overlap 4 cm; tier 3 overlap 6 cm
        bones, terms = rig(), contract(rings={'shoulder': 0.08, 'wrist': 0.01})
        fit = {'forel': arm(0.25, 0.6, 0.06), 'bicepl': arm(-0.05, 0.3, 0.075)}  # the forearm 5 cm past the elbow plane, 6 cm round
        report, failures = bake.ends(fit, bones, 'test', 2, terms)
        self.assertEqual(failures, [])
        elbow = report['elbow']['l']
        self.assertEqual((elbow['under']['part'], elbow['under']['tier'], elbow['under']['overlap']), ('forel', 2, 0.04))
        self.assertAlmostEqual(elbow['under']['past'], 0.05, places=3)
        self.assertAlmostEqual(elbow['under']['outside'], -0.005, places=3)
        self.assertEqual((elbow['over']['part'], elbow['over']['tier']), ('bicepl', 2))
        self.assertTrue(-0.01 < elbow['over']['inside'] < 0)
        self.assertEqual((report['shoulder']['l']['under']['part'], report['wrist']['l']['over']['part']), ('bicepl', 'forel'))
        self.assertEqual((report['neck']['c'], report['elbow']['r'], report['knee']['l']), ({}, {}, {}))  # no part at the other ends
        json.dumps(report)
        # an under end too wide for the tier's envelope, or too short past the plane; the tier it does meet
        report, failures = bake.ends({**fit, 'forel': arm(0.25, 0.6, 0.07)}, bones, 'test', 2, terms)
        self.assertEqual(failures, ['forel at the elbow: up to 0.5 cm outside the tier 2 envelope, in 16 of 16 directions'])
        self.assertIsNone(report['elbow']['l']['under']['tier'])  # tier 3 is wide enough, but asks 6 cm past the plane
        report, failures = bake.ends({**fit, 'forel': arm(0.275, 0.6, 0.042)}, bones, 'test', 2, terms)
        self.assertEqual(failures, ['forel at the elbow: 2.5 cm past the plane, short of the tier 2 overlap of 4.0 cm'])
        self.assertEqual(report['elbow']['l']['under']['tier'], 0)
        # an over end narrower than the envelope, or closed
        report, failures = bake.ends({**fit, 'bicepl': arm(-0.05, 0.3, 0.055)}, bones, 'test', 2, terms)
        self.assertEqual(failures, ['bicepl at the elbow: up to 1.0 cm inside the tier 2 envelope, in 16 of 16 directions'])
        self.assertEqual(report['elbow']['l']['over']['tier'], 1)
        plug = arm(-0.05, 0.3, 0.005)
        closed = {'v': np.concatenate([fit['bicepl']['v'], plug['v']]), 'f': np.concatenate([fit['bicepl']['f'], plug['f'] + len(fit['bicepl']['v'])])}
        self.assertEqual(bake.ends({**fit, 'bicepl': closed}, bones, 'test', 2, terms)[1],
                         ['bicepl at the elbow: up to 6.0 cm inside the tier 2 envelope, in 16 of 16 directions'])
        dome = {**closed, 'added': np.arange(len(closed['f'])) >= len(fit['bicepl']['f'])}  # what closes it is the split's: not the end
        self.assertEqual(bake.ends({**fit, 'bicepl': dome}, bones, 'test', 2, terms)[1], [])
        # a part that does not reach its joint, unless the body's own part ends there
        self.assertEqual(bake.ends({**fit, 'forel': arm(0.32, 0.6, 0.06)}, bones, 'test', 2, terms)[1], ['forel does not reach the elbow plane'])
        bracer = arm(0.32, 0.5, 0.06)
        report, failures = bake.ends({**fit, 'forel': {**bracer, 'skin': np.zeros(len(bracer['f']), bool)}}, bones, 'test', 2, terms)
        self.assertEqual((failures, 'under' in report['elbow']['l']), ([], False))
        # the body's skin beside the outfit's faces is not measured
        skin = arm(0.2, 0.5, 0.09)
        worn = {'v': np.concatenate([fit['forel']['v'], skin['v']]), 'f': np.concatenate([fit['forel']['f'], skin['f'] + len(fit['forel']['v'])]),
                'skin': np.r_[np.zeros(len(fit['forel']['f']), bool), np.ones(len(skin['f']), bool)]}
        self.assertEqual(bake.ends({**fit, 'forel': worn}, bones, 'test', 2, terms), bake.ends(fit, bones, 'test', 2, terms))
        # a torso piece is not measured at its openings; a body the contract has no rings of is not measured at all
        self.assertNotIn('over', bake.ends({'chest': arm(-0.3, 0.0, 0.2), 'bicepl': arm(-0.05, 0.3, 0.05)}, bones, 'test', 2, terms)[0]['shoulder']['l'])
        self.assertIsNone(bake.ends(fit, bones, 'pmh0', 2, terms))

    def test_the_bodys_own_skin_beside_a_sleeve_never_stands_out_through_it(self):
        # the body's upper arm 4 cm round from x = 0.05 to 0.3; a sleeve to x = 0.2, the arm below its hem kept beside it
        arm_ = closed(0.05, 0.3, 0.04, near=None, far=None)

        def sleeve(radius, dome=False):
            cloth = closed(0.05, 0.25, radius, near=None, far=None)
            below = arm_['f'][arm_['v'][arm_['f']][:, :, 0].min(axis=1) > 0.18]
            return {'v': np.concatenate([cloth['v'], arm_['v']]), 'f': np.concatenate([cloth['f'], below + len(cloth['v'])]),
                    'added': np.arange(len(cloth['f']) + len(below)) < len(cloth['f']) * dome,
                    'skin': np.arange(len(cloth['f']) + len(below)) >= len(cloth['f'])}
        bones = rig()
        report, failures = bake.through({'bicepl': sleeve(0.05), 'chest': part()}, bones)
        self.assertEqual((report, failures), ({'bicepl': 0.0}, []))  # the arm under the sleeve; a part with no skin is not measured
        for dome in (False, True):  # the sleeve's own cloth, or a dome closing it: the client draws both over the arm
            report, failures = bake.through({'bicepl': sleeve(0.035, dome)}, bones)
            self.assertAlmostEqual(report['bicepl'], 0.005, places=3)
            self.assertEqual(failures, ["bicepl: the body's own skin beside it stands up to 0.5 cm out through the outfit over it"])
        inward = sleeve(0.05)
        inward['f'] = np.where(~inward['skin'][:, None], inward['f'][:, ::-1], inward['f'])  # its cloth turned in: the client draws none of it
        report, failures = bake.through({'bicepl': inward}, bones)
        self.assertEqual(report, {'bicepl': 0.0})
        self.assertEqual(len(failures), 1)
        self.assertRegex(failures[0], r"^bicepl: \d+ points of the body's own skin beside it are covered only by faces turned in")
        self.assertEqual(bake.gates({'bicepl': part()}, {}, Path('nowhere'), skin=(report, failures))['through'], report)

    def test_every_end_is_closed_domed_and_hidden_as_the_body_stands_and_turned(self):
        bones, terms = rig(), {**contract(), 'designBend': 'p95', 'ends': dict(seams.ENDS)}
        for joint in terms['joints'].values():
            joint['bodies']['test']['bend'] = {'p95': 90.0}
        gate = lambda parts, **given: bake.hidden(parts, bones, 'test', terms, **given)
        sleeve = closed(0.05, 0.3, 0.06, near=None, far='dome')  # the upper arm, domed on past the elbow's plane (x = 0.3)
        cuff = closed(0.3, 0.5, 0.04, near='cap', far=None)  # the forearm, its end 3 cm back into the sleeve, 4 cm round
        report, failures = gate({'bicepl': sleeve, 'forel': cuff})
        self.assertEqual(failures, [])
        elbow = report['elbow']['l']
        self.assertEqual((elbow['over'], elbow['under'], elbow['open']), ('bicepl', 'forel', {'bicepl': 0.0, 'forel': 0.0}))
        self.assertAlmostEqual(elbow['rise'], split.DOME_DEPTH * 0.06, places=3)  # the pole 30% of the sleeve's radius past its rim
        self.assertAlmostEqual(elbow['past'], elbow['rise'], places=6)
        self.assertEqual((elbow['rest'], elbow['bent']), (0.0, 0.0))  # the end within its own ring turns within it
        json.dumps(report)
        self.assertIsNone(bake.hidden({'forel': cuff}, bones, 'pmh0', terms))  # a body the contract has no rings of
        # an end left open
        report, failures = gate({'bicepl': closed(0.05, 0.3, 0.06, near=None, far=None), 'forel': cuff})
        self.assertEqual(len(failures), 1)
        self.assertTrue(failures[0].startswith('bicepl at the elbow: open on its plane, 37.'), failures)
        # closed by a flat lid on the plane: closed, but not domed
        self.assertEqual(gate({'bicepl': closed(0.05, 0.3, 0.06, near=None, far='flat'), 'forel': cuff})[1],
                         ['bicepl at the elbow: not domed, what closes it stands no farther past the plane than its rim'])
        # a dome deeper past its rim than the contract lets it stand
        deep = closed(0.05, 0.3, 0.06, near=None, far='dome', shape={'depth': 1.0, 'most': 0.05})
        self.assertEqual(gate({'bicepl': deep, 'forel': cuff})[1], ["bicepl at the elbow: its dome stands 5.0 cm past its rim, over the contract's 2.0 cm"])
        # an end running back past what is over it as the body stands: 6 cm into a sleeve 3 cm long
        report, failures = gate({'bicepl': closed(0.27, 0.3, 0.06, far='dome'), 'forel': closed(0.3, 0.5, 0.04, near='cap', far=None, depth=0.06)})
        self.assertIn('forel at the elbow: what the split added stands up to 3.0 cm outside the outfit as the body stands', failures)
        # an end 8 cm long, beyond its 4 cm ring: inside the sleeve standing, 2 cm out of it with the forearm swung forward 90 degrees
        report, failures = gate({'bicepl': sleeve, 'forel': closed(0.3, 0.5, 0.04, near='cap', far=None, depth=0.08)})
        self.assertEqual(report['elbow']['l']['rest'], 0.0)
        self.assertEqual(len(failures), 1)
        self.assertTrue(failures[0].startswith("forel at the elbow: turned forward by 90 degrees of the design bend's 90, its end stands up to 2."), failures)
        # a hand left to the body: the forearm's end at the wrist is closed and domed as any over end, with no part under it
        long = closed(0.3, 0.55, 0.04, near='cap', far='dome')
        report, failures = gate({'bicepl': sleeve, 'forel': long}, left={'handl'})
        self.assertEqual(failures, [])
        wrist = report['wrist']['l']
        self.assertEqual((wrist['over'], wrist['under'], wrist['open'], wrist['rest'], wrist['bent']), ('forel', 'handl', {'forel': 0.0}, None, None))
        self.assertGreater(wrist['rise'], 0.0)
        self.assertEqual(gate({'bicepl': sleeve, 'forel': closed(0.3, 0.55, 0.04, near='cap', far=None)}, left={'handl'})[1][0][:38],
                         'forel at the wrist: open on its plane,')
        # under a slot left to the body, an end is measured against the body's own skin, when it is given
        glove = {'handl': closed(0.55, 0.7, 0.03, near='cap', far=None)}
        self.assertIsNone(gate(glove, left={'forel'})[0]['wrist']['l']['rest'])
        skin = closed(0.4, 0.6, 0.035)
        self.assertEqual(gate(glove, left={'forel'}, skin={'forel': (skin['v'], skin['f'])})[0]['wrist']['l']['rest'], 0.0)
        # parts as a bake lays them out read as they did split: a rim is the outfit's own however its points are copied
        self.assertEqual(gate({'bicepl': laid_out(sleeve), 'forel': laid_out(cuff)}), gate({'bicepl': sleeve, 'forel': cuff}))
        narrow = closed(0.4, 0.6, 0.028)  # the glove's rim 2 mm out of the skin, what closes it within
        for handl in (glove['handl'], laid_out(glove['handl'])):
            self.assertEqual(gate({'handl': handl}, left={'forel'}, skin={'forel': (narrow['v'], narrow['f'])})[0]['wrist']['l']['rest'], 0.0)

    def test_the_gates_tell_budgets_names_and_missing_textures(self):
        with tempfile.TemporaryDirectory() as folder:
            parts = {'chest': part(), 'pelvis': part()}
            models, resources = self.written(folder, parts), Path(folder) / 'resources'
            report = bake.gates(parts, models, resources, packs=[Path(folder) / 'pack'])
            self.assertEqual((report['passed'], report['failures']), (True, []))
            self.assertEqual(report['triangles'], {'chest': 1, 'pelvis': 1, 'outfit': 2})
            self.assertEqual(report['texels'], {'chest': 4, 'pelvis': 4})
            self.assertEqual(report['notBuilt'], list(bake.NOT_BUILT))  # a pass here is not the plan's
            json.dumps(report)
            # with what the generated outfit holds of holes and debris, those are gated too
            clean, faulty = {'holes': [], 'debris': [], 'pieces': 1}, {'holes': [0.012], 'debris': [0.0004], 'pieces': 2}
            report = bake.gates(parts, models, resources, whole=clean)
            self.assertEqual((report['passed'], report['surface'], bake.WHOLE in report['notBuilt']), (True, clean, False))
            self.assertEqual(bake.gates(parts, models, resources, whole=faulty)['failures'],
                             ['the generated outfit: an opening 1.2 cm round', 'the generated outfit: a piece of 4.0 cm² standing apart from the rest'])
            json.dumps(bake.gates(parts, models, resources, whole=faulty))
            # with what `facing` found, faces the client would show a hole at are gated too
            report = bake.gates(parts, models, resources, faced=({'chest': 0.0004, 'pelvis': 0.0}, ['chest: 3 faces turned in']))
            self.assertEqual((report['passed'], report['failures'], report['facing']), (False, ['chest: 3 faces turned in'], {'chest': 0.0004, 'pelvis': 0.0}))
            self.assertNotIn('facing', bake.gates(parts, models, resources))
            # with what `ends` found, the seam contract is gated too
            report = bake.gates(parts, models, resources, joined=({'elbow': {}}, ['forel does not reach the elbow plane']))
            self.assertEqual((report['passed'], report['failures'], report['seams']), (False, ['forel does not reach the elbow plane'], {'elbow': {}}))
            self.assertEqual(report['notBuilt'], [gate for gate in bake.NOT_BUILT if gate != bake.SEAM])
            # budgets: a chest may have more triangles than another part, and the outfit has a budget of its own
            fat = {'chest': part(bake.BUDGET['chest']), 'pelvis': part(bake.BUDGET['slot'])}
            self.assertTrue(bake.gates(fat, models, resources)['passed'])
            fat['pelvis'] = part(bake.BUDGET['slot'] + 1)
            self.assertEqual(bake.gates(fat, models, resources)['failures'],
                             [f'pelvis: {bake.BUDGET["slot"] + 1} triangles, over the budget of {bake.BUDGET["slot"]}'])
            many = {name: part(bake.BUDGET['slot']) for name in ('pelvis', 'legl', 'legr', 'shinl', 'shinr', 'footl', 'footr', 'bicepl', 'bicepr',
                                                                  'forel', 'forer', 'handl', 'handr', 'shol')}
            failures = bake.gates(many, {}, resources)['failures']
            self.assertEqual(failures, [f'the outfit: {14 * bake.BUDGET["slot"]} triangles, over the budget of {bake.BUDGET["outfit"]}'])
            wide = {'chest': part(size=2 * bake.BUDGET['texture'])}
            self.assertIn('over the budget of 1024', bake.gates(wide, {}, resources)['failures'][0])
            # a triangle with two corners at one point, which the model compiler would drop
            pinched = part(2)
            pinched['v'] = np.concatenate([pinched['v'], pinched['v'][2:] + bake.POINT / 2])
            pinched['f'] = np.array([[0, 1, 2], [1, 2, 3]])
            self.assertEqual(bake.gates({'chest': part(), 'pelvis': pinched}, models, resources)['failures'],
                             ['pelvis: 1 triangles with two corners at one point, which the model compiler drops'])
            # a name a pack already holds
            (Path(folder) / 'pack').mkdir()
            (Path(folder) / 'pack' / 'pmh0_pelvis332.mdl').write_text('')
            self.assertEqual(bake.gates(parts, models, resources, packs=[Path(folder) / 'pack'])['failures'],
                             [f'pmh0_pelvis332: {Path(folder) / "pack"} holds a model of that name'])
            # texture closure: the tint texture, the material file, and the map it names
            (resources / 'pmh0_chest332.plt').unlink()
            (resources / 'pmh0_chest332n.tga').unlink()
            (resources / 'pmh0_pelvis332.mtr').unlink()
            self.assertEqual(bake.gates(parts, models, resources)['failures'],
                             ['pmh0_chest332: no tint texture', 'pmh0_chest332: its material file names pmh0_chest332n, which is not there',
                              'pmh0_pelvis332: no material file'])

    def test_a_slot_left_to_the_body_gets_no_part_and_a_shared_one_the_bodys_skin(self):
        from .test_bodyskin import arm
        bone = lambda *place: np.block([[np.eye(3), np.array(place, float)[:, None]], [np.zeros((1, 3)), np.ones((1, 1))]])
        bones = {'torso_g': np.eye(4), 'lbicep_g': bone(0, 0, 1.5), 'lforearm_g': bone(0, 0, 1.2), 'lhand_g': bone(0, 0, 0.9)}
        parts = {'chest': part(), 'bicepl': part(), 'handl': part()}
        document, said = {'model': 'outfit', 'materials': [], 'bare': ['forearm'], 'skin': ['bicep']}, []
        self.assertEqual((bake.left_to_body(document), bake.shared_with_body(document)), ({'forel', 'forer'}, {'bicepl', 'bicepr'}))
        # bare hands: no hand part, and no end is laid under the body's skin for them (the forearm is over the hand)
        self.assertEqual(bake.left_to_body({'bare': ['hand']}), {'handl', 'handr'})
        self.assertEqual(bake.bare_joints({'left': ['handl', 'handr']}), set())
        self.assertEqual(bake.bare_joints({'left': ['forel', 'forer', 'handl', 'handr']}), {('wrist', 'l'), ('wrist', 'r')})
        self.assertEqual(bake.left_to_body({'bare': ['shin', 'foot']}), {'shinl', 'shinr', 'footl', 'footr'})
        self.assertEqual(bake.bare_joints({'left': ['shinl', 'shinr']}), {('ankle', 'l'), ('ankle', 'r')})  # a boot's top under a bare shin
        self.assertEqual(bake.bare_joints({'left': ['chest']}), {('waist', 'c')})  # trousers' waistband under a bare chest
        with mock.patch.object(bodyskin, 'body_part', lambda pack, maps, body, name, rig: arm()):
            out = bake.skinned(parts, document, 'pack', 'maps', 'pmh0', bones, say=said.append)
            self.assertEqual(bake.skinned(parts, {'model': 'outfit', 'materials': []}, 'pack', None, 'pmh0', bones), parts)  # a brief that names neither
        self.assertEqual(sorted(out), ['bicepl', 'chest', 'handl'])
        self.assertTrue(said[0].startswith("bicepl: 384 of the body's 384 faces"), said)
        arm_part = out['bicepl']
        self.assertEqual((int(arm_part['skin'].sum()), len(arm_part['rgb']), 'skin' in out['chest']), (len(arm()['f']), 8, False))
        with tempfile.TemporaryDirectory() as folder:
            bake.store(out, Path(folder) / 'kept')  # kept with what the skin adds, and read back with it
            back = bake.stored(Path(folder) / 'kept')
            self.assertTrue(all(np.array_equal(back['bicepl'][key], arm_part[key]) for key in bake.KEYS + bodyskin.KEYS))
            self.assertEqual(set(back['chest']), set(bake.KEYS))
            # the tint: the body's own shade and skin layer on its texels, the outfit's elsewhere
            cloth = (np.full((8, 8), 170), np.full((8, 8), export.LAYERS['cloth1']))
            shades, layers = bodyskin.tinted(arm_part, cloth)
            at = arm_part['skin_at']
            self.assertTrue((layers[at] == export.LAYERS['skin']).all() and (layers[~at] == export.LAYERS['cloth1']).all())
            self.assertTrue(np.array_equal(shades[at], arm_part['skin_tint'][..., 0][at]) and (shades[~at] == 170).all())
            self.assertIs(bodyskin.tinted(out['chest'], cloth), cloth)
            # written: its normal map whole, and its roughness as a map the material binds
            tinted = {name: bodyskin.tinted(one, (np.full(one['covered'].shape, 170), np.full(one['covered'].shape, export.LAYERS['cloth1'])))
                      for name, one in out.items()}
            models = bake.write(folder, out, tinted, bones, 'pmh0', 332)
            resources = Path(folder) / 'resources'
            self.assertEqual(bodyskin.image((resources / 'pmh0_bicepl332n.tga').read_bytes()).shape, (8, 8, 3))
            self.assertEqual(bodyskin.image((resources / 'pmh0_chest332n.tga').read_bytes()).shape, (4, 4, 3))  # whole too: no longer at half size
            rough = bodyskin.image((resources / 'pmh0_bicepl332r.tga').read_bytes())[..., 0]
            self.assertTrue(np.allclose(rough, arm_part['skin_rough'] / 255, atol=1 / 255))
            self.assertEqual(bodyskin.material(resources, 'pmh0_bicepl332'), {'normal': 'pmh0_bicepl332n', 'rough': 'pmh0_bicepl332r', 'roughness': 0.0})
            self.assertIn('Roughness 0\n', (resources / 'pmh0_bicepl332.mtr').read_text())
            even = bodyskin.image((resources / 'pmh0_chest332r.tga').read_bytes())[..., 0]  # a part with no skin: one roughness, as a map
            self.assertTrue(even.shape == (texture.EVEN, texture.EVEN) and np.allclose(even, texture.ROUGHNESS, atol=1 / 255))
            self.assertTrue(bake.gates(out, models, resources)['passed'])
            (resources / 'pmh0_bicepl332r.tga').unlink()
            self.assertEqual(bake.gates(out, models, resources)['failures'], ['pmh0_bicepl332: its material file names pmh0_bicepl332r, which is not there'])

    def test_a_run_compiles_the_models_it_wrote_and_no_others(self):
        with tempfile.TemporaryDirectory() as folder:
            output, parts, compiled = Path(folder) / 'out', {'chest': part(), 'pelvis': part()}, []
            bake.store(parts, Path(folder) / 'kept')
            (output / 'ascii').mkdir(parents=True)
            (output / 'ascii' / 'pmh0_chest331.mdl').write_text('')  # an earlier run's, under another number
            (output / 'ascii' / 'pmh0_shol332.mdl').write_text('')  # and a part this outfit does not have
            tinted = {name: (np.full((4, 4), 170), np.full((4, 4), export.LAYERS['cloth1'])) for name in parts}
            with mock.patch.object(bake, 'tints', lambda parts, document, **given: (tinted, {'materials': []})), \
                    mock.patch.object(measure, 'body', lambda pack, body: ({'torso_g': np.eye(4), 'pelvis_g': np.eye(4)}, {})), \
                    mock.patch.object(bake, 'ends', lambda parts, bones, body, tier, **more: ({'waist': {}}, [])), \
                    mock.patch.object(bake, 'hidden', lambda parts, bones, body, skin, left: ({'waist': {}}, [])), \
                    mock.patch.object(export, 'compile_models', lambda sources, into, **given: compiled.append((sources, into, given)) or sources):
                record = bake.run({'model': 'outfit', 'materials': []}, output, 'bodies', 332, kept=Path(folder) / 'kept', game='game', resources=['srn_body'])
            self.assertEqual(compiled, [([output / 'ascii' / 'pmh0_chest332.mdl', output / 'ascii' / 'pmh0_pelvis332.mdl'], output / 'resources',
                                         {'game': 'game', 'resources': ['srn_body']})])
            self.assertEqual((record['compiled'], record['models'], record['gates']['passed'], record['gates']['seams']),
                             (2, {'chest': 'pmh0_chest332', 'pelvis': 'pmh0_pelvis332'}, True, {'waist': {}}))
            self.assertEqual(json.loads((output / 'bake.json').read_text(encoding='utf-8')), record)

    def test_a_fresh_bakes_stages_are_in_its_record(self):
        # the bake's own stages were said in the log and left out of the record: `run` gives the bake its count
        parts = {'chest': part()}
        tinted = {name: (np.full((4, 4), 170), np.full((4, 4), export.LAYERS['cloth1'])) for name in parts}

        def baked(*given, mark=None, **more):
            mark('split')
            return parts, {'torso_g': np.eye(4)}, None
        with tempfile.TemporaryDirectory() as folder, mock.patch.object(bake, 'bake', baked), \
                mock.patch.object(bake, 'tints', lambda parts, document, **given: (tinted, {'materials': []})), \
                mock.patch.object(measure, 'body', lambda pack, body: ({'torso_g': np.eye(4)}, {})), \
                mock.patch.object(bake, 'ends', lambda parts, bones, body, tier, **more: ({}, [])), \
                mock.patch.object(bake, 'hidden', lambda parts, bones, body, skin, left: ({}, [])):
            record = bake.run({'model': 'outfit', 'materials': []}, Path(folder) / 'out', 'bodies', 332, mesh='m', colours='c', raw='r', xatlas='x')
        self.assertEqual(list(record['seconds']), ['split', 'tint', 'write', 'gates'])

    def test_what_of_a_collar_enters_the_neck_gives_way_to_a_fan_from_its_rim(self):
        # the neck: a box 10 cm wide from 0.9 to 1.2, its plane at 1.0; the chest: a lid of two faces across it, corner
        # to corner of the rim just over the plane, a seam of the texture along the edge they share, and one face of
        # the cloth beside it
        corners = np.array([(x, y, z) for x in (-0.05, 0.05) for y in (-0.05, 0.05) for z in (0.9, 1.2)])
        box = np.array([(0, 1, 3), (0, 3, 2), (4, 6, 7), (4, 7, 5), (0, 4, 5), (0, 5, 1), (2, 3, 7), (2, 7, 6), (0, 2, 6), (0, 6, 4), (1, 5, 7), (1, 7, 3)])
        rim = [(-0.08, -0.08, 1.01), (0.08, -0.08, 1.01), (0.08, 0.08, 1.01), (-0.08, 0.08, 1.01)]
        chest = {'v': np.array(rim + [rim[0], rim[2], (0.2, 0.0, 1.0), (0.3, 0.0, 1.0), (0.2, 0.1, 1.0)]),
                 'f': np.array([(0, 1, 2), (4, 5, 3), (6, 7, 8)]),
                 'uv': np.array([(0.0, 0.0), (0.2, 0.0), (0.2, 0.2), (0.6, 0.2), (0.4, 0.0), (0.6, 0.0), (0.5, 0.5), (0.6, 0.5), (0.5, 0.6)]),
                 'n': np.tile((0.0, 0.0, 1.0), (9, 1)), 'src': np.zeros((9, 3)), 'added': np.zeros(3, bool), 'domed': np.zeros(3, bool),
                 'trimmed': np.array([4, 7, -1]), 'pad': np.zeros(3, bool)}
        neck, plane = (corners, box), ((0.0, 0.0, 1.0), (0.0, 0.0, 1.0))
        out, taken = bake.collared(chest, neck, *plane)
        # the two are gone and the four edges of the rim each run down to the neck's axis: the shared edge, open on the
        # texture alone, gets nothing
        self.assertEqual((taken, len(out['f']), len(out['v'])), (2, 5, 13))
        self.assertTrue(np.allclose(out['v'][9:], (0.0, 0.0, 1.0 - bake.LID_SUNK)) and np.array_equal(out['v'][:9], chest['v']))
        self.assertEqual(out['f'].tolist(), [[6, 7, 8], [0, 1, 9], [1, 2, 10], [5, 3, 11], [3, 4, 12]])
        self.assertTrue(np.allclose(out['uv'][9:], [(0.1, 0.0), (0.2, 0.1), (0.6, 0.1), (0.5, 0.1)]) and np.allclose(out['n'][9:], (0, 0, 1)))
        self.assertEqual((out['trimmed'].tolist(), len(out['added']), len(out['pad'])), ([-1, 4, 4, 7, 7], 5, 5))
        # each keeps the winding of the face that held its edge: none is turned in
        facing = lambda v, f: np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]])[:, 2]
        self.assertTrue((facing(out['v'], out['f']) > 0).all())
        # no more faces than the lid had, give or take the rim's own: a chest at its budget stays within it
        self.assertLessEqual(len(out['f']) - len(chest['f']), 2)
        # a fold of the collar whose three corners stand outside the neck and whose middle is outside it too, but
        # which crosses the neck's corner: it enters the neck, and it is taken with the lid
        fold = {**chest, 'v': np.concatenate([chest['v'], [(0.07, 0.02, 1.05), (0.02, 0.07, 1.05), (0.09, 0.09, 1.05)]]),
                'f': np.concatenate([chest['f'], [(9, 10, 11)]]), 'uv': np.concatenate([chest['uv'], np.zeros((3, 2))]),
                'n': np.tile((0.0, 0.0, 1.0), (12, 1)), 'src': np.zeros((12, 3)), 'added': np.zeros(4, bool), 'domed': np.zeros(4, bool),
                'trimmed': np.array([4, 7, -1, 2]), 'pad': np.zeros(4, bool)}
        self.assertFalse((np.abs(measure.winding(np.vstack([fold['v'][9:], fold['v'][9:].mean(axis=0)]), corners, box)) >= 0.5).any())
        out, taken = bake.collared(fold, neck, *plane)
        self.assertEqual((taken, out['trimmed'].tolist()), (3, [-1, 4, 4, 7, 7, 2, 2, 2]))
        self.assertEqual(out['f'][-3:, :2].tolist(), [[9, 10], [10, 11], [11, 9]])  # no other face holds its edges: each runs down
        # one that lies along the neck over its plane, 5 mm out from its side, is cut back with the lid; a face as near
        # it but under the plane, or over the plane 2 cm out, is left
        side = lambda x, z: {**fold, 'v': np.concatenate([chest['v'], [(x, -0.03, z), (x, 0.03, z), (x, 0.0, z + 0.03)]])}
        self.assertEqual(bake.collared(side(0.055, 1.005), neck, *plane)[1], 3)
        self.assertEqual(bake.collared(side(0.055, 0.96), neck, *plane)[1], 2)
        self.assertEqual(bake.collared(side(0.07, 1.005), neck, *plane)[1], 2)
        # one that passes the neck's corner clear of it is left
        clear = {**fold, 'v': np.concatenate([chest['v'], [(0.09, 0.02, 1.05), (0.02, 0.09, 1.05), (0.09, 0.09, 1.05)]])}
        self.assertEqual(bake.collared(clear, neck, *plane)[1], 2)
        # a tooth: two faces that enter the neck, and between them one that does not and holds an edge of each. It is
        # left with two of its edges on the rim and goes with them; beside one of them alone it has one, and stays
        spots = np.array([(-0.03, -0.07, 1.01), (0.0, -0.12, 1.01), (0.03, -0.07, 1.01), (0.0, 0.04, 1.01)])
        flat = lambda faces: {'v': spots, 'f': np.array(faces), 'uv': np.zeros((4, 2)), 'n': np.tile((0.0, 0.0, 1.0), (4, 1)), 'src': np.zeros((4, 3))}
        out, taken = bake.collared(flat([(1, 0, 3), (2, 1, 3), (0, 2, 1)]), neck, *plane)
        self.assertEqual((taken, out['f'][:, :2].tolist()), (3, [[0, 3], [3, 2], [0, 2]]))
        self.assertEqual(bake.collared(flat([(1, 0, 3), (0, 2, 1)]), neck, *plane)[1], 1)
        # a pad's faces and the body's skin beside the cloth are left, and a chest clear of the neck comes back as it was
        self.assertEqual(bake.collared({**fold, 'pad': np.ones(4, bool)}, neck, *plane)[1], 0)
        self.assertEqual(bake.collared({**fold, 'skin': np.ones(4, bool)}, neck, *plane)[1], 0)
        self.assertIs(bake.collared(chest, (corners + (1.0, 0, 0), box), (1.0, 0.0, 1.0), (0.0, 0.0, 1.0))[0], chest)

    def test_the_tier_the_parts_were_cut_at_is_kept_with_them(self):
        cut = {'default': 3, 'waist': 1}
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            bake.store({'chest': part(3)}, root / 'own', {}, cut, ['knee'])
            bake.store({'pelvis': part(2)}, root / 'carried', {}, cut, ('knee',))
            bake.store({'legl': part()}, root / 'old', {})  # kept before the tier was listed: it says nothing
            bake.store({'legr': part()}, root / 'padded', {}, 2)
            self.assertEqual((bake.listing(root / 'own')['tier'], 'tier' in bake.listing(root / 'old')), (cut, False))
            bake.combine([(root / 'own', ['chest']), (root / 'carried', ['pelvis']), (root / 'old', ['legl'])], root / 'out', {})
            self.assertEqual((bake.listing(root / 'out')['tier'], bake.listing(root / 'out')['drawn']), (cut, ['knee']))  # and the joints cut as drawn
            bake.store({'legr': part()}, root / 'shaped', {}, cut)  # at the same tier, its knee shaped to the envelope
            with self.assertRaisesRegex(ValueError, 'drawn joints'):
                bake.combine([(root / 'own', ['chest']), (root / 'shaped', ['legr'])], root / 'mixed', {})
            with self.assertRaisesRegex(ValueError, 'cut at different tiers'):
                bake.combine([(root / 'own', ['chest']), (root / 'padded', ['legr'])], root / 'mixed', {})
            listed = json.loads((root / 'own' / bake.KEPT).read_text(encoding='utf-8'))
            (root / 'own' / bake.KEPT).write_text(json.dumps({**listed, 'tier': {'waist': 1}}), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'names no tier'):
                bake.listing(root / 'own')

    def test_parts_kept_apart_are_combined_into_one_outfit(self):
        document = {'model': 'outfit', 'materials': [], 'bare': ['forearm'], 'skin': ['bicep']}
        skin = dict(part(), skin=np.zeros(1, bool))
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            bake.store({'chest': part(3), 'bicepl': part()}, root / 'own', document)  # the body's own bake: its upper arm is left out
            bake.store({'bicepl': skin, 'pelvis': part(2), 'legl': part()}, root / 'carried', document)
            bake.store({'pelvis': part(2)}, root / 'other', {'skin': ['bicep']})  # baked with the forearm covered
            origin = bake.combine([(root / 'own', ['chest']), (root / 'carried', ['bicepl', 'pelvis'])], root / 'out', document)
            self.assertEqual(origin, {'chest': str(root / 'own'), 'bicepl': str(root / 'carried'), 'pelvis': str(root / 'carried')})
            back = bake.stored(root / 'out')
            self.assertEqual((sorted(back), len(back['chest']['f']), 'skin' in back['bicepl']), (['bicepl', 'chest', 'pelvis'], 3, True))
            self.assertEqual(bake.declared(root / 'out'), {'bare': {'forearm'}, 'skin': {'bicep'}})  # the brief's slots, for `bake --kept`
            (root / 'file').write_text('')
            refused = {'is not an empty folder': ([(root / 'own', ['chest'])], root / 'out'),
                       'is not an empty folder ': ([(root / 'own', ['chest'])], root / 'file'),  # a file, not a folder
                       'holds no shinl': ([(root / 'own', ['shinl'])], root / 'b'),
                       'take each part from one folder': ([(root / 'own', ['bicepl']), (root / 'carried', ['bicepl'])], root / 'c'),
                       'once': ([(root / 'own', ['chest', 'chest'])], root / 'c'),
                       'Name the parts': ([(root / 'own', [])], root / 'd'),
                       'shared with its skin than': ([(root / 'own', ['chest', 'bicepl'])], root / 'e'),  # an upper arm without the skin
                       'bake or refit them for it': ([(root / 'own', ['chest']), (root / 'other', ['pelvis'])], root / 'f')}
            for words, (sources, out) in refused.items():
                with self.assertRaisesRegex(ValueError, words.strip()):
                    bake.combine(sources, out, document)
            self.assertFalse(any((root / name).exists() for name in 'bcdef'))  # nothing kept where it was refused

    def test_kept_parts_baked_for_other_slots_left_to_the_body_or_its_skin_are_refused(self):
        skin = dict(part(), skin=np.zeros(1, bool))
        document = {'model': 'outfit', 'materials': [], 'bare': ['forearm'], 'skin': ['bicep']}
        plain = {'model': 'outfit', 'materials': []}
        cases = (({'chest': part(), 'forel': part()}, None, document),  # a part the brief now leaves to the body
                 ({'chest': part(), 'bicepl': part()}, None, document),  # an upper arm without the skin the brief now shows
                 ({'chest': part(), 'bicepl': skin}, None, plain),  # and with it, where the brief shows none
                 ({'chest': part()}, {**plain, 'bare': ['forearm']}, plain))  # no forearm, left to the body by the brief baked from and no longer
        with tempfile.TemporaryDirectory() as folder, mock.patch.object(measure, 'body', lambda pack, body: ({'torso_g': np.eye(4)}, {})), \
                mock.patch.object(bake, 'tints', lambda parts, document, **given: self.fail('tinted')):
            for parts, baked_from, brief in cases:
                bake.store(parts, Path(folder) / 'kept', baked_from)
                with self.assertRaisesRegex(ValueError, 'bake the outfit again'):
                    bake.run(brief, Path(folder) / 'out', 'bodies', 332, kept=Path(folder) / 'kept')
            self.assertEqual(bake.declared(Path(folder) / 'kept'), {'bare': {'forearm'}, 'skin': set()})
            # parts kept for the brief's own slots are tinted again
            bake.store({'chest': part(), 'bicepl': skin}, Path(folder) / 'kept', document)
            with mock.patch.object(bake, 'tints', mock.Mock(side_effect=RuntimeError('tinted'))):
                with self.assertRaisesRegex(RuntimeError, 'tinted'):
                    bake.run(document, Path(folder) / 'out', 'bodies', 332, kept=Path(folder) / 'kept')
            listed = json.loads((Path(folder) / 'kept' / bake.KEPT).read_text(encoding='utf-8'))
            (Path(folder) / 'kept' / bake.KEPT).write_text(json.dumps({**listed, 'skin': 'bicep'}), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'no list of baked parts'):  # the slots are checked with the list
                bake.declared(Path(folder) / 'kept')
            bake.store({'chest': part()}, Path(folder) / 'kept')  # stored without its brief, or before the list held the slots: none
            self.assertEqual(bake.declared(Path(folder) / 'kept'), {'bare': set(), 'skin': set()})

    def test_what_closes_a_part_is_brought_in_under_the_part_beside_it(self):
        bones, terms = rig(), {**contract(), 'designBend': 'p95', 'ends': dict(seams.ENDS)}
        for joint in terms['joints'].values():
            joint['bodies']['test']['bend'] = {'p95': 90.0}
        sleeve = closed(0.05, 0.3, 0.03, near=None, far='dome')  # a narrow upper arm
        cuff = closed(0.27, 0.5, 0.06, near='cap', far=None, depth=0.02)  # a forearm twice as wide: its end stands out round the sleeve
        parts = {'bicepl': sleeve, 'forel': cuff}
        before = bake.hidden(parts, bones, 'test', terms)
        self.assertTrue(any(line.startswith('forel at the elbow: what the split added stands up to') for line in before[1]), before[1])
        said = []
        self.assertIs(bake.tucked(parts, bones, terms, say=said.append)['forel'], cuff)  # the elbow is not among the joints tucked
        self.assertEqual(said, [])
        held = bake.tucked(parts, bones, terms, joints=('elbow',), say=said.append)
        self.assertIs(held['bicepl'], sleeve)  # the part over the joint: its dome stands over the other by contract
        moved = np.linalg.norm(held['forel']['v'] - cuff['v'], axis=1) > 0
        self.assertTrue(moved.any() and not moved[np.unique(cuff['f'][~cuff['added']])].any())  # the outfit's own surface and its edge stay
        self.assertTrue(np.array_equal(held['forel']['f'], cuff['f']))
        after = bake.hidden(held, bones, 'test', terms)
        self.assertFalse(any('stands up to' in line and 'as the body stands' in line for line in after[1]), after[1])
        self.assertLessEqual(after[0]['elbow']['l']['rest'], seams.ENDS['rest'])
        self.assertTrue(said[0].startswith('forel at the elbow: ') and 'brought in under the outfit beside it' in said[0])
        again = bake.tucked(held, bones, terms, joints=('elbow',))
        self.assertIs(again['forel'], held['forel'])  # nothing left to bring in

    def test_a_part_is_tinted_in_what_its_slot_wears_and_a_colour_drawn_as_another_is_reported(self):
        from .test_brief import BLUE, GREY, TAN, document
        given = document(('shirt', 'cloth', GREY), ('flaps', 'cloth', BLUE), ('boots', 'leather', TAN))
        for material, channel in zip(given['materials'], (1, 2, 1)):
            material['channel'] = channel
        chest, foot = part(2, size=16), part(2, size=16)
        chest['rgb'] = np.tile(np.array(GREY) / 255, (16, 16, 1))
        chest['rgb'][:, 10:] = np.array(BLUE) / 255
        foot['rgb'] = np.tile(np.array(TAN) / 255, (16, 16, 1))
        foot['rgb'][:, :4] = np.array(BLUE) / 255  # a boot's sole in the flaps' colour
        parts = {'chest': chest, 'footl': foot}
        layers = lambda tinted, name: set(np.unique(tinted[name][1]).tolist())
        tinted, record = bake.tints(parts, given, speck=0)
        self.assertEqual(layers(tinted, 'footl'), {export.LAYERS['leather1'], export.LAYERS['cloth2']})  # as the colours read
        self.assertNotIn('elsewhere', record['materials'][1])
        for material, slots in zip(given['materials'], (['chest'], ['chest', 'thigh'], ['foot'])):
            material['slots'] = slots
        said = []
        tinted, record = bake.tints(parts, given, speck=0, say=said.append)
        self.assertEqual(layers(tinted, 'footl'), {export.LAYERS['leather1']})  # all boot
        self.assertEqual(layers(tinted, 'chest'), {export.LAYERS['cloth1'], export.LAYERS['cloth2']})
        flaps = next(material for material in record['materials'] if material['name'] == 'flaps')
        self.assertEqual(flaps['elsewhere'], {'footl': 0.25})
        self.assertTrue(any('footl: 25% of it has the colour of flaps' in line for line in said))
        given['materials'][2]['slots'] = ['shin']
        with self.assertRaisesRegex(ValueError, 'footl: no material of the brief is worn on the foot'):
            bake.tints(parts, given, speck=0)

    def test_a_run_is_a_fresh_bake_or_a_second_tint_of_kept_parts(self):
        document = {'model': 'outfit', 'materials': []}
        for wrong in ({}, {'mesh': 'mesh.glb'}, {'mesh': 'mesh.glb', 'colours': 'field.npz', 'raw': 'raw.glb'},
                      {'kept': 'kept', 'xatlas': object()}):
            with self.assertRaises(ValueError):
                bake.run(document, 'out', 'bodies', 332, **wrong)


class BudgetTests(unittest.TestCase):
    """A part over its triangle budget, cut down after the split."""

    def setUp(self):
        from .test_split import JOINTS, RADII
        self.joints = {name: np.array(p, float) for name, p in JOINTS.items()}
        self.radii = RADII
        # a thigh: a fine tube from the hip to the knee, open at the hip and capped by a fan past the knee
        hip, knee = self.joints['lthigh_g'], self.joints['lshin_g']
        v, f, t = tube(hip, knee + (0, 0, -0.03), 0.07, around=24, along=40)
        pole = len(v)
        v = np.concatenate([v, [knee + (0, 0, -0.06)]])
        last = 40 * 24 + np.arange(24)
        cap = np.array([(pole, last[(k + 1) % 24], last[k]) for k in range(24)])
        self.v, self.f = v, np.concatenate([f, cap])
        self.columns = np.c_[v, np.arange(len(v))]  # a vertex's columns ride with it
        self.made = np.r_[np.full(len(f), split.OWN), np.full(len(cap), split.CAP)]
        self.origin = np.r_[np.arange(len(f)), np.full(len(cap), -1)]

    def run_budget(self, budget, beside=None, left=()):
        made, origins = {'legl': self.made.copy()}, {'legl': self.origin.copy()}
        with mock.patch.dict(bake.BUDGET, {'slot': budget}):
            out = bake.within_budget({'legl': (self.v, self.f, self.columns)}, made, origins, self.joints, self.radii, beside, left)
        return out['legl'], made['legl'], origins['legl']

    def test_a_part_over_its_budget_is_cut_down_and_what_the_split_made_and_its_ends_stay(self):
        (pv, pf, pc), made, origin = self.run_budget(1200)
        self.assertLessEqual(len(pf), 1200)
        self.assertEqual((len(made), len(origin)), (len(pf), len(pf)))
        self.assertTrue(np.array_equal(pv, self.v[pc[:, 3].astype(int)]))  # each vertex kept with its own columns, where it was
        self.assertEqual(int((made == split.CAP).sum()), 24)  # the cap whole
        kept = set(pc[:, 3].astype(int).tolist())
        knee_point, knee_normal = split.planes(self.joints)[('knee', 'l')]
        near = np.abs((self.v - knee_point) @ seams.unit(knee_normal)) < bake.END_BAND
        self.assertTrue(set(np.flatnonzero(near).tolist()) <= kept)  # the end the seam contract measures
        self.assertTrue(set(np.flatnonzero(self.v[:, 2] > self.joints['lthigh_g'][2] - 1e-9).tolist()) <= kept)  # the open rim
        self.assertTrue(np.array_equal(origin[made == split.OWN], np.sort(origin[made == split.OWN])))  # faces kept in their order

    def test_an_under_ends_ring_on_its_plane_keeps_every_point_however_far_the_part_is_cut_down(self):
        # a thigh standing on the hip plane, its end domed on past the plane into the pelvis, both dense
        point, normal = split.planes(self.joints)[('hip', 'l')]
        unit = seams.unit(normal)
        a, b = seams.frame(unit)
        around = np.linspace(0, 2 * np.pi, 48, endpoint=False)
        round_ = np.cos(around)[:, None] * a + np.sin(around)[:, None] * b
        heights = np.r_[-0.05 * np.sin(np.radians([75, 60, 45, 30, 15])), np.linspace(0, 0.3, 31)]  # the dome, then the tube
        widths = np.r_[0.07 * np.cos(np.radians([75, 60, 45, 30, 15])), np.full(31, 0.07)]
        v = np.concatenate([point + w * round_ + h * unit for h, w in zip(heights, widths)] + [[point - 0.05 * unit]])
        rows, pole = len(heights), len(heights) * 48
        f = [face for r in range(rows - 1) for k in range(48) for i, j in [(r * 48 + k, r * 48 + (k + 1) % 48)]
             for face in ((i, j, j + 48), (i, j + 48, i + 48))]
        f = np.array([(pole, k, (k + 1) % 48) for k in range(48)] + f)
        made = np.where(np.arange(len(f)) < 48 + 2 * 48 * 5, split.CAP, split.OWN)
        origin = np.where(made == split.OWN, np.arange(len(f)), -1)
        made_out, origins_out = {'legl': made}, {'legl': origin}
        with mock.patch.dict(bake.BUDGET, {'slot': 150}):
            pv, pf, _ = bake.within_budget({'legl': (v, f, np.c_[v, np.arange(len(v))])}, made_out, origins_out, self.joints,
                                           self.radii)['legl']
        self.assertLess(len(pf), len(f))
        on_plane = np.abs((pv[np.unique(pf)] - point) @ unit) < split.WELD
        self.assertEqual(int(on_plane.sum()), 48)  # the ring on the hip plane, whole

    def test_a_part_within_its_budget_or_left_to_the_body_is_not_touched(self):
        for budget, left in ((len(self.f), ()), (100, ('legl',))):
            (pv, pf, pc), made, origin = self.run_budget(budget, left=left)
            self.assertTrue(pv is self.v and pf is self.f and np.array_equal(made, self.made))

    def test_the_bodys_skin_beside_a_part_counts_against_its_budget(self):
        counted = []

        def beside(vertices, faces):
            counted.append(len(faces))
            return 300  # the body's own faces the part will hold
        (pv, pf, pc), _, _ = self.run_budget(1200, {'legl': beside})
        self.assertLessEqual(len(pf), 900)
        self.assertGreaterEqual(len(counted), 2)  # counted again on the part cut down


class SplitCaptureTests(unittest.TestCase):
    def test_what_the_split_is_given_is_kept_as_it_was(self):
        given = {'vertices': np.arange(12.0).reshape(4, 3), 'faces': np.array([(0, 1, 2), (0, 2, 3)]),
                 'radii': {('shoulder', 'l'): 0.12, ('waist', 'c'): np.float64(0.2)},
                 'sleeves': {'l': {'on': np.zeros((4, 4), bool), 'normals': [np.ones(3), -np.ones(3)], 'reach': 0.3}},
                 'whole': {('neck', 'c')}, 'left': ['handl'], 'body': 'pmh0', 'tier': np.int64(2), 'none': None, 'flag': True}
        with tempfile.TemporaryDirectory() as folder:
            path = bake.keep_split(given, Path(folder) / 'split.npz')
            kept = bake.kept_split(path)
            self.assertEqual(set(kept), set(given))
            self.assertTrue(np.array_equal(kept['vertices'], given['vertices']) and kept['faces'].dtype == given['faces'].dtype)
            self.assertEqual(kept['radii'], {('shoulder', 'l'): 0.12, ('waist', 'c'): 0.2})  # tuple keys stay tuples
            self.assertEqual(kept['sleeves']['l']['on'].dtype, bool)
            self.assertTrue(isinstance(kept['sleeves']['l']['normals'], list) and np.array_equal(kept['sleeves']['l']['normals'][1], -np.ones(3)))
            self.assertEqual((kept['whole'], kept['left'], kept['body'], kept['tier'], kept['none'], kept['flag']),
                             ({('neck', 'c')}, ['handl'], 'pmh0', 2, None, True))
            np.savez(Path(folder) / 'other.npz', vertices=given['vertices'])
            with self.assertRaises(ValueError):  # not what a bake kept
                bake.kept_split(Path(folder) / 'other.npz')
            with self.assertRaises(ValueError):  # nothing is kept that would need pickling to read back
                bake.keep_split({'shape': object()}, Path(folder) / 'bad.npz')

    def test_a_pad_is_what_was_carried_round_under_one_and_what_was_cut_from_its_faces(self):
        made = np.array([split.OWN, split.PADDED, split.OWN, split.CLOSING])
        origins = np.array([0, -1, 2, -1])
        guards = {('elbow', 'l'): np.array([False, False, True])}
        self.assertEqual(bake.pad_flags(made, origins, guards).tolist(), [False, True, True, False])
        self.assertEqual(bake.pad_flags(made, origins, {}).tolist(), [False, True, False, False])

    def test_a_split_run_again_reports_its_parts_and_their_ends_and_leaves_out_the_bodys(self):
        pinched = np.array([(0.0, 0.0, 0.0), (bake.POINT / 2, 0.0, 0.0), (0.0, 1.0, 0.0)])
        result = {'chest': (pinched, np.array([(0, 1, 2)]), np.zeros((3, 9))), 'handl': (pinched, np.array([(0, 1, 2)]), np.zeros((3, 9)))}
        made = {'chest': np.array([split.OWN]), 'handl': np.array([split.OWN])}
        origins = {'chest': np.array([0]), 'handl': np.array([0])}
        given = {'guards': {}, 'bones': {}, 'body': 'pmh0', 'tier': 2, 'left': ['handl'], 'shared': ['chest']}
        measured = []
        def ends(parts, bones, body, tier, contract, drawn=()):
            measured.append(parts)
            return {'elbow': {}}, ['forel does not reach the elbow plane']
        covered = lambda parts, bones, body, contract, skin, left: ({'elbow': {}}, ['chest at the waist: open on its plane, 1.0 cm of edge'])
        with mock.patch.object(bake, 'kept_split', lambda path: given), mock.patch.object(bake, 'cut', lambda kept, contract: (result, made, origins)), \
                mock.patch.object(bake, 'ends', ends), mock.patch.object(bake, 'hidden', covered):
            parts, report = bake.resplit('kept.npz')
        self.assertEqual(set(parts), {'chest'})  # the hand is the body's
        # a part sharing its slot with the body's skin is measured as the bake measures it: it may end short of its joint
        self.assertTrue('skin' in measured[0]['chest'] and not measured[0]['chest']['skin'].any())
        self.assertEqual(report['triangles'], {'chest': 1})
        self.assertEqual(report['collapsed'], {'chest': 1})
        self.assertEqual(report['seams'], {'elbow': {}})
        self.assertEqual((report['seams'], report['hidden']), ({'elbow': {}}, {'elbow': {}}))
        self.assertEqual(report['failures'], ['chest: 1 triangles with two corners at one point, which the model compiler drops',
                                              'forel does not reach the elbow plane', 'chest at the waist: open on its plane, 1.0 cm of edge'])
        with self.assertRaises(ValueError):  # parts tinted again were split long ago
            bake.run({'model': 'x'}, 'out', 'bodies', 332, kept='kept', capture='split.npz')


if __name__ == '__main__':
    unittest.main()
