"""Unpaid dispatch preflight and executable/dependency provenance regressions."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from head_workflow import pin, read, write_fresh
from meshy_cli import dispatch, validate_binding
import test_head_pipeline


class MeshyDispatchTests(unittest.TestCase):
    def setUp(self):
        self.fixture=test_head_pipeline.HeadTests();self.fixture.setUp();self.root=self.fixture.root
        self.node=self.root/'node.exe';self.node.write_bytes(b'byte-pinned runtime')
        self.dependencies=self.root/'node_modules';package=self.dependencies/'meshy-cli';package.mkdir(parents=True)
        write_fresh(package/'package.json',{'name':'meshy-cli','version':'0.4.0','bin':{'meshy':'cli.js'}})
        self.entry=package/'cli.js';self.entry.write_text('console.log("mock cli")')
        dependency=self.dependencies/'dependency';dependency.mkdir();(dependency/'index.js').write_text('module.exports = {};')
        self.binding={'command':[str(self.node),str(self.entry)],'dependencyRoot':str(self.dependencies),
                      'workspace':str(self.root/'workspace'),
                      'inputs':[pin(self.node),*[pin(p) for p in sorted(self.dependencies.rglob('*')) if p.is_file()]]}
        self.request={'designId':'human-male-01','requestId':'generation','operation':'multi-image-to-3d',
                      'estimatedCredits':20,'inputs':[pin(p) for p in self.fixture.views],'payload':self.fixture.payload}

    def tearDown(self):
        self.fixture.tearDown()

    def dispatch(self, name='operation'):
        request=self.root/'request.json';binding=self.root/'binding.json'
        write_fresh(request,self.request);write_fresh(binding,self.binding)
        return dispatch(self.fixture.session,request,binding,self.root/name)

    def test_local_preflight_failures_leave_no_reservation(self):
        cases=('output-exists','payload-exists','retexture-task','missing-remesh-source','invalid-project')
        for case in cases:
            with self.subTest(case=case):
                # Independent fixtures preserve exclusive request/output creation.
                nested=MeshyDispatchTests();nested.setUp()
                try:
                    before=nested.fixture.session.events()
                    if case=='output-exists':(nested.root/'operation').mkdir()
                    elif case=='payload-exists':(nested.root/'operation-payload.json').write_text('{}')
                    elif case=='retexture-task':
                        nested.request.update(operation='retexture',payload={'input_task_id':'master','enable_original_uv':True,
                                              'enable_pbr':True,'texture_resolution':'2k'})
                    elif case=='missing-remesh-source':
                        nested.request.update(operation='remesh',payload={'topology':'triangle','target_polycount':19000,'target_formats':['glb']})
                    else:nested.binding['project']=123
                    with patch('meshy_cli.subprocess.run') as remote:
                        with self.assertRaises((ValueError,KeyError)):nested.dispatch()
                        remote.assert_not_called()
                    self.assertEqual(nested.fixture.session.events(),before)
                    self.assertEqual(nested.fixture.session.credit_used(),0)
                finally:nested.tearDown()

    def test_cli_requires_pinned_absolute_runtime_entry_and_complete_tree(self):
        validate_binding(self.binding)
        for command in (['node',str(self.entry)],[str(self.node),'npm-cli.js','exec','--package=meshy-cli@0.4.0']):
            with self.subTest(command=command),self.assertRaises(ValueError):
                validate_binding({**self.binding,'command':command})
        with self.assertRaisesRegex(ValueError,'not declared'):
            validate_binding({**self.binding,'inputs':self.binding['inputs'][1:]})
        extra=self.dependencies/'new.js';extra.write_text('new dependency')
        with self.assertRaisesRegex(ValueError,'complete offline'):validate_binding(self.binding)
        extra.unlink();self.entry.write_text('changed package payload')
        with self.assertRaisesRegex(ValueError,'Frozen input changed'):validate_binding(self.binding)

    def test_valid_dispatch_reserves_before_subprocess_and_pins_runtime(self):
        def submit(command,**kwargs):
            self.assertEqual(self.fixture.session.credit_used(),20)
            self.assertEqual(command[:2],self.binding['command'])
            self.assertNotIn('NODE_OPTIONS',kwargs['env']);self.assertNotIn('NODE_PATH',kwargs['env'])
            kwargs['stdout'].write('{"result":"task-one"}')
            return SimpleNamespace(returncode=0)
        with patch.dict('os.environ',{'NODE_OPTIONS':'--require injected.js','NODE_PATH':'unbound'}),patch('meshy_cli.subprocess.run',side_effect=submit):
            self.assertEqual(self.dispatch(),'task-one')
        reserved=next(e for e in self.fixture.session.events() if e['kind']=='reserved')
        self.assertTrue(all(p in reserved['inputs'] for p in self.binding['inputs']))
        self.assertEqual(self.fixture.session.events()[-1]['kind'],'submitted')
        self.assertEqual(read(self.root/'operation/operation.json')['exitCode'],0)

    def test_bad_binding_cannot_reserve_or_invoke(self):
        self.binding['inputs']=self.binding['inputs'][1:]
        before=self.fixture.session.events()
        with patch('meshy_cli.subprocess.run') as remote:
            with self.assertRaises(ValueError):self.dispatch()
            remote.assert_not_called()
        self.assertEqual(self.fixture.session.events(),before)


if __name__=='__main__':unittest.main()
