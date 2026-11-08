"""Indexed namespaces must preserve byte and membership checks without payload scans."""
from pathlib import Path
import struct
import tempfile
import unittest
from tools.headkit.common import pin,read,write
from tools.itemkit.native_stack import namespace,key_names
from tools.itemkit.test_itemkit import Fixture
from tools.itemkit import contracts


def key(path,names):
    data=bytearray(64+22*len(names));data[:8]=b'KEY V1  '
    struct.pack_into('<I',data,12,len(names));struct.pack_into('<I',data,20,64)
    for i,(name,kind) in enumerate(names):struct.pack_into('<16sHI',data,64+22*i,name.encode(),kind,i)
    path.write_bytes(data)


class IndexedNamespaceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.installed=self.root/'installed';self.installed.mkdir()
        self.origin=self.installed/'base.key';key(self.origin,[('wswss_t_071',2002),('sr_cfl_07',2033),('foo',10)])
        self.copy=self.root/'copy.key';self.copy.write_bytes(self.origin.read_bytes())
        self.archive=self.installed/'models.bif';self.archive.write_bytes(b'fixture archive')
        write(self.root/'proof.json',{'kind':'verified-stock-native-extraction','noOverrides':True,'resources':[]})
        self.inputs=[pin(self.origin),pin(self.archive)]
        write(self.root/'launch.json',{'exitCode':0,'inputsUnchanged':True,'frozenInputs':{r['path']:r['sha256'] for r in self.inputs}})
        self.data={'kind':'nwn-key-namespace-v1','complete':True,'scope':'installed-stock-en-no-overrides',
          'keys':[{'path':'copy.key','sha256':pin(self.copy)['sha256']}],'originKeys':[pin(self.origin)],
          'keyDirectories':[str(self.installed)],'sourceArchives':[pin(self.archive)],
          'extractionProof':{'path':'proof.json','sha256':pin(self.root/'proof.json')['sha256']},
          'extractionLaunch':{'path':'launch.json','sha256':pin(self.root/'launch.json')['sha256']}}
        self.save()
    def tearDown(self):self.temp.cleanup()
    def save(self):
        write(self.root/'index.json',self.data)
        self.layer={'resources':[],'nameInventory':{'path':'index.json','sha256':pin(self.root/'index.json')['sha256']}}
    def test_key_names_include_native_collisions_without_reading_payloads(self):
        names,selected,pins=namespace(self.root/'stack.json',self.layer)
        self.assertEqual(names,{'wswss_t_071.mdl','sr_cfl_07.dds'});self.assertEqual(selected,{})
        self.assertTrue({pin(self.origin)['path'],pin(self.archive)['path']} <= {r['path'] for r in pins})
    def test_new_index_membership_invalidates_old_proof(self):
        key(self.installed/'added.key',[('wswss_t_081',2002)])
        with self.assertRaisesRegex(ValueError,'membership'):namespace(self.root/'stack.json',self.layer)
    def test_stock_blueprint_names_are_reserved_without_extracting_payloads(self):
        key(self.copy,[('existing_item',2025),('not_an_item',10)])
        self.assertEqual(key_names(self.copy),{'existing_item.uti'})
    def test_changed_source_archive_or_index_is_rejected(self):
        for path in (self.origin,self.archive):
            before=path.read_bytes();path.write_bytes(before[:-1]+bytes([before[-1]^1]))
            with self.assertRaises(ValueError):namespace(self.root/'stack.json',self.layer)
            path.write_bytes(before)
    def test_extraction_must_have_consumed_bound_archives(self):
        write(self.root/'launch.json',{'exitCode':0,'inputsUnchanged':True,'frozenInputs':{}})
        self.data['extractionLaunch']['sha256']=pin(self.root/'launch.json')['sha256'];self.save()
        with self.assertRaisesRegex(ValueError,'did not consume'):namespace(self.root/'stack.json',self.layer)
    def test_key_table_bounds_are_checked(self):
        self.copy.write_bytes(self.copy.read_bytes()[:-1])
        with self.assertRaisesRegex(ValueError,'escapes'):key_names(self.copy)
    def test_unqualified_namespace_is_rejected(self):
        self.data['complete']=False;self.save()
        with self.assertRaisesRegex(ValueError,'Incomplete'):namespace(self.root/'stack.json',self.layer)
    def test_published_namespace_requires_both_bodies_and_exact_counts(self):
        rows=[]
        for gender,prefix in (('male','pmh0'),('female','pfh0')):
            path=self.root/(gender+'.json');write(path,{'kind':'published-validated-target-body','productionAccepted':True,
                'gender':gender,'prefix':prefix,'pack':'srn_body','resourceCount':1,'resources':[{'path':'srn_body/'+prefix+'_handr001.mdl'}]})
            rows.append({'path':path.name,'sha256':pin(path)['sha256']})
        write(self.root/'bodies.json',{'kind':'published-human-namespace-v1','complete':True,'manifests':rows})
        layer={'nameInventory':{'path':'bodies.json','sha256':pin(self.root/'bodies.json')['sha256']}}
        names,_,_=namespace(self.root/'stack.json',layer)
        self.assertEqual(names,{'pmh0_handr001.mdl','pfh0_handr001.mdl'})
        write(self.root/'bodies.json',{'kind':'published-human-namespace-v1','complete':True,'manifests':rows[:1]})
        layer['nameInventory']['sha256']=pin(self.root/'bodies.json')['sha256']
        with self.assertRaisesRegex(ValueError,'Both shipped'):namespace(self.root/'stack.json',layer)


