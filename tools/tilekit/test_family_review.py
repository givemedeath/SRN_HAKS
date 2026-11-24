import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.tilekit import client_settings, family_review, merged, review
from tools.tilekit.test_openings import WALK, model, wall

CORNERS = ('TopLeft', 'TopRight', 'BottomLeft', 'BottomRight')


def tile(number, name, corners):
    return f'[TILE{number}]\nModel={name}\n' + ''.join(f'{key}={corner}\n' for key, corner in zip(CORNERS, corners))


def set_text():
    """A set whose `Tower` can be painted: plain, one corner, two along a side, full, as the Toolset needs them."""
    plain, tower = 'Ground', 'Tower'
    return '[GENERAL]\nDefault=Ground\n' + tile(0, 'x_plain', [plain] * 4) + tile(1, 'x_corner', [plain, plain, plain, tower]) + tile(2, 'x_side', [plain, plain, tower, tower]) + tile(3, 'x_full', [tower] * 4)


class FamilyReviewTest(unittest.TestCase):
    def setUp(self):
        held = tempfile.TemporaryDirectory(); self.addCleanup(held.cleanup); self.repo = Path(held.name); pack = self.repo / 'srn_t_x'; pack.mkdir(); (self.repo / 'srn_2da').mkdir()
        (pack / 'x.set').write_text(set_text())
        for name in ('x_plain', 'x_corner', 'x_side', 'x_full'):
            (pack / f'{name}.mdl').write_text(model(WALK, wall('pane', 'win_01', 'y', 2, -1, 1, 3, 5)))

    def plan(self, *layouts, **said):
        return family_review.plan(self.repo, {'tileset': 'x', 'layouts': list(layouts)}, base=self.repo, **said)

    def test_tiles_apart_and_the_views_of_each(self):
        (self.repo / 'spec.json').write_text(json.dumps({'tiles': {'x_side': [{'piece': 'camera', 'at': [5, 1, 3]}, {'piece': 'mast', 'at': [0, 0, 9]}]}}))
        areas, shots, left = self.plan({'kind': 'tiles', 'name': 'fam', 'terrains': ['tow*'], 'placements': 'spec.json', 'room': 4, 'views': [
            {'kind': 'facade', 'lights': ['day'], 'every': 2}, {'kind': 'wall'}, {'kind': 'up', 'only': ['mast'], 'lights': ['night']}]})
        self.assertEqual([shot['label'] for shot in shots], ['day-corner-facade', 'day-side-facade', 'day-side-wall', 'night-side-wall', 'night-side-up'])  # x_corner, x_full, x_side in order
        self.assertEqual([area['tag'] for area in areas], ['famd', 'famn']); self.assertEqual(left, []); self.assertEqual(areas[0]['width'], 5 * 2 + 1 + 8)
        wall_ = shots[2]; self.assertEqual((wall_['stand'], wall_['facing']), ([155.0, 45.0], 180))  # ten metres east of the third tile, looking west
        self.assertEqual(areas[0]['laid'][14, 4], (2, 0)); self.assertEqual(areas[0]['laid'][0, 0], (0, 0))

    def test_glass_is_looked_at_where_it_is(self):
        _, shots, _ = self.plan({'kind': 'tiles', 'name': 'g', 'models': ['X_full'], 'glass': ['win*'], 'lights': ['day'], 'views': [{'kind': 'glass'}]})
        faulty = model(wall('pane', 'win_01', 'y', 2, -1, 1, 3, 5)); faulty = family_review.geometry.parse(faulty)[2]
        for node in faulty:
            node.faces = [[0, 1, 99, *face[3:]] for face in node.faces]
        self.assertIsNone(family_review.largest_glass(faulty, ['win*']))
        self.assertIn(shots[0]['facing'], (90, 270)); self.assertEqual(shots[0]['height'], 2.0)

    def test_towers_are_painted_by_the_sets_rules(self):
        areas, shots, _ = self.plan({'kind': 'towers', 'name': 'tow', 'terrains': ['Tower', 'Tower'], 'size': 2, 'lights': ['day'], 'room': 4, 'views': [{'kind': 'side', 'sides': ['s']}, {'kind': 'up'}]})
        self.assertEqual([shot['label'] for shot in shots], ['day-0tower-s', 'day-0tower-up', 'day-1tower-s', 'day-1tower-up'])
        self.assertEqual(areas[0]['laid'][4, 4], (3, 0)); self.assertEqual(review.disagreements(areas[0]['width'], [areas[0]['laid'][column, row] for row in range(areas[0]['height'])
                         for column in range(areas[0]['width'])], family_review.Set(self.repo, 'x', None, None, '.').tiles), [])
        self.assertEqual(len(self.plan({'kind': 'towers', 'name': 'tow', 'terrains': ['Tower', 'Tower', 'Tower']}, most=None)[1]), 30)  # the default values make a layout
        with self.assertRaisesRegex(ValueError, 'outside'):
            self.plan({'kind': 'towers', 'name': 'tow', 'terrains': ['Tower'], 'size': 2, 'room': 1, 'views': [{'kind': 'far'}]})

    def test_a_block_seen_from_its_crossings(self):
        _, shots, _ = self.plan({'kind': 'block', 'name': 'big', 'lights': ['day'], 'width': 8, 'height': 8, 'patches': [{'terrain': 'tower', 'at': [2, 2], 'size': [2, 2]}], 'crossings': [[0, 0], [5, 5]], 'views': ['x05y05-sw']})
        self.assertEqual([shot['label'] for shot in shots], ['day-big-x05y05-sw'])
        with self.assertRaisesRegex(ValueError, 'x5y5-ne'):
            self.plan({'kind': 'block', 'name': 'big', 'lights': ['day'], 'width': 8, 'height': 8, 'patches': [], 'crossings': [[5, 5]], 'views': ['x05y05-sw', 'x5y5-ne']})

    def test_a_street_is_of_tiles_wholly_of_its_terrain(self):
        with mock.patch.object(family_review.placer, '_kerbs', return_value=[1]):
            areas, shots, _ = self.plan({'kind': 'street', 'name': 'st', 'terrains': ['Ground'], 'across': 2, 'down': 2})
        self.assertEqual({number for number, _ in areas[0]['laid'].values()}, {0}); self.assertEqual([shot['label'] for shot in shots], ['day-st-south', 'day-st-north'])

    def test_doors_stand_at_their_hooks(self):
        hook = {'tile': 2, 'model': 'x_side', 'door': 0, 'at': [0.0, 4.9, 0.0], 'turn': 0.0, 'width': 4.0, 'height': 3.0}
        (self.repo / 'op.json').write_text(json.dumps({'hooks': [hook, {**hook, 'tile': 3, 'model': 'x_full', 'width': 2.0}, {'tile': 1, 'model': 'x_corner', 'note': 'no'}]}))
        layout = {'kind': 'doors', 'name': 'dr', 'hooks': 'op.json', 'clear': [[2.0, 3.0]]}
        areas, shots, _ = self.plan(layout)
        self.assertEqual([shot['label'] for shot in shots], ['day-t2-d0']); self.assertNotIn('doors', areas[0]); self.assertEqual(shots[0]['facing'], 270.0)  # from the street past the cell's side
        areas, shots, _ = self.plan({**layout, 'doors': {'x_side': 1094}})
        self.assertEqual([(one['row'], one['opened']) for one in areas[0]['doors']], [(1094, 0), (1094, 1)]); self.assertEqual([shot['label'][-4:] for shot in shots], ['shut', 'open'])
        for opened in ([], [3], [1, 1]):
            with self.assertRaisesRegex(ValueError, 'each state once'):
                self.plan({**layout, 'doors': {'x_side': 1094}, 'opened': opened})
        areas, shots, _ = self.plan({**layout, 'clear': [], 'doors': {'x_side': 1094}, 'opened': [0, 1, 2]})
        self.assertEqual([shot['label'] for shot in shots], ['day-t2-d0-shut', 'day-t3-d0', 'day-t2-d0-open', 'day-t2-d0-open2'])

    def test_doors_at_the_ends_of_a_row_and_wide_ones(self):
        hook = {'tile': 2, 'model': 'x_side', 'door': 0, 'at': [-4.9, 0.0, 0.0], 'turn': 90.0, 'width': 9.0, 'height': 3.0}
        (self.repo / 'op.json').write_text(json.dumps({'hooks': [hook, {**hook, 'at': [4.9, 0.0, 0.0], 'turn': -90.0, 'door': 1}]})); layout = {'kind': 'doors', 'name': 'dr', 'hooks': 'op.json', 'models': ['X_Side']}
        self.assertEqual(len(self.plan(layout)[1]), 2)
        with self.assertRaisesRegex(ValueError, 'typo'):
            self.plan({**layout, 'doors': {'typo': 1}})
        (self.repo / 'op.json').write_text(json.dumps({'hooks': [{**hook, 'tile': 3}]}))
        with self.assertRaisesRegex(ValueError, 'measure the openings again'):
            self.plan(layout)

    def test_an_up_view_fits_the_default_room(self):
        self.assertEqual(len(self.plan({'kind': 'tiles', 'name': 'up', 'models': ['x_full'], 'lights': ['day'], 'views': [{'kind': 'up'}]})[1]), 1)

    def test_a_merged_sets_tiles_are_read_from_its_families(self):
        (self.repo / 'srn_t_m').mkdir(); (self.repo / 'srn_t_m' / 'm.set').write_text(set_text()); spec = self.repo / 'docs' / 'tilesets' / 'm'; spec.mkdir(parents=True)
        self.assertEqual(family_review.texts_of(self.repo, 'm', None, ()), {})
        (spec / 'merge.json').write_text(json.dumps({'families': [{'set': 'X'}]}))
        self.assertEqual(set(family_review.texts_of(self.repo, 'm', None, ())), {'x_plain', 'x_corner', 'x_side', 'x_full'}); self.assertEqual(merged.over(self.repo, 'x'), {'m'}); self.assertEqual(merged.over(self.repo, 'm'), set())
        with self.assertRaisesRegex(ValueError, 'srn_t_x'):
            family_review.haks({'tileset': 'm', 'haks': ['srn_t_m']}, self.repo)
        self.assertEqual(family_review.haks({'tileset': 'm', 'haks': ['srn_t_m', 'srn_t_x']}, self.repo), ('srn_t_m', 'srn_t_x'))

    def test_models_only_the_overlay_has(self):
        overlay = self.repo / 'ov'; overlay.mkdir(); (overlay / 'x.set').write_text(set_text() + tile(4, 'x_new', ['New'] * 4)); (overlay / 'x_new.mdl').write_text(model(WALK))
        self.assertEqual([shot['label'] for shot in self.plan({'kind': 'tiles', 'name': 'n', 'terrains': ['New'], 'lights': ['day']}, overlay=overlay)[1]], ['day-new-facade'])

    def test_views_are_few_unless_asked(self):
        layout = {'kind': 'tiles', 'name': 'fam', 'terrains': ['Ground', 'Tower']}
        self.assertEqual(len(self.plan(layout, most=None)[1]), 8)
        _, shots, left = self.plan(layout, most=3); self.assertEqual((len(shots), len(left)), (3, 5))
        self.assertEqual([shot['label'] for shot in self.plan(layout, views=['night-full'])[1]], ['night-full-facade'])
        with self.assertRaisesRegex(ValueError, 'begins with typo'):
            self.plan(layout, views=['night-full', 'typo'])
        labels = [shot['label'] for shot in self.plan(layout, {**layout, 'name': 'near', 'space': 4}, most=None)[1]]; self.assertEqual(len(set(labels)), 16); self.assertIn('day-full-facade-near', labels)

    def test_wrong_specs_are_refused(self):
        from types import SimpleNamespace
        from tools.tilekit import commands
        with self.assertRaisesRegex(ValueError, 'at least one'):
            commands._most(SimpleNamespace(all=False, most=0))
        for empty in ('', ','):
            with self.assertRaisesRegex(ValueError, '--models'):
                commands._names(empty, '--models')
        self.assertEqual(commands._names(None, '--models'), []); self.assertEqual(commands._names('a, b ,'), ['a', 'b'])
        for layout, why in (({'kind': 'x', 'name': 'a'}, 'A layout is'), ({'kind': 'tiles', 'name': 'A1'}, 'lowercase'), ({'kind': 'tiles', 'name': 'a', 'terrains': ['none']}, 'No tile'),
                            ({'kind': 'tiles', 'name': 'a', 'terrains': ['Tower'], 'lights': ['dusk']}, 'lit by'),
                            ({'kind': 'tiles', 'name': 'a', 'terrains': ['Tower'], 'views': [{'kind': 'facade', 'lights': ['dusk']}]}, 'lit by'),
                            ({'kind': 'tiles', 'name': 'a', 'terrains': ['Tower'], 'space': 0}, 'at least 1'),
                            ({'kind': 'tiles', 'name': 'a', 'terrains': ['Tower'], 'views': [{'kind': 'facade', 'every': 0}]}, 'at least 1'),
                            ({'kind': 'tiles', 'name': 'a', 'terrains': ['Tower'], 'views': [{'kind': 'facade', 'lights': ['overcast']}]}, 'not laid in'),
                            ({'kind': 'tiles', 'name': 'a', 'models': ['x_full', 'x_full']}, 'Two views'),
                            ({'kind': 'towers', 'name': 'a', 'terrains': []}, 'no terrain'),
                            ({'kind': 'tiles', 'name': 'a', 'models': ['x_full'], 'light': ['day']}, 'has no light'), ({'kind': 'tiles', 'name': 'a', 'models': ['x_full'], 'views': [{'kind': 'facade', 'light': 'day'}]}, 'has no light'),
                            ({'kind': 'tiles', 'name': 'a', 'models': ['x_full'], 'views': ['facade']}, 'objects'), ({'kind': 'block', 'name': 'a', 'width': 8, 'height': 8, 'patches': [], 'crossings': [], 'views': [{'kind': 'x'}]}, 'are names'),
                            ({'kind': 'street', 'name': 'a', 'terrains': ['Ground'], 'close': [{'piece': 'x', 'light': 'day', 'at': 1}]}, 'has no at'), ({'kind': 'tiles', 'name': 'a', 'models': ['x_full'], 'glass': ['none'], 'views': [{'kind': 'facade'}, {'kind': 'glass'}]}, 'no tile has a view glass'), ({'kind': 'towers', 'name': 'a', 'terrains': ['Tower'], 'across': 0}, 'at least 1'),
                            ({'kind': 'tiles', 'name': '\u00e9', 'terrains': ['Tower']}, 'lowercase'),
                            ({'kind': 'street', 'name': 'a', 'terrains': ['Ground'], 'close': [{'piece': 'x', 'light': 'dusk'}]}, 'lit by')):
            with self.assertRaisesRegex(ValueError, why):
                self.plan(layout)
        with self.assertRaisesRegex(ValueError, 'srn_t_x'):
            family_review.haks({'tileset': 'x'})
        with self.assertRaisesRegex(ValueError, 'has no hak'):
            family_review.plan(self.repo, {'tileset': 'x', 'hak': [], 'layouts': [{'kind': 'tiles', 'name': 'a', 'models': ['x_full']}]})

    def test_a_run(self):
        layout = {'kind': 'tiles', 'name': 'fam', 'models': ['x_full']}; spec = {'tileset': 'x', 'haks': ['srn_t_x', 'srn_door'], 'layouts': [layout]}; done = {'captures': ['a', 'b'], 'late': [], 'elsewhere': []}
        with mock.patch.object(review, 'build', return_value={'module': 'm.mod', 'overlay': ['x.set']}) as build, mock.patch.object(review, 'capture', return_value=dict(done)) as capture, \
                mock.patch.object(review, 'sheets', return_value={'s.jpg': 2}):
            overlay = self.repo / 'ov'; overlay.mkdir(); said = dict(overlay=overlay, base=self.repo)
            told = family_review.run(self.repo, spec, 'out', 'n', 'game', 'built', **said); self.assertEqual((told['views'], told['captures'], told['sheets'], told['areas']), (2, 2, {'s.jpg': 2}, ['famd', 'famn']))
            self.assertEqual(build.call_args.kwargs, {'overlay': overlay, 'haks': ('srn_t_x', 'srn_door')}); self.assertEqual((build.call_args.args[0], build.call_args.args[3:]), ('n', ('out', 'game', 'built')))
            self.assertNotIn('captures', family_review.run(self.repo, spec, 'out', 'n', 'game', 'built', start=False, **said)); self.assertEqual(capture.call_count, 1)

    def test_an_output_without_a_folder_is_refused_first(self):
        from types import SimpleNamespace
        from tools.tilekit import commands
        for command in (commands.propose_command, commands.openings_command, commands.rank_command):
            with self.assertRaisesRegex(ValueError, 'does not exist'):
                command(SimpleNamespace(out=self.repo / 'none' / 'a.json'))
            with self.assertRaisesRegex(ValueError, 'is a folder'):
                command(SimpleNamespace(out=self.repo))

    def test_every_run_states_the_client_settings(self):
        text = client_settings.settings()
        self.assertIn('[graphics.keyholing]\nenabled = false', text); self.assertIn('[graphics.framelimiter]\nenabled = true', text); self.assertNotIn('vsync', text)
        for cap in (0, 201, None):
            with self.assertRaisesRegex(ValueError, 'limited'):
                client_settings.settings(cap)
        with mock.patch.object(review.prop_fixture, 'run', return_value={'captures': [], 'late': [], 'lines': []}) as run, mock.patch.object(review.checks, 'wait_for_clients'), \
                tempfile.TemporaryDirectory() as folder:
            (Path(folder) / 'captures').mkdir(); review.capture('game', {}, folder)
        self.assertEqual(run.call_args.kwargs['extra_settings'], text)
        area = review.area_documents('a', 'A', 'x', 1, 1, {(0, 0): (0, 0)}, 'day')['a.are']; self.assertEqual(area['FogClipDist']['value'], 9999.0)


if __name__ == '__main__':
    unittest.main()
