"""Verify an executed two-resource Human posture diagnostic; never approve a client.

The installed root remains the immutable basis. The isolated root differs only
in its supermodel parent token; the carrier owns two native source-driven idles.
"""
from pathlib import Path
import hashlib
import json
import re
import struct

import numpy as np
import target_contract as contract
from retarget import nodes
from rig_pose_audit import quaternion

KIND = 'executed-single-human-source-native-idle-overlay'
NUMERIC_SHA = '0739683550694507f1f4b0ae1152a191a55c0fbe1b9353dc37e0f583fdaa53d1'
ROOT_SHA = '1da54afc5ff270c8c7decc61829df0595c6568d70cdef75026f63d8e94362f51'
SOURCE_SHA = '1f8b1ac2e4ab31e1b2172c7ca208160267cdbf861cd36e544775f391b5b6978d'
ALTERED = {'pelvis_g','lthigh_g','rthigh_g','lshin_g','rshin_g','lfoot_g','rfoot_g'}

class NativeIdleReader:
    """Bounded native character/controller decoding without decompilation."""
    def __init__(self, blob):
        self.blob = blob
        contract.require(len(blob) >= 12+0xe8, 'Truncated native character')
        zero,self.size,self.raw = struct.unpack_from('<III',blob)
        contract.require(zero == 0 and len(blob) == 12+self.size+self.raw, 'Native sections differ')
    def data(self, offset, width):
        contract.require(offset >= 0 and width >= 0 and offset+width <= self.size, 'Native range outside model')
        return self.blob[12+offset:12+offset+width]
    def u32(self, offset):
        return struct.unpack('<I', self.data(offset,4))[0]
    def text(self, offset, width):
        value = self.data(offset,width)
        contract.require(b'\0' in value, 'Unterminated native name')
        return value.split(b'\0',1)[0].decode('ascii').lower()
    def array(self, offset, width):
        start,count,capacity = struct.unpack('<III',self.data(offset,12))
        contract.require(count <= capacity, 'Native array exceeds capacity')
        self.data(start,count*width)
        return start,count
    def tree(self, offset):
        queue=[(offset,None)];seen=set();result={}
        while queue:
            offset,parent=queue.pop()
            contract.require(offset not in seen, 'Shared or cyclic native nodes')
            seen.add(offset);self.data(offset,0x70)
            name=self.text(offset+0x20,32);flags=self.u32(offset+0x6c)
            contract.require(name not in result and flags in (1,33,289), 'Duplicate/unsupported native node')
            children,count=self.array(offset+0x48,4)
            keys,key_count=self.array(offset+0x54,12)
            floats,float_count=self.array(offset+0x60,4)
            values=np.frombuffer(self.data(floats,float_count*4),'<f4')
            contract.require(np.isfinite(values).all(), 'Nonfinite native controller')
            controllers={}
            for i in range(key_count):
                typ,rows,time_offset,value_offset,columns,pad=struct.unpack('<ihhhbb',self.data(keys+i*12,12))
                contract.require(typ not in controllers and rows > 0 and 0 < columns <= 16
                    and time_offset >= 0 and value_offset >= 0 and time_offset+rows <= float_count
                    and value_offset+rows*columns <= float_count, 'Native controller shape/offset differs')
                times=values[time_offset:time_offset+rows];data=values[value_offset:value_offset+rows*columns].reshape(rows,columns)
                contract.require(np.all(np.diff(times.astype(float)) >= 0), 'Native controller times unordered')
                controllers[typ]={'times':times,'values':data,
                    'timeRange':(12+floats+4*time_offset,12+floats+4*(time_offset+rows)),
                    'dataRange':(12+floats+4*value_offset,12+floats+4*(value_offset+rows*columns))}
            mesh=None
            if flags != 1:
                self.data(offset,0x288 if flags==289 else 0x270)
                _,faces=self.array(offset+0x78,32)
                vertices,texture_count=struct.unpack('<HH',self.data(offset+0x230,4))
                mesh={'faces':faces,'vertices':vertices,'textureCount':texture_count,
                    'textures':[self.text(offset+0xe8+64*i,64) for i in range(4)]}
                if flags==289:
                    _,constraints=self.array(offset+0x270,4)
                    mesh['danglyConstraints']=constraints
                    mesh['danglyParameters']=struct.unpack('<fff',self.data(offset+0x27c,12))
                    contract.require(np.isfinite(mesh['danglyParameters']).all(), 'Nonfinite native dangly parameters')
            result[name]={'parent':parent,'flags':flags,'controls':controllers,'mesh':mesh}
            queue.extend((self.u32(children+4*i),name) for i in range(count))
        return result
    def decode(self, selected=None):
        contract.require(self.data(0x72,1)==b'\4', 'Native model must be character')
        scale=struct.unpack('<f',self.data(0xa4,4))[0]
        contract.require(np.isfinite(scale), 'Nonfinite native model scale')
        geometry=self.tree(self.u32(0x48))
        contract.require(len(geometry) <= self.u32(0x4c), 'Native node metadata understates graph')
        pointers,count=self.array(0x78,4);clips={};all_names=set()
        for i in range(count):
            at=self.u32(pointers+4*i);self.data(at,0xc4);name=self.text(at+8,64)
            contract.require(name not in all_names,'Duplicate native clip');all_names.add(name)
            if selected is not None and name not in selected:continue
            event_at,event_count=self.array(at+0xb8,36)
            events=[(struct.unpack('<f',self.data(event_at+36*j,4))[0],self.text(event_at+36*j+4,32)) for j in range(event_count)]
            length,transition=struct.unpack('<ff',self.data(at+0x70,8))
            contract.require(np.isfinite([length,transition]).all()
                and all(np.isfinite(time) for time,_ in events), 'Nonfinite native animation metadata')
            clips[name]={'length':length,'transition':transition,
                'animroot':self.text(at+0x78,64),'events':events,'nodes':self.tree(self.u32(at+0x48))}
            contract.require(len(clips[name]['nodes']) <= self.u32(at+0x4c), 'Native clip metadata understates graph')
        return {'name':self.text(8,64),'parent':self.text(0xa8,64),
            'scale':scale,'nodes':geometry,'clips':clips}

