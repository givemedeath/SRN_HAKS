"""Explicit finite material replay runs with full opening and closing verification.

No content-hash cache: each requested semantic input is rehashed. Unrelated frozen
historical execution inputs are checked at both boundaries and by the launcher.
Default material contexts retain their full per-call verification.
"""
import time
from pathlib import Path
import phenotype_infrastructure_adoption as a
import target_contract as c

KIND='typed-original-material-parent-guarded-run'
_SEAL=object()
FIELDS={'schemaVersion','kind','target','part','coordinateSpace','adoptionProof','originalRecipe','representation','parentScope','semanticInputs','fullInputs','currentHelpers'}


def inputs_for(context):
    from phenotype_material_execution_adoption import MaterialExecution,_SEAL as MATERIAL_SEAL
    c.require(type(context) is MaterialExecution and getattr(context,'_seal',None) is MATERIAL_SEAL and hasattr(context,'_parent_scope_pin') and not hasattr(context,'_run_state'),'Unsealed, legacy, or nested material run')
    full=dict(a.plain(context._verified.inputs))
    def merge(rows):
        for p,h in rows.items():
            c.require(p not in full or full[p]==h,'Material run input digest collision')
            full[p]=h
    for represented in context._representations.values():merge(a.plain(represented.inputs))
    for closure in context._scoped_closures.values():merge(a.plain(closure))
    semantic=dict(a.plain(context._graph)['pins'])
    semantic.update({context._parent_scope_pin['path']:context._parent_scope_pin['sha256'],context._recipe_pin['path']:context._recipe_pin['sha256'],context._target['path']:context._target['sha256']})
    scope=a.read_json(context._parent_scope_pin['path'])
    for pin in scope['geometryRepresentations'].values():semantic[pin['path']]=pin['sha256']
    for name,row in a.plain(context._graph)['geometries'].items():
        value=a.plain(context._graph)['values'][name]
        if 'nativeCornerArchive' in value:
            pin=value['nativeCornerArchive'];semantic[pin['path']]=pin['sha256']
    for p,h in semantic.items():
        c.require(p not in full or full[p]==h,'Material semantic input digest collision');full[p]=h
    helpers=dict(a.plain(context._verified.proof)['currentHelpers'])
    c.require(helpers.get(str(Path(__file__).resolve()))==c.sha(__file__),'Material run helper absent or stale in proof')
    return full,semantic,helpers


def descriptor(context,proof_pin):
    full,semantic,helpers=inputs_for(context)
    c.require(proof_pin['path'] in full and full[proof_pin['path']]==proof_pin['sha256'],'Material run proof association differs')
    return {'schemaVersion':1,'kind':KIND,'target':a.plain(context._target),'part':context._recipe['part'],'coordinateSpace':'working','adoptionProof':dict(proof_pin),'originalRecipe':a.plain(context._recipe_pin),'representation':a.plain(context._representation_pin),'parentScope':a.plain(context._parent_scope_pin),'semanticInputs':semantic,'fullInputs':full,'currentHelpers':helpers}


