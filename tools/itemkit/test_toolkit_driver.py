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

    def test_the_fit_does_not_depend_on_the_mesh_rotation_about_its_axis(self):
        # A round haft leaves the principal frame free to turn about the long axis (another numpy picks another turn);
        # the thickness probes must find the surface whatever it is.
        from tools.itemkit.fit_manifest import measure
        v, f = self.club()
        for degrees in range(0, 180, 15):
            a = np.radians(degrees); turn = np.array([[np.cos(a), 0, np.sin(a)], [0, 1, 0], [-np.sin(a), 0, np.cos(a)]])
            data = measure({}, self.family, {'positions': gltf(v @ turn.T), 'faces': f}, {}, self.standard)
            self.assertAlmostEqual(data['nativeLength'], .6, delta=.01, msg=f'{degrees} degrees')

    def test_a_half_turn_about_the_axis_swaps_the_sides_and_keeps_the_fit(self):
        from tools.itemkit.fit_manifest import measure
        v, f = self.club(); v = v.copy(); v[:, 0] += np.where((v[:, 1] > .8) & (v[:, 0] > 0), .03, 0)   # a one-sided blade
        plain = measure({}, self.family, {'positions': gltf(v), 'faces': f}, {}, self.standard)
        turned = measure({}, self.family, {'positions': gltf(v), 'faces': f}, {'turnAboutAxis': True}, self.standard)
        self.assertEqual(plain['landmarks'], turned['landmarks'])
        self.assertAlmostEqual(plain['nativeLength'], turned['nativeLength'], places=9)
        P, T = np.asarray(plain['matrix']), np.asarray(turned['matrix'])
        np.testing.assert_allclose(T[:3, :3], np.diag([-1., 1., -1.]) @ P[:3, :3], atol=1e-9)   # 180 degrees about native Y
        self.assertGreater(np.linalg.det(T[:3, :3]), 0)

    def test_a_chosen_length_and_a_bound_digest(self):
        from tools.itemkit.fit_manifest import measure
        v, f = self.club()
        data = measure({}, self.family, {'positions': gltf(v), 'faces': f}, {'targetLength': .76, 'departureDigest': 'x'}, self.standard)
        self.assertAlmostEqual(data['nativeLength'], .76, delta=.01)
        self.assertTrue(data['departurePending'])            # 'x' is not this measurement's digest: the worker would refuse it too

    def test_a_hafted_contract_without_stock_bounds_is_refused_clearly(self):
        from tools.itemkit.fit_manifest import measure
        v, f = self.club(); family = {**self.family, 'native': {k: x for k, x in self.family['native'].items() if k not in ('stockSpan', 'dimensions')}}
        with self.assertRaisesRegex(ValueError, 'needs stockSpan or dimensions'):
            measure({}, family, {'positions': gltf(v), 'faces': f}, {'targetLength': .6}, self.standard)

    def test_a_hafted_shape_check_skips_the_blade_and_guard_limits(self):
        from tools.itemkit.straightness import assess
        metrics = {'bendPctOfLength': .2, 'twistDegrees': 1, 'bladeDepthToWidth': 1.0, 'guardSectionRatio': 4.0}
        self.assertEqual({f['metric'] for f in assess(metrics)['flags']}, {'bladeDepthToWidth', 'guardSectionRatio'})
        self.assertEqual(assess(metrics, family='club')['flags'], [])                  # a round handle and a wide head are design
        self.assertTrue(assess({**metrics, 'bendPctOfLength': 3.}, family='halberd')['flags'])   # a bent haft is still flagged

    def test_head_at_the_low_end_is_turned_up(self):
        from tools.itemkit.fit_manifest import measure
        v, f = self.club(); v = v * [1, -1, 1]; f = f[:, ::-1]
        data = measure({}, self.family, {'positions': gltf(v), 'faces': f}, {}, self.standard)
        self.assertGreater(np.asarray(data['fittedBounds'])[1][1], .3)


