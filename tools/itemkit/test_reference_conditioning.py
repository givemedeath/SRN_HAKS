"""Focused CPU tests: alpha provenance, paired layout, holes and stale inputs."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
from PIL import Image

from tools.itemkit.reference_conditioning import Pins, prepare, registration, topology


class ConditioningTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        # Two disconnected parts, an intentional opening, and a thin member.
        self.mask = np.zeros((128, 192), np.uint8)
        self.mask[20:105, 20:115] = 255
        self.mask[45:80, 45:90] = 0
        self.mask[60:64, 115:145] = 255
        self.mask[30:95, 158:177] = 255
        detail = np.zeros((128, 192, 4), np.uint8)
        detail[:, :, :3] = [180, 30, 20]
        detail[:, :, 3] = self.mask
        clay = detail.copy()
        clay[:, :, :3] = 170
        clay[:, :, 3] = 240  # Unusable old target alpha including frame and hole.
        Image.fromarray(detail).save(self.root / 'detail.png')
        Image.fromarray(clay).save(self.root / 'clay.png')
        self.evidence = {
            'detailSha256': self.pin('detail.png')['sha256'],
            'claySha256': self.pin('clay.png')['sha256'],
            'actualImagesViewed': True, 'maskTransferVisuallyReviewed': True,
            'intentionalOpeningsReviewed': True, 'thinMembersReviewed': True,
            'notes': 'Synthetic registration only, not a visual approval of real art.',
            'landmarks': [{'name': str(i), 'detail': xy, 'clay': xy}
                          for i, xy in enumerate([[.15, .2], [.85, .3], [.2, .7], [.8, .7]])],
            'edgeMeasurements': [{'name': str(i), 'offsetPixels': 0} for i in range(4)],
        }
        self.write('registration.json', self.evidence)
        self.spec = {'route': 'replace-invalid-clay-alpha-from-registered-detail',
                     'detail': self.pin('detail.png'), 'clay': self.pin('clay.png'),
                     'registrationEvidence': self.pin('registration.json'),
                     'canvasSize': 2048, 'paddingPixels': 102, 'sourceAlphaFloor': 16}
        self.write('spec.json', self.spec)

    def write(self, name, data):
        (self.root / name).write_text(json.dumps(data), encoding='utf-8')

    def pin(self, name):
        path = self.root / name
        return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

    def run_prepare(self):
        return prepare(self.root / 'spec.json', self.root / 'output')

    def test_holes_components_thin_member_and_shared_canvas_preserved(self):
        result = self.run_prepare()
        self.assertEqual(result['sourceMaskTopology'], {role: {'components': 2, 'holes': 1} for role in ['detail', 'clay']})
        self.assertEqual(result['sourceMaskTopology'], result['outputMaskTopology'])
        self.assertTrue(result['resampled2K'])
        self.assertFalse(result['native2K'])
        self.assertFalse(result['conditionedReferenceAccepted'])
        self.assertEqual(result['holesFilled'], 0)
        with Image.open(result['artifacts']['detail']['mask']['path']) as first, Image.open(result['artifacts']['clay']['mask']['path']) as second:
            np.testing.assert_array_equal(np.asarray(first), np.asarray(second))
            self.assertEqual(first.size, (2048, 2048))
        for role in ['detail', 'clay']:
            with Image.open(result['artifacts'][role]['foregroundNative']['path']) as im:
                raw = np.asarray(im)
            np.testing.assert_array_equal(raw[:, :, 3], self.mask)
            expected = [180, 30, 20] if role == 'detail' else [170, 170, 170]
            self.assertTrue(np.all(raw[:, :, :3] == expected))

    def test_black_conditioning_contains_no_unmasked_background(self):
        result = self.run_prepare()
        for role in ['detail', 'clay']:
            with Image.open(result['artifacts'][role]['conditioning']['path']) as im:
                rgb = np.asarray(im)
            with Image.open(result['artifacts'][role]['mask']['path']) as im:
                mask = np.asarray(im)
            self.assertEqual(int(rgb[mask == 0].max()), 0)
            self.assertTrue(np.all(rgb <= mask[:, :, None]))

    def test_lanczos_color_overshoot_cannot_outlive_its_resampled_alpha(self):
        for role in ['detail', 'clay']:
            with Image.open(self.root / (role + '.png')) as im:
                data = np.array(im)
            data[:, :, :3] = np.random.default_rng(12).integers(0, 256, data[:, :, :3].shape, dtype=np.uint8)
            Image.fromarray(data).save(self.root / (role + '.png'))
            self.spec[role] = self.pin(role + '.png')
            self.evidence[role + 'Sha256'] = self.spec[role]['sha256']
        self.write('registration.json', self.evidence)
        self.spec['registrationEvidence'] = self.pin('registration.json')
        self.write('spec.json', self.spec)
        result = self.run_prepare()
        for role in ['detail', 'clay']:
            with Image.open(result['artifacts'][role]['conditioning']['path']) as im:
                rgb = np.asarray(im)
            with Image.open(result['artifacts'][role]['mask']['path']) as im:
                mask = np.asarray(im)
            self.assertTrue(np.all(rgb <= mask[:, :, None]))
            self.assertLessEqual(int(rgb[mask <= 2].max()), 2)

    def test_independent_valid_pair_masks_are_not_replaced_or_unioned(self):
        with Image.open(self.root / 'clay.png') as im:
            data = np.array(im)
        clay_mask = self.mask.copy()
        clay_mask[20:24, 20:115] = 0
        data[:, :, 3] = clay_mask
        Image.fromarray(data).save(self.root / 'clay.png')
        self.spec['clay'] = self.pin('clay.png')
        self.spec['route'] = 'preserve-reviewed-pair-alpha'
        self.evidence['claySha256'] = self.spec['clay']['sha256']
        self.evidence['pairMasksVisuallyReviewed'] = True
        self.write('registration.json', self.evidence)
        self.spec['registrationEvidence'] = self.pin('registration.json')
        self.write('spec.json', self.spec)
        result = self.run_prepare()
        with Image.open(result['artifacts']['clay']['foregroundNative']['path']) as im:
            np.testing.assert_array_equal(np.asarray(im)[:, :, 3], clay_mask)
        with Image.open(result['artifacts']['detail']['foregroundNative']['path']) as im:
            np.testing.assert_array_equal(np.asarray(im)[:, :, 3], self.mask)

    def test_stale_source_and_conflicting_pins_rejected(self):
        path = self.root / 'clay.png'
        path.write_bytes(path.read_bytes() + b'changed')
        with self.assertRaisesRegex(ValueError, 'Stale consumed'):
            self.run_prepare()
        pins = Pins()
        row = self.pin('detail.png')
        pins.check(row)
        with self.assertRaisesRegex(ValueError, 'Conflicting'):
            pins.check({**row, 'sha256': '0' * 64})

    def test_invalid_or_clipped_detailed_alpha_rejected(self):
        with Image.open(self.root / 'detail.png') as im:
            data = np.array(im)
        data[0, 0, 3] = 255
        Image.fromarray(data).save(self.root / 'detail.png')
        self.spec['detail'] = self.pin('detail.png')
        self.evidence['detailSha256'] = self.spec['detail']['sha256']
        self.write('registration.json', self.evidence)
        self.spec['registrationEvidence'] = self.pin('registration.json')
        self.write('spec.json', self.spec)
        with self.assertRaisesRegex(ValueError, 'clipped'):
            self.run_prepare()

    def test_bad_registration_cannot_authorize_mask_transfer(self):
        for change, error in [({'actualImagesViewed': False}, 'visual'),
                              ({'detailSha256': '0' * 64}, 'Stale'),
                              ({'thinMembersReviewed': False}, 'thin members')]:
            evidence = {**self.evidence, **change}
            with self.assertRaisesRegex(ValueError, error):
                registration(evidence, self.spec['detail'], self.spec['clay'], (192, 128))
        evidence = copy.deepcopy(self.evidence)
        evidence['landmarks'][0]['clay'] = [.3, .3]
        with self.assertRaisesRegex(ValueError, '2%'):
            registration(evidence, self.spec['detail'], self.spec['clay'], (192, 128))
        evidence = copy.deepcopy(self.evidence)
        evidence['edgeMeasurements'][0]['offsetPixels'] = 5
        with self.assertRaisesRegex(ValueError, 'measured silhouette'):
            registration(evidence, self.spec['detail'], self.spec['clay'], (192, 128))
        evidence = copy.deepcopy(self.evidence)
        for point in evidence['landmarks']:
            point['detail'] = point['clay'] = [.5, .5]
        with self.assertRaisesRegex(ValueError, 'distinct landmark positions'):
            registration(evidence, self.spec['detail'], self.spec['clay'], (192, 128))

    def test_fresh_output_required(self):
        (self.root / 'output').mkdir()
        with self.assertRaisesRegex(ValueError, 'fresh output'):
            self.run_prepare()

    def test_topology_is_read_only(self):
        original = self.mask.copy()
        topology(self.mask)
        np.testing.assert_array_equal(self.mask, original)


if __name__ == '__main__':
    unittest.main()
