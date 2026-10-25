"""Repair (reviewed Alpha Wrap, shell selection, smoothing, collision-blocking QSlim) and head-local neck shaping:
shortening/lengthening, taper, seal and the cut that removes the neck onto the body's own neck part. Kept apart from
mesh.py so neck tuning stales only repair and its dependants, not precluster, export or native."""
from pathlib import Path
import time
import numpy as np
from .common import require, positive, library, pin, read, write
from .gltf import mesh, write_mesh
from .mesh import BASIS, audit, checked_fit, enclosed, physical, section, select_shells, topology, transform

def taper_scale(local, taper, bottom):
    """Radial neck scale: 1 above a start height that follows the jaw (front under the chin, back higher), then a
    smoothstep (zero slope at both ends: no shelf, no lip) down to minScale at the rim. Facing walls of a
    double-walled stump share each ray's angle, hence the same scale, so their order is kept."""
    x, y = (local[:, :2]-np.asarray(taper['axis'], float)).T
    start = taper['backStart']+(taper['frontStart']-taper['backStart'])*((1+np.cos(np.arctan2(x, y)))/2)**2
    t = np.clip((start-local[:, 2])/(start-bottom), 0, 1)
    return 1-(1-taper['minScale'])*t*t*(3-2*t)


def neck_policy(neck, fit):
    """Validate optional head-local neck shaping; it needs the reviewed rigid fit that defines face +y, up +z."""
    if neck is None: return None
    require(isinstance(neck, dict) and neck and set(neck) <= {'shorten', 'taper', 'seal', 'cut'}, 'Neck policy takes shorten, taper, seal and/or cut')
    require(isinstance(fit, dict) and fit.get('reviewed') is True and 'matrix' in fit,
            'Neck taper/seal needs the reviewed head fit matrix')
    number = lambda v: type(v) in (int, float) and np.isfinite(v)
    taper, seal, shorten, cut = neck.get('taper'), neck.get('seal'), neck.get('shorten'), neck.get('cut')
    if cut is not None:
        require(isinstance(cut, dict) and 'height' in cut
                and set(cut) <= {'height', 'slope', 'band', 'offset', 'reach', 'rise', 'clearance', 'searchBottom', 'notes'}
                and (number(cut['height']) or cut['height'] == 'measured'),
                "Neck cut declares a head-local height or 'measured' (optional slope, band, offset, reach, rise, clearance, searchBottom)")
        cut = dict({'slope': 0.0, 'band': .03, 'offset': -.003, 'reach': .04, 'rise': .003, 'clearance': .01, 'searchBottom': -.16}, **cut)
        require(number(cut['clearance']) and 0 <= cut['clearance'] <= .04, 'Neck cut clearance outside the supported profile')
        require(number(cut['searchBottom']) and -.3 <= cut['searchBottom'] <= -.05, 'Neck cut searchBottom outside -0.3..-0.05')
        require(number(cut['slope']) and abs(cut['slope']) <= .6, 'Neck cut slope (dz/dy) must be within +-0.6')
        require(number(cut['band']) and .01 <= cut['band'] <= .08 and number(cut['offset']) and -.015 <= cut['offset'] <= .005
                and number(cut['reach']) and .01 <= cut['reach'] <= .12 and number(cut['rise']) and 0 < cut['rise'] <= .02,
                'Neck cut band, offset, reach or cap rise outside the supported profile')
        require(seal is None, 'A cut neck is capped by the cut; it takes no seal')
    if shorten is not None:
        require(isinstance(shorten, dict) and {'start', 'rim'} <= set(shorten) <= {'start', 'rim', 'band', 'notes'}
                and number(shorten['start']) and number(shorten['rim']) and shorten['rim'] < shorten['start'],
                'Neck shortening declares a head-local start height and a lower target rim height (below the current rim lengthens)')
        shorten = dict({'band': .02}, **shorten)
        require(number(shorten['band']) and .005 <= shorten['band'] <= .05, 'Neck shortening band must be in [0.005, 0.05]')
    if taper is not None:
        require(isinstance(taper, dict) and set(taper) == {'minScale', 'frontStart', 'backStart', 'axis'},
                'Taper declares minScale, frontStart, backStart and axis')
        require(number(taper['minScale']) and .2 <= taper['minScale'] < 1, 'Taper minScale must be in [0.2, 1)')
        require(number(taper['frontStart']) and number(taper['backStart']), 'Taper start heights must be numbers')
        require(isinstance(taper['axis'], list) and len(taper['axis']) == 2 and all(map(number, taper['axis'])),
                'Taper axis is a head-local [x, y]')
    if seal is not None:
        require(isinstance(seal, dict) and {'height', 'inset', 'rise'} <= set(seal)
                and set(seal) <= {'height', 'inset', 'rise', 'margin', 'step', 'segments', 'searchTop'},
                'Seal declares height, inset and rise')
        seal = dict({'margin': .003, 'step': .0005, 'segments': 24}, **seal)
        require(seal['height'] == 'measured' or number(seal['height']), "Seal height is a number or 'measured'")
        require(number(seal['inset']) and .5 <= seal['inset'] <= 1 and number(seal['rise']) and 0 < seal['rise'] <= .05,
                'Seal inset must be in [0.5, 1] and rise in (0, 0.05]')
        require(number(seal['margin']) and 0 <= seal['margin'] <= .02 and number(seal['step']) and .0001 <= seal['step'] <= .005,
                'Seal margin/step outside the supported profile')
        require(type(seal['segments']) is int and 8 <= seal['segments'] <= 64, 'Seal segments must be 8..64')
        if seal['height'] == 'measured':
            require(number(seal.get('searchTop', 0)) and ('searchTop' in seal or taper is not None),
                    'Measured seal needs searchTop or a taper start')
    return {'frame': checked_fit(fit["matrix"]) @ BASIS, 'fitMatrix': checked_fit(fit["matrix"]).tolist(),
            'fitSourceSha256': fit.get('sourceSha256'), 'taper': taper, 'seal': seal, 'shorten': shorten, 'cut': cut}


