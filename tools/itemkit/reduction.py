"""Bounded selected-face reduction preserving exact multipart mating contours."""
import numpy as np
from tools.headkit.common import require,digest
from .geometry import topology


def policy(budget,joins):
    return digest({'budget':budget,'joinY':joins,'maximumSourceDistance':.003})


def rims(vertices,joins):
    p=np.asarray(vertices,float)
    return [np.unique(p[np.abs(p[:,1]-y)<1e-7],axis=0) for y in joins]


def validate(source_vertices,vertices,faces,budget,joins):
    require(len(faces)<=budget,f'Constrained reduction exceeds its part budget: {len(faces)} > {budget}')
    audit=topology(vertices,faces)
    require(audit['closedWound'],'Constrained reduction must remain closed and outward')
    for before,after in zip(rims(source_vertices,joins),rims(vertices,joins)):
        require(before.shape==after.shape and np.allclose(before,after,atol=2e-6,rtol=0),
                'Constrained reduction changed a mating contour')
    return audit


def reduce(vertices,faces,budget,joins,meshlab):
    p=np.asarray(vertices,float);f=np.asarray(faces,np.int32)
    require(topology(p,f)['closedWound'],'Closed source required for constrained reduction')
    require(type(budget)is int and budget>=4 and len(joins)==2 and joins[0]<joins[1],
            'Explicit part budget and ordered natural joins required')
    if len(f)<=budget:return p.copy(),f.copy(),validate(p,p,f,budget,joins)
    seam=np.zeros(len(p),bool)
    for y in joins:seam|=np.abs(p[:,1]-y)<1e-7
    protected=seam[f].any(1);target=budget-int(protected.sum())-4
    require(target>=4,'Protected seam band alone exhausts this part budget')
    ms=meshlab.MeshSet();ms.add_mesh(meshlab.Mesh(p,f,f_scalar_array=(~protected).astype(float)))
    ms.compute_selection_by_scalar_per_face(minq=.5,maxq=1.,inclusive=True)
    ms.meshing_decimation_quadric_edge_collapse(targetfacenum=target,selected=True,
        preservetopology=True,preserveboundary=True,preservenormal=True,qualitythr=.3)
    m=ms.current_mesh();m.compact();v,ff=m.vertex_matrix(),m.face_matrix()
    return v,ff,validate(p,v,ff,budget,joins)
