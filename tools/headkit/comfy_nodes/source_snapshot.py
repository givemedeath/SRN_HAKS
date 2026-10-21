"""Source snapshots and loaded Python-code checks for the installed Comfy adapter."""
import ast
import functools
import gc
import hashlib
import inspect
import json
import operator
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


def _code_hash(code):
    # marshal tracks object identity/interning. Identical source compiled twice can
    # therefore produce different bytes, especially when the checker hashes itself.
    constants=[['code',_code_hash(value)] if isinstance(value,types.CodeType)
               else ['literal',_literal_signature(value)] for value in code.co_consts]
    payload={name:getattr(code,name) for name in ('co_argcount','co_posonlyargcount',
        'co_kwonlyargcount','co_nlocals','co_stacksize','co_flags','co_names',
        'co_varnames','co_freevars','co_cellvars','co_name','co_qualname','co_firstlineno')}
    payload.update(constants=constants,bytecode=code.co_code.hex(),
                   lines=code.co_linetable.hex(),exceptions=code.co_exceptiontable.hex())
    return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()


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
        value=_constant_ast_value(values[0])
        if value is _UNMATCHED_LITERAL:continue
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


_UNMATCHED_LITERAL=object()
_SAFE_BINARY_OPERATORS={
    ast.Add:operator.add,ast.Sub:operator.sub,ast.Mult:operator.mul,
    ast.Div:operator.truediv,ast.FloorDiv:operator.floordiv,ast.Mod:operator.mod,
    ast.Pow:operator.pow,ast.LShift:operator.lshift,ast.RShift:operator.rshift,
    ast.BitAnd:operator.and_,ast.BitOr:operator.or_,ast.BitXor:operator.xor,
}
_SAFE_UNARY_OPERATORS={ast.UAdd:operator.pos,ast.USub:operator.neg,
                       ast.Invert:operator.invert,ast.Not:operator.not_}


def _constant_ast_value(node,depth=0,budget=None):
    """Evaluate bounded literal data and numeric expressions without running source."""
    if budget is None:budget=[100000]
    budget[0]-=1
    if depth>32 or budget[0]<0:return _UNMATCHED_LITERAL
    def child(value):return _constant_ast_value(value,depth+1,budget)
    try:
        if isinstance(node,ast.Constant):
            result=node.value
        elif isinstance(node,(ast.Tuple,ast.List,ast.Set)):
            if len(node.elts)>budget[0]:return _UNMATCHED_LITERAL
            values=[child(value) for value in node.elts]
            if any(value is _UNMATCHED_LITERAL for value in values):return _UNMATCHED_LITERAL
            result={ast.Tuple:tuple,ast.List:list,ast.Set:set}[type(node)](values)
        elif isinstance(node,ast.Dict):
            if any(key is None for key in node.keys) or 2*len(node.keys)>budget[0]:return _UNMATCHED_LITERAL
            keys=[child(key) for key in node.keys];values=[child(value) for value in node.values]
            if any(value is _UNMATCHED_LITERAL for value in keys+values):return _UNMATCHED_LITERAL
            result=dict(zip(keys,values))
        elif isinstance(node,ast.UnaryOp) and type(node.op) in _SAFE_UNARY_OPERATORS:
            value=child(node.operand)
            if type(value) not in (bool,int,float,complex):return _UNMATCHED_LITERAL
            result=_SAFE_UNARY_OPERATORS[type(node.op)](value)
        elif isinstance(node,ast.BinOp) and type(node.op) in _SAFE_BINARY_OPERATORS:
            left=child(node.left);right=child(node.right)
            if type(left) not in (bool,int,float,complex) or type(right) not in (bool,int,float,complex):
                return _UNMATCHED_LITERAL
            if any(type(value) is int and value.bit_length()>4096 for value in (left,right)):
                return _UNMATCHED_LITERAL
            if isinstance(node.op,ast.Pow):
                if abs(right)>4096:return _UNMATCHED_LITERAL
                if type(left) is int and type(right) is int and right>0 \
                        and left.bit_length()*right>4096:return _UNMATCHED_LITERAL
            if isinstance(node.op,(ast.LShift,ast.RShift)):
                if type(right) is not int or abs(right)>4096:return _UNMATCHED_LITERAL
                if isinstance(node.op,ast.LShift) and type(left) is int \
                        and left.bit_length()+right>4096:return _UNMATCHED_LITERAL
            result=_SAFE_BINARY_OPERATORS[type(node.op)](left,right)
        else:return _UNMATCHED_LITERAL
    except (ArithmeticError,TypeError,ValueError,OverflowError,MemoryError,RecursionError):
        return _UNMATCHED_LITERAL
    if type(result) is int and result.bit_length()>4096:return _UNMATCHED_LITERAL
    return result


