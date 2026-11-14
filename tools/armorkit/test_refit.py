"""Parts carried from one body to another (tools/armorkit/refit.py), on the test rig's left arm."""
import math
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from . import bake, bodyskin, measure, refit, seams, split
from .test_bake import arm, closed, contract, part, rig
from .test_bodyskin import arm as body_arm


def moved(bones, rotation, scale, offset):
    """The rig `bones` with every joint carried by `scale * rotation @ p + offset`."""
    out = {name: matrix.copy() for name, matrix in bones.items()}
    for matrix in out.values():
        matrix[:3, 3] = scale * rotation @ matrix[:3, 3] + offset
    return out


def about_z(degrees):
    angle = math.radians(degrees)
    return np.array([[math.cos(angle), -math.sin(angle), 0.0], [math.sin(angle), math.cos(angle), 0.0], [0.0, 0.0, 1.0]])


def two_bodies(source_ring=0.04, target_ring=0.04):
    """A seam contract holding two bodies, `a` and `b`, with body rings of these radii at every joint."""
    a, b = contract(ring=source_ring), contract(ring=target_ring)
    for joint, spec in a['joints'].items():
        spec['bodies'] = {'a': spec['bodies']['test'], 'b': b['joints'][joint]['bodies']['test']}
    return a


def sleeved():
    """An upper arm's two faces of sleeve with the body's own arm beside them (`bodyskin.worn`)."""
    sleeve = part(faces=2)
    sleeve['v'] = np.array([(0.07, 0.0, 1.5), (0.07, 0.01, 1.5), (0.07, 0.0, 1.45)])
    return bodyskin.worn(sleeve, body_arm(), (0, 0, 1.5), (0, 0, 1.2))


def hand(scale=1.0, round_=None):
    """The body's own left hand: a short tube past the wrist plane (x = 0.55), `scale` times as long and
    `round_` (or `scale`) times as wide."""
    piece = arm(0.55, 0.55 + 0.12 * scale, 0.03 * (scale if round_ is None else round_))
    return piece['v'], piece['f']


