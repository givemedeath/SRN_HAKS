"""Conservative import/literal/config dependency catalog and focused test runner."""
import argparse
import ast
import json
from pathlib import Path
import subprocess
import sys

REPO=Path(__file__).resolve().parent.parent

def catalog(repo=REPO):
    all_files=sorted(p for p in (repo/'tools').rglob('*') if p.is_file()
                     and not set(p.parts)&{'vendor','__pycache__','build','dist','.venv'}
                     and not any(part.endswith('.egg-info') for part in p.parts))
    files=[p for p in all_files if p.suffix=='.py'];file_set=set(files)
    literal_index={}
    for p in all_files:literal_index.setdefault(p.name,[]).append(p)
    dependencies={};unresolved=[]
    for path in files:
        rel=path.relative_to(repo).as_posix();edges=set()
        tree=ast.parse(path.read_text(encoding='utf-8-sig'))
        for node in ast.walk(tree):
            imports=[]
            if isinstance(node,ast.Import):imports=[(row.name,0) for row in node.names]
            if isinstance(node,ast.ImportFrom):
                imports=[(node.module,node.level)] if node.module else []
                imports.extend(((node.module+'.' if node.module else '')+row.name,node.level) for row in node.names if row.name!='*')
            for name,level in imports:
                base=path.parent
                if level:
                    for _ in range(level-1):base=base.parent
                candidates=[base.joinpath(*name.split('.')).with_suffix('.py'),base.joinpath(*name.split('.'))/'__init__.py']
                local=[p for p in candidates if p in file_set]
                if local:matches=local
                elif level:matches=[]
                else:
                    module_suffix='/'.join(name.split('.'))
                    matches=[p for p in files if p.as_posix().endswith('/'+module_suffix+'.py') or p.as_posix().endswith('/'+module_suffix+'/__init__.py')]
                if len(matches)>1:unresolved.append(rel)
                edges.update(p.relative_to(repo).as_posix() for p in matches)
            if isinstance(node,ast.Constant) and isinstance(node.value,str) and not any(c in node.value for c in '*?[') and node.value.endswith(('.py','.json','.ps1','.psm1')):
                # Match unique tracked literals, including helper launches and with_name configs.
                literal=Path(node.value);qualified=repo/literal;relative=path.parent/literal
                if qualified.is_file():matches=[qualified]
                elif relative.is_file():matches=[relative]
                elif (path.parent/literal.name).is_file():matches=[path.parent/literal.name]
                else:matches=literal_index.get(literal.name,[])
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
