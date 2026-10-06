"""Reject returned Meshy geometry or UV changes before material transport."""
import argparse
from pathlib import Path
import numpy as np
from head_export import triangles
from head_workflow import pin, require, verify_pins, write_fresh


def ordered_corners(p, n, uv):
    # Preserve winding and per-corner attributes; only triangle ordering may vary.
    rows=[]
    for positions,normals,tex in zip(p,n,uv):
        joined=np.c_[positions,normals,tex]
        rotations=[np.roll(joined,offset,axis=0).ravel() for offset in range(3)]
        rows.append(min(rotations,key=lambda row:tuple(np.round(row,6))))
    rows=np.asarray(rows)
    return rows[np.lexsort(tuple(rows[:,i] for i in reversed(range(rows.shape[1]))))]


def corner_error(before,after,tolerance):
    """Match by spatial bins and cyclic winding, without unstable float sorting."""
    a=np.concatenate(before,axis=2);b=np.concatenate(after,axis=2)
    require(a.shape==b.shape,'Triangle/attribute counts differ')
    bins={}
    for i,row in enumerate(a):
        key=tuple(np.floor(row[:,:3].mean(0)*1000).astype(int));bins.setdefault(key,[]).append(i)
    used=set();maximum=np.zeros((3,8))
    for row in b:
        key=np.floor(row[:,:3].mean(0)*1000).astype(int);candidates=[]
        for dx in (-1,0,1):
            for dy in (-1,0,1):
                for dz in (-1,0,1):candidates+=bins.get(tuple(key+[dx,dy,dz]),[])
        candidates=[i for i in candidates if i not in used];require(candidates,'Triangle counterpart missing')
        rotations=np.stack([np.roll(row,j,axis=0) for j in range(3)])
        errors=np.abs(a[candidates,None,:,:]-rotations[None,:,:,:]);scores=errors.max((2,3))
        first,second=np.unravel_index(scores.argmin(),scores.shape);error=errors[first,second]
        require(error.max()<=tolerance,'Per-corner P/N/UV/winding differs: '+str(float(error.max())))
        used.add(candidates[first]);maximum=np.maximum(maximum,error)
    return maximum.ravel()


def verify(source, returned, output):
    pins=[pin(source),pin(returned)]
    corner_error(triangles(source,np.eye(4)),triangles(returned,np.eye(4)),1e-6)
    verify_pins(pins)
    write_fresh(output,{"kind":"srn-head-retexture-verification","source":pins[0],"returned":pins[1],
                        "geometryUvNormalsPreserved":True,"tolerance":1e-6,"productionAccepted":False})


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source",type=Path,required=True)
    parser.add_argument("--returned",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args(); verify(args.source,args.returned,args.output)
