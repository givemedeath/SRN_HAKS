"""Exterior-shell audit, reviewed Alpha Wrap, head-local neck taper/seal, and collision-blocking QSlim."""
from pathlib import Path
import time
import numpy as np
from .common import require, positive, library, pin, verify, write
from .gltf import mesh, write_mesh
from .intersections import scan


def physical(vertices, faces):
    corners = np.asarray(vertices)[np.asarray(faces)]
    values, inverse = np.unique(corners.reshape(-1, 3), axis=0, return_inverse=True)
    return values, inverse.reshape(-1, 3)


def topology(vertices, faces):
    return _topology(*physical(vertices, faces))


def _topology(vertices, faces):
    edges = np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]])
    undirected = np.sort(edges, axis=1)
    _, inverse, counts = np.unique(undirected[:, 0]*np.int64(len(vertices))+undirected[:, 1], return_inverse=True, return_counts=True)
    orientation = np.zeros(len(counts), int)
    np.add.at(orientation, inverse, np.where(edges[:, 0] < edges[:, 1], 1, -1))
    corners = vertices[faces].astype(float)
    areas = np.linalg.norm(np.cross(corners[:, 1]-corners[:, 0], corners[:, 2]-corners[:, 0]), axis=1)
    boundary = int(np.count_nonzero(counts == 1)); nonmanifold = int(np.count_nonzero(counts > 2))
    winding = int(np.count_nonzero((counts == 2) & (orientation != 0)))
    # Every vertex link on the supported closed shell must be one simple cycle: each link node of degree two, one component.
    owner = np.concatenate(faces.T); link = np.concatenate([faces[:, [1, 2]], faces[:, [2, 0]], faces[:, [0, 1]]])
    keys, node = np.unique(np.r_[owner, owner]*np.int64(len(vertices))+link.T.reshape(-1), return_inverse=True)
    node = node.reshape(2, -1); count = len(keys); held = keys//len(vertices)
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    labels = connected_components(coo_matrix((np.ones(node.shape[1]), (node[0], node[1])), (count, count)), directed=False)[1]
    cycles = np.bincount(held[np.unique(labels, return_index=True)[1]], minlength=len(vertices))
    bad_links = int(np.count_nonzero((cycles != 1) | (np.bincount(held, np.bincount(node.reshape(-1), minlength=count) != 2, len(vertices)) > 0)))
    zeros = int(np.count_nonzero(areas <= 1e-14))
    return {'triangles': len(faces), 'physicalVertices': len(vertices), 'boundaryEdges': boundary,
            'nonmanifoldEdges': nonmanifold, 'windingConflicts': winding, 'zeroAreaFaces': zeros,
            'invalidVertexLinks': bad_links, 'closed': not (boundary or nonmanifold or winding or zeros or bad_links)}


def audit(path, max_pairs=4000000):
    value = mesh(path); vertices, faces = physical(value['positions'], value['faces'])
    top = _topology(vertices, faces); crossings = scan(vertices, faces, max_pairs=max_pairs)
    return {'source': pin(path), 'topology': top, 'crossings': crossings,
            'passed': top['closed'] and crossings['complete'] and not crossings['pairs'],
            'visualReviewRequired': True}


