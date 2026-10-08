"""Typed, explicit adoption of one original skin-only calibration recipe.

This initial adapter supports working-space same-geometry skin parents only.
It never executes archived code, edits maps, or grants material acceptance.
"""
from dataclasses import dataclass
from pathlib import Path
import phenotype_infrastructure_adoption as a
import source_representation_contract as representation
import target_contract as c
import phenotype_material_run_scope as material_run_scope

_SEAL = object()
MODULE = 'replay_stage_skin_calibration.py'


@dataclass(frozen=True, init=False)
class MaterialExecution:
    _seal: object
    _verified: object
    _recipe: object
    _recipe_pin: object
    _representation: object
    _representation_pin: object
    _module: str
    _target: object

    def verify(self):
        c.require(getattr(self, '_seal', None) is _SEAL, 'Unverified material execution context')
        if hasattr(self,'_run_state'):
            self._run_state.verify_controls(self)
            return
        self._verified.verify()
        self._representation.verify()
        if hasattr(self,'_parent_scope_pin'):
            c.require(c.sha(self._parent_scope_pin['path'])==self._parent_scope_pin['sha256'], 'Material parent scope changed')
            for path,sha in self._graph['pins'].items():c.require(c.sha(path)==sha,'Scoped material data changed')
            for represented in self._representations.values(): represented.verify()
            for closure in self._scoped_closures.values():
                for path,sha in closure.items():c.require(c.sha(path)==sha,'Receipt-scoped material input changed')
        c.require(c.sha(self._recipe_pin['path']) == self._recipe_pin['sha256'],
                  'Original material recipe changed')

    def resolve(self, *, module_file, path, value, tp, target, part, space, consumer=None):
        self.verify()
        if hasattr(self,'_parent_scope_pin'):
            return scoped_resolution(self,module_file=module_file,path=path,value=value,tp=tp,target=target,part=part,space=space,consumer=consumer)
        c.require(consumer is None, 'Legacy material execution has no nested parent consumers')
        c.require(str(Path(module_file).resolve()) == self._module,
                  'Material execution belongs to another consumer module')
        c.require(space == 'working' and part == self._recipe['part']
                  and {'path':str(Path(tp).resolve()),'sha256':c.sha(tp)} == a.plain(self._target)
                  and target == c.load(tp), 'Material execution target/part/space differs')
        name = str(Path(path).resolve())
        if name == self._recipe_pin['path']:
            c.require(value == a.plain(self._recipe), 'Original recipe or controls changed')
        else:
            cfg = a.read_json(self._representation_pin['path'])
            c.require(name == cfg['geometryReceipt']['path']
                      and c.sha(name) == cfg['geometryReceipt']['sha256']
                      and value == a.read_json(name), 'Geometry outside exact material scope')
        key = (name, 'frozenInputs')
        c.require(key in self._verified.receiptClosures, 'Undeclared material closure')
        pins = a.plain(self._verified.receiptClosures[key])
        pins.update(a.plain(self._verified.inputs))
        pins.update(a.plain(self._representation.inputs))
        return pins, [{'kind':'typed-original-skin-calibration-adoption',
                       'recipe':a.plain(self._recipe_pin),
                       'representation':a.plain(self._representation_pin),
                       'originalClaimsUnchanged':True,'historicalCodeExecuted':False}]

    def geometry_proof(self, *, receipt_path=None, candidate=None, owner=None, space=None):
        self.verify()
        if hasattr(self,'_parent_scope_pin'):
            c.require(space=='working' and receipt_path is not None and candidate is not None and owner is not None, 'Exact scoped geometry proof lookup required')
            name=str(Path(receipt_path).resolve());row=a.plain(self._graph)['geometries'].get(name)
            c.require(row is not None and row['owner']==owner and row['candidate']=={'path':str(Path(candidate).resolve()),'sha256':c.sha(candidate)}, 'Geometry outside scoped material representation')
            if hasattr(self,'_run_state'):self._run_state.verify_geometry(self,name)
            return a.plain(self._representations[name].proof)
        return a.plain(self._representation.proof)

    def physical_closure(self, *, module_file, consumer, receipt_path, receipt, tp, target, owner, space):
        return scoped_resolution(self,module_file=module_file,path=receipt_path,value=receipt,tp=tp,target=target,part=owner,space=space,consumer=consumer)[0]


