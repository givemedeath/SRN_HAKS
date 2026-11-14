"""Shell recovery on small synthetic spheres: closed rebuild from an open donor, specks, a pinched join, remeshing."""
import unittest

import numpy as np

from tools.itemkit.geometry import invalid_vertex_links, topology, weld


def sphere(radius=.05, centre=(0, 0, 0), rings=12, segments=24):
    """A closed, outward UV sphere."""
    top, bottom = [0, 0, radius], [0, 0, -radius]; ring = []
    for i in range(1, rings):
        a = np.pi*i/rings
        ring += [[radius*np.sin(a)*np.cos(2*np.pi*j/segments), radius*np.sin(a)*np.sin(2*np.pi*j/segments), radius*np.cos(a)] for j in range(segments)]
    v = np.array([top] + ring + [bottom], float) + centre; last = len(v) - 1; faces = []
    at = lambda i, j: 1 + i*segments + j % segments
    for j in range(segments): faces.append((0, at(0, j), at(0, j + 1)))
    for i in range(rings - 2):
        for j in range(segments): faces += [(at(i, j), at(i + 1, j), at(i + 1, j + 1)), (at(i, j), at(i + 1, j + 1), at(i, j + 1))]
    for j in range(segments): faces.append((last, at(rings - 2, j + 1), at(rings - 2, j)))
    f = np.array(faces, np.int64)
    if topology(v, f)['signedVolume'] < 0: f = f[:, ::-1].copy()
    return v, f


def joined(*meshes):
    vs, fs, offset = [], [], 0
    for v, f in meshes: vs.append(v); fs.append(f + offset); offset += len(v)
    return np.vstack(vs), np.vstack(fs)


class SphereTests(unittest.TestCase):
    def test_the_synthetic_sphere_is_closed_and_the_link_helper_matches_topology(self):
        v, f = sphere(); self.assertTrue(topology(v, f)['closedWound'])
        pinched = joined(sphere(), sphere(centre=(0, 0, -.1)))             # one pole touches the other
        unique, w = weld(*pinched)
        self.assertEqual(len(invalid_vertex_links(w, len(unique))), 1)
        self.assertEqual(topology(*pinched)['invalidVertexLinks'], 1)


class ShellRepairTests(unittest.TestCase):
    def setUp(self):
        try:
            import pymeshlab, igl, scipy  # noqa: F401
        except ImportError: self.skipTest('pymeshlab, igl and scipy not on the path (itemkit PYTHONPATH)')
        from tools.itemkit import shell_repair
        self.repair = shell_repair

    def test_specks_are_dropped_and_the_main_body_kept(self):
        v, f = joined(sphere(), sphere(radius=1e-4, centre=(.2, 0, 0)))
        out_v, out_f, report = self.repair.drop_specks(v, f)
        self.assertEqual((report['components'], report['kept'], report['droppedTriangles']), (2, 1, len(sphere()[1])))
        self.assertTrue(report['after']['closedWound']); self.assertEqual(len(out_f), len(sphere()[1]))
        with self.assertRaisesRegex(ValueError, 'speck fraction'): self.repair.drop_specks(v, f, fraction=.5)

    def test_a_pinched_join_is_cut_out_and_closed(self):
        v, f = joined(sphere(), sphere(centre=(0, 0, -.1)))
        out_v, out_f, report = self.repair.repair_nonmanifold(v, f)
        self.assertEqual(report['badVertices'], 1); self.assertGreater(report['removedFaces'], 0)
        self.assertEqual(report['before']['invalidVertexLinks'], 1)
        self.assertTrue(report['after']['closedWound']); self.assertEqual(report['after']['invalidVertexLinks'], 0)
        self.assertGreater(report['volumeRatio'], .9)
        same_v, same_f, same = self.repair.repair_nonmanifold(*sphere())
        self.assertTrue(same['unchanged']); self.assertEqual(len(same_f), len(sphere()[1]))

    def test_remesh_keeps_a_closed_shell_at_the_same_genus(self):
        v, f = sphere()
        out_v, out_f, report = self.repair.remesh(v, f, .008)
        self.assertTrue(report['after']['closedWound']); self.assertEqual(report['after']['totalGenus'], 0)
        self.assertAlmostEqual(report['volumeRatio'], 1, delta=.05)
        with self.assertRaisesRegex(ValueError, 'Remesh input'): self.repair.remesh(v, f[:-3], .008)

    def test_a_closed_shell_is_rebuilt_around_an_open_donor(self):
        v, f = sphere(radius=.02); open_f = f[1:]                          # a one-triangle hole at the pole
        self.assertFalse(topology(v, open_f)['closedWound'])
        out_v, out_f, report = self.repair.shell_from_donor(v, open_f, voxel=.002, minimum_component=50)
        self.assertTrue(report['after']['closedWound']); self.assertEqual(report['after']['totalGenus'], 0)
        donor_volume = topology(v, f)['signedVolume']
        self.assertTrue(donor_volume < report['after']['signedVolume'] < 2*donor_volume)   # the dilation sits just outside
        with self.assertRaisesRegex(ValueError, 'voxels exceed'): self.repair.shell_from_donor(v, f, voxel=.002, maximum_voxels=1000)


class DriverWiringTests(unittest.TestCase):
    """The drive subcommands reach their functions with the right arguments, write new files only, and refuse cleanly."""
    def setUp(self):
        try:
            import pymeshlab, igl, scipy  # noqa: F401
        except ImportError: self.skipTest('pymeshlab, igl and scipy not on the path (itemkit PYTHONPATH)')

    def run_drive(self, *argv):
        import contextlib, io, json
        from unittest import mock
        from tools.itemkit import drive
        out = io.StringIO()
        with mock.patch.object(drive.Workspace, 'load', return_value=None), contextlib.redirect_stdout(out):
            drive.main(list(argv))
        return json.loads(out.getvalue())

    def test_shell_commands_write_a_new_glb_and_refuse_an_existing_one(self):
        import tempfile
        from pathlib import Path
        from tools.headkit.gltf import write_mesh
        with tempfile.TemporaryDirectory() as folder:
            source, specks, even = (str(Path(folder)/n) for n in ('in.glb', 'specks.glb', 'even.glb'))
            write_mesh(source, *joined(sphere(), sphere(radius=1e-4, centre=(.2, 0, 0))))
            self.assertEqual(self.run_drive('drop-specks', source, specks)['kept'], 1)
            result = self.run_drive('remesh-shell', specks, even, '0.008', '--taubin', '1')
            self.assertEqual((result['edge'], result['taubin'], result['after']['closedWound']), (.008, 1, True))
            with self.assertRaisesRegex(SystemExit, 'exists'): self.run_drive('repair-shell', source, even)
            opened = str(Path(folder)/'open.glb'); v, f = sphere(); write_mesh(opened, v, f[:-3])
            with self.assertRaisesRegex(SystemExit, 'remesh: Remesh input'): self.run_drive('remesh-shell', opened, str(Path(folder)/'x.glb'), '0.008')
            self.assertFalse((Path(folder)/'x.glb').exists())


if __name__ == '__main__':
    unittest.main()
