"""Explicit stage/runtime plumbing rejects mismatched or stale adoption scope."""
import copy
import json
from pathlib import Path
import unittest
import numpy as np
import target_contract as c
from target_part_pipeline import execute,verify_source_receipt
from target_part_stage import stage_controls,material_execution_controls
from test_execution_adoption import ExecutionFixture

class NativeAdoptionPlumbingTests(unittest.TestCase):
    def runtime(self):
        f=ExecutionFixture(self);part='bicepl'
        cfg={'schemaVersion':2,'operation':'runtime','part':part,'coordinateSpace':'runtime',
             'targetContract':str(f.target_path),'targetContractSha256':c.sha(f.target_path),
             'source':str(f.candidates[part]),'sourceSha256':c.sha(f.candidates[part]),
             'sourceReceipt':str(f.part_paths[part]),'sourceReceiptSha256':c.sha(f.part_paths[part]),
             'executionAdoption':{'proof':f.pin(f.proof_path)}}
        return f,cfg

    def test_runtime_adoption_is_once_identity_and_preserves_history(self):
        f,cfg=self.runtime();old=f.part_paths['bicepl'].read_bytes()
        path=f.write(f.out/'runtime-config.json',cfg);result=execute(path,f.out/'runtime')
        receipt=json.loads(result.read_text());candidate=Path(receipt['candidate'])
        self.assertEqual(receipt['statureApplications'],1)
        self.assertEqual(receipt['sourceToAttachmentLocal'],np.eye(4).tolist())
        self.assertFalse(receipt['productionAccepted']);self.assertFalse(receipt['clientAccepted'])
        self.assertIn('executionAdoptionEvidence',receipt)
        self.assertEqual(f.part_paths['bicepl'].read_bytes(),old);self.assertFalse(f.sentinel.exists())
        verify_source_receipt(candidate,result,f.target_path,f.target,'bicepl','runtime')
        repeat={**cfg,'source':str(candidate),'sourceSha256':c.sha(candidate),
                'sourceReceipt':str(result),'sourceReceiptSha256':c.sha(result)}
        with self.assertRaises(ValueError):execute(f.write(f.out/'repeat.json',repeat),f.out/'repeat')

    def test_default_literal_stale_source_and_nonruntime_controls_reject(self):
        f,cfg=self.runtime()
        with self.assertRaises(ValueError):
            execute(f.write(f.out/'literal.json',{k:v for k,v in cfg.items() if k!='executionAdoption'}),f.out/'literal')
        for op in ('fit','mirror'):
            with self.subTest(operation=op),self.assertRaises(ValueError):
                execute(f.write(f.out/(op+'.json'),{**cfg,'operation':op}),f.out/op)
        bad=copy.deepcopy(cfg);bad['executionAdoption']['proof']['sha256']='0'*64
        with self.assertRaises(ValueError):execute(f.write(f.out/'stale.json',bad),f.out/'stale')

    def test_material_scope_requires_exact_calibration_recipe(self):
        f,cfg=self.runtime();pin=f.pin(f.proof_path)
        controls={'proof':pin,'recipe':pin,'representation':pin}
        material_execution_controls(controls,{'recipe':pin})
        with self.assertRaisesRegex(ValueError,'recipe differs'):
            material_execution_controls(controls,{'recipe':f.pin(f.target_path)})
        with self.assertRaises(ValueError):material_execution_controls({**controls,'guess':pin},{'recipe':pin})
        with self.assertRaisesRegex(ValueError,'source-bound'):
            stage_controls({'kind':'target-part-stage','diagnosticOnly':True,'materialRoles':{'0':'skin'},
                            'materialExecutionInputs':controls})

if __name__=='__main__':unittest.main()
