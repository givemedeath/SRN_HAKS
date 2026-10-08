"""Matched comparison sources, target actor identity and honest pending gates."""
import re
import unittest

from target_fixture import POSES, actors, documents, scripts, module_name, fixture_profiles
from test_target_part_pipeline import target_fixture


def naked_reset_scope(source):
    """Inspect actual lexical code; a matching phrase in a comment cannot pass."""
    ignored = re.compile(r'"(?:\\.|[^"\\])*"|//[^\n]*|/\*.*?\*/', re.S)
    code = ignored.sub(lambda match: ' ' * len(match[0]), source)
    condition = re.search(r'if\s*\(\s*!GetIsObjectValid\s*\(\s*GetItemInSlot\s*\(\s*INVENTORY_SLOT_CHEST\s*,\s*OBJECT_SELF\s*\)\s*\)\s*\)\s*\{', code)
    if condition is None:
        raise ValueError('Explicit no-equipped-chest reset guard missing')
    start = code.index('{', condition.start()); depth = 1; end = start + 1
    while end < len(code) and depth:
        depth += (code[end] == '{') - (code[end] == '}'); end += 1
    if depth:
        raise ValueError('Unbalanced naked reset block')
    calls = list(re.finditer(r'\bSetCreatureBodyPart\s*\([^;]+;', code))
    if len(calls) != 5 or any(not (start < call.start() < call.end() < end) for call in calls):
        raise ValueError('A naked body-part reset escapes the chest-equipment guard')
    return start, end, [source[call.start():call.end()] for call in calls]


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

    def test_module_carries_stock_identity_fields(self):
        import base64
        from target_fixture import module_identity
        target = target_fixture(); first = documents({},target,'troll-palette',3,11)['module.ifo']
        second = documents({},target,'troll-palette',3,11)['module.ifo']
        for ifo in (first,second):
            self.assertEqual(ifo['Mod_ID']['type'],'void'); self.assertEqual(len(base64.b64decode(ifo['Mod_ID']['value64'])),16)
            self.assertEqual(ifo['Mod_Creator_ID'],{'type':'int','value':2}); self.assertEqual(ifo['Expansion_Pack'],{'type':'word','value':0})
            self.assertEqual(ifo['Mod_OnModLoad'],{'type':'resref','value':''}); self.assertEqual(ifo['Mod_Expan_List'],{'type':'list','value':[]})
        self.assertNotEqual(first['Mod_ID'],second['Mod_ID'])
        self.assertEqual(module_identity(bytes(range(16)))['Mod_ID']['value64'],base64.b64encode(bytes(range(16))).decode())
        with self.assertRaises(ValueError): module_identity(b'short')

    def test_sources_test_both_idle_clips_and_arrival_driven_movement(self):
        source = scripts('troll-matrix')
        self.assertIn('ANIMATION_LOOPING_PAUSE;',source['sr_tm_spawn'])
        self.assertIn('ANIMATION_LOOPING_PAUSE2;',source['sr_tm_spawn'])
        self.assertIn('outward-arrived',source['sr_tm_next']); self.assertIn('home-arrived',source['sr_tm_next'])
        self.assertIn('ActionMoveToLocation(home,step==3)',source['sr_tm_next'])
        self.assertIn('TM_MATRIX",1',source['sr_tm_enter'])
        self.assertIn('ActionCastSpellAtObject',source['sr_tm_next']); self.assertIn('ActionAttack(target)',source['sr_tm_next'])
        self.assertIn('EffectDeath(FALSE,FALSE)',source['sr_tm_next']); self.assertIn('EffectResurrection()',source['sr_tm_next'])
        self.assertIn('object corpse=OBJECT_SELF;',source['sr_tm_next'])
        self.assertNotIn('LockCameraPitch(pc,TRUE)',source['sr_tm_enter'])
        pilot = scripts('pilot'); self.assertIn('StartTorsoInspection(pc)',pilot['sr_tm_enter'])
        self.assertIn('GetObjectByTag("tm_',pilot['sr_tm_enter'])
        self.assertEqual(len(POSES),8)


