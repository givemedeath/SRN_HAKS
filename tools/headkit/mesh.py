"""Exterior-shell audit, reviewed Alpha Wrap, and collision-blocking QSlim."""
from pathlib import Path
import numpy as np
from .common import require, positive, library, pin, verify, write
from .gltf import mesh, write_mesh
from .intersections import scan


def physical(vertices, faces):
    corners = np.asarray(vertices)[np.asarray(faces)]
    values, inverse = np.unique(corners.reshape(-1, 3), axis=0, return_inverse=True)
    return values, inverse.reshape(-1, 3)


def topology(vertices, faces):
    vertices, faces = physical(vertices, faces)
    edges = np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]])
    undirected = np.sort(edges, axis=1)
    _, inverse, counts = np.unique(undirected, axis=0, return_inverse=True, return_counts=True)
    orientation = np.zeros(len(counts), int)
    np.add.at(orientation, inverse, np.where(edges[:, 0] < edges[:, 1], 1, -1))
    corners = vertices[faces].astype(float)
    areas = np.linalg.norm(np.cross(corners[:, 1]-corners[:, 0], corners[:, 2]-corners[:, 0]), axis=1)
    boundary = int(np.count_nonzero(counts == 1)); nonmanifold = int(np.count_nonzero(counts > 2))
    winding = int(np.count_nonzero((counts == 2) & (orientation != 0)))
    # Every vertex link on the supported closed shell must be one simple cycle.
    link_edges = [[] for _ in vertices]
    for a, b, c in faces:
        link_edges[a].append((int(b), int(c))); link_edges[b].append((int(c), int(a))); link_edges[c].append((int(a), int(b)))
    bad_links = 0
    for rows in link_edges:
        graph = {}
        for a, b in rows: graph.setdefault(a, []).append(b); graph.setdefault(b, []).append(a)
        pending = set(graph); stack = [pending.pop()] if pending else []
        while stack:
            for other in graph[stack.pop()]:
                if other in pending: pending.remove(other); stack.append(other)
        bad_links += int(not graph or bool(pending) or any(len(v) != 2 for v in graph.values()))
    zeros = int(np.count_nonzero(areas <= 1e-14))
    return {'triangles': len(faces), 'physicalVertices': len(vertices), 'boundaryEdges': boundary,
            'nonmanifoldEdges': nonmanifold, 'windingConflicts': winding, 'zeroAreaFaces': zeros,
            'invalidVertexLinks': bad_links, 'closed': not (boundary or nonmanifold or winding or zeros or bad_links)}


def audit(path, max_pairs=4000000):
    value = mesh(path); vertices, faces = physical(value['positions'], value['faces'])
    top = topology(vertices, faces); crossings = scan(vertices, faces, max_pairs=max_pairs)
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


def repair(source, output, bindings, policy, inspection):
    """No assumed holes, no discs, no component deletion without an explicit selection."""
    require(inspection.get('sourceSha256') == pin(source)['sha256'] and inspection.get('visualReviewed') is True,
            'Hash-bound exterior/underside review required')
    do_wrap = policy.get('alphaWrap', False)
    require(type(do_wrap) is bool, 'Explicit closure decision required')
    require(not do_wrap or (inspection.get('confirmedUnintendedOpening') is True
                            or inspection.get('confirmedShellDefect') is True), 'Do not repair an assumed opening')
    original = mesh(source); vertices, faces = physical(original['positions'], original['faces'])
    if do_wrap:
        ml = library(bindings, 'pymeshlab'); diagonal = float(np.linalg.norm(np.ptp(vertices, axis=0)))
        alpha = positive(policy.get('alphaRelative', .005), 'Alpha Wrap alpha')
        offset = positive(policy.get('offsetRelative', .00025), 'Alpha Wrap offset')
        require(alpha <= .02 and offset <= .002, 'Wrap distances exceed supported profile')
        ms = ml.MeshSet(); ms.add_mesh(ml.Mesh(vertices.astype(float), faces.astype(np.int32)))
        ms.generate_alpha_wrap(alpha=ml.PureValue(diagonal*alpha), offset=ml.PureValue(diagonal*offset))
        current = ms.current_mesh(); current.compact(); vertices, faces = current.vertex_matrix(), current.face_matrix()
    else:
        require(topology(vertices, faces)['closed'], 'Open/invalid shell: review before selecting repair')
    budget = policy.get('triangleBudget', 20000)
    require(type(budget) is int and 4 <= budget <= 20000, 'Supported budget is <=20K')
    master = Path(output).parent / 'master.glb'; write_mesh(master, vertices, faces)
    master_audit = audit(master, max_pairs=16000000); write(Path(output).parent/'master-audit.json', master_audit, fresh=True)
    require(master_audit['passed'], 'Master has invalid topology or crossings; retain failure evidence')
    births = None
    if len(faces) > budget:
        import multiprocessing
        import tempfile
        work=Path(output).parent/'qslim.npz'
        context=multiprocessing.get_context('spawn')
        process=context.Process(target=_reduce_worker,args=(bindings,vertices,faces,budget,str(work)))
        process.start();process.join(600)
        if process.is_alive():
            process.terminate();process.join(15)
            raise TimeoutError('Owned QSlim child exceeded ten minutes; master and failed stage are preserved')
        require(process.exitcode==0 and work.is_file(),'QSlim worker failed; inspect its retained traceback')
        with np.load(work,allow_pickle=False) as archive:
            vertices,faces,face_birth,vertex_birth=[archive[k] for k in ('vertices','faces','faceBirth','vertexBirth')]
        require(0<len(faces)<=budget,'QSlim did not reach the declared budget')
        births=pin(work)
    write_mesh(output, vertices, faces); result = audit(output)
    require(result['passed'], 'Reduced float32 shell failed topology/collision checks')
    igl=library(bindings,'igl');reference=mesh(master);a,af=physical(reference['positions'],reference['faces'])
    z=mesh(output);c,cf=physical(z['positions'],z['faces']);diagonal=float(np.linalg.norm(np.ptp(a,axis=0)))
    d1=igl.point_mesh_squared_distance(np.asarray(a,float),np.asarray(c,float),np.asarray(cf,np.int32))[0]
    d2=igl.point_mesh_squared_distance(np.asarray(c,float),np.asarray(a,float),np.asarray(af,np.int32))[0]
    maximum=float(np.sqrt(max(d1.max(),d2.max()))/diagonal)
    limit=positive(policy.get('maximumRelativeSurfaceError',.004),'surface error bound')
    require(limit<=.025,'Surface bound exceeds declared supported profile')
    result['surfaceDistance']={'relativeMaximum':maximum,'limit':limit,'passed':maximum<=limit,
                              'method':'bidirectional vertices to exact triangles; not continuous Hausdorff'}
    write(Path(output).parent/'reduction-audit.json',result,fresh=True)
    require(maximum<=limit,'Reduction exceeds measured surface error limit; retain and review before changing policy')
    result.update(master=pin(master), ancestry=births, alphaWrapApplied=do_wrap, componentDeletion=False,
                  triangleBudget=budget, visualReviewRequired=True)
    return result


def _reduce_worker(bindings,vertices,faces,budget,path):
    igl=library(bindings,'igl')
    vertices,faces,face_birth,vertex_birth=igl.qslim(np.asfortranarray(vertices,dtype=np.float64),
        np.asfortranarray(faces,dtype=np.int32),budget,block_intersections=True)
    np.savez(path,vertices=vertices,faces=faces,faceBirth=face_birth,vertexBirth=vertex_birth)
