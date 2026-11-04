import copy
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
import numpy as np
from PIL import Image
from tools.headkit.common import pin,write
from tools.itemkit import contracts,shield_native
from tools.itemkit.parts import active_parts,assembly_budget,grip_render_part
from tools.itemkit.firearm_native import placeholder_geometry


class ShieldTests(unittest.TestCase):
    def test_grip_closeup_defaults_to_the_active_native_part(self):
        profile={'family':'shield','nativePackaging':'enabled','native':{'kind':'shield-whole-v1'}}
        self.assertEqual(grip_render_part(profile),'whole')
        profile['native']['gripPart']='m'
        with self.assertRaisesRegex(ValueError,'active part'):grip_render_part(profile)
        self.assertEqual(grip_render_part({'family':'shortsword','native':{}}),'m')
        self.assertEqual(grip_render_part({'family':'bow','native':{}}),'m')

    def geometry(self):
        one=placeholder_geometry();two=placeholder_geometry(center=(.01,0,0))
        return {k:np.concatenate([one[k],two[k]]) for k in one} | {
            'paneFaces':np.array([True]*4+[False]*4),
            'shadowVertices':one['positions'].reshape(-1,3),'shadowFaces':np.arange(12).reshape(-1,3)}

    def test_preserves_exact_attributes_and_separate_alpha_nodes(self):
        g=self.geometry();before={k:v.copy() for k,v in g.items()}
        impacts={n:{'position':[0,0,0],'orientation':[0,0,0,1]} for n in ('imp_shield_1','imp_shield_2')}
        text=shield_native.model_text('ashlw_014','sr_shield',g,impacts)
        self.assertEqual(text.count('node trimesh '),3)
        self.assertEqual(text.count('  alpha '),1)
        self.assertEqual(text.count('bitmap sr_shield'),2)
        self.assertIn('node dummy imp_shield_2',text)
        for k in g:self.assertTrue(np.array_equal(g[k],before[k]))
        with self.assertRaisesRegex(ValueError,'impact attachments'):
            shield_native.model_text('ashlw_014','sr_shield',g,{})

    def test_raw_appearance_byte_and_combined_namespace(self):
        a=shield_native.allocation({},14,'sr_shield','sr_shieldu')
        b=shield_native.blueprint(a,{'blueprint':'sr_shieldu','displayName':'Riot Shield'})
        self.assertEqual([b['ModelPart'+str(i)]['value'] for i in (1,2,3)],[14,0,0])
        self.assertEqual(b['BaseItem']['value'],56)
        for resource in ('AShLw_014.MDL','iashlw_014.dds','sr_shield.txi','sr_shieldu.uti'):
            with self.assertRaisesRegex(ValueError,'collision'):
                shield_native.allocation({resource:None},14,'sr_shield','sr_shieldu')

    def test_unsafe_geometry_and_missing_material_rejected(self):
        for key,value in [('paneFaces',np.ones(8,bool)),('uv',np.full((8,3,2),1.1))]:
            g=self.geometry();g[key]=value
            with self.assertRaises(ValueError):shield_native.validate_geometry(g)
        g=self.geometry();g['shadowFaces']=g['shadowFaces'][:-1]
        with self.assertRaisesRegex(ValueError,'shadow'):shield_native.validate_geometry(g)

    def test_qualified_single_model_contract_and_legacy_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);table=root/'baseitems.2da'
            table.write_text('2DA V2.0\n\nItemClass ModelType WeaponWield InvSlotWidth InvSlotHeight\n56 AShLw 0 7 2 3\n')
            donor=root/'ashlw_011.mdl';donor.write_bytes(b'installed Shield bytes')
            icon=root/'iashlw_011.tga';Image.new('RGBA',(64,128)).save(icon)
            stack=root/'stack.json';write(stack,{'complete':True,'order':'low-to-high','layers':[{'resources':[
                {'resource':p.name,'file':{'path':p.name,'sha256':pin(p)['sha256']}} for p in (table,donor,icon)]}]})
            native={'kind':'shield-whole-v1','reviewed':True,'stack':{'path':stack.name,'sha256':pin(stack)['sha256']},
                    'baseItem':56,'baseitemsSha256':pin(table)['sha256'],'itemClass':'ashlw','modelType':0,
                    'donors':{'whole':donor.name,'icon':icon.name},'iconDimensions':{'whole':[64,96]},
                    'frame':np.eye(3).tolist(),'gripOrigin':[0,0,0],'gripLength':.18}
            profile={'schemaVersion':1,'kind':'item-family','family':'shield','nativePackaging':'enabled',
                     'materialRoute':'diffuse','bakeSize':4096,'runtimeTextureSize':1024,'native':native,
                     'resources':{'texturePrefix':'sr_shield','blueprint':'sr_shieldu','displayName':'Riot Shield','hak':'sr_shieldh','module':'sr_shieldm'},
                     'budgets':{'visible':10000,'shadow':500,'parts':{'whole':{'visible':10000,'shadow':500}}},
                     'allowedAssemblies':[{'whole':'riot-shield'}]}
            path=root/'family.json';write(path,profile)
            self.assertEqual(contracts.family(path),profile)
            self.assertEqual(active_parts(profile),('whole',))
            self.assertEqual(assembly_budget(profile,{'whole':4218},'visible')['assembly'],4218)
            with self.assertRaisesRegex(ValueError,'allocator'):contracts.model_names(profile,1)
            geometry=root/'geometry.npz';np.savez(geometry,**self.geometry())
            texture=root/'diffuse.png';Image.new('RGB',(1024,1024)).save(texture)
            impacts={n:{'position':[0,0,0],'orientation':[0,0,0,1]} for n in ('imp_shield_1','imp_shield_2')}
            prepared=root/'prepared';shield_native.prepare(path,geometry,texture,icon,impacts,[],prepared)
            with patch('tools.itemkit.native.offline_compiler_inputs',return_value=[]), \
                 patch('tools.itemkit.native.compile_offline',side_effect=ValueError('compiler rejected')) as compile_call, \
                 patch('subprocess.run') as process:
                with self.assertRaisesRegex(ValueError,'compiler rejected'):
                    shield_native.compile_package(prepared,{},root/'compiled')
                compile_call.assert_called_once();process.assert_not_called()
            rendered=root/'icon-whole.png';Image.new('RGBA',(64,96),(9,9,9,255)).save(rendered)
            shield_native.prepare(path,geometry,texture,rendered,impacts,[],root/'rendered')
            with Image.open(root/'rendered/resources/iashlw_014.tga') as image:
                self.assertEqual(image.size,(64,128));self.assertEqual(image.getpixel((0,95)),(9,9,9,255));self.assertEqual(image.getpixel((0,96))[3],0)
            with patch('tools.itemkit.contracts.source_version',return_value='changed'):
                with self.assertRaisesRegex(ValueError,'Stale Shield'):shield_native.compile_package(prepared,{},root/'stale')
            bad=copy.deepcopy(profile);bad['native']['iconDimensions']={'whole':[64,128]};write(path,bad)
            with self.assertRaisesRegex(ValueError,'dimensions'):contracts.family(path)
            bad=copy.deepcopy(profile);del bad['native']['kind'];write(path,bad)
            with self.assertRaises(ValueError):contracts.family(path)


if __name__=='__main__':unittest.main()
