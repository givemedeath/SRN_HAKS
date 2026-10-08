from copy import deepcopy
import unittest
import numpy as np
from render_native_cap_comparison import controls,camera_plans


class NativeCapRenderPlanTests(unittest.TestCase):
    def config(self):return {'schemaVersion':2,'kind':'explicit-cap-offline-native-comparison','diagnosticOnly':True,'targetContract':'t','targetContractSha256':'h','part':'bicepl','coordinateSpace':'working','skinPalette':'p','skinPaletteSha256':'h','paletteRows':[3,8],'control':{'nativeAudit':'a','nativeAuditSha256':'h','nativeModel':'m'},'repaired':{'nativeAudit':'a','nativeAuditSha256':'h','nativeModel':'m'},'capPreparation':'p','capPreparationSha256':'h','capOriginalFaceId':24724,'width':640,'height':900,'renderer':'cycles-cpu'}
    def test_explicit_exact_cpu_cap_scope(self):controls(self.config())
    def test_gpu_stale_scope_unmatched_palettes_and_hidden_waiver_reject(self):
        for key,value in [('renderer','eevee'),('renderer','cycles-gpu'),('capOriginalFaceId',10913),('paletteRows',[3]),('part','bicepr'),('coordinateSpace','runtime'),('width',True),('height',4096),('diagnosticOnly',False),('hiddenAccepted',True)]:
            cfg={**self.config(),key:value}
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):controls(cfg)
    def test_camera_basis_is_rigid_and_isolated_cap_is_explicit(self):
        p=np.asarray([[-.1,-.05,-.3],[.1,.05,.1],[0,0,-.2]],float);cap=np.asarray([[0,0,-.2],[.003,0,-.2],[.001,.0001,-.2]],float);rows=camera_plans(p,cap,640,900);self.assertEqual(len(rows),6);self.assertEqual(sum(row['isolatedCapOnly'] for row in rows),1)
        for row in rows:
            m=np.asarray(row['matrixWorld']);np.testing.assert_allclose(m[:3,:3].T@m[:3,:3],np.eye(3),atol=1e-12);self.assertAlmostEqual(np.linalg.det(m[:3,:3]),1);self.assertEqual(row['actualGeometryScale'],1)
        self.assertEqual(rows[-2]['orthographicHeightMetres'],.018);self.assertGreater(rows[-1]['orthographicHeightMetres'],.003)
    def test_camera_fail_closed_degenerate_cap(self):
        with self.assertRaises(ValueError):camera_plans(np.ones((3,3)),np.ones((3,3)),640,900)


if __name__=='__main__':unittest.main()
