"""Pure geometry checks used by the Blender worker and synthetic regressions."""
import numpy as np
from tools.headkit.common import require


def similarity_matrix(config, source_sha):
    require(config.get('reviewed') is True and config.get('sourceSha256') == source_sha,
            'Fit must be reviewed against this exact textured donor')
    matrix = np.asarray(config['matrix'], float)
    require(matrix.shape == (4, 4) and np.isfinite(matrix).all() and np.allclose(matrix[3], [0, 0, 0, 1]),
            'Finite affine fit required')
    gram = matrix[:3, :3].T @ matrix[:3, :3]
    require(np.linalg.det(matrix[:3, :3]) > 0 and np.allclose(gram, np.eye(3)*gram[0, 0], rtol=1e-7, atol=1e-12),
            'Item fitting must preserve proportions with a positive uniform similarity')
    return matrix


def transform(vertices, matrix):
    return np.asarray(vertices) @ matrix[:3, :3].T + matrix[:3, 3]


def cap_fan_center(vertices):
    """Return a safe interior fan point without deleting collinear rim corners.

    Native cuts through triangulated surfaces often create collinear boundary
    points. Ear triangulation can make zero-area caps from those points. A fan
    preserves the exact mating contour; reject it when the mean is not inside
    every directed boundary half-plane, so concave caps retain the general path.
    """
    p = np.asarray(vertices, float)
    if len(p) < 4 or not np.isfinite(p).all(): return None
    center = p.mean(axis=0); a = p-center; b = np.roll(a, -1, axis=0)
    cross = np.cross(a, b); normal = cross.sum(axis=0); length = np.linalg.norm(normal)
    if length <= 1e-12: return None
    normal /= length
    if np.max(np.abs(a@normal)) > 1e-6 or np.any(cross@normal <= 1e-12): return None
    return center


def camera_basis(location,target,up):
    forward=np.asarray(target,float)-location;forward/=np.linalg.norm(forward);up=np.asarray(up,float)
    if abs(np.dot(forward,up)/np.linalg.norm(up))>.999:
        up=np.array([0.,1.,0.]) if abs(forward[1])<.99 else np.array([0.,0.,1.])
    right=np.cross(forward,up);right/=np.linalg.norm(right);vertical=np.cross(right,forward)
    return np.column_stack([right,vertical,-forward])


def topology(vertices, faces):
    vertices, faces = np.asarray(vertices, float), np.asarray(faces)
    require(vertices.ndim == 2 and vertices.shape[1] == 3 and np.isfinite(vertices).all(), 'Finite vertices required')
    require(faces.ndim == 2 and faces.shape[1] == 3 and np.issubdtype(faces.dtype, np.integer)
            and len(faces) and faces.min() >= 0 and faces.max() < len(vertices), 'Valid triangles required')
    # Weld exact coordinate duplicates for audits, without changing authored geometry or UV seams.
    unique, ids = np.unique(vertices, axis=0, return_inverse=True)
    f = ids[faces]; p = unique[f]
    area = np.linalg.norm(np.cross(p[:, 1]-p[:, 0], p[:, 2]-p[:, 0]), axis=1)
    edges = {}; links = [[] for _ in unique]
    for face in f:
        a,b,c=map(int,face)
        links[a].append((b,c)); links[b].append((c,a)); links[c].append((a,b))
        for a, b in zip(face, np.roll(face, -1)):
            key = tuple(sorted((int(a), int(b))))
            edges.setdefault(key, []).append(1 if a < b else -1)
    boundary = sum(len(rows) == 1 for rows in edges.values())
    nonmanifold = sum(len(rows) > 2 for rows in edges.values())
    winding = sum(len(rows) == 2 and sum(rows) != 0 for rows in edges.values())
    invalid_links=0
    for rows in links:
        if not rows: continue
        neighbors={}
        for a,b in rows:
            neighbors.setdefault(a,[]).append(b); neighbors.setdefault(b,[]).append(a)
        if any(len(values)!=2 for values in neighbors.values()): invalid_links+=1; continue
        visited=set(); pending=[next(iter(neighbors))]
        while pending:
            node=pending.pop()
            if node in visited: continue
            visited.add(node); pending.extend(value for value in neighbors[node] if value not in visited)
        if len(visited)!=len(neighbors): invalid_links+=1
    per_face_volume = np.einsum('ij,ij->i', p[:, 0], np.cross(p[:, 1], p[:, 2]))/6
    parent = list(range(len(unique)))
    def root(i):
        while parent[i] != i: parent[i] = parent[parent[i]]; i = parent[i]
        return i
    for a, b, c in f:
        for x in (b, c): parent[root(int(x))] = root(int(a))
    components = {}
    for face, volume in zip(f, per_face_volume):
        key = root(int(face[0])); components[key] = components.get(key, 0.)+float(volume)
    volumes = float(per_face_volume.sum())
    euler=int(np.count_nonzero(np.bincount(f.ravel(),minlength=len(unique))))-len(edges)+len(f)
    valid_closed=boundary == nonmanifold == winding == invalid_links == 0 and bool(np.all(area > 1e-12)) and all(volume > 0 for volume in components.values())
    return {'triangles': len(f), 'degenerate': int(np.count_nonzero(area <= 1e-12)),
            'eulerCharacteristic':euler,'totalGenus':(2*len(components)-euler)//2 if valid_closed else None,
            'boundaryEdges': boundary, 'nonmanifoldEdges': nonmanifold,
            'invalidVertexLinks': invalid_links,
            'inconsistentEdges': winding, 'signedVolume': volumes,
            'componentVolumes': list(components.values()),
            'closedWound': valid_closed}


