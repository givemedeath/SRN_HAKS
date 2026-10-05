"""Diagnostic native cap binding and compiler tangent comparison tests."""
import copy,tempfile,unittest
from pathlib import Path
import numpy as np
from audit_target_diagnostic_uv_material_native import ascii_meshes,source_tangent_comparison,material_audit
from target_diagnostic_uv_material_stage import write_model,write_materials
from test_target_diagnostic_uv_material_stage import CAP
from test_target_part_stage import textured_fixture
from test_audit_target_native_part import fixture
from audit_target_native_part import decode
from target_body_inventory import flat_hashes
import target_diagnostic_uv_material_lineage as lineage


class DiagnosticUvMaterialNativeTests(unittest.TestCase):
    def test_four_ascii_material_bindings_reject_cap_skin_missing_and_transform(self):
        groups={}
        for i,(name,primitives) in enumerate(lineage.GROUPS):
            groups[name]={'positions':np.asarray([[[0,0,i],[1,0,i],[0,1,i]]],float),
                         'normals':np.tile([0,0,1.3],(1,3,1)),
                         'uvNative':np.asarray([[[0,0],[1,0],[0,1]]],float),'primitiveIds':list(primitives)}
        model='pmg0_pelvis001'
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'part.mdl';write_model(path,model,groups);text=path.read_text();rows=ascii_meshes(text,model)
            self.assertEqual([row['role'] for row in rows.values()],['skin','garment','cap-left','cap-right'])
            self.assertEqual([row['material'] for row in rows.values()],[model,model+'f',model+'c',model+'c'])
            for i,(name,_) in enumerate(lineage.GROUPS):
                np.testing.assert_array_equal(rows[model+'p'+str(i)]['corners']['normal'],groups[name]['normals'])
            for change in [text.replace('bitmap '+model+'c','bitmap '+model),
                           text.replace('materialname '+model+'c','materialname '+model+'f'),
                           text.replace('position 0 0 0','position .1 0 0'),
                           text.replace('position 0 0 0','position 0 0 0\n  scale 1.428571'),
                           text.replace('node trimesh '+model+'p3','node trimesh '+model+'p2')]:
                with self.assertRaises(ValueError):ascii_meshes(change,model)

    def test_compiled_tangents_report_raw_and_v_flipped_sign_without_preservation_claim(self):
        data,model,names,_,_=fixture(('skin','garment','cap-left','cap-right'));meshes,_=decode(data,model,names)
        native=meshes[names[0]];source={'tangents':np.tile([1,0,0,-1],(1,3,1)).astype(float)}
        proof=source_tangent_comparison(source,native)
        self.assertEqual(proof['sameRawGltfSignCorners'],0);self.assertEqual(proof['sameVFlippedSignCorners'],3)
        self.assertEqual(proof['sourceVsCompiledTangentCosines']['minimum'],1)
        self.assertFalse(proof['sourceAuthoredTangentPreservationClaim'])
        source['tangents'][:,:,:3]=[-1,0,0];proof=source_tangent_comparison(source,native)
        self.assertEqual(proof['sourceVsCompiledTangentCosines']['negativeCorners'],3)
        source['tangents'][0,0,:3]=0
        with self.assertRaises(ValueError):source_tangent_comparison(source,native)

    def test_material_decode_checks_actual_plt_normal_roughness_gray_and_compile_closure(self):
        doc,blob=textured_fixture();doc['materials']=[doc['materials'][0],copy.deepcopy(CAP),copy.deepcopy(doc['materials'][0])]
        model='pmg0_pelvis001'
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);write_materials(folder,model,doc,blob,.15);hashes=flat_hashes(folder)
            proof,_,files=material_audit(folder,model,doc,blob,.15,hashes)
            self.assertEqual(len(files),10);self.assertFalse(proof['unowned-neutral-diagnostic-cap']['nativeVisualEquivalenceToLinearGltfFactorClaim'])
            self.assertTrue(proof['skin']['skinTexture0Omitted']);self.assertTrue(proof['garment']['opaqueGarment'])
            bad=copy.deepcopy(hashes);bad[model+'n.tga']='0'*64
            with self.assertRaises(ValueError):material_audit(folder,model,doc,blob,.15,bad)
            path=folder/(model+'c.mtr');old=path.read_text();path.write_text(old+'texture1 '+model+'n\n')
            with self.assertRaises(ValueError):material_audit(folder,model,doc,blob,.15,flat_hashes(folder))


if __name__=='__main__':unittest.main()