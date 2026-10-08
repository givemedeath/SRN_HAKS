"""Portable native wire-layout and strict executed-overlay regressions.

Fixtures use declarative binary records; construction never calls the decoder.
Only fixed real-source identity hashes are substituted. Structural guards and
the actual target/stock-reference loader execute unchanged.
"""
import copy
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import target_animation_overlay as overlay
import target_contract as contract

# Offsets are relative to model data after the three-DWORD file header.
MODEL={'size':0xe8,'name':8,'root':0x48,'count':0x4c,'class':0x72,
       'animations':0x78,'scale':0xa4,'parent':0xa8}
CLIP={'size':0xc4,'name':8,'root':0x48,'count':0x4c,'length':0x70,
      'transition':0x74,'animroot':0x78,'events':0xb8}
NODE={'size':0x70,'name':0x20,'children':0x48,'keys':0x54,'floats':0x60,'flags':0x6c}
MESH={'size':0x270,'faces':0x78,'textures':0xe8,'vertices':0x230}
DANGLY={'size':0x288,'constraints':0x270,'parameters':0x27c}
PART_JOINTS={'chest':'torso_g','pelvis':'pelvis_g','neck':'neck_g','head':'head_g',
 'bicepl':'lbicep_g','bicepr':'rbicep_g','forel':'lforearm_g','forer':'rforearm_g',
 'handl':'lhand_g','handr':'rhand_g','legl':'lthigh_g','legr':'rthigh_g',
 'shinl':'lshin_g','shinr':'rshin_g','footl':'lfoot_g','footr':'rfoot_g'}
ALTERED={'pelvis_g','lthigh_g','rthigh_g','lshin_g','rshin_g','lfoot_g','rfoot_g'}
COMPILER_SHA='3b7cb1252e0edb2ce22d7971f333aade027039ae30a45b4bc64732c3e6bec73a'
PLAN_SHA='80ffdd796de4fd8abed6fc017beef162888e6eaeff052f1596ce5cb5c9ec0c32'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def pin(path):return {'path':str(Path(path).resolve()),'sha256':sha(path)}
def control(typ,values,times=None):
    return {'type':typ,'values':values,'times':list(times) if times is not None else [0.0]*len(values)}


