"""Installed female helmet sizing must never inherit male 1.05."""
import json
from pathlib import Path
import tempfile
import unittest
from measure_held_equipment import helmet_source_scale
from pipeline import digest


class HeldSizingTests(unittest.TestCase):
    def test_female_multiplier_comes_from_pinned_installed_row(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'raw').mkdir();appearance=root/'raw/appearance.2da'
            appearance.write_text('2DA V2.0\n\nLABEL HELMET_SCALE_M HELMET_SCALE_F\n6 Human 1.05 0.85\n')
            baseline=root/'baseline.json';baseline.write_text(json.dumps({'resources':[{'name':'appearance.2da','sha256':digest(appearance)}]}))
            female={'identity':{'gender':'female'}};inventory={'sourcePrefix':'pfh0'}
            value,proof=helmet_source_scale(female,inventory,baseline)
            self.assertEqual(value,.85);self.assertEqual(proof['column'],'helmet_scale_f')
            with self.assertRaises(ValueError):helmet_source_scale(female,inventory)
            appearance.write_text(appearance.read_text().replace('0.85','1.05'))
            with self.assertRaises(ValueError):helmet_source_scale(female,inventory,baseline)

    def test_legacy_male_receipt_default_remains_supported(self):
        self.assertEqual(helmet_source_scale({'identity':{'gender':'male'}},{'sourcePrefix':'pmh0'}),(1.05,None))


if __name__ == '__main__':unittest.main()
