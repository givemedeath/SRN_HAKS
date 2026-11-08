"""Upper-lid creases must not be counted as eyebrow hair."""
import unittest
from unittest.mock import patch
from pathlib import Path
import tempfile
from PIL import Image
import numpy as np
from headkit.brow_edges import upper_lids,apply_regions,fringe
from headkit.face_masks import EYE_RING,BROW_RING
from headkit.quality import upper_lid_hair_pixels


def landmarks():
    pts=np.zeros((478,2),float);pts[168]=[90,50]
    for side,left in [('R',20),('L',100)]:
        ring=EYE_RING[side];right=left+40
        pts[ring[0]]=[left,55];pts[ring[8]]=[right,55]
        pts[ring[1:8]]=np.c_[np.linspace(left+5,right-5,7),np.full(7,60)]
        pts[ring[9:]]=np.c_[np.linspace(right-5,left+5,7),np.full(7,50)]
        brow=BROW_RING[side]
        pts[brow[:5]]=np.c_[np.linspace(left-4,right+4,5),np.full(5,25)]
        pts[brow[5:]]=np.c_[np.linspace(right+4,left-4,5),np.full(5,35)]
    return pts


class UpperLids(unittest.TestCase):
    def test_lid_skin_is_separate_from_brows_and_eye_openings(self):
        pts=landmarks();hit=np.ones((100,180),bool)
        lids=upper_lids(hit.shape,pts,hit)
        self.assertTrue(lids[45,40]);self.assertTrue(lids[45,120])
        self.assertFalse(lids[30,40]);self.assertFalse(lids[57,40])
        self.assertFalse(lids[70].any())
        hit[45,40]=False;self.assertFalse(upper_lids(hit.shape,pts,hit)[45,40])
        self.assertFalse(upper_lids(hit.shape,pts,hit,'left')[:,:90].any())
        self.assertFalse(upper_lids(hit.shape,pts,hit,'right')[:,90:].any())
        with self.assertRaises(ValueError):upper_lids(hit.shape,pts,hit,'top')


    def test_full_gap_guards_false_brow_tails_but_preserves_real_hair_locks(self):
        pts=landmarks();hit=np.ones((100,180),bool);hair=np.zeros_like(hit)
        old=upper_lids(hit.shape,pts,hit)
        full=upper_lids(hit.shape,pts,hit,source_hair=hair)
        self.assertFalse(old[38,40]);self.assertTrue(full[38,40])
        self.assertTrue(full[38,68])  # an inner brow tail beyond the old horizontal limit
        self.assertFalse(full[30,40] or full[57,40])
        hair[36:42,35:45]=True
        protected=upper_lids(hit.shape,pts,hit,source_hair=hair)
        self.assertFalse(protected[38,40]);self.assertTrue(protected[45,40])
        region={'labels':np.zeros(hit.shape,np.uint8),'pts':pts,'view':{'hit':hit}}
        channel=np.zeros(hit.shape,np.uint8);channel[38,40]=1
        self.assertEqual(upper_lid_hair_pixels(region,channel),1)
        region['labels'][hair]=17
        self.assertEqual(upper_lid_hair_pixels(region,channel),0)
        self.assertFalse(upper_lids(hit.shape,pts,hit,'left',source_hair=hair)[:,:90].any())
        with self.assertRaisesRegex(ValueError,'matching boolean'):
            upper_lids(hit.shape,pts,hit,source_hair=np.zeros((2,2),bool))
        with self.assertRaisesRegex(ValueError,'matching boolean'):
            upper_lids(hit.shape,pts,hit,source_hair=np.zeros(hit.shape,np.uint8))

    def test_skin_precedes_recovery_and_protects_other_materials(self):
        labels=np.array([[1,0,8,3,9,1,0]],np.uint8)
        mapped=np.array([[1,1,1,1,1,0,1]],bool)
        brow=np.ones_like(mapped);lid=np.array([[1,1,1,1,1,1,0]],bool)
        result,report=apply_regions(labels,mapped,brow,lid)
        np.testing.assert_array_equal(result,[[0,0,8,3,9,1,1]])
        np.testing.assert_array_equal(labels,[[1,0,8,3,9,1,0]])
        self.assertEqual(report,{'changedTexels':1,'upperLidHairToSkinTexels':1})

    def test_independent_gate_catches_shadow_even_with_perfect_brow_coverage(self):
        pts=landmarks();shape=(100,180)
        region={'labels':np.zeros(shape,np.uint8),'pts':pts,'view':{'hit':np.ones(shape,bool)}}
        channel=np.zeros(shape,np.uint8);channel[30,40]=channel[30,120]=1
        self.assertEqual(upper_lid_hair_pixels(region,channel),0)
        channel[45,40]=1
        self.assertEqual(upper_lid_hair_pixels(region,channel),1)
        self.assertEqual(upper_lid_hair_pixels(region,channel,'left'),0)
        self.assertEqual(upper_lid_hair_pixels(region,channel,'right'),1)

    def test_lid_guard_runs_even_when_brow_recovery_is_disabled(self):
        from headkit.brow_edges import adjust
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);shape=(100,180);files={}
            for name,mode in [('frontRender','RGB'),('frontLabels','L')]:
                path=root/(name+'.png');Image.new(mode,shape[::-1]).save(path);files[name]={'path':str(path)}
            path=root/'pts.npy';np.save(path,landmarks());files['frontLandmarks']={'path':str(path)}
            path=root/'view.npz';np.savez(path,hit=np.ones(shape,bool));files['frontView']={'path':str(path)}
            labels=np.ones((4,4),np.uint8);labels[1,1]=8;mapped=np.ones_like(labels,bool)
            lid=np.zeros_like(labels);lid[0,0]=lid[1,1]=255
            def project(value,view,regions,size,*,visible_only=()):
                self.assertEqual(visible_only,('upperLid',))
                self.assertTrue(regions['upperLid'].any());self.assertFalse(regions['browEdge'].any())
                return {'upperLid':lid,'browEdge':np.zeros_like(labels)},{}
            with patch('headkit.brow_edges.project',side_effect=project):
                result,report=adjust(labels,{}, {'files':files},mapped,recover_brows=False)
            self.assertEqual(result[0,0],0);self.assertEqual(result[0,1],1);self.assertEqual(result[1,1],8)
            self.assertEqual(report['upperLidHairToSkinTexels'],1)
            self.assertIsNone(report['maximumFrontPixels'])

    def test_recovery_does_not_reintroduce_a_lid_classified_as_brow(self):
        shape=(100,180);lids=upper_lids(shape,landmarks(),np.ones(shape,bool))
        seed=np.ones(shape,bool);core=np.ones(shape,bool);eyes=np.zeros(shape,bool)
        recovered=fringe(seed,core,eyes,lids,8)
        self.assertFalse((recovered & lids).any())
        self.assertTrue(recovered[30,40])


if __name__=='__main__':unittest.main()
