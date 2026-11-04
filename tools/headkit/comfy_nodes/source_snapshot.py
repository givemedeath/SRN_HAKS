"""File membership and byte checks for the controlled Comfy deployment."""
import ast
from concurrent.futures import ThreadPoolExecutor
import _collections
import _thread
import enum
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
from .verification import CURRENT_PASS, VerificationPass


CORE_DATA={'input','output','temp','models','user','.venv','venv'}
REQUIRED_CORE={'main.py','execution.py','nodes.py','server.py','folder_paths.py'}


def require(condition,message):
    if not condition:raise ValueError(message)


def _linked(path):
    return path.is_symlink() or getattr(os.path,'isjunction',lambda value:False)(path)


class _SourceRoots(list):
    """Per-census path memoization; no state is reused across verification calls."""
    def __init__(self,roots):
        super().__init__(roots)
        self.module_paths={}
        self.resolved_paths={}
        self.class_coverage={}
        self.execution_proof={}
        self.override_ids=set()

    def covered_class(self,cls):
        if cls not in self.class_coverage:
            self.class_coverage[cls]=any(_source_module_path(base.__module__,self) is not None for base in cls.__mro__)
        return self.class_coverage[cls]

    def state_path(self,filename):
        path=self.resolve(filename)
        return path is not None and path.suffix.lower()=='.py' and _inside(path,self)

    def instance_state(self,value):
        return id(value) in self.override_ids or self.covered_class(type(value))

    def resolve(self,filename):
        if filename not in self.resolved_paths:
            try:self.resolved_paths[filename]=Path(filename).resolve(strict=True)
            except (OSError,RuntimeError):self.resolved_paths[filename]=None
        return self.resolved_paths[filename]


def _inside(path,roots):
    for root in roots:
        if not (path==root or path.is_relative_to(root)):continue
        relative=path.relative_to(root)
        # Match members(): runtime/data directories under the core are separate
        # inventories. An explicitly declared dependency root still includes them.
        if root==roots[0] and relative.parts and relative.parts[0] in CORE_DATA:continue
        if any(part in {'.git','.hg','.svn','__pycache__'} for part in relative.parts):continue
        return True
    return False


def members(core,roots):
    def fail_walk(error):raise error
    core=Path(core).resolve(strict=True)
    roots=[Path(root).resolve(strict=True) for root in roots]
    require(core in roots,'Inventory must cover the Comfy root')
    require(len(roots)==len(set(roots)),'Comfy source roots must be unique')
    found=set()
    for root in roots:
        require(root.is_dir(),'Missing Comfy source root')
        for current,dirs,names in os.walk(root,followlinks=False,onerror=fail_walk):
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
                require(path.is_file() and not _linked(path),'Regular unlinked Comfy source file required')
                resolved=path.resolve(strict=True)
                require(resolved==path.absolute(),'Regular unlinked Comfy source file required')
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
    session=CURRENT_PASS.get()
    if session is not None:return session.hash(path,retain_source=True,canonical=True)
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
    return digest.hexdigest()


def _inventory_files(paths):
    """Hash a canonical, ordered census with bounded request-scoped workers."""
    session=CURRENT_PASS.get()
    def checked(path):
        # ContextVars do not automatically follow worker threads. Reuse the
        # existing thread-safe pass explicitly, including its bounded source
        # retention, per-file lock and fresh-boundary lifetime.
        digest=session.hash(path,retain_source=True,canonical=True) if session is not None else _sha256(path)
        return {'path':str(path),'sha256':digest}
    if len(paths)<128:
        files=[checked(path) for path in paths]
    else:
        files=[]
        with ThreadPoolExecutor(max_workers=4) as workers:
            # Executor.map eagerly creates futures on supported Python versions.
            # Bound queued work as well as the four 1MiB streaming hash buffers.
            for offset in range(0,len(paths),128):
                files.extend(workers.map(checked,paths[offset:offset+128]))
    return files


def capture_inventory(core,roots):
    core=Path(core).resolve(strict=True)
    roots=[Path(root).resolve(strict=True) for root in roots]
    paths=sorted(members(core,roots),key=lambda value:str(value).casefold())
    return {'core':str(core),'roots':[str(root) for root in roots],'files':_inventory_files(paths)}


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


def _code_hash(code,memo=None):
    if memo is None:memo={}
    if id(code) in memo:return memo[id(code)]
    # marshal tracks object identity/interning. Identical source compiled twice can
    # therefore produce different bytes, especially when the checker hashes itself.
    constants=[['code',_code_hash(value,memo)] if isinstance(value,types.CodeType)
               else ['literal',_literal_signature(value)] for value in code.co_consts]
    payload={name:getattr(code,name) for name in ('co_argcount','co_posonlyargcount',
        'co_kwonlyargcount','co_nlocals','co_stacksize','co_flags','co_names',
        'co_varnames','co_freevars','co_cellvars','co_name','co_qualname','co_firstlineno')}
    payload.update(constants=constants,bytecode=code.co_code.hex(),
                   lines=code.co_linetable.hex(),exceptions=code.co_exceptiontable.hex())
    result=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    memo[id(code)]=result
    return result


def _code_tree_hashes(code,memo=None):
    if memo is None:memo={}
    yield _code_hash(code,memo)
    for item in code.co_consts:
        if isinstance(item,types.CodeType):yield from _code_tree_hashes(item,memo)


def _expected_code_hashes(source,path,optimize):
    # Analysis is shared by freshly hashed content inside loaded_source_code.
    # Do not retain raw source as persistent LRU keys (or traverse that cache).
    code=compile(source,path,'exec',dont_inherit=True,optimize=optimize)
    return frozenset(_code_tree_hashes(code))


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


def _scope_nodes(statements):
    """Walk compound blocks in one lexical scope, never nested callable/class bodies."""
    def visit(node):
        yield node
        for field,value in ast.iter_fields(node):
            if field=='body' and isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.Lambda,ast.ClassDef)):continue
            children=value if isinstance(value,list) else (value,)
            for child in children:
                if isinstance(child,ast.AST):yield from visit(child)
    for statement in statements:yield from visit(statement)


def _target_values(target,value):
    if isinstance(target,ast.Starred):
        yield from _target_values(target.value,value)
    elif isinstance(target,(ast.Tuple,ast.List)):
        stars=[index for index,item in enumerate(target.elts) if isinstance(item,ast.Starred)]
        values=[_UNMATCHED_LITERAL]*len(target.elts)
        if type(value) in (tuple,list) and len(stars)<=1:
            if not stars and len(value)==len(target.elts):values=list(value)
            elif stars and len(value)>=len(target.elts)-1:
                index=stars[0];tail=len(target.elts)-index-1
                values=list(value[:index])+[list(value[index:len(value)-tail])]+(list(value[-tail:]) if tail else [])
        for item,member in zip(target.elts,values):yield from _target_values(item,member)
    else:yield target,value


def _source_bindings(statements):
    for node in _scope_nodes(statements):
        if isinstance(node,ast.Assign):targets=node.targets;value=_constant_ast_value(node.value)
        elif isinstance(node,(ast.AnnAssign,ast.NamedExpr)):targets=[node.target];value=_constant_ast_value(node.value)
        elif isinstance(node,(ast.AugAssign,ast.For,ast.AsyncFor)):targets=[node.target];value=_UNMATCHED_LITERAL
        elif isinstance(node,ast.Delete):targets=node.targets;value=_UNMATCHED_LITERAL
        elif isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
            targets=[ast.Name(id=node.name)];value=_UNMATCHED_LITERAL
        elif isinstance(node,(ast.Import,ast.ImportFrom)):
            targets=[ast.Name(id=alias.asname or alias.name.split('.')[0]) for alias in node.names];value=_UNMATCHED_LITERAL
        elif isinstance(node,ast.ExceptHandler) and node.name:
            targets=[ast.Name(id=node.name)];value=_UNMATCHED_LITERAL
        elif isinstance(node,(ast.MatchAs,ast.MatchStar)) and node.name:
            targets=[ast.Name(id=node.name)];value=_UNMATCHED_LITERAL
        elif isinstance(node,ast.MatchMapping) and node.rest:
            targets=[ast.Name(id=node.rest)];value=_UNMATCHED_LITERAL
        elif isinstance(node,(ast.With,ast.AsyncWith)):
            targets=[item.optional_vars for item in node.items if item.optional_vars is not None];value=_UNMATCHED_LITERAL
        else:continue
        for target in targets:yield from _target_values(target,value)


def _unique_source_value(values):
    signatures=[None if value is _UNMATCHED_LITERAL else _literal_value_signature(value) for value in values]
    supported=[signature for signature in signatures if signature is not None]
    if not supported:return _UNMATCHED_LITERAL
    require(all(signature==supported[0] for signature in signatures),
            'Ambiguous source literal assignments cannot be safely matched')
    return values[0]


def _known_source_value(values,proven=False):
    # Startup proof permits dynamic initializers, never a blanket live-state exemption.
    # An unresolved initializer has no static value; other declared fields still check.
    try:return _unique_source_value(values)
    except ValueError:
        if not proven:raise
        return _UNMATCHED_LITERAL


def _condition_value(node, namespace):
    """Read a bounded literal predicate without eval, descriptors or user operators."""
    literal=_constant_ast_value(node)
    if literal is not _UNMATCHED_LITERAL:return literal
    if isinstance(node,(ast.Name,ast.Attribute,ast.Subscript)):
        if isinstance(node,ast.Attribute):
            parent=_static_source_reference(node.value,namespace)
            members=_stored_instance_attributes(parent) if not isinstance(parent,(type,types.ModuleType)) else {}
            value=members.get(node.attr,_static_source_reference(node,namespace))
        else:value=_static_source_reference(node,namespace)
        return value if _literal_value_signature(value) is not None else _UNMATCHED_LITERAL
    if isinstance(node,ast.UnaryOp) and isinstance(node.op,ast.Not):
        value=_condition_value(node.operand,namespace)
        return not value if value is not _UNMATCHED_LITERAL else value
    if isinstance(node,ast.BoolOp):
        for child in node.values:
            value=_condition_value(child,namespace)
            if value is _UNMATCHED_LITERAL:return value
            if isinstance(node.op,ast.And) and not value:return value
            if isinstance(node.op,ast.Or) and value:return value
        return value
    if isinstance(node,ast.Compare):
        left=_condition_value(node.left,namespace)
        if left is _UNMATCHED_LITERAL:return left
        operators={ast.Eq:operator.eq,ast.NotEq:operator.ne,ast.Lt:operator.lt,
                   ast.LtE:operator.le,ast.Gt:operator.gt,ast.GtE:operator.ge,
                   ast.Is:operator.is_,ast.IsNot:operator.is_not,
                   ast.In:lambda a,b:a in b,ast.NotIn:lambda a,b:a not in b}
        for operation,child in zip(node.ops,node.comparators):
            right=_condition_value(child,namespace)
            if right is _UNMATCHED_LITERAL:return right
            if isinstance(operation,(ast.Is,ast.IsNot)) and not (left is None or right is None
                    or type(left) is bool or type(right) is bool or left is Ellipsis or right is Ellipsis):
                return _UNMATCHED_LITERAL
            try:matched=operators[type(operation)](left,right)
            except (KeyError,TypeError,ValueError):return _UNMATCHED_LITERAL
            if not matched:return False
            left=right
        return True
    return _UNMATCHED_LITERAL


