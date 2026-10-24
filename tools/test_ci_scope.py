import json
import re
import subprocess
import unittest
from pathlib import Path
import ci_scope
from test_impact import REPO,catalog,load_config

CONFIG={'sharedInfrastructure':[r'^tools/shared_tools\.py$'],'itemImport':[r'^srn_item/'],'wheel':[r'^tools/kit/'],
    'groups':[{'name':'phenotypes','pattern':'^tools/phenotypes/','shards':2},{'name':'core','pattern':'^tools/','shards':1}],
    'operatingSystems':['ubuntu-latest','windows-latest'],'testCheckout':['.github','docs','tools']}
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
    def test_renamed_document_reports_both_paths_and_the_old_one_as_deleted(self):
        import subprocess,tempfile
        from test_impact import deleted_paths
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            def git(*args):return subprocess.run(['git','-C',str(root),'-c','user.name=t','-c','user.email=t@t',*args],check=True,capture_output=True,text=True).stdout.strip()
            git('init','-q');(root/'docs').mkdir();(root/'docs/read.md').write_text('same text\n'*20)
            git('add','-A');git('commit','-qm','base');base=git('rev-parse','HEAD')
            git('mv','docs/read.md','docs/moved.md');git('commit','-qm','rename')
            changed=ci_scope.changed_files(base,'HEAD',root)
            self.assertEqual(changed,['docs/moved.md','docs/read.md'])
            self.assertEqual(deleted_paths(changed,root),{'docs/read.md'})
            self.assertTrue(ci_scope.plan(changed,DATA,CONFIG,deleted=deleted_paths(changed,root))['fullSuite'])
    def test_missing_zero_or_undiffable_comparison_base_is_reported_as_missing(self):
        self.assertIsNone(ci_scope.changed_files(''))
        self.assertIsNone(ci_scope.changed_files('0'*40))
        self.assertIsNone(ci_scope.changed_files('f'*40))

    def test_job_output_carries_the_changed_count_and_keeps_an_unknown_base_null(self):
        many=[f'srn_body/p{i:05d}.mdl' for i in range(6000)]
        compact=json.loads(ci_scope.job_output(ci_scope.plan(many,DATA,CONFIG)))
        self.assertEqual(compact['changed'],6000)
        self.assertLess(len(ci_scope.job_output(ci_scope.plan(many,DATA,CONFIG))),len(json.dumps(many)))
        self.assertIsNone(json.loads(ci_scope.job_output(ci_scope.plan(None,DATA,CONFIG)))['changed'])

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

def reached_packs(data,test):
    """Independent closure: packs named by the test or anything it reaches through catalogued edges."""
    seen={test};stack=[test]
    while stack:
        for edge in data['dependencies'].get(stack.pop(),[]):
            if edge not in seen:seen.add(edge);stack.append(edge)
    return {p for path in seen for p in data['packReferences'].get(path,[])}

