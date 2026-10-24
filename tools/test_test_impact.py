import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from test_impact import REPO,absent_packs,catalog,deleted_paths,dependents,import_root,load_config,packs,run_tests,select

def write(root,files):
    for name,text in files.items():
        p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text,encoding='utf-8')

class ImpactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # The live catalog is immutable for the class; building it once keeps every case independent of order.
        cls.data=catalog();cls.config=load_config()
    def test_known_import_literal_and_config_edges(self):
        for changed,expected in [('tools/phenotypes/rig_pose_audit.py','tools/phenotypes/test_pose_preview_bridge.py'),
            ('tools/phenotypes/native_compile.py','tools/phenotypes/test_shared_caller_dependencies.py'),
            ('tools/phenotypes/audit_pelvis_package.py','tools/phenotypes/test_shared_caller_dependencies.py'),
            ('tools/shared-tools.lock.json','tools/test_shared_tools.py'),
            ('tools/phenotypes/height_targets.json','tools/phenotypes/test_generate_purpose_built_part_cli.py')]:
            result=select([changed],self.data);self.assertIn(expected,result['tests'])
        self.assertIn('tools/phenotypes/bootstrap_shared_blender_addons.py',self.data['dependencies']['tools/phenotypes/launch_shared_tool.py'])
    def test_unknown_changes_and_unresolved_paths_use_full_suite(self):
        self.assertTrue(select(['new/config.json'],self.data)['fullSuite'])
        fixture={'dependencies':{'helper.py':['dynamic.py'],'test_helper.py':['helper.py']},'unresolved':['helper.py'],'tests':['test_helper.py']}
        self.assertTrue(select(['dynamic.py'],fixture)['fullSuite'])
    def test_small_known_change_selects_subset(self):
        result=select(['tools/phenotypes/pose_preview_render_settings.py'],self.data)
        self.assertFalse(result['fullSuite']);self.assertLess(len(result['tests']),len(self.data['tests']))
    def test_live_catalog_has_no_unresolved_edges_and_matches_committed_copy(self):
        self.assertEqual(self.data['unresolved'],[])
        committed=json.loads((REPO/'tools/test-impact.json').read_text(encoding='utf-8'))
        self.assertEqual(committed,self.data,'Run: python -B tools/test_impact.py --write-catalog tools/test-impact.json')

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
            data=catalog(root)
            self.assertEqual(dependents(['tools/first/core.py'],data)&set(data['tests']),
                {'tools/first/test_local.py','tools/first/test_context.py','tools/test_literal.py'})
            # Its tests span tools/first and root tools, so the change is a shared-helper (full) run.
            self.assertIn('Shared helper changed',select(['tools/first/core.py'],data)['reason'])
            self.assertNotIn('tools/first/build/core.py',data['dependencies'])
            self.assertEqual(data['unresolved'],[])

    def test_from_package_import_submodule_retains_transitive_edge(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name,text in {'tools/pkg/__init__':'','tools/pkg/engine/__init__':'',
                    'tools/pkg/engine/core':'VALUE=1','tools/pkg/test_core':'from .engine import core'}.items():
                p=root/(name+'.py');p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
            self.assertIn('tools/pkg/test_core.py',select(['tools/pkg/engine/core.py'],catalog(root))['tests'])

class NamespaceDependencyTests(unittest.TestCase):
    def test_repository_namespace_absolute_imports_are_dependencies(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name,text in {'tools/kit/__init__':'','tools/kit/engine':'VALUE=1',
                    'tools/kit/test_engine':'from tools.kit import engine\nfrom tools.kit.engine import VALUE'}.items():
                p=root/(name+'.py');p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
            data=catalog(root)
            self.assertIn('tools/kit/engine.py',data['dependencies']['tools/kit/test_engine.py'])
            self.assertIn('tools/kit/test_engine.py',select(['tools/kit/engine.py'],data)['tests'])


class PackageDiscoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.data=catalog()
    def test_toolkit_package_tests_are_catalogued_with_package_import_roots(self):
        package=[t for t in self.data['tests'] if t.startswith('tools/phenomorpher/phenomorpher/')]
        self.assertIn('tools/phenomorpher/phenomorpher/test_public_api.py',package)
        self.assertTrue(any('/engine/' in t for t in package))
        root,name=import_root(REPO/'tools/phenomorpher/phenomorpher/engine/test_morph_anatomy_v15c.py')
        self.assertEqual((root,name),(REPO/'tools/phenomorpher','phenomorpher.engine.test_morph_anatomy_v15c'))
        self.assertEqual(import_root(REPO/'tools/phenotypes/test_lean_pipeline.py'),(REPO/'tools/phenotypes','test_lean_pipeline'))
    def test_flat_imports_do_not_resolve_to_package_internal_copies(self):
        # heads/robes import the flat phenotypes retarget; the package copy is only importable as phenomorpher.engine.retarget.
        self.assertIn('tools/phenotypes/retarget.py',self.data['dependencies']['tools/robes/lbs.py'])
        self.assertNotIn('tools/phenomorpher/phenomorpher/engine/retarget.py',self.data['dependencies']['tools/robes/lbs.py'])

class PackageRunnerTests(unittest.TestCase):
    def test_package_relative_tests_run_qualified_from_their_import_root_and_failures_propagate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            write(root,{'tools/kit/pkg/__init__.py':'','tools/kit/pkg/core.py':'VALUE=1',
                'tools/kit/pkg/test_ok.py':'import unittest\nfrom .core import VALUE\nclass T(unittest.TestCase):\n    def test_v(self):self.assertEqual(VALUE,1)\n',
                'tools/kit/pkg/test_bad.py':'import unittest\nfrom .core import VALUE\nclass T(unittest.TestCase):\n    def test_v(self):self.assertEqual(VALUE,2)\n',
                'tools/flat/helper.py':'VALUE=3','tools/flat/test_flat.py':'import unittest\nfrom helper import VALUE\nclass T(unittest.TestCase):\n    def test_v(self):self.assertEqual(VALUE,3)\n'})
            self.assertEqual(set(catalog(root)['tests']),{'tools/kit/pkg/test_ok.py','tools/kit/pkg/test_bad.py','tools/flat/test_flat.py'})
            timings=root/'timings.json'
            self.assertEqual(run_tests(['tools/kit/pkg/test_ok.py','tools/flat/test_flat.py'],sys.executable,root,timings),0)
            rows=json.loads(timings.read_text(encoding='utf-8'))
            self.assertEqual({row['root'] for row in rows},{'tools/kit','tools/flat'})
            self.assertTrue(any('pkg.test_ok' in row['test'] for row in rows))
            self.assertNotEqual(run_tests(['tools/kit/pkg/test_ok.py','tools/kit/pkg/test_bad.py'],sys.executable,root),0)
    def test_missing_or_empty_test_modules_fail_instead_of_passing_silently(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);write(root,{'tools/flat/test_empty.py':'X=1\n'})
            self.assertNotEqual(run_tests(['tools/flat/test_empty.py'],sys.executable,root),0)
            self.assertNotEqual(run_tests(['tools/flat/test_missing.py'],sys.executable,root),0)

class SparseCheckoutTests(unittest.TestCase):
    PEEK='import unittest\nfrom pathlib import Path\nclass T(unittest.TestCase):\n    def test_v(self):self.assertFalse((Path(__file__).resolve().parents[2]/{!r}).is_file())\n'
    def test_touching_an_absent_pack_fails_the_run_even_when_the_test_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);write(root,{'tools/flat/test_peek.py':self.PEEK.format('srn_gone/x.mdl'),
                'tools/flat/test_other.py':self.PEEK.format('docs/x.md')})
            self.assertEqual(run_tests(['tools/flat/test_peek.py'],sys.executable,root,absent=[]),0)
            self.assertNotEqual(run_tests(['tools/flat/test_peek.py'],sys.executable,root,absent=[root/'srn_gone']),0)
            self.assertEqual(run_tests(['tools/flat/test_other.py'],sys.executable,root,absent=[root/'srn_gone']),0)
    def test_sparse_checkout_catalogs_committed_packs_and_reports_them_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);write(root,{'srn_kept/a.2da':'x','srn_gone/b.mdl':'x','srn_gone/notes.md':'x','tools/test_x.py':"PACK='srn_gone'"})
            git=lambda *a:subprocess.run(['git','-C',str(root),*a],check=True,capture_output=True)
            git('init','-q');git('add','.');git('-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-qm','fixture')
            full=catalog(root);self.assertEqual(absent_packs(root),[])
            # init --cone then set: Git before 2.35 reads `set --cone` as a pattern.
            git('sparse-checkout','init','--cone');git('sparse-checkout','set','tools','srn_kept')
            self.assertFalse((root/'srn_gone').exists());self.assertTrue((root/'srn_kept/a.2da').is_file())
            self.assertEqual(packs(root),['srn_gone','srn_kept']);self.assertEqual(absent_packs(root),[root/'srn_gone'])
            self.assertEqual(catalog(root),full);self.assertEqual(full['packReferences'],{'tools/test_x.py':['srn_gone']})
            # Sparse-omitted files are not deletions; a path missing from both disk and index is.
            self.assertEqual(deleted_paths(['srn_gone/notes.md','srn_gone/b.mdl','docs/gone.md','tools/test_x.py'],root),{'docs/gone.md'})