class FemaleStockFixtureTests(unittest.TestCase):
    def target(self):
        target = target_fixture(); target['rig']['mode'] = 'stock-exact'
        target['identity'].update(gender='female',prefix='pfh0',raceId=6,appearanceRow=6)
        return target

    def test_stock_and_candidate_scenes_decode_to_identical_female_identity_and_layout(self):
        target = self.target(); profiles = fixture_profiles(target)
        self.assertEqual(len(profiles),6); self.assertEqual(module_name(target),'srn_female_test')
        for phase in ('poses','palette','matrix'):
            stock = actors({},target,'stock-human-female-'+phase,3,8)
            candidate = actors({},target,'candidate-human-female-'+phase,3,8)
            for a,b in zip(stock,candidate):
                for key in ('Appearance_Type','Race','Gender','Phenotype','XPosition','YPosition','ZPosition','Color_Skin','VarTable','ClassList'):
                    self.assertEqual(a[key],b[key])
                self.assertEqual([a[key]['value'] for key in ('Appearance_Type','Race','Gender','Phenotype')],[6,6,1,0])
            self.assertEqual([row['Color_Skin']['value'] for row in stock],[3,8]*4 if phase == 'palette' else [3]*8)

    def test_stock_exact_module_and_logs_use_female_declared_identity(self):
        target = self.target(); docs = documents({},target,'candidate-human-female-matrix',3,8)
        self.assertEqual(docs['module.ifo']['Mod_HakList']['value'][0]['Mod_Hak']['value'],'srn_female_test')
        self.assertEqual(docs['sr_tm_target.utc']['Gender']['value'],1)
        code = scripts('candidate-human-female-matrix',target)
        self.assertIn('HUMAN_FEMALE_FIXTURE',code['sr_tm_spawn']); self.assertNotIn('TROLL_FIXTURE',''.join(code.values()))
        self.assertIn('SetCreatureBodyPart(CREATURE_PART_BELT,0)',code['sr_tm_spawn'])
        self.assertIn('TM_MATRIX",1',code['sr_tm_enter']); self.assertIn('LockCameraPitch(pc,FALSE)',code['sr_tm_enter'])

    def test_all_naked_resets_share_one_no_equipped_chest_lexical_block(self):
        source = scripts('candidate-human-female-matrix', self.target())['sr_tm_spawn']
        start, end, calls = naked_reset_scope(source)
        self.assertEqual(calls, [
            'SetCreatureBodyPart(i,1);',
            'SetCreatureBodyPart(CREATURE_PART_BELT,0);',
            'SetCreatureBodyPart(CREATURE_PART_RIGHT_SHOULDER,0);',
            'SetCreatureBodyPart(CREATURE_PART_LEFT_SHOULDER,0);',
            'SetCreatureBodyPart(CREATURE_PART_HEAD,1);'])
        self.assertIn('for(i=0;i<18;i++)', source[start:end])
        self.assertLess(source.index('TM_INITIALIZED",TRUE'), start)
        self.assertLess(end, source.index('SetColor(OBJECT_SELF,COLOR_CHANNEL_SKIN'))
        self.assertLess(end, source.index('SetColor(OBJECT_SELF,COLOR_CHANNEL_HAIR'))
        self.assertLess(end, source.index('TM_SCHEDULE_MODE"'))
        # This catches the actual historical bug: accessories outside the loop guard.
        reset = '    SetCreatureBodyPart(CREATURE_PART_BELT,0);'
        moved = source.replace(reset, '', 1)
        moved = moved[:end-len(reset)] + '\n  ' + reset + moved[end-len(reset):]
        with self.assertRaisesRegex(ValueError, 'escapes'):
            naked_reset_scope(moved)
        with self.assertRaisesRegex(ValueError, 'guard missing'):
            naked_reset_scope('// if(!GetIsObjectValid(GetItemInSlot(INVENTORY_SLOT_CHEST,OBJECT_SELF))) {\n' + source.replace('!GetIsObjectValid', 'GetIsObjectValid', 1))

    def test_stock_exact_male_keeps_identity_and_palette_schedule_with_same_robe_guard(self):
        target = self.target(); target['identity'].update(gender='male', prefix='pmh0')
        code = scripts('candidate-human-male-matrix', target)
        naked_reset_scope(code['sr_tm_spawn'])
        self.assertIn('HUMAN_MALE_FIXTURE', code['sr_tm_spawn'])
        self.assertNotIn('HUMAN_FEMALE_FIXTURE', ''.join(code.values()))
        self.assertIn('TM_MATRIX",1', code['sr_tm_enter'])
        self.assertIn('if(GetLocalInt(OBJECT_SELF,"TM_SCHEDULE_MODE")==mode) return;', code['sr_tm_spawn'])
        legacy = scripts('troll-matrix', target_fixture())['sr_tm_spawn']
        self.assertNotIn('INVENTORY_SLOT_CHEST', legacy)
        self.assertIn('TROLL_FIXTURE_SPAWN', legacy)
        self.assertIn('SetCreatureBodyPart(CREATURE_PART_BELT,0)', legacy)

    def test_engine_spawn_and_repeated_player_entries_start_each_schedule_once(self):
        source = scripts('candidate-human-female-matrix',self.target()); spawn = source['sr_tm_spawn']
        self.assertIn('if(!GetLocalInt(OBJECT_SELF,"TM_INITIALIZED"))',spawn)
        self.assertIn('SetLocalInt(OBJECT_SELF,"TM_INITIALIZED",TRUE)',spawn)
        self.assertIn('int mode=1; if(GetLocalInt(GetModule(),"TM_MATRIX")) mode=2;',spawn)
        guard = spawn.index('if(GetLocalInt(OBJECT_SELF,"TM_SCHEDULE_MODE")==mode) return;')
        self.assertLess(guard,spawn.index('ClearAllActions(TRUE)'))
        self.assertLess(guard,spawn.index('SetLocalInt(OBJECT_SELF,"TM_PHASE"'))
        self.assertLess(guard,spawn.index('if(mode==2) ExecuteScript("sr_tm_next"'))
        self.assertIn('TM_SCHEDULE_MODE",mode',spawn)
        # Module entry can request the configured mode repeatedly without resetting actor locals.
        enter = source['sr_tm_enter']; self.assertIn('ExecuteScript("sr_tm_spawn",actor)',enter)
        self.assertNotIn('TM_PHASE',enter); self.assertNotIn('TM_SCHEDULE_MODE',enter)
        self.assertIn('GetLocalInt(OBJECT_SELF,"TM_SCHEDULE_MODE")!=2) return;',source['sr_tm_next'])
        recovery = source['sr_tm_next'].split('void Recover(int phase)',1)[1].split('void main()',1)[0]
        self.assertLess(recovery.index('TM_PHASE'),recovery.index('EffectResurrection()'))
        self.assertIn('TM_SCHEDULE_MODE',recovery)

    def test_legacy_profile_names_and_male_identity_remain_available(self):
        target = target_fixture()
        self.assertIn('pilot',fixture_profiles(target)); self.assertEqual(module_name(target),'srn_troll_test')
        self.assertTrue(all(row['Gender']['value'] == 0 for row in actors({},target,'troll-poses',3,11)))


if __name__ == '__main__': unittest.main()
