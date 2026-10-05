"""Preparation equivalence, immutable evidence, current state and review boundaries."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
from test_pose_preview_bridge import ROOT,animation
from test_effective_body_preview import model
from run_preparation import PreparationContext
from pose_preview_bridge import pose
from joint_review_packet import build
from resume_summary import FIELDS,summary,verify_summary,verify_integration
from shared_tools import sha,write_json,read_json
from finalize_shared_tool_migration import fixture_declaration

class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.addCleanup(self.tmp.cleanup)
        (self.root/'pmh0.mdl').write_text(ROOT,encoding='cp1252')
        (self.root/'a_ba.mdl').write_text(animation('positionkey 2\n 0 1 0 0\n 1 3 0 0'),encoding='cp1252')
    def context(self,**kwargs):
        return PreparationContext(target_revision='human-male',rig_revision='stock',animation_revision='a_ba',settings=kwargs)
    def test_cached_uncached_equivalence_once_per_resource(self):
        context=self.context()
        for time in [0,.25,.5,.75,1]:
            cached,_=pose(self.root,'pmh0','pause1',time,context=context)
            uncached,_=pose(self.root,'pmh0','pause1',time)
            for node in cached:np.testing.assert_array_equal(cached[node],uncached[node])
        self.assertEqual(context.counts['model/controller-parse'],2)
    def test_troll_and_female_target_chains_are_separate_and_unchanged(self):
        for target,prefix,chain in [('troll-male','pmg0','a_ba'),('human-female','pfh0','a_fa')]:
            directory=self.root/target;directory.mkdir()
            root=directory/(prefix+'.mdl');parent=directory/(chain+'.mdl')
            root.write_text(ROOT.replace('pmh0',prefix).replace('a_ba',chain),encoding='cp1252')
            parent.write_text(animation('position 3 0 0').replace('a_ba',chain),encoding='cp1252')
            pins={str(p):sha(p) for p in [root,parent]}
            context=PreparationContext(target_revision=target,rig_revision='declared-frozen-rig',animation_revision=chain,settings={})
            for time in [0,.5,1]:
                a,_=pose(directory,prefix,'pause1',time,context=context);b,_=pose(directory,prefix,'pause1',time)
                for node in a:np.testing.assert_array_equal(a[node],b[node])
            self.assertEqual(context.counts['model/controller-parse'],2)
            self.assertEqual(pins,{str(p):sha(p) for p in [root,parent]})
    def test_prepared_array_is_immutable_and_decoder_once(self):
        path=self.root/'geometry';path.write_bytes(b'geometry');calls=[];context=self.context()
        def decode(data):calls.append(data);return np.arange(12).reshape(4,3)
        a=context.prepared(path,'geometry',decode);b=context.prepared(path,'geometry',decode)
        self.assertIs(a,b);self.assertEqual(len(calls),1)
        with self.assertRaises(ValueError):a[0,0]=99
        with self.assertRaises(ValueError):a.setflags(write=True)
    def test_geometry_animation_material_helper_config_changes_invalidate(self):
        for kind in ['geometry','animation','material','helper','config']:
            with self.subTest(kind=kind):
                path=self.root/kind;path.write_bytes(b'parent');context=self.context()
                context.prepared(path,kind,lambda data:np.zeros((1,3)))
                path.write_bytes(b'changed')
                with self.assertRaisesRegex(ValueError,'changed'):context.verify()
                with self.assertRaisesRegex(ValueError,'invalidated'):context.prepared(path,kind,lambda data:0)
    def test_settings_and_revisions_are_part_of_key(self):
        self.assertNotEqual(self.context(normalStrength=1).identity_hash,self.context(normalStrength=.5).identity_hash)
        a=self.context();b=PreparationContext(target_revision='female',rig_revision='stock',animation_revision='a_fa',settings={})
        self.assertNotEqual(a.identity_hash,b.identity_hash)
    def test_joint_packet_binds_sources_motion_materials_without_approval(self):
        meshes=self.root/'part.mdl';meshes.write_text(model(),encoding='cp1252')
        row={'path':str(meshes),'sha256':sha(meshes),'attachmentFrame':np.eye(4).tolist(),
             'joint':'joint','connectorBounds':[[-1,-1,-1],[2,2,2]]}
        config={'coordinateSpace':'nwn-part-local','targetRevision':'target','rigRevision':'stock','animationRevision':'a_ba',
            'asciiDirectory':str(self.root),'prefix':'pmh0','reviewSettings':{'cameraScale':2,'threads':4},
            'parent':row,'candidate':row,'neighbor':{**row,'joint':'rootdummy'},'contactAxis':[1,0,0],
            'motionSamples':[{'clip':'pause1','time':0,'standing':True},{'clip':'pause1','time':1}]}
        path=self.root/'packet-config.json';write_json(path,config)
        packet=build(path,self.root/'packet.json')
        self.assertEqual(packet['preparation']['preparationCounts']['geometry-decode'],1)
        self.assertFalse(packet['numericSuccessApprovesAnatomy']);self.assertFalse(packet['clientEvidence'])
        self.assertEqual(len(packet['motionMeasurements']),2)
        self.assertEqual(packet['reviewViews'][0]['settings'],packet['reviewViews'][2]['settings'])
        with self.assertRaises(FileExistsError):build(path,self.root/'packet.json')
    def bindings(self):
        ledger={field:field+' value' for field in FIELDS}
        ledger['latestDirection']={'sequence':3,'superseded':False,'text':'Continue current task'}
        ledger['currentDirectionSequence']=3;path=self.root/'ledger.json';write_json(path,ledger)
        bindings={'ledger':{'path':str(path),'sha256':sha(path)},'selectors':{field:'/'+field for field in FIELDS}}
        b=self.root/'bindings.json';write_json(b,bindings);return path,b,ledger,bindings
    def test_resume_binds_exact_ledger_and_keeps_acceptance_axes_separate(self):
        ledger,b,_,_=self.bindings();report=summary(b);out=self.root/'résumé.json';write_json(out,report,fresh=True)
        self.assertEqual(verify_summary(out),report)
        self.assertNotEqual(report['current']['workingSelection'],report['current']['productionAcceptance'])
        ledger.write_text('{}',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'Stale'):verify_summary(out)
    def test_missing_conflicting_or_superseded_bindings_rejected(self):
        path,b,ledger,bindings=self.bindings()
        bindings['selectors'].pop('partsBank');write_json(b,bindings)
        with self.assertRaises(ValueError):summary(b)
        bindings['selectors']['partsBank']=['/partsBank','/targetRevision'];write_json(b,bindings)
        with self.assertRaisesRegex(ValueError,'Conflicting'):summary(b)
        bindings['selectors']['partsBank']='/partsBank';ledger['latestDirection']['superseded']=True
        write_json(path,ledger);bindings['ledger']['sha256']=sha(path);write_json(b,bindings)
        with self.assertRaisesRegex(ValueError,'unsuperseded'):summary(b)
    def test_stale_parent_and_neighbor_integration_rejected(self):
        parent=self.root/'parent';parent.write_bytes(b'parent');neighbor=self.root/'neighbor';neighbor.write_bytes(b'neighbor')
        pins=[{'path':str(p),'sha256':sha(p)} for p in [parent,neighbor]]
        verify_integration(pins[0],pins[1:]);neighbor.write_bytes(b'new selection')
        with self.assertRaisesRegex(ValueError,'Stale parent'):verify_integration(pins[0],pins[1:])
    def test_unicode_utf8_immutable_receipt(self):
        path=self.root/'收据.json';write_json(path,{'direction':'继续 — résumé'},fresh=True)
        self.assertEqual(read_json(path)['direction'],'继续 — résumé')
        self.assertNotEqual(path.read_bytes()[:3],b'\xef\xbb\xbf')
        with self.assertRaises(FileExistsError):write_json(path,{},fresh=True)
    def test_declared_male_and_female_fixture_sets_no_count_assumptions(self):
        for prefix in ['pmg0','pfh0']:
            fixture_declaration({'sourcePrefix':prefix,'equipmentFixtures':['chest','hand']},
                {'fixtures':[{'fixturePath':'/fixtures/chest'},{'fixturePath':'/fixtures/hand'}]},
                {'sourcePrefix':prefix,'overridesDisabled':True})
        with self.assertRaises(ValueError):fixture_declaration({'sourcePrefix':'pfh0','equipmentFixtures':['hand']},
            {'fixtures':[{'fixturePath':'/fixtures/chest'}]},{'sourcePrefix':'pfh0','overridesDisabled':True})

if __name__=='__main__':unittest.main()