def precluster(source, output, bindings, resolution=512):
    """Bound CPU source size before the 768 UDF remesh; preserve this source separately."""
    require(type(resolution) is int and 64 <= resolution <= 2048, 'Declared precluster resolution required')
    original = mesh(source); vertices, faces = original['positions'],original['faces']
    lo = vertices.min(0); size = float(np.max(np.ptp(vertices, axis=0)))
    positive(size, 'mesh extent')
    cells = np.floor((vertices-lo) / size * resolution).astype(np.int64)
    _, groups = np.unique(cells, axis=0, return_inverse=True)
    clustered = np.zeros((groups.max()+1, 3), float); np.add.at(clustered, groups, vertices)
    clustered /= np.bincount(groups)[:, None]; result = groups[faces]
    keep = np.all(np.diff(np.sort(result, axis=1), axis=1) != 0, axis=1); result = result[keep]
    require(len(result) > 0, 'Precluster removed all faces')
    _,first=np.unique(np.sort(result,axis=1),axis=0,return_index=True);result=result[np.sort(first)]
    tri=clustered[result];result=result[np.linalg.norm(np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]),axis=1)>0]
    movement=float(np.max(np.linalg.norm(clustered[groups]-vertices,axis=1)))
    diagonal=float(np.linalg.norm(np.ptp(vertices,axis=0)));require(movement/diagonal<=.004,'Precluster assigned-vertex displacement exceeds .4%')
    used,inverse=np.unique(result,return_inverse=True);clustered=clustered[used];result=inverse.reshape(-1,3)
    igl=library(bindings,'igl');result,components=igl.bfs_orient(np.asarray(result,np.int32))
    tri=clustered[result];volumes=np.bincount(components,weights=np.einsum('ij,ij->i',tri[:,0],np.cross(tri[:,1],tri[:,2]))/6)
    flipped=volumes[components]<0;result[flipped]=result[flipped][:,[0,2,1]]
    write_mesh(output, clustered, result)
    return {'source': pin(source), 'output': pin(output), 'resolution': resolution,
            'maximumAssignedVertexMovementRelativeToDiagonal':movement/diagonal,'notFullHausdorffBound':True,
            'beforeTriangles': len(faces), 'afterTriangles': len(result), 'visualReviewRequired': True}


BASIS = np.array([[1., 0, 0, 0], [0, 0, -1., 0], [0, 1., 0, 0], [0, 0, 0, 1.]])  # GLB -> NWN (x,-z,y)


def checked_fit(matrix):
    matrix = np.asarray(matrix, float)
    require(matrix.shape == (4, 4) and np.isfinite(matrix).all() and np.allclose(matrix[3], [0, 0, 0, 1]), 'Invalid fit transform')
    gram = matrix[:3, :3].T @ matrix[:3, :3]
    require(np.linalg.det(matrix[:3, :3]) > 0 and np.allclose(gram, np.eye(3)*gram[0, 0], atol=1e-8),
            'Fit must be a positive uniform similarity')
    return matrix


def transform(matrix, points):
    return (np.c_[points, np.ones(len(points))] @ np.asarray(matrix).T)[:, :3]


def section(local, faces, z):
    """Horizontal section of a triangle mesh at height z as (n, 2, 2) xy segments."""
    tri = local[faces]; s = tri[:, :, 2]-z; above = s > 0; keep = above.sum(1) % 3 != 0
    tri, s, above = tri[keep], s[keep], above[keep]; points, cuts = [], []
    for a, b in ((0, 1), (1, 2), (2, 0)):
        cut = above[:, a] != above[:, b]; w = np.where(cut, s[:, a]/np.where(cut, s[:, a]-s[:, b], 1), 0)
        points.append(tri[:, a, :2]+w[:, None]*(tri[:, b, :2]-tri[:, a, :2])); cuts.append(cut)
    order = np.argsort(~np.stack(cuts, 1), axis=1, kind='stable')[:, :2]
    return np.take_along_axis(np.stack(points, 1), order[:, :, None], 1)


def enclosed(segments, centre, bins=720):
    """True when the section sweeps every angle around centre: a closed ring, independent of density."""
    if not len(segments): return False
    a = np.arctan2(segments[..., 1]-centre[1], segments[..., 0]-centre[0])
    d = (a[:, 1]-a[:, 0]+np.pi) % (2*np.pi)-np.pi; low = np.where(d >= 0, a[:, 0], a[:, 1])
    start = np.floor((low+np.pi)/(2*np.pi)*bins).astype(int); end = np.floor((low+np.abs(d)+np.pi)/(2*np.pi)*bins).astype(int)
    first = start % bins; last = first+end-start
    marks = np.zeros(2*bins+1, int); np.add.at(marks, first, 1); np.add.at(marks, last+1, -1)
    run = np.cumsum(marks)[:2*bins]
    return bool(np.all(run[:bins]+run[bins:] > 0))


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
    require(isinstance(neck, dict) and neck and set(neck) <= {'taper', 'seal'}, 'Neck policy takes taper and/or seal')
    require(isinstance(fit, dict) and fit.get('reviewed') is True and 'matrix' in fit,
            'Neck taper/seal needs the reviewed head fit matrix')
    number = lambda v: type(v) in (int, float) and np.isfinite(v)
    taper, seal = neck.get('taper'), neck.get('seal')
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
            'fitSourceSha256': fit.get('sourceSha256'), 'taper': taper, 'seal': seal}


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


