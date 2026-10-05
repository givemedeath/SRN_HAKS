import unittest
from pathlib import Path
from test_impact import catalog,select

class ImpactTests(unittest.TestCase):
    def test_known_import_literal_and_config_edges(self):
        data=catalog()
        for changed,expected in [('tools/phenotypes/rig_pose_audit.py','tools/phenotypes/test_pose_preview_bridge.py'),
            ('tools/shared-tools.lock.json','tools/test_shared_tools.py'),
            ('tools/phenotypes/height_targets.json','tools/phenotypes/test_generate_purpose_built_part_cli.py')]:
            result=select([changed],data);self.assertIn(expected,result['tests'])
        self.assertIn('tools/phenotypes/bootstrap_shared_blender_addons.py',data['dependencies']['tools/phenotypes/launch_shared_tool.py'])
    def test_unknown_changes_and_unresolved_paths_use_full_suite(self):
        data=catalog();self.assertTrue(select(['new/config.json'],data)['fullSuite'])
        fixture={'dependencies':{'helper.py':['dynamic.py'],'test_helper.py':['helper.py']},'unresolved':['helper.py'],'tests':['test_helper.py']}
        self.assertTrue(select(['dynamic.py'],fixture)['fullSuite'])
    def test_small_known_change_selects_subset(self):
        data=catalog();result=select(['tools/phenotypes/pose_preview_render_settings.py'],data)
        self.assertFalse(result['fullSuite']);self.assertLess(len(result['tests']),len(data['tests']))

if __name__=='__main__':unittest.main()
