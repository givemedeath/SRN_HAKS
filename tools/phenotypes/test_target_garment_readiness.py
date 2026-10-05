"""Boundary probes must report interior crossings without classifying colours."""
import unittest

import numpy as np

from audit_target_garment_readiness import segment_triangle_interior, uv_pixels


class GarmentBoundaryProbeTests(unittest.TestCase):
    def test_crossing_segment_reports_only_inside_portion(self):
        result = segment_triangle_interior([[-1, 1], [3, 1]], [[0, 0], [2, 0], [0, 2]])
        np.testing.assert_allclose(result, [.25, .5], atol=1e-9)

    def test_winding_does_not_change_texture_boundary_probe(self):
        triangle = np.array([[5., 7.], [9., 8.], [6., 12.]])
        segment = [[3, 9], [12, 9]]
        np.testing.assert_allclose(segment_triangle_interior(segment, triangle),
                                   segment_triangle_interior(segment, triangle[::-1]), atol=1e-12)

    def test_exact_edge_and_single_vertex_touch_are_not_interior_crossings(self):
        triangle = [[0, 0], [2, 0], [0, 2]]
        self.assertIsNone(segment_triangle_interior([[-1, 0], [3, 0]], triangle))
        self.assertIsNone(segment_triangle_interior([[-1, 3], [1, 1]], triangle))

    def test_outside_segment_and_degenerate_uv_are_not_partition_candidates(self):
        self.assertIsNone(segment_triangle_interior([[3, 3], [4, 3]], [[0, 0], [2, 0], [0, 2]]))
        self.assertIsNone(segment_triangle_interior([[0, -1], [0, 1]], [[0, 0], [0, 1], [0, 2]]))

    def test_inside_segment_retains_full_interval(self):
        np.testing.assert_allclose(segment_triangle_interior([[.2, .2], [.4, .4]], [[0, 0], [2, 0], [0, 2]]), [0, 1])

    def test_zero_length_point_probe_has_no_boundary_crossing(self):
        self.assertIsNone(segment_triangle_interior([[.2, .2], [.2, .2]], [[0, 0], [2, 0], [0, 2]]))

    def test_nonfinite_probe_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Finite 2D'):
            segment_triangle_interior([[0, 0], [np.nan, 1]], [[0, 0], [2, 0], [0, 2]])

    def test_source_uv_top_left_and_texel_centres_are_explicit(self):
        np.testing.assert_allclose(uv_pixels([[0, 0], [1, 1], [.25, .5]], 2048, 1024),
                                   [[-.5, -.5], [2047.5, 1023.5], [511.5, 511.5]])


if __name__ == '__main__':
    unittest.main()
