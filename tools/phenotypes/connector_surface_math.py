"""Triangle surface relations; broad-phase boxes alone never prove contact."""
import numpy as np


def _distinct(points,tolerance):
    result=[]
    for point in points:
        if not any(np.linalg.norm(point-old)<=tolerance for old in result): result.append(np.asarray(point))
    return result


def _plane_cut(triangle,distances,tolerance):
    points=[triangle[i] for i in range(3) if abs(distances[i])<=tolerance]
    for i,j in [(0,1),(1,2),(2,0)]:
        if distances[i]*distances[j] < 0:
            factor=distances[i]/(distances[i]-distances[j]);points.append(triangle[i]+factor*(triangle[j]-triangle[i]))
    return _distinct(points,tolerance)


def triangle_relation(first,second,tolerance=1e-8):
    """Return exact-plane segment/coplanar contact after candidate generation.

    Tolerance is in metres. Nondegenerate input triangles are required. Returned
    segments are surface intersection, not overlap volume or a repair distance.
    """
    a,b=np.asarray(first,dtype=float),np.asarray(second,dtype=float)
    if a.shape!=(3,3) or b.shape!=(3,3) or not np.isfinite([a,b]).all(): raise ValueError('Finite triangles required')
    na,nb=np.cross(a[1]-a[0],a[2]-a[0]),np.cross(b[1]-b[0],b[2]-b[0])
    la,lb=np.linalg.norm(na),np.linalg.norm(nb)
    if la<=0 or lb<=0: raise ValueError('Nondegenerate triangles required')
    na,nb=na/la,nb/lb
    da,db=(a-b[0])@nb,(b-a[0])@na
    if any(np.all(d>tolerance) or np.all(d<-tolerance) for d in [da,db]): return None
    line=np.cross(na,nb);length=np.linalg.norm(line)
    if length<1e-10:
        if np.max(np.abs(db))>tolerance: return None
        keep=[i for i in range(3) if i!=np.argmax(np.abs(na))]
        xy=b[:,keep];orientation=np.sign(np.cross(xy[1]-xy[0],xy[2]-xy[0]))
        polygon=list(a)
        for edge in range(3):
            start,end=xy[edge],xy[(edge+1)%3];delta=end-start
            eps=tolerance*np.linalg.norm(delta)
            def distance(point): return orientation*np.cross(delta,point[keep]-start)
            if not polygon: return None
            result=[];previous=polygon[-1];dp=distance(previous)
            for current in polygon:
                dc=distance(current)
                if (dc>=-eps)!=(dp>=-eps): result.append(previous+(current-previous)*(dp/(dp-dc)))
                if dc>=-eps: result.append(current)
                previous,dp=current,dc
            polygon=_distinct(result,tolerance)
        if not polygon: return None
        points=np.asarray(polygon);area=0.
        if len(points)>=3:
            area=sum(np.linalg.norm(np.cross(points[i]-points[0],points[i+1]-points[0]))/2 for i in range(1,len(points)-1))
        span=float(np.max(np.linalg.norm(points[:,None]-points[None,:],axis=2)))
        return {'kind':'coplanar','points':points,'length':span if area<=tolerance**2 else 0.,'area':float(area)}
    line/=length
    ca,cb=_plane_cut(a,da,tolerance),_plane_cut(b,db,tolerance)
    if not ca or not cb: return None
    ta,tb=np.asarray(ca)@line,np.asarray(cb)@line
    lower,upper=max(ta.min(),tb.min()),min(ta.max(),tb.max())
    if upper<lower-tolerance: return None
    origin=ca[0];points=np.asarray([origin+line*(value-origin@line) for value in [lower,max(lower,upper)]])
    return {'kind':'segment' if upper-lower>tolerance else 'point','points':points,'length':float(max(0,upper-lower)),'area':0.}


def distinct_ray_hits(distances,tolerance=2e-6):
    """Count shared-edge duplicate hits once, retaining separated shell crossings."""
    values=np.sort(np.asarray(distances,dtype=float))
    if not np.isfinite(values).all() or (values<0).any(): raise ValueError('Finite forward hit distances required')
    if not len(values): return 0
    return 1+int(np.count_nonzero(np.diff(values)>tolerance))


def parity_consensus(counts):
    """Fail closed when independent rays disagree instead of inferring sign."""
    counts=np.asarray(counts,dtype=int)
    if counts.ndim!=1 or not len(counts) or (counts<0).any(): raise ValueError('Nonnegative ray counts required')
    values=counts%2
    return 'inside' if values.all() else ('outside' if not values.any() else 'ambiguous')


def closest_points_on_triangles(point, triangles):
    """Nearest points on actual triangle interiors/edges, without volume sign.

    Projects onto each triangle plane when inside, otherwise compares its three
    bounded edges. This supports exhaustive small point-to-mesh diagnostics.
    """
    point, triangles = np.asarray(point, dtype=float), np.asarray(triangles, dtype=float)
    if point.shape != (3,) or triangles.ndim != 3 or triangles.shape[1:] != (3, 3):
        raise ValueError('One point and an array of triangles required')
    if not np.isfinite(point).all() or not np.isfinite(triangles).all() or not len(triangles):
        raise ValueError('Finite nonempty geometry required')
    a, b, c = triangles[:, 0], triangles[:, 1], triangles[:, 2]
    normal = np.cross(b - a, c - a)
    squared = np.einsum('ij,ij->i', normal, normal)
    if (squared <= 0).any():
        raise ValueError('Nondegenerate triangles required')
    q = point - (np.einsum('ij,ij->i', point - a, normal) / squared)[:, None] * normal
    ub = np.einsum('ij,ij->i', np.cross(q - a, c - a), normal) / squared
    uc = np.einsum('ij,ij->i', np.cross(b - a, q - a), normal) / squared
    inside = (ub >= -1e-12) & (uc >= -1e-12) & (ub + uc <= 1 + 1e-12)
    candidates = [q]
    for start, end in [(a, b), (b, c), (c, a)]:
        edge = end - start
        fraction = np.clip(np.einsum('ij,ij->i', point - start, edge) /
                           np.einsum('ij,ij->i', edge, edge), 0, 1)
        candidates.append(start + fraction[:, None] * edge)
    points = np.stack(candidates, axis=1)
    distances = np.linalg.norm(points - point, axis=2)
    distances[~inside, 0] = np.inf
    selected = distances.argmin(axis=1)
    return points[np.arange(len(points)), selected]
