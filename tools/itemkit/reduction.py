"""Bounded selected-face reduction preserving exact multipart mating contours."""
import numpy as np
from tools.headkit.common import require,digest
from .geometry import closest_surface_point,topology

MAXIMUM_SOURCE_DISTANCE=.003


# A one-piece part (no mating contours: the firearm routes) is reduced with planar quadrics. Blender's plain collapse
# and the unweighted quadric both leave faces lying across grooves and recesses, facing no nearby donor surface, which
# the bake's transfer preflight refuses (firearm wave 1, 2026-11-17: 0.33% of the MP-5 TX's texture, 0.01% this way).
WHOLE_PART={'planarquadric':True,'planarweight':.002}


def policy(budget,joins):
    row={'budget':budget,'joinY':joins,'maximumSourceDistance':MAXIMUM_SOURCE_DISTANCE}
    if not joins:row['wholePart']=WHOLE_PART      # composite parts keep the hash their reviewed candidates carry
    return digest(row)


def rims(vertices,joins):
    p=np.asarray(vertices,float)
    return [np.unique(p[np.abs(p[:,1]-y)<1e-7],axis=0) for y in joins]


def validate(source_vertices,source_faces,vertices,faces,budget,joins,distances=None):
    """distances(points) may answer through a spatial index; the default scans the whole source per point."""
    require(len(faces)<=budget,f'Constrained reduction exceeds its part budget: {len(faces)} > {budget}')
    audit=topology(vertices,faces)
    require(audit['closedWound'],'Constrained reduction must remain closed and outward')
    for before,after in zip(rims(source_vertices,joins),rims(vertices,joins)):
        require(before.shape==after.shape and np.allclose(before,after,atol=2e-6,rtol=0),
                'Constrained reduction changed a mating contour')
    points=np.asarray(vertices,float)
    worst=np.max(distances(points)) if distances is not None else max(
        np.linalg.norm(closest_surface_point(source_vertices,source_faces,point)-point) for point in points)
    require(worst<=MAXIMUM_SOURCE_DISTANCE,'Constrained reduction left the source surface')
    return audit


def reduce(vertices,faces,budget,joins,meshlab,distances=None):
    p=np.asarray(vertices,float);f=np.asarray(faces,np.int32)
    require(topology(p,f)['closedWound'],'Closed source required for constrained reduction')
    require(type(budget)is int and budget>=4 and (len(joins)==0 or len(joins)==2 and joins[0]<joins[1]),
            'Explicit part budget and ordered natural joins (or none, for a one-piece part) required')
    if len(f)<=budget:return p.copy(),f.copy(),validate(p,f,p,f,budget,joins,distances)
    seam=np.zeros(len(p),bool)
    for y in joins:seam|=np.abs(p[:,1]-y)<1e-7
    protected=seam[f].any(1);target=budget-int(protected.sum())-4
    require(target>=4,'Protected seam band alone exhausts this part budget')
    ms=meshlab.MeshSet();ms.add_mesh(meshlab.Mesh(p,f,f_scalar_array=(~protected).astype(float)))
    ms.compute_selection_by_scalar_per_face(minq=.5,maxq=1.,inclusive=True)
    ms.meshing_decimation_quadric_edge_collapse(targetfacenum=target,selected=True,
        preservetopology=True,preserveboundary=True,preservenormal=True,qualitythr=.3,**({} if len(joins) else WHOLE_PART))
    m=ms.current_mesh();m.compact();v,ff=m.vertex_matrix(),m.face_matrix()
    return v,ff,validate(p,f,v,ff,budget,joins,distances)
