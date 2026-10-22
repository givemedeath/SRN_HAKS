"""Generated appearance sampler used by the reviewed heads; no image reprojection."""
import numpy as np

class GeneratedField:
    def __init__(self,coords,attrs,resolution,allow_decoder_overshoot=False):
        coords,attrs=np.asarray(coords),np.asarray(attrs)
        if (type(resolution) is not int or not 0<resolution<=2048
                or coords.ndim!=2 or coords.shape[1]!=3 or not len(coords)
                or not np.issubdtype(coords.dtype,np.integer)
                or attrs.shape!=(len(coords),6) or not np.isfinite(attrs).all()
                or coords.min()<0 or coords.max()>=resolution):
            raise ValueError('Require one bounded nonempty six-channel generated field')
        if not allow_decoder_overshoot and (attrs.min() < -1e-5 or attrs.max()>1.00001):
            raise ValueError('Generated voxel values exceed [0,1]; require explicit decoder range policy')
        self.resolution=resolution
        names=('red','green','blue','metallic','roughness','opacity')
        self.raw_ranges=[{'name':name,'min':float(attrs[:,index].min()),
            'max':float(attrs[:,index].max()),
            'belowZeroVoxels':int(np.count_nonzero(attrs[:,index]<0)),
            'aboveOneVoxels':int(np.count_nonzero(attrs[:,index]>1))}
            for index,name in enumerate(names)]
        self.clipped_samples_per_channel=np.zeros(6,dtype=np.int64)
        self.coords=coords.astype(np.int64)
        keys=(self.coords[:,0]*resolution+self.coords[:,1])*resolution+self.coords[:,2]
        order=np.argsort(keys)
        self.keys=keys[order]
        if np.any(self.keys[1:]==self.keys[:-1]):raise ValueError('Ambiguous duplicate voxel coordinates')
        # Match core transport: clamp sampled values after normalized interpolation,
        # never clamp decoded voxel attributes before their weights are combined.
        self.attrs=np.asarray(attrs[order],dtype=np.float32)
        self.order=order
        self.tree=None
        self.original_to_sorted=None

    def sample(self,positions,chunk=65536):
        positions=np.asarray(positions,dtype=np.float32)
        if positions.ndim!=2 or positions.shape[1]!=3 or not np.isfinite(positions).all():
            raise ValueError('Require finite surface hit positions')
        values=np.zeros((len(positions),6),dtype=np.float32)
        fallback=np.zeros(len(positions),dtype=bool)
        R=self.resolution
        for start in range(0,len(positions),chunk):
            query=positions[start:start+chunk]
            grid=(query+.5)*R-.5
            base=np.floor(grid).astype(np.int64); frac=grid-base
            accum=np.zeros((len(query),6),dtype=np.float64)
            weights=np.zeros(len(query),dtype=np.float64)
            for dx in (0,1):
                for dy in (0,1):
                    for dz in (0,1):
                        cc=base+np.array([dx,dy,dz])
                        key=(cc[:,0]*R+cc[:,1])*R+cc[:,2]
                        index=np.searchsorted(self.keys,key).clip(max=len(self.keys)-1)
                        match=((cc>=0)&(cc<R)).all(axis=1)&(self.keys[index]==key)
                        w=np.prod(np.where(np.array([dx,dy,dz]),frac,1-frac),axis=1)*match
                        accum+=self.attrs[index]*w[:,None]; weights+=w
            ok=weights>1e-8
            result=np.zeros((len(query),6),dtype=np.float32)
            result[ok]=accum[ok]/weights[ok,None]
            if not ok.all():
                from scipy.spatial import cKDTree
                if self.tree is None:
                    voxel_positions=(self.coords.astype(np.float64)+.5)/R-.5
                    self.tree=cKDTree(voxel_positions)
                    self.original_to_sorted=np.empty(len(self.order),dtype=np.int64)
                    self.original_to_sorted[self.order]=np.arange(len(self.order))
                _,near=self.tree.query(query[~ok],k=1,workers=4)
                # Tree uses original coordinates; attrs are sorted by packed key.
                result[~ok]=self.attrs[self.original_to_sorted[near]]
            self.clipped_samples_per_channel+=np.count_nonzero((result<0)|(result>1),axis=0)
            np.clip(result,0,1,out=result)
            values[start:start+len(query)]=result
            fallback[start:start+len(query)]=~ok
        return values,fallback