class NativeFixture:
    """Independent declarative wire writer with construction mutation locations."""
    def __init__(self,name,geometry,clips=(),parent='a_fa',raw=b''):
        self.data=bytearray(MODEL['size']);self.raw=raw;self.locations={};self.clips={}
        self.text(MODEL['name'],64,name);self.text(MODEL['parent'],64,parent)
        self.put('<B',MODEL['class'],4);self.put('<f',MODEL['scale'],1)
        root,count=self.tree(geometry,'geometry');self.put('<II',MODEL['root'],root,count)
        pointers=[]
        for clip in clips:
            at=self.allocate(bytes(CLIP['size']));self.clips[clip['name']]=at
            self.text(at+CLIP['name'],64,clip['name']);self.text(at+CLIP['animroot'],64,'rootdummy')
            self.put('<ff',at+CLIP['length'],1,0.25)
            root,count=self.tree(clip['nodes'],clip['name']);self.put('<II',at+CLIP['root'],root,count)
            events=b''.join(struct.pack('<f32s',t,n.encode()) for t,n in clip.get('events',[(0.25,'loop')]))
            self.array(at+CLIP['events'],events,36);pointers.append(at)
        self.array(MODEL['animations'],b''.join(struct.pack('<I',p) for p in pointers),4)

    def allocate(self,payload):
        self.data.extend(b'\0'*(-len(self.data)%4));at=len(self.data);self.data.extend(payload);return at

    def put(self,fmt,at,*values):struct.pack_into(fmt,self.data,at,*values)

    def text(self,at,width,value):
        data=value.encode('ascii')
        if len(data)>=width:raise ValueError('Fixture wire name too long')
        self.data[at:at+width]=data+b'\0'*(width-len(data))

    def array(self,at,payload,width):
        count=len(payload)//width
        if len(payload)!=count*width:raise ValueError('Fixture record size differs')
        start=self.allocate(payload) if payload else 0
        self.put('<III',at,start,count,count);return start

    def tree(self,specs,namespace):
        offsets={}
        for spec in specs:
            flag=spec.get('flags',1)
            width=DANGLY['size'] if flag==289 else MESH['size'] if flag==33 else NODE['size']
            offsets[spec['name']]=self.allocate(bytes(width))
        for spec in specs:
            at=offsets[spec['name']];self.text(at+NODE['name'],32,spec['name'])
            self.put('<I',at+NODE['flags'],spec.get('flags',1))
            children=spec.get('children',[row['name'] for row in specs if row.get('parent')==spec['name']])
            child_at=self.array(at+NODE['children'],b''.join(struct.pack('<I',offsets[n]) for n in children),4)
            values=[];keys=[];spans={}
            for c in spec.get('controls',[]):
                times=c['times'];rows=c['values'];width=len(rows[0])
                if len(times)!=len(rows) or any(len(row)!=width for row in rows):raise ValueError('Fixture grid differs')
                t=len(values);values.extend(times);v=len(values);values.extend(x for row in rows for x in row)
                keys.append(struct.pack('<ihhhbb',c['type'],len(rows),t,v,width,0))
                spans[c['type']]=(t,v,len(rows),width)
            key_at=self.array(at+NODE['keys'],b''.join(keys),12)
            float_at=self.array(at+NODE['floats'],struct.pack('<'+'f'*len(values),*values),4)
            ranges={typ:{'timeRange':[12+float_at+4*t,12+float_at+4*(t+rows)],
                         'dataRange':[12+float_at+4*v,12+float_at+4*(v+rows*width)]}
                    for typ,(t,v,rows,width) in spans.items()}
            self.locations[(namespace,spec['name'])]={'node':at,'children':child_at,'keys':key_at,
                                                      'floats':float_at,'ranges':ranges}
            if spec.get('flags',1) in (33,289):
                self.array(at+MESH['faces'],bytes(32*spec.get('faces',0)),32)
                self.put('<HH',at+MESH['vertices'],spec.get('vertices',0),1)
                for i in range(4):self.text(at+MESH['textures']+i*64,64,spec.get('texture','') if i==0 else '')
                if spec['flags']==289:
                    self.array(at+DANGLY['constraints'],struct.pack('<2f',0,1),4)
                    self.put('<3f',at+DANGLY['parameters'],0.1,0.2,0.3)
        roots=[row for row in specs if row.get('parent') is None]
        if len(roots)!=1:raise ValueError('Fixture must have one tree root')
        return offsets[roots[0]['name']],len(specs)

    def blob(self):return struct.pack('<III',0,len(self.data),len(self.raw))+bytes(self.data)+self.raw


def sample_native(mesh=None):
    geometry=[{'name':'a_test','parent':None,'controls':[control(36,[[1]])]},
              {'name':'rootdummy','parent':'a_test','controls':[control(8,[[0,0,0]]),control(20,[[0,0,0,1]])]}]
    if mesh is not None:
        geometry.append({'name':'cloth','parent':'rootdummy','flags':mesh,'faces':1,'vertices':3,'texture':'pfh0_robe030'})
    animated=[{'name':'a_test','parent':None,'controls':[]},
              {'name':'rootdummy','parent':'a_test','controls':[
                  control(8,[[0,0,0],[1,2,3]],[0,1]),control(20,[[0,0,0,1],[0,0,0,1]],[0,1])]}]
    return NativeFixture('a_test',geometry,[{'name':name,'nodes':copy.deepcopy(animated)} for name in ('pause1','pause2')])


