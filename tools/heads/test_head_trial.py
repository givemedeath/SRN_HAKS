import contextlib
import copy
import io
from pathlib import Path
import tempfile
import unittest
from head_workflow import pin,write_fresh
from verify_head_hak import TYPES,payload,write_hak
from build_head_trial import validate_spec,plan_actors,plan_hak,head_resources,launch_scripts,texture_references,entries,model_identity
import verify_head_trial

def binary_model(name):
    return bytes(12)+bytes(8)+name.encode('ascii').ljust(64,bytes(1))+b'geometry'


PIN={'path':'base/sr_t_body.hak','sha256':'0'*64}


def spec(**changes):
    value={'kind':'srn-head-trial-spec','trial':'troll-batch-v1','hak':'srn_trl_b1','module':'srn_trl_batch','prefix':'pmg0',
           'gameRoot':'game','lighting':'directional','identity':{'appearanceRow':2,'raceId':2,'visualScale':10/7},
           'base':{'haks':[PIN,{'path':'base/sr_h_fixture.hak','sha256':'1'*64}],'module':{'path':'base/view.mod','sha256':'2'*64}},
           'heads':[head('troll-male-02',16),head('troll-male-03',17,tattoo1Row=80)]}
    value.update(changes);return value


def head(identity,slot,**changes):
    value={'id':identity,'model':f'pmg0_head{slot:03d}','native':'native/'+identity,'skinRows':[65,3,12],'hairRows':[65,5,21],
           'tattoo1Row':85,'tattoo2Row':88}
    value.update(changes);return value


class TrialSpecTests(unittest.TestCase):
    def test_valid_spec_is_normalized(self):
        result=validate_spec(spec())
        self.assertEqual([h['slot'] for h in result['heads']],[16,17])
        self.assertEqual(result['heads'][0]['helmets'],[1,2]);self.assertEqual(result['heads'][0]['metalRow'],0)
        self.assertEqual(result['shared'],[])

    def test_rejects_malformed_specs(self):
        cases={
            'Explicit srn-head-trial-spec':spec(kind='other'),
            'resref':spec(hak='srn_troll_trial_heads'),
            'base HAK':spec(hak='sr_t_body'),
            'model must be':spec(heads=[head('a',16,model='pmh0_head016')]),
            'slot repeats':spec(heads=[head('a',16),head('b',16)]),
            'unique plain id':spec(heads=[head('a',16),head('a',17)]),
            'exactly one':spec(heads=[{**head('a',16),'resources':['x.mdl']}]),
            'skinRows':spec(heads=[head('a',16,skinRows=[176])]),
            'hairRows':spec(heads=[head('a',16,hairRows=[5,5])]),
            'tattoo2Row':spec(heads=[head('a',16,tattoo2Row=[88])]),
            'metalRow':spec(heads=[head('a',16,metalRow=3)]),
            'helmets':spec(heads=[head('a',16,helmets=[3])]),
            'Too many actors':spec(heads=[head(f'h{i}',16+i,skinRows=list(range(5)),hairRows=list(range(5))) for i in range(4)]),
            'identity':spec(identity={'appearanceRow':2,'raceId':2}),
            'Explicit lighting':spec(lighting='bright'),
            'sha256 pins':spec(base={'haks':[{'path':'x.hak'}],'module':PIN}),
        }
        for message,value in cases.items():
            with self.subTest(message),self.assertRaisesRegex(ValueError,message):validate_spec(value)

    def test_actors_cover_rows_and_helmets_per_head(self):
        actors=plan_actors(validate_spec(spec()))
        self.assertEqual(len(actors),22)
        self.assertEqual([a['tag'] for a in actors[:2]],['sr_h_actor0','sr_h_actor1'])
        first=actors[:11]
        self.assertEqual({a['slot'] for a in first},{16})
        self.assertEqual([(a['skin'],a['hair']) for a in first[:9]],[(s,h) for s in (65,3,12) for h in (65,5,21)])
        self.assertEqual([(a['skin'],a['hair'],a['helmet']) for a in first[9:]],[(65,65,1),(65,65,2)])
        self.assertEqual({(a['tattoo1'],a['tattoo2'],a['metal']) for a in first},{(85,88,0)})
        self.assertEqual({(a['slot'],a['tattoo1']) for a in actors[11:]},{(17,80)})
        self.assertGreater(min(a['y'] for a in actors[11:]),max(a['y'] for a in first))
        self.assertEqual(len({(a['x'],a['y']) for a in actors}),22)
        self.assertTrue(all(len(a['tag'])<=16 and 0<a['x']<80 and 0<a['y']<80 for a in actors))


