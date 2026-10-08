"""Client package guards: identity/tables, shared ownership and userdir isolation."""
import hashlib
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import target_contract as contract
from preflight_target_body_client import audit_tables, aliases, native_group, validate_payload, validate_actors, module_binding, stock_dependencies, stock_equipment
from test_target_part_pipeline import target_fixture


class TargetPreflightTests(unittest.TestCase):
    def baselines(self, root):
        payload = {'appearance.2da':b'2DA V2.0\n\nLABEL MODELTYPE RACE SIZECATEGORY HELMET_SCALE_F\n2 Gnome P G 2 .82\n6 Human P H 3 .85\n',
                   'racialtypes.2da':b'2DA V2.0\n\nLabel Name Appearance StrAdjust FeatsTable\n2 Gnome 26 2 -2 RACE_FEAT_GNOME\n6 Human 34 6 0 RACE_FEAT_HUMAN\n',
                   'phenotype.2da':b'2DA V2.0\n\nLabel Default\n0 Normal 0\n2 Large 0\n'}
        pins = {}
        for name,data in payload.items():
            path = root/name; path.write_bytes(data); pins[name] = {'path':str(path),'sha256':contract.sha(path)}
        payload['appearance.2da'] = payload['appearance.2da'].replace(b'Gnome P G 2',b'Troll P G 4')
        payload['racialtypes.2da'] = payload['racialtypes.2da'].replace(b'Gnome 26',b'Troll 16777217')
        return payload,pins

    def test_target_mapping_and_large_size_preserve_gameplay_and_human(self):
        with tempfile.TemporaryDirectory() as temporary:
            payload,pins = self.baselines(Path(temporary)); report = audit_tables(payload,target_fixture(),pins)
            self.assertTrue(report['phenotype.2da']['unchanged'])
            self.assertTrue(report['appearance.2da']['otherInstalledRowsExact'])
            mutations = [('appearance.2da',b'Human P H 3',b'Human P H 4'),
                         ('appearance.2da',b'Troll P G 4',b'Troll P H 4'),
                         ('appearance.2da',b'Troll P G 4 .82',b'Troll P G 4 1.2'),
                         ('racialtypes.2da',b'2 -2 RACE_FEAT_GNOME',b'2 4 RACE_FEAT_TROLL'),
                         ('phenotype.2da',b'Normal 0',b'Normal 2')]
            for name,before,after in mutations:
                bad = dict(payload); bad[name] = bad[name].replace(before,after)
                with self.subTest(table=name,change=after),self.assertRaises(ValueError): audit_tables(bad,target_fixture(),pins)

    def test_declared_comparison_rows_and_missing_tables(self):
        with tempfile.TemporaryDirectory() as temporary:
            payload,pins = self.baselines(Path(temporary))
            payload['appearance.2da'] += b'15100 StockHuman P X 3 .85\n'
            with self.assertRaisesRegex(ValueError,'Undeclared fixture'):
                audit_tables(payload,target_fixture(),pins)
            audit_tables(payload,target_fixture(),pins,[15100])
            del payload['phenotype.2da']
            with self.assertRaisesRegex(ValueError,'Required target table missing'):
                audit_tables(payload,target_fixture(),pins,[15100])

    def test_exact_packed_ownership_rejects_human_female_and_shared_overrides(self):
        data = b'actual-payload'; digest = hashlib.sha256(data).hexdigest()
        rows = [('pmg0_chest001',2002,data)]
        self.assertEqual(validate_payload(rows,{'body':{'pmg0_chest001.mdl':digest}}),{'pmg0_chest001.mdl'})
        for name in ['pmh0_chest001','pfg0','a_ba']:
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,'override packed'):
                validate_payload([(name,2002,data)],{'body':{name+'.mdl':digest}})
        with self.assertRaisesRegex(ValueError,'exact declared'):
            validate_payload(rows+[('unknown',2002,data)],{'body':{'pmg0_chest001.mdl':digest}})
        with self.assertRaisesRegex(ValueError,'Overlapping'):
            validate_payload(rows,{'body':{'pmg0_chest001.mdl':digest},'equipment':{'pmg0_chest001.mdl':digest}})

    def test_native_group_source_dependencies_and_client_are_exact(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary); (folder/'ascii').mkdir(); (folder/'resources').mkdir()
            source = folder/'ascii/pmg0.mdl'; source.write_bytes(b'ASCII-source')
            model = folder/'resources/pmg0.mdl'; model.write_bytes(b'\0\0\0\0native-data')
            receipt = folder/'native-compile.json'
            record = {'complete':True,'clientSha256':'pinned-client','materialResourceHashes':{},
                      'models':[{'name':'pmg0.mdl','sourceSha256':contract.sha(source),
                                 'binarySha256':contract.sha(model),'bytes':model.stat().st_size}]}
            receipt.write_text(json.dumps(record)); pin = contract.sha(receipt)
            self.assertEqual(native_group(folder,pin,'pinned-client',{'pmg0.mdl'}),{'pmg0.mdl':contract.sha(model)})
            with self.assertRaisesRegex(ValueError,'compiler differs'):
                native_group(folder,pin,'wrong-client',{'pmg0.mdl'})
            source.write_bytes(b'changed-source')
            with self.assertRaisesRegex(ValueError,'Stale native'):
                native_group(folder,pin,'pinned-client',{'pmg0.mdl'})

    def test_isolated_aliases_and_empty_override(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve(); (root/'override').mkdir()
            values = {'HD0':'','HAK':'hak','MODULES':'modules','OVERRIDE':'override','LOGS':'logs',
                      'CURRENTGAME':'currentgame','MODELCOMPILER':'modelcompiler'}
            (root/'nwn.ini').write_text('[Alias]\n'+'\n'.join(name+'='+str(root/path) for name,path in values.items()))
            aliases(root)
            (root/'override/stale.mdl').write_bytes(b'stale')
            with self.assertRaisesRegex(ValueError,'override must be empty'): aliases(root)


class StockExactPreflightTests(unittest.TestCase):
    def target(self):
        target = target_fixture(); target['rig']['mode'] = 'stock-exact'
        target['identity'].update(gender='female',prefix='pfh0',raceId=6,appearanceRow=6)
        target['models'] = {part:'pfh0_'+part+'001' for part in contract.PART_JOINTS}
        target['material'] = {'fixedGarmentParts':['chest','pelvis']}
        return target

    def test_stock_tables_are_installed_and_never_overridden_or_expanded(self):
        with tempfile.TemporaryDirectory() as temporary:
            payload,pins = TargetPreflightTests().baselines(Path(temporary)); target = self.target()
            proof = audit_tables({},target,pins)
            self.assertTrue(all(row['unchanged'] and not row['packed'] for row in proof.values()))
            for name in payload:
                with self.subTest(name=name),self.assertRaisesRegex(ValueError,'cannot override'):
                    audit_tables({name:Path(pins[name]['path']).read_bytes()},target,pins)
            with self.assertRaisesRegex(ValueError,'cannot add'): audit_tables({},target,pins,[15100])
            Path(pins['appearance.2da']['path']).write_bytes(b'stale extraction')
            with self.assertRaisesRegex(ValueError,'changed'): audit_tables({},target,pins)

    def test_female_body_namespace_does_not_authorize_rig_neck_head_or_other_targets(self):
        data = b'native'; digest = hashlib.sha256(data).hexdigest(); target = self.target()
        body = {'pfh0_chest001.mdl':digest,'pfh0_chest001.mtr':digest,'pfh0_pelvis001r.tga':digest}
        rows = [('pfh0_chest001',2002,data),('pfh0_chest001',2072,data),('pfh0_pelvis001r',3,data)]
        self.assertEqual(validate_payload(rows,{'body':body},target),set(body))
        # Single-PLT-per-part: per-node garment/overlay resources are no longer body resources.
        for name in ('pfh0.mdl','pfh0_head001.mdl','pfh0_neck001.plt','a_fa.mdl','pmh0_chest001.mdl','pfh0_chest020.mdl','appearance.2da',
                     'pfh0_chest001f.mtr','pfh0_pelvis001fr.tga','pfh0_pelviss1.plt'):
            kind = {'.mdl':2002,'.plt':6,'.2da':2017,'.mtr':2072,'.tga':3}[Path(name).suffix]
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,'overrides installed'):
                validate_payload([(Path(name).stem,kind,data)],{'body':{name:digest}},target)
        with self.assertRaisesRegex(ValueError,'overrides installed'):
            validate_payload(rows,{'equipment':body},target)
        with self.assertRaisesRegex(ValueError,'exact declared'):
            validate_payload(rows+[('pfh0_footl001',2002,data)],{'body':body},target)
        with self.assertRaisesRegex(ValueError,'exact declared'):
            validate_payload(rows+[rows[0]],{'body':body},target)

    def test_native_actor_identity_rejects_male_and_cross_race_and_phenotype(self):
        actor = {key:{'value':value} for key,value in {'Appearance_Type':6,'Race':6,'Gender':1,'Phenotype':0}.items()}
        self.assertEqual(validate_actors([actor]*8,self.target()),8)
        for key,value in [('Gender',0),('Race',2),('Appearance_Type',2),('Phenotype',2)]:
            bad = copy.deepcopy(actor); bad[key]['value'] = value
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'race/appearance/gender/phenotype'):
                validate_actors([actor,bad],self.target())
        with self.assertRaises(ValueError): validate_actors([],self.target())

    def test_actual_ifo_binds_safe_module_name_to_exact_hak_and_entry_area(self):
        build = {'moduleName':'srn_female_test','module':'srn_female_test.mod','hak':'srn_female_test.hak','actorAreaResref':'sr_tm_floor'}
        ifo = {'Mod_HakList':{'value':[{'Mod_Hak':{'value':'srn_female_test'}}]},'Mod_Entry_Area':{'value':'sr_tm_floor'}}
        with patch('preflight_target_body_client.decode_gff',return_value=ifo):
            self.assertEqual(module_binding([],build,'unused'),'srn_female_test')
            for key,value in [('moduleName','../other'),('module','other.mod'),('hak','other.hak')]:
                with self.subTest(key=key),self.assertRaises(ValueError): module_binding([],{**build,key:value},'unused')
        bad = copy.deepcopy(ifo); bad['Mod_HakList']['value'][0]['Mod_Hak']['value'] = 'other'
        with patch('preflight_target_body_client.decode_gff',return_value=bad),self.assertRaisesRegex(ValueError,'HAK/entry'):
            module_binding([],build,'unused')

    def test_stock_dependency_closure_requires_installed_head_neck_palettes_and_live_hashes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); (root/'raw').mkdir(); (root/'ascii').mkdir(); target = self.target()
            target['rig']['stockReferenceReceipt'] = {'path':'pinned-proof','sha256':'a'*64}
            for name in ('pfh0.mdl','a_fa.mdl','pfh0_head001.mdl','pfh0_neck001.mdl','pfh0_head001.plt','pfh0_neck001.plt',
                         'appearance.2da','racialtypes.2da','phenotype.2da','pal_skin01.tga','pal_hair01.tga','pal_cloth01.tga',
                         'pal_armor01.tga','pal_armor02.tga','pal_leath01.tga','pal_tattoo01.tga'):
                (root/'raw'/name).write_bytes(name.encode())
            for part in ('head','neck'):
                (root/'ascii'/('pfh0_'+part+'001.mdl')).write_text(' bitmap pfh0_'+part+'001\n')
            proof = {'rootAscii':{'path':str(root/'ascii/pfh0.mdl')},'chain':['pfh0','a_fa'],
                     'frozenInputs':{str(path.resolve()):contract.sha(path) for path in root.rglob('*') if path.is_file()}}
            tables = {name:{'path':str(root/'raw'/name),'sha256':contract.sha(root/'raw'/name)} for name in ('appearance.2da','racialtypes.2da','phenotype.2da')}
            with patch('preflight_target_body_client.contract.verify_stock_reference',return_value=proof):
                self.assertTrue(stock_dependencies(target,tables)['stockFramesExact'])
            missing = dict(proof); missing['frozenInputs'] = {key:value for key,value in proof['frozenInputs'].items() if not key.endswith('pfh0_neck001.plt')}
            with patch('preflight_target_body_client.contract.verify_stock_reference',return_value=missing),self.assertRaisesRegex(ValueError,'dependency pins missing'):
                stock_dependencies(target,tables)
            tool = root/'resman.exe'; tool.write_bytes(b'tool')
            build = {'resmanTool':str(tool),'resmanToolSha256':contract.sha(tool),'gameRoot':str(root),'userDirectory':str(root)}
            from types import SimpleNamespace
            def installed(command,**kwargs): return SimpleNamespace(stdout=(root/'raw'/command[-1]).read_bytes())
            with patch('preflight_target_body_client.contract.verify_stock_reference',return_value=proof),patch('preflight_target_body_client.subprocess.run',side_effect=installed):
                stock_dependencies(target,tables,build)
            with patch('preflight_target_body_client.contract.verify_stock_reference',return_value=proof),patch('preflight_target_body_client.subprocess.run',return_value=SimpleNamespace(stdout=b'new-installed-bits')):
                with self.assertRaisesRegex(ValueError,'changed since extraction'): stock_dependencies(target,tables,build)

    def test_equipment_identity_rejects_scale_overrides_cross_target_and_stale_receipts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); target = self.target(); target_path = root/'target.json'; target_path.write_text('{}')
            receipt = root/'equipment.json'
            data = {'schemaVersion':2,'kind':'target-equipment-selection',**contract.binding(target_path,target,'runtime'),
                    'mode':'stock-identity','sourcePrefix':'pfh0','runtimeScale':1,'resourceHashes':{},'productionTablesChanged':False}
            def call(value):
                receipt.write_text(json.dumps(value)); return stock_equipment({'equipmentSelection':{'path':str(receipt),'sha256':contract.sha(receipt)}},target,target_path)
            self.assertEqual(call(data)['resourceHashes'],{})
            for key,value in [('runtimeScale',1.1),('sourcePrefix','pmh0'),('resourceHashes',{'pfh0_chest020.mdl':'bad'}),('productionTablesChanged',True),('targetId','other-target')]:
                with self.subTest(key=key),self.assertRaises(ValueError): call({**data,key:value})
            call(data); expected = contract.sha(receipt); receipt.write_text('changed')
            with self.assertRaisesRegex(ValueError,'changed'): stock_equipment({'equipmentSelection':{'path':str(receipt),'sha256':expected}},target,target_path)


