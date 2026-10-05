"""Meaningful ownership, clipping, historical pin and mask regression tests."""
from pathlib import Path
import struct
import tempfile
import unittest

import numpy as np

from audit_effective_limb_materials import (calibration_proof,compare_pair,connector_mask,
    decode_plt,palette_delta,shade_bounds,sha,verify_pins)


def plt(top):
    h,w,_=top.shape
    return b'PLT V1  '+struct.pack('<IIII',10,0,w,h)+top[::-1].tobytes()


class EffectiveLimbMaterialTests(unittest.TestCase):
    def test_integer_skin_offset_clipping_preserves_non_skin(self):
        raw=np.array([[[3,0],[250,0],[90,1]]],np.uint8)
        lower=raw.copy();lower[0,:2,0]=[0,240]
        proof=calibration_proof(plt(raw),plt(lower),-10)
        self.assertEqual(proof['lowClampedPixels'],1)
        upper=raw.copy();upper[0,:2,0]=[14,255]
        proof=calibration_proof(plt(raw),plt(upper),11)
        self.assertEqual(proof['highClampedPixels'],1)
        upper[0,2,0]=91
        with self.assertRaises(RuntimeError):calibration_proof(plt(raw),plt(upper),11)
        with self.assertRaises(RuntimeError):calibration_proof(plt(raw),plt(raw),True)

    def test_connector_mask_protects_actual_pivot_not_mesh_extrema(self):
        # Two disjoint UV triangles: the upper positive-Z crown is wholly protected;
        # a shaft triangle 60mm inside the actual pivot remains influenced.
        p=np.array([[[0,0,.001],[1,0,.005],[0,1,.001]],
                    [[0,0,-.06],[1,0,-.06],[0,1,-.06]]],float)
        uv=np.array([[[.1,.9],[.4,.9],[.1,.6]],[[.6,.4],[.9,.4],[.6,.1]]])
        mask,protected=connector_mask(p,uv,(32,32),.02,[([0,0,1],0),([0,0,-1],.3)])
        self.assertTrue(protected[5,5]);self.assertEqual(mask[5,5],0)
        self.assertFalse(protected[22,21]);self.assertGreater(mask[22,21],250)

    def test_zero_mask_protected_fixed_and_limit_changes_rejected(self):
        before=np.array([[[100,0],[100,0],[100,1]]],np.uint8)
        after=before.copy();after[0,1,0]=95
        mask=np.array([[0,255,255]],np.uint8);protect=np.array([[True,False,False]])
        self.assertEqual(shade_bounds(before,after,mask,protect,12,3)['actualShadeDeltaRange'],[-5,0])
        for pixel,shade in [(0,99),(1,87),(1,104),(2,99)]:
            changed=after.copy();changed[0,pixel,0]=shade
            with self.assertRaises(RuntimeError):shade_bounds(before,changed,mask,protect,12,3)
        changed=after.copy();changed[0,1,1]=1
        with self.assertRaises(RuntimeError):shade_bounds(before,changed,mask,protect,12,3)

    def test_ao_white_identity_including_non_monotone_palette(self):
        rng=np.random.default_rng(4)
        palette=rng.integers(0,256,(9,256,3),dtype=np.uint8)
        shade=np.array([[0,2,100,255]],np.uint8)
        np.testing.assert_array_equal(palette_delta(shade,np.ones(shade.shape),palette,.35),np.zeros(shade.shape))
        np.testing.assert_array_equal(palette_delta(shade,np.zeros(shade.shape),palette,0),np.zeros(shade.shape))
        dark=palette_delta(shade,np.zeros(shade.shape),palette,.35)
        self.assertTrue(np.all(dark<=0));self.assertTrue(np.all(dark>=-48))
        with self.assertRaises(RuntimeError):palette_delta(shade,np.ones(shade.shape)*1.1,palette,.35)

    def test_pair_differences_reported_without_false_byte_identity(self):
        left=np.array([[[100,0],[99,0]]],np.uint8);right=left.copy();right[0,1,0]=100
        lm=np.array([[0,133]],np.uint8);rm=np.array([[0,134]],np.uint8)
        p=compare_pair(left,right,lm,rm,left[:,:,0].astype(float),right[:,:,0].astype(float))
        self.assertFalse(p['paletteBytesExact']);self.assertEqual(p['shadeDifferencePixels'],1)
        self.assertEqual(p['maximumAbsoluteShadeDifference'],1)
        self.assertEqual(p['shadeDifferencesInEitherZeroMask'],0)
        rm[0,1]=0
        p=compare_pair(left,right,lm,rm,left[:,:,0].astype(float),right[:,:,0].astype(float))
        self.assertEqual(p['shadeDifferencesInEitherZeroMask'],1)

    def test_historical_python_uses_exact_archive_not_edited_live_helper(self):
        with tempfile.TemporaryDirectory(prefix='limb-material-pin-test-') as directory:
            root=Path(directory);live=root/'collector.py';archive=root/'old.py'
            archive.write_text('old executed implementation\n');pin=sha(archive)
            live.write_text('new reusable implementation\n')
            inputs={};origins={str(live):{'archive':str(archive),'sha256':pin}}
            proof=verify_pins({str(live):pin},origins,inputs)
            self.assertEqual(inputs,{str(archive.resolve()):pin});self.assertEqual(proof[0]['origin'],str(live))
            alias=str(root)+'/./collector.py'
            verify_pins({str(live):pin},{alias:origins[str(live)]},{})
            with self.assertRaisesRegex(RuntimeError,'Conflicting historical'):
                verify_pins({str(live):pin},{**origins,alias:{'archive':str(archive),'sha256':'0'*64}},{})
            with self.assertRaises(RuntimeError):verify_pins({str(live):pin},{}, {})
            archive.write_text('changed archive\n')
            with self.assertRaises(RuntimeError):verify_pins({str(live):pin},origins,{})


if __name__=='__main__':unittest.main(verbosity=2)
