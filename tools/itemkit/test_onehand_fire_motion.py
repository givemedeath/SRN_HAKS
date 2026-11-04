"""Focused invariants for additive one-handed firearm motion."""
import unittest
import numpy as np
from tools.itemkit.onehand_fire_motion import rotation_between, fitted_frame, alias_weapon_clips


class MotionRotationTests(unittest.TestCase):
    def test_weapon_alias_retains_stock_clip_and_payload(self):
        prefix = 'newmodel bow\nbeginmodelgeom bow\nendmodelgeom bow\n'
        clip = 'newanim bowshot bow\n  length 1\n  transtime 0.25\n  event 0.5 hit\n  node dummy drawdummy\n    positionkey 2\n      0 0 0 0.1\n      0.5 0 0 0.8\n  endnode\ndoneanim bowshot bow'
        text = prefix+clip+'\ndonemodel bow\n'
        result = alias_weapon_clips(text, {'bowshot': 'srbowfire'})
        self.assertTrue(result.startswith(prefix+clip+'\n'))
        self.assertIn(clip.replace('anim bowshot bow', 'anim srbowfire bow'), result)
        self.assertTrue(result.endswith('donemodel bow\n'))
        windows = text.replace('\n', '\r\n')
        self.assertTrue(alias_weapon_clips(windows, {'bowshot': 'srbowfire'}).startswith(
            (prefix+clip+'\n').replace('\n', '\r\n')))
        with self.assertRaises(ValueError):
            alias_weapon_clips(result, {'bowshot': 'srbowfire'})
        with self.assertRaises(ValueError):
            alias_weapon_clips(text, {'xbowshot': 'srcbfire'})

    def test_receiver_top_is_not_weapon_width(self):
        # Independent source landmarks under the actual Ingram fit: muzzle -X,
        # receiver top +Z, width +Y. This catches the previous 90-degree roll.
        fit = {'fitMatrix': [[0, -.47534, 0, 0], [-.06818, 0, .47043, 0],
                             [-.47043, 0, -.06818, 0], [0, 0, 0, 1]]}
        frame = fitted_frame(fit)
        target = np.column_stack(([0., 1., 0.], [0., 0., 1.], [1., 0., 0.]))
        rotation = target @ frame.T
        matrix = np.array(fit['fitMatrix'])[:3, :3]
        for source, expected in [([-1, 0, 0], [0, 1, 0]), ([0, 0, 1], [0, 0, 1])]:
            transformed = matrix @ source
            np.testing.assert_allclose(rotation @ transformed / np.linalg.norm(transformed), expected, atol=1e-12)
        self.assertAlmostEqual(np.linalg.det(rotation), 1.)

    def test_alignment_preserves_length_and_handedness(self):
        for source, target in [([0, 0, -2], [.3, .8, -.1]), ([1, 2, 3], [-2, 1, 4])]:
            source, target = np.array(source, float), np.array(target, float)
            matrix = rotation_between(source, target)
            np.testing.assert_allclose(matrix @ source / np.linalg.norm(source), target / np.linalg.norm(target), atol=1e-12)
            np.testing.assert_allclose(matrix.T @ matrix, np.eye(3), atol=1e-12)
            self.assertAlmostEqual(np.linalg.det(matrix), 1.)

    def test_ambiguous_flip_is_rejected(self):
        with self.assertRaises(ValueError):
            rotation_between(np.array([0., 0., 1.]), np.array([0., 0., -1.]))


if __name__ == '__main__':
    unittest.main()
