"""Filtering equivalence and retained final-atlas provenance regressions."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from tools.itemkit.atlas import region_gutters,unwrap_parts


class AtlasTests(unittest.TestCase):
    def test_padding_candidates_are_bounded_before_asset_work(self):
        for values in ([],[4],[33],[8,8],[16,8],[True],[8,12,16,32]):
            with self.assertRaisesRegex(ValueError,'Ordered unique atlas paddings'):
                unwrap_parts('not-opened',{},'not-created',packing_paddings=values)
    def test_separable_gutters_match_explicit_neighbourhoods(self):
        rng=np.random.default_rng(317)
        for shape in ((1,1),(1,13),(17,1),(9,11),(31,27)):
            owners=rng.integers(-1,9,size=shape);regions=np.array([1,1,7,9,3,1,12,14,9])
            expected={}
            for radius in (1,2,4):
                collisions=0
                for y,x in np.ndindex(shape):
                    window=owners[max(0,y-radius):y+radius+1,max(0,x-radius):x+radius+1]
                    collisions+=len(np.unique(regions[window[window>=0]]))>1
                expected[str(radius)]=collisions
            self.assertEqual(region_gutters(owners,regions)['nearbyChartPixelsByRadius'],expected)
        empty=np.full((11,17),-1,np.int32)
        self.assertEqual(region_gutters(empty,regions)['nearbyChartPixelsByRadius'],dict.fromkeys(('1','2','4'),0))

    def test_proof_records_isolated_faces_not_last_native_part_group(self):
        from tools.itemkit.test_itemkit import GeometryTests
        p,f=GeometryTests().tetra();uv=[]
        for i in range(12):
            x=(i%4)/4+.006;y=(i//4)/3+.006
            uv.append(((x,y),(x+.238,y),(x,y+.321)))
        class Atlas:width=2048;height=2048
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'parts.npz';values={}
            for part in ('b','m','t'):
                values.update({part+'_positions':p,part+'_faces':f,part+'_hiddenCaps':np.zeros(len(f),bool)})
            np.savez(source,**values)
            with patch('tools.itemkit.atlas.library'),patch('tools.itemkit.atlas._pack',return_value=(np.array(uv),Atlas(),12)) as pack:
                result=unwrap_parts(source,{},root/'atlas',packing_paddings=[8,12,16])
            self.assertEqual(pack.call_args.kwargs['padding'],8)
            with np.load(result['regionProof']['path']) as proof:
                self.assertEqual(proof['isolatedFaces'].tolist(),[])
            with np.load(result['atlas']['path']) as output:
                for part in ('b','m','t'):
                    np.testing.assert_array_equal(output[part+'_positions'],p)
                    np.testing.assert_array_equal(output[part+'_faces'],f)
                    self.assertEqual(output[part+'_uvRegions'].shape,(len(f),))
                    self.assertTrue(np.all(output[part+'_uvRegions']>=0))


if __name__=='__main__':unittest.main()