def _conditional_statements(statements, namespace=None, *, live_bindings=False):
    """Select only proven branches; unsupported predicates retain fail-closed analysis."""
    namespace=dict(namespace or {})
    result=[]
    def update_bindings(nodes):
        assignments={}
        for target,value in _source_bindings(nodes):
            if isinstance(target,ast.Name):assignments.setdefault(target.id,[]).append(value)
        for name,values in assignments.items():
            try:value=_unique_source_value(values)
            except ValueError:value=_UNMATCHED_LITERAL
            # Module-level factories/imports produce runtime input objects. They
            # may supply stored predicates, but never prove a literal assignment.
            if (live_bindings and all(item is _UNMATCHED_LITERAL for item in values)
                    and name in namespace and namespace[name] is not _UNMATCHED_LITERAL
                    and _literal_value_signature(namespace[name]) is None):continue
            namespace[name]=value
    for original in statements:
        # Copy only the statement whose compound blocks we replace. Expressions
        # and nested lexical bodies are read-only; deep copying an entire module
        # for every retained instance was quadratic in large model modules.
        fields=dict(ast.iter_fields(original))
        fields.update({name:getattr(original,name) for name in original._attributes if hasattr(original,name)})
        node=type(original)(**fields)
        if isinstance(node,ast.If):
            value=_condition_value(node.test,namespace)
            if value is not _UNMATCHED_LITERAL:
                selected=_conditional_statements(node.body if value else node.orelse,namespace,live_bindings=live_bindings)
                result.extend(selected)
                update_bindings(selected)
                continue
        # Keep lexical scopes separate; classes/functions get their own context.
        if not isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
            for field in ('body','orelse','finalbody'):
                if hasattr(node,field):setattr(node,field,_conditional_statements(getattr(node,field),namespace,live_bindings=live_bindings))
        result.append(node)
        if isinstance(node,ast.If):
            # An unresolved branch may never run. Its writes cannot become
            # facts for selecting a later branch (for example RAM-dependent
            # pinned-memory setup after an optional integrated-GPU override).
            for target,_ in _source_bindings([node]):
                if isinstance(target,ast.Name):namespace[target.id]=_UNMATCHED_LITERAL
        else:update_bindings([node])
    return result


def _setting_literal(name,value):
    return value is not _UNMATCHED_LITERAL and (name.isupper() or _immutable_literal(value)
        or any(token in name.casefold() for token in ('setting','config','option','param','preset','profile')))


def _source_namespace_bindings(statements, inherited=None, *, module_scope=True):
    """Resolve bounded namespace writes without calling accessors or running source."""
    factories=('globals','locals','vars')
    dynamic=('exec','eval','compile')
    aliases={name:{'factory:'+name} for name in factories}
    aliases.update({name:{'dynamic:'+name} for name in dynamic})
    aliases['__builtins__']={'mutator'}
    aliases['__name__']={'module-name'}
    aliases.update({name:set(tags) for name,tags in (inherited or {}).items()})
    nodes=list(_scope_nodes(statements))
    readers={'get','keys','values','items','copy','__getitem__','__contains__','__iter__','__len__'}
    module_mutators={'__setattr__','__delattr__','__getattribute__','__getattr__'}

    def reference(node):
        if isinstance(node,ast.NamedExpr):return reference(node.value)
        if isinstance(node,ast.Name):
            tags=aliases.get(node.id,set())
            return next(iter(tags)) if len(tags)==1 else ('namespace:foreign' if tags else None)
        if isinstance(node,ast.Attribute):
            owner=reference(node.value)
            if node.attr=='modules' and owner=='sys':return 'modules'
            if owner=='modules' and node.attr in ('get','__getitem__'):return 'module-lookup:'+node.attr
            callable_reader=bool(owner) and owner.startswith(('factory:','module-lookup:','dynamic:'))
            if callable_reader:
                # Native owners/reducers can recover an otherwise hidden namespace.
                # Only the identity-preserving call wrapper is supported here.
                return owner if node.attr=='__call__' else 'mutator'
            if owner=='builtins' and node.attr=='__dict__':return 'mutator'
            if node.attr=='__dict__':return 'namespace:own' if owner=='self-module' else 'namespace:foreign'
            if owner in ('self-module','modules','builtins') and node.attr in module_mutators:return 'mutator'
            if owner=='builtins' and node.attr in factories:return 'factory:'+node.attr
            if owner=='builtins' and node.attr in dynamic:return 'dynamic:'+node.attr
            if owner and owner.startswith('namespace:') and node.attr not in readers:return 'mutator'
        if (isinstance(node,ast.Subscript) and reference(node.value)=='modules'
                and reference(node.slice)=='module-name'):
            return 'self-module'
        if isinstance(node,ast.Call):
            factory=reference(node.func)
            if factory and factory.startswith('module-lookup:') and not node.keywords and node.args:
                valid=len(node.args)==1 or (factory=='module-lookup:get' and len(node.args)==2)
                if valid and reference(node.args[0])=='module-name':return 'self-module'
            if factory=='namespace:foreign':return 'namespace:foreign'
            if factory=='factory:vars' and node.args and reference(node.args[0])=='builtins':return 'mutator'
            if factory and factory.startswith('factory:'):
                own=not node.args and not node.keywords
                own=own or factory=='factory:vars' and len(node.args)==1 and not node.keywords and reference(node.args[0])=='self-module'
                return 'namespace:own' if own else 'namespace:foreign'
            if isinstance(node.func,ast.Name) and node.func.id=='getattr' and len(node.args)>=2:
                name=_constant_ast_value(node.args[1])
                if reference(node.args[0])=='builtins':
                    if type(name) is not str or name=='__dict__' or name in module_mutators:return 'mutator'
                    if name in factories:return 'factory:'+name
                    if name in dynamic:return 'dynamic:'+name
                if name=='__dict__':return 'namespace:own' if reference(node.args[0])=='self-module' else 'namespace:foreign'
                if reference(node.args[0])=='self-module' and (type(name) is not str or name in module_mutators):return 'mutator'
                if (reference(node.args[0]) or '').startswith('namespace:') and name not in readers:
                    return 'mutator'
        return None

    def capability(node):
        kind=reference(node) or ''
        return kind in ('mutator','self-module','modules','builtins') or kind.startswith(('namespace:','factory:','module-lookup:','dynamic:'))

    def alias_targets(target,expression):
        if isinstance(target,ast.Name):yield target.id,reference(expression)
        elif (isinstance(target,(ast.Tuple,ast.List)) and isinstance(expression,(ast.Tuple,ast.List))
                and len(target.elts)==len(expression.elts)):
            for item,value in zip(target.elts,expression.elts):yield from alias_targets(item,value)

    for node in nodes:
        if isinstance(node,ast.Import):
            for item in node.names:
                if item.name in ('builtins','sys'):aliases.setdefault(item.asname or item.name,set()).add(item.name)
        elif isinstance(node,ast.ImportFrom) and node.module=='sys':
            for item in node.names:
                if item.name=='modules':aliases.setdefault(item.asname or item.name,set()).add('modules')
        elif isinstance(node,ast.ImportFrom) and node.module=='builtins':
            for item in node.names:
                if item.name in factories:
                    aliases.setdefault(item.asname or item.name,set()).add('factory:'+item.name)
                elif item.name in dynamic:
                    aliases.setdefault(item.asname or item.name,set()).add('dynamic:'+item.name)
    # Monotone alias discovery handles forward/conditional aliases conservatively.
    for _ in range(len(nodes)+1):
        changed=False
        for node in nodes:
            if isinstance(node,ast.Assign):targets=node.targets;expression=node.value
            elif isinstance(node,(ast.AnnAssign,ast.NamedExpr)):targets=[node.target];expression=node.value
            else:continue
            for target in targets:
                for name,tag in alias_targets(target,expression):
                    if tag and tag not in aliases.setdefault(name,set()):
                        aliases[name].add(tag);changed=True
        if not changed:break
    require(not changed,'Source namespace aliases exceed the bounded analysis')

    for target,value in _source_bindings(statements):
        if isinstance(target,ast.Attribute) and reference(target.value)=='self-module':
            kind='namespace:own';name=target.attr
        elif isinstance(target,ast.Subscript):
            kind=reference(target.value)
            if not kind or not kind.startswith('namespace:'):continue
            name=_constant_ast_value(target.slice)
        else:continue
        require(module_scope and kind=='namespace:own' and type(name) is str
                and value is not _UNMATCHED_LITERAL,
                'Unsupported or ambiguous source namespace assignment')
        yield name,value
    for node in nodes:
        if isinstance(node,ast.Match) and capability(node.subject):
            captures=any((isinstance(pattern,(ast.MatchAs,ast.MatchStar)) and pattern.name)
                         or (isinstance(pattern,ast.MatchMapping) and pattern.rest)
                         for case in node.cases for pattern in _scope_nodes([case.pattern]))
            require(not captures,'Unsupported source namespace pattern binding')
        # Branch truth can depend on runtime state. Do not lose a namespace
        # capability by pretending its enclosing expression is ordinary data.
        choices=([node.body,node.orelse] if isinstance(node,ast.IfExp)
                 else node.values if isinstance(node,ast.BoolOp) else ())
        require(not any(capability(value) for value in choices),
                'Unsupported source namespace conditional expression')
        require(not (isinstance(node,(ast.Name,ast.Attribute,ast.Call)) and reference(node)=='mutator'),
                'Unsupported source namespace mutator reference')
        if isinstance(node,ast.Call):
            executor=reference(node.func)
            require(executor not in ('dynamic:exec','dynamic:eval')
                    and not (module_scope and executor=='dynamic:compile'),
                    'Unsupported source namespace dynamic execution')
            require(reference(node.func)!='mutator','Unsupported source namespace mutation')
            arguments=[*node.args,*(item.value for item in node.keywords)]
            # These accessors expose storage for the checks above; they do not mutate it.
            own_argument=bool(node.args) and reference(node.args[0])=='self-module'
            own_vars=(reference(node.func)=='factory:vars' and len(node.args)==1 and not node.keywords)
            own_getattr=(isinstance(node.func,ast.Name) and node.func.id=='getattr' and len(node.args) in (2,3)
                         and type(_constant_ast_value(node.args[1])) is str and reference(node)!='mutator')
            builtin_getattr=(bool(node.args) and reference(node.args[0])=='builtins' and own_getattr)
            if (own_argument and (own_vars or own_getattr)) or builtin_getattr:arguments=arguments[1:]
            kinds=[reference(value) for value in arguments]
            method=node.func.attr if isinstance(node.func,ast.Attribute) else None
            mutator=method in {'__setitem__','__delitem__','update','setdefault','pop','popitem','clear','setitem','delitem','ior'}
            require(not any(kind and (kind in ('mutator','self-module','modules','builtins') or kind.startswith(('factory:','module-lookup:','dynamic:')) or
                            kind.startswith('namespace:') and (kind=='namespace:own' or mutator)) for kind in kinds),
                    'Unsupported source namespace escape')
        if isinstance(node,(ast.Assign,ast.AnnAssign,ast.NamedExpr)):
            targets=node.targets if isinstance(node,ast.Assign) else [node.target]
            if capability(node.value):
                require(all(isinstance(target,ast.Name) for target in targets),
                        'Unsupported source namespace attribute escape')
        if isinstance(node,(ast.ListComp,ast.SetComp,ast.GeneratorExp,ast.DictComp)):
            values=[node.key,node.value] if isinstance(node,ast.DictComp) else [node.elt]
            require(not any(capability(value) for value in values),
                    'Unsupported source namespace comprehension escape')
        if isinstance(node,(ast.List,ast.Tuple,ast.Set,ast.Dict)):
            values=[*node.keys,*node.values] if isinstance(node,ast.Dict) else node.elts
            require(not any(capability(value) for value in values),
                    'Unsupported source namespace container escape')
        if isinstance(node,(ast.Return,ast.Yield,ast.YieldFrom)):
            require(not capability(node.value),'Unsupported source namespace return escape')
        if isinstance(node,ast.arguments):
            require(not any(capability(value) for value in [*node.defaults,*node.kw_defaults]),
                    'Unsupported source namespace default escape')
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
            yield from _source_namespace_bindings(node.body,aliases,module_scope=False)
        elif isinstance(node,ast.Lambda):
            require(not capability(node.body),'Unsupported source namespace lambda escape')
            yield from _source_namespace_bindings([ast.Expr(value=node.body)],aliases,module_scope=False)


