import tempfile,unittest,json
from pathlib import Path
from PIL import Image
from head_workflow import pin
from client_capture_review import check_captures
from build_head_trial import validate_spec,plan_actors
from test_head_trial import spec,head,manifest,LOG
from unittest import mock
import verify_head_trial

class CaptureCoverage(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.manifest=self.root/'runtime-manifest.json';self.log=self.root/'client.log';self.record=self.root/'captures.json'
        module=self.root/'trial.mod';module.write_bytes(b'exact module')
        self.actors=[{'tag':'first','headId':'fixture','column':0,'skin':3,'hair':5,'tattoo1':0,'tattoo2':0},
                     {'tag':'second','headId':'fixture','column':1,'skin':3,'hair':21,'tattoo1':0,'tattoo2':0}]
        self.write(self.manifest,{'heads':[{'id':'fixture'}],'actors':self.actors,'files':[{'relativePath':'trial.mod','sha256':pin(module)['sha256']}]})
        lines=['HEAD_INSPECT actor=first view='+view for view in ('three','threeleft','backright','backleft')]
        lines+=['HEAD_MOTION actor=first sequence=talk-look','HEAD_INSPECT actor=first view=front','HEAD_INSPECT actor=second view=front']
        self.log.write_text('Messages for: fixture\n'+'\n'.join('[time] '+line for line in lines))
        captures=[]
        for n,(actor,view,event) in enumerate([('first','three',0),('first','threeleft',1),('first','backright',2),('first','backleft',3),('first','front',5),('second','front',6)]):
            frame=self.root/f'{n}.png';Image.new('RGB',(64,64),(n*30,10,30)).save(frame)
            row={'actor':actor,'view':view,'inspectionEvent':event,'frame':pin(frame)}
            if n==4:row['motionEvent']=4
            captures.append(row)
        self.data={'kind':'head-client-captures-v1','manifest':pin(self.manifest),'log':pin(self.log),'captures':captures}
        self.write(self.record,self.data)
        self.report={'passed':True,'actors':[{'tag':a['tag'],'status':'spawned'} for a in self.actors]}
    def write(self,path,data):path.write_text(json.dumps(data))
    def check(self):return check_captures(self.manifest,self.log,self.record,self.report)
    def test_complete_coverage_still_requires_human_approval(self):
        report=self.check();self.assertTrue(report['passed']);self.assertTrue(report['visualApprovalRequired']);self.assertFalse(report['productionAccepted'])
    def test_missing_view_motion_and_second_look_are_reported(self):
        self.data['captures']=self.data['captures'][:3];self.write(self.record,self.data)
        self.assertEqual(len(self.check()['problems']),3)
    def test_changed_asset_or_frame_cannot_reuse_coverage(self):
        (self.root/'trial.mod').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'changed'):self.check()
    def test_capture_cannot_claim_another_camera_event(self):
        self.data['captures'][0]['view']='backleft';self.write(self.record,self.data)
        with self.assertRaisesRegex(ValueError,'camera/actor'):self.check()
    def test_reusing_one_image_for_multiple_views_is_rejected(self):
        self.data['captures'][1]['frame']=self.data['captures'][0]['frame'];self.write(self.record,self.data)
        with self.assertRaisesRegex(ValueError,'several captures'):self.check()
    def test_new_trials_require_capture_packet_even_with_passing_log(self):
        self.write(self.manifest,manifest(captureCoverageRequired=True))
        self.log.write_text(LOG)
        with mock.patch('builtins.print'):
            self.assertEqual(verify_head_trial.main(['--manifest',str(self.manifest),'--log',str(self.log)]),1)
        self.write(self.manifest,manifest())
        with mock.patch('builtins.print'):
            self.assertEqual(verify_head_trial.main(['--manifest',str(self.manifest),'--log',str(self.log)]),0)
        with self.assertRaisesRegex(ValueError,'captureCoverageRequired'):
            validate_spec(spec(captureCoverageRequired='yes'))
    def test_tattoo_looks_are_separate_cases_with_exact_logged_colours(self):
        item=head('fixture',16,tattoo1Rows=[85,26],tattoo2Rows=[88,0],helmets=[])
        actors=plan_actors(validate_spec(spec(heads=[item])))
        self.assertTrue(any(a['tattoo1']==26 and a['tattoo2']==88 for a in actors))
        self.assertTrue(any(a['tattoo1']==85 and a['tattoo2']==0 for a in actors))
        self.assertTrue(all(a['metal']==0 for a in actors))

if __name__=='__main__':unittest.main()
