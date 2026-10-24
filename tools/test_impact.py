"""Conservative import/literal/config dependency catalog and focused test runner."""
import argparse
import ast
import json
import os
from pathlib import Path
import re
import subprocess
import sys

REPO=Path(__file__).resolve().parent.parent
CONFIG='tools/ci-scope.json'
EXCLUDED={'vendor','__pycache__','build','dist','.venv'}
LITERAL_SUFFIXES=('.py','.json','.ps1','.psm1','.md')
# Bare package markers and output READMEs name no particular file; a qualified path such as pkg/__init__.py still resolves.
GENERIC_LITERALS={'__init__.py','readme.md'}
PACK=re.compile(r'\bsrn_[a-z0-9_]+\b')

def import_root(path):
    """Return (import root, qualified module name) the way unittest/-m would import this file."""
    path=Path(path);parts=[path.stem];base=path.parent
    while (base/'__init__.py').is_file():parts.insert(0,base.name);base=base.parent
    if parts[-1]=='__init__':parts.pop()
    return base,'.'.join(parts)

def markdown_files(repo):
    found=[]
    for top,dirs,names in os.walk(repo):
        dirs[:]=[d for d in dirs if not d.startswith('.') and d not in EXCLUDED|{'output','node_modules'} and not d.startswith('srn_')]
        found.extend(Path(top)/n for n in names if n.lower().endswith('.md'))
    return sorted(found)

def committed_packs(repo):
    """Pack folders in HEAD; empty outside a Git checkout."""
    if not (repo/'.git').exists():return set()
    result=subprocess.run(['git','-C',str(repo),'ls-tree','-d','--name-only','HEAD'],capture_output=True,text=True)
    return {n for n in result.stdout.splitlines() if re.fullmatch(r'srn_[a-z0-9_]+',n)} if not result.returncode else set()

def packs(repo):
    """Pack folders on disk or in HEAD, so a sparse checkout catalogs the same pack names as a full one."""
    return sorted({p.name for p in repo.iterdir() if p.is_dir() and re.fullmatch(r'srn_[a-z0-9_]+',p.name)}|committed_packs(repo))

def absent_packs(repo=REPO):
    """Committed pack folders that this (sparse) checkout did not materialise."""
    return sorted(repo/name for name in committed_packs(repo) if not (repo/name).is_dir())

def pack_needs(data,test):
    """Packs named by a file in the test's transitive dependency closure, including the test itself."""
    seen={test};stack=[test]
    while stack:
        for edge in data['dependencies'].get(stack.pop(),[]):
            if edge not in seen:seen.add(edge);stack.append(edge)
    return sorted({pack for path in seen for pack in data.get('packReferences',{}).get(path,[])})

def catalog(repo=REPO):
    all_files=sorted(p for p in (repo/'tools').rglob('*') if p.is_file()
                     and not set(p.parts)&EXCLUDED
                     and not any(part.endswith('.egg-info') for part in p.parts))
    files=[p for p in all_files if p.suffix=='.py'];file_set=set(files)
    qualified={p:import_root(p)[1] for p in files}
    in_package={p:(p.parent/'__init__.py').is_file() for p in files}
    literal_index={}
    for p in all_files+[m for m in markdown_files(repo) if m not in set(all_files)]:literal_index.setdefault(p.name,[]).append(p)
    pack_names=set(packs(repo))
    config=repo/CONFIG
    # The selector's own tests name helper paths as data; those strings are not reads of the helpers.
    data_only=set(json.loads(config.read_text(encoding='utf-8')).get('literalsAreData',[])) if config.is_file() else set()
    dependencies={};unresolved=[];pack_references={}
    for path in files:
        rel=path.relative_to(repo).as_posix();edges=set();mentioned=set()
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
                    # A module inside a package is only importable by its package-qualified name.
                    matches=[p for p in files if (p.as_posix().endswith('/'+module_suffix+'.py') or p.as_posix().endswith('/'+module_suffix+'/__init__.py'))
                             and (not in_package[p] or qualified[p]==name or p.relative_to(repo).as_posix()
                                  in (module_suffix+'.py',module_suffix+'/__init__.py'))]
                if len(matches)>1:unresolved.append(rel)
                edges.update(p.relative_to(repo).as_posix() for p in matches)
            if isinstance(node,ast.Constant) and isinstance(node.value,str):
                if rel not in data_only:mentioned.update(set(PACK.findall(node.value))&pack_names)
                if rel in data_only or any(c in node.value for c in '*?[') or not node.value.endswith(LITERAL_SUFFIXES):continue
                # Match unique tracked literals, including helper launches, with_name configs and read documents.
                literal=Path(node.value.replace('\\','/').lstrip('/'));qualified_path=repo/literal;relative=path.parent/literal
                if len(literal.parts)<=1 and literal.name.lower() in GENERIC_LITERALS:matches=[]
                elif qualified_path.is_file():matches=[qualified_path]
                elif relative.is_file():matches=[relative]
                elif (path.parent/literal.name).is_file():matches=[path.parent/literal.name]
                elif len(literal.parts)>1:
                    suffix='/'+literal.as_posix().removeprefix('./')
                    matches=[p for p in literal_index.get(literal.name,[]) if p.as_posix().endswith(suffix)]
                else:matches=literal_index.get(literal.name,[])
                if len(matches)>1:unresolved.append(rel)
                edges.update(p.relative_to(repo).as_posix() for p in matches)
        dependencies[rel]=sorted(edges-{rel})
        if mentioned:pack_references[rel]=sorted(mentioned)
    # Non-Python registries govern these adapters even though their filenames are constructed.
    for rel in dependencies:
        if rel.endswith(('shared_tools.py','tool_runtime.py','shared_toolchain.py')):
            dependencies[rel]=sorted(set(dependencies[rel])|{'tools/shared-tools.lock.json','tools/toolchain.lock.json'})
    return {'schemaVersion':2,'dependencies':dependencies,'unresolved':sorted(set(unresolved)),'packReferences':pack_references,
        'tests':sorted(rel for rel in dependencies if Path(rel).name.startswith('test_') and rel!='tools/test_impact.py')}

