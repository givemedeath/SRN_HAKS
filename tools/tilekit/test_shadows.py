import tempfile
import unittest
from pathlib import Path

from tools.tilekit import shadows

MODEL = """newmodel t_a01
beginmodelgeom t_a01
node trimesh wall
  parent t_a01
  shadow 1
  verts 3
    0 0 0
    10 0.3 0
    0 0 12
endnode
node trimesh sill
  parent t_a01
  shadow 1
  verts 3
    0 0 0
    2 0.3 0
    0 0 0.1
endnode
node trimesh panel
  parent t_a01
  shadow 1
  verts 3
    0 0 0
    8 0 0
    0 0.02 9
endnode
node trimesh ledge
  parent t_a01
  verts 2
    0 0 0
    1.5 0.2 0.2
endnode
node trimesh lamp
  parent t_a01
  shadow 0
  verts 2
    0 0 0
    0.2 0.2 0.2
endnode
node aabb walk
  parent t_a01
  verts 1
    0 0 0
endnode
endmodelgeom t_a01
newanim animloop01 t_a01
  node trimesh sill
    parent t_a01
  endnode
doneanim animloop01 t_a01
donemodel t_a01
"""


class ShadowTests(unittest.TestCase):
    def test_a_thin_trim_stops_casting_a_shadow_and_a_wall_keeps_its_own(self):
        text, names = shadows.quieted(MODEL)
        self.assertEqual(names, ['sill', 'panel', 'ledge'])  # a mesh that says nothing casts one, and is told not to
        self.assertIn('node trimesh wall\n  parent t_a01\n  shadow 1', text); self.assertIn('node trimesh sill\n  parent t_a01\n  shadow 0', text); self.assertIn('node trimesh ledge\n  shadow 0\n  parent t_a01', text)
        self.assertEqual(shadows.extent('  verts 2\n    0 0 0\n    1 2 3\n'), [3.0, 2.0, 1.0])

    def test_a_shadow_written_as_a_decimal_is_set_not_doubled(self):
        text, names = shadows.quieted(MODEL.replace('shadow 1\n  verts 3\n    0 0 0\n    2', 'shadow 1.0\n  verts 3\n    0 0 0\n    2'))
        self.assertIn('sill', names); self.assertIn('node trimesh sill\n  parent t_a01\n  shadow 0\n  verts', text)
        self.assertEqual(shadows.quieted(MODEL.replace('shadow 0', 'shadow 0.0'))[1], ['sill', 'panel', 'ledge'])  # already quiet
        crlf = shadows.quieted(MODEL.replace('\n', '\r\n'))[0]; self.assertNotRegex(crlf, r'[^\r]\n')  # a line added ends as the model's own do

    def test_a_model_another_tileset_s_edge_table_lays_is_left(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary); own = repo / 'srn_t_t'
            for folder in (own, repo / 'srn_t_common', repo / 'srn_2da'):
                folder.mkdir()
            (own / 't.set').write_text('[TILES]\nCount=1\n[TILE0]\nModel=t_a01\n', encoding='cp1252'); (own / 't_a01.mdl').write_text(MODEL, encoding='cp1252')
            (repo / 'srn_2da' / 'u_edge.2da').write_text('2da v2.0\n\n   corner1 edge corner2 height model\n0  a **** a 0 T_A01\n', encoding='cp1252')  # its words in lower case
            self.assertEqual(shadows.quiet(repo, 't', repo / 'out'), {})

    def test_quiet_changes_the_folder_s_copy_and_only_the_set_s_tiles(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary); own = repo / 'srn_t_t'; common = repo / 'srn_t_common'; out = repo / 'out'
            for folder in (own, common, out):
                folder.mkdir()
            (own / 't.set').write_text('[TILES]\nCount=1\n[TILE0]\nModel=t_a01\n', encoding='cp1252')
            (own / 't_a01.mdl').write_text(MODEL, encoding='cp1252'); (common / 't_z01.mdl').write_text(MODEL, encoding='cp1252')
            (out / 't_a01.mdl').write_text(MODEL.replace('parent t_a01\n  shadow 1\n  verts 3\n    0 0 0\n    10', 'parent t_a01\n  shadow 1\n  radius 7.0\n  verts 3\n    0 0 0\n    10'), encoding='cp1252')
            self.assertEqual(shadows.quiet(repo, 't', out), {'t_a01': 3})
            self.assertIn('radius 7.0', (out / 't_a01.mdl').read_text(encoding='cp1252')); self.assertFalse((out / 't_z01.mdl').exists())


if __name__ == '__main__':
    unittest.main()