class TwoHandDepthTests(unittest.TestCase):
    def test_an_unapproved_depth_departure_keeps_its_measurement(self):
        from tools.itemkit.fit_manifest import STANDARD
        from tools.itemkit.grip import GripDeparture, two_hand_uniform
        standard = json.loads(STANDARD.read_text(encoding='utf-8')); depth = standard['targetMidpointSection']['depth']
        rows = [(y, depth) for y in np.arange(-.3, .3001, .004)]           # a round grip twice the approved depth
        v, f = lathe(rows, sides=64); ends = [[0, -.1, 0], [0, .1, 0]]
        with self.assertRaises(GripDeparture) as caught: two_hand_uniform(v, f, np.eye(4), ends, [0, 0, 0], standard)
        report = caught.exception.report; self.assertFalse(report['depthDepartureApproved']); self.assertTrue(report['measurementDigest'])
        with self.assertRaises(GripDeparture) as again:                  # approved depth, but no review of this digest yet
            two_hand_uniform(v, f, np.eye(4), ends, [0, 0, 0], standard, {'depthDepartureApproved': True})
        self.assertEqual(again.exception.report['measurementDigest'], report['measurementDigest'])


class ObliqueReviewTests(unittest.TestCase):
    def test_the_pair_is_only_conditioned_with_a_review_of_the_keyed_hashes(self):
        from PIL import Image
        from tools.itemkit.oblique import condition
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)/'design'; folder.mkdir()
            image = np.full((256, 256, 3), 255, np.uint8)
            for i in range(40, 216): image[256 - i - 6:256 - i + 6, i - 6:i + 6] = (90, 70, 60)     # a diagonal bar
            for role in ('detail', 'clay'): Image.fromarray(image).save(folder/f'{role}-original.png')
            first = condition(folder, Path(tmp), 'x')
            self.assertTrue(first['reviewRequired']); self.assertFalse((folder/'conditioning-v1/conditioned').exists())
            self.assertEqual(condition(folder, Path(tmp), 'x')['keyedSha256'], first['keyedSha256'])        # measuring again is safe
            with self.assertRaisesRegex(ValueError, 'keyed detail and clay hashes'):
                condition(folder, Path(tmp), 'x', notes="user's words", keyed_sha256=['0' * 64, '0' * 64])
            (Path(tmp)/'x.oblique-v1.asset.json').write_text('{}', encoding='utf-8')     # refused before anything is conditioned
            with self.assertRaisesRegex(ValueError, 'oblique-v1.asset.json exists'):
                condition(folder, Path(tmp), 'x', notes="user's words", keyed_sha256=first['keyedSha256'])
            self.assertFalse((folder/'conditioning-v1/conditioned').exists()); (Path(tmp)/'x.oblique-v1.asset.json').unlink()
            image[0, 0] = 0; Image.fromarray(image).save(folder/'clay-original.png')          # a replaced clay is never conditioned
            with self.assertRaisesRegex(ValueError, 'original images changed'): condition(folder, Path(tmp), 'x')


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


