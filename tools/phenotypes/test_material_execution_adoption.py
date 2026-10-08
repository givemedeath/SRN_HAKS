"""Material adoption keeps historical closures exact and consumer scope narrow."""
import copy
from dataclasses import FrozenInstanceError
import json
from pathlib import Path
import unittest
import phenotype_material_execution_adoption as material
import replay_stage_skin_calibration as cal
import target_contract as c
from test_source_representation_contract import RepresentationFixture


class MaterialExecutionTests(unittest.TestCase):
    def fixture(self):
        rf=RepresentationFixture(self);f=rf.f;part=rf.part
        rp=f.part_paths[part];source=f.candidates[part]
        recipe={'schemaVersion':1,'kind':'target-compiler-skin-intensity-calibration',
                'diagnosticOnly':True,**c.binding(f.target_path,f.target,'working'),'part':part,
                'candidate':f.pin(source),'geometryReceipt':f.pin(rp),
                'materialSource':{'candidate':f.pin(source),'geometryReceipt':f.pin(rp),
                                  'coordinateSpace':'working'},
                'parent':{'mode':'original-materialRoles-skin','controls':{'materialRoles':{'0':'skin'}}},
                'calibrationApplications':1,'parentAoStrength':0,
                'frozenInputs':dict(f.documents[part]['frozenInputs'])}
        recipe_path=f.write(f.out/'recipe.json',recipe)
        f.proof['historicalReceipts'].append({'receipt':f.pin(recipe_path),
                     'kind':recipe['kind'],'closures':['frozenInputs']})
        for p in (Path(material.__file__).resolve(),Path(cal.__file__).resolve()):
            f.proof['currentHelpers'][str(p)]=c.sha(p)
        reconciliation=Path(f.proof['reconciliation']['path'])
        value=json.loads(reconciliation.read_text())
        value['helpers']={p:{'sha256':h,'features':['Typed calibration consumer test']}
                          for p,h in f.proof['currentHelpers'].items()}
        f.write(reconciliation,value);f.proof['reconciliation']=f.pin(reconciliation);f.save()
        cfg=copy.deepcopy(rf.document);cfg['adoptionProof']=f.pin(f.proof_path)
        representation_path=f.write(f.out/'material-representation.json',cfg)
        args=(f.pin(f.proof_path),f.pin(recipe_path),f.pin(representation_path))
        kwargs=dict(target_path=f.target_path,target=f.target,part=part,space='working')
        return rf,recipe_path,recipe,args,kwargs

    def test_exact_physical_closure_and_default_legacy_rejection(self):
        rf,rp,recipe,args,kwargs=self.fixture();f=rf.f
        before=rp.read_bytes();context=material.prepare_material_execution(*args,**kwargs)
        pins,rows=material.resolve(context,module_file=cal.__file__,path=rp,value=recipe,
                                  tp=f.target_path,target=f.target,part=rf.part,space='working')
        self.assertIn(str(f.saved_helper),pins)
        self.assertNotEqual(pins.get(str(f.old_helper)),f.old_digest)
        self.assertEqual(rp.read_bytes(),before);self.assertFalse(f.sentinel.exists())
        with self.assertRaises(ValueError):cal.frozen_inputs(recipe,rp)
        self.assertTrue(rows[0]['originalClaimsUnchanged'])
        got=cal.geometry_input(recipe['candidate'],recipe['geometryReceipt'],f.target_path,
                               f.target,rf.part,'working',material_execution=context)
        self.assertIsNotNone(got['serializationProof'])
        self.assertEqual(got['source'],f.candidates[rf.part])

    def test_cross_module_part_space_and_recipe_controls_rejected(self):
        rf,rp,recipe,args,kwargs=self.fixture();f=rf.f
        context=material.prepare_material_execution(*args,**kwargs)
        base=dict(module_file=cal.__file__,path=rp,value=recipe,tp=f.target_path,
                  target=f.target,part=rf.part,space='working')
        for change in ({'module_file':__file__},{'part':'bicepr'},{'space':'runtime'},
                       {'value':{**recipe,'parentAoStrength':.15}}):
            with self.subTest(change=change),self.assertRaises(ValueError):
                material.resolve(context,**{**base,**change})

    def test_changed_original_recipe_and_physical_archive_rejected(self):
        for which in ('recipe','archive'):
            rf,rp,recipe,args,kwargs=self.fixture();context=material.prepare_material_execution(*args,**kwargs)
            p=rp if which=='recipe' else rf.f.saved_helper
            p.write_bytes(p.read_bytes()+b' ')
            with self.subTest(which=which),self.assertRaises(ValueError):context.verify()
            self.assertFalse(rf.f.sentinel.exists())

    def test_forged_or_mutable_context_rejected(self):
        rf,rp,recipe,args,kwargs=self.fixture()
        context=material.prepare_material_execution(*args,**kwargs)
        with self.assertRaises(FrozenInstanceError):context._module='bad'
        forged=object.__new__(material.MaterialExecution)
        with self.assertRaises(ValueError):forged.verify()
        with self.assertRaises(ValueError):
            material.resolve(object(),module_file=cal.__file__,path=rp,value=recipe,
                tp=rf.f.target_path,target=rf.f.target,part=rf.part,space='working')

    def test_foreign_geometry_and_runtime_factory_rejected(self):
        rf,rp,recipe,args,kwargs=self.fixture();f=rf.f
        context=material.prepare_material_execution(*args,**kwargs)
        foreign=f.part_paths['bicepr']
        with self.assertRaises(ValueError):
            material.resolve(context,module_file=cal.__file__,path=foreign,
                value=json.loads(foreign.read_text()),tp=f.target_path,target=f.target,
                part=rf.part,space='working')
        with self.assertRaises(ValueError):
            material.prepare_material_execution(*args,**{**kwargs,'space':'runtime'})


if __name__=='__main__':unittest.main()
