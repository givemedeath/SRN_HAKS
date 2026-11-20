"""Textures drawn again by a generator: what it is asked, the order, what is kept, and what a build takes."""
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from . import material, redraw
from .test_material import fake_compress


class RedrawTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(); self.addCleanup(folder.cleanup); self.root = Path(folder.name); (self.root / 'srn_t_common').mkdir()
        pane = np.zeros((16, 8, 3), np.uint8); pane[:, 3:5] = 200  # a tall picture with a mullion down the middle
        for name in ('pane', 'pane_g', 'sign'):
            Image.fromarray(pane).save(self.root / 'srn_t_common' / f'{name}.tga')
        self.spec = {'textures': {'pane_g': {'kind': 'window', 'district': 'barrens', 'of': 'pane', 'light': 'green'},
                                  'pane': {'kind': 'window', 'district': 'barrens', 'note': 'A sash window.', 'tiles': True},
                                  'sign': {'kind': 'sign', 'district': 'civic'}}}
        self.asked = []

    def draw(self, folder, text, images):
        self.asked.append((Path(folder).name, [Path(image).name for image in images], text))
        if Path(folder).name == 'sign':
            return  # the generator left nothing
        with Image.open(Path(folder) / 'ref.png') as reference:
            reference.save(Path(folder) / 'out.png')

    def test_a_prompt_names_the_thing_its_district_and_the_layout_to_keep(self):
        text = redraw.prompt('pane', self.spec['textures']['pane'], (512, 1024), tiles=True)
        for part in ('exactly 512x1024 pixels', 'game texture of a window', 'Shadowrun Barrens', 'A sash window.', 'stays in the same position', 'pure black', 'tile seamlessly'):
            self.assertIn(part, text)
        lit = redraw.prompt('pane_g', self.spec['textures']['pane_g'], (512, 1024))
        self.assertIn('day.png', lit); self.assertIn('The light is green', lit); self.assertNotIn('tile seamlessly', lit)
        for how, said in (({'kind': 'door', 'district': 'barrens'}, 'kind is one of'), ({'kind': 'sign', 'district': 'moon'}, 'district is one of')):
            with self.assertRaisesRegex(ValueError, said):
                redraw.prompt('x', how, (64, 64))

    def test_day_pictures_come_first_and_a_lit_one_is_drawn_from_its_day_picture(self):
        told = redraw.redraw(self.spec, self.root, self.root / 'new', self.draw, workers=1, say=None)
        self.assertEqual((told['pane'], told['pane_g']), ('redrawn', 'redrawn')); self.assertIn('left no out.png', told['sign'])
        self.assertEqual([(name, images) for name, images, _ in self.asked], [('pane', ['ref.png']), ('sign', ['ref.png']), ('pane_g', ['day.png', 'ref.png'])])
        with Image.open(self.root / 'new' / 'pane.png') as made:
            self.assertEqual(made.size, (512, 1024))
        record = json.loads((self.root / 'new' / 'pane.json').read_text())
        self.assertEqual((record['size'], record['alike'] > 0.9), ([512, 1024], True))
        again = redraw.redraw(self.spec, self.root, self.root / 'new', self.draw, only=['pane', 'pane_g'], workers=1, say=None)
        self.assertEqual((again, len(self.asked)), ({'pane': 'kept', 'pane_g': 'kept'}, 3))
        with self.assertRaisesRegex(ValueError, 'pane_g: it is of nothing'):
            redraw.redraw({'textures': {'pane_g': {'kind': 'window', 'district': 'barrens', 'of': 'nothing'}}}, self.root, self.root / 'other', self.draw, say=None)
        white = lambda folder, text, images: Image.new('RGB', (64, 128), (255, 255, 255)).save(Path(folder) / 'out.png')  # paints over everything
        redraw.redraw(self.spec, self.root, self.root / 'lit', white, only=['pane', 'pane_g'], workers=1, say=None)
        with Image.open(self.root / 'lit' / 'pane_g.png') as made:  # a lit variant's black openings are black again too
            self.assertEqual((made.getpixel((80, 500)), made.getpixel((256, 500))), ((0, 0, 0), (255, 255, 255)))
        self.assertLess(redraw.alike(np.asarray(Image.open(self.root / 'srn_t_common' / 'pane.tga')), np.random.default_rng(1).integers(0, 255, (16, 8, 3), np.uint8)), 0.3)

    def test_a_kept_picture_must_be_of_the_old_picture_and_a_lit_one_of_its_day_picture(self):
        redraw.redraw(self.spec, self.root, self.root / 'new', self.draw, only=['pane', 'pane_g'], workers=1, say=None)
        Image.new('RGB', (512, 1024), (1, 2, 3)).save(self.root / 'new' / 'pane.png')  # the day picture drawn again
        told =redraw.redraw(self.spec, self.root, self.root / 'new', self.draw, only=['pane_g'], say=None, workers=1)
        self.assertIn('made from another pane day picture', told['pane_g'])
        Image.new('RGB', (8, 16), (9, 9, 9)).save(self.root / 'srn_t_common' / 'pane.tga')  # the original changed
        self.assertIn('not made from the pane the game draws now', redraw.redraw(self.spec, self.root, self.root / 'new', self.draw, only=['pane'], say=None)['pane'])

    def test_a_composed_lit_variant_lights_what_the_old_night_texture_lit_and_no_generator_is_asked(self):
        day = np.full((16, 8, 3), 40, np.uint8); day[:, 3:5] = 90; night = day.copy(); night[:, :3] = (250, 220, 120)  # the left pane lit warm at night
        Image.fromarray(day).save(self.root / 'srn_t_common' / 'pane.tga'); Image.fromarray(night).save(self.root / 'srn_t_common' / 'pane_g.tga')
        made = np.asarray(redraw.composed(Image.fromarray(day).resize((64, 128), Image.NEAREST), day, night), int)
        self.assertGreater(made[64, 8, 0], 150); self.assertGreater(made[64, 8, 0], made[64, 8, 2] + 60)  # lit, and warm
        self.assertLess(made[64, 56].max(), 40)  # the right pane as by day, darker
        (self.root / 'new').mkdir(); Image.fromarray(day).save(self.root / 'new' / 'pane.png')
        (self.root / 'new' / 'pane.json').write_text(json.dumps({'source': redraw._sha(day)}), encoding='utf-8'); spec ={'textures': {**self.spec['textures'], 'pane_g': {**self.spec['textures']['pane_g'], 'compose': True}}}
        self.assertEqual(redraw.redraw(spec, self.root, self.root / 'new', self.draw, only=['pane', 'pane_g'], say=None), {'pane': 'kept', 'pane_g': 'composed'})
        self.assertEqual((self.asked, json.loads((self.root / 'new' / 'pane_g.json').read_text())['kind']), ([], 'tilekit-composed'))
        self.assertIn('The first image is a game texture, by day. The second image', redraw.prompt('pane_g', self.spec['textures']['pane_g'], (64, 64), tool=False))
        self.assertNotIn('out.png', redraw.prompt('pane', self.spec['textures']['pane'], (64, 64), tool=False))

    def test_a_build_starts_a_redrawn_texture_from_its_redrawn_picture(self):
        (self.root / 'new').mkdir(); Image.new('RGB', (64, 64), (0, 0, 255)).save(self.root / 'new' / 'pane.png'); seen = {}

        def keep(image, target, mode, size, crunch, *, data):
            seen[Path(target).name] = np.asarray(image.convert('RGB')); return fake_compress(image, target, mode, size, crunch, data=data)
        spec = {'textures': {'pane': {'route': 'upscale', 'size': [64, 64], 'redrawn': True}}}
        material.build(spec, self.root, self.root, self.root / 'out', 'crunch', compress=keep, redrawn=self.root / 'new')
        self.assertEqual(tuple(seen['pane.dds'][8, 8]), (0, 0, 255))
        with self.assertRaisesRegex(ValueError, 'pane is to be redrawn and has no redrawn picture: run `tilekit redraw`'):
            material.build(spec, self.root, self.root, self.root / 'none', 'crunch', compress=keep)



class WordsTests(unittest.TestCase):
    def test_new_words_replace_the_kind_s_keep_the_wording(self):
        text = redraw.prompt('sign', {'kind': 'sign', 'district': 'barrens', 'words': 'NUYEN XCHANGE'}, (512, 512), tool=False)
        self.assertIn('reads exactly NUYEN XCHANGE', text); self.assertNotIn('wording stays the same', text)
        self.assertIn('wording stays the same', redraw.prompt('sign', {'kind': 'sign', 'district': 'barrens'}, (512, 512), tool=False))


class BlackKeptTests(unittest.TestCase):
    def test_an_opening_black_in_the_old_picture_is_black_again(self):
        old = np.full((32, 64, 3), 200, np.uint8); old[8:24, 8:40] = 0; old[2, 60] = 0  # an opening, and a speck
        drawn = Image.new('RGB', (128, 64), (90, 120, 150))
        kept = np.asarray(redraw.black_kept(old, drawn))
        self.assertTrue((kept[20:44, 20:76] == 0).all()); self.assertTrue((kept[:8] == (90, 120, 150)).all())
        self.assertTrue((kept[4, 120] == (90, 120, 150)).all())


if __name__ == '__main__':
    unittest.main()
