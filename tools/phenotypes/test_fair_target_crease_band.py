import hashlib, json, subprocess, sys, tempfile, unittest
from pathlib import Path
import numpy as np
from fair_target_crease_band import fold_angles, stats, radial_fair, weights
from radial_envelope_field import Cylinder
from test_descendant_mesh_edit import write_test_glb, capped_cylinder
from descendant_mesh_edit import Mesh

HERE = Path(__file__).resolve().parent


def creased():
    pos, faces = capped_cylinder(radius=0.07, height=0.4, rings=80, segments=90, z0=-0.45)
    a = np.degrees(np.arctan2(pos[:, 0], pos[:, 1]))
    groove = (np.abs(((a + 165) + 180) % 360 - 180) < 3) & (pos[:, 2] > -0.42) & (pos[:, 2] < -0.08)
    r = np.hypot(pos[:, 0], pos[:, 1]); scale = np.where(groove & (r > 0.06), 0.93, 1.0)
    pos[:, :2] *= scale[:, None]
    return pos, faces


class CreaseBandTest(unittest.TestCase):
    def test_radial_fair_reduces_folds(self):
        pos, faces = creased()
        cyl = Cylinder([0, 0, 0], [0, 0, 1], pos, -0.5, 0.0, step=0.005)
        cfg = dict(thetaCentre=-165, thetaHalfFull=30, thetaHalfZero=50, sFull=[-0.40, -0.10], sZero=[-0.44, -0.06])
        w = weights(cyl, pos, cfg)
        a0, e = fold_angles(pos, faces); full = (w[e[:, 0]] >= .99) & (w[e[:, 1]] >= .99)
        X = radial_fair(cyl, pos, w, 0.012, 0.005, True)
        a1, _ = fold_angles(X, faces)
        self.assertLess(stats(a1[full])['max'], stats(a0[full])['max'])
        self.assertTrue(np.array_equal(X[w == 0], pos[w == 0]))

    def test_cli(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d); pos, faces = creased()
            write_test_glb(d / 'leg.glb', pos, faces)
            cfg = dict(part='leg', name='c', master=str(d / 'leg.glb'), masterSha256=hashlib.sha256((d / 'leg.glb').read_bytes()).hexdigest(),
                       sRange=[-0.5, 0.0], thetaCentre=-165, thetaHalfFull=30, thetaHalfZero=50, sFull=[-0.40, -0.10], sZero=[-0.44, -0.06],
                       method='radial', radialPasses=2, maxIterations=20, sigmaS=0.012, sigmaArc=0.005, valleyOnly=True)
            (d / 'c.json').write_text(json.dumps(cfg))
            r = subprocess.run([sys.executable, '-B', str(HERE / 'fair_target_crease_band.py'), '--config', str(d / 'c.json'), '--output', str(d / 'o')], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            rec = json.loads((d / 'o' / 'descendant.json').read_text())
            self.assertLess(rec['foldFullBand']['after']['max'], rec['foldFullBand']['before']['max'])


if __name__ == '__main__':
    unittest.main()