class _Run:
    def __init__(self,base,pin,value):
        self._seal=_SEAL;self.base=base;self.pin=dict(pin);self.value=a.immutable(value);self.closed=False;self.failed=False;self.calls=0;self.bytes=0;self.seconds=0.;self.started=time.perf_counter();self.checked={}
    def hash_rows(self,rows):
        c.require(self._seal is _SEAL and not self.closed and not self.failed,'Material run closed or failed')
        try:
            for p,h in rows.items():
                started=time.perf_counter();actual=c.sha(p);self.seconds+=time.perf_counter()-started;self.calls+=1;self.bytes+=Path(p).stat().st_size;self.checked[p]=self.checked.get(p,0)+1
                c.require(actual==h,'Material run input changed: '+p)
        except BaseException:
            self.failed=True;raise
    def verify_controls(self,context):
        c.require(getattr(context,'_run_state',None) is self and self.base._recipe_pin==context._recipe_pin and self.base._parent_scope_pin==context._parent_scope_pin,'Material run context collision')
        rows=dict(a.plain(self.value)['currentHelpers']);rows[self.pin['path']]=self.pin['sha256']
        for key in ('target','adoptionProof','originalRecipe','representation','parentScope'):
            pin=self.value[key];rows[pin['path']]=pin['sha256']
        self.hash_rows(rows)
    def verify_receipt(self,context,row):
        name=row['receipt']['path'];graph=a.plain(context._graph);c.require(name in graph['values'],'Receipt outside material run graph')
        allowed=a.plain(self.value)['semanticInputs'];rows={name:row['receipt']['sha256']}
        def visit(v):
            if isinstance(v,dict):
                if set(v)=={'path','sha256'}:
                    if v['path'] in allowed:
                        c.require(allowed[v['path']]==v['sha256'],'Material run semantic pin collision');rows[v['path']]=v['sha256']
                else:
                    for key,x in v.items():
                        if key not in ('frozenInputs','sourceClosure','helperSnapshots','outputHashes'):visit(x)
            elif isinstance(v,list):
                for x in v:visit(x)
        visit(graph['values'][name]);self.hash_rows(rows)
    def verify_geometry(self,context,name):
        graph=a.plain(context._graph);c.require(name in graph['geometries'],'Geometry outside material run')
        row=graph['geometries'][name];value=graph['values'][name];scope=a.read_json(context._parent_scope_pin['path']);rp=scope['geometryRepresentations'][name]
        rows={name:row['receipt']['sha256'],row['candidate']['path']:row['candidate']['sha256'],rp['path']:rp['sha256']}
        if 'nativeCornerArchive' in value:
            pin=value['nativeCornerArchive'];rows[pin['path']]=pin['sha256']
        self.hash_rows(rows)


def begin(context,run_pin,*,proof_pin):
    from phenotype_material_execution_adoption import MaterialExecution
    c.require(type(context) is MaterialExecution and not hasattr(context,'_run_state'),'Typed unnested material context required')
    context.verify()  # Full boundary, including every historical physical closure.
    path,h=a.row(run_pin);c.require(c.sha(path)==h,'Material run descriptor changed')
    value=a.read_json(path);expected=descriptor(context,proof_pin)
    c.require(set(value)==FIELDS and type(value.get('schemaVersion')) is int and value['schemaVersion']==1 and value==expected,'Exact material run target/graph/inputs required')
    state=_Run(context,run_pin,value);state.hash_rows(value['fullInputs'])
    result=object.__new__(MaterialExecution)
    for key,val in context.__dict__.items():object.__setattr__(result,key,val)
    object.__setattr__(result,'_run_state',state);result.verify();return result


def finish(context):
    from phenotype_material_execution_adoption import MaterialExecution
    c.require(type(context) is MaterialExecution and isinstance(getattr(context,'_run_state',None),_Run),'Material run context required')
    state=context._run_state;state.verify_controls(context)
    try:
        state.base.verify()  # Full independent closing boundary, no cached authority.
        state.hash_rows(a.plain(state.value)['fullInputs'])
    except BaseException:
        state.failed=True;raise
    state.closed=True
    return {'kind':'completed-original-material-parent-guarded-run','run':dict(state.pin),'pass':True,'fullOpeningAndClosingVerification':True,'nestedContentHashCache':False,'nestedInputs':'exact-requested-semantic-receipt-and-geometry','hashCalls':state.calls,'hashedBytes':state.bytes,'hashSeconds':state.seconds,'elapsedSeconds':time.perf_counter()-state.started,'readCounts':dict(state.checked),'materialAcceptanceCreated':False}


def require_finished(context,receipt):
    state=getattr(context,'_run_state',None)
    c.require(isinstance(state,_Run) and state._seal is _SEAL and state.closed and not state.failed and receipt.get('pass') is True and receipt.get('run')==state.pin,'Unfinalized, failed, or foreign material run cannot pass')