def prepare_material_execution(proof_pin, recipe_pin, representation_pin, *,
                               target_path, target, part, space):
    repo = Path(__file__).resolve().parents[2]
    verified = a.verify_proof(proof_pin, repo=repo)
    for path in (Path(__file__).resolve(), Path(__file__).with_name(MODULE).resolve()):
        c.require(verified.proof['currentHelpers'].get(str(path)) == c.sha(path),
                  'Current material consumer absent or stale in proof')
    rp, rh = a.row(recipe_pin)
    c.require(c.sha(rp) == rh, 'Original material recipe pin changed')
    recipe = a.read_json(rp)
    c.require(type(recipe.get('schemaVersion')) is int and recipe['schemaVersion'] == 1
              and recipe.get('kind') == 'target-compiler-skin-intensity-calibration'
              and recipe.get('diagnosticOnly') is True, 'Typed original calibration recipe required')
    c.verify_binding(recipe, target_path, target, space)
    c.require(space == 'working' and recipe['part'] == part
              and part not in c.fixed_garment_parts(target),
              'Initial material adoption supports working skin-only owners')
    c.require(recipe['parent'] == {'mode':'original-materialRoles-skin',
                                  'controls':{'materialRoles':{'0':'skin'}}},
              'Initial material adoption requires exact original skin parent')
    c.require(recipe['materialSource'] == {'candidate':recipe['candidate'],
                  'geometryReceipt':recipe['geometryReceipt'],'coordinateSpace':'working'},
              'Initial material adoption requires same exact geometry/material source')
    c.require(type(recipe['calibrationApplications']) is int
              and recipe['calibrationApplications'] == 1
              and recipe['parentAoStrength'] == 0, 'One untreated calibration required')
    c.require((str(rp), 'frozenInputs') in verified.receiptClosures,
              'Original recipe not declared in adoption proof')
    declaration = next((x for x in verified.proof['historicalReceipts']
                        if a.plain(x['receipt']) == dict(recipe_pin)), None)
    c.require(declaration is not None
              and declaration['kind'] == 'target-compiler-skin-intensity-calibration',
              'Typed original recipe declaration differs')
    represented = representation.verify_source_representation(
        representation_pin, target_path=target_path,target=target,part=part,space=space)
    cfg = a.read_json(representation_pin['path'])
    c.require(cfg['adoptionProof'] == proof_pin
              and cfg['candidate'] == recipe['candidate']
              and cfg['geometryReceipt'] == recipe['geometryReceipt'],
              'Material representation belongs to another source or proof')
    result = object.__new__(MaterialExecution)
    for key, value in dict(_seal=_SEAL,_verified=verified,_recipe=a.immutable(recipe),
            _recipe_pin=a.immutable(dict(recipe_pin)),_representation=represented,
            _representation_pin=a.immutable(dict(representation_pin)),
            _module=str(Path(__file__).with_name(MODULE).resolve()),
            _target=a.immutable({'path':str(Path(target_path).resolve()),
                                'sha256':c.sha(target_path)})).items():
        object.__setattr__(result,key,value)
    result.verify()
    return result


def resolve(context, **kwargs):
    c.require(type(context) is MaterialExecution, 'Typed material execution context required')
    return context.resolve(**kwargs)


_prepare_legacy_material_execution = prepare_material_execution


