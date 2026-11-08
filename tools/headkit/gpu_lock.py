"""Shared crash-safe local GPU/ledger mutex; independent of generation adapters."""
from contextlib import contextmanager
from pathlib import Path
import errno
import os
import threading
import uuid
_LOCAL_LOCKS=set()
_LOCAL_LOCKS_GUARD=threading.Lock()


@contextmanager
def locked(ledger):
    path = Path(str(ledger)+'.lock'); path.parent.mkdir(parents=True,exist_ok=True)
    # Windows mutexes are abandoned automatically when their owning process exits.
    if os.name=='nt':
        import ctypes
        kernel32=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel32.CreateMutexW.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_wchar_p]
        kernel32.CreateMutexW.restype=ctypes.c_void_p
        kernel32.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_uint]
        kernel32.WaitForSingleObject.restype=ctypes.c_uint
        kernel32.ReleaseMutex.argtypes=[ctypes.c_void_p]
        kernel32.CloseHandle.argtypes=[ctypes.c_void_p]
        name='Local\\SRNHeadkit-'+uuid.uuid5(uuid.NAMESPACE_URL,os.path.normcase(str(path.resolve()))).hex
        with _LOCAL_LOCKS_GUARD:
            if name in _LOCAL_LOCKS:raise FileExistsError(f'Ledger is locked: {path}')
        handle=kernel32.CreateMutexW(None,False,name)
        if not handle:raise ctypes.WinError(ctypes.get_last_error())
        acquired=False
        try:
            state=kernel32.WaitForSingleObject(handle,0)
            if state==0x102:raise FileExistsError(f'Ledger is locked: {path}')
            if state not in (0,0x80):raise ctypes.WinError(ctypes.get_last_error())
            acquired=True
            with _LOCAL_LOCKS_GUARD:_LOCAL_LOCKS.add(name)
            yield
        finally:
            if acquired:
                with _LOCAL_LOCKS_GUARD:_LOCAL_LOCKS.discard(name)
                kernel32.ReleaseMutex(handle)
            kernel32.CloseHandle(handle)
        return
    # Keep a stable Unix lock-file inode; flock is released on process exit.
    stream=path.open('a+b');acquired=False
    try:
        stream.seek(0,os.SEEK_END)
        if stream.tell()==0:stream.write(b'\0');stream.flush()
        stream.seek(0)
        try:
            import fcntl
            fcntl.flock(stream.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
            acquired=True
        except OSError as exc:
            busy={errno.EACCES,errno.EAGAIN,getattr(errno,'EDEADLK',-1)}
            if exc.errno in busy:raise FileExistsError(f'Ledger is locked: {path}') from exc
            raise
        yield
    finally:
        if acquired:
            import fcntl
            fcntl.flock(stream.fileno(),fcntl.LOCK_UN)
        stream.close()
