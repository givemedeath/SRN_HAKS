"""Verify stock-armor fallback does not bypass the Human rig/height boundary."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import build_derived_elf_fixture
import build_derived_orc_fixture
from build_test_module import stock_equipment_models


class StockEquipmentFallbackTests(unittest.TestCase):
    def test_human_identity_and_no_private_comparator_armor(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);converted=root/'human/converted';converted.mkdir(parents=True)
            conversion={'modelPrefix':'pmh0','rigMode':'stock-exact-game-fallback',
                'stockOtherPartsFromGame':True,'height':1.9339157,'stockReferenceHeight':1.9339157}
            def save(data):(converted/'conversion.json').write_text(json.dumps(data))
            save(conversion)
            records=[{'slug':'human'},{'slug':'private','fixtureControl':True}]
            item={'ArmorPart_Torso':{'value':16},'ArmorPart_Pelvis':{'value':1},
                'ArmorPart_LThigh':{'value':4},'ArmorPart_Robe':{'value':0}}
            self.assertEqual(stock_equipment_models(records,root,item),['pmh0_chest016.mdl','pmh0_legl004.mdl'])
            for key,value in [('modelPrefix','pmg0'),('rigMode','custom'),('rigMode','retargeted'),('stockOtherPartsFromGame',False),('height',2.1),('height',float('nan'))]:
                save({**conversion,key:value})
                with self.assertRaises(RuntimeError):stock_equipment_models(records,root,item)
            save(conversion)
            with self.assertRaises(RuntimeError):stock_equipment_models([records[1]],root,item)
            with self.assertRaises(RuntimeError):stock_equipment_models(records,root,{**item,'ArmorPart_Robe':{'value':1}})

    def test_elf_and_orc_staging_allows_stock_family_equipment(self):
        item = {'ArmorPart_Torso': {'value': 16}, 'ArmorPart_LThigh': {'value': 4},
                'ArmorPart_Robe': {'value': 0}}
        for race, prefix, builder in [('elf', 'pme0', build_derived_elf_fixture),
                                      ('orc', 'pmo0', build_derived_orc_fixture)]:
            with self.subTest(race=race), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                source = root / 'candidate/converted'
                (source / 'ascii').mkdir(parents=True)
                (source / 'resources').mkdir()
                name = prefix + '_chest001.mdl'
                (source / 'ascii' / name).write_text('synthetic ascii')
                (source / 'resources' / name).write_bytes(b'synthetic compiled model')
                (source / 'native-compile.json').write_text('{}')
                stage = root / 'stage'
                with patch.object(builder, 'CANDIDATE_CONVERTED', source):
                    builder.stage_candidate(stage)
                records = json.loads((stage / 'manifest.json').read_text())['combinations']
                records.append({'slug': 'private_control', 'fixtureControl': True})
                self.assertEqual(stock_equipment_models(records, stage, item),
                                 [prefix + '_chest016.mdl', prefix + '_legl004.mdl'])


if __name__=='__main__':unittest.main()
