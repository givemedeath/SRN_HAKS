"""Reviewed face coverage, attribute conservation and exactly-once stature tests."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
import target_contract as contract
from mirror_stock_limb_part import detached_affine_bake
from place_purposebuilt_pelvis import accessor,read_glb,write_glb
from partition_target_pelvis_materials import active_faces,execute,face_layout_sha,partition,partition_archive
from target_part_pipeline import execute as geometry_execute
from target_part_stage import stage
from test_target_part_pipeline import target_fixture
from test_target_part_stage import textured_fixture
from toolchain_test_fixture import bindings as runtime_test_bindings


def fixture():
    doc,blob=textured_fixture();doc,blob,archive,proof=detached_affine_bake(doc,blob,np.eye(4))
    return doc,blob,archive,proof


def face_map(doc,blob,skin=None,garment=None):
    rows=active_faces(doc,blob)
    return {'faceIdSpace':'parent-active-primitive-order','primitiveFaceCounts':[len(faces) for _,_,faces in rows],
            'sourceFaceLayoutSha256':face_layout_sha(rows),'skinFaceIds':[0,2] if skin is None else skin,'garmentFaceIds':[1,3] if garment is None else garment,
            'ambiguousFaceIds':[],'boundaryCrossingFaceIds':[],
            'review':{'reviewed':True,'reviewedBy':'root','scope':'whole-face-material-ownership','notes':'Synthetic test fixture ownership, not a real pelvis selection.'}}


class PelvisPartitionTests(unittest.TestCase):
    def test_exact_attribute_binary_map_material_and_face_conservation(self):
        doc,blob,archive,_=fixture();original=copy.deepcopy(doc)
        new,binary,order,proof=partition(doc,blob,face_map(doc,blob))
        self.assertEqual(doc,original);self.assertEqual(binary[:len(blob)],blob)
        self.assertEqual(new['accessors'][:len(doc['accessors'])],doc['accessors'])
        self.assertEqual(new['bufferViews'][:len(doc['bufferViews'])],doc['bufferViews'])
        for key in ('images','textures'):self.assertEqual(new[key],doc[key])
        self.assertEqual(new['materials'],doc['materials']+[doc['materials'][0]])
        self.assertEqual(proof['materialRoles'],{0:'skin',1:'garment'})
        self.assertTrue(np.array_equal(order,[0,2,1,3]))
        old_faces=active_faces(doc,blob)[0][2]
        output_faces=np.concatenate([accessor(new,binary,p['indices']).reshape(-1,3) for p in new['meshes'][0]['primitives']])
        self.assertTrue(np.array_equal(output_faces,old_faces[order]))
        for prim in new['meshes'][0]['primitives']:
            self.assertEqual(prim['attributes'],doc['meshes'][0]['primitives'][0]['attributes'])
            for semantic,index in prim['attributes'].items():
                allow=semantic=='COLOR_0'
                self.assertTrue(np.array_equal(accessor(doc,blob,index,allow),accessor(new,binary,index,allow)))
        out=partition_archive(archive,active_faces(doc,blob),order,proof)
        for key in ('positions','normals','uvGltf','uvNative','sourcePositions','sourceNormals','sourceUVNative','tangents'):
            self.assertTrue(np.array_equal(out[key],archive[key][order]))
        self.assertTrue(np.array_equal(out['primitiveIds'],[0,0,1,1]))
        self.assertTrue(np.array_equal(out['sourceTriangleIds'],order))
        self.assertTrue(np.array_equal(out['sourceCornerOrder'],archive['sourceCornerOrder'][order]))
        self.assertFalse(proof['visibleMaterialBoundaryAccepted'])

    def test_exhaustive_and_explicit_review_failures(self):
        doc,blob,_,_=fixture();valid=face_map(doc,blob)
        changes=[('skinFaceIds',[0]),('skinFaceIds',[0,0,2]),('skinFaceIds',[0,1,2]),('garmentFaceIds',[1,4]),
                 ('garmentFaceIds',[1,-1]),('garmentFaceIds',[1,2**90]),('skinFaceIds',[0.0,2]),('garmentFaceIds',[]),('ambiguousFaceIds',[2]),('boundaryCrossingFaceIds',[1]),
                 ('primitiveFaceCounts',[5]),('primitiveFaceCounts',[4.0]),('automaticPixelClassificationAccepted',True),('sourceFaceLayoutSha256','wrong'),('faceIdSpace','generation-master-order')]
        for field,value in changes:
            bad=copy.deepcopy(valid);bad[field]=value
            with self.subTest(field=field,value=value),self.assertRaises(ValueError):partition(doc,blob,bad)
        for field,value in [('reviewed',False),('reviewedBy','automatic-pixel-classifier'),('notes',''),('scope','texture-color-guess'),('waiveAmbiguousFaces',True)]:
            bad=copy.deepcopy(valid);bad['review'][field]=value
            with self.subTest(review=field),self.assertRaises(ValueError):partition(doc,blob,bad)

    def test_garment_other_part_and_nonopaque_source_rejected(self):
        doc,blob,_,_=fixture()
        with self.assertRaisesRegex(ValueError,'only to pelvis'):partition(doc,blob,face_map(doc,blob),'chest')
        for change in ('BLEND','MASK','factor'):
            bad=copy.deepcopy(doc)
            if change=='factor':bad['materials'][0]['pbrMetallicRoughness']['baseColorFactor']=[1,1,1,.5]
            else:bad['materials'][0]['alphaMode']=change
            with self.subTest(change=change),self.assertRaisesRegex(ValueError,'already be opaque'):partition(bad,blob,face_map(bad,blob))

    def test_multiple_primitives_share_attributes_and_unique_role_materials(self):
        doc,blob,_,_=fixture();old=copy.deepcopy(doc['meshes'][0]['primitives'][0]);indices=accessor(doc,blob,old['indices']).reshape(-1,3)
        binary=bytearray(blob);primitives=[]
        for faces in (indices[:2],indices[2:]):
            values=faces.reshape(-1);offset=len(binary);binary.extend(values.tobytes());binary.extend(b'\0'*(-len(binary)%4))
            doc['bufferViews'].append({'buffer':0,'byteOffset':offset,'byteLength':values.nbytes})
            doc['accessors'].append({'bufferView':len(doc['bufferViews'])-1,'componentType':5123,'type':'SCALAR','count':len(values)})
            prim=copy.deepcopy(old);prim['indices']=len(doc['accessors'])-1;primitives.append(prim)
        doc['meshes'][0]['primitives']=primitives;doc['buffers'][0]['byteLength']=len(binary)
        new,_,order,proof=partition(doc,bytes(binary),face_map(doc,bytes(binary)))
        self.assertEqual(len(new['materials']),2);self.assertEqual(len(new['meshes'][0]['primitives']),4)
        self.assertTrue(np.array_equal(order,np.arange(4)))
        self.assertEqual(proof['materialRoles'],{0:'skin',1:'garment'})
        self.assertTrue(all(prim['attributes']==old['attributes'] for prim in new['meshes'][0]['primitives']))

    def test_changed_face_layout_and_incomplete_tangent_archive_rejected(self):
        doc,blob,archive,_=fixture();selection=face_map(doc,blob);changed=copy.deepcopy(doc)
        changed['meshes'][0]['primitives'][0]['material']=1;changed['materials'].append(copy.deepcopy(changed['materials'][0]))
        with self.assertRaisesRegex(ValueError,'face layout differs'):partition(changed,blob,selection)
        _,_,order,proof=partition(doc,blob,selection);rows=active_faces(doc,blob)
        bad=copy.deepcopy(archive);bad.pop('tangents')
        with self.assertRaisesRegex(ValueError,'tangent provenance'):partition_archive(bad,rows,order,proof)
        bad=copy.deepcopy(archive);bad['sourceTriangleIds']=np.array([1,0,2,3])
        with self.assertRaisesRegex(ValueError,'face/corner provenance'):partition_archive(bad,rows,order,proof)
        bad=copy.deepcopy(archive);bad['positions']=np.ones((4,3,4))
        with self.assertRaisesRegex(ValueError,'authoritative corner'):partition_archive(bad,rows,order,proof)
        bad=copy.deepcopy(archive);bad['unreviewedAttribute']=np.ones(4)
        with self.assertRaisesRegex(ValueError,'Known complete'):partition_archive(bad,rows,order,proof)

    def prepare(self,root,space='working',acceptance_scope='offline-rig-structure'):
        toolchain,migration=runtime_test_bindings(root)
        doc,blob=textured_fixture();source=root/'synthetic-generation.glb';write_glb(source,doc,blob)
        data=target_fixture();data['rig'].update(revision='synthetic-offline-frozen',pilotAccepted=True,offlineStructureAccepted=True,pilotAcceptanceScope=acceptance_scope)
        target=root/'target.json';target.write_text(json.dumps(data));job=root/'synthetic-job.json'
        job.write_text(json.dumps({'state':'success','promptId':'synthetic-unit-test-only','outputs':[{'localPath':str(source),'sha256':contract.sha(source)}]}))
        fit={'schemaVersion':2,'operation':'fit','part':'pelvis','coordinateSpace':'working','targetContract':str(target),'targetContractSha256':contract.sha(target),
             'source':str(source),'sourceSha256':contract.sha(source),'sourceReceipt':str(job),'sourceReceiptSha256':contract.sha(job),
             'uniformScale':.73,'rotationDegreesXYZ':[13,-7,29],'sourceAnchorNwn':[.03,.02,-.01],'targetAnchorLocal':[.01,-.04,-.02]}
        config=root/'fit.json';config.write_text(json.dumps(fit));parent_path=geometry_execute(config,root/'fit');parent=json.loads(parent_path.read_text())
        if space=='runtime':
            runtime={'schemaVersion':2,'operation':'runtime','part':'pelvis','coordinateSpace':'runtime','targetContract':str(target),'targetContractSha256':contract.sha(target),
                     'source':parent['candidate'],'sourceSha256':parent['candidateSha256'],'sourceReceipt':str(parent_path),'sourceReceiptSha256':contract.sha(parent_path)}
            config=root/'runtime.json';config.write_text(json.dumps(runtime));parent_path=geometry_execute(config,root/'runtime');parent=json.loads(parent_path.read_text())
        fitted=Path(parent['candidate']);selection=face_map(*read_glb(fitted));evidence=root/'synthetic-review.txt';evidence.write_text('Synthetic face ownership fixture; no production pelvis selected.')
        selection.update(schemaVersion=2,kind='target-pelvis-material-face-map',diagnosticOnly=True,part='pelvis',joint='pelvis_g',model='pmg0_pelvis001',
                         source=str(fitted),sourceSha256=contract.sha(fitted),sourceReceipt=str(parent_path),sourceReceiptSha256=contract.sha(parent_path),**contract.binding(target,data,space))
        selection['review']['evidence']=[{'path':str(evidence),'sha256':contract.sha(evidence)}]
        face_path=root/'synthetic-reviewed-map.json';face_path.write_text(json.dumps(selection))
        partition_config={'schemaVersion':2,'kind':'target-pelvis-material-partition','diagnosticOnly':True,'part':'pelvis','coordinateSpace':space,
                         'targetContract':str(target),'targetContractSha256':contract.sha(target),'source':str(fitted),'sourceSha256':contract.sha(fitted),
                         'sourceReceipt':str(parent_path),'sourceReceiptSha256':contract.sha(parent_path),'faceMap':str(face_path),'faceMapSha256':contract.sha(face_path),
                         'sharedToolchain':str(toolchain),'sharedToolchainSha256':contract.sha(toolchain),'migrationReceipt':str(migration),'migrationReceiptSha256':contract.sha(migration)}
        path=root/'partition-config.json';path.write_text(json.dumps(partition_config))
        return path,target,parent_path,parent,face_path

    def test_noncanonical_or_broader_acceptance_scopes_rejected(self):
        for scope in ('rigStructureOffline','offline-rig-structure-only','production',None):
            with self.subTest(scope=scope), tempfile.TemporaryDirectory() as temporary:
                root=Path(temporary)
                config,_,_,_,_=self.prepare(root,acceptance_scope=scope)
                with patch('partition_target_pelvis_materials.ARTIFACT_ROOT',root),self.assertRaisesRegex(ValueError,'frozen offline structural target'):
                    execute(config,root/'must-not-exist')
                self.assertFalse((root/'must-not-exist').exists())

    def test_working_receipt_conserves_corners_and_existing_stage_accepts_roles(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);config,target,parent_path,parent,_=self.prepare(root)
            with patch('partition_target_pelvis_materials.ARTIFACT_ROOT',root):path=execute(config,root/'partition')
            receipt=json.loads(path.read_text());self.assertEqual(receipt['operation'],'material-partition');self.assertEqual(receipt['statureApplications'],0)
            self.assertEqual(receipt['sourceToAttachmentLocal'],np.eye(4).tolist());self.assertFalse(receipt['materialBindingsAccepted'])
            self.assertFalse(receipt['visibleMaterialBoundaryAccepted']);self.assertFalse(receipt['productionAccepted']);self.assertFalse(receipt['clientAccepted'])
            for name in receipt['frozenInputs']:self.assertEqual(contract.sha(name),receipt['frozenInputs'][name])
            staging={'schemaVersion':2,'kind':'target-part-stage','diagnosticOnly':True,'part':'pelvis','coordinateSpace':'working',
                     'targetContract':str(target),'targetContractSha256':contract.sha(target),'source':receipt['candidate'],'sourceSha256':receipt['candidateSha256'],
                     'sourceReceipt':str(path),'sourceReceiptSha256':contract.sha(path),'materialRoles':receipt['materialRoles'],'aoStrength':0}
            stage_config=root/'stage.json';stage_config.write_text(json.dumps(staging));staged=stage(stage_config,root/'stage')
            result=json.loads(staged.read_text());self.assertEqual(set(result['rawAttributeAsciiProof']),{'skin','garment'})
            skin=(root/'stage/resources/pmg0_pelvis001.mtr').read_text();garment=(root/'stage/resources/pmg0_pelvis001f.mtr').read_text()
            self.assertNotIn('texture0',skin);self.assertIn('texture0 pmg0_pelvis001f',garment)
            self.assertFalse(result['clientAccepted'])

    def test_runtime_parent_count_and_double_precision_attributes_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);config,_,_,parent,_=self.prepare(root,'runtime')
            with patch('partition_target_pelvis_materials.ARTIFACT_ROOT',root):path=execute(config,root/'partition')
            receipt=json.loads(path.read_text());self.assertEqual(receipt['statureApplications'],1)
            self.assertEqual(receipt['attachmentWorld'],parent['attachmentWorld'])
            with np.load(parent['nativeCornerArchive']['path']) as old,np.load(receipt['nativeCornerArchive']['path']) as new:
                order=new['parentTriangleIds']
                for key in ('positions','normals','uvGltf','uvNative','tangents'):self.assertTrue(np.array_equal(new[key],old[key][order]))
            self.assertFalse(receipt['proof']['positionsNormalsUvsTangentsColorsChanged'])

    def test_stale_parent_map_old_rig_wrong_part_and_missing_review_rejected_before_write(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);config,target,parent_path,parent,face_path=self.prepare(root)
            base=json.loads(config.read_text())
            for field,value in [('part','handl'),('sourceSha256','wrong'),('faceMapSha256','wrong')]:
                bad=copy.deepcopy(base);bad[field]=value;config.write_text(json.dumps(bad))
                with self.subTest(field=field),patch('partition_target_pelvis_materials.ARTIFACT_ROOT',root),self.assertRaises(ValueError):execute(config,root/'must-not-exist')
                self.assertFalse((root/'must-not-exist').exists())
            selection=json.loads(face_path.read_text());selection['review']['evidence']=[];face_path.write_text(json.dumps(selection));base['faceMapSha256']=contract.sha(face_path);config.write_text(json.dumps(base))
            with patch('partition_target_pelvis_materials.ARTIFACT_ROOT',root),self.assertRaisesRegex(ValueError,'review evidence'):execute(config,root/'must-not-exist')
            data=json.loads(target.read_text());data['rig']['offlineStructureAccepted']=False;target.write_text(json.dumps(data));base['targetContractSha256']=contract.sha(target);config.write_text(json.dumps(base))
            with patch('partition_target_pelvis_materials.ARTIFACT_ROOT',root),self.assertRaisesRegex(ValueError,'New frozen'):execute(config,root/'must-not-exist')


if __name__=='__main__':unittest.main()

