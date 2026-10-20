"""Lossless, non-pickle checkpoint transport for one sparse Pixal shape latent."""
import json
import numpy as np
KEYS={'samples','coords','coord_counts','coord_resolution','type','model_frame'}

def validate(arrays,meta):
    if set(arrays)|set(meta)!=KEYS:raise ValueError('Unsupported or incomplete shape latent keys')
    if meta['type']!='trellis2' or meta['model_frame'] not in ('z_up','y_up') or not isinstance(meta['coord_resolution'],int) or meta['coord_resolution']<=0:raise ValueError('Unsupported sparse latent metadata')
    samples,coords,counts=(arrays[k] for k in ('samples','coords','coord_counts'))
    if samples.ndim!=4 or samples.shape[0]!=1 or coords.ndim!=2 or coords.shape[1]!=4 or not np.issubdtype(coords.dtype,np.integer) or np.any(coords[:,0]!=0):raise ValueError('One finite sparse batch required')
    if counts.shape!=(1,) or not np.issubdtype(counts.dtype,np.integer) or int(counts.sum())!=len(coords) or samples.shape[2]<len(coords):raise ValueError('Coordinate counts differ from samples')
    if not all(np.isfinite(x).all() for x in arrays.values()):raise ValueError('Nonfinite latent')
    if np.any(coords[:,1:]<0) or np.any(coords[:,1:]>=meta['coord_resolution']):raise ValueError('Sparse coordinates out of frame')

def write(path,arrays,meta):
    validate(arrays,meta)
    with open(path,'xb') as f:np.savez(f,**arrays,metadata=np.frombuffer(json.dumps(meta,sort_keys=True).encode(),dtype=np.uint8))

def read(path):
    with np.load(path,allow_pickle=False) as z:
        if set(z.files)!=KEYS-{'coord_resolution','type','model_frame'}|{'metadata'}:raise ValueError('Unexpected shape archive keys')
        meta=json.loads(z['metadata'].tobytes());arrays={k:z[k].copy() for k in ('samples','coords','coord_counts')}
    validate(arrays,meta);return arrays,meta
