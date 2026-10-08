"""Stock fallback copies retain exact native/ASCII ownership without rig export."""
import json
from pathlib import Path
import tempfile
import unittest
from build_target_diagnostic import build,convert_part
from test_human_female_stock_exact import stock_fixture
from test_target_part_pipeline import target_fixture
import target_contract as contract


def fixture(root):
    target_path,target=stock_fixture(root)
    stock=root/'stock';(stock/'raw').mkdir(parents=True);(stock/'ascii').mkdir()
    models={'pfh0':(root/'pfh0.mdl').read_text(),'a_fa':'newmodel a_fa\nsetsupermodel a_fa NULL\nbeginmodelgeom a_fa\nnode dummy a_fa\n parent NULL\nendnode\nendmodelgeom a_fa\n'}
    for part in contract.PART_JOINTS:
        name='pfh0_'+part+'001'
        models[name]='newmodel '+name+'\nsetsupermodel '+name+' NULL\nbeginmodelgeom '+name+'\nnode dummy '+name+'\n parent NULL\nendnode\nnode trimesh skin\n parent '+name+'\n bitmap pfh0_neck001\n verts 3\n 0 0 0\n .1 0 .1\n 0 .1 .2\n faces 1\n 0 1 2 1 0 1 2 1\nendnode\nendmodelgeom '+name+'\n'
    proof_path=Path(target['rig']['stockReferenceReceipt']['path']);proof=json.loads(proof_path.read_text());proof['chain']=['pfh0','a_fa'];rows=[]
    for name,text in models.items():
        ascii_path=stock/'ascii'/(name+'.mdl');raw=stock/'raw'/(name+'.mdl');ascii_path.write_text(text);raw.write_bytes(b'original native bytes: '+name.encode())
        rows.append({'name':name+'.mdl','sha256':contract.sha(raw),'asciiSha256':contract.sha(ascii_path)})
        proof['frozenInputs'][str(raw)]=contract.sha(raw);proof['frozenInputs'][str(ascii_path)]=contract.sha(ascii_path)
    material=stock/'raw/pfh0_neck001.plt';material.write_bytes(b'original palette bytes');rows.append({'name':material.name,'sha256':contract.sha(material)});proof['frozenInputs'][str(material)]=contract.sha(material)
    proof['rootAscii']={'path':str(stock/'ascii/pfh0.mdl'),'sha256':contract.sha(stock/'ascii/pfh0.mdl')}
    (stock/'baseline.json').write_text(json.dumps({'resources':rows}));proof_path.write_text(json.dumps(proof));target['rig']['stockReferenceReceipt']['sha256']=contract.sha(proof_path);target_path.write_text(json.dumps(target))
    return target_path,target,stock


class StockDiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name).resolve()
        self.path,self.target,self.stock=fixture(self.root)

    def test_sixteen_fallbacks_and_rig_chain_are_byte_exact_and_identified(self):
        output=self.root/'diagnostic';receipt=build(self.path,None,self.stock,output,'working')
        self.assertEqual(len(receipt['parts']),16);self.assertFalse(receipt['rigExported']);self.assertFalse(receipt['clientAccepted'])
        self.assertTrue(all(row['stockFallback'] and row['byteExactStockSource'] for row in receipt['parts']))
        for name,pin in receipt['resources'].items():
            self.assertEqual((output/'ascii'/name).read_bytes(),(self.stock/'ascii'/name).read_bytes());self.assertEqual(contract.sha(output/'ascii'/name),pin)
        for name,pin in receipt['rawResourceHashes'].items():
            self.assertEqual((output/'raw'/name).read_bytes(),(self.stock/'raw'/name).read_bytes());self.assertEqual(contract.sha(output/'raw'/name),pin)
        self.assertEqual(set(receipt['stockMaterialResourceHashes']),{'pfh0_neck001.plt'})

    def test_private_rig_and_stale_raw_inputs_are_rejected_before_output(self):
        output=self.root/'diagnostic'
        with self.assertRaisesRegex(ValueError,'without a private'):build(self.path,self.root/'private',self.stock,output,'working')
        self.assertFalse(output.exists())
        (self.stock/'raw/pfh0_chest001.mdl').write_bytes(b'changed')
        with self.assertRaises(ValueError):build(self.path,None,self.stock,output,'working')
        self.assertFalse(output.exists())

    def test_legacy_retargeted_target_still_requires_its_rig_export(self):
        path=self.root/'legacy.json';path.write_text(json.dumps(target_fixture()))
        with self.assertRaisesRegex(ValueError,'requires its private'):build(path,None,self.stock,self.root/'legacy','working')

    def test_legacy_conversion_preserves_bitmap_and_applies_one_uniform_scale(self):
        source=(self.stock/'ascii/pfh0_chest001.mdl').read_text()
        result=convert_part(source,'pfh0_chest001','pmg0_chest001',2)
        self.assertIn('newmodel pmg0_chest001',result);self.assertIn('bitmap pfh0_neck001',result)
        self.assertIn('0.2',result)
        with self.assertRaisesRegex(ValueError,'Animated stock'):convert_part(source+'newanim test\n','pfh0_chest001','pmg0_chest001',2)


if __name__=='__main__':unittest.main()
