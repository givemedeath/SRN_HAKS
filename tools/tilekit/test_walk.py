"""The walk plan, layout, script and verdict of `tilekit walk`, without the client."""
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from tools.tilekit import review, walk
from tools.tilekit.__main__ import main


def wok(corners, faces):
    """A .wok's text of a walkmesh at the tile's middle; faces of corner numbers, all walked (material 4)."""
    return '\n'.join(['beginwalkmeshgeom t', 'node aabb walk', '  parent t', '  position 0 0 0', '  orientation 0 0 0 0', f'  verts {len(corners)}',
                      *(f'    {x} {y} {z}' for x, y, z in corners), f'  faces {len(faces)}', *(f'    {a} {b} {c} 1 0 0 0 4' for a, b, c in faces),
                      'endnode', 'endwalkmeshgeom t', ''])


# A floor whose middle line is one edge on the west and two on the east: met in pieces (a T-junction).
T_CORNERS = [(-5, -5, 0), (0, -5, 0), (0, 5, 0), (-5, 5, 0), (5, -5, 0), (0, 0, 0), (5, 5, 0)]
T_FACES = [(0, 1, 2), (0, 2, 3), (1, 4, 5), (5, 4, 6), (5, 6, 2)]


def square(east=5.0, side=5.0):
    """A level floor from `side` west of the tile's middle to `east`, `side` north and south, as walked triangles in the tile."""
    return walk.triangles(*walk.load(wok([(-side, -side, 0), (east, -side, 0), (east, side, 0), (-side, side, 0)], [(0, 1, 2), (0, 2, 3)])))


class Plan(unittest.TestCase):
    def test_a_floor_is_found_under_a_point_and_round_it(self):
        floor = square()
        self.assertEqual(walk.heights(floor, (1, 1)), [0.0])
        self.assertEqual(walk.near(floor, (1, 1), .2, .3), 0.0); self.assertIsNone(walk.near(floor, (1, 1), 1, .3))
        self.assertTrue(walk.room(floor, (0, 0), 0, .3)); self.assertFalse(walk.room(floor, (4.8, 0), 0, .3))  # its room runs off the tile

    def test_an_edge_met_in_pieces_is_crossed_from_floor_on_one_side_to_floor_on_the_other(self):
        corners, faces, placed = walk.load(wok(T_CORNERS, T_FACES))
        edges = walk.suspects(corners, faces, placed); self.assertTrue(edges)
        crossings = walk.edge_crossings(walk.triangles(corners, faces, placed), placed, edges)
        self.assertGreaterEqual(len(crossings), 3)
        for one in crossings:
            (a, za), (b, zb) = one['a'], one['b']
            self.assertLess(a[0] * b[0], 0); self.assertEqual((za, zb), (0, 0)); self.assertAlmostEqual(abs(a[0]), 1.2)

    def test_a_floor_that_ends_short_is_crossed_into_a_level_neighbour(self):
        crossings, beside = walk.side_crossings(square(4.98), {'udp1_a01_01': (7, square())})
        self.assertEqual(beside[(1, 0)], [7, 0, 'udp1_a01_01'])
        east = [one for one in crossings if one['b'][0][0] > 5]
        self.assertTrue(1 <= len(east) <= 5); self.assertTrue(all(one['a'][0][0] == 3.6 and one['b'][0][0] == 6.4 for one in east))
        self.assertEqual(walk.side_crossings(square(4.98), {'udp1_a01_02': (8, square(4.5, 4.5))}), ([], {}))  # a neighbour must reach its sides

    def test_a_plan_names_the_tiles_of_the_set(self):
        text = '[GENERAL]\nDefault=Grass\n[TILE0]\nModel=t_a01_01\n[TILE1]\nModel=t_b01_01\n'
        found = walk.plan(['t_b01_01'], text, lambda model: wok(T_CORNERS, T_FACES))
        self.assertEqual(found['t_b01_01']['number'], 1); self.assertTrue(found['t_b01_01']['crossings'])
        with self.assertRaises(ValueError):
            walk.plan(['t_c01_01'], text, lambda model: None)


CROSSING = {'edge': [[0, -1, 0], [0, 1, 0]], 't': .5, 'a': [[-1.0, 0.0], 0.0], 'b': [[1.0, 0.0], 0.0]}


