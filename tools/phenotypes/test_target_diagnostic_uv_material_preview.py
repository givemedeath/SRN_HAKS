"""Focused preview-only consent, source identity and mixed-channel regressions."""
import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import target_contract as contract
import target_diagnostic_uv_material_preview as preview
import target_diagnostic_uv_basis as policy
from pose_preview_target_parts import select_preview_receipts,select_receipts
from target_diagnostic_lineage import verify_receipt as old_diagnostic_reader
from test_target_part_pipeline import target_fixture

class UvMaterialPreviewTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.root=Path(self.temporary.name)
        self.target=self.root/'target.json';self.data=target_fixture()
        self.data['rig'].update(offlineStructureAccepted=True,pilotAccepted=True,pilotAcceptanceScope='offline-rig-structure')
        self.target.write_text(json.dumps(self.data));self.binding=contract.binding(self.target,self.data,'working')
        self.pins={}
        for key in preview.PIN_KEYS:
            p=self.root/(key+'.json');p.write_text('exact '+key);self.pins[key]={'path':str(p),'sha256':contract.sha(p)}
        self.frame=contract.frame(self.data,'pelvis_g','working').tolist()
        common={**self.binding,'part':'pelvis','joint':'pelvis_g','model':contract.model(self.data,'pelvis'),
                'statureApplications':0,'attachmentWorld':self.frame,'candidateToAttachmentLocal':np.eye(4).tolist(),**self.pins}
        self.review={**common,'schemaVersion':2,'kind':preview.REVIEW_KIND,'scope':preview.SCOPE,'reviewedBy':'/root',
                     'reviewed':True,'authorizeDiagnosticPreview':True,'pendingGates':{k:False for k in preview.FLAGS},
                     'pendingRisks':['Synthetic fixture only; caps and client pending.']}
        self.review['implementation']={name:{'path':str(Path(preview.__file__).with_name(name).resolve()),
            'sha256':contract.sha(Path(preview.__file__).with_name(name))} for name in preview.IMPLEMENTATION}
        self.review_path=self.root/'review.json'
        self.descriptor={**common,'schemaVersion':2,'kind':preview.KIND,'previewScope':preview.SCOPE,'diagnosticOnly':True,
                         **{k:False for k in preview.FLAGS}}
        self.path=self.root/'preview.json';self.write()
        self.prepared={'candidate':Path(self.pins['sourceCandidate']['path']),'receipt':{'kind':policy.KIND,
            'candidateSha256':self.pins['sourceCandidate']['sha256'],'attachmentWorld':self.frame,
            'candidateToAttachmentLocal':np.eye(4).tolist()},'inputs':{p['path']:p['sha256'] for p in self.pins.values()}}
    def tearDown(self):self.temporary.cleanup()
    def write(self):
        self.review_path.write_text(json.dumps(self.review));self.descriptor['rootReview']={'path':str(self.review_path),'sha256':contract.sha(self.review_path)}
        self.path.write_text(json.dumps(self.descriptor))
    def read(self,space='working'):
        with patch.object(preview.material,'verify_receipt',return_value=self.prepared) as proof:
            row=preview.verify_preview_descriptor(self.path,self.target,self.data,space)
        self.assertEqual(proof.call_count,1);return row
    def test_valid_preview_retains_distinct_identity_and_all_pending_gates(self):
        row=self.read();self.assertEqual(row['receiptKind'],preview.KIND)
        self.assertFalse(row['canonicalNativeLineage']);self.assertEqual(row['statureApplications'],0)
        self.assertEqual(row['materialBodyPrimitiveGroups'],{'skin':[0,4],'garment':[3,5],'cap-left':[1],'cap-right':[2]})
        self.assertTrue(all(v is False for v in row['pendingGates'].values()))
        self.assertEqual(row['primitiveRoleStatus'],{'0':'skin','1':'unowned-neutral-diagnostic-cap',
            '2':'unowned-neutral-diagnostic-cap','3':'garment','4':'skin','5':'garment'})
        self.assertEqual(row['materialRoles'],{'0':'skin','1':'unowned-neutral-diagnostic-cap','2':'garment'})
        self.assertFalse(row['historicalFitReapplied']);self.assertTrue(row['attachmentAppliedOnce'])
    def test_runtime_kind_transform_scope_and_acceptance_reject_before_source_consumer(self):
        cases=[('kind','target-part-geometry'),('previewScope','production'),('statureApplications',1),
               ('capOwnershipAccepted',True),('part','chest'),('unknownTransform',[1,2,3]),
               ('candidateToAttachmentLocal',np.diag([2,2,2,1]).tolist())]
        original=copy.deepcopy(self.descriptor)
        for key,value in cases:
            self.descriptor=copy.deepcopy(original);self.descriptor[key]=value;self.write()
            with self.subTest(key=key),patch.object(preview.material,'verify_receipt') as proof:
                with self.assertRaises(ValueError):preview.verify_preview_descriptor(self.path,self.target,self.data)
                proof.assert_not_called()
        self.descriptor=original;self.write()
        with self.assertRaises(ValueError):self.read('runtime')
    def test_root_consent_exact_audit_source_and_nested_gates_cannot_be_substituted(self):
        original=copy.deepcopy(self.review)
        for key,value in [('authorizeDiagnosticPreview',False),('scope','production'),('reviewedBy','classifier'),
                          ('pendingRisks',[]),('evidence',{'clientAccepted':True}),('authorizeNativeCompilation',True)]:
            self.review=copy.deepcopy(original);self.review[key]=value;self.write()
            with self.subTest(key=key),patch.object(preview.material,'verify_receipt') as proof:
                with self.assertRaises(ValueError):preview.verify_preview_descriptor(self.path,self.target,self.data)
                proof.assert_not_called()
        self.review=copy.deepcopy(original);other=self.root/'other-audit';other.write_text('exact decodedAudit')
        self.review['decodedAudit']={'path':str(other),'sha256':contract.sha(other)};self.write()
        with self.assertRaises(ValueError):self.read()
    def test_changed_source_hash_and_failed_material_or_cap_proof_propagate(self):
        Path(self.pins['sourceCandidate']['path']).write_text('mutated serialized source')
        with patch.object(preview.material,'verify_receipt') as proof:
            with self.assertRaises(ValueError):preview.verify_preview_descriptor(self.path,self.target,self.data)
            proof.assert_not_called()
        Path(self.pins['sourceCandidate']['path']).write_text('exact sourceCandidate')
        with patch.object(preview.material,'verify_receipt',side_effect=ValueError('Literal separate generated cap archive differs')):
            with self.assertRaisesRegex(ValueError,'cap archive'):preview.verify_preview_descriptor(self.path,self.target,self.data)
    def test_old_channels_reject_descriptor_and_canonical_selection_does_not_promote_it(self):
        with self.assertRaises(ValueError):old_diagnostic_reader(self.path,self.target,self.data)
        assembly={'schemaVersion':2,'kind':'target-stock-diagnostic','target':self.binding,
                  'parts':[{'part':'pelvis','model':contract.model(self.data,'pelvis')}],
                  'resources':{contract.model(self.data,'pelvis')+'.mdl':'unused'}}
        with self.assertRaises(ValueError):select_receipts([self.path],self.target,self.data,'working',assembly)
    def test_duplicate_channel_rejected_and_right_leg_stock_fallback_remains_explicit(self):
        parts=['pelvis','legl','legr','shinl','shinr','footl','footr','handl','handr']
        assembly={'schemaVersion':2,'kind':'target-stock-diagnostic','target':self.binding,
                  'parts':[{'part':p,'model':contract.model(self.data,p)} for p in parts],
                  'resources':{contract.model(self.data,p)+'.mdl':'unused' for p in parts}}
        row=self.read()
        with patch.object(preview,'verify_preview_descriptor',side_effect=lambda *a:copy.deepcopy(row)):
            selected=select_preview_receipts([],[],self.target,self.data,'working',assembly,[self.path])
            self.assertEqual(set(selected['parts']),{'pelvis'})
            self.assertIn('legr',selected['retainedTargetStockParts']);self.assertIn('footr',selected['retainedTargetStockParts'])
            with self.assertRaisesRegex(ValueError,'Duplicate'):
                select_preview_receipts([],[],self.target,self.data,'working',assembly,[self.path,self.path])

if __name__=='__main__':unittest.main()