class AnimationOverlayPreflightTests(unittest.TestCase):
    def overlay(self, root):
        paths={}; hashes={}
        for name in ('pfh0.mdl','srn_fa_h0.mdl'):
            path=root/name; path.write_bytes(b'\0\0\0\0overlay-'+name.encode()); paths[name]=str(path); hashes[name]=contract.sha(path)
        receipt=root/'animation.json'; receipt.write_text('{"test":true}')
        entry={'path':str(receipt),'sha256':contract.sha(receipt)}
        return entry,{'resourceHashes':hashes,'resourcePaths':paths,'frozenInputs':{str(receipt):entry['sha256']}}

    def test_animation_group_requires_verifier_exact_inventory_and_target_not_boolean(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary); target=StockExactPreflightTests().target(); target_path=root/'target.json'; target_path.write_text('{}'); entry,report=self.overlay(root)
            rows=[(Path(name).stem,2002,Path(report['resourcePaths'][name]).read_bytes()) for name in report['resourceHashes']]
            groups={'animation':report['resourceHashes']}
            verify=Mock(return_value=report)
            with patch.dict('sys.modules',{'target_animation_overlay':SimpleNamespace(verify_animation_overlay=verify)}):
                self.assertEqual(validate_payload(rows,groups,target,entry,target_path),set(report['resourceHashes']))
                verify.assert_called_once_with(entry,target_path)
                for badpin in (None,True,{'path':entry['path'],'sha256':entry['sha256'],'approved':True}):
                    with self.subTest(pin=badpin),self.assertRaisesRegex(ValueError,'exact receipt'): validate_payload(rows,groups,target,badpin,target_path)
                with self.assertRaisesRegex(ValueError,'target contract'): validate_payload(rows,groups,target,entry)
                with self.assertRaisesRegex(ValueError,'restricted'): validate_payload(rows,groups,target_fixture(),entry,target_path)
                with self.assertRaisesRegex(ValueError,'differs from verified'): validate_payload(rows,{'animation':{'pfh0.mdl':report['resourceHashes']['pfh0.mdl']}},target,entry,target_path)
                extra={**report['resourceHashes'],'a_fa.mdl':'0'*64}
                with self.assertRaisesRegex(ValueError,'differs from verified'): validate_payload(rows,{'animation':extra},target,entry,target_path)
                with self.assertRaisesRegex(ValueError,'Overlapping'): validate_payload(rows,{'animation':report['resourceHashes'],'body':{'pfh0.mdl':report['resourceHashes']['pfh0.mdl']}},target,entry,target_path)
                with self.assertRaisesRegex(ValueError,'exact declared'): validate_payload(rows[:-1],groups,target,entry,target_path)
                badrows=[(rows[0][0],2002,b'changed packed root'),rows[1]]
                with self.assertRaisesRegex(ValueError,'exact declared'): validate_payload(badrows,groups,target,entry,target_path)

    def test_preflight_rejects_a_client_other_than_the_overlay_compiler_before_installed_reads(self):
        from preflight_target_body_client import preflight
        from types import SimpleNamespace
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary); target=StockExactPreflightTests().target(); target_path=root/'target.json'; target_path.write_text('{}')
            entry,report=self.overlay(root); report['compilerClientSha256']='f'*64
            stage=root/'output/phenotypes'/target['id']/'fixture'; (stage/'test-module').mkdir(parents=True)
            helper=root/'tools/phenotypes/preflight_target_body_client.py'; helper.parent.mkdir(parents=True)
            receipt=stage/'test-module/receipt.json'; receipt.write_text(json.dumps({'schemaVersion':2,'kind':'target-body-fixture',
                **contract.binding(target_path,target,'runtime'),'validationScope':'full','animationOverlay':entry,'animationResourceHashes':report['resourceHashes']}))
            client=root/'client.exe'; client.write_bytes(b'other installed client')
            with patch.dict('sys.modules',{'target_animation_overlay':SimpleNamespace(verify_animation_overlay=Mock(return_value=report))}), \
                 patch('preflight_target_body_client.__file__',str(helper)),patch('preflight_target_body_client.contract.load',return_value=target), \
                 patch('preflight_target_body_client.contract.rig_ready',return_value=True),patch('preflight_target_body_client.stock_dependencies') as dependencies, \
                 self.assertRaisesRegex(ValueError,'animation carrier compiler'):
                preflight(stage,contract.sha(receipt),client,target_path)
            dependencies.assert_not_called()

    def test_unexecuted_or_cross_target_overlay_cannot_authorize_payload(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary); entry,report=self.overlay(root)
            with patch.dict('sys.modules',{'target_animation_overlay':SimpleNamespace(verify_animation_overlay=Mock(side_effect=ValueError('unexecuted or cross-target overlay')))}),self.assertRaisesRegex(ValueError,'unexecuted'):
                validate_payload([],{'animation':report['resourceHashes']},StockExactPreflightTests().target(),entry,root/'target.json')

    def test_overlay_does_not_skip_original_installed_root_or_inherited_dependencies(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary); stock=root/'stock'; (stock/'raw').mkdir(parents=True); (stock/'ascii').mkdir()
            target=StockExactPreflightTests().target(); target['rig']['stockReferenceReceipt']={'path':'pinned-stock','sha256':'a'*64}
            names=('pfh0.mdl','a_fa.mdl','pfh0_head001.mdl','pfh0_neck001.mdl','pfh0_head001.plt','pfh0_neck001.plt',
                   'appearance.2da','racialtypes.2da','phenotype.2da','pal_skin01.tga','pal_hair01.tga','pal_cloth01.tga',
                   'pal_armor01.tga','pal_armor02.tga','pal_leath01.tga','pal_tattoo01.tga')
            for name in names: (stock/'raw'/name).write_bytes(('installed-'+name).encode())
            for part in ('head','neck'): (stock/'ascii'/('pfh0_'+part+'001.mdl')).write_text(' bitmap pfh0_'+part+'001\n')
            proof={'rootAscii':{'path':str(stock/'ascii/pfh0.mdl')},'chain':['pfh0','a_fa'],
                   'frozenInputs':{str(path.resolve()):contract.sha(path) for path in stock.rglob('*') if path.is_file()}}
            tables={name:{'path':str(stock/'raw'/name),'sha256':contract.sha(stock/'raw'/name)} for name in ('appearance.2da','racialtypes.2da','phenotype.2da')}
            tool=root/'resman.exe'; tool.write_bytes(b'utility'); target_path=root/'target.json'; target_path.write_text('{}'); entry,report=self.overlay(root)
            build={'resmanTool':str(tool),'resmanToolSha256':contract.sha(tool),'gameRoot':str(root),'userDirectory':str(root),'animationResourceHashes':report['resourceHashes']}
            def installed(command,**kwargs):
                self.assertIn('--no-ovr',command); return SimpleNamespace(stdout=(stock/'raw'/command[-1]).read_bytes())
            with patch.dict('sys.modules',{'target_animation_overlay':SimpleNamespace(verify_animation_overlay=Mock(return_value=report))}), \
                 patch('preflight_target_body_client.contract.verify_stock_reference',return_value=proof), \
                 patch('preflight_target_body_client.subprocess.run',side_effect=installed) as reads:
                result=stock_dependencies(target,tables,build,entry,target_path)
                self.assertEqual({call.args[0][-1] for call in reads.call_args_list},set(names))
                self.assertEqual(result['installedRootBaselineSha256'],contract.sha(stock/'raw/pfh0.mdl'))
                self.assertTrue(result['animationParentRootOverridden']); self.assertTrue(result['stockFramesExact']); self.assertFalse(result['rigHeadNeckOverridden'])
                def changed(command,**kwargs): return SimpleNamespace(stdout=b'candidate-root' if command[-1]=='pfh0.mdl' else (stock/'raw'/command[-1]).read_bytes())
                reads.side_effect=changed
                with self.assertRaisesRegex(ValueError,'changed since extraction: pfh0.mdl'): stock_dependencies(target,tables,build,entry,target_path)


