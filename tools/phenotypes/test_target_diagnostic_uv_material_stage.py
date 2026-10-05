"""Focused diagnostic cap-role/material/ASCII/approval guard tests."""
import copy,json,struct,tempfile,unittest
from pathlib import Path
import numpy as np
from PIL import Image
import target_contract as contract
import target_diagnostic_uv_basis as basis
import target_diagnostic_uv_material_lineage as lineage
from target_diagnostic_uv_material_stage import cap_pixels,stage,write_materials,write_model
from audit_geometry import arrays
from segment_target_pelvis_boundary import CORNER_KEYS
from target_part_pipeline import verify_source_receipt
from test_target_part_pipeline import target_fixture
from test_target_part_stage import textured_fixture

CAP={'name':'UNACCEPTED_Troll_connector_neutral_diagnostic','pbrMetallicRoughness':
     {'baseColorFactor':[.36,.36,.36,1.],'metallicFactor':0.,'roughnessFactor':1.},
     'alphaMode':'OPAQUE','doubleSided':False,'extras':{'diagnosticOnly':True,'materialAccepted':False,
     'purpose':'Neutral cap-only material pending explicit Troll PLT mapping'}}


def review(source,candidate):
    return {'reviewed':True,'reviewedBy':'/root','scope':lineage.REVIEW_SCOPE,
            'sourceReceipt':source,'sourceCandidate':candidate,'newCornerShadingPolicy':basis.POLICY_ID,
            'capMode':lineage.CAP_MODE,'aoComparisons':[0,.15,.35],
            'authorizeStageExports':True,'authorizeOfflineNativeCompilation':True,
            'evidence':[{'path':'synthetic-review','sha256':'0'*64}],
            'notes':'Synthetic only: preserve unowned caps and all broader gates false.'}


