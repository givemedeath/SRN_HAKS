from unittest.mock import patch, Mock
from PIL import Image
from tools.headkit.common import write,pin
from .test_itemkit import Fixture
from . import contracts
from .parts import active_parts,active_icon_dimensions,assembly_budget,WHOLE_NATIVE_FAMILIES
from .runner import Runner


class RiggedContractTests(Fixture):
    def test_rigid_runner_rejects_rigged_export_before_dropping_weights(self):
        runner=Runner.__new__(Runner);runner.worker=Mock()
        for family in ('bow','whip','crossbow'):
            runner.family={'family':family}
            with self.subTest(family=family), self.assertRaisesRegex(ValueError,'reviewed skinned_native adapter'):
                runner._execute('export',self.root/'unwritten',parent_results={})
        runner.worker.assert_not_called()
        runner.family={'family':'shield'}
        with self.assertRaisesRegex(ValueError,'reviewed shield_native adapter'):
            runner._execute('export',self.root/'unwritten',parent_results={})
        runner.worker.assert_not_called()
        self.assertFalse((self.root/'unwritten').exists())

    def qualified(self,family):
        self.native();self.profile['family']=family;n=self.profile['native'];bow=family=='bow'
        base,cls,size,wield=(8,'wbwln',[64,128],'5') if bow else (111,'wwhip',[64,64],'****')
        layer=self.path.parent/'stack/base';table=layer/'baseitems.2da'
        table.write_text(f'2DA V2.0\n\nLabel ItemClass ModelType InvSlotWidth InvSlotHeight WeaponWield AmmunitionType\n{base} {family} {cls} 2 {size[0]//32} {size[1]//32} {wield} '+('1' if bow else '****')+'\n')
        names=['baseitems.2da'];n.update(baseItem=base,itemClass=cls,baseitemsSha256=pin(table)['sha256'],iconDonors={},iconDimensions={})
        for part in contracts.PARTS:
            name=f'{cls}_{part}_011.mdl';(layer/name).write_bytes(b'installed carrier');names.append(name);n['donors'][part]=name
            icon='i'+name[:-4]+'.tga';Image.new('RGBA',tuple(size)).save(layer/icon);names.append(icon);n['iconDonors'][part]=icon;n['iconDimensions'][part]=size
        stack=self.path.parent/'stack/stack.json';write(stack,{'complete':True,'order':'low-to-high','layers':[{'resources':[{'resource':name,'file':{'path':'base/'+name,'sha256':pin(layer/name)['sha256']}} for name in names]}]});n['stack']['sha256']=pin(stack)['sha256']
        self.profile['budgets']={'visible':10000,'shadow':500,'parts':{'m':{'visible':9992,'shadow':500},'b':{'visible':4,'shadow':0},'t':{'visible':4,'shadow':0}}};self.profile['allowedAssemblies']=[{'m':self.data['id'],'b':'hidden-placeholder','t':'hidden-placeholder'}];self.save_profile()

    def test_native_facts_and_budgets_without_firearm_fit(self):
        for family in ('bow','whip'):
            with self.subTest(family=family):
                if family=='whip':
                    # Each fixture has one installed-stack directory.
                    self.tearDown();self.setUp()
                self.qualified(family)
                with patch.object(contracts,'rigged_motion_inputs'):
                    data=contracts.family(self.profile_path);contracts.manifest(self.path)
                self.assertEqual(active_parts(data),('m',));self.assertNotIn(family,WHOLE_NATIVE_FAMILIES)
                self.assertEqual(active_icon_dimensions(data),{'m':data['native']['iconDimensions']['m']})
                self.assertEqual(set(data['native']['iconDimensions']),{'b','m','t'})
                incomplete={**data,'native':{**data['native'],'iconDimensions':{'b':[64,64],'t':[64,64]}}}
                with self.assertRaises(ValueError):active_icon_dimensions(incomplete)
                self.assertEqual(assembly_budget(data,{'m':9988},'visible')['assembly'],9996)
                with self.assertRaises(ValueError):assembly_budget(data,{'m':9995},'visible')
                self.profile['native']['baseItem']=22
                with self.assertRaises(ValueError):contracts.native_contract(self.profile_path,self.profile)

    def test_cross_part_donor_rejected(self):
        self.qualified('bow');self.profile['native']['donors']['m']='wbwln_t_011.mdl'
        with self.assertRaisesRegex(ValueError,'rigged donor part'):contracts.native_contract(self.profile_path,self.profile)

    def test_reviewed_motion_cannot_be_omitted(self):
        self.qualified('whip')
        with self.assertRaisesRegex(ValueError,'Reviewed rigged motion required'):contracts.family(self.profile_path)
