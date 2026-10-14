"""Repository migration proof rejects lookalike and incomplete doctor runs."""
import copy
import unittest
from pathlib import Path
from finalize_runtime import verify_doctor, sha

class DoctorProofTests(unittest.TestCase):
    def setUp(self):
        package = Path(__file__).resolve().parent/'phenomorpher'
        files = {str(p.resolve()):sha(p) for pattern in ('*.py','*.json') for p in package.rglob(pattern)}
        self.launch = {'command':['python','-B','-m','phenomorpher','doctor'],'frozenInputs':files}
        self.result = {'loadedPackageSources':{name:{'path':str((package/relative).resolve()),'sha256':sha(package/relative)}
            for name,relative in [('phenomorpher','__init__.py'),('phenomorpher.cli','cli.py'),
                                 ('phenomorpher.engine.measurement_workflow','engine/measurement_workflow.py')]}}

    def test_current_local_doctor_is_accepted(self):
        verify_doctor(self.launch,self.result)

    def test_lookalike_command_is_rejected(self):
        for args in (['fake.py'],['-B','-m','phenomorpher','doctor','extra'],['-m','phenomorpher','doctor']):
            launch=copy.deepcopy(self.launch);launch['command']=['python',*args]
            with self.subTest(args=args),self.assertRaisesRegex(ValueError,'command'):verify_doctor(launch,self.result)

    def test_missing_or_stale_package_input_is_rejected(self):
        for stale in (False,True):
            launch=copy.deepcopy(self.launch);path=next(iter(launch['frozenInputs']))
            if stale:launch['frozenInputs'][path]='0'*64
            else:del launch['frozenInputs'][path]
            with self.subTest(stale=stale),self.assertRaisesRegex(ValueError,'frozen'):verify_doctor(launch,self.result)

    def test_missing_or_shadowed_or_changed_loaded_source_is_rejected(self):
        for mode in ('missing','shadow','changed'):
            result=copy.deepcopy(self.result)
            if mode=='missing':del result['loadedPackageSources']['phenomorpher.cli']
            elif mode=='shadow':result['loadedPackageSources']['phenomorpher.cli']['path']=str(Path('shadow/cli.py').resolve())
            else:result['loadedPackageSources']['phenomorpher.cli']['sha256']='0'*64
            with self.subTest(mode=mode),self.assertRaises(ValueError):verify_doctor(self.launch,result)
