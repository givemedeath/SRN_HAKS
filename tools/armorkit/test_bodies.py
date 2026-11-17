"""An outfit on every body: the commands that build it, in their order, and the client check of the built packs."""
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from . import bake, bodies, client, poses, registry
from . import client_fixture as fixture

PARTS = ['chest', 'pelvis', 'legl', 'legr']
BRIEFS = {'m': 'male.json', 'f': 'female.json'}


def kept(folder, parts=PARTS):
    folder = Path(folder)
    folder.mkdir(parents=True)
    (folder / bake.KEPT).write_text(json.dumps({'schemaVersion': 1, 'kind': bake.KEPT_KIND, 'parts': list(parts)}), encoding='utf-8')
    return folder


def runner(calls, fail=(), passed=True, silent=()):
    """A stand-in for `bodies.command`: notes each command and writes what the kit's own would leave behind."""
    lock = threading.Lock()

    def run(arguments, stdout, stderr):
        with lock:
            calls.append(arguments)
        Path(stdout).write_text('{}', encoding='utf-8')
        Path(stderr).write_text('', encoding='utf-8')
        target = arguments[arguments.index('--to') + 1] if '--to' in arguments else arguments[arguments.index('--body') + 1] if '--body' in arguments else 'pfh0'
        if (arguments[0], target) in fail:
            return 1
        if arguments[0] in ('refit', 'combine'):
            kept(arguments[2])
            return 0
        if (arguments[0], target) in silent:
            return 0
        Path(arguments[2]).mkdir()
        gates = {'passed': passed, 'failures': [] if passed else ['a gate'], 'triangles': {'outfit': 25000}}
        (Path(arguments[2]) / 'bake.json').write_text(json.dumps({'body': target, 'gates': gates}), encoding='utf-8')
        return 0 if passed else 1  # as `bake` does: its record written, and 1 where a gate fails
    return run