class DiagnosticUvMaterialStageTests(unittest.TestCase):
    def test_semantic_pin_checks_actual_identity_and_truthful_optional_size(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'source.json';path.write_bytes(b'fixed source')
            original={'path':str(path),'sha256':contract.sha(path)}
            sized={**original,'bytes':path.stat().st_size}
            self.assertTrue(lineage.same_pin(original,sized))
            for bad in [{**sized,'bytes':1},{**sized,'bytes':True},{**original,'sha256':'0'*64}]:
                with self.assertRaises(ValueError):lineage.same_pin(original,bad)
            copy_path=path.with_name('same-bytes-other-source.json');copy_path.write_bytes(path.read_bytes())
            self.assertFalse(lineage.same_pin(original,{'path':str(copy_path),'sha256':contract.sha(copy_path)}))
    def test_explicit_root_source_policy_cap_and_ao_scope_required(self):
        source={'path':'source','sha256':'0'*64};candidate={'path':'candidate','sha256':'1'*64}
        valid=review(source,candidate);lineage.stage_review(valid,source,candidate)
        for key,value in [('reviewed',False),('reviewedBy','classifier'),('scope','production'),
                          ('capMode','skin'),('aoComparisons',[.15]),('authorizeStageExports',False),
                          ('authorizeOfflineNativeCompilation',False),('newCornerShadingPolicy','authored-default'),
                          ('sourceReceipt',candidate),('sourceCandidate',source),('evidence',[]),
                          ('capOwnershipAccepted',True)]:
            bad=copy.deepcopy(valid);bad[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):lineage.stage_review(bad,source,candidate)

    def test_neutral_caps_reject_relabel_recolor_shader_maps_and_alpha(self):
        pixels=cap_pixels(CAP);self.assertEqual(pixels.shape,(2048,2048,3));self.assertTrue((pixels==92).all())
        for change in ('color','map','normal','alpha','double','acceptance','roughness'):
            bad=copy.deepcopy(CAP)
            if change=='color':bad['pbrMetallicRoughness']['baseColorFactor']=[1,1,1,1]
            elif change=='map':bad['pbrMetallicRoughness']['baseColorTexture']={'index':0}
            elif change=='normal':bad['normalTexture']={'index':0}
            elif change=='alpha':bad['alphaMode']='BLEND'
            elif change=='double':bad['doubleSided']=True
            elif change=='acceptance':bad['extras']['materialAccepted']=True
            else:bad['pbrMetallicRoughness']['roughnessFactor']=0
            with self.subTest(change=change),self.assertRaises(ValueError):cap_pixels(bad)

    def test_same_untreated_ao_variants_only_change_skin_plt_intensity(self):
        doc,blob=textured_fixture();doc['materials']=[doc['materials'][0],copy.deepcopy(CAP),copy.deepcopy(doc['materials'][0])]
        model='pmg0_pelvis001';results=[]
        with tempfile.TemporaryDirectory() as temp:
            for i,ao in enumerate((0,.15,.35)):
                folder=Path(temp)/str(i);folder.mkdir();write_materials(folder,model,doc,blob,ao)
                plt=(folder/(model+'.plt')).read_bytes();v=np.frombuffer(plt[24:],'u1').reshape(2048,2048,2)[::-1]
                expected=int(np.dot([128,95,72],[.2126,.7152,.0722])*(1-ao*(1-80/255)))
                self.assertTrue((v[:,:,0]==expected).all());self.assertFalse(v[:,:,1].any())
                self.assertNotIn('texture0',(folder/(model+'.mtr')).read_text())
                self.assertIn('texture0 '+model+'f',(folder/(model+'f.mtr')).read_text())
                cap=(folder/(model+'c.mtr')).read_text();self.assertNotIn('texture1',cap);self.assertNotIn('texture3',cap)
                self.assertFalse((folder/(model+'c.plt')).exists())
                fixed={p.name:p.read_bytes() for p in folder.iterdir() if p.name!=model+'.plt'}
                results.append(fixed)
                np.testing.assert_array_equal(np.asarray(Image.open(folder/(model+'fn.tga')))[0,0],[111,133,244])
                np.testing.assert_array_equal(np.asarray(Image.open(folder/(model+'fr.tga')))[0,0],[102,102,102])
                self.assertTrue((np.asarray(Image.open(folder/(model+'c.tga')))==92).all())
            self.assertEqual(results[0],results[1]);self.assertEqual(results[1],results[2])

    def test_ascii_keeps_separate_caps_and_ordered_nonunit_normals(self):
        groups={}
        for i,(name,primitives) in enumerate(lineage.GROUPS):
            p=np.asarray([[[0,0,i],[1,0,i],[0,1,i]]],float)
            groups[name]={'positions':p,'normals':np.tile([0,0,1.3],(1,3,1)),
                          'uvNative':np.asarray([[[0,0],[1,0],[0,1]]],float),'primitiveIds':list(primitives)}
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'part.mdl';proof=write_model(path,'pmg0_pelvis001',groups);text=path.read_text()
            self.assertEqual(len(proof),4)
            self.assertEqual([v['role'] for v in proof.values()],['skin','garment','cap-left','cap-right'])
            self.assertEqual([v['material'] for v in proof.values()],['pmg0_pelvis001','pmg0_pelvis001f','pmg0_pelvis001c','pmg0_pelvis001c'])
            self.assertNotIn('tangents ',text)
            import re
            for index,(name,_) in enumerate(lineage.GROUPS):
                block=re.search(r'(?ms)^node trimesh pmg0_pelvis001p'+str(index)+r'\n(.*?)^endnode',text)[1]
                f=np.asarray(arrays(block,'faces'),int);n=np.asarray(arrays(block,'normals'))
                np.testing.assert_array_equal(n[f[:,:3]],groups[name]['normals'])
                self.assertFalse(proof['pmg0_pelvis001p'+str(index)]['authoredSourceTangentsSerialized'])

    def test_new_entrypoint_rejects_old_kind_runtime_caps_skin_and_unknown_controls_before_output(self):
        valid={'schemaVersion':2,'kind':lineage.STAGE_KIND,'diagnosticOnly':True,'coordinateSpace':'working',
               'part':'pelvis','newCornerShadingPolicy':basis.POLICY_ID,'capMode':lineage.CAP_MODE,
               'materialRoles':lineage.MATERIAL_ROLES,'aoStrength':0}
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for key,value in [('kind','target-part-stage'),('coordinateSpace','runtime'),('part','chest'),
                              ('newCornerShadingPolicy','none'),('capMode','skin'),('materialRoles',{'0':'skin','1':'skin','2':'garment'}),
                              ('aoStrength',.2),('normalStrength',.5)]:
                bad=copy.deepcopy(valid);bad[key]=value;path=root/'config.json';path.write_text(json.dumps(bad))
                with self.subTest(key=key),self.assertRaises(ValueError):stage(path,root/'unused')
                self.assertFalse((root/'unused').exists())

    def test_reader_and_existing_canonical_guards_do_not_promote_new_source(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);target=root/'target.json';data=target_fixture();target.write_text(json.dumps(data))
            path=root/'candidate.json';path.write_text(json.dumps({'schemaVersion':2,'kind':basis.KIND,
                'operation':basis.OPERATION,**contract.binding(target,data,'working')}))
            with self.assertRaises(ValueError):verify_source_receipt(root/'unused.glb',path,target,data,'pelvis','working')
            for kind in ('target-part-geometry','target-part-diagnostic-material-geometry','target-part-diagnostic-geometry'):
                path.write_text(json.dumps({'schemaVersion':2,'kind':kind,'coordinateSpace':'working'}))
                with self.subTest(kind=kind),self.assertRaises(ValueError):
                    lineage.verify_receipt(path,target,data,{},{})


if __name__=='__main__':unittest.main()
