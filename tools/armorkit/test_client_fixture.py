"""Fixture documents and scripts are built without the game; the client run itself is driven by hand."""
import hashlib
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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

    def test_actor_entries_are_checked_before_they_reach_the_script(self):
        """A misspelt key or a wrong type would otherwise give a capture of the default actor, read as the test."""
        for bad in ({'colors': {'cloth1': 1}}, {'part': {'chest': 300}}, {'head': '86'}, {'head': 0}, {'head': True},
                    {'vars': {'SWAP': True}}, {'vars': {'SWAP': None}}, {'parts': ['chest']}, {'partColours': {'chest': 3}}):
            with self.assertRaises(ValueError, msg=str(bad)):
                fixture.actor_variables(bad)
        self.assertEqual(values({'bare': True, 'vars': {'MODE': 'A', 'STEP': 2, 'GAP': 0.5}}),
                         {'AK_BARE': 1, 'MODE': 'A', 'STEP': 2, 'GAP': 0.5})

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
        with self.assertRaisesRegex(ValueError, 'needs label, body and position'):
            fixture.creature(template, {'body': 'pmh0'}, 'ak_t', 0)

    def test_each_shot_schedules_the_next_so_a_stall_cannot_bunch_them(self):
        text = fixture.enter_script('ak_t', [{'actor': 0}, {'actor': 2, 'facing': 270, 'distance': 1.5, 'pitch': 80, 'height': 1.4}])
        self.assertIn('if(n==0) { tag="ak_t_a0"; facing=90.000; distance=5.000; pitch=84.000; height=0.000; }', text)
        self.assertIn('if(n==1) { tag="ak_t_a2"; facing=270.000; distance=1.500; pitch=80.000; height=1.400; }', text)
        self.assertIn('if(n>=2) { WriteTimestampedLogEntry("ARMORKIT done"); return; }', text)
        self.assertIn('DelayCommand(3.0,Shot(pc,n+1));', text)
        self.assertEqual(text.count('DelayCommand(8.0,Shot(pc,0));'), 1)
        self.assertEqual(text.count('Shot(pc,'), 2)  # the first shot and the chain: nothing is laid out on the clock up front
        self.assertIn('DelayCommand(5.0,AttachCamera(pc,GetObjectByTag("ak_t_a0")));', text)
        self.assertIn('SetCutsceneMode(pc,TRUE,FALSE);', text)
        self.assertIn('DelayCommand(4.5,Shot(pc,n+1));', fixture.enter_script('ak_t', [{'actor': 0}], hold=4.5))
        for bad in ([{'tag': 'x'}], ['x'], [{'actor': 0, 'facing': 'north'}], [{'actor': -1}]):
            with self.assertRaisesRegex(ValueError, 'A shot is'):
                fixture.enter_script('ak_t', bad)

    def test_fixture_names_leave_room_for_the_resources_built_from_them(self):
        self.assertTrue(fixture.NAME.fullmatch('abcdefghijk'))
        self.assertFalse(fixture.NAME.fullmatch('abcdefghijkl'))
        self.assertLessEqual(len('abcdefghijk' + '_edge'), fixture.RESREF)
        self.assertEqual(fixture.actor_tag('abcdefghijk', 999), 'abcdefghijk_a999')
        with self.assertRaisesRegex(ValueError, 'Too many actors'):
            fixture.actor_tag('abcdefghijk', 1000)

    def test_build_checks_the_spec_before_it_makes_the_output_folder(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            (folder / 'game' / 'data').mkdir(parents=True)
            for name in ('one', 'two'):
                (folder / name).mkdir()
                (folder / name / 'pack_a.hak').write_bytes(name.encode())
            actor = {'label': 'A', 'body': 'pmh0', 'position': [34.0, 40.0]}
            cases = (({'name': 'abcdefghijkl', 'actors': [actor]}, 'at most 11 characters'),
                     ({'name': 'ak_t', 'actors': []}, 'at least one actor'),
                     ({'name': 'ak_t', 'actors': [actor], 'shots': [{'actor': 1}]}, 'actor that does not exist'),
                     ({'name': 'ak_t', 'actors': [actor], 'haks': [str(folder / 'one' / 'pack_a.hak'), str(folder / 'two' / 'pack_a.hak')]},
                      'Two fixture haks share a name'),
                     ({'name': 'ak_t', 'actors': [actor], 'haks': [str(folder / 'missing.hak')]}, 'existing .hak files'),
                     ({'name': 'ak_t', 'actors': [actor], 'extra': 1}, 'Unknown fixture keys'))
            for spec, message in cases:
                with self.assertRaisesRegex(ValueError, message):
                    fixture.build(spec, folder / 'out', folder / 'game')
                self.assertFalse((folder / 'out').exists(), message)
            with self.assertRaisesRegex(ValueError, 'game install folder'):
                fixture.build({'name': 'ak_t', 'actors': [actor]}, folder / 'out', folder / 'nowhere')
            self.assertFalse((folder / 'out').exists())
            (folder / 'out').mkdir()
            with self.assertRaisesRegex(ValueError, 'fresh folder'):
                fixture.build({'name': 'ak_t', 'actors': [actor]}, folder / 'out', folder / 'game')

    def test_a_pack_is_never_written_through_an_existing_link(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            (folder / 'first.hak').write_bytes(b'first')
            (folder / 'second.hak').write_bytes(b'second')
            fixture.place(folder / 'first.hak', folder / 'placed.hak')
            with self.assertRaisesRegex(ValueError, 'already exists'):
                fixture.place(folder / 'second.hak', folder / 'placed.hak')
            self.assertEqual(((folder / 'first.hak').read_bytes(), (folder / 'placed.hak').read_bytes()), (b'first', b'first'))
            self.assertEqual(fixture.digest(folder / 'placed.hak'), hashlib.sha256(b'first').hexdigest())

    def test_module_lists_the_fixture_hak_first(self):
        documents = fixture.module_documents('ak_t', ['pack_a', 'pack_b'], 'talk')
        ifo = documents['module.ifo']
        self.assertEqual([row['Mod_Hak']['value'] for row in ifo['Mod_HakList']['value']], ['ak_t', 'pack_a', 'pack_b'])
        self.assertEqual((ifo['Mod_CustomTlk']['value'], ifo['Mod_OnClientEntr']['value'], ifo['Mod_Entry_Area']['value']), ('talk', 'ak_t_en', 'ak_t_a'))
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
        self.assertEqual({slot for slot, number in fixture.NAKED.items() if number == 0}, {'belt', 'shoulder', 'robe'})


class FakeClient:
    """The driver's view of a client: a scripted log, and a record of what was captured when."""
    def __init__(self, test, reads):
        self.reads, self.captured, self.stopped = list(reads), [], 0
        for name, stand_in in (('start', lambda *a, **k: self), ('stop', self.stop), ('capture', self.capture),
                               ('log_lines', self.log_lines)):
            patcher = mock.patch.object(client, name, stand_in)
            patcher.start()
            test.addCleanup(patcher.stop)
        patcher = mock.patch.object(client.time, 'sleep', lambda seconds: None)
        patcher.start()
        test.addCleanup(patcher.stop)

    def poll(self):
        return None

    pid = 4321

    def stop(self, process):
        self.stopped += 1

    def capture(self, pid, path):
        self.captured.append(Path(path).name)
        return Path(path)

    def log_lines(self, user, prefix=None):
        return self.reads.pop(0) if len(self.reads) > 1 else self.reads[0]


SHOT = 'ARMORKIT shot={} target=ak_t_a{} valid=1'
RECORD = {'userDirectory': 'user', 'module': 'ak_t.mod', 'shots': 2, 'start': 8.0, 'hold': 3.0}


class ClientTests(unittest.TestCase):
    def test_command_isolates_the_user_directory(self):
        got = client.command(Path('game'), Path('fixture') / 'userdir', 'ak_t')
        self.assertEqual((Path(got[0]).parts[-3:], got[1], Path(got[2]).name, got[3:]),
                         (('bin', 'win32', 'nwmain.exe'), '-userdirectory', 'userdir', ['+TestNewModule', 'ak_t']))
        self.assertTrue(Path(got[2]).is_absolute())  # the client runs from its own folder

    def test_log_lines_are_filtered_and_parsed(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(client.log_lines(folder), [])
            (Path(folder) / 'logs').mkdir()
            (Path(folder) / 'logs' / 'nwclientLog1.txt').write_text(
                '[Mon Nov 10 00:00:01] noise\n[Mon Nov 10 00:00:02] ARMORKIT actor=Human M tag=ak_t_a0 parts=1,2,3\nARMORKIT done\n', encoding='cp1252')
            lines = client.log_lines(folder)
        self.assertEqual(lines, ['ARMORKIT actor=Human M tag=ak_t_a0 parts=1,2,3', 'ARMORKIT done'])
        self.assertEqual(client.parse_line(lines[0]), {'actor': 'Human M', 'tag': 'ak_t_a0', 'parts': '1,2,3'})
        self.assertEqual(client.shot_numbers([SHOT.format(0, 0), 'ARMORKIT actor=A tag=t', SHOT.format(1, 2)]), [0, 1])

    def test_only_a_client_started_here_can_be_stopped(self):
        with self.assertRaisesRegex(ValueError, 'Only a client started here'):
            client.stop(1234)
        self.assertIn('on-focus-loss', client.SETTINGS.format(width=1, height=1))

    def test_a_failed_process_listing_is_not_read_as_no_client_running(self):
        def listing(code, output):
            return mock.patch.object(client.subprocess, 'run', return_value=subprocess.CompletedProcess([], code, output, b''))
        with listing(1, b''), self.assertRaisesRegex(ValueError, 'tasklist failed'):
            client.running()
        with listing(0, b'INFO: No tasks are running which match the specified criteria.\r\n'):
            self.assertEqual(client.running(), [])
        with listing(0, b'"nwmain.exe","4321","Console","1","812,300 K"\r\n"NWMAIN.EXE","77","Console","1","1 K"\r\n'):
            self.assertEqual(client.running(), [4321, 77])

    def test_each_capture_is_filed_under_the_shot_on_screen(self):
        zero, one = SHOT.format(0, 0), SHOT.format(1, 1)
        fake = FakeClient(self, [[zero], [zero], [zero, one], [zero, one], [zero, one, 'ARMORKIT done']])
        got = client.run('game', RECORD, 'captures')
        self.assertEqual((fake.captured, fake.stopped), (['shot-00.png', 'shot-01.png'], 1))
        self.assertEqual(len(got['captures']), 2)

    def test_a_capture_that_would_show_a_later_shot_is_refused(self):
        """The Phase 0 helmet run filed eight pictures under the wrong shot after an 11 s stall."""
        zero, one = SHOT.format(0, 0), SHOT.format(1, 1)
        fake = FakeClient(self, [[zero], [zero, one]])
        with self.assertRaisesRegex(ValueError, 'Shot 0 was not captured before shot 1 began'):
            client.run('game', RECORD, 'captures')
        self.assertEqual((fake.captured, fake.stopped), ([], 1))

    def test_a_shot_without_its_actor_and_a_settle_longer_than_the_shot_are_refused(self):
        fake = FakeClient(self, [['ARMORKIT shot=0 target=ak_t_a9 valid=0']])
        with self.assertRaisesRegex(ValueError, 'no actor to look at'):
            client.run('game', RECORD, 'captures')
        self.assertEqual((fake.captured, fake.stopped), ([], 1))
        with self.assertRaisesRegex(ValueError, 'leaves no time to capture'):
            client.run('game', RECORD, 'captures', settle=2.5)
        self.assertEqual(fake.stopped, 1)  # refused before a client was started


if __name__ == '__main__':
    unittest.main()
