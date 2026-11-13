"""Railway track is built to gauge, low enough to walk across, and seamless along its length."""
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from . import convert, local, tile, track


class TrackTest(unittest.TestCase):
    def test_a_piece_is_built_to_gauge_and_lies_low(self):
        vertices, normals, uvs, faces = track.mesh()
        np.testing.assert_allclose(vertices.min(0), [-track.LENGTH / 2, -track.BED_BASE, 0.0], atol=1e-9)
        np.testing.assert_allclose(vertices.max(0), [track.LENGTH / 2, track.BED_BASE, track.HEIGHT], atol=1e-9)
        self.assertLess(track.HEIGHT, tile.KNEE)  # under the knee, so it closes no walk cell where it is laid
        heads = vertices[np.isclose(vertices[:, 2], track.HEIGHT)][:, 1]  # the rail tops
        self.assertAlmostEqual(heads[heads > 0].min() - heads[heads < 0].max(), track.GAUGE)
        np.testing.assert_allclose(np.diff(track.sleepers()), track.PITCH)
        self.assertAlmostEqual(track.sleepers()[0] + track.LENGTH / 2, track.PITCH / 2)  # so pieces laid end to end keep the pitch
        corner = vertices[faces]; turn = np.cross(corner[:, 1] - corner[:, 0], corner[:, 2] - corner[:, 0])
        self.assertTrue((np.einsum('ij,ij->i', turn, normals[faces[:, 0]]) > 0).all())  # each face wound to face its normal
        self.assertTrue((normals[:, 2] > -1e-9).all())  # and none looks down
        self.assertTrue((uvs >= 0).all() and (uvs <= 1).all())

    def test_a_merge_brings_the_next_rows_track_into_the_through_track(self):
        """User, 2026-11-13: "can you make the tracks merge" at both ends of the depot."""
        vertices, normals, uvs, faces = track.merge_mesh()
        offset, length = track.MERGE_OFFSET, track.MERGE_LENGTH
        np.testing.assert_allclose(vertices.min(0), [-length / 2, -track.BED_BASE, 0.0], atol=1e-9)
        np.testing.assert_allclose(vertices.max(0), [length / 2, offset + track.BED_BASE, track.HEIGHT], atol=1e-9)
        heads = np.unique(vertices[np.isclose(vertices[:, 0], length / 2) & np.isclose(vertices[:, 2], track.HEIGHT), 1].round(6))
        middle = track.rails()[1]; expected = [side * middle + edge * track.HEAD / 2 for side in (-1, 1) for edge in (-1, 1)]
        np.testing.assert_allclose(heads, sorted(expected + [offset + one for one in expected]), atol=1e-6)  # both tracks to gauge where it ends
        pieces, angle = track.merging(); line = track.path((-length / 2 + track.LEAD, 0.0), 0.0, pieces)
        turns = np.diff([sample[3] for sample in line]) / np.diff([sample[0] for sample in line])
        self.assertLessEqual(np.abs(turns).max(), 1 / track.MERGE_RADIUS + 1e-6)  # no curve tighter than the radius
        self.assertAlmostEqual(max(sample[3] for sample in line), angle); self.assertLess(np.degrees(angle), 30)
        self.assertAlmostEqual(line[-1][1], length / 2); self.assertAlmostEqual(line[-1][2], offset); self.assertAlmostEqual(line[-1][3], 0.0)
        corner = vertices[faces]; turn = np.cross(corner[:, 1] - corner[:, 0], corner[:, 2] - corner[:, 0])
        self.assertTrue((np.einsum('ij,ij->i', turn, normals[faces[:, 0]]) > 0).all())
        self.assertTrue((normals[:, 2] > -1e-9).all()); self.assertTrue((uvs >= 0).all() and (uvs <= 1).all())
        # One sleeper never stands in another: their tops, drawn on a two-centimetre grid, cover no cell twice.
        tops = faces[np.isclose(vertices[faces][:, :, 2], track.SLEEPER_TOP).all(1) & (normals[faces[:, 0], 2] > 0.99)]
        cell = 0.02; covered = np.zeros((int(length / cell) + 1, int((offset + 4) / cell) + 1), int); area = 0.0
        for triangle in vertices[tops][:, :, :2]:
            low, high = np.floor(triangle.min(0) / cell).astype(int), np.ceil(triangle.max(0) / cell).astype(int)
            xs, ys = np.meshgrid(np.arange(low[0], high[0]) + 0.5, np.arange(low[1], high[1]) + 0.5, indexing='ij'); spots = np.stack([xs, ys], -1) * cell
            a, b, c = triangle; d = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
            w0 = ((b[1] - c[1]) * (spots[..., 0] - c[0]) + (c[0] - b[0]) * (spots[..., 1] - c[1])) / d
            w1 = ((c[1] - a[1]) * (spots[..., 0] - c[0]) + (a[0] - c[0]) * (spots[..., 1] - c[1])) / d
            inside = (w0 >= 0) & (w1 >= 0) & (w0 + w1 < 1)  # half-open, so a shared edge is drawn once
            covered[(xs[inside] - 0.5 + length / 2 / cell).astype(int), (ys[inside] - 0.5 + 2 / cell).astype(int)] += 1
            area += abs(d) / 2
        self.assertLessEqual((covered > 1).sum() * cell ** 2, 0.002 * area)

    def test_its_maps_are_seamless_along_the_track_and_it_converts_as_it_was_built(self):
        with tempfile.TemporaryDirectory() as scratch:
            folder = Path(scratch) / 'piece'; record = track.build(folder, 3)
            self.assertEqual(sorted(record['files']), ['model.glb', *sorted(f'texture_0_{kind}.png' for kind in local.MAPS)])
            self.assertEqual(json.loads((folder / 'track.json').read_text(encoding='utf-8')), record)
            with self.assertRaisesRegex(ValueError, 'fresh folder'):
                track.build(folder, 3)
            colour = np.asarray(Image.open(folder / 'texture_0_base_color.png'), float)
            for band in ('ballast', 'railTop', 'railSide', 'railFoot'):  # the bands that run along the track
                top, bottom = track.BANDS[band]; part = colour[top:bottom]
                seam = np.abs(part[:, 0] - part[:, -1]).mean(); step = np.abs(np.diff(part, axis=1)).mean()
                self.assertLess(seam, 1.5 * step + 1, band)  # from the last column to the first no more than from one to the next
            made = convert.shape(folder / 'model.glb', {kind: folder / f'texture_0_{kind}.png' for kind in local.MAPS}, height=track.HEIGHT)
            self.assertAlmostEqual(made['scale'], 1.0, places=6); self.assertEqual(made['angles'], (0.0, 0.0, 0.0))
            self.assertEqual((made['facesTurned'], made['repaired'], made['turned']), (0, 0, 0))
            np.testing.assert_allclose(made['vertices'], track.mesh()[0], atol=1e-5)  # along x, as it was built


if __name__ == '__main__':
    unittest.main()
