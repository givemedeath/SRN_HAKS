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
