"""Pure bounded port-cap construction and intersection guards.

This helper does not imply a closed exterior. Original source defects must be
pinned and compared independently. No existing repair helper is imported here.
"""
import numpy as np


def require(ok, message):
    if not ok:
        raise ValueError(message)


def orient(a, b, c):
    u, v = b-a, c-a
    return float(u[0]*v[1]-u[1]*v[0])


def signed_area(poly):
    nxt = np.roll(poly, -1, axis=0)
    return float(np.sum(poly[:, 0]*nxt[:, 1]-nxt[:, 0]*poly[:, 1])/2)


def segment_cross(a, b, c, d, eps=1e-12):
    return orient(a, b, c)*orient(a, b, d) < -eps and orient(c, d, a)*orient(c, d, b) < -eps


def ear_partition(poly):
    """Non-overlapping projected ears, with a simple-polygon guard."""
    poly = np.asarray(poly, float)
    require(poly.ndim == 2 and poly.shape[1] == 2 and len(poly) >= 3 and np.isfinite(poly).all(), 'Finite polygon required')
    require(len(np.unique(poly, axis=0)) == len(poly), 'Repeated projected port vertex')
    for i in range(len(poly)):
        for j in range(i+1, len(poly)):
            if j in (i, (i+1) % len(poly)) or i == (j+1) % len(poly):
                continue
            require(not segment_cross(poly[i], poly[(i+1) % len(poly)], poly[j], poly[(j+1) % len(poly)]), 'Self-crossing projected port')
    ar = signed_area(poly); sign = np.sign(ar)
    require(abs(ar) > 1e-12, 'Degenerate projected port')
    remaining = list(range(len(poly))); triangles = []
    while len(remaining) > 3:
        choices = []
        for k, b in enumerate(remaining):
            a, c = remaining[k-1], remaining[(k+1) % len(remaining)]
            cross = sign*orient(poly[a], poly[b], poly[c])
            if cross <= 1e-12:
                continue
            if any(min(sign*orient(poly[a], poly[b], poly[q]), sign*orient(poly[b], poly[c], poly[q]),
                       sign*orient(poly[c], poly[a], poly[q])) >= -1e-12 for q in remaining if q not in (a, b, c)):
                continue
            xyz = poly[[a, b, c]]
            quality = cross / float(np.sum((xyz-np.roll(xyz, -1, axis=0))**2))
            choices.append((-quality, k, (a, b, c)))
        require(bool(choices), 'No nondegenerate projected ear')
        _, k, tri = min(choices); triangles.append(tri); remaining.pop(k)
    triangles.append(tuple(remaining)); triangles = np.asarray(triangles, np.int64)
    areas = np.asarray([orient(*poly[t])/2 for t in triangles])
    require(np.all(sign*areas > 1e-14) and abs(areas.sum()-ar) < 1e-10, 'Projected partition coverage')
    return triangles


