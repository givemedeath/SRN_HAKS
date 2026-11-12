"""The client checks' layouts are worked out from each model's size; the client itself is not started here."""
import math
import unittest

from tools.armorkit.client_fixture import field, gff_float

from . import checks, prop_fixture

MODELS = {'ek_desk': {'placeable': {'label': 'Check'}, 'lit': [{'box': [[0, 0, 0], [1, 1, 1]]}]}, 'ek_crate': {'placeable': {'label': 'Check'}},
          'ek_sign': {'placeable': {'label': 'Check'}, 'lit': [{'box': [[0, 0, 0], [1, 1, 1]]}], 'lift': 3.0}, 'ek_hall': {'tiles': {}, 'lit': [{'box': [[0, 0, 0], [1, 1, 1]]}]}}
SIZES = {'ek_desk': [2.0, 1.0, 1.1], 'ek_crate': [1.0, 1.0, 1.0], 'ek_sign': [1.5, 0.2, 1.0]}


def door(x, y, bearing=-math.pi):
    return {'X': gff_float(x), 'Y': gff_float(y), 'Bearing': gff_float(bearing), 'Tag': field('cexostring', 'Door'),
            'LinkedTo': field('cexostring', ''), 'LinkedToFlags': field('byte', 0), 'Appearance': field('dword', 58)}


