"""Source-colour repairs preserve the original donor and cannot widen3mm."""
from pathlib import Path
import tempfile,unittest
from unittest.mock import patch
import numpy as np
from PIL import Image
from tools.headkit.common import pin,write
from tools.headkit.gltf import write_mesh,load,arrays
from .donor import add_source_matched_caps


class DonorCapTests(unittest.TestCase):
    def fixture(self,root):
        source=root/'source.glb';p=np.array([[0,0,0],[1,0,0],[0,1,0]],float);f=np.array([[0,1,2]])
        write_mesh(source,p,f,uv=np.array([[[.1,.1],[.8,.1],[.1,.8]]]))
        image=np.empty((4096,4096,3),np.uint8);image[:,:,0]=np.arange(4096,dtype=np.uint16)[None,:]//16;image[:,:,1:]=[80,90]
        texture=root/'colour.png';Image.fromarray(image).save(texture)
        target=root/'target.npz';positions=np.array([[.1,.1,.0005],[.15,.1,.0005],[.1,.15,.0005]])
        np.savez(target,whole_positions=positions,whole_faces=np.tile(f,(1000,1)))
        fit=root/'fit.json';write(fit,{'rawToNativeMatrix':np.eye(4).tolist()})
        diagnostic=root/'preflight.json';write(diagnostic,{'blockers':['donor-distance-or-facing'],'donorSampling':{'failedFaces':[0]}})
        return [pin(p) for p in (source,texture,target,fit,diagnostic)],image

    def test_original_geometry_uv_normals_and_mapped_rgb_are_exact(self):
        class Igl:
            def point_mesh_squared_distance(self,points,vertices,faces):
                closest=points.copy();closest[:,2]=0
                return np.full(len(points),.0005**2),np.zeros(len(points),int),closest
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);pins,original=self.fixture(root)
            with patch('tools.headkit.common.library',return_value=Igl()):
                r=add_source_matched_caps(*pins,{},root/'repaired',sampling_triangle_allowance=2)
            v,f,a=arrays(*load(Path(pins[0]['path']).read_bytes()))
            vv,ff,aa=arrays(*load(Path(r['donor']['path']).read_bytes()))
            self.assertEqual(len(ff),2)
            np.testing.assert_array_equal(vv[ff[:1]],v[f])
            for name in ('NORMAL','TEXCOORD_0'):
                np.testing.assert_array_equal(aa[name][ff[:1]],a[name][f])
            with Image.open(r['texture']['path']) as image:actual=np.asarray(image)
            np.testing.assert_array_equal(actual[:,:4071],original[:,:4071])
            self.assertAlmostEqual(r['maximumLocalColourSampleDistance'],.0005)
            self.assertEqual(r['explicitRepairCapFaces'],[0])
            self.assertEqual(r['originalDonorTriangles'],1)
            self.assertEqual(r['auxiliarySamplingTriangles'],1)
            self.assertEqual(r['nativeTargetTriangleAllowance'],0)

    def test_auxiliary_allowance_is_bounded_and_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);pins,_=self.fixture(root)
            for value in (True,-1,129):
                with self.assertRaisesRegex(ValueError,'auxiliary sampling allowance'):
                    add_source_matched_caps(*pins,{},root/'bad',sampling_triangle_allowance=value)
            self.assertFalse((root/'bad').exists())

    def test_distant_rgb_source_is_rejected_before_creating_output(self):
        class Igl:
            def point_mesh_squared_distance(self,points,vertices,faces):
                return np.full(len(points),.004**2),np.zeros(len(points),int),points
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);pins,_=self.fixture(root)
            with patch('tools.headkit.common.library',return_value=Igl()),self.assertRaisesRegex(ValueError,'exceeds3mm'):
                add_source_matched_caps(*pins,{},root/'repaired')
            self.assertFalse((root/'repaired').exists())


if __name__=='__main__':unittest.main()
