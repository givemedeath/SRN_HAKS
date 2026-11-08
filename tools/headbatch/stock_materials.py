"""Verify the actual built-in material used by organic native heads before a client trial."""
from pathlib import Path
import re
import subprocess
from headkit.common import write, pin, verify, require, module_closure, module_path
from headkit.native import material_binding
from shared_tools import resolve_tool, register_run
from workspace import REPO, TOOLS


def expected(spec):
    result = {}
    for head in spec['heads']:
        binding = head.get('nativeMaterial')
        if binding is None:
            continue
        require(binding == material_binding(binding.get('policy'),head['model'],binding.get('channels',[])),
                'Trial native material differs from the export policy')
        if binding['applied']:
            result[binding['material']] = binding['expectedStockSha256']
    return result


def check(workspace, spec, output, fetch=None):
    wanted = expected(spec)
    if not wanted:
        return None
    output = Path(output);output.mkdir(parents=True,exist_ok=False)
    game = Path(spec['gameRoot']).resolve()
    base = spec['base']['haks']
    code = {Path(__file__),TOOLS/'shared_tools.py',TOOLS/'shared-tools.lock.json',TOOLS/'headbatch/workspace.py',
            *(module_path(name,TOOLS/'headkit') for name in module_closure({'native'},TOOLS/'headkit'))}
    inputs = [*(pin(path) for path in sorted(code)),*base]
    verify(inputs,fresh=True)
    tools = []
    if fetch is None:
        bank = workspace.path(workspace.data['toolsRoot']) if workspace.data.get('toolsRoot') else None
        cat = resolve_tool('resman_cat',REPO,root=bank);grep = resolve_tool('resman_grep',REPO,root=bank)
        tools = [cat,grep];inputs += [pin(row['path']) for row in tools]
        user = output/'isolated-user';(user/'override').mkdir(parents=True)
        args = ['--root',str(game),'--userdirectory',str(user),'--quiet',
                '--erfs',','.join(row['path'] for row in base)]
        def fetch(name):
            listed = subprocess.run([grep['path'],*args,'--pattern',name+'.mtr','--details'],
                                    check=True,capture_output=True,text=True,timeout=60).stdout
            matches = [line for line in listed.splitlines() if line.split() and line.split()[0]==name+'.mtr']
            require(len(matches)==1,'Resolve exactly one stock head material: '+name)
            location = matches[0]
            source = re.search(r'KeyTable:(.*\.key)\(id=\d+ in (.*\.bif)\)',location)
            require(source is not None,'Stock head material is shadowed or has an unsupported source: '+location)
            containers = [Path(source[1]),game/source[2]]
            data = subprocess.run([cat['path'],*args,name+'.mtr'],check=True,
                                  capture_output=True,timeout=60).stdout
            return data,[pin(path) for path in containers],location
    materials = {}
    for name,digest in wanted.items():
        data,containers,location = fetch(name)
        import hashlib
        require(hashlib.sha256(data).hexdigest()==digest,'Installed stock head material differs: '+name)
        path = output/(name+'.mtr');path.write_bytes(data)
        materials[name] = {'source':location,'payload':pin(path)}
        inputs += containers
    inputs = list({str(Path(row['path']).resolve()):row for row in inputs}.values())
    verify(inputs,fresh=True)
    proof = output/'check.json'
    write(proof,{'kind':'headbatch-stock-material-check-v1','passed':True,'expected':wanted,
                 'gameRoot':str(game),'baseHaks':base,'materials':materials,'inputs':inputs},fresh=True)
    if tools:
        register_run(REPO,root=bank,tools=tools,inputs=inputs,complete=True)
    return pin(proof)
