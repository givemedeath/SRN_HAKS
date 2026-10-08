import hashlib, json, subprocess, sys, tempfile, unittest
from pathlib import Path
import numpy as np
from assign_target_face_uv_islands import groups_of, find_slot, coverage
from test_descendant_mesh_edit import write_test_glb, capped_cylinder
from descendant_mesh_edit import Mesh

HERE = Path(__file__).resolve().parent


class FaceUvIslandTest(unittest.TestCase):
    def test_groups_by_shared_vertices(self):
        F = np.array([[0, 1, 2], [2, 3, 4], [5, 6, 7], [7, 8, 9], [10, 11, 12]])
        g = sorted(sorted(x) for x in groups_of(F, [0, 1, 2, 3, 4]))
        self.assertEqual(g, [[0, 1], [2, 3], [4]])

    def test_find_slot_avoids_occupied(self):
        occ = np.zeros((256, 256), bool); occ[:, :128] = True
        x, y = find_slot(occ, 40, 30)
        self.assertGreaterEqual(x, 128)
        self.assertFalse(occ[y:y + 30, x:x + 40].any())
        with self.assertRaises(RuntimeError):
            find_slot(np.ones((64, 64), bool), 8, 8)

    def test_coverage_raster(self):
        c = coverage(np.array([[[0, 0], [0.5, 0], [0, 0.5]]]), 64)
        self.assertTrue(c[4, 4]); self.assertFalse(c[60, 60])

    def test_cli_new_faces_get_empty_space_and_retained_uvs_stay_exact(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            pos, faces = capped_cylinder(radius=0.05, height=0.1, rings=6, segments=16)
            uv = np.c_[(np.arctan2(pos[:, 1], pos[:, 0]) / (2 * np.pi)) % 1 * 0.5, (pos[:, 2] - pos[:, 2].min()) * 4]
            write_test_glb(d / 'm.glb', pos, faces, uv=uv)
            mesh = Mesh(d / 'm.glb')
            fs = np.arange(len(mesh.F)); top = mesh.F.max()
            fs[np.any(mesh.F == top, axis=1)] = -1          # the top fan plays the rebuilt cap
            np.save(d / 'fs.npy', fs)
            h = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
            cfg = dict(name='t', master=str(d / 'm.glb'), masterSha256=h(d / 'm.glb'), faceSource=str(d / 'fs.npy'), faceSourceSha256=h(d / 'fs.npy'),
                       atlasSize=256, marginPixels=4)
            (d / 'c.json').write_text(json.dumps(cfg))
            r = subprocess.run([sys.executable, '-B', str(HERE / 'assign_target_face_uv_islands.py'), '--config', str(d / 'c.json'), '--output', str(d / 'o')],
                               cwd=HERE, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            out = Mesh(d / 'o' / 't-local.glb'); P, N, T = mesh.corners(); P2, N2, T2 = out.corners()
            new = fs < 0
            self.assertTrue(np.allclose(T2[~new], T[~new], atol=1e-7))
            self.assertTrue(np.allclose(P2, P, atol=1e-6))
            self.assertGreater(T2[new][..., 0].min(), 0.5)      # placed right of the occupied half
            rec = json.loads((d / 'o' / 'descendant.json').read_text())
            self.assertEqual(len(rec['islands']), 1)
            self.assertEqual(rec['islands'][0]['faces'], int(new.sum()))


if __name__ == '__main__':
    unittest.main()