def shells(vertices, faces):
    """Face labels of the edge-connected shells."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    edges = np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]]); n = len(vertices)
    labels = connected_components(coo_matrix((np.ones(len(edges)), (edges[:, 0], edges[:, 1])), (n, n)), directed=False)[1]
    return np.unique(labels[faces[:, 0]], return_inverse=True)[1].reshape(-1)


def select_shells(vertices, faces, selection):
    """A master must be one shell. Detached floaters and interior bubbles go only by a reviewed selection that keeps
    the largest-area shell, bounds the deleted area and records every deleted shell."""
    label = shells(vertices, faces); count = int(label.max())+1
    if selection is None:
        require(count == 1, f'Master has {count} separate shells; review them and declare mesh.components')
        return vertices, faces, {'shells': 1, 'deleted': [], 'deletedAreaFraction': 0.0}
    require(isinstance(selection, dict) and selection.get('keep') == 'largest' and selection.get('reviewed') is True,
            'Shell selection must be reviewed and keep the largest shell')
    limit = positive(selection.get('maximumDeletedAreaFraction', .01), 'deleted shell area bound')
    require(limit <= .05, 'Deleted shell area bound exceeds supported profile')
    corners = vertices[faces].astype(float)
    area = np.linalg.norm(np.cross(corners[:, 1]-corners[:, 0], corners[:, 2]-corners[:, 0]), axis=1)/2
    totals = np.bincount(label, area, count); keep = int(np.argmax(totals)); fraction = float(1-totals[keep]/totals.sum())
    deleted = [{'triangles': int(np.count_nonzero(label == k)), 'areaFraction': float(totals[k]/totals.sum()),
                'centroid': [round(float(c), 5) for c in vertices[np.unique(faces[label == k])].mean(0)]}
               for k in np.argsort(-totals) if k != keep]
    require(fraction <= limit, f'Deleted shells cover {fraction:.3%} of the master area, above the reviewed bound')
    expected = selection.get('expectedDeleted')
    require(expected is None or expected == len(deleted), f'{len(deleted)} shells would be deleted; the review expected {expected}')
    used = np.unique(faces[label == keep]); remap = np.full(len(vertices), -1); remap[used] = np.arange(len(used))
    return vertices[used], remap[faces[label == keep]], {'shells': count, 'deleted': deleted, 'deletedAreaFraction': fraction,
                                                        'keptTriangles': int(np.count_nonzero(label == keep))}


def repair(source, output, bindings, policy, inspection, fit=None):
    """No assumed holes, no discs, no component deletion without an explicit selection."""
    require(inspection.get('sourceSha256') == pin(source)['sha256'] and inspection.get('visualReviewed') is True,
            'Hash-bound exterior/underside review required')
    do_wrap = policy.get('alphaWrap', False)
    require(type(do_wrap) is bool, 'Explicit closure decision required')
    require(not do_wrap or (inspection.get('confirmedUnintendedOpening') is True
                            or inspection.get('confirmedShellDefect') is True), 'Do not repair an assumed opening')
    neck = neck_policy(policy.get('neck'), fit); work_dir = Path(output).parent
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
                  'frame': 'fit matrix @ GLB->NWN (x,-z,y): face +y, up +z', 'taper': None, 'seal': None,
                  'budget': {'total': budget, 'reservedForCap': budget-target, 'reductionTarget': target}}
    if neck is not None and neck['taper'] is not None:
        untapered = work_dir/'master-untapered.glb'; write_mesh(untapered, vertices, faces); begun = time.perf_counter()
        vertices, record['taper'] = neck_taper(vertices, faces, neck)
        record['taper'].update(untapered=pin(untapered), elapsedSeconds=time.perf_counter()-begun)
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