def scoped_resolution(context, *, module_file,path,value,tp,target,part,space,consumer=None):
    from phenotype_material_parent_scope import CONSUMERS
    c.require(type(context) is MaterialExecution and hasattr(context,'_parent_scope_pin'), 'Verified scoped material execution required')
    context.verify()
    c.require(space=='working' and {'path':str(Path(tp).resolve()),'sha256':c.sha(tp)}==a.plain(context._target) and target==c.load(tp), 'Scoped material consumer target/space differs')
    name=str(Path(path).resolve());expected=a.plain(context._graph)
    if consumer is None:
        c.require(str(Path(module_file).resolve())==context._module,'Material scope consumer module differs')
        consumer='calibration.root' if name==context._recipe_pin['path'] else 'calibration.geometry'
    c.require(consumer in CONSUMERS and str(Path(module_file).resolve())==str(Path(__file__).with_name(CONSUMERS[consumer][0]).resolve()), 'Unsupported scoped material consumer/module')
    rows=[r for r in expected['records'] if r['receipt']['path']==name]
    c.require(len(rows)==1,'Receipt outside consumed material parent scope');row=rows[0]
    c.require(consumer in row['consumers'] and row['owner']==part and row['coordinateSpace']==space and c.sha(name)==row['receipt']['sha256'] and value==expected['values'][name] and value.get('kind')==row['kind'],'Material scope owner/kind/original receipt differs')
    if hasattr(context,'_run_state'):context._run_state.verify_receipt(context,row)
    pins={name:row['receipt']['sha256']}
    if row['closure'] is not None:
        key=(name,row['closure']);c.require(key in context._verified.receiptClosures or key in context._scoped_closures,'Scoped historical closure absent from adoption proof')
        pins.update(a.plain(context._scoped_closures.get(key,context._verified.receiptClosures.get(key,{}))))
    for output,sha in value.get('outputHashes',{}).items():
        c.require(c.sha(output)==sha,'Original material output changed');pins[str(Path(output).resolve())]=sha
    if consumer in ('calibration.root','calibration.geometry'):
        pins.update(a.plain(context._verified.inputs));pins.update(a.plain(context._graph)['pins'])
        pins[context._parent_scope_pin['path']]=context._parent_scope_pin['sha256']
        for represented in context._representations.values():pins.update(a.plain(represented.inputs))
    return pins,[{'kind':'typed-original-material-parent-scope-adoption','scope':a.plain(context._parent_scope_pin),'receipt':row['receipt'],'consumer':consumer,'originalClaimsUnchanged':True,'historicalCodeExecuted':False}]


