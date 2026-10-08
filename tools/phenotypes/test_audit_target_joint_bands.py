"""Raw UV orientation, finite area, spatial bands and facing-compatible colors."""
from pathlib import Path
import struct
import tempfile
import unittest

import numpy as np

from audit_target_joint_bands import band_mask, match, sample_pixels, samples, statistics, summarize_pair, stock_neck_inputs


class TargetJointBandTests(unittest.TestCase):
    def test_stock_neck_sampling_uses_declared_female_family_and_frozen_plt(self):
        import target_contract as contract
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); neck = root/'pfh0_neck001.mdl'; plt = root/'pfh0_neck001.plt'
            neck.write_text('node trimesh neck\n bitmap pfh0_neck001\n verts 3\n 0 0 0\n 1 0 0\n 0 1 0\n tverts 3\n .5 .5 0\n .5 .5 0\n .5 .5 0\n faces 1\n 0 1 2 1 0 1 2 1\nendnode\n')
            plt.write_bytes(b'PLT V1  '+struct.pack('<IIII',10,0,1,1)+bytes([91,0]))
            selected = {'ascii':str(neck),'asciiSha256':contract.sha(neck),'plt':str(plt),'pltSha256':contract.sha(plt)}
            palette = np.repeat(np.arange(256,dtype='u1')[None,:,None],3,axis=2)
            result, _ = stock_neck_inputs(selected,palette,[0],'pfh0')
            self.assertEqual(result['sourceBitmap'],'pfh0_neck001')
            self.assertEqual(result['usedMeshUvPltShade']['mean'],[91])
            with self.assertRaisesRegex(ValueError,'neck bitmap'): stock_neck_inputs(selected,palette,[0],'pmh0')
            plt.write_bytes(plt.read_bytes()[:-1])
            with self.assertRaises(ValueError): stock_neck_inputs(selected,palette,[0],'pfh0')

    def test_raw_gltf_uv_origin_and_texture_center_sampling(self):
        image = np.array([[[10,20,30],[40,50,60]],[[70,80,90],[100,110,120]]],dtype='u1')
        before = image.copy()
        actual = sample_pixels(image,[[.25,.25],[.75,.25],[.25,.75],[.75,.75],[.5,.5]],33071,33071)
        np.testing.assert_array_equal(actual[:4],image.reshape(4,3))
        np.testing.assert_array_equal(actual[4],[55,65,75]); np.testing.assert_array_equal(image,before)

    def test_wrap_policy_is_explicit(self):
        image = np.array([[10,100],[20,200]],dtype='u1')
        self.assertEqual(sample_pixels(image,[[1.25,.25]],10497,33071)[0,0],10)
        self.assertEqual(sample_pixels(image,[[1.25,.25]],33071,33071)[0,0],100)
        self.assertEqual(sample_pixels(image,[[1.25,.25]],33648,33071)[0,0],100)
        with self.assertRaises(ValueError): sample_pixels(image,[[.5,.5]],42,33071)

    def test_attachment_frames_and_triangle_area_weights_preserved(self):
        p = np.array([[[0,0,0],[1,0,0],[0,1,0]]],float); n = np.tile([0,0,1],(1,3,1)); uv = p[...,:2]
        frame = np.eye(4); frame[:3,3] = [4,5,6]
        actual = samples(p,n,uv,[0],frame)
        np.testing.assert_allclose(actual['world'][0],[4+1/3,5+1/3,6])
        self.assertEqual(actual['weight'].sum(),.5)
        np.testing.assert_array_equal(actual['normal'],np.tile([0,0,1],(4,1)))
        # Sampling records coordinate values only; inputs do not receive the frame.
        np.testing.assert_array_equal(p[0,0],[0,0,0])

    def test_joint_cylinder_uses_axial_and_radial_limits(self):
        points = np.array([[0,0,.02],[.05,0,.02],[.11,0,.02],[0,0,.2]])
        np.testing.assert_array_equal(band_mask(points,[0,0,0],[0,0,2],[-.05,.05],.1),[True,True,False,False])
        with self.assertRaises(ValueError): band_mask(points,[0,0,0],[0,0,0],[-.05,.05],.1)

    def test_matching_rejects_nearest_opposite_facing_cap_and_distant_points(self):
        source = {'world':np.array([[0,0,0],[1,0,0]]), 'normal':np.array([[0,0,1],[0,0,1]]), 'weight':np.ones(2)}
        target = {'world':np.array([[0,0,.001],[0,0,.01]]),'normal':np.array([[0,0,-1],[0,0,1]]),'weight':np.ones(2)}
        result = match(source,target,.02,.5,2)
        np.testing.assert_array_equal(result['source'],[0]); np.testing.assert_array_equal(result['target'],[1])
        self.assertEqual(result['coverageSamples'],.5); self.assertEqual(result['coverageArea'],.5)

    def test_weighted_color_and_shade_deltas_preserve_sign_and_palette_inputs(self):
        source = {'world':np.array([[0,0,0],[1,0,0]]),'normal':np.tile([0,0,1],(2,1)),
                  'weight':np.array([1,3]),'rgb':np.array([[60,50,40],[70,60,50]]),'shade':np.array([50,60])}
        target = {**source,'rgb':source['rgb']-10,'shade':source['shade']-10}
        result = match(source,target,.001,.5,1)
        palette = np.repeat(np.arange(256,dtype='u1')[None,:,None],3,axis=2)
        proof = summarize_pair(source,target,result,palette,[0])
        self.assertEqual(proof['untreatedPltShadeSignedDifference']['mean'],[10])
        self.assertEqual(proof['originalByteRgbSignedDifference']['mean'],[10,10,10])
        self.assertEqual(proof['paletteInputColorDifference']['0']['mean'],[10,10,10])
        weighted = statistics(np.array([0,100]),np.array([1,3])); self.assertEqual(weighted['mean'],[75])

    def test_bounded_cell_matching_agrees_with_brute_force_nearest_candidates(self):
        random = np.random.default_rng(8192)
        source = {'world':random.uniform(-.03,.03,(90,3)),'normal':np.tile([0,0,1],(90,1)),'weight':np.ones(90)}
        target = {'world':random.uniform(-.03,.03,(70,3)),'normal':np.tile([0,0,1],(70,1)),'weight':np.ones(70)}
        target['normal'][::3] *= -1
        distance = .018; neighbors = 5; actual = match(source,target,distance,.5,neighbors)
        expected_rows = []; expected_targets = []
        for index,point in enumerate(source['world']):
            distances = np.linalg.norm(target['world']-point,axis=1)
            candidates = np.argsort(distances)[:neighbors]
            allowed = candidates[(distances[candidates] <= distance)&(target['normal'][candidates,2] >= .5)]
            if len(allowed): expected_rows.append(index); expected_targets.append(allowed[0])
        np.testing.assert_array_equal(actual['source'],expected_rows)
        np.testing.assert_array_equal(actual['target'],expected_targets)


if __name__ == '__main__': unittest.main()