class ComfyStopTests(unittest.TestCase):
    """comfy stop kills only the ComfyUI this driver started, and never forgets one that may still run."""
    def stop(self, command_line, *, query_fails=False, answering=False):
        import subprocess, types
        from unittest.mock import patch
        from tools.itemkit.drive import Driver
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup); runtime = Path(tmp.name)
        (runtime/'comfy.pid').write_text('4242')
        ws = types.SimpleNamespace(runtime=runtime, path=Path, data={'comfy': {'url': 'http://127.0.0.1:1', 'startup': 'x/srn_headkit/managed_startup.py'}})
        killed = []
        def run(command, **_):
            if command[0] == 'taskkill': killed.append(command[2]); return subprocess.CompletedProcess(command, 0, '', '')
            return subprocess.CompletedProcess(command, 1 if query_fails else 0, command_line, 'CIM failed' if query_fails else '')
        def urlopen(*_, **__):
            if answering: return None
            raise OSError('refused')
        with patch('subprocess.run', side_effect=run), patch('urllib.request.urlopen', side_effect=urlopen), patch('time.sleep'):
            try: result = Driver(ws).comfy('stop')
            except SystemExit as error: result = error
        return result, killed, (runtime/'comfy.pid').exists()

    def test_the_managed_startup_is_stopped(self):
        result, killed, kept = self.stop(r'"python.exe" -I -B C:\nodes\srn_headkit\managed_startup.py --config c.json')
        self.assertEqual(killed, ['4242']); self.assertFalse(kept); self.assertEqual(result['comfy'], 'stopped')

    def test_a_reused_pid_is_never_killed(self):
        result, killed, kept = self.stop('"C:\\Program Files\\Editor\\editor.exe"')
        self.assertEqual(killed, []); self.assertFalse(kept); self.assertIn('stale PID file removed', result['comfy'])

    def test_a_shared_comfy_is_never_started_or_stopped(self):
        import io, types
        from tools.itemkit.drive import Driver
        ws = types.SimpleNamespace(runtime=Path('.'), path=Path, data={'comfy': {'url': 'http://127.0.0.1:1', 'shared': True}})
        d = Driver(ws)
        with mock.patch('urllib.request.urlopen', side_effect=OSError('down')), \
                mock.patch('subprocess.Popen', side_effect=AssertionError('a shared ComfyUI is never started')), \
                mock.patch('subprocess.run', side_effect=AssertionError('or killed')):
            self.assertIn('left running', d.comfy('stop')['comfy'])
            with self.assertRaisesRegex(SystemExit, 'start Comfy Desktop'): d.comfy('start')
        with mock.patch('urllib.request.urlopen', return_value=io.BytesIO(b'{}')): self.assertEqual(d.comfy('start')['comfy'], 'shared')
        # Waiting for the GPU lease and an idle queue is the submitter's job (headkit.shared_comfy.slot), not the driver's.
        self.assertFalse(hasattr(d, 'wait_idle'))

    def test_a_failed_query_or_a_still_answering_comfy_keeps_the_pid_file(self):
        for kwargs in ({'query_fails': True}, {'answering': True}):
            result, killed, kept = self.stop('"C:\\Program Files\\Editor\\editor.exe"', **kwargs)
            self.assertIsInstance(result, SystemExit); self.assertEqual(killed, []); self.assertTrue(kept)


class CopyCheckedTests(unittest.TestCase):
    def test_a_truncated_copy_is_replaced_and_a_wrong_source_refused(self):
        import hashlib
        from tools.itemkit.drive import copy_checked
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)/'out.glb'; source.write_bytes(b'complete'); expected = hashlib.sha256(b'complete').hexdigest()
            target = Path(tmp)/'handoff/donor.glb'; target.parent.mkdir(); target.write_bytes(b'comp')      # an interrupted copy
            self.assertTrue(copy_checked(source, target, expected)); self.assertEqual(target.read_bytes(), b'complete')
            self.assertFalse(copy_checked(source, Path(tmp)/'handoff/other.glb', '0' * 64))
            self.assertFalse((Path(tmp)/'handoff/other.glb').exists()); self.assertFalse((Path(tmp)/'handoff/other.glb.partial').exists())


class HistoricalCodeTests(unittest.TestCase):
    def test_a_deleted_source_file_is_still_code_and_data_is_not(self):
        from tools.itemkit.contracts import code_pins, is_code_path
        test = is_code_path(); folder = Path(code_pins()[-1]['path']).parent
        self.assertTrue(test(str(folder/'since_deleted_helper.py')))
        self.assertFalse(test(str(Path(tempfile.gettempdir())/'manifest.json')))
        self.assertFalse(test(str(folder/'notes.txt')))
        self.assertTrue(test(code_pins()[-1]['path']))                                   # today's code
        with tempfile.NamedTemporaryFile(suffix='.json', dir=folder, delete=False) as data: pass   # an existing document in a code folder
        try: self.assertFalse(test(data.name))
        finally: Path(data.name).unlink()


