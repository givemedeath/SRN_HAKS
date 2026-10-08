"""Human source-family isolation and authored skin input regressions."""
import unittest
from inventory_target_equipment import select_models, inspect_model


class EquipmentIdentityTests(unittest.TestCase):
    def test_female_inventory_keeps_global_held_parts_but_excludes_other_body_families(self):
        names = ['pfh0_chest001.mdl','pfh0_chest020.mdl','pmh0_chest020.mdl','pfh0_robe001.mdl','pfh0_cloak_001.mdl','helm_001.mdl','ashls_m_011.mdl','pfg0_chest020.mdl']
        selected, excluded = select_models(names, 'pfh0')
        self.assertEqual({row['resource'] for row in selected}, {'pfh0_chest020.mdl','pfh0_robe001.mdl','pfh0_cloak_001.mdl','helm_001.mdl','ashls_m_011.mdl'})
        self.assertEqual([row['resource'] for row in excluded], ['pfh0_chest001.mdl'])
        self.assertEqual(next(row['category'] for row in selected if row['part']=='robe'), 'robe')

    def test_legacy_default_stays_male_and_invalid_families_fail(self):
        selected, _ = select_models(['pfh0_chest020.mdl','pmh0_chest020.mdl'])
        self.assertEqual([row['resource'] for row in selected], ['pmh0_chest020.mdl'])
        for prefix in ('pfg0','pmh2','../pfh0'):
            with self.assertRaises(ValueError): select_models([], prefix)

    def test_skin_binding_rows_are_retained_as_authored_inputs(self):
        text = 'newmodel robe\nsetsupermodel robe pfh0\nbeginmodelgeom robe\nnode skin cloth\n parent robe\n verts 1\n 0 0 0\n weights 1\n pelvis_g 0.75 torso_g 0.25\nendnode\nendmodelgeom robe\n'
        row = inspect_model(text)
        self.assertTrue(row['requiresSkinBindPath'])
        self.assertEqual(row['weightedBones'], ['pelvis_g','torso_g'])
        self.assertEqual(row['nodes'][0]['weightsText'], ' pelvis_g 0.75 torso_g 0.25')


if __name__ == '__main__': unittest.main()
