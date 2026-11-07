"""Sampled VRAM/RAM guard for owned GPU jobs. This is not an allocator hard limit."""
import ctypes
import math
import subprocess
import threading
import time
from head_files import write_json

class BudgetExceeded(RuntimeError):
    pass

def sample_device(index):
    result=subprocess.run(['nvidia-smi','-i',str(index),'--query-gpu=memory.used',
                           '--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=3,
                          creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if result.returncode:
        raise BudgetExceeded('GPU memory sampler failed')
    used=int(result.stdout.strip())*1048576
    class Memory(ctypes.Structure):
        _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong)]+[(name,ctypes.c_ulonglong) for name in
                   ('totalPhysical','availablePhysical','totalPage','availablePage','totalVirtual','availableVirtual','extended')]
    memory=Memory();memory.length=ctypes.sizeof(memory)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory)):
        raise BudgetExceeded('RAM sampler failed')
    return used,memory.availablePhysical/1073741824

class Budget:
    def __init__(self,config,output,sampler=sample_device):
        self.limit=config.get('memoryLimitBytes')
        self.floor=config.get('minimumFreeRAMGiB',0)
        self.start_floor=config.get('minimumStartRAMGiB',self.floor)
        self.latest_available=None
        self.index=config.get('gpuIndex',0)
        if (type(self.limit) is not int or self.limit<=0 or type(self.floor) not in (int,float)
                or not math.isfinite(self.floor) or self.floor<0 or type(self.index) is not int or self.index<0):
            raise ValueError('Positive memoryLimitBytes and nonnegative RAM floor/GPU index required')
        if type(self.start_floor) not in (int,float) or not math.isfinite(self.start_floor) or self.start_floor < self.floor:
            raise ValueError('minimumStartRAMGiB must be finite and at least the runtime floor')
        self.output=output;self.sampler=sampler;self.stop=threading.Event();self.thread=None
        self.reason=None;self.last=0;self.peak=0;self.minimum=None;self.samples=0
        self.first_sample = None
        self.maximumSampleGap=0;self.samplingSeconds=0
    def sample(self):
        begun=time.monotonic()
        try:
            used,available=self.sampler(self.index)
            if type(used) is not int or used<0 or not math.isfinite(available) or available<0:
                raise ValueError('Invalid memory sample')
            self.latest_available=available
            if self.first_sample is None:
                self.first_sample = {'deviceBytes': used, 'availableRAMGiB': available}
            now=time.monotonic()
            if self.last:self.maximumSampleGap=max(self.maximumSampleGap,now-self.last)
            self.last=now;self.peak=max(self.peak,used)
            self.minimum=available if self.minimum is None else min(self.minimum,available);self.samples+=1
            if used>self.limit:self.reason='VRAM budget exceeded'
            if available<self.floor:self.reason='Free RAM below budget floor'
        except Exception as error:
            self.reason='Memory supervision failed: '+str(error)
        finally:self.samplingSeconds+=time.monotonic()-begun
    def check(self):
        if self.reason or not self.last or time.monotonic()-self.last>5:
            raise BudgetExceeded(self.reason or 'Memory sampling unavailable or stale')
    def admit_prompt(self):
        self.check()
        if self.latest_available < self.start_floor:
            raise BudgetExceeded(f'GPU dispatch needs {self.start_floor:g} GiB free RAM; {self.latest_available:.2f} available')
    def start(self):
        self.sample();self.check()
        def watch():
            while not self.stop.wait(.25):self.sample()
        self.thread=threading.Thread(target=watch,daemon=True);self.thread.start()
    def close(self):
        self.stop.set()
        if self.thread:self.thread.join(timeout=5)
        write_json(self.output,{'limitBytes':self.limit,'initialSample':self.first_sample,'sampledPeakDeviceBytes':self.peak,
                    'minimumFreeRAMGiB':self.floor,'minimumStartRAMGiB':self.start_floor,'minimumAvailableRAMGiB':self.minimum,
                    'samples':self.samples,'reason':self.reason,'allocatorHardLimit':False,
                    'samplingSeconds':self.samplingSeconds,'maximumSampleGapSeconds':self.maximumSampleGap})


class Watchdog:
    """Budget cancellation runs independently of a stalled history request."""
    def __init__(self,budget,interrupt):
        self.budget=budget;self.interrupt=interrupt;self.reason=None
        self.stop=threading.Event();self.thread=None;self.interrupted=False
    def check(self):
        if self.budget:
            try:self.budget.check()
            except BudgetExceeded as error:self.reason=str(error)
        return self.reason
    def __enter__(self):
        def watch():
            while not self.stop.is_set():
                if self.check() and not self.interrupted:
                    try:self.interrupted=bool(self.interrupt())
                    except (OSError,ValueError):pass
                self.stop.wait(.1)
        if self.budget:
            self.thread=threading.Thread(target=watch,daemon=True);self.thread.start()
        return self
    def __exit__(self,*_):
        self.stop.set()
        if self.thread:
            self.thread.join(timeout=6)
            if self.thread.is_alive():raise RuntimeError('Cancellation thread did not stop; reconcile GPU prompt')
