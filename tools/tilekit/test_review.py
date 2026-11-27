"""The review module: how a tile turns, an area laid from a set's own rules, the views taken of it and its script."""
import math
import tempfile
import unittest
from pathlib import Path

from . import review


def tile(number, corners, crossers=('', '', '', ''), heights=(0, 0, 0, 0), model=None):
    return {'number': number, 'model': model or f't_{number:02d}', 'corners': list(corners), 'heights': list(heights), 'crossers': list(crossers), 'doors': 0}


G, T = 'Ground', 'Tower'
# Ground everywhere; a tower's one-corner, side, three-corner and middle tiles; a road straight, turning and crossing.
TILES = {one['number']: one for one in (
    tile(0, (G, G, G, G)), tile(1, (T, G, G, G)), tile(2, (G, T, G, T)), tile(3, (T, T, G, T)), tile(4, (T, T, T, T)),
    tile(5, (G, G, G, G), ('Road', '', 'Road', '')), tile(6, (G, G, G, G), ('', '', 'Road', 'Road')), tile(7, (G, G, G, G), ('Road', 'Road', 'Road', 'Road')),
    tile(8, (G, G, G, G), heights=(1, 1, 0, 0)), tile(9, (G, G, G, G)), tile(10, (G, G, G, G), model='ek_shop_t00'))}
SET = '[GENERAL]\nDefault=Ground\n' + ''.join(
    f'[TILE{one["number"]}]\nModel={one["model"]}\n' + ''.join(f'{key}={value}\n' for key, value in zip(('TopLeft', 'TopRight', 'BottomLeft', 'BottomRight'), one['corners']))
    + ''.join(f'{key}Height={value}\n' for key, value in zip(('TopLeft', 'TopRight', 'BottomLeft', 'BottomRight'), one['heights']))
    + ''.join(f'{key}={value}\n' for key, value in zip(('Top', 'Right', 'Bottom', 'Left'), one['crossers'])) for one in TILES.values()) + '[GROUP0]\nName=Spare\nTile0=9\n'


