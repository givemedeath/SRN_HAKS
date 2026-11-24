"""Lit panes are clear by day and full by night, a pane whose texture has a day texture gets a day pane, and an animation names
the whole line of parents of what it fades."""
import json
import re
import unittest
from pathlib import Path

from tools.tilekit import daylight

REPO = Path(__file__).resolve().parents[2]
PACKS = ('srn_t_udp1', 'srn_door', 'srn_placeable')  # the packs that hold the list's textures: named so the test selector checks them out
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

    def test_lit_meshes_of_one_name_each_take_their_own(self):
        # two strip mall tiles name every lit window alike (udp1_b12_04, udp1_b13_09)
        twice = MODEL.replace('node trimesh lens lit01', 'node trimesh pane').replace('endmodelgeom t_a01', 'endmodelgeom t_a01\nnewanim loop t_a01\n  node trimesh pane\n    parent lights\n  endnode\n  node trimesh pane\n    parent lights\n  endnode\ndoneanim loop t_a01')
        made = daylight.with_daylight(twice, LIT)[0]; loop = anim(made, 'loop')
        self.assertEqual(re.findall(r'(?m)^node trimesh (lit\S+)', made), ['lit00_0', 'lit01_0'])
        self.assertEqual(re.findall(r'node trimesh (\S+)', loop), ['lit00_0', 'lit01_0'])
        self.assertIn('node trimesh lit00_0\n  parent lights\n  selfillumcolor 0.7 0.7 0.7\n  bitmap win_b', made)
        shared = MODEL.replace('node trimesh dull', 'node trimesh pane')
        with self.assertRaisesRegex(ValueError, 'shares its name'):
            daylight.with_daylight(shared, LIT)

    def test_names_are_taken_as_the_game_reads_them(self):
        # review of PR 193: a parent written with its second word, a kind in capitals, a name that differs only in case
        spaced = MODEL.replace('  parent lights\n', '  parent lights on\n'); day = anim(daylight.with_daylight(spaced, LIT)[0], 'day')
        self.assertLess(day.index('node dummy lights\n    parent t_a01'), day.index('node trimesh pane\n    parent lights\n'))
        capital = MODEL.replace('node trimesh lens lit01', 'node Trimesh lens lit01'); made = daylight.with_daylight(capital, LIT)[0]
        self.assertNotIn('lens lit01', made); self.assertIn('node Trimesh lit01_0\n', made)
        with self.assertRaisesRegex(ValueError, 'shares its name'):
            daylight.with_daylight(MODEL.replace('node trimesh dull', 'node trimesh Pane'), LIT)
        with self.assertRaisesRegex(ValueError, 'has children'):
            daylight.with_daylight(MODEL.replace('  parent t_a01\n  selfillumcolor 0 0 0', '  parent lens\n  selfillumcolor 0 0 0'), LIT)

    def test_write_takes_a_merged_set_s_tiles_and_counts_those_already_done(self):
        import tempfile
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary); own = repo / 'srn_t_t'; merged = repo / 'srn_t_m'; out = repo / 'out'
            for folder in (own, merged, repo / 'srn_t_common'):
                folder.mkdir()
            for folder, name in ((own, 't'), (merged, 'm')):
                (folder / f'{name}.set').write_text('[TILES]\nCount=1\n[TILE0]\nModel=t_a01\n', encoding='cp1252')
            (own / 't_a01.mdl').write_text(MODEL, encoding='cp1252')
            self.assertEqual(daylight.write(repo, 't', out, LIT)['models'], {})  # the merged set draws it too
            told = daylight.write(repo, 't', out, LIT, shared=['M'])
            self.assertEqual((told['models'], told['panes'], told['done'], told['refused']), ({'t_a01': 2}, 1, 0, {}))
            again = daylight.write(repo, 't', out, LIT, shared=['M'])  # the folder's copy has its day and night: no refusal
            self.assertEqual((again['models'], again['done'], again['refused']), ({}, 1, {}))
            made = (out / 't_a01.mdl').read_text(encoding='cp1252'); self.assertEqual(daylight.with_daylight(daylight.without(made), LIT)[0], made)
            self.assertEqual(daylight.write(repo, 't', out, LIT, shared=['M'], again=True)['models'], {})  # made anew, the same: not written
            anew = daylight.write(repo, 't', out, {**LIT, 'lens': 'glass'}, shared=['M'], again=True)  # the lens given a day texture since
            self.assertEqual((anew['models'], anew['panes']), ({'t_a01': 2}, 2)); made = (out / 't_a01.mdl').read_text(encoding='cp1252')
            self.assertEqual(len(re.findall(r'(?m)^node trimesh day\d+_\d+$', made)), 2); self.assertEqual(made.count('newanim day t_a01'), 1)

    def test_line_ends_are_kept(self):
        made = daylight.with_daylight(MODEL.replace('\n', '\r\n'), LIT)[0]
        self.assertNotIn('\n', made.replace('\r\n', ''))

    def test_the_suburb_list_names_textures_the_pack_holds(self):
        lit = json.loads((REPO / 'docs' / 'tilesets' / 'udp1' / 'daylight.json').read_text(encoding='utf-8'))['lit']
        held = {path.stem.lower() for pack in PACKS for path in (REPO / pack).iterdir()}
        self.assertEqual(sorted(name for pair in lit.items() for name in pair if name and name not in held), [])


if __name__ == '__main__':
    unittest.main()
