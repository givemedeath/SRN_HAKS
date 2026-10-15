"""Seam coverage and penetration diagnostics, v16 (additive to v15, which stays unchanged).

Changes from v15:
* Penetration needs a closed, consistently oriented surface, not a 2-manifold: every geometric
  edge's directed uses must cancel. Non-manifold seams where submeshes meet (female pelvis, feet)
  keep a well-defined winding number, so the same solid-angle test applies. Submesh seams with
  gaps up to 0.1 mm count as joined for that edge test (reported per surface); positions are unchanged.
* Neck links: chest-neck and neck-head, measured on the assembly's own frames.
* A mesh lineage or topology difference makes only the affected link unavailable.
Diagnostic only: no anatomy, motion, native or client approval.
"""
import numpy as np
from .check_terminal_connectivity_v13 import LINKS
from .check_terminal_connectivity_v13b import source_controls, clipped_terminal_geometry
from .check_terminal_connectivity_v13c import triangle_minimum_distance
from .check_connector_surfaces_v15 import closest_surface, directional_coverage, inside_closed, quadrature, weighted_distribution

NECK_LINKS = (('chest', 'neck'), ('neck', 'head'))


def controls(left, right, frames):
    """Terminal bands: (start, end, distal) per part. Neck links use torso_g > neck_g > head_g."""
    p = lambda key: np.asarray(frames[key], float)[:3, 3]
    if (left, right) == ('chest', 'neck'):
        return (p('torso_g'), p('neck_g'), True), (p('neck_g'), p('head_g'), False), False
    if (left, right) == ('neck', 'head'):
        return (p('neck_g'), p('head_g'), True), (p('neck_g'), p('head_g'), False), False
    return source_controls(left, right, frames)


SEAM_TOLERANCE_METERS = 1e-4


def seam_representatives(positions, owners, tolerance):
    """Map each exact position to one representative. Positions closer than the tolerance are joined
    only when no mesh owns both, so a crack between submeshes closes and in-mesh detail never merges."""
    parent = list(range(len(positions)))
    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]; i = parent[i]
        return i
    cells = {}; joined = []
    for i, p in enumerate(positions):
        cells.setdefault(tuple(np.floor(p/tolerance).astype(int)), []).append(i)
    for (x, y, z), members in cells.items():
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    for j in cells.get((x+dx, y+dy, z+dz), ()):
                        for i in members:
                            if i < j and not owners[i] & owners[j]:
                                distance = float(np.linalg.norm(positions[i]-positions[j]))
                                if distance <= tolerance and find(i) != find(j):
                                    parent[find(i)] = find(j); joined.append(distance)
    return [find(i) for i in range(len(positions))], joined


def closed_oriented_triangles(meshes, part, tolerance=SEAM_TOLERANCE_METERS):
    """Rendered triangles of a part when every geometric edge's directed uses cancel; else None.

    Returns (triangles, report). Exact coincident positions across UV splits share an edge. Positions
    of different submeshes within the seam tolerance also share one, for this edge count only; the
    returned triangles and the winding number keep the exact positions, and no topology is welded."""
    triangles = []; owner = []
    for index, m in enumerate(meshes):
        if m['part'] != part or not m.get('render', True):
            continue
        tri = np.asarray(m['position'], float)[np.asarray(m['faces'], int)]; triangles.extend(tri); owner.extend([index]*len(tri))
    if not triangles:
        return None, {'part': part, 'status': 'absent'}
    triangles = np.asarray(triangles, float)
    exact = {}; owners = []
    for t, index in zip(triangles, owner):
        for v in t:
            key = tuple(v)
            if key not in exact:
                exact[key] = len(exact); owners.append(set())
            owners[exact[key]].add(index)
    def count(rep):
        edges = {}; collapsed = 0
        for t in triangles:
            ids = [rep[exact[tuple(v)]] for v in t]
            for i, j in ((0, 1), (1, 2), (2, 0)):
                a, b = ids[i], ids[j]
                if a == b:
                    collapsed += 1; continue
                edges.setdefault((min(a, b), max(a, b)), []).append(1 if a < b else -1)
        return edges, collapsed
    # Exact edges use the first-seen position order; only the cancellation sum matters.
    exact_edges, _ = count(list(range(len(exact))))
    exact_open = sum(1 for v in exact_edges.values() if sum(v) != 0)
    rep, joined = seam_representatives(np.array(list(exact)), owners, tolerance) if exact_open else (list(range(len(exact))), [])
    edges, collapsed = count(rep) if joined else (exact_edges, 0)
    open_edges = sum(1 for v in edges.values() if sum(v) != 0)
    non_manifold = sum(1 for v in edges.values() if len(v) != 2)
    report = {'part': part, 'edges': len(edges), 'unbalancedEdges': open_edges, 'nonManifoldEdges': non_manifold,
              'surface': 'open' if open_edges else ('closed-manifold' if not non_manifold else 'closed-oriented-nonmanifold'),
              'exactUnbalancedEdges': exact_open, 'seamToleranceMeters': tolerance, 'seamJoinedPositions': len(joined),
              'seamMaximumGapMeters': max(joined, default=0.), 'seamCollapsedEdgeUses': collapsed}
    return (None if open_edges or collapsed else triangles), report