def segment_hits(vertices, faces, start, end):
    """Moller-Trumbore intersections strictly inside a declared opening probe."""
    triangles = np.asarray(vertices, float)[faces]
    origin, target = np.asarray(start, float), np.asarray(end, float)
    require(origin.shape == target.shape == (3,) and np.isfinite([origin, target]).all()
            and np.linalg.norm(target-origin) > 0, 'Nonzero finite opening probe required')
    direction = target-origin
    a = triangles[:, 1]-triangles[:, 0]; b = triangles[:, 2]-triangles[:, 0]
    h = np.cross(direction, b); det = np.einsum('ij,ij->i', a, h)
    valid = np.abs(det) > 1e-12
    inv = np.zeros_like(det); inv[valid] = 1/det[valid]
    s = origin-triangles[:, 0]; u = inv*np.einsum('ij,ij->i', s, h)
    q = np.cross(s, a); v = inv*(q @ direction); t = inv*np.einsum('ij,ij->i', b, q)
    return int(np.count_nonzero(valid & (u >= 0) & (v >= 0) & (u+v <= 1) & (t > 1e-7) & (t < 1-1e-7)))


def closest_surface_point(vertices, faces, point):
    """Nearest point on triangles; sample checks must not depend on vertex density."""
    triangles = np.asarray(vertices, float)[faces]; point = np.asarray(point, float)
    a = triangles[:, 0]; ab = triangles[:, 1]-a; ac = triangles[:, 2]-a
    normal = np.cross(ab, ac); norm2 = np.einsum('ij,ij->i', normal, normal)
    projection = point+normal*(np.einsum('ij,ij->i', a-point, normal)/np.maximum(norm2, 1e-30))[:, None]
    q = projection-a; aa = np.einsum('ij,ij->i', ab, ab); bb = np.einsum('ij,ij->i', ac, ac)
    cross = np.einsum('ij,ij->i', ab, ac); det = aa*bb-cross*cross
    u = (bb*np.einsum('ij,ij->i', q, ab)-cross*np.einsum('ij,ij->i', q, ac))/np.maximum(det, 1e-30)
    v = (aa*np.einsum('ij,ij->i', q, ac)-cross*np.einsum('ij,ij->i', q, ab))/np.maximum(det, 1e-30)
    inside = (u >= 0) & (v >= 0) & (u+v <= 1) & (norm2 > 1e-30)
    candidates = [np.where(inside[:, None], projection, np.inf)]
    for first, second in ((0, 1), (1, 2), (2, 0)):
        start = triangles[:, first]; edge = triangles[:, second]-start
        fraction = np.clip(np.einsum('ij,ij->i', point-start, edge)/np.maximum(np.einsum('ij,ij->i', edge, edge), 1e-30), 0, 1)
        candidates.append(start+edge*fraction[:, None])
    points = np.concatenate(candidates)
    return points[np.argmin(np.linalg.norm(points-point, axis=1))]


