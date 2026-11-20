import hashlib
import unittest
from pathlib import Path

import numpy as np

import plt_repair as pr

SIZE = 64
ROOT = Path(__file__).resolve().parents[2]


def grid_mesh(n=16):
    """A curved strip (z bulges in the middle) mapped edge to edge with a small margin."""
    xs = np.linspace(0, 1, n+1)
    vx, vy = np.meshgrid(xs, xs)
    positions = np.c_[vx.ravel(), vy.ravel(), (np.sin(vx*np.pi)*0.3).ravel()]
    uv = np.c_[vx.ravel(), 1-vy.ravel()]*0.9+0.05
    faces = []
    for j in range(n):
        for i in range(n):
            a = j*(n+1)+i; b = a+1; c = a+n+1; d = c+1
            faces += [[a, b, d], [a, d, c]]
    faces = np.array(faces, np.int64)
    return {'positions': positions, 'faces': faces, 'uv': uv[faces]}


def palettes():
    ramp = np.zeros((176, 256, 3), np.uint8); ramp[:, :, :] = np.arange(256, dtype=np.uint8)[None, :, None]
    return {c: ramp for c in range(10)}


def header(size=SIZE):
    return pr.PLT_MAGIC+np.array([10, 0, size, size], '<u4').tobytes()


def spec(*operations, **extra):
    return {'schemaVersion': 1, 'model': 'test', 'source': {'plt': {'sha256': 'a'*64}, 'mdl': {'sha256': 'b'*64}},
            'operations': list(operations), **extra}


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.value = grid_mesh(); cls.texels = pr.Texels(cls.value, SIZE); cls.pal = palettes()

    def planes(self, shade=100, channel=1):
        return np.full((SIZE, SIZE), shade, np.uint8), np.full((SIZE, SIZE), channel, np.uint8)

    def run_spec(self, s, shades, layers):
        return pr.repair(s, self.value, header(), shades, layers, self.pal, self.texels)


class PltFormat(unittest.TestCase):
    def test_round_trip_keeps_header_and_orientation(self):
        shades = np.arange(SIZE*SIZE, dtype=np.uint32).reshape(SIZE, SIZE).astype(np.uint8)
        layers = (np.arange(SIZE)[:, None] % 10).repeat(SIZE, 1).astype(np.uint8)
        raw = pr.write_plt(header(), shades, layers)
        head, s, l = pr.read_plt(raw)
        self.assertEqual(head, header()); np.testing.assert_array_equal(s, shades); np.testing.assert_array_equal(l, layers)
        # PLT rows are stored bottom first: the first stored pair is the last top-down row.
        self.assertEqual(raw[24:26], bytes([shades[-1, 0], layers[-1, 0]]))

    def test_rejects_bad_files(self):
        with self.assertRaises(ValueError): pr.read_plt(b'NOT A PLT'+bytes(30))
        with self.assertRaises(ValueError): pr.read_plt(header()+bytes(10))
        with self.assertRaises(ValueError): pr.write_plt(header(), *[np.zeros((SIZE, SIZE), np.uint8)]*1, np.full((SIZE, SIZE), 10, np.uint8))

    def test_published_head_maps_to_headkit_frame(self):
        model = 'pfo0_head014'; path = ROOT/'srn_head'/(model+'.mdl')
        if not path.is_file(): self.skipTest('published head not present')
        value = pr.native_mesh(path.read_bytes(), model)
        p = value['positions']; lo, hi = p.min(0), p.max(0); unit = (p-lo)/(hi-lo)
        tip = unit[np.argmax(unit[:, 2])]
        # The most forward point (nose or tusk) sits near the middle, below the crown: the face looks along +z.
        self.assertLess(abs(tip[0]-0.5), 0.2); self.assertLess(tip[1], 0.8)
        self.assertTrue(((value['uv'] >= 0) & (value['uv'] <= 1)).all())


