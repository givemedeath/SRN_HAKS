import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from tools.itemkit.firearm_native import placeholder_geometry
from tools.itemkit.skinned_native import audit,model_text,decode_meshes


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

    def test_audit_reports_the_sanitized_tail_byte_count(self):
        p=np.array([[0,0,0],[1,0,0],[0,1,0],[0,0,1]],float);f=np.array([[0,2,1],[0,1,3],[1,2,3],[2,0,3]])
        base={'positions':p,'normals':p,'uv':p[:,:2],'faces':f}
        rows={'kv':{**base,'flags':{'render':1,'shadow':0},'textures':['tex']},
              'ks':{**base,'flags':{'render':0,'shadow':1},'textures':['null']}}
        expected={'positions':p[f],'normals':p[f],'uv':p[f][...,:2],'shadowVertices':p,'shadowFaces':f,
                  'weights':np.tile([1.,0.],(4,3,1)),'shadowWeights':np.tile([1.,0.],(4,1))}
        def node(label):
            lines=[f'node skin {label}','verts 4',*[' '.join(map(str,row)) for row in p],
                   'faces 4',*[' '.join(map(str,row)) for row in f],'weights 4',*['body 1']*4,'endnode']
            return '\n'.join(lines)+'\n'
        with tempfile.TemporaryDirectory() as folder:
            binary=Path(folder)/'k.mdl';binary.write_bytes(b'raw');decompiled=Path(folder)/'k.txt'
            decompiled.write_text(node('kv')+node('ks'),encoding='cp1252')
            with patch('tools.itemkit.native.sanitize_proof',return_value=(b'clean',3)), \
                 patch('tools.itemkit.skinned_native.decode_meshes',return_value=rows):
                clean,report=audit(binary,'k','tex',expected,decompiled,['body','limb'])
        self.assertEqual((clean,report['zeroedTailBytes']),(b'clean',3))

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