def hidden_cap_faces(vertices, faces, join_y, tolerance=1e-7):
    triangles = np.asarray(vertices, float)[faces]
    caps = np.zeros(len(faces), bool)
    for plane in join_y:
        caps |= np.all(np.abs(triangles[:, :, 1]-plane) < tolerance, axis=1)
    return caps


def loop_shadow_proxy(vertices,faces,probe,maximum_outline=12):
    """Build the closed loop in the measured aperture frame, including oblique bores."""
    p=np.asarray(vertices,float);start=np.asarray(probe['start'],float);end=np.asarray(probe['end'],float)
    require(start.shape==end.shape==(3,) and np.isfinite([start,end]).all(),'Finite shadow opening endpoints required')
    axis=end-start;length=np.linalg.norm(axis);require(length>1e-12,'Shadow opening axis has zero length')
    if np.allclose(start[1:],end[1:]) and end[0]>start[0]:
        return _axis_aligned_shadow_loop(p,faces,probe,maximum_outline)
    axis/=length;up=np.array([0.,1.,0.])
    if abs(np.dot(axis,up))>.99:up=np.array([0.,0.,1.])
    across=up-axis*np.dot(axis,up);across/=np.linalg.norm(across)
    basis=np.column_stack([axis,across,np.cross(axis,across)])
    local=(p-start)@basis;local_probe={**probe,'start':[0.,0.,0.],'end':[float(length),0.,0.]}
    result,triangles,report=_axis_aligned_shadow_loop(local,faces,local_probe,maximum_outline)
    result=result@basis.T+start
    require(topology(result,triangles)['closedWound'] and segment_hits(result,triangles,start,end)==0,
            'Measured-axis shadow loop is not closed or obstructs its opening')
    report.update(axisFrame={'origin':start.tolist(),'basisColumns':basis.tolist()},
                  sourceBounds=[p.min(0).tolist(),p.max(0).tolist()],proxyBounds=[result.min(0).tolist(),result.max(0).tolist()])
    return result,triangles,report


