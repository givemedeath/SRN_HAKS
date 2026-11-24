"""Nodes with spaced or shared names each take a name of their own, and parents and animations keep their meaning."""
import unittest

from tools.tilekit import unique

MODEL = """newmodel t_a01
beginmodelgeom t_a01
node dummy t_a01
  parent NULL
endnode
node trimesh bridge rail
  parent t_a01
endnode
node trimesh bridge deck
  parent t_a01
endnode
node trimesh post
  parent bridge deck
endnode
node trimesh zip
  parent t_a01
endnode
node trimesh zip
  parent bridge
endnode
node trimesh wall
  parent t_a01
endnode
endmodelgeom t_a01
newanim loop t_a01
  node dummy t_a01
    parent NULL
  endnode
  node trimesh bridge rail
    parent t_a01
  endnode
  node trimesh bridge deck
    parent t_a01
  endnode
  node trimesh zip
    parent t_a01
  endnode
  node trimesh zip
    parent bridge
  endnode
doneanim loop t_a01
donemodel t_a01
"""


class Unique(unittest.TestCase):
    def test_each_node_takes_its_own_name_and_references_keep_their_meaning(self):
        made, count = unique.unique(MODEL); geometry, loop = made.split('newanim')
        self.assertEqual(count, 4)
        for part in (geometry, loop):
            self.assertEqual([line.split()[2] for line in part.splitlines() if line.strip().startswith('node trimesh') and line.split()[2] != 'post' and line.split()[2] != 'wall'],
                             ['bridge_rail', 'bridge_deck', 'zip', 'zip_2'])
        self.assertIn('node trimesh post\n  parent bridge_rail\n', made)  # `bridge deck` was read as bridge: the first of them
        self.assertIn('node trimesh zip_2\n  parent bridge_rail\n', geometry)
        self.assertIn('node trimesh wall\n  parent t_a01\n', made)
        self.assertEqual(unique.unique(made), (made, 0))

    def test_a_model_of_plain_names_is_left_and_line_ends_are_kept(self):
        plain = MODEL.replace('bridge rail', 'rail').replace('bridge deck', 'deck').replace('parent bridge', 'parent rail').replace('node trimesh zip\n  parent rail', 'node trimesh zap\n  parent rail').replace('node trimesh zip\n    parent rail', 'node trimesh zap\n    parent rail')
        self.assertEqual(unique.unique(plain), (plain, 0))
        made = unique.unique(MODEL.replace('\n', '\r\n'))[0]
        self.assertNotIn('\n', made.replace('\r\n', ''))

    def test_a_long_name_is_cut_and_a_new_name_avoids_one_in_use(self):
        text = MODEL.replace('bridge rail', 'bridge ' + 'x' * 40).replace('node trimesh wall', 'node trimesh bridge_deck')
        made = unique.unique(text)[0]
        names = [line.split()[2] for line in made.split('newanim')[0].splitlines() if line.startswith('node ')]
        self.assertEqual(len(names), len({name.lower() for name in names}))
        self.assertTrue(all(len(name) <= unique.LONGEST for name in names))


if __name__ == '__main__':
    unittest.main()