class CheckTests(unittest.TestCase):
    def test_another_sessions_client_is_waited_for_and_never_closed(self):
        answers, slept = [[4242], [4242], []], []
        checks.wait_for_clients(running=lambda: answers.pop(0), sleep=slept.append)
        self.assertEqual((answers, slept), ([], [10, 10]))
        with self.assertRaisesRegex(ValueError, 'still running after 0 minutes'):
            checks.wait_for_clients(0.0, running=lambda: [4242], sleep=slept.append)

    def test_props_stand_in_a_row_each_seen_from_three_sides_with_figures_for_scale(self):
        props, shots, people = checks.row_of_props(MODELS, SIZES, ['ek_desk', 'ek_crate', 'ek_sign'])
        self.assertEqual([(one['model'], one['position'], one['static']) for one in props],
                         [('ek_desk', [13.0, 40.0], False), ('ek_crate', [20.5, 40.0], True), ('ek_sign', [27.75, 40.0], False)])  # six metres between them; a lit prop is reached by script
        self.assertEqual([shot['label'] for shot in shots[:3]], ['ek_desk-front', 'ek_desk-back', 'ek_desk-side'])
        self.assertEqual((shots[0]['stand'], shots[1]['stand'], shots[2]['stand']), ([13.0, 38.3], [13.0, 41.7], [15.2, 40.0]))
        self.assertEqual((shots[0]['distance'], shots[6]['distance']), (3.5, 6.0))  # the sign hangs three metres up: seen from further off
        self.assertEqual((len(shots), len(people)), (9, 6)); self.assertEqual(people[0]['position'], [14.8, 39.2])
        with self.assertRaisesRegex(ValueError, 'No such model'):
            checks.row_of_props(MODELS, SIZES, ['ek_other'])
        with self.assertRaisesRegex(ValueError, 'look at fewer at a time'):
            checks.row_of_props(MODELS, SIZES, ['ek_desk'] * 10)

    def test_lit_props_are_seen_lit_put_out_by_script_and_on_again(self):
        tags = {'ek_desk': 'GetObjectByTag("t_p0")', 'ek_sign': 'GetObjectByTag("t_p1")'}
        props, shots, people = checks.rows_of_lights(MODELS, SIZES, tags, {'ek_sign'})
        self.assertEqual([one['model'] for one in props], ['ek_desk', 'ek_sign'])  # a lit tile group is no prop; a prop that is not lit has no lights
        self.assertEqual([shot['label'] for shot in shots], ['row0-lit', 'row0-out', 'row0-on-again']); self.assertNotIn('run', shots[0])
        self.assertEqual(shots[1]['run'], 'ReplaceObjectTexture(GetObjectByTag("t_p0"),"ek_desk","ek_desk_o");ReplaceObjectTexture(GetObjectByTag("t_p1"),"ek_sign","ek_sign_o");'
                                          'ReplaceObjectTexture(GetObjectByTag("t_p1"),"ek_sign_h","ek_off");')  # only a model with a halo sheet has one put out
        self.assertEqual(shots[2]['run'].count('ReplaceObjectTexture'), 3); self.assertNotIn('_o"', shots[2]['run'])
        many = {f'ek_l{index}': MODELS['ek_desk'] for index in range(7)}; sizes = {name: [1.0, 1.0, 1.0] for name in many}
        props, shots, _ = checks.rows_of_lights(many, sizes, {name: 'OBJECT_SELF' for name in many}, set())
        self.assertEqual(sorted({one['position'][1] for one in props}), [46.0, 62.0]); self.assertEqual(len(shots), 6)  # five to a row
        self.assertEqual([shot['label'] for shot in shots if 'run' in shot], ['row0-out', 'row0-on-again'])  # the script runs once, before the first row's shot
        with self.assertRaisesRegex(ValueError, 'no lit props'):
            checks.rows_of_lights({'ek_crate': MODELS['ek_crate']}, SIZES, {}, set())
        with self.assertRaisesRegex(ValueError, 'twenty at most'):
            checks.rows_of_lights({f'ek_l{index}': MODELS['ek_desk'] for index in range(21)}, {}, {}, set())

    def test_a_tile_group_is_seen_from_its_front_its_door_and_along_its_sides(self):
        shots = checks.group_shots(3, 2, [1.0, 9.0], 'day')
        self.assertEqual([shot['label'] for shot in shots], ['east-slant', 'east-square', 'east-far-slant', 'nw-corner', 'west-slant', 'south-run', 'north-run', 'se-corner',
                                                             'front', 'door', 'east-above'])
        front, at_door = shots[8], shots[9]
        self.assertEqual((front['stand'], front['distance']), ([45.0, 50.0], 37.5))  # the group's middle is at (45, 40): south-west tile (3, 3), 30 m by 20 m
        self.assertEqual(at_door['stand'], [46.0, 51.2])
        for shot in shots[:8]:  # the slanting views stand inside the group's edge
            self.assertTrue(30.0 < shot['stand'][0] < 60.0 and 30.0 < shot['stand'][1] < 50.0, shot)
        self.assertNotIn('door', [shot['label'] for shot in checks.group_shots(3, 2, None, 'night')])
        near = checks.group_shots(3, 2, [1.0, 9.0], 'near')
        self.assertEqual([shot['label'] for shot in near], ['near-door', 'near-front', 'near-side', 'far', 'behind', 'behind-side'])
        self.assertIn('SetCutsceneMode(pc,FALSE)', near[0]['run']); self.assertFalse(any('run' in shot for shot in near[1:]))  # the player is freed once: upper storeys hide only outside cutscene mode
        doorless = checks.group_shots(2, 2, None, 'near'); self.assertEqual(doorless[0]['label'], 'near-front'); self.assertIn('run', doorless[0])

    def test_doors_are_chained_through_waypoints_in_front_of_them(self):
        walk = [('ektdg_a', door(45.0, 50.0)), ('ektdg_a', door(20.0, 30.0, bearing=-math.pi / 2)), ('ektud_a', door(40.0, 40.0))]
        waypoints = checks.chained(walk)
        self.assertEqual({area: len(found) for area, found in waypoints.items()}, {'ektdg_a': 2, 'ektud_a': 1})
        first, second = waypoints['ektdg_a']
        self.assertEqual((round(first['XPosition']['value'], 3), round(first['YPosition']['value'], 3)), (45.0, 53.5))  # a door whose bearing is -pi looks out north
        self.assertEqual((round(first['XOrientation']['value'], 3), round(first['YOrientation']['value'], 3)), (0.0, -1.0))  # the waypoint faces the door
        self.assertEqual((round(second['XPosition']['value'], 3), round(second['YPosition']['value'], 3)), (16.5, 30.0))
        self.assertEqual([(one['Tag']['value'], one['LinkedTo']['value'], one['LinkedToFlags']['value']) for _, one in walk],
                         [('ek_d1', 'ek_w2', 2), ('ek_d2', 'ek_w3', 2), ('ek_d3', 'ek_w1', 2)])  # the last leads back to the first
        self.assertEqual(walk[0][1]['Appearance']['value'], 58)  # nothing else of a door is changed
        with self.assertRaisesRegex(ValueError, 'two at least'):
            checks.chained(walk[:1])

    def test_the_watch_logs_where_the_player_is_and_the_stages_are_read_back(self):
        script = checks.watch_script(3, (45.0, 53.5), 270.0, 20, 8.0)
        self.assertIn('Probe("ek_d1"); Probe("ek_d2"); Probe("ek_d3");', script); self.assertIn('if(n>=20)', script)
        self.assertIn('Vector(45.000,53.500,0.0),270.0', script); self.assertIn('DelayCommand(8.0,Place(pc))', script); script.encode('ascii')
        prefix = prop_fixture.LOG_PREFIX
        lines = [f'{prefix} enter', f'{prefix} probe=ek_d1 valid=1 doorarea=ektdg_a target=ek_w2 targetarea=ektdg_a z= 0.000',
                 f'{prefix} watch=0 area=ektdg_a x= 45.000 y= 53.500 z=  0.000', f'{prefix} watch=1 area=ektdg_a x= 45.100 y= 53.400 z=  0.000',
                 f'{prefix} watch=2 area= x=  0.000 y=  0.000 z=  0.000',  # between areas the player is nowhere
                 f'{prefix} watch=3 area=ektud_a x= 40.000 y= 43.500 z=  0.000', f'{prefix} done']
        self.assertEqual(checks.stages(lines), [(0, 'ektdg_a', 45.0, 53.5), (3, 'ektud_a', 40.0, 43.5)])


if __name__ == '__main__':
    unittest.main()
