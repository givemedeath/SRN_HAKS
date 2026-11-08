"""Source-bound removal of a reviewed molding rim below long hair; exterior repair closes it."""
import numpy as np
from .common import pin, require, verify
from .gltf import positions, write_mesh


def trim(source, output, policy):
    require(isinstance(policy, dict) and set(policy) == {'sourceSha256','heightFraction','hairOnlyReviewed','notes'},
            'Hair-base trim needs exact source hash, heightFraction, hairOnlyReviewed and notes')
    require(policy['hairOnlyReviewed'] is True and isinstance(policy['notes'],str) and policy['notes'].strip(),
            'Review the selected lower band as hair only, below the full jaw')
    height=policy['heightFraction']
    require(type(height) in (int,float) and np.isfinite(height) and 0 < height <= .1,
            'Hair-base trim may remove at most the lowest ten percent of head height')
    frozen=pin(source)
    require(frozen['sha256']==policy['sourceSha256'],'Hair-base trim source differs from reviewed mesh')
    v,f=positions(source)
    # GLB transports explicit corners; weld identical positions before sharing new edge points.
    v,inverse=np.unique(v,axis=0,return_inverse=True);f=inverse[f]
    lo=float(v[:,1].min());extent=float(np.ptp(v[:,1]))
    require(extent>0 and np.isfinite(v).all(),'Finite nonempty hair mesh required')
    s=v[:,1]-(lo+height*extent);above=s>=0;count=above[f].sum(1)
    affected=count<3
    fraction=float(affected.mean())
    require(0 < fraction <= .1,'Hair-base trim exceeds ten percent of triangles or removes nothing')
    require(float(v[f[affected],1].max())<=lo+.12*extent,
            'Hair-base trim crosses protected upper geometry; inspect long triangles')
    points={};extra=[];clipped=[]
    def edge(i,j):
        key=(min(i,j),max(i,j))
        if s[i]==0:return int(i)
        if s[j]==0:return int(j)
        if key not in points:
            t=s[i]/(s[i]-s[j])
            points[key]=len(v)+len(extra);extra.append(v[i]+t*(v[j]-v[i]))
        return points[key]
    for face in f[(count>0)&(count<3)]:
        polygon=[]
        for k in range(3):
            i,j=face[k],face[(k+1)%3]
            if above[i]:polygon.append(int(i))
            if above[i]!=above[j]:polygon.append(edge(i,j))
        polygon=list(dict.fromkeys(polygon))
        clipped.extend([[polygon[0],polygon[k],polygon[k+1]] for k in range(1,len(polygon)-1)])
    vertices=np.concatenate([v,np.asarray(extra).reshape(-1,3)])
    faces=np.concatenate([f[count==3],np.asarray(clipped,dtype=np.int64).reshape(-1,3)])
    tri=vertices[faces]
    area=np.linalg.norm(np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]),axis=1)
    faces=faces[area>0]
    used,inv=np.unique(faces,return_inverse=True)
    verify([frozen],fresh=True)
    write_mesh(output,vertices[used],inv.reshape(-1,3))
    return {'source':frozen,'output':pin(output),'heightFraction':height,'affectedFaceFraction':fraction,
            'affectedFaces':int(affected.sum()),'beforeTriangles':len(f),'afterTriangles':len(faces),
            'maximumAffectedHeightFraction':float((v[f[affected],1].max()-lo)/extent),
            'protectedVerticesUnmoved':True,'exteriorRepairRequired':True,'visualReviewRequired':True,
            'notes':policy['notes']}