def _target_binds_name(target,name):
    if isinstance(target,ast.Name):return target.id==name
    if isinstance(target,(ast.Tuple,ast.List)):
        return any(_target_binds_name(item,name) for item in target.elts)
    if isinstance(target,ast.Starred):return _target_binds_name(target.value,name)
    return False


def _scope_literal_binding(scope,name):
    if isinstance(scope,ast.GeneratorExp):
        return any(_target_binds_name(row.target,name) for row in scope.generators),None
    if isinstance(scope,ast.Lambda):
        arguments=scope.args.posonlyargs+scope.args.args+scope.args.kwonlyargs
        if scope.args.vararg is not None:arguments.append(scope.args.vararg)
        if scope.args.kwarg is not None:arguments.append(scope.args.kwarg)
        if any(argument.arg==name for argument in arguments):return True,None
        bound=False
        def visit_lambda_scope(node):
            nonlocal bound
            if bound:return
            if isinstance(node,ast.Lambda):return
            if isinstance(node,ast.NamedExpr) and _target_binds_name(node.target,name):
                bound=True;return
            if isinstance(node,(ast.ListComp,ast.SetComp,ast.DictComp,ast.GeneratorExp)):
                if any(_target_binds_name(generator.target,name) for generator in node.generators):
                    bound=True;return
            for child in ast.iter_child_nodes(node):visit_lambda_scope(child)
        visit_lambda_scope(scope.body)
        return bound,None
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
    value=_constant_ast_value(bindings[0])
    if value is _UNMATCHED_LITERAL:return True,None
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
                value=_constant_ast_value(values[0])
                if value is _UNMATCHED_LITERAL:continue
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


def _source_attribute_literals(statements):
    """Only declared literal settings, never mutable runtime caches or descriptors."""
    for statement in statements:
        if isinstance(statement,ast.Assign):targets=statement.targets;node=statement.value
        elif isinstance(statement,ast.AnnAssign):targets=[statement.target];node=statement.value
        else:continue
        value=_constant_ast_value(node)
        if value is _UNMATCHED_LITERAL:continue
        for target in targets:
            if not isinstance(target,ast.Attribute):continue
            name=target.attr
            setting=any(token in name.casefold() for token in ('setting','config','option','param','preset','profile'))
            if name.isupper() or _immutable_literal(value) or setting:
                yield target,_literal_signature(value)


def _source_constructor_literals(source):
    classes={}
    def visit(node,ancestors):
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
            for statement in node.body:visit(statement,ancestors+[node.name,'<locals>'])
            return
        if isinstance(node,ast.ClassDef):
            fields={}
            for method in node.body:
                if isinstance(method,ast.FunctionDef) and method.name=='__init__':
                    arguments=method.args.posonlyargs+method.args.args
                    if arguments:
                        for target,signature in _source_attribute_literals(method.body):
                            if isinstance(target.value,ast.Name) and target.value.id==arguments[0].arg:
                                fields[target.attr]=signature
            if fields:classes['.'.join(ancestors+[node.name])]=fields
            for statement in node.body:visit(statement,ancestors+[node.name])
            return
        for child in ast.iter_child_nodes(node):
            if isinstance(child,ast.stmt):visit(child,ancestors)
    visit(ast.parse(source),[])
    return classes


