"""Fixture documents and scripts are built without the game; the client run itself is driven by hand."""
import tempfile
import unittest
from pathlib import Path

from . import client, registry
from . import client_fixture as fixture


def values(actor):
    return {row['Name']['value']: row['Value']['value'] for row in fixture.actor_variables(actor)}


class FixtureTests(unittest.TestCase):
    def test_actor_parts_map_to_item_model_indices(self):
        got = values({'parts': {'chest': 700, 'bicep': 300, 'shoulder.l': 1000, 'belt': 0}, 'head': 86})
        self.assertEqual((got['AK_M7'], got['AK_M13'], got['AK_M12'], got['AK_M15'], got['AK_M14'], got['AK_M8'], got['AK_HEAD']),
                         (701, 301, 301, 1001, 1, 1, 86))
        self.assertEqual(sum(key.startswith('AK_M') for key in got), 19)

    def test_unset_parts_are_bare_skin_not_the_template_outfit(self):
        got = values({})
        self.assertEqual({key: value - 1 for key, value in got.items()},
                         {f'AK_M{i}': (0 if i in (8, 14, 15, 18) else 1) for i in range(19)})
        self.assertEqual(values({'bare': True}), {'AK_BARE': 1})
        self.assertEqual(values({'item': 'ak_bp1', 'parts': {'belt': 300}}), {'AK_ITEM': 'ak_bp1', 'AK_M8': 301})

    def test_colours_overall_per_part_and_body(self):
        got = values({'colours': {'cloth1': 0, 'metal2': 175}, 'partColours': {'chest': {'leather1': 40}, 'foot.r': {'cloth2': 9}},
                      'bodyColours': {'skin': 3, 'tattoo2': 60}})
        self.assertEqual((got['AK_C2'], got['AK_C5'], got['AK_C48'], got['AK_C9'], got['AK_B0'], got['AK_B3']), (1, 176, 41, 10, 4, 61))
        for bad in ({'colours': {'cloth1': 176}}, {'colours': {'skin': 1}}, {'parts': {'head': 1}}, {'parts': {'chest.l': 1}},
                    {'vars': {'AK_HEAD': 2}}, {'vars': {'lower': 2}}, {'script': 'Bad Name'}):
            with self.assertRaises(ValueError):
                fixture.actor_variables(bad)

    def test_creature_is_a_scriptless_plot_copy_of_the_template(self):
        template = {'__data_type': 'UTC ', 'ScriptHeartbeat': fixture.field('resref', 'nw_c2_default1'),
                    'ScriptSpawn': fixture.field('resref', 'nw_c2_default9'), 'Str': fixture.field('byte', 12)}
        made = fixture.creature(template, {'label': 'Troll F Large', 'body': 'pfg2', 'position': [34.0, 40.0], 'vars': {'MODE': 'A'}}, 'ak_t', 3)
        self.assertEqual({key: made[key]['value'] for key in ('Appearance_Type', 'Race', 'Gender', 'Phenotype', 'Tag', 'ScriptSpawn',
                                                               'ScriptHeartbeat', 'Plot', 'Str')},
                         {'Appearance_Type': 15104, 'Race': 2, 'Gender': 1, 'Phenotype': 2, 'Tag': 'ak_t_a3', 'ScriptSpawn': 'ak_t_sp',
                          'ScriptHeartbeat': '', 'Plot': 1, 'Str': 12})
        self.assertEqual((made['__struct_id'], '__data_type' in made, round(made['YOrientation']['value'], 6)), (4, False, -1.0))
        self.assertEqual(template['ScriptSpawn']['value'], 'nw_c2_default9')
        with self.assertRaisesRegex(ValueError, '20 SRN bodies'):
            fixture.creature(template, {'label': 'x', 'body': 'pmh1', 'position': [0, 0]}, 'ak_t', 0)

    def test_enter_script_steps_the_camera_and_logs_each_shot(self):
        text = fixture.enter_script('ak_t', [{'actor': 0}, {'actor': 2, 'facing': 270, 'distance': 1.5, 'pitch': 80, 'height': 1.4}])
        self.assertIn('DelayCommand(8.0,Shot(pc,0,"ak_t_a0",90.000,5.000,84.000,0.000));', text)
        self.assertIn('DelayCommand(11.0,Shot(pc,1,"ak_t_a2",270.000,1.500,80.000,1.400));', text)
        self.assertIn('DelayCommand(14.0,WriteTimestampedLogEntry("ARMORKIT done"));', text)
        self.assertIn('SetCutsceneMode(pc,TRUE,FALSE);', text)
        with self.assertRaisesRegex(ValueError, 'A shot is'):
            fixture.enter_script('ak_t', [{'tag': 'x'}])

    def test_module_lists_the_fixture_hak_first(self):
        documents = fixture.module_documents('ak_t', ['srn_2da', 'srn_body'], 'srn')
        ifo = documents['module.ifo']
        self.assertEqual([row['Mod_Hak']['value'] for row in ifo['Mod_HakList']['value']], ['ak_t', 'srn_2da', 'srn_body'])
        self.assertEqual((ifo['Mod_CustomTlk']['value'], ifo['Mod_OnClientEntr']['value'], ifo['Mod_Entry_Area']['value']), ('srn', 'ak_t_en', 'ak_t_a'))
        area = fixture.area_documents('ak_t', [{'x': 1}], 4)
        self.assertEqual((len(area['ak_t_a.are']['Tile_List']['value']), area['ak_t_a.are']['Tileset']['value'],
                          area['ak_t_a.git']['Creature List']['value']), (16, 'ak_t', [{'x': 1}]))

    def test_tileset_is_renamed_and_bare(self):
        text = fixture.tileset('[GENERAL]\r\nName=TTR01\r\n[GRASS]\r\nDensity=0.250\r\n', 'ak_t')
        self.assertEqual(text, '[GENERAL]\r\nName=AK_T\r\n[GRASS]\r\nDensity=0.000\r\n')
        with self.assertRaisesRegex(ValueError, 'Unexpected stock tileset'):
            fixture.tileset('Name=OTHER\n', 'ak_t')

    def test_spawn_script_reads_every_item_part_and_colour(self):
        self.assertIn('ITEM_APPR_ARMOR_NUM_COLORS*(ITEM_APPR_ARMOR_NUM_MODELS+1)', fixture.SPAWN_SCRIPT)
        self.assertIn('"ARMORKIT actor="', fixture.SPAWN_SCRIPT)
        self.assertEqual(fixture.row(4, 5), [34.0 + 1.9, 44.0])
        self.assertEqual(set(fixture.NAKED), set(registry.SLOTS))