def verify_animation_overlay(receipt_pin, target_path):
    """Recheck actual source/root/native bytes; diagnostic-only two-file ownership."""
    repo=Path(__file__).resolve().parents[2];target_path=Path(target_path).resolve()
    target=contract.load(target_path);identity=target['identity']
    contract.require(target['id']=='human-female-fit-purposebuilt-v1' and contract.rig_mode(target)=='stock-exact'
        and identity['prefix']=='pfh0' and identity['gender']=='female' and identity['raceId']==identity['appearanceRow']==6
        and identity['phenotype']==0 and target['rig']['runtimeScale']==1, 'Overlay target must be stock-exact female Human')
    area=repo/'output/phenotypes'/target['id'];frozen={str(target_path):contract.sha(target_path),str(Path(__file__).resolve()):contract.sha(__file__)}
    def pinned(row, expected=None):
        contract.require(isinstance(row,dict) and set(row)=={'path','sha256'}, 'Exact overlay file pin required')
        path=Path(row['path']).resolve();digest=row['sha256']
        contract.require(path.is_relative_to(area) and path.is_file() and re.fullmatch('[0-9a-f]{64}',digest)
            and (expected is None or digest==expected) and contract.sha(path)==digest, 'Overlay pin changed or outside target')
        key=str(path);contract.require(key not in frozen or frozen[key]==digest, 'Conflicting overlay pin')
        frozen[key]=digest;return path
    receipt_path=pinned(receipt_pin);receipt=json.loads(receipt_path.read_text(encoding='utf-8'))
    contract.require(receipt.get('schemaVersion')==1 and receipt.get('kind')==KIND
        and receipt.get('executed') is True and receipt.get('clientAccepted') is False
        and receipt.get('runtimeSelected') is False and receipt.get('scope')=='single-human-posture-diagnostic',
        'Executed single-Human diagnostic receipt required')
    contract.verify_binding(receipt,target_path,target,'runtime')
    contract.require(set(receipt['resources'])=={'pfh0.mdl','srn_fa_h0.mdl'}, 'Exact two-resource animation ownership required')
    paths={name:pinned(row) for name,row in receipt['resources'].items()}
    source_root=pinned(receipt['sourceRoot'],ROOT_SHA)
    source_native=pinned(receipt['sourceNativeOwner'],SOURCE_SHA)
    numeric=pinned(receipt['numericCorrectedArrays'],NUMERIC_SHA)
    compile_path=pinned(receipt['compile']);prep_path=pinned(receipt['preparation'])
    review_path=pinned(receipt['independentReview']);restoration_path=pinned(receipt['restoration']);plan_path=pinned(receipt['rangePlan'])
    compilation=json.loads(compile_path.read_text());prep=json.loads(prep_path.read_text())
    review=json.loads(review_path.read_text());restoration=json.loads(restoration_path.read_text());plan=json.loads(plan_path.read_text())
    contract.require(compilation.get('kind')=='one-human-source-native-compile' and compilation.get('preparation')==receipt['preparation']
        and prep.get('kind')=='one-human-source-native-carrier-preparation' and prep.get('unchangedControlCount')==84
        and prep.get('frozenCompilePlan',{}).get('sha256')=='80ffdd796de4fd8abed6fc017beef162888e6eaeff052f1596ce5cb5c9ec0c32',
        'Source-native compile/preparation closure differs')
    execution_path=pinned(compilation['execution'])
    execution=json.loads(execution_path.read_text())
    compiler_sha=prep['client']['sha256']
    contract.require(compiler_sha=='3b7cb1252e0edb2ce22d7971f333aade027039ae30a45b4bc64732c3e6bec73a'
        and type(execution.get('compileCalls')) is int and execution['compileCalls']==1
        and type(execution.get('exitCode')) is int and execution['exitCode']==0
        and execution.get('interactiveClientLaunched') is False
        and Path(execution['command'][0]).resolve()==Path(prep['client']['path']).resolve(),
        'Single installed native compiler execution differs')
    parent_path=pinned(compilation['native'])
    # The plan and independent review are fresh evidence, not a plan marked executed.
    contract.require(plan.get('kind')=='independent-human-source-native-restoration-plan'
        and plan.get('pass') is True and plan.get('executed') is False
        and plan.get('sourceNativeOriginal')==receipt['sourceNativeOwner'] and plan.get('parentNative')==compilation['native'],
        'Fresh decoded restoration plan differs')
    contract.require(restoration.get('kind')=='executed-human-source-native-payload-restoration'
        and restoration.get('source')==receipt['sourceNativeOwner'] and restoration.get('parentNative')==compilation['native']
        and restoration.get('rangePlan')==receipt['rangePlan'] and restoration.get('native')==receipt['resources']['srn_fa_h0.mdl'],
        'Executed native restoration closure differs')
    contract.require(review.get('kind')=='independent-human-source-native-posture-review' and review.get('pass') is True
        and review.get('compile')==receipt['compile'] and review.get('native')==receipt['resources']['srn_fa_h0.mdl']
        and review.get('numericArchive')==receipt['numericCorrectedArrays']
        and review.get('uneditedControllers')==84 and review.get('editedControllers')==16
        and review.get('staticOwners')==56 and review.get('clientEvidence') is False
        and review.get('phase')=='after-restoration' and review.get('allUneditedNativePayloadsExact') is True
        and review.get('outsideRestorationRangesByteExact') is True
        and review.get('executedRestorationReceipt')==receipt['restoration']
        and review.get('originalSourceOwner')==receipt['sourceNativeOwner'] and review.get('root')==receipt['sourceRoot']
        and review.get('pendingRestoration') is False and review.get('editedTimestampWordsExact') is True,
        'Fresh independent native review differs')
    original=source_root.read_bytes();matches=list(re.finditer(rb'(?im)^setsupermodel[ \t]+pfh0[ \t]+(a_fa)(?=[ \t]*\r?$)',original))
    contract.require(len(matches)==1,'Literal installed root parent token must be unique')
    a,b=matches[0].span(1);expected_root=original[:a]+b'srn_fa_h0'+original[b:]
    contract.require(paths['pfh0.mdl'].read_bytes()==expected_root,'Root changes exceed its one parent token')
    source_blob=source_native.read_bytes();parent=parent_path.read_bytes();result=paths['srn_fa_h0.mdl'].read_bytes()
    contract.require(len(result)==len(parent) and hashlib.sha256(result).hexdigest()==plan['expectedResultSha256'],
        'Restored native result differs from frozen plan')
    source_decoded=NativeIdleReader(source_blob).decode({'pause1','pause2'})
    parent_decoded=NativeIdleReader(parent).decode()
    permitted_ranges={}
    for clip in ('pause1','pause2'):
        old=source_decoded['clips'][clip];new=parent_decoded['clips'][clip]
        for name,node in old['nodes'].items():
            dest='srn_fa_h0' if name=='a_fa' else name
            for typ,control in node['controls'].items():
                altered=(name=='rootdummy' and typ==8) or (name in ALTERED and typ==20)
                if altered:continue
                other=new['nodes'][dest]['controls'][typ]
                contract.require(control['times'].shape==other['times'].shape and control['values'].shape==other['values'].shape,
                    'Restoration controller shapes differ')
                for field in ('timeRange','dataRange'):
                    source_span=control[field];destination_span=other[field]
                    permitted_ranges[(tuple(source_span),tuple(destination_span))]=(clip,name,dest,typ,field)
    mask=np.zeros(len(parent),dtype=bool)
    for row in plan['rows']:
        association=permitted_ranges.get((tuple(row['sourceRange']),tuple(row['destinationRange'])))
        contract.require(association is not None,'Restoration is outside decoded unedited controller ranges')
        clip,old_name,new_name,typ,field=association
        contract.require(row.get('clip')==clip and row.get('node') in (old_name,new_name) and row.get('type')==typ,
            'Restoration row identity differs from decoded source control')
        start,end=row['destinationRange'];old_start,old_end=row['sourceRange']
        contract.require(type(start) is int and type(end) is int and 12<=start<end<=len(parent)
            and type(old_start) is int and type(old_end) is int and 12<=old_start<old_end<=len(source_blob) and end-start==old_end-old_start and not mask[start:end].any(),
            'Restoration ranges overlap or escape')
        contract.require(hashlib.sha256(source_blob[old_start:old_end]).hexdigest()==row['sourceBytesSHA256']
            and hashlib.sha256(parent[start:end]).hexdigest()==row['destinationBytesSHA256']
            and result[start:end]==source_blob[old_start:old_end], 'Restored payload bytes differ')
        mask[start:end]=True
    contract.require(np.array_equal(np.frombuffer(parent,np.uint8)[~mask],np.frombuffer(result,np.uint8)[~mask]),
        'Bytes outside restoration ranges changed')
    reader=NativeIdleReader(source_blob).decode({'pause1','pause2'});candidate=NativeIdleReader(result).decode()
    contract.require((candidate['name'],candidate['parent'],candidate['scale'])==('srn_fa_h0','a_fa',1)
        and set(candidate['clips'])=={'pause1','pause2'},'Carrier identity/clips/scale differ')
    static=nodes(original.decode('cp1252'))
    expected_names=(set(static)-{'pfh0'})|{'srn_fa_h0'}
    contract.require(set(candidate['nodes'])==expected_names and len(expected_names)==56 and 'belt_pelvis' not in expected_names,
        'Carrier static names or inherited renderable ownership differ')
    for name,row in candidate['nodes'].items():
        old_name='pfh0' if name=='srn_fa_h0' else name;old=static[old_name]
        want_parent=None if old['parent']=='null' else 'srn_fa_h0' if old['parent']=='pfh0' else old['parent']
        contract.require(row['flags']==1 and row['parent']==want_parent and set(row['controls']) <= {8,20,36},
            'Carrier static type/parent/control differs')
        for typ,control in row['controls'].items():
            contract.require(control['times'].shape==(1,) and control['times'][0]==0
                and control['values'].shape==(1,{8:3,20:4,36:1}[typ]),
                'Static controller must have one zero-time key of its declared width')
        p=row['controls'][8]['values'][0] if 8 in row['controls'] else np.zeros(3,dtype='<f4')
        q=row['controls'][20]['values'][0] if 20 in row['controls'] else np.array([0,0,0,1.])
        want=quaternion(old['orientation'])
        contract.require(np.array_equal(p,np.asarray(old['position'],dtype='<f4'))
            and min(float(np.max(abs(q-want))),float(np.max(abs(q+want))))<1e-6,
            'Carrier static frame differs')
        contract.require(36 not in row['controls'] or np.all(row['controls'][36]['values']==1), 'Carrier static scale differs')
    belt=reader['nodes']['belt_pelvis']
    contract.require(belt['parent']=='pelvis_g' and belt['flags']==33 and belt['mesh']['faces']==100
        and belt['mesh']['vertices']==152 and belt['mesh']['textures'][0]=='pfh0_robe030',
        'Inherited original belt/robe geometry differs')
    edited=unedited=0
    with np.load(numeric,allow_pickle=False) as archive:
        for clip in ('pause1','pause2'):
            old=reader['clips'][clip];new=candidate['clips'][clip]
            contract.require((old['length'],old['transition'],old['animroot'],old['events'])==
                (new['length'],new['transition'],new['animroot'],new['events']),'Idle timing/events/root changed')
            contract.require(set(new['nodes'])==(set(old['nodes'])-{'a_fa'})|{'srn_fa_h0'},'Idle node inventory differs')
            for name,node in old['nodes'].items():
                new_name='srn_fa_h0' if name=='a_fa' else name;other=new['nodes'][new_name]
                parent_name='srn_fa_h0' if node['parent']=='a_fa' else node['parent']
                contract.require(node['flags']==other['flags'] and node['mesh']==other['mesh']
                    and other['parent']==parent_name and set(node['controls'])==set(other['controls']),
                    'Typed idle node/controller/parent changed')
                for typ,control in other['controls'].items():
                    altered=(name=='rootdummy' and typ==8) or (name in ALTERED and typ==20)
                    if not altered:
                        original_control=node['controls'][typ]
                        contract.require(control['times'].tobytes()==original_control['times'].tobytes()
                            and control['values'].tobytes()==original_control['values'].tobytes(),'Unedited native payload changed')
                        unedited+=1;continue
                    prefix='pfh0|'+clip+'|'+name
                    times=archive[prefix+'|times'];values=archive[prefix+'|values']
                    contract.require(control['times'].tobytes()==times.tobytes() and control['values'].shape==values.shape,
                        'Corrected source-native grids differ')
                    error=float(np.max(abs(control['values']-values))) if typ==8 else max(
                        min(float(np.max(abs(x-y))),float(np.max(abs(x+y)))) for x,y in zip(control['values'],values))
                    contract.require(error<1e-6,'Corrected native controller differs from reviewed source-native arrays')
                    contract.require(all(not mask[a:b].any() for a,b in (control['timeRange'],control['dataRange'])),
                        'Restoration touched corrected controller')
                    edited+=1
    contract.require((edited,unedited)==(16,84),'Complete corrected/original controller closure differs')
    for path,digest in frozen.items():contract.require(contract.sha(path)==digest,'Overlay input changed during verification')
    return {'kind':'verified-single-human-source-native-animation-overlay','receipt':receipt_pin,
        'resourceHashes':{name:row['sha256'] for name,row in receipt['resources'].items()},
        'resourcePaths':{name:str(path) for name,path in paths.items()},'frozenInputs':frozen,
        'installedSourceRootUnchanged':True,'isolatedRootParentTokenOnly':True,'staticFramesExact':True,
        'animationParentRootOverridden':True,'compilerClientSha256':compiler_sha,'uneditedControllers':unedited,'editedControllers':edited,
        'clientAccepted':False,'runtimeSelected':False,'productionAccepted':False}