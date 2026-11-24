import json
import re
import tempfile
import unittest
from pathlib import Path

from tools.tilekit import retexture

REPO = Path(__file__).resolve().parents[2]
MODEL = """newmodel t_a01\r
beginmodelgeom t_a01\r
node dummy t_a01\r
  parent NULL\r
endnode\r
node trimesh floor\r
  parent t_a01\r
  ambient 1.0 1.0 1.0 \r
  diffuse 1.0 1.0 1.0\r
  selfillumcolor 0.0 0.0 0.0\r
  bitmap D_Ground03\r
endnode\r
node trimesh edge\r
  parent t_a01\r
  bitmap d_ground03b\r
endnode\r
node trimesh lamp\r
  parent t_a01\r
  ambient 1.0 0.02 0.02 \r
  Diffuse 0.7 0.0 0.0\r
  selfillumcolor 1.0 0.0 0.0 \r
  bitmap sign\r
endnode\r
node trimesh post\r
  parent t_a01\r
  ambient 0.5 0.4 0.1\r
  diffuse 0.5 0.4 0.1\r
  selfillumcolor 0.0 0.0 0.0\r
  bitmap sign\r
endnode\r
node aabb walk\r
  parent t_a01\r
  bitmap d_ground03\r
  verts 1\r
    0 0 0\r
endnode\r
endmodelgeom t_a01\r
newanim animloop01 t_a01\r
  node trimesh lamp\r
    parent t_a01\r
    selfillumcolor 1.0 0.0 0.0\r
  endnode\r
doneanim animloop01 t_a01\r
donemodel t_a01\r
"""
SET = "[GENERAL]\nName=t\n[TILES]\nCount=1\n[TILE0]\nModel=t_a01\n"


