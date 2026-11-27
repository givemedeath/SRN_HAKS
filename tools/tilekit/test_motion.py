"""Screens that move: the materials in the packs are the list's, and what is refused."""
import json
import unittest
from pathlib import Path

from tools.tilekit import motion

REPO = Path(__file__).resolve().parents[2]
SPEC = {'kinds': ['interface', 'trace'], 'contents': {'desk': 'interface'}, 'glow': 0.5, 'textures': {'wall': [{'box': [0, 0, 1, 0.25], 'kind': 'trace'}]}, 'glowing': []}
SCREENS = {'textures': {'laptop': {'screen': [{'box': [0.5, 0.1, 0.9, 0.4], 'picture': 'desk'}, {'box': [0, 0, 1, 1], 'mend': True}]}}}


class Motion(unittest.TestCase):
    def test_the_packs_hold_what_the_list_says(self):
        for path, text in motion.files(REPO).items():
            self.assertEqual((REPO / path).read_text(encoding='ascii'), text, path + ': tilekit motion')

    def test_a_material_s_boxes_count_up_from_the_picture_s_foot(self):
        made = motion.parts(SPEC, SCREENS); self.assertEqual(made, {'laptop': [([0.5, 0.1, 0.9, 0.4], 'interface')], 'wall': [([0, 0, 1, 0.25], 'trace')]})
        text = motion.material('wall', made['wall'], SPEC); self.assertIn('parameter float ScreenBox0 0.0000 0.7500 1.0000 1.0000', text); self.assertIn('parameter float ScreenHow0 2.0 ', text); self.assertIn('texture0 wall\n', text)

    def test_an_envkit_material_keeps_its_lines_and_is_made_once(self):
        text = motion.glowing('ek_a', 'renderhint NormalAndSpecMapped\r\n\r\ntexture0 ek_a\r\ntexture5 ek_a_i\r\n')
        self.assertIn('customshaderFS srn_screenp_fs', text); self.assertIn('texture5 ek_a_i', text); self.assertEqual(motion.glowing('ek_a', text), text)

    def test_what_is_refused(self):
        for spec, screens, wanted in (({**SPEC, 'contents': {}}, SCREENS, 'does not say what moves'), ({**SPEC, 'textures': {'laptop': []}}, SCREENS, 'its boxes are there'),
                                      ({**SPEC, 'textures': {'wall': [{'box': [0, 0, 1, 1], 'kind': 'dance'}]}}, SCREENS, 'what moves is one of'), ({**SPEC, 'textures': {'wall': [{'box': [0, 0, 1, 1], 'kind': 'trace'}] * 5}}, SCREENS, 'at most'),
                                      ({**SPEC, 'textures': {'wall': [{'box': [0.5, 0, 0.5, 1], 'kind': 'trace'}]}}, SCREENS, 'a box is')):
            with self.assertRaisesRegex(ValueError, wanted):
                motion.parts(spec, screens)
        with self.assertRaisesRegex(ValueError, 'no illumination map'):
            motion.glowing('ek_a', 'texture0 ek_a\ntexture5 null\n')

    def test_the_shaders_have_no_integer_literals_where_floats_stand(self):  # GLSL 1.10 turns none into a float
        for name in ('srn_screen', 'srn_screen_fs', 'srn_screenp_fs'):
            code = '\n'.join(line.split('//')[0] for line in (REPO / 'srn_placeable' / f'{name}.shd').read_text(encoding='ascii').splitlines() if not line.startswith('#'))
            self.assertNotRegex(code, r'(?<![\w.])\d+(?![\w.])')


if __name__ == '__main__':
    unittest.main()
