"""Micro-cap provenance and installed normal RG/TBN arithmetic diagnostics."""
import unittest

import numpy as np

from audit_target_native_caps import cap_metrics, cap_provenance


def native_triangle(sign=1):
    return {'position':np.array([[0,0,0],[1,0,0],[0,1,0]],dtype='f4'),
            'normal':np.tile([0,0,1],(3,1)).astype('f4'),'tangent':np.tile([1,0,0],(3,1)).astype('f4'),
            'sign':np.full((3,1),sign,dtype='f4'),'uv':np.array([[.25,.75],[.75,.75],[.25,.25]],dtype='f4'),
            'faces':np.array([[0,1,2]])}


class TargetNativeCapTests(unittest.TestCase):
    def test_only_explicit_appended_original_vertex_cap_provenance(self):
        archive = {'sourceTriangleIds':np.array([7,9,-1]),'addedConnectorMask':np.array([False,False,True]),
                   'addedSourceVertexFaces':np.array([[11,12,13]])}
        ids,vertices = cap_provenance(archive,3)
        np.testing.assert_array_equal(ids,[2]); np.testing.assert_array_equal(vertices,[[11,12,13]])
        for field,change in [('sourceTriangleIds',np.array([7,-1,9])),
                             ('addedConnectorMask',np.array([False,True,True])),
                             ('addedSourceVertexFaces',np.array([[11,12,-1]]))]:
            bad = {**archive,field:change}
            with self.assertRaises(ValueError): cap_provenance(bad,3)

    def test_neutral_normal_map_reports_exact_geometry_and_material_samples(self):
        native = native_triangle(); normal = np.tile([128,128,255],(2,2,1)).astype('u1')
        roughness = np.full((2,2,3),128,dtype='u1'); shade = np.full((2,2),90,dtype='u1')
        rows,tangent = cap_metrics(native,[0],normal,roughness,shade,33071,33071); row = rows[0]
        self.assertEqual(row['areaSquareMetres'],.5)
        self.assertEqual(row['authoredCornerNormalVsGeometricCosines'],[1,1,1])
        self.assertTrue(min(row['sampleMappedFrontNormalVsGeometricCosines']) > .999)
        self.assertEqual(row['sampleRoughnessRange'],[128/255,128/255]); self.assertEqual(row['samplePltShadeRange'],[90,90])
        self.assertEqual(tangent['positiveHandednessVertices'],3); self.assertFalse(row['visualAccepted'])

    def test_reconstructed_positive_z_ignores_blue_and_reports_outside_disk(self):
        native = native_triangle(); normal = np.tile([255,255,0],(2,2,1)).astype('u1')
        roughness = np.full((2,2,3),130,dtype='u1'); shade = np.full((2,2),80,dtype='u1')
        first,_ = cap_metrics(native,[0],normal,roughness,shade,33071,33071)
        normal[...,2] = 255; second,_ = cap_metrics(native,[0],normal,roughness,shade,33071,33071)
        self.assertEqual(first[0]['sampleRgOutsideUnitDiskCount'],7)
        self.assertEqual(first[0]['sampleMappedFrontNormalVsGeometricCosines'],[0]*7)
        self.assertEqual(first[0]['sampleMappedFrontNormalVsGeometricCosines'],second[0]['sampleMappedFrontNormalVsGeometricCosines'])
        self.assertAlmostEqual(first[0]['sampleFragmentNormalLengthRange'][1],np.sqrt(2))

    def test_zero_area_or_zero_interpolated_tangent_fails_closed(self):
        normal = np.tile([128,128,255],(2,2,1)).astype('u1'); rough = normal.copy(); shade = normal[...,0]
        bad = native_triangle(); bad['position'][2] = bad['position'][1]
        with self.assertRaisesRegex(ValueError,'Zero-area'): cap_metrics(bad,[0],normal,rough,shade)
        bad = native_triangle(); bad['tangent'][1] = [-1,0,0]
        with self.assertRaisesRegex(ValueError,'Undefined sampled normalize'): cap_metrics(bad,[0],normal,rough,shade)


if __name__ == '__main__': unittest.main()
