"""Focused terminal lineage/consent/changed-cap preview failures."""
import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import target_contract as tc
import target_diagnostic_terminal_preview as preview
from test_target_part_pipeline import target_fixture

class TerminalPreviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.target=self.root/'target.json'
        self.data=target_fixture();self.data['rig'].update(offlineStructureAccepted=True,pilotAccepted=True,pilotAcceptanceScope='offline-rig-structure')
        self.target.write_text(json.dumps(self.data));self.binding=tc.binding(self.target,self.data,'working')
        self.frame=tc.frame(self.data,'pelvis_g','working').tolist()
        def item(name,value):
            p=self.root/name;p.write_text(json.dumps(value));return {'path':str(p),'sha256':tc.sha(p)}
        self.child=item('child.glb','child serialized');self.parent_candidate=item('parent.glb','original serialized')
        self.parent_geometry=item('material.json',{'kind':'target-part-diagnostic-uv-basis-material-geometry'})
        self.parent_descriptor=item('original-preview.json',{'sourceGeometry':self.parent_geometry})
        self.source=item('terminal.json','source receipt')
        self.audit_data={'kind':'independent-decoded-pelvis-terminal-shortening35-audit','passed':True,
            'receipt':self.source,'candidate':self.child,'statureApplications':0,'capRoundMetres':0.,
            'originalIndexUVMaterialMapsAndSourceCornerRecordsExact':True,'coordinateWeldGraphIsomorphismProved':True,'frozenInputs':{}}
        self.audit=item('audit.json',self.audit_data)
        pins={'sourceGeometry':self.source,'sourceCandidate':self.child,'independentAudit':self.audit,'parentMaterialPreview':self.parent_descriptor}
        common={**self.binding,'schemaVersion':2,'part':'pelvis','joint':'pelvis_g','model':tc.model(self.data,'pelvis'),
            'statureApplications':0,'attachmentWorld':self.frame,'candidateToAttachmentLocal':np.eye(4).tolist(),**pins}
        self.review={**common,'kind':preview.REVIEW_KIND,'scope':preview.SCOPE,'reviewedBy':'/root','reviewed':True,
            'authorizeDiagnosticPreview':True,'pendingGates':{k:False for k in preview.FLAGS},'pendingRisks':['Generated shortened caps remain unowned.'],
            'implementation':{n:{'path':str(Path(preview.__file__).with_name(n).resolve()),'sha256':tc.sha(Path(preview.__file__).with_name(n))} for n in preview.IMPLEMENTATION}}
        self.review_path=self.root/'review.json';self.path=self.root/'preview.json'
        self.descriptor={**common,'kind':preview.KIND,'previewScope':preview.SCOPE,'diagnosticOnly':True,**{k:False for k in preview.FLAGS}}
        body=item('body.npz','body provenance');cap=item('caps.npz','changed cap ancestry')
        self.source_data={'kind':preview.terminal.KIND,'operation':preview.terminal.OPERATION,'candidateSha256':self.child['sha256'],
            'parentCandidate':self.parent_candidate,'parentMaterialGeometryReceipt':self.parent_geometry,'attachmentWorld':self.frame,
            'candidateToAttachmentLocal':np.eye(4).tolist(),'bodyFloat64DeformedCornerArchive':body,'generatedCapDeformedCornerArchive':cap,
            'capShadingPolicy':'generated-new-cap-basis','geometryAccepted':False}
        self.prepared={'receipt':self.source_data,'candidate':Path(self.child['path']),'inputs':{},
            'primitiveInventory':[{'primitive':i,'material':[0,1,1,2,0,2][i],'faces':n} for i,n in enumerate(preview.terminal.COUNTS)]}
        self.parent_row={'candidate':self.parent_candidate['path'],'candidateSha256':self.parent_candidate['sha256'],'inputs':{},
            'receiptKind':preview.parent_preview.KIND,'pendingGates':{k:False for k in preview.FLAGS},'attachmentAppliedOnce':True,
            'historicalFitReapplied':False,'canonicalNativeLineage':False,'materialRoles':{'0':'skin','1':'unowned-neutral-diagnostic-cap','2':'garment'}}
        self.write()
    def tearDown(self):self.tmp.cleanup()
    def write(self):
        Path(self.audit['path']).write_text(json.dumps(self.audit_data));self.audit['sha256']=tc.sha(self.audit['path'])
        self.descriptor['independentAudit']=copy.deepcopy(self.audit);self.review['independentAudit']=copy.deepcopy(self.audit)
        self.review_path.write_text(json.dumps(self.review));self.descriptor['rootReview']={'path':str(self.review_path),'sha256':tc.sha(self.review_path)}
        self.path.write_text(json.dumps(self.descriptor))
    def read(self,space='working'):
        with patch.object(preview.parent_preview,'verify_preview_descriptor',return_value=self.parent_row),patch.object(preview.terminal,'verify_receipt',return_value=self.prepared):
            return preview.verify_preview_descriptor(self.path,self.target,self.data,space)
    def test_changed_caps_receive_new_identity_and_pending_scope(self):
        row=self.read();self.assertEqual(row['receiptKind'],preview.KIND);self.assertEqual(row['sourceReceiptKind'],preview.terminal.KIND)
        self.assertEqual(row['capMode'],'deformed-unowned-neutral-gray-generated-shading');self.assertFalse(row['canonicalNativeLineage'])
        self.assertTrue(row['attachmentAppliedOnce']);self.assertFalse(row['historicalFitReapplied']);self.assertTrue(all(v is False for v in row['pendingGates'].values()))
        self.assertEqual(self.parent_row['receiptKind'],preview.parent_preview.KIND)
    def test_wrong_kind_runtime_double_fit_and_acceptance_reject(self):
        original=copy.deepcopy(self.descriptor)
        for key,value in [('kind',preview.parent_preview.KIND),('statureApplications',1),('capOwnershipAccepted',True),('candidateToAttachmentLocal',np.diag([2,2,2,1]).tolist())]:
            self.descriptor=copy.deepcopy(original);self.descriptor[key]=value;self.write()
            with self.subTest(key=key),self.assertRaises(ValueError):self.read()
        self.descriptor=original;self.write()
        with self.assertRaises(ValueError):self.read('runtime')
    def test_failed_or_wrong_child_audit_and_mutated_candidate_reject(self):
        original=copy.deepcopy(self.audit_data)
        for key,value in [('passed',False),('receipt',self.parent_geometry),('capRoundMetres',.004)]:
            self.audit_data=copy.deepcopy(original);self.audit_data[key]=value;self.write()
            with self.subTest(key=key),self.assertRaises(ValueError):self.read()
        self.audit_data=original;self.write();Path(self.child['path']).write_text('changed child')
        with self.assertRaises(ValueError):self.read()
    def test_actual_terminal_parent_roles_and_generated_archive_are_required(self):
        self.source_data['parentCandidate']=self.child
        with self.assertRaises(ValueError):self.read()
        self.source_data['parentCandidate']=self.parent_candidate;self.prepared['primitiveInventory'][1]['material']=0
        with self.assertRaises(ValueError):self.read()
        self.prepared['primitiveInventory'][1]['material']=1;Path(self.source_data['generatedCapDeformedCornerArchive']['path']).write_text('wrong cap ancestry')
        with self.assertRaises(ValueError):self.read()
    def test_preview_consent_and_nested_promotions_reject(self):
        original=copy.deepcopy(self.review)
        for key,value in [('authorizeDiagnosticPreview',False),('scope','native-stage'),('implementation',{}),('pendingRisks',[]),('nativeAccepted',True)]:
            self.review=copy.deepcopy(original);self.review[key]=value;self.write()
            with self.subTest(key=key),self.assertRaises(ValueError):self.read()

if __name__=='__main__':unittest.main()
