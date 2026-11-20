import json
import tempfile
import unittest
from pathlib import Path

from tools.tilekit import doors

DOOR = """newmodel {name}
beginmodelgeom {name}
node dummy {name}
  parent NULL
endnode
node trimesh leaf
  parent {name}
  bitmap door_tex
  verts 3
    0 0 0
    1 0 0
    0 0 2
  faces 1
    0 1 2 1 0 0 0 1
endnode
endmodelgeom {name}
donemodel {name}
"""
DOORTYPES = '2DA V2.0\n\n     Label Model TileSet TemplateResRef\n0    Generic **** **** ****\n1    "Shop Door" T_DOOR01 TST01 nw_door\n'
GENERIC = '2DA V2.0\n\n     Label StrRef ModelName BlockSight\n0    Wood 5349 T_DOOR01 1\n1    "Iron Gate" 5349 T_GDOOR02 1\n'
SET = '[GENERAL]\nName=t\n[TILE0]\nModel=t_a01\n[TILE0DOOR0]\nType=1\nX=0\n[TILE0DOOR1]\nType=0\n'


class Doors(unittest.TestCase):
    def test_each_model_is_listed_with_its_rows_its_hooks_and_its_cost(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            for folder in ('srn_door', 'srn_2da', 'srn_t_tst01'):
                (repo / folder).mkdir()
            (repo / 'srn_door' / 't_door01.mdl').write_text(DOOR.format(name='t_door01'), encoding='cp1252')
            (repo / 'srn_door' / 't_door01.dwk').write_text('', encoding='cp1252')
            (repo / 'srn_door' / 't_gdoor02.mdl').write_bytes(b'\0\0\0\0compiled')
            (repo / 'srn_door' / 't_door03.mdl').write_text(DOOR.format(name='t_door03'), encoding='cp1252')
            (repo / 'srn_2da' / 'doortypes.2da').write_text(DOORTYPES, encoding='cp1252')
            (repo / 'srn_2da' / 'genericdoors.2da').write_text(GENERIC, encoding='cp1252')
            (repo / 'srn_t_tst01' / 'tst01.set').write_text(SET, encoding='cp1252')
            found = {door['model']: door for door in doors.doors(repo)}
            self.assertEqual(found['t_door01']['doortypes'], [{'row': 1, 'label': 'Shop Door', 'tileset': 'tst01'}])
            self.assertEqual(found['t_door01']['genericdoors'], [{'row': 0, 'label': 'Wood'}])
            self.assertEqual(found['t_door01']['tileHooks'], {'tst01': 1})  # row 0 is the generic hook, not this model
            self.assertEqual((found['t_door01']['faces'], found['t_door01']['nodes'], found['t_door01']['textures']), (1, 1, ['door_tex']))
            self.assertTrue(found['t_door01']['walkmesh'])
            self.assertEqual((found['t_gdoor02']['form'], found['t_gdoor02']['kind']), ('compiled', 'gate'))
            self.assertEqual((found['t_door03']['doortypes'], found['t_door03']['genericdoors']), ([], []))  # used by nothing
            written = doors.write(repo / 'out', list(found.values()))
            self.assertEqual(len(json.loads(Path(written[0]).read_text(encoding='utf-8'))['doors']), 3)
            self.assertIn('t_door01,t_door,door,ascii,1,1,door_tex,1,0,tst01:1', Path(written[1]).read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
