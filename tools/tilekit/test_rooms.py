"""Room groups of the unified interior tileset: what a room is made of, what is refused, and that the pack holds what
today's shells, props and specs give."""
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from tools.tilekit import cuts, geometry, inventory, joins, merge, rooms
from tools.tilekit.test_strip import box, room

REPO = Path(__file__).resolve().parents[2]
PACKS = ('srn_t_srx02', 'srn_t_udp2', 'srn_t_tfb01', 'srn_t_tbx78', 'srn_t_nac01', 'srn_t_common', 'srn_door', 'srn_placeable', 'srn_envprop', 'srn_2da')  # what this reads: named so the test selector runs it when one changes
SPEC_PATH = REPO / 'docs' / 'tilesets' / 'srx02' / 'merge.json'
SPEC = json.loads(SPEC_PATH.read_text(encoding='utf-8'))
SET = ('[TILES]\r\nCount=1\r\n\r\n[TILE0]\r\nModel=tst\r\nTopLeft=Wall\r\nTopRight=Wall\r\nBottomLeft=Wall\r\nBottomRight=Wall\r\nTop=\r\nRight=\r\nBottom=\r\nLeft=\r\n\r\n'
       '[TILE0DOOR0]\r\nType=24\r\nX=0.00\r\n\r\n[GROUPS]\r\nCount=1\r\n\r\n[GROUP0]\r\nName=Den\r\nRows=1\r\nColumns=1\r\nTile0=0\r\n\r\n')
ROOM = {'id': 'den', 'category': 'Home', 'name': 'Den', 'shell': {'set': 'a', 'group': 'Den'}, 'ceiling': {'texture': 'tiles', 'height': 3.0, 'repeat': 2.5},
        'faces': [{'node': 'books', 'texture': 'shelf', 'corners': [[2.5, 1.5, 0], [2.5, -1.5, 0], [2.5, -1.5, 2.9], [2.5, 1.5, 2.9]], 'screen': {'texture': 'news', 'box': [0.25, 0.25, 0.75, 0.5], 'of': 1}}]}
CHAIR = {'piece': 'chair', 'at': [-2.5, 0.5, 0.0], 'faces': 'e'}


def piece(name, *parts):
    lines = [f'newmodel {name}', f'beginmodelgeom {name}', f'node dummy {name}', '  parent null', 'endnode']
    for part in parts:
        lines += part
    return geometry.parse('\n'.join(lines + [f'endmodelgeom {name}', f'donemodel {name}']))[2]


PIECES = {'chair': piece('chair', box('seat', -0.4, 0.4, -0.4, 0.4, 0, 0.9)), 'rug': piece('rug', box('rug', -0.5, 0.5, -0.5, 0.5, 0.01, 0.02)),
          'vase': piece('vase', box('vase', -0.1, 0.1, -0.1, 0.1, 0, 0.6)), 'screen': piece('screen', box('screen', -0.1, 0.1, -3.4, 3.4, 0, 2.0))}


def made(*props, **more):
    return rooms.made('den', {**ROOM, 'props': list(props), **more}, SET, lambda name: room(), PIECES, 'tst')


