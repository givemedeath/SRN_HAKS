import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from tools.headkit.common import pin,write,read
from .recovery import validate_pixels,successful_pixel_hash,recovery_inputs,unchanged_successful_pixels,prepare_recovery


class RecoveryTests(unittest.TestCase):
    def test_miss_classification_and_successful_pixel_invariance(self):
        pixels=np.full((4,4,4),.25,np.float32);pixels[0,0]=[1,0,1,1]
        owners=np.zeros((4,4),np.int32);caps=np.zeros((4,4),bool);misses=caps.copy();misses[0,0]=True
        self.assertEqual(validate_pixels(pixels,owners,caps,misses,1),1)
        before=successful_pixel_hash(pixels,misses);fixed=pixels.copy();fixed[0,0]=.5
        self.assertEqual(before,successful_pixel_hash(fixed,misses));unchanged_successful_pixels(pixels,fixed,misses)
        fixed[1,0]=.6
        with self.assertRaisesRegex(ValueError,'successful'):unchanged_successful_pixels(pixels,fixed,misses)
        with self.assertRaisesRegex(ValueError,'classification'):validate_pixels(pixels,owners,caps,~misses,1)
        owners[1,1]=3
        with self.assertRaisesRegex(ValueError,'owners'):validate_pixels(pixels,owners,caps,misses,1)

    def test_stale_artifacts_are_not_recovered(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);proof={'schemaVersion':1,'kind':'item-bake-recovery','externalImages':[]}
            for key in ('scene','sourceScene','pixels','masks'):
                p=root/key;p.write_bytes(key.encode());proof[key]=pin(p)
            self.assertEqual(len(recovery_inputs(proof)),4)
            proof.update(family={'bakeSize':4096},processing={'capColour':[0,0,0]})
            write(root/'proof.json',proof);write(root/'policy.json',{'method':'nearest-finished-donor','maximumDistance':.003,'minimumNormalAlignment':.5})
            with patch('tools.itemkit.contracts.code_pins',return_value=[]):
                result=prepare_recovery(root/'proof.json',root/'policy.json',root/'prepared')
            config=read(result['config']['path']);self.assertEqual(config['scene'],proof['sourceScene']['path'])
            self.assertEqual(config['processing']['capColour'],[0,0,0]);self.assertEqual(config['stage'],'recover-bake')
            self.assertIn(proof['scene'],config['inputs'])
            (root/'scene').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'Stale'):recovery_inputs(proof)