def build_cap(ring, inset_fraction, drop_source):
    """Keep a fixed ring; refine each projected ear into a shallow closed disk.

    Internal ear edges are replaced by shared two-point paths at the bottom
    plane, so no original boundary-to-boundary diagonal survives. Boundary
    strips and vertex corners descend within the declared barycentric fraction.
    Every projected triangle remains in one original ear, proving containment.
    """
    ring = np.asarray(ring, float)
    require(ring.ndim == 2 and ring.shape[1] == 3 and np.isfinite(ring).all(), 'Finite ring required')
    require(0 < inset_fraction <= .1 and 0 < drop_source <= .005, 'Explicit shallow construction bounds required')
    ears = ear_partition(ring[:, [0, 2]])
    require(signed_area(ring[:, [0, 2]]) > 0, 'Cap ring must oppose retained boundary and point downward')
    n = len(ring); level = float(ring[:, 1].min()-drop_source)
    vertices = ring.tolist(); owner = []; triangles = []; internal = {}
    boundary = {tuple(sorted((i, (i+1) % n))) for i in range(n)}
    def append(point):
        vertices.append(np.asarray(point, float).tolist()); return len(vertices)-1
    for ear_id, (a, b, c) in enumerate(ears):
        ids = [int(a), int(b), int(c)]; center = ring[ids].mean(0)
        inner = []
        for v in ids:
            q = (1-inset_fraction)*ring[v]+inset_fraction*center; q[1] = level
            inner.append(append(q))
        for i, a in enumerate(ids):
            b = ids[(i+1) % 3]; qa, qb = inner[i], inner[(i+1) % 3]
            key = tuple(sorted((a, b)))
            if key in boundary:
                pieces = [(a, b, qb), (a, qb, qa)]
            else:
                if key not in internal:
                    lo, hi = key; p = (1-inset_fraction)*ring[lo]+inset_fraction*ring[hi]
                    q = (1-inset_fraction)*ring[hi]+inset_fraction*ring[lo]
                    p[1] = q[1] = level; internal[key] = (append(p), append(q))
                first, last = internal[key] if a == key[0] else internal[key][::-1]
                pieces = [(a, first, qa), (first, last, qb), (first, qb, qa), (last, b, qb)]
            triangles.extend(pieces); owner.extend([ear_id]*len(pieces))
        triangles.append(tuple(inner)); owner.append(ear_id)
    positions = np.asarray(vertices, float); faces = np.asarray(triangles, np.int64)
    xyz = positions[faces]; normals = np.cross(xyz[:, 1]-xyz[:, 0], xyz[:, 2]-xyz[:, 0])
    require(np.all(normals[:, 1] < -1e-14), 'Projected cap folding or degeneracy')
    projected = normals[:, 1]*-.5
    require(abs(projected.sum()-signed_area(ring[:, [0, 2]])) < 1e-10, 'Exact cap footprint coverage')
    require(np.array_equal(positions[:n], ring), 'Original boundary positions changed')
    require(float(positions[:, 1].max()) <= float(ring[:, 1].max()) and float(positions[:, 1].min()) >= level, 'Depth bound exceeded')
    return {'positions': positions, 'faces': faces, 'ears': ears, 'faceEar': np.asarray(owner, np.int64),
            'boundaryCount': n, 'bottomY': level, 'insetFraction': inset_fraction, 'dropSource': drop_source}


def _unique(points, eps):
    unique = []
    for p in points:
        if not any(np.linalg.norm(p-q) <= eps for q in unique):
            unique.append(np.asarray(p, float))
    return unique


def triangle_contact(a, b, eps=1e-9):
    """Return the convex triangle intersection locus, including exact contact.

    Noncoplanar: intersect each triangle with the other's plane and overlap the
    intervals on their shared line. Coplanar: Sutherland-Hodgman clipping.
    Input triangles must have nonzero geometric area.
    """
    a, b = np.asarray(a, float), np.asarray(b, float)
    na = np.cross(a[1]-a[0], a[2]-a[0]); nb = np.cross(b[1]-b[0], b[2]-b[0])
    la, lb = np.linalg.norm(na), np.linalg.norm(nb)
    require(la > 1e-18 and lb > 1e-18, 'Degenerate intersection input')
    na, nb = na/la, nb/lb
    da = (a-b[0])@nb; db = (b-a[0])@na
    if da.min() > eps or da.max() < -eps or db.min() > eps or db.max() < -eps:
        return []
    line = np.cross(na, nb); length = np.linalg.norm(line)
    if length < 1e-10:
        if max(np.abs(da).max(), np.abs(db).max()) > eps:
            return []
        axis = int(np.argmax(np.abs(na))); dims = [i for i in range(3) if i != axis]
        aa, bb = a[:, dims], b[:, dims]; sign = np.sign(orient(*bb))
        out = [q.copy() for q in a]
        for i in range(3):
            c, d = bb[i], bb[(i+1) % 3]; old, out = out, []
            if not old:
                break
            for p, q in zip(old, old[1:]+old[:1]):
                dp, dq = sign*orient(c, d, p[dims]), sign*orient(c, d, q[dims])
                inp, inq = dp >= -eps, dq >= -eps
                if inp:
                    out.append(p)
                if inp != inq and abs(dp-dq) > 1e-20:
                    out.append(p+(q-p)*(dp/(dp-dq)))
        return _unique(out, eps)
    line /= length
    def plane_cut(tri, distances):
        pts = []
        for i in range(3):
            j = (i+1) % 3; x, y = distances[i], distances[j]
            if abs(x) <= eps:
                pts.append(tri[i])
            if x*y < 0 and abs(x-y) > 1e-20:
                pts.append(tri[i]+(tri[j]-tri[i])*(x/(x-y)))
        return _unique(pts, eps)
    pa, pb = plane_cut(a, da), plane_cut(b, db)
    if not pa or not pb:
        return []
    ta, tb = np.asarray(pa)@line, np.asarray(pb)@line
    lo, hi = max(ta.min(), tb.min()), min(ta.max(), tb.max())
    if hi < lo-eps:
        return []
    ref = pa[0]; t = float(ref@line)
    if hi-lo <= eps:
        return [ref+line*((hi+lo)/2-t)]
    return [ref+line*(lo-t), ref+line*(hi-t)]


