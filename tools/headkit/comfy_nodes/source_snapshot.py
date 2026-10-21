"""Source snapshots and loaded Python-code checks for the installed Comfy adapter."""
import ast
import functools
import hashlib
import inspect
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
    if value is Ellipsis:return ['ellipsis']
    if type(value) is bool:return ['bool',value]
    if type(value) is int:return ['int',value]
    if type(value) is float:return ['float',value.hex()]
    if type(value) is complex:return ['complex',value.real.hex(),value.imag.hex()]
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
    if value is Ellipsis or type(value) in (bool,int,float,complex,str,bytes):return True
    if value is None:return True
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
        # Lower-case mutable globals may be live caches; only named settings remain source constants.
        name_lower=name.casefold()
        mutable_setting=any(token in name_lower for token in
                            ('setting','config','option','param','preset','profile'))
        if name.isupper() or _immutable_literal(value) or mutable_setting:
            _literal_signature(value)
            constants[name]=value
    return constants


def _literal_value_signature(value):
    try:return _literal_signature(value)
    except (TypeError,ValueError,MemoryError,RecursionError):return None


def _target_binds_name(target,name):
    if isinstance(target,ast.Name):return target.id==name
    if isinstance(target,(ast.Tuple,ast.List)):
        return any(_target_binds_name(item,name) for item in target.elts)
    if isinstance(target,ast.Starred):return _target_binds_name(target.value,name)
    return False


def _scope_literal_binding(scope,name):
    bindings=[]
    def visit(node):
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.Lambda,ast.ClassDef)):
            if getattr(node,'name',None)==name:bindings.append(None)
            return
        if isinstance(node,ast.Assign) and any(_target_binds_name(target,name) for target in node.targets):
            bindings.append(node.value)
        elif isinstance(node,ast.AnnAssign) and _target_binds_name(node.target,name):
            bindings.append(node.value)
        elif isinstance(node,ast.NamedExpr) and _target_binds_name(node.target,name):
            bindings.append(node.value)
        elif isinstance(node,(ast.For,ast.AsyncFor)) and _target_binds_name(node.target,name):
            bindings.append(None)
        elif isinstance(node,(ast.With,ast.AsyncWith)):
            for item in node.items:
                if item.optional_vars is not None and _target_binds_name(item.optional_vars,name):
                    bindings.append(None)
        elif isinstance(node,ast.ExceptHandler) and node.name==name:
            bindings.append(None)
        for child in ast.iter_child_nodes(node):visit(child)
    for statement in scope.body:visit(statement)
    if not bindings:return False,None
    if len(bindings)!=1 or bindings[0] is None:return True,None
    try:value=ast.literal_eval(bindings[0])
    except (TypeError,ValueError,MemoryError,RecursionError):return True,None
    return True,_literal_value_signature(value)


def _source_class_literals(source):
    classes={}
    def visit_statement(node,ancestors):
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
            for statement in node.body:visit_statement(statement,ancestors+[node.name,'<locals>'])
            return
        if isinstance(node,ast.ClassDef):
            qualname='.'.join(ancestors+[node.name])
            assignments={}
            for statement in node.body:
                if isinstance(statement,ast.Assign):targets=statement.targets;value=statement.value
                elif isinstance(statement,ast.AnnAssign):targets=[statement.target];value=statement.value
                elif isinstance(statement,ast.AugAssign):targets=[statement.target];value=None
                else:continue
                for target in targets:
                    if isinstance(target,ast.Name):assignments.setdefault(target.id,[]).append(value)
            attributes={}
            for name,values in assignments.items():
                if len(values)!=1 or values[0] is None:continue
                try:value=ast.literal_eval(values[0])
                except (TypeError,ValueError,MemoryError,RecursionError):continue
                bound,signature=_scope_literal_binding(node,name)
                if not bound or signature is None:continue
                name_lower=name.casefold()
                mutable_setting=any(token in name_lower for token in
                                    ('setting','config','option','param','preset','profile'))
                if name.isupper() or _immutable_literal(value) or mutable_setting:
                    attributes[name]=signature
            if attributes:classes[qualname]=attributes
            for statement in node.body:visit_statement(statement,ancestors+[node.name])
            return
        for child in ast.iter_child_nodes(node):
            if isinstance(child,ast.stmt):visit_statement(child,ancestors)
    for statement in ast.parse(source).body:visit_statement(statement,[])
    return classes


