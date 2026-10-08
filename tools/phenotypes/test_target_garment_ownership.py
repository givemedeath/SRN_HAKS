"""Reviewed categorical garment boundaries preserve original GLB attributes/maps."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
from PIL import Image

import target_contract as contract
from place_purposebuilt_pelvis import accessor, raw_corners, read_glb, write_glb
from target_garment_ownership import apply, measure_uv_faces, partition, proposal
from target_part_pipeline import execute, verify_source_receipt
from target_part_stage import image_pixels, stage
from test_human_female_stock_exact import stock_fixture
from test_mirror_stock_limb_part import fixture
from test_target_part_stage import textured_fixture


def two_faces():
    doc, original = textured_fixture(); binary = bytearray(original)
    arrays = {
        'POSITION': (np.asarray([[0,0,0],[.1,0,0],[0,.1,0],[.2,0,0],[.3,0,0],[.2,.1,0]], dtype='<f4'), 'VEC3', 5126),
        'NORMAL': (np.tile(np.asarray([0,0,1.3], dtype='<f4'), (6,1)), 'VEC3', 5126),
        'TEXCOORD_0': (np.asarray([[.05,.05],[.15,.05],[.05,.15],[.8,.8],[.95,.8],[.8,.95]], dtype='<f4'), 'VEC2', 5126),
        'TANGENT': (np.tile(np.asarray([1.2,0,0,-1], dtype='<f4'), (6,1)), 'VEC4', 5126),
        'COLOR_0': (np.tile(np.asarray([43,91,201,255], dtype='u1'), (6,1)), 'VEC4', 5121),
        'indices': (np.arange(6, dtype='<u2'), 'SCALAR', 5123),
    }
    references = {}
    for name, (values, kind, component) in arrays.items():
        binary.extend(b'\0'*(-len(binary)%4)); offset = len(binary); binary.extend(values.tobytes())
        doc['bufferViews'].append({'buffer':0, 'byteOffset':offset, 'byteLength':values.nbytes})
        row = {'bufferView':len(doc['bufferViews'])-1, 'count':len(values), 'type':kind, 'componentType':component}
        if name == 'COLOR_0': row['normalized'] = True
        doc['accessors'].append(row); references[name] = len(doc['accessors'])-1
    doc['meshes'][0]['primitives'] = [{'attributes':{name:index for name,index in references.items() if name != 'indices'},
                                      'indices':references['indices'], 'material':0}]
    binary.extend(b'\0'*(-len(binary)%4)); doc['buffers'][0]['byteLength'] = len(binary)
    return doc, bytes(binary)


class GarmentOwnershipTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        self.target_path, self.target = stock_fixture(self.root)
        source = self.root/'raw.glb'; write_glb(source, *two_faces())
        job = self.root/'job.json'; job.write_text(json.dumps({'state':'success', 'promptId':'test',
            'outputs':[{'localPath':str(source), 'sha256':contract.sha(source)}]}))
        fit = {'schemaVersion':2, 'operation':'fit', 'part':'chest', 'coordinateSpace':'working',
            'targetContract':str(self.target_path), 'targetContractSha256':contract.sha(self.target_path),
            'source':str(source), 'sourceSha256':contract.sha(source), 'sourceReceipt':str(job),
            'sourceReceiptSha256':contract.sha(job), 'uniformScale':.7, 'rotationDegreesXYZ':[11,3,-7],
            'sourceAnchorNwn':[0,0,0], 'targetAnchorLocal':[0,0,0]}
        config = self.root/'fit.json'; config.write_text(json.dumps(fit))
        self.parent_path = execute(config, self.root/'fitted'); self.parent = json.loads(self.parent_path.read_text())
        mask = np.zeros((2048,2048), dtype=np.uint8); mask[:,1024:] = 255
        self.mask_path = self.root/'review-mask.png'; Image.fromarray(mask).save(self.mask_path)
        self.base = {'schemaVersion':2, 'diagnosticOnly':True, 'part':'chest', 'coordinateSpace':'working',
            'targetContract':str(self.target_path), 'targetContractSha256':contract.sha(self.target_path),
            'source':self.parent['candidate'], 'sourceSha256':self.parent['candidateSha256'],
            'sourceReceipt':str(self.parent_path), 'sourceReceiptSha256':contract.sha(self.parent_path)}

    def tearDown(self): self.tmp.cleanup()

    def propose(self, values=None, name='proposal'):
        config = {**self.base, 'kind':'target-garment-mask-proposal', 'filterRadiusPixels':1,
                  'ownershipMask':{'path':str(self.mask_path), 'sha256':contract.sha(self.mask_path)}}
        if values: config.update(values)
        path = self.root/(name+'.json'); path.write_text(json.dumps(config))
        result = proposal(path, self.root/name)
        return result, json.loads(result.read_text())

    def review_config(self, proposal_path, proposed, name='selection'):
        # Explicit review fixtures test protocol guards; the tool never creates approval.
        review = {key:proposed[key] for key in ('targetContract','targetContractSha256','targetId','rigRevision',
            'coordinateSpace','part','model','source','sourceSha256','sourceReceipt','sourceReceiptSha256','ownershipMask')}
        review.update(schemaVersion=2, kind='target-garment-mask-review', accepted=True, decision='approved-face-ownership',
            reviewer='independent test fixture', notes='Explicit categorical face ownership reviewed for this fixture.',
            proposalReceipt={'path':str(proposal_path), 'sha256':contract.sha(proposal_path)}, faceRoles=proposed['faceRoles'],
            reviewedViews=['front','rear','side','uv-mask'], reviewEvidence=[{'path':str(self.mask_path), 'sha256':contract.sha(self.mask_path)}])
        selection = self.root/(name+'.json'); selection.write_text(json.dumps(review))
        config = {**self.base, 'kind':'target-garment-mask-apply', 'proposalReceipt':str(proposal_path),
                  'proposalReceiptSha256':contract.sha(proposal_path), 'selectionReceipt':str(selection),
                  'selectionReceiptSha256':contract.sha(selection), 'maxOutputPrimitives':16}
        return config, selection, review

    def apply_config(self, config, name='owned'):
        path = self.root/(name+'.json'); path.write_text(json.dumps(config))
        result = apply(path, self.root/name)
        return result, json.loads(result.read_text())

    def test_full_reviewed_partition_preserves_bin_attributes_uvs_and_map_pixels(self):
        path, proposed = self.propose()
        self.assertFalse(proposed['accepted']); self.assertTrue(proposed['readyForIndependentReview'])
        pending=json.loads((path.parent/'pending-review-template.json').read_text())
        self.assertFalse(pending['accepted']);self.assertEqual(pending['decision'],'pending')
        self.assertEqual(proposed['faceRoles'], ['skin','garment'])
        config, _, _ = self.review_config(path, proposed)
        result_path, record = self.apply_config(config)
        before, binary = read_glb(self.parent['candidate']); after, output = read_glb(record['candidate'])
        self.assertEqual(binary, output)
        self.assertEqual(after['materials'][:len(before['materials'])], before['materials'])
        self.assertEqual(after['images'], before['images']); self.assertEqual(after['textures'], before['textures'])
        self.assertEqual(after['accessors'][:len(before['accessors'])], before['accessors'])
        for material in after['materials'][len(before['materials']):]: self.assertEqual(material, before['materials'][0])
        old_extra, new_extra = {}, {}
        old = raw_corners(before, binary, extra=old_extra); new = raw_corners(after, output, extra=new_extra)
        for original, copied in zip(old[:3], new[:3]): np.testing.assert_array_equal(original, copied)
        for semantic in ('TANGENT','COLOR_0'):
            np.testing.assert_array_equal(np.concatenate(old_extra[semantic]['rows']), np.concatenate(new_extra[semantic]['rows']))
        for binding in (before['materials'][0]['normalTexture'], before['materials'][0]['pbrMetallicRoughness']['baseColorTexture'],
                        before['materials'][0]['pbrMetallicRoughness']['metallicRoughnessTexture']):
            np.testing.assert_array_equal(image_pixels(before,binary,binding), image_pixels(after,output,binding))
        with np.load(self.parent['nativeCornerArchive']['path']) as old_archive, np.load(record['nativeCornerArchive']['path']) as new_archive:
            for key in old_archive.files:
                if key != 'primitiveIds': np.testing.assert_array_equal(old_archive[key], new_archive[key])
        verify_source_receipt(Path(record['candidate']), result_path, self.target_path, self.target, 'chest', 'working')
        self.assertEqual(record['statureApplications'], 0); self.assertFalse(record['clientAccepted'])
        staging = {**self.base, 'kind':'target-part-stage', 'source':record['candidate'],
            'sourceSha256':record['candidateSha256'], 'sourceReceipt':str(result_path),
            'sourceReceiptSha256':contract.sha(result_path), 'materialRoles':record['materialRoles']}
        stage_path = self.root/'stage.json'; stage_path.write_text(json.dumps(staging))
        staged = stage(stage_path,self.root/'stage'); self.assertTrue(staged.exists())

    def test_interleaved_partition_keeps_original_global_triangle_order(self):
        doc, binary = fixture(); labels = ['skin','garment','skin','garment']
        after, roles, ids = partition(doc,binary,labels,4)
        self.assertEqual(len(after['meshes'][0]['primitives']),4)
        self.assertEqual(ids.tolist(),[0,1,2,3]); self.assertEqual(set(roles.values()), {'skin','garment'})
        for a,b in zip(raw_corners(doc,binary)[:3],raw_corners(after,binary)[:3]): np.testing.assert_array_equal(a,b)
        with self.assertRaisesRegex(ValueError,'budget'): partition(doc,binary,labels,3)
        with self.assertRaisesRegex(ValueError,'ownership'): partition(doc,binary,labels[:-1],4)

    def test_mixed_or_unknown_mask_cannot_be_waived_by_review(self):
        mask = np.asarray(Image.open(self.mask_path)).copy(); mask[:1024,:1024] = 127
        Image.fromarray(mask).save(self.mask_path)
        path, proposed = self.propose(); self.assertFalse(proposed['readyForIndependentReview'])
        config, _, _ = self.review_config(path,proposed)
        with self.assertRaisesRegex(ValueError,'topology descendant'): self.apply_config(config)
        simple = np.zeros((8,8),dtype=np.uint8); simple[:,4:] = 255
        _, _, issues = measure_uv_faces(np.asarray([[[.4,.2],[.6,.2],[.4,.8]]]),simple,1)
        self.assertEqual(issues[0]['reason'],'mixed-skin-garment-footprint')

    def test_interior_boundary_cannot_hide_behind_pure_vertex_samples(self):
        mask=np.zeros((8,8),dtype=np.uint8);mask[2,2]=255
        _, counts, issues=measure_uv_faces(np.asarray([[[.1,.1],[.9,.1],[.1,.9]]]),mask,1)
        self.assertEqual(issues[0]['reason'],'mixed-skin-garment-footprint')
        self.assertGreater(counts[0,0],0);self.assertGreater(counts[0,2],0)

    def test_complete_face_roles_and_separate_approval_are_required(self):
        path, proposed = self.propose(); config, selection, review = self.review_config(path,proposed)
        for change, message in [({'accepted':False},'reviewed face'), ({'faceRoles':['skin']},'completely own'),
            ({'reviewedViews':['uv-mask']},'review evidence')]:
            bad = {**review, **change}; selection.write_text(json.dumps(bad)); config['selectionReceiptSha256'] = contract.sha(selection)
            with self.subTest(change=change), self.assertRaisesRegex(ValueError,message): self.apply_config(config)

    def test_stale_mask_receipt_and_cross_target_selection_are_rejected(self):
        path, proposed = self.propose(); config, selection, review = self.review_config(path,proposed)
        review['targetId']='another-female'; selection.write_text(json.dumps(review)); config['selectionReceiptSha256']=contract.sha(selection)
        with self.assertRaisesRegex(ValueError,'another target'): self.apply_config(config)
        config, selection, review = self.review_config(path,proposed)
        self.mask_path.write_bytes(self.mask_path.read_bytes()+b'changed')
        with self.assertRaisesRegex(ValueError,'Frozen input changed'): self.apply_config(config)
        self.assertFalse((self.root/'owned').exists())

    def test_non_owner_and_unbounded_filtering_are_rejected(self):
        with self.assertRaisesRegex(ValueError,'chest/pelvis'): self.propose({'part':'handl'})
        with self.assertRaisesRegex(ValueError,'one pixel'): self.propose({'filterRadiusPixels':0})

    def test_color_proposal_remains_unapproved_and_cannot_invent_cloth(self):
        config = {**self.base, 'kind':'target-garment-mask-proposal',
                  'diagnosticColorRule':{'garmentMaxChannel':64,'skinMinChannel':112}}
        path=self.root/'color.json';path.write_text(json.dumps(config))
        result=proposal(path,self.root/'color');record=json.loads(result.read_text())
        self.assertFalse(record['accepted']);self.assertFalse(record['readyForIndependentReview'])
        self.assertEqual(set(record['faceRoles']),{'skin'})


if __name__ == '__main__': unittest.main()