class PlacementTests(unittest.TestCase):
    def setUp(self):
        self.rotation, self.offset = about_z(30.0), np.array((0.1, -0.2, 0.05))
        self.source = (rig(), {'handl': hand()})

    def test_a_part_between_two_joints_is_carried_as_its_joints_are(self):
        target = (moved(rig(), self.rotation, 0.9, self.offset), {'handl': hand(0.9)})
        forearm = arm(0.3, 0.55, 0.05)
        linear, offset, scales = refit.placement('forel', self.source, target)
        self.assertTrue(np.allclose(forearm['v'] @ linear.T + offset, 0.9 * forearm['v'] @ self.rotation.T + self.offset))
        self.assertEqual(scales, {'along': 0.9, 'across': [0.9, 0.9]})

    def test_a_shoulder_pad_is_carried_as_its_upper_arm_is(self):
        target = (moved(rig(), self.rotation, 0.9, self.offset), {'handl': hand(0.9)})
        linear, offset, scales = refit.placement('shol', self.source, target)
        arm_linear, arm_offset, arm_scales = refit.placement('bicepl', self.source, target)
        self.assertTrue(np.allclose(linear, arm_linear) and np.allclose(offset, arm_offset))
        self.assertEqual(scales, {**arm_scales, 'with': 'bicepl'})

    def test_a_body_narrower_than_its_length_says_scales_the_part_across_its_axis_apart(self):
        target = (moved(rig(), np.eye(3), 0.9, np.zeros(3)), {'handl': hand(0.9)})
        linear, offset, scales = refit.placement('forel', self.source, target, two_bodies(0.04, 0.028), ('a', 'b'))
        self.assertEqual(scales, {'along': 0.9, 'across': [0.7, 0.7]})
        forearm = arm(0.3, 0.55, 0.05)
        carried = forearm['v'] @ linear.T + offset
        self.assertTrue(np.allclose(np.linalg.norm(carried[:, 1:], axis=1), 0.7 * 0.05))  # round, and as much narrower as the rings
        self.assertTrue(np.allclose(carried[:, 0], 0.9 * forearm['v'][:, 0]))  # and as long as the joints lie apart
        # however near the scales lie, each is its own: no one scale stands for them
        linear, _, scales = refit.placement('forel', self.source, target, two_bodies(0.04, 0.04 * 0.88), ('a', 'b'))
        self.assertEqual(scales, {'along': 0.9, 'across': [0.88, 0.88]})
        # a ring narrower one way than the other: 0.8 the source's across y (the frame's u at the elbow and the
        # wrist, square to the arm), 0.6 across z, between as cos and sin squared weigh them
        terms = two_bodies(0.04, 0.04)
        angle = 2 * np.pi * np.arange(seams.DIRECTIONS) / seams.DIRECTIONS
        for joint in terms['joints'].values():
            for ring in joint['bodies']['b']['sides'].values():
                ring['bodyRing'] = list(0.04 * (0.8 * np.cos(angle) ** 2 + 0.6 * np.sin(angle) ** 2))
        linear, offset, scales = refit.placement('forel', self.source, target, terms, ('a', 'b'))
        self.assertEqual((scales['along'], scales['across']), (0.9, [0.75, 0.65]))
        carried = forearm['v'] @ linear.T + offset
        self.assertAlmostEqual(float(np.ptp(carried[:, 1])), 0.75 * float(np.ptp(forearm['v'][:, 1])), places=9)
        self.assertAlmostEqual(float(np.ptp(carried[:, 2])), 0.65 * float(np.ptp(forearm['v'][:, 2])), places=9)

    def test_a_part_with_one_joint_turns_as_the_part_beside_it_and_scales_by_the_bodys_own(self):
        own = hand(0.8)
        target = (moved(rig(), self.rotation, 0.9, self.offset), {'handl': (own[0] @ self.rotation.T, own[1])})
        linear, offset, scales = refit.placement('handl', self.source, target)
        self.assertTrue(np.allclose(scales['axes'], 0.8, atol=1e-3))
        self.assertTrue(np.allclose(linear, 0.8 * self.rotation, atol=1e-3))
        wrist = np.array((0.55, 0.0, 0.0))
        self.assertTrue(np.allclose(linear @ wrist + offset, 0.9 * self.rotation @ wrist + self.offset))  # its joint where the other body's is
        # a hand as long but narrower: scaled along its own length and across it apart
        target = (rig(), {'handl': hand(0.9, 0.7)})
        linear, offset, scales = refit.placement('handl', self.source, target)
        self.assertTrue(np.allclose(sorted(scales['axes']), [0.7, 0.7, 0.9], atol=1e-3))
        carried = self.source[1]['handl'][0] @ linear.T + offset
        self.assertAlmostEqual(float(np.ptp(carried[:, 0])), 0.9 * 0.12, places=4)
        self.assertTrue(np.allclose(np.linalg.norm(carried[:, 1:], axis=1), 0.7 * 0.03, atol=1e-4))


