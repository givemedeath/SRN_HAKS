"""Run-scoped, content-bound preparation. No approval or persistent preview cache."""
import copy
import hashlib
import json
from pathlib import Path
import re
from types import MappingProxyType
import time
import numpy as np
from retarget import nodes
from rig_controller_audit import CLIP
from rig_pose_audit import compile_controllers, sample
from pose_preview_bridge import helper_inputs


def freeze(value):
    if isinstance(value,np.ndarray):
        # bytes-backed arrays cannot be made writeable by downstream code.
        return np.frombuffer(value.tobytes(),dtype=value.dtype).reshape(value.shape)
    if isinstance(value,dict):return MappingProxyType({key:freeze(row) for key,row in value.items()})
    if isinstance(value,(list,tuple)):return tuple(freeze(row) for row in value)
    return value


class PreparationContext:
    def __init__(self, *, target_revision, rig_revision, animation_revision, settings, dependencies=()):
        self.identity={'targetRevision':target_revision,'rigRevision':rig_revision,
            'animationRevision':animation_revision,'settings':copy.deepcopy(settings),'helpers':helper_inputs()}
        self.identity['numpyVersion']=np.__version__
        self.inputs={};self.cache={};self.counts={};self.timings={};self.invalid=False
        for path in [*self.identity['helpers'],*dependencies]:self.read(path)
        self.identity['dependencyHashes']=dict(self.inputs)
        self.identity_hash=hashlib.sha256(json.dumps(self.identity,sort_keys=True).encode()).hexdigest()

    def read(self,path):
        if self.invalid:raise ValueError('Preparation context invalidated; start a fresh run')
        path=Path(path).resolve();data=path.read_bytes();digest=hashlib.sha256(data).hexdigest()
        previous=self.inputs.setdefault(str(path),digest)
        if previous!=digest:
            self.invalid=True;raise ValueError('Input changed during preparation: '+str(path))
        return data,digest

    def prepared(self,path,kind,decoder,*,settings=None):
        data,digest=self.read(path)
        key=(self.identity_hash,digest,kind,json.dumps(settings,sort_keys=True))
        if key not in self.cache:
            begun=time.perf_counter();value=decoder(data);self.read(path)
            self.cache[key]=freeze(value);self.counts[kind]=self.counts.get(kind,0)+1
            self.timings[kind]=self.timings.get(kind,0)+time.perf_counter()-begun
        return self.cache[key]

    def model(self,path):
        def parse(data):
            # Match Path.read_text's universal-newline semantics without losing byte hashes.
            text=data.decode('cp1252').replace('\r\n','\n').replace('\r','\n');clips={}
            for row in CLIP.finditer(text):
                length=re.search(r'(?mi)^\s*length\s+(\S+)',row[2])
                if not length:raise RuntimeError('Animation length missing: '+row[1])
                clips.setdefault(row[1].lower(),{'length':float(length[1]),'controllers':compile_controllers(row[2])})
            parent=re.search(r'(?mi)^setsupermodel\s+\S+\s+(\S+)',text)
            return {'skeleton':nodes(text),'clips':clips,'parent':parent[1].lower() if parent else None}
        return self.prepared(path,'model/controller-parse',parse)

    def pose(self,ascii_dir,prefix,clip,time,stock_dir=None):
        root=(Path(ascii_dir)/(prefix+'.mdl')).resolve();skeleton=self.model(root)['skeleton']
        current=prefix.lower();visited=set();inheritance=[]
        while current!='null':
            if current in visited:raise RuntimeError('Supermodel cycle')
            visited.add(current);path=Path(ascii_dir)/(current+'.mdl')
            if not path.exists() and stock_dir is not None:path=Path(stock_dir)/(current+'.mdl')
            path=path.resolve();model=self.model(path)
            inheritance.append({'model':current,'file':str(path),'sha256':self.inputs[str(path)]})
            if clip.lower() in model['clips']:
                row=model['clips'][clip.lower()]
                if not 0<=time<=row['length']:raise RuntimeError('Time outside clip length')
                # Transform sampling owns a mutable copy; prepared data remains immutable.
                mutable={name:{key:(value.copy() if isinstance(value,np.ndarray) else list(value) if isinstance(value,tuple) else value)
                         for key,value in node.items()} for name,node in skeleton.items()}
                try:matrices=sample(mutable,None,time,controllers=row['controllers'])
                except ValueError as error:raise RuntimeError(str(error)) from error
                self.verify()
                return matrices,{'file':str(path),'sha256':self.inputs[str(path)],'clip':clip,'time':time,
                    'length':row['length'],'rootFile':str(root),'rootSha256':self.inputs[str(root)],
                    'sourceInheritance':inheritance,'sampler':'rig_pose_audit.sample','samplerHelperInputs':self.identity['helpers'],
                    'controllerEncodings':['explicit-count','endlist','static'],'preparationIdentity':self.identity_hash,'clientEvidence':False}
            if model['parent'] is None:raise RuntimeError('Supermodel declaration missing')
            current=model['parent']
        raise RuntimeError('Clip unavailable: '+clip)

    def verify(self):
        for path in list(self.inputs):self.read(path)

    def receipt(self):
        self.verify()
        return {'identity':self.identity,'identitySha256':self.identity_hash,'inputs':dict(self.inputs),
            'preparationCounts':dict(self.counts),'stageSeconds':dict(self.timings),'clientEvidence':False}