def load_config(repo=REPO):
    return json.loads((repo/CONFIG).read_text(encoding='utf-8'))

def full(data,reason):
    return {'fullSuite':True,'reason':reason,'tests':data['tests'],'documentation':[],'packs':[]}

def suite(path):
    """Helper-suite folder of a repository path: tools/<folder>, or tools for root helpers."""
    parts=path.split('/')
    return '/'.join(parts[:2]) if len(parts)>2 and parts[0]=='tools' else parts[0]

def dependents(paths,data):
    impacted=set(paths)
    while True:
        before=len(impacted)
        impacted.update(p for p,edges in data['dependencies'].items() if impacted.intersection(edges))
        if len(impacted)==before:return impacted

def deleted_paths(changed,repo=REPO):
    """Changed paths absent from the checked-out revision; sparse-omitted (skip-worktree) entries still exist."""
    missing=[p for p in changed if not (repo/p).exists()]
    if not missing or not (repo/'.git').exists():return set(missing)
    listed=subprocess.run(['git','-C',str(repo),'ls-files','-t','-z'],capture_output=True)
    if listed.returncode:return set(missing)
    sparse={row[2:].decode('utf-8') for row in listed.stdout.split(b'\0') if row.startswith(b'S ')}
    return set(missing)-sparse

def select(changed,data,config=None,deleted=()):
    """Select tests for changed paths; anything not provably covered selects the full suite."""
    if not changed:return full(data,'No comparison data; full suite required')
    shared=[p for p in changed if config and any(re.search(r,p) for r in config['sharedInfrastructure'])]
    if shared:return full(data,'Shared infrastructure changed: '+', '.join(shared))
    # A helper whose tests span several suite folders is shared; static imports cannot prove
    # coverage of its dynamic or indirect consumers, so it keeps the full helper suite.
    known=set(data['dependencies'])|{p for rows in data['dependencies'].values() for p in rows}
    tests_set=set(data['tests'])
    for path in changed:
        if path in known and path not in tests_set:
            folders={suite(t) for t in dependents([path],data)&tests_set}
            if len(folders)>1:return full(data,f'Shared helper changed: {path} (tests in {", ".join(sorted(folders))})')
    impacted=set();documentation=[];changed_packs=set();code=[]
    for path in changed:
        first=path.split('/')[0]
        if path in known:impacted.add(path);code.append(path)
        # The head catalog cannot see literals that read a deleted document, so its readers are unknown.
        elif path.lower().endswith('.md') and path in deleted:return full(data,'Deleted document; its former readers are unknown: '+path)
        elif path.lower().endswith('.md'):documentation.append(path)
        elif re.fullmatch(r'srn_[a-z0-9_]+',first) and len(path.split('/'))>1:changed_packs.add(first)
        else:return full(data,'Unknown/configuration dependency; full suite required: '+path)
    impacted.update(p for p,rows in data.get('packReferences',{}).items() if changed_packs&set(rows))
    impacted=dependents(impacted,data)
    tests=sorted(set(data['tests'])&impacted)
    if set(data['unresolved'])&impacted:return full(data,'Unresolved dependency; full suite required')
    if code and not tests:return full(data,'Changed code has no covering test; full suite required')
    reason='Transitive imports, helper literals and configurations'
    if documentation and not code and not changed_packs and not tests:reason='Documentation only; no helper tests read these files'
    elif changed_packs and not code:reason='Pack assets; tests referencing '+', '.join(sorted(changed_packs))
    return {'fullSuite':False,'reason':reason,'tests':tests,'documentation':sorted(documentation),'packs':sorted(changed_packs)}

