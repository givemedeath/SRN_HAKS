from PIL import Image
from tools.headkit.common import write,pin
from .test_itemkit import Fixture
from . import contracts


class ThrownTests(Fixture):
    def qualified(self):
        self.native();self.profile['family']='throwing-knife';n=self.profile['native']
        layer=self.path.parent/'stack/base';table=layer/'baseitems.2da'
        table.write_text('2DA V2.0\n\nLabel ItemClass ModelType InvSlotWidth InvSlotHeight WeaponWield\n63 throwingknife WThAx 2 1 2 11\n')
        names=['baseitems.2da'];n.update(baseItem=63,itemClass='wthax',baseitemsSha256=pin(table)['sha256'])
        n['donors']={};n['iconDonors']={};n['iconDimensions']={}
        for part in contracts.PARTS:
            name='wthax_'+part+'_011.mdl';(layer/name).write_bytes(b'installed thrown carrier');names.append(name);n['donors'][part]=name
            icon='i'+name[:-4]+'.tga';Image.new('RGBA',(32,64)).save(layer/icon);names.append(icon);n['iconDonors'][part]=icon;n['iconDimensions'][part]=[32,64]
        stack=self.path.parent/'stack/stack.json';write(stack,{'complete':True,'order':'low-to-high','layers':[{'resources':[
            {'resource':name,'file':{'path':'base/'+name,'sha256':pin(layer/name)['sha256']}} for name in names]}]})
        n['stack']['sha256']=pin(stack)['sha256'];self.save_profile()

    def test_actual_thrown_route_and_footprint(self):
        self.qualified();data=contracts.family(self.profile_path)
        self.assertEqual(data['native']['baseItem'],63)
        self.assertEqual(data['native']['iconDimensions'],dict.fromkeys(contracts.PARTS,[32,64]))
        self.profile['native']['baseItem']=22
        with self.assertRaises(ValueError):contracts.native_contract(self.profile_path,self.profile)

    def test_cross_part_donor_rejected(self):
        self.qualified();self.profile['native']['donors']['t']='wthax_b_011.mdl'
        with self.assertRaisesRegex(ValueError,'thrown donor part'):contracts.native_contract(self.profile_path,self.profile)

    def test_cross_part_icon_rejected(self):
        self.qualified();self.profile['native']['iconDonors']['m']='iwthax_b_011.tga'
        with self.assertRaisesRegex(ValueError,'thrown icon part'):contracts.native_contract(self.profile_path,self.profile)
