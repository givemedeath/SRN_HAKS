import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image

from build_animation_reference_sheet import checked_config,REQUIRED
from stage_stock_part import sha


class ReferenceEvidenceTests(unittest.TestCase):
    def fixture(self,root):
        inventory=root/'effective-material-inventory.json';inventory.write_text('{}')
        capture=root/'capture.png';capture.write_bytes(b'pinned actual capture')
        receipt=root/'capture.json';receipt.write_text('{}')
        config=root/'sheet.json'
        record={'evidenceKind':'nwn-ee-client','effectiveBodyConverted':str(root),
                'packagePins':{str(inventory):sha(inventory)},
                'cases':[{'category':category,'caption':category,'fullBodyReviewed':True,
                          'image':str(capture),'imageSha256':sha(capture),
                          'receipt':str(receipt),'receiptSha256':sha(receipt)} for category in REQUIRED]}
        config.write_text(json.dumps(record));return config,record,capture

    def test_partial_package_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            config,_,_=self.fixture(Path(folder))
            with patch('build_animation_reference_sheet.validate_effective_body',return_value=({}, {}, {'completeBodySelected':False})):
                with self.assertRaisesRegex(RuntimeError,'fourteen'):checked_config(config)

    def test_changed_capture_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            config,_,capture=self.fixture(Path(folder));capture.write_bytes(b'different capture')
            with patch('build_animation_reference_sheet.validate_effective_body',return_value=({}, {}, {'completeBodySelected':True})):
                with self.assertRaisesRegex(RuntimeError,'changed'):checked_config(config)

    def test_missing_motion_category_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            config,record,_=self.fixture(Path(folder))
            record['cases']=[c for c in record['cases'] if c['category']!='run']
            config.write_text(json.dumps(record))
            with patch('build_animation_reference_sheet.validate_effective_body',return_value=({}, {}, {'completeBodySelected':True})):
                with self.assertRaisesRegex(RuntimeError,'categories'):checked_config(config)

    def test_capture_crop_cannot_extend_beyond_original(self):
        with tempfile.TemporaryDirectory() as folder:
            config,record,capture=self.fixture(Path(folder))
            Image.new('RGB',(20,30)).save(capture)
            for row in record['cases']:
                row['imageSha256']=sha(capture)
                row['captureCrop']=[0,0,21,30]
            config.write_text(json.dumps(record))
            with patch('build_animation_reference_sheet.validate_effective_body',return_value=({}, {}, {'completeBodySelected':True})):
                with self.assertRaisesRegex(RuntimeError,'inside'):checked_config(config)


if __name__=='__main__':unittest.main()
