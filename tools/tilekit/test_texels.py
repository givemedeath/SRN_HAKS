import json
import unittest
from pathlib import Path
from unittest import mock

from . import texels

ROOT = Path(__file__).resolve().parents[2]
TEXT = """newmodel t
setsupermodel t null
beginmodelgeom t
node dummy t
  parent null
endnode
node trimesh slab
  parent t
  bitmap {picture}
  verts 4
    0 0 0
    2 0 0
    2 2 0
    0 2 0
  tverts 4
    0 0 0
    1 0 0
    1 1 0
    0 1 0
  faces 2
    0 1 2 1 0 1 2 0
    0 2 3 1 0 2 3 0
endnode
endmodelgeom t
donemodel t
"""


class TexelsTest(unittest.TestCase):
    def test_pixels_a_metre_by_drawn_area(self):
        told = texels.measure({'t': TEXT.format(picture='small')}, {'small': (128, 128)})
        self.assertAlmostEqual(told['small']['density'], 64)
        self.assertAlmostEqual(told['small']['area'], 4)
        self.assertEqual(told['small']['models'], ['t'])
        self.assertEqual(texels.measure({'t': TEXT.format(picture='other')}, {'small': (128, 128)}), {})

    def test_a_switched_light_s_unlit_copy_is_not_counted_twice(self):
        # the off copy of a lit fitting doubled lrk_lite06's area past SCRAP (CI of PR 209, 2026-11-28)
        body = TEXT.split('node trimesh slab', 1)[1].split('endmodelgeom', 1)[0]
        twice = TEXT.replace('endmodelgeom', 'node trimesh slab_off' + body + 'endmodelgeom', 1).format(picture='small')
        self.assertAlmostEqual(texels.measure({'t': twice}, {'small': (128, 128)})['small']['area'], 4)
        other = twice.replace('slab_off', 'shelf_off')
        self.assertAlmostEqual(texels.measure({'t': other}, {'small': (128, 128)})['small']['area'], 8)

    def test_a_weak_picture_is_small_coarse_and_not_one_colour(self):
        files = {name: name for name in 'abcd'}
        measured = {name: {'density': density, 'area': area} for name, density, area in (('a', 90, 5), ('b', 90, 1), ('c', 90, 5), ('d', 90, 5))}
        sizes = lambda side: {'a': (side, side), 'b': (side, side), 'c': (1024, 1024), 'd': (side, side)}
        with mock.patch.object(texels, 'plain', lambda path: path == 'd'):
            self.assertEqual(texels.weak(measured, sizes(256), files), ['a'])
            measured['a']['density'] = 300
            self.assertEqual(texels.weak(measured, sizes(256), files), [])
            self.assertEqual(texels.weak(measured, sizes(64), files), ['a'])

    @unittest.skipUnless((ROOT / 'sources' / 'srn_t_srx02').is_dir(), 'the sources are not checked out')
    def test_the_rooms_draw_no_weak_picture_but_those_left(self):
        left = json.loads((ROOT / 'docs' / 'placeables' / 'materials.json').read_text(encoding='utf-8'))['left']
        self.assertEqual([name for name in texels.weak(*texels.of_rooms(ROOT)) if name not in left], [],
                         'redraw or enlarge these (docs/placeables/materials.json), or say why one is left')


if __name__ == '__main__':
    unittest.main()
