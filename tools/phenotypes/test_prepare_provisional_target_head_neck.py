"""Provisional stock head/neck ownership, scaling and corner-lineage guards."""
import copy
import unittest
import numpy as np

from build_target_diagnostic import convert_part
from prepare_provisional_target_head_neck import owned_plt_stage, corner_correspondence, copy_shading

SOURCE = '''newmodel pmh0_head001
setsupermodel pmh0_head001 NULL
classification CHARACTER
setanimationscale 1
beginmodelgeom pmh0_head001
node dummy pmh0_head001
 parent NULL
 position 0 0 0
endnode
node trimesh pmh0_head001g
 parent pmh0_head001
 bitmap pmh0_head001
 specular 0 0 0
 shininess 1
 verts 3
  1 0 0
  0 1 0
  0 0 1
 tverts 3
  0 0 0
  1 0 0
  0 1 0
 faces 1
  0 1 2 1 0 1 2 1
 position 0.02 0.03 0.04
 orientation 0 0 0 0
endnode
endmodelgeom pmh0_head001
donemodel pmh0_head001
'''


class ProvisionalHeadNeckTests(unittest.TestCase):
    def test_only_bitmap_ownership_changes_after_exact_diagnostic_placement(self):
        for factor in (1.0, 10/7):
            diagnostic = convert_part(SOURCE, 'pmh0_head001', 'pmg0_head001', factor)
            staged = owned_plt_stage(SOURCE, diagnostic, 'pmh0_head001', 'pmg0_head001', factor)
            self.assertEqual(staged.replace('bitmap pmg0_head001', 'bitmap pmh0_head001'), diagnostic)
            self.assertIn('specular 0 0 0', staged); self.assertIn('shininess 1', staged)
            self.assertIn('orientation 0 0 0 0', staged)
            self.assertIn('  0 1 2 1 0 1 2 1', staged)

    def test_reject_wrong_part_human_female_or_global_ownership(self):
        diagnostic = convert_part(SOURCE, 'pmh0_head001', 'pmg0_head001', 1.0)
        for source, target in [('pfh0_head001', 'pmg0_head001'), ('pmh0_head001', 'pmh0_head001'),
                               ('pmh0_head001', 'pmg0_neck001'), ('pmh0_chest002', 'pmg0_chest002'),
                               ('helm_001', 'pmg0_head001')]:
            with self.subTest(source=source, target=target), self.assertRaisesRegex(ValueError, 'ownership'):
                owned_plt_stage(SOURCE, diagnostic, source, target, 1.0)

    def test_reject_double_scale_or_changed_geometry(self):
        runtime = convert_part(SOURCE, 'pmh0_head001', 'pmg0_head001', 10/7)
        double = convert_part(runtime, 'pmg0_head001', 'pmg0_head001', 10/7)
        for diagnostic in (double, runtime.replace('shininess 1', 'shininess 26'), runtime.replace('0.0285714285714', '0.5')):
            if diagnostic == runtime: continue
            with self.assertRaisesRegex(ValueError, 'exact stock placement'):
                owned_plt_stage(SOURCE, diagnostic, 'pmh0_head001', 'pmg0_head001', 10/7)
        with self.assertRaisesRegex(ValueError, 'single runtime'):
            owned_plt_stage(SOURCE, runtime, 'pmh0_head001', 'pmg0_head001', (10/7)**2)

    def test_reject_unproved_or_multiple_material_bindings(self):
        for modified in (SOURCE.replace('bitmap pmh0_head001', 'bitmap invented_texture'),
                         SOURCE.replace('bitmap pmh0_head001', 'bitmap pmh0_head001\n materialname invented')):
            diagnostic = convert_part(modified, 'pmh0_head001', 'pmg0_head001', 1.0)
            with self.assertRaisesRegex(ValueError, 'one stock part PLT binding'):
                owned_plt_stage(modified, diagnostic, 'pmh0_head001', 'pmg0_head001', 1.0)

    def correspondence(self):
        positions = np.array([[0., 0, 0], [1., 0, 0], [0., 1, 0]])
        uv = np.array([[0., 0], [1., 0], [0., 1]])
        ascii_faces = np.array([[0, 1, 2, 1, 0, 1, 2, 1], [0, 2, 1, 1, 0, 2, 1, 1]])
        native_faces = np.array([[0, 1, 2], [3, 4, 5]])
        return native_faces, ascii_faces, positions[[0,1,2,0,2,1]], positions, uv[[0,1,2,0,2,1]], uv

    def test_native_seam_duplicates_have_unique_original_face_position_and_uv_owners(self):
        values = self.correspondence(); result = corner_correspondence(*values)
        self.assertEqual(result['positionIds'], [0,1,2,0,2,1])
        self.assertEqual(result['uvIds'], [0,1,2,0,2,1])
        self.assertTrue(result['orderedFaceCornersProved'])
        self.assertEqual(result['positionMaximumLegacyDifferenceMeters'], 0)
        before = [x.copy() for x in values]; corner_correspondence(*values)
        for original, actual in zip(before, values): self.assertTrue(np.array_equal(original, actual))

    def test_unassigned_native_vertex_and_changed_uv_or_face_coverage_rejected(self):
        values = list(self.correspondence())
        unused = copy.deepcopy(values); unused[2] = np.vstack([unused[2], [0,0,0]]); unused[4] = np.vstack([unused[4], [0,0]])
        changed_uv = copy.deepcopy(values); changed_uv[4][0] = [.5,.5]
        missing_face = copy.deepcopy(values); missing_face[0] = missing_face[0][:1]
        for invalid in (unused, changed_uv, missing_face):
            with self.assertRaises(ValueError): corner_correspondence(*invalid)

    def test_ambiguous_native_owner_rejected_even_for_coincident_source_values(self):
        values = list(self.correspondence()); values[3] = np.vstack([values[3], values[3][0]])
        values[1][1,0] = 3; values[0][1,0] = 0
        with self.assertRaisesRegex(ValueError, 'ambiguous'):
            corner_correspondence(*values)

    def test_material_copy_preserves_header_fields_without_mutating_source(self):
        source = {'textures': ['pmh0_head001', '', '', ''], 'shininess': 1., 'render': 1, 'ambient': [1.,1.,1.]}
        before = copy.deepcopy(source); new = copy_shading(source, 'pmg0_head001')
        self.assertEqual(source, before); self.assertEqual(new['textures'][0], 'pmg0_head001')
        self.assertEqual(new['textures'][1:], source['textures'][1:]); self.assertEqual(new['ambient'], source['ambient'])


if __name__ == '__main__': unittest.main()