def _source_function_literals(source,compiled):
    nodes={}
    def visit_body(body,ancestors):
        for node in body:
            if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
                # Decorated code objects start at their earliest decorator line.
                source_line=min([node.lineno]+[decorator.lineno for decorator in node.decorator_list])
                key=(node.name,source_line)
                nodes[key]=(node,ancestors)
                visit_body(node.body,ancestors+[node])
            elif isinstance(node,ast.ClassDef):
                visit_body(node.body,ancestors)
    visit_body(ast.parse(source).body,[])
    codes={}
    def visit_code(code):
        if code.co_name!='<module>':codes[(code.co_name,code.co_firstlineno)]=code
        for value in code.co_consts:
            if isinstance(value,types.CodeType):visit_code(value)
    visit_code(compiled)
    states={}
    for key,(node,ancestors) in nodes.items():
        state={'defaults':{},'kwdefaults':{},'closure':{}}
        positional=node.args.posonlyargs+node.args.args
        for argument,default in zip(positional[-len(node.args.defaults):] if node.args.defaults else (),
                                    node.args.defaults):
            signature=_literal_value_signature(ast.literal_eval(default)) if _is_literal_ast(default) else None
            if signature is not None:state['defaults'][argument.arg]=signature
        for argument,default in zip(node.args.kwonlyargs,node.args.kw_defaults):
            if default is not None and _is_literal_ast(default):
                signature=_literal_value_signature(ast.literal_eval(default))
                if signature is not None:state['kwdefaults'][argument.arg]=signature
        code=codes.get(key)
        if code is not None:
            for name in code.co_freevars:
                for scope in reversed(ancestors):
                    bound,signature=_scope_literal_binding(scope,name)
                    if bound:
                        if signature is not None:state['closure'][name]=signature
                        break
        if any(state.values()):states[key]=state
    return states


def _is_literal_ast(node):
    try:ast.literal_eval(node);return True
    except (TypeError,ValueError,MemoryError,RecursionError):return False


def _loaded_function_literals(function):
    code=function.__code__
    state={'defaults':{},'kwdefaults':{},'closure':{}}
    if function.__defaults__:
        names=code.co_varnames[:code.co_argcount]
        for name,value in zip(names[-len(function.__defaults__):],function.__defaults__):
            signature=_literal_value_signature(value)
            if signature is not None:state['defaults'][name]=signature
    for name,value in (function.__kwdefaults__ or {}).items():
        signature=_literal_value_signature(value)
        if signature is not None:state['kwdefaults'][name]=signature
    for name,cell in zip(code.co_freevars,function.__closure__ or ()):
        try:value=cell.cell_contents
        except ValueError:continue
        signature=_literal_value_signature(value)
        if signature is not None:state['closure'][name]=signature
    return state


class _LoadedFunctionState:
    def __init__(self,function):
        self.code=function.__code__
        self.state=_loaded_function_literals(function)


class _LoadedClassState:
    def __init__(self,cls):
        self.module=cls.__module__
        self.qualname=cls.__qualname__
        self.attributes={}
        for name,value in vars(cls).items():
            signature=_literal_value_signature(value)
            if signature is not None:self.attributes[name]=signature


def _loaded_codes(value,seen,roots=()):
    marker=id(value)
    if marker in seen:return
    seen.add(marker)
    if isinstance(value,(functools.partial,functools.partialmethod)):
        yield from _loaded_codes(value.func,seen,roots)
        yield from _loaded_codes(value.args,seen,roots)
        yield from _loaded_codes(value.keywords or {},seen,roots)
        return
    if isinstance(value,types.FunctionType):
        yield value.__code__
        yield _LoadedFunctionState(value)
        for state in (value.__defaults__,value.__kwdefaults__):
            if state is not None:yield from _loaded_codes(state,seen,roots)
        for cell in value.__closure__ or ():
            try:captured=cell.cell_contents
            except ValueError:continue
            yield from _loaded_codes(captured,seen,roots)
        return
    if isinstance(value,types.MethodType):
        yield from _loaded_codes(value.__func__,seen,roots)
        if not isinstance(value.__self__,type):
            yield from _loaded_codes(value.__self__,seen,roots)
        return
    if isinstance(value,(staticmethod,classmethod)):
        yield from _loaded_codes(value.__func__,seen,roots)
        return
    if isinstance(value,property):
        for function in (value.fget,value.fset,value.fdel):
            if function is not None:yield from _loaded_codes(function,seen,roots)
        return
    if isinstance(value,type):
        yield _LoadedClassState(value)
        for member in vars(value).values():yield from _loaded_codes(member,seen,roots)
        return
    if isinstance(value,types.CodeType):
        yield value
        return
    if isinstance(value,dict):
        for member in value.values():yield from _loaded_codes(member,seen,roots)
    elif isinstance(value,(tuple,list,set,frozenset)):
        for member in value:yield from _loaded_codes(member,seen,roots)
    elif callable(value):
        try:wrapped=inspect.getattr_static(value,'__wrapped__')
        except AttributeError:wrapped=value
        if wrapped is not value:yield from _loaded_codes(wrapped,seen,roots)
        value_type=type(value)
        if _source_module_path(getattr(value_type,'__module__',None),roots) is not None:
            yield from _loaded_codes(value_type,seen,roots)
    else:
        value_type=type(value)
        if _source_module_path(getattr(value_type,'__module__',None),roots) is not None:
            yield from _loaded_codes(value_type,seen,roots)