def prepare_material_execution(proof_pin,recipe_pin,representation_pin,*,target_path,target,part,space,parent_scope_pin=None):
    if parent_scope_pin is None:
        return _prepare_legacy_material_execution(proof_pin,recipe_pin,representation_pin,target_path=target_path,target=target,part=part,space=space)
    from phenotype_material_parent_scope import graph,validate_scope,pinned
    repo=Path(__file__).resolve().parents[2];verified=a.verify_proof(proof_pin,repo=repo)
    rp=pinned(recipe_pin);recipe=a.read_json(rp)
    c.require(type(recipe.get('schemaVersion')) is int and recipe['schemaVersion']==1 and recipe.get('kind')=='target-compiler-skin-intensity-calibration' and recipe.get('diagnosticOnly') is True,'Typed original calibration recipe required')
    c.verify_binding(recipe,target_path,target,space)
    c.require(space=='working' and recipe['part']==part and type(recipe['calibrationApplications']) is int and recipe['calibrationApplications']==1 and recipe['parentAoStrength']==0,'One original working untreated calibration required')
    c.require(c.rig_mode(target)=='stock-exact' and target['rig']['runtimeScale']==1 and target['identity']['gender']=='female' and target['identity']['prefix']=='pfh0','Original female stock-exact material scope required')
    expected=graph(recipe_pin,recipe,part);sp=pinned(parent_scope_pin);scope=a.read_json(sp);tp={'path':str(Path(target_path).resolve()),'sha256':c.sha(target_path)}
    validate_scope(scope,proof_pin=proof_pin,recipe_pin=recipe_pin,recipe=recipe,target_pin=tp,part=part,expected=expected,bank=Path(__file__).parent)
    c.require(all(verified.proof['currentHelpers'].get(p)==h for p,h in scope['currentConsumers'].items()),'Current scoped material consumer absent or stale in proof')
    scoped_closures={}
    receipt_scopes=scope.get('receiptScopes',{})
    for name,pin in receipt_scopes.items():
        receipts,scopes,physical,inputs,evidence=representation.ancestor_contract(pin,bank_pin=proof_pin,verified=verified,target_path=Path(target_path).resolve(),target=target)
        c.require(set(receipts)=={name} and {'path':name,'sha256':c.sha(name)}==expected['geometries'][name]['receipt'],'Receipt scope cannot import another owner or closure')
        scoped_closures[name,'frozenInputs']={v['path']:v['sha256'] for v in physical.values()}
        scoped_closures[name,'frozenInputs'].update(inputs)
    for row in expected['records']:
        value=expected['values'][row['receipt']['path']]
        if 'targetId' in value:c.verify_binding(value,target_path,target,'working')
        if row['closure'] is not None:
            key=(row['receipt']['path'],row['closure']);c.require(key in verified.receiptClosures or key in scoped_closures,'Consumed material parent closure not declared')
            declaration=next((x for x in verified.proof['historicalReceipts'] if a.plain(x['receipt'])==row['receipt']),None)
            c.require(key in scoped_closures or (declaration is not None and declaration['kind']==row['kind'] and row['closure'] in declaration['closures']),'Consumed material receipt declaration differs')
    for claim in expected['historicalHelperClaims']:
        key=(claim['receipt']['path'],'frozenInputs');physical=a.plain(scoped_closures.get(key,verified.receiptClosures.get(key,{})))
        c.require(claim['original']['sha256'] in physical.values(),'Receipt-specific historical helper metadata absent from verified closure')
    represented={}
    for name,row in expected['geometries'].items():
        pin=scope['geometryRepresentations'][name];cfg=a.read_json(pin['path'])
        c.require(cfg['adoptionProof']==proof_pin and cfg['geometryReceipt']==row['receipt'] and cfg['candidate']==row['candidate'],'Scoped geometry representation source/proof differs')
        if cfg.get('kind')=='target-original-material-parent-direct-representation':
            from material_parent_representation import verify
            closure=scoped_closures.get((name,'frozenInputs'),a.plain(verified.receiptClosures.get((name,'frozenInputs'),{})))
            represented[name]=verify(pin,verified=verified,target_path=target_path,target=target,part=row['owner'],closure=closure,receipt_scope=receipt_scopes.get(name))
        else:represented[name]=representation.verify_source_representation(pin,target_path=target_path,target=target,part=row['owner'],space='working')
    current=recipe['geometryReceipt']['path'];c.require(scope['geometryRepresentations'][current]==representation_pin,'Root material representation differs from parent scope')
    result=object.__new__(MaterialExecution)
    fields=dict(_seal=_SEAL,_verified=verified,_recipe=a.immutable(recipe),_recipe_pin=a.immutable(dict(recipe_pin)),_representation=represented[current],_representation_pin=a.immutable(dict(representation_pin)),_module=str(Path(__file__).with_name(MODULE).resolve()),_target=a.immutable(tp),_parent_scope_pin=a.immutable(dict(parent_scope_pin)),_scoped_closures=a.immutable(scoped_closures),_graph=a.immutable(expected),_representations=a.immutable(represented))
    # Verified representation objects are already sealed/frozen; keep objects intact.
    fields['_representations']=__import__('types').MappingProxyType(represented)
    for key,value in fields.items():object.__setattr__(result,key,value)
    result.verify();return result