class Retexture(unittest.TestCase):
    def test_a_mesh_draws_the_copy_and_a_texture_of_a_longer_name_is_left(self):
        text, used = retexture.renamed(MODEL, {'d_ground03': 'fcx_ground03'})
        self.assertEqual(used, {'d_ground03': 'fcx_ground03'})
        self.assertEqual(len(re.findall(r'bitmap fcx_ground03\r', text)), 1)  # the floor
        self.assertIn('node aabb walk\r\n  parent t_a01\r\n  bitmap d_ground03\r', text)  # the walkmesh is left
        self.assertIn('bitmap d_ground03b\r', text)
        self.assertEqual(retexture.renamed(text, {'d_ground03': 'fcx_ground03'}), (text, {}))

    def test_a_coloured_mesh_turns_white_and_glows_white_only_where_it_glowed(self):
        text, meshes = retexture.whitened(MODEL, ['SIGN'])
        self.assertEqual(meshes, ['lamp', 'post'])
        lamp = text[text.index('node trimesh lamp'):text.index('node trimesh post')]; post = text[text.index('node trimesh post'):text.index('node aabb')]
        self.assertEqual(re.findall(r'(?i)(?:ambient|diffuse|selfillumcolor) ([^\r]*)\r', lamp), ['1.0 1.0 1.0 ', '1.0 1.0 1.0', '1.0 1.0 1.0 '])
        self.assertEqual(re.findall(r'(?i)(?:ambient|diffuse|selfillumcolor) ([^\r]*)\r', post), ['1.0 1.0 1.0', '1.0 1.0 1.0', '0.0 0.0 0.0'])
        self.assertIn('    selfillumcolor 1.0 0.0 0.0\r', text)  # an animation is left as it is
        self.assertIn('  ambient 1.0 1.0 1.0 \r\n  diffuse 1.0 1.0 1.0\r\n  selfillumcolor 0.0 0.0 0.0\r\n  bitmap D_Ground03', text)  # another texture's mesh too
        self.assertEqual(retexture.whitened(text, ['sign']), (text, []))
        with self.assertRaisesRegex(ValueError, 'lamp'):  # a glow that is no colour is refused by its mesh's name
            retexture.whitened(MODEL.replace('selfillumcolor 1.0 0.0 0.0 \r', 'selfillumcolor 1.0 red 0.0 \r'), ['sign'])

    def test_a_list_names_textures_a_model_can_carry(self):
        with self.assertRaises(ValueError):
            retexture.checked({'copies': {'d_ground03': 'a_name_longer_than_a_resref'}})
        with self.assertRaises(ValueError):
            retexture.checked({'copies': {'a': 'c', 'b': 'C'}})
        with self.assertRaises(ValueError):
            retexture.checked({})

    def test_write_changes_the_set_s_own_tiles_and_leaves_shared_ones(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            for pack, name in (('srn_t_t', 't'), ('srn_t_u', 'u')):
                (repo / pack).mkdir(); (repo / pack / f'{name}.set').write_text(SET, encoding='cp1252')
            (repo / 'srn_t_common').mkdir(); (repo / 'srn_t_common' / 't_a01.mdl').write_bytes(MODEL.encode('cp1252'))
            spec = {'copies': {'d_ground03': 'fcx_ground03'}, 'white': ['sign']}
            self.assertEqual(retexture.write(repo, 't', spec, repo / 'out'), {'t_a01': 'shared with u'})
            self.assertFalse((repo / 'out' / 't_a01.mdl').exists())
            told = retexture.write(repo, 't', spec, repo / 'out', shared=['U'])
            self.assertEqual(told, {'t_a01': {'copies': {'d_ground03': 'fcx_ground03'}, 'white': ['lamp', 'post']}})
            self.assertIn(b'bitmap fcx_ground03\r', (repo / 'out' / 't_a01.mdl').read_bytes())
            self.assertEqual(retexture.write(repo, 't', spec, repo / 'out', shared=['u']), {})  # the copy in the folder is the one read
            with self.assertRaisesRegex(ValueError, "u's, not t's"):  # another tileset's list
                retexture.write(repo, 't', {**spec, 'tileset': 'u'}, repo / 'other', shared=['u'])
            both = {'tileset': 'T', 'copies': {'sign': 'fcx_sign'}, 'white': ['sign']}  # copied and whitened: found under its copy's name
            self.assertEqual(retexture.write(repo, 't', both, repo / 'both', shared=['u']), {'t_a01': {'copies': {'sign': 'fcx_sign'}, 'white': ['lamp', 'post']}})

    def test_the_futuristic_city_s_list_fits_its_materials_and_tiles(self):
        spec = json.loads((REPO / 'docs' / 'tilesets' / 'fcx01' / 'retexture.json').read_text(encoding='utf-8'))
        copies, white = retexture.checked(spec)
        materials = json.loads((REPO / 'docs' / 'tilesets' / 'fcx01' / 'materials.json').read_text(encoding='utf-8'))['textures']
        for old, new in copies.items():  # a copy is made by the material spec, from the texture it stands in for
            self.assertEqual(materials.get(new, {}).get('copy'), old, new)
            self.assertNotIn(old, materials, f'{old} would be restyled for every tileset that draws it')
        drawn = set()
        for pack in ('srn_t_fcx01', 'sources/srn_t_fcx01'):
            for model in (REPO / pack).glob('*.mdl'):
                data = model.read_bytes()
                if not data.startswith(b'\0'):
                    drawn |= {one.lower() for one in re.findall(r'(?im)^[ \t]*(?:bitmap|texture0)[ \t]+(\S+)', data.decode('cp1252'))}
        # before the list is applied the tiles draw the shared textures, afterwards their copies
        self.assertEqual(spec['tileset'], 'fcx01')
        for old, new in copies.items():
            self.assertTrue(old.lower() in drawn or new.lower() in drawn, old)
            if new.lower() in drawn:  # applied: no tile of the set is left on the shared texture, among the others on the copy
                self.assertNotIn(old.lower(), drawn, f'a Futuristic City tile still draws {old}')
        self.assertEqual(sorted(one for one in white if one.lower() not in drawn), [])


if __name__ == '__main__':
    unittest.main()