def penetration(source_points, candidate_points, weights, source_closed, candidate_closed, scale, epsilon=1e-8):
    (s_tri, s_report), (c_tri, c_report) = source_closed, candidate_closed
    surfaces = {'source': s_report, 'candidate': c_report}
    if s_tri is None or c_tri is None:
        return {'status': 'unavailable', 'surfaces': surfaces,
                'reason': 'Opposite owning part has unbalanced (open) edges; solid penetration is undefined'}
    sd, _, _ = closest_surface(source_points, s_tri); cd, _, _ = closest_surface(candidate_points, c_tri)
    si = inside_closed(source_points, s_tri) & (sd > epsilon); ci = inside_closed(candidate_points, c_tri) & (cd > epsilon)
    source_depth = np.where(si, sd, 0.); candidate_depth = np.where(ci, cd, 0.); new = candidate_depth > scale*source_depth + epsilon
    return {'status': 'measured', 'surfaces': surfaces,
            'sourceInsideAreaFraction': float(weights[si].sum()/weights.sum()), 'candidateInsideAreaFraction': float(weights[ci].sum()/weights.sum()),
            'sourceCalibratedWorsenedPenetrationAreaFraction': float(weights[new].sum()/weights.sum()),
            'sourceDepthMeters': weighted_distribution(source_depth, weights), 'candidateDepthMeters': weighted_distribution(candidate_depth, weights),
            'limitations': 'Finite source surface samples inside the opposite closed oriented part (winding number); not collision resolution or anatomy approval'}


def lineage(source, candidate, parts):
    """Source and candidate meshes of these parts must match in name, render flag, vertex count and faces."""
    s = [m for m in source if m['part'] in parts]; c = [m for m in candidate if m['part'] in parts]
    if len(s) != len(c):
        raise ValueError('Mesh count differs for ' + '/'.join(parts))
    for a, b in zip(s, c):
        if (a['part'], a['name'], a.get('render', True)) != (b['part'], b['name'], b.get('render', True)) \
                or np.asarray(a['position']).shape != np.asarray(b['position']).shape or not np.array_equal(a['faces'], b['faces']):
            raise ValueError('Source-owned mesh/topology lineage differs for ' + a['part'])


def audit(source, candidate, source_frames, candidate_frames, part_scales=None, links=LINKS + NECK_LINKS):
    rows = []; scales = part_scales or {}; closed = {}
    for left, right in links:
        try:
            lineage(source, candidate, (left, right))
            ac, bc, fallback = controls(left, right, source_frames)
            sa, ca = clipped_terminal_geometry(source, candidate, left, ac); sb, cb = clipped_terminal_geometry(source, candidate, right, bc)
            scale = min(float(scales.get(left, 1.)), float(scales.get(right, 1.)))
            if not np.isfinite(scale) or scale <= 0:
                raise ValueError('Positive adjacent part scale required')
            directions = []
            for name, s, c, other_s, other_c, other_part in ((left, sa, ca, sb, cb, right), (right, sb, cb, sa, ca, left)):
                row = directional_coverage(s, c, other_s, other_c, scale); row['sampleOwner'] = name
                sp, cp, w = quadrature(s, c)
                if other_part not in closed:
                    closed[other_part] = (closed_oriented_triangles(source, other_part), closed_oriented_triangles(candidate, other_part))
                row['penetration'] = penetration(sp, cp, w, *closed[other_part], scale)
                directions.append(row)
            rows.append({'parts': [left, right], 'status': 'measured', 'sourceMinimumClearanceMeters': triangle_minimum_distance(sa, sb),
                         'candidateMinimumClearanceMeters': triangle_minimum_distance(ca, cb), 'directions': directions,
                         'coincidentTorsoPivotFallbackApplied': fallback, 'minimumContactAloneCertifiesCoverage': False})
        except (KeyError, ValueError) as error:
            rows.append({'parts': [left, right], 'status': 'unavailable', 'reason': str(error)})
    return {'kind': 'source-owned-area-seam-and-penetration-diagnostic-v16', 'connectors': rows,
            'links': [list(link) for link in links],
            'allRequestedConnectorsMeasured': all(r['status'] == 'measured' for r in rows),
            'sourceTerminalAuthority': 'Exact source native proximal/distal 25% clipped triangles with identical candidate barycentric transport; no candidate re-detection',
            'penetrationSurfacePolicy': 'closed oriented surface (directed edge uses cancel); non-manifold edges allowed; '
                                        'submesh seam gaps up to 0.1 mm count as joined for the edge test only',
            'candidateFramesUsedToRedetectTerminals': False, 'coverageAcceptanceThresholdInvented': False, 'rasterAllowanceAdded': False,
            'assetApprovalCreated': False, 'anatomyAcceptance': False, 'motionAcceptance': False, 'nativeValidated': False,
            'clientValidated': False, 'productionAccepted': False}
