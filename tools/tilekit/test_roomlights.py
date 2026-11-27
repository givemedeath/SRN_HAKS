"""A room's lit fittings are parked under the tile with an unlit copy in their place, and the third loop lifts them home."""
import re
import tempfile
import unittest
from pathlib import Path

from tools.tilekit import daylight, inventory, roomlights
from tools.tilekit.test_strip import box, room

LAMP = ('bitmap lamp', 'selfillumcolor 1 1 1')
PANEL = ('bitmap panel', 'selfillumcolor 0 0 0')  # a ceiling lit by its material's glow map alone


def lit_room():
    return room(extra=(box('lamp1', -0.5, 0.5, -0.5, 0.5, 2.9, 2.95, LAMP), box('panel', -2, 2, -2, 2, 2.99, 2.99, PANEL)))


def place(text, node):
    rest = roomlights._rests(text)[node.lower()]
    return rest[2]


class Switching(unittest.TestCase):
    def test_a_lit_mesh_rests_parked_its_unlit_copy_in_place_and_the_third_loop_swaps_them(self):
        made, count = roomlights.switch(lit_room(), {'lamp': None}); self.assertEqual(count, 1)
        self.assertEqual(place(made, 'lamp1'), (0.0, 0.0, -roomlights.PARK))
        self.assertEqual(place(made, 'lamp1_off'), (0.0, 0.0, 0.0))
        off = roomlights._block(made, 'lamp1_off').group(0)
        self.assertEqual(daylight._field(off, 'selfillumcolor'), '0 0 0'); self.assertEqual(daylight._field(off, 'bitmap'), 'lamp')
        self.assertEqual(roomlights._moved(made), {'lamp1': (0.0, 0.0, 0.0), 'lamp1_off': (0.0, 0.0, -roomlights.PARK)})
        self.assertEqual(roomlights._rests(made)['lamp1'][1], 'tsta')  # under the animated node, where a tile's animations play
        self.assertEqual(inventory.walk_hash(made), inventory.walk_hash(lit_room()))

    def test_a_ceiling_lit_by_its_glow_map_gets_a_copy_drawn_with_a_material_without_it(self):
        made, count = roomlights.switch(lit_room(), {'panel': 'panelx'}, mapped=('panel',)); self.assertEqual(count, 1)
        self.assertEqual(daylight._field(roomlights._block(made, 'panel_off').group(0), 'bitmap'), 'panelx')

    def test_a_model_is_switched_once_and_unswitched_to_what_it_was(self):
        once, _ = roomlights.switch(lit_room(), {'lamp': None})
        self.assertEqual(roomlights.switch(once, {'lamp': None}), (once, 0))
        twice, count = roomlights.switch(once, {'lamp': None, 'panel': 'panelx'}, mapped=('panel',)); self.assertEqual(count, 1)
        self.assertEqual(set(roomlights._moved(twice)), {'lamp1', 'lamp1_off', 'panel', 'panel_off'})
        back = roomlights.unswitch(twice)
        self.assertFalse(roomlights.switched(back)); self.assertNotIn('newanim animloop03', back)
        self.assertEqual(place(back, 'lamp1'), (0.0, 0.0, 0.0)); self.assertNotIn('lamp1_off', roomlights._rests(back))

    def test_a_loop_that_moves_something_else_is_refused_and_one_that_moves_nothing_is_dropped(self):
        def looped(key):
            return lit_room().replace('donemodel tst', '\n'.join(['newanim animloop03 tst', '  length 0.03333', '  animroot tst', '  node dummy tst', '    parent NULL', '  endnode',
                                                                   '  node trimesh rug', '    parent tst', '    positionkey 1', f'      0.0 {key}', '    endlist', '  endnode', 'doneanim animloop03 tst', 'donemodel tst']))
        with self.assertRaisesRegex(ValueError, 'moves rug'):
            roomlights.switch(looped('0 0 5'), {'lamp': None})
        made, count = roomlights.switch(looped('0 0 0'), {'lamp': None})
        self.assertEqual(count, 1); self.assertEqual(len(re.findall(r'(?m)^newanim animloop03', made)), 1)

    def test_the_set_turns_the_third_loop_on_for_switched_tiles(self):
        made, _ = roomlights.switch(lit_room(), {'lamp': None})
        with tempfile.TemporaryDirectory() as work:
            path = Path(work) / 'tst.set'
            path.write_bytes(b'[TILE0]\r\nModel=tst\r\nAnimLoop3=0\r\n[TILE1]\r\nModel=plain\r\nAnimLoop3=0\r\n')
            self.assertEqual(roomlights.loops_on(path, lambda name: made if name == 'tst' else room()), ['tst'])
            self.assertEqual(path.read_bytes(), b'[TILE0]\r\nModel=tst\r\nAnimLoop3=1\r\n[TILE1]\r\nModel=plain\r\nAnimLoop3=0\r\n')


if __name__ == '__main__':
    unittest.main()