def _source_constants(source,*,proven=False,namespace=None,selected=None):
    assignments={}
    statements=selected
    if statements is None:
        statements=(source if isinstance(source,ast.AST) else ast.parse(source)).body
        if proven:statements=_conditional_statements(statements,namespace,live_bindings=True)
    for target,value in _source_bindings(statements):
        if isinstance(target,ast.Name):assignments.setdefault(target.id,[]).append(value)
    if proven:
        for statement in statements:
            try:bindings=list(_source_namespace_bindings([statement]))
            except ValueError:continue  # Opaque namespace factories were verified before execution.
            for name,value in bindings:assignments.setdefault(name,[]).append(value)
    else:
        for name,value in _source_namespace_bindings(statements):assignments.setdefault(name,[]).append(value)
    constants={}
    for name,values in assignments.items():
        if not any(_setting_literal(name,value) for value in values):continue
        value=_known_source_value(values,proven)
        if value is not _UNMATCHED_LITERAL:
            _literal_signature(value);constants[name]=value
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
        elif isinstance(node,ast.NamedExpr):
            result=child(node.value)
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


def _scope_literal_binding(scope,name,namespace=None):
    if isinstance(scope,ast.GeneratorExp):
        return any(_target_binds_name(row.target,name) for row in scope.generators),None
    if isinstance(scope,ast.Lambda):
        arguments=scope.args.posonlyargs+scope.args.args+scope.args.kwonlyargs
        if scope.args.vararg is not None:arguments.append(scope.args.vararg)
        if scope.args.kwarg is not None:arguments.append(scope.args.kwarg)
        if any(argument.arg==name for argument in arguments):return True,None
        bindings=[value for target,value in _source_bindings([scope.body])
                  if isinstance(target,ast.Name) and target.id==name]
        if bindings:
            value=_unique_source_value(bindings)
            return True,None if value is _UNMATCHED_LITERAL else _literal_value_signature(value)
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
    if isinstance(scope,(ast.FunctionDef,ast.AsyncFunctionDef)):
        arguments=scope.args.posonlyargs+scope.args.args+scope.args.kwonlyargs
        if scope.args.vararg is not None:arguments.append(scope.args.vararg)
        if scope.args.kwarg is not None:arguments.append(scope.args.kwarg)
        if any(argument.arg==name for argument in arguments):return True,None
    statements=scope.body if namespace is None else _conditional_statements(scope.body,namespace)
    bindings=[value for target,value in _source_bindings(statements)
              if isinstance(target,ast.Name) and target.id==name]
    if not bindings:return False,None
    value=_unique_source_value(bindings)
    return True,None if value is _UNMATCHED_LITERAL else _literal_value_signature(value)


def _source_class_literals(source,*,proven=False,runtime_methods=None):
    classes={}
    def visit_statement(node,ancestors):
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
            for statement in node.body:visit_statement(statement,ancestors+[node.name,'<locals>'])
            return
        if isinstance(node,ast.ClassDef):
            qualname='.'.join(ancestors+[node.name])
            assignments={}
            for target,value in _source_bindings(node.body):
                if isinstance(target,ast.Name):assignments.setdefault(target.id,[]).append(value)
            attributes={}
            for name,values in assignments.items():
                if not any(_setting_literal(name,value) for value in values):continue
                value=_known_source_value(values,proven)
                if value is not _UNMATCHED_LITERAL:attributes[name]=_literal_value_signature(value)
            require(qualname not in classes or classes[qualname]==attributes,
                    'Ambiguous redeclared class settings cannot be safely matched')
            classes[qualname]=attributes
            if runtime_methods is not None:
                methods={}
                for method in node.body:
                    if not isinstance(method,(ast.FunctionDef,ast.AsyncFunctionDef)):continue
                    if not any(isinstance(decorator,ast.Name) and decorator.id=='classmethod'
                               for decorator in method.decorator_list):continue
                    arguments=method.args.posonlyargs+method.args.args
                    if not arguments:continue
                    receiver=arguments[0].arg;fields=set()
                    for target,_ in _source_bindings(method.body):
                        while isinstance(target,ast.Subscript):target=target.value
                        if isinstance(target,ast.Attribute) and isinstance(target.value,ast.Name) and target.value.id==receiver:
                            fields.add(target.attr)
                    for item in _scope_nodes(method.body):
                        if not (isinstance(item,ast.Call) and isinstance(item.func,ast.Attribute)
                                and item.func.attr in _MUTATING_METHODS):continue
                        owner=item.func.value
                        if isinstance(owner,ast.Attribute) and isinstance(owner.value,ast.Name) and owner.value.id==receiver:
                            fields.add(owner.attr)
                    if fields:methods[method.name]=fields
                runtime_methods[qualname]=methods
            for statement in node.body:visit_statement(statement,ancestors+[node.name])
            return
        for child in ast.iter_child_nodes(node):
            if isinstance(child,ast.stmt):visit_statement(child,ancestors)
    for statement in (source if isinstance(source,ast.AST) else ast.parse(source)).body:visit_statement(statement,[])
    return classes


def _source_attribute_literals(statements,*,proven=False):
    """Only declared literal settings, never mutable runtime caches or descriptors."""
    assignments={}
    for target,value in _source_bindings(statements):
        if not isinstance(target,ast.Attribute):continue
        key=ast.dump(target,include_attributes=False)
        assignments.setdefault(key,(target,[]))[1].append(value)
    for target,values in assignments.values():
        if not any(_setting_literal(target.attr,value) for value in values):continue
        value=_known_source_value(values,proven)
        if value is not _UNMATCHED_LITERAL:yield target,_literal_signature(value)


def _constructor_index(source):
    """Index class declarations once, retaining duplicates for ambiguity checks."""
    classes={}
    def visit(node,ancestors):
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
            for statement in node.body:visit(statement,ancestors+[node.name,'<locals>'])
            return
        if isinstance(node,ast.ClassDef):
            qualname='.'.join(ancestors+[node.name])
            classes.setdefault(qualname,[]).append([method for method in _scope_nodes(node.body)
                if isinstance(method,(ast.FunctionDef,ast.AsyncFunctionDef))])
            for statement in node.body:visit(statement,ancestors+[node.name])
            return
        for child in ast.iter_child_nodes(node):
            if isinstance(child,ast.stmt):visit(child,ancestors)
    visit(source if isinstance(source,ast.AST) else ast.parse(source),[])
    return classes


def _instance_literal_transitions(definitions,constructed=None,dynamic=None,external=None):
    """Source-owned writes of methods/captured callbacks, indexed once per class."""
    methods={}
    # Redeclared classes are ambiguous; constructor checking still fails closed.
    if len(definitions)!=1:return methods
    for method in definitions[0]:
        if method.decorator_list:continue
        arguments=method.args.posonlyargs+method.args.args
        if not arguments:continue
        receiver=arguments[0].arg
        scopes=[method];nodes=[];bindings=[]
        while scopes:
            scope=scopes.pop();args=scope.args
            parameters=args.posonlyargs+args.args+args.kwonlyargs+[args.vararg,args.kwarg]
            if scope is not method and any(arg and arg.arg==receiver for arg in parameters):continue
            local_nodes=list(_scope_nodes(scope.body))
            annotations={id(node.target) for node in local_nodes if isinstance(node,ast.AnnAssign) and node.value is None}
            local_bindings=[(target,value) for target,value in _source_bindings(scope.body) if id(target) not in annotations]
            if any(_target_binds_name(target,receiver) for target,_ in local_bindings):continue
            scopes.extend(node for node in local_nodes if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)))
            if scope is method and method.name=='__init__':continue
            nodes.extend(local_nodes);bindings.extend(local_bindings)
        fields={}
        for target,value in bindings:
            chain=[];owner=target
            while isinstance(owner,ast.Attribute):chain.append(owner.attr);owner=owner.value
            if (external is not None and len(chain)>1 and len(chain)<=4
                    and isinstance(owner,ast.Name) and owner.id==receiver):
                state=_UNMATCHED_LITERAL if value is _UNMATCHED_LITERAL else _literal_value_signature(value)
                external.setdefault(method.name,[]).append((tuple(reversed(chain)),state))
            if not (isinstance(target,ast.Attribute) and isinstance(target.value,ast.Name)
                    and target.value.id==receiver):continue
            if dynamic is not None and value is _UNMATCHED_LITERAL:
                dynamic.setdefault(method.name,set()).add(target.attr)
            if _setting_literal(target.attr,value):
                fields.setdefault(target.attr,[]).append(_literal_value_signature(value))
        if fields:methods[method.name]=fields
        if constructed is not None:
            for node in nodes:
                if not isinstance(node,(ast.Assign,ast.AnnAssign)) or not isinstance(node.value,ast.Call):continue
                targets=node.targets if isinstance(node,ast.Assign) else [node.target]
                for target in targets:
                    if (isinstance(target,ast.Attribute) and isinstance(target.value,ast.Name)
                            and target.value.id==receiver):
                        constructed.setdefault(method.name,{}).setdefault(target.attr,[]).append(node.value.func)
    return methods


def _source_constructor_literals(source, *, class_name=None, namespace=None, receiver=None, index=None,proven=False):
    index=_constructor_index(source) if index is None else index
    classes={}
    selected=index.items() if class_name is None else ((class_name,index.get(class_name,[])),)
    for qualname,definitions in selected:
        for methods in definitions:
            constructors=[]
            for method in methods:
                if isinstance(method,ast.FunctionDef) and method.name=='__init__':
                    arguments=method.args.posonlyargs+method.args.args;declared={}
                    if arguments:
                        scope=dict(namespace or {})
                        if receiver is not None:scope[arguments[0].arg]=receiver
                        for target,signature in _source_attribute_literals(_conditional_statements(method.body,scope),proven=proven):
                            if isinstance(target.value,ast.Name) and target.value.id==arguments[0].arg:
                                declared[target.attr]=signature
                    constructors.append(declared)
            fields=constructors[0] if constructors else {}
            if proven:
                alternatives=constructors+([classes[qualname]] if qualname in classes else [])
                fields={name:value for name,value in fields.items() if all(row.get(name)==value for row in alternatives)}
            else:
                require(all(declared==fields for declared in constructors),
                        'Ambiguous conditional constructor settings cannot be safely matched')
                require(qualname not in classes or classes[qualname]==fields,
                        'Ambiguous redeclared constructor settings cannot be safely matched')
            classes[qualname]=fields
    return classes


def _instance_container_writes(definitions):
    """Direct, source-owned container mutations, never a similarly named foreign field."""
    fields=set()
    if len(definitions)!=1:return fields
    for method in definitions[0]:
        args=method.args.posonlyargs+method.args.args
        if method.name=='__init__' or method.decorator_list or not args:continue
        receiver=args[0].arg;bindings=list(_source_bindings(method.body))
        if any(_target_binds_name(target,receiver) for target,_ in bindings):continue
        for node in _scope_nodes(method.body):
            target=None
            if isinstance(node,(ast.Assign,ast.AnnAssign,ast.AugAssign,ast.Delete)):
                targets=node.targets if isinstance(node,(ast.Assign,ast.Delete)) else [node.target]
                for target in targets:
                    if not isinstance(target,ast.Subscript):continue
                    while isinstance(target,ast.Subscript):target=target.value
                    if isinstance(target,ast.Attribute) and isinstance(target.value,ast.Name) and target.value.id==receiver:
                        fields.add(target.attr)
            elif isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr in _MUTATING_METHODS:
                target=node.func.value
                while isinstance(target,ast.Subscript):target=target.value
                if isinstance(target,ast.Attribute) and isinstance(target.value,ast.Name) and target.value.id==receiver:
                    fields.add(target.attr)
    return fields


def _same_stored_data(a,b,budget=4096):
    """Compare literal/copied containers and exact opaque references without equality hooks."""
    pending=[(a,b)];seen=set()
    while pending:
        a,b=pending.pop()
        if a is b:continue
        budget-=1
        if budget<0 or type(a)is not type(b):return False
        key=(id(a),id(b))
        if key in seen:continue
        seen.add(key)
        if type(a) in (list,tuple):
            if len(a)!=len(b) or len(a)>budget:return False
            pending.extend(zip(a,b));continue
        if type(a)is dict:
            # Avoid arbitrary key equality/hash methods too.
            if len(a)!=len(b) or len(a)>budget:return False
            if any(type(k)not in (str,int,float,bool,type(None))for mapping in (a,b)for k in mapping):return False
            if a.keys()!=b.keys():return False
            pending.extend((a[k],b[k])for k in a);continue
        x=_literal_value_signature(a);y=_literal_value_signature(b)
        if x is None or y is None or x!=y:return False
    return True


