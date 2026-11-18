"""The review module: how a tile turns, an area laid from a set's own rules, the views taken of it and its script."""
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
        crossing = review.solve(TILES, G, 3, 3, [], [{'crosser': 'Road', 'cells': [[1, 0], [1, 2]]}, {'crosser': 'Road', 'cells': [[0, 1], [2, 1]]}])
        self.assertEqual(crossing[(1, 1)][0], 7)  # two runs that reach the area's edges cross in the middle
        with self.assertRaisesRegex(ValueError, r'No tile of the set fits: 0,0 needs corners Ground/Lake/Ground/Ground'):
            review.solve(TILES, G, 3, 3, [{'terrain': 'Lake', 'at': [1, 1], 'size': [1, 1]}])
        with self.assertRaisesRegex(ValueError, "reaches the area's edge"):
            review.solve(TILES, G, 3, 3, [{'terrain': T, 'at': [2, 1]}])
        with self.assertRaisesRegex(ValueError, 'lies over another patch'):
            review.solve(TILES, G, 5, 5, [{'terrain': T, 'at': [1, 1]}, {'terrain': T, 'at': [2, 2]}])
        with self.assertRaisesRegex(ValueError, 'is straight'):
            review.solve(TILES, G, 3, 3, [], [{'crosser': 'Road', 'cells': [[0, 0], [1, 1]]}])

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
        self.assertIn('DelayCommand(wait+1.0,WriteTimestampedLogEntry("ENVKIT shot="+IntToString(n)+" target="+label+" valid=1"));', script)
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
        self.assertEqual([area['tag'] for area in review.plan(SET, spec, parts=('grid', 'area'))[0]], ['tkgd'])  # no built area given: that part is left out
        with self.assertRaisesRegex(ValueError, 'does not agree with this set'):
            review.plan(SET, spec, built_area=(2, 1, [(2, 0), (0, 0)]))  # a tower's side beside plain ground
        with self.assertRaisesRegex(ValueError, 'Nothing to review'):
            review.plan(SET, spec, parts=('area',))

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
            for index, label in enumerate(['block-day-x03y03-ne', 'block-night-x03y03-ne', 'grid-day-r00-c00-s', 'grid-day-r00-c00-n', 'grid-day-r01-c00-s']):
                Image.new('RGB', (160, 90)).save(captures / f'shot-{index:02d}-{label}.png')
            self.assertEqual(review.sheets(folder, most=2), {'block-day.jpg': 1, 'block-night.jpg': 1, 'grid-day-1.jpg': 2, 'grid-day-2.jpg': 1})
            self.assertTrue((Path(folder) / 'sheets' / 'grid-day-2.jpg').is_file())


def review_tile(turned):
    """A tile as `turned` left it, to turn again."""
    return {'corners': list(turned[0]), 'crossers': list(turned[1])}


if __name__ == '__main__':
    unittest.main()
