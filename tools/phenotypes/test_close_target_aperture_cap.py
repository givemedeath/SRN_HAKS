import hashlib, json, subprocess, sys, tempfile, unittest
from pathlib import Path
import numpy as np
from close_target_aperture_cap import classify_shell, boundary_loops, zipper, resample_closed
from test_descendant_mesh_edit import write_test_glb
from descendant_mesh_edit import Mesh, closure

HERE = Path(__file__).resolve().parent


def vessel(seg=32, rings=10, R=0.1, r=0.096, H=0.3):
    pos = []; faces = []
    def ring(rad, z):
        start = len(pos)
        for j in range(seg):
            a = 2 * np.pi * j / seg; pos.append([rad * np.cos(a), rad * np.sin(a), z])
        return start
    outer = [ring(R, H * i / rings) for i in range(rings + 1)]
    inner = [ring(r, H - (H - 0.01) * i / rings) for i in range(rings + 1)]
    chain = outer + inner  # outer up, rim, inner down: one continuous tube
    for a, b in zip(chain[:-1], chain[1:]):
        for j in range(seg):
            p, q = a + j, a + (j + 1) % seg; s, t = b + j, b + (j + 1) % seg
            faces += [[p, q, t], [p, t, s]]
    cb = len(pos); pos.append([0, 0, 0]); ci = len(pos); pos.append([0, 0, 0.01])
    for j in range(seg):
        faces.append([cb, outer[0] + (j + 1) % seg, outer[0] + j])
        faces.append([ci, inner[-1] + j, inner[-1] + (j + 1) % seg])
    return np.asarray(pos), np.asarray(faces)


class ApertureCapTest(unittest.TestCase):
    def test_vessel_closed_and_classified(self):
        pos, faces = vessel()
        self.assertEqual(closure(faces)['boundaryEdges'], 0)
        inner, info = classify_shell(pos, faces)
        cen = pos[faces].mean(1)
        self.assertTrue(np.all(np.hypot(cen[inner, 0], cen[inner, 1]) < 0.0985))

    def test_zipper_closes_ring_strip(self):
        a = resample_closed(np.c_[np.cos(np.linspace(0, 2 * np.pi, 40, endpoint=False)), np.sin(np.linspace(0, 2 * np.pi, 40, endpoint=False))], 40)
        b = 0.5 * resample_closed(a, 17)
        tris = zipper(np.arange(40), a, np.arange(40, 57), b, np.zeros(2))
        self.assertEqual(len(tris), 57)

    def test_cli_closes_aperture(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d); pos, faces = vessel()
            write_test_glb(d / 'v.glb', pos, faces)
            cfg = dict(part='v', name='cap', master=str(d / 'v.glb'), masterSha256=hashlib.sha256((d / 'v.glb').read_bytes()).hexdigest(),
                       apertureAxisXY=[0, 0], lipCut=0.29, lipRadius=0.2, apexZ=0.33, rings=6, blend=0.02, smoothIterations=10)
            (d / 'c.json').write_text(json.dumps(cfg))
            r = subprocess.run([sys.executable, '-B', str(HERE / 'close_target_aperture_cap.py'), '--config', str(d / 'c.json'), '--output', str(d / 'o')], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            out = Mesh(d / 'o' / 'cap-local.glb')
            c = closure(out.F)
            self.assertEqual((c['boundaryEdges'], c['nonManifoldEdges']), (0, 0))
            self.assertLess(len(out.F), len(faces))


if __name__ == '__main__':
    unittest.main()
