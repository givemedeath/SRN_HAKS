"""Longitudinal ownership follows the bone axis, not projection/radial size."""
import unittest
import numpy as np
from measure_target_upperarm_ownership import axial_measure
from place_purposebuilt_pelvis import rotation_xyz


class UpperarmOwnershipTests(unittest.TestCase):
    def test_radial_bulge_does_not_change_axial_envelope(self):
        corners=np.array([[[0,0,-.08],[.10,0,.20],[0,0,.34]]])
        result,_,_=axial_measure(corners,[0,0,0],[0,0,.30])
        self.assertAlmostEqual(result['proximalEnvelopeBeyondShoulderMetres'],.08)
        self.assertAlmostEqual(result['distalEnvelopeBeyondElbowMetres'],.04)
        changed=corners.copy();changed[0,1,0]=.20
        larger,_,_=axial_measure(changed,[0,0,0],[0,0,.30])
        self.assertEqual(result['distalEnvelopeBeyondElbowMetres'],larger['distalEnvelopeBeyondElbowMetres'])
        self.assertGreater(larger['maximumRadialDistanceMetres'],result['maximumRadialDistanceMetres'])

    def test_pose_rotation_and_translation_preserve_correct_frame_ownership(self):
        points=np.array([[[0,0,-.08],[.10,.04,.20],[0,0,.308]]]);rotation=rotation_xyz([73,-21,37]);translation=np.array([.2,-.1,1.5])
        initial,_,_=axial_measure(points,[0,0,0],[0,0,.3])
        moved,_,_=axial_measure(points@rotation.T+translation,translation,np.array([0,0,.3])@rotation.T+translation)
        for key in ('boneLengthMetres','proximalEnvelopeBeyondShoulderMetres','distalEnvelopeBeyondElbowMetres','maximumRadialDistanceMetres'):
            self.assertAlmostEqual(initial[key],moved[key],places=12)


if __name__=='__main__':unittest.main()
