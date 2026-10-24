"""Source atlas repair preserves geometry and healthy UVs without losing gates."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from tools.headkit.common import read
from tools.itemkit.source_atlas import repair_uv,unwrap


class SourceAtlasTests(unittest.TestCase):
    def fixture(self):
        p=[];f=[];uv=[]
        for k in range(100):
            p.extend(((k,0,0),(k+1,0,0),(k,1,0)));f.append((k*3,k*3+1,k*3+2))
            x=(k%10)*.1+.005;y=(k//10)*.1+.005
            uv.append(((x,y),(x+.09,y),(x,y+.09)))
        return np.array(p,float),np.array(f,int),np.array(uv,float)

    def test_only_bounded_defects_move_and_all_4k_gates_pass(self):
        p,f,uv=self.fixture();uv[-1]=uv[0];before=[a.copy() for a in (p,f,uv)]
        result,proof,report=repair_uv(p,f,uv)
        for a,b in zip((p,f,uv),before):np.testing.assert_array_equal(a,b)
        self.assertEqual(report['isolatedFaces'],[0,99]);self.assertEqual(report['isolatedAreaFraction'],.02)
        np.testing.assert_array_equal(result[1:99],proof['originalUV'][1:99])
        self.assertEqual(report['audit']['overlapFaces'],[])
        self.assertEqual(report['audit']['degenerateUvFaces'],[])
        self.assertEqual(report['unmappedCharts'],[])
        self.assertLess(report['unmappedSurfaceFraction'],.001)
        self.assertEqual(report['gutters']['nearbyChartPixelsByRadius']['2'],0)
        self.assertEqual(len(set(proof['finalRegions'][[0,99]])),2)

    def test_excessive_repair_nonfinite_or_wrong_resolution_stops(self):
        p,f,uv=self.fixture();uv[-2:]=uv[0]
        with self.assertRaisesRegex(ValueError,'bounded local'):repair_uv(p,f,uv)
        for bad in (np.full_like(uv,np.nan),uv*2):
            with self.assertRaisesRegex(ValueError,'Finite source UV'):repair_uv(p,f,bad)
        with self.assertRaisesRegex(ValueError,'4K donor'):repair_uv(p,f,uv,size=1024)

    def test_large_surface_patch_cannot_hide_behind_small_face_count(self):
        p,f,uv=self.fixture();uv[-1]=uv[0];p[f[0]]*=100
        with self.assertRaisesRegex(ValueError,'face/area scope'):repair_uv(p,f,uv)

    def test_coverage_failure_retains_actual_measurement_without_weakening_gate(self):
        p,f,uv=self.fixture()
        with tempfile.TemporaryDirectory() as tmp:
            report=Path(tmp)/'repair.json'
            with self.assertRaisesRegex(ValueError,'source UV coverage'):
                repair_uv(p,f,uv*.4,diagnostic_path=report)
            self.assertLess(read(report)['audit']['coverageFraction'],.30)
            self.assertEqual(read(report)['audit']['overlapFaces'],[])

    def test_unwrap_retains_failed_candidate_and_error_for_resume(self):
        p,f,uv=self.fixture();mesh={'positions':p,'faces':f,'uv':uv}
        class Atlas:width=2048;height=2048
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'atlas'
            with patch('tools.itemkit.source_atlas.physical_fans',return_value=(p,f)),\
                 patch('tools.itemkit.source_atlas.library'),\
                 patch('tools.itemkit.source_atlas._pack',return_value=(uv,Atlas(),100)),\
                 patch('tools.itemkit.source_atlas.repair_uv',side_effect=ValueError('bounded stop')):
                with self.assertRaisesRegex(ValueError,'bounded stop'):unwrap(mesh,{},out)
            self.assertTrue((out/'candidate-padding-4.npz').exists())
            report=read(out/'attempts.json')['attempts'][0]
            self.assertEqual(report['state'],'failed');self.assertEqual(report['error'],'bounded stop')
            self.assertFalse((out/'atlas.json').exists())

    def test_gutter_failure_requires_new_pack_and_never_accepts(self):
        p,f,uv=self.fixture();mesh={'positions':p,'faces':f,'uv':uv}
        class Atlas:width=2048;height=2048
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'atlas'
            report={'gutters':{'nearbyChartPixelsByRadius':{'2':1}}}
            with patch('tools.itemkit.source_atlas.physical_fans',return_value=(p,f)),\
                 patch('tools.itemkit.source_atlas.library'),\
                 patch('tools.itemkit.source_atlas._pack',return_value=(uv,Atlas(),100)) as pack,\
                 patch('tools.itemkit.source_atlas.repair_uv',return_value=(uv,{},report)):
                with self.assertRaisesRegex(ValueError,'two-pixel 4K gutter'):unwrap(mesh,{},out)
            self.assertEqual([c.kwargs['padding'] for c in pack.call_args_list],[4,8,16])
            self.assertEqual(len(read(out/'attempts.json')['attempts']),3)
            self.assertFalse((out/'atlas.json').exists())


if __name__=='__main__':unittest.main()
