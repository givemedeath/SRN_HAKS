"""Request-scoped byte verification and low-overhead, metadata-only measurements.

No trust crosses requests or processes. Membership is always censused by callers;
only actual reads within one explicit validation boundary may be shared.
"""
from contextlib import contextmanager
from contextvars import ContextVar
import functools
import hashlib
import json
import logging
import os
from pathlib import Path
import threading
import time


CURRENT_PASS=ContextVar('headkit_verification_pass',default=None)
HEAVY_VERIFICATION_LOCK=threading.RLock()


@functools.cache
def _windows_memory():
    # Bind once per process; the RSS monitor samples every 50ms.
    import ctypes
    from ctypes import wintypes
    class Counters(ctypes.Structure):
        _fields_=[('cb',wintypes.DWORD),('faults',wintypes.DWORD),
                  *[(name,ctypes.c_size_t) for name in ('peak','working','peakPaged','paged',
                    'peakNonPaged','nonPaged','pagefile','peakPagefile')]]
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    psapi=ctypes.WinDLL('psapi',use_last_error=True)
    kernel.GetCurrentProcess.restype=wintypes.HANDLE
    query=psapi.GetProcessMemoryInfo
    query.argtypes=[wintypes.HANDLE,ctypes.POINTER(Counters),wintypes.DWORD]
    return ctypes,Counters,query,kernel.GetCurrentProcess()


def resident_bytes():
    """Current process RSS, never an estimate from bytes hashed or model sizes."""
    try:
        if os.name=='nt':
            ctypes,Counters,query,process=_windows_memory()
            counters=Counters();counters.cb=ctypes.sizeof(counters)
            if query(process,ctypes.byref(counters),counters.cb):
                return counters.working
        else:
            with open('/proc/self/statm',encoding='ascii') as stream:
                return int(stream.read().split()[1])*os.sysconf('SC_PAGE_SIZE')
    except (OSError,ValueError,IndexError,AttributeError):pass
    return None


class VerificationPass:
    """One lexical boundary; a later pass always opens and hashes bytes again."""
    def __init__(self,name):
        self.name=name;self.hashes={};self.sources={};self._lifecycle={'sourceBytes':0,'closed':False}
        self.counts={'filesHashed':0,'bytesHashed':0,'hashHits':0,'objectsVisited':0,'astParses':0,
                     'constructorIndexes':0,'retainedInstances':0,'retainedFunctions':0}
        self.phases=[]
        self._guard=threading.Lock();self._file_locks={}

    @property
    def closed(self):return self._lifecycle['closed']

    @property
    def source_bytes(self):return self._lifecycle['sourceBytes']

    def hash(self,path,*,retain_source=False,canonical=False):
        if self.closed:raise ValueError('Verification pass is closed')
        path=Path(path) if canonical else Path(path).resolve(strict=True)
        with self._guard:lock=self._file_locks.setdefault(path,threading.Lock())
        with lock:return self._hash(path,retain_source=retain_source)

    def _hash(self,path,*,retain_source):
        # Counters and the retention budget are shared by hash workers; _guard
        # covers only bookkeeping, never file I/O.
        with self._guard:
            if path in self.hashes:self.counts['hashHits']+=1;return self.hashes[path]
        digest=hashlib.sha256();size=0;blocks=[]
        # Bound transient source retention independently of model/binary sizes.
        hint=path.stat().st_size if retain_source and path.suffix=='.py' else None
        with self._guard:
            keep=hint is not None and hint<=1024*1024 and self._lifecycle['sourceBytes']+hint<=32*1024*1024
            reserved=hint if keep else 0;self._lifecycle['sourceBytes']+=reserved
        try:
            with path.open('rb') as stream:
                for block in iter(lambda:stream.read(1024*1024),b''):
                    digest.update(block);size+=len(block)
                    if keep:
                        if size<=1024*1024:blocks.append(block)
                        else:keep=False;blocks.clear()
        except BaseException:
            with self._guard:self._lifecycle['sourceBytes']-=reserved
            raise
        result=digest.hexdigest()
        with self._guard:
            self.hashes[path]=result;self.counts['filesHashed']+=1;self.counts['bytesHashed']+=size
            if keep:self.sources[path]=b''.join(blocks)
            self._lifecycle['sourceBytes']+=(size if keep else 0)-reserved
        return result

    def source(self,path):
        path=Path(path).resolve(strict=True)
        if path in self.sources:return self.sources[path]
        if path not in self.hashes:self.hash(path,retain_source=True,canonical=True)
        if path in self.sources:return self.sources[path]
        # Oversized source is not retained. Rebind that read to the pass digest.
        value=path.read_bytes()
        with self._guard:self.counts['bytesHashed']+=len(value)
        if hashlib.sha256(value).hexdigest()!=self.hashes[path]:
            raise ValueError('Source changed within verification pass: '+str(path))
        return value

    @contextmanager
    def phase(self,name):
        before=dict(self.counts);start=time.perf_counter();rss=resident_bytes()
        peak=[rss];stop=threading.Event()
        def sample():
            while not stop.wait(.05):
                value=resident_bytes()
                if value is not None:peak[0]=max(peak[0] or 0,value)
        monitor=threading.Thread(target=sample,daemon=True);monitor.start()
        success=False
        try:yield;success=True
        finally:
            stop.set();monitor.join();end=resident_bytes()
            if end is not None:peak[0]=max(peak[0] or 0,end)
            self.phases.append({'phase':name,'seconds':time.perf_counter()-start,'success':success,
                'rssStartBytes':rss,'rssEndBytes':end,'sampledPeakRssBytes':peak[0],
                'counts':{key:value-before.get(key,0) for key,value in self.counts.items()}})

    def report(self):
        return {'schemaVersion':1,'boundary':self.name,'counts':dict(self.counts),'phases':list(self.phases),
                'memoryScope':'process RSS sampled every 50ms plus boundaries; includes model residency; not exact allocation peak'}

    def close(self):
        self.hashes.clear();self.sources.clear();self._file_locks.clear()
        self._lifecycle.update(sourceBytes=0,closed=True)


@contextmanager
def verification_pass(name):
    # Always fresh, including nested boundaries. Never carry a dispatch cache
    # across a wait, execution, completion check or separate server request.
    session=VerificationPass(name);token=CURRENT_PASS.set(session)
    try:
        with session.phase(name):yield session
    finally:
        CURRENT_PASS.reset(token)
        logging.getLogger(__name__).info('headkit-verification %s',json.dumps(session.report()))
        session.close()
