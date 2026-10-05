"""Exact receipt/ownership/space gates for target-local pose substitutions."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

import target_contract as contract
from pose_preview_target_parts import select_receipts
from test_target_part_pipeline import target_fixture


class TargetPreviewReceiptTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        self.target = target_fixture(); self.path = self.root/'target.json'
        self.path.write_text(json.dumps(self.target))
        self.source = self.root/'donor.glb'; self.source.write_bytes(b'original donor')
        self.job = self.root/'job.json'; self.job.write_text('collected donor receipt')
        self.protected = self.root/'accepted-neighbour.bin'; self.protected.write_bytes(b'protected')
        self.assembly = {'schemaVersion':2, 'kind':'target-stock-diagnostic',
            'target':contract.binding(self.path,self.target,'working'),
            'parts':[{'part':part,'model':model} for part,model in self.target['models'].items()],
            'resources':{model+'.mdl':'serialized-part-pin' for model in self.target['models'].values()}}

    def tearDown(self):self.tmp.cleanup()

    def receipt(self, part='bicepl'):
        candidate = self.root/(part+'.glb'); candidate.write_bytes(b'fit-'+part.encode('ascii'))
        data = {'schemaVersion':2, 'kind':'target-part-geometry',
                **contract.binding(self.path,self.target,'working'),
                'part':part,'joint':contract.PART_JOINTS[part], 'model':contract.model(self.target,part),
                'candidate':str(candidate), 'candidateSha256':contract.sha(candidate),
                'attachmentWorld':contract.frame(self.target,contract.PART_JOINTS[part]).tolist(),
                'statureApplications':0, 'source':str(self.source), 'sourceSha256':contract.sha(self.source),
                'sourceReceipt':str(self.job), 'sourceReceiptSha256':contract.sha(self.job),
                'frozenInputs':{str(p):contract.sha(p) for p in
                                (self.path,self.source,self.job,self.protected)}}
        path = self.root/(part+'-geometry.json'); path.write_text(json.dumps(data))
        return path, data

    def select(self, paths, assembly=None, space='working'):
        return select_receipts(paths,self.path,self.target,space,assembly or self.assembly)

    def test_selects_only_owned_parts_and_retains_complete_input_pins(self):
        left,l=self.receipt(); right,r=self.receipt('bicepr')
        result=self.select([left,right])
        self.assertEqual(set(result['parts']),{'bicepl','bicepr'})
        self.assertEqual(result['parts']['bicepl'],Path(l['candidate']))
        self.assertEqual(set(result['retainedTargetStockParts']),set(contract.PART_JOINTS)-{'bicepl','bicepr'})
        self.assertEqual(result['inputs'][str(left)],contract.sha(left))
        self.assertEqual(result['inputs'][str(self.protected)],contract.sha(self.protected))
        self.assertFalse(result['receipts'][0]['clientEvidence'])
        self.assertEqual(result['receipts'][0]['statureApplications'],0)

    def test_rejects_other_target_revision_coordinate_space_and_legacy_receipts(self):
        path,receipt=self.receipt()
        for key,value in [('rigRevision','old-rig'),('coordinateSpace','runtime'),
                          ('targetContractSha256','wrong'),('targetId','other'),('schemaVersion',1)]:
            with self.subTest(field=key):
                changed=copy.deepcopy(receipt); changed[key]=value; path.write_text(json.dumps(changed))
                with self.assertRaises(ValueError):self.select([path])

    def test_rejects_wrong_joint_model_frame_and_double_scaling(self):
        path,receipt=self.receipt()
        frame=copy.deepcopy(receipt['attachmentWorld']);frame[0][3]+=.01
        for key,value in [('joint','rbicep_g'),('model','pmh0_bicepl001'),
                          ('attachmentWorld',frame),('statureApplications',1)]:
            with self.subTest(field=key):
                changed=copy.deepcopy(receipt); changed[key]=value;path.write_text(json.dumps(changed))
                with self.assertRaises(ValueError):self.select([path])

    def test_rejects_duplicate_parts_and_undeclared_assembly_ownership(self):
        path,_=self.receipt()
        with self.assertRaisesRegex(ValueError,'Duplicate'):self.select([path,path])
        assembly=copy.deepcopy(self.assembly)
        assembly['parts']=[row for row in assembly['parts'] if row['part']!='bicepl']
        with self.assertRaisesRegex(ValueError,'not declared'):self.select([path],assembly)
        assembly=copy.deepcopy(self.assembly);assembly['parts'][0]['model']='pmh0_chest001'
        with self.assertRaisesRegex(ValueError,'ownership'):self.select([path],assembly)
        assembly=copy.deepcopy(self.assembly);del assembly['resources']['pmg0_chest001.mdl']
        with self.assertRaisesRegex(ValueError,'frozen resource'):self.select([path],assembly)

    def test_rejects_changed_candidate_and_frozen_protected_neighbour(self):
        path,receipt=self.receipt(); candidate=Path(receipt['candidate'])
        original=candidate.read_bytes();candidate.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'candidate changed'):self.select([path])
        candidate.write_bytes(original);self.protected.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'frozen input changed'):self.select([path])

    def test_requires_source_provenance_and_exact_target_input(self):
        path,receipt=self.receipt()
        for missing in (str(self.path),str(self.source),str(self.job)):
            with self.subTest(missing=missing):
                changed=copy.deepcopy(receipt);del changed['frozenInputs'][missing]
                path.write_text(json.dumps(changed))
                with self.assertRaises(ValueError):self.select([path])
        changed=copy.deepcopy(receipt);changed['sourceReceiptSha256']='wrong'
        path.write_text(json.dumps(changed))
        with self.assertRaisesRegex(ValueError,'provenance'):self.select([path])

    def test_runtime_receipt_accepts_one_scale_and_runtime_frame(self):
        path,receipt=self.receipt()
        assembly=copy.deepcopy(self.assembly)
        assembly['target']=contract.binding(self.path,self.target,'runtime')
        receipt.update(contract.binding(self.path,self.target,'runtime'))
        receipt['statureApplications']=1
        receipt['attachmentWorld']=contract.frame(self.target,'lbicep_g','runtime').tolist()
        path.write_text(json.dumps(receipt))
        result=self.select([path],assembly,'runtime')
        self.assertEqual(result['receipts'][0]['statureApplications'],1)
        receipt['statureApplications']=2;path.write_text(json.dumps(receipt))
        with self.assertRaisesRegex(ValueError,'conversion count'):self.select([path],assembly,'runtime')


if __name__=='__main__':unittest.main()
