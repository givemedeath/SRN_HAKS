import unittest
import tempfile
from pathlib import Path
from test_impact import catalog,select

class ImpactTests(unittest.TestCase):
    def test_known_import_literal_and_config_edges(self):
        data=catalog()
        for changed,expected in [('tools/phenotypes/rig_pose_audit.py','tools/phenotypes/test_pose_preview_bridge.py'),
            ('tools/phenotypes/native_compile.py','tools/phenotypes/test_shared_caller_dependencies.py'),
            ('tools/phenotypes/audit_pelvis_package.py','tools/phenotypes/test_shared_caller_dependencies.py'),
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

class PackageImpactTests(unittest.TestCase):
    def test_package_relative_and_qualified_literals_resolve_without_duplicate_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            files={'tools/first/__init__':'','tools/first/core':'VALUE=1',
                'tools/second/__init__':'','tools/second/core':'VALUE=2',
                'tools/first/test_local':'from .core import VALUE\nfrom . import core',
                'tools/test_literal':"SOURCE='tools/first/core.py'",
                'tools/first/test_context':"SOURCE='helpers/core.py'",
                'tools/first/build/core':'BROKEN GENERATED'}
            for name,text in files.items():
                p=root/(name+'.py');p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
            data=catalog(root);selected=select(['tools/first/core.py'],data)
            self.assertFalse(selected['fullSuite'])
            self.assertEqual(set(selected['tests']),{'tools/first/test_local.py','tools/first/test_context.py','tools/test_literal.py'})
            self.assertNotIn('tools/first/build/core.py',data['dependencies'])
            self.assertEqual(data['unresolved'],[])

    def test_from_package_import_submodule_retains_transitive_edge(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name,text in {'tools/pkg/__init__':'','tools/pkg/engine/__init__':'',
                    'tools/pkg/engine/core':'VALUE=1','tools/pkg/test_core':'from .engine import core'}.items():
                p=root/(name+'.py');p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
            self.assertIn('tools/pkg/test_core.py',select(['tools/pkg/engine/core.py'],catalog(root))['tests'])

if __name__=='__main__':unittest.main()
