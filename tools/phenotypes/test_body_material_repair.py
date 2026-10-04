"""Color-space, palette and shader-binding regression tests for body repair."""
import unittest
import numpy as np
from pathlib import Path
from tempfile import TemporaryDirectory
import json

from bake_body_materials import srgb_linear, linear_srgb, palette_delta, mtr_roughness, run, ownership_mask
from pack_body_material_fixture import pack


class BodyMaterialRepairTests(unittest.TestCase):
    def test_measured_joint_plane_protects_seam_inside_mesh_extrema(self):
        z=[.083,0.,-.15,-.302,-.344]
        triangles=np.array([[[0,0,h],[.01,0,h],[0,.01,h]] for h in z])
        uv=np.array([[[.08+.18*i,.25],[.14+.18*i,.25],[.08+.18*i,.75]] for i in range(5)])
        samples={'position':triangles,'uv':uv}
        old,_=ownership_mask(samples,'bicepl',(300,200),.02)
        planes=[{'outwardNormal':[0,0,1],'offsetMetres':0},
                {'outwardNormal':[0,0,-1],'offsetMetres':.301921}]
        current,protected=ownership_mask(samples,'bicepl',(300,200),.02,planes)
        # Stock shoulder pivot Z0 lies well inside this donor's global height.
        self.assertGreater(old[90,83],.95)
        self.assertEqual(current[90,83],0);self.assertTrue(protected[90,83])
        self.assertGreater(current[90,137],.95)
        self.assertEqual(current[90,191],0);self.assertTrue(protected[90,191])
        with self.assertRaisesRegex(RuntimeError,'Unit finite'):
            ownership_mask(samples,'bicepl',(300,200),.02,[{'outwardNormal':[0,0,2],'offsetMetres':0}])
        with self.assertRaisesRegex(RuntimeError,'Positive connector'):
            ownership_mask(samples,'bicepl',(300,200),0,planes)

    def test_missing_operation_flags_fail_before_output_creation(self):
        with TemporaryDirectory() as directory:
            root=Path(directory);config=root/'config.json';out=root/'trial'
            config.write_text(json.dumps({'schemaVersion':1,'kind':'human-male-material-trial'}))
            with self.assertRaisesRegex(RuntimeError,'Explicit useAO/useRoughness'):
                run(config,out)
            self.assertFalse(out.exists())

    def test_srgb_transfer_including_toe_of_curve(self):
        source=np.array([0,.001,.04045,.25,.5,1.])
        self.assertTrue(np.allclose(linear_srgb(srgb_linear(source)),source,atol=1e-7))
        self.assertAlmostEqual(float(srgb_linear(np.array([.5]))[0]),.21404114048)

    def test_white_ao_is_identity_even_with_palette_reversals(self):
        palette=np.repeat(np.arange(256,dtype=np.uint8)[None,:,None],10,axis=0)
        palette=np.repeat(palette,3,axis=2)
        palette[:,120:123]=palette[:,120:123][:,::-1]
        shades=np.arange(256,dtype=np.uint8).reshape(16,16)
        self.assertTrue(np.array_equal(palette_delta(shades,np.ones((16,16)),palette,.35),np.zeros((16,16))))

    def test_ao_darkens_in_linear_color_and_is_bounded(self):
        palette=np.tile(np.arange(256,dtype=np.uint8)[None,:,None],(10,1,3))
        shades=np.full((2,2),128,np.uint8)
        delta=palette_delta(shades,np.array([[1.,.9],[.5,0.]]),palette,.35)
        self.assertEqual(delta[0,0],0)
        self.assertTrue(np.all(delta<=0) and np.all(delta>=-48))
        self.assertLess(delta[1,1],delta[0,1])

    def test_roughness_binding_disables_constant_without_touching_normal(self):
        before='renderhint NormalTangents\ntexture1 pmh0_chest001n\nparameter float Roughness 0.72\nparameter float Specularity 0.04\nparameter float Metallicness 0.001\n'
        after=mtr_roughness(before,'pmh0_chest001r')
        self.assertIn('parameter float Roughness 0\n',after)
        self.assertIn('texture3 pmh0_chest001r\n',after)
        for line in ['texture1 pmh0_chest001n','parameter float Specularity 0.04','parameter float Metallicness 0.001']:
            self.assertIn(line,after)
        self.assertNotIn('texture0',after)

    def test_existing_height_or_roughness_slot_is_rejected(self):
        before='renderhint NormalTangents\ntexture1 n\nparameter float Roughness .72\n'
        for slot in (0,3,4,5):
            with self.assertRaises(RuntimeError):mtr_roughness(before+f'texture{slot} unexpected\n','valid_r')

    def test_stale_source_is_rejected_before_writing_descendant(self):
        with TemporaryDirectory() as directory:
            root=Path(directory);source=root/'source';source.write_bytes(b'changed')
            config=root/'config.json';config.write_text(json.dumps({'schemaVersion':1,
                'kind':'human-male-material-trial','useAO':True,'useRoughness':True,
                'inputHashes':{str(source):'0'*64}}))
            out=root/'out'
            with self.assertRaisesRegex(RuntimeError,'Stale input'):run(config,out)
            self.assertFalse(out.exists())

    def test_false_geometry_or_height_operation_cannot_enter_package(self):
        with TemporaryDirectory() as directory:
            root=Path(directory);op=root/'material-operation.json'
            op.write_text(json.dumps({'kind':'runtime-body-ao-roughness',
                'nativeGeometryAndNormalsExact':True,'pltDiffuseOverride':False,'heightMapUsed':True}))
            with self.assertRaisesRegex(RuntimeError,'Unsupported/unverified'):
                pack(root/'fixture',op,root/'tools',root/'settings',root/'out')
            self.assertFalse((root/'out').exists())


if __name__=='__main__':unittest.main()