class ResourceStemTests(unittest.TestCase):
    def test_designs_sharing_an_id_suffix_get_distinct_resource_names(self):
        import hashlib
        from tools.itemkit.contracts import resource_stem, resref
        a, b = resource_stem('red-club-v1'), resource_stem('blue-axe-v1')
        self.assertNotEqual(a, b); resref(a + 'h'); resref(a + 'm')
        self.assertEqual(a, 'sr' + hashlib.sha256(b'red-club-v1').hexdigest()[:8])      # the intake's own identity


class SiblingSlotTests(unittest.TestCase):
    def test_a_second_design_on_the_same_carrier_sees_the_first_ones_slot(self):
        from tools.itemkit.family_contract import sibling_models
        from tools.itemkit.contracts import reserve
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            def profile(name, cls, index=None):
                data = {'family': 'club', 'nativePackaging': 'enabled', 'native': {'itemClass': cls},
                        'resources': {'texturePrefix': 'sr' + name, **({'appearanceIndex': index} if index else {})}}
                (root/f'family-{name}.json').write_text(json.dumps(data), encoding='utf-8'); return data
            profile('one', 'wblcl', 1); profile('axe', 'waxhn', 2); mine = profile('two', 'wblcl')
            taken = sibling_models(root, root/'family-two.json', 'wblcl')
            self.assertIn('wblcl_b_011.mdl', taken); self.assertFalse(any(n.startswith('waxhn') for n in taken))
            self.assertEqual(reserve(mine, taken)['modelIndex'], 2)


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
            with mock.patch.object(d, 'chain', side_effect=OSError('disk')):          # any error is that item's, not the batch's
                self.assertIn('disk', d.batch(['a:fit-v1'], ['fit'])['items'][0]['failed'])
            with self.assertRaisesRegex(SystemExit, 'ID:SUFFIX'): d.batch(['sr4-club', 'a:fit-v1'], ['fit'])

    def test_a_fit_rerun_reuses_its_measured_candidate(self):
        from tools.itemkit.drive import Driver, sha
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); d = Driver(self.workspace(root)); working, donor = root/'w.glb', root/'d.glb'
            working.write_bytes(b'w'); donor.write_bytes(b'd')
            self.assertIsNone(d._measured_candidate('x', 'fit-v1-measure', working, donor, {}))
            (root/'h').mkdir(); (root/'h/x.fit-v1-measure.asset.json').write_text('{}', encoding='utf-8')
            gen = root/'h/generated/x/fit-v1-measure'; gen.mkdir(parents=True)
            (gen/'fit-data.json').write_text(json.dumps({'working': sha(working), 'donor': sha(donor), 'overrides': {'gripCentre': .5}}), encoding='utf-8')
            for n, digest in ((1, 'old'), (2, 'new')):
                folder = root/f'x/run-fit-v1-measure/measure-{n}/worker'; folder.mkdir(parents=True)
                (folder/'measurement.json').write_text(json.dumps({'measurementDigest': digest, 'departure': True, 'nativeLength': .7,
                                                                   'gripLength': .18, 'preview': {}}), encoding='utf-8')
            self.assertEqual(d._measured_candidate('x', 'fit-v1-measure', working, donor, {'gripCentre': .5})['measurementDigest'], 'new')
            with self.assertRaisesRegex(SystemExit, 'other inputs'): d._measured_candidate('x', 'fit-v1-measure', working, donor, {})

    def test_batch_stages_are_one_comma_list_so_items_can_follow(self):
        import argparse
        from tools.itemkit.drive import stage_list
        self.assertEqual(stage_list('fit,reduce,unwrap'), ['fit', 'reduce', 'unwrap'])
        for bad in ('', 'fit,polish', 'sr4-club:fit-v1'):
            with self.assertRaises(argparse.ArgumentTypeError): stage_list(bad)


if __name__ == '__main__':
    unittest.main()