def _stored_instance_attributes(value):
    """Read built-in dict/slot storage without calling user properties or getters."""
    fields={}
    for base in reversed(type(value).__mro__):
        for name,descriptor in vars(base).items():
            if name=='__dict__' and isinstance(descriptor,types.GetSetDescriptorType):
                fields.update(descriptor.__get__(value,type(value)))
            elif isinstance(descriptor,types.MemberDescriptorType):
                try:fields[name]=descriptor.__get__(value,type(value))
                except AttributeError:pass
    return fields


def _static_source_reference(node,namespace):
    if isinstance(node,ast.Name):return namespace.get(node.id,_UNMATCHED_LITERAL)
    if isinstance(node,ast.Attribute):
        parent=_static_source_reference(node.value,namespace)
        if isinstance(parent,types.ModuleType):return vars(parent).get(node.attr,_UNMATCHED_LITERAL)
        return inspect.getattr_static(parent,node.attr,_UNMATCHED_LITERAL)
    if isinstance(node,ast.Subscript):
        parent=_static_source_reference(node.value,namespace);key=_constant_ast_value(node.slice)
        if type(parent) in (dict,list,tuple) and key is not _UNMATCHED_LITERAL:
            try:return parent[key]
            except (KeyError,IndexError,TypeError):pass
    return _UNMATCHED_LITERAL


def _source_function_literals(source,compiled):
    nodes={}
    def visit_node(node,ancestors):
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
            # Decorated code objects start at their earliest decorator line.
            source_line=min([node.lineno]+[decorator.lineno for decorator in node.decorator_list])
            nodes[(node.name,source_line)]=(node,ancestors)
            for field,value in ast.iter_fields(node):
                if field=='body':continue
                children=value if isinstance(value,list) else (value,)
                for child in children:
                    if isinstance(child,ast.AST):visit_node(child,ancestors)
            for statement in node.body:visit_node(statement,ancestors+[node])
            return
        if isinstance(node,ast.ClassDef):
            for field,value in ast.iter_fields(node):
                if field=='body':continue
                children=value if isinstance(value,list) else (value,)
                for child in children:
                    if isinstance(child,ast.AST):visit_node(child,ancestors)
            for statement in node.body:visit_node(statement,ancestors)
            return
        if isinstance(node,(ast.Lambda,ast.GeneratorExp)):
            body=node.body if isinstance(node,ast.Lambda) else node.elt
            name='<lambda>' if isinstance(node,ast.Lambda) else '<genexpr>'
            key=(name,node.lineno,body.lineno,body.end_lineno,body.col_offset,body.end_col_offset)
            nodes[key]=(node,ancestors)
            for child in ast.iter_child_nodes(node):visit_node(child,ancestors+[node])
            return
        for child in ast.iter_child_nodes(node):visit_node(child,ancestors)
    visit_node(ast.parse(source),[])
    codes={}
    lambda_codes=[]
    def visit_code(code):
        if code.co_name in ('<lambda>','<genexpr>'):lambda_codes.append(code)
        elif code.co_name!='<module>':codes[(code.co_name,code.co_firstlineno)]=code
        for value in code.co_consts:
            if isinstance(value,types.CodeType):visit_code(value)
    visit_code(compiled)
    lambda_keys={key for key in nodes if key[0] in ('<lambda>','<genexpr>')}
    for code in lambda_codes:
        positions=set(code.co_positions()) if hasattr(code,'co_positions') else set()
        matches=[key for key in lambda_keys
                 if key[0]==code.co_name and key[1]==code.co_firstlineno and key[2:] in positions]
        if not matches:
            matches=[key for key in lambda_keys if key[0]==code.co_name and key[1]==code.co_firstlineno]
        if len(matches)==1:codes[matches[0]]=code
    states={}
    for key,(node,ancestors) in nodes.items():
        state={'defaults':{},'kwdefaults':{},'closure':{},'unresolved_defaults':{}}
        arguments=getattr(node,'args',None)
        positional=[] if arguments is None else arguments.posonlyargs+arguments.args
        defaults=[] if arguments is None else arguments.defaults
        for argument,default in zip(positional[-len(defaults):] if defaults else (),defaults):
            value=_constant_ast_value(default)
            signature=None if value is _UNMATCHED_LITERAL else _literal_value_signature(value)
            if signature is not None:state['defaults'][argument.arg]=signature
            else:state['unresolved_defaults'][argument.arg]=ast.dump(default,include_attributes=False)
        for argument,default in zip([] if arguments is None else arguments.kwonlyargs,
                                    [] if arguments is None else arguments.kw_defaults):
            if default is not None:
                value=_constant_ast_value(default)
                signature=None if value is _UNMATCHED_LITERAL else _literal_value_signature(value)
                if signature is not None:state['kwdefaults'][argument.arg]=signature
                else:state['unresolved_defaults'][argument.arg]=ast.dump(default,include_attributes=False)
        code=codes.get(key)
        if code is not None:
            for name in code.co_freevars:
                for scope in reversed(ancestors):
                    bound,signature=_scope_literal_binding(scope,name)
                    if bound:
                        if signature is not None:state['closure'][name]=signature
                        break
        if any(state.values()) or key[0] in ('<lambda>','<genexpr>'):states[key]=state
    return states


