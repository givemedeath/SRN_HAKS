import copy,unittest
from derive_reference_color_bounded_fallback import associations
class Tests(unittest.TestCase):
 def fixture(self):
  p={'kind':'literal-reference-rgb-region-descendant-receipt','diagnosticOnly':True,'selected':False,'targetId':'test-fit-v1','part':'chest','targetContractSha256':'target','source':{'sha256':'source'}};c={'kind':'read-only-approved-cut-face-uv-contour-proposal','selected':False,'targetId':'test-fit-v1','source':{'sha256':'source'},'sourceArrayPin':{'sha256':'arrays'}};a={'targetId':'test-fit-v1','part':'chest','targetContractSha256':'target','source':{'sha256':'source'},'sourceCornerArrays':{'sha256':'arrays'}};return p,c,a
 def test_cross_target_stale_geometry_contract_rejected(self):
  for mutate in (lambda p,c,a:c.__setitem__('targetId','other'),lambda p,c,a:a.__setitem__('part','pelvis'),lambda p,c,a:p.__setitem__('targetContractSha256','stale'),lambda p,c,a:c['source'].__setitem__('sha256','different'),lambda p,c,a:c['sourceArrayPin'].__setitem__('sha256','different')):
   p,c,a=self.fixture();mutate(p,c,a)
   with self.assertRaises(ValueError):associations(p,c,a,'target','test-fit-v1','chest')
 def test_diagnostic_unselected_required(self):
  p,c,a=self.fixture();associations(p,c,a,'target','test-fit-v1','chest');p['selected']=True
  with self.assertRaises(ValueError):associations(p,c,a,'target','test-fit-v1','chest')
if __name__=='__main__':unittest.main()