class IndexedContractTests(Fixture):
    def indexed(self):
        self.native();stack_path=self.path.parent/'stack/stack.json';stack=read(stack_path)
        root=stack_path.parent;installed=root/'installed';installed.mkdir()
        entries=[('baseitems',2017)]+[(f'wswss_{p}_011',2002) for p in contracts.PARTS]+[('wswss_t_071',2002)]
        origin=installed/'base.key';key(origin,entries);copy=root/'copy.key';copy.write_bytes(origin.read_bytes())
        archive=installed/'stock.bif';archive.write_bytes(b'fixture selected source archive')
        rows=[pin(origin),pin(archive)]
        write(root/'proof.json',{'kind':'verified-stock-native-extraction','noOverrides':True,'resources':stack['layers'][0]['resources']})
        write(root/'launch.json',{'exitCode':0,'inputsUnchanged':True,'frozenInputs':{r['path']:r['sha256'] for r in rows}})
        def relative(path):return {'path':path.name,'sha256':pin(path)['sha256']}
        write(root/'index.json',{'kind':'nwn-key-namespace-v1','complete':True,'scope':'installed-stock-en-no-overrides',
          'keys':[relative(copy)],'originKeys':[pin(origin)],'keyDirectories':[str(installed)],'sourceArchives':[pin(archive)],
          'extractionProof':relative(root/'proof.json'),'extractionLaunch':relative(root/'launch.json')})
        stack['layers'][0]['nameInventory']=relative(root/'index.json');write(stack_path,stack)
        self.profile['native']['stack']['sha256']=pin(stack_path)['sha256'];self.save_profile()
        return stack_path,archive
    def test_index_only_occupied_slot_rejects_collision_and_allows_next_slot(self):
        self.indexed();_,resources=contracts.native_contract(self.profile_path,self.profile)
        self.assertIsNone(resources['wswss_t_071.mdl'])
        with self.assertRaisesRegex(ValueError,'collision-free'):contracts.reserve(self.profile,resources,index=7)
        self.assertEqual(contracts.reserve(self.profile,resources,index=8)['modelIndex'],8)
    def test_all_inputs_include_index_and_source_archive_pins(self):
        _,archive=self.indexed()
        pins=contracts.all_pins(self.path)
        self.assertIn(pin(archive),pins)
    def test_selected_donor_cannot_disagree_with_stock_extraction(self):
        stack_path,_=self.indexed();stack=read(stack_path)
        donor=stack_path.parent/'base/wswss_t_011.mdl';donor.write_bytes(b'changed donor')
        stack['layers'][0]['resources'][-1]['file']['sha256']=pin(donor)['sha256'];write(stack_path,stack)
        self.profile['native']['stack']['sha256']=pin(stack_path)['sha256'];self.save_profile()
        with self.assertRaisesRegex(ValueError,'differs from its stock extraction'):contracts.family(self.profile_path)


if __name__=='__main__':unittest.main()
