"""Analytical equipment invariants, independent of the helper's SRT math."""
from pathlib import Path
import tempfile
import unittest
import numpy as np
from armory_rigid import correct_rigid, profile_affine, rigid_frames
from audit_geometry import arrays
from inventory_target_equipment import select_models, inspect_model


SOURCE = '''newmodel pmh0_chest002
setsupermodel pmh0_chest002 NULL
beginmodelgeom pmh0_chest002
node dummy pmh0_chest002
 parent NULL
 position 0 0 0
endnode
node dummy pivot
 parent pmh0_chest002
 position .2 .3 .4
 orientation 0 0 1 1.5707963267948966
endnode
node trimesh torso_g
 parent pivot
 position .1 .2 .3
 orientation 0 1 0 1.5707963267948966
 bitmap pmh0_chest002
 materialname skin
 verts 4
 1 0 0
 0 1 0
 0 0 1
 0 0 0
 normals 4
 .7071067811865475 .7071067811865475 0
 .7071067811865475 .7071067811865475 0
 .7071067811865475 .7071067811865475 0
 .7071067811865475 .7071067811865475 0
 tangents 4
 0 0 1 1
 0 0 1 1
 0 0 1 1
 0 0 1 1
 tverts 4
 0 0 0
 1 0 0
 0 1 0
 1 1 0
 faces 1
 0 1 2 1 0 1 2 0
endnode
endmodelgeom pmh0_chest002
'''

# Literal pinned Armory output for S=(2,3,4), Rz=90, T=(.5,-.6,.7).
RAW = SOURCE.replace('pmh0_chest002', 'pmg0_chest002').replace('position 0 0 0', 'position .5 -.6 .7').replace('position .2 .3 .4', 'position -.4 -.2 2.3').replace('position .1 .2 .3', 'position -.1 -.4 1.9')
RAW = RAW.replace('verts 4\n 1 0 0\n 0 1 0\n 0 0 1\n 0 0 0', 'verts 4\n .5 1.4 .7\n -2.5 -.6 .7\n .5 -.6 4.7\n .5 -.6 .7')
RAW = RAW.replace('.7071067811865475 .7071067811865475 0', '-.5547001962252291 .8320502943378437 0')
RAW = RAW.replace('bitmap pmg0_chest002', 'bitmap pmh0_chest002')
PROFILE = {'scale': [2, 3, 4], 'rotate': [0, 0, 90], 'translate': [.5, -.6, .7]}


