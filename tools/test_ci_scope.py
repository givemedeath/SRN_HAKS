import json
import re
import unittest
from pathlib import Path
import ci_scope
from test_impact import REPO,catalog,load_config

CONFIG={'sharedInfrastructure':[r'^tools/shared_tools\.py$'],'itemImport':[r'^srn_item/'],'wheel':[r'^tools/kit/'],
    'groups':[{'name':'phenotypes','pattern':'^tools/phenotypes/','shards':2},{'name':'core','pattern':'^tools/','shards':1}],
    'operatingSystems':['ubuntu-latest','windows-latest']}
DATA={'dependencies':{'tools/phenotypes/a.py':[],'tools/phenotypes/test_a.py':['tools/phenotypes/a.py'],
    'tools/phenotypes/test_b.py':[],'tools/phenotypes/test_c.py':[],'tools/kit/test_k.py':[],'tools/test_root.py':[]},
    'unresolved':[],'packReferences':{},
    'tests':['tools/kit/test_k.py','tools/phenotypes/test_a.py','tools/phenotypes/test_b.py','tools/phenotypes/test_c.py','tools/test_root.py']}

def legs(plan):return {(r['os'],r['group']):r['tests'] for r in plan['helperMatrix']}

class FallbackTests(unittest.TestCase):
    def assert_full(self,plan):
        self.assertTrue(plan['fullSuite'])
        for os_name in CONFIG['operatingSystems']:
            ran=sorted(t for (o,_),tests in legs(plan).items() if o==os_name for t in tests)
            self.assertEqual(ran,sorted(DATA['tests']))
        self.assertTrue(plan['itemImport']);self.assertTrue(plan['wheel'])
    def test_unknown_unresolved_missing_base_and_explicit_full_runs_select_every_suite(self):
        self.assert_full(ci_scope.plan(['unknown/file.cfg'],DATA,CONFIG))
        self.assert_full(ci_scope.plan(['tools/shared_tools.py'],DATA,CONFIG))
        self.assert_full(ci_scope.plan(None,DATA,CONFIG))
        self.assert_full(ci_scope.plan([],DATA,CONFIG))
        self.assert_full(ci_scope.plan(['README.md'],DATA,CONFIG,full_reason='Explicit full run'))
        unresolved={**DATA,'unresolved':['tools/phenotypes/a.py']}
        self.assert_full(ci_scope.plan(['tools/phenotypes/a.py'],unresolved,CONFIG))
    def test_missing_zero_or_undiffable_comparison_base_is_reported_as_missing(self):
        self.assertIsNone(ci_scope.changed_files(''))
        self.assertIsNone(ci_scope.changed_files('0'*40))
        self.assertIsNone(ci_scope.changed_files('f'*40))

class ScopedPlanTests(unittest.TestCase):
    def test_documentation_only_change_keeps_verification_but_selects_no_helper_jobs(self):
        plan=ci_scope.plan(['README.md'],DATA,CONFIG)
        self.assertFalse(plan['fullSuite']);self.assertEqual(plan['helperMatrix'],[])
        self.assertEqual(plan['expectedJobs'],['Scope','Repository verification'])
        self.assertFalse(plan['itemImport']);self.assertFalse(plan['wheel'])
    def test_focused_change_runs_on_every_os_and_records_expected_job_names(self):
        plan=ci_scope.plan(['tools/phenotypes/a.py','srn_item/x.uti','tools/kit/README.md'],DATA,CONFIG)
        self.assertEqual(set(legs(plan)),{('ubuntu-latest','phenotypes-1'),('windows-latest','phenotypes-1')})
        self.assertEqual(legs(plan)[('ubuntu-latest','phenotypes-1')],['tools/phenotypes/test_a.py'])
        self.assertTrue(plan['itemImport']);self.assertTrue(plan['wheel'])
        self.assertEqual(plan['expectedJobs'],['Scope','Repository verification','Helpers / ubuntu-latest phenotypes-1',
            'Helpers / windows-latest phenotypes-1','Helpers / item-import ubuntu-latest','Helpers / item-import windows-latest','Helpers / wheel'])
    def test_shards_are_deterministic_balanced_and_complete(self):
        durations={'a':10.0,'b':9.0,'c':5.0,'d':4.0,'e':1.0}
        parts=ci_scope.shards(list('edcba'),2,durations)
        self.assertEqual(parts,ci_scope.shards(list('abcde'),2,durations))
        self.assertEqual(sorted(t for p in parts for t in p),list('abcde'))
        self.assertLessEqual(abs(sum(durations[t] for t in parts[0])-sum(durations[t] for t in parts[1])),durations['e']*2)
        self.assertEqual(ci_scope.shards(['x','y'],3,{}),[['x'],['y'],[]])

class LiveConfigurationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.data=catalog();cls.config=load_config()
    def test_every_catalogued_test_runs_exactly_once_per_os_in_a_full_plan(self):
        plan=ci_scope.plan(None,self.data,self.config)
        for os_name in self.config['operatingSystems']:
            ran=[t for (o,_),tests in legs(plan).items() if o==os_name for t in tests]
            self.assertEqual(sorted(ran),sorted(self.data['tests']));self.assertEqual(len(ran),len(set(ran)))
        durations=json.loads((REPO/ci_scope.DURATIONS).read_text(encoding='utf-8'))['seconds']
        self.assertLessEqual(set(durations),set(self.data['tests']),'Prune durations for removed tests')
    def test_shared_helper_change_selects_dependents_across_folders(self):
        plan=ci_scope.plan(['tools/phenotypes/retarget.py'],self.data,self.config)
        selected={t for row in plan['helperMatrix'] for t in row['tests']}
        self.assertFalse(plan['fullSuite'])
        self.assertTrue(any(t.startswith('tools/heads/') for t in selected))
        self.assertTrue(any(t.startswith('tools/robes/') for t in selected))
        self.assertTrue(any(t.startswith('tools/phenotypes/') for t in selected))

class WorkflowWiringTests(unittest.TestCase):
    """Text checks; GitHub Actions YAML is not parsed by the standard library."""
    @classmethod
    def setUpClass(cls):
        cls.ci=(REPO/'.github/workflows/ci.yml').read_text(encoding='utf-8')
        cls.helpers=(REPO/'.github/workflows/shared-tooling.yml').read_text(encoding='utf-8')
        cls.action=(REPO/'.github/actions/srn-tools/action.yml').read_text(encoding='utf-8')
        cls.all=[p.read_text(encoding='utf-8') for p in (REPO/'.github').rglob('*.yml')]
    def jobs(self,text):
        body=text.split('\njobs:\n',1)[1]
        return re.findall(r'^  ([a-z][a-z0-9_-]*):\s*$',body,re.M)
    def test_result_job_needs_every_other_job_and_runs_always(self):
        jobs=self.jobs(self.ci);self.assertIn('result',jobs)
        needs=re.search(r'^  result:\n(?:    .*\n)*?    needs: \[([^\]]*)\]',self.ci,re.M)
        self.assertEqual(sorted(n.strip() for n in needs[1].split(',')),sorted(j for j in jobs if j!='result'))
        self.assertRegex(self.ci,r'(?m)^  result:\n    name: CI result\n    if: always\(\)')
    def test_job_display_names_match_the_planner(self):
        self.assertIn('    name: Scope\n',self.ci);self.assertIn('    name: Repository verification\n',self.ci)
        self.assertIn('    name: Helpers\n',self.ci)
        self.assertIn('    name: ${{ matrix.os }} ${{ matrix.group }}\n',self.helpers)
        self.assertIn('    name: item-import ${{ matrix.os }}\n',self.helpers);self.assertIn('    name: wheel\n',self.helpers)
        self.assertEqual(set(self.jobs(self.helpers)),{'tests','item-import','wheel'})
    def test_single_item_import_owner_and_single_cache_key_format(self):
        self.assertEqual(sum(t.count('./tools/Test-ItemImportTools.ps1') for t in self.all),1)
        self.assertEqual(sum(t.count('./tools/Test-ItemImportScope.ps1') for t in self.all),0)
        self.assertEqual(sum(t.count('actions/cache@') for t in self.all),1)
        self.assertIn("key: srn-tools-${{ runner.os }}-${{ hashFiles('tools/toolchain.lock.json', 'tools/shared-tools.lock.json') }}",self.action)
        for text in (self.ci,self.helpers):self.assertNotIn('srn-tools-',text)
    def test_superseded_pull_request_runs_cancel_while_main_runs_do_not(self):
        self.assertIn("cancel-in-progress: ${{ github.event_name == 'pull_request' }}",self.ci)
        self.assertIn("format('pr-{0}', github.event.pull_request.number)",self.ci)
        self.assertIn("format('{0}-{1}', github.ref, github.sha)",self.ci)
    def test_helpers_consume_the_plan_and_never_rediscover_scope(self):
        self.assertIn('workflow_call:',self.helpers);self.assertNotIn('pull_request',self.helpers)
        self.assertNotIn('discover -s tools',self.helpers);self.assertNotIn('git diff',self.helpers)
        self.assertIn('fromJSON(inputs.plan).helperMatrix',self.helpers)

if __name__=='__main__':unittest.main()