def body_neck(path):
    """Head-local (face +y, up +z) triangles of the body's neck part, the surface a cut head neck must meet."""
    data = read(path)
    require(isinstance(data, dict) and data.get('kind') == 'srn-head-body-neck', 'Explicit srn-head-body-neck reference required')
    vertices = np.asarray(data['vertices'], float); faces = np.asarray(data['faces'], int)
    require(vertices.ndim == 2 and vertices.shape[1] == 3 and faces.ndim == 2 and faces.shape[1] == 3 and len(faces) >= 4
            and faces.min() >= 0 and faces.max() < len(vertices), 'Body neck needs head-local vertices and triangles')
    return vertices, faces


def section_radius(segments, centre, bins=720):
    """Radius of a closed section from centre in each of `bins` directions (outermost hit), by ray casting its segments."""
    theta = -np.pi+(np.arange(bins)+.5)*2*np.pi/bins; direction = np.c_[np.cos(theta), np.sin(theta)]
    a = segments[:, 0]-centre; e = segments[:, 1]-segments[:, 0]
    cross = lambda u, v: u[..., 0]*v[..., 1]-u[..., 1]*v[..., 0]
    denominator = cross(direction[:, None], e[None])
    with np.errstate(divide='ignore', invalid='ignore'):
        t = cross(a[None], e[None])/denominator; s = cross(a[None], direction[:, None])/denominator
    hit = (np.abs(denominator) > 1e-12) & (t > 0) & (s >= 0) & (s <= 1)
    radius = np.where(hit, t, -np.inf).max(1)
    require(np.isfinite(radius).all(), 'Body neck section must surround its centre')
    return radius


