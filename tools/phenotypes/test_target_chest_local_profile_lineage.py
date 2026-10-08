"""Regression for near-horizontal cuts: one double partition drives both representations."""
import unittest
import numpy as np
from place_purposebuilt_pelvis import BASIS
from repair_target_chest_local_profile import subdivide
class SingleLineageTests(unittest.TestCase):
 def test_near_horizontal_edge_does_not_use_independent_float32_cut(self):
  p=np.array([[.1,-.037001,0],[.11,-.036998,.001],[.105,.02,.002]],dtype='<f4')
  attrs={'POSITION':p,'NORMAL':np.tile([0,0,1.5],(3,1)).astype('<f4'),'TEXCOORD_0':np.array([[.1,.2],[.6,.7],[.8,.9]],dtype='<f4'),'TANGENT':np.tile([1.2,0,0,-1],(3,1)).astype('<f4')};f=np.array([[0,1,2]])
  nativeP=p.astype(float)@BASIS.T;nativeP[0,2]+=1e-8;nativeP[1,2]-=1e-8
  uv=attrs['TEXCOORD_0'][f].astype(float);nt=attrs['TANGENT'].astype(float);nt[:,:3]=nt[:,:3]@BASIS.T
  native={'positions':nativeP[f],'normals':(attrs['NORMAL'].astype(float)@BASIS.T)[f],'uvGltf':uv,'uvNative':np.stack((uv[:,:,0],1-uv[:,:,1]),2),'tangents':nt[f]}
  planes=[-.037,.01];sp=subdivide(attrs,f,planes,native)
  np.testing.assert_array_equal(sp['barycentric'],sp['nativeBarycentric'])
  step=sp['steps'][0];plane=step['planeLocalZMetres'];edge=next(v for v in step['splitRawRows'].values() if set(v['sourceRawEdge'])=={0,1})
  expected=(plane-nativeP[0,2])/(nativeP[1,2]-nativeP[0,2]);floatcut=(plane-float(p[0,1]))/(float(p[1,1])-float(p[0,1]))
  self.assertAlmostEqual(edge['bWeight'],expected,14);self.assertGreater(abs(expected-floatcut),1e-5)
  for k,v in attrs.items():self.assertEqual(sp['attributes'][k][:3].tobytes(),v.tobytes())
  w=sp['barycentric'];parents=sp['parentFaceIds'];expectedUv=np.einsum('fci,fij->fcj',w,native['uvGltf'][parents])
  np.testing.assert_allclose(sp['nativeValues']['uvGltf'],expectedUv,atol=3e-16)
  np.testing.assert_allclose(sp['attributes']['TEXCOORD_0'][sp['faces']],expectedUv,atol=8e-8)
  self.assertTrue(sp['upperFaceMask'].any());self.assertTrue((~sp['upperFaceMask']).any())
if __name__=='__main__':unittest.main()
