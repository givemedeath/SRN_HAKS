"""A tile open to the sky over its floor is given a ceiling at its walls' top, high enough over any floor walked."""
import unittest

from tools.tilekit import ceilings, geometry, inventory
from tools.tilekit.test_strip import box, room

PACKS = ('srn_t_tfb01',)  # what this reads: named so the test selector runs it when one changes


def open_room(floor=0.0):
    """The strip tests' room without the lid on its walls: open to the sky, as Modern Interior was drawn."""
    return room(floor=floor).replace('\n'.join(box('lid', -5, 5, -5, 5, 3, 3, ('bitmap black',))) + '\n', '')


class Capping(unittest.TestCase):
    def test_an_open_room_gets_a_ceiling_at_its_walls_top_and_keeps_its_walkmesh(self):
        text = open_room(); self.assertNotEqual(text, room())
        made, high = ceilings.capped(text, 'tst', 'plaster')
        self.assertEqual(high, 3.0)
        _, _, nodes = geometry.parse(made); ceiling = [node for node in nodes if node.name == 'tst_ceil']
        self.assertEqual(len(ceiling), 1); self.assertEqual({round(point[2], 3) for point in ceiling[0].verts}, {3.0})
        self.assertIn('bitmap plaster', ceiling[0].look)
        self.assertEqual(inventory.walk_hash(made), inventory.walk_hash(text))

    def test_a_room_with_its_lid_is_left_alone(self):
        self.assertEqual(ceilings.capped(room(), 'tst', 'plaster'), (None, 'ceiled already'))

    def test_a_floor_walked_a_storey_up_takes_its_ceiling_a_storey_over_it(self):
        made, high = ceilings.capped(open_room(floor=3.0), 'tst', 'plaster')  # its walls stop at the floor: no top clear of it
        self.assertEqual(high, 6.0); self.assertGreaterEqual(high - 3.0, ceilings.CLEAR)


if __name__ == '__main__':
    unittest.main()
