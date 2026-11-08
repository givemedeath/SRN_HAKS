import math
import re
import unittest

from tools.itemkit import anim_chain_probe as probe


class AddCustomClip(unittest.TestCase):
    STOCK = ('newmodel a_ba_custom\nnewanim custom6lp a_ba_custom\n'
             '  node dummy a_ba_custom\n    parent NULL\n  endnode\n'
             '  node dummy rootdummy\n    parent a_ba_custom\n  endnode\n'
             '  node trimesh torso_g\n    parent rootdummy\n  endnode\n'
             '  node trimesh rbicep_g\n    parent torso_g\n  endnode\n'
             'doneanim custom6lp a_ba_custom\ndonemodel a_ba_custom\n')

    def test_keeps_every_stock_line_and_adds_the_clip_last(self):
        text = probe.add_custom_clip(self.STOCK)
        self.assertLess(text.index('doneanim custom6lp'), text.index('newanim srpcust'))
        self.assertTrue(text.endswith('doneanim srpcust a_ba_custom\ndonemodel a_ba_custom\n'))
        self.assertEqual([line for line in self.STOCK.splitlines() if line not in text.splitlines()], [])

    def test_every_parent_is_in_the_clip(self):
        clip = probe.add_custom_clip(self.STOCK).split('newanim srpcust')[1]
        names = set(re.findall(r'node \w+ (\S+)', clip))
        self.assertEqual(set(re.findall(r'parent (\S+)', clip)) - names, {'NULL'})

    def test_refuses_a_second_insertion(self):
        with self.assertRaises(ValueError):
            probe.add_custom_clip(probe.add_custom_clip(self.STOCK))


class ArmRotation(unittest.TestCase):
    def test_each_hanging_arm_rises_on_its_own_side(self):
        for right, side in ((True, 1), (False, -1)):
            _, y, _, w = probe.arm_quaternion(right)
            angle = 2 * math.atan2(y, w)  # a rotation about +Y carries (0, 0, -1) here
            self.assertGreater(-math.cos(angle), .5)
            self.assertGreater(-math.sin(angle) * side, .3)


if __name__ == '__main__':
    unittest.main()