def _source_clone_plans(definitions,namespace,base):
    """Index returned same-class clones once per freshly verified class.

    Only the clone receives these writes. An ordinary instance does not inherit
    exemptions merely because its class has a clone method. Copies are compared
    against the actual parent, and no constructor, property or copy helper runs.
    """
    plans=[]
    if len(definitions)!=1:return plans
    for method in definitions[0]:
        args=method.args.posonlyargs+method.args.args
        if method.name=='__init__' or method.decorator_list or not args:continue
        receiver=args[0].arg;nodes=list(_scope_nodes(method.body))
        expressions={}
        for node in nodes:
            if isinstance(node,ast.Assign):targets=node.targets;value=node.value
            elif isinstance(node,(ast.AnnAssign,ast.NamedExpr)):targets=[node.target];value=node.value
            else:continue
            for target in targets:expressions[id(target)]=value
        bindings=[(target,expressions.get(id(target)))for target,_ in _source_bindings(method.body)];names={}
        if any(_target_binds_name(target,receiver)for target,_ in bindings):continue
        for target,value in bindings:
            if isinstance(target,ast.Name):names.setdefault(target.id,[]).append(value)
        parameters=method.args.posonlyargs+method.args.args+method.args.kwonlyargs+[method.args.vararg,method.args.kwarg]
        hidden=set(names)|{arg.arg for arg in parameters if arg is not None}
        globals_={k:v for k,v in namespace.items()if k not in hidden}
        constructors={}
        for name,values in names.items():
            if len(values)!=1 or not isinstance(values[0],ast.Call):continue
            call=values[0];targets=names.get(call.func.id,[])if isinstance(call.func,ast.Name)else []
            if not targets:targets=[call.func]
            if all((isinstance(t,ast.Attribute) and isinstance(t.value,ast.Name)
                    and t.value.id==receiver and t.attr=='__class__')
                   or _static_source_reference(t,globals_)is base for t in targets):constructors[name]=call
        returned={node.value.id for node in nodes if isinstance(node,ast.Return) and isinstance(node.value,ast.Name)}
        for name in constructors.keys()&returned:
            writes=[(target.attr,value)for target,value in bindings if isinstance(target,ast.Attribute)
                    and isinstance(target.value,ast.Name) and target.value.id==name]
            parents=[field for field,value in writes if isinstance(value,ast.Name)and value.id==receiver]
            copies=[]
            for field,value in writes:
                origin=value.args[0]if isinstance(value,ast.Call)and len(value.args)==1 and not value.keywords else value
                if isinstance(origin,ast.Attribute)and isinstance(origin.value,ast.Name)and origin.value.id==receiver:
                    copies.append((field,origin.attr))
            if parents:plans.append((tuple(parents),tuple(copies)))
    return plans


def _source_clone_fields(plans,base,members):
    accepted=set()
    for parents,copies in plans:
        for parent_field in parents:
            parent=members.get(parent_field,_UNMATCHED_LITERAL)
            if parent is _UNMATCHED_LITERAL or not any(cls is base for cls in type(parent).__mro__):continue
            source=_stored_instance_attributes(parent)
            accepted.add(parent_field)
            for field,origin in copies:
                if field in members and origin in source and _same_stored_data(members[field],source[origin]):accepted.add(field)
    return accepted


def _scope_expression_bindings(node):
    """Retain raw expressions only at unambiguous direct binding sites."""
    expressions={}
    def retain(target,value):
        expressions[id(target)]=value
        if isinstance(target,(ast.Tuple,ast.List)) and not any(isinstance(x,ast.Starred)for x in target.elts):
            for index,child in enumerate(target.elts):
                item=(value.elts[index]if isinstance(value,(ast.Tuple,ast.List))and len(value.elts)==len(target.elts)
                      else ast.Subscript(value=value,slice=ast.Constant(index),ctx=ast.Load())if value is not None else None)
                retain(child,item)
    for item in _scope_nodes(node.body):
        if isinstance(item,ast.Assign):targets=item.targets;value=item.value
        elif isinstance(item,(ast.AnnAssign,ast.NamedExpr)):targets=[item.target];value=item.value
        else:continue
        for target in targets:retain(target,value)
    bindings={}
    for target,_ in _source_bindings(node.body):
        if isinstance(target,ast.Name):bindings.setdefault(target.id,[]).append(expressions.get(id(target)))
    args=node.args
    parameters={a.arg for a in args.posonlyargs+args.args+args.kwonlyargs+[args.vararg,args.kwarg]if a is not None}
    return expressions,bindings,parameters


def _all_source_nodes(tree):
    # ast.walk lazily imports collections; validation must never import providers.
    pending=[tree]
    while pending:
        node=pending.pop();yield node
        pending.extend(ast.iter_child_nodes(node))


