import tempfile
import unittest
from pathlib import Path

from tools.tilekit import lamps

MODEL = """newmodel t_a01
beginmodelgeom t_a01
node dummy t_a01
  parent NULL
endnode
node light t_a01{first}
  parent t_a01
  radius 0.0
  lensflares 1
endnode
node light t_a01sl2
  parent t_a01
  radius 0.0
endnode
node aabb walk
  parent t_a01
  verts 1
    0 0 0
endnode
endmodelgeom t_a01
newanim animloop01 t_a01
  node light t_a01sl2
    parent t_a01
  endnode
doneanim animloop01 t_a01
donemodel t_a01
"""
SET = "[GENERAL]\nName=t\n[TILES]\nCount=1\n[TILE0]\nModel=t_a01\n"


class Lamps(unittest.TestCase):
    def test_source_lights_become_main_lights_with_a_radius(self):
        text, made = lamps.moved(MODEL.format(first='sl1'), 6.0)
        self.assertEqual(made, ['t_a01ml1', 't_a01ml2'])
        self.assertNotIn('sl1', text); self.assertNotIn('sl2', text)
        self.assertEqual(text.count('radius 6.0'), 2); self.assertEqual(text.count('node light t_a01ml2'), 2)  # the animation's node too
        self.assertIn('verts 1', text)

    def test_a_light_node_written_with_a_tab_is_found(self):
        text, made = lamps.moved(MODEL.format(first='sl1').replace('node light t_a01sl1', 'node\tlight  t_a01sl1'))
        self.assertEqual(made, ['t_a01ml1', 't_a01ml2'])

    def test_a_model_with_a_main_light_or_no_source_light_is_left(self):
        self.assertEqual(lamps.moved(MODEL.format(first='ml1')), (None, 'has a main light'))
        self.assertEqual(lamps.moved(MODEL.format(first='sl1').replace('sl', 'xx')), (None, 'no source light'))

    def test_move_writes_only_the_tileset_s_own_unshared_tiles(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary); own = repo / 'srn_t_t'; common = repo / 'srn_t_common'; other = repo / 'srn_t_u'
            for folder in (own, common, other):
                folder.mkdir()
            (own / 't.set').write_text(SET.replace('Count=1', 'Count=3') + '[TILE1]\nModel=t_b01\n[TILE2]\nModel=t_c01\n', encoding='cp1252')
            (other / 'u.set').write_text(SET.replace('t_a01', 't_c01'), encoding='cp1252')
            (own / 't_a01.mdl').write_text(MODEL.format(first='sl1'), encoding='cp1252')
            (common / 't_b01.mdl').write_text(MODEL.format(first='ml1').replace('t_a01', 't_b01'), encoding='cp1252')
            (common / 't_c01.mdl').write_text(MODEL.format(first='sl1').replace('t_a01', 't_c01'), encoding='cp1252')
            (common / 't_z01.mdl').write_text(MODEL.format(first='sl1').replace('t_a01', 't_z01'), encoding='cp1252')  # no tile of the set
            told = lamps.move(repo, 't', repo / 'out')
            self.assertEqual(told, {'t_a01': 'moved', 't_b01': 'has a main light', 't_c01': 'shared with u'})
            self.assertEqual([path.name for path in (repo / 'out').iterdir()], ['t_a01.mdl'])

    def test_an_edge_tile_s_lamps_are_moved_too(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary); own = repo / 'srn_t_t'
            for folder in (own, repo / 'srn_t_common', repo / 'srn_2da'):
                folder.mkdir()
            (own / 't.set').write_text(SET, encoding='cp1252')
            (repo / 'srn_2da' / 't_edge.2da').write_text('2DA V2.0\n\n   Corner1 Edge Corner2 Height Model\n0  Concrete **** Concrete 0 T_E01\n', encoding='cp1252')
            (own / 't_e01.mdl').write_text(MODEL.format(first='sl1').replace('t_a01', 't_e01'), encoding='cp1252')
            self.assertEqual(lamps.move(repo, 't', repo / 'out'), {'t_e01': 'moved'})

    def test_a_model_in_both_packs_is_taken_from_the_tileset_s_own(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary); own = repo / 'srn_t_t'; common = repo / 'srn_t_common'
            for folder in (own, common):
                folder.mkdir()
            (own / 't.set').write_text(SET, encoding='cp1252')
            (own / 't_a01.mdl').write_text(MODEL.format(first='sl1').replace('sl', 'xx'), encoding='cp1252')  # what the game shows: no source light
            (common / 't_a01.mdl').write_text(MODEL.format(first='sl1'), encoding='cp1252')
            self.assertEqual(lamps.move(repo, 't', repo / 'out'), {}); self.assertFalse((repo / 'out' / 't_a01.mdl').exists())

    def test_a_copy_already_in_the_folder_is_the_one_moved(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary); own = repo / 'srn_t_t'; out = repo / 'out'
            for folder in (own, repo / 'srn_t_common', out):
                folder.mkdir()
            (own / 't.set').write_text(SET, encoding='cp1252'); (own / 't_a01.mdl').write_text(MODEL.format(first='sl1'), encoding='cp1252')
            (out / 't_a01.mdl').write_text(MODEL.format(first='sl1').replace('verts 1', 'verts 1\n  # quieted'), encoding='cp1252')  # the shadows' copy
            self.assertEqual(lamps.move(repo, 't', out), {'t_a01': 'moved'})
            self.assertIn('# quieted', (out / 't_a01.mdl').read_text(encoding='cp1252'))


if __name__ == '__main__':
    unittest.main()