def body_profile(bv, bf, low, high, bins=720):
    """Lookup of the body neck surface between two heights: (centre xy, surface radius, angle bin) for head-local points.
    Radii are a +-10 degree circular mean, so the low-poly neck's facets do not print into the head."""
    require(bv[:, 2].min() < low and high < bv[:, 2].max(), 'Body neck must span the cut band')
    levels = np.linspace(low, high, 81); centres = []; radii = []; window = np.ones(41)/41
    for z in levels:
        ring = section(bv, bf, z); centre = ring.reshape(-1, 2).mean(0)
        require(enclosed(ring, centre), 'Body neck must be a closed ring across the cut band')
        r = section_radius(ring, centre, bins); centres.append(centre); radii.append(np.convolve(np.r_[r[-20:], r, r[:20]], window, 'valid'))
    centres = np.array(centres); radii = np.array(radii)
    def lookup(points, heights):
        k = (np.clip(heights, low, high)-low)/max(high-low, 1e-9)*(len(levels)-1); lo = np.floor(k).astype(int).clip(0, len(levels)-1)
        hi = np.minimum(lo+1, len(levels)-1); f = k-lo; centre = centres[lo]*(1-f)[:, None]+centres[hi]*f[:, None]
        offset = points[:, :2]-centre; index = np.floor((np.arctan2(offset[:, 1], offset[:, 0])+np.pi)/(2*np.pi)*bins).astype(int) % bins
        return centre, radii[lo, index]*(1-f)+radii[hi, index]*f, offset
    return lookup


def jaw_line(local, bv, bf, reach, slope, bottom=-.16):
    """Highest cut plane z = h + slope*y that passes under every front feature: over the front half below the head
    joint (y forward of the body neck centre), vertices standing more than `reach` outside the body neck are the chin,
    jaw corners, tusks or beard, never neck. h is the lowest of their z - slope*y; the neck below is what the cut
    removes. Only heights above `bottom` are searched: a long generated neck flares into a bust base about 20-25 cm under
    the joint (from about -0.19), which stands outside the body neck too. -0.16 reproduces the reviewed explicit heights
    of troll batch v2 (f15, f16, f19-f23; chins down to -0.136), where the unbounded search landed on the bust at -0.22..-0.25."""
    low = max(float(local[:, 2].min()), float(bv[:, 2].min())+1e-4, bottom)
    candidates = local[(local[:, 2] < 0) & (local[:, 2] > low)]
    lookup = body_profile(bv, bf, low, -1e-4); centre, surface, offset = lookup(candidates, candidates[:, 2])
    front = (offset[:, 1] > 0) & (np.linalg.norm(offset, axis=1)-surface > reach); features = candidates[front]
    require(len(features) > 0, 'No front feature (chin) stands beyond the reach; set an explicit cut height')
    intercept = features[:, 2]-slope*features[:, 1]; lowest = int(np.argmin(intercept))
    return {'height': float(intercept[lowest]), 'point': features[lowest].round(5).tolist(), 'reach': reach, 'slope': slope}


