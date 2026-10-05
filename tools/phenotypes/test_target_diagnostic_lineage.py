"""Diagnostic lineage rejection tests: real indexed storage, not a permissive mock."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

import target_contract as contract
from place_purposebuilt_pelvis import accessor
from pose_preview_target_parts import select_preview_receipts, select_receipts
from target_diagnostic_lineage import (ARCHIVE_KEYS, FLAGS, KIND, OPERATION, PREVIEW_SCOPE, ROLES,
    SCOPE, decode_active, fingerprint, no_acceptance, pin, load_archive, verify_audits, verify_preserved_child, verify_receipt)
from target_part_pipeline import verify_source_receipt
from test_target_part_pipeline import target_fixture


def indexed_fixture(space='working'):
    """Two unedited body faces plus two neutral caps and one inactive bad row."""
    binary = bytearray(); views = []; accessors = []
    def append(value, kind):
        binary.extend(b'\0'*(-len(binary)%4)); offset = len(binary); binary.extend(value.tobytes())
        views.append({'buffer': 0, 'byteOffset': offset, 'byteLength': value.nbytes})
        accessors.append({'bufferView': len(views)-1, 'componentType': 5126 if value.dtype.kind == 'f' else 5125,
                          'count': len(value), 'type': kind})
        return len(accessors)-1
    p = np.asarray([[0,0,0],[1,0,0],[0,1,0],[1,1,0],[0,0,1]], '<f4')
    n = np.tile(np.asarray([0,0,1.2], '<f4'), (5,1)); n[-1] = [0,0,1e-13]
    uv = np.asarray([[.1,.2],[.9,.2],[.1,.8],[.9,.8],[.5,.5]], '<f4')
    t = np.tile(np.asarray([1.1,0,0,-1], '<f4'), (5,1))
    attrs = {key: append(value, kind) for key, value, kind in
             [('POSITION',p,'VEC3'),('NORMAL',n,'VEC3'),('TEXCOORD_0',uv,'VEC2'),('TANGENT',t,'VEC4')]}
    # The parent has six body faces. The four reviewed faces alone reference row4.
    parent_ids = np.asarray([[0,1,2],[0,4,1],[1,4,2],[1,3,2],[2,4,3],[3,4,0]], '<u4')
    body_index = append(parent_ids.reshape(-1), 'SCALAR')
    primitives = [{'attributes': attrs, 'indices': body_index, 'material': 0}]
    for sign in (1,-1):
        cap_p = np.asarray([[0,0,.2*sign],[.5,0,.2*sign],[0,.5,.2*sign]], '<f4')
        cap_attrs = {key: append(value, kind) for key, value, kind in
                     [('POSITION',cap_p,'VEC3'),('NORMAL',n[:3],'VEC3'),('TEXCOORD_0',uv[:3],'VEC2'),('TANGENT',t[:3],'VEC4')]}
        primitives.append({'attributes':cap_attrs,'indices':append(np.asarray([0,1,2],'<u4'),'SCALAR'),'material':1})
    image = b'exact authored image bytes'; binary.extend(b'\0'*(-len(binary)%4))
    views.append({'buffer':0,'byteOffset':len(binary),'byteLength':len(image)});binary.extend(image)
    binary.extend(b'\0'*(-len(binary)%4))
    parent_doc = {'asset':{'version':'2.0'},'buffers':[{'byteLength':len(binary)}],
        'bufferViews':copy.deepcopy(views),'accessors':copy.deepcopy(accessors),
        'nodes':[{'mesh':0}] if space == 'source' else [{'name':'detached_geometry','mesh':0}],
        'scenes':[{'nodes':[0]}],'scene':0,'meshes':[{'primitives':copy.deepcopy(primitives)}],
        'images':[{'mimeType':'image/png','bufferView':len(views)-1}], 'textures':[{'source':0}],
        'materials':[{'pbrMetallicRoughness':{'baseColorTexture':{'index':0}}},
                     {'alphaMode':'OPAQUE','extras':{'diagnosticOnly':True,'materialAccepted':False},
                      'pbrMetallicRoughness':{'baseColorFactor':[.36,.36,.36,1]}}]}
    parent_binary=bytes(binary); keep=np.asarray([True,False,False,True,False,False])
    new_index=append(parent_ids[keep].reshape(-1),'SCALAR')
    doc=copy.deepcopy(parent_doc);doc['bufferViews']=views;doc['accessors']=accessors
    doc['buffers']=[{'byteLength':len(binary)}];doc['meshes'][0]['primitives'][0]['indices']=new_index
    blob=bytes(binary);original_ids=np.asarray([0,3],dtype=np.int64)
    archive={key:np.concatenate([accessor(doc,blob,primitive['attributes'][key])[
        accessor(doc,blob,primitive['indices']).reshape(-1,3)] for primitive in doc['meshes'][0]['primitives']]) for key in
        ('POSITION','NORMAL','TEXCOORD_0','TANGENT')}
    archive.update(primitiveIds=np.asarray([0,0,1,2],dtype=np.int64),materialIds=np.asarray([0,0,1,1],dtype=np.int64),
                   sourceOriginalFaceIds=np.asarray([0,3,-1,-1],dtype=np.int64))
    mapping={space+'_primitive'+str(i)+'ReferencedOriginalAccessorRows':np.unique(accessor(doc,blob,p['indices'])).astype(np.int64)
             for i,p in enumerate(doc['meshes'][0]['primitives'])}
    return doc,blob,parent_doc,parent_binary,keep,archive,original_ids,mapping


class ActiveStorageTests(unittest.TestCase):
    def test_index_only_child_preserves_all_stored_rows_and_both_caps(self):
        doc,blob,parent,parent_blob,keep,archive,ids,mapping=indexed_fixture()
        before=copy.deepcopy(doc);binary_before=bytes(blob)
        verify_preserved_child(doc,blob,parent,parent_blob,keep)
        rows=decode_active(doc,blob,archive,ids,mapping,'working')
        self.assertEqual(rows[0]['storedAttributeRows'],5);self.assertEqual(rows[0]['referencedRows'],4)
        self.assertEqual(rows[0]['storedNearZeroNormalRows'],[4]);self.assertEqual(rows[0]['inactiveRows'],1)
        self.assertEqual(rows[0]['inactiveNormalRawFloat32Hex']['4'],accessor(doc,blob,1)[4].tobytes().hex())
        self.assertEqual([r['triangles'] for r in rows],[2,1,1]);self.assertEqual(doc,before);self.assertEqual(blob,binary_before)

    def test_source_and_working_layouts_are_distinct_and_never_transformed(self):
        for space in ('source','working'):
            doc,blob,_,_,_,archive,ids,mapping=indexed_fixture(space)
            decode_active(doc,blob,archive,ids,mapping,space)
            with self.assertRaisesRegex(ValueError,'layout'):
                decode_active(doc,blob,archive,ids,mapping,'source' if space=='working' else 'working')
        doc,blob,_,_,_,archive,ids,mapping=indexed_fixture()
        doc['nodes'][0]['scale']=[.54,.54,.54]
        with self.assertRaisesRegex(ValueError,'layout'):decode_active(doc,blob,archive,ids,mapping,'working')

    def test_rejects_mutated_inactive_normal_bytes_without_any_active_corner_change(self):
        doc,blob,parent,parent_blob,keep,archive,ids,mapping=indexed_fixture()
        data=bytearray(blob);view=doc['bufferViews'][doc['accessors'][1]['bufferView']]
        data[view['byteOffset']+4*12+8]^=1
        self.assertTrue(np.array_equal(accessor(doc,blob,1)[:4],accessor(doc,bytes(data),1)[:4]))
        with self.assertRaisesRegex(ValueError,'BIN prefix'):verify_preserved_child(doc,bytes(data),parent,parent_blob,keep)

    def test_rejects_reference_to_preserved_bad_normal_even_with_forged_row_inventory(self):
        doc,blob,_,_,_,archive,ids,mapping=indexed_fixture();data=bytearray(blob)
        ix=doc['meshes'][0]['primitives'][0]['indices'];offset=doc['bufferViews'][doc['accessors'][ix]['bufferView']]['byteOffset']
        data[offset:offset+4]=np.asarray([4],'<u4').tobytes();mapping['working_primitive0ReferencedOriginalAccessorRows']=np.asarray([1,2,3,4])
        with self.assertRaisesRegex(ValueError,'near-zero'):decode_active(doc,bytes(data),archive,ids,mapping,'working')

    def test_rejects_forged_active_inventory_and_wrong_corner_provenance(self):
        for mutation in ('inventory','sourceIds','primitiveIds','materialIds','cornerOrder','precision'):
            with self.subTest(mutation=mutation):
                doc,blob,_,_,_,archive,ids,mapping=indexed_fixture()
                if mutation=='inventory':mapping['working_primitive0ReferencedOriginalAccessorRows']=np.asarray([0,1,2])
                elif mutation=='sourceIds':archive['sourceOriginalFaceIds'][0]=1
                elif mutation in ('primitiveIds','materialIds'):archive[mutation][0]=1
                elif mutation=='cornerOrder':archive['POSITION'][0]=archive['POSITION'][0,[0,2,1]]
                else:archive['POSITION']=archive['POSITION'].astype(np.float64)
                with self.assertRaises(ValueError):decode_active(doc,blob,archive,ids,mapping,'working')

    def test_rejects_active_tangent_degeneracy_ambiguous_sign_and_unknown_geometry(self):
        for tangent in ([0,0,0,1],[0,0,1,1],[1,0,0,0],[1,0,0,.5]):
            with self.subTest(tangent=tangent):
                doc,blob,_,_,_,archive,ids,mapping=indexed_fixture();data=bytearray(blob)
                offset=doc['bufferViews'][doc['accessors'][3]['bufferView']]['byteOffset']
                data[offset:offset+16]=np.asarray(tangent,'<f4').tobytes()
                with self.assertRaisesRegex(ValueError,'tangent'):decode_active(doc,bytes(data),archive,ids,mapping,'working')
        doc,blob,_,_,_,archive,ids,mapping=indexed_fixture();doc['meshes'][0]['primitives'][0]['attributes']['COLOR_0']=2
        with self.assertRaisesRegex(ValueError,'Unsupported'):decode_active(doc,blob,archive,ids,mapping,'working')

    def test_rejects_cap_and_material_map_mutations_or_extra_index_removal(self):
        for mutation in ('cap','material','image','oldAccessor','indices'):
            with self.subTest(mutation=mutation):
                doc,blob,parent,parent_blob,keep,_,_,_=indexed_fixture()
                if mutation=='cap':doc['meshes'][0]['primitives'][1]['material']=0
                elif mutation=='material':doc['materials'][1]['extras']['materialAccepted']=True
                elif mutation=='image':doc['images'][0]['mimeType']='image/jpeg'
                elif mutation=='oldAccessor':doc['accessors'][0]['count']-=1
                else:keep=np.asarray([True,False,False,False,False,True])
                with self.assertRaises(ValueError):verify_preserved_child(doc,blob,parent,parent_blob,keep)

    def test_caps_cannot_be_declared_skin_or_final_material(self):
        doc,blob,_,_,_,archive,ids,mapping=indexed_fixture()
        doc['materials'][1]['normalTexture']={'index':0}
        with self.assertRaisesRegex(ValueError,'neutral'):decode_active(doc,blob,archive,ids,mapping,'working')


class ScopeAndChannelTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.target=target_fixture();self.target['rig'].update(pilotAccepted=True,offlineStructureAccepted=True,
                                                               pilotAcceptanceScope='offline-rig-structure')
        self.target_path=self.root/'target.json';self.target_path.write_text(json.dumps(self.target))
        self.receipt={'schemaVersion':2,'kind':KIND,'operation':OPERATION,'previewScope':PREVIEW_SCOPE,'diagnosticOnly':True,
            **contract.binding(self.target_path,self.target,'working'),'part':'pelvis','joint':'pelvis_g','model':'pmg0_pelvis001',
            'statureApplications':0,'primitiveRoleStatus':copy.deepcopy(ROLES),'candidateToAttachmentLocal':np.eye(4).tolist(),
            'attachmentWorld':contract.frame(self.target,'pelvis_g').tolist(),**{flag:False for flag in FLAGS}}
        self.path=self.root/'diagnostic.json'
        self.assembly={'schemaVersion':2,'kind':'target-stock-diagnostic','target':contract.binding(self.target_path,self.target,'working'),
            'parts':[{'part':p,'model':m} for p,m in self.target['models'].items()],
            'resources':{m+'.mdl':'pin' for m in self.target['models'].values()}}
    def tearDown(self):self.tmp.cleanup()
    def verify(self,data=None,space='working'):
        self.path.write_text(json.dumps(data or self.receipt))
        return verify_receipt(self.path,self.target_path,self.target,space)

    def test_rejects_every_nonpreview_gate_and_nested_acceptance(self):
        for flag in FLAGS:
            with self.subTest(flag=flag):
                row=copy.deepcopy(self.receipt);row[flag]=True
                with self.assertRaisesRegex(ValueError,'gate'):self.verify(row)
        with self.assertRaisesRegex(ValueError,'acceptance'):no_acceptance({'pending':{'materialAccepted':True}})

    def test_rejects_runtime_second_scaling_fit_reapplication_and_changed_attachment(self):
        with self.assertRaisesRegex(ValueError,'working preview'):self.verify(space='runtime')
        for key,value in [('statureApplications',1),('coordinateSpace','runtime'),('rigRevision','stale'),
                          ('candidateToAttachmentLocal',np.diag([.54,.54,.54,1]).tolist()),
                          ('attachmentWorld',np.diag([1,1,1,2]).tolist()),('part','legl'),('joint','lthigh_g')]:
            with self.subTest(key=key):
                row=copy.deepcopy(self.receipt);row[key]=value
                with self.assertRaises(ValueError):self.verify(row)

    def test_requires_exact_frozen_structure_scope_and_explicit_root_declaration(self):
        for scope in ('rigStructureOffline','production',None):
            self.target['rig']['pilotAcceptanceScope']=scope
            with self.assertRaisesRegex(ValueError,'Frozen offline'):self.verify()
        self.target['rig']['pilotAcceptanceScope']='offline-rig-structure'
        review=self.root/'review.json'
        review.write_text(json.dumps({'schemaVersion':2,'kind':'target-diagnostic-preview-root-review',
            'scope':'production','reviewed':True,'reviewedBy':'/root','authorizeDiagnosticPreview':True}))
        row=copy.deepcopy(self.receipt);row['rootReview']={'path':str(review),'sha256':contract.sha(review)}
        with self.assertRaisesRegex(ValueError,'root review'):self.verify(row)
        row['rootReview']['sha256']='wrong'
        with self.assertRaisesRegex(ValueError,'evidence changed'):self.verify(row)

    def test_canonical_preview_and_pipeline_continue_rejecting_diagnostic_kind(self):
        self.path.write_text(json.dumps(self.receipt))
        with self.assertRaisesRegex(ValueError,'target-part-geometry'):
            select_receipts([self.path],self.target_path,self.target,'working',self.assembly)
        with self.assertRaisesRegex(ValueError,'Target geometry receipt'):
            verify_source_receipt(self.root/'candidate.glb',self.path,self.target_path,self.target,'pelvis','working')
        with self.assertRaisesRegex(ValueError,'diagnostic preview'):
            row=copy.deepcopy(self.receipt);row['kind']='target-part-geometry';self.verify(row)

    def test_pinned_source_parent_fit_audit_and_archives_reject_changed_bytes(self):
        for role in ('originalSource','boundedConnectorParent','properTargetFit','independentDecode',
                     'childMapping','parentMapping','activeSerializedCornerArchive','capLeftGenerator'):
            with self.subTest(role=role):
                item_path=self.root/(role+'.bin');item_path.write_bytes(b'frozen source evidence')
                item={'path':str(item_path),'sha256':contract.sha(item_path)}
                inputs={};pin(item,inputs);self.assertEqual(inputs[str(item_path)],item['sha256'])
                item_path.write_bytes(b'changed source evidence')
                with self.assertRaisesRegex(ValueError,'evidence changed'):pin(item,{})
        item_path=self.root/'active.npz';np.savez(item_path,POSITION=np.zeros((1,3,3),np.float32))
        item={'path':str(item_path),'sha256':contract.sha(item_path)}
        self.assertEqual(load_archive(item,{})['POSITION'].dtype,np.float32)
        np.savez(item_path,POSITION=np.ones((1,3,3),np.float32))
        with self.assertRaisesRegex(ValueError,'evidence changed'):load_archive(item,{})

    def test_fingerprint_preserves_sign_bit_and_precision_not_just_numerical_equality(self):
        positive=np.asarray([0.],np.float32);negative=np.asarray([-0.],np.float32)
        self.assertTrue(np.array_equal(positive,negative));self.assertNotEqual(fingerprint(positive),fingerprint(negative))
        self.assertNotEqual(fingerprint(positive),fingerprint(positive.astype(np.float64)))

    def test_separate_selector_does_not_change_empty_canonical_result(self):
        canonical=select_receipts([],self.target_path,self.target,'working',self.assembly)
        result=select_preview_receipts([],[],self.target_path,self.target,'working',self.assembly)
        self.assertEqual(canonical,result);self.assertNotIn('diagnosticReceipts',result)

    def test_duplicate_ownership_rejected_and_diagnostic_provenance_retained(self):
        row={'part':'pelvis','candidate':str(self.root/'candidate.glb'),'inputs':{'exact-child':'hash'},
             'pendingGates':{flag:False for flag in FLAGS},'primitiveRoleStatus':copy.deepcopy(ROLES)}
        with patch('target_diagnostic_lineage.verify_receipt',return_value=copy.deepcopy(row)):
            result=select_preview_receipts([],['diagnostic'],self.target_path,self.target,'working',self.assembly)
        self.assertEqual(result['diagnosticParts'],['pelvis']);self.assertEqual(result['inputs']['exact-child'],'hash')
        self.assertEqual(result['diagnosticReceipts'][0]['primitiveRoleStatus'],ROLES)
        with patch('target_diagnostic_lineage.verify_receipt',side_effect=lambda *a:copy.deepcopy(row)):
            with self.assertRaisesRegex(ValueError,'Duplicate'):
                select_preview_receipts([],['one','two'],self.target_path,self.target,'working',self.assembly)
        canonical={'parts':{'pelvis':Path('already-selected')},'inputs':{},'receipts':[],'retainedTargetStockParts':[]}
        with patch('pose_preview_target_parts.select_receipts',return_value=canonical),\
             patch('target_diagnostic_lineage.verify_receipt',return_value=copy.deepcopy(row)):
            with self.assertRaisesRegex(ValueError,'Duplicate'):
                select_preview_receipts(['canonical'],['diagnostic'],self.target_path,self.target,'working',self.assembly)

    def test_independent_audit_false_result_is_not_hidden_by_successful_recipe(self):
        child={'exports':{s:{'candidate':{'path':s,'sha256':'pin'},'parentCandidate':{'path':s+'parent','sha256':'pin'}} for s in ('source','working')}}
        item={'path':'child','sha256':'pin'};parent={'path':'parent','sha256':'pin'}
        decode={'kind':'independent-four-face-troll-pelvis-child-decode','diagnostic':item,'spaces':{}}
        audit={'kind':'independent-bounded-troll-pelvis-diagnostic-recipe-audit','diagnostic':parent,
            'exactRecipeAndFootprintVerified':True,'originalOutsideAttributeAndCornerBytesVerified':True,'topologyAndIntersections':{}}
        for space in ('source','working'):
            decode['spaces'][space]={**child['exports'][space],**{key:True for key in
                ('bodyAttributeBytesAndRetainedCornersExact','capBindingsCornerAndAttributeBytesExact','allMaterialAndMapBytesExact',
                 'onlyOneNewIndexAccessor','remainingBoundaryAndDefectPositionsPinned','activeArchiveMatchesDecodedPrimitives')}}
            decode['spaces'][space]['childCandidate']=decode['spaces'][space].pop('candidate')
            audit['topologyAndIntersections'][space]={'checks':{'noCapBodyIntersection':True,'capShadingFramesCorrect':True}}
        verify_audits(decode,audit,item,parent,child)
        audit['topologyAndIntersections']['working']['checks']['noCapBodyIntersection']=False
        with self.assertRaisesRegex(ValueError,'audit failed'):verify_audits(decode,audit,item,parent,child)
        audit['topologyAndIntersections']['working']['checks']['noCapBodyIntersection']=True
        decode['spaces']['source']['childCandidate']={'path':'working','sha256':'pin'}
        with self.assertRaisesRegex(ValueError,'binding differs'):verify_audits(decode,audit,item,parent,child)


if __name__=='__main__':unittest.main()
