"""Working-shell recovery on CPU: a closed shell rebuilt from the donor, stray specks dropped, non-manifold spots
repaired and an even isotropic remesh. Each returns new arrays and a report and refuses a result that is not one closed
outward solid (drop_specks reports it instead), so a bad shell never replaces a good one silently. Uses the bound
pymeshlab, libigl and SciPy (itemkit PYTHONPATH); nothing here runs Blender, the GPU or a generation job.
"""
import numpy as np

from tools.headkit.common import require
from .geometry import invalid_vertex_links, topology, weld

SUMMARY = ('triangles', 'degenerate', 'boundaryEdges', 'nonmanifoldEdges', 'invalidVertexLinks', 'closedWound', 'totalGenus',
           'signedVolume')


def summary(report):
    return {key: report[key] for key in SUMMARY}


def _components(faces, count):
    """A component label per face (faces sharing a welded vertex are connected)."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    f = np.asarray(faces, np.int64)
    edges = np.concatenate((f[:, [0, 1]], f[:, [1, 2]]))
    graph = coo_matrix((np.ones(len(edges)), (edges[:, 0], edges[:, 1])), shape=(count, count))
    _, labels = connected_components(graph, directed=False)
    return labels[f[:, 0]]


def _compact(vertices, faces):
    used = np.unique(faces); remap = -np.ones(len(vertices), np.int64); remap[used] = np.arange(len(used))
    return np.asarray(vertices)[used], remap[faces]


def _meshset(vertices, faces):
    import pymeshlab
    ms = pymeshlab.MeshSet(); ms.add_mesh(pymeshlab.Mesh(np.asarray(vertices, float), np.asarray(faces, np.int32))); return ms


def _arrays(ms):
    m = ms.current_mesh(); m.compact(); return m.vertex_matrix(), m.face_matrix().astype(np.int64)


def _closed(vertices, faces, what):
    report = topology(vertices, faces)
    require(report['closedWound'], f'{what}: not one closed outward solid ({summary(report)}); nothing written')
    return report


def shell_from_donor(vertices, faces, *, voxel=.001, faces_target=200000, dilate=1, erode=0, sigma=.8, taubin=5,
                     minimum_component=1000, maximum_voxels=50_000_000):     # about 1.2 GB of float64 grid coordinates
    """A closed exterior shell around the donor surface: rasterise it into voxels, dilate, flood-fill the outside,
    smooth the solid, marching cubes, clean, Taubin-smooth and decimate. The dilation pushes the surface outward by
    about `dilate` voxels; `erode` takes voxels back off the solid. Holes narrower than the dilation close."""
    import igl
    from scipy import ndimage
    v = np.asarray(vertices, float); f = np.asarray(faces, np.int64)
    require(0 < voxel <= .01 and 0 <= erode <= dilate <= 4 and 0 <= sigma <= 3 and 0 <= taubin <= 50, 'Bounded shell settings required')
    lo = v.min(0) - 6*voxel; dims = np.ceil((v.max(0) + 6*voxel - lo)/voxel).astype(int) + 1
    require(int(np.prod(dims)) <= maximum_voxels, f'{tuple(dims)} voxels exceed the {maximum_voxels:,} limit: use a larger voxel')
    occupied = np.zeros(dims, bool); tri = v[f]
    longest = np.linalg.norm(tri - np.roll(tri, 1, axis=1), axis=2).max(1)
    steps = np.clip(np.ceil(longest/(.5*voxel)).astype(int), 1, 40)          # samples at half-voxel spacing
    for k in np.unique(steps):
        chosen = tri[steps == k]
        for i in range(k + 1):
            for j in range(k + 1 - i):
                a, b = i/k, j/k; ix = np.floor((chosen[:, 0]*(1 - a - b) + chosen[:, 1]*a + chosen[:, 2]*b - lo)/voxel).astype(int)
                occupied[ix[:, 0], ix[:, 1], ix[:, 2]] = True
    structure = ndimage.generate_binary_structure(3, 3)
    if dilate: occupied = ndimage.binary_dilation(occupied, structure=structure, iterations=dilate)
    labels, _ = ndimage.label(~occupied); solid = labels != labels[0, 0, 0]
    if erode: solid = ndimage.binary_erosion(solid, structure=structure, iterations=erode)
    field = ndimage.gaussian_filter(solid.astype(np.float32), sigma=sigma) if sigma else solid.astype(np.float32)
    axes = [lo[i] + voxel*np.arange(dims[i]) for i in range(3)]
    grid = np.stack([g.ravel(order='F') for g in np.meshgrid(*axes, indexing='ij')], 1)
    sv, sf, _ = igl.marching_cubes(field.ravel(order='F').astype(np.float64), grid, int(dims[0]), int(dims[1]), int(dims[2]), .5)
    require(len(sf), 'Marching cubes found no surface')
    ms = _meshset(sv, sf)
    ms.meshing_remove_duplicate_vertices(); ms.meshing_remove_unreferenced_vertices()
    ms.meshing_remove_connected_component_by_face_number(mincomponentsize=minimum_component)
    ms.meshing_repair_non_manifold_edges(method='Remove Faces'); ms.meshing_repair_non_manifold_vertices(vertdispratio=0.0)
    ms.meshing_remove_unreferenced_vertices()
    if taubin: ms.apply_coord_taubin_smoothing(lambda_=.5, mu=-.53, stepsmoothnum=taubin)
    if ms.current_mesh().face_number() > faces_target:
        ms.meshing_decimation_quadric_edge_collapse(targetfacenum=faces_target, preservetopology=True, preserveboundary=True,
                                                    preservenormal=True, qualitythr=.3)
    ov, of = _arrays(ms)
    if topology(ov, of)['signedVolume'] < 0: of = of[:, ::-1].copy()
    report = _closed(ov, of, 'Donor shell')
    return ov, of, {'voxel': voxel, 'grid': dims.tolist(), 'solidVoxels': int(solid.sum()), 'dilate': dilate, 'erode': erode,
                    'sigma': sigma, 'taubin': taubin, 'after': summary(report)}


def drop_specks(vertices, faces, *, fraction=1e-6):
    """Drop components whose volume is under `fraction` of the largest (stray specks of an export)."""
    require(0 < fraction < .01, 'Bounded speck fraction required')
    v = np.asarray(vertices, float); f = np.asarray(faces, np.int64)
    unique, w = weld(v, f); labels = _components(w, len(unique)); tri = unique[w]
    volume = np.einsum('ij,ij->i', tri[:, 0], np.cross(tri[:, 1], tri[:, 2]))/6
    volumes = {int(k): float(volume[labels == k].sum()) for k in np.unique(labels)}
    largest = max(abs(x) for x in volumes.values()); keep = [k for k, x in volumes.items() if abs(x) >= fraction*largest]
    mask = np.isin(labels, keep); ov, of = _compact(v, f[mask])
    return ov, of, {'components': len(volumes), 'kept': len(keep), 'droppedVolumes': [x for k, x in volumes.items() if k not in keep],
                    'droppedTriangles': int((~mask).sum()), 'after': summary(topology(ov, of))}


def repair_nonmanifold(vertices, faces, *, rings=2, maximum_hole=200):
    """Remove `rings` rings of faces around every non-manifold vertex or edge, close the holes left and check the shell
    is one closed outward solid again."""
    require(1 <= rings <= 5 and 3 <= maximum_hole <= 2000, 'Bounded repair settings required')
    v = np.asarray(vertices, float); f = np.asarray(faces, np.int64); before = topology(v, f)
    unique, w = weld(v, f)
    edges = np.sort(np.concatenate((w[:, [0, 1]], w[:, [1, 2]], w[:, [2, 0]])), 1)
    _, inverse, uses = np.unique(edges[:, 0]*len(unique) + edges[:, 1], return_inverse=True, return_counts=True)
    bad = set(np.unique(edges[uses[inverse.ravel()] > 2]).tolist()) | set(invalid_vertex_links(w, len(unique)))
    if not bad: return v, f, {'badVertices': 0, 'removedFaces': 0, 'before': summary(before), 'after': summary(before), 'unchanged': True}
    ring = np.zeros(len(unique), bool); ring[list(bad)] = True
    for _ in range(rings): ring[np.unique(w[ring[w].any(1)])] = True
    drop = ring[w].any(1)
    ms = _meshset(unique, w[~drop]); ms.meshing_remove_unreferenced_vertices()
    ms.meshing_close_holes(maxholesize=maximum_hole, newfaceselected=False)
    ov, of = _arrays(ms); after = _closed(ov, of, 'Repaired shell')
    return ov, of, {'badVertices': len(bad), 'removedFaces': int(drop.sum()), 'before': summary(before), 'after': summary(after),
                    'volumeRatio': after['signedVolume']/before['signedVolume'], 'unchanged': False}


def remesh(vertices, faces, edge, *, taubin=0, iterations=8, feature_degrees=40):
    """Isotropic remesh to an even `edge` length (native units), with optional Taubin smoothing first; it must stay
    closed and outward, at the same genus and with no degenerate triangles."""
    import pymeshlab
    require(0 < edge < 1 and 0 <= taubin <= 50 and 1 <= iterations <= 30, 'Bounded remesh settings required')
    ms = _meshset(vertices, faces); ms.meshing_remove_duplicate_vertices()
    before = _closed(*_arrays(ms), 'Remesh input')
    if taubin: ms.apply_coord_taubin_smoothing(lambda_=.5, mu=-.53, stepsmoothnum=taubin)
    ms.meshing_isotropic_explicit_remeshing(iterations=iterations, targetlen=pymeshlab.PureValue(edge), featuredeg=feature_degrees,
                                            adaptive=False)
    ms.meshing_remove_unreferenced_vertices(); ov, of = _arrays(ms); after = _closed(ov, of, 'Remeshed shell')
    require(after['totalGenus'] == before['totalGenus'] and after['degenerate'] == 0,
            f'Remesh changed genus {before["totalGenus"]} -> {after["totalGenus"]} or left degenerate triangles')
    return ov, of, {'edge': edge, 'taubin': taubin, 'before': summary(before), 'after': summary(after),
                    'volumeRatio': after['signedVolume']/before['signedVolume']}
