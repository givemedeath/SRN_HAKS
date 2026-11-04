from PIL import Image
from tools.headkit.common import write,pin
from .test_itemkit import Fixture
from . import contracts


class StaffTests(Fixture):
    def qualified(self):
        self.native();self.profile['family']='staff';n=self.profile['native']
        layer=self.path.parent/'stack/base';table=layer/'baseitems.2da'
        table.write_text('2DA V2.0\n\nLabel ItemClass ModelType InvSlotWidth InvSlotHeight\n50 quarterstaff WDbQs 2 1 4\n')
        names=['baseitems.2da'];n.update(baseItem=50,itemClass='wdbqs',baseitemsSha256=pin(table)['sha256'])
        n['donors']={};n['iconDonors']={};n['iconDimensions']={}
        for part in contracts.PARTS:
            name='wdbqs_'+part+'_011.mdl';(layer/name).write_bytes(b'installed staff');names.append(name);n['donors'][part]=name
            icon='i'+name[:-4]+'.tga';Image.new('RGBA',(32,128)).save(layer/icon);names.append(icon);n['iconDonors'][part]=icon;n['iconDimensions'][part]=[32,128]
        stack=self.path.parent/'stack/stack.json';write(stack,{'complete':True,'order':'low-to-high','layers':[{'resources':[
            {'resource':name,'file':{'path':'base/'+name,'sha256':pin(layer/name)['sha256']}} for name in names]}]})
        n['stack']['sha256']=pin(stack)['sha256'];self.save_profile()

    def test_staff_uses_its_actual_native_route_and_footprint(self):
        self.qualified();data=contracts.family(self.profile_path)
        self.assertEqual(data['native']['baseItem'],50)
        self.assertEqual(data['native']['iconDimensions'],dict.fromkeys(contracts.PARTS,[32,128]))
        self.profile['native']['baseItem']=13
        with self.assertRaises(ValueError):contracts.native_contract(self.profile_path,self.profile)

    def test_wrong_part_cannot_enter_an_otherwise_valid_assembly(self):
        self.qualified();self.profile['native']['donors']['t']='wdbqs_b_011.mdl'
        with self.assertRaisesRegex(ValueError,'Staff donor part'):contracts.native_contract(self.profile_path,self.profile)

    def test_wrong_icon_assignment_is_rejected(self):
        self.qualified();self.profile['native']['iconDonors']['m']='iwdbqs_b_011.tga'
        with self.assertRaisesRegex(ValueError,'Staff icon part'):contracts.native_contract(self.profile_path,self.profile)
