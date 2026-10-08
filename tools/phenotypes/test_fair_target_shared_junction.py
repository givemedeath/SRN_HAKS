import hashlib, json, subprocess, sys, tempfile, unittest
from pathlib import Path
import numpy as np
from fair_target_shared_junction import shared_targets
from test_descendant_mesh_edit import write_test_glb, capped_cylinder
from descendant_mesh_edit import Mesh

HERE = Path(__file__).resolve().parent


class SharedJunctionTest(unittest.TestCase):
    def cfg(self):
        return dict(tLowRef=-0.05, tHighRef=0.06, tSeam=0.0, margin=0.0015, tuck=0.3, tuckBlend=0.008, coverOffset=0.0003,
                    plateauHigh=0.01, plateauLow=0.01)

    def test_targets_meet_at_seam_and_tuck_smoothly(self):
        t = np.round(np.arange(-0.08, 0.09, 0.0025), 5)
        r_low = np.where(t < 0.02, 0.05, np.nan); r_low[(t > 0.0) & (t < 0.02)] = 0.045
        r_high = np.where(t > -0.02, 0.06, np.nan); r_high[(t > -0.02) & (t < 0.01)] = 0.066  # rolled lip
        TL, TH, E = shared_targets(t, r_low, r_high, self.cfg())
        i = int(np.argmin(np.abs(t)))
        self.assertAlmostEqual(TH[i] - TL[i], 0.0003, places=6)
        vis = np.fmax(TL, TH)
        band = (t >= -0.05) & (t <= 0.06)
        self.assertLess(np.nanmax(np.abs(np.diff(vis[band]))), 0.0015)  # no shelf in the visible envelope
        below = (t < 0) & (t > -0.02)
        self.assertTrue(np.all(TH[below] <= TL[below] + 0.0003 + 1e-9))
        self.assertTrue(np.allclose(TH[t > 0.07], r_high[t > 0.07], equal_nan=True))

    def test_rounded_high_cap_and_max_grow(self):
        t = np.round(np.arange(-0.08, 0.09, 0.0025), 5)
        r_low = np.where(t < 0.03, 0.05, np.nan)
        r_high = np.where(t > -0.03, 0.045, np.nan)
        cfg = dict(self.cfg(), highCapLength=0.02, overlap=0.0)
        TL, TH, E = shared_targets(t, r_low, r_high, cfg)
        below = (t < 0) & (t > -0.03)
        self.assertTrue(np.all(np.diff(TH[below]) >= -1e-12))          # monotone rounded terminal, no lip
        self.assertTrue(np.all(TH[below] <= r_high[below] + 1e-12))     # the terminal never grows below the seam
        self.assertLess(TH[int(np.argmin(np.abs(t + 0.02)))], 0.005)   # closed within the cap length
        grown = shared_targets(t, r_low, r_high, dict(cfg, highMaxGrow=0.001))[1]
        band = (t >= -0.05) & (t <= 0.06) & ~np.isnan(r_high)
        self.assertTrue(np.all(grown[band] <= r_high[band] + 0.001 + 1e-12))

    def test_cli_two_parts(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            lo, flo = capped_cylinder(radius=0.05, height=0.2, rings=40, segments=36, z0=-0.18)
            hi, fhi = capped_cylinder(radius=0.058, height=0.2, rings=40, segments=36, z0=-0.02)
            write_test_glb(d / 'lo.glb', lo, flo); write_test_glb(d / 'hi.glb', hi, fhi)
            h = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
            cfg = dict(self.cfg(), name='j', origin=[0, 0, 0], axis=[0, 0, 1], tRange=[-0.1, 0.12], samples=40000,
                       low=dict(part='lo', name='lo', master=str(d / 'lo.glb'), sha256=h(d / 'lo.glb'), joint=[0, 0, 0]),
                       high=dict(part='hi', name='hi', master=str(d / 'hi.glb'), sha256=h(d / 'hi.glb'), joint=[0, 0, 0]))
            (d / 'c.json').write_text(json.dumps(cfg))
            r = subprocess.run([sys.executable, '-B', str(HERE / 'fair_target_shared_junction.py'), '--config', str(d / 'c.json'), '--output', str(d / 'o')],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            rec = json.loads((d / 'o' / 'descendant.json').read_text())
            self.assertLess(rec['visibleEnvelopeMaxJumpPerSample']['after'], rec['visibleEnvelopeMaxJumpPerSample']['before'])
            self.assertTrue((d / 'o' / 'lo-local.glb').exists() and (d / 'o' / 'hi-local.glb').exists())
            far = Mesh(d / 'hi.glb').prims[0]['pos'][:, 2] > 0.1
            self.assertTrue(np.allclose(Mesh(d / 'o' / 'hi-local.glb').prims[0]['pos'][far], Mesh(d / 'hi.glb').prims[0]['pos'][far]))


if __name__ == '__main__':
    unittest.main()
