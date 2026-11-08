import unittest
import numpy as np
from .preflight import geometry_report,uv_report,target_hash,region_hash


class PreflightTests(unittest.TestCase):
    def test_geometry_and_protected_features_fail_early(self):
        p=np.array([[0,0,0],[1,0,0],[0,1,0],[0,0,1]],float)
        f=np.array([[0,2,1],[0,1,3],[0,3,2],[1,2,3]])
        report=geometry_report(p,f,{},budget=4)
        self.assertTrue(report['passed']);self.assertEqual(report['totalGenus'],0)
        self.assertIn('triangle-budget',geometry_report(p,f,{},budget=3)['blockers'])
        self.assertFalse(geometry_report(p,f[:-1],{})['passed'])
        report=geometry_report(p,f,{'openingProbes':[{'name':'blocked','start':[-1,.1,.1],'end':[2,.1,.1]}]})
        self.assertIn('protected-feature',report['blockers'])

    def test_runtime_uvs_caps_and_tiny_charts(self):
        uv=np.array([[[.1,.1],[.9,.1],[.9,.9]],[[.1,.1],[.9,.9],[.1,.9]]])
        corners=np.concatenate([uv,np.zeros((2,3,1))],axis=2)
        report=uv_report(corners,uv,np.zeros(2,bool),64)
        self.assertTrue(report['passed'],report)
        bad=uv.copy();bad[1]=bad[0]
        self.assertIn('overlap-or-degenerate-uv',uv_report(corners,bad,np.zeros(2,bool),64)['blockers'])
        tiny=np.array([[[.02,.02],[.02001,.02],[.02,.02001]]])
        report=uv_report(np.r_[corners,corners[:1]],np.r_[uv,tiny],np.zeros(3,bool),64)
        self.assertIn('unsampled-surface',report['blockers'])
        report=uv_report(np.r_[corners,corners[:1]],np.r_[uv,uv[:1]],np.array([False,False,True]),64)
        self.assertIn('cap-visible-overlap',report['blockers'])
        self.assertNotEqual(target_hash(corners,uv),target_hash(corners,uv+.01))
        self.assertNotEqual(region_hash(corners,uv,[0,0]),region_hash(corners,uv,[0,1]))
        report=uv_report(corners,uv,np.zeros(2,bool),64,regions=np.zeros(2,np.int32))
        self.assertTrue(report['passed']);self.assertEqual(report['regionAuthority'],'bound-atlas-lineage')
        with self.assertRaisesRegex(ValueError,'retained UV regions'):
            uv_report(corners,uv,np.zeros(2,bool),64,regions=[-1,-1])

    def test_nonfinite_or_outside_uv_rejected(self):
        uv=np.array([[[0.,0.],[1.,0.],[0.,1.]]]);p=np.c_[uv[0],np.zeros(3)][None]
        self.assertIn('uv-outside-atlas',uv_report(p,uv+1,np.zeros(1,bool),64)['blockers'])
        uv[0,0,0]=np.nan
        with self.assertRaisesRegex(ValueError,'Finite'):uv_report(p,uv,np.zeros(1,bool),64)
