"""Authored cloth must keep source ownership explicit and native PLT fields valid."""
import struct
import unittest
from author_target_robe_cloth import authored_cloth_plt,separate_source_cloth,HIDDEN

def fixture():
    text='newmodel pmh0_robe001\nbeginmodelgeom pmh0_robe001\nnode dummy pmh0_robe001\n parent NULL\nendnode\nnode trimesh Robe\n parent pmh0_robe001\n bitmap pmh0_robe001\n verts 1\n 0 0 0\nendnode\n'
    for name in sorted(HIDDEN):text+=f'node trimesh {name}\n parent pmh0_robe001\n render 0\n bitmap NULL\n verts 1\n 1 0 0\nendnode\n'
    return text+'endmodelgeom pmh0_robe001\n'

class AuthoredClothTests(unittest.TestCase):
    def test_new_uniform_cloth_pixels_preserve_native_header_only(self):
        template=b'PLT V1  '+struct.pack('<IIII',4,7,2,2)+bytes([0,2,254,3,55,0,255,9])
        blob,metadata=authored_cloth_plt(template)
        self.assertEqual(blob[:24],template[:24]);self.assertEqual(metadata['unusedHeaderDwords'],[4,7]);self.assertEqual(blob[24:],bytes([128,4])*4)
        self.assertEqual(metadata['materialChannelPixelCounts'],{'4':4});self.assertNotEqual(blob[24:],template[24:])

    def test_visible_cloth_and_all_thirteen_hidden_bind_meshes_are_explicit(self):
        visible,block,hidden,frame=separate_source_cloth(fixture());self.assertEqual(visible['node'],'Robe');self.assertEqual(len(hidden),13)
        self.assertTrue(all(row['render']=='0' and row['bitmap']=='NULL' for row in hidden))

    def test_rendered_bind_or_hidden_named_texture_rejects_source_ownership(self):
        for text in (fixture().replace('render 0','render 1',1),fixture().replace('bitmap NULL','bitmap pmh0_pelvis001',1)):
            with self.assertRaises(ValueError):separate_source_cloth(text)

    def test_additional_visible_material_or_missing_bind_rejects_source_ownership(self):
        with self.assertRaisesRegex(ValueError,'material/skin'):separate_source_cloth(fixture().replace('bitmap pmh0_robe001','bitmap pmh0_robe001\n materialname guessed_mat'))
        with self.assertRaisesRegex(ValueError,'thirteen'):separate_source_cloth(fixture().replace('node trimesh rootdummy','node dummy rootdummy').replace('rootdummy\n parent pmh0_robe001\n render 0\n bitmap NULL\n verts 1\n 1 0 0','rootdummy\n parent pmh0_robe001'))

if __name__=='__main__':unittest.main()