class Made(unittest.TestCase):
    def test_a_room_is_its_shell_stripped_ceiled_and_given_its_pictures(self):
        tiles, told = made(CHAIR); text, wok = tiles['tst_denu_01']; _, root, nodes = geometry.parse(text); named = {node.name: node for node in nodes}
        self.assertEqual(root, 'tst_denu_01'); self.assertEqual(told['left']['tst_denu_01'], ['rug', 'table'])
        self.assertEqual({name for name in named if 'den' in name}, {root, f'{root}_wm', f'{root}_ceil', f'{root}_face0', f'{root}_screen0'}); self.assertNotIn('books', named)
        self.assertEqual([named[f'{root}_{part}'].material for part in ('ceil', 'face0', 'screen0')], ['tiles', 'shelf', 'news'])
        self.assertEqual(sorted({vertex[0] for vertex in named[f'{root}_screen0'].verts}), [2.49])  # a centimetre into the room
        self.assertEqual(sorted({round(vertex[2], 3) for vertex in named[f'{root}_screen0'].verts}), [1.45, 2.175])  # the picture's rows run down
        a, b, c = (named[f'{root}_ceil'].verts[corner] for corner in named[f'{root}_ceil'].faces[0][:3])
        self.assertLess((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]), 0)  # seen from below only
        self.assertTrue(wok.startswith('beginwalkmeshgeom tst_denu_01'))

    def test_what_is_baked_or_built_in_casts_no_shadow_and_the_room_does(self):
        tiles, _ = made(CHAIR); _, root, nodes = geometry.parse(tiles['tst_denf_01'][0])
        quiet = {node.name for node in nodes if ['shadow', '0'] in node.properties}
        self.assertEqual(quiet, {f'{root}_ceil', f'{root}_face0', f'{root}_screen0', f'{root}_kit00'})
        tiles, _ = made(unshadowed=['wood']); _, _, nodes = geometry.parse(tiles['tst_denu_01'][0])
        self.assertIn('wall_w', {node.name for node in nodes if ['shadow', '0'] in node.properties})

    def test_the_furnished_room_is_not_walked_under_its_furniture_and_nowhere_else_differs(self):
        tiles, _ = made(CHAIR, {'piece': 'rug', 'at': [0.0, 0.0, 0.0], 'turn': 0})
        area = lambda text: sum(abs(joins.flat_area(one)) for one in joins.bake(text)[1] if int(one[0, 3]) == 5)
        self.assertAlmostEqual(area(tiles['tst_denu_01'][0]) - area(tiles['tst_denf_01'][0]), 0.64, places=2)  # the chair's foot; a rug is walked over

    def test_a_vase_stands_on_the_chair_placed_before_it_and_nowhere_in_the_air(self):
        vase = {'piece': 'vase', 'at': [-2.5, 0.5, 0.9], 'turn': 0}; made(CHAIR, vase)
        with self.assertRaisesRegex(ValueError, 'stands where a player walks'):
            made(CHAIR, {**vase, 'at': [0.0, 0.0, 0.9]})

    def test_a_prop_s_halo_is_not_baked(self):
        nodes = piece('lamp', box('lamp', 0, 1, 0, 1, 0, 1, ('bitmap ek_ad_lamp',)), box('halo', 0, 1, 0, 1, 1, 2, ('bitmap ek_ad_lamp_h',)))
        self.assertEqual([node.name for node in rooms.without_halos(nodes) if node.rendered], ['lamp'])

    def test_a_room_with_no_props_is_the_same_twice(self):
        tiles, _ = made(); self.assertEqual(tiles['tst_denu_01'][0].replace('denu', 'denf'), tiles['tst_denf_01'][0])


class Refused(unittest.TestCase):
    def test_a_piece_that_faces_a_wall_stands_back_to_front(self):
        with self.assertRaisesRegex(ValueError, 'stands back to front'):  # the couch and the chair of the trial room, 2026-11-24
            made({**CHAIR, 'at': [-3.0, 0.5, 0.0], 'faces': 'w'})
        made({**CHAIR, 'at': [-3.0, 0.5, 0.0], 'front': 'n'})

    def test_furniture_that_cuts_the_room_in_two(self):
        with self.assertRaisesRegex(ValueError, 'denf_01: within the tile, of .* places to stand only'):
            made({'piece': 'screen', 'at': [0.0, 0.0, 0.0], 'turn': 0})
        cells = {(x, y) for x in range(40) for y in range(20) if x not in (19, 20)}
        self.assertRegex(rooms._lanes(cells, [])[0], r'only 2\d\d can be reached'); self.assertEqual(rooms._lanes(cells | {(x, y) for x in (19, 20) for y in range(8, 13)}, []), [])

    def test_a_doorway_furniture_stands_in(self):
        cells = {(x, y) for x in range(20) for y in range(20)} | {(9, y) for y in range(20, 40)}
        self.assertEqual(rooms._lanes(cells, [(9, 20)]), []); self.assertRegex(rooms._lanes(cells, [(9, 39)])[0], 'the way in at')

    def test_a_furnishing_that_is_no_placeable_and_a_spec_that_says_too_little(self):
        with self.assertRaisesRegex(ValueError, 'no model of placeables.2da'):
            rooms.piece_paths(REPO, {'den': {'props': [{'piece': 'nosuchpiece'}]}})
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'den.json'
            for spec, wanted in (({**ROOM, 'id': 'other'}, 'under its id'), ({**ROOM, 'props': [{'piece': 'x', 'turn': 0, 'faces': 'n'}]}, 'one of `faces` and `turn`')):
                path.write_text(json.dumps(spec), encoding='utf-8')
                with self.assertRaisesRegex(ValueError, wanted):
                    rooms.read(path)

    def test_a_screen_that_would_not_play(self):
        with tempfile.TemporaryDirectory() as folder:
            pack = Path(folder) / 'srn_t_x'; pack.mkdir()
            for name in ('tiles.dds', 'shelf.dds', 'news.dds', 'news.txi'):
                (pack / name).write_text('proceduretype cycle', encoding='ascii')
            with self.assertRaisesRegex(ValueError, 'TGA'):  # a sheet in a DDS drew as a pale film, 2026-11-24
                rooms.textured(folder, 'den', ROOM)
            (pack / 'news.dds').rename(pack / 'news.tga'); rooms.textured(folder, 'den', ROOM); (pack / 'news.txi').unlink()
            with self.assertRaisesRegex(ValueError, 'cycle'):
                rooms.textured(folder, 'den', ROOM)