CHILD='''import json,os,sys,unittest
out,names=sys.argv[1],sys.argv[2:]
# Sparse checkouts: any in-process look at a pack folder this checkout omitted fails the run instead of passing silently.
absent=[os.path.normcase(p) for p in os.environ.get('SRN_ABSENT_PACKS','').split(os.pathsep) if p]
touched=set();current=['']
if absent:
    def hit(path):
        if isinstance(path,int):return
        try:full=os.path.normcase(os.path.abspath(os.fsdecode(os.fspath(path))))
        except (TypeError,ValueError):return
        if any(full==p or full.startswith(p+os.sep) for p in absent):touched.add((current[0],full))
    def hook(event,args):
        if event in ('open','os.listdir','os.scandir') and args:hit(args[0])
    sys.addaudithook(hook)
    def guard(original):
        def checked(path,*rest,**options):
            hit(path);return original(path,*rest,**options)
        return checked
    for module,name in ((os,'stat'),(os,'lstat'),(os.path,'exists'),(os.path,'lexists'),(os.path,'isfile'),(os.path,'isdir')):
        setattr(module,name,guard(getattr(module,name)))
class Result(unittest.TextTestResult):
    def startTest(self,test):
        current[0]=test.id();super().startTest(test)
    def stopTest(self,test):
        super().stopTest(test);current[0]=''
result=unittest.TextTestRunner(verbosity=2,durations=0,resultclass=Result).run(unittest.defaultTestLoader.loadTestsFromNames(names))
if out:
    with open(out,'w',encoding='utf-8') as f:json.dump([[n,round(t,3)] for n,t in result.collectedDurations],f)
for test,path in sorted(touched):print('Absent pack accessed by '+(test or 'module import/fixture')+': '+path,file=sys.stderr)
sys.exit(0 if result.wasSuccessful() and result.testsRun and not touched else 1)
'''

def run_tests(tests,python=None,repo=REPO,timings=None,absent=None):
    """Run tests from their import roots, package-qualified where needed; return the first failing exit code."""
    absent=absent_packs(repo) if absent is None else absent
    env={**os.environ,'SRN_ABSENT_PACKS':os.pathsep.join(str(Path(p).resolve()) for p in absent)}
    groups={}
    for rel in tests:
        root,name=import_root(repo/rel);groups.setdefault(root,[]).append(name)
    records=[];code=0
    for index,(root,names) in enumerate(sorted(groups.items(),key=lambda row:str(row[0]))):
        # Absolute, because the child runs from the import root.
        out=str(Path(timings).resolve().with_suffix(f'.{index}.json')) if timings else ''
        # -c keeps sys.path[0] at the import root, exactly as `python -m unittest` from that folder.
        result=subprocess.call([python or sys.executable,'-B','-c',CHILD,out,*names],cwd=root,env=env)
        if out and Path(out).is_file():
            rows=json.loads(Path(out).read_text(encoding='utf-8'));Path(out).unlink()
            records.extend({'root':Path(root).relative_to(repo).as_posix(),'test':n,'seconds':t} for n,t in rows)
        code=code or result
    if timings:Path(timings).write_text(json.dumps(records,indent=1)+'\n',encoding='utf-8')
    return code

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--changed',action='append',default=[])
    p.add_argument('--write-catalog',type=Path);p.add_argument('--run',action='store_true')
    p.add_argument('--tests-from',type=Path,help='JSON list of repository-relative test files to run instead of a selection')
    p.add_argument('--timings',type=Path,help='Write per-test durations as JSON');a=p.parse_args()
    if a.tests_from:
        tests=json.loads(a.tests_from.read_text(encoding='utf-8'))
        print(json.dumps({'fullSuite':None,'reason':'Explicit test list','tests':tests}),flush=True)
        raise SystemExit(run_tests(tests,timings=a.timings) if tests else 0)
    data=catalog()
    if a.write_catalog:a.write_catalog.write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8',newline='\n')
    result=select(a.changed,data,load_config(),deleted_paths(a.changed));print(json.dumps(result),flush=True)
    if a.run and result['tests']:raise SystemExit(run_tests(result['tests'],timings=a.timings))

if __name__=='__main__':main()
