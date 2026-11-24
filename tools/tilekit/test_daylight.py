"""Lit panes are clear by day and full by night, a pane whose texture has a day texture gets a day pane, and an animation names
the whole line of parents of what it fades."""
import json
import re
import unittest
from pathlib import Path

from tools.tilekit import daylight

REPO = Path(__file__).resolve().parents[2]
MODEL = """newmodel t_a01
beginmodelgeom t_a01
node dummy t_a01
  parent NULL
endnode
node dummy lights on
  parent t_a01
endnode
node trimesh pane
  parent lights
  selfillumcolor 0.7 0.7 0.7
  bitmap win_b
  verts 3
    0 0 0
    1 0 0
    0 0 1
endnode
node trimesh lens lit01
  parent lights
  selfillumcolor 1 1 1
  bitmap lens
  verts 3
    0 0 0
    1 0 0
    0 0 1
endnode
node trimesh dull
  parent t_a01
  selfillumcolor 0 0 0
  bitmap win_b
  verts 3
    0 0 0
    1 0 0
    0 0 1
endnode
endmodelgeom t_a01
donemodel t_a01
"""
LIT = {'WIN_B': 'win', 'lens': None}


def anim(text, name):
    return re.search(rf'(?ms)^newanim {name} .*?^doneanim {name} ', text).group(0)


class Daylight(unittest.TestCase):
    def test_lit_meshes_are_the_glowing_ones_of_the_list(self):
        self.assertEqual(daylight.lit_nodes(MODEL, LIT), [('pane', 'lights', 'win_b'), ('lens lit01', 'lights', 'lens')])

    def test_a_lit_pane_is_clear_by_day_and_its_day_pane_the_other_way(self):
        made, lit, panes = daylight.with_daylight(MODEL, LIT)
        self.assertEqual((lit, panes), (2, 1))
        self.assertIn('node trimesh day00_0\n  parent lights\n  selfillumcolor 0 0 0\n  bitmap win\n', made)
        day, turn = anim(made, 'day'), anim(made, 'day2night')
        self.assertIn('node trimesh pane\n    parent lights\n    alphakey 2\n      0.00000 0\n      0.03333 0\n', day)
        self.assertIn('node trimesh day00_0\n    parent lights\n    alphakey 2\n      0.00000 1\n      0.03333 1\n', day)
        self.assertIn('node trimesh pane\n    parent lights\n    alphakey 2\n      0.00000 0\n      0.56667 1\n', turn)
        self.assertIn('node trimesh day00_0\n    parent lights\n    alphakey 2\n      0.00000 1\n      0.56667 0\n', turn)
        self.assertNotIn('dull', day)
        self.assertTrue(made.rstrip().endswith('donemodel t_a01'))

    def test_an_animation_names_the_parents_and_a_spaced_name_is_replaced(self):
        # Without the parents in the animation the client fell over as the area loaded (pilot, 2026-11-23).
        made = daylight.with_daylight(MODEL, LIT)[0]; day = anim(made, 'day')
        self.assertLess(day.index('node dummy lights\n    parent t_a01'), day.index('node trimesh pane'))
        self.assertEqual(day.count('node dummy lights\n'), 1)  # the name as the game reads it, once
        self.assertNotIn('lens lit01', made); self.assertIn('node trimesh lit01_0\n  parent lights\n', made)

    def test_a_model_with_no_lit_mesh_is_left_and_one_with_a_day_already_is_refused(self):
        self.assertEqual(daylight.with_daylight(MODEL, {'other': None}), (MODEL, 0, 0))
        made = daylight.with_daylight(MODEL, LIT)[0]
        with self.assertRaisesRegex(ValueError, 'already'):
            daylight.with_daylight(made, LIT)

    def test_line_ends_are_kept(self):
        made = daylight.with_daylight(MODEL.replace('\n', '\r\n'), LIT)[0]
        self.assertNotIn('\n', made.replace('\r\n', ''))

    def test_the_suburb_list_names_textures_the_pack_holds(self):
        lit = json.loads((REPO / 'docs' / 'tilesets' / 'udp1' / 'daylight.json').read_text(encoding='utf-8'))['lit']
        held = {path.stem.lower() for path in (REPO / 'srn_t_udp1').iterdir()}
        self.assertEqual(sorted(name for pair in lit.items() for name in pair if name and name not in held), [])


if __name__ == '__main__':
    unittest.main()
