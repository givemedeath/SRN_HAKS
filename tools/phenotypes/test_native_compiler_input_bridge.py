import unittest,tempfile
from pathlib import Path
import numpy as np
from native_compiler_input_bridge import validate_arrays
from target_part_stage import validate_material_slots,material_resref,write_model
class NativeCompilerBridgeTests(unittest.TestCase):
 def arrays(self):
  return {'positions':np.array([[[0.,0.,0.],[1.00000001449,0.,0.],[0.,1.,0.]]]),'normals':np.tile([0.,0.,1.],(1,3,1)),'uvNative':np.array([[[0.,0.],[1.,0.],[0.,1.]]])}
 def test_native_precision_ascii_roundtrip(self):
  a=self.arrays();self.assertNotEqual(a['positions'][0,1,0],float(np.float32(a['positions'][0,1,0])))
  with tempfile.TemporaryDirectory()as d:
   proof=write_model(Path(d)/'x.mdl','pfh0_handl001',a['positions'],a['normals'],a['uvNative'],['skin']);self.assertEqual(proof['skin']['actualAsciiCornerMaximumErrors'],{'position':0.,'normal':0.,'uv':0.})
 def test_preview_f32_rejected(self):
  a=self.arrays();a['positions']=a['positions'].astype('f4')
  with self.assertRaises(ValueError):validate_arrays(a,np.array([0]))
 def test_face_order_extent_rejected(self):
  with self.assertRaises(ValueError):validate_arrays(self.arrays(),np.array([0,1]))
 def test_nonfinite_native_rejected(self):
  a=self.arrays();a['positions'][0,0,0]=np.nan
  with self.assertRaises(ValueError):validate_arrays(a,np.array([0]))
 def test_negative_material_rejected(self):
  with self.assertRaises(ValueError):validate_arrays(self.arrays(),np.array([-1]))
 def test_typed_multiskin_slots(self):
  slots=validate_material_slots({'0':{'role':'skin','atlasKey':'skin'},'2':{'role':'skin','atlasKey':'skin1'},'4':{'role':'garment','atlasKey':'garment'}});self.assertEqual(len(slots),3);self.assertEqual(material_resref('pfh0_pelvis001','skin1','skin'),'pfh0_pelviss1')
 def test_garment_cannot_claim_skin_atlas(self):
  with self.assertRaises(ValueError):validate_material_slots({'0':{'role':'garment','atlasKey':'skin1'}})
 def test_resref_limit(self):
  with self.assertRaises(ValueError):material_resref('this_model_name_is_far_too_long','skin1','skin')
if __name__=='__main__':unittest.main()
