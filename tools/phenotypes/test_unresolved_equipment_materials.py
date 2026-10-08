"""Material closure must not mistake invisible bind meshes or metadata for textures."""
import unittest
from audit_unresolved_equipment_materials import mesh_materials,named_closure

SOURCE='''newmodel pmh0_robe001
beginmodelgeom pmh0_robe001
node trimesh Robe
 parent pmh0_robe001
 bitmap pmh0_robe001
 diffuse 1 1 1
 verts 1
 0 0 0
 tverts 1
 .25 .75 0
endnode
node trimesh pelvis_g
 parent pmh0_robe001
 render 0
 bitmap NULL
 verts 1
 1 0 0
endnode
endmodelgeom pmh0_robe001
'''

class MaterialClosureTests(unittest.TestCase):
    def test_visible_missing_bitmap_does_not_become_intended_untextured_material(self):
        rows=mesh_materials(SOURCE);self.assertEqual(rows[0]['requestedMaterialOrTextureNames'],['pmh0_robe001']);self.assertTrue(rows[0]['renderEnabled'])
        self.assertTrue(rows[0]['renderDefaultApplied']);self.assertFalse(rows[0]['explicitUntexturedDeclaration'])
        self.assertEqual(rows[0]['textureVertices'],1)
        closure=named_closure(rows[0]['requestedMaterialOrTextureNames'][0],set())
        self.assertTrue(closure['declaredImageOrMaterialAbsent']);self.assertFalse(closure['intendedUntexturedMaterialProved']);self.assertFalse(closure['bindingAccepted'])

    def test_hidden_null_bind_mesh_is_separate_from_rendered_material_closure(self):
        hidden=mesh_materials(SOURCE)[1];self.assertFalse(hidden['renderEnabled']);self.assertEqual(hidden['requestedMaterialOrTextureNames'],[])
        self.assertTrue(hidden['explicitUntexturedDeclaration'])

    def test_texture_metadata_alone_does_not_close_image_or_material_dependency(self):
        closure=named_closure('pmh0_shol255',{'pmh0_shol255.txi','pmh0_shol011.plt'})
        self.assertTrue(closure['declaredImageOrMaterialAbsent']);self.assertEqual(closure['presentTextureMetadata'],['pmh0_shol255.txi'])
        self.assertFalse(closure['metadataAloneCanCloseBaseColor']);self.assertFalse(closure['bindingAccepted'])

    def test_named_mtr_is_a_resource_candidate_not_accepted_material(self):
        rows=mesh_materials(SOURCE.replace('bitmap pmh0_robe001','bitmap NULL\n materialname robe_mat'))
        self.assertEqual(rows[0]['requestedMaterialOrTextureNames'],['robe_mat']);self.assertFalse(rows[0]['explicitUntexturedDeclaration'])
        closure=named_closure('robe_mat',{'robe_mat.mtr'})
        self.assertFalse(closure['declaredImageOrMaterialAbsent']);self.assertFalse(closure['bindingAccepted'])

if __name__=='__main__':unittest.main()