class PlanTests(unittest.TestCase):
    def test_every_body_is_refit_from_the_human_of_its_gender_and_baked_at_the_number(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            male, out = kept(root / 'male'), root / 'out'
            steps = bodies.plan(male, out, BRIEFS, 6020, 'pack', body_textures='tex', packs=['a', 'b'], game='game', tint_cache='cache')
            self.assertEqual(list(steps)[:2], ['pfh0', 'pmh0'])  # the Humans first: the others are carried from them
            self.assertEqual(set(steps), set(registry.BODIES))
            self.assertEqual([step['arguments'] for step in steps['pmh0']],
                             [['bake', 'male.json', str(out / 'pmh0'), '--number', '6020', '--body', 'pmh0', '--body-pack', 'pack', '--body-textures', 'tex',
                               '--kept', str(male), '--pack', 'a', '--pack', 'b', '--nwn-root', 'game', '--tint-cache', 'cache']])
            refit, tint = steps['pfd2']
            self.assertEqual(refit['arguments'], ['refit', str(out / 'pfh0-kept'), str(out / 'pfd2-kept'), '--body-pack', 'pack', '--body-textures', 'tex',
                                                  '--from', 'pfh0', '--to', 'pfd2'])
            self.assertEqual((refit['stdout'], tint['stderr']), (out / 'pfd2-refit.json', out / 'pfd2.log'))
            self.assertEqual(tint['arguments'][:3] + tint['arguments'][tint['arguments'].index('--kept'):][:2],
                             ['bake', 'female.json', str(out / 'pfd2'), '--kept', str(out / 'pfd2-kept')])
            self.assertEqual(steps['pmg2'][0]['arguments'][1:3] + steps['pmg2'][0]['arguments'][-4:], [str(male), str(out / 'pmg2-kept'), '--from', 'pmh0', '--to', 'pmg2'])
            # without a bake of her own the Human female is the male, refit whole
            self.assertEqual(steps['pfh0'][0]['arguments'][-4:], ['--from', 'pmh0', '--to', 'pfh0'])
            self.assertEqual(len(steps['pfh0']), 2)

    def test_a_human_female_keeps_her_own_parts_and_takes_the_rest_from_the_male(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            male, own, out = kept(root / 'male'), kept(root / 'own', ['chest']), root / 'out'
            carried, combined, tint = bodies.plan(male, out, BRIEFS, 6020, 'pack', own=own, bodies=('pfh0',))['pfh0']
            self.assertEqual(carried['arguments'], ['refit', str(male), str(out / 'pfh0-carried'), '--body-pack', 'pack', '--from', 'pmh0', '--to', 'pfh0',
                                                    '--seat-in', str(own), '--parts', 'pelvis,legl,legr'])
            self.assertEqual(combined['arguments'], ['combine', 'female.json', str(out / 'pfh0-kept'), '--from', f'{own}=chest', '--from', f'{out / "pfh0-carried"}=pelvis,legl,legr'])
            self.assertEqual(tint['arguments'][-2:], ['--kept', str(out / 'pfh0-kept')])
            for wrong in ({'bodies': ('pmx0',)}, {'bodies': ()}):
                with self.assertRaises(ValueError):
                    bodies.plan(male, out, BRIEFS, 6020, 'pack', **wrong)
            with self.assertRaises(ValueError):  # a brief for each gender
                bodies.plan(male, out, {'m': 'male.json'}, 6020, 'pack')
            with self.assertRaisesRegex(ValueError, 'holds no pelvis'):  # a part her own bake did not keep, told before anything runs
                bodies.plan(male, out, BRIEFS, 6020, 'pack', own=own, own_parts=('chest', 'pelvis'))
            for parts in ((), tuple(PARTS)):  # she keeps some parts and takes some: neither none nor all
                with self.assertRaisesRegex(ValueError, 'keeps some'):
                    bodies.plan(male, out, BRIEFS, 6020, 'pack', own=own, own_parts=parts)


class BuildTests(unittest.TestCase):
    def test_the_humans_are_built_before_the_bodies_carried_from_them(self):
        with tempfile.TemporaryDirectory() as folder:
            root, calls, said = Path(folder), [], []
            male, out = kept(root / 'male'), root / 'out'
            wanted = ('pmh0', 'pfh0', 'pmd0', 'pfd0', 'pfe2')
            report = bodies.build(male, out, BRIEFS, 6020, 'pack', bodies=wanted, run=runner(calls), say=said.append)
            self.assertTrue(report['passed'])
            self.assertEqual(set(report['bodies']), set(wanted))
            self.assertEqual(report['bodies']['pfe2']['triangles'], 25000)
            self.assertEqual(json.loads((out / bodies.REPORT).read_text(encoding='utf-8')), report)
            first = {(arguments[0], arguments[2]) for arguments in calls[:3]}  # the two Humans, side by side
            self.assertEqual(first, {('refit', str(out / 'pfh0-kept')), ('bake', str(out / 'pfh0')), ('bake', str(out / 'pmh0'))})
            self.assertEqual(len(calls), 3 + 2 * 3)
            self.assertEqual(len(said), len(wanted))
            with self.assertRaisesRegex(ValueError, 'built already'):  # nothing built is written over
                bodies.build(male, out, BRIEFS, 6020, 'pack', bodies=('pmd0',), run=runner(calls))
            # a race body alone is carried from the Human an earlier run kept
            again = bodies.build(male, out, BRIEFS, 6020, 'pack', bodies=('pfo2', 'pmo2'), run=runner(calls))
            self.assertTrue(again['passed'])
            with self.assertRaisesRegex(ValueError, 'carried from pfh0'):
                bodies.build(male, root / 'other', BRIEFS, 6020, 'pack', bodies=('pfo2',), run=runner(calls))
            self.assertFalse((root / 'other').exists())
            # a body that failed is built again elsewhere, carried from the Human female the first run kept
            calls.clear()
            retried = bodies.build(male, root / 'other', BRIEFS, 6020, 'pack', bodies=('pfo2',), female_from=out / 'pfh0-kept', run=runner(calls))
            self.assertTrue(retried['passed'])
            self.assertEqual(calls[0][:3], ['refit', str(out / 'pfh0-kept'), str(root / 'other' / 'pfo2-kept')])
            with self.assertRaisesRegex(ValueError, 'not both'):
                bodies.plan(male, root / 'third', BRIEFS, 6020, 'pack', bodies=('pfh0', 'pfo2'), female_from=out / 'pfh0-kept')

    def test_a_failed_step_stops_its_body_and_a_failed_human_the_bodies_carried_from_it(self):
        with tempfile.TemporaryDirectory() as folder:
            root, calls = Path(folder), []
            male = kept(root / 'male')
            report = bodies.build(male, root / 'a', BRIEFS, 6020, 'pack', bodies=('pmh0', 'pfh0', 'pmd0', 'pfd0'),
                                  run=runner(calls, fail={('refit', 'pfh0'), ('bake', 'pmd0')}))
            found = report['bodies']
            self.assertFalse(report['passed'])
            self.assertEqual((found['pfh0']['failed'], found['pfd0']['failed'], found['pmd0']['failed']), ('refit', 'not begun', 'bake'))
            self.assertEqual(found['pfd0']['log'], str(root / 'a' / 'pfh0-refit.log'))
            self.assertTrue(found['pmh0']['passed'])
            self.assertFalse(any('pfd0' in arguments for arguments in calls))
            # A bake whose gates fail says which, and stops no body: the parts the others are carried from are kept all the same.
            failing = bodies.build(male, root / 'b', BRIEFS, 6020, 'pack', bodies=('pmh0', 'pfh0', 'pmd0', 'pfd0'), run=runner([], passed=False))
            self.assertFalse(failing['passed'])
            self.assertEqual({body: (found['failed'], found['failures']) for body, found in failing['bodies'].items()},
                             {body: ('bake', ['a gate']) for body in ('pmh0', 'pfh0', 'pmd0', 'pfd0')})
            # A bake that says it is done and wrote no record fails alone; the report is still written.
            mute = bodies.build(male, root / 'c', BRIEFS, 6020, 'pack', bodies=('pmh0', 'pmd0'), run=runner([], silent={('bake', 'pmd0')}))
            self.assertEqual((mute['bodies']['pmd0']['failed'], mute['bodies']['pmh0']['passed'], mute['passed']), ('bake', True, False))
            self.assertTrue((root / 'c' / bodies.REPORT).is_file())

            def broken(arguments, stdout, stderr):
                raise OSError('no room')
            self.assertEqual(bodies.build(male, root / 'd', BRIEFS, 6020, 'pack', bodies=('pmh0',), run=broken)['bodies']['pmh0']['failed'], 'report')


class CheckTests(unittest.TestCase):
    def test_every_body_is_looked_at_in_two_poses_from_a_distance_its_height_sets(self):
        actors, shots, labels = bodies.cast(['pmh0', 'pfd2', 'pmg0'], {'chest': 6020}, {'pmh0': 1.0, 'pfd2': 0.7, 'pmg0': 1.3})
        self.assertEqual([actor['label'] for actor in actors], ['pmh0, standing', 'pfd2, standing', 'pmg0, standing', 'pmh0, arms up', 'pfd2, arms up', 'pmg0, arms up'])
        self.assertEqual((len(shots), labels[4]), (6 * len(bodies.VIEWS), 'pfd2, standing, front'))
        self.assertEqual([actor['head'] for actor in actors[:3]], [bodies.HEADS['pmh'], bodies.HEADS['pfd'], bodies.HEADS['pmg']])
        self.assertTrue(all(actor['colours'] == poses.COLOURS and actor['parts'] == {'chest': 6020} for actor in actors))
        self.assertEqual(len({actor['position'] for actor in actors}), 6)
        # all 20 bodies stand inside the fixture's area, 160 m a side, in rows; more than it holds are refused
        everyone = bodies.cast(list(registry.BODIES), {}, {body: 1.0 for body in registry.BODIES})[0]
        self.assertEqual((len(everyone), len({actor['position'] for actor in everyone})), (40, 40))
        self.assertTrue(all(5.0 < x < 155.0 and 5.0 < y < 155.0 and (x, y) != bodies.HOST for x, y in (actor['position'] for actor in everyone)))
        steps = [abs(a['position'][0] - b['position'][0]) + abs(a['position'][1] - b['position'][1]) for a, b in zip(everyone, everyone[1:])]
        self.assertLessEqual(max(steps), bodies.APART)  # the camera never goes far from one actor to the next
        with self.assertRaisesRegex(ValueError, 'room for'):
            bodies.cast(list(registry.BODIES), {}, {body: 1.0 for body in registry.BODIES}, stances=bodies.CAST * 2)
        human, dwarf, troll = (shots[at * len(bodies.VIEWS)] for at in range(3))
        self.assertEqual((human['distance'], dwarf['distance'], troll['distance']), (3.2, 3.2, 4.16))  # further off a taller body, never nearer
        self.assertEqual((human['height'], dwarf['height'], troll['height']), (0.95, 0.665, 1.235))
        self.assertEqual(bodies.cast(['pmh0'], {}, {'pmh0': 1.0}, heads={'pmh': 3})[0][0]['head'], 3)
        with self.assertRaises(ValueError):
            bodies.cast(['pmx0'], {}, {'pmx0': 1.0})

    def test_the_outfit_is_read_from_the_registry(self):
        parts = [{'slot': 'chest', 'number': 6020, 'bodies': list(registry.BODIES)}, {'slot': 'pelvis', 'number': 6020, 'bodies': ['pmh0', 'pfh0']},
                 {'slot': 'chest', 'number': 7, 'bodies': ['pmh0']}]
        self.assertEqual(bodies.published(parts, 6020), (['chest', 'pelvis'], ['pmh0', 'pfh0']))
        self.assertEqual(bodies.published(parts, 6020, ['pfh0']), (['chest', 'pelvis'], ['pfh0']))
        for wrong in ((8, None), (6020, ['pmd0'])):
            with self.assertRaises(ValueError):
                bodies.published(parts, *wrong)

    def test_the_fixture_shows_the_packs_and_the_outfit_as_an_item(self):
        heights = {'pmh0': 1.0, 'pfh0': 1.0}
        with mock.patch.object(bodies, 'statures', return_value=heights):
            document, layout = bodies.check_spec(['pmh0', 'pfh0'], ['chest', 'pelvis'], 6020, ['parts.hak', 'body.hak'], 'pack', tlk='srn.tlk', hold=5.0)
            plain, without = bodies.check_spec(['pmh0'], ['chest'], 6020, [], 'pack', icons=False)
            for wrong in ((['pmh0', 'pmh0'], ['chest']), ([], ['chest']), (['pmh0'], ['wing']), (['pmh0'], [])):
                with self.assertRaises(ValueError):
                    bodies.check_spec(*wrong, 6020, [], 'pack')
        count = 4 * len(bodies.VIEWS)
        self.assertEqual((len(document['shots']), len(layout['labels']), layout['columns'], layout['icons']), (count, count, len(bodies.VIEWS), True))
        self.assertEqual((document['haks'], document['tlk'], document['hold']), (['parts.hak', 'body.hak'], 'srn.tlk', 5.0))
        self.assertNotIn('resources', document)  # nothing of a bake: what the packs hold
        host = document['actors'][-1]
        self.assertEqual((host['bare'], host['script'], len(document['actors'])), (True, 'ak_icons', 5))
        script = document['scripts']['ak_icons']
        # every slot the outfit fills and nothing in the others, a slot a tick; the windows stay a whole hold after their line
        for line in (f'shot={count} target=item', '{ index=7; value=6020; }', '{ index=6; value=6020; }', '{ index=8; value=0; }', 'if(n==18)',
                     'DelayCommand(0.1,Step(pc,next,n+1))', 'target=item valid="+IntToString(made)', 'SetLocalInt(GetModule(),"ARMORKIT_ICON_FAILED",1)', 'DelayCommand(1.5+5.0,Line("ARMORKIT icons-done"))',
                     f'!GetLocalInt(GetModule(),"{fixture.DONE}")) {{ DelayCommand(1.0,Wait()); return; }}'):  # after the shots, whenever they end
            self.assertIn(line, script)
        self.assertEqual((without['icons'], set(plain['scripts']), len(plain['actors'])), (False, {'ak_pose'}, 2))
        self.assertNotIn('tlk', plain)

    def test_a_run_waits_for_the_icons_and_files_them_apart_from_the_sheet(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            layout = {'labels': ['a', 'b'], 'columns': 2, 'icons': True}
            record = {'module': 'ak_bodies.mod', 'shots': 2, 'start': 8.0, 'hold': 5.0}
            asked = {}

            def ran(nwn_root, given, captures, **options):
                asked.update(options)
                Path(captures).mkdir()
                for name in ('0', '1', '2'):
                    (Path(captures) / f'shot-0{name}.png').write_bytes(name.encode())
                return {'lines': [], 'captures': [str(Path(captures) / f'shot-0{name}.png') for name in ('0', '1', '2')], 'missed': []}
            with mock.patch.object(poses, 'build', side_effect=lambda *_: dict(record)) as built, mock.patch.object(client, 'run', side_effect=ran), \
                    mock.patch.object(client, 'wait_free') as waited, mock.patch.object(poses, 'sheet', side_effect=lambda captures, layout, path: path) as sheet:
                found = bodies.check({'name': 'x'}, layout, root / 'check', 'game', run=True, wait=60)
                self.assertEqual(sheet.call_args.args[0], found['evidence']['captures'][:2])
                built.assert_called_once()
                self.assertEqual(built.call_args.args[2:], (root / 'check', 'game'))
                waited.assert_called_once_with(60)
                self.assertEqual((asked['until'], asked['timeout'], asked['tolerate']), ('icons-done', 8.0 + 4 * 5.0 + 300 + 2 * 5.0, True))
                self.assertEqual((found['evidence']['missed'], found['evidence']['retries']), ([], []))
                self.assertEqual((root / 'check' / 'icon.png').read_bytes(), b'2')
                self.assertTrue((root / 'check' / 'evidence.json').is_file())
                with self.assertRaisesRegex(ValueError, 'no time to capture'):  # asked before the folder is made
                    bodies.check({'name': 'x', 'hold': 2.0}, layout, root / 'short', 'game', run=True)
                self.assertFalse((root / 'short').exists())
                with self.assertRaisesRegex(ValueError, 'fresh folder'):
                    bodies.check({'name': 'x'}, layout, root / 'check', 'game')
                self.assertNotIn('evidence', bodies.check({'name': 'x'}, layout, root / 'built', 'game'))

    def test_shots_missed_are_looked_at_again_by_themselves(self):
        heights = {body: 1.0 for body in registry.BODIES}
        with mock.patch.object(bodies, 'statures', return_value=heights):
            document, layout = bodies.check_spec(list(registry.BODIES), ['chest'], 6020, [], 'pack', hold=5.0)
        count = len(layout['labels'])
        # the shots of two actors far apart in the whole check, and the item: side by side when looked at again
        again, part = bodies.subset(document, layout, [3, 101, 102, count])
        self.assertEqual(part, {'labels': [layout['labels'][number] for number in (3, 101, 102)], 'columns': layout['columns'], 'icons': True})
        self.assertEqual([actor['label'] for actor in again['actors']], ['pmh0, standing', 'pme2, arms up', 'icon host'])
        self.assertEqual([actor['position'] for actor in again['actors'][:2]], [bodies.place(0), bodies.place(1)])
        self.assertEqual([(shot['actor'], shot['distance']) for shot in again['shots']],
                         [(0, document['shots'][3]['distance']), (1, document['shots'][101]['distance']), (1, document['shots'][102]['distance'])])
        self.assertIn('shot=3 target=item', again['scripts']['ak_icons'])
        self.assertEqual(again['hold'], 2 * document['hold'])  # twice the time on each: these are the shots a slow machine lost
        self.assertNotIn(f'shot={count} target=item', again['scripts']['ak_icons'])
        plain, without = bodies.subset(document, layout, [5])
        self.assertEqual((without['icons'], set(plain['scripts']), len(plain['actors'])), (False, {'ak_pose'}, 1))
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            small = {'labels': ['a', 'b', 'c'], 'columns': 3, 'icons': True}
            spec = {**document, 'shots': document['shots'][:3]}
            spec['scripts'] = {**spec['scripts'], 'ak_icons': spec['scripts']['ak_icons'].replace(f'shot={count} target=item', 'shot=3 target=item')}
            runs, first = [], [0, 2]

            def ran(nwn_root, given, captures, **options):
                """The whole check misses shots 1 and 3 (the item); the first look again misses the item once more."""
                runs.append(Path(captures).parent.name)
                taken = {1: first, 2: [0], 3: [0]}[len(runs)]
                if taken:  # as the driver does: no folder where nothing was captured
                    Path(captures).mkdir(parents=True)
                for number in taken:
                    (Path(captures) / f'shot-{number:02d}.png').write_bytes(f'{len(runs)}:{number}'.encode())
                wanted = given['shots'] + (1 if options['until'] == 'icons-done' else 0)
                return {'lines': [f'run {len(runs)}'], 'captures': [str(Path(captures) / f'shot-{number:02d}.png') for number in taken],
                        'missed': [number for number in range(wanted) if number not in taken]}
            built = lambda document, layout, output, nwn_root: {'module': 'm', 'shots': len(document['shots']), 'start': 8.0, 'hold': 5.0}
            with mock.patch.object(poses, 'build', side_effect=built), mock.patch.object(client, 'run', side_effect=ran), \
                    mock.patch.object(poses, 'sheet', side_effect=lambda captures, layout, path: path) as sheet:
                found = bodies.check(spec, small, root / 'check', 'game', run=True)
                evidence = found['evidence']
                self.assertEqual(runs, ['check', 'retry-1', 'retry-2'])
                self.assertEqual(evidence['retries'], [{'shots': [1, 3], 'lines': ['run 2'], 'missed': [3]}, {'shots': [3], 'lines': ['run 3'], 'missed': []}])
                self.assertEqual([Path(path).name for path in evidence['captures']], ['shot-00.png', 'shot-01.png', 'shot-02.png', 'shot-03.png'])
                self.assertEqual([Path(path).read_bytes() for path in evidence['captures']], [b'1:0', b'2:0', b'1:2', b'3:0'])
                self.assertEqual(((root / 'check' / 'icon.png').read_bytes(), len(sheet.call_args.args[0]), evidence['missed']), (b'3:0', 3, []))
                runs.clear()  # looked at again as often as asked, and no more: what is still missed is an error, the evidence kept
                with self.assertRaisesRegex(ValueError, 'Shots 3 were not captured in 1 more looks'):
                    bodies.check(spec, small, root / 'once', 'game', run=True, retries=1)
                self.assertEqual(json.loads((root / 'once' / 'evidence.json').read_text(encoding='utf-8'))['missed'], [3])
                runs.clear(); first.clear()  # a whole check that captured nothing leaves no folder for the retries' captures: it is made
                with self.assertRaisesRegex(ValueError, 'were not captured'):
                    bodies.check(spec, small, root / 'none', 'game', run=True)
                self.assertEqual(sorted(path.name for path in (root / 'none' / 'captures').iterdir()), ['shot-00.png', 'shot-01.png'])  # one shot from each look


if __name__ == '__main__':
    unittest.main()