class Walkers(unittest.TestCase):
    def test_each_tile_is_laid_twice_with_its_neighbours_and_walked_both_ways(self):
        found = {'t_b01_01': {'number': 1, 'crossings': [CROSSING], 'beside': [[[1, 0], [4, 2, 't_c01_01']]]}, 't_c01_01': {'number': 4, 'crossings': [], 'beside': []}}
        width, height, laid, walkers = walk.layout(found, 0)
        self.assertEqual((width, height, len(laid)), (20, 5, 100))
        self.assertEqual([walker['tag'] for walker in walkers], ['t_b01_01.human', 't_b01_01.troll'])
        self.assertEqual((laid[(2, 2)], laid[(3, 2)], laid[(5, 2)], laid[(6, 2)], laid[(4, 2)]), ((1, 0), (4, 2), (1, 0), (4, 2), (0, 0)))
        self.assertEqual(walkers[0]['legs'], [[0, 'to', [24.0, 25.0, 0.0]], [0, 'ab', [26.0, 25.0, 0.0]], [0, 'ba', [24.0, 25.0, 0.0]]])
        self.assertEqual(walkers[1]['legs'][0][2], [54.0, 25.0, 0.0])
        many = {f't_b{index:02d}_01': {'number': 1, 'crossings': [CROSSING], 'beside': []} for index in range(31)}
        self.assertEqual(walk.layout(dict(list(many.items())[:30]), 0)[1], 32)
        with self.assertRaises(ValueError):  # an area is 32 tiles high at most
            walk.layout(many, 0)

    def test_the_walkers_script_makes_each_one_and_sends_it_along_its_legs(self):
        walkers = walk.layout({'t_b01_01': {'number': 1, 'crossings': [CROSSING], 'beside': []}}, 0)[3]
        functions, statement = walk.script(walkers, walk.AREA)
        self.assertEqual((functions.count('void W0()'), functions.count('void W1()'), functions.count('Go("t_b01_01.troll"'), functions.count('GetObjectByTag("wlk")')), (1, 1, 3, 2))
        self.assertIn(',15104);', functions); self.assertEqual(statement, 'DelayCommand(12.0,Walk());')
        self.assertEqual(functions.count('SetLocalInt(c,"LAST",2);'), 2); self.assertIn('!GetLocalInt(OBJECT_SELF,"WALKED")', functions)  # traced to the last leg
        text = review.enter_script([{'area': 'wlk', 'label': 'row0', 'stand': [10.0, 20.0], 'facing': 90, 'distance': 70, 'pitch': 35, 'height': 1}], more=(functions, statement))
        self.assertLess(text.index('void Walk()'), text.index('void main()')); self.assertLess(text.index('void main()'), text.index(statement))
        self.assertNotIn('Walk', review.enter_script([{'area': 'wlk', 'label': 'row0', 'stand': [10.0, 20.0], 'facing': 90, 'distance': 70, 'pitch': 35, 'height': 1}]))

    def test_a_bent_route_a_short_stop_a_leg_never_reached_and_a_walker_never_made_are_told(self):
        legs = [[0, 'to', [0, 0, 0]], [0, 'ab', [2, 0, 0]], [0, 'ba', [0, 0, 0]]]
        walkers = [{'tag': 'a.human', 'appearance': 6, 'legs': legs}, {'tag': 'b.troll', 'appearance': 15104, 'legs': legs}]
        lines = ['ENVKIT walk=a.human made=1 app=6', 'ENVKIT walk=a.human leg=0 at=   0.00,   0.00,  0.00', 'ENVKIT walk=a.human trace=   1.00,   0.05,  0.00',
                 'ENVKIT walk=a.human leg=1 at=   2.00,   0.00,  0.00', 'ENVKIT walk=a.human leg=1 at=   2.00,   0.00,  0.00', 'ENVKIT walk=a.human trace=   1.00,   0.50,  0.00',
                 'ENVKIT walk=a.human leg=2 at=   0.30,   0.00,  0.00', 'ENVKIT walk=b.troll made=1 app=6', 'ENVKIT shot=0 target=row0 valid=1']
        told = walk.verdict(lines, walkers)
        self.assertEqual([(one['way'], one['off'], one['strayed']) for one in told['walked']], [('ab', 0.0, .05), ('ba', .3, .5)])
        self.assertEqual(([one['way'] for one in told['bent']], [one['way'] for one in told['short']]), (['ba'], ['ba']))
        self.assertEqual(told['missing'], [{'tag': 'b.troll', 'crossing': 0, 'way': way} for way in ('to', 'ab', 'ba')])
        self.assertEqual(told['unmade'], ['b.troll'])  # made, but not as a Troll
        off = [{'tag': 'c.human', 'appearance': 6, 'legs': legs}]  # stopped 0.5 m short of the crossing's start, then straight across from there
        late = walk.verdict(['ENVKIT walk=c.human made=1 app=6', 'ENVKIT walk=c.human leg=0 at=   0.00,   0.50,  0.00', 'ENVKIT walk=c.human trace=   1.00,   0.25,  0.00',
                             'ENVKIT walk=c.human leg=1 at=   2.00,   0.00,  0.00'], off)
        self.assertEqual([(one['way'], one['off']) for one in late['short']], [('to', .5)]); self.assertEqual((late['walked'][0]['strayed'], late['bent']), (0.0, []))
        self.assertEqual(told['walked'][0]['longer'], 1.001)


class Command(unittest.TestCase):
    def test_a_plan_is_walked_only_as_it_was_made(self):
        with tempfile.TemporaryDirectory() as folder:
            plan = Path(folder) / 'plan.json'; run = ['walk', '--plan', str(plan), '--game', folder, '--built', folder, '--out', str(Path(folder) / 'out'), '--name', 'walkt']
            plan.write_text(json.dumps({'tileset': 'fcx01', 'sides': False, 'tiles': {'fcx01_x05_01': {'number': 211, 'crossings': [CROSSING], 'beside': []}}}), encoding='utf-8')
            self.assertEqual(main([*run, '--tileset', 'udp1']), 2)  # a plan of another set
            self.assertEqual(main([*run, '--tileset', 'fcx01', '--tiles', 'fcx01_x05_02']), 2)  # of other tiles
            self.assertEqual(main([*run, '--tileset', 'fcx01', '--sides']), 2)  # made without the sides
            self.assertEqual(main([*run, '--tileset', 'fcx01', '--fill', '99999']), 2)  # a fill the set lacks
            self.assertFalse((Path(folder) / 'out').exists())


if __name__ == '__main__':
    unittest.main()