class _SourceFactoryWrites:
    """Bounded source-only checks for returned factory objects, after the census.

    This is not an evaluator: it resolves constructors/returns and compares stored
    values. It never calls a factory, property or equality hook. All ASTs and
    function summaries are shared with the fresh pass; no cross-pass cache.
    """
    def __init__(self,roots,source_tree):
        self.roots=roots;self.source_tree=source_tree;self.functions={};self.scopes={};self.returns={};self.classes={};self.receivers={};self.limit=20000

    def class_references(self,expr,node,namespace,trail=()):
        self.limit-=1
        if self.limit<0 or expr is None or len(trail)>12 or id(expr)in trail:return set()
        trail=trail+(id(expr),);_,bindings,parameters=self.scope(node)
        if isinstance(expr,ast.Name)and expr.id in bindings:
            choices=[self.class_references(v,node,namespace,trail)for v in bindings[expr.id]]
            return set().union(*choices)if choices and all(choices)else set()
        if isinstance(expr,ast.IfExp):
            left=self.class_references(expr.body,node,namespace,trail);right=self.class_references(expr.orelse,node,namespace,trail)
            return left|right if left and right else set()
        globals_={k:v for k,v in namespace.items()if k not in bindings and k not in parameters}
        target=_static_source_reference(expr,globals_)
        if not isinstance(target,type):return set()
        path=_source_module_path(target.__module__,self.roots)
        if path not in self.roots.execution_proof:return set()
        if path not in self.classes:self.classes[path]=set(_constructor_index(self.source_tree(path)))
        return {target} if target.__qualname__ in self.classes[path] else set()

    def function(self,value):
        for _ in range(5):
            if type(value)is not types.FunctionType:return None
            wrapped=vars(value).get('__wrapped__')
            if wrapped is None:break
            value=wrapped
        path=self.roots.resolve(value.__code__.co_filename)
        if path not in self.roots.execution_proof:return None
        if path not in self.functions:
            self.functions[path]={(n.name,min([n.lineno]+[d.lineno for d in n.decorator_list])):n
                for n in _all_source_nodes(self.source_tree(path))if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
        node=self.functions[path].get((value.__code__.co_name,value.__code__.co_firstlineno))
        return (node,value.__globals__)if node is not None else None

    def scope(self,node):
        if id(node)not in self.scopes:self.scopes[id(node)]=_scope_expression_bindings(node)
        return self.scopes[id(node)]

    def types(self,expr,node,namespace,trail=()):
        self.limit-=1
        if self.limit<0 or len(trail)>12 or expr is None:return set()
        key=(id(expr),id(node))
        if key in trail:return set()
        trail=trail+(key,);_,bindings,parameters=self.scope(node)
        if isinstance(expr,ast.Name)and expr.id in bindings:
            return set().union(*(self.types(v,node,namespace,trail)for v in bindings[expr.id]))
        if isinstance(expr,ast.Name)and expr.id in parameters:return set()
        if isinstance(expr,ast.IfExp):return self.types(expr.body,node,namespace,trail)|self.types(expr.orelse,node,namespace,trail)
        globals_={k:v for k,v in namespace.items()if k not in bindings and k not in parameters}
        if isinstance(expr,ast.Call):
            constructors=self.class_references(expr.func,node,namespace)
            if constructors:return constructors
            target=_static_source_reference(expr.func,globals_)
            function=self.function(target)
            if function is None:return set()
            child,scope=function;cache=(id(child),id(scope))
            if cache not in self.returns:
                self.returns[cache]=set()
                for statement in _scope_nodes(child.body):
                    if isinstance(statement,ast.Return):self.returns[cache].update(self.types(statement.value,child,scope,trail))
            return self.returns[cache]
        if isinstance(expr,ast.Attribute):
            classes=self.types(expr.value,node,namespace,trail);result=set()
            for cls in classes:
                method=inspect.getattr_static(cls,'__init__',None)
                function=self.function(method)
                if function is None:continue
                child,scope=function;args=child.args.posonlyargs+child.args.args
                if not args:continue
                expressions,_,_=self.scope(child)
                for statement in _scope_nodes(child.body):
                    targets=statement.targets if isinstance(statement,ast.Assign)else [statement.target]if isinstance(statement,ast.AnnAssign)else []
                    for target in targets:
                        if (isinstance(target,ast.Attribute)and target.attr==expr.attr and isinstance(target.value,ast.Name)
                                and target.value.id==args[0].arg):result.update(self.types(expressions.get(id(target)),child,scope,trail))
            return result
        return set()

    def captured_data(self,expr,value,node,namespace):
        """A verified reload factory can capture computed, data-only arguments.

        File paths/headers are runtime data, not constructor defaults. Keep this
        scope inside an exact source-declared callback/argument tuple: it grants
        no exemption to arbitrary fields or callbacks hidden in computed data.
        """
        if isinstance(expr,ast.Subscript) and type(_constant_ast_value(expr.slice))is int:expr=expr.value
        if not isinstance(expr,ast.Call):return False
        _,bindings,parameters=self.scope(node)
        globals_={k:v for k,v in namespace.items()if k not in bindings and k not in parameters}
        if self.function(_static_source_reference(expr.func,globals_))is None:return False
        pending=[value];seen=set();budget=4096
        while pending:
            item=pending.pop();budget-=1
            if budget<0:return False
            if item is None or type(item)in (bool,int,float,str,bytes):continue
            if type(item)not in (tuple,list,dict)or id(item)in seen:return False
            seen.add(id(item))
            if len(item)>budget:return False
            if type(item)is dict:
                if len(item)*2>budget:return False
                pending.extend(item.keys());pending.extend(item.values())
            else:pending.extend(item)
        return True

    def matches(self,expr,value,node,namespace,trail=(),*,capture=False):
        self.limit-=1
        if self.limit<0 or len(trail)>16 or expr is None:return False
        key=(id(expr),id(node))
        if key in trail:return False
        trail=trail+(key,);_,bindings,parameters=self.scope(node)
        literal=_constant_ast_value(expr)
        if literal is not _UNMATCHED_LITERAL:return _same_stored_data(literal,value)
        if isinstance(expr,ast.Name):
            if expr.id in bindings:return any(self.matches(v,value,node,namespace,trail,capture=capture)for v in bindings[expr.id])
            if expr.id in parameters:
                receiver=self.receivers.get(id(node));args=node.args.posonlyargs+node.args.args
                if receiver is not None and args and expr.id==args[0].arg:
                    cls,class_method=receiver
                    bases=value.__mro__ if class_method and isinstance(value,type)else type(value).__mro__
                    return any(base is cls for base in bases)
                return True  # The verified factory explicitly stores its caller's argument.
            return expr.id in namespace and namespace[expr.id]is value
        if isinstance(expr,(ast.Tuple,ast.List)):
            reload_args=(isinstance(expr,ast.Tuple)and type(value)is tuple and len(expr.elts)in (2,3)
                         and len(value)==len(expr.elts)and type(value[0])is types.FunctionType
                         and isinstance(expr.elts[1],ast.Tuple)and type(value[1])is tuple
                         and self.function(value[0])is not None
                         and self.matches(expr.elts[0],value[0],node,namespace,trail))
            return type(value)is {ast.Tuple:tuple,ast.List:list}[type(expr)] and len(expr.elts)==len(value) and all(
                self.matches(x,y,node,namespace,trail,capture=capture or reload_args and index==1)
                for index,(x,y)in enumerate(zip(expr.elts,value)))
        if capture and self.captured_data(expr,value,node,namespace):return True
        if isinstance(expr,ast.Call):return type(value)in self.types(expr,node,namespace)
        globals_={k:v for k,v in namespace.items()if k not in bindings and k not in parameters}
        return _static_source_reference(expr,globals_)is value

    def protocol_owner(self,owner,field,value,node,namespace=None):
        """Recognize a source-declared data protocol when its temporary owner is gone.

        The class declaring the field must also provide the managed methods the
        writer invokes on that exact expression. A bare attribute write, matching
        field name, property, or foreign method grants no permission.
        """
        retiring=isinstance(owner,ast.Name)
        if retiring:
            # A source-owned cache can pop its entry while a callback still
            # retains that object. Match its boolean lifecycle protocol rather
            # than pretending the object must still be in the active registry.
            # This is source protocol recognition, not a claim of past membership.
            expressions,bindings,_=self.scope(node);origins=bindings.get(owner.id,())
            if len(origins)!=1 or not isinstance(origins[0],ast.Subscript):return False
            indexed=origins[0];registries=self.references(indexed.value,node,namespace or {})
            if not registries or any(type(row)is not list or len(row)>256 for row in registries):return False
            base=ast.dump(indexed.value,include_attributes=False);index=ast.dump(indexed.slice,include_attributes=False)
            statements=list(_scope_nodes(node.body))
            if not any(isinstance(item,ast.Call)and isinstance(item.func,ast.Attribute)
                    and item.func.attr=='pop'and len(item.args)==1 and not item.keywords
                    and ast.dump(item.func.value,include_attributes=False)==base
                    and ast.dump(item.args[0],include_attributes=False)==index for item in statements):return False
            members=_stored_instance_attributes(value)
            if type(members.get(field))is not bool:return False
            if not any(isinstance(target,ast.Attribute)and target.attr==field
                    and isinstance(target.value,ast.Name)and target.value.id==owner.id
                    and type(_constant_ast_value(expressions.get(id(target))))is bool
                    for target,_ in _source_bindings(node.body)):return False
        elif isinstance(owner,ast.Attribute):
            args=node.args.posonlyargs+node.args.args
            root=owner
            while isinstance(root,ast.Attribute):root=root.value
            if not args or not isinstance(root,ast.Name)or root.id!=args[0].arg:return False
            if any(_target_binds_name(target,root.id)for target,_ in _source_bindings(node.body)):return False
        else:return False
        key=ast.dump(owner,include_attributes=False)
        methods={item.func.attr for item in _scope_nodes(node.body)if isinstance(item,ast.Call)
                 and isinstance(item.func,ast.Attribute)and ast.dump(item.func.value,include_attributes=False)==key}
        if not methods:return False
        for base in type(value).__mro__:
            path=_source_module_path(base.__module__,self.roots)
            if path not in self.roots.execution_proof:continue
            constructor=vars(base).get('__init__')
            source=self.function(constructor)
            if source is None:continue
            init,_=source;arguments=init.args.posonlyargs+init.args.args
            if not arguments:continue
            declared=any(isinstance(target,ast.Attribute)and target.attr==field and isinstance(target.value,ast.Name)
                         and target.value.id==arguments[0].arg and (not retiring or type(initial)is bool)
                         for target,initial in _source_bindings(init.body))
            if not declared:continue
            valid=True
            for name in methods:
                method=vars(base).get(name)
                if type(method)is not types.FunctionType or self.function(method)is None:valid=False;break
            if valid:return True
        return False

    def references(self,expr,node,namespace,trail=()):
        """Resolve bounded stored registry references; never execute an index or getter."""
        self.limit-=1
        if self.limit<0 or len(trail)>12 or expr is None:return []
        key=(id(expr),id(node))
        if key in trail:return []
        trail=trail+(key,);_,bindings,parameters=self.scope(node)
        if isinstance(expr,ast.Name):
            if expr.id in bindings:
                result=[]
                for value in bindings[expr.id]:result.extend(self.references(value,node,namespace,trail))
                if bindings[expr.id]==[None]:
                    for statement in _scope_nodes(node.body):
                        if isinstance(statement,(ast.For,ast.AsyncFor))and isinstance(statement.target,ast.Name)and statement.target.id==expr.id:
                            for values in self.references(statement.iter,node,namespace,trail):
                                if type(values)in (list,tuple)and len(values)<=256:result.extend(values)
                return result
            return [namespace[expr.id]]if expr.id not in parameters and expr.id in namespace else []
        if isinstance(expr,ast.Attribute):
            result=[]
            for value in self.references(expr.value,node,namespace,trail):
                members=_stored_instance_attributes(value)
                if type(value)is types.ModuleType:members=vars(value)
                if expr.attr in members:result.append(members[expr.attr])
            return result
        if isinstance(expr,ast.Subscript):
            result=[];index=_constant_ast_value(expr.slice)
            for value in self.references(expr.value,node,namespace,trail):
                if type(value)not in (list,tuple,dict)or len(value)>256:continue
                if index is _UNMATCHED_LITERAL:
                    result.extend(value.values()if type(value)is dict else value)
                elif type(index)in (str,int):
                    if type(value)is dict and any(type(k)not in (str,int)for k in value):continue
                    try:result.append(value[index])
                    except (KeyError,IndexError,TypeError):pass
            return result
        return []

    def callables(self,statements,namespace,fields,owner=None):
        for node in _scope_nodes(statements):
            if not isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):continue
            value=namespace.get(node.name)
            if isinstance(node,ast.ClassDef):
                if isinstance(value,type):
                    members=type.__dict__['__dict__'].__get__(value,type(value))
                    yield from self.callables(node.body,members,fields,value)
                continue
            body=list(_scope_nodes(node.body));assignments=[]
            for statement in body:
                targets=statement.targets if isinstance(statement,ast.Assign)else [statement.target]if isinstance(statement,ast.AnnAssign)else []
                assignments.extend(target for target in targets if isinstance(target,ast.Attribute)and target.attr in fields)
            if not assignments:continue
            candidates=(value,)
            if type(value)in (staticmethod,classmethod):candidates=(value.__func__,)
            elif type(value)is property:candidates=(value.fget,value.fset,value.fdel)
            for candidate in candidates:
                function=self.function(candidate)
                if function is not None and function[0]is node:
                    if owner is not None and type(value)is not staticmethod:self.receivers[id(node)]=(owner,type(value)is classmethod)
                    yield node,function[1],body,assignments;break

    def apply(self,tree,namespace,mismatches,writes):
        fields={field for _,_,values,_ in mismatches.values()for field in values}
        for node,namespace,statements,assignments in self.callables(tree.body,namespace,fields):
            expressions,bindings,_=self.scope(node)
            returned={member.id for statement in statements if isinstance(statement,ast.Return)and statement.value is not None
                      for member in _all_source_nodes(statement.value)if isinstance(member,ast.Name)}
            for target in assignments:
                root=target.value
                while isinstance(root,ast.Attribute):root=root.value
                factory=isinstance(root,ast.Name)and root.id in returned and root.id in bindings
                owners=self.types(target.value,node,namespace)if factory else set()
                referenced={id(value)for value in self.references(target.value,node,namespace)}
                expr=expressions.get(id(target))
                for identity,(value,_,values,explicit)in mismatches.items():
                    if target.attr not in values or target.attr in explicit:continue
                    if identity not in referenced and type(value)not in owners and not self.protocol_owner(target.value,target.attr,value,node,namespace):continue
                    members=_stored_instance_attributes(value)
                    if target.attr in members and self.matches(expr,members[target.attr],node,namespace):
                        _,owned=writes.setdefault(identity,(value,{}))
                        owned.setdefault(target.attr,[]).append(values[target.attr])


def _stored_instance_attributes(value):
    """Read built-in dict/slot storage without calling user properties or getters."""
    fields={}
    for base in reversed(type(value).__mro__):
        for name,descriptor in vars(base).items():
            if name=='__dict__' and isinstance(descriptor,(types.GetSetDescriptorType,types.MemberDescriptorType)):
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


def _source_function_literals(source,compiled,*,proven=False,closure_scopes=None):
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
    visit_node(source if isinstance(source,ast.AST) else ast.parse(source),[])
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
                    try:bound,signature=_scope_literal_binding(scope,name)
                    except ValueError as exc:
                        if not proven:raise
                        # A module plan also contains never-instantiated nested
                        # functions. Keep the failure and enforce it if that
                        # exact callable is actually reached by the live walk.
                        state.setdefault('deferred_closure_errors',{})[name]=str(exc)
                        if closure_scopes is not None:
                            closure_scopes.setdefault(key,{})[name]=(scope,ancestors)
                        break
                    if bound:
                        if signature is not None and (not proven or _setting_signature(name,signature)):
                            state['closure'][name]=signature
                        break
        if any(state.values()) or key[0] in ('<lambda>','<genexpr>'):states[key]=state
    return states


def _setting_signature(name,signature):
    def immutable(value):
        return (all(immutable(child) for child in value[1]) if value[0] in ('tuple','frozenset')
                else value[0] not in ('dict','list','set'))
    return name.isupper() or immutable(signature) or any(
        token in name.casefold() for token in ('setting','config','option','param','preset','profile'))


def _is_literal_ast(node):
    try:ast.literal_eval(node);return True
    except (TypeError,ValueError,MemoryError,RecursionError):return False


def _loaded_function_literals(function,fields=None):
    code=function.__code__
    state={'defaults':{},'kwdefaults':{},'closure':{},'unresolved_defaults':[]}
    if function.__defaults__:
        names=code.co_varnames[:code.co_argcount]
        for name,value in zip(names[-len(function.__defaults__):],function.__defaults__):
            if fields is not None and name not in fields.get('defaults',{}):continue
            signature=_literal_value_signature(value)
            if signature is not None:state['defaults'][name]=signature
    for name,value in (function.__kwdefaults__ or {}).items():
        if fields is not None and name not in fields.get('kwdefaults',{}):continue
        signature=_literal_value_signature(value)
        if signature is not None:state['kwdefaults'][name]=signature
    for name,cell in zip(code.co_freevars,function.__closure__ or ()):
        if fields is not None and name not in fields.get('closure',{}):continue
        try:value=cell.cell_contents
        except ValueError:continue
        signature=_literal_value_signature(value)
        if signature is not None:state['closure'][name]=signature
    return state


class _LoadedFunctionState:
    def __init__(self,function,fields=None):
        self.code=function.__code__
        self.source_fields=fields
        self.state=_loaded_function_literals(function,fields)


class _LoadedClassState:
    def __init__(self,cls):
        self.cls=cls
        self.is_enum=any(base is enum.Enum for base in type.__getattribute__(cls,'__mro__'))
        provider=sys.modules.get('pydantic.main')
        base_model=provider.__dict__.get('BaseModel') if type(provider) is types.ModuleType else None
        self.is_pydantic=base_model is not None and any(base is base_model for base in type.__getattribute__(cls,'__mro__'))
        self.module=cls.__module__
        self.qualname=cls.__qualname__
        self.members=dict(vars(cls))

    def signature(self,name):
        if name not in self.members:
            # Pydantic moves annotated defaults off the class into FieldInfo.
            # Read its native storage slot only: never run a validator, factory
            # or user descriptor, and still compare the exact declared literal.
            fields=self.members.get('__pydantic_fields__')
            if self.is_pydantic and type(fields) is dict:
                field=fields.get(name);field_type=type(field)
                slot=vars(field_type).get('default')
                factory=vars(field_type).get('default_factory')
                if (field_type.__module__=='pydantic.fields' and field_type.__qualname__=='FieldInfo'
                        and type(slot) is types.MemberDescriptorType
                        and type(factory) is types.MemberDescriptorType
                        and factory.__get__(field,field_type) is None):
                    return _literal_value_signature(slot.__get__(field,field_type))
            return None
        value=self.members[name]
        if self.is_enum and type(value) is self.cls:
            # Enum's standard metaclass replaces declared literals with member
            # objects. Compare their stored values, without invoking .value or
            # a user descriptor; changed enum values still fail verification.
            value=object.__getattribute__(value,'__dict__').get('_value_',_UNMATCHED_LITERAL)
        elif type(value) is _collections._tuplegetter:
            fields=self.members.get('_fields');defaults=self.members.get('_field_defaults')
            constructor=self.members.get('__new__')
            if not (type(fields) is tuple and all(type(item) is str for item in fields)
                    and type(defaults) is dict and name in defaults
                    and type(constructor) is staticmethod):return None
            constructor=constructor.__func__
            if type(constructor) is not types.FunctionType:return None
            arguments=constructor.__code__.co_varnames[:constructor.__code__.co_argcount]
            if arguments[1:]!=fields:return None
            # This is the standard C tuplegetter's metadata method, never a
            # user getter or a call to the generated constructor.
            index=_collections._tuplegetter.__reduce__(value)[1][0]
            if type(index) is not int or index!=fields.index(name):return None
            declared=_literal_value_signature(defaults[name])
            positional=constructor.__defaults__ or ()
            actual=dict(zip(arguments[-len(positional):] if positional else (),positional))
            if name not in actual or _literal_value_signature(actual[name])!=declared:return None
            return declared
        return _literal_value_signature(value)

    def runtime_fields(self,methods):
        fields=set()
        for name,writes in methods.items():
            # Recognize only actual built-in classmethod storage, never a
            # decorator lookalike, instance method or descriptor invocation.
            if type(self.members.get(name)) is classmethod:fields.update(writes)
        return fields