def _source_module_path(module_name,roots):
    module=sys.modules.get(module_name)
    namespace=getattr(module,'__dict__',None)
    module_file=namespace.get('__file__') if isinstance(namespace,dict) else None
    if not isinstance(module_file,(str,os.PathLike)):return None
    try:path=Path(module_file).resolve(strict=True)
    except (OSError,RuntimeError):return None
    if path.suffix.lower()!='.py' or not _inside(path,roots):return None
    return path


def loaded_source_code(roots):
    """Verify loaded code, literal callable/class state and module constants against source."""
    roots=[Path(root).resolve(strict=True) for root in roots]
    loaded={};module_namespaces={};loaded_function_states={};loaded_class_states={}
    for module in tuple(sys.modules.values()):
        namespace=getattr(module,'__dict__',None)
        if not isinstance(namespace,dict):continue
        module_path=None
        module_file=namespace.get('__file__')
        if isinstance(module_file,(str,os.PathLike)):
            try:module_path=Path(module_file).resolve(strict=True)
            except (OSError,RuntimeError):module_path=None
            if module_path is not None and module_path.suffix.lower()=='.py' and _inside(module_path,roots):
                module_namespaces.setdefault(module_path,[]).append(namespace)
        seen=set()
        for value in tuple(namespace.values()):
            for record in _loaded_codes(value,seen,roots):
                if isinstance(record,_LoadedClassState):
                    class_path=_source_module_path(record.module,roots)
                    if class_path is not None:
                        loaded_class_states.setdefault(class_path,[]).append(record)
                    continue
                function_state=record.state if isinstance(record,_LoadedFunctionState) else None
                code=record.code if isinstance(record,_LoadedFunctionState) else record
                try:path=Path(code.co_filename).resolve(strict=True)
                except (OSError,RuntimeError):continue
                if path.suffix.lower()!='.py' or not _inside(path,roots):continue
                loaded_hashes=loaded.setdefault(path,set())
                loaded_hashes.add(_code_hash(code))
                if function_state is not None:
                    loaded_function_states.setdefault(path,[]).append((code,function_state))
    rows=[]
    for path in sorted(set(loaded)|set(module_namespaces),key=lambda value:str(value).casefold()):
        loaded_hashes=loaded.setdefault(path,set())
        source=path.read_bytes()
        compiled=compile(source,str(path),'exec',dont_inherit=True,optimize=sys.flags.optimize)
        expected=set(_code_tree_hashes(compiled))
        function_literals=_source_function_literals(source,compiled)
        expected.update(_literal_hash(state) for state in function_literals.values())
        class_literals=_source_class_literals(source)
        expected.update(_literal_hash(state) for state in class_literals.values())
        for code,function_state in loaded_function_states.get(path,()):
            source_state=function_literals.get((code.co_name,code.co_firstlineno))
            if not source_state:continue
            for category,values in source_state.items():
                for name,signature in values.items():
                    require(function_state.get(category,{}).get(name)==signature,
                            'Loaded Comfy function defaults or closure differ from source on disk')
            comparable={category:{name:function_state[category][name] for name in values}
                        for category,values in source_state.items() if values}
            loaded_hashes.add(_literal_hash(comparable))
        for class_state in loaded_class_states.get(path,()):
            source_state=class_literals.get(class_state.qualname)
            if not source_state:continue
            comparable={name:class_state.attributes.get(name) for name in source_state}
            require(comparable==source_state,
                    'Loaded Comfy class attributes differ from source on disk')
            loaded_hashes.add(_literal_hash(comparable))
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
