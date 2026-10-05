import unittest
import numpy as np
from write_bounded_pelvis_diagnostic import (CAP_MATERIAL, append_accessor, append_diagnostic,
    decoded_primitives, preservation, shade_with_uv, source_to_fit_raw)


class BoundedDiagnosticWriterTests(unittest.TestCase):
    def original(self):
        doc={'asset':{'version':'2.0'},'buffers':[{'byteLength':0}], 'accessors':[],'bufferViews':[],
            'materials':[{'name':'original-painted-body','pbrMetallicRoughness':{'baseColorFactor':[.1,.2,.3,1]}}],
            'meshes':[{'primitives':[]}],'nodes':[{'mesh':0,'name':'original'}],'scenes':[{'nodes':[0]}],'scene':0}
        binary=b'ORIGINAL';attrs={}
        data={'POSITION':np.array([[0.,0.,0.],[1.,0.,0.],[0.,0.,1.],[1.,0.,1.]]),
              'NORMAL':np.array([[0.,-1.,0.]]*4),'TEXCOORD_0':np.array([[0.,0.],[1.,0.],[0.,1.],[1.,1.]]),
              'TANGENT':np.array([[1.,0.,0.,1.]]*4)}
        for key,value in data.items():binary,index=append_accessor(doc,binary,value,key);attrs[key]=index
        binary,index=append_accessor(doc,binary,np.array([[0,1,2],[1,3,2]]),'indices')
        doc['meshes'][0]['primitives']=[{'attributes':attrs,'indices':index,'material':0,'mode':4}]
        doc['buffers'][0]['byteLength']=len(binary)
        return doc,binary

    def cap(self):
        p=np.array([[0.,-.001,0.],[1.,-.001,0.],[0.,-.001,1.]])
        return shade_with_uv(p,np.array([[0,1,2]]),np.array([[0.,0.],[1.,0.],[0.,1.]]))

    def test_lossless_body_attributes_material_and_corner_preservation(self):
        doc,blob=self.original();faces=np.array([[0,1,2]])
        out,binary=append_diagnostic(doc,blob,faces,[('left',self.cap()),('right',self.cap())])
        proof=preservation(doc,blob,out,binary,faces)
        self.assertTrue(proof['originalBinPrefixExact'])
        self.assertEqual(binary[:len(blob)],blob)
        self.assertEqual(out['materials'][0],doc['materials'][0])
        self.assertEqual(out['materials'][1],CAP_MATERIAL)
        self.assertEqual(len(decoded_primitives(out,binary)),3)

    def test_modified_body_corner_order_rejected(self):
        doc,blob=self.original();faces=np.array([[0,1,2]])
        out,binary=append_diagnostic(doc,blob,faces,[('left',self.cap()),('right',self.cap())])
        with self.assertRaisesRegex(ValueError,'corner'):preservation(doc,blob,out,binary,np.array([[1,0,2]]))

    def test_modified_source_bytes_rejected(self):
        doc,blob=self.original();faces=np.array([[0,1,2]])
        out,binary=append_diagnostic(doc,blob,faces,[('left',self.cap()),('right',self.cap())])
        with self.assertRaisesRegex(ValueError,'prefix'):preservation(doc,blob,out,b'X'+binary[1:],faces)

    def test_modified_original_material_rejected(self):
        doc,blob=self.original();faces=np.array([[0,1,2]])
        out,binary=append_diagnostic(doc,blob,faces,[('left',self.cap()),('right',self.cap())])
        out['materials'][0]['name']='changed'
        with self.assertRaisesRegex(ValueError,'materials'):preservation(doc,blob,out,binary,faces)

    def test_nwn_to_raw_fit_bridge_preserves_up_and_front(self):
        m=np.eye(4);m[:3,:3]=np.diag([-.54,-.54,.54]);m[:3,3]=[.1,.2,.3]
        p=np.array([[1.,2.,3.]])
        actual=source_to_fit_raw(p,m)
        # rawGLTF(1,2,3) => NWN(1,-3,2); fit => (-.44,1.82,1.38) => raw(-.44,1.38,-1.82)
        self.assertTrue(np.allclose(actual,[[-.44,1.38,-1.82]]))

    def test_transformed_cap_shading_uses_serialized_geometry_and_fixed_uv(self):
        p=np.array([[0.,0.,0.],[1.,.1,0.],[0.,0.,1.]],dtype=np.float32)
        uv=np.array([[.1,.2],[.8,.2],[.1,.9]],dtype=np.float32)
        attrs=shade_with_uv(p,np.array([[0,1,2]]),uv)
        self.assertTrue(np.array_equal(attrs['TEXCOORD_0'],uv))
        normal=np.cross(p[1]-p[0],p[2]-p[0]);normal/=np.linalg.norm(normal)
        self.assertTrue(np.allclose(attrs['NORMAL'],normal))
        self.assertTrue(np.allclose(np.sum(attrs['NORMAL']*attrs['TANGENT'][:,:3],axis=1),0,atol=1e-7))

    def test_cap_chart_degeneracy_rejected(self):
        with self.assertRaisesRegex(ValueError,'UV'):shade_with_uv(np.array([[0.,0.,0.],[1.,0.,0.],[0.,0.,1.]]),np.array([[0,1,2]]),np.zeros((3,2)))


if __name__=='__main__':unittest.main()
