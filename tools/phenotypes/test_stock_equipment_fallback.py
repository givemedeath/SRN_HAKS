"""Verify stock-armor fallback does not bypass the Human rig/height boundary."""
import json
from pathlib import Path
import tempfile
import unittest

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
            for key,value in [('modelPrefix','pmg0'),('rigMode','custom'),('stockOtherPartsFromGame',False),('height',2.1),('height',float('nan'))]:
                save({**conversion,key:value})
                with self.assertRaises(RuntimeError):stock_equipment_models(records,root,item)
            save(conversion)
            with self.assertRaises(RuntimeError):stock_equipment_models([records[1]],root,item)
            with self.assertRaises(RuntimeError):stock_equipment_models(records,root,{**item,'ArmorPart_Robe':{'value':1}})


if __name__=='__main__':unittest.main()
