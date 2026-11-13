"""The promoted wave tooling: carrier measurement, hafted fits, texture outliers, contracts budgets and the driver."""
import json
import os
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
        with self.assertRaisesRegex(ValueError, 'true or false'):
            measure({}, self.family, {'positions': gltf(v), 'faces': f}, {'turnAboutAxis': 'false'}, self.standard)
        with self.assertRaisesRegex(ValueError, 'sectionBasis applies only'):                      # a club is hafted, not a staff
            measure({}, self.family, {'positions': gltf(v), 'faces': f}, {'sectionBasis': 'visibleFaceWidth'}, self.standard)

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


class StaffSectionTests(unittest.TestCase):
    """The stun staff was flattened by the per-axis hilt calibration (user, 2026-11-12): a staff keeps its own section."""
    def setUp(self):
        from tools.itemkit.fit_manifest import STANDARD
        self.standard = json.loads(STANDARD.read_text(encoding='utf-8'))
        self.family = {'family': 'staff', 'native': {'gripOrigin': [0, 0, 0], 'gripLength': self.standard['usableLength']}}
        rows = [(y, .022) for y in np.linspace(0, 1, 250)]
        v, self.f = lathe(rows, sides=96, depth=1 / 1.2)                                  # a 1.2:1 shaft, thick for a hand
        self.v = gltf(v); self.overrides = {'bladeAtLowEnd': False, 'pommelEnd': .2, 'gripStart': .32, 'gripEnd': .41,
                                            'bladeStart': .68, 'sizeToLength': False,       # the stun staff's own overrides
                                            'targetLength': 1.9}

    def section(self, data):
        mid = data['gripReport']['measuredFittedSections'][2]; return mid['depth'], mid['visibleFaceWidth']

    def test_a_staff_is_thinned_evenly_to_the_grip_depth(self):
        from tools.itemkit.fit_manifest import measure
        data = measure({}, self.family, {'positions': self.v, 'faces': self.f}, self.overrides, self.standard)
        self.assertEqual(data['sizingAuthority'], 'midpoint-depth-uniform'); self.assertTrue(data['departurePending'])
        depth, width = self.section(data)
        self.assertAlmostEqual(depth, self.standard['targetMidpointSection']['depth'], delta=.001)
        self.assertAlmostEqual(width / depth, 1.2, delta=.03)                            # not 50/30 = 1.67 (the hilt section)
        thick = measure({}, self.family, {'positions': self.v, 'faces': self.f}, {**self.overrides, 'sectionBasis': 'visibleFaceWidth'},
                        self.standard)
        depth, width = self.section(thick)
        self.assertAlmostEqual(width, self.standard['targetMidpointSection']['visibleFaceWidth'], delta=.001)
        self.assertAlmostEqual(width / depth, 1.2, delta=.03)

    def test_the_hilt_calibration_is_refused_where_it_would_flatten_a_shaft(self):
        from tools.itemkit import fit_manifest
        from tools.itemkit.routes import ROUTES
        hilt = ROUTES['staff']._replace(section='calibrated')
        with mock.patch.dict(fit_manifest.ROUTES, {'staff': hilt}):
            with self.assertRaisesRegex(ValueError, 'would flatten this staff'):
                fit_manifest.measure({}, self.family, {'positions': self.v, 'faces': self.f}, self.overrides, self.standard)

    def test_a_thickness_probe_tolerance_follows_its_section(self):
        # Thin edges keep 2.5 mm; a thick section gets 5% of its thickness (the wave-1 Spear's collar, 2026-11-12).
        from tools.itemkit.fit_manifest import PROBE_SAMPLE_FRACTION, measure
        data = measure({}, self.family, {'positions': self.v, 'faces': self.f}, self.overrides, self.standard)
        self.assertTrue(data['thicknessProbes'])
        for probe in data['thicknessProbes']:
            self.assertAlmostEqual(probe['maximumSampleError'], max(.0025, PROBE_SAMPLE_FRACTION * probe['measuredThickness']))


