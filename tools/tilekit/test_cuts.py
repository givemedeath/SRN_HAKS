"""A walkmesh written back into its model or .wok."""
import unittest
from types import SimpleNamespace

from tools.tilekit import cuts

WOK = """beginwalkmeshgeom t
node aabb walk
  parent t
  position 0 0 0
  orientation 0 0 0 0
  verts 3
    0 0 0
    1 0 0
    0 1 0
  faces 1
    0 1 2  1  0 1 2  4
  tverts 3
    0.25 0.5 0
    -0.75 .5 0
    1 1 0
  aabb 0 0 0 1 1 0 -1
    0 0 0 1 1 0 0
endnode
endwalkmeshgeom t
"""


class Rewritten(unittest.TestCase):
    walk = SimpleNamespace(verts=[(0, 0, 0), (2, 0, 0), (0, 2, 0)], faces=[(0, 1, 2, 1, 0, 1, 2, 4)])

    def test_the_texture_corners_stay_and_the_mesh_is_the_new_one(self):
        for text in (WOK, WOK.replace('\n', '\r\n')):
            new = cuts.rewritten(text, self.walk); lines = [line.strip() for line in new.splitlines()]
            self.assertEqual(lines[lines.index('tverts 3') + 1:][:3], ['0.25 0.5 0', '-0.75 .5 0', '1 1 0'])
            self.assertEqual([sum(line.startswith(word) for line in lines) for word in ('verts', 'faces', 'tverts', 'aabb')], [1, 1, 1, 1])
            self.assertEqual(new.count('\r\n'), new.count('\n') if '\r' in text else 0)
            node = cuts._walk_node(new)
            self.assertEqual((node.verts, node.faces, len(node.tverts)), (self.walk.verts, self.walk.faces, 3))
            self.assertEqual(lines[-2:], ['endnode', 'endwalkmeshgeom t'])

    def test_writing_twice_changes_nothing_more(self):
        once = cuts.rewritten(WOK, self.walk)
        self.assertEqual(cuts.rewritten(once, self.walk), once)


if __name__ == '__main__':
    unittest.main()
