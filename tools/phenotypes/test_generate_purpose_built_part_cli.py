"""Prevent accidental preparation of the wrong part without network activity."""
import contextlib
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import generate_purpose_built_part as generator


class ExplicitPartConfiguration(unittest.TestCase):
    def test_prepare_without_configuration_fails_before_service_access(self):
        with patch.object(sys, 'argv', ['generator', 'prepare', '--output', 'fresh',
                                      '--views-dir', 'views']), \
                patch.object(generator, 'prepare') as prepare, \
                contextlib.redirect_stderr(io.StringIO()) as error:
            with self.assertRaises(SystemExit) as exit_status:
                generator.main()
        self.assertEqual(exit_status.exception.code, 2)
        self.assertIn('explicit --config', error.getvalue())
        prepare.assert_not_called()

    def test_explicit_configuration_reaches_prepare_unchanged(self):
        with patch.object(sys, 'argv', ['generator', 'prepare', '--output', 'fresh',
                                      '--views-dir', 'views', '--config', 'shin.json']), \
                patch.object(generator, 'prepare') as prepare:
            generator.main()
        self.assertEqual(prepare.call_args.args[0].config, Path('shin.json'))

    def test_collection_uses_receipts_without_a_new_configuration(self):
        with patch.object(sys, 'argv', ['generator', 'status', '--output', 'existing']), \
                patch.object(generator, 'status') as status:
            generator.main()
        self.assertIsNone(status.call_args.args[0].config)


if __name__ == '__main__':
    unittest.main()