class ArmoryRigidTests(unittest.TestCase):
    def run_conversion(self, source=SOURCE, raw=RAW, transform=PROFILE):
        with tempfile.TemporaryDirectory() as directory:
            a, b = Path(directory) / 'source.mdl', Path(directory) / 'target.mdl'
            a.write_text(source); b.write_text(raw)
            proof = correct_rigid(a, b, transform)
            return b.read_text(), proof

    def test_frozen_source_cannot_be_its_own_correction_target(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'source.mdl';path.write_text(SOURCE)
            before=path.read_bytes()
            with self.assertRaisesRegex(RuntimeError,'frozen source'):
                correct_rigid(path,path,PROFILE)
            self.assertEqual(path.read_bytes(),before)

    def test_nested_world_placement_has_one_translation(self):
        text, proof = self.run_conversion()
        _, blocks, frames = rigid_frames(text)
        vertices = np.asarray(arrays(blocks['torso_g'][3], 'verts'))
        expected = [[-.7, -.6, -.5], [-.7, -2.6, 3.5], [-3.7, -.6, 3.5], [-.7, -.6, 3.5]]
        np.testing.assert_allclose(vertices, expected, atol=1e-9)
        np.testing.assert_allclose(frames['torso_g'], np.eye(4), atol=1e-12)
        self.assertLess(proof['maximumWorldTransformError'], 1e-9)
        self.assertTrue(proof['parentHierarchyFlattened'])
        self.assertFalse(proof['clientAccepted'])

    def test_normals_follow_surface_and_tangent_has_correct_transport(self):
        text, proof = self.run_conversion()
        _, blocks, _ = rigid_frames(text)
        normal = np.asarray(arrays(blocks['torso_g'][3], 'normals'))
        tangent = np.asarray(arrays(blocks['torso_g'][3], 'tangents'))
        np.testing.assert_allclose(normal, np.tile([0, -2 / np.sqrt(5), -1 / np.sqrt(5)], (4, 1)), atol=1e-9)
        np.testing.assert_allclose(tangent, np.tile([-1, 0, 0, 1], (4, 1)), atol=1e-9)
        np.testing.assert_allclose(np.sum(normal * tangent[:, :3], axis=1), 0, atol=1e-9)
        self.assertLess(proof['maximumWorldNormalError'], 1e-9)

    def test_uvs_faces_bitmap_material_and_mesh_name_survive(self):
        text, _ = self.run_conversion()
        _, before, _ = rigid_frames(SOURCE)
        _, after, _ = rigid_frames(text)
        for field in ('tverts', 'faces'):
            self.assertEqual(arrays(before['torso_g'][3], field), arrays(after['torso_g'][3], field))
        self.assertIn('bitmap pmh0_chest002', text)
        self.assertIn('materialname skin', text)
        self.assertEqual(after['torso_g'][2], 'torso_g')

    def test_identity_preserves_source_world_geometry(self):
        raw = SOURCE.replace('pmh0_chest002', 'pmg0_chest002').replace('bitmap pmg0_chest002', 'bitmap pmh0_chest002')
        text, _ = self.run_conversion(raw=raw, transform={'scale': [1, 1, 1], 'translate': [0, 0, 0]})
        _, blocks, _ = rigid_frames(text)
        np.testing.assert_allclose(arrays(blocks['torso_g'][3], 'verts'), [[0, .4, -.3], [-1, .4, .7], [0, 1.4, .7], [0, .4, .7]], atol=1e-9)

    def test_rejects_wrong_raw_output_or_changed_uv_binding(self):
        for old, new in [('.5 1.4 .7', '.5 1.5 .7'), ('1 1 0', '.9 1 0'),
                         ('bitmap pmh0_chest002', 'bitmap other'),
                         ('-.5547001962252291 .8320502943378437 0', '1 0 0')]:
            with self.subTest(new=new), self.assertRaises(RuntimeError):
                self.run_conversion(raw=RAW.replace(old, new))

    def test_rejects_skin_animations_unresolved_parent_and_cycles(self):
        cases = [SOURCE.replace('node trimesh', 'node skin'), SOURCE + '\nnewanim pause model\n',
                 SOURCE.replace('parent pivot', 'parent absent'), SOURCE.replace('parent pmh0_chest002', 'parent torso_g')]
        for source in cases:
            with self.subTest(source=source[-60:]), self.assertRaises(RuntimeError):
                self.run_conversion(source=source)

    def test_rejects_invalid_scales_or_selective_transform(self):
        for profile in [{**PROFILE, 'scale': [0, 1, 1]}, {**PROFILE, 'scale': [-1, 1, 1]},
                        {**PROFILE, 'rotate': [float('nan'), 0, 0]}, {**PROFILE, 'minimum': [0, 0, 0]}]:
            with self.subTest(profile=profile), self.assertRaises(RuntimeError):
                profile_affine(profile)

    def test_pinned_euler_signs_match_analytical_axes(self):
        for angles, point in [([90, 0, 0], [0, 0, -1]), ([0, 90, 0], [0, 0, 1]), ([0, 0, 90], [-1, 0, 0])]:
            matrix, _ = profile_affine({'scale': [1, 1, 1], 'translate': [0, 0, 0], 'rotate': angles})
            vector = [1, 0, 0] if angles[1] else [0, 1, 0]
            np.testing.assert_allclose(matrix @ vector, point, atol=1e-12)


class EquipmentInventoryTests(unittest.TestCase):
    def test_ownership_excludes_only_custom_bare_parts(self):
        selected, excluded = select_models(['pmh0_chest001.mdl', 'pmh0_chest002.mdl', 'pmh0_belt001.mdl',
            'pmh0_robe001.mdl', 'pmh0_shol001.mdl', 'pmh0_neck001.mdl', 'pmh0_cloak_001.mdl',
            'helm_001.mdl', 'ashsw_001.mdl', 'pfh0_chest002.mdl', 'pmo0_chest002.mdl'])
        self.assertEqual({row['resource'] for row in excluded}, {'pmh0_chest001.mdl', 'pmh0_neck001.mdl'})
        self.assertEqual({row['part'] for row in selected}, {'chest', 'belt', 'robe', 'shol', 'cloak', 'helmet', 'shield'})

    def test_skin_weights_remain_explicit_bone_name_pairs(self):
        model = SOURCE.replace('node trimesh', 'node skin').replace(' materialname skin', ' materialname skin\n weights 4\n pelvis_g .5 torso_g .5\n pelvis_g 1\n torso_g 1\n torso_g .2 pelvis_g .8')
        result = inspect_model(model)
        self.assertTrue(result['requiresSkinBindPath'])
        self.assertEqual(result['weightedBones'], ['pelvis_g', 'torso_g'])
        self.assertEqual(result['nodes'][-1]['weights'], 4)
        self.assertIn('pelvis_g .5 torso_g .5', result['nodes'][-1]['weightsText'])


if __name__ == '__main__':
    unittest.main()
