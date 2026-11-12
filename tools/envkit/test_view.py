"""The pictures a sheet's work is judged by without the game: references beside their crops, and models square on."""
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from . import view
from .test_convert import WALL, glb


class ViewTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(); self.addCleanup(self.folder.cleanup); self.root = Path(self.folder.name)
        source = self.root / 'meshy' / 'wall'; source.mkdir(parents=True); glb(source / 'model.glb', **WALL)
        Image.new('RGB', (64, 64), (200, 180, 160)).save(source / 'texture_0_base_color.png')
        self.models = {'ek_wall': {'source': 'meshy/wall', 'height': 2.0, 'lit': [{'box': [[-0.6, -0.1, 1.0], [0.6, 0.1, 2.1]]}],
                                   'paint': [{'box': [[-0.6, -0.1, -0.1], [0.6, 0.1, 0.5]], 'colour': [10, 20, 30]}]},
                       'ek_plain': {'source': 'meshy/wall', 'height': 2.0}}

    def test_references_are_shown_beside_the_crops_they_were_drawn_from(self):
        run = self.root / 'run'; (run / 'crops').mkdir(parents=True)
        for name in ('desk', 'yard-gate'):
            Image.new('RGB', (40, 30), (255, 0, 0)).save(run / 'crops' / f'{name}.png'); Image.new('RGB', (90, 110), (0, 0, 255)).save(run / f'{name}-s101-b0.png')
        self.assertEqual(view.contact(run, self.root / 'out' / 'contact.png', columns=2), 2)
        with Image.open(self.root / 'out' / 'contact.png') as page:
            self.assertEqual(page.size[0] % 2, 0); colours = {colour for _, colour in page.convert('RGB').getcolors(1 << 20)}
        self.assertTrue({(255, 0, 0), (0, 0, 255)} <= colours)
        with self.assertRaisesRegex(ValueError, 'No references'):
            view.contact(self.root / 'meshy', self.root / 'out' / 'none.png')
        with self.assertRaisesRegex(ValueError, 'one column at least'):
            view.contact(run, self.root / 'out' / 'contact.png', columns=0)
        Image.new('RGB', (90, 110), (0, 0, 255)).save(run / 'gate-s101-b0.png')  # drawn in this run from a crop made in another
        with self.assertRaisesRegex(ValueError, 'gate-s101-b0.png has no crop beside it'):
            view.contact(run, self.root / 'out' / 'contact.png')

    def test_a_view_is_asked_for_by_name_sides_scale_and_grid(self):
        from .__main__ import _views
        self.assertEqual(_views('ek_wall'), ('ek_wall', [0], None, None)); self.assertEqual(_views('ek_wall:02:300:0.25'), ('ek_wall', [0, 2], 300, 0.25))
        self.assertEqual(_views('ek_wall::300'), ('ek_wall', [0], 300, None))
        for text in ('ek_wall:front', 'ek_wall:4', 'ek_wall:0:300:0', 'ek_wall:0:0', 'ek_wall:0:big', ':0', 'ek_wall:0:300:0.25:9'):
            with self.assertRaisesRegex(ValueError, 'A view'):
                _views(text)

    def test_a_game_set_model_is_drawn_as_it_will_ship(self):
        told = view.elevations(self.models, self.root, 'ek_wall', self.root / 'views', fine=128)
        self.assertEqual(told['bounds'], [[-0.5, 0.0, 0.0], [0.5, 0.0, 2.0]]); self.assertEqual([Path(path).name for path in told['pictures']], ['ek_wall-side0.png'])
        with self.assertRaisesRegex(ValueError, 'Nothing of ek_wall faces side 2'):  # the wall is one face, seen from the front alone
            view.elevations(self.models, self.root, 'ek_wall', self.root / 'views', sides=(2,), fine=128)
        with Image.open(told['pictures'][0]) as front:
            colours = {colour for _, colour in front.convert('RGB').getcolors(1 << 20)}
        self.assertIn((10, 20, 30), colours); self.assertIn((200, 180, 160), colours)  # the set's paint and the picture as generated
        lit = view.elevations(self.models, self.root, 'ek_wall', self.root / 'lit', fine=128, lit=True)
        self.assertGreater(lit['litShare'], 0.3); self.assertLess(lit['litShare'], 0.7)  # the upper half is lit
        (part,) = lit['litParts']; self.assertEqual(part['part'], None); self.assertGreater(part['held'], 0); self.assertEqual(part['lit'], part['held'])  # what its box holds, it lights
        dark = {**self.models['ek_wall'], 'paint': [{'box': [[-0.6, -0.1, -0.1], [0.6, 0.1, 2.1]], 'colour': [0, 0, 0]}], 'lit': [{'part': 'sign', 'box': [[-0.6, -0.1, 1.0], [0.6, 0.1, 2.1]]}]}
        (part,) = view.elevations({'ek_wall': dark}, self.root, 'ek_wall', self.root / 'dark', fine=128, lit=True)['litParts']
        self.assertEqual((part['part'], part['lit']), ('sign', 0)); self.assertGreater(part['held'], 0)  # a box on a part with nothing to light is told
        with self.assertRaisesRegex(ValueError, 'states no lit parts'):
            view.elevations(self.models, self.root, 'ek_plain', self.root / 'lit', lit=True)
        with self.assertRaisesRegex(ValueError, 'No such model'):
            view.elevations(self.models, self.root, 'ek_other', self.root / 'views')
        with self.assertRaisesRegex(ValueError, 'A side is'):
            view.elevations(self.models, self.root, 'ek_plain', self.root / 'views', sides=(4,), fine=128)

    def test_a_model_is_drawn_from_a_stated_eye(self):
        self.assertEqual([value if isinstance(value, (str, float)) else value.tolist() for value in view.eye('front=0,-4,1,0,0,1')], ['front', [0.0, -4.0, 1.0], [0.0, 0.0, 1.0], 50.0, 14.0])
        self.assertEqual(view.eye('a-1=0,-4,1,0,0,1,60,3')[3:], (60.0, 3.0)); self.assertEqual(view.eye('a=0,-4,1,0,0,1,60')[3:], (60.0, 14.0))
        for text in ('front', 'front=0,-4,1', '=0,-4,1,0,0,1', 'front=0,-4,1,0,0,x', 'front=0,0,1,0,0,1', 'front=0,-4,1,0,0,1,0', 'front=0,-4,1,0,0,1,50,0', 'front=0,-4,1,0,0,1,50,3,9'):
            with self.assertRaisesRegex(ValueError, 'An eye'):
                view.eye(text)
        told = view.perspective(self.models, self.root, 'ek_wall', self.root / 'eyes', [view.eye('front=0,-4,1,0,0,1')], size=(160, 100))
        self.assertEqual(([Path(path).name for path in told['pictures']], told['faces']), (['ek_wall-front.png'], {'front': 2}))
        with Image.open(told['pictures'][0]) as picture:
            self.assertEqual(picture.size, (160, 100)); colours = {colour for _, colour in picture.convert('RGB').getcolors(1 << 20)}
        self.assertTrue({(10, 20, 30), (200, 180, 160), (40, 44, 52)} <= colours)  # the set's paint, the picture as generated, and nothing behind them
        for said, eyes in (('Nothing of ek_wall is seen from the eye away', ['away=0,-4,1,0,-8,1']), ('looks straight up or down', ['down=0,0,9,0,0,1']), ('Give an eye', [])):
            with self.assertRaisesRegex(ValueError, said):
                view.perspective(self.models, self.root, 'ek_wall', self.root / 'eyes', [view.eye(text) for text in eyes], size=(160, 100))
        with self.assertRaisesRegex(ValueError, 'No such model'):
            view.perspective(self.models, self.root, 'ek_other', self.root / 'eyes', [view.eye('front=0,-4,1,0,0,1')])

    def test_a_generated_model_is_drawn_before_any_game_set_states_it(self):
        told = view.raw(self.root / 'meshy' / 'wall', 3.0, self.root / 'raw', sides=(0,), fine=128)
        self.assertEqual(told['bounds'][1][2], 3.0); self.assertTrue(Path(told['pictures'][0]).is_file()); self.assertEqual(Path(told['pictures'][0]).name, 'wall-side0.png')
        from argparse import Namespace
        from . import __main__ as command
        asked = dict(models=None, source=str(self.root / 'meshy' / 'wall'), height=3.0, output=str(self.root / 'raw2'), root=None, eye=[])
        for more in (dict(model=['0'], lit=True), dict(model=['0', '2'], lit=False), dict(model=['0'], lit=False, root='root'), dict(model=['0'], lit=False, eye=['front=0,-4,1,0,0,1'])):
            with self.assertRaisesRegex(ValueError, 'has no set to give it lit boxes'):  # what it would ignore is refused
                command.command_view(Namespace(**{**asked, **more}))


if __name__ == '__main__':
    unittest.main()
