"""Texture downsampling regressions on synthetic PLT/TGA payloads."""
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest

import numpy as np

from . import texture_downsample as tex
from ..inputs import consumed

FOOTER = bytes(8) + b'TRUEVISION-XFILE.\0'


def plt(pixels):
    h, w = pixels.shape[:2]
    return b'PLT V1  ' + struct.pack('<IIII', 10, 0, w, h) + pixels.astype(np.uint8).tobytes()


def tga(pixels):
    h, w = pixels.shape[:2]
    return struct.pack('<BBB5xHHHHBB', 0, 0, 2, 0, 0, w, h, 24, 0) + pixels.astype(np.uint8).tobytes() + FOOTER


class ReductionTests(unittest.TestCase):
    def test_palette_mode_layer_tie_order_and_winning_layer_intensity(self):
        rows = [[(10, 4), (20, 4), (30, 0), (40, 2)],     # block 1: cloth 2 texels wins over skin/metal
                [(50, 0), (70, 4), (99, 5), (1, 5)],      # block 2: cloth2 2 texels wins
                [(100, 0), (200, 4), (8, 2), (9, 7)],     # block 3: 1-1-1-1 tie, skin first
                [(0, 4), (0, 5), (3, 7), (5, 2)]]         # block 4: tie between 4,5,7,2: cloth 4 first
        pixels = np.zeros((2, 8, 2), np.uint8)
        for b, block in enumerate(rows):
            for i, (value, layer) in enumerate(block):
                pixels[i//2, 2*b+i % 2] = (value, layer)
        data, stats = tex.reduce_plt(plt(pixels))
        self.assertEqual(struct.unpack_from('<II', data, 16), (4, 1))
        out = np.frombuffer(data, np.uint8, offset=24).reshape(1, 4, 2)
        self.assertEqual(out[0, :, 1].tolist(), [4, 5, 0, 4])
        self.assertEqual(out[0, :, 0].tolist(), [15, 50, 100, 0])
        self.assertEqual(stats['mixedBlocks'], 4)

    def test_mean_rounds_ties_to_even(self):
        self.assertEqual(tex.mean_round(np.array([2, 6, 5, 7]), 4).tolist(), [0, 2, 1, 2])

    def test_normals_are_averaged_renormalized_with_z_floor_and_footer_kept(self):
        flat = np.array([255, 128, 128]); tilt = np.array([128, 128, 255])  # BGR: (0,0,1) and grazing +X
        pixels = np.array([[flat, tilt], [flat, tilt]], np.uint8)
        data, stats = tex.reduce_normal(tga(pixels))
        head, out, tail = tex.tga_parts(data)
        self.assertEqual((out.shape, tail), ((1, 1, 3), FOOTER))
        v = out[0, 0, ::-1]/255*2-1
        self.assertAlmostEqual(np.linalg.norm(v), 1, delta=0.01)
        self.assertAlmostEqual(v[0], v[2], delta=0.02)          # 45 degrees between the two inputs
        steep = np.array([[[128, 128, 255]]*2]*2, np.uint8)      # all grazing: z floor keeps a usable normal
        self.assertGreaterEqual(tex.tga_parts(tex.reduce_normal(tga(steep))[0])[1][0, 0, 0], 130)

    def test_roughness_is_a_linear_channel_mean(self):
        pixels = np.array([[[0, 10, 255], [2, 10, 255]], [[4, 11, 0], [6, 11, 0]]], np.uint8)
        data, _ = tex.reduce_roughness(tga(pixels))
        self.assertEqual(tex.tga_parts(data)[1][0, 0].tolist(), [3, 10, 128])


class DownsampleTests(unittest.TestCase):
    def test_roles_from_materials_shared_payloads_once_and_small_textures_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root/'body').mkdir(); rng = np.random.default_rng(1); rows = []
            def put(path, data, role):
                (root/path).write_bytes(data)
                rows.append({'path': path, 'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data), 'role': role})
            chest = plt(np.stack([rng.integers(0, 255, (8, 8)), rng.choice([0, 4], (8, 8))], -1))
            put('body/pfx0_chest001.plt', chest, 'selected-palette'); put('body/pfx2_chest001.plt', chest, 'selected-palette')
            put('body/small.plt', plt(np.zeros((4, 4, 2))), 'selected-palette')
            put('body/skin_n.tga', tga(np.full((8, 8, 3), (255, 128, 128))), 'selected-map')
            put('body/skin_r.tga', tga(rng.integers(0, 255, (8, 8, 3))), 'selected-map')
            put('body/skin.mtr', b'renderhint NormalTangents\ntexture1 skin_n\ntexture3 skin_r\n', 'selected-material')
            (root/'m.json').write_text(json.dumps({'resources': rows}))
            receipt = tex.downsample(root, root/'m.json', root/'out', max_size=4)
            self.assertEqual(receipt['summary']['resources'], 4); self.assertEqual(receipt['summary']['uniquePayloads'], 3)
            self.assertEqual({r['path']: r['kind'] for r in receipt['resources']}, {
                'body/pfx0_chest001.plt': 'palette', 'body/pfx2_chest001.plt': 'palette',
                'body/skin_n.tga': 'normal', 'body/skin_r.tga': 'roughness'})
            self.assertEqual((root/'out/body/pfx0_chest001.plt').read_bytes(), (root/'out/body/pfx2_chest001.plt').read_bytes())
            self.assertFalse((root/'out/body/small.plt').exists())
            self.assertEqual(struct.unpack_from('<HH', (root/'out/body/skin_r.tga').read_bytes(), 12), (4, 4))
            declared = consumed(['downsample-textures', '--root', str(root), '--manifest', str(root/'m.json'), '--output', str(root/'x')])
            self.assertIn((root/'body/skin.mtr').resolve(), declared)
            (root/'body/stray.tga').write_bytes(tga(np.zeros((8, 8, 3))))
            rows.append({'path': 'body/stray.tga', 'sha256': hashlib.sha256((root/'body/stray.tga').read_bytes()).hexdigest(),
                         'bytes': 0, 'role': 'selected-map'})
            (root/'m.json').write_text(json.dumps({'resources': rows}))
            with self.assertRaisesRegex(ValueError, 'Map role unknown'):
                tex.downsample(root, root/'m.json', root/'out2', max_size=4)

    def test_every_pass_of_a_multi_pass_reduction_is_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); data = plt(np.stack([np.full((16, 16), 200), np.zeros((16, 16))], -1)); (root/'a.plt').write_bytes(data)
            (root/'m.json').write_text(json.dumps({'resources': [{'path': 'a.plt', 'sha256': hashlib.sha256(data).hexdigest(),
                                                                  'bytes': len(data), 'role': 'selected-palette'}]}))
            stats = next(iter(tex.downsample(root, root/'m.json', root/'out', max_size=4)['payloads'].values()))['stats']
            self.assertEqual([(s['from'], s['to']) for s in stats], [([16, 16], [8, 8]), ([8, 8], [4, 4])])
            self.assertEqual(stats[0]['layerTexelsBefore'][0], 256)  # the published source, not an intermediate


if __name__ == '__main__':
    unittest.main()
