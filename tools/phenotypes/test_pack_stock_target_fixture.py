"""Packaging guards reject cross-target/module/output contamination before copying."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import target_contract as contract
from pack_stock_target_fixture import pack
from test_target_part_pipeline import target_fixture


class StockFixturePackageTests(unittest.TestCase):
    def test_wrong_target_binding_and_unsafe_module_or_output_fail_before_mutation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve(); helper=root/'tools/phenotypes/pack_stock_target_fixture.py'; helper.parent.mkdir(parents=True)
            target=target_fixture(); target['rig']['mode']='stock-exact'; target['identity'].update(gender='female',prefix='pfh0',raceId=6,appearanceRow=6)
            target_path=root/'target.json'; target_path.write_text('{}'); prepared=root/'prepared.json'
            valid={'kind':'target-fixture-source',**contract.binding(target_path,target,'runtime'),'moduleName':'srn_female_test'}
            allowed=root/'output/phenotypes'/target['id']
            for label,changes,output in [('cross-target',{'targetId':'other'},allowed/'wrong-target'),
                                          ('module',{'moduleName':'../escape'},allowed/'wrong-module'),
                                          ('output',{},root/'outside-target')]:
                with self.subTest(label=label):
                    prepared.write_text(json.dumps({**valid,**changes}))
                    with patch('pack_stock_target_fixture.contract.load',return_value=target),patch('pack_stock_target_fixture.__file__',str(helper)),self.assertRaises(ValueError):
                        pack(target_path,prepared,contract.sha(prepared),root,root,output)
                    self.assertFalse(output.exists())

    def test_legacy_retargeted_target_does_not_enter_stock_pack_path(self):
        with patch('pack_stock_target_fixture.contract.load',return_value=target_fixture()),self.assertRaisesRegex(ValueError,'Stock-exact target required'):
            pack('target','unused','unused','tools','game','output')


class AnimationOverlayPackageTests(unittest.TestCase):
    def fixture(self, root):
        from target_fixture import module_name
        helper=root/'tools/phenotypes/pack_stock_target_fixture.py'; helper.parent.mkdir(parents=True); helper.write_text('# test fixture path')
        target=target_fixture(); target['rig']['mode']='stock-exact'; target['identity'].update(gender='female',prefix='pfh0',raceId=6,appearanceRow=6)
        target_path=root/'target.json'; target_path.write_text('{}')
        source=root/'prepared'; source.mkdir(); (source/'module-resources').mkdir(); (source/'hak-resources').mkdir()
        (source/'module-resources/module.ifo').write_bytes(b'test module resource')
        (source/'hak-resources/sr_tm.set').write_bytes(b'test fixture tile')
        module=source/'native.mod'; module.write_bytes(b'test archive')
        from target_body_inventory import flat_hashes
        data={'kind':'target-fixture-source',**contract.binding(target_path,target,'runtime'),'moduleName':module_name(target),
              'module':str(module),'moduleSha256':contract.sha(module),'moduleResourceHashes':flat_hashes(source/'module-resources'),
              'fixtureResourceHashes':flat_hashes(source/'hak-resources'),'runtimeBodySource':'stock-human-female',
              'stockTableBaselines':{},'profile':'stock-human-female-poses','actorAreaResref':'sr_tm_floor','configuration':{}}
        prepared=source/'prepared.json'; prepared.write_text(json.dumps(data))
        tools=root/'utilities'; tools.mkdir()
        for name in ('nwn_erf.exe','nwn_gff.exe','nwn_resman_cat.exe'): (tools/name).write_bytes(name.encode())
        overlay=root/'overlay'; overlay.mkdir(); receipt=overlay/'receipt.json'; receipt.write_text('{"test":true}')
        hashes={}; paths={}
        for name in ('pfh0.mdl','srn_fa_h0.mdl'):
            path=overlay/name; path.write_bytes(b'\0\0\0\0'+name.encode()); hashes[name]=contract.sha(path); paths[name]=str(path)
        entry={'path':str(receipt),'sha256':contract.sha(receipt)}
        report={'resourceHashes':hashes,'resourcePaths':paths,'frozenInputs':{str(receipt):entry['sha256']}}
        return helper,target,target_path,prepared,tools,entry,report

    def run_pack(self, root, fixture, name, overlay=None, posture_roster=None, body=None, posture_stock_binding=None):
        from types import SimpleNamespace
        helper,target,target_path,prepared,tools,entry,report=fixture
        output=root/'output/phenotypes'/target['id']/name
        def erf(command,**kwargs):
            Path(command[command.index('-f')+1]).write_bytes(b'test hak archive')
            return SimpleNamespace(returncode=0)
        with patch('pack_stock_target_fixture.contract.load',return_value=target),patch('pack_stock_target_fixture.__file__',str(helper)), \
             patch('pack_stock_target_fixture.archive',return_value=[]),patch('pack_stock_target_fixture.compare_archive'), \
             patch('pack_stock_target_fixture.subprocess.run',side_effect=erf):
            return pack(target_path,prepared,contract.sha(prepared),tools,root,output,body=body,animation_overlay=overlay,posture_roster=posture_roster,posture_stock_binding=posture_stock_binding)

    def test_verified_overlay_is_separate_exact_copy_and_plain_stock_has_no_overlay(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve(); fixture=self.fixture(root); entry,report=fixture[-2:]
            verify=Mock(return_value=report)
            with patch.dict('sys.modules',{'target_animation_overlay':SimpleNamespace(verify_animation_overlay=verify)}):
                receipt=self.run_pack(root,fixture,'with-overlay',entry); data=json.loads(receipt.read_text())
                self.assertEqual(data['animationOverlay'],entry); self.assertEqual(data['animationResourceHashes'],report['resourceHashes'])
                self.assertEqual(data['fixtureResourceHashes'],{'sr_tm.set':contract.sha(receipt.parent/'hak-resources/sr_tm.set')})
                for name,expected in report['resourceHashes'].items(): self.assertEqual(contract.sha(receipt.parent/'hak-resources'/name),expected)
                self.assertFalse(any((Path(data['userDirectory'])/'override').iterdir())); self.assertFalse(data['clientLaunched'])
                self.assertEqual(verify.call_count,2)
                plain=self.run_pack(root,fixture,'plain-stock'); ordinary=json.loads(plain.read_text())
                self.assertNotIn('animationOverlay',ordinary); self.assertNotIn('animationResourceHashes',ordinary)
                self.assertEqual(verify.call_count,2)

    def test_overlay_verifier_rejection_and_fixture_collision_leave_output_absent(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve(); fixture=self.fixture(root); entry,report=fixture[-2:]
            verify=Mock(side_effect=ValueError('stale or cross-target overlay'))
            with patch.dict('sys.modules',{'target_animation_overlay':SimpleNamespace(verify_animation_overlay=verify)}),self.assertRaisesRegex(ValueError,'cross-target'):
                self.run_pack(root,fixture,'rejected',entry)
            self.assertFalse((root/'output/phenotypes'/fixture[1]['id']/'rejected').exists())
            prepared=fixture[3]; data=json.loads(prepared.read_text()); path=prepared.parent/'hak-resources/pfh0.mdl'; path.write_bytes(b'colliding fixture root')
            data['fixtureResourceHashes']['pfh0.mdl']=contract.sha(path); prepared.write_text(json.dumps(data))
            with patch.dict('sys.modules',{'target_animation_overlay':SimpleNamespace(verify_animation_overlay=Mock(return_value=report))}),self.assertRaisesRegex(ValueError,'overlaps'):
                self.run_pack(root,fixture,'colliding',entry)
            self.assertFalse((root/'output/phenotypes'/fixture[1]['id']/'colliding').exists())

    def test_consumer_rechecks_exact_model_inventory_and_source_drift(self):
        from pack_stock_target_fixture import verified_animation_overlay
        from types import SimpleNamespace
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve(); fixture=self.fixture(root); entry,report=fixture[-2:]; target_path=fixture[2]
            with self.assertRaisesRegex(ValueError,'exact receipt'): verified_animation_overlay({'path':entry['path'],'sha256':entry['sha256'],'trusted':True},target_path)
            bad={**report,'resourceHashes':{**report['resourceHashes'],'a_fa.mdl':'0'*64}}
            with patch.dict('sys.modules',{'target_animation_overlay':SimpleNamespace(verify_animation_overlay=Mock(return_value=bad))}),self.assertRaisesRegex(ValueError,'exactly'):
                verified_animation_overlay(entry,target_path)
            Path(report['resourcePaths']['pfh0.mdl']).write_bytes(b'changed after verification')
            with patch.dict('sys.modules',{'target_animation_overlay':SimpleNamespace(verify_animation_overlay=Mock(return_value=report))}),self.assertRaisesRegex(ValueError,'changed'):
                verified_animation_overlay(entry,target_path)


class SharedFemaleOverlayPackageTests(unittest.TestCase):
    fixture = AnimationOverlayPackageTests.fixture
    def run_pack(self, root, fixture, name, overlay=None, posture_roster=None, body=None, posture_stock_binding="automatic"):
        if posture_stock_binding == "automatic":
            posture_stock_binding = self.stock_binding_pin if posture_roster is not None else None
        return AnimationOverlayPackageTests.run_pack(self,root,fixture,name,overlay,posture_roster,body,posture_stock_binding)

    def shared_fixture(self, root):
        from shared_female_native_contract import ROOTS
        from test_shared_female_posture_fixture import roster, native_rows
        from target_body_inventory import flat_hashes
        fixture = self.fixture(root)
        helper,target,target_path,prepared,tools,entry,report = fixture
        receipt = Path(entry['path'])
        receipt.write_text(json.dumps({'kind':'executed-shared-female-source-native-idle-overlay'}))
        entry['sha256'] = contract.sha(receipt)
        report['frozenInputs'][str(receipt)] = entry['sha256']
        for family in ROOTS:
            for name in (family+'.mdl','srn_fa_'+family[2:]+'.mdl'):
                path = receipt.parent/name
                path.write_bytes(bytes(4)+name.encode())
                report['resourceHashes'][name] = contract.sha(path)
                report['resourcePaths'][name] = str(path)
        report['kind'] = 'verified-shared-female-source-native-animation-overlay'
        (prepared.parent/'hak-resources/sr_tm_edge.2da').write_bytes(b'stock diagnostic edge')
        document = roster()
        roster_path = root/'reviewed-roster.json'; roster_path.write_text(json.dumps(document))
        self.roster_pin = {'path':str(roster_path),'sha256':contract.sha(roster_path)}
        self.roster_report = {'kind':'verified-shared-female-posture-roster','roster':self.roster_pin,
            'document':document,'frozenInputs':{str(roster_path):self.roster_pin['sha256']}}
        self.native_rows = native_rows(document)
        import copy, shutil
        import shared_female_stock_basis
        data = json.loads(prepared.read_text())
        data['postureRoster'] = self.roster_pin
        data['fixtureResourceHashes'] = flat_hashes(prepared.parent/'hak-resources')
        source = prepared.parent
        names = {'module.ifo','sr_tm_floor.are','sr_tm_floor.git','repute.fac','sr_tm_target.utc'}
        names |= {name+ext for name in ('sr_tm_spawn','sr_tm_next','sr_tm_enter','sr_tm_damage','sr_tm_death')
                  for ext in ('.nss','.ncs')}
        for name in names:
            path = source/'module-resources'/name
            if not path.exists(): path.write_bytes(('native source '+name).encode())
        data['moduleResourceHashes'] = flat_hashes(source/'module-resources')
        parent = root/'original-parent'; parent.mkdir()
        shutil.copytree(source/'module-resources',parent/'module-resources')
        shutil.copytree(source/'hak-resources',parent/'hak-resources')
        parent_module = parent/'original.mod'; parent_module.write_bytes(b'original parent native module')
        def write(path,value):
            path.write_text(json.dumps(value))
            return {'path':str(path),'sha256':contract.sha(path)}
        self.decoded_document = {'Creature List':{'type':'list','value':copy.deepcopy(self.native_rows)},
                                 'Waypoint List':{'type':'list','value':[]}}
        decoded = write(source/'native-actors.json',self.decoded_document)
        original_proof = write(parent/'source-proof.json',
            {'actualNativeGIT':{'path':str(parent/'module-resources/sr_tm_floor.git'),
                               'sha256':contract.sha(parent/'module-resources/sr_tm_floor.git')}})
        parent_data = {**data,'module':str(parent_module),'moduleSha256':contract.sha(parent_module),
            'sourceProof':original_proof,'moduleResourceHashes':flat_hashes(parent/'module-resources')}
        parent_pin = write(parent/'preparation.json',parent_data)
        recipe = write(root/'recipe.json',{'sourcePreparation':parent_pin,'sourceProof':original_proof})
        coverage = write(root/'coverage.json',{'covered':'all four roster batches'})
        self.stock_binding_pin = write(root/'stock-binding.json',{'rosterRecipe':recipe,'coverage':coverage})
        self.stock_binding_report = {'kind':'verified-shared-female-installed-stock-basis',
            'postureStockBinding':self.stock_binding_pin,'postureRoster':self.roster_pin,
            'liveSourceLookupExecuted':False,'coverage':coverage,
            'frozenInputs':{self.stock_binding_pin['path']:self.stock_binding_pin['sha256'],
                            self.roster_pin['path']:self.roster_pin['sha256']}}
        from shared_female_posture_fixture import GFF_FIELDS, PLACEMENT_FIELDS
        proof = {'schemaVersion':1,'kind':'shared-female-stockbody-roster-native-source-proof',
            **contract.binding(target_path,target,'runtime'),'pass':True,
            'postureRoster':self.roster_pin,'postureStockBinding':self.stock_binding_pin,
            'parentSourcePreparation':parent_pin,'parentSourceProof':original_proof,
            'parentNativeModule':{'path':str(parent_module),'sha256':contract.sha(parent_module)},
            'parentNativeGIT':{'path':str(parent/'module-resources/sr_tm_floor.git'),
                'sha256':contract.sha(parent/'module-resources/sr_tm_floor.git')},
            'nativeModule':{'path':data['module'],'sha256':data['moduleSha256']},
            'actualNativeGIT':{'path':str(source/'module-resources/sr_tm_floor.git'),
                'sha256':contract.sha(source/'module-resources/sr_tm_floor.git')},
            'decodedNativeGIT':decoded,
            'authorizedActorFields':sorted(set(GFF_FIELDS)|PLACEMENT_FIELDS|{'Equip_ItemList','VarTable'}),
            'protected14ModuleResourceHashes':{n:h for n,h in data['moduleResourceHashes'].items() if n!='sr_tm_floor.git'},
            'fixtureResourceHashes':data['fixtureResourceHashes'],'stockTableBaselines':data['stockTableBaselines'],
            'allOtherNativeGITFieldsExact':True,'scriptCompileCalls':0,'modelCompileCalls':0,
            'nativeGITEncodeCalls':1,'nativeMODPackCalls':1,
            **{k:False for k in ('HAKBuilt','clientLaunched','clientAccepted','runtimeSelected','productionAccepted')}}
        self.source_proof_path = source/'source-proof.json'
        data.update(sourceProof=write(self.source_proof_path,proof),parentSourcePreparation=parent_pin,
                    parentSourceProof=original_proof,postureStockBinding=self.stock_binding_pin)
        prepared.write_text(json.dumps(data))
        return fixture

    def guards(self, report, native=None):
        from contextlib import ExitStack
        from types import SimpleNamespace
        from unittest.mock import Mock
        stack = ExitStack()
        self.shared_verify = Mock(return_value=report)
        self.human_verify = Mock(side_effect=ValueError('Human receipt kind required'))
        self.roster_verify = Mock(return_value=self.roster_report)
        stack.enter_context(patch.dict('sys.modules',{
            'shared_female_animation_overlay':SimpleNamespace(verify_shared_female_animation_overlay=self.shared_verify),
            'target_animation_overlay':SimpleNamespace(verify_animation_overlay=self.human_verify)}))
        stack.enter_context(patch('shared_female_posture_fixture.verify_roster',self.roster_verify))
        self.actor_reader = stack.enter_context(patch('preflight_target_body_client.actor_rows',
            return_value=self.native_rows if native is None else native))
        self.full_decoder = stack.enter_context(patch('preflight_target_body_client.decode_gff',
            return_value=self.decoded_document))
        self.basis_verify = stack.enter_context(patch('shared_female_stock_basis.verify_stock_basis',
            return_value=self.stock_binding_report))
        return stack

    def test_exact_shared_candidate_and_matching_stock_keep_stock_body_and_native_roster(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve(); fixture=self.shared_fixture(root); entry,report=fixture[-2:]
            with self.guards(report):
                candidate=json.loads(self.run_pack(root,fixture,'shared-candidate',entry,self.roster_pin).read_text())
                stock=json.loads(self.run_pack(root,fixture,'shared-stock',posture_roster=self.roster_pin).read_text())
                self.assertEqual(self.shared_verify.call_count,2)
                self.human_verify.assert_not_called()
                self.assertEqual(self.roster_verify.call_count,4)
                self.assertEqual(self.actor_reader.call_count,4)
            self.assertEqual(len(candidate['animationResourceHashes']),24)
            self.assertNotIn('animationOverlay',stock)
            for data in (stock,candidate):
                self.assertIsNone(data['bodyConverted']); self.assertIsNone(data['rigConverted'])
                self.assertIsNone(data['provisionalConverted'])
                self.assertEqual(data['postureRoster'],self.roster_pin)
                self.assertTrue(data['postureNativeActorsValidated'])
                self.assertFalse(data['clientLaunched']); self.assertFalse(data['clientAccepted'])
                self.assertFalse(any((Path(data['userDirectory'])/'override').iterdir()))
            self.assertEqual(Path(stock['module']).read_bytes(),Path(candidate['module']).read_bytes())
            self.assertEqual(stock['fixtureResourceHashes'],candidate['fixtureResourceHashes'])
            for name,digest in report['resourceHashes'].items():
                self.assertEqual(contract.sha(Path(candidate['userDirectory']).parent/'test-module/hak-resources'/name),digest)

    def test_explicit_receipt_kind_and_hash_are_required(self):
        from pack_stock_target_fixture import verified_animation_overlay
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve(); fixture=self.shared_fixture(root); entry,report=fixture[-2:]
            receipt=Path(entry['path']); receipt.write_text(json.dumps({'kind':'generic-rig-exemption'}))
            entry['sha256']=contract.sha(receipt); report['frozenInputs'][str(receipt)]=entry['sha256']
            with self.guards(report),self.assertRaisesRegex(ValueError,'Human receipt kind'):
                verified_animation_overlay(entry,fixture[2])
            self.shared_verify.assert_not_called()
            receipt.write_text(json.dumps({'kind':'executed-shared-female-source-native-idle-overlay'}))
            with self.guards(report),self.assertRaisesRegex(ValueError,'changed'):
                verified_animation_overlay(entry,fixture[2])
            self.shared_verify.assert_not_called()

    def test_partial_extra_path_inventory_and_wrong_verified_kind_fail(self):
        import copy
        from pack_stock_target_fixture import verified_animation_overlay
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve(); fixture=self.shared_fixture(root); entry,report=fixture[-2:]
            variants=[]
            missing=copy.deepcopy(report);missing['resourceHashes'].pop('pfo2.mdl');variants.append(missing)
            extra=copy.deepcopy(report);extra['resourceHashes']['a_fa.mdl']='0'*64;variants.append(extra)
            wrong_path=copy.deepcopy(report);wrong_path['resourcePaths'].pop('pfd2.mdl');variants.append(wrong_path)
            wrong_kind=copy.deepcopy(report);wrong_kind['kind']='verified-single-human-source-native-animation-overlay';variants.append(wrong_kind)
            for bad in variants:
                with self.subTest(case=bad.get('kind')),self.guards(bad),self.assertRaises(ValueError):
                    verified_animation_overlay(entry,fixture[2])
            path=Path(report['resourcePaths']['pfg0.mdl']);path.write_bytes(b'source drift')
            with self.guards(report),self.assertRaisesRegex(ValueError,'changed'):
                verified_animation_overlay(entry,fixture[2])

    def test_shared_overlay_requires_roster_and_rejects_custom_body_before_native_body_read(self):
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve(); fixture=self.shared_fixture(root); entry,report=fixture[-2:]
            with self.guards(report),self.assertRaisesRegex(ValueError,'explicit roster'):
                self.run_pack(root,fixture,'no-roster',entry)
            self.assertFalse((root/'output/phenotypes'/fixture[1]['id']/'no-roster').exists())
            data=json.loads(fixture[3].read_text());data['runtimeBodySource']='target-human-female'
            fixture[3].write_text(json.dumps(data))
            body_reader=Mock()
            with self.guards(report),patch('pack_stock_target_fixture.verify_native_body',body_reader),self.assertRaisesRegex(ValueError,'stock body'):
                self.run_pack(root,fixture,'custom-body',entry,self.roster_pin,root/'candidate-body')
            body_reader.assert_not_called()
            self.assertFalse((root/'output/phenotypes'/fixture[1]['id']/'custom-body').exists())

    def test_roster_pin_source_scene_and_fixture_dependencies_must_match(self):
        import copy
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve(); fixture=self.shared_fixture(root); entry,report=fixture[-2:]
            original=json.loads(fixture[3].read_text())
            data=copy.deepcopy(original);data['postureRoster']={**self.roster_pin,'sha256':'0'*64}
            fixture[3].write_text(json.dumps(data))
            with self.guards(report),self.assertRaisesRegex(ValueError,'exact posture roster'):
                self.run_pack(root,fixture,'wrong-roster',entry,self.roster_pin)
            self.assertFalse((root/'output/phenotypes'/fixture[1]['id']/'wrong-roster').exists())
            fixture[3].write_text(json.dumps(original))
            self.roster_report['document']['actorAreaResref']='another_area'
            with self.guards(report),self.assertRaisesRegex(ValueError,'module/area'):
                self.run_pack(root,fixture,'wrong-area',entry,self.roster_pin)
            self.assertFalse((root/'output/phenotypes'/fixture[1]['id']/'wrong-area').exists())
            self.roster_report['document']['actorAreaResref']='sr_tm_floor'
            path=fixture[3].parent/'hak-resources/pfo2.mdl';path.write_bytes(b'forbidden fixture rig')
            data=copy.deepcopy(original);data['fixtureResourceHashes']['pfo2.mdl']=contract.sha(path)
            fixture[3].write_text(json.dumps(data))
            with self.guards(report),self.assertRaisesRegex(ValueError,'two stock fixture'):
                self.run_pack(root,fixture,'rig-collision',entry,self.roster_pin)
            self.assertFalse((root/'output/phenotypes'/fixture[1]['id']/'rig-collision').exists())

    def test_actual_native_actor_head_race_phenotype_and_schedule_are_checked_before_copy(self):
        import copy
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve(); fixture=self.shared_fixture(root); entry,report=fixture[-2:]
            cases=[('missing-head',None),('wrong-race',('Race',{'type':'byte','value':6})),
                ('wrong-phenotype',('Phenotype',{'type':'int','value':2})),
                ('wrong-head-type',('Appearance_Head',{'type':'word','value':1}))]
            for label,change in cases:
                bad=copy.deepcopy(self.native_rows)
                if change is None:bad[0].pop('Appearance_Head')
                else:bad[0][change[0]]=change[1]
                with self.subTest(case=label),self.guards(report,bad),self.assertRaisesRegex(ValueError,'Native typed actor'):
                    self.run_pack(root,fixture,label,entry,self.roster_pin)
                self.assertFalse((root/'output/phenotypes'/fixture[1]['id']/label).exists())
            bad=copy.deepcopy(self.native_rows)
            bad[0]['VarTable']['value'][0]['Value']['value']=1
            with self.guards(report,bad),self.assertRaisesRegex(ValueError,'schedule'):
                self.run_pack(root,fixture,'wrong-schedule',entry,self.roster_pin)
            self.assertFalse((root/'output/phenotypes'/fixture[1]['id']/'wrong-schedule').exists())

    def test_redecode_copied_native_module_catches_late_actor_drift_without_final_receipt(self):
        import copy
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve(); fixture=self.shared_fixture(root); entry,report=fixture[-2:]
            bad=copy.deepcopy(self.native_rows);bad[0]['Appearance_Head']['value']=2
            with self.guards(report),self.assertRaisesRegex(ValueError,'Native typed actor'):
                self.actor_reader.side_effect=[self.native_rows,bad]
                self.run_pack(root,fixture,'late-actor-drift',entry,self.roster_pin)
            output=root/'output/phenotypes'/fixture[1]['id']/'late-actor-drift'
            self.assertTrue(output.exists())
            self.assertFalse((output/'test-module/receipt.json').exists())


class SharedFemaleStockBindingPackageTests(unittest.TestCase):
    fixture = AnimationOverlayPackageTests.fixture
    shared_fixture = SharedFemaleOverlayPackageTests.shared_fixture
    run_pack = SharedFemaleOverlayPackageTests.run_pack
    guards = SharedFemaleOverlayPackageTests.guards
    def update_proof(self, fixture, document):
        self.source_proof_path.write_text(json.dumps(document))
        data=json.loads(fixture[3].read_text())
        data['sourceProof']={'path':str(self.source_proof_path),'sha256':contract.sha(self.source_proof_path)}
        fixture[3].write_text(json.dumps(data))

    def test_binding_propagates_exact_coverage_proof_and_actual_consumed_inputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve(); fixture=self.shared_fixture(root); entry,report=fixture[-2:]
            with self.guards(report):
                data=json.loads(self.run_pack(root,fixture,'bound',entry,self.roster_pin).read_text())
                self.assertEqual(self.basis_verify.call_count,2)
                self.assertTrue(all(call.kwargs['live_source_lookup'] is False for call in self.basis_verify.call_args_list))
            self.assertEqual(data['postureStockBinding'],self.stock_binding_pin)
            self.assertEqual(data['postureCoverage'],self.stock_binding_report['coverage'])
            self.assertEqual(data['postureSourceProof'],json.loads(fixture[3].read_text())['sourceProof'])
            self.assertIn(str(self.source_proof_path),data['postureStockFrozenInputs'])
            self.assertEqual(data['postureStockFrozenInputs'][str(fixture[3].resolve())],contract.sha(fixture[3]))
            self.assertIn(str(fixture[4]/'nwn_gff.exe'),data['postureStockFrozenInputs'])
            self.assertFalse(data['clientAccepted'])
            self.assertIsNone(data['bodyConverted'])

    def test_missing_unbound_and_mismatched_binding_reject_before_copy(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve(); fixture=self.shared_fixture(root); entry,report=fixture[-2:]
            with self.guards(report),self.assertRaisesRegex(ValueError,'explicit installed stock binding'):
                self.run_pack(root,fixture,'missing-binding',entry,self.roster_pin,posture_stock_binding=None)
            with self.guards(report),self.assertRaisesRegex(ValueError,'posture roster'):
                self.run_pack(root,fixture,'binding-no-roster',posture_stock_binding=self.stock_binding_pin)
            bad={**self.stock_binding_pin,'sha256':'a'*64}
            with self.guards(report),self.assertRaisesRegex(ValueError,'changed'):
                self.run_pack(root,fixture,'stale-binding',entry,self.roster_pin,posture_stock_binding=bad)
            original=json.loads(fixture[3].read_text())
            original['postureStockBinding']={**self.stock_binding_pin,'path':'foreign'}
            fixture[3].write_text(json.dumps(original))
            with self.guards(report),self.assertRaisesRegex(ValueError,'exact posture stock binding'):
                self.run_pack(root,fixture,'mismatched-binding',entry,self.roster_pin)
            for name in ('missing-binding','binding-no-roster','stale-binding','mismatched-binding'):
                self.assertFalse((root/'output/phenotypes'/fixture[1]['id']/name).exists())

    def test_guard_rejection_and_wrong_verified_pin_or_kind_block_packing(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve(); fixture=self.shared_fixture(root); entry,report=fixture[-2:]
            with self.guards(report),self.assertRaisesRegex(ValueError,'installed archive changed'):
                self.basis_verify.side_effect=ValueError('installed archive changed')
                self.run_pack(root,fixture,'guard-failure',entry,self.roster_pin)
            for key,value in (('kind','generic-success'),('postureStockBinding',{}),('postureRoster',{}),
                              ('liveSourceLookupExecuted',True)):
                original=self.stock_binding_report[key];self.stock_binding_report[key]=value
                with self.subTest(key=key),self.guards(report),self.assertRaisesRegex(ValueError,'Explicit read-only'):
                    self.run_pack(root,fixture,'wrong-'+key,entry,self.roster_pin)
                self.stock_binding_report[key]=original

    def test_proof_parent_roster_and_operation_lineage_must_match(self):
        import copy
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve(); fixture=self.shared_fixture(root); entry,report=fixture[-2:]
            original=json.loads(self.source_proof_path.read_text())
            for key,value in (('postureRoster',{}),('postureStockBinding',{}),('parentSourcePreparation',{}),
                              ('nativeGITEncodeCalls',2),('clientAccepted',True)):
                bad=copy.deepcopy(original);bad[key]=value;self.update_proof(fixture,bad)
                with self.subTest(key=key),self.guards(report),self.assertRaises(ValueError):
                    self.run_pack(root,fixture,'proof-'+key,entry,self.roster_pin)
                self.assertFalse((root/'output/phenotypes'/fixture[1]['id']/('proof-'+key)).exists())
            self.update_proof(fixture,original)

    def test_protected_resource_bytes_and_authorized_actor_fields_are_independently_checked(self):
        import copy
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve(); fixture=self.shared_fixture(root); entry,report=fixture[-2:]
            original=json.loads(self.source_proof_path.read_text())
            bad=copy.deepcopy(original);bad['protected14ModuleResourceHashes']['module.ifo']='a'*64
            self.update_proof(fixture,bad)
            with self.guards(report),self.assertRaisesRegex(ValueError,'Protected fourteen'):
                self.run_pack(root,fixture,'protected-drift',entry,self.roster_pin)
            bad=copy.deepcopy(original);bad['authorizedActorFields'].append('Tag')
            self.update_proof(fixture,bad)
            with self.guards(report),self.assertRaisesRegex(ValueError,'authorized actor fields'):
                self.run_pack(root,fixture,'undeclared-authority',entry,self.roster_pin)

    def test_full_native_git_change_rejects_even_with_claimed_pass_and_matching_actor_rows(self):
        import copy
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve(); fixture=self.shared_fixture(root); entry,report=fixture[-2:]
            original=copy.deepcopy(self.decoded_document)
            changed=copy.deepcopy(original);changed['Waypoint List']['value']=[{'hidden':'change'}]
            proof=json.loads(self.source_proof_path.read_text())
            decoded=Path(proof['decodedNativeGIT']['path']);decoded.write_text(json.dumps(changed))
            proof['decodedNativeGIT']['sha256']=contract.sha(decoded);self.update_proof(fixture,proof)
            with self.guards(report),self.assertRaisesRegex(ValueError,'Undeclared native GIT fields'):
                self.full_decoder.side_effect=[changed,original]
                self.run_pack(root,fixture,'hidden-native-change',entry,self.roster_pin)
            self.assertFalse((root/'output/phenotypes'/fixture[1]['id']/'hidden-native-change').exists())

    def test_only_pose_palette_values_can_change_inside_ordered_actor_locals(self):
        import copy
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve(); fixture=self.shared_fixture(root); entry,report=fixture[-2:]
            original=copy.deepcopy(self.decoded_document)
            unrelated={'Name':{'type':'cexostring','value':'UNCHANGED_LOCAL'},
                'Type':{'type':'dword','value':1},'Value':{'type':'int','value':17}}
            original['Creature List']['value'][0]['VarTable']['value'].append(unrelated)
            for label in ('unrelated-value','extra-local','unrelated-type','reordered-locals'):
                changed=copy.deepcopy(original)
                variables=changed['Creature List']['value'][0]['VarTable']['value']
                if label=='unrelated-value': variables[-1]['Value']['value']=99
                elif label=='extra-local':
                    variables.append({'Name':{'type':'cexostring','value':'EXTRA_LOCAL'},
                        'Type':{'type':'dword','value':1},'Value':{'type':'int','value':17}})
                elif label=='unrelated-type': variables[-1]['Type']['value']=2
                else: variables[0],variables[-1]=variables[-1],variables[0]
                proof=json.loads(self.source_proof_path.read_text())
                decoded=Path(proof['decodedNativeGIT']['path']);decoded.write_text(json.dumps(changed))
                proof['decodedNativeGIT']['sha256']=contract.sha(decoded);self.update_proof(fixture,proof)
                with self.subTest(case=label),self.guards(report),self.assertRaisesRegex(ValueError,'Unrelated native actor locals'):
                    self.full_decoder.side_effect=[changed,original]
                    self.run_pack(root,fixture,label,entry,self.roster_pin)
                self.assertFalse((root/'output/phenotypes'/fixture[1]['id']/label).exists())
    def test_after_copy_binding_input_drift_leaves_partial_output_without_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve(); fixture=self.shared_fixture(root); entry,report=fixture[-2:]
            calls=0
            def verify(*args,**kwargs):
                nonlocal calls
                calls+=1
                if calls==2: raise ValueError('installed archive changed after copy')
                return self.stock_binding_report
            with self.guards(report),self.assertRaisesRegex(ValueError,'changed after copy'):
                self.basis_verify.side_effect=verify
                self.run_pack(root,fixture,'late-stock-drift',entry,self.roster_pin)
            output=root/'output/phenotypes'/fixture[1]['id']/'late-stock-drift'
            self.assertTrue(output.exists())
            self.assertFalse((output/'test-module/receipt.json').exists())

if __name__ == '__main__': unittest.main()