def _is_literal_ast(node):
    try:ast.literal_eval(node);return True
    except (TypeError,ValueError,MemoryError,RecursionError):return False


def _loaded_function_literals(function):
    code=function.__code__
    state={'defaults':{},'kwdefaults':{},'closure':{},'unresolved_defaults':[]}
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


class _LoadedInstanceState:
    def __init__(self,value):
        self.value=value;self.cls=type(value)
        self.members=_stored_instance_attributes(value)
        self.attributes={}
        for name,member in self.members.items():
            signature=_literal_value_signature(member)
            if signature is not None:self.attributes[name]=signature


def _execution_state(value):
    if isinstance(value,types.GeneratorType):return value.gi_code,value.gi_frame,value.gi_yieldfrom
    if isinstance(value,types.CoroutineType):return value.cr_code,value.cr_frame,value.cr_await
    if isinstance(value,types.AsyncGeneratorType):return value.ag_code,value.ag_frame,value.ag_await
    return None


class _LoadedFrameState:
    def __init__(self,frame):
        self.frame=frame;self.code=frame.f_code;self.members=dict(frame.f_locals)
        names=self.code.co_varnames
        positional=names[:self.code.co_argcount]
        keywords=names[self.code.co_argcount:self.code.co_argcount+self.code.co_kwonlyargcount]
        self.state={}
        for category,fields in (('defaults',positional),('kwdefaults',keywords),('closure',self.code.co_freevars)):
            self.state[category]={name:_literal_value_signature(self.members[name]) for name in fields if name in self.members}


def _callable_source_state(states,code):
    if code.co_name not in ('<lambda>','<genexpr>'):return states.get((code.co_name,code.co_firstlineno))
    positions=set(code.co_positions())
    matches=[state for key,state in states.items() if len(key)==6 and key[0]==code.co_name
             and key[1]==code.co_firstlineno and key[2:] in positions]
    require(len(matches)==1,'Loaded Comfy expression could not be matched to source')
    return matches[0]


def _source_frame_arguments(statements,namespace,frames):
    """Bind literal arguments at direct source creation sites; never invoke a factory."""
    bindings={}
    for statement in statements:
        if isinstance(statement,ast.Assign):targets=statement.targets;call=statement.value
        elif isinstance(statement,ast.AnnAssign):targets=[statement.target];call=statement.value
        else:continue
        if not isinstance(call,ast.Call) or not isinstance(call.func,ast.Name):continue
        for target in targets:
            execution=_execution_state(_static_source_reference(target,namespace))
            if execution is None or execution[1] is None:continue
            code,frame,_=execution
            if id(frame) not in frames or code.co_qualname!=call.func.id:continue
            fields={};names=code.co_varnames[:code.co_argcount]
            for name,node in list(zip(names,call.args))+[(row.arg,row.value) for row in call.keywords if row.arg is not None]:
                value=_constant_ast_value(node)
                if value is _UNMATCHED_LITERAL:value=_static_source_reference(node,namespace)
                signature=None if value is _UNMATCHED_LITERAL else _literal_value_signature(value)
                if signature is not None:fields[name]=signature
            require(not any(isinstance(row,ast.Starred) for row in call.args)
                    and not any(row.arg is None for row in call.keywords),
                    'Retained frame argument expansion cannot be safely matched to source')
            bindings[id(frame)]=fields
    return bindings


