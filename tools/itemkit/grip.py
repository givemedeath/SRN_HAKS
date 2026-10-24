"""Measured native grip calibration and UV-preserving corner transforms."""
import numpy as np
from tools.headkit.common import require


def section_dimensions(vertices, faces, y):
    tri = np.asarray(vertices, float)[faces]; hits = []
    for a,b in ((0,1),(1,2),(2,0)):
        v,w = tri[:,a],tri[:,b]
        crossing = (v[:,1]-y)*(w[:,1]-y) < 0
        v,w = v[crossing],w[crossing]
        if len(v): hits.extend(v+(w-v)*((y-v[:,1])/(w[:,1]-v[:,1]))[:,None])
    require(len(hits)>=3, 'Usable grip section has no surface')
    return np.ptp(np.asarray(hits),axis=0)[[0,2]]


def calibration(vertices, faces, matrix, origin, standard):
    require(standard.get('id')=='cougar-approved-grip-v1' and standard['approval']['gripSizingApproved'],
            'Reviewed grip reference required')
    origin=np.asarray(origin,float);matrix=np.asarray(matrix,float)
    fitted=np.c_[vertices,np.ones(len(vertices))]@matrix.T
    measured=section_dimensions(fitted[:,:3],faces,origin[1])
    target=standard['targetMidpointSection']
    scales=np.array([target['depth']/measured[0],1.,target['visibleFaceWidth']/measured[1]])
    require(np.isfinite(scales).all() and np.all(scales>0), 'Positive grip calibration required')
    correction=np.eye(4);correction[:3,:3]=np.diag(scales);correction[:3,3]=origin-origin*scales
    result=correction@matrix
    final=(np.c_[vertices,np.ones(len(vertices))]@result.T)[:,:3]
    sections=[]
    if 'usableLength' in standard:
        for row in standard['referenceSections']:
            fraction=row['fractionFromPommel'];y=origin[1]+(fraction-.5)*standard['usableLength']
            depth,width=section_dimensions(final,faces,y)
            sections.append({'fractionFromPommel':fraction,'depth':float(depth),'visibleFaceWidth':float(width)})
    return result,{'reference':standard['id'],'transverseScale':scales.tolist(),
                   'sourceSection':measured.tolist(),'measuredFittedSections':sections}


def affine_corners(positions,normals,uv,matrix):
    """Transform exact authored corners; UVs are retained without resampling."""
    p=np.asarray(positions,float);n=np.asarray(normals,float);m=np.asarray(matrix,float)
    require(m.shape==(4,4) and np.isfinite(m).all() and np.allclose(m[3],[0,0,0,1])
            and np.linalg.det(m[:3,:3])>0,'Positive finite affine transform required')
    transformed=p@m[:3,:3].T+m[:3,3]
    normals=n@np.linalg.inv(m[:3,:3]);normals/=np.linalg.norm(normals,axis=-1)[...,None]
    return transformed,normals,np.asarray(uv).copy()
