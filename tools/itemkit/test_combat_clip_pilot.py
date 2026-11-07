import re
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
        text = pilot.clip_text('fire_rfl_tm', 'owner', {**fitted, 'animroot': 'torso_g'}, tree)
        for name in ('owner', 'rootdummy', 'rbicep_g'):
            self.assertIn(' ' + name + '\n', text)
        self.assertIn('animroot torso_g', text)

    def test_hand_nodes_are_held_flat_for_the_whole_clip(self):
        fitted, _ = pilot.retarget(pilot.read_clip(SOURCE, 'custom11lp'), {'rootdummy', 'rhand'},
                                   np.array([0., 0., 1.]), np.array([.1, 0., 2.]))
        self.assertEqual(fitted['nodes']['rhand']['orientation'].tolist(), [[0., 1., 0., 0., 0.], [1., 1., 0., 0., 0.]])

    def test_reload_starts_and_ends_raised(self):
        rows = np.array([[0., 0., 0., 0., 0.], [.3, 1., 0., 0., 1.], [1.7, 1., 0., 0., .8], [2., 0., 0., 0., 0.]])
        held = pilot.hold_ends({'transition': .15, 'nodes': {'lbicep_g': {'orientation': rows}}})
        self.assertEqual(held['nodes']['lbicep_g']['orientation'][:, 4].tolist(), [1., 1., .8, .8])
        self.assertEqual(held['nodes']['lbicep_g']['orientation'][:, 0].tolist(), [0., .3, 1.7, 2.])
        self.assertEqual(held['transition'], pilot.RELOAD_BLEND)

    def test_fixed_contact_is_used_as_given(self):
        self.assertEqual(pilot.support_point({'fixed': (-.03, 0., .03)}, 0.).tolist(), [-.03, 0., .03])

    def test_palm_leaves_the_magazine_only_for_the_belt(self):
        weights = pilot.contact_weight(np.array([0., .3, .9, 1.47, 2.]))
        self.assertEqual(weights.tolist(), [1., 1., 0., 1., 1.])

    def test_rest_clip_holds_the_first_pose_without_events(self):
        rows = np.array([[0., 1., 0., 0., .5], [.4, 1., 0., 0., .9]])
        clip = {'length': .8, 'transition': .1, 'events': [(.2, 'hit')],
                'nodes': {'rhand_g': {'orientation': rows}, 'torso_g': {'orientation': rows}}}
        held = pilot.rest_clip(clip)
        self.assertEqual(held['nodes']['rhand_g']['orientation'].tolist(), [[0., 1., 0., 0., .5], [1., 1., 0., 0., .5]])
        self.assertEqual((held['length'], held['events']), (1., []))

    def test_ready_clip_keeps_the_hold_and_adds_the_stock_motion(self):
        hold = np.array([[0., 1., 0., 0., .5], [.4, 1., 0., 0., .9]])
        clip = {'length': .8, 'transition': .1, 'events': [],
                'nodes': {'torso_g': {'orientation': hold}, 'rbicep_g': {'orientation': hold},
                          'rootdummy': {'position': np.array([[0., 0., 0., 1.], [.4, 0., 0., 2.]])}}}
        sway = np.array([[0., 1., 0., 0., .2], [.5, 1., 0., 0., .3], [1., 1., 0., 0., .2]])
        stock = {'nodes': {'torso_g': {'orientation': sway},
                           'rootdummy': {'position': np.array([[0., 0., 0., 3.], [.5, 0., 0., 3.1], [1., 0., 0., 3.]])}}}
        ready = pilot.ready_clip(clip, stock, 2.)
        self.assertEqual(ready['nodes']['rbicep_g']['orientation'][:, 4].tolist(), [.5, .5])
        self.assertAlmostEqual(ready['nodes']['torso_g']['orientation'][1, 4], .6)
        self.assertAlmostEqual(ready['nodes']['torso_g']['orientation'][2, 4], .5)
        self.assertAlmostEqual(ready['nodes']['rootdummy']['position'][1, 3], 1.2)

    def test_every_clip_name_is_action_weapon_slot(self):
        names = [*pilot.CLIPS.values(), *pilot.READY.values(), *pilot.RELOAD_VARIANTS]
        self.assertEqual(len(names), len(set(names)))
        for name in names:
            self.assertRegex(name, r'^(fire|ready|reload|throw)_(rfl|sg|pst|smg|dpst|dsmg|dual|gren)$')
        self.assertTrue(all(len(slot) == 2 for slot in pilot.SLOTS))
        self.assertNotIn('gm', pilot.SLOTS)

    def test_shipped_model_has_every_clip_name(self):
        text = (pilot.REPO / 'srn_body' / 'a_ba_custom.mdl').read_text(encoding='cp1252')
        clips = set(re.findall(r'(?m)^newanim (\S+) a_ba_custom$', text))
        shared = {'fire_dpst', 'fire_dsmg', 'reload_dual', 'throw_gren'}
        codes = {*pilot.CLIPS.values(), *pilot.READY.values(), *pilot.RELOAD_VARIANTS}
        wanted = {f'{code}_{slot}' for code in codes for slot in pilot.SLOTS}
        wanted |= {f'{code}_{slot}l' for code in codes - shared for slot in pilot.SLOTS if slot.endswith('f')}
        self.assertEqual(wanted - clips, set())
        self.assertEqual(len(wanted), 175)

    def test_delayed_turns_a_loop_later(self):
        clip = {'length': 1., 'events': [('0.0', 'hit')], 'nodes': {
            'torso_g': {'orientation': np.array([[0., 1., 0., 0., 0.], [.2, 1., 0., 0., .4], [1., 1., 0., 0., 0.]]),
                        'position': np.array([[0., 0., 0., 0.], [.2, 0., 0., .1], [1., 0., 0., 0.]])}}}
        late = pilot.delayed(clip, .3)
        keys = late['nodes']['torso_g']
        position = {'times': keys['position'][:, 0], 'values': keys['position'][:, 1:4]}
        self.assertAlmostEqual(pilot.value(position, .5)[2], .1)
        self.assertAlmostEqual(pilot.value(position, 0.)[2], .1 * .3 / .8)
        rotation = {'times': keys['orientation'][:, 0], 'values': pilot.quaternions(keys['orientation'])}
        self.assertAlmostEqual(abs(pilot.value(rotation, .5, True)[0]), np.sin(.2), places=6)
        self.assertEqual(late['events'], clip['events'])
        self.assertEqual(keys['position'][[0, -1], 0].tolist(), [0., 1.])

    def test_kicked_replays_a_squeezed_weaker_kick(self):
        # Rest until 0.1, kicked back 0.1 at 0.2, recovered by 0.5, then still.
        clip = {'length': 1., 'events': [('0.0', 'hit')], 'nodes': {
            'torso_g': {'orientation': np.array([[0., 1., 0., 0., 0.], [.1, 1., 0., 0., 0.], [.2, 1., 0., 0., .4],
                                                 [.5, 1., 0., 0., 0.], [1., 1., 0., 0., 0.]]),
                        'position': np.array([[0., 0., 0., 0.], [.1, 0., 0., 0.], [.2, 0., 0., .1], [.5, 0., 0., 0.],
                                              [1., 0., 0., 0.]])}}}
        auto = pilot.kicked(clip, (.1, .5), (.3, .6), .1, .5)
        keys = auto['nodes']['torso_g']
        position = {'times': keys['position'][:, 0], 'values': keys['position'][:, 1:4]}
        rotation = {'times': keys['orientation'][:, 0], 'values': pilot.quaternions(keys['orientation'])}
        for kick in (.3, .6):
            self.assertAlmostEqual(pilot.value(position, kick + .025)[2], .05)
            self.assertAlmostEqual(abs(pilot.value(rotation, kick + .025, True)[0]), np.sin(.1), places=3)
        for still in (0., .2, .45, .55, .8, 1.):
            self.assertAlmostEqual(pilot.value(position, still)[2], 0.)
        self.assertEqual(auto['events'], clip['events'])

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
