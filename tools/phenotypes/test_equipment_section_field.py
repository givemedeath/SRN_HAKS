import unittest
from copy import deepcopy
import numpy as np
import equipment_section_field as field


def config():
    return {'schemaVersion': 1, 'kind': 'equipment-c2-section-field', 'axialPolicy': 'identity', 'statureApplications': 0,
            'knots': [{'z': -.05, 'scaleXY': [1., 1.], 'translateXY': [0., 0.]},
                      {'z': .15, 'scaleXY': [1.2, 1.35], 'translateXY': [.001, -.025]},
                      {'z': .4, 'scaleXY': [1.15, 1.25], 'translateXY': [.002, -.03]},
                      {'z': .5, 'scaleXY': [1., 1.], 'translateXY': [0., 0.]}]}


class RegionalEquipmentFieldTests(unittest.TestCase):
    def test_analytic_jacobian_matches_independent_central_difference(self):
        p = np.array([[.13, -.1, .06], [-.2, .03, .27], [.04, -.11, .47]])
        q, j = field.evaluate(config(), p)
        for ax in range(3):
            step = np.zeros_like(p); step[:, ax] = 1e-7
            plus, _ = field.evaluate(config(), p + step)
            minus, _ = field.evaluate(config(), p - step)
            np.testing.assert_allclose((plus-minus)/2e-7, j[:, :, ax], rtol=1e-8, atol=1e-9)

    def test_positive_determinant_everywhere_and_exact_axial_bits(self):
        p = np.c_[np.full(1001, .2), np.full(1001, -.1), np.linspace(-.1, .6, 1001)]
        q, j = field.evaluate(config(), p)
        self.assertTrue((np.linalg.det(j) > 0).all())
        np.testing.assert_array_equal(q[:, 2].view('u8'), p[:, 2].view('u8'))
        np.testing.assert_allclose(np.linalg.det(j), j[:, 0, 0]*j[:, 1, 1], rtol=1e-15)

    def test_c2_knots_have_zero_first_and_second_coefficient_derivatives(self):
        c = config()
        for knot in c['knots']:
            z = knot['z']; p = np.array([[.2, -.1, z]])
            q, j = field.evaluate(c, p)
            np.testing.assert_array_equal(j[0, :2, 2], [0., 0.])
            e = 1e-5
            plus, _ = field.evaluate(c, p+[0, 0, e]); minus, _ = field.evaluate(c, p-[0, 0, e])
            self.assertLess(float(abs((plus+minus-2*q)/e**2).max()), .01)

    def test_noop_and_outside_identity_preserve_authored_nonorthogonal_normal_bits(self):
        p = np.array([[.2, -.1, -.06], [.04, -.11, .5], [0., .1, .55]])
        _, j = field.evaluate(config(), p)
        n = np.array([[.11, -.02, .93], [.6, .4, .9], [1., .02, .05]], dtype='f4')
        out = field.transport_native_normals(n, np.arange(3), j)
        np.testing.assert_array_equal(out.view('u4'), n.view('u4'))

    def test_native_owner_seams_stay_distinct_with_original_magnitudes(self):
        p = np.array([[.13, -.1, .06], [-.2, .03, .27]])
        _, j = field.evaluate(config(), p)
        n = np.array([[.2, .4, 1.1], [.7, -.1, .9], [-.4, .3, .6]])
        owners = np.array([0, 0, 1])
        out = field.transport_native_normals(n, owners, j)
        np.testing.assert_allclose(np.linalg.norm(out, axis=1), np.linalg.norm(n, axis=1), rtol=3e-16, atol=3e-16)
        self.assertFalse(np.array_equal(out[0], out[1]))
        for i, owner in enumerate(owners):
            expected = np.linalg.inv(j[owner]).T @ n[i]
            expected *= np.linalg.norm(n[i])/np.linalg.norm(expected)
            np.testing.assert_allclose(out[i], expected, rtol=1e-15, atol=1e-15)

    def test_normals_remain_perpendicular_to_transformed_tangent_plane(self):
        p = np.array([[.13, -.1, .06]])
        _, j = field.evaluate(config(), p)
        n = np.array([[.3, -.4, .8]])
        tang = np.cross(n[0], [1., 0., 0.])
        out = field.transport_native_normals(n, np.array([0]), j)
        self.assertLess(abs(float(out[0] @ (j[0] @ tang))), 1e-15)

    def test_reject_nonpositive_scale_and_bad_knot_order(self):
        for mutate in ('negative', 'zero', 'duplicate', 'reverse', 'nonfinite'):
            c = config()
            if mutate == 'negative': c['knots'][1]['scaleXY'][0] = -1.
            if mutate == 'zero': c['knots'][1]['scaleXY'][1] = 0.
            if mutate == 'duplicate': c['knots'][2]['z'] = c['knots'][1]['z']
            if mutate == 'reverse': c['knots'] = c['knots'][::-1]
            if mutate == 'nonfinite': c['knots'][1]['translateXY'][0] = float('nan')
            with self.subTest(mutate=mutate), self.assertRaises(ValueError): field.evaluate(c, np.array([[0., 0., .2]]))

    def test_reject_runtime_scale_axial_edit_and_unknown_schema(self):
        for key, value in [('statureApplications', 1), ('axialPolicy', 'shorten'), ('kind', 'unknown'), ('schemaVersion', 2), ('interpolation', 'linear'), ('outsidePolicy', 'repeat-scale')]:
            c = config(); c[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): field.evaluate(c, np.array([[0., 0., .2]]))

    def test_reject_missing_ambiguous_or_out_of_range_native_ownership(self):
        _, j = field.evaluate(config(), np.array([[.13, -.1, .06]]))
        n = np.array([[.3, -.4, .8]])
        for owners in [np.array([-1]), np.array([1]), np.array([0.,]), np.array([[0]]), np.array([], int)]:
            with self.subTest(owners=owners), self.assertRaises(ValueError): field.transport_native_normals(n, owners, j)

    def test_reject_nonfinite_zero_normals_and_improper_jacobian(self):
        j = np.array([np.eye(3)])
        for n in [np.array([[0., 0., 0.]]), np.array([[1., float('nan'), 0.]])]:
            with self.assertRaises(ValueError): field.transport_native_normals(n, np.array([0]), j)
        j[0, 0, 0] = -1.
        with self.assertRaises(ValueError): field.transport_native_normals(np.array([[1., 0., 0.]]), np.array([0]), j)