def allowed_shared_contact(a, b, contacts, eps=1e-9):
    """Allow only contacts on their exact shared coordinate vertex/edge."""
    shared = [q for q in a if any(np.array_equal(q, p) for p in b)]
    if not contacts:
        return True
    if len(shared) == 1:
        return all(np.linalg.norm(q-shared[0]) <= eps*4 for q in contacts)
    if len(shared) == 2:
        x, y = shared; v = y-x; length2 = float(v@v)
        def on_edge(q):
            t = float((q-x)@v/length2)
            return -eps <= t <= 1+eps and np.linalg.norm(q-(x+np.clip(t, 0, 1)*v)) <= eps*4
        return all(on_edge(q) for q in contacts)
    return False


def intersect_meshes(first, second, eps=1e-9, same=False):
    """AABB-filtered independent exact triangle contacts; no ray inference."""
    first, second = np.asarray(first, float), np.asarray(second, float)
    minimum, maximum = second.min(1), second.max(1); failures = []; candidates = 0
    for i, a in enumerate(first):
        ids = np.flatnonzero(np.all(maximum >= a.min(0)-eps, axis=1) & np.all(minimum <= a.max(0)+eps, axis=1))
        if same:
            ids = ids[ids > i]
        for j in ids:
            b = second[j]; candidates += 1; contacts = triangle_contact(a, b, eps)
            if contacts and not allowed_shared_contact(a, b, contacts, eps):
                failures.append({'firstFace': int(i), 'secondFace': int(j), 'contacts': np.asarray(contacts).tolist()})
    return {'testedAabbPairs': candidates, 'forbiddenContacts': failures, 'contactToleranceSource': eps}


def chart_attributes(positions, faces):
    """Append cap-only flat authored normals and a consistent planar UV chart.

    Corner duplication creates valid tangent frames on steep boundary strips;
    old body rows are never reused or changed. The cap material is diagnostic.
    """
    corners = np.asarray(positions, float)[np.asarray(faces, int)]
    normal = np.cross(corners[:, 1]-corners[:, 0], corners[:, 2]-corners[:, 0])
    lengths = np.linalg.norm(normal, axis=1); require(np.all(lengths > 1e-14), 'Degenerate cap shading')
    normal /= lengths[:, None]
    low = np.asarray(positions).min(0)[[0, 2]]; extent = np.ptp(positions, axis=0)[[0, 2]]
    require(np.all(extent > 0), 'Degenerate cap UV chart')
    uv = (corners[:, :, [0, 2]]-low)/extent
    duv = uv[:, 1:]-uv[:, :1]; edges = corners[:, 1:]-corners[:, :1]
    determinant = duv[:, 0, 0]*duv[:, 1, 1]-duv[:, 0, 1]*duv[:, 1, 0]
    require(np.all(np.abs(determinant) > 1e-14), 'Degenerate cap UV triangle')
    tangent = (edges[:, 0]*duv[:, 1, 1, None]-edges[:, 1]*duv[:, 0, 1, None])/determinant[:, None]
    bitangent = (edges[:, 1]*duv[:, 0, 0, None]-edges[:, 0]*duv[:, 1, 0, None])/determinant[:, None]
    tangent -= normal*np.einsum('ij,ij->i', normal, tangent)[:, None]; tangent /= np.linalg.norm(tangent, axis=1)[:, None]
    hand = np.sign(np.einsum('ij,ij->i', np.cross(normal, tangent), bitangent))
    t = np.column_stack((tangent, hand))
    return {'POSITION': corners.reshape(-1, 3), 'NORMAL': np.repeat(normal, 3, axis=0),
            'TEXCOORD_0': uv.reshape(-1, 2), 'TANGENT': np.repeat(t, 3, axis=0),
            'faces': np.arange(corners.size//3, dtype=np.int64).reshape(-1, 3)}
