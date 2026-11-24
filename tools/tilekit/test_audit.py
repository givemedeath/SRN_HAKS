import tempfile
import unittest
from pathlib import Path

from tools.tilekit import audit
from tools.tilekit.test_detail import PIECE
from tools.tilekit.test_family_review import tile
from tools.tilekit.test_openings import model, wall

BOX = [wall('a', 'brick', 'x', 2, -2, 2, 3, 20), wall('b', 'brick', 'y', 2, -2, 2, 3, 20)]
ODD = 'node trimesh odd\n  parent t\n  bitmap brick\n  verts 3\n    -3 -3 5\n    3 -3 5\n    0 3 12\n  faces 1\n    0 1 2 1 0 0 0 1\nendnode\n'


class AuditTest(unittest.TestCase):
    def setUp(self):
        held = tempfile.TemporaryDirectory(); self.addCleanup(held.cleanup); self.repo = Path(held.name); self.pack = self.repo / 'srn_t_x'; self.pack.mkdir(); (self.repo / 'srn_2da').mkdir()
        (self.pack / 'x.set').write_text('[GENERAL]\nDefault=Ground\n[TERRAIN0]\nName=Ground\n[TERRAIN1]\nName=Water\n' + tile(0, 'x_box', ['Ground', 'Tower', 'Tower', 'Tower']) + tile(1, 'x_odd', ['Tower'] * 4)
                                         + tile(2, 'x_low', ['Tower'] * 4) + tile(3, 'x_wet', ['Water', 'Ground', 'Ground', 'Ground']))
        for name, nodes in (('x_box', BOX), ('x_odd', [ODD]), ('x_low', [wall('a', 'brick', 'x', 0, -1, 1, 0, 3)]), ('x_wet', BOX)):
            (self.pack / f'{name}.mdl').write_text(model(*nodes))

    def test_the_plainest_first(self):
        rows = audit.rank(self.repo, 'X', ['water'])
        self.assertEqual([row['tile'] for row in rows], ['x_box', 'x_odd']); self.assertEqual((rows[0]['family'], rows[0]['boxy'], rows[1]['boxy']), ('Tower', 1.0, 0.0))
        with self.assertRaisesRegex(ValueError, 'lava'):
            audit.rank(self.repo, 'x', ['lava'])

    def test_who_else_draws_a_texture(self):
        other = self.repo / 'srn_t_y'; other.mkdir(); (other / 'y.set').write_text(tile(0, 'y_a', ['G'] * 4)); (other / 'y_a.mdl').write_text('bitmap BRICK\n'); (other / 'loose.mdl').write_text('bitmap brick\n')
        (other / 'none.mdl').write_text('bitmap bricks\n'); kept = self.repo / 'sources' / 'srn_t_y'; kept.mkdir(parents=True); (kept / 'loose.mdl').write_text('bitmap stone\n')
        self.assertEqual(audit.shared(self.repo, 'x', ['Brick', 'stone']), {'srn_t_y': {'loose': ['stone']}, 'y': {'y_a': ['brick']}})

    def test_a_piece_set_into_the_tiles_own(self):
        kit = self.repo / 'kit'; kit.mkdir(); (kit / 'box.mdl').write_text(PIECE)
        spec = {'tileset': 'x', 'tiles': {'x_box': [{'piece': 'box', 'at': [1.5, 2.0, 5], 'turn': 0}, {'piece': 'box', 'at': [-3, -4.0, 5], 'turn': 180}]}}
        found = audit.placements(self.repo, spec, kit)
        self.assertEqual([(one['tile'], one['number']) for one in found], [])  # fixed to the wall: nothing proud of it
        spec['tiles']['x_box'][0]['at'] = [1.5, 1.65, 5]  # a third of a metre behind what the tile draws
        self.assertEqual([(one['tile'], one['number'], one['piece']) for one in audit.placements(self.repo, spec, kit)], [('x_box', 0, 'box')])
        with self.assertRaisesRegex(ValueError, 'gone'):
            audit.placements(self.repo, {'tileset': 'x', 'tiles': {'gone': []}}, kit)


if __name__ == '__main__':
    unittest.main()
