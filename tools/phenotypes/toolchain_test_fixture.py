"""Select current launcher bindings for tests, or create unexecuted test data.

The standalone fixture exercises the real byte and migration guards without
an installed runtime. Its runtime bytes are deliberately not executable and
its receipt explicitly is not production tool-migration evidence.
"""
import json
import os
from pathlib import Path

from shared_toolchain import load, sha


def bindings(root):
    root=Path(root).resolve()
    supplied_toolchain=os.environ.get('SRN_SHARED_TOOLCHAIN')
    supplied_migration=os.environ.get('SRN_SHARED_TOOL_MIGRATION')
    if bool(supplied_toolchain)!=bool(supplied_migration):
        raise ValueError('Tests require both current launcher toolchain and migration bindings')
    if supplied_toolchain:
        toolchain=Path(supplied_toolchain).resolve()
        migration=Path(supplied_migration).resolve()
        # A supplied but stale binding must fail, never fall back to synthetic data.
        load(toolchain,migration)
        scope='current-launcher-bound-runtimes'
    else:
        directory=root/'unexecuted-toolchain-test-fixture'
        directory.mkdir(parents=True,exist_ok=False)
        durable=directory/'shared-tools';durable.mkdir()
        runtime=directory/'non-executable-runtime.fixture'
        runtime.write_bytes(b'UNIT TEST DATA ONLY: this is not a Python executable\n')
        toolchain=directory/'toolchain.json'
        toolchain.write_text(json.dumps({'schemaVersion':2,'kind':'phenotype-shared-toolchain',
            'toolsRoot':str(durable),'requiredTools':['python'],
            'runtimes':{'python':{'path':str(runtime),'sha256':sha(runtime)}},
            'fixtureScope':'synthetic-unexecuted-unit-test-only','runtimeExecutionAllowed':False})+'\n',encoding='utf-8')
        helpers={str(Path(__file__).with_name(name).resolve()):{'sha256':sha(Path(__file__).with_name(name))}
                 for name in ('shared_toolchain.py','launch_shared_tool.py',
                              'bootstrap_shared_blender_addons.py','historical_helper_bindings.py')}
        migration=directory/'unexecuted-test-migration-shape.json'
        migration.write_text(json.dumps({'kind':'phenotype-shared-tool-migration','smokeChecksPassed':True,
            'toolchain':{'path':str(toolchain),'sha256':sha(toolchain)},'launchHelpers':helpers,
            'fixtureScope':'synthetic-unexecuted-unit-test-only','smokeChecksActuallyExecuted':False,
            'runtimeExecutionAllowed':False,'productionMigrationEvidence':False,'clientAccepted':False,
            'note':'Unit-test schema data for real load guards only. No tool smoke was executed; do not launch tools with this fixture.'})+'\n',encoding='utf-8')
        load(toolchain,migration)
        scope='synthetic-unexecuted-unit-test-only'
    declaration=root/'test-fixture-runtime-inputs.json'
    declaration.write_text(json.dumps({'schemaVersion':1,'kind':'test-fixture-runtime-inputs',
        'scope':scope,'runtimeExecutionPerformed':False,
        'inputs':[{'path':str(path),'sha256':sha(path)} for path in (toolchain,migration)]})+'\n',encoding='utf-8')
    return toolchain,migration
