import unittest
import numpy as np
from .reduction import validate


class ContourValidationTests(unittest.TestCase):
    def setUp(self):
        self.p=np.array([[-.02,-.1,-.02],[.02,-.1,-.02],[0,-.1,.02],[0,.1,0]])
        self.f=np.array([[0,2,1],[0,1,3],[1,2,3],[2,0,3]])
        vol=np.einsum('ij,ij->i',self.p[self.f[:,0]],np.cross(self.p[self.f[:,1]],self.p[self.f[:,2]])).sum()
        if vol<0:self.f=self.f[:,[0,2,1]]
    def test_closed_exact_contour_is_valid(self):
        self.assertTrue(validate(self.p,self.f,self.p.copy(),self.f,4,[-.1,.1])['closedWound'])
    def test_closed_mesh_with_shifted_rim_is_rejected(self):
        changed=self.p.copy();changed[0,0]+=.001
        with self.assertRaisesRegex(ValueError,'mating contour'):validate(self.p,self.f,changed,self.f,4,[-.1,.1])
    def test_open_or_overbudget_candidate_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'closed'):validate(self.p,self.f,self.p,self.f[:3],4,[-.1,.1])
        with self.assertRaisesRegex(ValueError,'budget'):validate(self.p,self.f,self.p,self.f,3,[-.1,.1])
    def test_candidate_leaving_the_source_surface_is_rejected(self):
        changed=self.p.copy();changed[3,0]+=.01
        with self.assertRaisesRegex(ValueError,'source surface'):validate(self.p,self.f,changed,self.f,4,[-.1,.2])