class _LoadedInstanceState:
    def __init__(self,value,members=None):
        self.value=value;self.cls=type(value)
        self.members=_stored_instance_attributes(value) if members is None else members

    def signature(self,name):
        # Fingerprint declared settings on demand. Traversal still follows every
        # member to find stale callbacks; unrelated runtime caches are not settings.
        return _literal_value_signature(self.members[name]) if name in self.members else None

    def parameter_slot(self,name):
        """Read standard PyTorch parameter storage without Tensor/getter calls."""
        if name in self.members:return False
        parameters=self.members.get('_parameters')
        if type(parameters) is not dict or name not in parameters:return False
        module=sys.modules.get('torch.nn.modules.module');parameter=sys.modules.get('torch.nn.parameter')
        if type(module) is not types.ModuleType or type(parameter) is not types.ModuleType:return False
        module_type=module.__dict__.get('Module');parameter_type=parameter.__dict__.get('Parameter')
        if module_type is None or parameter_type is None:return False
        if not any(base is module_type for base in self.cls.__mro__):return False
        value=parameters[name]
        return value is None or any(base is parameter_type for base in type(value).__mro__)


def _execution_state(value):
    if isinstance(value,types.GeneratorType):return value.gi_code,value.gi_frame,value.gi_yieldfrom
    if isinstance(value,types.CoroutineType):return value.cr_code,value.cr_frame,value.cr_await
    if isinstance(value,types.AsyncGeneratorType):return value.ag_code,value.ag_frame,value.ag_await
    return None


class _LoadedFrameState:
    def __init__(self,frame,*,fingerprint=True):
        self.frame=frame;self.code=frame.f_code;self.members=dict(frame.f_locals)
        self.state={}
        if not fingerprint:return
        names=self.code.co_varnames
        positional=names[:self.code.co_argcount]
        keywords=names[self.code.co_argcount:self.code.co_argcount+self.code.co_kwonlyargcount]
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
    for statement in _scope_nodes(statements):
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
            require(id(frame) not in bindings or bindings[id(frame)]==fields,
                    'Ambiguous retained frame creation arguments cannot be safely matched')
            bindings[id(frame)]=fields
    return bindings


def _loaded_codes(value,seen,roots=()):
    marker=id(value)
    if marker in seen:return
    seen.add(marker)
    value_type=type(value)
    # Exact builtin leaves cannot retain callbacks or user storage. Subclasses
    # deliberately keep the complete traversal below.
    if value is None or value is Ellipsis or value_type in (bool,int,float,complex,str,bytes,bytearray):return
    if value_type in (dict,list,tuple,set,frozenset):
        # Exact builtin containers have no user attributes/descriptors. GC gives
        # all owned entries in one snapshot; subclasses retain the full path.
        for member in gc.get_referents(value):yield from _loaded_codes(member,seen,roots)
        return
    if value_type.__module__=='weakref' and value_type.__name__ in ('ProxyType','CallableProxyType'):
        # Avoid isinstance/proxy attribute access, which dereferences dead proxies.
        for member in gc.get_referents(value):yield from _loaded_codes(member,seen,roots)
        return
    if isinstance(value,types.ModuleType):
        namespace=types.ModuleType.__dict__['__dict__'].__get__(value,value_type)
        for member in tuple(namespace.values()):yield from _loaded_codes(member,seen,roots)
        return
    execution=_execution_state(value)
    if execution is not None:
        code,frame,delegate=execution
        yield code
        if frame is not None:yield from _loaded_codes(frame,seen,roots)
        if delegate is not None:yield from _loaded_codes(delegate,seen,roots)
        return
    if isinstance(value,types.FrameType):
        needed=not isinstance(roots,_SourceRoots) or (roots.state_path(value.f_code.co_filename)
                and roots.resolve(value.f_code.co_filename) not in roots.execution_proof)
        frame=_LoadedFrameState(value,fingerprint=needed)
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
        members=_stored_instance_attributes(value)
        if members and (not isinstance(roots,_SourceRoots) or roots.instance_state(value)):yield _LoadedInstanceState(value,members)
        for member in gc.get_referents(value):yield from _loaded_codes(member,seen,roots)
        return
    if isinstance(value,types.FunctionType):
        yield value.__code__
        if not isinstance(roots,_SourceRoots) or roots.state_path(value.__code__.co_filename):
            fields=roots.proven_function_fields(value) if (isinstance(roots,_SourceRoots)
                    and roots.resolve(value.__code__.co_filename) in roots.execution_proof) else None
            yield _LoadedFunctionState(value,fields)
        if value.__dict__:
            if not isinstance(roots,_SourceRoots) or roots.instance_state(value):
                yield _LoadedInstanceState(value,value.__dict__)
        for member in gc.get_referents(value):yield from _loaded_codes(member,seen,roots)
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
    if isinstance(value,(staticmethod,classmethod,property)):
        members=_stored_instance_attributes(value)
        if members and (not isinstance(roots,_SourceRoots) or roots.instance_state(value)):yield _LoadedInstanceState(value,members)
        for member in gc.get_referents(value):yield from _loaded_codes(member,seen,roots)
        return
    if isinstance(value,type):
        class_path=_source_module_path(value.__module__,roots)
        if class_path is not None:
            yield _LoadedClassState(value)
        for base in value.__bases__:yield from _loaded_codes(base,seen,roots)
        for member in tuple(vars(value).values()):yield from _loaded_codes(member,seen,roots)
        return
    if isinstance(value,types.CodeType):
        yield value
        return
    value_type=type(value)
    if not isinstance(value,types.ModuleType):
        members=_stored_instance_attributes(value)
        covered=roots.covered_class(value_type) if isinstance(roots,_SourceRoots) else any(
            _source_module_path(base.__module__,roots) is not None for base in value_type.__mro__)
        if members or covered:
            if not isinstance(roots,_SourceRoots) or roots.instance_state(value):
                yield _LoadedInstanceState(value,members)
            yield from _loaded_codes(value_type,seen,roots)
            for member in members.values():yield from _loaded_codes(member,seen,roots)
    if isinstance(value,dict):
        for key,member in tuple(dict.items(value)):
            yield from _loaded_codes(key,seen,roots)
            yield from _loaded_codes(member,seen,roots)
    elif isinstance(value,(tuple,list,set,frozenset)):
        storage=next(base for base in (tuple,list,set,frozenset) if isinstance(value,base))
        for member in tuple(storage.__iter__(value)):yield from _loaded_codes(member,seen,roots)
    elif callable(value):
        try:wrapped=inspect.getattr_static(value,'__wrapped__')
        except AttributeError:wrapped=value
        if wrapped is not value:yield from _loaded_codes(wrapped,seen,roots)
    # Native foreign holders may retain callbacks outside dict/slot storage
    # (for example Context's HAMT). GC exposes these edges without getters.
    for member in gc.get_referents(value):yield from _loaded_codes(member,seen,roots)


def _source_module_path(module_name,roots):
    module=sys.modules.get(module_name)
    namespace=getattr(module,'__dict__',None)
    module_file=namespace.get('__file__') if isinstance(namespace,dict) else None
    if not isinstance(module_file,(str,os.PathLike)):return None
    key=(module_name,id(module),module_file)
    if isinstance(roots,_SourceRoots) and key in roots.module_paths:return roots.module_paths[key]
    try:path=Path(module_file).resolve(strict=True)
    except (OSError,RuntimeError):return None
    if path.suffix.lower()!='.py' or not _inside(path,roots):path=None
    if isinstance(roots,_SourceRoots):roots.module_paths[key]=path
    return path


_MUTATING_METHODS=frozenset({'update','setdefault','append','extend','insert','pop','popitem','clear','remove',
                             'add','discard','sort','reverse','__setitem__','__delitem__'})


def _module_package(path,namespace):
    package=namespace.get('__package__')
    if isinstance(package,str) and package:return package
    module_name=namespace.get('__name__','')
    return module_name if path.name=='__init__.py' else module_name.rpartition('.')[0]


def _runtime_state(tree):
    """Module globals the module's own verified source changes after their literal assignment.

    In-place container mutation (subscript stores/deletes or mutating methods) and
    `global` rebinds in its functions are runtime state, such as ComfyUI's custom-node
    registries, not settings. A change made from any other module, verified or not,
    still fails, so a registry exempts only what its owning source declares.
    """
    state=set()
    def visit(statements,local,declared):
        nodes=list(_scope_nodes(statements));aliases={}
        # Recognize only a single direct Name binding: out = MODULE_CACHE.
        # Copies, parameters, rebinding and attribute lookups provide no alias
        # proof. This is owning-source mutation evidence, never a foreign waiver.
        bindings={}
        for target,_ in _source_bindings(statements):
            if isinstance(target,ast.Name):bindings[target.id]=bindings.get(target.id,0)+1
        assignments=[node for node in nodes if isinstance(node,ast.Assign) and len(node.targets)==1
                     and isinstance(node.targets[0],ast.Name) and isinstance(node.value,ast.Name)]
        for _ in range(len(assignments)):
            changed=False
            for node in assignments:
                target=node.targets[0].id;source=node.value.id
                if bindings.get(target)!=1 or target in aliases:continue
                origin=aliases.get(source,source if source not in local else None)
                if origin is not None and origin!=target:aliases[target]=origin;changed=True
            if not changed:break
        def origin(name):return aliases.get(name,name if name not in local else None)
        for node in nodes:
            targets=(node.targets if isinstance(node,(ast.Assign,ast.Delete)) else
                     [node.target] if isinstance(node,(ast.AugAssign,ast.AnnAssign)) else [])
            for target in targets:
                # _scope_nodes, not ast.walk: verification must not import modules lazily.
                for item in _scope_nodes([target]):
                    # Only the written container, never a subscript read inside a key.
                    if not isinstance(getattr(item,'ctx',None),(ast.Store,ast.Del)):continue
                    if isinstance(item,ast.Subscript) and isinstance(item.value,ast.Name):
                        name=origin(item.value.id)
                        if name is not None:state.add(name)
                    elif isinstance(item,ast.Name) and item.id in declared:state.add(item.id)
            if (isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr in _MUTATING_METHODS
                    and isinstance(node.func.value,ast.Name)):
                name=origin(node.func.value.id)
                if name is not None:state.add(name)
    def functions(statements,enclosing):
        # Names local to an enclosing function shadow the module global in closures too.
        for function in _scope_nodes(statements):
            if isinstance(function,ast.ClassDef):functions(function.body,enclosing)
            if not isinstance(function,(ast.FunctionDef,ast.AsyncFunctionDef)):continue
            scope=list(_scope_nodes(function.body))
            declared={name for node in scope if isinstance(node,ast.Global) for name in node.names}
            arguments=function.args.posonlyargs+function.args.args+function.args.kwonlyargs
            local={argument.arg for argument in arguments+[function.args.vararg,function.args.kwarg] if argument}
            local|={node.id for node in scope if isinstance(node,ast.Name) and isinstance(node.ctx,(ast.Store,ast.Del))}
            # Imports, with/except/match captures and nested defs bind locals without a Name store.
            local|={target.id for target,_ in _source_bindings(function.body) if isinstance(target,ast.Name)}
            local=(local|enclosing)-declared
            visit(function.body,local,declared);functions(function.body,local)
    visit(tree.body,set(),set());functions(tree.body,set())
    return state


