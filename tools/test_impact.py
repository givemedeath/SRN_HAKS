"""Conservative import/literal/config dependency catalog and focused test runner."""
import argparse
import ast
import json
from pathlib import Path
import subprocess
import sys

REPO=Path(__file__).resolve().parent.parent

def catalog(repo=REPO):
    files=sorted((repo/'tools').rglob('*.py'))
    files=[p for p in files if 'vendor' not in p.parts and '__pycache__' not in p.parts]
    dependencies={};unresolved=[]
    for path in files:
        rel=path.relative_to(repo).as_posix();edges=set()
        tree=ast.parse(path.read_text(encoding='utf-8-sig'))
        for node in ast.walk(tree):
            names=[]
            if isinstance(node,ast.Import):names=[row.name for row in node.names]
            if isinstance(node,ast.ImportFrom) and node.module:names=[node.module]
            for name in names:
                leaf=name.split('.')[0];matches=[p for p in files if p.stem==leaf]
                if len(matches)>1:unresolved.append(rel)
                edges.update(p.relative_to(repo).as_posix() for p in matches)
            if isinstance(node,ast.Constant) and isinstance(node.value,str) and not any(c in node.value for c in '*?[') and node.value.endswith(('.py','.json','.ps1','.psm1')):
                # Match unique tracked literals, including helper launches and with_name configs.
                matches=[p for p in (repo/'tools').rglob(Path(node.value).name) if p.is_file() and 'vendor' not in p.parts]
                if len(matches)>1:unresolved.append(rel)
                edges.update(p.relative_to(repo).as_posix() for p in matches)
        dependencies[rel]=sorted(edges-{rel})
    # Non-Python registries govern these adapters even though their filenames are constructed.
    for rel in dependencies:
        if rel.endswith(('shared_tools.py','tool_runtime.py','shared_toolchain.py')):
            dependencies[rel]=sorted(set(dependencies[rel])|{'tools/shared-tools.lock.json','tools/toolchain.lock.json'})
    return {'schemaVersion':1,'dependencies':dependencies,'unresolved':sorted(set(unresolved)),
        'tests':sorted(rel for rel in dependencies if Path(rel).name.startswith('test_') and rel!='tools/test_impact.py')}

def select(changed,data):
    known=set(data['dependencies'])|{p for rows in data['dependencies'].values() for p in rows}
    if not changed or any(p not in known for p in changed):return {'fullSuite':True,'reason':'Unknown/configuration dependency; full suite required','tests':data['tests']}
    impacted=set(changed)
    while True:
        before=len(impacted)
        impacted.update(p for p,edges in data['dependencies'].items() if impacted.intersection(edges))
        if len(impacted)==before:break
    tests=sorted(set(data['tests'])&impacted)
    if not tests or set(data['unresolved'])&impacted:
        return {'fullSuite':True,'reason':'Unresolved or uncovered dependency','tests':data['tests']}
    return {'fullSuite':False,'reason':'Transitive imports, helper literals and configurations','tests':tests}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--changed',action='append',default=[])
    p.add_argument('--write-catalog',type=Path);p.add_argument('--run',action='store_true');a=p.parse_args()
    data=catalog()
    if a.write_catalog:a.write_catalog.write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
    result=select(a.changed,data);print(json.dumps(result),flush=True)
    if a.run:
        folders={}
        for path in result['tests']:folders.setdefault(str((REPO/path).parent),[]).append(Path(path).stem)
        for folder,names in folders.items():
            code=subprocess.call([sys.executable,'-B','-m','unittest',*names],cwd=folder)
            if code:raise SystemExit(code)

if __name__=='__main__':main()
