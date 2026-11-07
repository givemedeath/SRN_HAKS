import re
import unittest

from tools.itemkit import firearm_fx_pilot as fx

GUN = '''newmodel wbwsl_b_051
setsupermodel wbwsl_b_051 NULL
setanimationscale 1

beginmodelgeom wbwsl_b_051
node dummy wbwsl_b_051
  parent NULL
endnode
node trimesh wbwsl_b_051v
  parent wbwsl_b_051
  verts 3
    0.0 0.1 -0.3
    0.0 0.2 -0.3
    0.0 0.5 0.1
endnode
endmodelgeom wbwsl_b_051

donemodel wbwsl_b_051
'''


class TaggedGun(unittest.TestCase):
    def test_muzzle_is_the_barrel_tip(self):
        self.assertEqual(fx.muzzle(GUN).round(3).tolist(), [0., .15, -.3])

    def test_each_build_has_one_burst_on_one_set_of_names(self):
        for names, emitter, other, count in (('stock', 'srp_red', 'srp_green', 2), ('replaced', 'srp_green', 'srp_red', 15)):
            text = fx.tagged_gun(GUN, 'fire_pst', names)
            clips = re.findall(r'(?ms)^newanim (\S+) wbwsl_b_051\n(.*?)^doneanim', text)
            self.assertEqual(len(clips), count)
            self.assertNotIn(other, text)
            for _, body in clips:
                self.assertIn('event 0.1 detonate', body)
                self.assertIn(emitter, body)

    def test_replaced_names_cover_every_slot(self):
        text = fx.tagged_gun(GUN, 'fire_pst', 'replaced')
        self.assertIn('newanim fire_pst_tfl wbwsl_b_051', text)
        self.assertNotIn('newanim throwr', text)

    def test_clips_sit_after_the_geometry_and_inside_the_model(self):
        text = fx.tagged_gun(GUN, 'fire_pst', 'stock')
        self.assertLess(text.index('endmodelgeom'), text.index('newanim'))
        self.assertLess(text.rindex('doneanim'), text.index('donemodel'))
        self.assertLess(text.index('node emitter srp_marker'), text.index('endmodelgeom'))
        self.assertIn('classification Character', text)

    def test_a_gun_with_clips_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'Unexpected gun shape'):
            fx.tagged_gun(GUN.replace('donemodel', 'newanim old wbwsl_b_051\ndoneanim old wbwsl_b_051\ndonemodel'), 'fire_pst', 'stock')


if __name__ == '__main__':
    unittest.main()
