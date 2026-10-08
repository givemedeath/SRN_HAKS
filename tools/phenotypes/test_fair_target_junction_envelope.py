import hashlib, json, subprocess, sys, tempfile, unittest
from pathlib import Path
import numpy as np
from fair_target_junction_envelope import column_target
from test_descendant_mesh_edit import write_test_glb, capped_cylinder
from descendant_mesh_edit import Mesh, write_preview

HERE = Path(__file__).resolve().parent


class JunctionEnvelopeTest(unittest.TestCase):
    def test_column_target_continuous_and_tucked(self):
        t = np.round(np.arange(-0.05, 0.1, 0.0025), 5)
        rX = np.where(t > -0.01, 0.06, np.nan); rX[(t > -0.01) & (t < 0.02)] = 0.065  # lip
        rY = np.where(t < 0.03, 0.055, np.nan)
        cfg = dict(tFar=0.05, tCross=0.0, margin=0.0015, tuck=0.3)
        E = column_target(t, rX, rY, cfg)
        i = int(np.argmin(np.abs(t)))
        self.assertAlmostEqual(E[i], 0.055, places=6)
        self.assertTrue(np.all(E[(t < 0) & (t > -0.01)] <= 0.055 - 0.0015 + 1e-9))
        band = (t >= 0) & (t <= 0.05)
        self.assertLess(np.abs(np.diff(E[band])).max(), 0.002)

    def test_cap_length_rounds_terminal(self):
        t = np.round(np.arange(-0.05, 0.1, 0.0025), 5)
        rX = np.where(t > -0.03, 0.06, np.nan)
        rY = np.where(t < 0.03, 0.055, np.nan)
        E = column_target(t, rX, rY, dict(tFar=0.05, tCross=0.0, margin=0.0015, tuck=0.3, capLength=0.01))
        below = (t < 0) & (t > -0.03)
        self.assertTrue(np.all(np.diff(E[below]) >= -1e-12))
        self.assertLess(E[int(np.argmin(np.abs(t + 0.01)))], 0.001)

    def test_cli_partner_preview(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            x, fx = capped_cylinder(radius=0.065, height=0.2, rings=40, segments=36, z0=0.0)
            y, fy = capped_cylinder(radius=0.055, height=0.2, rings=40, segments=36, z0=-0.17)
            write_test_glb(d / 'x.glb', x, fx); write_test_glb(d / 'y.glb', y, fy)
            ym = Mesh(d / 'y.glb'); P, N, T = ym.corners(); write_preview(d / 'y.glb', P, N, T, d / 'yp.glb')
            cfg = dict(part='x', name='j', master=str(d / 'x.glb'), masterSha256=hashlib.sha256((d / 'x.glb').read_bytes()).hexdigest(),
                       partner=dict(part='y', master=str(d / 'yp.glb'), sha256=hashlib.sha256((d / 'yp.glb').read_bytes()).hexdigest(), offset=[0, 0, 0]),
                       origin=[0, 0, 0], axis=[0, 0, 1], tRange=[-0.06, 0.12], tFar=0.08, tCross=0.01, margin=0.0015, tuck=0.3, samples=40000)
            (d / 'c.json').write_text(json.dumps(cfg))
            r = subprocess.run([sys.executable, '-B', str(HERE / 'fair_target_junction_envelope.py'), '--config', str(d / 'c.json'), '--output', str(d / 'o')], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            out = Mesh(d / 'o' / 'j-local.glb')
            low = out.U[:, 2] < 0.012
            self.assertLess(np.hypot(out.U[low, 0], out.U[low, 1]).max(), 0.058)
            src = Mesh(d / 'x.glb').prims[0]['pos']; far = src[:, 2] > 0.12
            self.assertTrue(np.allclose(out.prims[0]['pos'][far], src[far]))


if __name__ == '__main__':
    unittest.main()