class TrialHakTests(unittest.TestCase):
    def setUp(self):
        self.heads=validate_spec(spec())['heads']

    def plan(self,resources_a,resources_b=None,*,shared=(),base=None,ascii_a=None):
        rows=[(self.heads[0],resources_a,ascii_a)]
        if resources_b is not None:rows.append((self.heads[1],resources_b,None))
        return plan_hak(rows,list(shared),base or {'sr_h_fixture':{('sr_h_floor',2013):'f'}})

    def own(self,slot):
        name=f'pmg0_head{slot:03d}'
        return [(name,2002,binary_model(name)),(name,6,b'plt'+bytes([slot]))]

    def test_model_must_be_internally_named_for_its_slot(self):
        self.assertEqual(model_identity(binary_model('pmg0_head016')),'pmg0_head016')
        self.assertEqual(model_identity(b'# ascii\nnewmodel PMG0_head016\n'),'pmg0_head016')
        with self.assertRaisesRegex(ValueError,'internally named pmg0_head015'):
            self.plan([('pmg0_head016',2002,binary_model('pmg0_head015')),('pmg0_head016',6,b'p')])

    def test_merges_heads_in_spec_and_archive_order(self):
        entries,dependencies=self.plan(self.own(16),self.own(17))
        self.assertEqual([(n,k) for n,k,_ in entries],[('pmg0_head016',2002),('pmg0_head016',6),('pmg0_head017',2002),('pmg0_head017',6)])
        with tempfile.TemporaryDirectory() as tmp:
            single=Path(tmp)/'single.hak';write_hak(single,self.own(16))
            merged=Path(tmp)/'merged.hak';write_hak(merged,self.plan(self.own(16))[0])
            self.assertEqual(single.read_bytes(),merged.read_bytes())
        self.assertEqual(dependencies['troll-male-02'],{'checked':False})

    def test_refuses_collisions_and_shadows(self):
        with self.assertRaisesRegex(ValueError,'not named for its head'):self.plan(self.own(16),self.own(17)+[('pmg0_head016n',3,b'n')])
        with self.assertRaisesRegex(ValueError,'Resource collision'):
            self.plan(self.own(16)+[('pmg0_head016',3,b'tga')])
        with self.assertRaisesRegex(ValueError,'Resource collision'):
            self.plan(self.own(16),self.own(17),shared=[('pmg0_head016',6,b'other')])
        with self.assertRaisesRegex(ValueError,'shadow pmg0_head016.tga in base HAK sr_t_heads'):
            self.plan(self.own(16),base={'sr_t_heads':{('pmg0_head016',3):'x'}})
        with self.assertRaisesRegex(ValueError,'no pmg0_head016.mdl'):self.plan(self.own(16)[1:])

    def test_identical_shared_resources_merge(self):
        entries,_=self.plan(self.own(16),shared=[('sr_trl_common',3,b'same'),('sr_trl_common',3,b'same')])
        self.assertIn(('sr_trl_common',3,b'same'),entries)

    def test_model_texture_dependencies(self):
        text='newmodel pmg0_head016\n  bitmap pmg0_head016\n  materialname pmg0_head016\n  texture1 sr_trl_detail\n  texture2 NULL\n'
        self.assertEqual(texture_references(text),({'pmg0_head016','sr_trl_detail'},{'pmg0_head016'}))
        with self.assertRaisesRegex(ValueError,'sr_trl_detail'):self.plan(self.own(16),ascii_a=text)
        _,dependencies=self.plan(self.own(16),shared=[('sr_trl_detail',3,b'd')],ascii_a=text)
        self.assertEqual(dependencies['troll-male-02']['materialFallbackToBitmap'],['pmg0_head016'])
        _,dependencies=self.plan(self.own(16),base={'sr_t_heads':{('sr_trl_detail',2033):'x'}},ascii_a=text)
        self.assertTrue(dependencies['troll-male-02']['checked'])
        self.heads[0]['externalTextures']=['sr_trl_detail']
        _,dependencies=self.plan(self.own(16),ascii_a=text)
        self.assertEqual(dependencies['troll-male-02']['external'],['sr_trl_detail'])
        with self.assertRaisesRegex(ValueError,'mtr texture not packaged'):
            self.plan(self.own(16)+[('pmg0_head016',2072,b'texture0 pmg0_head016_missing\n')])

    def test_archive_reader_matches_payload_and_checks_signature(self):
        with tempfile.TemporaryDirectory() as tmp:
            hak=Path(tmp)/'a.hak';write_hak(hak,self.own(16))
            self.assertEqual(entries(hak),self.own(16))
            with self.assertRaisesRegex(ValueError,'Expected native MOD archive'):entries(hak,signature=b'MOD V1.0')
            module=Path(tmp)/'a.mod';module.write_bytes(b'MOD'+hak.read_bytes()[3:])
            self.assertEqual(entries(module,signature=b'MOD V1.0'),self.own(16))

    def test_native_stage_resources_come_from_its_verified_hak(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage=Path(tmp);hak=stage/'pmg0_head016.hak';write_hak(hak,self.own(16))
            (stage/'converted/ascii').mkdir(parents=True);(stage/'converted/ascii/pmg0_head016.mdl').write_text('bitmap pmg0_head016\n')
            rows=payload(hak)
            record={'model':'pmg0_head016','hak':pin(hak),'mdl':{'path':'x','sha256':rows[('pmg0_head016',2002)]},
                    'plt':{'path':'x','sha256':rows[('pmg0_head016',6)]}}
            write_fresh(stage/'native.json',record)
            item={**self.heads[0],'native':str(stage)}
            found,ascii_model,pins=head_resources(item)
            self.assertEqual(found,self.own(16));self.assertEqual(ascii_model.name,'pmg0_head016.mdl');self.assertEqual(pins,[pin(hak)])
            with self.assertRaisesRegex(ValueError,'native stage builds'):head_resources({**item,'model':'pmg0_head017'})
            (stage/'native.json').unlink();write_fresh(stage/'native.json',{**record,'plt':{'path':'x','sha256':'0'*64}})
            with self.assertRaisesRegex(ValueError,'plt pin differs'):head_resources(item)
            write_hak(hak,self.own(16)[:1])
            with self.assertRaisesRegex(ValueError,'native HAK differs'):head_resources(item)


class TrialModuleTests(unittest.TestCase):
    def test_tattoo_actor_and_spawn_script(self):
        from build_head_fixture import make_creature,spawn_script,SPAWN,module_scripts
        actor=make_creature({'FirstName':{'type':'cexolocstring','value':{}}},'sr_h_actor0','n',0,0,16,65,5,2,2,10/7,0,tattoo=(85,88))
        variables={v['Name']['value']:v['Value']['value'] for v in actor['VarTable']['value']}
        self.assertEqual(actor['__struct_id'],4);self.assertEqual(actor['ScriptDeath']['value'],'sr_h_death')
        self.assertEqual({k:variables[k] for k in ('HEAD_SLOT','SKIN_ROW','HAIR_ROW','TATTOO1_ROW','TATTOO2_ROW')},
                         {'HEAD_SLOT':16,'SKIN_ROW':65,'HAIR_ROW':5,'TATTOO1_ROW':85,'TATTOO2_ROW':88})
        plain=make_creature({'FirstName':{'type':'cexolocstring','value':{}}},'t','n',0,0,16,65,5,2,2,1.0)
        self.assertNotIn('TATTOO1_ROW',{v['Name']['value'] for v in plain['VarTable']['value']})
        self.assertEqual(spawn_script(),SPAWN)
        script=spawn_script(tattoo=True)
        self.assertIn('SetColor(OBJECT_SELF,COLOR_CHANNEL_TATTOO_1,GetLocalInt(OBJECT_SELF,"TATTOO1_ROW"));',script)
        self.assertIn('SetColor(OBJECT_SELF,COLOR_CHANNEL_TATTOO_2,GetLocalInt(OBJECT_SELF,"TATTOO2_ROW"));',script)
        self.assertIn('HEAD_FIXTURE_COLORS actor=',script);self.assertIn('HEAD_FIXTURE_SLOT actor=',script)
        self.assertLess(script.index('TATTOO1_ROW'),script.index('HEAD_FIXTURE_SLOT'))
        self.assertEqual(set(module_scripts(tattoo=True)),{'sr_h_spawn','sr_h_hb','sr_h_death','sr_h_enter'})

    def test_module_documents_put_trial_hak_first(self):
        from build_head_fixture import module_documents,target_creature
        target=target_creature({'FirstName':{'type':'cexolocstring','value':{}}},2,2,10/7,40,60)
        self.assertEqual((target['Tag']['value'],target['Plot']['value'],target['ScriptHeartbeat']['value']),('head_target',1,''))
        documents=module_documents([target],['srn_trl_b1','sr_t_body','sr_h_fixture'],'ambient',name='Trial')
        self.assertEqual(list(documents),['module.ifo','sr_h_floor.are','sr_h_floor.git','repute.fac'])
        haks=[h['Mod_Hak']['value'] for h in documents['module.ifo']['Mod_HakList']['value']]
        self.assertEqual(haks,['srn_trl_b1','sr_t_body','sr_h_fixture'])
        self.assertEqual(documents['sr_h_floor.git']['Creature List']['value'],[target])
        with self.assertRaisesRegex(ValueError,'light profile'):module_documents([],['a'],'bright')

    def test_launch_scripts_open_the_module_in_an_isolated_userdir(self):
        cmd,ps1=launch_scripts('srn_trl_batch')
        self.assertIn('Launch.ps1',cmd);self.assertIn("'+TestNewModule', 'srn_trl_batch'",ps1)
        self.assertIn("[string]$Client = ''",ps1);self.assertIn('-userdirectory',ps1);self.assertIn('Runtime hash mismatch',ps1)
        _,ps1=launch_scripts('m',"C:\\Games\\it's\\nwmain.exe")
        self.assertIn("[string]$Client = 'C:\\Games\\it''s\\nwmain.exe'",ps1)


LOG='''--------------------------------------
Messages for: Thu Oct 22 10:00:00 2026
--------------------------------------
[Thu Oct 22 10:00:02] Loading Module: srn_trl_batch
[Thu Oct 22 10:00:02] HEAD_FIXTURE_CLIENT_ENTER
[Thu Oct 22 10:00:02] HEAD_FIXTURE_SLOT actor=sr_h_actor0 selected=16
[Thu Oct 22 10:00:02] HEAD_FIXTURE_SLOT actor=sr_h_actor1 selected=17
--------------------------------------
Messages for: Fri Oct 23 13:01:11 2026
--------------------------------------
[Fri Oct 23 13:01:13] Loading Module: srn_trl_batch
[Fri Oct 23 13:01:13] HEAD_FIXTURE_CLIENT_ENTER
[Fri Oct 23 13:01:13] HEAD_FIXTURE_SLOT actor=sr_h_actor1 selected=17
[Fri Oct 23 13:01:13] HEAD_FIXTURE_COLORS actor=sr_h_actor1 skin=3 hair=5 tattoo1=80 tattoo2=88
[Fri Oct 23 13:01:14] HEAD_FIXTURE_SLOT actor=head_target selected=1
[Fri Oct 23 13:01:14] HEAD_FIXTURE_SLOT actor=sr_h_actor0 selected=16
[Fri Oct 23 13:01:14] HEAD_FIXTURE_COLORS actor=sr_h_actor0 skin=65 hair=65 tattoo1=85 tattoo2=88
[Fri Oct 23 13:01:23] HEAD_FIXTURE_MOTION actor=sr_h_actor0 step=1 action=65535
'''


def manifest(**changes):
    value={'kind':'srn-head-trial-client-view','module':'srn_trl_batch','colorsLogged':True,'ignoredActors':['head_target'],
           'actors':[{'tag':'sr_h_actor0','headId':'a','model':'pmg0_head016','slot':16,'skin':65,'hair':65,'tattoo1':85,'tattoo2':88},
                     {'tag':'sr_h_actor1','headId':'b','model':'pmg0_head017','slot':17,'skin':3,'hair':5,'tattoo1':80,'tattoo2':88}]}
    value.update(changes);return value


class TrialLogTests(unittest.TestCase):
    def test_passes_when_every_actor_spawned_on_its_slot(self):
        report=verify_head_trial.check(manifest(),LOG)
        self.assertTrue(report['passed'],report['problems'])
        self.assertEqual(report['session'],'Fri Oct 23 13:01:11 2026')
        self.assertEqual([r['status'] for r in report['actors']],['spawned','spawned'])
        self.assertEqual(report['actors'][0]['observedColors'],{'skin':'65','hair':'65','tattoo1':'85','tattoo2':'88'})

    def test_only_the_newest_session_counts(self):
        older=LOG.split('--------------------------------------\nMessages for: Fri')[0]
        newer='--------------------------------------\nMessages for: Sat Oct 24 09:00:00 2026\n--------------------------------------\n'
        report=verify_head_trial.check(manifest(),older+newer)
        self.assertFalse(report['passed'])
        self.assertEqual([r['status'] for r in report['actors']],['missing','missing'])
        self.assertIn('Module srn_trl_batch was not loaded in the newest session',report['problems'])

    def test_reports_wrong_slot_colours_and_strays(self):
        log=LOG.replace('actor=sr_h_actor1 selected=17','actor=sr_h_actor1 selected=1').replace('hair=65','hair=5')
        log+='[Fri Oct 23 13:01:30] HEAD_FIXTURE_SLOT actor=sr_h_actor9 selected=16\n'
        report=verify_head_trial.check(manifest(),log)
        self.assertEqual([r['status'] for r in report['actors']],['wrong-colors','wrong-slot'])
        self.assertEqual(report['unexpectedActors'],['sr_h_actor9'])
        report=verify_head_trial.check(manifest(),LOG.replace('[Fri Oct 23 13:01:14] HEAD_FIXTURE_COLORS actor=sr_h_actor0','[x] OTHER'))
        self.assertEqual(report['actors'][0]['status'],'colors-missing')
        report=verify_head_trial.check(manifest(colorsLogged=False),LOG.replace('HEAD_FIXTURE_COLORS','OTHER'))
        self.assertTrue(report['passed'])

    def test_cli_exit_code_and_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);write_fresh(root/'runtime-manifest.json',manifest())
            (root/'userdir/logs').mkdir(parents=True);log=root/'userdir/logs/nwclientLog1.txt';log.write_text(LOG)
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(verify_head_trial.main(['--manifest',str(root/'runtime-manifest.json'),'--output',str(root/'report.json')]),0)
            self.assertIn('PASSED (2/2',out.getvalue());self.assertTrue((root/'report.json').is_file())
            log.write_text(LOG.replace('selected=16','selected=15'))
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(verify_head_trial.main(['--manifest',str(root/'runtime-manifest.json'),'--log',str(log)]),1)
            self.assertIn('sr_h_actor0 (pmg0_head016): wrong-slot',out.getvalue());self.assertIn('FAILED (1/2',out.getvalue())
            log.write_text(LOG.replace('HEAD_FIXTURE_COLORS','OTHER'))
            arguments=['--manifest',str(root/'runtime-manifest.json')]
            with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(verify_head_trial.main(arguments),1)
            with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(verify_head_trial.main(arguments+['--slots-only']),0)
            log.unlink()
            with contextlib.redirect_stdout(io.StringIO()) as out:self.assertEqual(verify_head_trial.main(arguments),2)
            self.assertIn('Client log not found',out.getvalue())


if __name__=='__main__':unittest.main()
