"""Reject plausible donors unless ordered UV/material ownership can be proved."""
import unittest
import numpy as np
from prepare_target_material_donors import uv_coverage,layer_coverage,compare_meshes,target_palette_name

class MaterialDonorTests(unittest.TestCase):
    def test_square_has_full_center_coverage_and_triangle_uses_texture_indices(self):
        uv=np.array([[0,0,0],[1,0,0],[1,1,0],[0,1,0]])
        faces=np.array([[0,1,2,1,0,1,2,0],[0,2,3,1,0,2,3,0]])
        mask,proof=uv_coverage(uv,faces,4,4);self.assertTrue(mask.all());self.assertEqual(proof['texelCentersCovered'],16)
        faces[:,4:7]=0;mask,proof=uv_coverage(uv,faces,4,4);self.assertFalse(mask.any());self.assertEqual(proof['degenerateUvTriangles'],2)

    def test_uv_order_and_face_uv_mapping_change_reject_exact_donor(self):
        original={'name':'source','type':'trimesh','verts':np.array([[0,0,0],[1,0,0],[0,1,0]]),'faces':np.array([[0,1,2,1,0,1,2,0]]),'tverts':np.array([[0,0,0],[1,0,0],[0,1,0]]),'normals':np.array([])}
        self.assertTrue(compare_meshes([original],[original])['orderedVertexFaceUvCorrespondenceExact'])
        for key in ('verts','tverts'):
            changed={**original,key:original[key][[1,0,2]]}
            self.assertFalse(compare_meshes([original],[changed])['orderedVertexFaceUvCorrespondenceExact'])
        faces=original['faces'].copy();faces[0,4:7]=[1,0,2];changed={**original,'faces':faces}
        self.assertFalse(compare_meshes([original],[changed])['orderedVertexFaceUvCorrespondenceExact'])

    def test_wrapped_uvs_and_invalid_texture_indices_need_separate_review(self):
        uv=np.array([[0,0,0],[1,0,0],[0,1,0]],dtype=float);faces=np.array([[0,1,2,1,0,1,2,0]])
        bad=uv.copy();bad[0,0]=-.1
        with self.assertRaisesRegex(ValueError,'Wrapping'):uv_coverage(bad,faces,4,4)
        faces[0,6]=3
        with self.assertRaisesRegex(ValueError,'indices'):uv_coverage(uv,faces,4,4)

    def test_layer_sampling_records_both_texture_row_orientations_unaccepted(self):
        pixels=bytes([10,2,20,2,30,3,40,3]);mask=np.array([[True,False],[False,False]])
        result=layer_coverage(b'0'*24+pixels,mask)
        self.assertEqual(result['orientations']['row0-as-v0']['layerPixelCounts'],{'2':1})
        self.assertEqual(result['orientations']['row0-as-v1']['layerPixelCounts'],{'3':1});self.assertFalse(result['clientTextureRowOrientationAccepted'])

    def test_global_human_and_female_material_outputs_are_not_permitted(self):
        data={'identity':{'prefix':'pmg0','gender':'male','phenotype':0}}
        self.assertEqual(target_palette_name(data),'pmg0_shol255.plt')
        for identity in ({'prefix':'pmh0','gender':'male','phenotype':0},{'prefix':'pmg0','gender':'female','phenotype':0}):
            with self.assertRaisesRegex(ValueError,'Human or female'):target_palette_name({'identity':identity})

if __name__=='__main__':unittest.main()
