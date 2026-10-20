"""Source snapshots and loaded Python-code checks for the installed Comfy adapter."""
import ast
import hashlib
import json
import marshal
import os
from pathlib import Path
import sys
import types


EXTENSIONS={'.py','.pyx','.pyi','.json','.yaml','.yml','.toml','.pyd','.so','.dll','.dylib','.ptx','.cubin','.h','.hpp','.c','.cpp','.cu','.cuh'}
CORE_DATA={'input','output','temp','models','user','.venv','venv'}
REQUIRED_CORE={'main.py','execution.py','nodes.py','server.py','folder_paths.py'}


def require(condition,message):
    if not condition:raise ValueError(message)


def _linked(path):
    return path.is_symlink() or getattr(os.path,'isjunction',lambda value:False)(path)


def _inside(path,roots):
    return any(path==root or path.is_relative_to(root) for root in roots)


def members(core,roots):
    core=Path(core).resolve(strict=True)
    roots=[Path(root).resolve(strict=True) for root in roots]
    require(core in roots,'Inventory must cover the Comfy root')
    require(len(roots)==len(set(roots)),'Comfy source roots must be unique')
    found=set()
    for root in roots:
        require(root.is_dir(),'Missing Comfy source root')
        for current,dirs,names in os.walk(root,followlinks=False):
            current=Path(current)
            dirs[:]=[name for name in dirs if name not in {'.git','.hg','.svn','__pycache__'}
                     and not (current==core and name in CORE_DATA)]
            for name in dirs:
                path=current/name
                require(not _linked(path) and path.resolve(strict=True)==path.absolute(),
                        'Linked source directories need an explicit unlinked installation')
            for name in names:
                path=current/name
                if path.name=='source-roots.json' and path.parent.name=='srn_headkit':continue
                if path.suffix.lower() not in EXTENSIONS:continue
                require(not _linked(path) and path.resolve(strict=True)==path.absolute(),'Linked Comfy source files are unsupported')
                resolved=path.resolve(strict=True)
                require(resolved.is_relative_to(root),'Comfy source file escapes its inventory root')
                found.add(resolved)
    require({core/name for name in REQUIRED_CORE}<=found,'Incomplete Comfy core source inventory')
    require(any(path.is_relative_to(core/'comfy') for path in found),'Missing Comfy model implementation tree')
    names={path.name for path in found}
    require({'nodes_trellis2.py','flexgemm.py','model.py'}<=names,'Missing Pixal/Trellis/FlexGEMM implementation inventory')
    require(any(path.suffix.lower() in {'.pyd','.so','.dll','.dylib'} for path in found),
            'Missing compiled implementation inventory')
    return found


