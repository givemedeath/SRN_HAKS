import struct
import unittest
import numpy as np
from offline_native_material_bridge import palette_rgba,normal_rg,basis_fragment

class NativeMaterialBridge(unittest.TestCase):
    def test_native_uv_and_file_rows(self):
        palette=np.zeros((4,256,3),dtype='u1');palette[3,:,0]=np.arange(256)
        top=np.array([[1,2],[3,4]],dtype='u1');body=np.stack([top,np.zeros_like(top)],axis=-1)[::-1].tobytes()
        rgba=palette_rgba(b'PLT V1  '+struct.pack('<IIII',10,0,2,2)+body,palette,3)
        np.testing.assert_array_equal(rgba[:,:,0],top)
        # Blender's loaded buffer is bottom-first, while native v=0 is bottom.
        np.testing.assert_array_equal(rgba[::-1,0,0],[3,1])
        self.assertTrue((rgba[:,:,3]==255).all())
    def test_categorical_palette_lookup_precedes_filter(self):
        palette=np.zeros((4,256,3),dtype='u1');palette[3,255]=255;palette[3,128]=12
        body=np.array([[[0,0],[255,0]]],dtype='u1').tobytes()
        rgba=palette_rgba(b'PLT V1  '+struct.pack('<IIII',10,0,2,1)+body,palette,3)
        self.assertEqual(float(rgba[0,:,:3].mean()),127.5)
        self.assertNotEqual(float(palette[3,128].mean()),127.5)
    def test_installed_rg_reconstruction_not_original_blue(self):
        np.testing.assert_allclose(normal_rg([.5,.5]),[0,0,1])
        np.testing.assert_allclose(normal_rg([1.,1.]),[1,1,0])
        with self.assertRaises(ValueError):normal_rg([2.,.5])
    def test_handedness_and_backface_basis(self):
        rg=[.5,.8];n=[0,0,2];t=[3,0,0]
        np.testing.assert_allclose(basis_fragment(n,t,1,rg),[0,.6,.8])
        np.testing.assert_allclose(basis_fragment(n,t,-1,rg),[0,-.6,.8])
        np.testing.assert_allclose(basis_fragment(n,t,1,rg,False),[0,-.6,-.8])
        # Installed step(0,handedness) chooses positive at exactly zero.
        np.testing.assert_allclose(basis_fragment(n,t,0,rg),[0,.6,.8])
    def test_interpolated_vectors_are_normalized_before_cross(self):
        result=basis_fragment([0,0,4],[5,0,0],-.1,[.8,.5])
        np.testing.assert_allclose(result,[.6,0,.8])

if __name__=='__main__':unittest.main()