def _source_import_literals(statements,path,namespace,roots,sources,constants_cache,local_constants,runtime=None):
    """Verify retained literal imports without importing providers or invoking hooks."""
    imported={};nodes=list(_scope_nodes(statements));copies=[]
    def copy_pairs(target,value):
        if isinstance(target,ast.Name) and isinstance(value,ast.Name):yield target.id,value.id
        elif isinstance(target,(ast.Tuple,ast.List)) and isinstance(value,(ast.Tuple,ast.List)) and len(target.elts)==len(value.elts):
            for child,member in zip(target.elts,value.elts):yield from copy_pairs(child,member)
    for node in nodes:
        targets=node.targets if isinstance(node,ast.Assign) else [node.target] if isinstance(node,(ast.AnnAssign,ast.NamedExpr)) else []
        for target in targets:copies.extend(copy_pairs(target,node.value))
    for node in nodes:
        if not isinstance(node,ast.ImportFrom) or node.module=='__future__':continue
        provider_name=node.module or ''
        if node.level:
            package=_module_package(path,namespace)
            parts=package.split('.') if package else []
            provider_name='.'.join(parts[:len(parts)-node.level+1]+([provider_name] if provider_name else []))
        bindings=[]
        for item in node.names:
            if item.name=='*':
                bindings.extend((name,name) for name,value in tuple(namespace.items())
                                if not name.startswith('_') and name not in local_constants
                                and _literal_value_signature(value) is not None)
            else:
                names={item.asname or item.name}
                for _ in range(len(copies)+1):
                    updated=names|{target for target,origin in copies if origin in names}
                    if updated==names:break
                    names=updated
                for bound in names:
                    if bound in namespace and _literal_value_signature(namespace[bound]) is not None:
                        bindings.append((bound,item.name))
        if not bindings:continue
        provider=sys.modules.get(provider_name)
        require(isinstance(provider,types.ModuleType),f'Imported literal provider is unavailable: {provider_name} in {path.name}: {bindings}')
        values=types.ModuleType.__dict__['__dict__'].__get__(provider,type(provider))
        declared={}
        filename=values.get('__file__')
        if isinstance(filename,(str,os.PathLike)):
            provider_path=Path(filename).resolve()
            if provider_path.suffix.lower()=='.py' and _inside(provider_path,roots):
                require(provider_path in sources,'Imported literal provider is outside the source snapshot')
                if provider_path not in constants_cache:
                    constants_cache[provider_path]=_source_constants(sources[provider_path])
                declared=constants_cache[provider_path]
                if runtime is not None:
                    # A copy of provider runtime state legitimately diverges after import.
                    changing=runtime(provider_path,values)
                    bindings=[(bound,name) for bound,name in bindings if name not in changing]
        if runtime is not None:
            local=runtime(path,namespace);bindings=[(bound,name) for bound,name in bindings if bound not in local]
        for bound,name in bindings:
            require(name in values,'Imported literal provider no longer declares its binding')
            expected=declared.get(name,values[name])
            signature=_literal_value_signature(expected)
            require(signature is not None and _literal_value_signature(values[name])==signature,
                    'Imported literal provider differs from source on disk')
            require(_literal_value_signature(namespace[bound])==signature,
                    'Loaded Comfy imported literals differ from provider source')
            require(bound not in imported or _literal_value_signature(imported[bound])==signature,
                    'Ambiguous imported literal provenance')
            imported[bound]=expected
    return imported


def _startup_execution_proof(roots,session=None):
    module=sys.modules.get('_srn_verified_startup')
    if module is None:return {}
    require(type(module) is types.ModuleType,'Invalid startup proof module')
    namespace=vars(module);function=namespace.get('verified_sources')
    path=Path(__file__).with_name('verified_startup.py').resolve()
    require(isinstance(function,types.FunctionType) and function.__globals__ is namespace
            and Path(function.__code__.co_filename).resolve()==path,
            'Startup proof must come from the installed verifier')
    compiled=compile(session.source(path) if session else path.read_bytes(),str(path),'exec',dont_inherit=True,optimize=sys.flags.optimize)
    require(_code_hash(function.__code__) in set(_code_tree_hashes(compiled)),
            'Loaded startup verifier differs from source')
    return function(roots,session=session) if session else function(roots)


def loaded_source_code(roots):
    """Verify loaded code, literal callable/class state and module constants against source."""
    session=CURRENT_PASS.get()
    if session is None:
        session=VerificationPass('loaded-source')
        try:return _loaded_source_code(roots,session)
        finally:session.close()
    return _loaded_source_code(roots,session)


def _runtime_value_batches(modules,roots):
    for module in modules:
        namespace=getattr(module,'__dict__',None)
        if isinstance(namespace,dict):yield tuple(namespace.values())
    # Worker stacks retain executor instances after their job has completed.
    # Add only other threads currently executing managed source, streaming them
    # through the same census instead of a second whole-process object walk.
    current=_thread.get_ident()
    frames=[]
    for identity,frame in sys._current_frames().items():
        if identity==current:continue
        while frame is not None:
            if roots.state_path(frame.f_code.co_filename):frames.append(frame);break
            frame=frame.f_back
    yield tuple(frames)


