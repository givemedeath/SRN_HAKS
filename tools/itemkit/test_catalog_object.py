"""Generation-only objects must not acquire native weapon authority."""
import unittest
import os
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from tools.headkit.common import pin, write, verification_pass

from tools.itemkit.test_itemkit import Fixture
from tools.itemkit import contracts
from tools.itemkit.parts import active_parts, assembly_budget


class CatalogObjectTests(Fixture):
    def setUp(self):
        super().setUp()
        self.profile.update(family='catalog-object', nativePackaging='blocked',
            sourceExport={'remeshResolution':768,'targetFaceCount':200000,'signMode':'udf'},
            budgets={'visible':5000,'shadow':500,'parts':{'whole':{'visible':5000,'shadow':500}}},
            allowedAssemblies=[{'whole':self.data['id']}])
        self.save_profile()

    def test_working_export_preserves_the_udf_donor_contract(self):
        from tools.itemkit.generation import export_settings
        original = dict(self.profile['sourceExport'])
        settings = export_settings(self.profile, 'export', True)
        self.assertEqual(settings, {'remeshResolution':768,'targetFaceCount':200000,'signMode':'solid','fill':40.0})
        self.assertEqual(self.profile['sourceExport'], original)
        self.assertEqual(export_settings(self.profile, 'export'), original)
        settings['signMode'] = 'invalid'
        self.assertEqual(export_settings(self.profile, 'export'), original)
        self.assertIsNone(export_settings(self.profile, 'appearance'))

    def test_working_export_rejects_neural_stages_before_runtime_work(self):
        from tools.itemkit.generation import request_stage
        for stage in ('calibrate', 'geometry', 'appearance'):
            with self.subTest(stage=stage), patch('tools.itemkit.generation.manifest') as load:
                with self.assertRaisesRegex(ValueError, 'export-only'):
                    request_stage(None,None,stage,None,runtime=None,comfy_runtime=None,working_shell=True)
                load.assert_not_called()

    def test_geometry_contract_uses_one_whole_object_and_keeps_caps(self):
        profile = contracts.family(self.profile_path)
        self.assertEqual(active_parts(profile), ('whole',))
        assembly_budget(profile, {'whole':5000}, 'visible')
        with self.assertRaises(ValueError): assembly_budget(profile, {'whole':5001}, 'visible')
        contracts.manifest(self.path)

    def test_native_authority_cannot_be_enabled_even_when_native_validation_is_skipped(self):
        self.profile['nativePackaging'] = 'enabled'; self.save_profile()
        with self.assertRaises(ValueError): contracts.family(self.profile_path, validate_native=False)

    def test_direct_native_contract_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'no qualified native'):
            contracts.native_contract(self.profile_path, self.profile)

    def test_native_part_layout_cannot_leak_into_generic_geometry_route(self):
        self.profile['allowedAssemblies'] = [dict.fromkeys(('b','m','t'), self.data['id'])]
        self.save_profile()
        with self.assertRaises(ValueError): contracts.family(self.profile_path)

    def test_calibration_analyzes_reviewed_alpha_instead_of_black_comfy_input(self):
        from tools.itemkit.generation import calibration_background_decision
        image = self.path.parent / 'calibration.png'
        Image.new('RGBA', (512,512), (80,80,80,0)).save(image)
        self.data['inputs']['calibrationReference'] = {'path':image.name,'sha256':pin(image)['sha256']}
        with patch('tools.itemkit.generation.analyze_reference',return_value={'route':'preserve-alpha'}) as analyze:
            self.assertEqual(calibration_background_decision(self.path,self.data), {'route':'preserve-alpha'})
            self.assertEqual(Path(analyze.call_args.args[0]).resolve(),image.resolve())
        self.assertIn('calibrationReference',contracts.stage_roles('calibrate'))
        self.assertNotIn('calibrationReference',contracts.stage_roles('geometry'))

    def test_changed_input_approval_is_rejected_across_fresh_geometry_passes(self):
        review = self.path.parent/'review.json'
        review.write_text('{"approval":"approved"}')
        self.data['inputs']['referenceApproval'] = {'path':review.name,'sha256':pin(review)['sha256']}
        write(self.path,self.data)
        with verification_pass('catalog-review-before'):
            contracts.all_pins(self.path,roles=contracts.stage_roles('geometry'),native=False)
        old = review.stat()
        review.write_text('{"approval":"rejected"}')
        os.utime(review,ns=(old.st_atime_ns,old.st_mtime_ns))
        with verification_pass('catalog-review-after'):
            with self.assertRaises(ValueError):
                contracts.all_pins(self.path,roles=contracts.stage_roles('geometry'),native=False)

    def test_only_calibration_stages_the_unassociated_pair(self):
        from tools.itemkit.generation import generation_manifest
        from tools.headkit.common import read
        original = dict(self.data['inputs'])
        for role in ('calibrationReference','calibrationDetail'):
            path = self.path.parent / (role+'.png')
            Image.new('RGBA',(512,512),(180,90,45,128)).save(path)
            self.data['inputs'][role] = {'path':path.name,'sha256':pin(path)['sha256']}
        write(self.path,self.data)
        calibrated = generation_manifest(self.path,roles=contracts.stage_roles('calibrate'))
        for role,source in (('geometry','calibrationReference'),('detail','calibrationDetail')):
            self.assertEqual(calibrated['inputs'][role],self.data['inputs'][source])
        self.assertEqual(calibrated['inputs']['mask'],self.data['inputs']['calibrationReference'])
        generated = generation_manifest(self.path,roles=contracts.stage_roles('geometry'))
        self.assertEqual(generated['inputs']['geometry'],original.get('geometry',original['reference']))
        self.assertEqual(generated['inputs']['detail'],original.get('detail',original['reference']))
        self.assertEqual(read(self.path),self.data)

    def test_calibration_rejects_a_missing_unassociated_detail(self):
        from tools.itemkit.generation import generation_manifest
        self.data['inputs']['calibrationReference'] = self.data['inputs']['reference']
        write(self.path,self.data)
        with self.assertRaisesRegex(ValueError,'both unassociated'):
            generation_manifest(self.path,roles=contracts.stage_roles('calibrate'))


if __name__ == '__main__': unittest.main()
