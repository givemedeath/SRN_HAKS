import copy
import unittest
from unittest.mock import patch
import numpy as np
import verify_diagnostic_foot_uniform120 as v
from diagnostic_foot_uniform120 import append_position
from test_diagnostic_foot_uniform120 import fixture
from place_purposebuilt_pelvis import accessor,BASIS
import target_contract as tc

class Foot120ActualDecode(unittest.TestCase):
    def mesh(self):
        d,b=fixture();nd,nb,p=append_position(d,b,[0,0,-.1]);return d,b,nd,nb

    def test_exact_serialized_proof_keeps_nonorthogonal_authored_basis(self):
        d,b,nd,nb=self.mesh();rows,actual,F=v.verify_serialized(d,b,nd,nb,[0,0,-.1])
        self.assertEqual(rows['NORMAL'].tobytes(),actual['NORMAL'].tobytes())
        self.assertEqual(rows['TANGENT'].tobytes(),actual['TANGENT'].tobytes())
        self.assertNotEqual(actual['NORMAL'][0]@actual['TANGENT'][0,:3],0.)
        np.testing.assert_array_equal(F,[[0,1,2]])

    def test_position_seam_bijection_allows_sort_permutation_but_rejects_merge_or_split(self):
        original=np.array([[0.,2.,0.],[1.,0.,0.],[0.,2.,0.]],dtype='<f4')
        permutation=np.array([[1.,2.,0.],[1.,0.,0.],[1.,2.,0.]],dtype='<f4')
        self.assertEqual(v.verify_position_classes(original,permutation),2)
        with self.assertRaises(ValueError):v.verify_position_classes(original,np.zeros((3,3),dtype='<f4'))
        split=permutation.copy();split[2,2]=.001
        with self.assertRaises(ValueError):v.verify_position_classes(original,split)

    def test_bin_shading_and_pixel_mutations_rejected(self):
        for view in [1,2,3,5]:
            d,b,nd,nb=self.mesh();raw=bytearray(nb);raw[d['bufferViews'][view]['byteOffset']]^=1
            with self.assertRaisesRegex(ValueError,'BIN prefix'):v.verify_serialized(d,b,nd,bytes(raw),[0,0,-.1])

    def test_changed_indices_and_metadata_or_extra_append_rejected(self):
        for field in ['indices','material','node','append']:
            d,b,nd,nb=self.mesh()
            if field=='indices':nd['meshes'][0]['primitives'][0]['indices']=0
            if field=='material':nd['materials'][0]['normalTexture']['scale']=.5
            if field=='node':nd['nodes'][0]['translation']=[0,0,.01]
            if field=='append':nb+=b'\0'*4
            with self.assertRaises(ValueError):v.verify_serialized(d,b,nd,nb,[0,0,-.1])

    def test_scaled_position_bit_mutation_rejected(self):
        d,b,nd,nb=self.mesh();raw=bytearray(nb);raw[len(b)]^=1
        with self.assertRaisesRegex(ValueError,'exact scaled POSITION'):v.verify_serialized(d,b,nd,bytes(raw),[0,0,-.1])

    def archive(self):
        d,b,nd,nb=self.mesh();rows,actual,F=v.verify_serialized(d,b,nd,nb,[0,0,-.1])
        # Authoritative source corners at measured sole plane -.1.
        P=(rows['POSITION'].astype(float)@BASIS.T)*.1;P[:,2]+=-.1-P[:,2].min()
        N=rows['NORMAL'].astype(float)[F]@BASIS.T
        T=rows['TANGENT'].astype(float)[F].copy();T[...,:3]=T[...,:3]@BASIS.T
        source={'positions':P[F],'normals':N,'tangents':T,
                'uvGltf':rows['TEXCOORD_0'].astype(float)[F],
                'sourceTriangleIds':np.array([0],dtype=np.int64)}
        c=np.array([0.,0.,-.1]);child={k:a.copy() for k,a in source.items()}
        child['positions']=c+(source['positions']-c)*1.2
        # Paired literal serialized approximation of this fixture's own corner positions.
        actual['POSITION']=(child['positions'][0]@BASIS).astype('<f4')
        return source,child,np.eye(4),c,actual,F

    def test_actual_archive_exact_protection_and_independent_world_formula(self):
        source,child,A,c,actual,F=self.archive()
        r=v.verify_archives(source,child,A,c,actual,F)
        self.assertLess(r['independentWorldAffineMaxErrorMetres'],2e-16)
        self.assertEqual(r['actualBindSoleMinimumWorldZ'],r['originalBindSoleMinimumWorldZ'])

    def test_archive_normal_uv_w_or_identity_provenance_mutations_rejected(self):
        for key in ['normals','tangents','uvGltf','sourceTriangleIds']:
            source,child,A,c,actual,F=self.archive();child[key].flat[0]+=1
            with self.assertRaisesRegex(ValueError,'Protected archive'):v.verify_archives(source,child,A,c,actual,F)

    def test_compounded_scale_or_wrong_pivot_rejected(self):
        source,child,A,c,actual,F=self.archive();child['positions']=c+(source['positions']-c)*1.44
        with self.assertRaisesRegex(ValueError,'own-coordinate'):v.verify_archives(source,child,A,c,actual,F)
        source,child,A,c,actual,F=self.archive()
        with self.assertRaises(ValueError):v.verify_archives(source,child,A,c+[.01,0,0],actual,F)

    def test_typed_identity_and_final_acceptance_cannot_be_promoted(self):
        target=tc.load(v.TARGET);r=v.read(v.GEOMETRY);v.validate_typed_receipt(r,v.TARGET,target)
        for key,value in [('operation','fit'),('part','footr'),('sourceOriginalRatio',1.44),
                          ('statureApplications',1),('geometryAccepted',True),('clientAccepted',True)]:
            child=copy.deepcopy(r);child[key]=value
            with self.assertRaises(ValueError):v.validate_typed_receipt(child,v.TARGET,target)

    def test_runtime_or_other_resource_row_rejected_before_reads(self):
        with patch.object(v,'read',side_effect=AssertionError('unexpected read')):
            with self.assertRaisesRegex(ValueError,'Exact current LEFT'):v.verify_receipt(v.GEOMETRY,v.TARGET,{},'runtime')
            with self.assertRaisesRegex(ValueError,'Exact current LEFT'):v.verify_receipt(v.GEOMETRY.parent/'other.json',v.TARGET,{})

    def test_generic_pipeline_still_rejects_new_foot_operation(self):
        import target_part_pipeline as generic
        with patch.object(generic,'read_target',return_value=(v.TARGET,tc.load(v.TARGET))), \
             patch.object(generic.json,'loads',return_value={'schemaVersion':2,'operation':v.OPERATION}), \
             patch.object(generic.Path,'read_text',return_value='{}'):
            with self.assertRaisesRegex(ValueError,'Undeclared geometry operation'):generic.execute(v.CONFIG,v.BASE/'unused')

if __name__=='__main__':unittest.main()


