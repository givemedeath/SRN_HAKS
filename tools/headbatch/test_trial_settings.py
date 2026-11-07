import tempfile
import tomllib
import unittest
from pathlib import Path
from trials import inspection_settings


class TrialCaptureSettingsTests(unittest.TestCase):
    def test_preserves_source_and_embedded_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, dest = [Path(tmp)/name for name in ('base.tml', 'trial.tml')]
            for initial in ('', '[ui]', '[ui]\nscale=1.0\nmouseover-feedback = true\n[other]\ntargeting-feedback-mode = 2\n',
                            '[ui]\ntargeting-feedback-mode=2\n["~~schema".binds."ui.mouseover-feedback"]\ndefault=true\n'):
                source.write_text(initial, encoding='utf8')
                inspection_settings(source, dest)
                expected = tomllib.loads(initial)
                expected.setdefault('ui', {}).update({'mouseover-feedback': False, 'targeting-feedback-mode': 0})
                self.assertEqual(tomllib.loads(dest.read_text(encoding='utf8')), expected)
                self.assertEqual(initial, source.read_text(encoding='utf8'))