def _axis_aligned_shadow_loop(vertices,faces,probe,maximum_outline=12):
    """Closed variable-thickness silhouette with a measured through opening.

    A matched outer/inner ring uses eight triangles per outline vertex. Twelve
    vertices therefore preserve the principal loop within a 100-triangle part.
    """
    p=np.asarray(vertices,float);projected=p[:,1:];start=np.asarray(probe['start']);end=np.asarray(probe['end'])
    require(np.allclose(start[1:],end[1:]) and end[0]>start[0],'Shadow loop requires the measured native X opening axis')
    centre=start[1:];unique=np.unique(projected,axis=0);ordered=sorted(map(tuple,unique))
    def turn(a,b,c):
        u=np.asarray(b)-a;v=np.asarray(c)-b
        return float(u[0]*v[1]-u[1]*v[0])
    lower=[];upper=[]
    for point in ordered:
        while len(lower)>=2 and turn(lower[-2],lower[-1],point)<=0:lower.pop()
        lower.append(point)
    for point in reversed(ordered):
        while len(upper)>=2 and turn(upper[-2],upper[-1],point)<=0:upper.pop()
        upper.append(point)
    hull=lower[:-1]+upper[:-1];anchors={min(hull,key=lambda q:q[a]) for a in (0,1)}|{max(hull,key=lambda q:q[a]) for a in (0,1)}
    while len(hull)>maximum_outline:
        eligible=[(abs(turn(hull[i-1],q,hull[(i+1)%len(hull)])),i) for i,q in enumerate(hull) if q not in anchors]
        require(bool(eligible),'Cannot simplify protected shadow outline');hull.pop(min(eligible)[1])
    outer=np.asarray(hull);n=len(outer);require(3<=n<=12,'Shadow outline exceeds the native pommel budget')
    x0=p[:,0].min()-.001;x1=p[:,0].max()+.001;inner=[]
    for target in outer:
        direction=target-centre;previous=0.;hit=None
        for fraction in np.linspace(0,1,97)[1:]:
            q=centre+fraction*direction
            if segment_hits(p,faces,[x0,*q],[x1,*q]):hit=float(fraction);break
            previous=float(fraction)
        require(hit is not None,'Shadow loop radial boundary is not closed')
        for _ in range(14):
            mid=(previous+hit)/2;q=centre+mid*direction
            if segment_hits(p,faces,[x0,*q],[x1,*q]):hit=mid
            else:previous=mid
        inner.append(centre+previous*.95*direction)
    inner=np.asarray(inner);cx=(p[:,0].min()+p[:,0].max())/2;global_half=np.ptp(p[:,0])/2
    def thickness(q):
        ids=np.argsort(np.linalg.norm(projected-q,axis=1))[:12]
        return max(global_half*.1,float(np.quantile(np.abs(p[ids,0]-cx),.9)))
    outer_h=np.array([thickness(q) for q in outer]);inner_h=np.array([thickness(q) for q in inner])
    result=np.concatenate([np.c_[cx+outer_h,outer],np.c_[cx+inner_h,inner],np.c_[cx-outer_h,outer],np.c_[cx-inner_h,inner]])
    triangles=[]
    for i in range(n):
        j=(i+1)%n
        for quad in ((i,j,n+j,n+i),(2*n+i,3*n+i,3*n+j,2*n+j),(i,2*n+i,2*n+j,j),(n+j,3*n+j,3*n+i,n+i)):
            a,b,c,d=quad;triangles.extend(((a,b,c),(a,c,d)))
    triangles=np.asarray(triangles,int);require(topology(result,triangles)['closedWound'],'Constructed shadow loop is not closed and outward')
    require(segment_hits(result,triangles,start,end)==0,'Constructed shadow obstructs its measured opening')
    return result,triangles,{'method':'projected-loop','outlineVertices':n,'triangles':len(triangles),'outerYZ':outer.tolist(),'innerYZ':inner.tolist(),'sourceBounds':[p.min(0).tolist(),p.max(0).tolist()],'proxyBounds':[result.min(0).tolist(),result.max(0).tolist()]}


def protected_checks(vertices, faces, config):
    report = {'openings': [], 'thickness': []}
    for row in config.get('openingProbes', []):
        hits = segment_hits(vertices, faces, row['start'], row['end'])
        require(hits == 0, 'Intentional opening obstructed: ' + row['name'])
        report['openings'].append({'name': row['name'], 'hits': hits})
    # Thickness endpoints identify retained opposed surface positions. Nearest distances
    # are an explicit sampled check; they do not assert a continuous thickness proof.
    p = np.asarray(vertices)
    for row in config.get('thicknessProbes', []):
        ends = np.asarray(row['points'], float)
        require(ends.shape == (2, 3) and np.isfinite(ends).all(), 'Two thickness samples required')
        picked = np.array([closest_surface_point(p, faces, point) for point in ends])
        distance = float(np.linalg.norm(picked[1]-picked[0]))
        residual = float(np.linalg.norm(picked-ends, axis=1).max())
        require(row['minimum'] > 0 and distance >= row['minimum'] and residual <= row['maximumSampleError'],
                'Protected thickness sample failed: ' + row['name'])
        report['thickness'].append({'name': row['name'], 'distance': distance, 'maximumSampleError': residual})
    return report


def check_budgets(counts, budgets, kind):
    require(set(counts) == set(budgets['parts']), 'Count every native part')
    require(all(type(n) is int and (0 < n <= budgets['parts'][p][kind]
                or n == 0 == budgets['parts'][p][kind]) for p, n in counts.items()), 'Per-part '+kind+' budget exceeded')
    require(sum(counts.values()) <= budgets[kind], 'Whole-object '+kind+' budget exceeded')
    return {'parts': counts, 'assembly': sum(counts.values()), 'limit': budgets[kind]}
