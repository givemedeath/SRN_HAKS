"""Atlas-only omissions are bounded in fitted metres; runtime faces remain intact."""
from pathlib import Path
import tempfile
import unittest
import numpy as np
from head_workflow import pin,write_fresh
from verify_texture_transfer import cap_only_omissions
from correct_neck_rim import write_glb
from head_export import triangles


class AtlasAllowanceTests(unittest.TestCase):
    def test_fitted_cap_allowance_rejects_large_or_mismatched_omissions(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'head.glb';source.write_bytes(b'fixed source')
            fit=root/'fit.json';closure=root/'closure.json'
            write_fresh(fit,{'source':pin(source),'uniformScale':.1,'localMatrix':np.diag([.1,.1,.1,1]).tolist()})
            write_fresh(closure,{'source':pin(source),'output':pin(source),'kind':'srn-head-cap-only-closure',
                'passed':True,'originalSurfacePreserved':True,'trimApplied':False,'taperApplied':False,'holes':[{'faces':[10,11]}]})
            before=source.read_bytes()
            result=cap_only_omissions([2,10],[1e-5,1e-4],source,fit,closure)
            self.assertTrue(result['allSourceFacesRetained']);self.assertEqual(result['omittedCapFaceIds'],[10])
            self.assertEqual(source.read_bytes(),before)
            for missing,areas in [([2],[.01]),([10],[.1]),(list(range(9)),[1e-8]*9)]:
                with self.subTest(missing=missing),self.assertRaisesRegex(ValueError,'bounded'):
                    cap_only_omissions(missing,areas,source,fit,closure)
            review=root/'review.json'
            write_fresh(review,{'kind':'srn-head-atlas-omission-review','passed':True,'source':pin(source),'fit':pin(fit),'closure':pin(closure),'evidence':[],'omittedOriginalFaceIds':list(range(9))})
            approved=cap_only_omissions(list(range(9)),[1e-8]*9,source,fit,closure,review)
            self.assertEqual(approved['review'],pin(review));self.assertTrue(approved['allSourceFacesRetained'])
            with self.assertRaisesRegex(ValueError,'IDs differ'):cap_only_omissions(list(range(8)),[1e-8]*8,source,fit,closure,review)
            with self.assertRaisesRegex(ValueError,'bounded'):cap_only_omissions(list(range(9)),[.01]*9,source,fit,closure,review)
            other=root/'other.glb';other.write_bytes(b'other')
            with self.assertRaisesRegex(ValueError,'matching'):cap_only_omissions([],[],other,fit,closure)

    def test_runtime_budget_counts_all_faces_at_20k_boundary(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'head.glb'
            for count in (20000,20001):
                p=np.tile([[0,0,0],[1,0,0],[0,1,0]],(count,1,1))
                n=np.tile([0,0,1],(count,3,1));uv=np.tile([[.2,.2],[.4,.2],[.2,.4]],(count,1,1))
                write_glb(path,p,n,uv)
                if count==20000:self.assertEqual(len(triangles(path,np.eye(4))[0]),count)
                else:
                    with self.assertRaisesRegex(ValueError,'budget'):triangles(path,np.eye(4))


if __name__=='__main__':unittest.main()