def neck_cut(vertices, faces, neck, body, rewrap=None):
    """Remove the head's neck so the body's own neck part forms the neck (as on stock heads): nothing long hangs below
    the head joint to show through the body in animation. The cut plane z = height + slope*y runs under the chin, jaw
    corners and any front feature ('measured': `clearance` below the lowest of them, see jaw_line) and is higher at
    the nape. Over `band` above the plane the remaining stub is drawn radially, about the body neck section centre at
    each height, onto the smoothed body neck surface plus `offset` (negative: just inside it). The weight is a
    smoothstep in height (0 at the band top: no shelf) times a smoothstep in distance outside the body neck (0 beyond
    `reach`) that fades out toward the plane, so features above the plane do not move, the cut lands on the surface,
    and the map stays monotonic along every ray. The shell is clipped at the plane. A single boundary ring is capped
    by a shallow fan facing down, inside the body neck. Several rings (a hollow, double-walled stump from wrapping an
    open neck) are closed by `rewrap`, the repair's own Alpha Wrap, which seals every boundary inside the body neck."""
    cut = dict(neck['cut']); local = transform(neck['frame'], vertices); band = cut['band']; bv, bf = body; jaw = None
    if cut['height'] == 'measured':
        jaw = jaw_line(local, bv, bf, cut['reach'], cut['slope'], cut['searchBottom']); cut['height'] = jaw['height']-cut['clearance']
    plane = lambda points: cut['height']+cut['slope']*points[:, 1]
    above = local[:, 2]-plane(local)
    require(above.min() < 0 < above.max(), 'Neck cut plane must cross the head')
    # Vertices below the plane are drawn fully, at the body radius of the plane above them, so every clipped edge
    # interpolates between drawn points and the cut lands on the target surface.
    moving = above < band; p = local[moving]
    require(np.count_nonzero(above[moving] > 0) > 0, 'Neck cut band holds no vertices')
    height_at = np.maximum(p[:, 2], plane(p)); lookup = body_profile(bv, bf, float(height_at.min()), float(height_at.max()))
    centre, surface, offset = lookup(p, height_at); radius = np.linalg.norm(offset, axis=1)
    smooth = lambda t: t*t*(3-2*t)
    # The reach protection fades out toward the plane (h**4), so the cut itself always lands on the body neck surface.
    h = smooth(np.clip(1-above[moving]/band, 0, 1)); protect = smooth(np.clip(1-(radius-surface)/cut['reach'], 0, 1))
    weight = np.where(above[moving] > 0, h*protect+h**4*(1-protect), 1)
    scale = np.where(radius > 1e-9, (radius+weight*(surface+cut['offset']-radius))/np.maximum(radius, 1e-9), 1)
    shaped = local.copy(); shaped[moving, :2] = centre+offset*scale[:, None]
    movement = np.linalg.norm(shaped-local, axis=1)
    # Clip at the plane: keep the part above, splitting crossing triangles on shared edge points.
    s = shaped[:, 2]-plane(shaped); s[np.abs(s) < 1e-9] = 1e-9; keep = s > 0
    points = {}; extra = []
    def edge_point(i, j):
        key = (min(i, j), max(i, j))
        if key not in points:
            w = s[i]/(s[i]-s[j]); points[key] = len(shaped)+len(extra); extra.append(shaped[i]+w*(shaped[j]-shaped[i]))
        return points[key]
    count = keep[faces].sum(1); clipped = []
    for face in faces[(count > 0) & (count < 3)]:
        polygon = []
        for corner in range(3):
            i, j = face[corner], face[(corner+1) % 3]
            if keep[i]: polygon.append(i)
            if keep[i] != keep[j]: polygon.append(edge_point(i, j))
        clipped += [[polygon[0], polygon[n], polygon[n+1]] for n in range(1, len(polygon)-1)]
    all_vertices = np.r_[shaped, np.array(extra).reshape(-1, 3)]; kept = np.r_[faces[count == 3], np.array(clipped, int).reshape(-1, 3)]
    # The cut leaves boundary edges (used once) in closed loops.
    edges = np.concatenate([kept[:, [0, 1]], kept[:, [1, 2]], kept[:, [2, 0]]])
    unique, counts = np.unique(np.sort(edges, 1), axis=0, return_counts=True); single = {tuple(e) for e in unique[counts == 1]}
    boundary = np.array([e for e in edges if tuple(sorted(e)) in single])
    require(len(boundary) >= 3 and set(boundary[:, 0]) == set(boundary[:, 1]), 'Neck cut must leave closed boundary loops')
    following = dict(zip(boundary[:, 0], boundary[:, 1])); loops = []; left = set(following)
    while left:
        start = min(left); loop = [start]; left.discard(start)
        while following[loop[-1]] != start:
            loop.append(following[loop[-1]]); require(loop[-1] in left, 'Broken cut ring'); left.discard(loop[-1])
        loops.append(loop)
    record = dict(cut, jawLine=jaw, previousRimHeight=float(local[:, 2].min()), conformedVertices=int(np.count_nonzero(movement > 1e-6)),
                  maximumMovementMetres=float(movement.max()), loops=sorted((len(l) for l in loops), reverse=True))
    ring_all = all_vertices[np.unique(boundary)]; record.update(rimFront=float(ring_all[:, 2].min()), rimBack=float(ring_all[:, 2].max()))
    used = np.unique(kept); remap = np.full(len(all_vertices), -1); remap[used] = np.arange(len(used))
    if len(loops) > 1:
        require(rewrap is not None, f'Neck cut leaves {len(loops)} rings (a hollow stump or a feature under the plane); '
                'only a wrapped repair (alphaWrap) can close them')
        sealed, sealed_faces = rewrap(transform(np.linalg.inv(neck['frame']), all_vertices[used]), remap[kept])
        record.update(closure='rewrap', profile='stub drawn onto the smoothed body neck + offset (height x reach smoothsteps); '
                      'plane cut z=height+slope*y; open rings closed by the repair Alpha Wrap')
        return sealed, sealed_faces, record
    loop = loops[0]; ring = all_vertices[loop]; require(np.abs(ring[:, 2]-plane(ring)).max() < 1e-6, 'Cut ring left the cut plane')
    # The centre rises into the head (a shallow cone, like the seal's): a flat fan's coplanar triangles read as crossings.
    middle = ring[:, :2].mean(0); middle = np.r_[middle, cut['height']+cut['slope']*middle[1]+cut['rise']]
    all_vertices = np.r_[all_vertices, [middle]]; cap = np.c_[boundary[:, 1], boundary[:, 0], np.full(len(boundary), len(all_vertices)-1)]
    corners = all_vertices[cap]; normal_z = np.cross(corners[:, 1]-corners[:, 0], corners[:, 2]-corners[:, 0])[:, 2]
    require((normal_z < 0).all(), 'Cut ring is not star-shaped about its centre; the cap fan would fold')
    kept = np.r_[kept, cap]; used = np.unique(kept); remap = np.full(len(all_vertices), -1); remap[used] = np.arange(len(used))
    record.update(closure='fan', ringVertices=len(loop), capTriangles=len(cap), ringSpan=np.ptp(ring[:, :2], 0).tolist(),
                  profile='stub drawn onto the smoothed body neck + offset (height x reach smoothsteps); plane cut z=height+slope*y; shallow fan cap facing down')
    return transform(np.linalg.inv(neck['frame']), all_vertices[used]), remap[kept], record


