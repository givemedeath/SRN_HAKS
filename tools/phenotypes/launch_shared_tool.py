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
from shared_tools import register_run, write_json, tools_root, resolve_tool, resolve_addon


def tree_files(root):
    root = Path(root).resolve()
    if not root.is_dir():
        raise ValueError(f"Input tree does not exist: {root}")
    return sorted(p.resolve() for p in root.rglob("*") if p.is_file() and "__pycache__" not in p.parts)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--toolchain',type=Path,required=True)
    parser.add_argument('--migration-receipt',type=Path)
    parser.add_argument('--migration-smoke',action='store_true')
    parser.add_argument('--tool',choices=('python','blender','armory'),required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--input',type=Path,action='append',default=[],help='Consumed input, registered and frozen before dispatch')
    parser.add_argument('--input-tree',type=Path,action='append',default=[],help='Freeze every file and membership of a consumed input directory')
    parser.add_argument('--provenance',type=Path,action='append',default=[])
    parser.add_argument('arguments',nargs=argparse.REMAINDER)
    args=parser.parse_args()
    if bool(args.migration_receipt)==args.migration_smoke:
        raise ValueError('Use a passed migration receipt, or explicit pre-migration smoke mode')
    config=args.toolchain.resolve();migration=args.migration_receipt.resolve() if args.migration_receipt else None
    data=load(config,migration,required=[args.tool])
    repo=Path(__file__).resolve().parents[2]
    if data['schemaVersion']==1:
        if args.tool=='armory':resolve_tool('armory',repo,override=data['tools']['armory']['path'])
        if args.tool=='blender':resolve_addon(repo=repo,override=data['addons']['root'])
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=False)
    argv=args.arguments[1:] if args.arguments[:1]==['--'] else args.arguments
    env=os.environ.copy();env['SRN_SHARED_TOOLCHAIN']=str(config)
    env['PYTHONUTF8']='1';env['PYTHONIOENCODING']='utf-8';env['PYTHONDONTWRITEBYTECODE']='1'
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
    inputs=[config,Path(__file__).resolve(),Path(__file__).with_name('shared_toolchain.py'),
            Path(__file__).resolve().parents[1]/'shared_tools.py',
            Path(__file__).resolve().parents[1]/'shared-tools.lock.json',*args.input]
    if data.get('addons'):
        inputs.extend(Path(data['addons']['root'])/rel for rel in data['addons']['files'])
    if args.tool=='blender':inputs.append(Path(__file__).with_name('bootstrap_shared_blender_addons.py'))
    if migration:inputs.append(migration)
    trees={str(root.resolve()):tree_files(root) for root in args.input_tree}
    for files in trees.values():inputs.extend(files)
    inputs=list(dict.fromkeys(inputs))
    frozen={str(p.resolve()):sha(p) for p in inputs}
    snapshots={};(output/'helper-snapshots').mkdir()
    for path in inputs:
        if path.suffix=='.py':
            copied=output/'helper-snapshots'/(sha(path)[:12]+'-'+path.name);shutil.copyfile(path,copied)
            if sha(copied)!=frozen[str(path.resolve())]:raise ValueError('Helper changed during snapshot')
            snapshots[str(path)]={'snapshot':str(copied),'sha256':sha(copied)}
    repo=Path(__file__).resolve().parents[2]
    dependency=register_run(repo,root=data.get('toolsRoot'),tools=list(data['tools'].values()),
                            inputs=[{'path':p,'sha256':h} for p,h in frozen.items()],provenance=args.provenance)
    begun=time.monotonic()
    with (output/'stdout.log').open('w',encoding='utf-8') as out,(output/'stderr.log').open('w',encoding='utf-8') as err:
        result=subprocess.run(command,env=env,stdout=out,stderr=err,check=False)
    verification_error=None
    try:
        load(config,migration,required=[args.tool])
        if any(tree_files(root)!=files for root,files in trees.items()):raise ValueError("Input directory membership changed during execution; result invalid")
        if any(sha(p)!=h for p,h in frozen.items()):raise ValueError('Input/helper changed during execution; result invalid')
    except (ValueError,OSError) as error:verification_error=str(error)
    receipt={'schemaVersion':1,'kind':'verified-shared-tool-launch','createdUtc':datetime.now(timezone.utc).isoformat(),
        'tool':args.tool,'toolchain':str(config),'toolchainSha256':sha(config),
        'migrationReceipt':str(migration) if migration else None,'migrationReceiptSha256':sha(migration) if migration else None,
        'preMigrationSmoke':args.migration_smoke,'command':command,'workingDirectory':str(Path.cwd()),
        'toolBinary':data['tools'][args.tool],'exitCode':result.returncode,'elapsedSeconds':time.monotonic()-begun,
        'inputsUnchanged':verification_error is None,'verificationError':verification_error,
        'inputTrees':{root:[str(p) for p in files] for root,files in trees.items()},
        'frozenInputs':frozen,'helperSnapshots':snapshots,'dependencyReceipt':str(dependency),
        'selectedRoot':str(tools_root(repo,data.get('toolsRoot'))[0]),
        'inventorySha256':sha(repo/'tools/shared-tools.lock.json'),
        'stdoutSha256':sha(output/'stdout.log'),'stderrSha256':sha(output/'stderr.log'),
        'addonBootstrap':{'path':str(output/'loaded-addons.json'),'sha256':sha(output/'loaded-addons.json')}
            if (output/'loaded-addons.json').is_file() else None,'gameClientTesting':False}
    path=output/'launch.json';path.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'receipt':str(path),'sha256':sha(path),'exitCode':result.returncode}))
    raise SystemExit(1 if verification_error else result.returncode)


if __name__=='__main__':main()
