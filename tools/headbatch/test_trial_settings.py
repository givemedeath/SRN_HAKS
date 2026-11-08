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


class TrialInspectionTests(unittest.TestCase):
    def test_measured_race_view_overrides_without_changing_defaults_or_other_races(self):
        from types import SimpleNamespace
        from trials import inspection_view
        data={'trialInspection':{'dwarf':{'height':{'pmd0':1.23},'distance':.75}}}
        w=SimpleNamespace(data=data)
        view=inspection_view(w,'dwarf'); self.assertEqual(view,data['trialInspection']['dwarf'])
        view['height']['pmd0']=2
        self.assertEqual(data['trialInspection']['dwarf']['height']['pmd0'],1.23)
        self.assertEqual(inspection_view(w,'troll')['height']['pmg0'],2.52)
        self.assertEqual(inspection_view(w,'elf'),{})

    def test_rejects_invalid_or_cross_race_framing(self):
        from types import SimpleNamespace
        from trials import inspection_view
        from guards import Refused
        for view in [{'height':{'pmg0':1.23}},{'height':{'pmd0':True}},
                     {'height':{'pmd0':float('nan')}},{'distance':.1},{'distance':float('inf')},
                     {'height':[]},{'camera':'guess'}]:
            with self.subTest(view=view),self.assertRaises(Refused):
                inspection_view(SimpleNamespace(data={'trialInspection':{'dwarf':view}}),'dwarf')


class TrialBuildLeaseTests(unittest.TestCase):
    def test_failed_ram_admission_starts_no_freeze_or_compiler(self):
        from unittest.mock import patch,MagicMock
        import trials
        lease=MagicMock();lease.__enter__.side_effect=RuntimeError('RAM floor')
        with patch.object(trials.launcher,'cpu_slot',return_value=lease),patch.object(trials,'_build') as worker:
            with self.assertRaisesRegex(RuntimeError,'RAM floor'):trials.build(object(),'dwarf','1')
            worker.assert_not_called()

    def test_build_failure_releases_the_lane(self):
        from unittest.mock import patch,MagicMock
        import trials
        lease=MagicMock()
        with patch.object(trials.launcher,'cpu_slot',return_value=lease),patch.object(trials,'_build',side_effect=ValueError('compile failed')):
            with self.assertRaisesRegex(ValueError,'compile failed'):trials.build(object(),'dwarf','1')
            lease.__exit__.assert_called_once()