def shorten_depth(depth, scale, band):
    """Depth below the start after shortening: slope 1 at the start (no crease), easing to `scale` over about `band`.
    Strictly increasing, so every vertical column keeps its order and the surface cannot fold."""
    return scale*depth+(1-scale)*band*(1-np.exp(-depth/band))


def neck_shorten(vertices, neck):
    """Shorten an over-long stump on the dense master by compressing the neck below a reviewed head-local start height
    until its rim reaches a target height. The rounded closed end keeps its shape (no cut, no new cap); x and y are
    unchanged, so the taper that follows sees the same outline at a higher rim."""
    shorten = neck['shorten']; local = transform(neck['frame'], vertices); bottom = float(local[:, 2].min())
    start, band = shorten['start'], shorten['band']; depth = start-bottom; target = start-shorten['rim']
    require(bottom < start < local[:, 2].max() and shorten['rim'] < start, 'Neck shortening needs rim < start inside the head')
    # The far scale is solved; a band too wide for the shortening would need a scale near zero (a crushed stump). A rim
    # below the current one lengthens the neck with the same profile (far scale above 1, still strictly increasing).
    require(shorten_depth(depth, .1, band) < target < shorten_depth(depth, 4.0, band),
            'Neck shortening cannot reach its rim within the band; use a smaller band or a nearer rim')
    low, high = .1, 4.0
    for _ in range(60):
        middle = (low+high)/2; low, high = (middle, high) if shorten_depth(depth, middle, band) < target else (low, middle)
    scale = (low+high)/2; below = local[:, 2] < start; shaped = local.copy()
    shaped[below, 2] = start-shorten_depth(start-local[below, 2], scale, band)
    return transform(np.linalg.inv(neck['frame']), shaped), dict(
        shorten, previousRimHeight=bottom, rimHeight=float(shaped[:, 2].min()), farScale=float(scale),
        removedLengthMetres=float(shaped[:, 2].min()-bottom), movedVertices=int(np.count_nonzero(below)),
        profile='depth below start -> s*d+(1-s)*band*(1-exp(-d/band)): slope 1 at the start, s far below')


