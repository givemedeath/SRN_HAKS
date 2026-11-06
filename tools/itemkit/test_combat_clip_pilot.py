import unittest

import numpy as np

from tools.itemkit import combat_clip_pilot as pilot

SOURCE = '''newanim custom11lp old
  length 1.0
  transtime 0.1
  animroot rootdummy
  event 0.0 hit
  node dummy rootdummy
    parent old
    positionkey
      0.0 0.0 0.0 1.0
      1.0 0.0 0.0 1.2
    endlist
  endnode
  node trimesh rbicep_g
    parent torso_g
    positionkey
      0.0 0.2 0.0 0.3
    endlist
    orientationkey
      0.0 0.0 1.0 0.0 1.5
    endlist
  endnode
  node trimesh world_mp5
    parent rhand
    orientationkey
      0.0 0.0 1.0 0.0 1.0
    endlist
  endnode
doneanim custom11lp old
'''


class Retarget(unittest.TestCase):
    def fitted(self):
        return pilot.retarget(pilot.read_clip(SOURCE, 'custom11lp'), {'rootdummy', 'rbicep_g'},
                              np.array([0., 0., 1.]), np.array([.1, 0., 2.]))

    def test_drops_foreign_nodes_and_limb_positions(self):
        fitted, dropped = self.fitted()
        self.assertEqual(dropped, ['world_mp5'])
        self.assertNotIn('position', fitted['nodes']['rbicep_g'])
        self.assertIn('orientation', fitted['nodes']['rbicep_g'])

    def test_scales_the_root_to_the_target_bind(self):
        fitted, _ = self.fitted()
        self.assertEqual(fitted['nodes']['rootdummy']['position'][:, 1:4].tolist(), [[.1, 0., 2.], [.1, 0., 2.4]])

    def test_keeps_rotation_keys_and_events(self):
        fitted, _ = self.fitted()
        self.assertEqual(fitted['nodes']['rbicep_g']['orientation'].tolist(), [[0., 0., 1., 0., 1.5]])
        self.assertEqual(fitted['events'], [('0.0', 'hit')])

    def test_text_keeps_the_whole_tree_and_the_torso_root(self):
        fitted, _ = self.fitted()
        tree = [('dummy', 'owner', 'NULL'), ('dummy', 'rootdummy', 'owner'), ('trimesh', 'rbicep_g', 'rootdummy')]
        text = pilot.clip_text('c11lp_gm', 'owner', {**fitted, 'animroot': 'torso_g'}, tree)
        for name in ('owner', 'rootdummy', 'rbicep_g'):
            self.assertIn(' ' + name + '\n', text)
        self.assertIn('animroot torso_g', text)

    def test_quaternion_matches_axis_angle(self):
        value = pilot.quaternions(np.array([[0., 0., 1., 0., np.pi]]))[0]
        self.assertTrue(np.allclose(value, [0., 1., 0., 0.]))

    def test_counted_keys_are_read(self):
        counted = SOURCE.replace('    orientationkey\n      0.0 0.0 1.0 0.0 1.5\n    endlist\n',
                                 '    orientationkey 2\n      0.0 0.0 1.0 0.0 1.5\n      1.0 0.0 1.0 0.0 0.5\n')
        rows = pilot.read_clip(counted, 'custom11lp')['nodes']['rbicep_g']['orientation']
        self.assertEqual(rows.tolist(), [[0., 0., 1., 0., 1.5], [1., 0., 1., 0., .5]])

    def test_unread_key_tables_are_refused(self):
        with self.assertRaises(ValueError):
            pilot.read_keys('    scalekey\n      0.0 1.0\n    endlist\n')

    def test_bezier_keys_are_refused(self):
        with self.assertRaises(ValueError):
            pilot.read_clip(SOURCE.replace('positionkey', 'positionbezierkey'), 'custom11lp')


if __name__ == '__main__':
    unittest.main()