class NativeCornerOwnershipTests(unittest.TestCase):
    def fixture(self):
        p = np.array([[0., 0., 0.], [1., 0., 0.], [0., 1., 0.], [1., 1., 0.]])
        uv = np.array([[0., 0., 0.], [1., 0., 0.], [0., 1., 0.], [1., 1., 0.], [.5, .5, 0.]])
        f = np.array([[0, 1, 2, 1, 0, 1, 2, 0], [1, 3, 2, 1, 4, 3, 2, 0]])
        po = f[:, :3].ravel(); uo = f[:, 4:7].ravel()
        np_ = p[po].copy(); nn = np.tile([.01, .02, 1.03], (6, 1)); nuv = uv[uo, :2].copy(); nf = np.arange(6).reshape(2, 3)
        return [p, f, uv, np_, nn, nuv, nf, po.copy(), uo.copy()]

    def test_exact_face_order_uv_seam_and_normal_owner_inventory(self):
        a = self.fixture(); r = field.validate_source_correspondence(*a)
        self.assertEqual(r['orderedCorners'], 6)
        self.assertTrue(r['orderedFaceAndUvCornerOwnershipExact'])
        self.assertEqual(r['maximumAsciiNativePositionDifference'], 0.)
        # Same position has two distinct UV owners; no seam collapse.
        self.assertEqual(a[7][1], a[7][3]); self.assertNotEqual(a[8][1], a[8][3])

    def test_reject_changed_winding_or_declared_uv_owner(self):
        for mutate in ('winding', 'uv'):
            a = self.fixture()
            if mutate == 'winding': a[6][0] = a[6][0, ::-1]
            else: a[8][3] = 1
            with self.subTest(mutate=mutate), self.assertRaisesRegex(ValueError, 'ownership changed'):
                field.validate_source_correspondence(*a)

    def test_reject_uv_precision_loss_and_ambiguous_native_position(self):
        for mutate in ('uv', 'position'):
            a = self.fixture()
            if mutate == 'uv': a[5][1, 0] = np.nextafter(np.float32(1.), np.float32(2.))
            else: a[3][3, 0] += .001
            with self.subTest(mutate=mutate), self.assertRaises(ValueError): field.validate_source_correspondence(*a)

    def test_reject_partial_or_out_of_range_native_owner_table(self):
        for mutate in ('shape', 'position_owner', 'uv_owner', 'face', 'zero_normal'):
            a = self.fixture()
            if mutate == 'shape': a[7] = a[7][:-1]
            if mutate == 'position_owner': a[7][0] = 4
            if mutate == 'uv_owner': a[8][0] = -1
            if mutate == 'face': a[6][0, 0] = 6
            if mutate == 'zero_normal': a[4][0] = 0.
            with self.subTest(mutate=mutate), self.assertRaises(ValueError): field.validate_source_correspondence(*a)


if __name__ == '__main__': unittest.main()