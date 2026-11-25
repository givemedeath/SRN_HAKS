import json
import tempfile
import unittest
from pathlib import Path

from tools.tilekit import finish

REPO = Path(__file__).resolve().parents[2]


class Finish(unittest.TestCase):
    def test_segments_fill_the_band_with_lit_pieces_in_a_seeded_order(self):
        from PIL import Image
        how = {'band': [2, 2, 61, 13], 'fill': [10, 20, 30], 'row': [5, 10], 'from': 4, 'to': 56, 'end': 58, 'widths': [4, 8], 'colours': [[200, 210, 220], [240, 180, 70]], 'gap': 3, 'seed': 7}
        blank = Image.new('RGB', (64, 16), (90, 0, 0)); made = finish.finished(blank, [{'segments': how}])
        self.assertEqual(made.mode, 'RGBA'); self.assertEqual(made.tobytes(), finish.finished(blank, [{'segments': how}]).tobytes())  # the same every time
        row = [made.getpixel((x, 7))[:3] for x in range(64)]
        self.assertEqual(row[0], (90, 0, 0)); self.assertEqual(row[2], (10, 20, 30)); self.assertIn((200, 210, 220), row); self.assertIn((240, 180, 70), row)
        self.assertTrue(all(value in ((90, 0, 0), (10, 20, 30)) for value in row[59:]))  # none past its end
        self.assertEqual(made.getpixel((20, 12))[:3], (10, 20, 30))  # the row alone is lit
        self.assertEqual(blank.getpixel((20, 7)), (90, 0, 0))  # the picture given is left

    def test_a_lift_brightens_what_is_lit_and_leaves_the_dark(self):
        from PIL import Image
        picture = Image.new('RGB', (3, 1)); picture.putdata([(20, 30, 40), (70, 70, 70), (200, 10, 10)])
        made = finish.finished(picture, [{'lift': {'above': 40, 'over': 60, 'to': [225, 240, 250]}}])
        self.assertEqual([made.getpixel((x, 0))[:3] for x in range(3)], [(20, 30, 40), (147, 155, 160), (225, 240, 250)])

    def test_a_malformed_step_is_refused(self):
        from PIL import Image
        picture = Image.new('RGB', (8, 8))
        for steps in ([], {}, [{'glow': {}}], [{'lift': {}}], [{'lift': {'above': 1, 'over': 0, 'to': [1, 1, 1]}}], [{'segments': {'band': [0, 0, 1, 1]}}], [{'caption': {'text': 'A'}}],
                      [{'caption': {'band': [0, 0, 8, 8], 'fill': [0, 0, 0], 'text': 'A', 'font': '../a.ttf', 'size': 8, 'colour': [1, 1, 1], 'middle': 4}}],
                      [{'caption': {'band': [0, 0, 8, 8], 'fill': [0, 0, 0], 'text': 'A', 'font': 'no-such-font-here.ttf', 'size': 8, 'colour': [1, 1, 1], 'middle': 4}}]):
            with self.assertRaises(ValueError):
                finish.finished(picture, steps)

    def test_write_takes_a_redraw_folder_to_another_with_its_records(self):
        from PIL import Image
        spec = {'textures': {'a': {'finish': [{'lift': {'above': 0, 'over': 1, 'to': [9, 9, 9]}}]}, 'b': {}}}
        with tempfile.TemporaryDirectory() as temporary:
            redrawn, out = Path(temporary) / 'in', Path(temporary) / 'out'; redrawn.mkdir()
            with self.assertRaisesRegex(ValueError, 'No redrawn picture'):
                finish.write(spec, redrawn, out)
            Image.new('RGB', (2, 2), (50, 50, 50)).save(redrawn / 'a.png'); (redrawn / 'a.json').write_text('{"seed": 1}')
            self.assertEqual(finish.write(spec, redrawn, out), ['a']); self.assertEqual((out / 'a.json').read_text(), '{"seed": 1}')
            self.assertEqual(Image.open(out / 'a.png').getpixel((0, 0))[:3], (9, 9, 9)); self.assertEqual(Image.open(redrawn / 'a.png').getpixel((0, 0)), (50, 50, 50))
            self.assertEqual(finish.write(spec, redrawn, out, only=['b']), [])
            with self.assertRaisesRegex(ValueError, 'another folder'):
                finish.write(spec, redrawn, redrawn)

    def test_the_arcology_s_hand_finished_pictures_are_recorded(self):
        # three pictures were finished by hand with no record: nothing but the shipped maps held them (2026-11-24)
        textures = json.loads((REPO / 'docs' / 'tilesets' / 'fcx01' / 'redraw.json').read_text(encoding='utf-8'))['textures']
        self.assertEqual({name: [next(iter(step)) for step in how['finish']] for name, how in textures.items() if how.get('finish')},
                         {'kuhmu': ['segments'], 'fcx_pub': ['caption'], 'lights3': ['lift']})


if __name__ == '__main__':
    unittest.main()
