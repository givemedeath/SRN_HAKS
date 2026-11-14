"""Parts carried from one body to another (tools/armorkit/refit.py), on the test rig's left arm."""
import math
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from . import bake, refit
from .test_bake import arm, contract, part, rig


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


def hand(scale=1.0):
    """The body's own left hand: a short tube past the wrist plane (x = 0.55), `scale` times the size."""
    piece = arm(0.55, 0.55 + 0.12 * scale, 0.03 * scale)
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
        self.assertEqual(scales, {'along': 0.9, 'across': 0.9})

    def test_a_body_narrower_than_its_length_says_scales_the_part_across_its_axis_apart(self):
        target = (moved(rig(), np.eye(3), 0.9, np.zeros(3)), {'handl': hand(0.9)})
        linear, offset, scales = refit.placement('forel', self.source, target, two_bodies(0.04, 0.028), ('a', 'b'))
        self.assertEqual(scales, {'along': 0.9, 'across': 0.7})
        forearm = arm(0.3, 0.55, 0.05)
        carried = forearm['v'] @ linear.T + offset
        self.assertTrue(np.allclose(np.linalg.norm(carried[:, 1:], axis=1), 0.7 * 0.05))  # round, and as much narrower as the rings
        self.assertTrue(np.allclose(carried[:, 0], 0.9 * forearm['v'][:, 0]))  # and as long as the joints lie apart
        # within `UNIFORM` of each other, one scale: their geometric mean
        linear, _, scales = refit.placement('forel', self.source, target, two_bodies(0.04, 0.04 * 0.88), ('a', 'b'))
        self.assertAlmostEqual(scales['along'], math.sqrt(0.9 * 0.88), places=4)
        self.assertTrue(np.allclose(linear, math.sqrt(0.9 * 0.88) * np.eye(3)))

    def test_a_part_with_one_joint_turns_as_the_part_beside_it_and_scales_by_the_bodys_own(self):
        target = (moved(rig(), self.rotation, 0.9, self.offset), {'handl': hand(0.8)})
        linear, offset, scales = refit.placement('handl', self.source, target)
        self.assertAlmostEqual(scales['along'], 0.8, places=3)
        self.assertTrue(np.allclose(linear, scales['along'] * self.rotation))
        wrist = np.array((0.55, 0.0, 0.0))
        self.assertTrue(np.allclose(linear @ wrist + offset, 0.9 * self.rotation @ wrist + self.offset))  # its joint where the other body's is


class RefitTests(unittest.TestCase):
    def test_parts_are_carried_with_their_normals_and_one_with_the_bodys_skin_is_refused(self):
        source = (rig(), {'handl': hand()})
        target = (moved(rig(), about_z(90.0), 1.0, np.zeros(3)), {'handl': hand()})
        glove = part(faces=1)
        glove['v'] = glove['v'] + (0.6, 0.0, 0.0)
        out, report = refit.refit({'handl': glove, 'bicepl': {**part(), 'skin': np.zeros(1, bool)}}, source, target, ['handl'])
        self.assertEqual(report['handl']['degrees'], 90.0)
        self.assertTrue(np.allclose(out['handl']['n'], [[0.0, 0.0, 1.0]] * 3))  # turned about z, a normal along z stays
        self.assertTrue(np.allclose(out['handl']['v'], glove['v'] @ about_z(90.0).T))
        self.assertTrue(np.array_equal(out['handl']['rgb'], glove['rgb']))  # nothing else changes
        with self.assertRaisesRegex(ValueError, "body's own skin"):
            refit.refit({'bicepl': {**part(), 'skin': np.zeros(1, bool)}}, source, target)

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
        self.assertEqual((report['forel']['along'], report['forel']['across']), (0.9, 0.9))  # no contract: one scale
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

    def test_the_command_keeps_the_refit_parts_with_the_slots_the_brief_gave(self):
        with tempfile.TemporaryDirectory() as folder:
            kept, out = Path(folder) / 'kept', Path(folder) / 'out'
            glove = part(faces=1)
            bake.store({'handl': glove}, kept, {'bare': ['forearm'], 'skin': ['bicep']})
            bodies = {'pmh0': (rig(), {'handl': hand()}), 'pfh0': (rig(), {'handl': hand(0.8)})}
            with mock.patch('tools.armorkit.measure.body', side_effect=lambda pack, name: bodies[name]), \
                    mock.patch('tools.armorkit.seams.load_contract', return_value=None):
                report = refit.run(kept, out, 'pack', 'pmh0', 'pfh0')
            self.assertAlmostEqual(report['handl']['along'], 0.8, places=3)
            self.assertEqual(bake.declared(out), {'bare': {'forearm'}, 'skin': {'bicep'}})
            self.assertEqual(list(bake.stored(out)), ['handl'])
            with self.assertRaises(ValueError):
                refit.run(kept, kept, 'pack', 'pmh0', 'pfh0')


if __name__ == '__main__':
    unittest.main()
