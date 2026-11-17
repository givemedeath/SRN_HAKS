import unittest
import numpy as np
from .reduction import policy,reduce,validate


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
        with self.assertRaisesRegex(ValueError,'source surface'):
            validate(self.p,self.f,self.p,self.f,4,[-.1,.1],lambda points:np.full(len(points),.004))


class WholePartTests(unittest.TestCase):
    def test_one_piece_policy_is_its_own_and_composite_hashes_are_unchanged(self):
        from tools.headkit.common import digest
        self.assertEqual(policy(100,[-.1,.1]),digest({'budget':100,'joinY':[-.1,.1],'maximumSourceDistance':.003}))
        self.assertNotEqual(policy(100,[]),digest({'budget':100,'joinY':[],'maximumSourceDistance':.003}))
    def test_one_piece_part_reduces_without_joins_and_one_join_is_refused(self):
        try:import pymeshlab
        except ImportError:self.skipTest('pymeshlab not on this path')
        n=24;u,v=np.meshgrid(np.linspace(0,2*np.pi,n,endpoint=False),np.linspace(.15,np.pi-.15,n))
        ring=np.stack([.02*np.sin(v)*np.cos(u),.02*np.cos(v),.02*np.sin(v)*np.sin(u)],-1).reshape(-1,3)
        p=np.vstack([ring,[[0,.02,0],[0,-.02,0]]]);f=[]
        for i in range(n-1):
            for j in range(n):
                a,b,c,d=i*n+j,i*n+(j+1)%n,(i+1)*n+j,(i+1)*n+(j+1)%n;f+=[[a,b,c],[b,d,c]]
        top,bottom=n*n,n*n+1
        for j in range(n):f+=[[top,(j+1)%n,j],[bottom,(n-1)*n+j,(n-1)*n+(j+1)%n]]
        f=np.array(f)
        if np.einsum('ij,ij->i',p[f[:,0]],np.cross(p[f[:,1]],p[f[:,2]])).sum()<0:f=f[:,::-1]
        rv,rf,audit=reduce(p,f,300,[],pymeshlab)
        self.assertTrue(audit['closedWound']);self.assertLessEqual(len(rf),300);self.assertLess(len(rf),len(f))
        with self.assertRaisesRegex(ValueError,'natural joins'):reduce(p,f,300,[0.],pymeshlab)