class ReviewTests(unittest.TestCase):
    def test_a_tile_turns_counter_clockwise_as_an_areas_orientation_turns_it(self):
        one = tile(1, ('a', 'b', 'c', 'd'), ('top', 'right', 'bottom', 'left'))
        self.assertEqual(review.turned(one, 0), (('a', 'b', 'c', 'd'), ('top', 'right', 'bottom', 'left')))
        self.assertEqual(review.turned(one, 1), (('b', 'd', 'a', 'c'), ('right', 'bottom', 'left', 'top')))  # the top right corner comes to the top left
        self.assertEqual(review.turned(one, 4), review.turned(one, 0)); self.assertEqual(review.turned(one, 3), review.turned(review_tile(review.turned(one, 1)), 2))

    def test_an_area_laid_from_the_sets_rules_agrees_at_every_corner_and_crosser(self):
        patches = [{'terrain': T, 'at': [1, 1]}]; runs = [{'crosser': 'Road', 'cells': [[3, 0], [3, 4]]}, {'crosser': 'Road', 'cells': [[0, 4], [3, 4]]}]
        laid = review.solve(TILES, G, 5, 6, patches, runs, avoid={9, 10})
        self.assertEqual(len(laid), 30); self.assertEqual({number for number, _ in laid.values()}, {0, 1, 2, 4, 5, 6})  # no crossing here, and never the raised or avoided tile
        self.assertEqual(laid[(1, 1)], (4, 0)); self.assertEqual({laid[cell][0] for cell in ((0, 0), (2, 0), (0, 2), (2, 2))}, {1})  # the tower's middle and its four corners
        self.assertEqual(laid[(3, 2)][0], 5); self.assertEqual(laid[(3, 4)], (6, 0))  # the road runs north off the south edge and turns west short of the top
        self.assertEqual((laid[(0, 4)][0], laid[(4, 4)][0]), (5, 0))  # it runs off the west edge; east of the turn is plain ground
        cells = [laid[(index % 5, index // 5)] for index in range(30)]
        self.assertEqual(review.disagreements(5, cells, TILES), [])
        cells[6] = (0, 0)  # plain ground where the tower's middle stood
        self.assertIn('tile 0 at 1,1: Ground where a neighbour has Tower', review.disagreements(5, cells, TILES))
        # A terrain is matched in any case, as the game matches it: dgt04 spells Freeway two ways.
        spelled = {**TILES, 4: tile(4, ('tower',) * 4), 11: tile(11, ('TOWER', 'tower', 'Tower', 'tower'))}; cells[6] = (4, 0)
        self.assertEqual(review.disagreements(5, cells, spelled), [])
        self.assertEqual(review.solve({11: spelled[11], 0: TILES[0]}, 'ground', 1, 1, [{'terrain': 'Tower', 'at': [0, 0], 'size': [2, 2], 'border': True}]), {(0, 0): (11, 0)})
        self.assertEqual(review.plain({'default': 'Ground', 'groups': [], 'tiles': [tile(3, (T,) * 4), tile(5, ('ground',) * 4)]}), 5)
        crossing = review.solve(TILES, G, 3, 3, [], [{'crosser': 'Road', 'cells': [[1, 0], [1, 2]]}, {'crosser': 'Road', 'cells': [[0, 1], [2, 1]]}])
        self.assertEqual(crossing[(1, 1)][0], 7)  # two runs that reach the area's edges cross in the middle
        with self.assertRaisesRegex(ValueError, r'(?i)No tile of the set fits: 0,0 needs corners Ground/Lake/Ground/Ground'):
            review.solve(TILES, G, 3, 3, [{'terrain': 'Lake', 'at': [1, 1], 'size': [1, 1]}])
        with self.assertRaisesRegex(ValueError, "reaches the area's edge"):
            review.solve(TILES, G, 3, 3, [{'terrain': T, 'at': [2, 1]}])
        for at in ([2, 1], [-1, 1], [3, 1]):  # a border patch meets the edge (corner 3 is the area's east edge), and no further
            try:
                review.solve(TILES, G, 3, 3, [{'terrain': T, 'at': at, 'border': True}]); self.assertEqual(at, [2, 1])
            except ValueError as error:
                self.assertNotEqual(at, [2, 1]); self.assertIn("reaches the area's edge", str(error))
        with self.assertRaisesRegex(ValueError, 'lies over another patch'):
            review.solve(TILES, G, 5, 5, [{'terrain': T, 'at': [1, 1]}, {'terrain': T, 'at': [2, 2]}])
        with self.assertRaisesRegex(ValueError, 'is straight'):
            review.solve(TILES, G, 3, 3, [], [{'crosser': 'Road', 'cells': [[0, 0], [1, 1]]}])

    def test_a_patch_lies_over_another_only_where_it_says_so(self):
        laid = review.solve(TILES, G, 5, 5, [{'terrain': T, 'at': [1, 1], 'size': [3, 3]}, {'terrain': G, 'at': [2, 2], 'size': [1, 1], 'over': True}])
        self.assertEqual({laid[cell][0] for cell in ((1, 1), (2, 1), (1, 2), (2, 2))}, {3})  # a yard in the tower's middle: four three-corner tiles round it
        self.assertEqual(review.disagreements(5, [laid[(index % 5, index // 5)] for index in range(25)], TILES), [])

    def test_a_group_is_laid_whole_where_asked_and_refused_where_the_ground_is_not_its_own(self):
        tiles = {**TILES, 12: tile(12, (T, T, T, T)), 13: tile(13, (T, T, T, T))}
        text = SET + '[GROUP1]\nName=Keep\nRows=2\nColumns=2\nTile0=12\nTile1=13\nTile2=-1\nTile3=12\n'
        cells = review.solve(tiles, G, 5, 5, [{'terrain': T, 'at': [1, 1], 'size': [3, 3]}], avoid={12, 13})
        laid = review.stamped(cells, tiles, text, [{'name': 'keep', 'at': [1, 1]}], 5, 5)
        self.assertEqual([laid[cell] for cell in ((1, 1), (2, 1), (2, 2))], [(12, 0), (13, 0), (12, 0)])  # Tile0 is the south-west one, rows going north
        self.assertEqual(laid[(1, 2)], cells[(1, 2)]); self.assertEqual(cells[(1, 1)], (4, 0))  # a hole in a group leaves the ground; what was solved is not changed
        with self.assertRaisesRegex(ValueError, 'does not fit the ground it is laid on: tile 12 at 3,3: Tower where a neighbour has Ground'):
            review.stamped(cells, tiles, text, [{'name': 'Keep', 'at': [3, 3]}], 5, 5)
        self.assertEqual(review.stamped(cells, tiles, text, [{'name': 'Keep', 'at': [3, 3], 'loose': True}], 5, 5)[(3, 3)], (12, 0))  # laid to be looked at
        with self.assertRaisesRegex(ValueError, 'Keep at 4,1 leaves the area'):
            review.stamped(cells, tiles, text, [{'name': 'Keep', 'at': [4, 1]}], 5, 5)
        with self.assertRaisesRegex(ValueError, 'The set has no group Spare'):  # a group with no shape is one tile's name, not a building
            review.stamped(cells, tiles, text, [{'name': 'Spare', 'at': [0, 0]}], 5, 5)

    def test_a_grid_keeps_plain_ground_on_both_sides_of_every_row(self):
        width, height, laid, rows = review.grid([1, 2, 3, 4, 5], 0, across=2)
        self.assertEqual((width, height, rows, len(laid)), (2, 7, 3, 14))
        self.assertEqual([laid[(0, 1)], laid[(1, 1)], laid[(0, 5)], laid[(1, 5)]], [(1, 0), (2, 0), (5, 0), (0, 0)])
        self.assertEqual({laid[(column, row)] for column in range(2) for row in (0, 2, 4, 6)}, {(0, 0)})
        shots = review.grid_shots('tkgd', 'grid-day', 14, 2, reach=6)
        self.assertEqual(len(shots), 12); self.assertEqual([shots[0]['label'], shots[1]['label'], shots[-1]['label']], ['grid-day-r00-c00-s', 'grid-day-r00-c00-n', 'grid-day-r01-c12-n'])
        self.assertEqual((shots[0]['stand'], shots[0]['facing'], shots[1]['stand'], shots[1]['facing']), ([30.0, 5.0], 90, [30.0, 25.0], 270))  # on the plain row south of it, then north
        self.assertEqual(shots[-1]['stand'], [130.0, 45.0])  # the last view holds the two tiles left over
        with self.assertRaisesRegex(ValueError, 'do not fit one area'):
            review.grid(range(600), 0)

    def test_views_of_a_block_and_of_a_built_area_stand_in_the_middle_of_cells(self):
        shots = review.corner_shots('tkbd', 'block-day', [(3, 3)])
        self.assertEqual([(shot['label'], shot['stand'], shot['facing']) for shot in shots],
                         [('block-day-x03y03-ne', [35.0, 35.0], 45), ('block-day-x03y03-nw', [35.0, 35.0], 135), ('block-day-x03y03-sw', [35.0, 35.0], 225),
                          ('block-day-x03y03-se', [35.0, 35.0], 315)])
        shots = review.lattice_shots('tkad', 'area-day', 13, 11)
        self.assertEqual(len(shots), 18); self.assertEqual((shots[0]['label'], shots[0]['stand'], shots[-1]['label']), ('area-day-x02y02-n', [25.0, 25.0], 'area-day-x10y10-s'))

    def test_the_script_gives_a_view_in_another_area_time_to_load_and_logs_as_envkit_does(self):
        shots = [review._shot('tkbd', 'one', 5, 5, 90, 30, 50), review._shot('tkbd', 'two', 15, 5, 90, 30, 50), review._shot('tkbn', 'three', 5, 5, 90, 30, 50)]
        script = review.enter_script(shots, hold=6.0, arrive=8.0)
        self.assertIn('if(n==0) { x=5.000; y=5.000; facing=90.000; distance=30.000; pitch=50.000; height=1.000; wait=8.0; label="one"; area="tkbd"; }', script)
        self.assertIn('wait=0.2; label="two"; area="tkbd"', script); self.assertIn('wait=8.0; label="three"; area="tkbn"', script)
        self.assertIn('JumpToLocation(Location(GetObjectByTag(area),Vector(x,y,0.0),facing))', script)
        self.assertIn('DelayCommand(wait+1.0,Line(pc,n,label,area));', script)  # the line is written then, and says whether the player stands in the view's area
        self.assertIn('WriteTimestampedLogEntry("ENVKIT shot="+IntToString(n)+" target="+label+" valid="+IntToString(GetTag(GetArea(pc))==area));', script)
        self.assertEqual(review.elsewhere(['ENVKIT enter shots=3', 'ENVKIT shot=0 target=one valid=1', 'ENVKIT shot=1 target=two valid=0', 'ENVKIT done']), ['two'])
        self.assertIn('DelayCommand(wait+6.0,Shot(pc,n+1));', script); self.assertIn('if(n>=3) { WriteTimestampedLogEntry("ENVKIT done"); return; }', script)
        with self.assertRaisesRegex(ValueError, 'label is letters'):
            review.enter_script([review._shot('tkbd', 'two words', 5, 5, 90, 30, 50)])

    def test_an_area_is_laid_and_lit_as_asked(self):
        laid = {(column, row): (column + row * 2, row) for column in range(2) for row in range(3)}
        made = review.area_documents('tkbn', 'Block, night', 'tst01', 2, 3, laid, 'night'); are = made['tkbn.are']
        self.assertEqual(sorted(made), ['tkbn.are', 'tkbn.git']); self.assertEqual((are['Tileset']['value'], are['Width']['value'], are['Height']['value'], are['Tag']['value']), ('tst01', 2, 3, 'tkbn'))
        self.assertEqual([(one['Tile_ID']['value'], one['Tile_Orientation']['value']) for one in are['Tile_List']['value']], [(0, 0), (1, 0), (2, 1), (3, 1), (4, 2), (5, 2)])  # row by row from the south-west
        self.assertEqual((are['IsNight'], are['MoonDiffuseColor'], are['MoonAmbientColor']), ({'type': 'byte', 'value': 1}, {'type': 'dword', 'value': 0x504840}, {'type': 'dword', 'value': 0x302820}))
        day = review.area_documents('tkbd', 'Block, day', 'tst01', 2, 3, laid, 'day')['tkbd.are']
        self.assertEqual((day['IsNight']['value'], day['SunAmbientColor']['value'], day['DayNightCycle']['value']), (0, 11579568, 0))  # envkit's check lighting, and no clock to change it
        with self.assertRaisesRegex(ValueError, 'every cell'):
            review.area_documents('tkbd', 'Block', 'tst01', 2, 4, laid, 'day')
        with self.assertRaisesRegex(ValueError, 'lit by'):
            review.area_documents('tkbd', 'Block', 'tst01', 2, 3, laid, 'dusk')

    def test_a_generic_door_stands_where_asked_its_row_past_255_in_the_new_field(self):
        laid = {(0, 0): (0, 0)}
        git = review.area_documents('tkd', 'Doors', 'tst01', 1, 1, laid, 'day', doors=[{'row': 1094, 'position': (5.0, 4.1, 0.2), 'bearing': -90.0, 'opened': 1}])['tkd.git']
        one = git['Door List']['value'][0]
        self.assertEqual((one['__struct_id'], one['Appearance']['value'], one['GenericType_New']['value'], one['GenericType']['value'], one['OpenState']['value']), (8, 0, 1094, 255, 1))
        self.assertAlmostEqual(one['Bearing']['value'], -math.pi / 2, places=5); self.assertAlmostEqual(one['Y']['value'], 4.1, places=5)
        self.assertEqual(review.area_documents('tkd', 'Doors', 'tst01', 1, 1, laid, 'day')['tkd.git']['Door List']['value'], [])

    def test_the_shared_part_lays_another_tileset_s_tiles_on_its_plain_tile_and_stands_placeables_in_rows(self):
        table = '2DA V2.0\n\n   Label StrRef ModelName\n0  Bin 1 plc_bin\n1  Crate 2 plc_crate\n'
        spec = {'tileset': 'tst01', 'fill': 0, 'shared': {'lights': ['day'], 'tilesets': {'oth01': {'models': ['T_04', 't_02'], 'lights': ['day', 'night']}},
                                                           'placeables': {'groups': [{'name': 'small', 'models': ['plc_crate', 'plc_bin']},
                                                                                     {'name': 'large', 'models': ['plc_bin'], 'across': 1, 'spacing': 40, 'apart': 40, 'distance': 50}]}}}
        areas, shots = review.plan(SET, spec, sets={'oth01': SET}, table=table)
        self.assertEqual([(area['tag'], area['tileset'], area['width'], area['height']) for area in areas],
                         [('tkoth01d', 'oth01', 4, 3), ('tkoth01n', 'oth01', 4, 3), ('tkp0d', 'tst01', 5, 4), ('tkp1d', 'tst01', 6, 6)])
        self.assertEqual(sorted({number for number, _ in areas[0]['laid'].values()}), [0, 2, 4])  # tile 0 is the plain one: tile 9 is of a group
        self.assertEqual([(prop['model'], prop['appearance']) for prop in areas[2]['props']], [('plc_crate', 1), ('plc_bin', 0)])
        self.assertEqual([(shot['label'], shot['distance']) for shot in shots if shot['area'].startswith('tkp')], [('props-small-day-r00', 24.0), ('props-large-day-r00', 50)])
        self.assertEqual(review.area_documents('tkpsd', 'P', 'tst01', 5, 4, areas[2]['laid'], 'day', props=areas[2]['props'])['tkpsd.git']['Placeable List']['value'][1]['Appearance']['value'], 0)
        self.assertEqual(review.prop_rows(['plc_bin'] * 6, {'plc_bin': 0}, across=6, spacing=6.75)[:2], (7, 4))  # a 40.5 m row takes five tiles, a tile of ground round them
        with self.assertRaisesRegex(ValueError, 'No tile of oth01 is t_77'):
            review.plan(SET, {**spec, 'shared': {**spec['shared'], 'tilesets': {'oth01': {'models': ['t_77']}}}}, sets={'oth01': SET}, table=table)
        with self.assertRaisesRegex(ValueError, 'no row of placeables.2da: plc_lamp'):
            review.plan(SET, {**spec, 'shared': {**spec['shared'], 'placeables': {'groups': [{'name': 'small', 'models': ['plc_lamp']}]}}}, sets={'oth01': SET}, table=table)

    def test_a_plan_lays_each_part_once_for_every_lighting_and_keeps_group_and_envkit_tiles_out_of_the_block(self):
        spec = {'tileset': 'tst01', 'fill': 0, 'block': {'width': 4, 'height': 4, 'lights': ['day', 'night'], 'patches': [{'terrain': T, 'at': [1, 1]}], 'crossings': [[3, 3]]},
                'grid': {'across': 4, 'lights': ['day']}, 'area': {'step': 2, 'lights': ['overcast']}}
        built = (2, 1, [(0, 0), (9, 2)])
        areas, shots = review.plan(SET, spec, built_area=built)
        self.assertEqual([(area['tag'], area['light'], area['width'], area['height']) for area in areas],
                         [('tkbd', 'day', 4, 4), ('tkbn', 'night', 4, 4), ('tkgd', 'day', 4, 7), ('tkao', 'overcast', 2, 1)])
        self.assertEqual({number for number, _ in areas[0]['laid'].values()}, {0, 1, 2, 4})  # tile 9 is of a group and 10 an envkit building's: neither is painted
        self.assertEqual(sorted({number for number, _ in areas[2]['laid'].values()}), list(range(10)))  # the grid shows the group's tile, not the envkit one
        self.assertEqual([len([shot for shot in shots if shot['area'] == tag]) for tag in ('tkbd', 'tkbn', 'tkgd', 'tkao')], [4, 4, 6, 2])
        lamped = {**spec, 'block': {**spec['block'], 'lights': ['night'], 'lamps': [{'name': 'source', 'source': 2, 'lights': ['night']}]}}
        areas, shots = review.plan(SET, lamped, parts=('block',)); self.assertEqual([(area['tag'], area.get('lamps')) for area in areas], [('tkbn', None), ('tklsn', {'main': 0, 'source': 2})])
        self.assertTrue(any(shot['label'].startswith('lamp-source-night') and shot['area'] == 'tklsn' for shot in shots))
        few = review.plan(SET, {**lamped, 'block': {**lamped['block'], 'views': [shots[0]['label'].split('-', 2)[2]]}}, parts=('block',))[1]
        self.assertEqual([shot['label'].split('-', 2)[2] for shot in few if shot['label'].startswith('block-')], [shots[0]['label'].split('-', 2)[2]])
        self.assertEqual([shot['label'] for shot in few if shot['label'].startswith('lamp-')], ['lamp-source-night-' + shots[0]['label'].split('-', 2)[2]])  # a lamp label has a longer prefix
        lit = review.area_documents('tklsn', 'Lamps', 'tst01', 1, 1, {(0, 0): (0, 0)}, 'night', {'source': 2})['tklsn.are']['Tile_List']['value'][0]
        self.assertEqual((lit['Tile_SrcLight1']['value'], lit['Tile_SrcLight2']['value'], lit['Tile_MainLight1']['value']), (2, 2, 0))
        self.assertEqual([area['tag'] for area in review.plan(SET, spec, parts=('grid', 'area'))[0]], ['tkgd'])  # no built area given: that part is left out
        with self.assertRaisesRegex(ValueError, 'does not agree with this set'):
            review.plan(SET, spec, built_area=(2, 1, [(2, 0), (0, 0)]))  # a tower's side beside plain ground
        with self.assertRaisesRegex(ValueError, 'Nothing to review'):
            review.plan(SET, spec, parts=('area',))
        with self.assertRaisesRegex(ValueError, 'has tiles this set does not: 77'):
            review.plan(SET, spec, built_area=(2, 1, [(0, 0), (77, 0)]))
        with self.assertRaisesRegex(ValueError, r'Two areas would be named tkgd: .*lighting \(dusk\)'):
            review.LIGHTS['dusk'] = review.LIGHTS['overcast']; self.addCleanup(review.LIGHTS.pop, 'dusk')
            review.plan(SET, {**spec, 'grid': {'across': 4, 'lights': ['day', 'dusk']}}, parts=('grid',))
        self.assertEqual([area['tag'] for area in review.plan(SET, {key: spec[key] for key in ('tileset', 'grid')})[0]], ['tkgd'])  # a spec of a grid alone
        near = review.plan(SET, {**spec, 'block': {**spec['block'], 'near': {'distance': 15, 'pitch': 64}}}, parts=('block',))[1]
        self.assertEqual([(shot['label'], shot['area'], shot['distance'], shot['pitch']) for shot in near if shot['label'].startswith('near-night')][0],
                         ('near-night-x03y03-ne', 'tkbn', 15, 64))  # the same crossings again from a player's distance, in the block's own areas
        self.assertEqual(len(near), 16)
        eye = review.plan(SET, {**spec, 'block': {**spec['block'], 'eye': {'crossings': [[3, 3]], 'turns': [0, 180], 'pitches': [90, 110]}}}, parts=('block',))[1]
        seen = [(shot['label'], shot['area'], shot['stand'], shot['facing'], shot['pitch'], shot['height'], shot['distance']) for shot in eye if shot['label'].startswith('eye-night')]
        self.assertEqual(seen[0], ('eye-night-x03y03-000-090', 'tkbn', [35.0, 35.0], 0, 90, 1.7, 1.0))  # inside the cell, a person's eye, level
        self.assertEqual([one[0] for one in seen], ['eye-night-x03y03-000-090', 'eye-night-x03y03-180-090', 'eye-night-x03y03-000-110', 'eye-night-x03y03-180-110'])  # then looking up, at the ceiling
        with self.assertRaisesRegex(ValueError, 'eye views of a block take'):
            review.plan(SET, {**spec, 'block': {**spec['block'], 'eye': {'tilt': 5}}}, parts=('block',))

    def test_the_command_refuses_in_words_and_a_refused_overlay_leaves_the_folder_fresh(self):
        import contextlib, io, json
        from . import __main__ as command
        spec = {'tileset': 'tst01', 'grid': {'across': 4, 'lights': ['day']}, 'haks': ['srn_t_tst01', *review.HAKS]}
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); (root / 'srn_t_tst01').mkdir(); (root / 'srn_t_tst01' / 'tst01.set').write_text(SET, encoding='cp1252')
            (root / 'game' / 'data').mkdir(parents=True); (root / 'built').mkdir(); (root / 'over').mkdir(); (root / 'over' / 'Brick.tga').write_bytes(b'')
            for name in [pack + '.hak' for pack in spec['haks']] + [review.TLK + '.tlk']:
                (root / 'built' / name).write_bytes(b'')

            def run(document, *more, encoding='utf-8'):
                (root / 'spec.json').write_text(json.dumps(document), encoding=encoding); said = io.StringIO()
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(said):
                    code = command.main(['review', '--spec', str(root / 'spec.json'), '--game', str(root / 'game'), '--built', str(root / 'built'),
                                         '--out', str(root / 'out'), '--name', 'tkt', '--repo', str(root), '--no-run', *more])
                return code, said.getvalue()
            self.assertEqual(run(spec, '--views', 'blok-day'), (2, 'tilekit: No view begins with blok-day\n'))
            self.assertEqual(run(spec, '--views', 'blok-day', encoding='utf-8-sig'), (2, 'tilekit: No view begins with blok-day\n'))  # a spec with a byte-order mark is read
            self.assertEqual(run({'fill': 0}), (2, 'tilekit: A review spec names its tileset\n'))
            self.assertEqual(run({'tileset': 'tst01', 'grid': {}}), (2, "tilekit: The review spec lacks 'lights'\n"))
            self.assertEqual(run({'tileset': 'nope', 'grid': {}})[0], 2)  # no such set file: said, not thrown
            self.assertEqual(run(spec, '--overlay', str(root / 'over')), (2, 'tilekit: Overlay files are lowercase resref files: Brick.tga\n'))
            (root / 'over' / 'Brick.tga').unlink(); (root / 'over' / 'tst02.set').write_bytes(b'[GENERAL]\nName=TST02\n')  # bare LF: the client fell over on it
            self.assertEqual(run(spec, '--overlay', str(root / 'over')), (2, 'tilekit: tst02.set: a set file has CRLF line ends; the client falls over on bare LF lines\n'))
            (root / 'over' / 'tst02.set').unlink()
            self.assertIn('add srn_t_tst01 to the spec\'s haks', run({**spec, 'haks': list(review.HAKS)})[1])  # a tileset whose pack the module would not load
            self.assertIn('The fill tile 99 is no tile of tst01', run({**spec, 'fill': 99})[1])
            self.assertEqual(run(spec, '--views', ','), (2, 'tilekit: No view named in --views\n'))  # a stray comma is no view, not every one
            self.assertIn('not named like a pack it loads (srn_2da)', run(spec, '--name', 'srn_2da')[1])  # its own pack would be written over the built one
            self.assertFalse((root / 'out').exists())

    def test_what_the_views_wait_is_counted_for_every_change_of_area(self):
        shots = [review._shot(area, 'one', 5, 5, 90, 30, 50) for area in ('tkbd', 'tkbd', 'tkbn', 'tkbd')]
        self.assertEqual(review.waits(shots), [8.0, 0.2, 8.0, 8.0])  # back to an area is another arrival

    def test_a_sheet_shows_every_capture_under_its_name(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as folder:
            paths = []
            for index in range(5):
                path = Path(folder) / f'shot-{index:02d}.png'; Image.new('RGB', (160, 90), (index * 40, 0, 0)).save(path); paths.append(path)
            self.assertEqual(review.sheet(paths, Path(folder) / 'out' / 'sheet.jpg', columns=2, wide=80), 5)
            with Image.open(Path(folder) / 'out' / 'sheet.jpg') as page:
                self.assertEqual(page.size, (160, (45 + 16) * 3))
            with self.assertRaisesRegex(ValueError, 'No captures'):
                review.sheet([], Path(folder) / 'none.jpg')

    def test_sheets_are_made_for_each_part_and_lighting_in_pages(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as folder:
            captures = Path(folder) / 'captures'; captures.mkdir()
            for index, label in enumerate(['block-day-x03y03-ne', 'block-night-x03y03-ne', 'grid-day-r00-c00-s', 'grid-day-r00-c00-n', 'grid-day-r01-c00-s',
                                           'lamp-main-day-x03y03-ne', 'lamp-main-night-x03y03-ne']):
                Image.new('RGB', (160, 90)).save(captures / f'shot-{index:02d}-{label}.png')
            self.assertEqual(review.sheets(folder, most=2), {'block-day.jpg': 1, 'block-night.jpg': 1, 'grid-day-1.jpg': 2, 'grid-day-2.jpg': 1,
                                                             'lamp-main-day.jpg': 1, 'lamp-main-night.jpg': 1})  # a lamp view's lighting is its third part
            self.assertTrue((Path(folder) / 'sheets' / 'grid-day-2.jpg').is_file())

    def test_sheets_keep_the_order_of_the_views_past_the_hundredth(self):
        from unittest import mock
        with tempfile.TemporaryDirectory() as folder:
            captures = Path(folder) / 'captures'; captures.mkdir()
            for index in (100, 9, 99, 10):
                (captures / f'shot-{index:02d}-grid-day-r00-c00-s.png').write_bytes(b'')
            with mock.patch.object(review, 'sheet', side_effect=lambda pictures, output, **_: len(pictures)) as sheet:
                review.sheets(folder, most=2)
            self.assertEqual([[path.name.split('-')[1] for path in call.args[0]] for call in sheet.call_args_list], [['09', '10'], ['99', '100']])


def review_tile(turned):
    """A tile as `turned` left it, to turn again."""
    return {'corners': list(turned[0]), 'crossers': list(turned[1])}


if __name__ == '__main__':
    unittest.main()