class NativeIdleReaderTests(unittest.TestCase):
    def test_character_controllers_names_and_absolute_file_ranges(self):
        f=sample_native();d=overlay.NativeIdleReader(f.blob()).decode()
        self.assertEqual((d['name'],d['parent'],d['scale']),('a_test','a_fa',1))
        self.assertEqual(set(d['nodes']),{'a_test','rootdummy'});self.assertEqual(set(d['clips']),{'pause1','pause2'})
        c=d['clips']['pause1']['nodes']['rootdummy']['controls'][8]
        np.testing.assert_array_equal(c['times'],[0,1]);np.testing.assert_array_equal(c['values'],[[0,0,0],[1,2,3]])
        self.assertEqual(c['dataRange'],tuple(f.locations[('pause1','rootdummy')]['ranges'][8]['dataRange']))
        a,b=c['dataRange'];self.assertEqual(f.blob()[a:b],struct.pack('<6f',0,0,0,1,2,3))
        self.assertEqual(d['clips']['pause1']['events'],[(0.25,'loop')])
        self.assertEqual(set(overlay.NativeIdleReader(f.blob()).decode({'pause2'})['clips']),{'pause2'})

    def test_mesh_and_dangly_metadata(self):
        for flags in (33,289):
            with self.subTest(flags=flags):
                m=overlay.NativeIdleReader(sample_native(flags).blob()).decode()['nodes']['cloth']['mesh']
                self.assertEqual((m['faces'],m['vertices'],m['textureCount']),(1,3,1))
                self.assertEqual(m['textures'][0],'pfh0_robe030')
                if flags==289:self.assertEqual(m['danglyConstraints'],2);np.testing.assert_allclose(m['danglyParameters'],[0.1,0.2,0.3])

    def test_truncation_prefix_and_section_size_corruption(self):
        blob=sample_native().blob()
        for data in (blob[:20],blob[:-1],struct.pack('<I',1)+blob[4:],
                     blob[:4]+struct.pack('<I',len(blob))+blob[8:],blob[:8]+struct.pack('<I',7)+blob[12:]):
            with self.subTest(bytes=len(data)),self.assertRaises(ValueError):overlay.NativeIdleReader(data).decode()

    def test_model_class_root_pointer_and_understated_count(self):
        for at,fmt,value in ((MODEL['class'],'<B',2),(MODEL['root'],'<I',0xffffffff),(MODEL['count'],'<I',1)):
            f=sample_native();f.put(fmt,at,value)
            with self.subTest(at=at),self.assertRaises(ValueError):overlay.NativeIdleReader(f.blob()).decode()

    def test_child_animation_and_event_arrays(self):
        for which in ('capacity','child-array','child-pointer','animations','events'):
            f=sample_native();root=f.locations[('geometry','a_test')]
            if which=='capacity':f.put('<I',root['node']+NODE['children']+8,0)
            elif which=='child-array':f.put('<I',root['node']+NODE['children'],0xffffffff)
            elif which=='child-pointer':f.put('<I',root['children'],0xffffffff)
            elif which=='animations':f.put('<I',MODEL['animations'],0xffffffff)
            else:f.put('<I',f.clips['pause1']+CLIP['events'],0xffffffff)
            with self.subTest(which=which),self.assertRaises(ValueError):overlay.NativeIdleReader(f.blob()).decode()

    def test_cycles_shared_children_duplicate_names_wrong_flags_and_unterminated_names(self):
        for which in ('cycle','shared','duplicate','flags','name'):
            f=sample_native();root=f.locations[('geometry','a_test')];child=f.locations[('geometry','rootdummy')]
            if which=='cycle':f.put('<I',root['children'],root['node'])
            elif which=='shared':f.array(root['node']+NODE['children'],struct.pack('<2I',child['node'],child['node']),4)
            elif which=='duplicate':f.text(child['node']+NODE['name'],32,'a_test')
            elif which=='flags':f.put('<I',child['node']+NODE['flags'],17)
            else:f.data[child['node']+NODE['name']:child['node']+NODE['name']+32]=b'z'*32
            with self.subTest(which=which),self.assertRaises(ValueError):overlay.NativeIdleReader(f.blob()).decode()

    def test_key_float_arrays_controller_shapes_offsets_and_duplicate_types(self):
        for which in ('key-range','float-range','capacity','rows','columns','time','value','duplicate'):
            f=sample_native();a=f.locations[('pause1','rootdummy')]
            if which=='key-range':f.put('<I',a['node']+NODE['keys'],0xffffffff)
            elif which=='float-range':f.put('<I',a['node']+NODE['floats'],0xffffffff)
            elif which=='capacity':f.put('<I',a['node']+NODE['keys']+8,1)
            elif which=='rows':f.put('<h',a['keys']+4,-1)
            elif which=='columns':f.put('<b',a['keys']+10,0)
            elif which=='time':f.put('<h',a['keys']+6,-1)
            elif which=='value':f.put('<h',a['keys']+8,32767)
            else:f.put('<i',a['keys']+12,8)
            with self.subTest(which=which),self.assertRaises(ValueError):overlay.NativeIdleReader(f.blob()).decode()

    def test_nonfinite_controller_values_and_descending_times(self):
        for which in ('nan','inf','order'):
            f=sample_native();a=f.locations[('pause1','rootdummy')]
            f.put('<f',a['floats']+(8 if which=='nan' else 0 if which=='inf' else 4),
                  float('nan') if which=='nan' else float('inf') if which=='inf' else -1)
            with self.subTest(which=which),self.assertRaises(ValueError):overlay.NativeIdleReader(f.blob()).decode()

    def test_nonfinite_model_scale(self):
        for value in (float('nan'),float('inf'),float('-inf')):
            f=sample_native();f.put('<f',MODEL['scale'],value)
            with self.subTest(value=value),self.assertRaisesRegex(ValueError,'Nonfinite native model scale'):
                overlay.NativeIdleReader(f.blob()).decode()

    def test_nonfinite_animation_metadata(self):
        for field in ('length','transition','event-time'):
            for value in (float('nan'),float('inf'),float('-inf')):
                f=sample_native();clip=f.clips['pause1']
                at=clip+CLIP[field] if field!='event-time' else struct.unpack_from('<I',f.data,clip+CLIP['events'])[0]
                f.put('<f',at,value)
                with self.subTest(field=field,value=value),self.assertRaisesRegex(ValueError,'Nonfinite native animation metadata'):
                    overlay.NativeIdleReader(f.blob()).decode()

    def test_nonfinite_dangly_metadata(self):
        for component in range(3):
            for value in (float('nan'),float('inf'),float('-inf')):
                f=sample_native(289);node=f.locations[('geometry','cloth')]['node']
                f.put('<f',node+DANGLY['parameters']+4*component,value)
                with self.subTest(component=component,value=value),self.assertRaisesRegex(ValueError,'Nonfinite native dangly parameters'):
                    overlay.NativeIdleReader(f.blob()).decode()

    def test_finite_metadata_is_retained_exactly(self):
        f=sample_native(289);f.put('<f',MODEL['scale'],0.75)
        clip=f.clips['pause1'];f.put('<ff',clip+CLIP['length'],2.5,0.125)
        event=struct.unpack_from('<I',f.data,clip+CLIP['events'])[0];f.put('<f',event,0.5)
        node=f.locations[('geometry','cloth')]['node'];f.put('<fff',node+DANGLY['parameters'],0.375,0.625,0.875)
        d=overlay.NativeIdleReader(f.blob()).decode()
        self.assertEqual(d['scale'],0.75)
        self.assertEqual((d['clips']['pause1']['length'],d['clips']['pause1']['transition']),(2.5,0.125))
        self.assertEqual(d['clips']['pause1']['events'],[(0.5,'loop')])
        self.assertEqual(d['nodes']['cloth']['mesh']['danglyParameters'],(0.375,0.625,0.875))

    def test_duplicate_clips_and_understated_animation_tree(self):
        for which in ('duplicate','count'):
            f=sample_native()
            if which=='duplicate':f.text(f.clips['pause2']+CLIP['name'],64,'pause1')
            else:f.put('<I',f.clips['pause1']+CLIP['count'],1)
            with self.subTest(which=which),self.assertRaises(ValueError):overlay.NativeIdleReader(f.blob()).decode()


