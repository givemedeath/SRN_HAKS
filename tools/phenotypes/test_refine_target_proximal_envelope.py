import hashlib, json, subprocess, sys, tempfile, unittest
from pathlib import Path
import numpy as np
from refine_target_proximal_envelope import cap_map, target_field
from test_descendant_mesh_edit import write_test_glb, capped_cylinder
from descendant_mesh_edit import Mesh

HERE = Path(__file__).resolve().parent


class ProximalEnvelopeTest(unittest.TestCase):
    def test_cap_map_monotone_and_hits_target(self):
        s = np.linspace(-0.1, 0.083, 200)
        m, k = cap_map(s, 0.0, 0.03, 0.083, 0.067)
        self.assertTrue(np.all(np.diff(m) > 0))
        self.assertAlmostEqual(float(m[-1]), 0.067, places=6)
        self.assertTrue(np.array_equal(m[s <= 0], s[s <= 0]))

    def test_target_field_reduces_dome_and_fills_pinch(self):
        s = np.round(np.arange(-0.2, 0.09, 0.005), 4)
        r = np.full((len(s), 4), 0.06); r[np.abs(s) < 0.02] = 0.072; r[np.abs(s + 0.05) < 0.015] = 0.055
        cfg = dict(reduction=0.1, plateau=[-0.01, 0.03], falloff=[-0.12, 0.083], fill=dict(peak=0.0, belly=-0.09))
        t = target_field(r, s, cfg)
        i0 = int(np.argmin(np.abs(s))); ip = int(np.argmin(np.abs(s + 0.05)))
        self.assertAlmostEqual(t[i0, 0], 0.072 * 0.9, places=6)
        self.assertGreater(t[ip, 0], 0.058)

    def test_cli_descendant(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            pos, faces = capped_cylinder(radius=0.06, height=0.43, rings=43, segments=36, z0=-0.35)
            write_test_glb(d / 'arm.glb', pos, faces, tangent=True)
            cfg = dict(part='test', name='t', master=str(d / 'arm.glb'), masterSha256=hashlib.sha256((d / 'arm.glb').read_bytes()).hexdigest(),
                       sRange=[-0.36, 0.1], reduction=0.1, plateau=[-0.01, 0.03], falloff=[-0.12, 0.07], fill=dict(peak=0.0, belly=-0.09),
                       capTop=0.07, capStart=0.0, capRamp=0.03)
            (d / 'c.json').write_text(json.dumps(cfg))
            subprocess.run([sys.executable, '-B', str(HERE / 'refine_target_proximal_envelope.py'), '--config', str(d / 'c.json'), '--output', str(d / 'out')], check=True, capture_output=True)
            out = Mesh(d / 'out' / 't-local.glb')
            self.assertAlmostEqual(float(out.U[:, 2].max()), 0.07, places=5)
            self.assertTrue(np.array_equal(out.prims[0]['uv'], Mesh(d / 'arm.glb').prims[0]['uv']))


if __name__ == '__main__':
    unittest.main()