class SelectionPolicyTests(unittest.TestCase):
    fixture={'dependencies':{'tools/a/helper.py':[],'tools/a/test_helper.py':['tools/a/helper.py'],
        'tools/a/test_doc.py':['docs/read.md'],'tools/b/test_pack.py':[]},'unresolved':[],
        'packReferences':{'tools/b/test_pack.py':['srn_body']},
        'tests':['tools/a/test_doc.py','tools/a/test_helper.py','tools/b/test_pack.py']}
    def test_documentation_only_selection(self):
        readme=select(['README.md','docs/other.md'],self.fixture)
        self.assertFalse(readme['fullSuite']);self.assertEqual(readme['tests'],[]);self.assertIn('Documentation only',readme['reason'])
        self.assertEqual(select(['docs/read.md'],self.fixture)['tests'],['tools/a/test_doc.py'])
        mixed=select(['README.md','docs/read.md','tools/a/helper.py'],self.fixture)
        self.assertEqual(mixed['tests'],['tools/a/test_doc.py','tools/a/test_helper.py'])
    def test_deleted_documents_select_the_full_suite(self):
        # A refreshed head catalog no longer sees literals that read a deleted document.
        result=select(['docs/read-before.md'],self.fixture,deleted={'docs/read-before.md'})
        self.assertTrue(result['fullSuite']);self.assertIn('Deleted document',result['reason'])
        self.assertFalse(select(['docs/other.md'],self.fixture,deleted=set())['fullSuite'])
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);write(root,{'docs/kept.md':'x'})
            from test_impact import deleted_paths
            self.assertEqual(deleted_paths(['docs/kept.md','docs/gone.md'],root),{'docs/gone.md'})
    def test_pack_assets_select_only_tests_that_reference_the_pack(self):
        self.assertEqual(select(['srn_body/x.mdl'],self.fixture)['tests'],['tools/b/test_pack.py'])
        self.assertEqual(select(['srn_item/x.uti'],self.fixture)['tests'],[])
    def test_unknown_and_uncovered_changes_select_everything(self):
        for changed in (['hakbuilder.json'],['tools/a/unknown.ps1'],['README.md','other/thing.cfg'],[]):
            self.assertTrue(select(changed,self.fixture)['fullSuite'],changed)
        uncovered={**self.fixture,'dependencies':{**self.fixture['dependencies'],'tools/a/lonely.py':[]}}
        self.assertTrue(select(['tools/a/lonely.py'],uncovered)['fullSuite'])
    def test_helpers_or_configs_used_by_several_suite_folders_select_the_full_suite(self):
        shared={**self.fixture,'dependencies':{**self.fixture['dependencies'],
            'tools/a/common.py':[],'tools/a/test_common.py':['tools/a/common.py'],'tools/b/test_common.py':['tools/a/common.py'],
            'tools/a/test_config.py':['tools/a/config.json'],'tools/test_root.py':['tools/a/config.json']},
            'tests':sorted(self.fixture['tests']+['tools/a/test_common.py','tools/b/test_common.py','tools/a/test_config.py','tools/test_root.py'])}
        for path in ('tools/a/common.py','tools/a/config.json'):
            result=select([path],shared);self.assertTrue(result['fullSuite'],path);self.assertIn('Shared helper changed',result['reason'])
        # A helper confined to one suite folder stays focused.
        self.assertEqual(select(['tools/a/helper.py'],shared),{**select(['tools/a/helper.py'],self.fixture)})
        self.assertFalse(select(['tools/a/helper.py'],shared)['fullSuite'])
    def test_every_shared_infrastructure_file_selects_the_full_suite(self):
        config=load_config()
        for path in ('.github/workflows/ci.yml','.github/workflows/shared-tooling.yml','.github/actions/srn-tools/action.yml',
                'tools/shared_tools.py','tools/test_impact.py','tools/ci_scope.py','tools/ci_result.py','tools/ci-scope.json',
                'tools/ci-test-durations.json','tools/test-impact.json','tools/SrnTools.psm1','tools/SrnHaks.Common.psm1',
                'tools/toolchain.lock.json','tools/shared-tools.lock.json','tools/Bootstrap-Tools.ps1',
                'tools/phenotypes/requirements.txt','tools/phenotypes/launch_shared_tool.py'):
            result=select([path],self.fixture,config)
            self.assertTrue(result['fullSuite'],path);self.assertIn('Shared infrastructure',result['reason'])

if __name__=='__main__':unittest.main()
