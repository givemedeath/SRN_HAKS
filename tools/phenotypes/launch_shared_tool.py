"""Run a verified shared CLI tool and retain an immutable launch receipt."""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import subprocess
import shutil
import time

from shared_toolchain import load, sha


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--toolchain',type=Path,required=True)
    parser.add_argument('--migration-receipt',type=Path)
    parser.add_argument('--migration-smoke',action='store_true')
    parser.add_argument('--tool',choices=('python','blender','armory'),required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('arguments',nargs=argparse.REMAINDER)
    args=parser.parse_args()
    if bool(args.migration_receipt)==args.migration_smoke:
        raise ValueError('Use a passed migration receipt, or explicit pre-migration smoke mode')
    config=args.toolchain.resolve();migration=args.migration_receipt.resolve() if args.migration_receipt else None
    data=load(config,migration)
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=False)
    argv=args.arguments[1:] if args.arguments[:1]==['--'] else args.arguments
    env=os.environ.copy();env['SRN_SHARED_TOOLCHAIN']=str(config)
    env['SRN_SHARED_ADDON_BOOTSTRAP_RECEIPT']=str(output/'loaded-addons.json')
    if migration:env['SRN_SHARED_TOOL_MIGRATION']=str(migration)
    else:env.pop('SRN_SHARED_TOOL_MIGRATION',None)
    command=[data['tools'][args.tool]['path']]
    if args.tool=='blender':
        if any(value in argv for value in ('--factory-startup','-b','--background')):
            raise ValueError('Launcher owns isolated background startup flags')
        command+=['--factory-startup','-b','-t','4','--python-exit-code','1','--python',
                  str(Path(__file__).with_name('bootstrap_shared_blender_addons.py').resolve())]
    command+=argv
    begun=time.monotonic()
    with (output/'stdout.log').open('w',encoding='utf-8') as out,(output/'stderr.log').open('w',encoding='utf-8') as err:
        result=subprocess.run(command,env=env,stdout=out,stderr=err,check=False)
    load(config,migration)
    inputs=[config,Path(__file__).resolve(),Path(__file__).with_name('shared_toolchain.py')]
    if args.tool=='blender':inputs.append(Path(__file__).with_name('bootstrap_shared_blender_addons.py'))
    if migration:inputs.append(migration)
    snapshots={};(output/'helper-snapshots').mkdir()
    for path in inputs:
        if path.suffix=='.py':
            copied=output/'helper-snapshots'/path.name;shutil.copyfile(path,copied)
            snapshots[str(path)]={'snapshot':str(copied),'sha256':sha(copied)}
    receipt={'schemaVersion':1,'kind':'verified-shared-tool-launch','createdUtc':datetime.now(timezone.utc).isoformat(),
        'tool':args.tool,'toolchain':str(config),'toolchainSha256':sha(config),
        'migrationReceipt':str(migration) if migration else None,'migrationReceiptSha256':sha(migration) if migration else None,
        'preMigrationSmoke':args.migration_smoke,'command':command,'workingDirectory':str(Path.cwd()),
        'toolBinary':data['tools'][args.tool],'exitCode':result.returncode,'elapsedSeconds':time.monotonic()-begun,
        'frozenInputs':{str(p):sha(p) for p in inputs},'helperSnapshots':snapshots,
        'stdoutSha256':sha(output/'stdout.log'),'stderrSha256':sha(output/'stderr.log'),
        'addonBootstrap':{'path':str(output/'loaded-addons.json'),'sha256':sha(output/'loaded-addons.json')}
            if (output/'loaded-addons.json').is_file() else None,'gameClientTesting':False}
    path=output/'launch.json';path.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'receipt':str(path),'sha256':sha(path),'exitCode':result.returncode}))
    raise SystemExit(result.returncode)


if __name__=='__main__':main()
