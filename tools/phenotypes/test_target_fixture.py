"""Matched comparison sources, target actor identity and honest pending gates."""
import unittest

from target_fixture import POSES, actors, documents, scripts
from test_target_part_pipeline import target_fixture


class TargetFixtureTests(unittest.TestCase):
    def test_matched_eight_actor_comparisons_keep_common_scene_and_gameplay(self):
        target = target_fixture(); template = {'__data_type':'UTC ','__struct_id':-1}
        scenes = [actors(template,target,profile,3,11) for profile in
                  ('stock-human-comparison','published-human-comparison','troll-comparison')]
        self.assertTrue(all(len(scene) == 8 for scene in scenes))
        keys = ('XPosition','YPosition','ZPosition','Color_Skin','Color_Hair','ClassList','CurrentHitPoints','VarTable')
        for index in range(8):
            for key in keys:
                self.assertEqual(scenes[0][index][key],scenes[1][index][key]); self.assertEqual(scenes[0][index][key],scenes[2][index][key])
        self.assertTrue(all(row['Appearance_Type']['value'] == 2 and row['Race']['value'] == 2
                            and row['Gender']['value'] == 0 and row['Phenotype']['value'] == 0 for row in scenes[2]))
        self.assertTrue(all(row['Appearance_Type']['value'] == 6 for scene in scenes[:2] for row in scene))

    def test_palette_and_source_documents_are_explicit(self):
        target = target_fixture(); docs = documents({},target,'troll-palette',3,11)
        actors_ = docs['sr_tm_floor.git']['Creature List']['value']
        self.assertEqual([row['Color_Skin']['value'] for row in actors_],[3,11]*4)
        self.assertEqual(len(docs['sr_tm_floor.are']['Tile_List']['value']),64)
        self.assertEqual(docs['module.ifo']['Mod_HakList']['value'][0]['Mod_Hak']['value'],'srn_troll_test')
        self.assertIn('Incomplete',docs['module.ifo']['Mod_Description']['value']['0'])

    def test_sources_test_both_idle_clips_and_arrival_driven_movement(self):
        source = scripts('troll-matrix')
        self.assertIn('ANIMATION_LOOPING_PAUSE;',source['sr_tm_spawn'])
        self.assertIn('ANIMATION_LOOPING_PAUSE2;',source['sr_tm_spawn'])
        self.assertIn('outward-arrived',source['sr_tm_next']); self.assertIn('home-arrived',source['sr_tm_next'])
        self.assertIn('ActionMoveToLocation(home,step==3)',source['sr_tm_next'])
        self.assertIn('ActionCastSpellAtObject',source['sr_tm_next']); self.assertIn('ActionAttack(target)',source['sr_tm_next'])
        self.assertIn('EffectDeath(FALSE,FALSE)',source['sr_tm_next']); self.assertIn('EffectResurrection()',source['sr_tm_next'])
        self.assertIn('object corpse=OBJECT_SELF;',source['sr_tm_next'])
        self.assertNotIn('LockCameraPitch(pc,TRUE)',source['sr_tm_enter'])
        pilot = scripts('pilot'); self.assertIn('StartTorsoInspection(pc)',pilot['sr_tm_enter'])
        self.assertIn('GetObjectByTag("tm_',pilot['sr_tm_enter'])
        self.assertEqual(len(POSES),8)


if __name__ == '__main__': unittest.main()
