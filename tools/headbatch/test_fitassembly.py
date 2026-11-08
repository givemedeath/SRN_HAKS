import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from headbatch.review.fitassembly import body_surface
from headkit.body_neck import KIND

SKELETON="""node dummy torso_g
 parent NULL
 position 0 0 1
endnode
node dummy neck_g
 parent torso_g
 position 0 .02 .3
endnode
node dummy head_g
 parent neck_g
 position 0 .01 .1
endnode
endmodelgeom pfe0
newanim bad pfe0
node dummy head_g
 parent NULL
 position 9 9 9
endnode
"""

class BodyAssemblyTests(unittest.TestCase):
    def fixture(self):
        return {'kind':KIND,'neckToHead':[[1,0,0,0],[0,1,0,-.01],[0,0,1,-.1],[0,0,0,1]],
                'vertices':[[0,0,-.1],[1,0,-.1],[0,1,-.1]],'faces':[[0,1,2]]}
    def test_torso_uses_head_frame_and_excludes_animation_nodes(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'pfe0_chest001.mdl';p.write_bytes(b'fixture')
            parts=[{'position':np.array([[0,0,0],[1,0,0],[0,1,0]]),'faces':np.array([[0,1,2]])}]
            with patch('headbatch.review.fitassembly.decode',return_value=parts) as decoder:
                v,f,m=body_surface(p,SKELETON,self.fixture())
            np.testing.assert_allclose(v[:3],parts[0]['position']+[0,-.03,-.4],atol=1e-12)
            np.testing.assert_array_equal(v[3:],self.fixture()['vertices'])
            np.testing.assert_array_equal(f,[[0,1,2],[3,4,5]])
            self.assertTrue(decoder.call_args.kwargs['apply_rigid_transforms'])
    def test_mismatched_attachment_frame_is_refused(self):
        neck=self.fixture();neck['neckToHead'][2][3]=-.2
        with self.assertRaisesRegex(ValueError,'frames disagree'):
            body_surface('pfe0_chest001.mdl',SKELETON,neck)
    def test_native_model_basename_required(self):
        with self.assertRaisesRegex(ValueError,'native model basename'):
            body_surface('body-torso.mdl',SKELETON,self.fixture())

if __name__=='__main__':unittest.main()
