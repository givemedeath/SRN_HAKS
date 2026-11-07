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


class Support(unittest.TestCase):
    def rig(self):
        def node(parent, x=0., y=0., z=0.):
            return {'parent': parent, 'controls': {8: {'times': np.array([0.]), 'values': np.array([[x, y, z]])}}}
        return {'name': 'test', 'nodes': {
            'rootdummy': node(None, z=1.), 'torso_g': node('rootdummy', z=.3),
            'rbicep_g': node('torso_g', x=.2), 'rforearm_g': node('rbicep_g', z=-.15), 'rhand_g': node('rforearm_g', z=-.15),
            'rhand': node('rhand_g', z=-.1),
            'lbicep_g': node('torso_g', x=-.2), 'lforearm_g': node('lbicep_g', z=-.42), 'lhand_g': node('lforearm_g', z=-.42),
            'lhand': node('lhand_g', z=-.08)}}

    def clip(self):
        forward = [0., 1., 0., 0., 0.]
        return {'length': 1., 'transition': .1, 'animroot': 'rootdummy', 'events': [], 'nodes': {
            'rbicep_g': {'orientation': np.array([[0., 1., 0., 0., 1.2], [1., 1., 0., 0., 1.3]])},
            'rforearm_g': {'orientation': np.array([[0., 1., 0., 0., .2]])},
            'rhand_g': {'orientation': np.array([forward])},
            'lbicep_g': {'orientation': np.array([[0., 1., 0., 0., 1.]])}}}

    def marks(self, tilt=.1):
        barrel = np.array([0., np.sin(tilt), -np.cos(tilt)])
        up = np.array([0., -barrel[2], barrel[1]])
        verts = np.array([[0., y, z] for z in np.arange(-.34, -.1, .005) for y in (.04, .1)])
        return {'barrel': barrel, 'up': up, 'verts': verts, 'front': -.25, 'rear': -.19, 'pump': None,
                'correction': np.array([[1., 0., 0.], up, -barrel])}

    def test_axis_row_round_trips(self):
        matrix = pilot.rotation_between(np.array([1., 2., 3.]), np.array([-2., 1., .5]))
        row = np.array([pilot.axis_row(.5, matrix)])
        self.assertTrue(np.allclose(pilot.quaternion_matrix(pilot.quaternions(row)[0]), matrix))

    def test_rotation_refuses_opposite_directions(self):
        with self.assertRaises(ValueError):
            pilot.rotation_between(np.array([1., 0., 0.]), np.array([-1., 0., 0.]))

    def test_rifle_marks_read_the_tilt_of_the_top_line(self):
        rows = [f'{0.:.3f} {.2 - z * .25:.4f} {z:.3f}' for z in np.arange(-.34, 0., .01)]
        text = f'node trimesh gun\n  verts {len(rows)}\n' + '\n'.join(rows) + '\n  faces 0\n'
        marks = pilot.weapon_marks([text], {'barrel': (-.33, -.03), 'front': -.25, 'rear': -.19, 'pump': None})
        self.assertAlmostEqual(marks['tiltDegrees'], np.degrees(np.arctan(.25)), places=2)
        self.assertTrue(np.allclose(marks['correction'] @ marks['barrel'], [0., 0., -1.]))

    def test_left_palm_lands_on_the_fore_end_and_the_barrel_keeps_the_aim(self):
        root, clip, marks = self.rig(), self.clip(), self.marks()
        solved = pilot.solve_support(clip, root, marks)
        fit = pilot.fit_errors(solved, clip, root, marks)
        self.assertLess(fit['contactMetres'], .005)
        self.assertLess(fit['aimDegrees'], .01)

    def test_short_arms_slide_back_along_the_fore_end(self):
        root, clip, marks = self.rig(), self.clip(), self.marks()
        far = pilot.solve_support(clip, root, marks)['support'][1][0, 2]
        root['nodes']['lforearm_g']['controls'][8]['values'] = np.array([[0., 0., -.35]])
        root['nodes']['lhand_g']['controls'][8]['values'] = np.array([[0., 0., -.35]])
        self.assertGreater(pilot.solve_support(clip, root, marks)['support'][1][0, 2], far)

    def test_pump_follows_the_source_hand_along_the_fore_end(self):
        root, clip, marks = self.rig(), self.clip(), self.marks()
        clip['nodes']['lbicep_g']['orientation'] = np.array([[0., 1., 0., 0., 1.], [.5, 1., 0., 0., 1.4], [1., 1., 0., 0., 1.]])
        solved = pilot.solve_support(clip, root, {**marks, 'pump': -.2})
        travel = solved['support'][1][:, 2]
        self.assertAlmostEqual(travel.min(), -.25)
        self.assertAlmostEqual(travel.max(), -.2)
        self.assertLess(pilot.fit_errors(solved, clip, root, marks)['contactMetres'], .02)

    def test_weapon_is_pulled_in_when_sliding_is_not_enough(self):
        root, clip, marks = self.rig(), self.clip(), self.marks()
        root['nodes']['lforearm_g']['controls'][8]['values'] = np.array([[0., 0., -.31]])
        root['nodes']['lhand_g']['controls'][8]['values'] = np.array([[0., 0., -.31]])
        solved = pilot.solve_support(clip, root, marks)
        fit = pilot.fit_errors(solved, clip, root, marks)
        self.assertGreater(solved['pull'], 0.)
        self.assertLess(fit['contactMetres'], .005)
        self.assertLess(fit['aimDegrees'], .01)

    def test_unreachable_fore_end_is_refused(self):
        root, clip, marks = self.rig(), self.clip(), self.marks()
        root['nodes']['lforearm_g']['controls'][8]['values'] = np.array([[0., 0., -.05]])
        root['nodes']['lhand_g']['controls'][8]['values'] = np.array([[0., 0., -.05]])
        with self.assertRaises(ValueError):
            pilot.solve_support(clip, root, marks)


if __name__ == '__main__':
    unittest.main()
