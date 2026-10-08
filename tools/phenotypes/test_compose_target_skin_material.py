import struct, tempfile, unittest
from pathlib import Path
import numpy as np
from compose_target_skin_material import plt_read, plt_write, tga_read, tga_write, soft_limit, pad, sample, stats, raster, surface, blur, gauss, valley_clamp
from compose_target_skin_material import nearest, smoothstep01, level_shift, contrast_gain, raster_interp


def tga_bytes(img, top):
    h, w = img.shape[:2]
    head = struct.pack('<BBBHHBHHHHBB', 0, 0, 2, 0, 0, 0, 0, 0, w, h, 24, 0x20 if top else 0)
    rows = img if top else img[::-1]
    return head + np.ascontiguousarray(rows[:, :, ::-1]).tobytes()


class ComposeSkinMaterialTest(unittest.TestCase):
    def test_plt_round_trip_keeps_layers_and_orientation(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            raw = np.zeros((4, 8, 2), np.uint8); raw[0, :, 0] = 7; raw[:, :, 1] = 3   # raw row 0 is the bottom row
            (d / 'a.plt').write_bytes(b'PLT V1  ' + struct.pack('<IIII', 10, 0, 8, 4) + raw.tobytes())
            head, img = plt_read(d / 'a.plt')
            self.assertTrue((img[-1, :, 0] == 7).all())                              # top-down: bottom row last
            plt_write(d / 'b.plt', head, img)
            self.assertEqual((d / 'a.plt').read_bytes(), (d / 'b.plt').read_bytes())

    def test_tga_round_trip_both_origins(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            img = np.random.default_rng(1).integers(0, 255, (4, 6, 3), dtype=np.uint8)
            for top in (True, False):
                (d / 'a.tga').write_bytes(tga_bytes(img, top))
                meta, got = tga_read(d / 'a.tga')
                self.assertTrue((got == img).all())
                tga_write(d / 'b.tga', meta, got)
                self.assertEqual((d / 'a.tga').read_bytes(), (d / 'b.tga').read_bytes())

    def test_soft_limit_monotone_and_bounded(self):
        x = np.linspace(-100, 400, 2001)
        y = soft_limit(x, 14, 242)
        self.assertTrue(np.all(np.diff(y) > 0))
        self.assertGreater(y.min(), 14 - 1e-9); self.assertLess(y.max(), 242 + 1e-9)
        mid = (x > 40) & (x < 220)
        self.assertTrue(np.allclose(y[mid], x[mid]))

    def test_pad_fills_from_valid_neighbours(self):
        img = np.zeros((5, 5), 'f4'); valid = np.zeros((5, 5), bool); img[2, 2] = 9; valid[2, 2] = True
        out, ok = pad(img, valid, 4)
        self.assertTrue(ok.all()); self.assertTrue(np.allclose(out, 9))

    def test_masked_blur_ignores_empty_atlas(self):
        img = np.zeros((32, 32), 'f4'); mask = np.zeros((32, 32), bool); mask[:, :16] = True; img[mask] = 100
        self.assertTrue(np.allclose(blur(img, 3, mask)[mask], 100, atol=1e-3))   # no darkening from empty texels
        self.assertLess(blur(img, 3)[:, 15].mean(), 90)                           # unmasked blur bleeds
        g = gauss(np.ones((8, 8, 3), 'f4'), 2)
        self.assertTrue(np.allclose(g, 1))

    def test_valley_clamp_softens_thin_lines_keeps_broad_shade(self):
        X = np.ones((64, 64), 'f4'); X[:, 30:32] = 0.3          # thin groove
        X[:, 48:] = 0.4                                          # broad occluded area
        mask = np.ones((64, 64), bool)
        Y = valley_clamp(X, mask, 4, 0.1)
        self.assertGreater(Y[:, 30].min(), 0.75)
        self.assertTrue(np.allclose(Y[:, 56:], 0.4, atol=0.02))
        W = np.zeros((64, 64), 'f4'); W[:, 28:34] = 1
        self.assertGreater(valley_clamp(X, mask, 4, 0.1, W)[:, 30].min(), Y[:, 30].min())

    def test_sample_raster_surface_stats(self):
        img = np.tile(np.arange(8, dtype='f4'), (8, 1))
        v = sample(img, np.array([[0.5 / 8 + 3 / 8, 0.5]]))
        self.assertAlmostEqual(float(v[0]), 3.0, places=5)
        r = raster(np.array([[[0, 0], [1, 0], [0, 1]]]), [5.0], 16)
        self.assertEqual(r[2, 2], 5.0); self.assertEqual(r[15, 15], 0.0)
        P = np.array([[[0, 0, 0], [1, 0, 0], [0, 1, 0]]], float); T = P[:, :, :2]
        sp, suv = surface(P, T, 500, 3)
        self.assertTrue(np.allclose(sp[:, :2], suv)); self.assertTrue(np.all(sp[:, :2].sum(1) <= 1 + 1e-9))
        s = stats(np.arange(101))
        self.assertAlmostEqual(s['mean'], 50); self.assertAlmostEqual(s['p1'], 1)

    def test_nearest_and_smoothstep(self):
        ref = np.array([[0, 0, 0], [1, 0, 0], [0, 2, 0]], 'f4'); q = np.array([[0.9, 0, 0], [0, 1.5, 0]], 'f4')
        d, k = nearest(q, ref, chunk=1)
        self.assertEqual(k.tolist(), [1, 2]); self.assertTrue(np.allclose(d, [0.1, 0.5], atol=1e-6))
        self.assertEqual(float(smoothstep01(-1)), 0.0); self.assertEqual(float(smoothstep01(2)), 1.0)
        self.assertAlmostEqual(float(smoothstep01(0.5)), 0.5)

    def test_level_shift_matches_reference_luminance(self):
        L = np.linspace(0, 255, 256)   # identity palette row: luminance == shade
        cur = {'a': np.full(100, 150.0), 'b': np.full(100, 130.0)}; ref = {'a': np.full(10, 120.0), 'b': np.full(10, 110.0)}
        shift, target = level_shift(cur, {'a': 1.0, 'b': 3.0}, ref, [L])
        self.assertAlmostEqual(target, (120 + 3 * 110) / 4)
        self.assertAlmostEqual(shift, target - (150 + 3 * 130) / 4, delta=0.6)   # PLT byte rounding
        shift_b, target_b = level_shift(cur, {'a': 1.0, 'b': 3.0}, ref, [L], bias=-5.0)
        self.assertAlmostEqual(target_b, target - 5.0); self.assertAlmostEqual(shift_b, shift - 5.0, delta=1.0)
        with self.assertRaises(Exception):
            level_shift(cur, {'a': 1.0, 'b': 1.0}, {'a': np.full(5, 400.0), 'b': np.full(5, 400.0)}, [L])

    def test_contrast_gain_restores_disk_contrast(self):
        L = np.linspace(0, 255, 256)
        v = np.r_[np.full(50, 100.0), np.full(50, 120.0)]; disk = np.arange(100) < 50; ring = ~disk
        g, after = contrast_gain(v, disk.astype(float), disk, ring, 120.0, -40.0, [L])
        self.assertAlmostEqual(g, 2.0, delta=0.03); self.assertAlmostEqual(after, -40.0, places=4)   # PLT byte rounding

    def test_raster_interp_is_barycentric(self):
        UV = np.array([[[0, 0], [1, 0], [0, 1]]], float); vals = np.array([[[0.0], [8.0], [0.0]]])
        img, hit = raster_interp(UV, vals, 8, [0])
        self.assertTrue(hit[0, 0]); self.assertFalse(hit[7, 7])
        self.assertAlmostEqual(float(img[0, 3, 0]), 3.5, places=4)   # u = 3.5/8 -> 8 * u


if __name__ == '__main__':
    unittest.main()
