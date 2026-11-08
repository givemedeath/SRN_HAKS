import numpy as np
from .firearm_grip import GripDeparture
from pathlib import Path
from PIL import Image
from tools.headkit.common import read,write,pin
from .test_itemkit import Fixture
from . import contracts,native
from .grip import two_hand_uniform
from .firearm_native import placeholder_geometry


class GreatswordTests(Fixture):
    def qualified(self):
        self.native();self.profile['family']='greatsword';n=self.profile['native']
        layer=self.path.parent/'stack/base';table=layer/'baseitems.2da'
        table.write_text('2DA V2.0\n\nLabel ItemClass ModelType InvSlotWidth InvSlotHeight\n13 greatsword WSwGs 2 2 5\n')
        names=['baseitems.2da'];n.update(baseItem=13,itemClass='wswgs',baseitemsSha256=pin(table)['sha256'])
        n['donors']={};n['iconDonors']={};n['iconDimensions']={};n['iconCanvasDimensions']={}
        for part in contracts.PARTS:
            name='wswgs_'+part+'_011.mdl';(layer/name).write_bytes(b'installed Greatsword');names.append(name);n['donors'][part]=name
            icon='i'+name[:-4]+'.tga';Image.new('RGBA',(64,256)).save(layer/icon);names.append(icon);n['iconDonors'][part]=icon
            n['iconDimensions'][part]=[64,160];n['iconCanvasDimensions'][part]=[64,256]
        stack=self.path.parent/'stack/stack.json';write(stack,{'complete':True,'order':'low-to-high','layers':[{'resources':[
            {'resource':name,'file':{'path':'base/'+name,'sha256':pin(layer/name)['sha256']}} for name in names]}]})
        n['stack']['sha256']=pin(stack)['sha256'];self.save_profile()
        return contracts.native_contract(self.profile_path,self.profile)

    def test_qualified_greatsword_and_inventory_contract(self):
        _,resources=self.qualified();self.assertIn('iwswgs_m_011.tga',resources)
        self.assertEqual(contracts.family(self.profile_path)['native']['baseItem'],13)
        self.profile['native']['iconDimensions']['m']=[64,256]
        with self.assertRaisesRegex(ValueError,'logical icons'):contracts.native_contract(self.profile_path,self.profile)

    def test_native_icon_padding_preserves_every_logical_pixel(self):
        self.qualified();g=placeholder_geometry();arrays={};icons={}
        for part in contracts.PARTS:
            file=self.root/(part+'.npz');np.savez(file,**g,shadowVertices=g['positions'].reshape(-1,3),shadowFaces=np.arange(12).reshape(-1,3));arrays[part]=pin(file)
            file=self.root/(part+'.png');image=Image.new('RGBA',(64,160),(17,29,93,255));image.putpixel((5,159),(2,3,4,128));image.save(file);icons[part]=pin(file)
        texture=self.root/'diffuse.png';Image.new('RGB',(1024,1024)).save(texture)
        out=self.root/'native';result=native.prepare(self.profile_path,self.profile,arrays,texture,icons,out)
        for part,name in result['allocation']['icons'].items():
            with Image.open(out/'resources'/(name+'.tga')) as padded,Image.open(icons[part]['path']) as source:
                self.assertEqual(padded.size,(64,256));self.assertTrue(np.array_equal(np.asarray(padded)[:160],np.asarray(source)))
                self.assertFalse(np.asarray(padded)[160:].any())

    def test_two_hand_melee_thickness_does_not_shorten_the_hilt(self):
        standard=read(Path(__file__).resolve().parents[2]/'docs/items/weapon-grip-standard-v1.json');a=np.arange(32)*2*np.pi/32
        ring=np.c_[np.cos(a)*standard['targetMidpointSection']['depth']/4,np.zeros(32),np.sin(a)*.01]
        p=np.concatenate([ring+[0,-.07,0],ring+[0,.07,0]])
        f=np.array([(i,(i+1)%32,(i+1)%32+32) for i in range(32)]+[(i,(i+1)%32+32,i+32) for i in range(32)])
        m=np.diag([2.,2.,2.,1.]);m[1,3]=-.09
        with self.assertRaises(GripDeparture) as caught:two_hand_uniform(p,f,m,[[0,-.07,0],[0,.07,0]],[0,-.09,0],standard)
        review={'decision':'approved','measurementDigest':caught.exception.report['measurementDigest'],'notes':'Reviewed on both bodies'}
        actual,r=two_hand_uniform(p,f,m,[[0,-.07,0],[0,.07,0]],[0,-.09,0],standard,review)
        self.assertTrue(np.array_equal(actual,m));self.assertAlmostEqual(r['usableLength'],.28)
        self.assertTrue(r['bothBodyVisualReviewRequired']);self.assertGreater(r['midpointRelativeDifferences']['usableLength'],.5)
        bad=m.copy();bad[0,0]=1.7
        with self.assertRaisesRegex(ValueError,'uniformly'):two_hand_uniform(p,f,bad,[[0,-.07,0],[0,.07,0]],[0,-.09,0],standard)
        bad=m.copy();bad[:3,:3]*=.8
        with self.assertRaisesRegex(ValueError,'thickness'):two_hand_uniform(p,f,bad,[[0,-.07,0],[0,.07,0]],[0,-.09,0],standard)
