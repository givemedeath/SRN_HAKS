"""Exercise migrated caller paths and file receipts without running the game."""
import argparse
from contextlib import ExitStack, redirect_stdout
from io import StringIO
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import audit_pelvis_package as pelvis
import native_compile as native
import tool_runtime
from shared_tools import read_json, sha, write_json


class CallerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.repo = self.root / 'consumer'
        (self.repo / 'tools').mkdir(parents=True)
        write_json(self.repo / 'tools/shared-tools.lock.json', {'schemaVersion': 1})
        self.bank = self.root / 'durable-tools'
        self.stack = ExitStack()
        self.stack.enter_context(patch.object(tool_runtime, 'REPO', self.repo))
        self.stack.enter_context(patch.dict(os.environ, {'SRN_TOOLS_ROOT': str(self.bank)}))
        self.stack.enter_context(redirect_stdout(StringIO()))
        self.real_process = subprocess.run
        self.calls = []

    def tearDown(self):
        self.stack.close()
        self.tmp.cleanup()

    def registered(self):
        records = [read_json(path) for path in (self.bank / 'consumers').glob('*/current.json')]
        self.assertEqual(len(records), 1)
        return {row['path']: row for row in records[0]['references']}

    def compile_fixture(self, name='candidate'):
        converted = self.root / 'borrowed-worktree' / name
        (converted / 'ascii').mkdir(parents=True)
        (converted / 'resources').mkdir()
        source = converted / 'ascii/body.mdl'
        source.write_bytes(b'newmodel body\n# unchanged source\n')
        material = converted / 'resources/body.mtr'
        material.write_bytes(b'texture0 bodycolor\n')
        color = converted / 'resources/bodycolor.tga'
        color.write_bytes(b'actual material dependency')
        (converted / 'resources/unconsumed.txt').write_bytes(b'not a compiler input')
        client = self.root / 'installed-nwn-stub.exe'
        client.write_bytes(b'non-executable compiler fixture')
        userdir = self.root / ('compiler-' + name)
        return converted, source, [material, color], client, userdir

    def compile(self, fixture, *, donor=None, mutate=None, materials=True):
        converted, source, dependencies, client, userdir = fixture
        args = ['native_compile.py', '--client', str(client), '--user-directory', str(userdir),
                '--converted', str(converted)]
        if donor: args += ['--reuse-from', str(donor)]
        if not materials: args += ['--without-material-resources']

        def dispatch(command, **kwargs):
            if command[0] != str(client):
                return self.real_process(command, **kwargs)
            self.calls.append(command)
            registered = self.registered()
            for path in [source, *(dependencies if materials else [])]:
                self.assertEqual(registered[str(path)]['sha256'], sha(path))
            self.assertNotIn(str(converted), registered)
            (userdir / 'modelcompiler/body.mdl').write_bytes(b'\0\0\0\0compiled fixture')
            if mutate: mutate()
            return subprocess.CompletedProcess(command, 0, b'', b'')

        with patch.object(sys, 'argv', args), patch.object(native.subprocess, 'run', side_effect=dispatch):
            native.main()
        return read_json(converted / 'native-compile.json')

    def test_native_registers_source_and_material_files_before_dispatch_and_cache_reuse(self):
        fixture = self.compile_fixture()
        converted, source, dependencies, _, _ = fixture
        report = self.compile(fixture)
        expected = {str(path): sha(path) for path in [source, *dependencies]}
        self.assertEqual(report['frozenInputs'], expected)
        self.assertTrue(report['complete'])
        self.assertFalse(report['interactiveClientLaunched'])
        self.compile(fixture)
        self.assertEqual(len(self.calls), 1)
        refs = self.registered()
        self.assertNotIn(str(converted / 'resources/unconsumed.txt'), refs)
        self.assertTrue(all(refs[path]['sha256'] == pin for path, pin in expected.items()))

    def test_native_rejects_source_material_and_compiler_drift(self):
        for field in ('source', 'material', 'compiler'):
            with self.subTest(field=field):
                fixture = self.compile_fixture(field)
                target = {'source': fixture[1], 'material': fixture[2][0], 'compiler': fixture[3]}[field]
                with self.assertRaisesRegex(RuntimeError, 'changed'):
                    self.compile(fixture, mutate=lambda: target.write_bytes(b'changed during dispatch'))
                report = fixture[0] / 'native-compile.json'
                self.assertFalse(read_json(report).get('complete', False) if report.exists() else False)

    def test_diagnostic_without_materials_declares_only_consumed_files(self):
        fixture = self.compile_fixture()
        report = self.compile(fixture, materials=False)
        self.assertEqual(report['frozenInputs'], {str(fixture[1]): sha(fixture[1])})
        self.assertEqual(report['materialResourceHashes'], {})
        refs = self.registered()
        self.assertTrue(all(str(path) not in refs for path in fixture[2]))

    def test_reused_donor_receipt_and_binary_are_pinned_and_registered(self):
        fixture = self.compile_fixture()
        converted, source, dependencies, client, _ = fixture
        donor = self.root / 'donor-worktree'
        (donor / 'resources').mkdir(parents=True)
        binary = donor / 'resources/body.mdl'
        binary.write_bytes(b'\0\0\0\0verified donor')
        receipt = donor / 'native-compile.json'
        write_json(receipt, {'complete': True, 'clientSha256': sha(client),
            'materialResourceHashes': {path.name: sha(path) for path in dependencies},
            'models': [{'name': source.name, 'sourceSha256': sha(source), 'binarySha256': sha(binary)}]})
        report = self.compile(fixture, donor=donor)
        self.assertEqual(len(self.calls), 0)
        self.assertEqual((converted / 'resources/body.mdl').read_bytes(), binary.read_bytes())
        refs = self.registered()
        for path in (receipt, binary):
            self.assertEqual(report['frozenInputs'][str(path)], sha(path))
            self.assertEqual(refs[str(path)]['sha256'], sha(path))

    def test_pelvis_actor_extraction_uses_the_shared_resolver(self):
        stage = self.root / 'stage'
        resources = stage / 'human_male_fit/converted/resources'
        staging = stage / 'test-module/hak-resources'
        frozen = self.root / 'frozen'
        for directory in (resources, staging, frozen, stage / 'userdir/override',
                          stage / 'human_male_fit/converted/ascii', self.root / 'stock/raw'):
            directory.mkdir(parents=True)
        payloads = {'pmh0_chest001.mdl': b'\0\0\0\0chest', 'pmh0_chest001.mtr': b'material',
                    'pmh0_chest001.plt': b'palette', 'pmh0_chest001n.tga': b'normal'}
        for name, data in payloads.items():
            (frozen / name).write_bytes(data)
            shutil.copyfile(frozen / name, resources / name)
        payloads.update({'pmh0_pelvis001.mdl': b'\0\0\0\0pelvis', 'appearance.2da': b'6 human stock\n'})
        for name, data in payloads.items(): (staging / name).write_bytes(data)
        (self.root / 'stock/raw/appearance.2da').write_bytes(payloads['appearance.2da'])
        source = stage / 'human_male_fit/converted/ascii/pmh0_pelvis001.mdl'
        source.write_bytes(b'setsupermodel pmh0_pelvis001 NULL\n')
        write_json(resources.parent / 'native-compile.json', {'models': [{'name': source.name,
            'sourceSha256': sha(source), 'binarySha256': sha(staging / source.name)}]})
        hak, module = stage / 'fixture.hak', stage / 'fixture.mod'
        kinds = {'.mdl': 2002, '.mtr': 2072, '.plt': 6, '.tga': 3, '.2da': 2017}
        self.write_archive(hak, [(Path(name).stem, kinds[Path(name).suffix], data) for name, data in payloads.items()])
        self.write_archive(module, [('sr_pt_floor', 2023, b'GIT fixture')])
        write_json(stage / 'test-module/receipt.json', {'hak': str(hak), 'hakSha256': sha(hak),
            'module': str(module), 'moduleSha256': sha(module), 'configuration': {'cameraLock': False}})
        tool = self.bank / 'gff-fixture.exe'
        tool.parent.mkdir(parents=True); tool.write_bytes(b'non-executable gff fixture')
        identity = {'name': 'gff', 'path': str(tool), 'sha256': sha(tool), 'origin': 'shared',
                    'toolsRoot': str(self.bank), 'rootOrigin': 'environment', 'inventorySha256':
                    sha(self.repo / 'tools/shared-tools.lock.json')}
        output = self.root / 'audit'

        def dispatch(command, **kwargs):
            self.calls.append(command)
            self.assertEqual(command[0], str(tool))
            actors = [{'Gender': {'value': 0}, 'Phenotype': {'value': 0}, 'Appearance_Type': {'value': 6}}]
            write_json(Path(command[command.index('-o') + 1]), {'Creature List': {'value': actors}})
            return subprocess.CompletedProcess(command, 0)

        args = argparse.Namespace(stage=stage, frozen_torso=frozen, stock_bank=self.root / 'stock',
                                  tool_directory=None, output=output)
        with patch.object(tool_runtime, 'resolve_tool', return_value=identity) as resolver, \
             patch.object(pelvis.subprocess, 'run', side_effect=dispatch):
            # Explicit root avoids Git subprocesses during registration.
            with patch('shared_tools.reject_linked'):
                pelvis.run(args)
        resolver.assert_called_once_with('gff', self.repo, override=None)
        self.assertEqual(read_json(output / 'audit.json')['packedActors'][0]['appearance'], 6)

    @staticmethod
    def write_archive(path, rows):
        count = len(rows); keys = 160; resources = keys + count * 24
        data = bytearray(resources + count * 8)
        data[:8] = b'MOD V1.0' if path.suffix == '.mod' else b'HAK V1.0'
        struct.pack_into('<I', data, 16, count)
        struct.pack_into('<II', data, 24, keys, resources)
        for index, (name, kind, payload) in enumerate(rows):
            struct.pack_into('<16sIH', data, keys + index * 24, name.encode('ascii'), index, kind)
            struct.pack_into('<II', data, resources + index * 8, len(data), len(payload))
            data.extend(payload)
        path.write_bytes(data)


if __name__ == '__main__': unittest.main()