class Cut(unittest.TestCase):
    def test_a_footprint_that_nicks_a_face_takes_no_more_than_itself(self):  # a coffee table took 7 square metres of the trial room's floor with it
        triangle = [(-2.5688, -0.9723, 0.0), (-1.72, -3.48, 0.0), (-1.72, -0.15, 0.0)]; footprint = [(-1.76, -0.16), (-0.84, -0.16), (-0.84, 0.76), (-1.76, 0.76)]
        inside = cuts._clip(triangle, footprint); parts = cuts.outside(triangle, inside, footprint); area = lambda ring: abs(cuts._area_signed(ring))
        self.assertAlmostEqual(sum(map(area, parts)) + area(inside), area(triangle), places=3)


class Screens(unittest.TestCase):
    def test_a_sheet_plays_from_its_bottom_row_up(self):
        frames = [Image.new('RGB', (4, 2), (index * 40, 0, 0)) for index in range(4)]; sheet = rooms.flipbook(frames, 2)
        self.assertEqual([sheet.getpixel(at)[0] for at in ((0, 2), (4, 2), (0, 0), (4, 0))], [0, 40, 80, 120])
        self.assertIn('numx 2\nnumy 2\nfps 8\n', rooms.flipbook_txi((4, 2), 2, 2, 8))
        with self.assertRaisesRegex(ValueError, 'full'):
            rooms.flipbook(frames[:3], 2)


class Merged(unittest.TestCase):
    names = {'terrains': [{'set': 'a', 'name': 'Wall', 'key': 'Wall', 'display': 'Wall'}], 'crossers': [], 'groups': [{'set': 'a', 'name': 'Den', 'display': 'Home: Old Den'}]}
    spec = {'set': 'm', 'display': 'M', 'families': [{'set': 'a', 'label': 'Home', 'edge': False}], 'general': 'a', 'grass': 'a', 'doors': {'24': 269}}

    def test_a_room_s_tiles_come_after_the_sets_own_with_their_shell_s_doors_and_both_its_groups_are_shown(self):
        head = '[GENERAL]\r\nName=a\r\nBorder=Wall\r\nDefault=Wall\r\nFloor=Wall\r\n\r\n'; text, _, groups = merge.merged_set({'a': head + SET}, self.names, self.spec, roomed=rooms.records({'den': ROOM}, {'a': SET}, 'm'))
        self.assertEqual([tile['model'] for tile in inventory.read_set(text)['tiles']], ['tst', 'm_denu_01', 'm_denf_01'])
        read = dict(inventory.sections(text)); self.assertEqual([read[f'TILE{at}DOOR0']['Type'] for at in range(3)], ['269'] * 3)
        self.assertEqual([(group['display'], group['tiles'], group['model']) for group in groups], [('Home: Old Den', [0], 'tst'), ('Home: Den', [1], 'm_denu_01'), ('Home: Den, furnished', [2], 'm_denf_01')])

    def test_a_room_s_number_is_kept_and_a_room_taken_away_is_refused(self):
        number, record = merge.numbered({'a': 1}, [], [['a', 0, 1], ['room', 'm_x_01']], ['m_w_01', 'm_x_01'])
        self.assertEqual((number[('room', 'm_x_01')], number[('room', 'm_w_01')], record[-1]), (1, 2, ['room', 'm_w_01']))
        with self.assertRaisesRegex(ValueError, 'room tile m_x_01, which is no longer built'):
            merge.numbered({'a': 1}, [], [['room', 'm_x_01']], [])


class Pack(unittest.TestCase):
    def test_the_pack_holds_what_todays_shells_and_props_give(self):
        self.assertEqual(rooms.stale(REPO, SPEC, SPEC_PATH.with_name('rooms-built.json')), [])
        folder, _ = rooms.paths(REPO, SPEC); specs = rooms.specs(folder)
        if all(not inventory.compiled(path.read_bytes()) for path in rooms.piece_paths(REPO, specs).values()):  # a compiled prop needs Blender to be read
            for path, text in rooms.work(REPO, SPEC)[0].items():
                self.assertEqual((REPO / path).read_bytes().decode('cp1252'), text, path)
        for room, spec in specs.items():
            rooms.textured(REPO, room, spec)


if __name__ == '__main__':
    unittest.main()
