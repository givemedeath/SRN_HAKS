"""Connector configurations reject inherited regions and stale pose ownership."""
import copy
import json
import numpy as np
from pathlib import Path
import tempfile
import unittest
from connector_audit_inputs import pinned, validate_regions, verify_pose, load_config
import target_contract as contract
from test_human_female_stock_exact import stock_fixture


def regions():
    return {'neckChestSurface':{'absoluteXMaximum':.08,'bindZMinimum':1.55},
            'shoulderTerminalCaps':{side:{'lateralMinimum':.18,'bindZInterval':[1.3,1.6],'outwardNormalMinimumDot':.7} for side in ['left','right']},
            'upperArmProximalCaps':{'axialIntervalMetres':[-.04,.02],'oppositeShaftNormalMinimumDot':.3},'neckCapFaces':4}


class ConnectorInputTests(unittest.TestCase):
    def test_regions_require_independent_bilateral_measured_limits(self):
        self.assertEqual(validate_regions(regions()),regions())
        for change in ('missing-side','inverted-band','bad-dot','inherited-faces'):
            value = regions()
            if change=='missing-side': del value['shoulderTerminalCaps']['right']
            if change=='inverted-band': value['upperArmProximalCaps']['axialIntervalMetres']=[.02,-.04]
            if change=='bad-dot': value['shoulderTerminalCaps']['left']['outwardNormalMinimumDot']=1.1
            if change=='inherited-faces': value['neckCapFaces']=None
            with self.assertRaises(ValueError): validate_regions(value)

    def test_pinned_female_config_accepts_only_proven_stock_head_neck_and_geometry_frames(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);target_path,target=stock_fixture(root)
            proof_path=Path(target['rig']['stockReferenceReceipt']['path']);proof=json.loads(proof_path.read_text())
            stock_parts={}
            for part in ('head','neck'):
                source=root/'ascii'/('pfh0_'+part+'001.mdl');source.parent.mkdir(exist_ok=True);source.write_text('newmodel pfh0_'+part+'001\n')
                proof['frozenInputs'][str(source)]=contract.sha(source)
                copy_path=root/'diagnostic'/source.name;copy_path.parent.mkdir(exist_ok=True);copy_path.write_bytes(source.read_bytes())
                stock_parts[part]={'path':str(copy_path),'sha256':contract.sha(copy_path)}
            proof_path.write_text(json.dumps(proof));target['rig']['stockReferenceReceipt']['sha256']=contract.sha(proof_path);target_path.write_text(json.dumps(target))
            receipts={}
            for part in ('chest','bicepl','bicepr'):
                source=root/(part+'.glb');source.write_bytes(b'exact candidate bytes '+part.encode())
                receipt={**contract.binding(target_path,target,'working'),'schemaVersion':2,'kind':'target-part-geometry','part':part,'joint':contract.PART_JOINTS[part],
                         'statureApplications':0,'candidate':str(source),'candidateSha256':contract.sha(source),'attachmentWorld':contract.frame(target,contract.PART_JOINTS[part],'working').tolist(),
                         'frozenInputs':{str(target_path):contract.sha(target_path)}}
                path=root/(part+'-receipt.json');path.write_text(json.dumps(receipt));receipts[part]={'path':str(path),'sha256':contract.sha(path)}
            config={'schemaVersion':1,'kind':'target-connector-surface-config','coordinateSpace':'working','targetContract':{'path':str(target_path),'sha256':contract.sha(target_path)},
                    'geometryReceipts':receipts,'stockParts':stock_parts,'poses':[],'regions':regions()}
            path=root/'config.json';path.write_text(json.dumps(config));loaded=load_config(path)
            self.assertEqual(loaded[2]['identity']['gender'],'female')
            # A changed attachment is rejected even with a newly pinned receipt.
            receipt_path=Path(receipts['chest']['path']);bad=json.loads(receipt_path.read_text());bad['attachmentWorld'][0][3]+=.01;receipt_path.write_text(json.dumps(bad))
            config['geometryReceipts']['chest']['sha256']=contract.sha(receipt_path);path.write_text(json.dumps(config))
            with self.assertRaisesRegex(ValueError,'attachment frame'):load_config(path)

    def test_frozen_source_and_pose_pins_reject_stale_or_cross_target_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'target.json';path.write_text('{}')
            target={'id':'female-fit','rig':{'revision':'female-stock'}}
            source=Path(directory)/'pfh0_neck001.mdl';source.write_text('stock')
            frozen={'path':str(source),'sha256':contract.sha(source)};self.assertEqual(pinned(frozen),source)
            receipts={'chest':{'candidateSha256':'body-a'}};stock={'neck':source};pins={str(source):contract.sha(source)}
            specimen={'target':contract.binding(path,target,'working'),'displayScale':1,'targetPartReceipts':[{'part':'chest','candidateSha256':'body-a'}],'partInputs':pins.copy()}
            verify_pose(specimen,path,target,receipts,stock,pins)
            copied=Path(directory)/'diagnostic/pfh0_neck001.mdl';copied.parent.mkdir();copied.write_bytes(source.read_bytes())
            exact_copy=copy.deepcopy(specimen);exact_copy['partInputs']={str(copied):contract.sha(copied)}
            verify_pose(exact_copy,path,target,receipts,stock,pins)
            self.assertIn(str(copied),pins)
            for key in ('target','candidate','stock','scale'):
                bad=copy.deepcopy(specimen)
                if key=='target':bad['target']['targetId']='troll'
                if key=='candidate':bad['targetPartReceipts'][0]['candidateSha256']='body-b'
                if key=='stock':bad['partInputs'][str(source)]='changed'
                if key=='scale':bad['displayScale']=1.2
                with self.assertRaises(ValueError):verify_pose(bad,path,target,receipts,stock,pins)
            source.write_text('changed')
            with self.assertRaises(ValueError):pinned(frozen)


if __name__ == '__main__': unittest.main()
