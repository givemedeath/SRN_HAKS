import unittest
import numpy as np
from tools.itemkit.firearm_native import placeholder_geometry
from tools.itemkit.skinned_native import model_text,decode_meshes


class SkinnedNativeTests(unittest.TestCase):
    def geometry(self):
        base=placeholder_geometry()
        return {**base,'shadowVertices':base['positions'].reshape(-1,3),
                'shadowFaces':np.arange(12).reshape(-1,3),
                'weights':np.tile([.7,.3],(4,3,1)),
                'shadowWeights':np.tile([1.,0.],(12,1))}

    def rig(self):
        return ('newmodel original\nsetsupermodel original NULL\nclassification ITEM\n'
                'setanimationscale 1\nbeginmodelgeom original\nnode dummy original\n parent NULL\nendnode\n'
                'node dummy body_bind\n parent original\nendnode\nnode dummy limb_l\n parent original\n position .1 0 0\nendnode\n'
                'node skin originalv\n parent original\nendnode\nendmodelgeom original\n'
                'newanim xbowshot original\n length 1\n transtime .25\n animroot original\n'
                ' node dummy limb_l\n  parent original\n  orientationkey 2\n   0 0 1 0 0\n   1 0 1 0 .1\n endnode\n'
                'doneanim xbowshot original\ndonemodel original\n')

    def test_rename_leaves_bones_and_clips_containing_the_rig_name(self):
        rig=self.rig().replace('original','xbow').replace('body_bind','xbow_bind')
        text=model_text('wbwxh_t_016','sr_test',self.geometry(),rig,['xbow_bind','limb_l'])
        self.assertIn('node dummy xbow_bind',text);self.assertIn('newanim xbowshot wbwxh_t_016',text)

    def test_preserves_qualified_clip_and_bone_bind_position(self):
        rig=self.rig();text=model_text('wbwxh_t_016','sr_test',self.geometry(),rig,['body_bind','limb_l'])
        self.assertIn(rig[rig.index('endmodelgeom '):].replace('original','wbwxh_t_016'),text)
        self.assertIn('position .1 0 0',text)
        self.assertEqual(text.count('node skin '),2)
        self.assertIn('bitmap sr_test',text)
        self.assertIn('render 0\n  shadow 1',text)

    def test_rejects_non_normalized_weights(self):
        data=self.geometry();data['weights'][0,0]=[.7,.4]
        with self.assertRaisesRegex(ValueError,'skin weights'):model_text('wbwxh_t_016','sr_test',data,self.rig(),['body_bind','limb_l'])

    def test_rejects_missing_qualified_bone(self):
        with self.assertRaisesRegex(ValueError,'bind tree'):model_text('wbwxh_t_016','sr_test',self.geometry(),self.rig(),['body_bind','wrong_bone'])

    def test_rejects_unsafe_uv_before_native_export(self):
        data=self.geometry();data['uv'][0,0,0]=1.1
        with self.assertRaisesRegex(ValueError,'UVs'):model_text('wbwxh_t_016','sr_test',data,self.rig(),['body_bind','limb_l'])

    def test_rejects_truncated_binary(self):
        with self.assertRaisesRegex(ValueError,'Truncated'):decode_meshes(bytes(20))


if __name__=='__main__':unittest.main()
