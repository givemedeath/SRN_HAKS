"""Work-count and boundary regressions, without timing-dependent assertions."""
import ast
from concurrent.futures import ThreadPoolExecutor
import hashlib
import os
from pathlib import Path
import tempfile
import types
import sys
import threading
import unittest
from unittest.mock import patch

from headkit.common import pin,verify
from headkit.comfy_nodes import source_snapshot as snapshot
from headkit.comfy_nodes.verification import CURRENT_PASS,HEAVY_VERIFICATION_LOCK,VerificationPass,verification_pass


class VerificationPerformanceTests(unittest.TestCase):
    def test_one_read_per_pass_conflicting_pins_and_fresh_next_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'source.py';path.write_bytes(b'VALUE=1\n')
            expected=pin(path);before=path.stat()
            with verification_pass('dispatch') as session:
                verify([expected,expected]);verify([expected]);self.assertEqual(pin(path),expected)
                self.assertEqual(session.counts['filesHashed'],1)
                self.assertEqual(session.counts['bytesHashed'],len(b'VALUE=1\n'))
                with self.assertRaisesRegex(ValueError,'Stale file pin'):
                    verify([expected,{**expected,'sha256':'0'*64}])
            self.assertTrue(session.closed);self.assertFalse(session.sources);self.assertFalse(session.hashes)
            path.write_bytes(b'VALUE=2\n');os.utime(path,ns=(before.st_atime_ns,before.st_mtime_ns))
            with verification_pass('completion'):
                with self.assertRaisesRegex(ValueError,'Stale file pin'):verify([expected])

    def test_nested_pass_is_fresh_and_exception_releases_storage(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'source.py';path.write_bytes(b'A=1\n')
            with verification_pass('outer') as outer:
                first=outer.source(path)
                try:
                    with verification_pass('inner') as inner:
                        path.write_bytes(b'A=2\n')
                        self.assertNotEqual(inner.source(path),first)
                        raise RuntimeError('fixture')
                except RuntimeError:pass
                self.assertIs(CURRENT_PASS.get(),outer)
                self.assertTrue(inner.closed);self.assertFalse(inner.sources)
            self.assertIsNone(CURRENT_PASS.get())

    def test_large_binaries_stream_and_do_not_enter_source_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'checkpoint.bin';path.write_bytes(b'x'*(3*1024*1024))
            with verification_pass('binary') as session:
                self.assertEqual(session.hash(path,retain_source=True),hashlib.sha256(path.read_bytes()).hexdigest())
                self.assertFalse(session.sources)
                self.assertEqual(session.counts['bytesHashed'],3*1024*1024)

    def test_parallel_hashes_share_only_the_explicit_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'source.py';path.write_bytes(b'x'*1024*1024)
            with verification_pass('parallel') as session:
                with ThreadPoolExecutor(max_workers=4) as pool:
                    hashes=list(pool.map(session.hash,[path]*16))
                self.assertEqual(len(set(hashes)),1)
                self.assertEqual(session.counts['filesHashed'],1)
                self.assertEqual(session.counts['bytesHashed'],1024*1024)

    def test_oversized_source_rechecks_uncached_read_against_verified_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'source.py';path.write_bytes(b'#'+b'x'*(1024*1024))
            with verification_pass('large-source') as session:
                session.hash(path,retain_source=True)
                self.assertFalse(session.sources)
                path.write_bytes(b'#'+b'y'*(1024*1024))
                with self.assertRaisesRegex(ValueError,'changed within'):session.source(path)

    def test_instrumentation_failure_is_explicit_and_does_not_change_identity(self):
        with patch('headkit.comfy_nodes.verification.resident_bytes',return_value=None):
            session=VerificationPass('metrics')
            with self.assertRaises(ValueError):
                with session.phase('failure'):raise ValueError('fixture')
            report=session.report()
            self.assertFalse(report['phases'][0]['success'])
            self.assertIsNone(report['phases'][0]['sampledPeakRssBytes'])
            session.close()

    def test_heavy_pass_gate_serializes_concurrent_requests(self):
        started=threading.Event();finished=threading.Event()
        def request():
            started.set()
            with HEAVY_VERIFICATION_LOCK:finished.set()
        with HEAVY_VERIFICATION_LOCK:
            thread=threading.Thread(target=request);thread.start()
            self.assertTrue(started.wait(2));self.assertFalse(finished.is_set())
        thread.join(2);self.assertTrue(finished.is_set())

    def test_source_inventory_and_loaded_analysis_share_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for name in ('main.py','execution.py','nodes.py','server.py','folder_paths.py',
                         'comfy/model.py','nodes_trellis2.py','flexgemm.py','kernel.pyd'):
                path=root/name;path.parent.mkdir(exist_ok=True);path.write_text('# fixture\n')
            path=root/'comfy/model.py'
            source=('class Model:\n    def __init__(self,mode):\n        self.mode=mode\n'
                    '        if self.mode: self.setting=1\n        else: self.setting=2\n'
                    'instances=[Model(i%2) for i in range(50)]\n')
            path.write_text(source)
            module=types.ModuleType('fixture');module.__file__=str(path)
            exec(compile(source,str(path),'exec'),vars(module))
            # Prewarm OS metrics outside the deliberately isolated module graph.
            with verification_pass('measured') as session:
                with patch.dict(sys.modules,{'fixture':module},clear=True):
                    inventory=snapshot.capture_inventory(root,[root]);snapshot.loaded_source_code([root])
                self.assertEqual(session.counts['filesHashed'],len(inventory['files']))
                self.assertEqual(session.counts['astParses'],1)
                self.assertEqual(session.counts['constructorIndexes'],1)
                self.assertEqual(session.counts['retainedInstances'],50)

    def test_conditional_selection_preserves_shared_ast(self):
        tree=ast.parse('if mode:\n    pending.setting=1\nelse:\n    pending.setting=2\n')
        original=ast.dump(tree,include_attributes=True)
        for mode in (True,False,True):
            selected=snapshot._conditional_statements(tree.body,{'mode':mode})
            self.assertEqual(list(snapshot._source_attribute_literals(selected))[0][1],['int',1 if mode else 2])
            self.assertEqual(ast.dump(tree,include_attributes=True),original)

    def test_startup_proven_state_streams_with_one_analysis_and_no_retained_objects(self):
        with tempfile.TemporaryDirectory() as directory:
            # Startup proof is keyed by resolved paths; temp may be an 8.3 alias on Windows runners.
            path=Path(directory).resolve()/'model.py'
            source=('SCALE=1\nclass Model:\n    RATE=3\n    def __init__(self,mode):\n'
                    '        self.mode=mode\n        if self.mode: self.setting=1\n        else: self.setting=2\n'
                    'def callback(factory=object(), mode=1): return mode\ninstances=[Model(i%2) for i in range(50)]\n'
                    'instances[0].setting=2\n')
            path.write_text(source);module=types.ModuleType('fixture');module.__file__=str(path)
            exec(compile(source,str(path),'exec'),vars(module))
            proof={path:snapshot._code_hash(compile(source,str(path),'exec',dont_inherit=True,optimize=sys.flags.optimize))}
            opaque=module.callback.__defaults__[0];real_signature=snapshot._literal_value_signature
            def signature(value):
                self.assertIsNot(value,opaque,'Opaque factory results must not be fingerprinted')
                return real_signature(value)
            with patch.object(snapshot,'_startup_execution_proof',return_value=proof), \
                 patch.object(snapshot,'_literal_value_signature',side_effect=signature), \
                 patch.object(snapshot,'_source_function_literals',wraps=snapshot._source_function_literals) as functions:
                with verification_pass('proven-literals') as session:
                    with patch.dict(sys.modules,{'fixture':module},clear=True):snapshot.loaded_source_code([directory])
                    self.assertEqual(session.counts['filesHashed'],1)
                    self.assertEqual(session.counts['astParses'],1)
                    self.assertEqual(session.counts['constructorIndexes'],1)
                    self.assertEqual(session.counts['retainedInstances'],0)
                    self.assertEqual(session.counts['retainedFunctions'],0)
                    functions.assert_called_once()
                module.instances[0].setting=999
                with patch.dict(sys.modules,{'fixture':module},clear=True):
                    with self.assertRaisesRegex(ValueError,'instance attributes'):snapshot.loaded_source_code([directory])

    def test_bytecode_and_conditional_state_are_rechecked_after_warm_analysis(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'model.py';source='def callback(): return 1\n'
            path.write_text(source);module=types.ModuleType('fixture');module.__file__=str(path)
            exec(compile(source,str(path),'exec'),vars(module))
            with patch.dict(sys.modules,{'fixture':module},clear=True):
                snapshot.loaded_source_code([directory])
                module.callback.__code__=module.callback.__code__.replace(co_consts=(None,2))
                with self.assertRaisesRegex(ValueError,'Python code differs'):
                    snapshot.loaded_source_code([directory])


if __name__=='__main__':unittest.main()
