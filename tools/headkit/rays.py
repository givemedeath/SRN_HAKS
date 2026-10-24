"""Pinned Embree4 CPU triangle visibility; never an eight-bit depth proxy."""
import ctypes,os,math
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import numpy as np

class EmbreeScene:
    """One copied triangle scene, Embree4 packet ABI and four caller threads."""
    def __init__(self,dll_path,points,faces):
        self.device=None; self.scene=None; self.dll_directory=None
        points=np.asarray(points); faces=np.asarray(faces)
        if (points.ndim!=2 or points.shape[1]!=3 or not len(points) or not np.isfinite(points).all()
                or faces.ndim!=2 or faces.shape[1]!=3 or not len(faces)
                or not np.issubdtype(faces.dtype,np.integer) or faces.min()<0
                or faces.max()>=len(points) or len(points)>=2**32 or len(faces)>=2**32):
            raise ValueError('Require finite unchanged triangle geometry and valid uint32 indices')
        if os.name=='nt':self.dll_directory=os.add_dll_directory(str(Path(dll_path).resolve().parent))
        self.dll=ctypes.CDLL(str(Path(dll_path).resolve()))
        ptr=ctypes.c_void_p; uint=ctypes.c_uint; size=ctypes.c_size_t
        definitions={
            'rtcNewDevice':([ctypes.c_char_p],ptr), 'rtcReleaseDevice':([ptr],None),
            'rtcGetDeviceProperty':([ptr,ctypes.c_int],ctypes.c_ssize_t),
            'rtcGetDeviceError':([ptr],ctypes.c_int),
            'rtcNewScene':([ptr],ptr), 'rtcReleaseScene':([ptr],None),
            'rtcSetSceneFlags':([ptr,ctypes.c_int],None), 'rtcCommitScene':([ptr],None),
            'rtcNewGeometry':([ptr,ctypes.c_int],ptr), 'rtcReleaseGeometry':([ptr],None),
            'rtcSetNewGeometryBuffer':([ptr,ctypes.c_int,uint,ctypes.c_int,size,size],ptr),
            'rtcCommitGeometry':([ptr],None), 'rtcAttachGeometry':([ptr,ptr],uint),
            'rtcIntersect4':([ptr,ptr,ptr,ptr],None),
        }
        for name,(argtypes,restype) in definitions.items():
            function=getattr(self.dll,name); function.argtypes=argtypes; function.restype=restype
        self.device=self.dll.rtcNewDevice(b'threads=4')
        if not self.device:raise RuntimeError('Embree4 device creation failed')
        self.version=tuple(self.dll.rtcGetDeviceProperty(self.device,index) for index in (1,2,3))
        if self.version!=(4,4,0):self.close(); raise ValueError('Unsupported Embree native ABI version')
        if not self.dll.rtcGetDeviceProperty(self.device,32):self.close(); raise ValueError('Native four-ray packets unsupported')
        if self.dll.rtcGetDeviceProperty(self.device,65):self.close(); raise ValueError('Backface-culling build unsupported')
        self.scene=self.dll.rtcNewScene(self.device)
        if not self.scene:self.close(); raise RuntimeError('Embree scene creation failed')
        self.dll.rtcSetSceneFlags(self.scene,4) # RTC_SCENE_FLAG_ROBUST
        geometry=self.dll.rtcNewGeometry(self.device,0) # TRIANGLE
        if not geometry:self.close(); raise RuntimeError('Embree geometry creation failed')
        try:
            for buffer_type,format_code,array in ((1,0x9003,np.ascontiguousarray(points,dtype=np.float32)),
                                                    (0,0x5003,np.ascontiguousarray(faces,dtype=np.uint32))):
                target=self.dll.rtcSetNewGeometryBuffer(geometry,buffer_type,0,format_code,12,len(array))
                if not target:raise RuntimeError('Embree geometry buffer allocation failed')
                ctypes.memmove(target,array.ctypes.data,array.nbytes)
            self.dll.rtcCommitGeometry(geometry); self.geometry_id=self.dll.rtcAttachGeometry(self.scene,geometry)
        except BaseException:
            self.close(); raise
        finally:self.dll.rtcReleaseGeometry(geometry)
        self.dll.rtcCommitScene(self.scene); self.check_error()

    def check_error(self):
        error=self.dll.rtcGetDeviceError(self.device)
        if error:raise RuntimeError('Embree native operation failed, error '+str(error))

    def query(self,origins,directions):
        origins=np.asarray(origins,dtype=np.float32); directions=np.asarray(directions,dtype=np.float32)
        if directions.shape==(3,):directions=np.broadcast_to(directions,origins.shape)
        if (origins.ndim!=2 or origins.shape[1]!=3 or directions.shape!=origins.shape
                or not np.isfinite(origins).all() or not np.isfinite(directions).all()
                or not np.allclose(np.linalg.norm(directions,axis=1),1,atol=1e-5,rtol=0)):
            raise ValueError('Require finite unit rays')
        count=len(origins)
        if not count:return np.empty(0),np.empty(0,dtype=np.int64),np.empty((0,3))
        packets=(count+3)//4
        # Header offsets before instance arrays are stable for all Embree4 builds.
        # Reserve128 floats (512bytes) per packet, exceeding either standard
        # instance-array variant, and require 16byte alignment. Never create instances.
        rays=np.zeros((packets,128),dtype=np.float32)
        if rays.ctypes.data%16:raise ValueError('Packet base is not 16byte aligned')
        padded_origins=np.zeros((packets*4,3),dtype=np.float32); padded_origins[:count]=origins
        padded_dirs=np.zeros_like(padded_origins); padded_dirs[:count]=directions
        rays[:,0:12]=padded_origins.reshape(packets,4,3).transpose(0,2,1).reshape(packets,12)
        rays[:,16:28]=padded_dirs.reshape(packets,4,3).transpose(0,2,1).reshape(packets,12)
        rays[:,32:36]=np.inf # tfar[4]
        unsigned=rays.view(np.uint32)
        unsigned[:,36:40]=0xffffffff # mask[4]
        unsigned[:,68:84]=0xffffffff # primID,geomID,instID, optional instPrimID
        valid=np.full((packets,4),-1,dtype=np.int32)
        if count%4:valid[-1,count%4:]=0
        def run_chunk(start,end):
            for index in range(start,end):
                self.dll.rtcIntersect4(valid.ctypes.data+index*16,self.scene,
                                      rays.ctypes.data+index*rays.strides[0],None)
            self.check_error()
        ranges=[(start,min(start+math.ceil(packets/4),packets))
                for start in range(0,packets,math.ceil(packets/4))]
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures=[pool.submit(run_chunk,*bounds) for bounds in ranges]
            for future in futures:future.result()
        ids=unsigned[:,68:72].reshape(-1)[:count].astype(np.int64)
        ids[ids==0xffffffff]=-1
        depth=rays[:,32:36].reshape(-1)[:count].copy(); depth[ids<0]=np.inf
        normals=rays[:,48:60].reshape(packets,3,4).transpose(0,2,1).reshape(-1,3)[:count].copy()
        return depth,ids,normals

    def close(self):
        if self.scene:self.dll.rtcReleaseScene(self.scene); self.scene=None
        if self.device:self.dll.rtcReleaseDevice(self.device); self.device=None
        if self.dll_directory:self.dll_directory.close(); self.dll_directory=None
