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
                graphics=expected.setdefault('graphics', {})
                graphics['framelimiter']={'enabled':True, 'foreground':{'target-fps':30},
                    'background':{'target-fps':10}, 'non-interactive':{'target-fps':10}}
                graphics['window']={'mode':'windowed','windowed':{'borderless':False,'width':1920,'height':1080}}
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


class ClientSafetyTests(unittest.TestCase):
    def test_caps_uncapped_large_window_without_touching_personal_profile_or_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            source,dest=Path(tmp)/'personal.tml',Path(tmp)/'private.tml'
            raw=('[graphics.framelimiter]\nenabled=false\n[graphics.window]\nmode="fullscreen"\n'
                 '[graphics.window.windowed]\nwidth=3840\nheight=2071\nx=22\n'
                 '["~~schema".graphics.framelimiter]\ndefault=false\n')
            source.write_text(raw,encoding='utf8')
            inspection_settings(source,dest)
            result=tomllib.loads(dest.read_text())
            self.assertTrue(result['graphics']['framelimiter']['enabled'])
            self.assertEqual(result['graphics']['framelimiter']['foreground']['target-fps'],30)
            self.assertEqual(result['graphics']['window']['windowed'],{'width':1920,'height':1080,'borderless':False,'x':22})
            self.assertEqual(source.read_text(),raw)
            self.assertEqual(result['~~schema'],tomllib.loads(raw)['~~schema'])
            inspection_settings(dest,dest)
            self.assertEqual(result,tomllib.loads(dest.read_text()))

    def test_client_holds_all_lanes_and_gpu_until_exit_and_releases_on_failure(self):
        from contextlib import contextmanager
        from types import SimpleNamespace
        from unittest.mock import patch
        import client_trial
        events=[]
        @contextmanager
        def cpu(paths):
            path=paths()[0];events.append(('take',path.name))
            try:yield
            finally:events.append(('drop',path.name))
        @contextmanager
        def gpu(w):
            events.append(('take','gpu'))
            try:yield
            finally:events.append(('drop','gpu'))
        w=SimpleNamespace(locks=Path('locks'),ram_gates=lambda:{1:6,2:8,3:10})
        with patch.object(client_trial.launcher,'lock',cpu),patch.object(client_trial.launcher,'gpu_lock',gpu):
            with self.assertRaisesRegex(RuntimeError,'client'):
                with client_trial.exclusive(w):
                    events.append(('running','client'))
                    raise RuntimeError('client')
        self.assertEqual(events,[('take','cpu-1'),('take','cpu-2'),('take','cpu-3'),('take','gpu'),
                                 ('running','client'),('drop','gpu'),('drop','cpu-3'),('drop','cpu-2'),('drop','cpu-1')])

    def test_memory_failure_stops_only_the_owned_process(self):
        from unittest.mock import MagicMock
        from client_trial import supervise
        process=MagicMock()
        process.poll.side_effect=[None,None,None,0]
        process.returncode=1
        budget=MagicMock();budget.check.side_effect=RuntimeError('Free RAM below floor')
        result=supervise(process,budget,MagicMock(),sleep=lambda _:None)
        self.assertIn('RAM',result['stopReason'])
        process.terminate.assert_called_once()
        process.wait.assert_called_once_with(timeout=10)

    def test_natural_exit_does_not_terminate(self):
        from unittest.mock import MagicMock
        from client_trial import supervise
        process=MagicMock();process.poll.return_value=0;process.returncode=0
        result=supervise(process,MagicMock(),MagicMock())
        self.assertIsNone(result['stopReason'])
        process.terminate.assert_not_called()

    def test_manifest_cannot_escape_private_userdir(self):
        import json
        from client_trial import runtime_files
        from guards import Refused
        with tempfile.TemporaryDirectory() as tmp:
            trial=Path(tmp)/'trial';trial.mkdir()
            (Path(tmp)/'outside').write_text('asset')
            (trial/'runtime-manifest.json').write_text(json.dumps({'kind':'srn-head-trial-client-view',
                'module':'sr_test','files':[{'relativePath':'../outside','sha256':'x'}]}))
            with self.assertRaisesRegex(Refused,'escapes'):runtime_files(trial)


    def test_stop_and_deadline_terminate_only_the_owned_child(self):
        from unittest.mock import MagicMock
        from client_trial import supervise
        for stop_requested in (True,False):
            child=MagicMock();child.poll.return_value=None;child.returncode=1
            stop=MagicMock();stop.exists.return_value=stop_requested
            times=iter((0,2,3))
            result=supervise(child,MagicMock(),stop,seconds=1,sleep=lambda _:None,clock=lambda:next(times))
            self.assertEqual(result['stopReason'],'Operator STOP' if stop_requested else 'Client QA time limit reached')
            child.terminate.assert_called_once()
            child.wait.assert_called_once()