class BladeFaceFrameTests(unittest.TestCase):
    """A handle thicker than it is tall must not turn the blade a quarter round (the wave-3 Vibro Knife, 2026-11-13)."""
    def knife(self, handle_depth):
        blade, _ = lathe([(y, .05) for y in np.linspace(0, .6, 240)], sides=48, depth=.1)          # broad along Blender Z
        handle, _ = lathe([(y, .06) for y in np.linspace(-.4, -.002, 160)], sides=48, depth=handle_depth)
        return np.concatenate([blade, handle])

    def frame(self, points):
        from tools.itemkit import fit_manifest as fm
        _, U, q = fm._frame(points)
        overrides = {'bladeAtLowEnd': bool(U[1, 0] < 0), 'pommelEnd': .02, 'gripStart': .02, 'gripEnd': .38, 'bladeStart': .41}
        _, q, U, _ = fm.bladed_landmarks(q, U, overrides)               # the blade (Blender +Y) at the high end
        return q, U

    def test_the_width_axis_follows_the_blade_face(self):
        for handle_depth in (.6, 2.2):                                  # a slim handle, and one far thicker than tall
            q, U = self.frame(self.knife(handle_depth))
            blade = q[q[:, 0] > np.percentile(q[:, 0], 70)]
            self.assertGreater(np.ptp(blade[:, 1]), 4 * np.ptp(blade[:, 2]), handle_depth)
            self.assertAlmostEqual(abs(U[2, 1]), 1, places=3); self.assertAlmostEqual(np.linalg.det(U), 1, places=9)

    def test_a_flat_axe_head_on_a_thick_haft_faces_the_width_axis(self):
        from tools.itemkit import fit_manifest as fm
        haft, _ = lathe([(y, .03) for y in np.linspace(-.4, .45, 340)], sides=48, depth=2.5)     # thicker than it is tall
        head, _ = lathe([(y, .15) for y in np.linspace(.45, .6, 60)], sides=48, depth=.1)         # broad along Blender Z
        _, U0, q0 = fm._frame(np.concatenate([haft, head]))
        method, q, U, _ = fm.hafted_landmarks(q0, U0, {'headAtLowEnd': bool(U0[1, 0] < 0)})
        self.assertEqual(method, 'hafted-head')
        top = q[q[:, 0] > np.percentile(q[:, 0], 90)]
        self.assertGreater(np.ptp(top[:, 1]), 4 * np.ptp(top[:, 2])); self.assertAlmostEqual(np.linalg.det(U), 1, places=9)

    def test_a_round_blade_keeps_the_principal_frame(self):
        from tools.itemkit import fit_manifest as fm
        bat, _ = lathe([(y, .03) for y in np.linspace(-.4, .6, 400)], sides=48)
        _, U0, q0 = fm._frame(bat); _, U1 = fm._oriented(q0, U0, False); _, U = self.frame(bat)
        self.assertTrue(np.allclose(U, U1))


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
    def test_a_second_design_on_the_same_carrier_sees_the_first_ones_slot_in_any_wave(self):
        from tools.itemkit.family_contract import sibling_models
        from tools.itemkit.contracts import reserve
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            def profile(wave, name, cls, index=None):
                data = {'family': 'club', 'nativePackaging': 'enabled', 'native': {'itemClass': cls},
                        'resources': {'texturePrefix': 'sr' + name, **({'appearanceIndex': index} if index else {})}}
                (root/wave).mkdir(exist_ok=True)
                (root/wave/f'family-{name}.json').write_text(json.dumps(data), encoding='utf-8'); return data
            # An earlier wave's unpublished design holds slot 1, this wave's sibling slot 2.
            profile('wave-1', 'one', 'wblcl', 1); profile('wave-2', 'axe', 'waxhn', 3); profile('wave-2', 'three', 'wblcl', 2)
            mine = profile('wave-2', 'two', 'wblcl')
            taken = sibling_models(root, root/'wave-2/family-two.json', 'wblcl')
            self.assertIn('wblcl_b_011.mdl', taken); self.assertIn('wblcl_b_021.mdl', taken)
            self.assertFalse(any(n.startswith('waxhn') for n in taken))
            self.assertEqual(reserve(mine, taken)['modelIndex'], 3)

    def test_a_retired_contract_folder_gives_its_slots_back(self):
        from tools.itemkit.family_contract import retire, retired, sibling_models
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for wave, name, index in (('abandoned', 'old', 1), ('live', 'kept', 2), ('live', 'mine', None)):
                (root/wave).mkdir(exist_ok=True)
                (root/wave/f'family-{name}.json').write_text(json.dumps({'family': 'club', 'nativePackaging': 'enabled',
                                                                         'native': {'itemClass': 'wblcl'}, 'resources': {
                    'texturePrefix': 'sr' + name, **({'appearanceIndex': index} if index else {})}}), encoding='utf-8')
            mine = root/'live/family-mine.json'
            self.assertIn('wblcl_b_011.mdl', sibling_models(root, mine, 'wblcl'))
            with self.assertRaisesRegex(ValueError, 'reason'): retire(root/'abandoned', ' ', '2026-11-13')
            record = retire(root/'abandoned', 'slots collided with wave 1', '2026-11-13')
            self.assertEqual(record['contracts'], ['family-old.json']); self.assertEqual(retired(root/'abandoned')['date'], '2026-11-13')
            taken = sibling_models(root, mine, 'wblcl')
            self.assertNotIn('wblcl_b_011.mdl', taken); self.assertIn('wblcl_b_021.mdl', taken)
            with self.assertRaisesRegex(ValueError, 'already retired'): retire(root/'abandoned', 'again', '2026-11-13')
            with self.assertRaisesRegex(ValueError, 'no family contracts'): retire(root/'missing', 'why', '2026-11-13')

    def test_a_base_contracts_reviewed_grip_origin_is_kept_and_disagreement_refused(self):
        from tools.itemkit.family_contract import base_grip_origin
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            def contract(name, cls, origin):
                (base/f'family-{name}.json').write_text(json.dumps({'native': {'itemClass': cls, 'gripOrigin': origin}}), encoding='utf-8')
            contract('claymore', 'wswgs', [0, -.0630, 0]); contract('sword', 'wswls', [0, -.0307, 0])
            self.assertEqual(base_grip_origin(base, 'wswgs'), [0, -.0630, 0])
            self.assertEqual(base_grip_origin(base, 'WSwGs'), [0, -.0630, 0])
            self.assertIsNone(base_grip_origin(base, 'wswdg'))                     # no reviewed contact: measure the carrier
            contract('bat', 'wswgs', [0, -.0712, 0])                               # a fresh-measured contact that disagrees
            with self.assertRaisesRegex(ValueError, 'different grip origins'): base_grip_origin(base, 'wswgs')