def _sha256(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
    return digest.hexdigest()


def capture_inventory(core,roots):
    core=Path(core).resolve(strict=True)
    roots=[Path(root).resolve(strict=True) for root in roots]
    files=[{'path':str(path),'sha256':_sha256(path)}
           for path in sorted(members(core,roots),key=lambda value:str(value).casefold())]
    return {'core':str(core),'roots':[str(root) for root in roots],'files':files}


def same_inventory(left,right):
    if not isinstance(left,dict) or not isinstance(right,dict):return False
    if set(left)!={'core','roots','files'} or set(right)!={'core','roots','files'}:return False
    try:
        left_files={row['path']:row['sha256'] for row in left['files']}
        right_files={row['path']:row['sha256'] for row in right['files']}
    except (TypeError,KeyError):return False
    return left['core']==right['core'] and left['roots']==right['roots'] and left_files==right_files \
        and len(left_files)==len(left['files']) and len(right_files)==len(right['files'])


def verify_inventory(inventory):
    require(isinstance(inventory,dict) and set(inventory)=={'core','roots','files'},
            'Complete installed Comfy source snapshot required')
    current=capture_inventory(inventory['core'],inventory['roots'])
    require(same_inventory(current,inventory),'Comfy source files differ from the installed startup snapshot')
    return inventory


def load_inventory(path,expected_core):
    payload=json.loads(Path(path).read_text(encoding='utf-8'))
    require(isinstance(payload,dict) and set(payload)=={'schemaVersion','inventory'}
            and payload['schemaVersion']==1,'Installed Comfy source snapshot configuration is invalid')
    inventory=payload['inventory']
    require(isinstance(inventory,dict) and set(inventory)=={'core','roots','files'}
            and isinstance(inventory['core'],str) and isinstance(inventory['roots'],list)
            and isinstance(inventory['files'],list),'Installed Comfy source inventory is malformed')
    require(Path(inventory['core']).resolve(strict=True)==Path(expected_core).resolve(strict=True),
            'Installed Comfy source snapshot targets another Comfy root')
    return verify_inventory(inventory)


def _normalized_code(code):
    constants=tuple(_normalized_code(item) if isinstance(item,types.CodeType) else item for item in code.co_consts)
    return code.replace(co_filename='<source>',co_consts=constants)


def _code_hash(code):
    return hashlib.sha256(marshal.dumps(_normalized_code(code))).hexdigest()


def _code_tree_hashes(code):
    yield _code_hash(code)
    for item in code.co_consts:
        if isinstance(item,types.CodeType):yield from _code_tree_hashes(item)


def _literal_signature(value,depth=0,budget=None):
    if budget is None:budget=[100000]
    budget[0]-=1
    if depth>64 or budget[0]<0:raise ValueError('Module constant exceeds the safe fingerprint limits')
    if value is None:return ['none']
    if type(value) is bool:return ['bool',value]
    if type(value) is int:return ['int',value]
    if type(value) is float:return ['float',value.hex()]
    if type(value) is str:return ['str',value]
    if type(value) is bytes:return ['bytes',value.hex()]
    if type(value) in (tuple,list):
        return [type(value).__name__,[_literal_signature(item,depth+1,budget) for item in value]]
    if type(value) is dict:
        rows=[(_literal_signature(key,depth+1,budget),_literal_signature(item,depth+1,budget))
              for key,item in value.items()]
        rows.sort(key=lambda row:json.dumps(row[0],sort_keys=True,separators=(',',':')))
        return ['dict',rows]
    if type(value) in (set,frozenset):
        values=[_literal_signature(item,depth+1,budget) for item in value]
        values.sort(key=lambda item:json.dumps(item,sort_keys=True,separators=(',',':')))
        return [type(value).__name__,values]
    raise ValueError('Module constant is not a supported literal value')


def _literal_hash(values):
    payload=json.dumps([(name,_literal_signature(value)) for name,value in sorted(values.items())],
                       sort_keys=True,separators=(',',':'))
    return hashlib.sha256(payload.encode()).hexdigest()


def _immutable_literal(value):
    if value is None or type(value) in (bool,int,float,str,bytes):return True
    if type(value) in (tuple,frozenset):return all(_immutable_literal(item) for item in value)
    return False


def _source_constants(source):
    assignments={}
    for statement in ast.parse(source).body:
        if isinstance(statement,ast.Assign):
            targets=statement.targets;value=statement.value
        elif isinstance(statement,ast.AnnAssign):
            targets=[statement.target];value=statement.value
        elif isinstance(statement,ast.AugAssign):
            targets=[statement.target];value=None
        else:continue
        for target in targets:
            if isinstance(target,ast.Name):
                assignments.setdefault(target.id,[]).append(value)
    constants={}
    for name,values in assignments.items():
        if len(values)!=1 or values[0] is None:continue
        try:value=ast.literal_eval(values[0])
        except (ValueError,TypeError,MemoryError,RecursionError):continue
        if name.isupper() or _immutable_literal(value):constants[name]=value
    return constants


def _loaded_codes(value,seen):
    marker=id(value)
    if marker in seen:return
    seen.add(marker)
    if isinstance(value,types.FunctionType):
        yield value.__code__
        for state in (value.__defaults__,value.__kwdefaults__):
            if state is not None:yield from _loaded_codes(state,seen)
        for cell in value.__closure__ or ():
            try:captured=cell.cell_contents
            except ValueError:continue
            yield from _loaded_codes(captured,seen)
        return
    if isinstance(value,types.MethodType):
        yield from _loaded_codes(value.__func__,seen)
        return
    if isinstance(value,(staticmethod,classmethod)):
        yield from _loaded_codes(value.__func__,seen)
        return
    if isinstance(value,property):
        for function in (value.fget,value.fset,value.fdel):
            if function is not None:yield from _loaded_codes(function,seen)
        return
    if isinstance(value,type):
        for member in vars(value).values():yield from _loaded_codes(member,seen)
        return
    if isinstance(value,types.CodeType):
        yield value
        return
    if isinstance(value,dict):
        for member in value.values():yield from _loaded_codes(member,seen)
    elif isinstance(value,(tuple,list,set,frozenset)):
        for member in value:yield from _loaded_codes(member,seen)


def loaded_source_code(roots):
    """Verify loaded callables and literal module constants against source and return a stable summary."""
    roots=[Path(root).resolve(strict=True) for root in roots]
    loaded={};module_namespaces={}
    for module in tuple(sys.modules.values()):
        namespace=getattr(module,'__dict__',None)
        if not isinstance(namespace,dict):continue
        module_file=namespace.get('__file__')
        if isinstance(module_file,(str,os.PathLike)):
            try:module_path=Path(module_file).resolve(strict=True)
            except (OSError,RuntimeError):module_path=None
            if module_path is not None and module_path.suffix.lower()=='.py' and _inside(module_path,roots):
                module_namespaces.setdefault(module_path,[]).append(namespace)
        seen=set()
        for value in tuple(namespace.values()):
            for code in _loaded_codes(value,seen):
                try:path=Path(code.co_filename).resolve(strict=True)
                except (OSError,RuntimeError):continue
                if path.suffix.lower()!='.py' or not _inside(path,roots):continue
                loaded.setdefault(path,set()).add(_code_hash(code))
    rows=[]
    for path in sorted(set(loaded)|set(module_namespaces),key=lambda value:str(value).casefold()):
        loaded_hashes=loaded.setdefault(path,set())
        source=path.read_bytes()
        compiled=compile(source,str(path),'exec',dont_inherit=True,optimize=sys.flags.optimize)
        expected=set(_code_tree_hashes(compiled))
        constants=_source_constants(source)
        expected.add(_literal_hash(constants))
        for namespace in module_namespaces.get(path,()):
            try:
                actual={name:namespace[name] for name in constants}
                require(_literal_hash(actual)==_literal_hash(constants),
                        'Loaded Comfy module constants differ from their source on disk')
            except (KeyError,TypeError,ValueError):
                require(False,'Loaded Comfy module constants differ from their source on disk')
            loaded_hashes.add(_literal_hash(actual))
        require(loaded_hashes<=expected,'Loaded Comfy Python code differs from its source on disk')
        loaded_digest=hashlib.sha256(json.dumps(sorted(loaded_hashes),separators=(',',':')).encode()).hexdigest()
        rows.append({'path':str(path),'sourceSha256':hashlib.sha256(source).hexdigest(),'loadedCodeSha256':loaded_digest})
    return rows