class SyntheticOverlay:
    """Complete synthetic 56-owner, 16-edited, 84-unedited overlay closure."""
    def __init__(self,root):
        self.root=Path(root);self.fillers=['fixture'+str(i).zfill(2) for i in range(38)]
        self.names=['rootdummy',*PART_JOINTS.values(),*self.fillers]
        self.parents={name:'rootdummy' for name in self.names};self.parents['rootdummy']=None
        self.parents.update({'lthigh_g':'pelvis_g','rthigh_g':'pelvis_g',
            'lshin_g':'lthigh_g','rshin_g':'rthigh_g','lfoot_g':'lshin_g','rfoot_g':'rshin_g'})
        self.source_root=self.root/'installed-root.mdl'
        lines=['newmodel pfh0','setsupermodel pfh0 a_fa','setanimationscale 1','beginmodelgeom pfh0',
               'node dummy pfh0',' parent NULL',' position 0 0 0',' orientation 0 0 0 0','endnode']
        for name in self.names:
            lines+=['node dummy '+name,' parent '+(self.parents[name] or 'pfh0'),
                    ' position 0 0 0',' orientation 0 0 0 0','endnode']
        lines+=['endmodelgeom pfh0','donemodel pfh0']
        self.source_root.write_text('\n'.join(lines)+'\n',encoding='ascii')
        self.root_resource=self.root/'pfh0.mdl'
        self.root_resource.write_bytes(self.source_root.read_bytes().replace(b'pfh0 a_fa',b'pfh0 srn_fa_h0',1))
        self.source_fixture=self.character('a_fa',True)
        self.candidate_fixture=self.character('srn_fa_h0',False)
        self.source_native=self.root/'a_fa.mdl';self.source_native.write_bytes(self.source_fixture.blob())
        self.result=self.root/'srn_fa_h0.mdl';self.result.write_bytes(self.candidate_fixture.blob())
        self.parent_native=self.root/'compiler-parent.mdl'
        parent=bytearray(self.result.read_bytes())
        self.source_span=self.source_fixture.locations[('pause1','fixture00')]['ranges'][8]['dataRange']
        self.destination_span=self.candidate_fixture.locations[('pause1','fixture00')]['ranges'][8]['dataRange']
        struct.pack_into('<f',parent,self.destination_span[0],99)
        self.parent_native.write_bytes(parent)
        self.numeric=self.root/'corrected-arrays.npz';np.savez(self.numeric,**self.corrected_arrays)
        self.fixed_hashes={'ROOT_SHA':sha(self.source_root),'SOURCE_SHA':sha(self.source_native),'NUMERIC_SHA':sha(self.numeric)}
        self.target_path=self.root/'target.json'
        frames={name:np.eye(4).tolist() for name in ['pfh0',*self.names]}
        stock=self.root/'stock-reference.json'
        stock.write_text(json.dumps({'kind':'stock-target-reference','pass':True,'prefix':'pfh0',
            'heightMeters':1.8,'frames':frames,'rootAscii':pin(self.source_root),
            'frozenInputs':{str(self.source_root.resolve()):sha(self.source_root)}}))
        self.target={'schemaVersion':2,'kind':'phenotype-target','id':'human-female-fit-purposebuilt-v1',
            'identity':{'race':'human','gender':'female','prefix':'pfh0','phenotype':0,'raceId':6,'appearanceRow':6},
            'heightMeters':1.8,'workingHeightMeters':1.8,
            'rig':{'mode':'stock-exact','revision':'synthetic-installed-frame-basis','sourcePrefix':'pfh0',
                'runtimeScale':1,'positionPolicy':'stock-exact','preserveRotations':True,'preserveTimingEvents':True,
                'frames':{'working':frames,'runtime':copy.deepcopy(frames)},'stockReferenceReceipt':pin(stock)},
            'models':{part:'pfh0_'+part+'001' for part in PART_JOINTS},
            'material':{'fixedGarmentParts':['chest','pelvis']},'frozenInputs':{}}
        self.target_path.write_text(json.dumps(self.target))
        self.documents={name:self.root/(name+'.json') for name in (
            'preparation','compile','execution','rangePlan','restoration','independentReview')}
        self.preparation={'kind':'one-human-source-native-carrier-preparation','unchangedControlCount':84,
            'frozenCompilePlan':{'sha256':PLAN_SHA},
            'client':{'path':str(self.root/'unlaunchable-compiler.exe'),'sha256':COMPILER_SHA}}
        self.execution={'compileCalls':1,'exitCode':0,'interactiveClientLaunched':False,
            'command':[self.preparation['client']['path'],'-convertmdls','fixture-only']}
        self.plan={'kind':'independent-human-source-native-restoration-plan','pass':True,'executed':False,
            'rows':[{'clip':'pause1','node':'fixture00','type':8,
                     'sourceRange':self.source_span,'destinationRange':self.destination_span}]}
        self.review={'kind':'independent-human-source-native-posture-review','pass':True,
            'uneditedControllers':84,'editedControllers':16,'staticOwners':56,'clientEvidence':False,
            'phase':'after-restoration','allUneditedNativePayloadsExact':True,
            'outsideRestorationRangesByteExact':True,'pendingRestoration':False,'editedTimestampWordsExact':True}
        self.receipt_path=self.root/'overlay.json';self.refresh()

    def character(self,name,source):
        static=[control(8,[[0,0,0]]),control(20,[[0,0,0,1]]),control(36,[[1]])]
        geometry=[{'name':name,'parent':None,'controls':copy.deepcopy(static)}]
        for node in self.names:
            geometry.append({'name':node,'parent':self.parents[node] or name,'controls':copy.deepcopy(static)})
        if source:geometry.append({'name':'belt_pelvis','parent':'pelvis_g','flags':33,
                                   'faces':100,'vertices':152,'texture':'pfh0_robe030'})
        clips=[]
        if not source:self.corrected_arrays={}
        unedited=set(self.fillers)|{'torso_g','neck_g','head_g','lbicep_g'}
        for clip in ('pause1','pause2'):
            specs=[{'name':name,'parent':None,'controls':[]}]
            for node in self.names:
                controls=[]
                if node=='rootdummy':
                    values=[[0,0,1],[0 if source else 0.01,0,1]];controls.append(control(8,values,[0,1]))
                elif node in ALTERED:
                    values=[[0,0,0,1],[0,0,0 if source else 0.01,1]];controls.append(control(20,values,[0,1]))
                if not source and (node=='rootdummy' or node in ALTERED):
                    prefix='pfh0|'+clip+'|'+node
                    self.corrected_arrays[prefix+'|times']=np.array([0,1],dtype='<f4')
                    self.corrected_arrays[prefix+'|values']=np.array(values,dtype='<f4')
                if node in unedited:controls.append(control(8,[[1,2,3],[4,5,6]],[0,1]))
                specs.append({'name':node,'parent':self.parents[node] or name,'controls':controls})
            clips.append({'name':clip,'nodes':specs})
        return NativeFixture(name,geometry,clips,parent='a_ba' if source else 'a_fa')

    def write(self,name,value):
        path=self.documents[name];path.write_text(json.dumps(value));return pin(path)

    def refresh(self):
        prep=self.write('preparation',self.preparation);execution=self.write('execution',self.execution)
        compilation=self.write('compile',{'kind':'one-human-source-native-compile',
            'preparation':prep,'execution':execution,'native':pin(self.parent_native)})
        plan=copy.deepcopy(self.plan)
        plan.update(sourceNativeOriginal=pin(self.source_native),parentNative=pin(self.parent_native),
                    expectedResultSha256=sha(self.result))
        for row in plan['rows']:
            a,b=row['sourceRange'];c,d=row['destinationRange']
            row['sourceBytesSHA256']=hashlib.sha256(self.source_native.read_bytes()[a:b]).hexdigest()
            row['destinationBytesSHA256']=hashlib.sha256(self.parent_native.read_bytes()[c:d]).hexdigest()
        range_plan=self.write('rangePlan',plan)
        restoration=self.write('restoration',{'kind':'executed-human-source-native-payload-restoration',
            'source':pin(self.source_native),'parentNative':pin(self.parent_native),'rangePlan':range_plan,'native':pin(self.result)})
        review=copy.deepcopy(self.review)
        review.update(compile=compilation,native=pin(self.result),numericArchive=pin(self.numeric),
            executedRestorationReceipt=restoration,originalSourceOwner=pin(self.source_native),root=pin(self.source_root))
        self.receipt={'schemaVersion':1,'kind':overlay.KIND,'executed':True,'clientAccepted':False,
            'runtimeSelected':False,'scope':'single-human-posture-diagnostic',
            **contract.binding(self.target_path,self.target,'runtime'),
            'resources':{'pfh0.mdl':pin(self.root_resource),'srn_fa_h0.mdl':pin(self.result)},
            'sourceRoot':pin(self.source_root),'sourceNativeOwner':pin(self.source_native),
            'numericCorrectedArrays':pin(self.numeric),'compile':compilation,'preparation':prep,
            'rangePlan':range_plan,'restoration':restoration,'independentReview':self.write('independentReview',review)}
        self.write_receipt()

    def write_receipt(self):self.receipt_path.write_text(json.dumps(self.receipt))

    def verify(self):
        with patch.multiple(overlay,**self.fixed_hashes):
            return overlay.verify_animation_overlay(pin(self.receipt_path),self.target_path)

    def mutate_candidate(self,offset,payload,include_parent=True):
        for path in [self.result,self.parent_native] if include_parent else [self.result]:
            data=bytearray(path.read_bytes());data[offset:offset+len(payload)]=payload;path.write_bytes(data)
        self.refresh()


