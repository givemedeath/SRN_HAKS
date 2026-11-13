"""The client checks' layouts are worked out from each model's size; the client itself is not started here."""
import math
import unittest
from unittest import mock

import numpy as np

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
        crowd = {f'ek_l{index}': MODELS['ek_desk'] for index in range(21)}
        with self.assertRaisesRegex(ValueError, 'four rows at most'):
            checks.rows_of_lights(crowd, {name: [1.0, 1.0, 1.0] for name in crowd}, {name: 'OBJECT_SELF' for name in crowd}, set())
        # Wide props stand fewer to a row: a row ends where its view does.
        wide = {name: [12.0, 1.0, 3.0] for name in many}
        props, shots, _ = checks.rows_of_lights(many, wide, {name: 'OBJECT_SELF' for name in many}, set())
        self.assertEqual([sum(one['position'][1] == y for one in props) for y in (62.0, 46.0, 30.0, 14.0)], [2, 2, 2, 1]); self.assertEqual(len(shots), 12)
        self.assertLessEqual(max(one['position'][0] + 6.0 for one in props), checks.ROW_END)

    def test_a_check_refuses_a_mode_it_does_not_run(self):
        from argparse import Namespace
        from . import __main__ as command
        asked = dict(game='game', repo='.', models='set.json', root='root', name='ekt1', built=['built'], model=['ek_desk'], tileset=None, second_storey='0')
        with self.assertRaisesRegex(ValueError, 'check props has no --mode near: day or night'):
            command.command_check(Namespace(kind='props', mode='near', **asked))
        with self.assertRaisesRegex(ValueError, 'check lights has no --mode near: night'):  # the lights check is the night check
            command.command_check(Namespace(kind='lights', mode='near', **asked))
        with mock.patch.object(checks, 'lights', return_value={}) as lights, mock.patch.object(checks, 'props', return_value={}) as props, mock.patch('builtins.print'):
            command.command_check(Namespace(kind='lights', mode='night', **asked)); command.command_check(Namespace(kind='lights', mode=None, **asked))
            command.command_check(Namespace(kind='props', mode=None, **asked)); command.command_check(Namespace(kind='props', mode='night', **asked))
        self.assertEqual(lights.call_count, 2); self.assertEqual([call.kwargs['night'] for call in props.call_args_list], [False, True])

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
        east = checks.group_shots(3, 2, [1.0, 9.0], 'day', facing=0.0)[9]  # a door that opens east is seen from the east
        self.assertEqual((east['stand'], east['facing']), ([48.2, 49.0], 180.0))

    def test_a_groups_door_is_found_where_the_tiles_put_it_not_where_the_model_did(self):
        # The Saeder-Krupp yard: 3 by 3, its door on the north middle tile. The game set had it at (2.78, 3.68) on the
        # model, whose origin lay 7 metres from the middle of the tiles, cut about the fence far out in front.
        tiles = [{'column': column, 'row': row, 'doors': []} for row in range(3) for column in range(3)]
        tiles[7]['doors'] = [{'type': 58, 'x': 1.31, 'y': 0.74, 'z': 0.55, 'orientation': 180.0}]
        self.assertEqual([round(value, 2) for value in checks.laid_door({'columns': 3, 'rows': 3, 'tiles': tiles})], [1.31, 10.74])
        self.assertIsNone(checks.laid_door({'columns': 2, 'rows': 2, 'tiles': tiles[:4]}))

    def test_walkers_set_out_from_the_far_corners_for_the_door_round_the_group_and_into_its_yard(self):
        # The Saeder-Krupp yard, 3 by 3 from tile (3, 3), its door on the north middle tile and opening north; a target
        # south of the building and a yard with few ways in, each from the group's south-west corner.
        walkers = checks.walk_plan(3, 3, [1.31, 10.74], 90.0, {'south': (15.0, 4.0), 'pocket': (10.0, 6.0)})
        self.assertEqual(walkers, [{'label': 'door', 'start': [5.0, 5.0], 'target': [46.31, 56.94]},  # 1.2 m out of the door, as the yard's walker was sent
                                   {'label': 'south', 'start': [85.0, 85.0], 'target': [45.0, 34.0]},
                                   {'label': 'pocket', 'start': [83.5, 85.0], 'target': [40.0, 36.0]},  # the same far corner, a step along it
                                   {'label': 'pocket-near', 'start': [40.0, 25.0], 'target': [40.0, 36.0]}])  # and from the next tile out, south of it
        self.assertEqual([one['label'] for one in checks.walk_plan(2, 2, None, 90.0, {})], [])
        shots = checks.walk_shots(3, 3, walkers, 'skwalk')
        self.assertEqual([shot['label'] for shot in shots], ['go', 'w1', 'w2', 'w3', 'w4', 'w5', 'w6', 'at-door', 'at-south', 'at-pocket', 'at-pocket-near'])
        self.assertEqual((shots[0]['run'].count('ActionMoveToLocation('), shots[0]['run'].count('EffectCutsceneGhost()')), (4, 4)); self.assertIn('Vector(46.310,56.940,0.0)', shots[0]['run'])
        self.assertIn('GetObjectByTag("skwalk_h3")', shots[6]['run']); self.assertIn('walker=3 stage=6', shots[6]['run'])  # tagged as the fixture tags its people
        prop_fixture.enter_script(shots, hold=checks.WALK_HOLD)  # each shot's script is one line
        lines = ['ENVKIT enter shots=11', 'ENVKIT walker=0 stage=0 x=  5.000 y=  5.000', 'ENVKIT walker=0 stage=6 x= 46.100 y= 56.800',
                 'ENVKIT walker=1 stage=6 x= 50.000 y= 34.000', 'ENVKIT shot=6 target=w6 valid=1']
        found = checks.walks(lines, walkers[:2])
        self.assertEqual([(one['stage'], one['at'], one['short']) for one in found], [(6, [46.1, 56.8], 0.25), (6, [50.0, 34.0], 5.0)])
        with self.assertRaisesRegex(ValueError, 'never placed walker pocket'):
            checks.walks(lines, walkers[:3])

    def test_a_groups_lights_are_put_out_for_everyone_and_on_again(self):
        shots = checks.blackout_shots(3, 3, [('ek_sk_yard', False), ('ek_sk_yardp1', True)])
        self.assertEqual([shot['label'] for shot in shots], ['out', 'out-behind', 'lit-again'])
        self.assertEqual(shots[0]['run'], 'SetTextureOverride("ek_sk_yard_i","ek_sk_yard_o",pc);SetTextureOverride("ek_sk_yardp1_i","ek_sk_yardp1_o",pc);'
                                          'SetTextureOverride("ek_sk_yardp1_h","ek_off",pc);')
        self.assertIn('SetTextureOverride("ek_sk_yard_i","",pc);', shots[2]['run']); self.assertNotIn('run', shots[1])
        self.assertEqual((shots[0]['stand'], shots[0]['facing'], shots[1]['stand'], shots[1]['facing']), ([45.0, 37.5], 90, [45.0, 55.5], 270))
        self.assertEqual(checks.blackout_shots(3, 3, []), [])

    def test_a_capture_made_after_its_shot_has_passed_is_refused_not_mislabelled(self):
        """The rail freight depot (2026-11-13): the client stalled for twenty seconds on the sixth shot, and the last view
        was captured five times under five names."""
        import tempfile
        from pathlib import Path
        self.assertIsNone(prop_fixture.late(100, 103.0, 6.0)); self.assertEqual(prop_fixture.late(100, 123.0, 6.0), 23.0)
        self.assertIsNone(prop_fixture.late(86399, 3.0, 6.0)); self.assertIsNone(prop_fixture.late(None, 500.0, 6.0))  # past midnight; no stamp
        with tempfile.TemporaryDirectory() as scratch:
            user = Path(scratch) / 'user'; (user / 'logs').mkdir(parents=True); captures = Path(scratch) / 'captures'; captures.mkdir()
            record = {'userDirectory': str(user), 'module': 'ekx.mod', 'start': 1.0, 'hold': 6.0, 'shots': ['a', 'b']}

            def shoot(pid, path):
                Path(path).write_bytes(b'png'); return path

            def go(stamps):
                (user / 'logs' / 'nwclientLog1.txt').write_text(''.join(f'[Fri Nov 13 {stamp}] {line}' + chr(10) for stamp, line in zip(
                    stamps, ['ENVKIT shot=0 target=a valid=1', 'ENVKIT shot=1 target=b valid=1', 'ENVKIT done'])), encoding='cp1252')
                process = mock.Mock(pid=7); process.poll.return_value = None
                with mock.patch.object(prop_fixture.client, 'start', return_value=process), mock.patch.object(prop_fixture.client, 'stop'), \
                        mock.patch.object(prop_fixture, 'capture', side_effect=shoot), mock.patch.object(prop_fixture.time, 'sleep'), \
                        mock.patch.object(prop_fixture, 'clock', return_value=13 * 3600 + 58 * 60 + 25.0):
                    return prop_fixture.run('game', record, captures)
            self.assertEqual(len(go(['13:58:21', '13:58:23', '13:58:24'])['captures']), 2)
            for path in captures.iterdir():
                path.unlink()
            with self.assertRaisesRegex(ValueError, r'show a later view: a \(25 s\)'):
                go(['13:58:00', '13:58:22', '13:58:24'])
            self.assertEqual(sorted(path.name for path in captures.iterdir()), ['shot-00-a-late.png', 'shot-01-b.png'])

    def test_a_check_area_holds_the_group_with_ground_all_round(self):
        """The rail freight depot, 8 by 8 (2026-11-13), did not fit the area of 9 tiles that held the 3 by 3 groups."""
        self.assertEqual([checks.area_size(3, 3), checks.area_size(2, 3), checks.area_size(8, 8), checks.area_size(8, 5)], [9, 9, 14, 14])
        for columns, rows in ((1, 1), (3, 3), (8, 8), (12, 7)):
            size = checks.area_size(columns, rows)
            self.assertLessEqual(max(columns, rows) + checks.MARGIN + 1, size)  # as the check requires
            self.assertGreaterEqual(size - max(columns, rows) - checks.MARGIN, checks.MARGIN)  # ground beyond the far side too
        # A walker from a far corner has as long to arrive for each metre of a larger area.
        self.assertEqual(checks.walk_hold(9), checks.WALK_HOLD); self.assertAlmostEqual(checks.walk_hold(14) / 14, checks.WALK_HOLD / 9)

    def test_a_walk_check_needs_the_walk_picture_of_its_build(self):
        import json
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as scratch:
            built = Path(scratch) / 'tiles1' / 'ek_yard'; built.mkdir(parents=True)
            (built / 'report.json').write_text(json.dumps({'columns': 1, 'rows': 1, 'tiles': []}), encoding='utf-8')
            with mock.patch.object(checks.convert, 'load_models', return_value={'ek_yard': {'tiles': {'ground': 'pavement'}}}):
                with self.assertRaisesRegex(ValueError, 'has no walk.png, which picks where walkers go: build the group again'):
                    checks.group('game', scratch, scratch, 'ekwalk', 'set.json', Path(scratch) / 'tiles1', 'ek_yard', 'dgt04', 'walk')
        from argparse import Namespace
        from . import __main__ as command
        asked = dict(game='game', repo='.', models='set.json', root='root', name='ekt1', built=['built'], model=['ek_yard'], tileset='dgt04', second_storey='0')
        with mock.patch.object(checks, 'group', return_value={}) as group, mock.patch('builtins.print'):
            command.command_check(Namespace(kind='group', mode='walk', target=['bay=22,23.5', 'apron=23.0,11'], **asked))
        self.assertEqual((group.call_args.args[-1], group.call_args.kwargs['targets']), ('walk', {'bay': (22.0, 23.5), 'apron': (23.0, 11.0)}))
        # A target must lie on ground with room to stand on in walk.png: one in a wall or off the group is a typo, not a lost way.
        roomy = np.zeros((40, 40), bool); roomy[:, :20] = True
        checks.own_targets(roomy, {'yard': (4.9, 9.9)}, {})
        for wrong in ({'wall': (5.1, 2.0)}, {'off': (-0.1, 2.0)}, {'beyond': (2.0, 10.0)}):
            with self.assertRaisesRegex(ValueError, 'not on ground with room to stand on in walk.png'):
                checks.own_targets(roomy, wrong, {})
        # Nor may it take a label the check gives: `pocket` brings a second walker of its own even where walk.png finds none.
        for label, chosen in (('north', {'north': (1.0, 1.0)}), ('door', {}), ('pocket', {}), ('pocket-near', {})):
            with self.assertRaisesRegex(ValueError, 'takes a label of its own: ' + label):
                checks.own_targets(roomy, {label: (4.9, 9.9)}, chosen)
        with self.assertRaisesRegex(ValueError, 'A --target is a place a group walk check sends a walker'):  # not dropped from another check
            command.command_check(Namespace(kind='props', mode='day', target=['bay=1,2'], **asked))
        for wrong in (['bay=22'], ['Bay=1,2'], ['bay=1,2', 'bay=3,4'], ['bay=x,2'], ['bay=inf,2'], ['bay=1,nan']):
            with self.assertRaisesRegex(ValueError, 'A target is label=x,y'):
                command.command_check(Namespace(kind='group', mode='walk', target=wrong, **asked))
        with self.assertRaisesRegex(ValueError, 'give them with --mode walk'):
            checks.group('game', '.', '.', 'ekwalk', 'set.json', 'built', 'ek_yard', 'dgt04', 'day', targets={'bay': (1.0, 2.0)})

    def test_a_group_is_laid_with_the_packs_tiles_only_where_the_pack_holds_this_build(self):
        text = '[TILE0]\r\nModel=tdg01_a01_01\r\n[TILE1]\r\nModel=ek_hall_t00\r\nWalkMesh=msb01\r\n[TILE1DOOR0]\r\nType=58\r\n[TILE2]\r\nModel=ek_hall_t01\r\n[TILE3]\r\nModel=ek_shop_t00\r\n'
        tiles = [{'model': 'ek_hall_t00', 'column': 0, 'row': 0}, {'model': 'ek_hall_t01', 'column': 1, 'row': 0}]
        self.assertEqual(checks.laid_tiles(text, 'dgt04', 'ek_hall', tiles, 3, 3), {(3, 3): 1, (4, 3): 2})
        with self.assertRaisesRegex(ValueError, 'install the group first'):
            checks.laid_tiles(text, 'dgt04', 'ek_yard', tiles, 3, 3)
        with self.assertRaisesRegex(ValueError, 'another build of ek_hall: its tile 3 is ek_shop_t00, not ek_hall_t02'):  # built again as three tiles, not installed again
            checks.laid_tiles(text, 'dgt04', 'ek_hall', [*tiles, {'model': 'ek_hall_t02', 'column': 2, 'row': 0}], 3, 3)
        with self.assertRaisesRegex(ValueError, 'its tile 3 is None'):
            checks.laid_tiles(text.split('[TILE3]')[0], 'dgt04', 'ek_hall', [*tiles, {'model': 'ek_hall_t02', 'column': 2, 'row': 0}], 3, 3)

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
        script = checks.watch_script(3, 270.0, 20, 8.0)
        self.assertIn('Probe("ek_d1"); Probe("ek_d2"); Probe("ek_d3");', script); self.assertIn('if(n>=20)', script)
        self.assertIn('JumpToLocation(GetLocation(GetWaypointByTag("ek_w1")))', script)  # the first door's waypoint, in whichever area it is
        self.assertIn('DelayCommand(8.0,Place(pc))', script); script.encode('ascii')
        prefix = prop_fixture.LOG_PREFIX
        lines = [f'{prefix} enter', f'{prefix} probe=ek_d1 valid=1 doorarea=ektdg_a target=ek_w2 targetarea=ektdg_a z= 0.000',
                 f'{prefix} watch=0 area=ektdg_a x= 45.000 y= 53.500 z=  0.000', f'{prefix} watch=1 area=ektdg_a x= 45.100 y= 53.400 z=  0.000',
                 f'{prefix} watch=2 area= x=  0.000 y=  0.000 z=  0.000',  # between areas the player is nowhere
                 f'{prefix} watch=3 area=ektud_a x= 40.000 y= 43.500 z=  0.000', f'{prefix} done']
        self.assertEqual(checks.stages(lines), [(0, 'ektdg_a', 45.0, 53.5), (3, 'ektud_a', 40.0, 43.5)])
        # A walk that did not run, did not end, or has a door that leads nowhere is no result.
        self.assertEqual(checks.walked(lines, 1), {'probes': [{'door': 'ek_d1', 'target': 'ek_w2', 'area': 'ektdg_a'}], 'stages': checks.stages(lines)})
        for told, count, said in (([], 1, 'never ran its entry script'), (lines[:-1], 1, 'did not finish'), (lines, 2, '2 doors were to be probed and 1 were'),
                                  ([lines[0], f'{prefix} probe=ek_d1 valid=1 doorarea=ektdg_a target= targetarea= z= 0.000', lines[-1]], 1, 'ek_d1 leads nowhere'),
                                  ([lines[0], f'{prefix} probe=ek_d1 valid=0 doorarea= target= targetarea= z= 0.000', lines[-1]], 1, 'ek_d1 leads nowhere')):
            with self.assertRaisesRegex(ValueError, said):
                checks.walked(told, count)

    def test_a_check_is_built_into_fresh_folders_and_reads_a_set_file_whatever_its_line_endings(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as scratch:
            base = Path(scratch); resources = checks._fresh(base, 'ekt1'); self.assertTrue(resources.is_dir())
            with self.assertRaisesRegex(ValueError, 'ekt1 was used before'):  # before anything is copied over the earlier run
                checks._fresh(base, 'ekt1')
            (base / 'fixtures' / 'ekt2').mkdir()
            with self.assertRaisesRegex(ValueError, 'ekt2 was used before'):
                checks._fresh(base, 'ekt2')
        for ending in ('\r\n', '\n'):
            text = ending.join(['[TILE0]', 'Model=tdg01_a01_01', 'ImageMap2D=MI_dg_a01', '[TILE1]', 'Model=ek_hall_t00', '[TILE1DOOR0]', 'Type=58', ''])
            self.assertEqual((checks._tile_field(text, 0, 'Model'), checks._tile_field(text, 0, 'ImageMap2D'), checks._tile_field(text, 1, 'Model')), ('tdg01_a01_01', 'MI_dg_a01', 'ek_hall_t00'))
            self.assertIsNone(checks._tile_field(text, 1, 'ImageMap2D')); self.assertIsNone(checks._tile_field(text, 2, 'Model'))  # not the door section's, and no such tile


if __name__ == '__main__':
    unittest.main()
