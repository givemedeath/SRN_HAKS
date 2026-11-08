"""Explicit Cycles GPU selection, shared admission and sampled owned-process VRAM guard."""
from contextlib import contextmanager
from pathlib import Path
import json
import urllib.request
from urllib.parse import urlparse
from .gpu_lock import locked
import csv
import os
import re
import subprocess
import threading
import time
from .common import require,write


def settings(config):
    value=config.get('compute',{'device':'CPU'})
    require(isinstance(value,dict) and not set(value)-{'device','backend','gpuIndex','memoryLimitBytes','gpuLock','comfyUrl','deviceId'},'Unknown render compute settings')
    require(value.get('device') in ('CPU','GPU'),'Render compute device must be CPU or GPU')
    if value['device']=='GPU':
        require(value.get('backend') in ('OPTIX','CUDA'),'GPU rendering needs OPTIX or CUDA')
        require(type(value.get('gpuIndex')) is int and value['gpuIndex']>=0,'GPU rendering needs a nonnegative GPU index')
        require(type(value.get('memoryLimitBytes')) is int and value['memoryLimitBytes']>0,'GPU rendering needs an explicit positive VRAM budget')
        require(all(isinstance(value.get(k),str) and value[k].strip() for k in ('gpuLock','comfyUrl')),'GPU rendering needs shared lock and ComfyUI coordination')
        require('deviceId' not in value or isinstance(value['deviceId'],str) and value['deviceId'].strip(),'Invalid GPU device identity')
    return dict(value)


def pci(value):
    match=re.search(r'([0-9a-f]{4,8}):([0-9a-f]{2}):([0-9a-f]{2})(?:\.[0-7])?',value,re.I)
    require(match is not None,'GPU has no verifiable PCI identity')
    return tuple(int(v,16) for v in match.groups())


def sample(index):
    result=subprocess.run(['nvidia-smi','-i',str(index),'--query-gpu=memory.used,name,pci.bus_id','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=3,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    require(result.returncode==0,'GPU memory sampler failed')
    rows=list(csv.reader(result.stdout.strip().splitlines()));require(len(rows)==1 and len(rows[0])==3,'Ambiguous GPU memory sample')
    used,name,bus=(v.strip() for v in rows[0]);return {'usedBytes':int(used)*1048576,'name':name,'pci':bus}


def comfy_idle(url):
    """Read the local queue only; never unload models or initialize generation adapters."""
    parsed=urlparse(url)
    require(parsed.scheme=='http' and parsed.hostname in ('localhost','127.0.0.1')
            and not parsed.username and not parsed.password and parsed.path in ('','/')
            and not parsed.query and not parsed.fragment,'Use the bound local ComfyUI instance')
    with urllib.request.urlopen(url.rstrip('/')+'/queue',timeout=10) as response:
        queue=json.loads(response.read(1048577))
    require(isinstance(queue,dict) and all(isinstance(queue.get(k),list) for k in ('queue_running','queue_pending')),
            'Invalid ComfyUI queue response')
    return not queue['queue_running'] and not queue['queue_pending']


@contextmanager
def lease(config):
    value=settings(config)
    if value['device']=='CPU':yield;return
    deadline=time.monotonic()+300
    while True:
        held=locked(Path(value['gpuLock']))
        try:held.__enter__();break
        except FileExistsError:
            require(time.monotonic()<deadline,'Timed out waiting for the shared GPU render lock');time.sleep(2)
    try:
        require(comfy_idle(value['comfyUrl']),'ComfyUI is busy; GPU rendering refused')
        yield
    finally:held.__exit__(None,None,None)


def configure(bpy,config,identity):
    value=settings(config);scene=bpy.context.scene
    if value['device']=='CPU':scene.cycles.device='CPU';return {'device':'CPU'}
    prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type=value['backend'];prefs.refresh_devices()
    selected=[d for d in prefs.devices if d.type==value['backend'] and pci(d.id)==pci(identity['pci']) and d.name==identity['name']]
    if value.get('deviceId'):selected=[d for d in selected if d.id==value['deviceId']]
    require(len(selected)==1,'The budgeted GPU is not uniquely available in Cycles; CPU fallback refused')
    for device in prefs.devices:device.use=device==selected[0]
    scene.cycles.device='GPU'
    return {'device':'GPU','backend':value['backend'],'deviceId':selected[0].id,'name':selected[0].name,'gpuIndex':value['gpuIndex'],'pci':identity['pci']}


class MemoryWatch:
    """A sampled device-wide budget, not an allocator hard limit; abort only this Blender process."""
    def __init__(self,config,output,sampler=sample,abort=None):
        self.value=settings(config);self.output=Path(output);self.sampler=sampler;self.abort=abort or os._exit
        self.stop=threading.Event();self.thread=None;self.identity=None;self.peak=0;self.count=0;self.reason=None;self.last=None;self.max_gap=0
    def tick(self):
        try:
            row=self.sampler(self.value['gpuIndex']);require(type(row['usedBytes']) is int and row['usedBytes']>=0,'Invalid GPU memory sample')
            if self.identity is None:self.identity=dict(row)
            require(row['name']==self.identity['name'] and pci(row['pci'])==pci(self.identity['pci']),'GPU identity changed during rendering')
            now=time.monotonic()
            if self.last is not None:self.max_gap=max(self.max_gap,now-self.last)
            self.last=now;self.peak=max(self.peak,row['usedBytes']);self.count+=1
            require(row['usedBytes']<=self.value['memoryLimitBytes'],'GPU render VRAM budget exceeded')
        except Exception as error:self.reason=str(error)
        return self.reason
    def save(self):
        self.output.parent.mkdir(parents=True,exist_ok=True)
        write(self.output,{'limitBytes':self.value['memoryLimitBytes'],'sampledPeakDeviceBytes':self.peak,'samples':self.count,'reason':self.reason,'maximumSampleGapSeconds':self.max_gap,'allocatorHardLimit':False,'scope':'device-wide sampled usage, including other processes'})
    def __enter__(self):
        if self.value['device']=='CPU':return self
        if self.tick():
            self.save();require(False,self.reason)
        def watch():
            while not self.stop.wait(.25):
                if self.tick():
                    try:self.save()
                    finally:self.abort(70)
                    return
        self.thread=threading.Thread(target=watch,daemon=True);self.thread.start();return self
    def __exit__(self,*error):
        if self.value['device']=='CPU':return
        self.stop.set()
        if self.thread:self.thread.join(timeout=5);require(not self.thread.is_alive(),'GPU memory sampler did not stop')
        self.save()
        if not error[0]:require(self.reason is None,self.reason or 'GPU memory supervision failed')