def neck_taper(vertices, faces, neck):
    """Taper the dense master, before reduction: the thin stump stays crossing-free only at master density."""
    taper = neck['taper']; local = transform(neck['frame'], vertices); bottom = float(local[:, 2].min())
    top = max(taper['frontStart'], taper['backStart']); axis = np.asarray(taper['axis'], float)
    require(min(taper['frontStart'], taper['backStart']) > bottom+.001 and top < local[:, 2].max(),
            'Taper must start inside the head, above the neck rim')
    require(enclosed(section(local, faces, top), axis), 'Taper axis must lie inside the closed neck ring at its start')
    scale = taper_scale(local, taper, bottom); shaped = local.copy()
    shaped[:, :2] = axis+(local[:, :2]-axis)*scale[:, None]
    movement = np.linalg.norm(shaped-local, axis=1)
    return transform(np.linalg.inv(neck['frame']), shaped), dict(
        taper, rimHeight=bottom, profile='smoothstep radial scale; start follows the jaw ((1+cos phi)/2)^2',
        movedVertices=int(np.count_nonzero(movement > 1e-9)), maximumMovementMetres=float(movement.max()))


def neck_seal(vertices, faces, neck, top):
    """Closed flat cone cap on the star-shaped inner outline of the lowest closed neck ring, inside the walls."""
    seal = neck['seal']; local = transform(neck['frame'], vertices); n = seal['segments']
    measured = seal['height'] == 'measured'; lowest = None
    if measured:
        top = seal.get('searchTop', top); bottom = local[:, 2].min(); step = seal['step']
        ring = lambda z: (lambda s: len(s) > 0 and enclosed(s, s.reshape(-1, 2).mean(0)))(section(local, faces, z))
        require(ring(top), 'Neck section must be a closed ring at the seal search top')
        lowest = top
        while lowest-step > bottom and ring(lowest-step): lowest -= step
        height = lowest+seal['margin']
        require(height < top, 'Seal margin reaches above its search top')
    else: height = float(seal['height'])
    cut = section(local, faces, height); points = cut.reshape(-1, 2)
    require(len(cut) > 0, 'Seal height misses the mesh'); centre = points.mean(0)
    require(enclosed(cut, centre), 'Seal height must cut a closed neck ring')
    angle = np.arctan2(points[:, 1]-centre[1], points[:, 0]-centre[0]); radius = np.linalg.norm(points-centre, axis=1)
    nearest = np.full(n, np.inf); np.minimum.at(nearest, np.floor((angle+np.pi)/(2*np.pi)*n).astype(int) % n, radius)
    require(np.isfinite(nearest).all(), 'Every seal direction needs an inner-wall section point')
    theta = -np.pi+(np.arange(n)+.5)*2*np.pi/n
    rim = centre+seal['inset']*nearest[:, None]*np.c_[np.cos(theta), np.sin(theta)]
    cap = np.r_[np.c_[rim, np.full(n, height)], [[*centre, height], [*centre, height+seal['rise']]]]
    k = np.arange(n)  # counter-clockwise from +z: the base fan faces down, the cone faces up
    cap_faces = np.r_[np.c_[np.full(n, n), (k+1) % n, k], np.c_[np.full(n, n+1), k, (k+1) % n]]
    return transform(np.linalg.inv(neck['frame']), cap), cap_faces, dict(
        seal, height=float(height), measured=measured, searchTop=float(top) if measured else None,
        lowestClosedRing=None if lowest is None else float(lowest), centre=centre.tolist(),
        outlineSpan=np.ptp(rim, 0).tolist(), capTriangles=len(cap_faces))