class SpecValidation(unittest.TestCase):
    def test_refusals(self):
        good = {'name': 'a', 'op': 'shade', 'shade': 3, 'when': {'channel': 1}}
        pr.validate_spec(spec(good))
        for bad in (spec(), spec(good, dict(good)), spec(dict(good, op='blur')), spec(dict(good, shade=300)),
                    spec({'name': 'c', 'op': 'curve', 'points': [[0, 0], [200, 10]], 'when': {'channel': 1}}),
                    spec({'name': 'c', 'op': 'curve', 'points': [[0, 0], [100, 50], [90, 60], [255, 255]], 'when': {'channel': 1}}),
                    spec({'name': 'm', 'op': 'match', 'when': {'channel': 1}}),
                    spec(dict(good, op='channel', channel=12)),
                    {**spec(good), 'source': {}}, {**spec(good), 'schemaVersion': 2}):
            with self.subTest(bad=bad), self.assertRaises(ValueError): pr.validate_spec(bad)

    def test_pins(self):
        s = spec({'name': 'a', 'op': 'shade', 'shade': 3, 'when': {'channel': 1}})
        s['source'] = {'plt': {'sha256': hashlib.sha256(b'p').hexdigest()}, 'mdl': {'sha256': hashlib.sha256(b'm').hexdigest()}}
        pr.check_pins(s, b'p', b'm')
        with self.assertRaises(ValueError): pr.check_pins(s, b'q', b'm')
        with self.assertRaises(ValueError): pr.check_pins(s, b'p', b'n')


class Operations(Base):
    def test_fill_replaces_a_blotch_with_its_surroundings(self):
        shades, layers = self.planes(100); shades[20:30, 20:30] = 5
        out, lay, report = self.run_spec(spec({'name': 'blotch', 'op': 'fill', 'when': {'of': 'shade', 'lt': 50}}), shades, layers)
        self.assertTrue((out[self.texels.mapped] == 100).all()); np.testing.assert_array_equal(lay, layers)
        self.assertEqual(report['operations'][0]['changed'], int(self.texels.mapped[20:30, 20:30].sum()))
        self.assertTrue((shades[20:30, 20:30] == 5).all(), 'inputs are not modified')

    def test_fill_into_another_channel_uses_that_channel(self):
        shades, layers = self.planes(100, 1); layers[:, :32] = 0; shades[:, :32] = 200; layers[20:24, 40:44] = 0; shades[20:24, 40:44] = 7
        s = spec({'name': 'patch', 'op': 'fill', 'channel': 1, 'when': {'all': [{'channel': 0}, {'of': 'u', 'gt': 0.6}]}})
        out, lay, _ = self.run_spec(s, shades, layers)
        block = self.texels.mapped[20:24, 40:44]
        self.assertTrue((lay[20:24, 40:44][block] == 1).all()); self.assertTrue((out[20:24, 40:44][block] == 100).all())
        self.assertTrue((lay[10:50, 5:30][self.texels.mapped[10:50, 5:30]] == 0).all())

    def test_despeckle_side(self):
        shades, layers = self.planes(100); shades[30, 30] = 10; shades[40, 40] = 240
        dark = spec({'name': 'd', 'op': 'despeckle', 'threshold': 40, 'side': 'darker', 'when': {'channel': 1}})
        out, _, _ = self.run_spec(dark, shades, layers)
        self.assertEqual(out[30, 30], 100); self.assertEqual(out[40, 40], 240)
        both = spec({'name': 'd', 'op': 'despeckle', 'threshold': 40, 'when': {'channel': 1}})
        out, _, _ = self.run_spec(both, shades, layers)
        self.assertEqual(out[30, 30], 100); self.assertEqual(out[40, 40], 100)

    def test_match_takes_the_reference_distribution_and_keeps_order(self):
        rng = np.random.default_rng(1)
        shades, layers = self.planes(); shades[:, :32] = rng.integers(150, 250, (SIZE, 32)); shades[:, 32:] = rng.integers(20, 60, (SIZE, 32))
        s = spec({'name': 'm', 'op': 'match', 'when': {'of': 'u', 'lt': 0.5}, 'reference': {'of': 'u', 'ge': 0.5}, 'maxFraction': 0.6})
        out, _, _ = self.run_spec(s, shades, layers)
        left = self.texels.mapped & (np.arange(SIZE)[None, :] < 32)
        self.assertTrue(20 <= out[left].min() and out[left].max() <= 60)
        a, b = np.argsort(shades[left], kind='stable'), out[left]
        self.assertTrue((np.diff(b[a].astype(int)) >= 0).all(), 'rank order is kept')

    def test_curve_and_ramp(self):
        shades, layers = self.planes(200)
        s = spec({'name': 'c', 'op': 'curve', 'points': [[0, 0], [100, 100], [255, 150]], 'when': {'channel': 1},
                  'ramp': {'of': 'u', 'from': 0.3, 'to': 0.6}, 'maxFraction': 1})
        out, _, _ = self.run_spec(s, shades, layers)
        m = self.texels.mapped
        self.assertTrue((out[:, :10][m[:, :10]] == 200).all())
        self.assertTrue((out[:, 50:][m[:, 50:]] == 132).all())
        mid = out[32, 20:40]; self.assertTrue((np.diff(mid.astype(int)) <= 0).all())

    def test_relabel_moves_a_fleck_and_respects_to(self):
        shades, layers = self.planes(100, 1); layers[30:32, 30:32] = 0; shades[30:32, 30:32] = 220
        out, lay, rep = self.run_spec(spec({'name': 'r', 'op': 'relabel', 'when': {'channel': 0}}), shades, layers)
        self.assertTrue((lay[30:32, 30:32] == 1).all()); self.assertTrue((out[30:32, 30:32] == 100).all())
        self.assertEqual(rep['operations'][0]['detail']['moved'], 4)
        _, lay, _ = self.run_spec(spec({'name': 'r', 'op': 'relabel', 'to': [0, 8], 'when': {'channel': 0}}), shades, layers)
        self.assertTrue((lay[30:32, 30:32] == 0).all())

    def test_clamp_reference_percentiles(self):
        shades, layers = self.planes(); shades[:] = np.arange(SIZE)[None, :]*3
        s = spec({'name': 'c', 'op': 'clamp', 'when': {'of': 'u', 'lt': 0.5}, 'reference': {'of': 'u', 'ge': 0.5},
                  'percentiles': [50, 100], 'maxFraction': 0.6})
        out, _, rep = self.run_spec(s, shades, layers)
        lo = rep['operations'][0]['detail']['bounds'][0]
        left = self.texels.mapped & (np.arange(SIZE)[None, :] < 32)
        self.assertTrue((out[left] >= lo).all() and lo > shades[left].max())


