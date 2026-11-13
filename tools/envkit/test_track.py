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