class ClientSessionLogTests(unittest.TestCase):
    def test_archives_exact_private_log_and_refuses_overwrite(self):
        import json
        from client_trial import archive_client_log
        from guards import Refused
        from head_files import sha
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);user=root/'private';output=root/'session'
            (user/'logs').mkdir(parents=True);output.mkdir()
            source=user/'logs'/'nwclientLog1.txt';source.write_bytes(b'private inspection log')
            target=archive_client_log(user,output)
            self.assertEqual(target.read_bytes(),source.read_bytes())
            self.assertEqual(json.loads((output/'client-log.json').read_text())['sha256'],sha(source))
            source.write_bytes(b'next run')
            with self.assertRaisesRegex(Refused,'Preserve'):archive_client_log(user,output)
            self.assertEqual(target.read_bytes(),b'private inspection log')

    def test_missing_log_cannot_claim_complete_evidence(self):
        from client_trial import archive_client_log
        from guards import Refused
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(Refused,'log missing'):archive_client_log(Path(tmp),Path(tmp))


class ClientStartupFailureTests(unittest.TestCase):
    def test_receipt_failure_after_spawn_stops_owned_client_before_budget_close(self):
        import json
        from unittest.mock import patch,MagicMock
        import client_trial
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);trial=root/'trial';out=root/'out';client=root/'nwmain.exe'
            (trial/'userdir').mkdir(parents=True);out.mkdir()
            (trial/'runtime-manifest.json').write_text('{}')
            config=root/'session.json'
            config.write_text(json.dumps({'trial':str(trial),'output':str(out),'client':str(client),'gpuIndex':0}))
            child=MagicMock();running=[True];events=[]
            child.poll.side_effect=lambda:None if running[0] else 1
            child.terminate.side_effect=lambda:events.append('terminate')
            def stopped(**kwargs):running[0]=False;events.append('wait')
            child.wait.side_effect=stopped
            budget=MagicMock();budget.close.side_effect=lambda:events.append('budget-close')
            with patch.object(client_trial,'existing_clients',return_value=''), \
                 patch.object(client_trial,'runtime_files',return_value=({'module':'test'},[])), \
                 patch.object(client_trial,'Budget',return_value=budget), \
                 patch.object(client_trial.subprocess,'Popen',return_value=child), \
                 patch.object(client_trial,'write_json',side_effect=OSError('receipt write failed')), \
                 patch.object(client_trial,'archive_client_log'):
                with self.assertRaisesRegex(OSError,'receipt write failed'):client_trial.session(config)
            self.assertEqual(events,['terminate','wait','budget-close'])

    def test_forced_cleanup_waits_for_owned_child(self):
        from unittest.mock import MagicMock
        from client_trial import stop_owned
        import subprocess
        child=MagicMock();child.poll.return_value=None
        child.wait.side_effect=[subprocess.TimeoutExpired('owned',10),None]
        stop_owned(child)
        child.terminate.assert_called_once();child.kill.assert_called_once()
        self.assertEqual(child.wait.call_count,2)