class ReviewRegressions(Base):
    def test_relabel_on_a_tiny_pool(self):
        value = grid_mesh(1); texels = pr.Texels(value, 8)
        shades = np.full((8, 8), 100, np.uint8); layers = np.ones((8, 8), np.uint8); layers[texels.mapped] = 1
        s = spec({'name': 'r', 'op': 'relabel', 'neighbours': 256, 'when': {'channel': 1}, 'maxFraction': 1})
        pr.repair(s, value, header(8), shades, layers, self.pal, texels)

    def test_missing_palette_previews_grey(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            pal = pr.load_palettes(d, {4})
        self.assertEqual(pal[4].shape, (176, 256, 3)); self.assertEqual(pal[4][3, 77].tolist(), [77, 77, 77])

    def test_validation_catches_bad_ramps_clamps_and_curves(self):
        base = {'name': 'c', 'when': {'channel': 1}}
        for op in ({**base, 'op': 'curve', 'points': [[0, 'a'], [255, 255]]},
                   {**base, 'op': 'curve', 'points': [[0, 0], [255, 255]], 'ramp': {'of': 'z', 'from': 0.5}},
                   {**base, 'op': 'clamp', 'reference': {'channel': 1}, 'percentiles': [5]},
                   {**base, 'op': 'clamp', 'lo': '3'}):
            with self.subTest(op=op), self.assertRaises(ValueError): pr.validate_spec(spec(op))

    def test_validation_refuses_unknown_keys_and_bad_parameters(self):
        base = {'name': 'd', 'when': {'channel': 1}}
        for op in ({**base, 'op': 'despeckle', 'threshold': 10, 'neighbors': 48},
                   {**base, 'op': 'despeckle'},
                   {**base, 'op': 'despeckle', 'threshold': 10, 'side': 'up'},
                   {**base, 'op': 'fill', 'neighbours': 0},
                   {**base, 'op': 'match', 'reference': {'channel': 1}, 'strength': 2},
                   {**base, 'op': 'relabel', 'minshare': 0.8},
                   {**base, 'op': 'relabel', 'to': [12]},
                   {**base, 'op': 'shade', 'shade': 1, 'maxFraction': 0},
                   {**base, 'op': 'shade', 'shade': 1, 'allowEmpty': 'yes'}):
            with self.subTest(op=op), self.assertRaises(ValueError): pr.validate_spec(spec(op))
        op = {**base, 'op': 'shade', 'shade': 1}
        for rows in ({'1': -1}, {'12': 3}, {'1': 'a'}):
            with self.subTest(rows=rows), self.assertRaises(ValueError): pr.validate_spec(spec(op, previewRows=rows))
        with self.assertRaises(ValueError): pr.parse_rows('1:-1')

    def test_preview_row_beyond_the_palette_refuses(self):
        shades, layers = self.planes()
        with self.assertRaises(ValueError): pr.decode_colours(shades, layers, self.pal, {1: 176})

    def test_ramp_weight_uses_spec_validation(self):
        values = {'z': np.zeros((SIZE, SIZE))}; target = self.texels.mapped
        with self.assertRaises(ValueError): pr.ramp_weight({'of': 'z', 'from': '0', 'to': 1}, values, target)
        w = pr.ramp_weight([{'of': 'z', 'from': -1, 'to': 1}, {'of': 'z', 'from': -3, 'to': 1}], values, target)
        np.testing.assert_allclose(w, 0.5*0.75)

    def test_spec_keys_names_sources_clamps_and_ramp_quantities(self):
        good = {'name': 'a', 'op': 'shade', 'shade': 3, 'when': {'channel': 1}}
        curve = {'name': 'c', 'op': 'curve', 'points': [[0, 0], [255, 255]], 'when': {'channel': 1}}
        pr.validate_spec(spec(dict(curve, ramp={'of': 'mask:ear', 'from': 0, 'to': 1}), surfaceOutlines={'ear': {}}))
        for bad in (spec(good, previewRow={'1': 65}), spec(good, texture='../srn_head/x'), spec(good, texture='PFO0_HEAD014'),
                    spec(good, texture='a'*17), {**spec(good), 'model': 'a/b'}, {**spec(good), 'source': 'abc'},
                    {**spec(good), 'source': {'plt': 'x', 'mdl': {'sha256': 'b'}}},
                    spec({'name': 'k', 'op': 'clamp', 'reference': {'channel': 1}, 'hi': 200, 'when': {'channel': 1}}),
                    spec({'name': 'k', 'op': 'clamp', 'percentiles': [5, 95], 'when': {'channel': 1}}),
                    spec(dict(curve, ramp={'of': 'lumm', 'from': 0, 'to': 1})),
                    spec(dict(curve, ramp={'of': 'mask:ear', 'from': 0, 'to': 1}))):
            with self.subTest(bad=bad), self.assertRaises(ValueError): pr.validate_spec(bad)

    def test_load_pins_the_texture_and_refuses_non_square(self):
        import argparse, tempfile
        model = 'pfo0_head014'; mdl = ROOT/'srn_head'/(model+'.mdl')
        if not mdl.is_file(): self.skipTest('published head not present')
        with tempfile.TemporaryDirectory() as d:
            plt = Path(d)/'x.plt'; plt.write_bytes(header()+bytes(2*SIZE*SIZE))
            pins = {'plt': {'sha256': hashlib.sha256(plt.read_bytes()).hexdigest()},
                    'mdl': {'sha256': hashlib.sha256(mdl.read_bytes()).hexdigest()}}
            s = {**spec({'name': 'a', 'op': 'shade', 'shade': 3, 'when': {'channel': 1}}), 'model': model, 'source': pins}
            args = lambda texture=None: argparse.Namespace(mdl=str(mdl), plt=str(plt), model=None, texture=texture)
            self.assertEqual(pr.load(args(), s)[1], model)
            self.assertEqual(pr.load(args(model.upper()), s)[1], model)
            with self.assertRaises(ValueError): pr.load(args('other'), s)
            with self.assertRaises(ValueError):
                pr.load(argparse.Namespace(mdl=str(mdl), plt=str(plt), model='pfo0_head015', texture=None), s)
            plt.write_bytes(pr.PLT_MAGIC+np.array([10, 0, SIZE, SIZE//2], '<u4').tobytes()+bytes(SIZE*SIZE))
            with self.assertRaises(ValueError): pr.load(args())

    def test_predicates_refuse_before_any_work(self):
        good = {'name': 'a', 'op': 'shade', 'shade': 3, 'when': {'region': 'nape'}}
        regions = {'nape': {'all': [{'of': 'y', 'lt': 0.4}, {'mask': 'ear'}]}}
        pr.validate_spec(spec(good, regions=regions, surfaceOutlines={'ear': {}}))
        for bad in (spec(dict(good, when={'region': 'nap'}), regions=regions, surfaceOutlines={'ear': {}}),
                    spec(good, regions=regions),
                    spec(dict(good, when={'of': 'lumm', 'gt': 3})),
                    spec({'name': 'f', 'op': 'fill', 'donors': {'of': 'y', 'lt': 'x'}, 'when': {'channel': 1}}),
                    spec({'name': 'm', 'op': 'match', 'reference': {'channel': 12}, 'when': {'channel': 1}})):
            with self.subTest(bad=bad), self.assertRaises(ValueError): pr.validate_spec(bad)

    def test_cli_arguments(self):
        import argparse
        for text in ('1:a', '1', 'x:2'):
            with self.subTest(text=text), self.assertRaises(ValueError): pr.parse_rows(text)
        self.assertEqual(pr.parse_rows('0:5, 1:65'), {0: 5, 1: 65})
        for text in ('0', '-5', '4096'):
            with self.subTest(text=text), self.assertRaises(argparse.ArgumentTypeError): pr.view_size(text)

    def test_apply_writes_nothing_when_a_sheet_fails(self):
        import json, tempfile
        from unittest import mock
        shades, layers = self.planes()
        loaded = ('test', 'test', b'm', b'p', self.value, header(), shades, layers)
        s = spec({'name': 'a', 'op': 'shade', 'shade': 3, 'when': {'all': [{'of': 'u', 'lt': 0.2}, {'of': 'v', 'lt': 0.2}]}})
        with tempfile.TemporaryDirectory() as d, mock.patch.object(pr, 'load', return_value=loaded), \
                mock.patch.object(pr, 'load_palettes', return_value=self.pal), \
                mock.patch.object(pr, 'render', side_effect=RuntimeError('embree')):
            path = Path(d)/'s.json'; path.write_text(json.dumps(s), encoding='utf-8'); out = Path(d)/'out'
            with self.assertRaises(RuntimeError):
                pr.main(['apply', '--mdl', 'm', '--plt', 'p', '--palettes', d, '--embree', 'e', '--out', str(out), '--spec', str(path)])
            self.assertFalse((out/'test.plt').exists() or (out/'receipt.json').exists())


class Guards(Base):
    def test_empty_selection_and_change_cap(self):
        shades, layers = self.planes()
        with self.assertRaises(ValueError): self.run_spec(spec({'name': 'e', 'op': 'shade', 'shade': 1, 'when': {'channel': 5}}), shades, layers)
        _, _, rep = self.run_spec(spec({'name': 'e', 'op': 'shade', 'shade': 1, 'when': {'channel': 5}, 'allowEmpty': True}), shades, layers)
        self.assertEqual(rep['changedMapped'], 0)
        with self.assertRaises(ValueError): self.run_spec(spec({'name': 'all', 'op': 'shade', 'shade': 1, 'when': {'channel': 1}}), shades, layers)

    def test_padding_follows_only_changed_texels(self):
        shades, layers = self.planes(100); pad = ~self.texels.mapped
        shades[pad] = 77
        s = spec({'name': 'one', 'op': 'shade', 'shade': 9, 'when': {'all': [{'of': 'u', 'lt': 0.2}, {'of': 'v', 'lt': 0.2}]}})
        out, _, rep = self.run_spec(s, shades, layers)
        self.assertGreater(rep['changedPadding'], 0)
        near_corner = out[:3, :3]; self.assertTrue((near_corner == 9).all())
        self.assertTrue((out[-3:, -3:] == 77).all(), 'padding far from the edit keeps its bytes')


if __name__ == '__main__':
    unittest.main()