def repair(source, output, bindings, policy, inspection, fit=None, body=None):
    """No assumed holes, no discs, no component deletion without an explicit selection."""
    require(inspection.get('sourceSha256') == pin(source)['sha256'] and inspection.get('visualReviewed') is True,
            'Hash-bound exterior/underside review required')
    do_wrap = policy.get('alphaWrap', False)
    require(type(do_wrap) is bool, 'Explicit closure decision required')
    require(not do_wrap or (inspection.get('confirmedUnintendedOpening') is True
                            or inspection.get('confirmedShellDefect') is True), 'Do not repair an assumed opening')
    neck = neck_policy(policy.get('neck'), fit); work_dir = Path(output).parent
    require((body is not None) == (neck is not None and neck['cut'] is not None), 'A neck cut needs the bodyNeck reference, and only a cut reads it')
    original = mesh(source); vertices, faces = physical(original['positions'], original['faces'])

    if do_wrap:
        ml = library(bindings, 'pymeshlab'); diagonal = float(np.linalg.norm(np.ptp(vertices, axis=0)))
        alpha = positive(policy.get('alphaRelative', .005), 'Alpha Wrap alpha')
        offset = positive(policy.get('offsetRelative', .00025), 'Alpha Wrap offset')
        require(alpha <= .02 and offset <= .002, 'Wrap distances exceed supported profile')

        def wrap(vertices, faces):
            ms = ml.MeshSet(); ms.add_mesh(ml.Mesh(vertices.astype(float), faces.astype(np.int32)))
            ms.generate_alpha_wrap(alpha=ml.PureValue(diagonal*alpha), offset=ml.PureValue(diagonal*offset))
            current = ms.current_mesh(); current.compact(); return current.vertex_matrix(), current.face_matrix()
        vertices, faces = wrap(vertices, faces)
    else:
        require(topology(vertices, faces)['closed'], 'Open/invalid shell: review before selecting repair')
    vertices, faces, shell_record = select_shells(vertices, faces, policy.get('components'))
    smoothing = None
    if policy.get('smooth') is not None:
        from .relief import smooth
        require(isinstance(fit, dict) and fit.get('reviewed') is True and 'matrix' in fit, 'Smoothing regions need the reviewed head fit')
        begun = time.perf_counter(); vertices, records = smooth(vertices, faces, policy['smooth'], transform(checked_fit(fit['matrix']) @ BASIS, vertices))
        smoothing = {'regions': records, 'rewrapped': do_wrap}
        if do_wrap:
            # Collapsing thin fins on the master can pass faces through each other; a second wrap with the same distances
            # re-closes the smoothed surface crossing-free (smoothing the dense source instead is too weak at its density).
            selection = policy.get('components'); vertices, faces = wrap(vertices, faces)
            vertices, faces, smoothing['rewrapShells'] = select_shells(vertices, faces, None if selection is None else
                {k: v for k, v in selection.items() if k != 'expectedDeleted'})
        smoothing['elapsedSeconds'] = time.perf_counter()-begun
    budget = policy.get('triangleBudget', 20000)
    require(type(budget) is int and 4 <= budget <= 20000, 'Supported budget is <=20K')
    seal = neck is not None and neck['seal'] is not None
    target = budget-2*neck['seal']['segments'] if seal else budget  # the cap counts against the 20K budget
    require(target >= 4, 'Budget leaves no room for the reduced shell beside the neck cap')
    record = None
    if neck is not None:
        record = {'fitMatrix': neck['fitMatrix'], 'fitSourceSha256': neck['fitSourceSha256'],
                  'frame': 'fit matrix @ GLB->NWN (x,-z,y): face +y, up +z', 'taper': None, 'seal': None, 'cut': None,
                  'budget': {'total': budget, 'reservedForCap': budget-target, 'reductionTarget': target}}
    if neck is not None and neck['shorten'] is not None:
        begun = time.perf_counter(); vertices, record['shorten'] = neck_shorten(vertices, neck)
        record['shorten']['elapsedSeconds'] = time.perf_counter()-begun
    if neck is not None and neck['taper'] is not None:
        untapered = work_dir/'master-untapered.glb'; write_mesh(untapered, vertices, faces); begun = time.perf_counter()
        vertices, record['taper'] = neck_taper(vertices, faces, neck)
        record['taper'].update(untapered=pin(untapered), elapsedSeconds=time.perf_counter()-begun)
    if neck is not None and neck['cut'] is not None:
        uncut = work_dir/'master-uncut.glb'; write_mesh(uncut, vertices, faces); begun = time.perf_counter()
        vertices, faces, record['cut'] = neck_cut(vertices, faces, neck, body_neck(body), rewrap=wrap if do_wrap else None)
        if record['cut']['closure'] == 'rewrap':
            selection = policy.get('components')
            vertices, faces, record['cut']['rewrapShells'] = select_shells(vertices, faces, None if selection is None else
                {k: v for k, v in selection.items() if k != 'expectedDeleted'})
        record['cut'].update(uncut=pin(uncut), bodyNeck=pin(body), elapsedSeconds=time.perf_counter()-begun)
    master = work_dir / 'master.glb'; write_mesh(master, vertices, faces)
    master_audit = audit(master, max_pairs=16000000); write(work_dir/'master-audit.json', master_audit, fresh=True)
    require(master_audit['passed'], 'Master has invalid topology or crossings; retain failure evidence')
    births = None
    if len(faces) > target:
        work = work_dir/'qslim.npz'
        vertices, faces = _reduce(bindings, vertices, faces, target, work)
        require(0 < len(faces) <= target, 'QSlim did not reach the declared budget')
        births = pin(work)
    shell = work_dir/'reduced.glb' if seal else Path(output); write_mesh(shell, vertices, faces)
    if seal:
        begun = time.perf_counter(); reduced = mesh(shell); vertices, faces = physical(reduced['positions'], reduced['faces'])
        top = max(neck['taper']['frontStart'], neck['taper']['backStart']) if neck['taper'] is not None else None
        cap, cap_faces, record['seal'] = neck_seal(vertices, faces, neck, top)
        record['seal'].update(shell=pin(shell), shellTriangles=len(faces), elapsedSeconds=time.perf_counter()-begun)
        write_mesh(output, np.r_[vertices, cap], np.r_[faces, cap_faces+len(vertices)])
    result = audit(output)
    require(result['passed'], 'Reduced float32 shell failed topology/collision checks')
    require(result['topology']['triangles'] <= budget, 'Final shell exceeds the triangle budget')
    # Reduction error is measured against the (tapered) master, on the shell without the added cap.
    igl=library(bindings,'igl');reference=mesh(master);a,af=physical(reference['positions'],reference['faces'])
    z=mesh(shell);c,cf=physical(z['positions'],z['faces']);diagonal=float(np.linalg.norm(np.ptp(a,axis=0)))
    d1=igl.point_mesh_squared_distance(np.asarray(a,float),np.asarray(c,float),np.asarray(cf,np.int32))[0]
    d2=igl.point_mesh_squared_distance(np.asarray(c,float),np.asarray(a,float),np.asarray(af,np.int32))[0]
    maximum=float(np.sqrt(max(d1.max(),d2.max()))/diagonal)
    limit=positive(policy.get('maximumRelativeSurfaceError',.004),'surface error bound')
    require(limit<=.025,'Surface bound exceeds declared supported profile')
    result['surfaceDistance']={'relativeMaximum':maximum,'limit':limit,'passed':maximum<=limit,'reference':pin(master),
                              'measured':pin(shell),'method':'bidirectional vertices to exact triangles; not continuous Hausdorff'}
    result['neck'] = record
    write(work_dir/'reduction-audit.json',result,fresh=True)
    require(maximum<=limit,'Reduction exceeds measured surface error limit; retain and review before changing policy')
    result.update(master=pin(master), ancestry=births, alphaWrapApplied=do_wrap, componentDeletion=bool(shell_record['deleted']), shells=shell_record, smoothing=smoothing,
                  triangleBudget=budget, visualReviewRequired=True)
    return result


def _reduce(bindings, vertices, faces, target, work):
    import multiprocessing
    process = multiprocessing.get_context('spawn').Process(target=_reduce_worker, args=(bindings, vertices, faces, target, str(work)))
    process.start(); process.join(600)
    if process.is_alive():
        process.terminate(); process.join(15)
        raise TimeoutError('Owned QSlim child exceeded ten minutes; master and failed stage are preserved')
    require(process.exitcode == 0 and Path(work).is_file(), 'QSlim worker failed; inspect its retained traceback')
    with np.load(work, allow_pickle=False) as archive:
        return archive['vertices'], archive['faces']


def _reduce_worker(bindings,vertices,faces,budget,path):
    igl=library(bindings,'igl')
    vertices,faces,face_birth,vertex_birth=igl.qslim(np.asfortranarray(vertices,dtype=np.float64),
        np.asfortranarray(faces,dtype=np.int32),budget,block_intersections=True)
    np.savez(path,vertices=vertices,faces=faces,faceBirth=face_birth,vertexBirth=vertex_birth)
