"""Finalize a Python-only PhenoMorpher migration from a real registered doctor smoke."""
import argparse
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO/'tools/phenotypes'))
from finalize_shared_tool_migration import verify_launch
from shared_toolchain import load, sha


def pin(path):
    path = Path(path).resolve()
    return {'path':str(path),'sha256':sha(path)}


def verify_doctor(launch, result):
    """Require the prescribed command, local source coverage and loaded origins."""
    if launch['command'][1:] != ['-B', '-m', 'phenomorpher', 'doctor']:
        raise ValueError('Exact PhenoMorpher doctor command required')
    package = Path(__file__).resolve().parent/'phenomorpher'
    expected = {p.resolve() for pattern in ('*.py', '*.json') for p in package.rglob(pattern)}
    frozen = {Path(p).resolve(): h for p, h in launch['frozenInputs'].items()}
    if any(frozen.get(p) != sha(p) for p in expected):
        raise ValueError('All local package Python/JSON inputs must be frozen at current bytes')
    loaded = result.get('loadedPackageSources', {})
    required = {'phenomorpher', 'phenomorpher.cli', 'phenomorpher.engine.measurement_workflow'}
    if not required.issubset(loaded):
        raise ValueError('Doctor loaded package source evidence required')
    for name, row in loaded.items():
        path = Path(row['path']).resolve()
        if not name.startswith('phenomorpher') or path not in expected or row['sha256'] != frozen[path]:
            raise ValueError('Doctor loaded another package or changed source')


def finalize(toolchain, smoke, output):
    toolchain, smoke, output = map(lambda p:Path(p).resolve(),(toolchain,smoke,output))
    if output.exists():
        raise ValueError('Fresh migration receipt required')
    tools = load(toolchain, required=['python'])
    launch = verify_launch(smoke, 'python', toolchain, tools)
    result = json.loads((smoke/'stdout.log').read_text(encoding='utf-8'))
    verify_doctor(launch, result)
    if result.get('kind')!='phenotype-measurement-python-smoke' or not result.get('checksPassed'):
        raise ValueError('Real PhenoMorpher doctor smoke required')
    if Path(result['executable']).resolve()!=Path(tools['tools']['python']['path']).resolve():
        raise ValueError('Smoke interpreter differs from bound runtime')
    helpers={p:{'sha256':h} for p,h in launch['frozenInputs'].items()
             if Path(p).name in ('launch_shared_tool.py','shared_toolchain.py')}
    if len(helpers)!=2:
        raise ValueError('Both launch helper pins required')
    receipt={'schemaVersion':1,'kind':'phenotype-shared-tool-migration','scope':'measurement-tools',
        'allowedTools':['python'],'smokeChecksPassed':True,'toolchain':pin(toolchain),
        'launchHelpers':helpers,'frozenSmokeFiles':[pin(p) for p in sorted(smoke.rglob('*')) if p.is_file()],
        'executedFinalizer':pin(__file__),'gameClientTesting':False,
        'limits':'CPU geometry/measurement tooling only; no Blender/Armory/client or asset acceptance.'}
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8',newline='\n')
    load(toolchain,output,required=['python'])
    return pin(output)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('toolchain','smoke','output'):parser.add_argument('--'+name,required=True,type=Path)
    args=parser.parse_args();print(json.dumps(finalize(args.toolchain,args.smoke,args.output)))