def _loaded_codes(value,seen,roots=()):
    marker=id(value)
    if marker in seen:return
    seen.add(marker)
    execution=_execution_state(value)
    if execution is not None:
        code,frame,delegate=execution
        yield code
        if frame is not None:yield from _loaded_codes(frame,seen,roots)
        if delegate is not None:yield from _loaded_codes(delegate,seen,roots)
        return
    if isinstance(value,types.FrameType):
        frame=_LoadedFrameState(value)
        yield value.f_code;yield frame
        for member in frame.members.values():yield from _loaded_codes(member,seen,roots)
        back=value.f_back
        if back is not None:
            try:covered=_inside(Path(back.f_code.co_filename).resolve(strict=True),roots)
            except (OSError,RuntimeError):covered=False
            if covered:yield from _loaded_codes(back,seen,roots)
        return
    if isinstance(value,types.TracebackType):
        yield from _loaded_codes(value.tb_frame,seen,roots)
        if value.tb_next is not None:yield from _loaded_codes(value.tb_next,seen,roots)
        return
    if isinstance(value,BaseException):
        for member in gc.get_referents(value):yield from _loaded_codes(member,seen,roots)
        return
    if isinstance(value,types.BuiltinFunctionType):
        owner=value.__self__
        if owner is not None and not isinstance(owner,(types.ModuleType,type)):
            yield from _loaded_codes(owner,seen,roots)
        return
    value_type=type(value)
    native_async=value_type.__module__=='_asyncio' and value_type.__name__ in ('Task','Future')
    native_cache=value_type.__module__=='functools' and value_type.__name__=='_lru_cache_wrapper'
    native_iterator=value_type.__module__ in ('builtins','itertools') and (
        inspect.getattr_static(value_type,'__next__',None) is not None
        or inspect.getattr_static(value_type,'__await__',None) is not None)
    native_weakref=value_type.__module__=='weakref' and value_type.__name__ in ('ReferenceType','ProxyType','CallableProxyType')
    native_container=(value_type.__module__=='builtins' and value_type.__name__ in ('dict_keys','dict_values','dict_items')
                      or value_type is types.MappingProxyType
                      or value_type.__module__=='collections' and value_type.__name__=='deque')
    if native_async or native_cache or native_iterator or native_weakref or native_container:
        # These CPython execution carriers keep callbacks/delegates/results in
        # native fields. GC exposes references without running or advancing them.
        for member in gc.get_referents(value):yield from _loaded_codes(member,seen,roots)
        return
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
    value_type=type(value)
    if _source_module_path(getattr(value_type,'__module__',None),roots) is not None:
        instance=_LoadedInstanceState(value)
        yield instance
        yield from _loaded_codes(value_type,seen,roots)
        for member in instance.members.values():yield from _loaded_codes(member,seen,roots)
    if isinstance(value,dict):
        for key,member in dict.items(value):
            yield from _loaded_codes(key,seen,roots)
            yield from _loaded_codes(member,seen,roots)
    elif isinstance(value,(tuple,list,set,frozenset)):
        for member in value:yield from _loaded_codes(member,seen,roots)
    elif callable(value):
        try:wrapped=inspect.getattr_static(value,'__wrapped__')
        except AttributeError:wrapped=value
        if wrapped is not value:yield from _loaded_codes(wrapped,seen,roots)


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
    loaded={};module_namespaces={};loaded_function_states={};loaded_class_states={};loaded_instances={};loaded_frames={}
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
                if isinstance(record,_LoadedFrameState):
                    loaded_frames[id(record.frame)]=record
                    continue
                if isinstance(record,_LoadedInstanceState):
                    loaded_instances[id(record.value)]=record
                    continue
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
    sources={path:path.read_bytes() for path in set(loaded)|set(module_namespaces)}
    constructors={path:_source_constructor_literals(source) for path,source in sources.items()}
    overrides={};frame_arguments={}
    for path,namespaces in module_namespaces.items():
        statements=ast.parse(sources[path]).body
        declarations=list(_source_attribute_literals(statements))
        for namespace in namespaces:
            frame_arguments.update(_source_frame_arguments(statements,namespace,loaded_frames))
            for target,signature in declarations:
                instance=_static_source_reference(target.value,namespace)
                if id(instance) in loaded_instances:
                    overrides.setdefault(id(instance),{})[target.attr]=signature
    instance_states={}
    for marker,state in loaded_instances.items():
        fields={}
        for base in reversed(state.cls.__mro__):
            class_path=_source_module_path(base.__module__,roots)
            fields.update(constructors.get(class_path,{}).get(base.__qualname__,{}))
        fields.update(overrides.get(marker,{}))
        if fields:
            path=_source_module_path(state.cls.__module__,roots)
            instance_states.setdefault(path,[]).append((state,fields))
    rows=[]
    for path in sorted(sources,key=lambda value:str(value).casefold()):
        loaded_hashes=loaded.setdefault(path,set())
        source=sources[path]
        compiled=compile(source,str(path),'exec',dont_inherit=True,optimize=sys.flags.optimize)
        expected=set(_code_tree_hashes(compiled))
        function_literals=_source_function_literals(source,compiled)
        expected.update(_literal_hash({category:values for category,values in state.items() if values})
                        for state in function_literals.values())
        class_literals=_source_class_literals(source)
        expected.update(_literal_hash(state) for state in class_literals.values())
        for code,function_state in loaded_function_states.get(path,()):
            source_state=_callable_source_state(function_literals,code)
            if not source_state:continue
            require(not source_state.get('unresolved_defaults'),
                    'Loaded Comfy function default expression cannot be safely matched to source')
            for category,values in source_state.items():
                if category=='unresolved_defaults':continue
                for name,signature in values.items():
                    require(function_state.get(category,{}).get(name)==signature,
                            'Loaded Comfy function defaults or closure differ from source on disk')
            comparable={category:{name:function_state[category][name] for name in values}
                        for category,values in source_state.items()
                        if category!='unresolved_defaults' and values}
            loaded_hashes.add(_literal_hash(comparable))
        for marker,frame in loaded_frames.items():
            if Path(frame.code.co_filename).resolve()!=path:continue
            source_state=_callable_source_state(function_literals,frame.code) or {}
            require(not source_state.get('unresolved_defaults'),
                    'Loaded Comfy frame defaults cannot be safely matched to source')
            comparable={}
            for category in ('defaults','kwdefaults','closure'):
                fields=dict(source_state.get(category,{}))
                if category!='closure':
                    start=0 if category=='defaults' else frame.code.co_argcount
                    end=frame.code.co_argcount if category=='defaults' else start+frame.code.co_kwonlyargcount
                    parameters=set(frame.code.co_varnames[start:end])
                    fields.update({name:signature for name,signature in frame_arguments.get(marker,{}).items() if name in parameters})
                if not fields:continue
                require(all(signature is not None and frame.state[category].get(name)==signature
                            for name,signature in fields.items()),
                        'Loaded Comfy frame defaults or closure differ from source on disk')
                comparable[category]=fields
            signature=_literal_hash(comparable)
            expected.add(signature);loaded_hashes.add(signature)
        for class_state in loaded_class_states.get(path,()):
            source_state=class_literals.get(class_state.qualname)
            if not source_state:continue
            comparable={name:class_state.attributes.get(name) for name in source_state}
            require(comparable==source_state,
                    'Loaded Comfy class attributes differ from source on disk')
            loaded_hashes.add(_literal_hash(comparable))
        for instance,source_state in instance_states.get(path,()):
            comparable={name:instance.attributes.get(name) for name in source_state}
            require(comparable==source_state,'Loaded Comfy instance attributes differ from source on disk')
            expected.add(_literal_hash(source_state));loaded_hashes.add(_literal_hash(comparable))
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
