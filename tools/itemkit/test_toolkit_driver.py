"""The promoted wave tooling: carrier measurement, hafted fits, texture outliers, contracts budgets and the driver."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import numpy as np


def lathe(profile, *, sides=24, depth=1.0):
    """A closed solid of revolution about +Y from (y, radius) rows; `depth` squashes X for flat sections."""
    rings = []
    for y, r in profile:
        a = np.linspace(0, 2 * np.pi, sides, endpoint=False)
        rings.append(np.c_[r * np.cos(a) * depth, np.full(sides, y), r * np.sin(a)])
    v = np.concatenate(rings + [np.array([[0, profile[0][0], 0], [0, profile[-1][0], 0]])]); faces = []
    for i in range(len(profile) - 1):
        for j in range(sides):
            a, b = i * sides + j, i * sides + (j + 1) % sides; c, d = a + sides, b + sides
            faces += [[a, c, b], [b, c, d]]
    bottom, top = len(v) - 2, len(v) - 1; last = (len(profile) - 1) * sides
    for j in range(sides):
        faces.append([bottom, j, (j + 1) % sides]); faces.append([top, last + (j + 1) % sides, last + j])
    return v, np.asarray(faces)


def gltf(positions):
    """Inverse of fit_manifest.gltf_to_blender, so a Blender-frame solid becomes a glTF working shell."""
    p = np.asarray(positions, float); return np.c_[p[:, 0], p[:, 2], -p[:, 1]]


class CarrierTests(unittest.TestCase):
    def test_sword_hilt_centre_and_long_haft_hand_point(self):
        from tools.itemkit.carrier import measure
        sword = lathe([(-.18, .02), (-.15, .02), (-.149, .013), (.06, .013), (.061, .09), (.08, .09), (.081, .02), (.9, .004)])
        r = measure(*sword, .1831918)
        self.assertEqual(r['method'], 'hilt-centre'); self.assertAlmostEqual(r['gripOrigin'][1], (-.15 + .06) / 2, delta=.01)
        haft = lathe([(-.6, .015), (1.4, .015), (1.401, .1), (1.6, .1)])
        r = measure(*haft, .1831918, 'two'); self.assertEqual(r['method'], 'hand-point'); self.assertEqual(r['gripOrigin'][1], 0.)
        self.assertAlmostEqual(r['length'], 2.2, places=3)


class HaftedFitTests(unittest.TestCase):
    def setUp(self):
        from tools.itemkit.fit_manifest import STANDARD
        self.standard = json.loads(STANDARD.read_text(encoding='utf-8'))
        self.family = {'family': 'club', 'native': {'gripOrigin': [0, -.04, 0], 'gripLength': self.standard['usableLength'],
                                                    'stockSpan': [-.2, .4]}}

    def club(self):
        # A 1.0-unit club: butt cap, round handle, then a gradual swell to a wide head at the top (dense: the
        # straightness frame needs a real shell's vertex count).
        rows = [(0, .03), (.03, .03), (.031, .022), (.5, .024), (.8, .04), (.95, .05), (1.0, .05)]
        dense = []
        for (y0, r0), (y1, r1) in zip(rows, rows[1:]):
            n = max(1, int(round((y1 - y0) / .004)))      # a ring in every one of the 200 measuring slices
            dense += [(y0 + (y1 - y0) * k / n, r0 + (r1 - r0) * k / n) for k in range(n)]
        return lathe(dense + [rows[-1]], sides=96)

    def test_hafted_club_is_scaled_to_the_stock_length_with_the_head_up(self):
        from tools.itemkit.fit_manifest import measure
        v, f = self.club(); data = measure({}, self.family, {'positions': gltf(v), 'faces': f}, {}, self.standard)
        self.assertIn(data['method'], ('hafted-head', 'hafted-taper'))
        self.assertAlmostEqual(data['nativeLength'], .6, delta=.01)                     # the stock carrier's length
        self.assertEqual(data['sizingAuthority'], 'usable-length-round'); self.assertTrue(data['departurePending'])
        fitted = np.asarray(data['fittedBounds']); self.assertGreater(fitted[1][1], .3)    # head above the hand
        self.assertLess(data['joinY'][0], data['joinY'][1])
        self.assertLess(abs(data['landmarks']['gripStart'] + data['landmarks']['gripEnd'] - 2 * (-.04 + .2) / .6), .02)

    def test_a_chosen_length_and_a_bound_digest(self):
        from tools.itemkit.fit_manifest import measure
        v, f = self.club()
        data = measure({}, self.family, {'positions': gltf(v), 'faces': f}, {'targetLength': .76, 'departureDigest': 'x'}, self.standard)
        self.assertAlmostEqual(data['nativeLength'], .76, delta=.01)
        self.assertTrue(data['departurePending'])            # 'x' is not this measurement's digest: the worker would refuse it too

    def test_head_at_the_low_end_is_turned_up(self):
        from tools.itemkit.fit_manifest import measure
        v, f = self.club(); v = v * [1, -1, 1]; f = f[:, ::-1]
        data = measure({}, self.family, {'positions': gltf(v), 'faces': f}, {}, self.standard)
        self.assertGreater(np.asarray(data['fittedBounds'])[1][1], .3)


class TextureCheckTests(unittest.TestCase):
    def test_a_stroke_on_grain_is_found_and_grain_alone_is_not(self):
        from tools.itemkit.texture_check import outliers
        rng = np.random.default_rng(3); image = np.clip(60 + rng.normal(0, 18, (256, 256)), 0, 255)
        mapped = np.zeros((256, 256), bool); mapped[20:236, 20:236] = True
        rgb = np.repeat(image[..., None], 3, 2).astype(np.uint8)
        report, mask = outliers(rgb, mapped); self.assertEqual(report['blobCount'], 0)
        rgb[120:124, 60:200] = 170
        report, mask = outliers(rgb, mapped); self.assertGreaterEqual(report['blobCount'], 1)
        self.assertTrue(mask[121:123, 80:180].any()); self.assertTrue(report['advisory'])


class ContractBudgetTests(unittest.TestCase):
    def test_budget_follows_the_raised_policy_and_parts_sum(self):
        from tools.itemkit.family_contract import allocation, visible_budget
        self.assertEqual(visible_budget(.4), 7500); self.assertEqual(visible_budget(2.2), 22500)
        self.assertTrue(7500 < visible_budget(1.1) < 22500)
        for total in (7500, 9000, 17000, 22500):
            b = allocation(total); self.assertEqual(sum(p['visible'] for p in b['parts'].values()), total)
            self.assertEqual(b['shadow'], 500)


class FixtureCarryTests(unittest.TestCase):
    def test_two_handers_are_framed_at_the_shoulder(self):
        from tools.itemkit.fixture import carry_for
        self.assertEqual(carry_for(13), 'shoulder'); self.assertEqual(carry_for(18), 'shoulder'); self.assertEqual(carry_for(10), 'shoulder')
        self.assertEqual(carry_for(1), 'hip'); self.assertEqual(carry_for(28), 'hip'); self.assertEqual(carry_for(9999), 'hip')


class WorkspaceAndDriverTests(unittest.TestCase):
    def workspace(self, root, **extra):
        data = {'kind': 'srn-item-workspace', 'schemaVersion': 1, 'python': 'py.exe', 'pythonPath': ['bank'], 'blender': 'b.exe',
                'runtime': 'rt', 'bindings': 'b.json', 'handoff': 'h', 'items': '.', **extra}
        (root/'workspace.json').write_text(json.dumps(data), encoding='utf-8')
        from tools.itemkit.workspace import Workspace
        return Workspace.load(root/'workspace.json')

    def test_relative_paths_resolve_against_the_workspace_and_bindings_split(self):
        from tools.itemkit.workspace import Workspace, WorkspaceError
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); ws = self.workspace(root)
            self.assertEqual(ws.handoff, (root/'h').resolve()); self.assertEqual(ws.bindings('generation'), (root/'rt').resolve()/'b.json')
            ws = self.workspace(root, generationBindings='g.json'); self.assertEqual(ws.bindings('generation').name, 'g.json')
            self.assertIn(str((root/'bank').resolve()), ws.environment()['PYTHONPATH'])
            (root/'workspace.json').write_text('{"kind": "other"}', encoding='utf-8')
            with self.assertRaises(WorkspaceError): Workspace.load(root/'workspace.json')

    def test_batch_runs_items_side_by_side_and_keeps_failures(self):
        from tools.itemkit.drive import Driver
        with tempfile.TemporaryDirectory() as tmp:
            d = Driver(self.workspace(Path(tmp)))
            def chain(design, suffix, stages):
                if design == 'bad': raise SystemExit('boom')
                return {'design': design, 'suffix': suffix, 'stages': stages}
            with mock.patch.object(d, 'chain', side_effect=chain):
                result = d.batch(['a:fit-v1', 'bad:fit-v1', 'c:fit-v2'], ['fit', 'reduce'], jobs=2)
            self.assertEqual([r['design'] for r in result['items']], ['a', 'bad', 'c'])
            self.assertIn('failed', result['items'][1]); self.assertEqual(result['items'][2]['suffix'], 'fit-v2')
            with self.assertRaises(SystemExit): d.batch(['a:x'], ['fit'], jobs=4)

    def test_batch_stages_are_one_comma_list_so_items_can_follow(self):
        import argparse
        from tools.itemkit.drive import stage_list
        self.assertEqual(stage_list('fit,reduce,unwrap'), ['fit', 'reduce', 'unwrap'])
        for bad in ('', 'fit,polish', 'sr4-club:fit-v1'):
            with self.assertRaises(argparse.ArgumentTypeError): stage_list(bad)


if __name__ == '__main__':
    unittest.main()