class PackCheckoutTests(unittest.TestCase):
    """Every test that reaches a pack, directly or transitively, runs in a leg whose sparse checkout includes it."""
    def assert_covered(self,plan,data,config):
        for row in plan['helperMatrix']:
            checkout=row['checkout'].split('\n')
            self.assertEqual(checkout[:len(config['testCheckout'])],config['testCheckout'])
            self.assertEqual(sorted(p for p in checkout if p.startswith('srn_')),row['packs'])
            for test in row['tests']:
                self.assertLessEqual(reached_packs(data,test),set(checkout),(row['os'],row['group'],test))
    def test_transitive_pack_reference_selects_a_pack_leg_and_other_legs_stay_pack_free(self):
        config={**CONFIG,'groups':[{'name':'packs','packTests':True,'shards':1},*CONFIG['groups']]}
        data={**DATA,'dependencies':{**DATA['dependencies'],'tools/phenotypes/a.py':['tools/phenotypes/deep.py'],'tools/phenotypes/deep.py':[]},
            'packReferences':{'tools/phenotypes/deep.py':['srn_alpha'],'tools/kit/test_k.py':['srn_beta']}}
        for plan in (ci_scope.plan(None,data,config),ci_scope.plan(['srn_alpha/x.mdl'],data,config),ci_scope.plan(['tools/phenotypes/deep.py'],data,config)):
            self.assert_covered(plan,data,config)
        rows=legs(ci_scope.plan(None,data,config))
        self.assertEqual(rows[('ubuntu-latest','packs')],['tools/kit/test_k.py','tools/phenotypes/test_a.py'])
        full=ci_scope.plan(None,data,config)['helperMatrix']
        self.assertEqual({r['group']:r['packs'] for r in full},{'packs':['srn_alpha','srn_beta'],'phenotypes-1':[],'phenotypes-2':[],'core':[]})
        self.assertEqual(next(r['checkout'] for r in full if r['group']=='core'),'.github\ndocs\ntools')
    def test_without_a_pack_group_the_pattern_leg_checks_out_the_pack(self):
        data={**DATA,'packReferences':{'tools/phenotypes/a.py':['srn_alpha']}}
        plan=ci_scope.plan(None,data,CONFIG);self.assert_covered(plan,data,CONFIG)
        self.assertIn('srn_alpha',next(r['packs'] for r in plan['helperMatrix'] if 'tools/phenotypes/test_a.py' in r['tests']))
    def test_live_catalog_every_pack_test_is_checked_out_with_its_packs_in_full_and_scoped_plans(self):
        data=catalog();config=load_config()
        needing={t for t in data['tests'] if reached_packs(data,t)}
        # Guard against a vacuous pass: some tests name a pack themselves, others reach one only through helpers.
        direct={t for t in needing if data['packReferences'].get(t)}
        self.assertTrue(direct);self.assertTrue(needing-direct)
        plans=[ci_scope.plan(None,data,config)]
        plans+=[ci_scope.plan([test],data,config) for test in sorted(needing)]
        plans+=[ci_scope.plan([pack+'/changed.bin'],data,config) for pack in sorted({p for t in needing for p in reached_packs(data,t)})]
        for plan in plans:
            self.assert_covered(plan,data,config)
            for row in plan['helperMatrix']:
                if row['group']!='packs':self.assertEqual(row['packs'],[],row['group'])
        ran={t for row in plans[0]['helperMatrix'] if row['group']=='packs' for t in row['tests']}
        self.assertEqual(ran,needing)

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
    def test_controlled_startup_suite_keeps_its_declared_pack_dependencies(self):
        target='tools/headkit/test_comfy_runtime_snapshot.py'
        required=reached_packs(self.data,target)
        for plan in (ci_scope.plan(None,self.data,self.config),ci_scope.plan([target],self.data,self.config)):
            for os_name in self.config['operatingSystems']:
                matches=[row for row in plan['helperMatrix'] if row['os']==os_name and target in row['tests']]
                self.assertEqual(len(matches),1)
                row=matches[0]
                self.assertEqual(row['group'],'packs' if required else 'headkit')
                self.assertLessEqual(required,set(row['packs']))
                self.assertLessEqual(required,set(row['checkout'].split('\n')))

    def test_shared_helper_change_runs_the_full_helper_suite(self):
        # retarget.py is consumed by phenotype, head and robe helpers (AGENTS.md: shared helpers run the full suite).
        plan=ci_scope.plan(['tools/phenotypes/retarget.py'],self.data,self.config)
        self.assertTrue(plan['fullSuite']);self.assertIn('Shared helper changed: tools/phenotypes/retarget.py',plan['reason'])
        selected={t for row in plan['helperMatrix'] for t in row['tests']}
        self.assertEqual(selected,set(self.data['tests']))
    def test_single_folder_helper_change_stays_focused(self):
        plan=ci_scope.plan(['tools/phenotypes/pose_preview_render_settings.py'],self.data,self.config)
        self.assertFalse(plan['fullSuite'])
        selected={t for row in plan['helperMatrix'] for t in row['tests']}
        self.assertTrue(selected and all(t.startswith('tools/phenotypes/') for t in selected))

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
    def test_snapshot_jobs_have_time_for_census_and_finalization(self):
        tests=self.helpers.split('  tests:',1)[1].split('  item-import:',1)[0]
        # Windows measured 841 seconds of successful tests before its 15-minute
        # job limit expired during finalization. Keep other groups bounded at 15.
        self.assertIn("timeout-minutes: ${{ matrix.group == 'headkit' && 25 || 15 }}",tests)

    def test_single_item_import_owner_and_single_cache_key_format(self):
        self.assertEqual(sum(t.count('./tools/Test-ItemImportTools.ps1') for t in self.all),1)
        self.assertEqual(sum(t.count('./tools/Test-ItemImportScope.ps1') for t in self.all),0)
        self.assertEqual(sum(t.count('actions/cache@') for t in self.all),1)
        self.assertIn("key: srn-tools-${{ runner.os }}-${{ hashFiles('tools/toolchain.lock.json', 'tools/shared-tools.lock.json') }}",self.action)
        for text in (self.ci,self.helpers):self.assertNotIn('srn-tools-',text)
    def test_result_refresh_is_bounded_and_final_pending_status_still_fails(self):
        result=self.ci.split('  result:',1)[1]
        self.assertIn('for attempt in 1 2 3 4 5 6; do',result)
        loop=result.split('for attempt in 1 2 3 4 5 6; do',1)[1].split('done',1)[0]
        self.assertIn('gh api ',loop);self.assertIn('filter=all&per_page=100',loop)
        self.assertIn('--pending-exit-code 2',loop)
        self.assertIn('if [ "$result" -ne 2 ]; then exit "$result"; fi',loop)
        self.assertIn('sleep 10',loop)
        final=result.split('done',1)[1]
        self.assertIn('tools/ci_result.py',final);self.assertNotIn('--pending-exit-code',final)

    def test_superseded_pull_request_runs_cancel_while_main_runs_do_not(self):
        self.assertIn("cancel-in-progress: ${{ github.event_name == 'pull_request' }}",self.ci)
        self.assertIn("format('pr-{0}', github.event.pull_request.number)",self.ci)
        self.assertIn("format('{0}-{1}', github.ref, github.sha)",self.ci)
    def checkout(self,job,text):
        """The indented settings of a job's actions/checkout step."""
        body=re.search(r'(?ms)^  '+job+r':\n(.*?)(?=^  [a-z]|\Z)',text)[1]
        return re.search(r'(?m)^ *(?:- )?uses: actions/checkout@v\d+\n((?:        .*\n)*)',body)[1]
    def test_helper_jobs_use_bounded_sparse_blobless_checkouts(self):
        tests=self.checkout('tests',self.helpers)
        self.assertIn('sparse-checkout: ${{ matrix.checkout }}\n',tests);self.assertIn('filter: blob:none\n',tests)
        item=self.checkout('item-import',self.helpers)
        self.assertIn('sparse-checkout: |\n            .github\n            tools\n',item);self.assertIn('filter: blob:none\n',item)
        wheel=self.checkout('wheel',self.helpers)
        self.assertIn('sparse-checkout: tools/phenomorpher\n',wheel);self.assertIn('filter: blob:none\n',wheel)
        self.assertNotIn('sparse-checkout-cone-mode',self.helpers)
        # Verification builds every pack, so it keeps the complete working tree.
        verify=self.checkout('verify',self.ci);self.assertIn('fetch-depth: 0\n',verify);self.assertNotIn('sparse-checkout',verify)
    def test_scope_checks_out_every_folder_the_catalog_reads(self):
        scope=self.checkout('scope',self.ci);base=load_config()['testCheckout']
        self.assertIn('fetch-depth: 0\n',scope);self.assertIn('filter: blob:none\n',scope)
        self.assertIn('sparse-checkout: |\n'+''.join(' '*12+p+'\n' for p in base),scope)
        # The catalog walks every non-pack folder for tools and Markdown, so a new top-level folder must join the set.
        top=subprocess.run(['git','-C',str(REPO),'ls-tree','-d','--name-only','HEAD'],capture_output=True,text=True,check=True).stdout.split()
        self.assertEqual(sorted(base),sorted(d for d in top if not re.fullmatch(r'srn_[a-z0-9_]+',d)))
    def test_helpers_consume_the_plan_and_never_rediscover_scope(self):
        self.assertIn('workflow_call:',self.helpers);self.assertNotIn('pull_request',self.helpers)
        self.assertNotIn('discover -s tools',self.helpers);self.assertNotIn('git diff',self.helpers)
        self.assertIn('fromJSON(inputs.plan).helperMatrix',self.helpers)

if __name__=='__main__':unittest.main()