class OpeningProbeTests(unittest.TestCase):
    def plate(self):
        """A 100 x 60 mm plate across x with a 20 mm square through-hole centred 70 mm along its length (y)."""
        ys, zs = [0, .06, .08, .1], [0, .02, .04, .06]; v = []; f = []
        for i in range(3):
            for j in range(3):
                if (i, j) == (1, 1): continue
                k = len(v); v += [[0, ys[i], zs[j]], [0, ys[i + 1], zs[j]], [0, ys[i + 1], zs[j + 1]], [0, ys[i], zs[j + 1]]]
                f += [[k, k + 1, k + 2], [k, k + 2, k + 3]]
        return np.array(v, float), np.array(f)

    def test_a_through_hole_is_found_and_matched_from_either_end(self):
        from tools.itemkit import opening_probes as op
        v, f = self.plate(); found = op.holes(v, f, 0)
        self.assertEqual(len(found), 1); hole = found[0]
        self.assertEqual(hole['hits'], 0); self.assertAlmostEqual(hole['clearance'], .01, delta=.001)
        self.assertAlmostEqual(hole['area'], .0004, delta=.00005); hole['fraction'] = hole['y'] / .1
        self.assertAlmostEqual(hole['fraction'], .7, delta=.01)
        probe, = op.match([('lanyard', .3)], found)                              # the reference measured from the other end
        self.assertEqual((probe['name'], probe['start'], probe['end']), ('lanyard', hole['start'], hole['end']))
        with self.assertRaisesRegex(ValueError, 'No clear through-hole matches'): op.match([('lanyard', .5)], found)
        narrow = [{**hole, 'clearance': .001}]                                    # a 2 mm gap closes in reduction
        with self.assertRaisesRegex(ValueError, 'too narrow'): op.match([('lanyard', .7)], narrow)
        self.assertEqual(op.reference_fractions({'inputs': {}}, '.'), [])                 # no reviewed openings, nothing to place
        with self.assertRaisesRegex(ValueError, 'geometryForegroundMask'):
            op.reference_fractions({'inputs': {}, 'openings': [{'name': 'x', 'referenceBounds': [0, 0, 1, 1]}]}, '.')

    def test_matching_backs_up_so_every_reference_gets_a_hole(self):
        from tools.itemkit import opening_probes as op
        hole = lambda fraction, clearance, tag: {'fraction': fraction, 'clearance': clearance, 'hits': 0, 'start': tag, 'end': tag}
        found = [hole(.20, .004, 'wide'), hole(.23, .002, 'narrow')]
        # "a" prefers the wide hole, but only the wide hole is near "b": greedy order would leave "b" without one
        probes = op.match([('a', .22), ('b', .18)], found)
        self.assertEqual([(p['name'], p['start']) for p in probes], [('a', 'narrow'), ('b', 'wide')])
        with self.assertRaisesRegex(ValueError, 'distinct clear'): op.match([('a', .2), ('b', .21), ('c', .22)], found)

    def test_all_references_are_matched_from_the_same_end(self):
        from tools.itemkit import opening_probes as op
        hole = lambda fraction, tag: {'fraction': fraction, 'clearance': .004, 'hits': 0, 'start': tag, 'end': tag}
        found = [hole(.2, 'near'), hole(.3, 'far')]
        # .2 fits unflipped and .7 only flipped: no one end places both, so the lost opening is not certified
        with self.assertRaisesRegex(ValueError, 'No single end'): op.match([('a', .2), ('b', .7)], found)
        probes = op.match([('a', .8), ('b', .7)], found)                         # both measured from the other end
        self.assertEqual([p['start'] for p in probes], ['near', 'far'])


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

    def test_colour_geometry_meshes_from_the_detail_image_with_a_quoted_waiver(self):
        from tools.itemkit.drive import Driver
        with tempfile.TemporaryDirectory() as tmp:
            d = Driver(self.workspace(Path(tmp))); h = d.ws.handoff; h.mkdir(parents=True, exist_ok=True)
            pin = lambda n: {'path': f'inputs/{n}.png', 'sha256': n * 8}
            for name, family in (('bat', 'greatsword'), ('knife', 'dagger')):
                (h/f'family-{name}.json').write_text(json.dumps({'family': family}), encoding='utf-8')
                (h/f'{name}.c.asset.json').write_text(json.dumps({
                    'conditioning': 'clay-detail-v1', 'familyProfile': {'path': f'family-{name}.json'}, 'approval': {},
                    'inputs': {'reference': pin('r'), 'detail': pin('d'), 'geometry': pin('g'), 'foregroundMask': pin('f'),
                               'geometryForegroundMask': pin('m'), 'mask': pin('m')}}), encoding='utf-8')
            with self.assertRaises(SystemExit): d.colour_geometry('bat', 'c', 'x', ' ')
            m = json.loads(Path(d.colour_geometry('bat', 'c', 'colour', 'mesh it from the colour image')).read_text(encoding='utf-8'))
            self.assertEqual(m['conditioning'], 'detailed-v1')
            self.assertEqual((m['inputs']['geometry'], m['inputs']['mask']), (pin('d'), pin('f')))
            self.assertEqual(m['approval']['referenceView'], {'view': 'side', 'decision': 'approved', 'sideViewWaiver': True,
                                                              'notes': 'mesh it from the colour image'})
            knife = json.loads(Path(d.colour_geometry('knife', 'c', 'colour', 'words')).read_text(encoding='utf-8'))
            self.assertNotIn('referenceView', knife['approval'])          # a short design needs no long-weapon waiver
            self.assertEqual(knife['approval']['colourGeometry'], {'decision': 'approved', 'geometrySha256': 'dddddddd', 'notes': 'words'})
            with self.assertRaises(SystemExit): d.colour_geometry('bat', 'colour', 'again', 'words')   # already colour

    def test_a_contract_folder_a_design_still_builds_on_is_not_retired(self):
        from tools.itemkit.drive import Driver
        with tempfile.TemporaryDirectory() as tmp:
            d = Driver(self.workspace(Path(tmp))); h = d.ws.handoff; (h/'contracts/old').mkdir(parents=True)
            (h/'contracts/old/family-axe.json').write_text(json.dumps({'family': 'club'}), encoding='utf-8')
            pinned = json.dumps({'familyProfile': {'path': 'contracts/old/family-axe.json'}})
            (h/'axe.old-contract.asset.json').write_text(pinned, encoding='utf-8')      # the folder's own contract manifest
            (h/'axe.calibrated-v1.asset.json').write_text(pinned, encoding='utf-8')     # a design built on past it
            with self.assertRaisesRegex(SystemExit, r'1 current manifest\(s\) build on, e\.g\. axe\.calibrated-v1'):
                d.retire_contracts('contracts/old', 'abandoned', '2026-11-13')
            self.assertFalse((h/'contracts/old/retired.json').exists())
            # a later profile elsewhere without a contract there is not a move: the axe still holds its slot
            (h/'loose.json').write_text(json.dumps({'family': 'club'}), encoding='utf-8')
            (h/'axe.loose-v1.asset.json').write_text(json.dumps({'familyProfile': {'path': 'loose.json'}}), encoding='utf-8')
            with self.assertRaisesRegex(SystemExit, 'not retired'): d.retire_contracts('contracts/old', 'abandoned', '2026-11-13')
            # re-contracted in another wave, its newest manifest on that contract: it has moved on
            (h/'contracts/new').mkdir(); (h/'contracts/new/family-axe.json').write_text(json.dumps({'family': 'club'}), encoding='utf-8')
            (h/'axe.new-contract.asset.json').write_text(json.dumps({'familyProfile': {'path': 'contracts/new/family-axe.json'}}), encoding='utf-8')
            for k, name in enumerate(('old-contract', 'calibrated-v1', 'loose-v1', 'new-contract')):
                os.utime(h/f'axe.{name}.asset.json', (1e9 + k, 1e9 + k))
            self.assertEqual(d.retire_contracts('contracts/old', 'abandoned', '2026-11-13')['contracts'], ['family-axe.json'])

    def test_textured_refuses_a_field_range_an_existing_donor_manifest_does_not_hold(self):
        from tools.itemkit.drive import Driver
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); d = Driver(self.workspace(root)); h = d.ws.handoff; h.mkdir(parents=True, exist_ok=True)
            for stage in ('geometry', 'appearance'):
                (root/f'knife/{stage}-a1/job').mkdir(parents=True)
                (root/f'knife/{stage}-a1/job/collection.json').write_text(json.dumps({'outputs': [{'path': 'raw.glb', 'sha256': 'g'}]}), encoding='utf-8')
            (h/'knife.geometry-approved-v1.asset.json').write_text(json.dumps({'approval': {'generatedGeometry': {'geometryRawSha256': 'g'}}}), encoding='utf-8')
            (h/'knife.donor-v1.asset.json').write_text(json.dumps({'processing': {'sourceFieldPolicy': {'minimum': -.05, 'maximum': 1.065}}}), encoding='utf-8')
            with mock.patch.object(Driver, 'stage') as stage, self.assertRaisesRegex(SystemExit, 'binds only a new donor manifest'):
                d.textured('knife', 'a1', 'src', 'approved', field_range=[-.22, 1.13])
            stage.assert_not_called()

    def test_an_overshooting_colour_field_needs_a_reviewed_range_bound_to_its_hash(self):
        import hashlib
        from tools.itemkit.drive import Driver
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); d = Driver(self.workspace(root)); h = d.ws.handoff; h.mkdir(parents=True, exist_ok=True)
            job = root/'knife/appearance-a1/job'; job.mkdir(parents=True); digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
            (job/'node-961_00001.glb').write_bytes(b'raw'); (job/'node-922_00001.glb').write_bytes(b'donor')
            def field(attrs):
                np.savez(job/'node-962_00001.npz', attrs=attrs)
                (job/'collection.json').write_text(json.dumps({'state': 'complete', 'outputs': [
                    {'path': str(p), 'sha256': digest(p)} for p in sorted(job.glob('node-*'))]}), encoding='utf-8')
            attrs = np.full((1000, 3), .5); attrs[:3] = -.2; attrs[3:5] = 1.12                # 5 of 1000 samples overshoot
            field(attrs)
            (h/'knife.src.asset.json').write_text(json.dumps({'inputs': {'geometryRaw': {'sha256': digest(job/'node-961_00001.glb')}},
                                                              'approval': {}, 'processing': {}}), encoding='utf-8')
            with self.assertRaisesRegex(SystemExit, r'-0\.2000\.\.1\.1200 lies outside .*\(5 of 1000 .* --field-range -0\.2 1\.12$') as caught:
                d.donor_manifest('knife', 'src', 'donor-v1', 'words')
            from tools.itemkit.drive import parser
            suggested = str(caught.exception).rsplit('--field-range ', 1)[1].split()   # the suggestion parses as typed
            self.assertEqual(parser().parse_args(['textured', 'knife', 'a1', 'src', '--notes', 'n', '--field-range', *suggested]).field_range, [-.2, 1.12])
            with self.assertRaisesRegex(SystemExit, 'lies outside'): d.donor_manifest('knife', 'src', 'donor-v1', 'words', field_range=(-.1, 1.2))
            with self.assertRaisesRegex(SystemExit, 'within'): d.donor_manifest('knife', 'src', 'donor-v1', 'words', field_range=(-.3, 1.2))
            field(attrs.astype(np.float32))                       # float32 -0.2 lies just below -0.2: the suggestion steps out
            with self.assertRaisesRegex(SystemExit, r'--field-range -0\.21 1\.13$') as caught: d.donor_manifest('knife', 'src', 'donor-v1', 'words')
            low, high = (float(x) for x in str(caught.exception).rsplit('--field-range ', 1)[1].split())
            float32 = Path(d.donor_manifest('knife', 'src', 'donor-f32', 'words', field_range=(low, high)))
            self.assertEqual(json.loads(float32.read_text(encoding='utf-8'))['processing']['sourceFieldPolicy']['minimum'], -.21)
            far = attrs.copy(); far[5] = 1.3; field(far)            # past donor.py's reviewed limits: no range can take it
            with self.assertRaisesRegex(SystemExit, 'regenerate the appearance'): d.donor_manifest('knife', 'src', 'donor-far', 'words')
            field(np.full((1000, 3), .5))                                                      # a field the decoder takes as it is
            with self.assertRaisesRegex(SystemExit, 'no reviewed --field-range is needed'):
                d.donor_manifest('knife', 'src', 'donor-v1', 'words', field_range=(-.2, 1.12))
            field(attrs)
            m = json.loads(Path(d.donor_manifest('knife', 'src', 'donor-v1', 'words', field_range=(-.2, 1.12))).read_text(encoding='utf-8'))
            field = m['inputs']['field']['sha256']
            self.assertEqual(m['processing']['sourceFieldPolicy'], {'allowDecoderOvershoot': True, 'fieldSha256': field, 'minimum': -.2, 'maximum': 1.12})
            self.assertIn('5 of 1000 samples (0.500%)', m['approval']['sourceDonor']['notes'])

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