class SharedFemalePosturePreflightTests(unittest.TestCase):
    def fixture(self, root):
        target = StockExactPreflightTests().target()
        target_path = root/'target.json'; target_path.write_text('{}')
        receipt = root/'shared.json'
        receipt.write_text(json.dumps({'kind':'executed-shared-female-source-native-idle-overlay'}))
        roots = ('pfa0','pfa2','pfd0','pfd2','pfe0','pfe2','pfg0','pfg2','pfh0','pfh2','pfo0','pfo2')
        paths, hashes = {}, {}
        for family in roots:
            for name in (family+'.mdl','srn_fa_'+family[2:]+'.mdl'):
                path = root/name; path.write_bytes(b'synthetic-'+name.encode())
                paths[name], hashes[name] = str(path), contract.sha(path)
        entry = {'path':str(receipt),'sha256':contract.sha(receipt)}
        report = {'kind':'verified-shared-female-source-native-animation-overlay',
            'resourceHashes':hashes,'resourcePaths':paths,
            'frozenInputs':{str(receipt):entry['sha256']}}
        return target, target_path, entry, report

    def test_shared24_payload_has_explicit_dispatch_and_exact_namespace(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary); target,target_path,entry,report=self.fixture(root)
            shared=Mock(return_value=report); human=Mock(side_effect=AssertionError('Human branch must stay separate'))
            rows=[(Path(name).stem,2002,Path(report['resourcePaths'][name]).read_bytes()) for name in report['resourceHashes']]
            with patch.dict('sys.modules',{'shared_female_animation_overlay':SimpleNamespace(verify_shared_female_animation_overlay=shared),
                'target_animation_overlay':SimpleNamespace(verify_animation_overlay=human)}):
                self.assertEqual(validate_payload(rows,{'animation':report['resourceHashes']},target,entry,target_path),set(report['resourceHashes']))
                shared.assert_called_once_with(entry,target_path); human.assert_not_called()
                for bad in (rows[:-1],rows+[('a_fa',2002,b'unowned')],rows+[rows[0]]):
                    with self.subTest(rows=len(bad)),self.assertRaisesRegex(ValueError,'exact declared'):
                        validate_payload(bad,{'animation':report['resourceHashes']},target,entry,target_path)
                with self.assertRaisesRegex(ValueError,'overrides installed'):
                    validate_payload([('pfh0_head001',2002,b'head')],{'equipment':{'pfh0_head001.mdl':contract.sha(root/'pfh0.mdl')}},target)

    def test_shared_guard_failure_and_resource_drift_cannot_authorize_payload(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from preflight_target_body_client import verified_animation_overlay
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary); _,target_path,entry,report=self.fixture(root)
            guard=Mock(side_effect=ValueError('actual native mismatch'))
            with patch.dict('sys.modules',{'shared_female_animation_overlay':SimpleNamespace(verify_shared_female_animation_overlay=guard)}):
                with self.assertRaisesRegex(ValueError,'actual native'): verified_animation_overlay(entry,target_path)
                guard.side_effect=None; guard.return_value={**report,'resourceHashes':dict(list(report['resourceHashes'].items())[:-1])}
                with self.assertRaisesRegex(ValueError,'twelve roots'): verified_animation_overlay(entry,target_path)
                guard.return_value=report; Path(report['resourcePaths']['pfd2.mdl']).write_bytes(b'drift')
                with self.assertRaisesRegex(ValueError,'changed'): verified_animation_overlay(entry,target_path)

    def test_shared_overlay_requires_typed_roster_and_installed_body(self):
        from preflight_target_body_client import verified_posture_roster
        target=StockExactPreflightTests().target()
        animation={'kind':'verified-shared-female-source-native-animation-overlay'}
        build={'runtimeBodySource':'stock-human-female','bodyConverted':None,'bodyNativeReceiptSha256':None,
            'rigConverted':None,'provisionalConverted':None,'postureRoster':{'path':'exact','sha256':'a'*64},
            'postureStockBinding':{'path':'stock','sha256':'b'*64},
            'moduleName':'srn_female_test','actorAreaResref':'sr_tm_floor',
            'fixtureResourceHashes':{'sr_tm.set':'a'*64,'sr_tm_edge.2da':'b'*64}}
        proof={'document':{'moduleName':'srn_female_test','actorAreaResref':'sr_tm_floor'},'requiredCells':[]}
        with patch('preflight_target_body_client.contract.load',return_value=target), \
             patch('shared_female_posture_fixture.verify_roster',return_value=proof) as verify:
            self.assertIs(verified_posture_roster(build,'target',animation),proof)
            self.assertIs(verified_posture_roster(build,'target',None),proof)
            for key,value in [('runtimeBodySource','target-human-female'),('bodyConverted','custom-body'),
                    ('bodyNativeReceiptSha256','custom-receipt'),('rigConverted','private-rig'),('provisionalConverted','new-head')]:
                with self.subTest(field=key),self.assertRaisesRegex(ValueError,'installed female body'):
                    verified_posture_roster({**build,key:value},'target',animation)
            bad={k:v for k,v in build.items() if k!='postureRoster'}
            with self.assertRaisesRegex(ValueError,'typed posture roster'): verified_posture_roster(bad,'target',animation)
            with self.assertRaisesRegex(ValueError,'declared roster'): verified_posture_roster(bad,'target',None)
            self.assertIsNone(verified_posture_roster({k:v for k,v in bad.items() if k!='postureStockBinding'},'target',None))
            with self.assertRaisesRegex(ValueError,'installed stock binding'):
                verified_posture_roster({k:v for k,v in build.items() if k!='postureStockBinding'},'target',None)
            with self.assertRaisesRegex(ValueError,'installed female body'):
                verified_posture_roster(build,'target',{'kind':'ordinary-human-overlay'})
            with self.assertRaisesRegex(ValueError,'differs from typed'):
                verified_posture_roster({**build,'actorAreaResref':'wrong'},'target',animation)
            for hashes in ({},{'sr_tm.set':'a'*64},{**build['fixtureResourceHashes'],'unknown.tga':'c'*64}):
                with self.subTest(fixture=hashes),self.assertRaisesRegex(ValueError,'two fixture dependencies'):
                    verified_posture_roster({**build,'fixtureResourceHashes':hashes},'target',animation)
            verify.side_effect=ValueError('stale or cross-target roster')
            with self.assertRaisesRegex(ValueError,'stale or cross-target'): verified_posture_roster(build,'target',animation)


    def test_installed_basis_requires_live_matching_verification(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from preflight_target_body_client import verified_posture_stock_basis
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary); tool=root/'resman.exe'; tool.write_bytes(b'synthetic')
            basis=root/'stock.json'; basis.write_text(json.dumps({'resmanTool':{
                'path':str(tool),'sha256':contract.sha(tool)}}))
            entry={'path':str(basis),'sha256':contract.sha(basis)}
            roster={'path':'roster','sha256':'a'*64}
            build={'postureStockBinding':entry,'postureRoster':roster,'gameRoot':'game',
                'resmanTool':str(tool),'resmanToolSha256':contract.sha(tool)}
            proof={'kind':'verified-shared-female-installed-stock-basis','postureStockBinding':entry,
                'postureRoster':roster,'liveSourceLookupExecuted':True,'clientAccepted':False,
                'runtimeSelected':False,'productionAccepted':False}
            guard=Mock(return_value=proof)
            with patch.dict('sys.modules',{'shared_female_stock_basis':SimpleNamespace(verify_stock_basis=guard)}):
                self.assertIs(verified_posture_stock_basis(build,'target',{},'client'),proof)
                guard.assert_called_once_with(entry,'target',roster,game_root='game',client_path='client',live_source_lookup=True)
                for key,value in [('liveSourceLookupExecuted',False),('postureRoster',{}),('clientAccepted',True),
                                  ('runtimeSelected',True),('productionAccepted',True),('kind','recorded-only')]:
                    guard.return_value={**proof,key:value}
                    with self.subTest(field=key),self.assertRaisesRegex(ValueError,'Executed live'):
                        verified_posture_stock_basis(build,'target',{},'client')
                guard.side_effect=ValueError('installed archive drift')
                with self.assertRaisesRegex(ValueError,'archive drift'):
                    verified_posture_stock_basis(build,'target',{},'client')
                guard.side_effect=None; guard.return_value=proof
                with self.assertRaisesRegex(ValueError,'lookup tool differs'):
                    verified_posture_stock_basis({**build,'resmanToolSha256':'f'*64},'target',{},'client')
                basis.write_text('{}')
                with self.assertRaisesRegex(ValueError,'changed'):
                    verified_posture_stock_basis(build,'target',{},'client')
            self.assertIsNone(verified_posture_stock_basis({},'target',None,'client'))
            with self.assertRaisesRegex(ValueError,'declared roster'):
                verified_posture_stock_basis(build,'target',None,'client')
            with self.assertRaisesRegex(ValueError,'Exact installed'):
                verified_posture_stock_basis({**build,'postureStockBinding':None},'target',{},'client')

    def test_each_posture_actor_resolves_installed_identity_tables(self):
        from preflight_target_body_client import audit_posture_identity_tables
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary); pins={}
            texts={'appearance.2da':'2DA V2.0\n\nMODELTYPE RACE\n0 P D\n6 P H\n',
                   'racialtypes.2da':'2DA V2.0\n\nAppearance PlayerRace\n0 0 1\n6 6 1\n',
                   'phenotype.2da':'2DA V2.0\n\nLabel\n0 Normal\n2 Large\n'}
            for name,text in texts.items():
                path=root/name;path.write_text(text)
                pins[name]={'path':str(path),'sha256':contract.sha(path)}
            actors=[{'tag':'tm_0','raceId':0,'appearanceId':0,'phenotypeId':2,'femaleRoot':'pfd2'},
                    {'tag':'tm_1','raceId':6,'appearanceId':6,'phenotypeId':0,'femaleRoot':'pfh0'}]
            report={'document':{'actors':actors}}
            self.assertEqual(len(audit_posture_identity_tables(report,pins)),2)
            for key,value in [('femaleRoot','pfe2'),('raceId',6),('phenotypeId',1),('appearanceId',99)]:
                bad={'document':{'actors':[{**actors[0],key:value},actors[1]]}}
                with self.subTest(field=key),self.assertRaisesRegex(ValueError,'installed appearance'):
                    audit_posture_identity_tables(bad,pins)
            path=root/'racialtypes.2da';path.write_text(texts['racialtypes.2da'].replace('0 0 1','0 6 1'))
            pins['racialtypes.2da']={'path':str(path),'sha256':contract.sha(path)}
            with self.assertRaisesRegex(ValueError,'installed appearance'):
                audit_posture_identity_tables(report,pins)


if __name__ == '__main__': unittest.main()