class ExecutedOverlayGuardTests(unittest.TestCase):
    def setUp(self):
        # Exercise real containment and target validation in isolated temporary
        # files. No installed asset, existing receipt or structural mock is used.
        area=Path(overlay.__file__).resolve().parents[2]/'output/phenotypes/human-female-fit-purposebuilt-v1'
        area.mkdir(parents=True,exist_ok=True)
        temporary=tempfile.TemporaryDirectory(prefix='synthetic-overlay-test-',dir=area)
        self.addCleanup(temporary.cleanup);self.fixture=SyntheticOverlay(Path(temporary.name))

    def test_complete_synthetic_overlay_without_structural_mocks(self):
        self.assertEqual(PART_JOINTS,contract.PART_JOINTS)
        self.assertEqual(len(contract.load(self.fixture.target_path)['rig']['frames']['working']),56)
        result=self.fixture.verify()
        self.assertEqual((result['editedControllers'],result['uneditedControllers']),(16,84))
        self.assertEqual(set(result['resourceHashes']),{'pfh0.mdl','srn_fa_h0.mdl'})
        self.assertTrue(result['staticFramesExact'])
        self.assertFalse(result['clientAccepted']);self.assertFalse(result['runtimeSelected']);self.assertFalse(result['productionAccepted'])
        self.assertTrue({str(path.resolve()) for path in self.fixture.documents.values()}<=set(result['frozenInputs']))

    def test_kind_scope_executed_and_acceptance_flags(self):
        original=copy.deepcopy(self.fixture.receipt)
        for key,value in (('kind','UNEXECUTED-plan'),('schemaVersion',2),('executed',1),
                          ('scope','global-production'),('runtimeSelected',True),('clientAccepted',True)):
            with self.subTest(key=key,value=value):
                self.fixture.receipt={**original,key:value};self.fixture.write_receipt()
                with self.assertRaises(ValueError):self.fixture.verify()

    def test_target_space_revision_and_two_resource_ownership(self):
        original=copy.deepcopy(self.fixture.receipt)
        for key,value in (('targetId','other'),('coordinateSpace','working'),('rigRevision','other'),
                          ('targetContractSha256','a'*64)):
            with self.subTest(key=key):
                self.fixture.receipt={**original,key:value};self.fixture.write_receipt()
                with self.assertRaisesRegex(ValueError,'another target'):self.fixture.verify()
        self.fixture.receipt=original;self.fixture.receipt['resources']['a_fa.mdl']=pin(self.fixture.source_native)
        self.fixture.write_receipt()
        with self.assertRaisesRegex(ValueError,'two-resource'):self.fixture.verify()

    def test_stale_digest_and_outside_target_pins(self):
        original=copy.deepcopy(self.fixture.receipt)
        self.fixture.receipt['compile']['sha256']='a'*64;self.fixture.write_receipt()
        with self.assertRaisesRegex(ValueError,'changed or outside'):self.fixture.verify()
        self.fixture.receipt=original
        outside=self.fixture.root.parent.parent/('outside-'+self.fixture.root.name+'.json')
        outside.write_text('{}');self.addCleanup(outside.unlink)
        self.fixture.receipt['compile']=pin(outside);self.fixture.write_receipt()
        with self.assertRaisesRegex(ValueError,'changed or outside'):self.fixture.verify()

    def test_compile_scalars_have_exact_types_and_no_interactive_launch(self):
        original=copy.deepcopy(self.fixture.execution)
        for key,value in (('compileCalls',True),('compileCalls',2),('exitCode',False),
                          ('exitCode',1),('interactiveClientLaunched',0),('interactiveClientLaunched',True)):
            with self.subTest(key=key,value=value):
                self.fixture.execution={**original,key:value};self.fixture.refresh()
                with self.assertRaisesRegex(ValueError,'compiler execution'):self.fixture.verify()

    def test_plan_flags_and_pending_or_inexact_final_review(self):
        self.fixture.plan['executed']=True;self.fixture.refresh()
        with self.assertRaisesRegex(ValueError,'restoration plan'):self.fixture.verify()
        self.fixture.plan['executed']=False;self.fixture.review['pendingRestoration']=True;self.fixture.refresh()
        with self.assertRaisesRegex(ValueError,'independent native review'):self.fixture.verify()
        self.fixture.review['pendingRestoration']=False;self.fixture.review['editedTimestampWordsExact']=False;self.fixture.refresh()
        with self.assertRaisesRegex(ValueError,'independent native review'):self.fixture.verify()

    def test_root_changes_exceeding_parent_token(self):
        self.fixture.root_resource.write_bytes(self.fixture.root_resource.read_bytes()+b'\n# extra\n');self.fixture.refresh()
        with self.assertRaisesRegex(ValueError,'one parent token'):self.fixture.verify()

    def test_static_zero_time_and_declared_width(self):
        for which in ('time','width'):
            with self.subTest(which=which):
                f=SyntheticOverlay(self.fixture.root);at=f.candidate_fixture.locations[('geometry','rootdummy')]
                if which=='time':f.mutate_candidate(12+at['floats'],struct.pack('<f',0.5))
                else:f.mutate_candidate(12+at['keys']+10,struct.pack('<b',2))
                with self.assertRaisesRegex(ValueError,'one zero-time key'):f.verify()

    def test_extra_static_rows_do_not_pass_first_row_frame_comparison(self):
        at=self.fixture.candidate_fixture.locations[('geometry','rootdummy')]
        for path in (self.fixture.result,self.fixture.parent_native):
            data=bytearray(path.read_bytes())
            start=len(data)-12
            data+=struct.pack('<15f',0,1,0,0,0,9,9,9,0,0,0,0,1,0,1)
            struct.pack_into('<I',data,4,len(data)-12)
            struct.pack_into('<III',data,12+at['node']+NODE['floats'],start,15,15)
            struct.pack_into('<ihhhbb',data,12+at['keys'],8,2,0,2,3,0)
            struct.pack_into('<ihhhbb',data,12+at['keys']+12,20,1,8,9,4,0)
            struct.pack_into('<ihhhbb',data,12+at['keys']+24,36,1,13,14,1,0)
            path.write_bytes(data)
        self.fixture.refresh()
        with self.assertRaisesRegex(ValueError,'one zero-time key'):self.fixture.verify()

    def test_changed_static_frame_and_header_identity(self):
        at=self.fixture.candidate_fixture.locations[('geometry','rootdummy')]
        self.fixture.mutate_candidate(at['ranges'][8]['dataRange'][0],struct.pack('<f',0.02))
        with self.assertRaisesRegex(ValueError,'static frame'):self.fixture.verify()
        f=SyntheticOverlay(self.fixture.root)
        f.mutate_candidate(12+MODEL['name'],b'wrong_name\0'+b'\0'*(64-11))
        with self.assertRaisesRegex(ValueError,'identity/clips/scale'):f.verify()

    def test_edited_and_unedited_native_payload_corruption(self):
        for node in ('rootdummy','fixture01'):
            with self.subTest(node=node):
                f=SyntheticOverlay(self.fixture.root)
                at=f.candidate_fixture.locations[('pause1',node)]['ranges'][8]['dataRange'][0]
                f.mutate_candidate(at,struct.pack('<f',9))
                with self.assertRaisesRegex(ValueError,'Corrected native controller|Unedited native payload'):f.verify()

    def test_restoration_cannot_touch_edited_controllers(self):
        source=self.fixture.source_fixture.locations[('pause1','rootdummy')]['ranges'][8]['dataRange']
        destination=self.fixture.candidate_fixture.locations[('pause1','rootdummy')]['ranges'][8]['dataRange']
        self.fixture.plan['rows']=[{'clip':'pause1','node':'rootdummy','type':8,'sourceRange':source,'destinationRange':destination}]
        self.fixture.refresh()
        with self.assertRaisesRegex(ValueError,'outside decoded unedited'):self.fixture.verify()

    def test_overlap_and_fractional_source_byte_ranges(self):
        row=copy.deepcopy(self.fixture.plan['rows'][0]);self.fixture.plan['rows'].append(row);self.fixture.refresh()
        with self.assertRaisesRegex(ValueError,'overlap or escape'):self.fixture.verify()
        plan=json.loads(self.fixture.documents['rangePlan'].read_text())
        row['sourceRange']=[float(x) for x in row['sourceRange']];plan['rows']=[row]
        plan_pin=self.fixture.write('rangePlan',plan)
        restoration=json.loads(self.fixture.documents['restoration'].read_text());restoration['rangePlan']=plan_pin
        restoration_pin=self.fixture.write('restoration',restoration)
        review=json.loads(self.fixture.documents['independentReview'].read_text());review['executedRestorationReceipt']=restoration_pin
        self.fixture.receipt.update(rangePlan=plan_pin,restoration=restoration_pin,
                                   independentReview=self.fixture.write('independentReview',review))
        self.fixture.write_receipt()
        with self.assertRaisesRegex(ValueError,'overlap or escape'):self.fixture.verify()


if __name__=='__main__':unittest.main()
