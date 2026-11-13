"""The command line routes each subcommand to its function with the arguments it was given."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from . import __main__ as cli
from . import client, registry
from . import client_fixture as fixture

EXAMPLE = Path(__file__).with_name('examples') / 'registry.json'


def run(*arguments):
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        cli.main([str(argument) for argument in arguments])
    return json.loads(output.getvalue())


class CommandLineTests(unittest.TestCase):
    def test_registry_reports_its_parts_and_writes_the_handoff(self):
        with tempfile.TemporaryDirectory() as folder:
            got = run('registry', EXAMPLE, '--publish', '--handoff', Path(folder) / 'handoff.json')
            handoff = json.loads((Path(folder) / 'handoff.json').read_text(encoding='utf-8'))
        self.assertEqual(got['parts'], len(handoff['parts']))
        self.assertEqual(handoff['kind'], registry.KIND + '-handoff')

    def test_refit_carries_kept_parts_to_another_body(self):
        with mock.patch('tools.armorkit.refit.run', return_value={'handl': {'degrees': 1.5}}) as call:
            self.assertEqual(run('refit', 'kept', 'out', '--body-pack', 'bodies', '--to', 'pfh0', '--parts', 'handl, footl'), {'handl': {'degrees': 1.5}})
        call.assert_called_once_with('kept', 'out', 'bodies', 'pmh0', 'pfh0', ['handl', 'footl'])

    def test_brief_reports_its_materials_and_writes_the_image_prompt(self):
        from . import brief
        given = {'schemaVersion': 1, 'kind': brief.KIND, 'model': 'test-outfit', 'prompt': 'An outfit. ' + brief.MARK + ' ' + brief.BUILT, 'construction': max(brief.CONSTRUCTIONS),
                 'materials': [{'name': 'fabric', 'kind': 'cloth', 'colour': [128, 128, 128], 'look': 'GREY cloth', 'wears': 'the shirt.'},
                               {'name': 'plates', 'kind': 'metal', 'colour': [150, 180, 220], 'look': 'PALE BLUE plastic', 'wears': 'the guards.'}]}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'brief.json'
            path.write_text(json.dumps(given), encoding='utf-8')
            self.assertEqual(run('brief', path), {'model': 'test-outfit', 'materials': {'fabric': 'cloth', 'plates': 'metal'}, 'pads': [], 'sealed': None})
            sealed = Path(folder) / 'out'
            run('brief', path, '--seal', sealed)
            self.assertEqual((sealed / 'PROMPT.txt').read_text(encoding='utf-8'), brief.prompt(given) + '\n')
            self.assertEqual(brief.sealed(sealed)[0], given)
            # an image made from the folder's prompt by another route is registered, and is then let through
            image, stray = sealed / 'image.png', Path(folder) / 'stray.png'
            image.write_bytes(b'made from the prompt'); stray.write_bytes(b'from somewhere else')
            self.assertEqual(run('register', sealed, image), {'registered': ['image.png']})
            self.assertEqual(run('admit', image, '--root', folder), {'model': 'test-outfit', 'folder': str(sealed)})
            with self.assertRaises(ValueError):
                run('admit', stray, '--root', folder)
            given['materials'][1]['colour'] = [135, 135, 140]  # drawn too alike: refused, and nothing is written
            path.write_text(json.dumps(given), encoding='utf-8')
            with self.assertRaises(ValueError):
                run('brief', path, '--seal', Path(folder) / 'again')
            self.assertFalse((Path(folder) / 'again').exists())

    def test_image_makes_reference_images_from_the_brief_it_is_given(self):
        from . import reference
        calls = {}
        with mock.patch.object(reference, 'generate', lambda *given: calls.setdefault('given', given) and [Path('run-1') / 'image-0.png']):
            got = run('image', 'brief.json', 'folder', '--seed', 7, '--reference', 'earlier.png')
        self.assertEqual(calls['given'], ('brief.json', 'folder', 7, 1, ['earlier.png'], 'http://127.0.0.1:8188', 'flux2-turbo-v1', 1800))
        self.assertEqual(got, {'images': [str(Path('run-1') / 'image-0.png')]})

    def test_generate_routes_each_stage_with_what_it_needs(self):
        from . import generate
        calls = []
        stage = lambda name: (lambda *given: calls.append((name, given)) or {'folder': name + '-1', 'status': 'success'})
        url = 'http://127.0.0.1:8188'
        with mock.patch.object(generate, 'calibrate', stage('calibrate')), mock.patch.object(generate, 'geometry', stage('geometry')), \
                mock.patch.object(generate, 'appearance', stage('appearance')), mock.patch.object(generate, 'export', stage('export')):
            self.assertEqual(run('generate', 'calibrate', 'work', 'outfit', 'image.png', '--models', 'models')['folder'], 'calibrate-1')
            run('generate', 'geometry', 'work', 'outfit', 'image.png', '--models', 'models', '--fov', 36.5)
            run('generate', 'appearance', 'work', 'outfit', 'image.png', '--models', 'models', '--fov', 36.5, '--shape', 'shape.npz')
            run('generate', 'export', 'work', 'outfit', 'mesh.glb', '--faces', 12000, '--fill', 0.5)
            for missing in (('geometry', 'work', 'outfit', 'image.png', '--models', 'models'),  # no field of view
                            ('calibrate', 'work', 'outfit', 'image.png'), ('export', 'work', 'outfit', 'mesh.glb'),
                            ('appearance', 'work', 'outfit', 'image.png', '--models', 'models', '--fov', 36.5)):
                with self.assertRaises(ValueError):
                    run('generate', *missing)
        self.assertEqual(calls, [('calibrate', ('work', 'outfit', 'image.png', 'models', url)),
                                 ('geometry', ('work', 'outfit', 'image.png', 36.5, 'models', url)),
                                 ('appearance', ('work', 'outfit', 'image.png', 36.5, 'shape.npz', 'models', url)),
                                 ('export', ('work', 'outfit', 'mesh.glb', 12000, 0.5, url))])

    def test_bake_routes_a_fresh_bake_and_a_second_tint_and_fails_on_a_gate(self):
        from . import bake
        calls, brief_file = [], Path(__file__).with_name('briefs') / 'corpsec-siteguard-male-2.json'
        report = lambda passed: (lambda document, output, pack, number, **given: calls.append((document['model'], output, pack, number, given))
                                 or {'model': document['model'], 'number': number, 'models': {}, 'gates': {'passed': passed, 'failures': []}})
        with mock.patch.object(bake, 'run', report(True)), mock.patch.object(cli, 'layout_library', lambda folder: 'library of ' + folder):
            got = run('bake', brief_file, 'out', '--number', 332, '--body-pack', 'bodies', '--mesh', 'mesh.glb', '--colours', 'field.npz', '--raw', 'raw.glb',
                      '--xatlas', 'layout', '--kept', 'kept', '--pack', 'srn_body', '--pack', 'srn_armor')
            run('bake', brief_file, 'out', '--number', 332, '--body-pack', 'bodies', '--kept', 'kept', '--tier', 1)
            for wrong in (('--mesh', 'mesh.glb'), ('--mesh', 'mesh.glb', '--colours', 'field.npz', '--raw', 'raw.glb'), (),
                          ('--kept', 'kept', '--xatlas', 'layout')):  # half a bake, nothing to bake or tint, and both at once
                with self.assertRaises(ValueError):
                    run('bake', brief_file, 'out', '--number', 332, '--body-pack', 'bodies', *wrong)
        self.assertEqual(got['gates']['passed'], True)
        self.assertEqual([call[:4] for call in calls], [('corpsec-siteguard-male', 'out', 'bodies', 332)] * 2)
        fresh, again = (call[4] for call in calls)
        self.assertEqual((fresh['mesh'], fresh['colours'], fresh['raw'], fresh['xatlas'], fresh['kept'], fresh['packs'], fresh['tier']),
                         ('mesh.glb', 'field.npz', 'raw.glb', 'library of layout', 'kept', ['srn_body', 'srn_armor'], 2))
        self.assertEqual((again['mesh'], again['xatlas'], again['kept'], again['tier'], again['game']), (None, None, 'kept', 1, None))
        with mock.patch.object(bake, 'run', report(False)), self.assertRaises(SystemExit) as stopped:
            run('bake', brief_file, 'out', '--number', 332, '--body-pack', 'bodies', '--kept', 'kept')
        self.assertEqual(stopped.exception.code, 1)

    def fixture_run(self, *flags):
        """Run the fixture command with the builder and the client replaced; return what each was called with."""
        calls = {}
        with tempfile.TemporaryDirectory() as folder:
            spec = Path(folder) / 'spec.json'
            spec.write_text(json.dumps({'name': 'ak_t', 'actors': []}), encoding='utf-8')
            with mock.patch.object(fixture, 'build', lambda spec, output, root: calls.setdefault('build', {'shots': 0})), \
                    mock.patch.object(client, 'run', lambda root, record, captures, **options: calls.setdefault('run', options)):
                run('fixture', '--spec', spec, '--output', Path(folder) / 'out', '--nwn-root', 'game', *flags)
        return calls

    def test_fixture_builds_without_starting_the_game_unless_asked(self):
        """`--run` once shared its name with the handler: the game always started, and the flag itself crashed."""
        self.assertEqual(set(self.fixture_run()), {'build'})
        self.assertEqual(self.fixture_run('--run')['run'], {'timeout': None, 'settle': 1.5})
        self.assertEqual(self.fixture_run('--run', '--timeout', '600', '--settle', '1.2')['run'], {'timeout': 600.0, 'settle': 1.2})

    def test_a_split_runs_again_on_what_a_bake_kept_and_fails_on_a_gate(self):
        from . import bake
        calls = {}
        report = lambda failures: (lambda capture: calls.setdefault('capture', capture) and ({'chest': {}}, {'failures': failures}))
        with mock.patch.object(bake, 'resplit', report([])), mock.patch.object(bake, 'keep_parts', lambda parts, path: calls.setdefault('parts', path)):
            self.assertEqual(run('split', 'kept.npz', '--output', 'parts.npz'), {'failures': []})
        self.assertEqual((calls['capture'], calls['parts']), ('kept.npz', 'parts.npz'))
        with mock.patch.object(bake, 'resplit', report(['chest: short'])), self.assertRaises(SystemExit) as stopped:
            run('split', 'kept.npz')
        self.assertEqual(stopped.exception.code, 1)
        given = []
        with mock.patch.object(bake, 'run', lambda *args, **options: given.append(options) or {'gates': {'passed': True}}), \
                mock.patch.object(cli, 'layout_library', lambda folder: folder):
            run('bake', Path(__file__).with_name('briefs') / 'corpsec-siteguard-male-2.json', 'out', '--number', 332, '--body-pack', 'bodies',
                '--mesh', 'm', '--colours', 'c', '--raw', 'r', '--xatlas', 'x', '--capture', 'split.npz')
        self.assertEqual(given[0]['capture'], 'split.npz')

    def test_render_and_poses_route_their_options(self):
        from . import poses, view
        calls = {}
        with mock.patch.object(view, 'views', lambda *given: calls.setdefault('views', given) and {'output': 'sheet.png'}):
            run('render', 'parts.npz', 'sheet.png', '--body-pack', 'bodies', '--animations', 'stock', '--clip', 'conjure2', '--views', 'left, front')
            run('render', 'kept', 'rest.png', '--body-pack', 'bodies', '--focus', 'body')
        self.assertEqual(calls['views'], ('parts.npz', 'sheet.png', 'bodies', 'pmh0', ['stock'], 'conjure2', 0.5, 'shoulders', ('left', 'front'), 520))
        layout = {'labels': [], 'columns': 4}
        steps = []
        with mock.patch.object(poses, 'spec', lambda *given, **options: steps.append(('spec', given, options)) or ({'name': 'ak_poses'}, layout)), \
                mock.patch.object(poses, 'build', lambda *given: steps.append(('build', given)) or {'module': 'm', 'shots': 0}), \
                mock.patch.object(poses, 'run', lambda *given, **options: steps.append(('run', given, options)) or {'captures': []}), \
                mock.patch.object(client, 'wait_free', lambda seconds: steps.append(('wait', seconds))):
            got = run('poses', 'bake', 'check', '--nwn-root', 'game', '--stock', 'stock', '--hak', 'a.hak', '--hak', 'b.hak',
                      '--preset', 'shoulders', '--without', 'shoulder', '--colours', '{"cloth1": 10}', '--run', '--wait', 600)
            run('poses', 'bake', 'check', '--nwn-root', 'game', '--stock', 'stock', '--hak', 'a.hak')
        self.assertEqual(got, {'module': 'm', 'shots': 0, 'evidence': {'captures': []}})
        self.assertEqual(steps[0], ('spec', ('bake', 'check', 'stock', ['a.hak', 'b.hak']),
                                    {'tlk': None, 'preset': 'shoulders', 'without': ['shoulder'], 'colours': {'cloth1': 10}}))
        self.assertEqual([step[0] for step in steps], ['spec', 'build', 'wait', 'run', 'spec', 'build'])  # waits only to run, runs only when asked
        self.assertEqual((steps[3][1][0], steps[3][1][1]['module'], *steps[3][1][2:], steps[3][2]), ('game', 'm', layout, 'check', {'settle': 1.2}))

    def test_measuring_seams_needs_the_animation_models(self):
        for flags in ((), ('--only', 'seams')):
            with self.assertRaisesRegex(ValueError, 'needs --supermodels'):
                run('measure', '--body-pack', 'body', '--head-pack', 'head', '--output', 'out', *flags)

    def test_tables_are_written_only_after_every_table_passes(self):
        with tempfile.TemporaryDirectory() as folder:
            stock = Path(folder) / 'stock'
            stock.mkdir()
            for table in registry.TABLES:
                rows = 39 if table == 'parts_robe' else 201
                columns = ['COSTMODIFIER', 'ACBONUS'] + (['HIDE' + name for name in registry.ROBE_HIDES] if table == 'parts_robe' else [])
                lines = ['2DA V2.0', '', '    ' + ' '.join(columns)] + [f'{i} ' + ' '.join('0' for _ in columns) for i in range(rows)]
                (stock / (table + '.2da')).write_bytes(('\r\n'.join(lines) + '\r\n').encode('cp1252'))
            report = run('tables', EXAMPLE, '--stock', stock, '--output', Path(folder) / 'made')
            self.assertEqual({row['table'] for row in report}, set(registry.TABLES))
            self.assertEqual(len(list((Path(folder) / 'made').glob('*.2da'))), 12)
            (stock / 'parts_neck.2da').write_bytes(b'2DA V2.0\r\n\r\n   COSTMODIFIER ACBONUS\r\n0 0 0\r\n')
            with self.assertRaisesRegex(ValueError, 'expected 201 stock rows'):
                run('tables', EXAMPLE, '--stock', stock, '--output', Path(folder) / 'again')
            self.assertFalse((Path(folder) / 'again').exists())


if __name__ == '__main__':
    unittest.main()
