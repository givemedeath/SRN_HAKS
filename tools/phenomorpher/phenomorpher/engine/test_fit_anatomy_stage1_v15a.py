"""The guide objective must distinguish useful feasible character changes."""
import unittest
from .fit_anatomy_stage1_v15a import centered_length_loss

def goal(preferred=.2,uncertainty=.13,weight=.35,available=True):
    return {'preferredMeters':preferred,'measurementUncertaintyMeters':uncertainty,'designSlackFraction':.05,'weight':weight,'available':available}

class CenteredGuideTests(unittest.TestCase):
    def test_large_uncertainty_does_not_erase_character_gradient(self):
        row=goal(.22282930846850063,.09360902422994005)
        source=centered_length_loss(.2896311981483256,row)
        modest=centered_length_loss(.2751496382409093,row)
        self.assertGreater(source,modest)
        self.assertGreater(modest,0)
        self.assertEqual(centered_length_loss(row['preferredMeters'],row),0)

    def test_inside_design_range_still_has_gradient(self):
        self.assertGreater(centered_length_loss(.204,goal()),centered_length_loss(.202,goal()))

    def test_uncertainty_remains_reported_not_added_as_band(self):
        self.assertEqual(centered_length_loss(.21,goal(uncertainty=.01)),centered_length_loss(.21,goal(uncertainty=.15)))
        self.assertLess(centered_length_loss(.21,goal(weight=.1)),centered_length_loss(.21,goal(weight=.7)))

    def test_huber_tail_symmetric_linear_not_squared(self):
        row=goal();self.assertAlmostEqual(centered_length_loss(.23,row),centered_length_loss(.17,row))
        self.assertAlmostEqual(centered_length_loss(.24,row)-centered_length_loss(.23,row),centered_length_loss(.23,row)-centered_length_loss(.22,row))

    def test_unavailable_anatomy_contributes_no_invented_preference(self):
        self.assertEqual(centered_length_loss(.3,goal(available=False)),0)

if __name__=='__main__':unittest.main()