class RefitTests(unittest.TestCase):
    def test_parts_are_carried_with_their_normals_and_one_with_the_bodys_skin_without_it(self):
        source = (rig(), {'handl': hand()})
        target = (moved(rig(), about_z(90.0), 1.0, np.zeros(3)), {'handl': (hand()[0] @ about_z(90.0).T, hand()[1])})
        glove = part(faces=1)
        glove['v'] = glove['v'] + (0.6, 0.0, 0.0)
        sleeve = sleeved()
        out, report = refit.refit({'handl': glove, 'bicepl': sleeve}, source, target, ['handl'])
        self.assertEqual(report['handl']['degrees'], 90.0)
        self.assertTrue(np.allclose(out['handl']['n'], [[0.0, 0.0, 1.0]] * 3))  # turned about z, a normal along z stays
        self.assertTrue(np.allclose(out['handl']['v'], glove['v'] @ about_z(90.0).T))
        self.assertTrue(np.array_equal(out['handl']['rgb'], glove['rgb']))  # nothing else changes
        out, _ = refit.refit({'bicepl': sleeve}, source, target)  # the source body's skin left behind, the sleeve carried
        self.assertFalse(set(bodyskin.KEYS) & set(out['bicepl']))
        self.assertEqual((len(out['bicepl']['f']), len(out['bicepl']['v']), len(out['bicepl']['rgb'])), (2, 3, 4))

    def test_a_triangle_shrunk_to_a_sliver_the_compiler_drops_is_left_out(self):
        # two triangles of a glove, the second with two corners 2 microns apart: on a hand 0.4 the size, 0.8 apart
        glove = part(faces=2)
        glove['v'] = np.array([(0.6, 0.0, 0.0), (0.7, 0.0, 0.0), (0.6, 0.1, 0.0), (0.7 + 2e-6, 0.0, 0.0)])
        glove['f'], glove['n'] = np.array([[0, 1, 2], [1, 3, 2]]), np.tile([[0.0, 0.0, 1.0]], (4, 1))
        glove['added'], glove['pad'] = np.array([False, True]), np.array([False, True])
        source, target = (rig(), {'handl': hand()}), (rig(), {'handl': hand(0.4)})
        out, report = refit.refit({'handl': glove}, source, target)
        self.assertEqual((out['handl']['f'].tolist(), report['handl']['dropped']), ([[0, 1, 2]], 1))
        self.assertEqual((out['handl']['added'].tolist(), out['handl']['pad'].tolist(), len(out['handl']['trimmed'])), ([False], [False], 1))
        self.assertEqual(bake._collapsed(out['handl']['v'], out['handl']['f']), 0)
        self.assertNotIn('dropped', refit.refit({'handl': glove}, source, source)[1]['handl'])  # nothing shrunk, nothing dropped

    def test_a_stretched_parts_normals_stay_square_to_its_surface(self):
        source = (rig(), {})
        target = (moved(rig(), np.eye(3), 0.9, np.zeros(3)), {})
        forearm = arm(0.32, 0.53, 0.05)
        piece = {**part(), 'v': forearm['v'], 'f': forearm['f'], 'n': np.c_[np.zeros(len(forearm['v'])), forearm['v'][:, 1:] / 0.05]}
        out, report = refit.refit({'forel': piece}, source, target)
        self.assertEqual((report['forel']['along'], report['forel']['across']), (0.9, [0.9, 0.9]))  # no contract: the scale along every way
        linear, offset, _ = refit.placement('forel', source, target, two_bodies(0.04, 0.028), ('a', 'b'))
        normals = piece['n'] @ np.linalg.inv(linear)
        normals /= np.linalg.norm(normals, axis=1, keepdims=True)
        self.assertTrue(np.allclose(normals, piece['n']))  # a tube's radial normals stay radial when it is narrowed

    def test_a_cap_past_an_end_drawn_in_stays_as_far_inside_its_rim(self):
        # a forearm 5 cm round under the elbow plane (x = 0.3), its cap past the plane 3.5 cm round: drawn in to a
        # 4 cm body ring at tier 0, the cap is drawn in with it
        forearm, cap = arm(0.3, 0.55, 0.05), arm(0.27, 0.3, 0.035)
        piece = {**part(), 'v': np.concatenate([forearm['v'], cap['v']]), 'f': np.concatenate([forearm['f'], cap['f'] + len(forearm['v'])])}
        piece['n'] = np.c_[np.zeros(len(piece['v'])), piece['v'][:, 1:] / np.linalg.norm(piece['v'][:, 1:], axis=1, keepdims=True)]
        out, _ = refit.refit({'forel': piece}, (rig(), {}), (rig(), {}), contract=contract(ring=0.04), bodies=('test', 'test'), tier=0)
        radius = np.linalg.norm(out['forel']['v'][:, 1:], axis=1)
        rim, past = radius[np.abs(out['forel']['v'][:, 0] - 0.3) < 1e-9][:len(forearm['v'])].max(), radius[len(forearm['v']):][cap['v'][:, 0] < 0.3]
        self.assertLess(rim, 0.045)  # the end is drawn in to the envelope
        self.assertTrue(np.allclose(past / rim, 0.7, atol=0.01))  # the cap as far inside it as before
        # where the upper arm is left to the body, the cap stays inside the other body's own upper arm, 3 cm round
        skin = arm(0.0, 0.3, 0.03)
        out, _ = refit.refit({'forel': piece}, (rig(), {}), (rig(), {'bicepl': (skin['v'], skin['f'])}), contract=contract(ring=0.04),
                             bodies=('test', 'test'), tier=0, bare={('elbow', 'l')})
        past = np.linalg.norm(out['forel']['v'][len(forearm['v']):][cap['v'][:, 0] < 0.3][:, 1:], axis=1)
        self.assertLess(past.max(), 0.03 - refit.UNDER_SKIN + 1e-3)
        self.assertGreater(past.min(), 0.02)  # moved in to the skin, not onto the axis

    def test_a_sleeve_is_held_outside_the_other_bodys_arm(self):
        # a sleeve to x = 0.3, its end capped 3 cm back past x = 0.05, with the other body's arm 4 cm round kept beside it
        # from x = 0.18 (the left arm runs along +X from the origin)
        bones = rig()
        start, end = bones['lbicep_g'][:3, 3], bones['lforearm_g'][:3, 3]

        def worn(radius, dome=False, fuller=0.04):
            sleeve, arm_ = closed(0.05, 0.3, radius, near='cap', far=None), closed(0.0, 0.35, fuller, near=None, far=None)
            below = arm_['f'][arm_['v'][arm_['f']][:, :, 0].min(axis=1) > 0.18]
            v = np.concatenate([sleeve['v'], arm_['v']])
            added = np.concatenate([sleeve['added'] | dome, np.zeros(len(below), bool)])
            return {'v': v, 'n': np.zeros_like(v), 'f': np.concatenate([sleeve['f'], below + len(sleeve['v'])]), 'added': added,
                    'skin': np.arange(len(added)) >= len(sleeve['f'])}
        for dome in (False, True):  # the sleeve's own cloth, or a dome closing it, drawn over the arm all the same
            near = worn(0.035, dome)
            self.assertNotEqual(bake.through({'bicepl': near}, bones)[1], [])
            out = refit.over_skin(near, start, end)
            self.assertEqual(bake.through({'bicepl': out}, bones), ({'bicepl': 0.0}, []))  # held clear of the arm kept beside it
            skin = np.unique(near['f'][near['skin']])
            self.assertTrue(np.array_equal(out['v'][skin], near['v'][skin]))  # the arm itself is not moved
            pushed = np.linalg.norm(out['v'] - near['v'], axis=1)
            self.assertLessEqual(pushed.max(), 0.04 + refit.OVER_SKIN - 0.035 + 1e-6)  # by no more than it needs
        clear = worn(0.05)
        self.assertIs(refit.over_skin(clear, start, end), clear)  # a sleeve clear of the arm is not touched
        bare = closed(0.05, 0.3, 0.035, near=None, far=None)
        self.assertIs(refit.over_skin(bare, start, end), bare)  # nor a part with no skin beside it
        with self.assertRaisesRegex(Exception, 'would move 4.8 cm, past 3 cm'):  # an arm far fuller than the sleeve fails
            refit.over_skin(worn(0.035, fuller=0.08), start, end)

    def test_an_end_carried_under_the_other_bodys_own_part_is_seated_in_it(self):
        # an upper arm 4 cm round, its cap 10 cm back past the shoulder plane (x = 0.05), under a chest that stands
        # 8 cm over the joint, 8 cm round: the cap is drawn in to the chest's room less the gap, and held inside it
        sleeve, chest = closed(0.05, 0.3, 0.04, near='cap', far=None, depth=0.1), closed(-0.03, 0.05, 0.06)
        point, normal = np.array((0.05, 0.0, 0.0)), np.array((1.0, 0.0, 0.0))
        out = refit.seated(sleeve, point, normal, (chest['v'], chest['f']))
        own = np.unique(sleeve['f'][~sleeve['added']])
        self.assertTrue(np.array_equal(out[own], sleeve['v'][own]))  # the sleeve itself is not moved
        cap = np.setdiff1d(np.unique(sleeve['f'][sleeve['added']]), own)
        self.assertAlmostEqual(float(((out[cap] - point) @ normal).min()), -(0.08 - split.SEAT_GAP), places=6)
        self.assertTrue(bake._inside(out[cap], [(chest['v'], chest['f'])]).all())
        self.assertTrue(np.array_equal(refit.seated(sleeve, point, normal, (chest['v'][:0], chest['f'][:0])), sleeve['v']))  # no room: as it was
        shallow = closed(0.05, 0.3, 0.04, near='cap', far=None, depth=0.03)  # an end already inside the chest stays as it was
        self.assertTrue(np.array_equal(refit.seated(shallow, point, normal, (chest['v'], chest['f'])), shallow['v']))
        pole = np.argmin(sleeve['v'][:, 0])  # what lies nearer another joint of the part is that end's, and stays
        self.assertTrue(np.array_equal(refit.seated(sleeve, point, normal, (chest['v'], chest['f']), others=[sleeve['v'][pole]])[pole], sleeve['v'][pole]))

    def test_the_command_keeps_the_refit_parts_with_the_slots_the_brief_gave(self):
        with tempfile.TemporaryDirectory() as folder:
            kept, out = Path(folder) / 'kept', Path(folder) / 'out'
            glove = part(faces=1)
            bake.store({'handl': glove}, kept, {'bare': ['forearm'], 'skin': ['bicep']})
            bodies = {'pmh0': (rig(), {'handl': hand()}), 'pfh0': (rig(), {'handl': hand(0.8)})}
            with mock.patch.object(measure, 'body', side_effect=lambda pack, name: bodies[name]), \
                    mock.patch.object(seams, 'load_contract', return_value=None):
                report = refit.run(kept, out, 'pack', 'pmh0', 'pfh0')
            self.assertTrue(np.allclose(report['handl']['axes'], 0.8, atol=1e-3))
            self.assertEqual(bake.declared(out), {'bare': {'forearm'}, 'skin': {'bicep'}})
            self.assertEqual(list(bake.stored(out)), ['handl'])
            with self.assertRaises(ValueError):
                refit.run(kept, kept, 'pack', 'pmh0', 'pfh0')
            # a sleeve sharing its slot with the body's skin: carried without the male's, given the female's
            bake.store({'bicepl': sleeved()}, Path(folder) / 'sleeve', {'skin': ['bicep']})
            with mock.patch.object(measure, 'body', side_effect=lambda pack, name: bodies[name]), \
                    mock.patch.object(seams, 'load_contract', return_value=None), \
                    mock.patch.object(bodyskin, 'body_part', return_value=body_arm()) as read:
                with self.assertRaisesRegex(ValueError, "give the body's textures"):
                    refit.run(Path(folder) / 'sleeve', out / 'a', 'pack', 'pmh0', 'pfh0')
                refit.run(Path(folder) / 'sleeve', out / 'b', 'pack', 'pmh0', 'pfh0', body_textures='maps')
            self.assertEqual(read.call_args.args[:4], ('pack', 'maps', 'pfh0', 'bicepl'))
            self.assertEqual(int(bake.stored(out / 'b')['bicepl']['skin'].sum()), len(body_arm()['f']))


if __name__ == '__main__':
    unittest.main()