class ClientTests(unittest.TestCase):
    def test_command_isolates_the_user_directory(self):
        got = client.command(Path('game'), Path('fixture') / 'userdir', 'ak_t')
        self.assertEqual((Path(got[0]).parts[-3:], got[1], Path(got[2]).name, got[3:]),
                         (('bin', 'win32', 'nwmain.exe'), '-userdirectory', 'userdir', ['+TestNewModule', 'ak_t']))

    def test_log_lines_are_filtered_and_parsed(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(client.log_lines(folder), [])
            (Path(folder) / 'logs').mkdir()
            (Path(folder) / 'logs' / 'nwclientLog1.txt').write_text(
                '[Mon Nov 10 00:00:01] noise\n[Mon Nov 10 00:00:02] ARMORKIT actor=Human M tag=ak_t_a0 parts=1,2,3\nARMORKIT done\n', encoding='cp1252')
            lines = client.log_lines(folder)
        self.assertEqual(lines, ['ARMORKIT actor=Human M tag=ak_t_a0 parts=1,2,3', 'ARMORKIT done'])
        self.assertEqual(client.parse_line(lines[0]), {'actor': 'Human M', 'tag': 'ak_t_a0', 'parts': '1,2,3'})

    def test_only_a_client_started_here_can_be_stopped(self):
        with self.assertRaisesRegex(ValueError, 'Only a client started here'):
            client.stop(1234)
        self.assertIn('on-focus-loss', client.SETTINGS.format(width=1, height=1))


if __name__ == '__main__':
    unittest.main()
