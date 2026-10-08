"""Exactly-once stock-exact identity conversion guards for verified native stages."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

import target_contract as contract
from convert_native_stage_identity import convert
from test_human_female_stock_exact import stock_fixture


def pin(path):
    return {'path':str(path),'sha256':contract.sha(path)}


class IdentityConversionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.target_path,self.target=stock_fixture(self.root)

    def tearDown(self):self.tmp.cleanup()

    def stage(self,name='stage',**changes):
        folder=self.root/name;(folder/'ascii').mkdir(parents=True);(folder/'resources').mkdir()
        model=folder/'ascii'/'pfh0_bicepl001.mdl';model.write_text('newmodel pfh0_bicepl001\ndonemodel pfh0_bicepl001\n')
        texture=folder/'resources'/'pfh0_bicepl001n.tga';texture.write_bytes(b'normal')
        np.savez(folder/'authoritative-native-compiler-corners.npz',positions=np.arange(9,dtype=np.float64).reshape(3,3))
        dependency=self.root/(name+'-input.bin');dependency.write_bytes(b'input')
        receipt={'kind':'target-part-stage','part':'bicepl','statureApplications':0,
            **contract.binding(self.target_path,self.target,'working'),
            'nativeCompilerInputProof':{'authority':'literalNativeArchive','identityConversionApplied':False},
            'frozenInputs':{str(dependency):contract.sha(dependency)},
            'asciiModel':str(model),'asciiModelSha256':contract.sha(model),
            'materialResourceHashes':{texture.name:contract.sha(texture)}}
        receipt.update(changes)
        path=folder/'target-stage.json';path.write_text(json.dumps(receipt));return path

    def test_converts_once_and_preserves_native_bytes(self):
        source=self.stage();result=convert(pin(source),pin(self.target_path),self.root/'runtime')
        data=json.loads(result.read_text())
        self.assertEqual(data['coordinateSpace'],'runtime');self.assertEqual(data['statureApplications'],1)
        self.assertTrue(data['nativeCompilerInputProof']['identityConversionApplied'])
        self.assertEqual(data['identityRuntimeConversion']['matrix'],np.eye(4).tolist())
        self.assertEqual(data['sourceWorkingStage'],pin(source))
        for rel in ('ascii/pfh0_bicepl001.mdl','resources/pfh0_bicepl001n.tga','authoritative-native-compiler-corners.npz'):
            self.assertEqual(contract.sha(self.root/'runtime'/rel),contract.sha(source.parent/rel))
        self.assertEqual(contract.sha(data['asciiModel']),data['asciiModelSha256'])
        with self.assertRaisesRegex(ValueError,'Repeated identity conversion rejected'):
            convert(pin(result),pin(self.target_path),self.root/'again')

    def test_rejects_prior_stature_application(self):
        source=self.stage(statureApplications=1)
        with self.assertRaisesRegex(ValueError,'Repeated identity conversion'):convert(pin(source),pin(self.target_path),self.root/'out')

    def test_rejects_non_literal_or_converted_native_authority(self):
        for proof in ({'authority':'serializedGlb','identityConversionApplied':False},
                      {'authority':'literalNativeArchive','identityConversionApplied':True}):
            with self.subTest(proof=proof):
                source=self.stage(name='stage-'+proof['authority']+str(proof['identityConversionApplied']),nativeCompilerInputProof=proof)
                with self.assertRaisesRegex(ValueError,'Verified unconverted native-f64 stage'):
                    convert(pin(source),pin(self.target_path),self.root/('out-'+source.parent.name))

    def test_rejects_changed_pins_and_dependencies(self):
        source=self.stage();bad=pin(source);bad['sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'Changed identity input'):convert(bad,pin(self.target_path),self.root/'a')
        with self.assertRaisesRegex(ValueError,'Changed identity input'):
            convert({**pin(source),'extra':1},pin(self.target_path),self.root/'b')
        (self.root/'stage-input.bin').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'Changed source stage dependency'):convert(pin(source),pin(self.target_path),self.root/'c')

    def test_rejects_unequal_working_runtime_frames(self):
        target=copy.deepcopy(self.target);target['rig']['frames']['runtime']['lbicep_g'][0][3]+=.001
        path=self.root/'unequal.json';path.write_text(json.dumps(target))
        source=self.stage(**contract.binding(path,target,'working'))
        with self.assertRaises(ValueError):convert(pin(source),pin(path),self.root/'out')

    def test_requires_fresh_output(self):
        source=self.stage();(self.root/'exists').mkdir()
        with self.assertRaisesRegex(ValueError,'Fresh identity result required'):convert(pin(source),pin(self.target_path),self.root/'exists')


if __name__=='__main__':unittest.main()