def _loaded_source_code(roots,session):
    roots=_SourceRoots(Path(root).resolve(strict=True) for root in roots)
    execution_proof=_startup_execution_proof(roots,session)
    roots.execution_proof=execution_proof
    loaded={};module_namespaces={};loaded_function_states={};loaded_class_states={};loaded_instances={};loaded_frames={}
    sources={};trees={};indexes={};overrides={};override_paths={};frame_arguments={}
    proof_plans={};proven_bases={};instance_mismatches={};external_instance_writes={}
    # A single AST for each freshly verified content digest. Parsing precedes
    # traversal only for modules with static state checks, so we can retain just
    # instances whose literal state is actually consumed. All edges still walk.
    def source_tree(path):
        if path not in sources:sources[path]=session.source(path)
        key=(session.hashes[path],str(path),sys.flags.optimize)
        if key not in trees:
            trees[key]=ast.parse(sources[path]);session.counts['astParses']+=1
        return trees[key]
    def proof_plan(path):
        if path not in proof_plans:
            tree=source_tree(path)
            compiled=compile(sources[path],str(path),'exec',dont_inherit=True,optimize=sys.flags.optimize)
            runtime_methods={};closure_scopes={}
            classes=_source_class_literals(tree,proven=True,runtime_methods=runtime_methods)
            proof_plans[path]={'tree':tree,'functions':_source_function_literals(
                               tree,compiled,proven=True,closure_scopes=closure_scopes),
                               'expected':set(_code_tree_hashes(compiled)),
                               'classes':classes,'classRuntimeMethods':runtime_methods,'closureScopes':closure_scopes}
        return proof_plans[path]
    def check_proven_function(path,record):
        state=record.source_fields
        for category,values in state.items():
            if category=='unresolved_defaults':continue  # Initial factory execution is proven, not replayed.
            require(all(record.state.get(category,{}).get(name)==signature for name,signature in values.items()),
                    f'{path}:{record.code.co_qualname}: Loaded Comfy function defaults or closure differ from source on disk ({category})')
    def proven_function_fields(function):
        path=roots.resolve(function.__code__.co_filename)
        plan=proof_plan(path)
        fields=_callable_source_state(plan['functions'],function.__code__) or {}
        if fields.get('deferred_closure_errors'):
            cache=plan.setdefault('resolvedClosures',{});key=(function.__code__,id(function.__globals__))
            if key not in cache:
                fields={category:dict(values) for category,values in fields.items()}
                scopes=_callable_source_state(plan['closureScopes'],function.__code__) or {}
                for name,(scope,ancestors) in scopes.items():
                    hidden=set()
                    # A same-named global cannot resolve a shadowed outer local.
                    for ancestor in ancestors:
                        arguments=getattr(ancestor,'args',None)
                        if arguments is not None:
                            for argument in arguments.posonlyargs+arguments.args+arguments.kwonlyargs:
                                hidden.add(argument.arg)
                            for argument in (arguments.vararg,arguments.kwarg):
                                if argument is not None:hidden.add(argument.arg)
                        if isinstance(ancestor.body,list):
                            for target,_ in _source_bindings(ancestor.body):
                                if isinstance(target,ast.Name):hidden.add(target.id)
                    namespace={key:value for key,value in function.__globals__.items() if key not in hidden}
                    try:bound,signature=_scope_literal_binding(scope,name,namespace)
                    except ValueError:continue
                    if bound:
                        fields['deferred_closure_errors'].pop(name,None)
                        if signature is not None:fields['closure'][name]=signature
                if not fields['deferred_closure_errors']:fields.pop('deferred_closure_errors')
                cache[key]=fields
            fields=cache[key]
        require(not fields.get('deferred_closure_errors'),
                f'{path}:{function.__code__.co_qualname}: ambiguous live closure: {fields.get("deferred_closure_errors")}')
        return fields
    roots.proven_function_fields=proven_function_fields
    def check_proven_instance(record):
        fields={};transitions={};constructed_types={};dynamic_fields=set();container_fields=set();clone_fields=set()
        if record.cls not in proven_bases:
            proven_bases[record.cls]=[(base,path) for base in reversed(record.cls.__mro__)
                if (path:=_source_module_path(base.__module__,roots)) in execution_proof]
        for base,path in proven_bases[record.cls]:
            plan=proof_plan(path)
            if path not in indexes:
                indexes[path]=_constructor_index(plan['tree']);session.counts['constructorIndexes']+=1
            fields.update(_source_constructor_literals(plan['tree'],class_name=base.__qualname__,
                namespace=vars(sys.modules[base.__module__]),receiver=record.value,index=indexes[path],proven=True).get(base.__qualname__,{}))
            per_class=plan.setdefault('instanceTransitions',{})
            if base.__qualname__ not in per_class:
                constructors={};dynamic={};external={}
                definitions=indexes[path].get(base.__qualname__,[])
                literals=_instance_literal_transitions(definitions,constructors,dynamic,external)
                per_class[base.__qualname__]=(literals,constructors,dynamic,external,
                    _instance_container_writes(definitions),_source_clone_plans(definitions,vars(sys.modules[base.__module__]),base))
            literals,constructors,dynamic,external,containers,clones=per_class[base.__qualname__]
            container_fields.update(containers)
            clone_fields.update(_source_clone_fields(clones,base,record.members))
            for name in literals.keys()|constructors.keys()|dynamic.keys()|external.keys():
                method=vars(base).get(name)
                if type(method) is not types.FunctionType:continue
                if method.__code__.co_qualname!=base.__qualname__+'.'+name:continue
                dynamic_fields.update(dynamic.get(name,()))
                for field,states in literals.get(name,{}).items():transitions.setdefault(field,[]).extend(states)
                for field,calls in constructors.get(name,{}).items():
                    for call in calls:
                        target=_static_source_reference(call,vars(sys.modules[base.__module__]))
                        if isinstance(target,type):constructed_types.setdefault(field,[]).append(target)
                for chain,state in external.get(name,()):
                    target=record.value
                    for member in chain[:-1]:
                        target=_stored_instance_attributes(target).get(member,_UNMATCHED_LITERAL)
                        if target is _UNMATCHED_LITERAL:break
                    if target is _UNMATCHED_LITERAL or not roots.covered_class(type(target)):continue
                    # Retain only source-written target identities, not every
                    # traversed instance or a second copy of its member graph.
                    _,writes=external_instance_writes.setdefault(id(target),(target,{}))
                    writes.setdefault(chain[-1],[]).append(state)
        explicit=overrides.get(id(record.value),{})
        fields.update(explicit)
        mismatched=[]
        for name,signature in fields.items():
            current=record.signature(name)
            constructed=False
            if current is None and name in record.members:
                actual_type=type(record.members[name])
                for candidate in constructed_types.get(name,[]):
                    if actual_type is candidate:constructed=True;break
            changing=(name in dynamic_fields and name not in constructed_types and
                      (signature==['none'] or (current is not None and current[0]==signature[0])))
            container=(name in container_fields and signature[0]in ('dict','list','set')
                       and type(record.members.get(name))is {'dict':dict,'list':list,'set':set}[signature[0]])
            parameter=(signature==['none'] and record.parameter_slot(name))
            if current!=signature and (name in explicit or (current not in transitions.get(name,[]) and not constructed
                    and not changing and not parameter and not container and name not in clone_fields)):
                mismatched.append(name)
        if mismatched:
            label=f'{record.cls.__module__}.{record.cls.__qualname__}'
            instance_mismatches[id(record.value)]=(record.value,label,
                {name:record.signature(name) for name in mismatched},set(explicit))
    # Derived from each module's own verified source, sharing its single parsed tree.
    runtime_names={}
    def runtime_state(path,namespace=None):
        if path not in runtime_names:runtime_names[path]=_runtime_state(source_tree(path))
        return runtime_names[path]
    modules=tuple(sys.modules.values())
    for module in modules:
        namespace=getattr(module,'__dict__',None)
        if not isinstance(namespace,dict):continue
        filename=namespace.get('__file__')
        path=roots.resolve(filename) if isinstance(filename,(str,os.PathLike)) else None
        if path is None or path.suffix.lower()!='.py' or not _inside(path,roots):continue
        module_namespaces.setdefault(path,[]).append(namespace)
        statements=source_tree(path).body
        selected=_conditional_statements(statements,namespace,live_bindings=True)
        if path in execution_proof:
            # One plan per freshly checked file. Check each live namespace, then
            # stream callable/object state during the existing graph traversal.
            tree=proof_plan(path)['tree'];changing=runtime_state(path,namespace)
            constants=_source_constants(tree,proven=True,namespace=namespace,selected=selected)
            mismatched=[name for name,value in constants.items() if name not in changing
                        and (name not in namespace or _literal_value_signature(namespace[name])!=_literal_value_signature(value))]
            require(not mismatched,
                    f'{path}: Loaded Comfy module constants differ from their source on disk: {", ".join(mismatched)}')
        try:declarations=list(_source_attribute_literals(selected,proven=path in execution_proof))
        except ValueError as exc:raise ValueError(f'{path}: module attributes: {exc}') from exc
        for target,signature in declarations:
            instance=_static_source_reference(target.value,namespace)
            previous=overrides.setdefault(id(instance),{})
            require(target.attr not in previous or previous[target.attr]==signature,
                    'Conflicting source assignments for retained instance setting')
            previous[target.attr]=signature
            override_paths.setdefault(id(instance),set()).add(path)
    roots.override_ids=set(overrides)
    seen=set()
    code_memo={}
    for values in _runtime_value_batches(modules,roots):
        for value in values:
            for record in _loaded_codes(value,seen,roots):
                if isinstance(record,_LoadedFrameState):
                    path=roots.resolve(record.code.co_filename)
                    if path is not None and path.suffix.lower()=='.py' and _inside(path,roots) and path not in execution_proof:
                        loaded_frames[id(record.frame)]=record
                    continue
                if isinstance(record,_LoadedInstanceState):
                    if execution_proof:check_proven_instance(record)
                    if any(path not in execution_proof for path in override_paths.get(id(record.value),())) or any(
                            (path:=_source_module_path(base.__module__,roots)) is not None and path not in execution_proof
                            for base in record.cls.__mro__):
                        loaded_instances[id(record.value)]=record
                    continue
                if isinstance(record,_LoadedClassState):
                    class_path=_source_module_path(record.module,roots)
                    if class_path in execution_proof:
                        plan=proof_plan(class_path)
                        changing=record.runtime_fields(plan['classRuntimeMethods'].get(record.qualname,{}))
                        fields={name:signature for name,signature in plan['classes'].get(record.qualname,{}).items()
                                if name not in changing}
                        mismatched=[name for name,signature in fields.items() if record.signature(name)!=signature]
                        require(not mismatched,
                                'Loaded Comfy class attributes differ from source on disk: '
                                f'{class_path}: {record.qualname}: {", ".join(mismatched)}')
                    if class_path is not None and class_path not in execution_proof:
                        loaded_class_states.setdefault(class_path,[]).append(record)
                    continue
                function_state=record.state if isinstance(record,_LoadedFunctionState) else None
                code=record.code if isinstance(record,_LoadedFunctionState) else record
                path=roots.resolve(code.co_filename)
                if path is None or path.suffix.lower()!='.py' or not _inside(path,roots):continue
                if function_state is not None and path in execution_proof:check_proven_function(path,record)
                loaded_hashes=loaded.setdefault(path,set())
                # Retain the code beside its identity key: transient ids can be
                # reused, and CodeType equality omits some fingerprint fields.
                if id(code) not in code_memo:code_memo[id(code)]=(code,_code_hash(code))
                loaded_hashes.add(code_memo[id(code)][1])
                if function_state is not None and path not in execution_proof:
                    loaded_function_states.setdefault(path,[]).append((code,function_state))
    session.counts['objectsVisited']+=len(seen)
    session.counts['retainedInstances']+=len(loaded_instances)+len(instance_mismatches)
    session.counts['retainedFunctions']+=sum(map(len,loaded_function_states.values()))
    seen.clear();code_memo.clear()
    if instance_mismatches:
        factory=_SourceFactoryWrites(roots,source_tree)
        for path,namespaces in module_namespaces.items():
            if path in execution_proof:
                for namespace in namespaces:factory.apply(source_tree(path),namespace,instance_mismatches,external_instance_writes)
        remaining={}
        for identity,(value,label,fields,explicit) in instance_mismatches.items():
            _,writes=external_instance_writes.get(identity,(None,{}))
            for name,signature in fields.items():
                states=writes.get(name,())
                if name not in explicit and (_UNMATCHED_LITERAL in states or signature in states):continue
                remaining.setdefault(label,set()).add(name)
        if remaining:
            details=[label+': '+', '.join(sorted(names)) for label,names in sorted(remaining.items())]
            require(False,'Loaded Comfy instance attributes differ from source on disk: '+'; '.join(details))
    instance_mismatches.clear();external_instance_writes.clear()
    for path in set(loaded)|set(module_namespaces)|set(execution_proof):
        if path not in sources:sources[path]=session.source(path)
    constructor_trees={path:source_tree(path) for path in sources if path not in execution_proof}
    for path,namespaces in module_namespaces.items():
        if path in execution_proof:continue
        statements=constructor_trees[path].body
        for namespace in namespaces:
            frame_arguments.update(_source_frame_arguments(statements,namespace,loaded_frames))
    instance_states={}
    for marker,state in loaded_instances.items():
        fields={};paths=set(override_paths.get(marker,()))
        for base in reversed(state.cls.__mro__):
            class_path=_source_module_path(base.__module__,roots)
            declared={}
            if class_path in constructor_trees:
                # Uninstantiated classes have no retained constructor state to validate.
                # Their methods still participate in the exact loaded bytecode checks.
                namespace=vars(sys.modules[base.__module__])
                tree=constructor_trees[class_path]
                if class_path not in indexes:
                    indexes[class_path]=_constructor_index(tree);session.counts['constructorIndexes']+=1
                try:
                    declared=_source_constructor_literals(tree,class_name=base.__qualname__,namespace=namespace,
                        receiver=state.value,index=indexes[class_path]).get(base.__qualname__,{})
                except ValueError as exc:
                    raise ValueError(f'{class_path}:{base.__qualname__}: {exc}') from exc
            fields.update(declared)
            if declared:paths.add(class_path)
        fields.update(overrides.get(marker,{}))
        if fields:
            for path in paths:instance_states.setdefault(path,[]).append((state,fields))
    rows=[];constants_cache={}
    for path in sorted(sources,key=lambda value:str(value).casefold()):
        loaded_hashes=loaded.setdefault(path,set())
        source=sources[path]
        if path in execution_proof:
            expected=proof_plan(path)['expected']
            # The complete module body was checked before it executed. This proves
            # initializers without evaluating them twice. Known literal state was
            # checked above; proof never exempts live defaults, closures or settings.
            loaded_hashes.add(execution_proof[path])
            require(loaded_hashes<=expected,f'Loaded Comfy Python code differs from its source on disk: {path}')
            loaded_digest=hashlib.sha256(json.dumps(sorted(loaded_hashes),separators=(',',':')).encode()).hexdigest()
            rows.append({'path':str(path),'sourceSha256':hashlib.sha256(source).hexdigest(),'loadedCodeSha256':loaded_digest})
            continue
        compiled=compile(source,str(path),'exec',dont_inherit=True,optimize=sys.flags.optimize)
        expected=set(_code_tree_hashes(compiled))
        tree=constructor_trees[path]
        function_literals=_source_function_literals(tree,compiled)
        expected.update(_literal_hash({category:values for category,values in state.items() if values})
                        for state in function_literals.values())
        class_runtime_methods={}
        class_literals=_source_class_literals(tree,runtime_methods=class_runtime_methods)
        expected.update(_literal_hash(state) for state in class_literals.values())
        for code,function_state in loaded_function_states.get(path,()):
            source_state=_callable_source_state(function_literals,code)
            if not source_state:continue
            require(not source_state.get('unresolved_defaults'),
                    f'{path}:{code.co_qualname}: Loaded Comfy function default expression cannot be safely matched to source: {source_state.get("unresolved_defaults")}')
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
            changing=class_state.runtime_fields(class_runtime_methods.get(class_state.qualname,{}))
            source_state={name:signature for name,signature in source_state.items() if name not in changing}
            expected.add(_literal_hash(source_state))
            comparable={name:class_state.signature(name) for name in source_state}
            require(comparable==source_state,
                    'Loaded Comfy class attributes differ from source on disk: '
                    f'{path}: {class_state.qualname}')
            loaded_hashes.add(_literal_hash(comparable))
        for instance,source_state in instance_states.get(path,()):
            comparable={name:instance.signature(name) for name in source_state}
            require(comparable==source_state,'Loaded Comfy instance attributes differ from source on disk')
            expected.add(_literal_hash(source_state));loaded_hashes.add(_literal_hash(comparable))
        if path not in constants_cache:constants_cache[path]=_source_constants(tree)
        constants=constants_cache[path]
        expected.add(_literal_hash(constants))
        for namespace in module_namespaces.get(path,()):
            changing=runtime_state(path,namespace)
            imports=_source_import_literals(tree.body,path,namespace,roots,
                {**sources,**constructor_trees},constants_cache,set(constants)|changing,runtime_state)
            imported_actual={name:namespace[name] for name in imports}
            require(_literal_hash(imported_actual)==_literal_hash(imports),
                    'Loaded Comfy imported literals changed during verification')
            expected.add(_literal_hash(imports));loaded_hashes.add(_literal_hash(imported_actual))
            checked={name:value for name,value in constants.items() if name not in changing}
            expected.add(_literal_hash(checked))
            try:
                actual={name:namespace[name] for name in checked}
                require(_literal_hash(actual)==_literal_hash(checked),
                        'Loaded Comfy module constants differ from their source on disk')
            except (KeyError,TypeError,ValueError):
                require(False,'Loaded Comfy module constants differ from their source on disk')
            loaded_hashes.add(_literal_hash(actual))
        require(loaded_hashes<=expected,'Loaded Comfy Python code differs from its source on disk')
        loaded_digest=hashlib.sha256(json.dumps(sorted(loaded_hashes),separators=(',',':')).encode()).hexdigest()
        rows.append({'path':str(path),'sourceSha256':hashlib.sha256(source).hexdigest(),'loadedCodeSha256':loaded_digest})
    return rows
