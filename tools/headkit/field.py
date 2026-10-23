"""Generated appearance sampler used by the reviewed heads; no image reprojection."""
import numpy as np


def load_generated_field(path,allow_decoder_overshoot=False):
    """Load a field saved by HeadkitSaveFieldV1. Trellis sparse voxels carry a leading batch column
    (batch,x,y,z); one saved head is exactly one batch, which is dropped here."""
    with np.load(path,allow_pickle=False) as archive:
        if set(archive.files)!={'coords','attrs','resolution'}:raise ValueError('Unexpected generated field layout')
        coords=archive['coords'];attrs=archive['attrs'];resolution=int(archive['resolution'])
    if coords.ndim==2 and coords.shape[1]==4:
        if len(coords) and np.any(coords[:,0]!=0):raise ValueError('Generated field must hold exactly one batch (index 0)')
        coords=coords[:,1:]
    return GeneratedField(coords,attrs,resolution,allow_decoder_overshoot)

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

    def centres(self,index=slice(None)):
        """World centres of sorted voxels, matching the sampler's grid=(p+.5)*R-.5."""
        k,R=self.keys[index],self.resolution
        return (np.stack([k//(R*R),k//R%R,k%R],axis=1)+.5)/R-.5

    def nearest(self,query):
        """Sorted index of the nearest voxel centre; ties go to the lowest packed key."""
        from scipy.spatial import cKDTree
        query=np.asarray(query,dtype=np.float64)
        # Uncompacted sliding-midpoint cells keep far queries inside a hollow shell cheap: on a 20.5M-voxel
        # head the default median/compact tree spent ~7ms per sample beyond 128 voxels, this one ~0.12ms.
        if self.tree is None:self.tree=cKDTree(self.centres(),balanced_tree=False,compact_nodes=False)
        distance,near=self.tree.query(query,k=min(2,len(self.keys)),workers=4)
        if distance.ndim==1:return near
        best=near[:,0]
        # Exact and near ties are re-measured together, so the tree's visit order never picks the winner.
        for i in np.flatnonzero(distance[:,1]<=distance[:,0]*(1+1e-9)+1e-15):
            candidates=np.asarray(self.tree.query_ball_point(query[i],distance[i,0]*(1+1e-9)+1e-15))
            squared=((self.centres(candidates)-query[i])**2).sum(axis=1)
            best[i]=candidates[squared==squared.min()].min()
        return best

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
            if not ok.all():result[~ok]=self.attrs[self.nearest(query[~ok])]
            self.clipped_samples_per_channel+=np.count_nonzero((result<0)|(result>1),axis=0)
            np.clip(result,0,1,out=result)
            values[start:start+len(query)]=result
            fallback[start:start+len(query)]=~ok
        return values,fallback
